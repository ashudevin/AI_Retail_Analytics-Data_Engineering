"""
Retail Analytics Pipeline DAG

Orchestrates the full medallion + AI insights workflow:

    bronze_ingestion
        >> silver_transformation
        >> gold_transformation
        >> export_dashboard_json
        >> generate_ai_insights
        >> pipeline_success

Schedule: daily at 06:00 UTC (override via RETAIL_DAG_SCHEDULE env var).
Manual trigger: supported via Airflow UI "Trigger DAG".

Docker: set RETAIL_ANALYTICS_ROOT=/opt/airflow/project and mount the repo.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path before importing airflow.config
_DAGS_DIR = Path(__file__).resolve().parent
_AIRFLOW_HOME = _DAGS_DIR.parent
_PROJECT_ROOT = Path(
    __import__("os").environ.get("RETAIL_ANALYTICS_ROOT", _AIRFLOW_HOME.parent)
)
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_AIRFLOW_HOME) not in sys.path:
    sys.path.insert(0, str(_AIRFLOW_HOME))

from airflow import DAG
from airflow.operators.python import PythonOperator

from config.airflow_config import (
    DAG_DESCRIPTION,
    DAG_ID,
    DAG_TAGS,
    SCHEDULE_INTERVAL,
    TASK_TIMEOUT_AI,
    TASK_TIMEOUT_BRONZE,
    TASK_TIMEOUT_EXPORT,
    TASK_TIMEOUT_GOLD,
    TASK_TIMEOUT_SILVER,
    TASK_TIMEOUT_SUCCESS,
    get_dag_default_args,
)
from config.pipeline_runner import (
    bronze_ingestion,
    export_dashboard_json,
    generate_ai_insights,
    gold_transformation,
    pipeline_success,
    silver_transformation,
)

# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id=DAG_ID,
    description=DAG_DESCRIPTION,
    default_args=get_dag_default_args(),
    schedule=SCHEDULE_INTERVAL or None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=DAG_TAGS,
    max_active_runs=1,
    doc_md=__doc__,
) as dag:

    # Task 1: Bronze ingestion (python -m src.extract.ingest_data)
    task_bronze = PythonOperator(
        task_id="bronze_ingestion",
        python_callable=bronze_ingestion,
        execution_timeout=TASK_TIMEOUT_BRONZE,
    )

    # Task 2: Silver transformation (python -m src.transform.silver_transform)
    task_silver = PythonOperator(
        task_id="silver_transformation",
        python_callable=silver_transformation,
        execution_timeout=TASK_TIMEOUT_SILVER,
    )

    # Task 3: Gold transformation (python -m src.gold.gold_transform)
    task_gold = PythonOperator(
        task_id="gold_transformation",
        python_callable=gold_transformation,
        execution_timeout=TASK_TIMEOUT_GOLD,
    )

    # Task 4: Dashboard JSON export (python -m src.dashboard.export_json)
    task_export = PythonOperator(
        task_id="export_dashboard_json",
        python_callable=export_dashboard_json,
        execution_timeout=TASK_TIMEOUT_EXPORT,
    )

    # Task 5: AI insights (python -m src.ai.run_ai_insights)
    task_ai = PythonOperator(
        task_id="generate_ai_insights",
        python_callable=generate_ai_insights,
        execution_timeout=TASK_TIMEOUT_AI,
    )

    # Task 6: Pipeline success summary
    task_success = PythonOperator(
        task_id="pipeline_success",
        python_callable=pipeline_success,
        execution_timeout=TASK_TIMEOUT_SUCCESS,
    )

    # Linear dependency chain
    (
        task_bronze
        >> task_silver
        >> task_gold
        >> task_export
        >> task_ai
        >> task_success
    )
