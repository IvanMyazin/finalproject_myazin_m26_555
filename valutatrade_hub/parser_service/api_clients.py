"""Клиенты внешних сервисов курсов валют."""

from abc import ABC, abstractmethod
from time import perf_counter

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Общий интерфейс клиента внешнего API."""

    source: str

    def __init__(self) -> None:
        self.last_metadata: dict[str, dict[str, str | int]] = {}

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Получить курсы в формате ``КОД_КОД: значение``."""

    @staticmethod
    def _validate_rate(value: object, pair: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ApiRequestError(f"некорректный курс для {pair}")
        rate = float(value)
        if rate <= 0:
            raise ApiRequestError(f"курс для {pair} должен быть положительным")
        return rate

    @staticmethod
    def _request(
        url: str,
        timeout: int,
        params: dict[str, str] | None = None,
    ) -> tuple[dict[str, object], int, int, str]:
        started_at = perf_counter()
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except requests.exceptions.Timeout as error:
            raise ApiRequestError("превышено время ожидания ответа") from error
        except requests.exceptions.RequestException as error:
            raise ApiRequestError("не удалось подключиться к сервису курсов") from error

        request_ms = round((perf_counter() - started_at) * 1000)
        if response.status_code != 200:
            raise ApiRequestError(f"сервис вернул HTTP {response.status_code}")

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError as error:
            raise ApiRequestError("сервис вернул некорректный JSON") from error
        if not isinstance(data, dict):
            raise ApiRequestError("сервис вернул данные неизвестного формата")

        return data, request_ms, response.status_code, response.headers.get("ETag", "")


class CoinGeckoClient(BaseApiClient):
    """Получение курсов криптовалют из CoinGecko."""

    source = "CoinGecko"

    def __init__(self, config: ParserConfig | None = None) -> None:
        super().__init__()
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        coin_ids = [
            self.config.CRYPTO_ID_MAP[code] for code in self.config.CRYPTO_CURRENCIES
        ]
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": self.config.BASE_FIAT_CURRENCY.lower(),
        }
        data, request_ms, status_code, etag = self._request(
            self.config.COINGECKO_URL,
            self.config.REQUEST_TIMEOUT,
            params,
        )

        rates: dict[str, float] = {}
        self.last_metadata = {}
        base_code = self.config.BASE_FIAT_CURRENCY
        for code in self.config.CRYPTO_CURRENCIES:
            coin_id = self.config.CRYPTO_ID_MAP[code]
            coin_data = data.get(coin_id)
            if not isinstance(coin_data, dict):
                raise ApiRequestError(f"CoinGecko не вернул данные для {code}")

            pair = f"{code}_{base_code}"
            rate = self._validate_rate(coin_data.get(base_code.lower()), pair)
            rates[pair] = rate
            self.last_metadata[pair] = {
                "raw_id": coin_id,
                "request_ms": request_ms,
                "status_code": status_code,
                "etag": etag,
            }
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Получение курсов фиатных валют из ExchangeRate-API."""

    source = "ExchangeRate-API"

    def __init__(self, config: ParserConfig | None = None) -> None:
        super().__init__()
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        api_key = self.config.EXCHANGE_RATE_API_KEY
        if not api_key:
            raise ApiRequestError("не задан EXCHANGE_RATE_API_KEY")

        url = (
            f"{self.config.EXCHANGE_RATE_API_URL}/{api_key}/latest/"
            f"{self.config.BASE_FIAT_CURRENCY}"
        )
        data, request_ms, status_code, etag = self._request(
            url,
            self.config.REQUEST_TIMEOUT,
        )
        if data.get("result") != "success":
            reason = data.get("error-type", "неизвестная ошибка")
            raise ApiRequestError(f"ExchangeRate-API: {reason}")

        raw_rates = data.get("conversion_rates", data.get("rates"))
        if not isinstance(raw_rates, dict):
            raise ApiRequestError("ExchangeRate-API не вернул список курсов")

        rates: dict[str, float] = {}
        self.last_metadata = {}
        base_code = self.config.BASE_FIAT_CURRENCY
        for code in self.config.FIAT_CURRENCIES:
            pair = f"{code}_{base_code}"
            base_to_currency = self._validate_rate(raw_rates.get(code), pair)
            rates[pair] = 1 / base_to_currency
            self.last_metadata[pair] = {
                "request_ms": request_ms,
                "status_code": status_code,
                "etag": etag,
            }
        return rates
