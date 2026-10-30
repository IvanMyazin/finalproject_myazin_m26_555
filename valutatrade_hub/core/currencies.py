"""Классы фиатных и криптовалют."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Общий интерфейс валюты."""

    def __init__(self, name: str, code: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        if (
            not isinstance(code, str)
            or not 2 <= len(code) <= 5
            or not code.isupper()
            or any(character.isspace() for character in code)
        ):
            raise ValueError(
                "Код валюты должен содержать 2–5 символов в верхнем регистре"
            )

        self.name = name.strip()
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Вернуть строковое представление валюты для UI или логов."""


class FiatCurrency(Currency):
    """Фиатная валюта, выпущенная государством или валютной зоной."""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна или зона эмиссии не может быть пустой")
        self.issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        """Вернуть описание фиатной валюты."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и известной капитализацией."""

    def __init__(
        self,
        name: str,
        code: str,
        algorithm: str,
        market_cap: float,
    ) -> None:
        super().__init__(name, code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм криптовалюты не может быть пустым")
        if isinstance(market_cap, bool) or not isinstance(market_cap, (int, float)):
            raise TypeError("Капитализация должна быть числом")
        if market_cap < 0:
            raise ValueError("Капитализация не может быть отрицательной")

        self.algorithm = algorithm.strip()
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        """Вернуть описание криптовалюты."""
        short_market_cap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {short_market_cap})"
        )


CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.20e11),
}


def get_currency(code: str) -> Currency:
    """Вернуть объект валюты из реестра по её коду."""
    if not isinstance(code, str):
        raise CurrencyNotFoundError(f"Валюта '{code}' не найдена")

    normalized_code = code.strip().upper()
    currency = CURRENCY_REGISTRY.get(normalized_code)
    if currency is None:
        raise CurrencyNotFoundError(f"Валюта '{normalized_code}' не найдена")
    return currency
