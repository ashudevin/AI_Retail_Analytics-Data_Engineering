"""
CLI entry point for the AI-Powered Retail Analytics insights engine.

Reads gold-layer KPI Parquet files, generates executive insights via Gemini,
and saves outputs to data/ai_insights/.

Usage:
    python -m src.ai.run_ai_insights
"""

from __future__ import annotations

from src.ai.gemini_client import GeminiClientError
from src.ai.insight_generator import (
    GOLD_DATA_DIR,
    INSIGHTS_OUTPUT_DIR,
    InsightGeneratorError,
    run_insight_generation,
    setup_logging,
)
from src.utils.venv import ensure_virtual_env


def main() -> int:
    """Run the AI insights pipeline."""
    logger = setup_logging()
    try:
        ensure_virtual_env()
        result = run_insight_generation(
            gold_dir=GOLD_DATA_DIR,
            output_dir=INSIGHTS_OUTPUT_DIR,
            logger=logger,
        )
        print("\n" + "=" * 60)
        print("AI INSIGHTS GENERATED SUCCESSFULLY")
        print("=" * 60)
        print(f"Model:      {result.model_name}")
        print(f"JSON:       {result.output_json_path}")
        print(f"Text:       {result.output_txt_path}")
        print("=" * 60 + "\n")
        return 0
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    except GeminiClientError as exc:
        logger.error("Gemini API error: %s", exc)
        return 1
    except InsightGeneratorError as exc:
        logger.error("Insight generation aborted: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
