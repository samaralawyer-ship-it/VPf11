"""Проверка всех эндпоинтов живого сервиса.

    python test_endpoints.py
    python test_endpoints.py --url http://127.0.0.1:8090
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx


def check(client: httpx.Client, label: str, method: str, url: str, **kwargs) -> tuple[bool, str]:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        return False, f"{label}: сбой соединения ({exc})"

    body = response.text.replace("\n", " ")[:120]
    return True, f"{label}: {response.status_code} | {body}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка эндпоинтов users API")
    parser.add_argument("--url", default="http://127.0.0.1:8090", help="базовый адрес сервиса")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    name = f"Гость {int(time.time())}"
    failures: list[str] = []

    def expect(label: str, method: str, path: str, expected: int, **kwargs) -> httpx.Response | None:
        try:
            response = httpx.request(method, f"{base}{path}", timeout=15, **kwargs)
        except httpx.HTTPError as exc:
            failures.append(f"{label}: нет связи ({exc})")
            print(f"FAIL {label}: {exc}")
            return None
        ok = response.status_code == expected
        body = response.text.replace("\n", " ")[:110]
        print(f"{'ok  ' if ok else 'FAIL'} {label}: {response.status_code} (ждали {expected}) | {body}")
        if not ok:
            failures.append(f"{label}: {response.status_code} вместо {expected}")
        return response

    health = expect("GET /health", "GET", "/health", 200)
    created = expect("POST /adduser", "POST", "/adduser", 201, json={"name": name, "tags": ["тест", "api"], "password": "secret123"})
    user_id = None
    if created is not None and created.status_code == 201:
        user_id = created.json().get("id")

    if user_id is not None:
        expect("GET /user/<id>", "GET", f"/user/{user_id}", 200)
        expect("POST /activate/<id>", "POST", f"/activate/{user_id}", 202)

    expect("GET /user?name=", "GET", "/user", 200, params={"name": name})
    expect("GET /active", "GET", "/active", 200)
    expect("GET /slow", "GET", "/slow", 200, params={"n": 1000})
    expect("GET /wrong (404)", "GET", "/no-such-route", 404)
    expect("POST /adduser пустое имя", "POST", "/adduser", 400, json={"name": ""})
    expect("GET /user/999999", "GET", "/user/999999", 404)
    expect("GET /slow n=0", "GET", "/slow", 400, params={"n": 0})

    if health is not None and health.status_code == 200:
        print("health:", health.json())

    print()
    if failures:
        print("ПРОБЛЕМЫ:")
        for problem in failures:
            print("  -", problem)
        return 1

    print("все проверки прошли")
    return 0


if __name__ == "__main__":
    sys.exit(main())