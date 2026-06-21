"""
Task execution helpers with monitoring for the retail analytics Airflow DAG.

Wraps pipeline run_* functions with start/end timing, structured logging,
and XCom-friendly result payloads. Used by PythonOperator callables.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from config.airflow_config import ensure_project_on_path

LOGGER_NAME = "airflow.retail.pipeline"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_monitored_task(
    task_name: str,
    pipeline_fn: Callable[..., Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute a pipeline function with full monitoring.

    Logs start time, end time, duration, and success/failure status.
    Returns a dict pushed to XCom for downstream summary tasks.
    """
    logger = logging.getLogger(LOGGER_NAME)
    start = _utc_now()
    logger.info("=" * 60)
    logger.info("TASK START | %s | %s", task_name, start.isoformat())
    logger.info("=" * 60)

    result_payload: Dict[str, Any] = {
        "task": task_name,
        "status": "running",
        "start_time": start.isoformat(),
        "end_time": None,
        "duration_seconds": None,
        "result": None,
        "error": None,
    }

    try:
        ensure_project_on_path()
        result = pipeline_fn(**kwargs)
        end = _utc_now()
        duration = (end - start).total_seconds()

        result_payload.update(
            {
                "status": "success",
                "end_time": end.isoformat(),
                "duration_seconds": round(duration, 2),
                "result": _serialize_result(result),
            }
        )

        logger.info("TASK SUCCESS | %s", task_name)
        logger.info("  Start:    %s", start.isoformat())
        logger.info("  End:      %s", end.isoformat())
        logger.info("  Duration: %.2f seconds (%.1f min)", duration, duration / 60)
        logger.info("=" * 60)
        return result_payload

    except Exception as exc:
        end = _utc_now()
        duration = (end - start).total_seconds()
        result_payload.update(
            {
                "status": "failed",
                "end_time": end.isoformat(),
                "duration_seconds": round(duration, 2),
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        logger.error("TASK FAILED | %s", task_name)
        logger.error("  Start:    %s", start.isoformat())
        logger.error("  End:      %s", end.isoformat())
        logger.error("  Duration: %.2f seconds", duration)
        logger.error("  Error:    %s", exc)
        logger.error("=" * 60)
        raise


def _serialize_result(result: Any) -> Any:
    """Convert pipeline return values to JSON-serializable XCom payloads."""
    if result is None:
        return None
    if isinstance(result, dict):
        return {k: _serialize_result(v) for k, v in result.items()}
    if isinstance(result, (list, tuple)):
        return [_serialize_result(v) for v in result]
    from pathlib import Path

    if isinstance(result, Path):
        return str(result)
    if isinstance(result, (str, int, float, bool)):
        return result
    return str(result)


# ---------------------------------------------------------------------------
# Task callables (equivalent to python -m src.* CLI entry points)
# ---------------------------------------------------------------------------


def bronze_ingestion(**context) -> Dict[str, Any]:
    """Task 1: Raw CSV → Bronze Parquet (python -m src.extract.ingest_data)."""
    from config.airflow_config import BRONZE_DATA_DIR, RAW_DATA_DIR
    from src.extract.ingest_data import run_ingestion

    return run_monitored_task(
        "bronze_ingestion",
        run_ingestion,
        raw_dir=RAW_DATA_DIR,
        bronze_dir=BRONZE_DATA_DIR,
    )


def silver_transformation(**context) -> Dict[str, Any]:
    """Task 2: Bronze → Silver (python -m src.transform.silver_transform)."""
    from config.airflow_config import BRONZE_DATA_DIR, SILVER_DATA_DIR
    from src.transform.silver_transform import run_silver_transform

    return run_monitored_task(
        "silver_transformation",
        run_silver_transform,
        bronze_dir=BRONZE_DATA_DIR,
        silver_dir=SILVER_DATA_DIR,
    )


def gold_transformation(**context) -> Dict[str, Any]:
    """Task 3: Silver → Gold (python -m src.gold.gold_transform)."""
    from config.airflow_config import GOLD_DATA_DIR, SILVER_DATA_DIR
    from src.gold.gold_transform import run_gold_transform

    return run_monitored_task(
        "gold_transformation",
        run_gold_transform,
        silver_dir=SILVER_DATA_DIR,
        gold_dir=GOLD_DATA_DIR,
    )


def export_dashboard_json(**context) -> Dict[str, Any]:
    """Task 4: Gold Parquet → Dashboard JSON (python -m src.dashboard.export_json)."""
    from config.airflow_config import FRONTEND_DATA_DIR, GOLD_DATA_DIR
    from src.dashboard.export_json import run_export

    return run_monitored_task(
        "export_dashboard_json",
        run_export,
        gold_dir=GOLD_DATA_DIR,
        output_dir=FRONTEND_DATA_DIR,
        require_ai_insights=False,  # AI runs in next task; placeholder until then
    )


def generate_ai_insights(**context) -> Dict[str, Any]:
    """Task 5: Gold KPIs → Gemini insights (python -m src.ai.run_ai_insights)."""
    import logging

    from config.airflow_config import AI_INSIGHTS_DIR, FRONTEND_DATA_DIR, GOLD_DATA_DIR
    from src.ai.insight_generator import run_insight_generation
    from src.dashboard.export_json import export_ai_insights, utc_now_iso, write_json

    result = run_monitored_task(
        "generate_ai_insights",
        run_insight_generation,
        gold_dir=GOLD_DATA_DIR,
        output_dir=AI_INSIGHTS_DIR,
    )

    # Sync fresh AI insights to the frontend dashboard JSON
    logger = logging.getLogger(LOGGER_NAME)
    logger.info("Syncing ai_insights.json to frontend dashboard data directory")
    ai_payload = export_ai_insights(utc_now_iso(), logger, required=True)
    write_json(FRONTEND_DATA_DIR / "ai_insights.json", ai_payload, logger)

    return result


def pipeline_success(**context) -> Dict[str, Any]:
    """Task 6: Log pipeline completion summary from upstream XCom data."""
    logger = logging.getLogger(LOGGER_NAME)
    ti = context["ti"]
    dag_run = context["dag_run"]

    task_ids = [
        "bronze_ingestion",
        "silver_transformation",
        "gold_transformation",
        "export_dashboard_json",
        "generate_ai_insights",
    ]

    start = _utc_now()
    summaries = []
    total_duration = 0.0

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETION SUMMARY")
    logger.info("  DAG Run ID: %s", dag_run.run_id)
    logger.info("  Execution:  %s", dag_run.execution_date)
    logger.info("=" * 60)

    for task_id in task_ids:
        payload: Optional[Dict[str, Any]] = ti.xcom_pull(task_ids=task_id)
        if payload:
            summaries.append(payload)
            duration = payload.get("duration_seconds") or 0
            total_duration += duration
            logger.info(
                "  ✓ %-25s | %8.1fs | %s",
                task_id,
                duration,
                payload.get("status", "unknown"),
            )
        else:
            logger.warning("  ✗ %-25s | no XCom data", task_id)

    end = _utc_now()
    summary = {
        "task": "pipeline_success",
        "status": "success",
        "dag_run_id": dag_run.run_id,
        "execution_date": str(dag_run.execution_date),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "total_pipeline_duration_seconds": round(total_duration, 2),
        "task_summaries": summaries,
    }

    logger.info("-" * 60)
    logger.info(
        "ALL TASKS COMPLETED | Total pipeline duration: %.1f min",
        total_duration / 60,
    )
    logger.info("=" * 60)

    return summary
