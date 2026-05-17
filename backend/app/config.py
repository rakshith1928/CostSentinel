from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ollama_url: str = "http://ollama:11434"
    redis_url: str = "redis://redis:6379"
    default_budget_tokens: int = 100_000
    default_team_budget_tokens: int = 500_000
    hard_limit_multiplier: float = 1.2
    downgrade_model: str = "tinyllama"
    sentinel_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    ws_token_secret: str = "change-me-in-production"  # ← add
    admin_users: str = ""   # ← comma-separated admin user IDs e.g. "alice,bob"

    class Config:
        env_file = ".env"

    def is_admin(self, user_id: str) -> bool:
        if not self.admin_users:
            return False
        return user_id in {u.strip() for u in self.admin_users.split(',')}

settings = Settings()