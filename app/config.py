from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "openrouter"
    llm_api_key: str
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "deepseek/deepseek-v4-flash"

    llm_temperature: float = 0.2
    llm_max_tokens: int = 1200
    llm_timeout_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()