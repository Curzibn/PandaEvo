from __future__ import annotations

import logging
from datetime import datetime
from logging import Logger
from pathlib import Path

from app.config import get_env, get_service_data_dir

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(console)

    if get_env() == "dev":
        now = datetime.now()
        log_dir = get_service_data_dir() / "logs" / "python-service" / now.strftime("%Y-%m-%d")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / now.strftime("%H-%M-%S.log")

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(file_handler)


def get_logger(name: str) -> Logger:
    return logging.getLogger(name)
