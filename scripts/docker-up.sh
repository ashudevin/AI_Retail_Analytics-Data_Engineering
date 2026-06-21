#!/usr/bin/env bash
# Start the full AI-Powered Retail Analytics Docker platform (Phase 7).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ ! -f .env ]]; then
  echo "WARNING: .env not found."
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit GEMINI_API_KEY before running AI tasks."
  fi
fi

case "${1:-up}" in
  up)
    docker compose up --build -d
    echo ""
    echo "============================================================"
    echo " Dashboard : http://localhost:3000"
    echo " Airflow UI: http://localhost:8080  (airflow / airflow)"
    echo "============================================================"
    ;;
  down)
    docker compose down
    ;;
  logs)
    docker compose logs -f
    ;;
  pipeline)
    docker compose --profile manual run --rm pipeline-runner
    ;;
  *)
    echo "Usage: $0 {up|down|logs|pipeline}"
    exit 1
    ;;
esac
