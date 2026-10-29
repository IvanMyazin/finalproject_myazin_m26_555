"""Вспомогательные функции приложения."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"

JsonData = list[dict[str, object]] | dict[str, object]


def validate_amount(amount: object) -> float:
    """Проверить сумму операции и вернуть её как float."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise TypeError("Сумма должна быть числом")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    return float(amount)


def normalize_currency_code(currency_code: object) -> str:
    """Проверить и привести код валюты к верхнему регистру."""
    if not isinstance(currency_code, str) or not currency_code.strip():
        raise ValueError("Код валюты должен быть непустой строкой")
    return currency_code.strip().upper()


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
