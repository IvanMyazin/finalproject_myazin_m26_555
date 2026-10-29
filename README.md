# ValutaTrade Hub

Учебное консольное приложение, которое имитирует работу валютного кошелька.
Пользователь сможет управлять виртуальным портфелем фиатных и криптовалют,
совершать сделки и просматривать актуальные курсы.

## Технологии

- Python 3.12;
- `uv` для зависимостей и сборки пакета;
- `ruff` для проверки и форматирования кода;
- `prettytable` для вывода таблиц в консоли;
- JSON-файлы для хранения учебных данных.

## Подготовка окружения

```bash
uv sync
```

## Запуск

```bash
uv run valutatrade-hub
```

Приложение откроет интерактивную сессию. После `login` в этой же сессии доступны
операции с портфелем:

```text
register --username alice --password 1234
login --username alice --password 1234
show-portfolio --base USD
buy --currency BTC --amount 0.05
sell --currency BTC --amount 0.01
get-rate --from BTC --to USD
```

Команда `help` показывает доступные команды, `exit` завершает приложение.

## Проверка кода

```bash
uv run ruff check .
uv run ruff format --check .
```
