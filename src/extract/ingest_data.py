"""
PySpark ingestion module for Instacart Market Basket Analysis raw CSV data.

Reads validated CSV files from data/raw/, applies explicit schemas, logs record
counts, and writes bronze-layer Parquet datasets to data/processed/bronze/.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

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
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
BRONZE_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "bronze"

DEFAULT_APP_NAME = "InstacartRetailIngestion"
LOGGER_NAME = "retail_analytics.ingest"
CORRUPT_RECORD_COLUMN = "_corrupt_record"
MALFORMED_SUBDIR = "_malformed"


class IngestionError(Exception):
    """Raised when ingestion cannot proceed due to validation or I/O failures."""


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration for a single raw CSV dataset."""

    name: str
    filename: str
    schema: StructType


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
    Create a SparkSession tuned for local CSV-to-Parquet ingestion.

    Args:
        app_name: Spark application name.
        master: Optional Spark master URL (defaults to Spark's local[*]).
    """
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
    )
    if master:
        builder = builder.master(master)

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def get_dataset_configs() -> List[DatasetConfig]:
    """Return dataset definitions with explicit Spark schemas."""
    return [
        DatasetConfig(
            name="orders",
            filename="orders.csv",
            schema=StructType(
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
        ),
        DatasetConfig(
            name="products",
            filename="products.csv",
            schema=StructType(
                [
                    StructField("product_id", LongType(), nullable=False),
                    StructField("product_name", StringType(), nullable=False),
                    StructField("aisle_id", LongType(), nullable=False),
                    StructField("department_id", LongType(), nullable=False),
                ]
            ),
        ),
        DatasetConfig(
            name="departments",
            filename="departments.csv",
            schema=StructType(
                [
                    StructField("department_id", LongType(), nullable=False),
                    StructField("department", StringType(), nullable=False),
                ]
            ),
        ),
        DatasetConfig(
            name="aisles",
            filename="aisles.csv",
            schema=StructType(
                [
                    StructField("aisle_id", LongType(), nullable=False),
                    StructField("aisle", StringType(), nullable=False),
                ]
            ),
        ),
        DatasetConfig(
            name="order_products__prior",
            filename="order_products__prior.csv",
            schema=StructType(
                [
                    StructField("order_id", LongType(), nullable=False),
                    StructField("product_id", LongType(), nullable=False),
                    StructField("add_to_cart_order", IntegerType(), nullable=False),
                    StructField("reordered", IntegerType(), nullable=False),
                ]
            ),
        ),
        DatasetConfig(
            name="order_products__train",
            filename="order_products__train.csv",
            schema=StructType(
                [
                    StructField("order_id", LongType(), nullable=False),
                    StructField("product_id", LongType(), nullable=False),
                    StructField("add_to_cart_order", IntegerType(), nullable=False),
                    StructField("reordered", IntegerType(), nullable=False),
                ]
            ),
        ),
    ]


def validate_file_exists(file_path: Path, logger: logging.Logger) -> None:
    """Ensure the raw CSV file exists and is readable before Spark loads it."""
    if not file_path.exists():
        raise IngestionError(f"Required file not found: {file_path}")
    if not file_path.is_file():
        raise IngestionError(f"Path is not a file: {file_path}")
    if file_path.stat().st_size == 0:
        raise IngestionError(f"File is empty: {file_path}")

    logger.info("Validated file: %s (%.2f MB)", file_path, file_path.stat().st_size / 1_048_576)


def schema_with_corrupt_record(schema: StructType) -> StructType:
    """Extend a dataset schema with Spark's corrupt-record capture column."""
    if any(field.name == CORRUPT_RECORD_COLUMN for field in schema.fields):
        return schema
    return StructType(
        list(schema.fields)
        + [StructField(CORRUPT_RECORD_COLUMN, StringType(), nullable=True)]
    )


def read_csv_dataset(
    spark: SparkSession,
    file_path: Path,
    schema: StructType,
    dataset_name: str,
    logger: logging.Logger,
) -> Tuple[DataFrame, DataFrame]:
    """Read a CSV file using an explicit schema and split valid/malformed rows."""
    logger.info("Reading dataset '%s' from %s", dataset_name, file_path)
    read_schema = schema_with_corrupt_record(schema)
    data_columns = [field.name for field in schema.fields]

    try:
        raw_df = (
            spark.read.option("header", "true")
            .option("nullValue", "")
            .option("mode", "PERMISSIVE")
            .option("multiLine", "true")
            .option("escape", "\"")
            .option("quote", "\"")
            .option("columnNameOfCorruptRecord", CORRUPT_RECORD_COLUMN)
            .schema(read_schema)
            .csv(str(file_path))
        )
    except Exception as exc:
        raise IngestionError(
            f"Failed to read '{dataset_name}' from {file_path}: {exc}"
        ) from exc

    malformed_df = raw_df.filter(
        F.col(CORRUPT_RECORD_COLUMN).isNotNull()
    ).select(CORRUPT_RECORD_COLUMN)
    valid_df = raw_df.filter(F.col(CORRUPT_RECORD_COLUMN).isNull()).select(
        *data_columns
    )
    return valid_df, malformed_df


def log_and_print_record_count(
    df: DataFrame,
    dataset_name: str,
    logger: logging.Logger,
) -> int:
    """Count records, log the result, and print to stdout."""
    try:
        record_count = df.count()
    except Exception as exc:
        raise IngestionError(
            f"Failed to count records for '{dataset_name}': {exc}"
        ) from exc

    message = f"{dataset_name}: {record_count:,} records"
    logger.info(message)
    print(message)
    return record_count


def write_bronze_parquet(
    df: DataFrame,
    output_dir: Path,
    dataset_name: str,
    logger: logging.Logger,
) -> None:
    """Persist a DataFrame as Parquet in the bronze layer."""
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Writing dataset '%s' to %s", dataset_name, output_dir)
    try:
        df.write.mode("overwrite").parquet(str(output_dir))
    except Exception as exc:
        raise IngestionError(
            f"Failed to write '{dataset_name}' to {output_dir}: {exc}"
        ) from exc


def ingest_dataset(
    spark: SparkSession,
    config: DatasetConfig,
    raw_dir: Path,
    bronze_dir: Path,
    logger: logging.Logger,
) -> int:
    """
    Validate, read, count, and persist a single dataset.

    Returns:
        Number of records ingested.
    """
    input_path = raw_dir / config.filename
    output_path = bronze_dir / config.name

    validate_file_exists(input_path, logger)
    df, malformed_df = read_csv_dataset(
        spark, input_path, config.schema, config.name, logger
    )
    record_count = log_and_print_record_count(df, config.name, logger)
    write_bronze_parquet(df, output_path, config.name, logger)

    malformed_count = malformed_df.count()
    if malformed_count > 0:
        malformed_name = f"{config.name}__malformed"
        logger.warning(
            "Captured %d malformed record(s) for '%s'",
            malformed_count,
            config.name,
        )
        log_and_print_record_count(malformed_df, malformed_name, logger)
        write_bronze_parquet(
            malformed_df,
            bronze_dir / MALFORMED_SUBDIR / config.name,
            malformed_name,
            logger,
        )

    return record_count


def run_ingestion(
    raw_dir: Path | None = None,
    bronze_dir: Path | None = None,
    app_name: str = DEFAULT_APP_NAME,
    master: str | None = None,
) -> Dict[str, int]:
    """
    Execute the full raw-to-bronze ingestion pipeline.

    Returns:
        Mapping of dataset name to record count.
    """
    logger = setup_logging()
    raw_path = raw_dir or RAW_DATA_DIR
    bronze_path = bronze_dir or BRONZE_DATA_DIR
    record_counts: Dict[str, int] = {}
    spark: SparkSession | None = None

    logger.info("Starting ingestion")
    logger.info("Raw directory: %s", raw_path)
    logger.info("Bronze directory: %s", bronze_path)

    try:
        spark = create_spark_session(app_name=app_name, master=master)

        for config in get_dataset_configs():
            try:
                record_counts[config.name] = ingest_dataset(
                    spark=spark,
                    config=config,
                    raw_dir=raw_path,
                    bronze_dir=bronze_path,
                    logger=logger,
                )
            except IngestionError:
                logger.exception("Ingestion failed for dataset '%s'", config.name)
                raise

        logger.info("Ingestion completed successfully for %d datasets", len(record_counts))
        return record_counts

    except IngestionError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during ingestion")
        raise IngestionError(f"Ingestion pipeline failed: {exc}") from exc
    finally:
        if spark is not None:
            spark.stop()
            logger.info("SparkSession stopped")


def main() -> int:
    """CLI entry point."""
    logger = setup_logging()
    try:
        ensure_virtual_env()
        run_ingestion()
        return 0
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    except IngestionError as exc:
        logger.error("Ingestion aborted: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
