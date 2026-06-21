# Airflow Orchestration — Phase 6

Automates the full AI-Powered Retail Analytics pipeline with Apache Airflow.

## Pipeline

```
bronze_ingestion
    >> silver_transformation
    >> gold_transformation
    >> export_dashboard_json
    >> generate_ai_insights
    >> pipeline_success
```

| Task | Equivalent CLI | Description |
|------|----------------|-------------|
| `bronze_ingestion` | `python -m src.extract.ingest_data` | Raw CSV → Bronze Parquet |
| `silver_transformation` | `python -m src.transform.silver_transform` | Bronze → Silver |
| `gold_transformation` | `python -m src.gold.gold_transform` | Silver → Gold KPIs |
| `export_dashboard_json` | `python -m src.dashboard.export_json` | Gold → `frontend/public/data/` |
| `generate_ai_insights` | `python -m src.ai.run_ai_insights` | Gemini AI insights |
| `pipeline_success` | — | Logs completion summary |

## Files

```
airflow/
├── config/
│   ├── airflow_config.py      # Paths, retries, DAG metadata
│   └── pipeline_runner.py     # Task callables + monitoring
├── dags/
│   └── retail_analytics_pipeline.py
├── requirements.txt
└── README.md
```

## DAG Settings

| Setting | Value |
|---------|-------|
| DAG ID | `retail_analytics_pipeline` |
| Schedule | Daily 06:00 UTC (`0 6 * * *`) |
| Catchup | Disabled |
| Retries | 2 |
| Retry delay | 5 minutes |
| Email | Disabled |
| Manual trigger | Supported |

Override schedule: `RETAIL_DAG_SCHEDULE=""` for manual-only.

## Local Setup (without Docker)

### 1. Install Airflow

```bash
cd airflow
pip install -r requirements.txt
pip install -r ../requirements.txt
```

### 2. Configure environment

```bash
export AIRFLOW_HOME=/path/to/AI_Powered_Retail_Analytics/airflow
export RETAIL_ANALYTICS_ROOT=/path/to/AI_Powered_Retail_Analytics
export PYTHONPATH="${AIRFLOW_HOME}:${RETAIL_ANALYTICS_ROOT}"
```

### 3. Initialize Airflow

```bash
airflow db init
airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com
```

### 4. Start services

```bash
# Terminal 1
airflow webserver --port 8080

# Terminal 2
airflow scheduler
```

### 5. Trigger the DAG

Open http://localhost:8080 → **retail_analytics_pipeline** → **Trigger DAG**

## Docker Setup

**Full platform deployment (Phase 7)** is documented in the root [README.md](../README.md).

Quick start:

```bash
docker compose up --build -d
# Airflow UI: http://localhost:8080
```

For Airflow-only local setup without the full platform, see below.

### Docker environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `RETAIL_ANALYTICS_ROOT` | `/opt/airflow/project` | Project root inside container |
| `RETAIL_DAG_SCHEDULE` | `0 6 * * *` | Cron schedule |
| `GEMINI_API_KEY` | — | Required for AI insights task |
| `JAVA_HOME` | — | Required for PySpark tasks |

Mount the full project repo so `data/raw/`, `src/`, and `frontend/` are accessible.

## Monitoring

Each task logs:

- Start time (UTC)
- End time (UTC)
- Duration (seconds)
- Success / failure status

Task results are pushed to XCom. `pipeline_success` prints a full summary.

View logs in Airflow UI: **DAG → Task → Log**.

## Prerequisites

Before triggering the full pipeline:

1. Raw CSV files in `data/raw/`
2. `GEMINI_API_KEY` in `.env` (for AI insights task)
3. Java 11+ available (for PySpark)
4. Sufficient RAM for Silver/Gold transforms (8 GB+ recommended)

## Task Timeouts

| Task | Default timeout |
|------|-----------------|
| bronze_ingestion | 3 hours |
| silver_transformation | 4 hours |
| gold_transformation | 2 hours |
| export_dashboard_json | 30 minutes |
| generate_ai_insights | 15 minutes |

Override via `TIMEOUT_BRONZE_HOURS`, `TIMEOUT_SILVER_HOURS`, etc.

## Troubleshooting

**DAG not appearing in UI**
- Check `PYTHONPATH` includes `airflow/` and project root
- Verify no import errors: `python airflow/dags/retail_analytics_pipeline.py`

**PySpark OOM**
- Increase Docker memory limit
- Tune Spark settings in silver/gold modules

**AI insights task fails**
- Confirm `GEMINI_API_KEY` is set in container environment
- Mount `.env` or pass via `docker-compose.yml`
