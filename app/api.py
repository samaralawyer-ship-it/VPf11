"""Flask-приложение: маршруты users API."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from app import users
from app.config import settings
from app.db import init_db, ping

logger = logging.getLogger(__name__)

SLOW_MAX = 100_000


HTTP_MESSAGES = {
    400: "некорректный запрос",
    404: "маршрут не найден",
    405: "метод не разрешён для этого маршрута",
}


def create_app(db_path: Path | str | None = None, active_limit: int | None = None) -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config["DB_PATH"] = str(db_path) if db_path is not None else str(settings.db_path)
    app.config["ACTIVE_LIMIT"] = int(active_limit or settings.active_limit)
    init_db(app.config["DB_PATH"])

    def db() -> str:
        return app.config["DB_PATH"]

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        message = HTTP_MESSAGES.get(error.code, error.description)
        return jsonify({"error": message, "status": error.code}), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception):
        logger.exception("необработанная ошибка: %s", error)
        return jsonify({"error": "internal server error", "status": 500}), 500

    @app.get("/health")
    def health():
        ok = ping(db())
        payload = {"status": "ok" if ok else "degraded", "db": "ok" if ok else "fail"}
        return jsonify(payload), (200 if ok else 503)

    @app.post("/adduser")
    def adduser():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "ожидался JSON-объект"}), 400

        try:
            user = users.add_user(
                name=payload.get("name"),
                tags=payload.get("tags"),
                password=payload.get("password"),
                db_path=db(),
            )
        except users.UserError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(user), 201

    @app.get("/user/<int:user_id>")
    def user_by_id(user_id: int):
        user = users.get_user(user_id, db())
        if user is None:
            return jsonify({"error": f"пользователь {user_id} не найден"}), 404
        return jsonify(user), 200

    @app.get("/user")
    def user_by_name():
        name = request.args.get("name", "")
        try:
            user = users.get_user_by_name(name, db())
        except users.UserError as exc:
            return jsonify({"error": str(exc)}), 400
        if user is None:
            return jsonify({"error": f"пользователь «{name}» не найден"}), 404
        return jsonify(user), 200

    @app.post("/activate/<int:user_id>")
    def activate(user_id: int):
        try:
            snapshot = users.activate(user_id, db(), app.config["ACTIVE_LIMIT"])
        except users.UserNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except users.UserError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"active": snapshot, "count": len(snapshot)}), 202

    @app.get("/active")
    def active():
        snapshot = users.active_snapshot()
        return jsonify({"active": snapshot, "count": len(snapshot)}), 200

    @app.get("/slow")
    def slow():
        raw = request.args.get("n", "1000")
        try:
            n = int(raw)
        except (TypeError, ValueError):
            return jsonify({"error": "n должно быть целым числом"}), 400
        if not 1 <= n <= SLOW_MAX:
            return jsonify({"error": f"n должно быть от 1 до {SLOW_MAX}"}), 400

        started = time.perf_counter()
        result = sum(index * index for index in range(n))
        return jsonify(
            {"n": n, "result": result, "seconds": round(time.perf_counter() - started, 4)}
        ), 200

    return app