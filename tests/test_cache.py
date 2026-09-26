import json
import time

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app.github.cache import ResponseCache
from app.github.client import cache_key
from app.github.fixtures import load_into
from app.tools.search_repos import search_repos


def test_cache_key_is_order_independent_and_skips_none():
    assert cache_key("/x", {"b": 2, "a": 1, "c": None}) == cache_key("/x", {"a": 1, "b": 2}) == "GET /x?a=1&b=2"


def test_cache_ttl():
    c = ResponseCache(":memory:")
    c.set("k", {"v": 1}, fetched_at=time.time() - 100)
    assert c.get("k", max_age=200).body == {"v": 1}
    assert c.get("k", max_age=50) is None
    assert c.get("k", max_age=None) is not None


async def test_second_call_uses_cache(gh, fake):
    await search_repos("mcp")
    await search_repos("mcp")
    assert len(fake.requests) == 1


async def test_expired_entry_refetched(make_client, fake):
    make_client(cache_ttl_seconds=0)
    await search_repos("mcp")
    await search_repos("mcp")
    assert len(fake.requests) == 2


async def test_offline_mode_serves_cache_and_never_calls_network(make_client, fake):
    client = make_client(offline_mode=True)
    client.cache.set(cache_key("/search/repositories", {"q": "mcp", "per_page": 10}),
                     {"total_count": 1, "items": [{"full_name": "example-org/x", "html_url": "https://x"}]},
                     fetched_at=0)  # very old: offline ignores age
    assert (await search_repos("mcp")).items[0].full_name == "example-org/x"
    with pytest.raises(ToolError, match="offline_miss"):
        await search_repos("something else")
    assert fake.requests == []


def test_fixture_loading(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"key": "GET /x", "recorded_at": 100.0, "body": {"old": True}}))
    c = ResponseCache(":memory:")
    assert load_into(c, tmp_path) == 1
    assert c.get("GET /x", max_age=None).fetched_at == 100.0
    c.set("GET /x", {"new": True})  # a newer live response isn't overwritten by an older fixture
    assert load_into(c, tmp_path) == 0 and c.get("GET /x", max_age=None).body == {"new": True}
