# mcp-server-template

A Model Context Protocol (MCP) server over GitHub's public API, with three read-only tools and a demo agent that uses them. It needs no GitHub auth and runs locally for free.

## What it does

- **Three MCP tools** built on the official `mcp` Python SDK (FastMCP):

  | Tool | What it returns |
  |---|---|
  | `search_repos(query, language?, sort?, limit?)` | Repos with description, stars, forks, language, topics, license, URL |
  | `get_issues(owner, repo, state?, labels?, limit?)` | Recent issues (pull requests filtered out) with labels, author, comment count, a body preview |
  | `get_file_contents(owner, repo, path?, ref?)` | A decoded text file (truncated if large), or a directory listing |

  Each tool has a typed input schema (limits, enums, descriptions) and a structured output schema. All three are marked read-only.
- **Two transports from one server definition:**
  - **Streamable HTTP** at `/mcp`, started with `uvicorn main:app` or Docker.
  - **stdio**, started with `python server_stdio.py`, for Claude Desktop, Cursor or the MCP Inspector.
- **Built for GitHub's 60 requests/hour unauthenticated limit:**
  - A SQLite response cache serves repeat questions without spending a request.
  - When the limit is hit, the error says when it resets, and a stale cached copy is served if one exists.
  - An optional free `GITHUB_TOKEN` raises the limit to 5,000/hour.
- **Clear errors for agents.** Each error starts with a code the agent can act on: `not_found`, `rate_limited`, `invalid_input`, `too_large`, `unsupported_binary`, `network_error`, `upstream_error`, `offline_miss`. Timeouts and 5xx responses are retried. Names and paths are validated before any request, so `../` can't escape the repo.
- **Offline mode.** Serves recorded GitHub responses and never touches the network.
- **A demo agent** (`python -m client`) connects over MCP and discovers the tools at runtime with `list_tools`. With a Groq key, gpt-oss-120b decides which tools to call. Without a key, a rule-based planner makes the same MCP calls. The agent prints every tool call it makes.

## Quickstart

With Docker:

```bash
git clone https://github.com/joel819/mcp-server-template.git && cd mcp-server-template
docker compose up
docker compose run --rm agent "What are the most popular Python repos about model context protocol?"
```

Without Docker (Python 3.11+):

```bash
git clone https://github.com/joel819/mcp-server-template.git && cd mcp-server-template
pip install -r requirements.txt
uvicorn main:app
```

Then, in a second terminal:

```bash
python -m client --url http://localhost:8000/mcp "Show open issues in fastapi/fastapi"
```

`python -m client` without `--url` starts the server itself over stdio, so you don't need uvicorn for that. With no question, it runs three example questions.

- Health check: http://localhost:8000/health
- Tests: `pytest`. There are 48 tests, and they need no network, no GitHub token and no Groq key.

Example output with no key:

```
Connected over HTTP http://localhost:8000/mcp. Server tools: search_repos, get_issues, get_file_contents
Agent: planner (no GROQ_API_KEY)
Question: show open issues in fastapi/fastapi

[tool 1] get_issues({'owner': 'fastapi', 'repo': 'fastapi', 'state': 'open', 'limit': 5}) -> ok

Latest open issues in fastapi/fastapi:
- #…
```

## A real run

The demo agent (`python -m client`) with a Groq key, asked about a public repo. It lists the tools over MCP at runtime, picks `get_file_contents` twice (directory listing, then the README) and writes the answer from what the tools returned. Unedited output:

```text
Connected over stdio. Server tools: search_repos, get_issues, get_file_contents
Agent: LLM (openai/gpt-oss-120b)
Question: What files are in the top level of joel819/docs-rag-chatbot, and what does the project do? Use its README.

[tool 1] get_file_contents({'owner': 'joel819', 'path': '', 'repo': 'docs-rag-chatbot'}) -> ok
[tool 2] get_file_contents({'owner': 'joel819', 'path': 'README.md', 'repo': 'docs-rag-chatbot'}) -> ok

**Top‑level contents of `joel819/docs-rag-chatbot`**

| File / Directory | Type |
|------------------|------|
| `app/` | directory |
| `docs/` | directory |
| `sample_docs/` | directory |
| `scripts/` | directory |
| `tests/` | directory |
| `.dockerignore` | file |
| `.env.example` | file |
| `.gitignore` | file |
| `docker-compose.yml` | file |
| `Dockerfile` | file |
| `main.py` | file |
| `pytest.ini` | file |
| `README.md` | file |
| `requirements.txt` | file |

**What the project does**

`docs-rag-chatbot` is a locally‑run RAG (Retrieval‑Augmented Generation) chatbot for PDF documents.  

- **Upload PDFs** via a web UI or API; each page is extracted, split into overlapping chunks that never cross page boundaries.  
- **Embed chunks** with the `all‑MiniLM‑L6‑v2` sentence‑transformer (CPU‑only) and store the vectors in ChromaDB.  
- **Ask questions** – the most relevant chunks are retrieved and sent to an LLM (Groq’s free‑tier `gpt‑oss‑120b` or a built‑in “canned” extractor). The answer must cite the source documents, showing the filename and page number (`[1]`, `[2]`, …).  
- **Citations are clickable**: clicking a citation opens the PDF at the cited page.  
- **Honest fallback**: if the documents don’t contain the answer, the system replies “I couldn't find that in the uploaded documents.” instead of hallucinating.  
- **Duplicate detection** via SHA‑256 hash, and optional document‑specific querying.  
- **Ready‑to‑try**: three sample PDFs are pre‑indexed on startup, so you can query immediately after cloning.  

The repo includes Docker support, a simple FastAPI backend (`main.py`), a static single‑page UI, SQLite metadata storage, and a full offline test suite.

**Repository URL**

https://github.com/joel819/docs-rag-chatbot
```

## Use it from Claude Desktop, Cursor or the MCP Inspector

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "github-public": {
      "command": "python",
      "args": ["/absolute/path/to/mcp-server-template/server_stdio.py"],
      "env": { "GITHUB_TOKEN": "" }
    }
  }
}
```

MCP Inspector:

```bash
npx @modelcontextprotocol/inspector python server_stdio.py
```

For HTTP clients, point them at `http://localhost:8000/mcp`.

## Architecture

```
 Claude Desktop / Cursor ──stdio──► server_stdio.py ─┐
                                                      ├─► app/server.py  (FastMCP "github-public")
 client/ demo agent ───────HTTP───► main.py  /mcp ───┘        │  tools: search_repos, get_issues, get_file_contents
        │                                                      ▼
        │ list_tools → OpenAI tool schemas              app/tools/*  validate input, trim GitHub JSON to Pydantic models
        │ Groq chooses tools (or rule-based planner)           │
        │ call_tool over MCP, results back to the LLM          ▼
        ▼                                               app/github/client.py
   printed trace + answer                                 cache (SQLite, TTL) ─► hit: no request
                                                          miss ─► api.github.com (retries on 5xx/timeouts)
                                                          rate-limited / down ─► stale cache or clear error
```

```
main.py                 HTTP entrypoint (uvicorn main:app): /mcp + /health
server_stdio.py         stdio entrypoint for desktop MCP clients
app/
  server.py             FastMCP instance; tools registered once, with read-only annotations
  tools/                search_repos.py, get_issues.py, get_file.py, validation.py
  github/               client.py (HTTP, errors, retries), cache.py (SQLite TTL cache), fixtures.py
  models.py             structured tool outputs
  errors.py             coded ToolErrors
  config.py             settings
client/                 demo agent: connection.py (stdio/HTTP), agent.py (Groq), planner.py (no key)
fixtures/github/        recorded GitHub responses for offline mode (see below)
scripts/                record_fixtures.py, seed.py
tests/                  fake GitHub (fictional repos), in-memory, stdio and HTTP MCP tests
```

**Design choices:**

- **Tool outputs are trimmed Pydantic models.** Raw GitHub JSON is roughly 10x larger, which wastes the agent's context window. The output schemas also let MCP clients validate results.
- **The agent hard-codes nothing about GitHub.** It builds its tool list from `list_tools()`, so adding a tool to the server makes it available to the agent with no client changes.
- **Stateless HTTP with JSON responses.** Each request stands alone, so the server scales horizontally and is easy to call with plain HTTP.
- **DNS-rebinding protection.** `/mcp` only accepts `Host` headers listed in `ALLOWED_HOSTS`.

## Recording fixtures (offline mode)

`fixtures/github/` holds real GitHub API responses for the example queries. It ships empty because the build environment couldn't reach GitHub. To record them once (about 8 requests, no token needed):

```bash
python -m scripts.record_fixtures
```

Commit the JSON files it writes. They're loaded into the cache on startup:

- Online, they're only a fallback, and fresh data is fetched as normal.
- With `OFFLINE_MODE=true`, they're served as-is, so the demo runs with no network at all.

## Demo mode

**It runs free, with no API keys.**

| Piece | Cost |
|---|---|
| GitHub public API, unauthenticated (60 req/hour, or 5,000 with an optional free token) | free |
| Response cache: SQLite in `./data` | free |
| Demo agent LLM: Groq free tier. Without a key, the rule-based planner is used | free |

The server itself never needs an LLM. `GROQ_API_KEY` only affects the demo client:

- **Without a key,** the planner picks one tool from the question, calls it over MCP and formats the result. It can't chain tools.
- **With a free key** from https://console.groq.com/keys, the LLM agent can chain calls, for example "find the top Python MCP repo, then show its open issues". If the LLM call fails, the client falls back to the planner.

## Configuration

Every variable is listed with its default in [`.env.example`](.env.example).
