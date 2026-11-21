# Users API: аудит кода, исправление и Docker

Учебный проект по уроку «Кейс 3: AI для кода».

Взят намеренно плохой модуль с типичными ошибками и уязвимостями, проведён аудит,
код переписан, обёрнут в HTTP-сервис и упакован в Docker. Каждое исправление проверяется тестом.

- Аудит: [`АУДИТ-VPf11.md`](АУДИТ-VPf11.md) — 18 пунктов «проблема → риск → исправление».
- Плохой исходник: `legacy/utils_bad.py` (только для сравнения, сервисом не используется).
- Исправленный код: `app/db.py`, `app/users.py`, `app/api.py`.

## Что было не так и что стало

| Было | Стало |
|---|---|
| SQL склейкой строк — инъекция | параметризованные запросы `?` |
| `tags=[]` мутировал аргумент вызывающего | `tags=None`, локальная копия |
| `return cur.lastrowid + ""` | `int(id)` |
| соединения не закрывались | `@contextmanager` + `finally: close` |
| «хеш» `password[::-1]` | `pbkdf2_hmac` + соль, формат `salt$hash` |
| `open()` без `with`, пароли в файле | таблица `passwords` в БД |
| гонка потоков на общем списке | `threading.Lock` |
| `return {}` вместо `None` | `None` |
| `except: return True` в `is_admin` | строгая проверка типа и роли |
| нет валидации входа | имя 1–80, до 10 тегов по 40, пароль от 6 |
| traceback клиенту | JSON-ошибки, traceback только в лог |

Подробности и привязка к тестам — в файле аудита.

## Эндпоинты

| Метод | Путь | Что делает |
|---|---|---|
| GET | `/health` | проверка сервиса и базы |
| POST | `/adduser` | создать пользователя (`name`, `tags?`, `password?`) |
| GET | `/user/<id>` | пользователь по id |
| GET | `/user?name=Иван` | пользователь по имени |
| POST | `/activate/<id>` | добавить в активные |
| GET | `/active` | список активных |
| GET | `/slow?n=1000` | вычислительная задача |

Примеры:

```bash
curl -X POST http://127.0.0.1:8090/adduser \
  -H "Content-Type: application/json" \
  -d '{"name": "Иван", "tags": ["стартер"], "password": "secret123"}'

curl http://127.0.0.1:8090/user/1
curl -X POST http://127.0.0.1:8090/activate/1
curl http://127.0.0.1:8090/health
```

Пароль принимается на вход, но никогда не возвращается: в ответе только `id`, `name`, `tags`.

## Запуск локально

```cmd
cd "C:\Users\<ваш путь>\VPf11"
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements-dev.txt
python run.py
```

Сервис слушает `0.0.0.0:8000` (порт и путь к базе — в `.env`).

## Docker

```cmd
docker build -t vpf11-api:1.0 .
docker run -d --name vpf11-api -p 8090:8000 vpf11-api:1.0
docker ps
docker logs vpf11-api
```

Снаружи сервис на `http://127.0.0.1:8090` (порт 8080 на машине занят другим контейнером).

В образе:

- `python:3.12-slim`, зависимости отдельным слоем;
- запуск от непривилегированного пользователя `appuser`;
- `waitress` с 4 потоками вместо dev-сервера;
- `HEALTHCHECK` на `/health`, поэтому `docker ps` показывает `(healthy)`;
- `.env`, тесты, `legacy/` и база в образ не попадают (см. `.dockerignore`).

## Проверки

```cmd
pytest -q
python test_endpoints.py --url http://127.0.0.1:8090
```

`pytest` — 50 тестов: инъекции, хеширование паролей, гонка потоков, валидация,
контракты API (201/200/202/400/404), читаемая кириллица в JSON.

`test_endpoints.py` — 11 живых проверок всех маршрутов плюс негативные случаи; печатает
код ответа и тело, при ошибке завершается с кодом 1.

## OpenAPI

`openapi.yaml` описывает все 7 путей, схемы (`User`, `AddUserRequest`, `ActiveList`,
`SlowResult`, `Health`, `Error`) и коды ответов. Импортируется в Swagger UI, Postman,
Insomnia.

## Структура

```
app/config.py        настройки из .env
app/db.py            соединение через contextmanager, схема, healthcheck
app/users.py         валидация, пароли, пользователи, активные
app/api.py           Flask: маршруты, JSON-ошибки, кодировка UTF-8
run.py               запуск через waitress
test_endpoints.py    проверка живого сервиса
legacy/utils_bad.py  исходный плохой код (для сравнения)
tests/               50 тестов
Dockerfile, .dockerignore, openapi.yaml, requirements.txt
```

## Ограничения

- аутентификации нет: сервис учебный, эндпоинты открыты;
- SQLite вместо БД с конкурентной записью;
- список активных хранится в памяти процесса, после перезапуска пуст;
- нет миграций и HTTPS.

## Для сдачи

Скриншоты: (1) вывод `pytest`, (2) `docker build` и `docker ps` со статусом `healthy`,
(3) `test_endpoints.py` — все проверки `ok`, (4) пример ответа API с кириллицей.