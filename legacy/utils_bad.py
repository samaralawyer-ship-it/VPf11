"""ИСХОДНЫЙ ПЛОХОЙ КОД — только для сравнения при аудите.

Репозиторий этот файл не использует: он импортируется лишь тестом,
который доказывает, что уязвимости воспроизводятся на «плохой» версии.

Здесь намеренно собраны типичные ошибки, которые ИИ выдаёт, если не проверять результат.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time

CACHE: dict = {}

_active_users: list[int] = []
_active_users_lock = threading.Lock()


def init_db(db_path: str = "users.db") -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, tags TEXT NOT NULL)"
    )
    conn.commit()
    # соединение не закрыто


def add_user(name, tags=[], db_path: str = "users.db"):
    """Добавляет пользователя. Обещает вернуть int, но возвращает str."""
    tags.append("new")  # мутирует аргумент вызывающего

    conn = sqlite3.connect(db_path)  # не закрывается при ошибке
    cur = conn.cursor()

    # SQL-инъекция: значения склеены в строку запроса
    query = f"INSERT INTO users (name, tags) VALUES ('{name}', '{json.dumps(tags)}')"
    cur.execute(query)
    conn.commit()

    return cur.lastrowid + ""  # тип не тот, что в документации


def store_password(user_id, password, path: str = "passwords.txt") -> None:
    """«Хеширование» через разворот строки — пароль восстановим."""
    hashed = password[::-1]
    f = open(path, "a")  # без with, без кодировки
    f.write(f"{user_id}:{hashed}\n")
    # файл не закрыт


def set_active(user_id) -> None:
    """Общий список без блокировки — гонка потоков."""
    _active_users.append(user_id)
    time.sleep(0.1)  # искусственная задержка, чтобы гонка проявилась
    if len(_active_users) > 5:
        _active_users.pop(0)  # странная логика удаления


def get_user_by_name(name: str, db_path: str = "users.db"):
    """Возвращает {} вместо None и падает на битых тегах."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, tags FROM users WHERE name = '%s'" % name)

    row = cur.fetchone()
    if not row:
        return {}  # контракт нарушен: пустой dict вместо None

    uid, uname, tags_json = row
    return {"id": uid, "name": uname, "tags": tags_json}  # теги не декодированы


def is_admin(user) -> bool:
    """Любая ошибка превращается в «админ»."""
    try:
        return user["role"] == "admin"
    except Exception:  # noqa: BLE001
        return True


def self_test() -> None:
    """Проверки, которые ничего не проверяют."""
    add_user("test")
    get_user_by_name("test")
    assert True
    print("всё хорошо")