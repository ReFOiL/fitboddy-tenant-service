from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="sqlite+pysqlite:///./tenant_service.db", alias="DATABASE_URL")
    alembic_ini_path: str = Field(default="alembic.ini", alias="ALEMBIC_INI_PATH")
