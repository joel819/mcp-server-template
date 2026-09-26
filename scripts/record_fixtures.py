"""Record real GitHub API responses into fixtures/github/ for offline mode and instant first demos.

Run once on a machine with internet access (no token needed; uses ~10 requests):
    python -m scripts.record_fixtures

Each recorded request is exactly what the tools send, so the same tool calls hit these fixtures later.
"""
import asyncio
import hashlib
import json
import time

from app.config import get_settings
from app.github.cache import ResponseCache
from app.github.client import GitHubClient
from app.github.fixtures import FIXTURE_DIR
from app.github import set_github
from app.tools.get_file import get_file_contents
from app.tools.get_issues import get_issues
from app.tools.search_repos import search_repos

# The example queries used in the README and by the demo agent's canned questions.
CALLS = [
    (search_repos, dict(query="model context protocol", language="python", sort="stars", limit=5)),
    (search_repos, dict(query="vector database", sort="stars", limit=5)),
    (search_repos, dict(query="web framework", language="python", sort="stars", limit=5)),
    (get_issues, dict(owner="modelcontextprotocol", repo="python-sdk", state="open", limit=10)),
    (get_issues, dict(owner="fastapi", repo="fastapi", state="open", limit=10)),
    (get_file_contents, dict(owner="modelcontextprotocol", repo="python-sdk", path="README.md")),
    (get_file_contents, dict(owner="modelcontextprotocol", repo="python-sdk", path="")),
    (get_file_contents, dict(owner="fastapi", repo="fastapi", path="pyproject.toml")),
]


async def main() -> None:
    settings = get_settings().model_copy(update={"offline_mode": False, "cache_ttl_seconds": 0})
    cache = ResponseCache(":memory:")
    client = GitHubClient(settings, cache)
    set_github(client)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for fn, kwargs in CALLS:
        try:
            await fn(**kwargs)
            print(f"  ok    {fn.__name__}({kwargs})")
        except Exception as exc:  # keep going; report what failed
            print(f"  FAIL  {fn.__name__}({kwargs}): {exc}")
    for key in cache.keys():
        entry = cache.get(key, max_age=None)
        name = hashlib.sha1(key.encode()).hexdigest()[:12]
        (FIXTURE_DIR / f"{name}.json").write_text(
            json.dumps({"key": key, "recorded_at": entry.fetched_at or time.time(), "body": entry.body}, indent=1),
            encoding="utf-8")
    print(f"Wrote {len(cache.keys())} fixture(s) to {FIXTURE_DIR}")
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
