"""Единая абстракция над JSON-хранилищем."""

from pathlib import Path
from threading import RLock
from typing import Callable, TypeVar

from valutatrade_hub.core.utils import JsonData, load_json, save_json

ResultType = TypeVar("ResultType")


class DatabaseManager:
    """Singleton для безопасных операций с JSON-файлами."""

    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._lock = RLock()
        self._initialized = True

    def read_json(
        self,
        file_path: str | Path,
        default: JsonData | None = None,
    ) -> JsonData:
        """Прочитать данные под общей блокировкой."""
        with self._lock:
            return load_json(file_path, default)

    def update_json(
        self,
        file_path: str | Path,
        update: Callable[[JsonData], ResultType],
        default: JsonData | None = None,
    ) -> ResultType:
        """Атомарно для процесса выполнить чтение, изменение и запись."""
        with self._lock:
            data = load_json(file_path, default)
            result = update(data)
            save_json(file_path, data)
            return result
