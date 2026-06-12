"""
PySpark gold-layer transformations for Instacart retail analytics.

Reads silver Parquet datasets and produces business-ready KPI tables for
product performance, department sales, customer behavior, basket analysis,
and reorder analytics.

Design principles (32M+ rows):
- Column-pruned reads from retail_transactions (single silver fact table)
- One aggregation pass per KPI grain (product, department, order/customer)
- No collect() or toPandas() — all operations stay distributed
- Broadcast joins only where a small dimension is needed (not required here
  because retail_transactions is already denormalized in silver)
- Reuse order-level aggregation for both basket and customer metrics
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

from src.utils.venv import ensure_virtual_env

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SILVER_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "silver"
GOLD_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "gold"

DEFAULT_APP_NAME = "InstacartRetailGoldTransform"
LOGGER_NAME = "retail_analytics.gold"

# Silver inputs required to build all gold KPIs.
SILVER_RETAIL_TRANSACTIONS = "retail_transactions"

# Explicit gold output schemas for validation before write.
GOLD_SCHEMAS: Dict[str, StructType] = {
    "gold_top_products": StructType(
        [
            StructField("product_id", LongType(), nullable=False),
            StructField("product_name", StringType(), nullable=False),
            StructField("total_orders", LongType(), nullable=False),
            StructField("total_reorders", LongType(), nullable=False),
            StructField("reorder_rate", DoubleType(), nullable=False),
        ]
    ),
    "gold_department_metrics": StructType(
        [
            StructField("department", StringType(), nullable=False),
            StructField("total_products_sold", LongType(), nullable=False),
            StructField("unique_customers", LongType(), nullable=False),
        ]
    ),
    "gold_customer_metrics": StructType(
        [
            StructField("user_id", LongType(), nullable=False),
            StructField("total_orders", LongType(), nullable=False),
            StructField("total_products", LongType(), nullable=False),
            StructField("avg_basket_size", DoubleType(), nullable=False),
        ]
    ),
    "gold_basket_metrics": StructType(
        [
            StructField("order_id", LongType(), nullable=False),
            StructField("basket_size", IntegerType(), nullable=False),
        ]
    ),
    "gold_reorder_metrics": StructType(
        [
            StructField("product_id", LongType(), nullable=False),
            StructField("product_name", StringType(), nullable=False),
            StructField("reorder_rate", DoubleType(), nullable=False),
        ]
    ),
}


class GoldTransformError(Exception):
    """Raised when gold-layer transformation cannot proceed."""


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the module logger."""
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


def create_spark_session(
    app_name: str = DEFAULT_APP_NAME,
    master: str | None = None,
) -> SparkSession:
    """Create a SparkSession tuned for silver-to-gold aggregation on 32M+ rows."""
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.driver.memory", "3g")
        .config("spark.executor.memory", "3g")
        .config("spark.sql.shuffle.partitions", "100")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.autoBroadcastJoinThreshold", "64m")
        .config("spark.sql.files.maxPartitionBytes", "67108864")
    )
    if master:
        builder = builder.master(master)

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def validate_silver_path(path: Path, dataset_name: str) -> None:
    """Ensure a silver Parquet dataset directory exists."""
    if not path.exists():
        raise GoldTransformError(f"Silver dataset not found: {dataset_name} at {path}")
    if not path.is_dir():
        raise GoldTransformError(f"Silver path is not a directory: {path}")


def read_silver_parquet(
    spark: SparkSession,
    silver_dir: Path,
    dataset_name: str,
    logger: logging.Logger,
    columns: List[str] | None = None,
) -> DataFrame:
    """
    Read a silver Parquet dataset with optional column pruning.

    Column pruning reduces I/O and memory when scanning 32M+ row facts.
    """
    dataset_path = silver_dir / dataset_name
    validate_silver_path(dataset_path, dataset_name)
    logger.info("Reading silver dataset '%s' from %s", dataset_name, dataset_path)
    try:
        reader = spark.read.parquet(str(dataset_path))
        if columns:
            return reader.select(*columns)
        return reader
    except Exception as exc:
        raise GoldTransformError(
            f"Failed to read silver dataset '{dataset_name}': {exc}"
        ) from exc


def read_retail_transactions_fact(
    spark: SparkSession,
    silver_dir: Path,
    logger: logging.Logger,
) -> DataFrame:
    """
    Load the denormalized silver fact table with only columns needed for gold KPIs.

    retail_transactions already contains product, department, and order context
    from silver — avoids re-joining 32M rows to dimension tables.
    """
    return read_silver_parquet(
        spark,
        silver_dir,
        SILVER_RETAIL_TRANSACTIONS,
        logger,
        columns=[
            "order_id",
            "user_id",
            "product_id",
            "product_name",
            "department",
            "reordered",
        ],
    )


def build_product_aggregates(fact_df: DataFrame) -> DataFrame:
    """
    Aggregate product-level order and reorder KPIs in a single shuffle.

    Each row in retail_transactions is one product line in an order:
    - total_orders     = number of times the product appeared in any basket
    - total_reorders   = count where reordered = 1
    - reorder_rate     = total_reorders / total_orders
    """
    return (
        fact_df.groupBy("product_id", "product_name")
        .agg(
            F.count(F.lit(1)).alias("total_orders"),
            F.sum(F.col("reordered").cast("long")).alias("total_reorders"),
        )
        .withColumn(
            "reorder_rate",
            F.when(
                F.col("total_orders") > 0,
                F.col("total_reorders") / F.col("total_orders"),
            ).otherwise(F.lit(0.0)),
        )
    )


def build_gold_top_products(product_agg: DataFrame) -> DataFrame:
    """
    Business KPI: product popularity and reorder performance.

    Sorted by total_orders descending so top sellers appear first in BI tools.
    """
    return product_agg.select(
        "product_id",
        "product_name",
        "total_orders",
        "total_reorders",
        "reorder_rate",
    ).orderBy(F.desc("total_orders"))


def build_gold_reorder_metrics(product_agg: DataFrame) -> DataFrame:
    """
    Business KPI: reorder rate per product (subset of product aggregates).

    Reuses product_agg to avoid a second full scan of retail_transactions.
    """
    return product_agg.select(
        "product_id",
        "product_name",
        "reorder_rate",
    ).orderBy(F.desc("reorder_rate"))


def build_gold_department_metrics(fact_df: DataFrame) -> DataFrame:
    """
    Business KPI: department-level sales volume and customer reach.

    - total_products_sold = line-item count per department
    - unique_customers    = distinct users who purchased from the department
    """
    return (
        fact_df.filter(F.col("department").isNotNull())
        .groupBy("department")
        .agg(
            F.count(F.lit(1)).alias("total_products_sold"),
            F.countDistinct("user_id").alias("unique_customers"),
        )
        .orderBy(F.desc("total_products_sold"))
    )


def build_order_level_metrics(fact_df: DataFrame) -> DataFrame:
    """
    Aggregate to order grain in one shuffle pass.

    Produces basket_size per order and preserves user_id for customer KPIs.
    This intermediate powers both gold_basket_metrics and gold_customer_metrics
    without scanning retail_transactions twice.
    """
    return fact_df.groupBy("order_id", "user_id").agg(
        F.count(F.lit(1)).alias("basket_size")
    )


def build_gold_basket_metrics(order_level: DataFrame) -> DataFrame:
    """Business KPI: number of products per order (basket size)."""
    return order_level.select("order_id", "basket_size")


def build_gold_customer_metrics(order_level: DataFrame) -> DataFrame:
    """
    Business KPI: per-customer purchasing behavior.

    Derived from order_level (not the 32M fact) — ~3.4M orders, cheap to shuffle:
    - total_orders    = number of orders placed by the customer
    - total_products  = sum of basket sizes across all orders
    - avg_basket_size = mean products per order
    """
    return (
        order_level.groupBy("user_id")
        .agg(
            F.count(F.lit(1)).alias("total_orders"),
            F.sum("basket_size").alias("total_products"),
            F.avg("basket_size").alias("avg_basket_size"),
        )
        .orderBy(F.desc("total_orders"))
    )


def validate_gold_schema(df: DataFrame, dataset_name: str) -> None:
    """Verify output columns match the expected gold schema before write."""
    expected = {field.name for field in GOLD_SCHEMAS[dataset_name].fields}
    actual = set(df.columns)
    missing = expected - actual
    if missing:
        raise GoldTransformError(
            f"Gold dataset '{dataset_name}' missing columns: {sorted(missing)}"
        )


def write_gold_parquet(
    df: DataFrame,
    output_dir: Path,
    dataset_name: str,
    logger: logging.Logger,
) -> None:
    """Persist a gold DataFrame as Parquet with schema validation."""
    validate_gold_schema(df, dataset_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Writing gold dataset '%s' to %s", dataset_name, output_dir)
    try:
        df.write.mode("overwrite").parquet(str(output_dir))
        print(f"{dataset_name}: written to {output_dir}")
    except Exception as exc:
        raise GoldTransformError(
            f"Failed to write gold dataset '{dataset_name}' to {output_dir}: {exc}"
        ) from exc


def run_gold_transform(
    silver_dir: Path | None = None,
    gold_dir: Path | None = None,
    app_name: str = DEFAULT_APP_NAME,
    master: str | None = None,
) -> Dict[str, str]:
    """
    Execute the full silver-to-gold transformation pipeline.

    Pipeline stages (3 scans of the fact table):
      1. Product aggregates  → gold_top_products, gold_reorder_metrics
      2. Department aggregates → gold_department_metrics
      3. Order-level aggregates → gold_basket_metrics, gold_customer_metrics

    Returns:
        Mapping of gold dataset name to output path.
    """
    logger = setup_logging()
    silver_path = silver_dir or SILVER_DATA_DIR
    gold_path = gold_dir or GOLD_DATA_DIR
    output_paths: Dict[str, str] = {}
    spark: Optional[SparkSession] = None

    logger.info("Starting gold transformation")
    logger.info("Silver directory: %s", silver_path)
    logger.info("Gold directory: %s", gold_path)

    try:
        spark = create_spark_session(app_name=app_name, master=master)
        fact_df = read_retail_transactions_fact(spark, silver_path, logger)

        # ── Stage 1: product KPIs (one scan → two gold tables) ──
        logger.info("Building product-level gold datasets")
        product_agg = build_product_aggregates(fact_df)

        gold_top_products = build_gold_top_products(product_agg)
        write_gold_parquet(
            gold_top_products,
            gold_path / "gold_top_products",
            "gold_top_products",
            logger,
        )
        output_paths["gold_top_products"] = str(gold_path / "gold_top_products")

        gold_reorder_metrics = build_gold_reorder_metrics(product_agg)
        write_gold_parquet(
            gold_reorder_metrics,
            gold_path / "gold_reorder_metrics",
            "gold_reorder_metrics",
            logger,
        )
        output_paths["gold_reorder_metrics"] = str(gold_path / "gold_reorder_metrics")
        del product_agg, gold_top_products, gold_reorder_metrics

        # ── Stage 2: department KPIs (one scan) ──
        logger.info("Building department-level gold dataset")
        gold_department_metrics = build_gold_department_metrics(fact_df)
        write_gold_parquet(
            gold_department_metrics,
            gold_path / "gold_department_metrics",
            "gold_department_metrics",
            logger,
        )
        output_paths["gold_department_metrics"] = str(
            gold_path / "gold_department_metrics"
        )
        del gold_department_metrics

        # ── Stage 3: order/customer KPIs (one scan → two gold tables) ──
        logger.info("Building basket and customer gold datasets")
        order_level = build_order_level_metrics(fact_df)
        del fact_df

        gold_basket_metrics = build_gold_basket_metrics(order_level)
        write_gold_parquet(
            gold_basket_metrics,
            gold_path / "gold_basket_metrics",
            "gold_basket_metrics",
            logger,
        )
        output_paths["gold_basket_metrics"] = str(gold_path / "gold_basket_metrics")
        del gold_basket_metrics

        gold_customer_metrics = build_gold_customer_metrics(order_level)
        write_gold_parquet(
            gold_customer_metrics,
            gold_path / "gold_customer_metrics",
            "gold_customer_metrics",
            logger,
        )
        output_paths["gold_customer_metrics"] = str(
            gold_path / "gold_customer_metrics"
        )
        del order_level, gold_customer_metrics

        logger.info(
            "Gold transformation completed successfully | datasets=%d",
            len(output_paths),
        )
        return output_paths

    except GoldTransformError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during gold transformation")
        raise GoldTransformError(f"Gold pipeline failed: {exc}") from exc
    finally:
        if spark is not None:
            spark.stop()
            logger.info("SparkSession stopped")


def main() -> int:
    """CLI entry point."""
    logger = setup_logging()
    try:
        ensure_virtual_env()
        run_gold_transform()
        return 0
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    except GoldTransformError as exc:
        logger.error("Gold transformation aborted: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
