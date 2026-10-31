"""Основные классы платформы ValutaTrade Hub."""

from __future__ import annotations

import hashlib
from datetime import datetime

from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.utils import normalize_currency_code, validate_amount


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
        self.currency_code = normalize_currency_code(currency_code)
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
        amount = validate_amount(amount)
        self.balance += amount

    def withdraw(self, amount: float) -> None:
        """Снять с кошелька положительную сумму, если средств достаточно."""
        amount = validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(self._balance, amount, self.currency_code)
        self.balance -= amount

    def get_balance_info(self) -> dict[str, str | float]:
        """Вернуть код валюты и текущий баланс."""
        return {
            "currency_code": self.currency_code,
            "balance": self._balance,
        }


class Portfolio:
    """Набор валютных кошельков одного пользователя."""

    exchange_rates = {
        "USD": 1.0,
        "EUR": 1.0786,
        "RUB": 0.01016,
        "BTC": 59_337.21,
        "ETH": 3_720.0,
    }

    def __init__(
        self,
        user: User,
        wallets: dict[str, Wallet] | None = None,
    ) -> None:
        if not isinstance(user, User):
            raise TypeError("Портфель должен принадлежать объекту User")

        self._user = user
        self._user_id = user.user_id
        self._wallets: dict[str, Wallet] = {}

        if wallets is not None:
            for wallet in wallets.values():
                if not isinstance(wallet, Wallet):
                    raise TypeError("В портфеле могут храниться только объекты Wallet")
                self._wallets[wallet.currency_code] = wallet

    @property
    def user(self) -> User:
        """Вернуть пользователя, которому принадлежит портфель."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Вернуть копию словаря кошельков."""
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> None:
        """Добавить пустой кошелёк для новой валюты."""
        normalized_code = normalize_currency_code(currency_code)
        if normalized_code in self._wallets:
            raise ValueError(f"Кошелёк {normalized_code} уже существует")

        self._wallets[normalized_code] = Wallet(normalized_code)

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Вернуть кошелёк по коду валюты или None, если его нет."""
        normalized_code = normalize_currency_code(currency_code)
        return self._wallets.get(normalized_code)

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Рассчитать стоимость всех кошельков в базовой валюте."""
        normalized_base = normalize_currency_code(base_currency)
        if normalized_base not in self.exchange_rates:
            raise ValueError(f"Неизвестный курс валюты {normalized_base}")

        total_in_usd = 0.0
        for currency_code, wallet in self._wallets.items():
            if currency_code not in self.exchange_rates:
                raise ValueError(f"Неизвестный курс валюты {currency_code}")
            total_in_usd += wallet.balance * self.exchange_rates[currency_code]

        return total_in_usd / self.exchange_rates[normalized_base]
