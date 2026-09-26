import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app.tools.search_repos import search_repos


async def test_rate_limit_error_says_when_and_how(gh, fake):
    fake.rate_limited = True
    with pytest.raises(ToolError) as exc:
        await search_repos("mcp")
    msg = str(exc.value)
    assert msg.startswith("rate_limited:") and "resets at" in msg and "GITHUB_TOKEN" in msg


async def test_rate_limit_serves_stale_cache(make_client, fake):
    client = make_client(cache_ttl_seconds=0)  # everything is immediately stale
    await search_repos("mcp")
    fake.rate_limited = True
    r = await search_repos("mcp")  # served from the stale cache instead of failing
    assert r.items[0].full_name == "example-org/lighthouse"
    assert client.rate_limit_remaining == 0  # read from the 403's headers


async def test_retries_transient_5xx(gh, fake):
    fake.fail_times = 2
    assert (await search_repos("mcp")).items
    assert len(fake.requests) == 3


async def test_gives_up_after_retries(gh, fake):
    fake.fail_times = 10
    with pytest.raises(ToolError, match="upstream_error"):
        await search_repos("mcp")
    assert len(fake.requests) == 3  # 1 try + 2 retries


async def test_network_error(make_client):
    import httpx

    from app.github import set_github
    from app.github.cache import ResponseCache
    from app.github.client import GitHubClient
    from app.config import get_settings

    def boom(request):
        raise httpx.ConnectError("no route to host")

    set_github(GitHubClient(get_settings(), ResponseCache(":memory:"), transport=httpx.MockTransport(boom)))
    with pytest.raises(ToolError, match="network_error"):
        await search_repos("mcp")


async def test_token_is_sent_when_configured(make_client, fake):
    make_client(github_token="ghp_example")
    await search_repos("mcp")
    assert fake.requests[0].headers["authorization"] == "Bearer ghp_example"


async def test_no_auth_header_without_token(gh, fake):
    await search_repos("mcp")
    assert "authorization" not in fake.requests[0].headers
