"""Environment-based configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from dotenv import load_dotenv

DEFAULT_SUMMARY_THRESHOLD = 1000
DEFAULT_DATABASE_URL = "sqlite:///database.db"


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    chat_model: str
    summarize_model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    summarize_threshold: int = DEFAULT_SUMMARY_THRESHOLD
    database_url: str = DEFAULT_DATABASE_URL
    include_stream_usage: bool = True


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_threshold(value: Optional[str]) -> int:
    if value is None or value.strip() == "":
        return DEFAULT_SUMMARY_THRESHOLD
    try:
        threshold = int(value)
    except ValueError:
        raise ConfigError(
            f"MT_FOR_START_SUMMARIZE must be an integer, got {value!r}."
        ) from None
    if threshold <= 0:
        raise ConfigError("MT_FOR_START_SUMMARIZE must be greater than zero.")
    return threshold


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    """Build :class:`Settings` from ``env`` (defaults to ``os.environ`` + ``.env``)."""
    if env is None:
        load_dotenv()
        env = os.environ

    chat_model = env.get("MODEL_CHAT_NAME")
    if not chat_model:
        raise ConfigError(
            "MODEL_CHAT_NAME is not set. Copy .env.example to .env and fill it in."
        )

    return Settings(
        chat_model=chat_model,
        summarize_model=env.get("MODEL_SUMMARIZE_NAME") or chat_model,
        # Optional: the OpenAI SDK falls back to OPENAI_API_KEY when this is None.
        api_key=env.get("API_KEY") or None,
        base_url=env.get("PV_BASE_URL") or None,
        summarize_threshold=_parse_threshold(env.get("MT_FOR_START_SUMMARIZE")),
        database_url=env.get("DATABASE_URL") or DEFAULT_DATABASE_URL,
        include_stream_usage=_parse_bool(env.get("INCLUDE_STREAM_USAGE"), True),
    )
