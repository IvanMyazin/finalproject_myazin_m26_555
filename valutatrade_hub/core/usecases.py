"""Бизнес-логика приложения."""

from pathlib import Path

from valutatrade_hub.core.utils import (
    RATES_FILE,
    load_json,
    normalize_currency_code,
    validate_amount,
)


class RateService:
    """Получение обменных курсов из локального JSON-кеша."""

    def __init__(self, rates_file: str | Path = RATES_FILE) -> None:
        self._rates_file = Path(rates_file)

    def get_rate(self, from_currency: str, to_currency: str = "USD") -> float:
        """Вернуть стоимость одной единицы первой валюты во второй."""
        from_code = normalize_currency_code(from_currency)
        to_code = normalize_currency_code(to_currency)

        if from_code == to_code:
            return 1.0

        rates = load_json(self._rates_file, {})
        if not isinstance(rates, dict):
            raise ValueError("Файл курсов должен содержать словарь")

        direct_rate = self._find_direct_rate(rates, from_code, to_code)
        if direct_rate is not None:
            return direct_rate

        from_usd = self._find_direct_rate(rates, from_code, "USD")
        to_usd = self._find_direct_rate(rates, to_code, "USD")
        if from_usd is None or to_usd is None:
            raise ValueError(f"Курс {from_code}/{to_code} не найден")

        return from_usd / to_usd

    @staticmethod
    def _find_direct_rate(
        rates: dict[str, object],
        from_code: str,
        to_code: str,
    ) -> float | None:
        """Найти прямой или обратный курс валютной пары."""
        direct_data = rates.get(f"{from_code}_{to_code}")
        if isinstance(direct_data, dict) and "rate" in direct_data:
            return validate_amount(direct_data["rate"])

        reverse_data = rates.get(f"{to_code}_{from_code}")
        if isinstance(reverse_data, dict) and "rate" in reverse_data:
            return 1 / validate_amount(reverse_data["rate"])

        return None
