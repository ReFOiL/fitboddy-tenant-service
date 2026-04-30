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
- `GET /api/v1/marketplace/clients/looking` - клиенты в поиске тренера
- `POST /api/v1/marketplace/relations` - создать связь trainer-client (`invite`/`direct`) с `acting_user_id`
- `POST /api/v1/marketplace/relations/{relation_id}/accept` - принять приглашение (`acting_user_id`)
- `POST /api/v1/marketplace/relations/{relation_id}/leave` - завершить связь (`acting_user_id`)
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/clients?status=active` - клиенты тренера
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/clients?status=invited` - отправленные приглашения тренера
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/clients?status=declined` - отклоненные приглашения тренера
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/clients?status=ended` - завершенные активные связи тренера
- `GET /api/v1/marketplace/trainers/{trainer_user_id}/funnel` - бизнес-метрики воронки (`invites_sent`, `invites_pending`, `invites_accepted`, `invites_declined`, `active_clients`, `invite_acceptance_rate`)
- `GET /api/v1/marketplace/clients/{client_user_id}/invites` - входящие приглашения клиента
- `POST /api/v1/marketplace/profiles/check` - проверить существование профиля и роль (`exists`, `role`)

Правила:
- `invite` может создавать только тренер (`acting_user_id == trainer_user_id`).
- `direct` может создавать тренер или клиент (actor должен быть участником пары).
- `accept`/`leave` может выполнять только участник связи.
- `leave` из `invited` переводит связь в `declined`, из `active` в `ended`.

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
