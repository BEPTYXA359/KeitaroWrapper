"""Настройки приложения (pydantic-settings, значения из .env)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Keitaro Admin API
    KT_BASE_URL: str = "https://tlgk.host"
    KT_API_KEY: str = ""

    # БД
    DATABASE_URL: str = "sqlite:///./dev.db"

    # Префикс имён создаваемых кампаний в Keitaro
    CAMPAIGN_PREFIX: str = "test_"

    # Группа/источник/домен, к которым привязываем создаваемые кампании
    KT_GROUP_NAME: str = "FORTESTS"
    KT_SOURCE_NAME: str = "FORTESTS"
    KT_DOMAIN_ID: int | None = None

    @field_validator("KT_DOMAIN_ID", mode="before")
    @classmethod
    def _empty_domain_id_is_none(cls, value: object) -> object:
        """Пустое значение в .env (KT_DOMAIN_ID=) означает «домен не задан»."""
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
