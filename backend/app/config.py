from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ollama_url: str = "http://ollama:11434"
    redis_url: str = "redis://redis:6379"
    default_budget_tokens: int = 100_000
    default_team_budget_tokens: int = 500_000
    hard_limit_multiplier: float = 1.2
    downgrade_model: str = "tinyllama"
    sentinel_api_key: str | None = None
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

settings = Settings()