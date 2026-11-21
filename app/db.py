"""Работа с SQLite: соединение через контекстный менеджер и схема."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import settings

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tags TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS passwords (
    user_id INTEGER PRIMARY KEY,
    hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
"""


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Соединение всегда закрывается, транзакция откатывается при ошибке."""
    target = Path(db_path) if db_path is not None else settings.db_path
    target.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path: Path | str | None = None) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)
    logger.debug("схема готова: %s", db_path or settings.db_path)


def ping(db_path: Path | str | None = None) -> bool:
    """Проверка, что база открывается и таблица доступна."""
    try:
        with connect(db_path) as connection:
            connection.execute("SELECT 1 FROM users LIMIT 1").fetchall()
        return True
    except sqlite3.Error as exc:
        logger.warning("проверка БД не прошла: %s", exc)
        return False