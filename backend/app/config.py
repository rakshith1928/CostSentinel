from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find the project root (parent of backend folder)
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra fields like VITE_USER_ID
    )

    # Core URLs (Required)
    ollama_url: str
    redis_url: str

    # Database configuration (PostgreSQL + TimescaleDB) (Required)
    database_url: str
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Budget defaults
    default_budget_tokens: int = 100_000
    default_team_budget_tokens: int = 500_000
    hard_limit_multiplier: float = 1.2
    downgrade_model: str = "tinyllama"

    # API & Auth (Required)
    sentinel_api_key: str = ""
    history_api_admin_key: str = ""  # Separate key for history API
    ws_token_secret: str
    admin_users: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000"

    # History retention
    history_ttl_days: int = 90

    def is_admin(self, user_id: str) -> bool:
        if not self.admin_users:
            return False
        return user_id in {u.strip() for u in self.admin_users.split(',')}


settings = Settings()
