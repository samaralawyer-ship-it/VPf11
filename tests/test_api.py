"""Тесты HTTP-контрактов через test_client."""

import pytest

from app import users
from app.api import create_app


@pytest.fixture()
def client(tmp_path):
    users.reset_active()
    app = create_app(db_path=tmp_path / "api.db", active_limit=3)
    with app.test_client() as test_client:
        yield test_client
    users.reset_active()


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert response.json["db"] == "ok"


def test_adduser_created(client):
    response = client.post("/adduser", json={"name": "Иван", "tags": ["тест"]})

    assert response.status_code == 201
    body = response.json
    assert isinstance(body["id"], int)
    assert body["name"] == "Иван"
    assert body["tags"] == ["тест"]


def test_adduser_without_json(client):
    response = client.post("/adduser", data="не json")
    assert response.status_code == 400
    assert "error" in response.json


def test_adduser_empty_name(client):
    response = client.post("/adduser", json={"name": "  "})
    assert response.status_code == 400


def test_password_not_returned(client):
    response = client.post("/adduser", json={"name": "Иван", "password": "secret123"})
    body = response.json

    assert "password" not in body
    assert "hash" not in body


def test_get_user_by_id(client):
    user_id = client.post("/adduser", json={"name": "Иван"}).json["id"]

    response = client.get(f"/user/{user_id}")
    assert response.status_code == 200
    assert response.json["id"] == user_id

    missing = client.get("/user/999999")
    assert missing.status_code == 404
    assert "error" in missing.json


def test_get_user_by_name(client):
    client.post("/adduser", json={"name": "Мария"})

    found = client.get("/user", query_string={"name": "Мария"})
    assert found.status_code == 200

    missing = client.get("/user", query_string={"name": "нет такой"})
    assert missing.status_code == 404

    empty = client.get("/user")
    assert empty.status_code == 400


def test_activate_endpoint(client):
    user_id = client.post("/adduser", json={"name": "Иван"}).json["id"]

    response = client.post(f"/activate/{user_id}")
    assert response.status_code == 202
    assert user_id in response.json["active"]

    missing = client.post("/activate/999999")
    assert missing.status_code == 404


def test_active_endpoint(client):
    user_id = client.post("/adduser", json={"name": "Иван"}).json["id"]
    client.post(f"/activate/{user_id}")

    response = client.get("/active")
    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["active"] == [user_id]


def test_slow_endpoint(client):
    response = client.get("/slow", query_string={"n": 1000})
    assert response.status_code == 200
    assert response.json["result"] == 332833500


@pytest.mark.parametrize("n", ["0", "-5", "100001", "abc"])
def test_slow_bad_input(client, n):
    response = client.get("/slow", query_string={"n": n})
    assert response.status_code == 400


def test_unknown_route_returns_json(client):
    response = client.get("/no-such-route")
    assert response.status_code == 404
    assert "error" in response.json


def test_method_not_allowed_returns_json(client):
    response = client.get("/adduser")
    assert response.status_code == 405
    assert "error" in response.json

def test_russian_text_is_utf8(client):
    response = client.post("/adduser", json={"name": "Иван"})
    assert "Иван".encode("utf-8") in response.data


def test_error_message_in_russian(client):
    response = client.get("/no-such-route")
    assert "маршрут не найден" in response.json["error"]