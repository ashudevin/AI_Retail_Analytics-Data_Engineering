"""Virtual environment helpers for local development and CLI entry points."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"


def is_virtual_env() -> bool:
    """Return True when the current interpreter is running inside a venv."""
    return (
        hasattr(sys, "real_prefix")
        or (getattr(sys, "base_prefix", sys.prefix) != sys.prefix)
        or bool(os.environ.get("VIRTUAL_ENV"))
    )


def ensure_virtual_env() -> None:
    """
    Refuse to run project CLIs outside an activated virtual environment.

    Raises:
        RuntimeError: If the current Python interpreter is not from a venv.
    """
    if is_virtual_env():
        return

    setup_cmd = "scripts\\setup.ps1" if os.name == "nt" else "scripts/setup.sh"
    ingest_cmd = "scripts\\ingest.ps1" if os.name == "nt" else "scripts/ingest.sh"
    silver_cmd = "scripts\\silver.ps1" if os.name == "nt" else "scripts/silver.sh"
    gold_cmd = "scripts\\gold.ps1" if os.name == "nt" else "scripts/gold.sh"
    ai_cmd = "scripts\\ai_insights.ps1" if os.name == "nt" else "scripts/ai_insights.sh"
    export_cmd = "scripts\\export_json.ps1" if os.name == "nt" else "scripts/export_json.sh"

    raise RuntimeError(
        "This project must run inside a virtual environment.\n"
        f"  1. Create and install deps: .\\{setup_cmd}\n"
        f"  2. Run ingestion:           .\\{ingest_cmd}\n"
        f"  3. Run silver transform:    .\\{silver_cmd}\n"
        f"  4. Run gold transform:      .\\{gold_cmd}\n"
        f"  5. Run AI insights:         .\\{ai_cmd}\n"
        f"  6. Export dashboard JSON:   .\\{export_cmd}\n"
        f"Or activate manually:         .\\.venv\\Scripts\\Activate.ps1"
    )
