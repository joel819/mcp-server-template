"""The MCP server: one FastMCP instance, shared by the HTTP (main.py) and stdio (server_stdio.py) transports."""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from app.config import get_settings
from app.tools.get_file import get_file_contents
from app.tools.get_issues import get_issues
from app.tools.search_repos import search_repos

INSTRUCTIONS = """Read-only access to public GitHub data.
- search_repos: find repositories by keywords, language, stars.
- get_issues: list recent issues of a repository (owner + repo).
- get_file_contents: read a file or list a directory in a repository.
Errors start with a code (not_found, rate_limited, invalid_input, ...). On rate_limited, don't retry immediately."""


def build_server() -> FastMCP:
    s = get_settings()
    mcp = FastMCP(
        "github-public",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[h.strip() for h in s.allowed_hosts.split(",") if h.strip()],
        ),
    )
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)
    mcp.tool(title="Search GitHub repositories", annotations=read_only)(search_repos)
    mcp.tool(title="List repository issues", annotations=read_only)(get_issues)
    mcp.tool(title="Read a repository file", annotations=read_only)(get_file_contents)
    return mcp


def seed_cache() -> int:
    """Load recorded fixtures into the response cache (see app/github/fixtures.py)."""
    from app.github import get_github
    from app.github.fixtures import load_into

    return load_into(get_github().cache)


mcp = build_server()
