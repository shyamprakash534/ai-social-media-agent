from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = "local-only-change-me"
    encryption_secret: str = "local-only-encryption-secret"
    database_url: str = "sqlite:///./social_agent.db"
    redis_url: str = "redis://localhost:6379/0"
    frontend_origin: str = "http://localhost:3000"
    backend_public_url: str = "http://localhost:8000"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "ai-social-media-agent"
    publish_mode: str = "demo"
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:8000/auth/linkedin/callback"
    linkedin_version: str = "202606"
    linkedin_author_urn: str = ""
    slack_bot_token: str = ""
    slack_channel_id: str = ""
    slack_signing_secret: str = ""
    slack_allowed_user_ids: str = ""
    use_postgres_checkpointer: bool = True

    @property
    def slack_allowed_users(self) -> set[str]:
        return {item.strip() for item in self.slack_allowed_user_ids.split(",") if item.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
