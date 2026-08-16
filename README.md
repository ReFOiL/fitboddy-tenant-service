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
