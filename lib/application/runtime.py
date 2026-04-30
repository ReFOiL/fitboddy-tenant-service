from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import text

from application.config import Settings
from application.db import DatabaseManager
from application.use_cases import TenantService


class TenantApplicationRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db_manager = DatabaseManager(settings.database_url)

    @contextmanager
    def tenant_service_scope(self):
        session = self._db_manager.create_session()
        try:
            yield TenantService(session=session)
        finally:
            session.close()

    def check_ready(self) -> bool:
        with self._db_manager.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def shutdown(self) -> None:
        self._db_manager.dispose()
