"""Open an MCP ClientSession over stdio (spawns server_stdio.py) or streamable HTTP."""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def connect(url: str | None = None):
    if url:
        async with streamablehttp_client(url) as (read, write, _), ClientSession(read, write) as session:
            await session.initialize()
            yield session
    else:
        # The SDK only forwards a few safe variables by default; the server needs our settings
        # (GITHUB_TOKEN, OFFLINE_MODE, DATA_DIR, ...), so pass the environment through.
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server_stdio.py")], cwd=str(ROOT),
                                       env=dict(os.environ))
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            yield session
