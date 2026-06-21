#!/bin/sh
# Frontend container entrypoint — starts Next.js standalone server.
set -e

echo "============================================================"
echo " Retail Analytics Dashboard"
echo " Data directory: ${DASHBOARD_DATA_DIR:-/app/public/data}"
echo " Port: ${PORT:-3000}"
echo "============================================================"

if [ ! -f "${DASHBOARD_DATA_DIR:-/app/public/data}/top_products.json" ]; then
  echo "WARNING: Dashboard JSON not found yet."
  echo "         Run the Airflow pipeline or: docker compose run pipeline-runner"
fi

exec "$@"
