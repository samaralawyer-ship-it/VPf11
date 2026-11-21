"""Пользователи: валидация, пароли, активные."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
from pathlib import Path
from typing import Iterable

from app.config import settings
from app.db import connect

logger = logging.getLogger(__name__)

NAME_LIMIT = 80
TAG_LIMIT = 40
TAGS_MAX = 10
PASSWORD_MIN = 6
HASH_ITERATIONS = 100_000

_active: list[int] = []
_active_lock = threading.Lock()


class UserError(ValueError):
    """Некорректные данные: ответ 400."""


class UserNotFound(UserError):
    """Пользователь не найден: ответ 404."""


# ---------------------------------------------------------------- валидация

def validate_name(name: object) -> str:
    if not isinstance(name, str):
        raise UserError("имя должно быть строкой")
    clean = name.strip()
    if not clean:
        raise UserError("имя не может быть пустым")
    if len(clean) > NAME_LIMIT:
        raise UserError(f"имя длиннее {NAME_LIMIT} символов")
    return clean


def validate_tags(tags: object) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str) or not isinstance(tags, Iterable):
        raise UserError("теги должны быть списком строк")

    result: list[str] = []
    for item in tags:
        if not isinstance(item, str):
            raise UserError("каждый тег должен быть строкой")
        clean = item.strip()
        if not clean:
            continue
        if len(clean) > TAG_LIMIT:
            raise UserError(f"тег длиннее {TAG_LIMIT} символов")
        if clean not in result:
            result.append(clean)
    if len(result) > TAGS_MAX:
        raise UserError(f"тегов не больше {TAGS_MAX}")
    return result


def validate_password(password: object) -> str | None:
    if password is None:
        return None
    if not isinstance(password, str):
        raise UserError("пароль должен быть строкой")
    if len(password) < PASSWORD_MIN:
        raise UserError(f"пароль короче {PASSWORD_MIN} символов")
    return password


# ---------------------------------------------------------------- пароли

def hash_password(password: str, salt: bytes | None = None) -> str:
    """pbkdf2 + соль. Формат хранения: salt_hex$hash_hex."""
    if not password:
        raise UserError("пустой пароль")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    return hmac.compare_digest(candidate.hex(), digest_hex)


# ---------------------------------------------------------------- пользователи

def _row_to_user(row) -> dict:
    raw_tags = row["tags"]
    try:
        tags = json.loads(raw_tags)
    except (TypeError, json.JSONDecodeError):
        tags = []
    if not isinstance(tags, list):
        tags = []
    return {
        "id": int(row["id"]),
        "name": str(row["name"]),
        "tags": [str(tag) for tag in tags],
    }


def add_user(
    name: str,
    tags: Iterable[str] | None = None,
    password: str | None = None,
    db_path: Path | str | None = None,
) -> dict:
    """Создать пользователя. Вернуть id(int), имя и теги."""
    clean_name = validate_name(name)
    clean_tags = validate_tags(tags)
    clean_password = validate_password(password)

    with connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO users (name, tags) VALUES (?, ?)",
            (clean_name, json.dumps(clean_tags, ensure_ascii=False)),
        )
        user_id = int(cursor.lastrowid)
        if clean_password is not None:
            connection.execute(
                "INSERT INTO passwords (user_id, hash, created_at) VALUES (?, ?, datetime('now'))",
                (user_id, hash_password(clean_password)),
            )

    logger.info("создан пользователь id=%s", user_id)
    return {"id": user_id, "name": clean_name, "tags": clean_tags}


def get_user(user_id: int, db_path: Path | str | None = None) -> dict | None:
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT id, name, tags FROM users WHERE id = ?", (int(user_id),)
        ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_name(name: str, db_path: Path | str | None = None) -> dict | None:
    clean_name = validate_name(name)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT id, name, tags FROM users WHERE name = ?", (clean_name,)
        ).fetchone()
    return _row_to_user(row) if row else None


def get_password_hash(user_id: int, db_path: Path | str | None = None) -> str | None:
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT hash FROM passwords WHERE user_id = ?", (int(user_id),)
        ).fetchone()
    return row["hash"] if row else None


def count_users(db_path: Path | str | None = None) -> int:
    with connect(db_path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])


# ---------------------------------------------------------------- активные

def activate(
    user_id: int, db_path: Path | str | None = None, limit: int | None = None
) -> list[int]:
    """Отметить пользователя активным. Вернуть снапшот списка."""
    if get_user(user_id, db_path) is None:
        raise UserNotFound(f"пользователь {user_id} не найден")

    max_active = int(limit or settings.active_limit)
    with _active_lock:
        _active.append(int(user_id))
        if len(_active) > max_active:
            del _active[: len(_active) - max_active]
        return list(_active)


def active_snapshot() -> list[int]:
    with _active_lock:
        return list(_active)


def reset_active() -> None:
    """Очистить список активных (для тестов и перезапуска)."""
    with _active_lock:
        _active.clear()


def is_admin(user: object) -> bool:
    if not isinstance(user, dict):
        return False
    return user.get("role") == "admin"