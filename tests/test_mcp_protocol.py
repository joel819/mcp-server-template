"""The server spoken to through a real MCP ClientSession (in-memory, stdio and HTTP transports)."""
import json
import os

from mcp.shared.memory import create_connected_server_and_client_session
from starlette.testclient import TestClient

from app.server import mcp


async def test_list_tools_over_mcp(gh):
    async with create_connected_server_and_client_session(mcp) as s:
        tools = {t.name: t for t in (await s.list_tools()).tools}
    assert set(tools) == {"search_repos", "get_issues", "get_file_contents"}
    schema = tools["search_repos"].inputSchema
    assert schema["required"] == ["query"] and schema["properties"]["limit"]["maximum"] == 30
    assert tools["get_issues"].annotations.readOnlyHint is True
    assert tools["get_file_contents"].outputSchema is not None


async def test_call_tool_returns_structured_content(gh):
    async with create_connected_server_and_client_session(mcp) as s:
        r = await s.call_tool("get_issues", {"owner": "example-org", "repo": "lighthouse", "limit": 2})
    assert not r.isError
    assert [i["number"] for i in r.structuredContent["items"]] == [12, 10]
    assert json.loads(r.content[0].text)["repo"] == "example-org/lighthouse"


async def test_tool_errors_are_mcp_errors_not_crashes(gh):
    async with create_connected_server_and_client_session(mcp) as s:
        r = await s.call_tool("get_file_contents", {"owner": "example-org", "repo": "lighthouse", "path": "nope.md"})
        schema_err = await s.call_tool("search_repos", {"query": "x", "limit": 999})
    assert r.isError and "not_found" in r.content[0].text
    assert schema_err.isError  # limit > 30 rejected by the input schema


def _rpc(client, method, params=None, id_=1):
    return client.post("/mcp", json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}},
                       headers={"Accept": "application/json, text/event-stream"})


def test_http_transport_health_and_host_check():
    from main import app

    # The session manager can only start once per process, so one TestClient covers all HTTP checks.
    with TestClient(app, base_url="http://localhost:8000") as c:
        assert c.get("/health").json()["tools"] == ["search_repos", "get_issues", "get_file_contents"]
        init = _rpc(c, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "test", "version": "1"}})
        assert init.status_code == 200 and init.json()["result"]["serverInfo"]["name"] == "github-public"
        tools = _rpc(c, "tools/list", id_=2).json()["result"]["tools"]
        assert len(tools) == 3
        # DNS-rebinding protection: only ALLOWED_HOSTS may talk to the MCP endpoint
        evil = c.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
                      headers={"Host": "evil.example:8000", "Accept": "application/json, text/event-stream"})
        assert evil.status_code in (403, 421)
        # The explorer page runs in a browser and sends an Origin header: local origins pass, others don't.
        h = {"Accept": "application/json, text/event-stream"}
        body = {"jsonrpc": "2.0", "id": 4, "method": "tools/list"}
        assert c.post("/mcp", json=body, headers={**h, "Origin": "http://localhost:8000"}).status_code == 200
        assert c.post("/mcp", json=body, headers={**h, "Origin": "https://evil.example"}).status_code == 403


async def test_stdio_transport_end_to_end(tmp_path):
    """Spawns server_stdio.py as a subprocess, in offline mode with a pre-filled cache."""
    from app.github.cache import ResponseCache
    from app.github.client import cache_key
    from client.connection import connect

    ResponseCache(tmp_path / "github_cache.db").set(
        cache_key("/search/repositories", {"q": "mcp", "per_page": 10}),
        {"total_count": 1, "items": [{"full_name": "example-org/lighthouse", "html_url": "https://x",
                                      "stargazers_count": 5}]})
    env = {"DATA_DIR": str(tmp_path), "OFFLINE_MODE": "true", "SEED_ON_STARTUP": "false"}
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)  # the stdio client passes its environment to the subprocess
    try:
        async with connect() as session:
            r = await session.call_tool("search_repos", {"query": "mcp"})
    finally:
        for k, v in old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    assert not r.isError and r.structuredContent["items"][0]["stars"] == 5


def test_explorer_page_is_served():
    from starlette.testclient import TestClient

    from main import app

    r = TestClient(app).get("/")
    assert r.status_code == 200 and "MCP" in r.text and "tools/list" in r.text

