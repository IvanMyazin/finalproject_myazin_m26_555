"""Хранение истории и актуального кеша курсов."""

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from valutatrade_hub.core.utils import load_json
from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    """Атомарное сохранение результатов Parser Service в JSON."""

    def __init__(self, config: ParserConfig | None = None) -> None:
        config = config or ParserConfig()
        self.rates_file = config.RATES_FILE_PATH
        self.history_file = config.HISTORY_FILE_PATH
        self._lock = RLock()

    def save(
        self,
        rates: dict[str, dict[str, object]],
        last_refresh: str,
    ) -> None:
        """Добавить измерения в историю и обновить последний кеш."""
        self._validate_rates(rates)
        with self._lock:
            self._append_history(rates)
            self._update_cache(rates, last_refresh)

    def _append_history(self, rates: dict[str, dict[str, object]]) -> None:
        data = load_json(self.history_file, [])
        if not isinstance(data, list):
            raise ValueError("Файл exchange_rates.json должен содержать список")

        known_ids = {
            item.get("id")
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for pair, details in rates.items():
            timestamp = str(details["updated_at"])
            record_id = f"{pair}_{timestamp}"
            if record_id in known_ids:
                continue

            from_code, to_code = pair.split("_", maxsplit=1)
            data.append(
                {
                    "id": record_id,
                    "from_currency": from_code,
                    "to_currency": to_code,
                    "rate": details["rate"],
                    "timestamp": timestamp,
                    "source": details["source"],
                    "meta": details.get("meta", {}),
                }
            )
            known_ids.add(record_id)
        self._atomic_write(self.history_file, data)

    def _update_cache(
        self,
        rates: dict[str, dict[str, object]],
        last_refresh: str,
    ) -> None:
        data = load_json(self.rates_file, {})
        if not isinstance(data, dict):
            raise ValueError("Файл rates.json должен содержать словарь")

        pairs = self._extract_existing_pairs(data)
        for pair, details in rates.items():
            current = pairs.get(pair)
            if current is None or self._is_newer(
                str(details["updated_at"]),
                str(current.get("updated_at", "")),
            ):
                pairs[pair] = {
                    "rate": details["rate"],
                    "updated_at": details["updated_at"],
                    "source": details["source"],
                }

        current_refresh = data.get("last_refresh", "")
        if isinstance(current_refresh, str) and not self._is_newer(
            last_refresh, current_refresh
        ):
            last_refresh = current_refresh
        cache = {"pairs": pairs, "last_refresh": last_refresh}
        self._atomic_write(self.rates_file, cache)

    @staticmethod
    def _validate_rates(rates: dict[str, dict[str, object]]) -> None:
        for pair, details in rates.items():
            codes = pair.split("_")
            if len(codes) != 2 or any(
                not code.isalpha() or not code.isupper() or not 2 <= len(code) <= 5
                for code in codes
            ):
                raise ValueError(f"Некорректная валютная пара '{pair}'")

            rate = details.get("rate")
            if (
                isinstance(rate, bool)
                or not isinstance(rate, (int, float))
                or rate <= 0
            ):
                raise ValueError(f"Некорректный курс для '{pair}'")
            timestamp = details.get("updated_at")
            source = details.get("source")
            if not isinstance(timestamp, str):
                raise ValueError(f"Не указано время обновления '{pair}'")
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError(f"Некорректное время обновления '{pair}'") from error
            if not isinstance(source, str) or not source:
                raise ValueError(f"Не указан источник курса '{pair}'")

    @staticmethod
    def _extract_existing_pairs(
        data: dict[str, object],
    ) -> dict[str, dict[str, object]]:
        nested_pairs = data.get("pairs")
        if isinstance(nested_pairs, dict):
            return {
                pair: details
                for pair, details in nested_pairs.items()
                if isinstance(pair, str) and isinstance(details, dict)
            }

        source = str(data.get("source", "Unknown"))
        return {
            pair: {**details, "source": details.get("source", source)}
            for pair, details in data.items()
            if "_" in pair and isinstance(details, dict)
        }

    @staticmethod
    def _is_newer(new_timestamp: str, current_timestamp: str) -> bool:
        try:
            new_time = datetime.fromisoformat(new_timestamp.replace("Z", "+00:00"))
            current_time = datetime.fromisoformat(
                current_timestamp.replace("Z", "+00:00")
            )
        except ValueError:
            return True
        return new_time > current_time

    @staticmethod
    def _atomic_write(path: Path, data: list[object] | dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                json.dump(data, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_path = Path(temporary_file.name)
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
