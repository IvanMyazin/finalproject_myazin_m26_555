"""Координация загрузки и сохранения курсов."""

import logging
from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import get_parser_logger
from valutatrade_hub.parser_service.api_clients import BaseApiClient
from valutatrade_hub.parser_service.storage import RatesStorage


class RatesUpdater:
    """Получение курсов от клиентов и передача их в хранилище."""

    def __init__(
        self,
        clients: list[BaseApiClient],
        storage: RatesStorage,
        logger: logging.Logger | None = None,
    ) -> None:
        self.clients = clients
        self.storage = storage
        self.logger = logger or get_parser_logger()
        self.last_errors: list[tuple[str, str]] = []
        self.last_results: dict[str, int] = {}
        self.last_refresh = ""

    def run_update(self) -> dict[str, dict[str, object]]:
        """Последовательно опросить клиентов и сохранить успешные ответы."""
        self.last_errors = []
        self.last_results = {}
        self.last_refresh = ""
        self.logger.info("UPDATE_RATES result=STARTED")
        updated_at = (
            datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        combined_rates: dict[str, dict[str, object]] = {}

        for client in self.clients:
            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                self.last_errors.append((client.source, str(error)))
                self.logger.info(
                    "UPDATE_RATES source='%s' result=ERROR error_message='%s'",
                    client.source,
                    str(error).replace("\n", " "),
                )
                continue

            self.last_results[client.source] = len(rates)

            for pair, rate in rates.items():
                combined_rates[pair] = {
                    "rate": rate,
                    "updated_at": updated_at,
                    "source": client.source,
                    "meta": client.last_metadata.get(pair, {}),
                }
            self.logger.info(
                "UPDATE_RATES source='%s' pairs=%s result=OK",
                client.source,
                len(rates),
            )

        if not combined_rates:
            self.logger.info("UPDATE_RATES result=ERROR error_message='нет данных'")
            raise ApiRequestError("не удалось получить курсы ни от одного источника")

        self.storage.save(combined_rates, updated_at)
        self.last_refresh = updated_at
        self.logger.info(
            "UPDATE_RATES pairs=%s result=OK",
            len(combined_rates),
        )
        return combined_rates
