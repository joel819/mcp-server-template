"""LLM agent: Llama 3.3 70B on Groq, with its tools discovered from the MCP server at runtime.

Nothing about GitHub is hard-coded here: the tool names, descriptions and JSON schemas all come
from session.list_tools(), which is the point of MCP.
"""
import json

import openai
from mcp import ClientSession

from app.config import Settings
from client.tools import call, to_openai_tools

SYSTEM = """You answer questions about public GitHub repositories using the provided tools.
Call tools to get facts; never guess repository names, star counts or issue numbers.
If a tool returns an error, explain it plainly (for rate_limited, say when to retry).
Answer concisely with the key facts and repository URLs."""


class AgentError(Exception):
    pass


async def answer(session: ClientSession, question: str, trace: list, settings: Settings,
                 llm: openai.AsyncOpenAI | None = None) -> str:
    llm = llm or openai.AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url,
                                    timeout=45, max_retries=2)
    tools = to_openai_tools((await session.list_tools()).tools)
    messages: list[dict] = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]

    for step in range(settings.agent_max_steps):
        final = step == settings.agent_max_steps - 1
        try:
            resp = await llm.chat.completions.create(
                model=settings.groq_model, temperature=0, messages=messages,
                **({} if final else {"tools": tools, "tool_choice": "auto"}),
            )
        except openai.OpenAIError as exc:
            raise AgentError(f"{type(exc).__name__}: {exc}") from exc
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "").strip()
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except ValueError:
                args = None
            if not isinstance(args, dict):
                text = "invalid_input: tool arguments were not a JSON object"
                trace.append({"tool": tc.function.name, "arguments": tc.function.arguments, "ok": False,
                              "preview": text})
            else:
                _, text, _ = await call(session, tc.function.name, args, trace)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text[:12_000]})
    raise AgentError("Agent did not finish within AGENT_MAX_STEPS")
