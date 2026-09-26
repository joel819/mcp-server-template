"""Demo agent using the MCP server.

    python -m client "What are the most popular Python MCP server repos?"
    python -m client --url http://localhost:8000/mcp "Show open issues in fastapi/fastapi"

Without --url it starts the server itself over stdio. With GROQ_API_KEY set, an LLM chooses the
tools; without it, a rule-based planner does (still through MCP).
"""
import argparse
import asyncio
import sys

from app.config import get_settings
from client import agent, planner
from client.connection import connect

EXAMPLES = [
    "What are the most popular Python repositories about model context protocol?",
    "Show me the open issues in modelcontextprotocol/python-sdk",
    "What's in the README of modelcontextprotocol/python-sdk?",
]


async def run(question: str, url: str | None) -> int:
    settings = get_settings()
    trace: list[dict] = []
    async with connect(url) as session:
        tools = (await session.list_tools()).tools
        print(f"Connected over {'HTTP ' + url if url else 'stdio'}. Server tools: {', '.join(t.name for t in tools)}")
        mode = "planner (no GROQ_API_KEY)" if settings.groq_api_key == "" else f"LLM ({settings.groq_model})"
        print(f"Agent: {mode}\nQuestion: {question}\n")
        if settings.groq_api_key:
            try:
                text = await agent.answer(session, question, trace, settings)
            except agent.AgentError as exc:
                print(f"LLM failed ({exc}); falling back to the planner.\n", file=sys.stderr)
                text = await planner.answer(session, question, trace)
        else:
            text = await planner.answer(session, question, trace)
    for i, t in enumerate(trace, 1):
        status = "ok" if t["ok"] else "ERROR"
        print(f"[tool {i}] {t['tool']}({t['arguments']}) -> {status}")
    print(f"\n{text}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("question", nargs="*", help="Question to ask (default: runs the example questions)")
    p.add_argument("--url", help="MCP server URL, e.g. http://localhost:8000/mcp (default: spawn over stdio)")
    args = p.parse_args()
    questions = [" ".join(args.question)] if args.question else EXAMPLES
    for q in questions:
        asyncio.run(run(q, args.url))
        print("\n" + "-" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
