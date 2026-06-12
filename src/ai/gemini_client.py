"""
Gemini API client for retail analytics insight generation.

Credentials are loaded from environment variables — never hardcoded.
Requires GEMINI_API_KEY in .env or the process environment.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from src.ai.prompt_templates import HEALTH_CHECK_PROMPT

LOGGER_NAME = "retail_analytics.ai.gemini"


class GeminiClientError(Exception):
    """Raised when Gemini API communication fails."""


@dataclass(frozen=True)
class GeminiConfig:
    """Configuration for the Gemini API client."""

    api_key: str
    model_name: str = "gemini-1.5-flash"
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    temperature: float = 0.3
    max_output_tokens: int = 4096


def load_gemini_config(env_file: Optional[str] = None) -> GeminiConfig:
    """
    Load Gemini configuration from environment variables.

    Environment variables:
        GEMINI_API_KEY   (required) — API key from Google AI Studio
        GEMINI_MODEL     (optional) — model name, default gemini-1.5-flash
        GEMINI_MAX_RETRIES (optional) — retry count on transient failures
    """
    load_dotenv(env_file)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiClientError(
            "GEMINI_API_KEY is not set. Add it to your .env file:\n"
            "  GEMINI_API_KEY=your_api_key_here"
        )

    return GeminiConfig(
        api_key=api_key,
        model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip(),
        max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "3")),
        retry_delay_seconds=float(os.getenv("GEMINI_RETRY_DELAY_SECONDS", "2.0")),
        temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.3")),
        max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "4096")),
    )


class GeminiClient:
    """Thin wrapper around the Google Generative AI SDK."""

    def __init__(self, config: GeminiConfig, logger: Optional[logging.Logger] = None):
        self._config = config
        self._logger = logger or logging.getLogger(LOGGER_NAME)
        self._model = self._build_model()

    @property
    def model_name(self) -> str:
        """Return the configured Gemini model name."""
        return self._config.model_name

    def _build_model(self):
        """Configure and instantiate the Gemini generative model."""
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise GeminiClientError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai"
            ) from exc

        genai.configure(api_key=self._config.api_key)
        return genai.GenerativeModel(
            model_name=self._config.model_name,
            generation_config={
                "temperature": self._config.temperature,
                "max_output_tokens": self._config.max_output_tokens,
            },
        )

    def generate(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate text from a user prompt with optional system instruction.

        Retries on transient API failures with exponential backoff.
        """
        full_prompt = user_prompt
        if system_prompt:
            full_prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"

        last_error: Optional[Exception] = None
        for attempt in range(1, self._config.max_retries + 1):
            try:
                self._logger.debug(
                    "Gemini request attempt %d/%d (model=%s)",
                    attempt,
                    self._config.max_retries,
                    self._config.model_name,
                )
                response = self._model.generate_content(full_prompt)
                text = self._extract_text(response)
                if not text.strip():
                    raise GeminiClientError("Gemini returned an empty response.")
                return text.strip()
            except GeminiClientError:
                raise
            except Exception as exc:
                last_error = exc
                self._logger.warning(
                    "Gemini API attempt %d failed: %s", attempt, exc
                )
                if attempt < self._config.max_retries:
                    delay = self._config.retry_delay_seconds * attempt
                    time.sleep(delay)

        raise GeminiClientError(
            f"Gemini API failed after {self._config.max_retries} attempts: {last_error}"
        ) from last_error

    @staticmethod
    def _extract_text(response) -> str:
        """Safely extract text from a Gemini response object."""
        if hasattr(response, "text") and response.text:
            return response.text
        if hasattr(response, "candidates") and response.candidates:
            parts = response.candidates[0].content.parts
            return "".join(part.text for part in parts if hasattr(part, "text"))
        return ""

    def health_check(self) -> bool:
        """Verify API key and model connectivity with a minimal prompt."""
        try:
            result = self.generate(HEALTH_CHECK_PROMPT)
            self._logger.info("Gemini health check passed: %s", result[:80])
            return True
        except Exception as exc:
            raise GeminiClientError(f"Gemini health check failed: {exc}") from exc
