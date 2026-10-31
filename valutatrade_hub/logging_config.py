"""Настройка логирования доменных операций."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import PROJECT_ROOT, SettingsLoader

LOGGER_NAME = "valutatrade.actions"


def get_action_logger() -> logging.Logger:
    """Вернуть настроенный логгер с ротацией файлов по размеру."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    settings = SettingsLoader()
    level_name = str(settings.get("log_level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    log_path = Path(settings.get("log_file", "logs/actions.log"))
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=int(settings.get("log_max_bytes", 1_048_576)),
        backupCount=int(settings.get("log_backup_count", 3)),
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        fmt=str(settings.get("log_format")),
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
