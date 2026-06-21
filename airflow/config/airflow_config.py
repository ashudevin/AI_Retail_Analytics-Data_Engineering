"""
Central configuration for the Retail Analytics Airflow pipeline.

Paths resolve from RETAIL_ANALYTICS_ROOT (Docker) or auto-detect from repo layout.
Override any path via environment variables for container deployments.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution (Docker-compatible)
# ---------------------------------------------------------------------------

# airflow/config/airflow_config.py → parents[1] = airflow/ → parents[2] = project root
_CONFIG_DIR = Path(__file__).resolve().parent
AIRFLOW_HOME = _CONFIG_DIR.parent

PROJECT_ROOT = Path(
    os.environ.get("RETAIL_ANALYTICS_ROOT", AIRFLOW_HOME.parent)
).resolve()

# Data layer directories
RAW_DATA_DIR = Path(os.environ.get("RAW_DATA_DIR", PROJECT_ROOT / "data" / "raw"))
BRONZE_DATA_DIR = Path(
    os.environ.get("BRONZE_DATA_DIR", PROJECT_ROOT / "data" / "processed" / "bronze")
)
SILVER_DATA_DIR = Path(
    os.environ.get("SILVER_DATA_DIR", PROJECT_ROOT / "data" / "processed" / "silver")
)
GOLD_DATA_DIR = Path(
    os.environ.get("GOLD_DATA_DIR", PROJECT_ROOT / "data" / "processed" / "gold")
)
FRONTEND_DATA_DIR = Path(
    os.environ.get(
        "FRONTEND_DATA_DIR", PROJECT_ROOT / "frontend" / "public" / "data"
    )
)
AI_INSIGHTS_DIR = Path(
    os.environ.get("AI_INSIGHTS_DIR", PROJECT_ROOT / "data" / "ai_insights")
)
ENV_FILE = Path(os.environ.get("RETAIL_ENV_FILE", PROJECT_ROOT / ".env"))

# Python interpreter for BashOperator fallback (Docker: set to container python)
PYTHON_BIN = os.environ.get("RETAIL_PYTHON_BIN", "python")

# ---------------------------------------------------------------------------
# DAG metadata
# ---------------------------------------------------------------------------

DAG_ID = "retail_analytics_pipeline"
DAG_DESCRIPTION = (
    "End-to-end AI-Powered Retail Analytics: Bronze → Silver → Gold → "
    "Dashboard JSON → Gemini AI Insights"
)
DAG_OWNER = "data-engineering"
DAG_TAGS = ["retail", "pyspark", "medallion", "ai", "instacart"]

# Daily at 06:00 UTC — set SCHEDULE_INTERVAL="" for manual-only triggers
SCHEDULE_INTERVAL = os.environ.get("RETAIL_DAG_SCHEDULE", "0 6 * * *")

# ---------------------------------------------------------------------------
# Retry & timeout settings
# ---------------------------------------------------------------------------

DEFAULT_RETRIES = int(os.environ.get("RETAIL_DAG_RETRIES", "2"))
RETRY_DELAY_MINUTES = int(os.environ.get("RETAIL_RETRY_DELAY_MINUTES", "5"))
RETRY_DELAY = timedelta(minutes=RETRY_DELAY_MINUTES)

# Spark-heavy tasks need longer timeouts (seconds)
TASK_TIMEOUT_BRONZE = timedelta(hours=int(os.environ.get("TIMEOUT_BRONZE_HOURS", "3")))
TASK_TIMEOUT_SILVER = timedelta(hours=int(os.environ.get("TIMEOUT_SILVER_HOURS", "4")))
TASK_TIMEOUT_GOLD = timedelta(hours=int(os.environ.get("TIMEOUT_GOLD_HOURS", "2")))
TASK_TIMEOUT_EXPORT = timedelta(minutes=int(os.environ.get("TIMEOUT_EXPORT_MINUTES", "30")))
TASK_TIMEOUT_AI = timedelta(minutes=int(os.environ.get("TIMEOUT_AI_MINUTES", "15")))
TASK_TIMEOUT_SUCCESS = timedelta(minutes=5)

# ---------------------------------------------------------------------------
# Email (disabled per requirements)
# ---------------------------------------------------------------------------

EMAIL_ON_FAILURE = False
EMAIL_ON_RETRY = False

# ---------------------------------------------------------------------------
# Pipeline module entry points (equivalent to python -m invocations)
# ---------------------------------------------------------------------------

PIPELINE_MODULES = {
    "bronze_ingestion": "src.extract.ingest_data",
    "silver_transformation": "src.transform.silver_transform",
    "gold_transformation": "src.gold.gold_transform",
    "export_dashboard_json": "src.dashboard.export_json",
    "generate_ai_insights": "src.ai.run_ai_insights",
}


def ensure_project_on_path() -> None:
    """Add project root to sys.path so `src.*` imports work inside Airflow."""
    import sys

    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def get_dag_default_args() -> dict:
    """Shared default_args dict for the retail analytics DAG."""
    return {
        "owner": DAG_OWNER,
        "depends_on_past": False,
        "email_on_failure": EMAIL_ON_FAILURE,
        "email_on_retry": EMAIL_ON_RETRY,
        "retries": DEFAULT_RETRIES,
        "retry_delay": RETRY_DELAY,
    }
