"""Бизнес-логика приложения."""

import secrets
from datetime import datetime, timedelta
from pathlib import Path

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError, InsufficientFundsError
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import (
    PROJECT_ROOT,
    JsonData,
    normalize_currency_code,
    validate_amount,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


def _get_configured_path(settings: SettingsLoader, key: str) -> Path:
    """Преобразовать путь из конфигурации в абсолютный путь проекта."""
    path = Path(settings.get(key))
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


class RateService:
    """Получение обменных курсов из локального JSON-кеша."""

    def __init__(self, rates_file: str | Path | None = None) -> None:
        self._settings = SettingsLoader()
        self._database = DatabaseManager()
        self._rates_file = (
            Path(rates_file)
            if rates_file is not None
            else _get_configured_path(self._settings, "rates_file")
        )
        self._rates_ttl_seconds = int(self._settings.get("rates_ttl_seconds", 300))
        self._default_base_currency = str(
            self._settings.get("default_base_currency", "USD")
        )

    def get_rate(
        self,
        from_currency: str,
        to_currency: str | None = None,
    ) -> dict[str, str | float]:
        """Вернуть курс и время обновления локального кеша."""
        from_code = normalize_currency_code(from_currency)
        if to_currency is None:
            to_currency = self._default_base_currency
        to_code = normalize_currency_code(to_currency)
        get_currency(from_code)
        get_currency(to_code)

        data = self._database.read_json(self._rates_file, {})
        if not isinstance(data, dict):
            raise ValueError("Файл курсов должен содержать словарь")

        pairs = self._extract_pairs(data)
        rate = self._calculate_rate(pairs, from_code, to_code)
        updated_at = self._find_updated_at(pairs, from_code, to_code)
        if not updated_at:
            last_refresh = data.get("last_refresh", "")
            updated_at = last_refresh if isinstance(last_refresh, str) else ""
        if self._is_outdated(updated_at):
            raise ApiRequestError(f"данные курса {from_code}→{to_code} устарели")

        return {
            "from_currency": from_code,
            "to_currency": to_code,
            "rate": rate,
            "updated_at": updated_at,
        }

    @staticmethod
    def _extract_pairs(data: dict[str, object]) -> dict[str, object]:
        """Поддержать новый вложенный и прежний плоский формат кеша."""
        pairs = data.get("pairs")
        if isinstance(pairs, dict):
            return pairs
        return data

    @classmethod
    def _calculate_rate(
        cls,
        rates: dict[str, object],
        from_code: str,
        to_code: str,
    ) -> float:
        """Рассчитать прямой, обратный или кросс-курс."""
        if from_code == to_code:
            return 1.0

        direct_rate = cls._find_direct_rate(rates, from_code, to_code)
        if direct_rate is not None:
            return direct_rate

        from_usd = cls._find_direct_rate(rates, from_code, "USD")
        to_usd = cls._find_direct_rate(rates, to_code, "USD")
        if from_usd is None or to_usd is None:
            raise ApiRequestError(f"курс {from_code}→{to_code} недоступен")
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

    @staticmethod
    def _find_updated_at(
        rates: dict[str, object],
        from_code: str,
        to_code: str,
    ) -> str:
        """Найти время обновления прямой или обратной пары."""
        for pair in (f"{from_code}_{to_code}", f"{to_code}_{from_code}"):
            pair_data = rates.get(pair)
            if isinstance(pair_data, dict):
                updated_at = pair_data.get("updated_at")
                if isinstance(updated_at, str):
                    return updated_at

        last_refresh = rates.get("last_refresh")
        if isinstance(last_refresh, str):
            return last_refresh
        return ""

    def _is_outdated(self, updated_at: str) -> bool:
        """Проверить, прошло ли с обновления курса больше пяти минут."""
        try:
            updated_time = datetime.fromisoformat(updated_at)
        except ValueError:
            return True
        current_time = datetime.now(updated_time.tzinfo)
        return current_time - updated_time > timedelta(seconds=self._rates_ttl_seconds)


class TradingService:
    """Регистрация, сессия и операции с портфелем пользователя."""

    def __init__(
        self,
        users_file: str | Path | None = None,
        portfolios_file: str | Path | None = None,
        rates_file: str | Path | None = None,
    ) -> None:
        self._settings = SettingsLoader()
        self._database = DatabaseManager()
        self._users_file = (
            Path(users_file)
            if users_file is not None
            else _get_configured_path(self._settings, "users_file")
        )
        self._portfolios_file = (
            Path(portfolios_file)
            if portfolios_file is not None
            else _get_configured_path(self._settings, "portfolios_file")
        )
        self.default_base_currency = str(
            self._settings.get("default_base_currency", "USD")
        )
        self.rate_service = RateService(rates_file)
        self.current_user: User | None = None

    def register(self, username: str, password: str) -> User:
        """Зарегистрировать пользователя и создать пустой портфель."""
        username = self._validate_username(username)
        self._validate_password(password)

        def add_user(data: JsonData) -> User:
            users = self._validate_records(data, "пользователей")
            if any(record.get("username") == username for record in users):
                raise ValueError(f"Имя пользователя '{username}' уже занято")

            user_ids = [record.get("user_id", 0) for record in users]
            user_id = (
                max(
                    (value for value in user_ids if isinstance(value, int)),
                    default=0,
                )
                + 1
            )
            user = User(
                user_id,
                username,
                "",
                secrets.token_hex(8),
                datetime.now(),
            )
            user.change_password(password)
            users.append(self._user_to_record(user))
            return user

        user = self._database.update_json(self._users_file, add_user, [])

        def add_portfolio(data: JsonData) -> None:
            portfolios = self._validate_records(data, "портфелей")
            portfolios.append({"user_id": user.user_id, "wallets": {}})

        self._database.update_json(self._portfolios_file, add_portfolio, [])
        return user

    def login(self, username: str, password: str) -> User:
        """Проверить пароль и сохранить пользователя текущей сессии."""
        username = self._validate_username(username)
        users = self._load_records(self._users_file, "пользователей")
        record = next(
            (item for item in users if item.get("username") == username),
            None,
        )
        if record is None:
            raise ValueError(f"Пользователь '{username}' не найден")

        user = self._record_to_user(record)
        if not user.verify_password(password):
            raise ValueError("Неверный пароль")

        self.current_user = user
        return user

    def show_portfolio(
        self,
        base_currency: str | None = None,
    ) -> tuple[list[dict[str, str | float]], float]:
        """Вернуть кошельки и итоговую стоимость в базовой валюте."""
        user = self._require_login()
        if base_currency is None:
            base_currency = self.default_base_currency
        base_code = normalize_currency_code(base_currency)
        self.rate_service.get_rate(base_code, "USD")

        portfolio = self._load_portfolio(user)
        rows: list[dict[str, str | float]] = []
        total = 0.0
        for currency_code, wallet in portfolio.wallets.items():
            rate_info = self.rate_service.get_rate(currency_code, base_code)
            rate = float(rate_info["rate"])
            value = wallet.balance * rate
            total += value
            rows.append(
                {
                    "currency_code": currency_code,
                    "balance": wallet.balance,
                    "value": value,
                }
            )
        return rows, total

    @log_action("BUY", verbose=True)
    def buy(
        self,
        user_id: int,
        currency_code: str,
        amount: float,
    ) -> dict[str, str | float]:
        """Добавить купленную валюту в портфель пользователя."""
        user = self._require_user(user_id)
        amount = validate_amount(amount)
        currency = get_currency(currency_code)
        code = currency.code
        rate_info = self.rate_service.get_rate(code, "USD")
        rate = float(rate_info["rate"])

        portfolio = self._load_portfolio(user)
        wallet = portfolio.get_wallet(code)
        if wallet is None:
            portfolio.add_currency(code)
            wallet = portfolio.get_wallet(code)

        previous_balance = wallet.balance
        wallet.deposit(amount)
        self._save_portfolio(portfolio)
        return {
            "currency_code": code,
            "amount": amount,
            "rate": rate,
            "previous_balance": previous_balance,
            "new_balance": wallet.balance,
            "value": amount * rate,
        }

    @log_action("SELL", verbose=True)
    def sell(
        self,
        user_id: int,
        currency_code: str,
        amount: float,
    ) -> dict[str, str | float]:
        """Уменьшить баланс продаваемой валюты пользователя."""
        user = self._require_user(user_id)
        amount = validate_amount(amount)
        currency = get_currency(currency_code)
        code = currency.code
        portfolio = self._load_portfolio(user)
        wallet = portfolio.get_wallet(code)
        if wallet is None:
            raise InsufficientFundsError(0.0, amount, code)
        if amount > wallet.balance:
            raise InsufficientFundsError(wallet.balance, amount, code)

        rate_info = self.rate_service.get_rate(code, "USD")
        rate = float(rate_info["rate"])

        previous_balance = wallet.balance
        wallet.withdraw(amount)
        self._save_portfolio(portfolio)
        return {
            "currency_code": code,
            "amount": amount,
            "rate": rate,
            "previous_balance": previous_balance,
            "new_balance": wallet.balance,
            "value": amount * rate,
        }

    def _require_login(self) -> User:
        if self.current_user is None:
            raise ValueError("Сначала выполните login")
        return self.current_user

    def _require_user(self, user_id: int) -> User:
        """Проверить сессию и соответствие переданного пользователя."""
        user = self._require_login()
        if user.user_id != user_id:
            raise ValueError("Нельзя выполнять операции с чужим портфелем")
        return user

    def _load_portfolio(self, user: User) -> Portfolio:
        records = self._load_records(self._portfolios_file, "портфелей")
        record = next(
            (item for item in records if item.get("user_id") == user.user_id),
            None,
        )
        if record is None:
            raise ValueError("Портфель пользователя не найден")

        wallets_data = record.get("wallets", {})
        if not isinstance(wallets_data, dict):
            raise ValueError("Некорректный формат кошельков в portfolios.json")

        wallets: dict[str, Wallet] = {}
        for currency_code, wallet_data in wallets_data.items():
            if not isinstance(currency_code, str) or not isinstance(wallet_data, dict):
                raise ValueError("Некорректный формат кошелька в portfolios.json")
            wallets[currency_code] = Wallet(
                currency_code,
                wallet_data.get("balance", 0.0),
            )
        return Portfolio(user, wallets)

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        wallets = {
            code: {"balance": wallet.balance}
            for code, wallet in portfolio.wallets.items()
        }

        def update_portfolio(data: JsonData) -> None:
            records = self._validate_records(data, "портфелей")
            for record in records:
                if record.get("user_id") == portfolio.user.user_id:
                    record["wallets"] = wallets
                    return
            raise ValueError("Портфель пользователя не найден")

        self._database.update_json(self._portfolios_file, update_portfolio, [])

    def _load_records(
        self,
        file_path: Path,
        data_name: str,
    ) -> list[dict[str, object]]:
        data = self._database.read_json(file_path, [])
        return self._validate_records(data, data_name)

    @staticmethod
    def _validate_records(
        data: JsonData,
        data_name: str,
    ) -> list[dict[str, object]]:
        if not isinstance(data, list) or not all(
            isinstance(item, dict) for item in data
        ):
            raise ValueError(f"Файл {data_name} должен содержать список объектов")
        return data

    @staticmethod
    def _validate_username(username: object) -> str:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        return username.strip()

    @staticmethod
    def _validate_password(password: object) -> None:
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

    @staticmethod
    def _user_to_record(user: User) -> dict[str, object]:
        return {
            "user_id": user.user_id,
            "username": user.username,
            "hashed_password": user.hashed_password,
            "salt": user.salt,
            "registration_date": user.registration_date.isoformat(),
        }

    @staticmethod
    def _record_to_user(record: dict[str, object]) -> User:
        try:
            return User(
                user_id=int(record["user_id"]),
                username=str(record["username"]),
                hashed_password=str(record["hashed_password"]),
                salt=str(record["salt"]),
                registration_date=datetime.fromisoformat(
                    str(record["registration_date"])
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Некорректная запись пользователя в users.json") from error
