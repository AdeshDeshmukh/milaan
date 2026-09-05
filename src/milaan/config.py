"""Milaan configuration — all bounds and tunables live here, not in code."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderChoice(str, Enum):
    """Supported LLM providers."""

    STUB = "stub"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    """Application settings, loaded from .env / environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Razorpay ──────────────────────────────────────────────────────────
    razorpay_key_id: str = "rzp_test_xxxxxxxxxxxxx"
    razorpay_key_secret: str = "xxxxxxxxxxxxxxxxxxxxxxxx"

    # ── LLM ───────────────────────────────────────────────────────────────
    llm_provider: LLMProviderChoice = LLMProviderChoice.STUB
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # ── Matching bounds ───────────────────────────────────────────────────
    max_fuzzy_amount_delta_paise: int = 100  # ±₹1
    max_fuzzy_date_window_days: int = 2
    max_subset_sum_candidates: int = 60  # beyond → NEEDS_HUMAN
    subset_sum_timeout_ms: int = 500

    # ── AI budget ─────────────────────────────────────────────────────────
    max_llm_calls_per_run: int = 200

    # ── Action bounds ─────────────────────────────────────────────────────
    max_proposal_adjust_paise: int = 1_00_000  # ₹1,000
    max_proposals_per_run: int = 50

    # ── Paths ─────────────────────────────────────────────────────────────
    db_path: Path = Path("data/generated/milaan.db")
    audit_log_path: Path = Path("data/generated/audit.jsonl")
    synth_output_dir: Path = Path("data/generated")


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
