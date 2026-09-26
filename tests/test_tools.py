import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app.tools.get_file import get_file_contents
from app.tools.get_issues import get_issues
from app.tools.search_repos import search_repos


async def test_search_repos(gh, fake):
    r = await search_repos("mcp", limit=5)
    assert r.items[0].full_name == "example-org/lighthouse"
    assert r.items[0].stars == 4210 and r.items[0].license == "MIT" and r.items[0].topics == ["mcp", "llm", "agents"]
    assert fake.requests[0].url.params["per_page"] == "5"


async def test_search_language_and_sort_params(gh, fake):
    r = await search_repos("database", language="rust", sort="stars")
    params = fake.requests[0].url.params
    assert params["q"] == "database language:rust" and params["sort"] == "stars" and params["order"] == "desc"
    assert [i.full_name for i in r.items] == ["example-org/tidepool"]


async def test_search_empty_query_rejected(gh, fake):
    with pytest.raises(ToolError, match="invalid_input"):
        await search_repos("   ")
    assert fake.requests == []


async def test_search_invalid_query_reports_github_reason(gh):
    with pytest.raises(ToolError, match="invalid_input: .*search query is invalid"):
        await search_repos("::bad")


async def test_issues_exclude_pull_requests(gh):
    r = await get_issues("example-org", "lighthouse", limit=10)
    assert [i.number for i in r.items] == [12, 10, 9]  # #11 is a PR
    assert r.items[0].labels == ["bug"] and r.items[0].author == "user12"
    assert len(r.items[0].body_preview) <= 401


async def test_issues_limit(gh):
    assert (await get_issues("example-org", "lighthouse", limit=2)).count == 2


@pytest.mark.parametrize("owner,repo", [("bad owner", "x"), ("..", "x"), ("ok", "a/b"), ("", "x")])
async def test_issues_invalid_names(gh, fake, owner, repo):
    with pytest.raises(ToolError, match="invalid_input"):
        await get_issues(owner, repo)
    assert fake.requests == []


async def test_issues_not_found(gh):
    with pytest.raises(ToolError, match="not_found"):
        await get_issues("example-org", "missing")


async def test_read_file(gh):
    f = await get_file_contents("example-org", "lighthouse", "README.md")
    assert f.type == "file" and f.content.startswith("# Lighthouse") and not f.truncated


async def test_list_directory(gh):
    d = await get_file_contents("example-org", "lighthouse", "")
    assert d.type == "dir" and [e.name for e in d.entries] == ["src", "pyproject.toml", "README.md"]


async def test_large_file_truncated(gh):
    f = await get_file_contents("example-org", "lighthouse", "big.txt")
    assert f.truncated and len(f.content) == 100_000


@pytest.mark.parametrize("path,code", [("logo.png", "unsupported_binary"), ("huge.bin", "too_large"),
                                       ("submod", "unsupported_type"), ("nope.md", "not_found"),
                                       ("../secrets", "invalid_input")])
async def test_file_errors(gh, path, code):
    with pytest.raises(ToolError, match=code):
        await get_file_contents("example-org", "lighthouse", path)
