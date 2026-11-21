"""Тесты бизнес-логики: инъекции, пароли, потоки, валидация."""

import threading

import pytest

from app import users
from app.db import init_db


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "users.db"
    init_db(path)
    return path


@pytest.fixture(autouse=True)
def clean_active():
    users.reset_active()
    yield
    users.reset_active()


# ---------------------------------------------------------------- базовое

def test_add_user_returns_int(db_path):
    created = users.add_user("Иван", ["стартер"], db_path=db_path)

    assert isinstance(created["id"], int)
    assert created["name"] == "Иван"
    assert created["tags"] == ["стартер"]


def test_tags_do_not_leak_between_calls(db_path):
    tags = ["стартер"]
    users.add_user("Первый", tags, db_path=db_path)

    assert tags == ["стартер"], "аргумент вызывающего не должен меняться"

    second = users.add_user("Второй", db_path=db_path)
    assert second["tags"] == []


def test_missing_user_returns_none(db_path):
    assert users.get_user(999, db_path) is None
    assert users.get_user_by_name("нет такого", db_path) is None


def test_tags_are_list(db_path):
    created = users.add_user("Иван", ["a", "b"], db_path=db_path)
    stored = users.get_user(created["id"], db_path)
    assert stored["tags"] == ["a", "b"]


def test_many_inserts_do_not_lock_db(db_path):
    for index in range(200):
        users.add_user(f"пользователь {index}", db_path=db_path)
    assert users.count_users(db_path) == 200


# ---------------------------------------------------------------- инъекции

def test_injection_does_not_break_db(db_path):
    payload = "' OR 1=1 --"
    created = users.add_user(payload, db_path=db_path)

    assert users.count_users(db_path) == 1
    stored = users.get_user(created["id"], db_path)
    assert stored["name"] == payload


def test_injection_in_name_is_literal(db_path):
    users.add_user("Иван", db_path=db_path)

    assert users.get_user_by_name("' OR '1'='1", db_path) is None
    assert users.count_users(db_path) == 1

    dropped = "'); DROP TABLE users; --"
    users.add_user(dropped, db_path=db_path)
    assert users.count_users(db_path) == 2


# ---------------------------------------------------------------- is_admin

@pytest.mark.parametrize("value", [None, "admin", {"role": "Admin"}, {}, 123, {"role": "user"}])
def test_is_admin_strict(value):
    assert users.is_admin(value) is False


def test_is_admin_true_only_for_admin_role():
    assert users.is_admin({"role": "admin"}) is True


# ---------------------------------------------------------------- пароли

def test_password_hash_is_not_reversible():
    stored = users.hash_password("secret123")

    assert stored != "secret123"
    assert stored != "secret123"[::-1]
    assert "secret123" not in stored
    assert "$" in stored
    assert users.verify_password("secret123", stored) is True
    assert users.verify_password("другой пароль", stored) is False


def test_same_password_gives_different_hashes():
    first = users.hash_password("secret123")
    second = users.hash_password("secret123")
    assert first != second, "соль должна быть случайной"


def test_password_stored_in_db(db_path):
    created = users.add_user("Иван", password="secret123", db_path=db_path)
    stored = users.get_password_hash(created["id"], db_path)

    assert stored is not None
    assert "secret123" not in stored
    assert users.verify_password("secret123", stored) is True


def test_broken_hash_is_rejected():
    assert users.verify_password("secret123", "не-хеш") is False
    assert users.verify_password("secret123", "") is False


# ---------------------------------------------------------------- активные

def test_active_limit_respected(db_path):
    ids = [users.add_user(f"u{index}", db_path=db_path)["id"] for index in range(5)]

    snapshot = []
    for user_id in ids:
        snapshot = users.activate(user_id, db_path, limit=3)

    assert snapshot == ids[-3:]
    assert len(users.active_snapshot()) == 3


def test_activate_unknown_user(db_path):
    with pytest.raises(users.UserNotFound):
        users.activate(999, db_path)


def test_active_users_thread_safe(db_path):
    user_id = users.add_user("Иван", db_path=db_path)["id"]

    def worker() -> None:
        users.activate(user_id, db_path, limit=5)

    threads = [threading.Thread(target=worker) for _ in range(200)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    snapshot = users.active_snapshot()
    assert len(snapshot) == 5
    assert all(item == user_id for item in snapshot)


def test_snapshot_is_a_copy():
    snapshot = users.active_snapshot()
    snapshot.append(12345)
    assert users.active_snapshot() == []


# ---------------------------------------------------------------- валидация

@pytest.mark.parametrize("name", ["", "   ", None, 123, "я" * 81])
def test_name_validation(db_path, name):
    with pytest.raises(users.UserError):
        users.add_user(name, db_path=db_path)


@pytest.mark.parametrize(
    "tags",
    [["ок" * 21], [str(index) for index in range(11)], [123], "строка вместо списка"],
)
def test_tags_validation(db_path, tags):
    with pytest.raises(users.UserError):
        users.add_user("Иван", tags, db_path=db_path)


def test_short_password_rejected(db_path):
    with pytest.raises(users.UserError):
        users.add_user("Иван", password="123", db_path=db_path)