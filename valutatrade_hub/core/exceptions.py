"""Пользовательские исключения приложения."""


class InsufficientFundsError(Exception):
    """На кошельке недостаточно средств для операции."""

    def __init__(self, available: float, required: float, code: str) -> None:
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available} {code}, "
            f"требуется {required} {code}"
        )


class CurrencyNotFoundError(Exception):
    """Валюта отсутствует в реестре."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(Exception):
    """Не удалось получить данные от внешнего сервиса."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
