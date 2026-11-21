"""Настройки сервиса."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    db_path: Path
    active_limit: int
    log_level: str


settings = Settings(
    host=os.getenv("HOST", "0.0.0.0"),
    port=_get_int("PORT", 8000),
    db_path=BASE / os.getenv("DB_PATH", "./users.db"),
    active_limit=_get_int("ACTIVE_LIMIT", 50),
    log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
)