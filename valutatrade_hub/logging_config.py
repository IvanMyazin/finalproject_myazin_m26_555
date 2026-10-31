"""Настройка логирования доменных операций."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import PROJECT_ROOT, SettingsLoader

LOGGER_NAME = "valutatrade.actions"
PARSER_LOGGER_NAME = "valutatrade.parser"


def get_action_logger() -> logging.Logger:
    """Вернуть настроенный логгер с ротацией файлов по размеру."""
    return _get_rotating_logger(LOGGER_NAME, "log_file", "logs/actions.log")


def get_parser_logger() -> logging.Logger:
    """Вернуть логгер операций Parser Service."""
    return _get_rotating_logger(
        PARSER_LOGGER_NAME,
        "parser_log_file",
        "logs/parser.log",
    )


def _get_rotating_logger(
    logger_name: str,
    file_setting: str,
    default_file: str,
) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    settings = SettingsLoader()
    level_name = str(settings.get("log_level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    log_path = Path(settings.get(file_setting, default_file))
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
