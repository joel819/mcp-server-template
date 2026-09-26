"""The demo client: planner (no key) and the Groq agent (mocked), both talking MCP to the real server."""
import json
from types import SimpleNamespace

import openai
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from app.config import get_settings
from app.server import mcp
from client import agent, planner


@pytest.mark.parametrize("question,tool,args", [
    ("most popular python repos about vector search", "search_repos",
     {"query": "vector search", "language": "python", "sort": "stars", "limit": 5}),
    ("show open issues in example-org/lighthouse", "get_issues",
     {"owner": "example-org", "repo": "lighthouse", "state": "open", "limit": 5}),
    ("what's in the README of example-org/lighthouse?", "get_file_contents",
     {"owner": "example-org", "repo": "lighthouse", "path": "README.md"}),
    ("read pyproject.toml in example-org/lighthouse", "get_file_contents",
     {"owner": "example-org", "repo": "lighthouse", "path": "pyproject.toml"}),
    ("list the files in example-org/lighthouse", "get_file_contents",
     {"owner": "example-org", "repo": "lighthouse", "path": ""}),
])
def test_planner_picks_tool(question, tool, args):
    assert planner.plan(question) == (tool, args)


async def test_planner_answers_through_mcp(gh):
    trace = []
    async with create_connected_server_and_client_session(mcp) as s:
        text = await planner.answer(s, "show open issues in example-org/lighthouse", trace)
    assert "#12 Crash when tool returns None" in text
    assert trace[0]["tool"] == "get_issues" and trace[0]["ok"]


async def test_planner_reports_tool_errors(gh):
    async with create_connected_server_and_client_session(mcp) as s:
        text = await planner.answer(s, "show issues in example-org/missing", [])
    assert "not_found" in text


def tc(name, args, id_="c1"):
    return SimpleNamespace(id=id_, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def reply(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))])


class FakeLLM:
    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


async def test_agent_discovers_tools_and_calls_them_over_mcp(gh):
    llm = FakeLLM(
        reply(tool_calls=[tc("search_repos", {"query": "mcp", "language": "python", "sort": "stars", "limit": 3})]),
        reply(tool_calls=[tc("get_issues", {"owner": "example-org", "repo": "lighthouse", "limit": 2}, "c2")]),
        reply("example-org/lighthouse is the top result; its newest issue is #12."),
    )
    settings = get_settings().model_copy(update={"groq_api_key": "gsk_test"})
    trace = []
    async with create_connected_server_and_client_session(mcp) as s:
        text = await agent.answer(s, "top python mcp repo and its latest issue?", trace, settings, llm=llm)
    assert text.startswith("example-org/lighthouse")
    assert [t["tool"] for t in trace] == ["search_repos", "get_issues"]
    first = llm.requests[0]
    assert first["model"] == "llama-3.3-70b-versatile"
    assert {t["function"]["name"] for t in first["tools"]} == {"search_repos", "get_issues", "get_file_contents"}
    tool_msg = llm.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "example-org/lighthouse" in tool_msg["content"]


async def test_agent_passes_tool_errors_back_to_model(gh):
    llm = FakeLLM(reply(tool_calls=[tc("get_file_contents", {"owner": "example-org", "repo": "lighthouse",
                                                             "path": "nope.md"})]),
                  reply("That file doesn't exist."))
    settings = get_settings().model_copy(update={"groq_api_key": "gsk_test"})
    trace = []
    async with create_connected_server_and_client_session(mcp) as s:
        await agent.answer(s, "read nope.md", trace, settings, llm=llm)
    assert trace[0]["ok"] is False and "not_found" in llm.requests[1]["messages"][-1]["content"]


async def test_agent_llm_failure_raises_agent_error(gh):
    llm = FakeLLM(openai.APIConnectionError(request=None))
    settings = get_settings().model_copy(update={"groq_api_key": "gsk_test"})
    async with create_connected_server_and_client_session(mcp) as s:
        with pytest.raises(agent.AgentError):
            await agent.answer(s, "anything", [], settings, llm=llm)


async def test_agent_step_limit_forces_answer(gh):
    loop = reply(tool_calls=[tc("search_repos", {"query": "mcp"})])
    llm = FakeLLM(loop, loop, reply("done"))
    settings = get_settings().model_copy(update={"groq_api_key": "gsk_test", "agent_max_steps": 3})
    async with create_connected_server_and_client_session(mcp) as s:
        assert await agent.answer(s, "loop", [], settings, llm=llm) == "done"
    assert "tools" not in llm.requests[-1]
