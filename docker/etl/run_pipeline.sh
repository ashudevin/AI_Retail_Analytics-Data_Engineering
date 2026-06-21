#!/usr/bin/env bash
# Run the full medallion + export + AI pipeline sequentially (manual / one-shot).
set -euo pipefail

echo "============================================================"
echo " Retail Analytics — Full Pipeline Run"
echo " Started: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "============================================================"

run_step() {
  local name="$1"
  shift
  echo ""
  echo ">>> STEP: ${name}"
  "$@"
  echo ">>> DONE: ${name}"
}

run_step "Bronze Ingestion"       python -m src.extract.ingest_data
run_step "Silver Transformation"  python -m src.transform.silver_transform
run_step "Gold Transformation"    python -m src.gold.gold_transform
run_step "Dashboard JSON Export"  python -m src.dashboard.export_json
run_step "AI Insights"            python -m src.ai.run_ai_insights

echo ""
echo "============================================================"
echo " Pipeline completed: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "============================================================"
