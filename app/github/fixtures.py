"""Recorded GitHub API responses (fixtures/github/*.json).

Each file is {"key": "GET /path?query", "recorded_at": <unix time>, "body": <GitHub JSON>}.
Loaded into the cache with their original timestamps: online they count as stale (fresh data is
fetched, fixtures are only a fallback); in offline mode they are served as-is.
"""
import json
from pathlib import Path

from app.github.cache import ResponseCache

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "github"


def iter_fixtures(directory: Path = FIXTURE_DIR):
    for f in sorted(directory.glob("*.json")):
        yield json.loads(f.read_text(encoding="utf-8"))


def load_into(cache: ResponseCache, directory: Path = FIXTURE_DIR) -> int:
    n = 0
    for fx in iter_fixtures(directory):
        existing = cache.get(fx["key"], max_age=None)
        if existing is None or existing.fetched_at < fx["recorded_at"]:
            cache.set(fx["key"], fx["body"], fetched_at=fx["recorded_at"])
            n += 1
    return n
