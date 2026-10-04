"""Settings from environment variables / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # GitHub
    github_api_url: str = "https://api.github.com"
    github_token: str = ""  # optional: raises the limit from 60 to 5,000 requests/hour. Never required.
    http_timeout_seconds: float = 15.0
    http_retries: int = 2  # for timeouts and 5xx

    # Cache / offline
    data_dir: Path = Path("./data")
    cache_ttl_seconds: int = 600
    offline_mode: bool = False  # serve only recorded fixtures/cache, never touch the network
    seed_on_startup: bool = True  # load fixtures/ into the cache on startup

    # Tool limits
    max_file_bytes: int = 100_000  # file contents larger than this are truncated
    max_search_results: int = 30
    max_issues: int = 50

    # HTTP transport
    allowed_hosts: str = "localhost:*,127.0.0.1:*,server:*"  # Host headers accepted (DNS-rebinding protection)
    # Browser Origin headers accepted. Local pages (like the built-in explorer at /) only by default.
    allowed_origins: str = "http://localhost:*,http://127.0.0.1:*"

    # Demo agent (client/)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    agent_max_steps: int = 6

    @property
    def cache_path(self) -> Path:
        return self.data_dir / "github_cache.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
