"""Настройки Parser Service."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from valutatrade_hub.infra.settings import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class ParserConfig:
    """Параметры внешних API и файлов парсера."""

    EXCHANGE_RATE_API_KEY: str | None = field(
        default_factory=lambda: os.getenv("EXCHANGE_RATE_API_KEY")
    )

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGE_RATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_FIAT_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    RATES_FILE_PATH: Path = PROJECT_ROOT / "data" / "rates.json"
    HISTORY_FILE_PATH: Path = PROJECT_ROOT / "data" / "exchange_rates.json"
    REQUEST_TIMEOUT: int = 10
