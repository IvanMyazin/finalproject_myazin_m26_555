"""Основные классы платформы ValutaTrade Hub."""

from __future__ import annotations

import hashlib
from datetime import datetime


class User:
    """Пользователь системы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        """Вернуть идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Вернуть имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """Изменить имя пользователя после проверки."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        """Вернуть хеш пароля."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Вернуть соль пользователя."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Вернуть дату регистрации."""
        return self._registration_date

    def get_user_info(self) -> dict[str, int | str]:
        """Вернуть открытые данные пользователя без пароля и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Проверить и сохранить хеш нового пароля."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")

        password_with_salt = new_password + self._salt
        self._hashed_password = hashlib.sha256(
            password_with_salt.encode("utf-8")
        ).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Проверить, совпадает ли введённый пароль с сохранённым."""
        password_with_salt = password + self._salt
        password_hash = hashlib.sha256(password_with_salt.encode("utf-8")).hexdigest()
        return password_hash == self._hashed_password


class Wallet:
    """Кошелёк пользователя для одной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")

        self.currency_code = currency_code.strip().upper()
        self.balance = balance

    @property
    def balance(self) -> float:
        """Вернуть текущий баланс."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Установить неотрицательное числовое значение баланса."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополнить кошелёк на положительную сумму."""
        self._validate_amount(amount)
        self.balance += amount

    def withdraw(self, amount: float) -> None:
        """Снять с кошелька положительную сумму, если средств достаточно."""
        self._validate_amount(amount)
        if amount > self._balance:
            raise ValueError("Недостаточно средств на балансе")
        self.balance -= amount

    def get_balance_info(self) -> dict[str, str | float]:
        """Вернуть код валюты и текущий баланс."""
        return {
            "currency_code": self.currency_code,
            "balance": self._balance,
        }

    @staticmethod
    def _validate_amount(amount: float) -> None:
        """Проверить сумму пополнения или снятия."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом")
        if amount <= 0:
            raise ValueError("Сумма должна быть больше нуля")
