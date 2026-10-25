# tenant-service

Сервис маркетплейс-связей между тренерами и клиентами.

## Stack

- FastAPI + Pydantic
- SQLAlchemy + Alembic
- Poetry
- Postgres (prod) / SQLite (local tests)

## API

- `GET /health`
- `GET /ready`
- `PUT /api/v1/marketplace/users/{user_id}/profile` - upsert discovery-профиля (`trainer`/`client`)
- `GET /api/v1/marketplace/trainers` - список видимых тренеров
- `POST /api/v1/marketplace/relations` - создать связь trainer-client (`invite`/`direct`); actor берется из Bearer-токена
- `POST /api/v1/marketplace/relations/{relation_id}/accept` - принять приглашение (только приглашенный клиент)
- `POST /api/v1/marketplace/relations/{relation_id}/leave` - завершить связь (участник связи)
- `GET /api/v1/marketplace/trainers/me/invite-link` - постоянный инвайт-код текущего тренера (`code`, `invite_path`). Код создаётся при первом чтении. Нужен `Authorization: Bearer`
- `POST /api/v1/marketplace/trainers/me/invite-link/rotate` - заменить код. Предыдущий код сразу перестаёт находиться. Если кода ещё не было, создаётся первый
- `GET /api/v1/marketplace/invite/{code}` - публичное превью приглашения без авторизации (`code`, `trainer_user_id`, `trainer_display_name`, `trainer_login`). 404, если код неизвестен
- `POST /api/v1/marketplace/invite/{code}/accept` - клиент принимает код и получает активную связь с тренером. Необязательный query-параметр `force=true`
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/clients?status=active` - клиенты тренера
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/clients?status=invited` - отправленные приглашения тренера
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/clients?status=declined` - отклоненные приглашения тренера
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/clients?status=ended` - завершенные активные связи тренера
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/funnel` - бизнес-метрики воронки (`invites_sent`, `invites_pending`, `invites_accepted`, `invites_declined`, `active_clients`, `invite_acceptance_rate`)
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/publication-status` - статус публикации тренера (`is_published`)
- `GET /api/v1/marketplace/clients/{client_user_id}/invites` - входящие приглашения клиента
- `POST /api/v1/marketplace/profiles/check` - проверить существование профиля и роль (`exists`, `role`)
- `GET /api/v1/marketplace/internal/relations/access` - internal ACL для чата (`X-Service-Token`, `allowed`/`relation_id`/`status`)

Ответы discovery/relations дополнительно включают `login` (если доступен из `auth-service`).

Правила:
- Write-операции связей требуют `Authorization: Bearer <access_token>`; actor = `user_id` из токена.
- `invite` может создавать только тренер (actor == `trainer_user_id`).
- `direct` может создавать тренер или клиент (actor должен быть участником пары).
- `accept` может выполнять только приглашенный клиент.
- `leave` может выполнять только участник связи.
- `leave` из `invited` переводит связь в `declined`, из `active` в `ended`.

Постоянный инвайт тренера:

- У тренера один код. Это 6 символов из `23456789ABCDEFGHJKMNPQRSTUVWXYZ` (без похожих `0/O`, `1/I/L`), сравнение без учёта регистра, в ответе код в верхнем регистре.
- `invite_path` равен `/i/{code}`. Этот путь принадлежит фронтенду: сервис его не обслуживает, только возвращает в API.
- Выдать и принять код можно и у неопубликованного тренера (`is_visible=false`). В каталог `GET /marketplace/trainers` он по-прежнему не попадает.
- `POST .../accept` доступен роли `client`. Если discovery-профиля ещё нет, он создаётся (`role=client`), и сразу появляется активная связь `source=invite_code`.
- Уже активная связь с этим же тренером: `200` и та же `relation_id`, без изменений.
- Уже активная связь с другим тренером: `409` и тело `{"detail": {"reason": "already_linked", "message": "client already linked to another trainer", "current_trainer_user_id": "<id>"}}`. Клиент не переключается, пока не повторит запрос с `?force=true`. Тогда прежняя активная связь становится `ended`, а связь с тренером из кода — `active`.
- Тренер (роль `trainer` в токене или в discovery-профиле) не может принять инвайт, в том числе свой.
- Воронка `funnel` по-прежнему считает только точечные приглашения `source=invite`. Новая связь из кода имеет `source=invite_code` и попадает в `active_clients`, но не в счётчики invites_*. Уже существующая пара при повторной активации сохраняет свой прежний `source`.

Шлюз и фронтенд:

- Публичным должен быть только `GET /api/v1/marketplace/invite/{code}`. `POST /api/v1/marketplace/invite/{code}/accept` требует Bearer клиента: нельзя открывать весь префикс `/invite` без учёта метода.
- `GET /api/v1/marketplace/trainers/me/invite-link` и `POST /api/v1/marketplace/trainers/me/invite-link/rotate` требуют Bearer. Actor — это `user_id` из токена, и у него должен быть discovery-профиль с ролью `trainer` (роль в токене для этих двух ручек не проверяется).
- Лендинг фронтенда: маршрут `/i/{code}` читает `code` из URL, вызывает публичный `GET`, после регистрации или входа клиента вызывает `POST .../accept`. При `409` и `detail.reason=already_linked` показывает подтверждение смены тренера и повторяет accept с `force=true`.

Совместимость:

- `POST /api/v1/tenants/{tenant_id}/members/check` - временный compatibility endpoint для старых интеграций.

## Local run

```bash
poetry install
poetry run uvicorn --app-dir lib presentation.http.main:app --reload --port 8000
```

## Migrations

```bash
poetry run alembic upgrade head
```

## Tests

```bash
poetry run pytest tests/unit -q
```
