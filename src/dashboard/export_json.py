"""
Export gold-layer Parquet datasets to frontend-ready JSON files.

Converts aggregated gold KPIs into compact JSON for static Next.js dashboard
loading. Large datasets (basket/customer) are summarized — never exports
millions of raw rows.

Usage:
    python -m src.dashboard.export_json
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.utils.venv import ensure_virtual_env

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLD_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "gold"
INSIGHTS_JSON_PATH = PROJECT_ROOT / "data" / "ai_insights" / "insights.json"
INSIGHTS_TXT_PATH = PROJECT_ROOT / "data" / "ai_insights" / "insights.txt"
FRONTEND_DATA_DIR = PROJECT_ROOT / "frontend" / "public" / "data"

LOGGER_NAME = "retail_analytics.dashboard.export"
TOP_N_PRODUCTS = 500
TOP_N_CUSTOMERS = 50

GOLD_FILES = {
    "top_products": "gold_top_products",
    "reorder_metrics": "gold_reorder_metrics",
    "department_metrics": "gold_department_metrics",
    "basket_metrics": "gold_basket_metrics",
    "customer_metrics": "gold_customer_metrics",
}


class ExportError(Exception):
    """Raised when JSON export cannot proceed."""


def setup_logging(level: int = logging.INFO) -> logging.Logger:
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_gold_parquet(gold_dir: Path, dataset_name: str, logger: logging.Logger) -> pd.DataFrame:
    path = gold_dir / dataset_name
    if not path.exists():
        raise ExportError(
            f"Gold dataset not found: {path}. Run: python -m src.gold.gold_transform"
        )
    logger.info("Reading %s", path)
    return pd.read_parquet(path)


def round_floats(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for row in records:
        for key, value in row.items():
            if isinstance(value, float):
                row[key] = round(value, 4)
    return records


def export_top_products(df: pd.DataFrame, last_updated: str) -> Dict[str, Any]:
    sorted_df = df.sort_values("total_orders", ascending=False).head(TOP_N_PRODUCTS)
    return {
        "last_updated": last_updated,
        "total_products": int(df["product_id"].nunique()),
        "products": round_floats(sorted_df.to_dict(orient="records")),
    }


def export_reorder_metrics(df: pd.DataFrame, last_updated: str) -> Dict[str, Any]:
    sorted_df = df.sort_values("reorder_rate", ascending=False).head(TOP_N_PRODUCTS)
    return {
        "last_updated": last_updated,
        "total_products": int(df["product_id"].nunique()),
        "products": round_floats(sorted_df.to_dict(orient="records")),
    }


def export_department_metrics(df: pd.DataFrame, last_updated: str) -> Dict[str, Any]:
    sorted_df = df.sort_values("total_products_sold", ascending=False)
    return {
        "last_updated": last_updated,
        "total_departments": int(df["department"].nunique()),
        "departments": round_floats(sorted_df.to_dict(orient="records")),
    }


def export_basket_metrics(df: pd.DataFrame, last_updated: str) -> Dict[str, Any]:
    bins = [1, 2, 3, 5, 10, 20, 50, 100, float("inf")]
    labels = ["1", "2", "3-4", "5-9", "10-19", "20-49", "50-99", "100+"]
    bucketed = pd.cut(df["basket_size"], bins=bins, labels=labels, right=False)
    distribution = [
        {"bucket": str(label), "orders": int(count)}
        for label, count in bucketed.value_counts().sort_index().items()
    ]
    return {
        "last_updated": last_updated,
        "summary": {
            "total_orders": int(df["order_id"].nunique()),
            "total_line_items": int(df["basket_size"].sum()),
            "mean_basket_size": round(float(df["basket_size"].mean()), 2),
            "median_basket_size": round(float(df["basket_size"].median()), 2),
            "min_basket_size": int(df["basket_size"].min()),
            "max_basket_size": int(df["basket_size"].max()),
            "std_basket_size": round(float(df["basket_size"].std()), 2),
        },
        "distribution": distribution,
    }


def export_customer_metrics(df: pd.DataFrame, last_updated: str) -> Dict[str, Any]:
    def segment(row: pd.Series) -> str:
        orders = row["total_orders"]
        if orders == 1:
            return "Single Order"
        if orders <= 5:
            return "Occasional (2-5)"
        if orders <= 10:
            return "Regular (6-10)"
        if orders <= 20:
            return "Loyal (11-20)"
        return "Power User (21+)"

    segmented = df.copy()
    segmented["segment"] = segmented.apply(segment, axis=1)
    seg_counts = segmented.groupby("segment").agg(
        customers=("user_id", "count"),
        avg_basket_size=("avg_basket_size", "mean"),
        avg_products=("total_products", "mean"),
    ).reset_index()
    total = len(df)
    segmentation = [
        {
            "segment": row["segment"],
            "customers": int(row["customers"]),
            "percentage": round(row["customers"] / total * 100, 2),
            "avg_basket_size": round(float(row["avg_basket_size"]), 2),
            "avg_products": round(float(row["avg_products"]), 2),
        }
        for _, row in seg_counts.iterrows()
    ]
    order_freq = [
        {"orders": int(k), "customers": int(v)}
        for k, v in df["total_orders"].value_counts().sort_index().head(15).items()
    ]
    top_customers = round_floats(
        df.sort_values("total_orders", ascending=False)
        .head(TOP_N_CUSTOMERS)
        .to_dict(orient="records")
    )
    return {
        "last_updated": last_updated,
        "summary": {
            "total_customers": int(df["user_id"].nunique()),
            "avg_orders_per_customer": round(float(df["total_orders"].mean()), 2),
            "median_orders_per_customer": round(float(df["total_orders"].median()), 2),
            "avg_products_per_customer": round(float(df["total_products"].mean()), 2),
            "avg_basket_size": round(float(df["avg_basket_size"].mean()), 2),
            "single_order_customer_pct": round(
                float((df["total_orders"] == 1).mean() * 100), 2
            ),
            "power_user_pct": round(
                float((df["total_orders"] >= 21).mean() * 100), 2
            ),
        },
        "segmentation": segmentation,
        "order_frequency": order_freq,
        "top_customers": top_customers,
    }


def parse_insight_sections(markdown_text: str) -> Dict[str, str]:
    """Split Gemini markdown output into named sections."""
    sections: Dict[str, str] = {}
    current_key = "introduction"
    current_lines: List[str] = []

    for line in markdown_text.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = (
                line[3:].strip().lower().replace(" ", "_").replace("-", "_")
            )
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


def extract_recommendations(text: str) -> List[str]:
    """Pull numbered recommendations from the recommendations section."""
    recs = re.findall(r"^\s*\d+[\.\)]\s*(.+)$", text, re.MULTILINE)
    return [r.strip() for r in recs if r.strip()]


def export_ai_insights(last_updated: str, logger: logging.Logger) -> Dict[str, Any]:
    if not INSIGHTS_JSON_PATH.exists():
        raise ExportError(
            f"AI insights not found: {INSIGHTS_JSON_PATH}. "
            "Run: python -m src.ai.run_ai_insights"
        )

    payload = json.loads(INSIGHTS_JSON_PATH.read_text(encoding="utf-8"))
    full_text = payload.get("executive_insights", "")
    if INSIGHTS_TXT_PATH.exists():
        full_text = INSIGHTS_TXT_PATH.read_text(encoding="utf-8")

    sections = parse_insight_sections(full_text)
    recommendations = extract_recommendations(
        sections.get("key_business_recommendations", full_text)
    )

    return {
        "last_updated": payload.get("generated_at", last_updated),
        "model": payload.get("model", "unknown"),
        "executive_summary": sections.get("executive_summary", full_text[:500]),
        "sections": sections,
        "recommendations": recommendations,
        "full_text": full_text,
        "kpi_overview": payload.get("kpi_summary", {}).get("dataset_overview", {}),
    }


def write_json(path: Path, data: Dict[str, Any], logger: logging.Logger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote %s", path)


def run_export(
    gold_dir: Path | None = None,
    output_dir: Path | None = None,
) -> Dict[str, Path]:
    logger = setup_logging()
    gold_path = gold_dir or GOLD_DATA_DIR
    out_path = output_dir or FRONTEND_DATA_DIR
    last_updated = utc_now_iso()

    logger.info("Starting JSON export for dashboard")
    logger.info("Gold directory: %s", gold_path)
    logger.info("Output directory: %s", out_path)

    try:
        top_products_df = read_gold_parquet(gold_path, GOLD_FILES["top_products"], logger)
        reorder_df = read_gold_parquet(gold_path, GOLD_FILES["reorder_metrics"], logger)
        dept_df = read_gold_parquet(gold_path, GOLD_FILES["department_metrics"], logger)
        basket_df = read_gold_parquet(gold_path, GOLD_FILES["basket_metrics"], logger)
        customer_df = read_gold_parquet(gold_path, GOLD_FILES["customer_metrics"], logger)

        exports = {
            "top_products.json": export_top_products(top_products_df, last_updated),
            "reorder_metrics.json": export_reorder_metrics(reorder_df, last_updated),
            "department_metrics.json": export_department_metrics(dept_df, last_updated),
            "basket_metrics.json": export_basket_metrics(basket_df, last_updated),
            "customer_metrics.json": export_customer_metrics(customer_df, last_updated),
            "ai_insights.json": export_ai_insights(last_updated, logger),
        }

        written: Dict[str, Path] = {}
        for filename, data in exports.items():
            target = out_path / filename
            write_json(target, data, logger)
            written[filename] = target

        logger.info("Export completed | files=%d", len(written))
        return written

    except ExportError:
        raise
    except Exception as exc:
        logger.exception("Unexpected export error")
        raise ExportError(f"Export failed: {exc}") from exc


def main() -> int:
    logger = setup_logging()
    try:
        ensure_virtual_env()
        run_export()
        print("\nDashboard JSON files exported to frontend/public/data/")
        return 0
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    except ExportError as exc:
        logger.error("Export aborted: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
