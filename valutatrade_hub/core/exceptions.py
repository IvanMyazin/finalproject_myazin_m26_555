"""Пользовательские исключения приложения."""


class CurrencyNotFoundError(Exception):
    """Валюта отсутствует в реестре."""
