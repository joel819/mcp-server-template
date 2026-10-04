"""HTTP entrypoint: `uvicorn main:app`. MCP endpoint at /mcp (streamable HTTP), health at /health."""
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from app.config import get_settings
from app.github import get_github
from app.server import mcp, seed_cache

if get_settings().seed_on_startup:
    seed_cache()


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    s = get_settings()
    tools = await mcp.list_tools()
    return JSONResponse({
        "status": "ok",
        "mcp_endpoint": "/mcp",
        "tools": [t.name for t in tools],
        "offline_mode": s.offline_mode,
        "github_token": bool(s.github_token),
        "rate_limit_remaining": get_github().rate_limit_remaining,
        "cached_responses": len(get_github().cache.keys()),
    })


@mcp.custom_route("/", methods=["GET"])
async def index(request: Request) -> FileResponse:
    """A small MCP client page: list the tools, call them, see the JSON-RPC on the wire."""
    return FileResponse(Path(__file__).parent / "app" / "static" / "index.html")


app = mcp.streamable_http_app()
