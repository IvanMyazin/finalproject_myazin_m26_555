"""Вспомогательные функции приложения."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"

JsonData = list[dict[str, object]] | dict[str, object]


def load_json(file_path: str | Path, default: JsonData | None = None) -> JsonData:
    """Прочитать список или словарь из JSON-файла."""
    path = Path(file_path)

    if not path.exists():
        if default is None:
            return []
        return default.copy()

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"Файл {path.name} содержит некорректный JSON") from error

    if not isinstance(data, (list, dict)):
        raise ValueError(f"Файл {path.name} должен содержать список или словарь")

    return data


def save_json(file_path: str | Path, data: JsonData) -> None:
    """Сохранить список или словарь в JSON-файл."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
