from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/polyproof"
    API_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"
    LEAN_SERVER_URL: str = "http://localhost:8000"
    LEAN_SERVER_SECRET: str = ""
    OPENAI_API_KEY: str = ""
    ACTIVITY_THRESHOLD: int = 5
    ADMIN_API_KEY: str = ""
    RATE_LIMIT_ENABLED: bool = True
    API_BASE_URL: str = "https://api.polyproof.org"

    @model_validator(mode="after")
    def _require_secrets_in_production(self) -> "Settings":
        if self.API_ENV == "production":
            if not self.LEAN_SERVER_SECRET:
                raise ValueError("LEAN_SERVER_SECRET must be set in production")
            if not self.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY must be set in production")
            if not self.ADMIN_API_KEY:
                raise ValueError("ADMIN_API_KEY must be set in production")
        return self

    @property
    def async_database_url(self) -> str:
        """Convert any postgres URL to use asyncpg driver."""
        url = self.DATABASE_URL
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix) :]
        return url

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        if "*" in origins:
            raise ValueError("Wildcard '*' is not allowed in CORS_ORIGINS")
        return origins

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
