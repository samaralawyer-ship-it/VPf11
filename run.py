"""Запуск сервиса через waitress: python run.py"""

from __future__ import annotations

import logging

from waitress import serve

from app.api import create_app
from app.config import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("serve")
    app = create_app()
    logger.info("слушаю %s:%s, база: %s", settings.host, settings.port, settings.db_path)
    serve(app, host=settings.host, port=settings.port, threads=4)


if __name__ == "__main__":
    main()