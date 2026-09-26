"""stdio entrypoint for desktop MCP clients (Claude Desktop, Cursor, MCP Inspector).

    python server_stdio.py
"""
import logging
import sys

from app.config import get_settings
from app.server import mcp, seed_cache

if __name__ == "__main__":
    # stdout carries the MCP protocol: all logging must go to stderr
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    if get_settings().seed_on_startup:
        seed_cache()
    mcp.run(transport="stdio")
