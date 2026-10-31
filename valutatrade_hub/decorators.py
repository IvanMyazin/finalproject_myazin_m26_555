"""Декораторы приложения."""

from functools import wraps
from inspect import signature
from typing import Any, Callable

from valutatrade_hub.logging_config import get_action_logger


def log_action(
    action: str,
    verbose: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Логировать результат доменной операции и пробрасывать её исключения."""

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        function_signature = signature(function)

        @wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_action_logger()
            arguments = function_signature.bind_partial(*args, **kwargs).arguments
            service = arguments.get("self")
            current_user = getattr(service, "current_user", None)
            username = getattr(current_user, "username", "anonymous")
            currency = str(arguments.get("currency_code", "")).upper()
            amount = arguments.get("amount")
            base = getattr(service, "default_base_currency", "USD")

            try:
                result = function(*args, **kwargs)
            except Exception as error:
                logger.info(
                    "%s user='%s' currency='%s' amount=%s base='%s' "
                    "result=ERROR error_type='%s' error_message='%s'",
                    action,
                    username,
                    currency,
                    _format_number(amount, 4),
                    base,
                    type(error).__name__,
                    str(error).replace("\n", " "),
                )
                raise

            rate = result.get("rate") if isinstance(result, dict) else None
            message = (
                f"{action} user='{username}' currency='{currency}' "
                f"amount={_format_number(amount, 4)} "
                f"rate={_format_number(rate, 2)} base='{base}' result=OK"
            )
            if verbose and isinstance(result, dict):
                previous = _format_number(result.get("previous_balance"), 4)
                current = _format_number(result.get("new_balance"), 4)
                message += f" balance='{previous}→{current}'"
            logger.info(message)
            return result

        return wrapper

    return decorator


def _format_number(value: object, decimal_places: int) -> str:
    """Подготовить число для человекочитаемой записи лога."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return f"{value:.{decimal_places}f}"
