# AI-Powered Retail Analytics Platform

End-to-end data engineering platform for Instacart retail analytics — from 37M+ raw records to an AI-powered executive dashboard.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Platform (Phase 7)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌─────────────────────────────────────────────────┐   │
│  │  PostgreSQL  │◄───│              Apache Airflow                      │   │
│  │  (metadata)  │    │  Webserver :8080  +  Scheduler                 │   │
│  └──────────────┘    │  DAG: retail_analytics_pipeline                  │   │
│                      └──────────────┬──────────────────────────────────┘   │
│                                     │                                       │
│         ┌───────────────────────────┼───────────────────────────┐          │
│         ▼                           ▼                           ▼          │
│  ┌─────────────┐           ┌─────────────┐            ┌──────────────┐    │
│  │ data/raw    │  PySpark  │  processed  │   JSON     │  frontend/   │    │
│  │  (CSV)      │ ────────► │ bronze/     │ ────────►  │ public/data  │    │
│  │             │           │ silver/     │            │              │    │
│  │             │           │ gold/       │            └──────┬───────┘    │
│  └─────────────┘           └─────────────┘                   │            │
│         ▲                           │                          ▼            │
│         │                           ▼                  ┌──────────────┐    │
│         │                    ┌─────────────┐           │  Next.js     │    │
│         │                    │ ai_insights │           │  Dashboard   │    │
│         │                    │  (Gemini)   │           │  :3000       │    │
│         │                    └─────────────┘           └──────────────┘    │
│         │                                                                   │
│  ┌──────┴───────┐                                                          │
│  │ ETL Worker   │  Manual: docker compose run pipeline-runner               │
│  └──────────────┘                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Medallion Pipeline

| Phase | Layer | Module | Output |
|-------|-------|--------|--------|
| 1 | Ingestion | `src/extract/ingest_data.py` | `data/processed/bronze/` |
| 2 | Silver | `src/transform/silver_transform.py` | `data/processed/silver/` |
| 3 | Gold | `src/gold/gold_transform.py` | `data/processed/gold/` |
| 4 | Export | `src/dashboard/export_json.py` | `frontend/public/data/` |
| 5 | AI | `src/ai/run_ai_insights.py` | `data/ai_insights/` |
| 6 | Orchestration | `airflow/dags/retail_analytics_pipeline.py` | Airflow DAG |
| 7 | Docker | `docker-compose.yml` | Full platform |

## Quick Start (Docker — Phase 7)

### Prerequisites

- Docker Desktop 4.x+ (or Docker Engine + Compose v2)
- 8 GB+ RAM allocated to Docker
- Instacart CSV files in `data/raw/`
- `GEMINI_API_KEY` for AI insights ([Google AI Studio](https://aistudio.google.com/apikey))

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY and optionally AIRFLOW_FERNET_KEY
```

Generate Fernet key (recommended for Airflow):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Place raw data

Copy Instacart CSVs into `data/raw/`:

```
data/raw/
├── orders.csv
├── products.csv
├── departments.csv
├── aisles.csv
├── order_products__prior.csv
└── order_products__train.csv
```

### 3. Start the platform

**Windows (PowerShell):**

```powershell
.\scripts\docker-up.ps1 -Build
```

**Linux / macOS / WSL:**

```bash
chmod +x scripts/docker-up.sh
./scripts/docker-up.sh up
```

**Or directly:**

```bash
docker compose up --build -d
```

### 4. Access services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dashboard** | http://localhost:3000 | — |
| **Airflow UI** | http://localhost:8080 | `airflow` / `airflow` |

### 5. Run the pipeline

**Via Airflow (recommended):**

1. Open http://localhost:8080
2. Unpause `retail_analytics_pipeline`
3. Click **Trigger DAG**

**Manual one-shot (no Airflow UI):**

```bash
docker compose --profile manual run --rm pipeline-runner
```

### 6. Stop the platform

```bash
docker compose down
# Or: .\scripts\docker-up.ps1 -Down
```

## Docker Services

| Service | Image | Purpose |
|---------|-------|---------|
| `postgres` | postgres:16-alpine | Airflow metadata DB |
| `airflow-init` | retail-analytics-airflow | DB migration (runs once) |
| `airflow-webserver` | retail-analytics-airflow | Orchestration UI |
| `airflow-scheduler` | retail-analytics-airflow | DAG execution |
| `etl-worker` | retail-analytics-etl | Idle ETL container for exec |
| `pipeline-runner` | retail-analytics-etl | One-shot full pipeline (profile: manual) |
| `frontend` | retail-analytics-frontend | Next.js dashboard |

## Persistent Volumes

Pipeline outputs survive `docker compose down`:

| Volume | Mount Point | Contents |
|--------|-------------|----------|
| `retail-processed-data` | `data/processed/` | Bronze, Silver, Gold Parquet |
| `retail-ai-insights-data` | `data/ai_insights/` | Gemini insights JSON/TXT |
| `retail-frontend-data` | `frontend/public/data/` | Dashboard JSON files |
| `retail-postgres-data` | PostgreSQL | Airflow metadata |
| `retail-airflow-logs` | Airflow logs | Task execution logs |

## Local Development (without Docker)

### Python pipeline

```powershell
.\scripts\setup.ps1          # Create .venv + install deps
.\scripts\ingest.ps1         # Phase 1 — Bronze
.\scripts\silver.ps1         # Phase 2 — Silver
.\scripts\gold.ps1           # Phase 3 — Gold
.\scripts\export_json.ps1    # Export dashboard JSON
.\scripts\ai_insights.ps1    # Phase 4 — AI insights
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

See [frontend/README.md](frontend/README.md) for Vercel deployment.

## Project Structure

```
AI_Powered_Retail_Analytics/
├── airflow/
│   ├── config/                 # Airflow settings + task runners
│   ├── dags/                   # retail_analytics_pipeline DAG
│   └── README.md
├── docker/
│   ├── airflow/Dockerfile      # Airflow + Java + PySpark
│   └── etl/Dockerfile          # Standalone ETL runner
├── frontend/                   # Next.js dashboard (Phase 5)
├── scripts/                    # PowerShell + shell runners
├── src/
│   ├── extract/                # Bronze ingestion
│   ├── transform/              # Silver transformation
│   ├── gold/                   # Gold KPIs
│   ├── dashboard/              # JSON export
│   └── ai/                     # Gemini insights
├── data/
│   ├── raw/                    # Instacart CSVs (bind-mounted)
│   ├── processed/              # Bronze/Silver/Gold (volume)
│   └── ai_insights/            # AI output (volume)
├── docker-compose.yml          # Phase 7 orchestration
├── requirements.txt
└── .env.example
```

## Verification Checklist

After `docker compose up --build -d` and triggering the DAG:

- [ ] Airflow UI loads at http://localhost:8080
- [ ] DAG `retail_analytics_pipeline` is visible
- [ ] All 6 tasks show green in Graph view
- [ ] `data/processed/bronze/`, `silver/`, `gold/` contain Parquet (in volume)
- [ ] `frontend/public/data/*.json` files updated (in volume)
- [ ] Dashboard at http://localhost:3000 shows KPIs and charts
- [ ] `docker compose ps` shows all services healthy

```bash
# Check service health
docker compose ps

# View Airflow scheduler logs
docker compose logs airflow-scheduler --tail 50

# Verify dashboard JSON inside volume
docker compose exec frontend ls -la /app/public/data/
```

## Troubleshooting

### `routes-manifest.json` error (Vercel)

Do not set Vercel Output Directory to `out`. See [frontend/README.md](frontend/README.md).

### Airflow DAG not appearing

```bash
docker compose logs airflow-scheduler | grep -i error
# Verify PYTHONPATH and dags mount
docker compose exec airflow-scheduler airflow dags list
```

### PySpark OOM in Docker

Increase Docker Desktop memory to 8 GB+. Silver/Gold tasks are memory-intensive.

### AI insights task fails

- Confirm `GEMINI_API_KEY` is set in `.env`
- Restart services: `docker compose up -d`

### Dashboard shows "Failed to load data"

Pipeline has not run yet. Trigger the DAG or run:

```bash
docker compose --profile manual run --rm pipeline-runner
```

### Permission errors on Linux (Airflow)

```bash
echo "AIRFLOW_UID=$(id -u)" >> .env
docker compose up --build -d
```

### Reset all pipeline data

```bash
docker compose down -v   # WARNING: deletes all named volumes
```

## Tech Stack

- **Python 3.12** · PySpark · Pandas · Google Gemini API
- **Apache Airflow 2.10** · PostgreSQL 16
- **Next.js 15** · TypeScript · Tailwind · Recharts
- **Docker Compose** · Medallion Architecture

## License

Instacart dataset for non-commercial use only.
