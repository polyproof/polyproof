from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/polyproof"
    API_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"
    LEAN_SERVER_URL: str = "http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
