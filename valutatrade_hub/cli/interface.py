"""Точка запуска консольного интерфейса."""

import shlex
import sys

from prettytable import PrettyTable

from valutatrade_hub.core.currencies import CURRENCY_REGISTRY
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import TradingService


class CommandInterface:
    """Разбор пользовательских команд и форматирование результата."""

    def __init__(self, service: TradingService | None = None) -> None:
        self.service = service or TradingService()

    def execute(self, command_line: str) -> str:
        """Выполнить одну строку команды."""
        try:
            parts = shlex.split(command_line)
            if not parts:
                return ""

            command = parts[0].lower()
            arguments = parts[1:]
            handlers = {
                "register": self._register,
                "login": self._login,
                "show-portfolio": self._show_portfolio,
                "buy": self._buy,
                "sell": self._sell,
                "get-rate": self._get_rate,
                "help": self._help,
            }
            handler = handlers.get(command)
            if handler is None:
                return f"Неизвестная команда '{command}'. Введите help."
            return handler(arguments)
        except InsufficientFundsError as error:
            return str(error)
        except CurrencyNotFoundError as error:
            supported_codes = ", ".join(CURRENCY_REGISTRY)
            return (
                f"{error}. Используйте: help get-rate.\n"
                f"Поддерживаемые валюты: {supported_codes}"
            )
        except ApiRequestError as error:
            return f"{error}. Повторите попытку позже или проверьте сеть."
        except (TypeError, ValueError) as error:
            return str(error)

    def _register(self, arguments: list[str]) -> str:
        options = self._parse_options(arguments, {"username", "password"})
        user = self.service.register(options["username"], options["password"])
        return (
            f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
            f"Войдите: login --username {user.username} --password ****"
        )

    def _login(self, arguments: list[str]) -> str:
        options = self._parse_options(arguments, {"username", "password"})
        user = self.service.login(options["username"], options["password"])
        return f"Вы вошли как '{user.username}'"

    def _show_portfolio(self, arguments: list[str]) -> str:
        options = self._parse_options(
            arguments,
            set(),
            {"base": self.service.default_base_currency},
        )
        base_code = options["base"].strip().upper()
        rows, total = self.service.show_portfolio(base_code)
        user = self.service.current_user
        if user is None:
            raise ValueError("Сначала выполните login")
        if not rows:
            return f"Портфель пользователя '{user.username}' пока пуст"

        table = PrettyTable()
        table.field_names = ["Валюта", "Баланс", f"Стоимость, {base_code}"]
        for row in rows:
            table.add_row(
                [
                    row["currency_code"],
                    f"{row['balance']:.4f}",
                    f"{row['value']:,.2f}",
                ]
            )
        return (
            f"Портфель пользователя '{user.username}' (база: {base_code}):\n"
            f"{table}\nИТОГО: {total:,.2f} {base_code}"
        )

    def _buy(self, arguments: list[str]) -> str:
        options = self._parse_options(arguments, {"currency", "amount"})
        amount = self._parse_amount(options["amount"])
        result = self.service.buy(options["currency"], amount)
        return (
            f"Покупка выполнена: {result['amount']:.4f} "
            f"{result['currency_code']} по курсу {result['rate']:.2f} USD/"
            f"{result['currency_code']}\n"
            "Изменения в портфеле:\n"
            f"- {result['currency_code']}: было {result['previous_balance']:.4f} "
            f"→ стало {result['new_balance']:.4f}\n"
            f"Оценочная стоимость покупки: {result['value']:,.2f} USD"
        )

    def _sell(self, arguments: list[str]) -> str:
        options = self._parse_options(arguments, {"currency", "amount"})
        amount = self._parse_amount(options["amount"])
        result = self.service.sell(options["currency"], amount)
        return (
            f"Продажа выполнена: {result['amount']:.4f} "
            f"{result['currency_code']} по курсу {result['rate']:.2f} USD/"
            f"{result['currency_code']}\n"
            "Изменения в портфеле:\n"
            f"- {result['currency_code']}: было {result['previous_balance']:.4f} "
            f"→ стало {result['new_balance']:.4f}\n"
            f"Оценочная выручка: {result['value']:,.2f} USD"
        )

    def _get_rate(self, arguments: list[str]) -> str:
        options = self._parse_options(arguments, {"from", "to"})
        try:
            info = self.service.rate_service.get_rate_info(
                options["from"], options["to"]
            )
        except ValueError as error:
            from_code = options["from"].strip().upper()
            to_code = options["to"].strip().upper()
            raise ValueError(
                f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже."
            ) from error

        updated_at = str(info["updated_at"]).replace("T", " ")
        reverse_rate = 1 / float(info["rate"])
        return (
            f"Курс {info['from_currency']}→{info['to_currency']}: "
            f"{info['rate']:.8f} (обновлено: {updated_at})\n"
            f"Обратный курс {info['to_currency']}→{info['from_currency']}: "
            f"{reverse_rate:.8f}"
        )

    def _help(self, arguments: list[str]) -> str:
        if arguments == ["get-rate"]:
            supported_codes = ", ".join(CURRENCY_REGISTRY)
            return (
                "get-rate --from <код> --to <код>\n"
                "Показывает текущий курс одной валюты к другой.\n"
                f"Поддерживаемые валюты: {supported_codes}"
            )
        if arguments:
            raise ValueError("Справка для указанной команды не найдена")
        return (
            "Доступные команды:\n"
            "  register --username <имя> --password <пароль>\n"
            "  login --username <имя> --password <пароль>\n"
            "  show-portfolio [--base USD]\n"
            "  buy --currency <код> --amount <сумма>\n"
            "  sell --currency <код> --amount <сумма>\n"
            "  get-rate --from <код> --to <код>\n"
            "  exit"
        )

    @staticmethod
    def _parse_options(
        arguments: list[str],
        required: set[str],
        defaults: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Разобрать пары вида --имя значение."""
        options = {} if defaults is None else defaults.copy()
        allowed = required | set(options)
        if len(arguments) % 2 != 0:
            raise ValueError("Каждый аргумент команды должен иметь значение")

        for index in range(0, len(arguments), 2):
            name = arguments[index]
            if not name.startswith("--"):
                raise ValueError(f"Ожидался аргумент, получено '{name}'")
            option_name = name[2:]
            if option_name not in allowed:
                raise ValueError(f"Неизвестный аргумент '--{option_name}'")
            options[option_name] = arguments[index + 1]

        missing = required - options.keys()
        if missing:
            missing_names = ", ".join(f"--{name}" for name in sorted(missing))
            raise ValueError(f"Не указаны обязательные аргументы: {missing_names}")
        return options

    @staticmethod
    def _parse_amount(value: str) -> float:
        try:
            amount = float(value)
        except ValueError as error:
            raise ValueError("'amount' должен быть положительным числом") from error
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        return amount


def main() -> None:
    """Запустить консольное приложение."""
    interface = CommandInterface()

    if len(sys.argv) > 1:
        print(interface.execute(shlex.join(sys.argv[1:])))
        return

    print("ValutaTrade Hub. Введите help для списка команд.")
    while True:
        try:
            command_line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if command_line.lower() in {"exit", "quit"}:
            print("До свидания!")
            break

        result = interface.execute(command_line)
        if result:
            print(result)


if __name__ == "__main__":
    main()
