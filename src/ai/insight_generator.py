"""
Insight generator: loads gold-layer KPIs and produces AI-powered business insights.

Uses Pandas to read small aggregated gold Parquet files (not the 32M-row fact
table). Summaries are condensed before sending to Gemini to stay within token
limits and avoid leaking raw PII-scale data.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.ai.gemini_client import GeminiClient, GeminiClientError
from src.ai.prompt_templates import (
    EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
    EXECUTIVE_SUMMARY_USER_TEMPLATE,
)

LOGGER_NAME = "retail_analytics.ai.generator"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLD_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "gold"
INSIGHTS_OUTPUT_DIR = PROJECT_ROOT / "data" / "ai_insights"

GOLD_DATASETS = (
    "gold_top_products",
    "gold_reorder_metrics",
    "gold_department_metrics",
    "gold_basket_metrics",
    "gold_customer_metrics",
)

TOP_N = 10


class InsightGeneratorError(Exception):
    """Raised when insight generation cannot proceed."""


@dataclass(frozen=True)
class GoldDataBundle:
    """Container for all loaded gold-layer DataFrames."""

    top_products: pd.DataFrame
    reorder_metrics: pd.DataFrame
    department_metrics: pd.DataFrame
    basket_metrics: pd.DataFrame
    customer_metrics: pd.DataFrame


@dataclass(frozen=True)
class InsightResult:
    """Structured output from the AI insights pipeline."""

    generated_at: str
    model_name: str
    kpi_summary: Dict[str, Any]
    executive_insights: str
    output_json_path: Path
    output_txt_path: Path


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the module logger."""
    import sys

    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def validate_gold_path(path: Path, dataset_name: str) -> None:
    """Ensure a gold Parquet dataset directory exists."""
    if not path.exists():
        raise InsightGeneratorError(
            f"Gold dataset not found: {dataset_name} at {path}. "
            "Run the gold transform first: python -m src.gold.gold_transform"
        )


def load_gold_parquet(gold_dir: Path, dataset_name: str, logger: logging.Logger) -> pd.DataFrame:
    """Read a single gold Parquet dataset with Pandas."""
    dataset_path = gold_dir / dataset_name
    validate_gold_path(dataset_path, dataset_name)
    logger.info("Loading gold dataset '%s' from %s", dataset_name, dataset_path)
    try:
        return pd.read_parquet(dataset_path)
    except Exception as exc:
        raise InsightGeneratorError(
            f"Failed to read gold dataset '{dataset_name}': {exc}"
        ) from exc


def load_all_gold_data(gold_dir: Path, logger: logging.Logger) -> GoldDataBundle:
    """Load all five gold KPI datasets."""
    for name in GOLD_DATASETS:
        validate_gold_path(gold_dir / name, name)

    return GoldDataBundle(
        top_products=load_gold_parquet(gold_dir, "gold_top_products", logger),
        reorder_metrics=load_gold_parquet(gold_dir, "gold_reorder_metrics", logger),
        department_metrics=load_gold_parquet(
            gold_dir, "gold_department_metrics", logger
        ),
        basket_metrics=load_gold_parquet(gold_dir, "gold_basket_metrics", logger),
        customer_metrics=load_gold_parquet(gold_dir, "gold_customer_metrics", logger),
    )


def _df_records(df: pd.DataFrame, n: int = TOP_N) -> List[Dict[str, Any]]:
    """Convert top-N DataFrame rows to JSON-serializable records."""
    sample = df.head(n).copy()
    for col in sample.select_dtypes(include=["float"]).columns:
        sample[col] = sample[col].round(4)
    return sample.to_dict(orient="records")


def _basket_distribution(df: pd.DataFrame) -> Dict[str, int]:
    """Bucket basket sizes for compact LLM context."""
    bins = [1, 2, 3, 5, 10, 20, 50, 100, float("inf")]
    labels = ["1", "2", "3-4", "5-9", "10-19", "20-49", "50-99", "100+"]
    bucketed = pd.cut(df["basket_size"], bins=bins, labels=labels, right=False)
    counts = bucketed.value_counts().sort_index()
    return {str(k): int(v) for k, v in counts.items()}


def build_kpi_summary(bundle: GoldDataBundle, logger: logging.Logger) -> Dict[str, Any]:
    """
    Build a compact KPI summary dict for Gemini prompts.

    Aggregates large datasets (3M+ basket rows, 200K+ customers) into
    statistics and top-N slices — never sends full tables to the API.
    """
    logger.info("Building KPI summary for AI prompt")

    top_products = bundle.top_products
    reorder = bundle.reorder_metrics
    departments = bundle.department_metrics
    baskets = bundle.basket_metrics
    customers = bundle.customer_metrics

    summary: Dict[str, Any] = {
        "dataset_overview": {
            "total_unique_products": int(top_products["product_id"].nunique()),
            "total_departments": int(departments["department"].nunique()),
            "total_orders": int(baskets["order_id"].nunique()),
            "total_customers": int(customers["user_id"].nunique()),
            "total_line_items": int(baskets["basket_size"].sum()),
        },
        "top_performing_products": {
            "description": f"Top {TOP_N} products by total order volume",
            "products": _df_records(
                top_products.sort_values("total_orders", ascending=False)
            ),
        },
        "most_reordered_products": {
            "description": f"Top {TOP_N} products by reorder rate",
            "products": _df_records(
                reorder.sort_values("reorder_rate", ascending=False)
            ),
        },
        "best_performing_departments": {
            "description": f"Top {TOP_N} departments by products sold",
            "departments": _df_records(
                departments.sort_values("total_products_sold", ascending=False)
            ),
        },
        "basket_size_analysis": {
            "mean_basket_size": round(float(baskets["basket_size"].mean()), 2),
            "median_basket_size": round(float(baskets["basket_size"].median()), 2),
            "min_basket_size": int(baskets["basket_size"].min()),
            "max_basket_size": int(baskets["basket_size"].max()),
            "std_basket_size": round(float(baskets["basket_size"].std()), 2),
            "distribution_by_size_bucket": _basket_distribution(baskets),
        },
        "customer_purchasing_trends": {
            "avg_orders_per_customer": round(
                float(customers["total_orders"].mean()), 2
            ),
            "avg_products_per_customer": round(
                float(customers["total_products"].mean()), 2
            ),
            "avg_basket_size_per_customer": round(
                float(customers["avg_basket_size"].mean()), 2
            ),
            "median_orders_per_customer": round(
                float(customers["total_orders"].median()), 2
            ),
            "top_customers_by_orders": _df_records(
                customers.sort_values("total_orders", ascending=False),
                n=5,
            ),
            "customers_with_single_order_pct": round(
                float((customers["total_orders"] == 1).mean() * 100), 2
            ),
            "customers_with_10plus_orders_pct": round(
                float((customers["total_orders"] >= 10).mean() * 100), 2
            ),
        },
        "reorder_highlights": {
            "overall_avg_reorder_rate": round(
                float(top_products["reorder_rate"].mean()), 4
            ),
            "products_with_reorder_rate_above_50pct": int(
                (top_products["reorder_rate"] > 0.5).sum()
            ),
            "top_reorder_rate_products": _df_records(
                reorder.sort_values("reorder_rate", ascending=False)
            ),
        },
    }

    logger.info(
        "KPI summary built | products=%d | departments=%d | customers=%d",
        summary["dataset_overview"]["total_unique_products"],
        summary["dataset_overview"]["total_departments"],
        summary["dataset_overview"]["total_customers"],
    )
    return summary


def generate_executive_insights(
    kpi_summary: Dict[str, Any],
    gemini_client: GeminiClient,
    logger: logging.Logger,
) -> str:
    """Call Gemini to produce executive-summary insights from KPI data."""
    kpi_json = json.dumps(kpi_summary, indent=2, default=str)
    user_prompt = EXECUTIVE_SUMMARY_USER_TEMPLATE.substitute(kpi_summary=kpi_json)

    logger.info("Requesting executive insights from Gemini")
    try:
        return gemini_client.generate(
            user_prompt=user_prompt,
            system_prompt=EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
        )
    except GeminiClientError:
        raise
    except Exception as exc:
        raise InsightGeneratorError(
            f"Failed to generate insights from Gemini: {exc}"
        ) from exc


def save_insights(
    result_data: Dict[str, Any],
    insights_text: str,
    output_dir: Path,
    logger: logging.Logger,
) -> tuple[Path, Path]:
    """Persist insights as JSON (structured) and TXT (human-readable)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "insights.json"
    txt_path = output_dir / "insights.txt"

    try:
        json_path.write_text(
            json.dumps(result_data, indent=2, default=str),
            encoding="utf-8",
        )
        txt_path.write_text(insights_text, encoding="utf-8")
    except Exception as exc:
        raise InsightGeneratorError(f"Failed to save insights: {exc}") from exc

    logger.info("Saved insights JSON to %s", json_path)
    logger.info("Saved insights TXT to %s", txt_path)
    return json_path, txt_path


def run_insight_generation(
    gold_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    gemini_client: Optional[GeminiClient] = None,
    logger: Optional[logging.Logger] = None,
) -> InsightResult:
    """
    Execute the full gold-to-insights pipeline.

    1. Load gold Parquet KPIs with Pandas
    2. Build compact KPI summary
    3. Generate executive insights via Gemini
    4. Save insights.json and insights.txt
    """
    log = logger or setup_logging()
    gold_path = gold_dir or GOLD_DATA_DIR
    out_path = output_dir or INSIGHTS_OUTPUT_DIR

    log.info("Starting AI insight generation")
    log.info("Gold directory: %s", gold_path)
    log.info("Output directory: %s", out_path)

    try:
        bundle = load_all_gold_data(gold_path, log)
        kpi_summary = build_kpi_summary(bundle, log)

        model_name = "unknown"
        if gemini_client is None:
            from src.ai.gemini_client import GeminiClient, load_gemini_config

            config = load_gemini_config()
            model_name = config.model_name
            gemini_client = GeminiClient(config, logger=log)
            gemini_client.health_check()
        else:
            model_name = gemini_client.model_name

        executive_insights = generate_executive_insights(
            kpi_summary, gemini_client, log
        )

        generated_at = datetime.now(timezone.utc).isoformat()
        result_payload = {
            "generated_at": generated_at,
            "model": model_name,
            "source": "gold_layer",
            "gold_datasets": list(GOLD_DATASETS),
            "kpi_summary": kpi_summary,
            "executive_insights": executive_insights,
        }

        json_path, txt_path = save_insights(
            result_payload, executive_insights, out_path, log
        )

        log.info("AI insight generation completed successfully")
        return InsightResult(
            generated_at=generated_at,
            model_name=model_name,
            kpi_summary=kpi_summary,
            executive_insights=executive_insights,
            output_json_path=json_path,
            output_txt_path=txt_path,
        )

    except InsightGeneratorError:
        raise
    except GeminiClientError:
        raise
    except Exception as exc:
        log.exception("Unexpected error during insight generation")
        raise InsightGeneratorError(f"Insight pipeline failed: {exc}") from exc
