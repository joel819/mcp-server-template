"""Shared helpers: MCP tool list -> OpenAI tool schema, and MCP call results -> text."""
import json

from mcp import ClientSession
from mcp.types import CallToolResult, Tool


def to_openai_tools(tools: list[Tool]) -> list[dict]:
    return [{"type": "function",
             "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}}
            for t in tools]


def result_text(result: CallToolResult) -> str:
    if result.structuredContent is not None:
        return json.dumps(result.structuredContent)
    return "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")


async def call(session: ClientSession, name: str, args: dict, trace: list) -> tuple[bool, str, dict | None]:
    """Call a tool over MCP and record it in the trace. Returns (ok, text, structured)."""
    result = await session.call_tool(name, args)
    text = result_text(result)
    trace.append({"tool": name, "arguments": args, "ok": not result.isError,
                  "preview": text[:160] + ("…" if len(text) > 160 else "")})
    return not result.isError, text, result.structuredContent
