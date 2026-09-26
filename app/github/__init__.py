"""Process-wide GitHub client. Tests swap it with set_github()."""
from app.config import get_settings
from app.github.cache import ResponseCache
from app.github.client import GitHubClient

_client: GitHubClient | None = None


def get_github() -> GitHubClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = GitHubClient(s, ResponseCache(s.cache_path))
    return _client


def set_github(client: GitHubClient | None) -> None:
    global _client
    _client = client
