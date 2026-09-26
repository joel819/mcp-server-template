"""Tool errors. The code prefix lets an agent react programmatically (e.g. wait on rate_limited)."""
from mcp.server.fastmcp.exceptions import ToolError


def tool_error(code: str, message: str) -> ToolError:
    return ToolError(f"{code}: {message}")
