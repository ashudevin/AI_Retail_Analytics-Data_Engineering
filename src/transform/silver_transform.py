"""
PySpark silver-layer transformations for Instacart retail analytics.

Reads bronze Parquet datasets, runs data-quality checks, cleans and standardizes
dimensions/facts, merges order-product splits, builds retail_transactions, and
writes outputs to data/processed/silver/.

Memory optimizations (7.6 GB RAM / 32M+ rows):
- Incremental bronze reads (not all datasets loaded at once)
- Single-pass quality aggregations on large fact tables
- Broadcast joins for dimension tables (aisles, departments, products)
- Disk checkpoint between heavy stages to break lineage
- Tuned Spark memory and shuffle settings
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DataType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

from src.utils.venv import ensure_virtual_env

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRONZE_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "bronze"
SILVER_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "silver"

DEFAULT_APP_NAME = "InstacartRetailSilverTransform"
LOGGER_NAME = "retail_analytics.silver"

# Datasets too large for repeated full scans (32M+ rows).
# Quality checks run once on the merged fact table, not on each split.
LARGE_FACT_DATASETS = frozenset(
    {"order_products__prior", "order_products__train", "order_products_merged"}
)

BRONZE_DATASETS = (
    "orders",
    "products",
    "departments",
    "aisles",
    "order_products__prior",
    "order_products__train",
)

EXPECTED_BRONZE_SCHEMAS: Dict[str, StructType] = {
    "orders": StructType(
        [
            StructField("order_id", LongType(), nullable=False),
            StructField("user_id", LongType(), nullable=False),
            StructField("eval_set", StringType(), nullable=False),
            StructField("order_number", IntegerType(), nullable=False),
            StructField("order_dow", IntegerType(), nullable=False),
            StructField("order_hour_of_day", IntegerType(), nullable=False),
            StructField("days_since_prior_order", DoubleType(), nullable=True),
        ]
    ),
    "products": StructType(
        [
            StructField("product_id", LongType(), nullable=False),
            StructField("product_name", StringType(), nullable=False),
            StructField("aisle_id", LongType(), nullable=False),
            StructField("department_id", LongType(), nullable=False),
        ]
    ),
    "departments": StructType(
        [
            StructField("department_id", LongType(), nullable=False),
            StructField("department", StringType(), nullable=False),
        ]
    ),
    "aisles": StructType(
        [
            StructField("aisle_id", LongType(), nullable=False),
            StructField("aisle", StringType(), nullable=False),
        ]
    ),
    "order_products": StructType(
        [
            StructField("order_id", LongType(), nullable=False),
            StructField("product_id", LongType(), nullable=False),
            StructField("add_to_cart_order", IntegerType(), nullable=False),
            StructField("reordered", IntegerType(), nullable=False),
        ]
    ),
}


class SilverTransformError(Exception):
    """Raised when silver-layer transformation cannot proceed."""


@dataclass(frozen=True)
class QualityCheckResult:
    """Single data-quality metric for reporting."""

    dataset: str
    check_type: str
    column_name: str
    metric_name: str
    metric_value: str
    status: str


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
    """
    Create a SparkSession tuned for low-memory bronze-to-silver transformation.

    OOM fix: explicit heap limits + fewer shuffle partitions reduce driver
    pressure on 7.6 GB RAM laptops. AQE coalesces small shuffle outputs.
    """
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.driver.memory", "3g")
        .config("spark.executor.memory", "3g")
        .config("spark.sql.shuffle.partitions", "100")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        # AQE reduces over-shuffling on skewed joins (retail_transactions).
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        # Broadcast small dimension tables (aisles=134, departments=21, products=50K).
        .config("spark.sql.autoBroadcastJoinThreshold", "64m")
        # Smaller read chunks lower peak memory during Parquet scan.
        .config("spark.sql.files.maxPartitionBytes", "67108864")
    )
    if master:
        builder = builder.master(master)

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def validate_bronze_path(path: Path, dataset_name: str) -> None:
    """Ensure a bronze Parquet dataset directory exists."""
    if not path.exists():
        raise SilverTransformError(f"Bronze dataset not found: {dataset_name} at {path}")
    if not path.is_dir():
        raise SilverTransformError(f"Bronze path is not a directory: {path}")


def read_bronze_parquet(
    spark: SparkSession,
    bronze_dir: Path,
    dataset_name: str,
    logger: logging.Logger,
    columns: Sequence[str] | None = None,
) -> DataFrame:
    """
    Read a single bronze Parquet dataset.

    OOM fix: column pruning at read time avoids loading unused fields into
    the query plan for downstream joins.
    """
    dataset_path = bronze_dir / dataset_name
    validate_bronze_path(dataset_path, dataset_name)
    logger.info("Reading bronze dataset '%s' from %s", dataset_name, dataset_path)
    try:
        reader = spark.read.parquet(str(dataset_path))
        if columns:
            return reader.select(*columns)
        return reader
    except Exception as exc:
        raise SilverTransformError(
            f"Failed to read bronze dataset '{dataset_name}': {exc}"
        ) from exc


def materialize_checkpoint(
    df: DataFrame,
    output_dir: Path,
    dataset_name: str,
    spark: SparkSession,
    logger: logging.Logger,
) -> DataFrame:
    """
    Write an intermediate DataFrame to Parquet and read it back.

    OOM fix: breaks the cumulative lineage chain. Without this, Spark retains
    the entire transformation DAG (union + joins + dedup) in memory when
    building retail_transactions on 33M+ rows.
    """
    write_silver_parquet(df, output_dir, dataset_name, logger)
    logger.info("Checkpoint loaded from %s", output_dir)
    return spark.read.parquet(str(output_dir))


def normalize_text_column(column: F.Column) -> F.Column:
    """Trim, collapse whitespace, and lowercase text fields."""
    collapsed = F.regexp_replace(F.trim(column), r"\s+", " ")
    return F.lower(collapsed)


def standardize_missing_double(column: F.Column) -> F.Column:
    """Keep valid doubles; invalid or sentinel values become null."""
    return F.when(column.cast("double").isNull(), F.lit(None)).otherwise(
        column.cast("double")
    )


def schema_field_map(schema: StructType) -> Dict[str, DataType]:
    """Return column name to data type mapping from a StructType."""
    return {field.name: field.dataType for field in schema.fields}


def validate_schema(
    df: DataFrame,
    dataset_name: str,
    expected_schema: StructType,
) -> List[QualityCheckResult]:
    """
    Compare actual DataFrame schema against the expected bronze schema.

    Metadata-only check — no Spark action, zero memory cost.
    """
    results: List[QualityCheckResult] = []
    actual = schema_field_map(df.schema)
    expected = schema_field_map(expected_schema)

    missing_columns = sorted(set(expected) - set(actual))
    extra_columns = sorted(set(actual) - set(expected))

    results.append(
        QualityCheckResult(
            dataset=dataset_name,
            check_type="schema",
            column_name="*",
            metric_name="missing_columns",
            metric_value=",".join(missing_columns) if missing_columns else "none",
            status="FAIL" if missing_columns else "PASS",
        )
    )
    results.append(
        QualityCheckResult(
            dataset=dataset_name,
            check_type="schema",
            column_name="*",
            metric_name="extra_columns",
            metric_value=",".join(extra_columns) if extra_columns else "none",
            status="WARN" if extra_columns else "PASS",
        )
    )

    for column_name, expected_type in expected.items():
        if column_name not in actual:
            continue
        actual_type = actual[column_name].simpleString()
        expected_type_name = expected_type.simpleString()
        type_matches = actual_type == expected_type_name
        results.append(
            QualityCheckResult(
                dataset=dataset_name,
                check_type="schema",
                column_name=column_name,
                metric_name="expected_type",
                metric_value=expected_type_name,
                status="PASS" if type_matches else "FAIL",
            )
        )
        results.append(
            QualityCheckResult(
                dataset=dataset_name,
                check_type="schema",
                column_name=column_name,
                metric_name="actual_type",
                metric_value=actual_type,
                status="PASS" if type_matches else "FAIL",
            )
        )

    return results


def _build_single_pass_agg_exprs(
    df: DataFrame,
    expected_schema: StructType,
) -> List[F.Column]:
    """
    Build one aggregation that returns total rows, null counts, and invalid casts.

    OOM fix: replaces separate count() + agg() + per-column filter().count()
    calls. Previously dtype validation alone scanned 32M rows once per column
    (4 full passes on order_products).
    """
    agg_exprs: List[F.Column] = [F.count(F.lit(1)).alias("_total_rows")]

    for column in df.columns:
        agg_exprs.append(
            F.sum(F.when(F.col(column).isNull(), 1).otherwise(0)).alias(
                f"null__{column}"
            )
        )

    for field in expected_schema.fields:
        if field.name not in df.columns:
            continue
        cast_type = field.dataType.simpleString()
        agg_exprs.append(
            F.sum(
                F.when(
                    F.col(field.name).isNotNull()
                    & F.col(field.name).cast(cast_type).isNull(),
                    1,
                ).otherwise(0)
            ).alias(f"invalid__{field.name}")
        )

    return agg_exprs


def analyze_nulls_and_dtypes_single_pass(
    df: DataFrame,
    dataset_name: str,
    expected_schema: StructType,
    logger: logging.Logger,
) -> Tuple[List[QualityCheckResult], int]:
    """
    Null + dtype validation in a single Spark job.

    OOM fix: one .agg().collect() returns a single driver row (safe collect).
    The old code called df.count() then agg().collect() then filter().count()
    per column — up to 6+ full scans on 32M rows.
    """
    results: List[QualityCheckResult] = []
    agg_exprs = _build_single_pass_agg_exprs(df, expected_schema)
    metrics = df.agg(*agg_exprs).collect()[0].asDict()
    total_rows = int(metrics.get("_total_rows") or 0)

    if total_rows == 0:
        logger.warning("Dataset '%s' is empty during quality analysis", dataset_name)
        return results, total_rows

    for key, value in metrics.items():
        if key == "_total_rows":
            continue
        count_value = int(value or 0)

        if key.startswith("null__"):
            column_name = key.replace("null__", "", 1)
            null_pct = (count_value / total_rows) * 100
            status = "PASS" if count_value == 0 else "WARN"
            results.append(
                QualityCheckResult(
                    dataset=dataset_name,
                    check_type="null",
                    column_name=column_name,
                    metric_name="null_count",
                    metric_value=str(count_value),
                    status=status,
                )
            )
            results.append(
                QualityCheckResult(
                    dataset=dataset_name,
                    check_type="null",
                    column_name=column_name,
                    metric_name="null_pct",
                    metric_value=f"{null_pct:.4f}",
                    status=status,
                )
            )
        elif key.startswith("invalid__"):
            column_name = key.replace("invalid__", "", 1)
            status = "PASS" if count_value == 0 else "FAIL"
            results.append(
                QualityCheckResult(
                    dataset=dataset_name,
                    check_type="dtype",
                    column_name=column_name,
                    metric_name="invalid_cast_count",
                    metric_value=str(count_value),
                    status=status,
                )
            )

    return results, total_rows


def analyze_duplicates(
    df: DataFrame,
    dataset_name: str,
    key_columns: Sequence[str],
    total_rows: int | None = None,
) -> List[QualityCheckResult]:
    """
    Count duplicate rows using groupBy instead of distinct().

    OOM fix: the old code used df.select(*keys).distinct().count() which forces
    a full shuffle + dedup of 32M rows into driver memory. groupBy + sum of
    excess counts is the standard Spark pattern and uses less peak memory.
    """
    if total_rows is None:
        total_rows = df.count()

    duplicate_rows = (
        df.groupBy(*key_columns)
        .agg(F.count(F.lit(1)).alias("_key_count"))
        .filter(F.col("_key_count") > 1)
        .agg(F.sum(F.col("_key_count") - F.lit(1)).alias("duplicate_rows"))
        .collect()[0]["duplicate_rows"]
    )
    duplicate_rows = int(duplicate_rows or 0)
    distinct_rows = total_rows - duplicate_rows
    status = "PASS" if duplicate_rows == 0 else "WARN"

    return [
        QualityCheckResult(
            dataset=dataset_name,
            check_type="duplicate",
            column_name=",".join(key_columns),
            metric_name="total_rows",
            metric_value=str(total_rows),
            status="INFO",
        ),
        QualityCheckResult(
            dataset=dataset_name,
            check_type="duplicate",
            column_name=",".join(key_columns),
            metric_name="distinct_keys",
            metric_value=str(distinct_rows),
            status="INFO",
        ),
        QualityCheckResult(
            dataset=dataset_name,
            check_type="duplicate",
            column_name=",".join(key_columns),
            metric_name="duplicate_rows",
            metric_value=str(duplicate_rows),
            status=status,
        ),
    ]


def run_quality_checks(
    df: DataFrame,
    dataset_name: str,
    expected_schema: StructType,
    key_columns: Sequence[str],
    logger: logging.Logger,
    *,
    include_duplicate_check: bool = True,
) -> List[QualityCheckResult]:
    """Run data-quality analysis with memory-aware strategy per dataset size."""
    logger.info("Running quality checks for '%s'", dataset_name)
    results: List[QualityCheckResult] = []
    results.extend(validate_schema(df, dataset_name, expected_schema))

    if dataset_name in LARGE_FACT_DATASETS:
        # Large facts: schema (free) + one agg pass. Skip per-split duplicate
        # checks on prior/train — duplicates checked once on merged data.
        null_dtype_results, total_rows = analyze_nulls_and_dtypes_single_pass(
            df, dataset_name, expected_schema, logger
        )
        results.extend(null_dtype_results)
        if include_duplicate_check:
            results.extend(
                analyze_duplicates(df, dataset_name, key_columns, total_rows)
            )
        return results

    # Small dimensions: full checks, still using single-pass null/dtype agg.
    null_dtype_results, total_rows = analyze_nulls_and_dtypes_single_pass(
        df, dataset_name, expected_schema, logger
    )
    results.extend(null_dtype_results)
    if include_duplicate_check:
        results.extend(
            analyze_duplicates(df, dataset_name, key_columns, total_rows)
        )
    return results


def deduplicate_by_keys(df: DataFrame, key_columns: Sequence[str]) -> DataFrame:
    """Remove duplicate rows using business keys."""
    return df.dropDuplicates(list(key_columns))


def clean_orders(df: DataFrame) -> DataFrame:
    """Clean and standardize orders."""
    return (
        df.filter(
            F.col("order_id").isNotNull()
            & F.col("user_id").isNotNull()
            & F.col("eval_set").isNotNull()
            & F.col("order_number").isNotNull()
            & F.col("order_dow").isNotNull()
            & F.col("order_hour_of_day").isNotNull()
        )
        .withColumn("eval_set", normalize_text_column(F.col("eval_set")))
        .withColumn(
            "days_since_prior_order",
            standardize_missing_double(F.col("days_since_prior_order")),
        )
        .filter(
            (F.col("order_number") >= 1)
            & (F.col("order_dow").between(0, 6))
            & (F.col("order_hour_of_day").between(0, 23))
        )
        .dropDuplicates(["order_id"])
    )


def clean_products(df: DataFrame) -> DataFrame:
    """Clean and standardize products."""
    return (
        df.filter(
            F.col("product_id").isNotNull()
            & F.col("product_name").isNotNull()
            & F.col("aisle_id").isNotNull()
            & F.col("department_id").isNotNull()
        )
        .withColumn(
            "product_name",
            F.regexp_replace(F.trim(F.col("product_name")), r"\s+", " "),
        )
        .filter(F.length(F.col("product_name")) > 0)
        .dropDuplicates(["product_id"])
    )


def clean_departments(df: DataFrame) -> DataFrame:
    """Clean and standardize departments."""
    return (
        df.filter(
            F.col("department_id").isNotNull() & F.col("department").isNotNull()
        )
        .withColumn("department", normalize_text_column(F.col("department")))
        .filter(F.length(F.col("department")) > 0)
        .dropDuplicates(["department_id"])
    )


def clean_aisles(df: DataFrame) -> DataFrame:
    """Clean and standardize aisles."""
    return (
        df.filter(F.col("aisle_id").isNotNull() & F.col("aisle").isNotNull())
        .withColumn("aisle", normalize_text_column(F.col("aisle")))
        .filter(F.length(F.col("aisle")) > 0)
        .dropDuplicates(["aisle_id"])
    )


def merge_order_products(
    order_products_prior: DataFrame,
    order_products_train: DataFrame,
) -> DataFrame:
    """Union prior and train order-product datasets with column pruning."""
    prior = order_products_prior.select(
        "order_id", "product_id", "add_to_cart_order", "reordered"
    )
    train = order_products_train.select(
        "order_id", "product_id", "add_to_cart_order", "reordered"
    )
    return prior.unionByName(train)


def clean_order_products(
    df: DataFrame,
    valid_order_ids: DataFrame,
    valid_product_ids: DataFrame,
) -> DataFrame:
    """
    Clean merged order products and enforce referential integrity.

    OOM fix: broadcast the ~50K product_id lookup. Orders (~3.4M) use a
    sort-merge join — too large to broadcast on 7.6 GB RAM but small enough
    to shuffle efficiently with 100 partitions.
    """
    return (
        df.filter(
            F.col("order_id").isNotNull()
            & F.col("product_id").isNotNull()
            & F.col("add_to_cart_order").isNotNull()
            & F.col("reordered").isNotNull()
        )
        .filter(F.col("add_to_cart_order") >= 1)
        .filter(F.col("reordered").isin(0, 1))
        .join(F.broadcast(valid_product_ids), on="product_id", how="inner")
        .join(valid_order_ids, on="order_id", how="inner")
        .dropDuplicates(["order_id", "product_id", "add_to_cart_order"])
    )


def build_retail_transactions(
    clean_order_products: DataFrame,
    clean_orders: DataFrame,
    clean_products: DataFrame,
    clean_aisles: DataFrame,
    clean_departments: DataFrame,
) -> DataFrame:
    """
    Build the retail_transactions analytic dataset.

    OOM fix: broadcast all dimension tables (aisles=134, departments=21,
    products+enrichment=~50K). The 33M fact rows stay on the left side of
    each join — never collected to driver.
    """
    orders_slim = clean_orders.select(
        "order_id", "user_id", "order_dow", "order_hour_of_day"
    )

    products_enriched = (
        clean_products.select(
            "product_id", "product_name", "aisle_id", "department_id"
        )
        .join(F.broadcast(clean_aisles), on="aisle_id", how="left")
        .join(F.broadcast(clean_departments), on="department_id", how="left")
        .select("product_id", "product_name", "aisle", "department")
    )

    return (
        clean_order_products.join(orders_slim, on="order_id", how="inner")
        .join(F.broadcast(products_enriched), on="product_id", how="inner")
        .select(
            F.col("order_id"),
            F.col("user_id"),
            F.col("product_id"),
            F.col("product_name"),
            F.col("aisle"),
            F.col("department"),
            F.col("add_to_cart_order"),
            F.col("reordered"),
            F.col("order_dow"),
            F.col("order_hour_of_day"),
        )
    )


def quality_results_to_dataframe(
    spark: SparkSession,
    results: List[QualityCheckResult],
) -> DataFrame:
    """Convert quality-check results into a Spark DataFrame."""
    rows = [
        {
            "dataset": result.dataset,
            "check_type": result.check_type,
            "column_name": result.column_name,
            "metric_name": result.metric_name,
            "metric_value": result.metric_value,
            "status": result.status,
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
        }
        for result in results
    ]
    return spark.createDataFrame(rows)


def write_quality_report_json(
    results: List[QualityCheckResult],
    output_path: Path,
    logger: logging.Logger,
) -> None:
    """Write a human-readable JSON quality report."""
    payload: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_checks": len(results),
            "failures": sum(1 for item in results if item.status == "FAIL"),
            "warnings": sum(1 for item in results if item.status == "WARN"),
        },
        "checks": [
            {
                "dataset": item.dataset,
                "check_type": item.check_type,
                "column_name": item.column_name,
                "metric_name": item.metric_name,
                "metric_value": item.metric_value,
                "status": item.status,
            }
            for item in results
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote data quality JSON report to %s", output_path)


def write_silver_parquet(
    df: DataFrame,
    output_dir: Path,
    dataset_name: str,
    logger: logging.Logger,
    *,
    log_count: bool = False,
) -> int:
    """
    Persist a silver DataFrame as Parquet.

    OOM fix: write-only by default. Avoids a second full scan via count() on
    33M-row outputs. Enable log_count only for small dimension tables.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Writing silver dataset '%s' to %s", dataset_name, output_dir)
    try:
        df.write.mode("overwrite").parquet(str(output_dir))
        if log_count:
            record_count = df.sparkSession.read.parquet(str(output_dir)).count()
            message = f"{dataset_name}: {record_count:,} records"
            logger.info(message)
            print(message)
            return record_count
        logger.info("Wrote %s (count skipped to save memory)", dataset_name)
        print(f"{dataset_name}: written to {output_dir}")
        return 0
    except Exception as exc:
        raise SilverTransformError(
            f"Failed to write silver dataset '{dataset_name}' to {output_dir}: {exc}"
        ) from exc


def run_silver_transform(
    bronze_dir: Path | None = None,
    silver_dir: Path | None = None,
    app_name: str = DEFAULT_APP_NAME,
    master: str | None = None,
) -> Dict[str, int]:
    """
    Execute the full bronze-to-silver transformation pipeline.

    OOM fix: staged execution — small dims first, large facts last, with disk
    checkpoints between stages. Never holds all 6 bronze DataFrames + quality
    scan results in memory simultaneously.
    """
    logger = setup_logging()
    bronze_path = bronze_dir or BRONZE_DATA_DIR
    silver_path = silver_dir or SILVER_DATA_DIR
    output_counts: Dict[str, int] = {}
    quality_results: List[QualityCheckResult] = []
    spark: Optional[SparkSession] = None

    logger.info("Starting silver transformation")
    logger.info("Bronze directory: %s", bronze_path)
    logger.info("Silver directory: %s", silver_path)

    try:
        spark = create_spark_session(app_name=app_name, master=master)

        # ── Stage 1: small dimension tables (fits easily in memory) ──
        orders_bronze = read_bronze_parquet(spark, bronze_path, "orders", logger)
        products_bronze = read_bronze_parquet(spark, bronze_path, "products", logger)
        departments_bronze = read_bronze_parquet(
            spark, bronze_path, "departments", logger
        )
        aisles_bronze = read_bronze_parquet(spark, bronze_path, "aisles", logger)

        for name, df, schema, keys in [
            ("orders", orders_bronze, EXPECTED_BRONZE_SCHEMAS["orders"], ["order_id"]),
            (
                "products",
                products_bronze,
                EXPECTED_BRONZE_SCHEMAS["products"],
                ["product_id"],
            ),
            (
                "departments",
                departments_bronze,
                EXPECTED_BRONZE_SCHEMAS["departments"],
                ["department_id"],
            ),
            ("aisles", aisles_bronze, EXPECTED_BRONZE_SCHEMAS["aisles"], ["aisle_id"]),
        ]:
            quality_results.extend(
                run_quality_checks(df, name, schema, keys, logger)
            )

        clean_orders_df = clean_orders(orders_bronze)
        clean_products_df = clean_products(products_bronze)
        clean_departments_df = clean_departments(departments_bronze)
        clean_aisles_df = clean_aisles(aisles_bronze)

        # Release bronze dimension references before loading 32M fact tables.
        del orders_bronze, products_bronze, departments_bronze, aisles_bronze

        for dataset_name, dataframe in [
            ("clean_orders", clean_orders_df),
            ("clean_products", clean_products_df),
            ("clean_departments", clean_departments_df),
            ("clean_aisles", clean_aisles_df),
        ]:
            output_counts[dataset_name] = write_silver_parquet(
                dataframe,
                silver_path / dataset_name,
                dataset_name,
                logger,
                log_count=True,
            )

        # Slim lookup tables for referential joins on the fact table.
        valid_order_ids = clean_orders_df.select("order_id").distinct()
        valid_product_ids = clean_products_df.select("product_id").distinct()

        # ── Stage 2: large fact tables (read one at a time) ──
        prior_bronze = read_bronze_parquet(
            spark,
            bronze_path,
            "order_products__prior",
            logger,
            columns=["order_id", "product_id", "add_to_cart_order", "reordered"],
        )
        train_bronze = read_bronze_parquet(
            spark,
            bronze_path,
            "order_products__train",
            logger,
            columns=["order_id", "product_id", "add_to_cart_order", "reordered"],
        )

        # Schema-only checks on splits — skip full scans on 32M prior file.
        quality_results.extend(
            validate_schema(
                prior_bronze,
                "order_products__prior",
                EXPECTED_BRONZE_SCHEMAS["order_products"],
            )
        )
        quality_results.extend(
            validate_schema(
                train_bronze,
                "order_products__train",
                EXPECTED_BRONZE_SCHEMAS["order_products"],
            )
        )

        merged_order_products = merge_order_products(prior_bronze, train_bronze)
        del prior_bronze, train_bronze

        # One full quality pass on merged data (not on each 32M split).
        quality_results.extend(
            run_quality_checks(
                merged_order_products,
                "order_products_merged",
                EXPECTED_BRONZE_SCHEMAS["order_products"],
                ["order_id", "product_id", "add_to_cart_order"],
                logger,
            )
        )

        clean_order_products_df = clean_order_products(
            merged_order_products,
            valid_order_ids,
            valid_product_ids,
        )
        del merged_order_products

        # Checkpoint: materialize 33M rows to disk before the heaviest join.
        clean_order_products_df = materialize_checkpoint(
            clean_order_products_df,
            silver_path / "clean_order_products",
            "clean_order_products",
            spark,
            logger,
        )
        print("clean_order_products: written to", silver_path / "clean_order_products")
        output_counts["clean_order_products"] = 0

        # ── Stage 3: retail_transactions (broadcast dims, fact on left) ──
        retail_transactions_df = build_retail_transactions(
            clean_order_products_df,
            clean_orders_df,
            clean_products_df,
            clean_aisles_df,
            clean_departments_df,
        )
        del clean_order_products_df

        write_silver_parquet(
            retail_transactions_df,
            silver_path / "retail_transactions",
            "retail_transactions",
            logger,
        )
        output_counts["retail_transactions"] = 0

        quality_df = quality_results_to_dataframe(spark, quality_results)
        write_silver_parquet(
            quality_df,
            silver_path / "data_quality_report",
            "data_quality_report",
            logger,
        )
        write_quality_report_json(
            quality_results,
            silver_path / "data_quality_report.json",
            logger,
        )

        failures = sum(1 for item in quality_results if item.status == "FAIL")
        warnings = sum(1 for item in quality_results if item.status == "WARN")
        logger.info(
            "Silver transformation completed | datasets=%d | quality_failures=%d | quality_warnings=%d",
            len(output_counts),
            failures,
            warnings,
        )
        return output_counts

    except SilverTransformError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during silver transformation")
        raise SilverTransformError(f"Silver pipeline failed: {exc}") from exc
    finally:
        if spark is not None:
            spark.stop()
            logger.info("SparkSession stopped")


def main() -> int:
    """CLI entry point."""
    logger = setup_logging()
    try:
        ensure_virtual_env()
        run_silver_transform()
        return 0
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    except SilverTransformError as exc:
        logger.error("Silver transformation aborted: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
