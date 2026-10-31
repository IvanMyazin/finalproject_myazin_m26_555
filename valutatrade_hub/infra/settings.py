"""Загрузка и кеширование конфигурации проекта."""

import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "pyproject.toml"


class SettingsLoader:
    """Единая точка доступа к настройкам приложения."""

    _instance: "SettingsLoader | None" = None

    # __new__ выбран для простоты: паттерн виден прямо в классе без метакласса.
    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._config_path = DEFAULT_CONFIG_PATH
        self._settings: dict[str, Any] = {}
        self.reload()
        self._initialized = True

    def get(self, key: str, default: Any = ...) -> Any:
        """Вернуть настройку или переданное значение по умолчанию."""
        if key in self._settings:
            return self._settings[key]
        if default is not ...:
            return default
        raise KeyError(f"Настройка '{key}' не найдена")

    def reload(self) -> None:
        """Повторно загрузить секцию tool.valutatrade из pyproject.toml."""
        with self._config_path.open("rb") as config_file:
            config = tomllib.load(config_file)

        tool_settings = config.get("tool", {}).get("valutatrade", {})
        if not isinstance(tool_settings, dict):
            raise ValueError("Секция [tool.valutatrade] должна быть таблицей TOML")
        self._settings = tool_settings.copy()
