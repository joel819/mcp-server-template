"""A fake GitHub API for tests (httpx.MockTransport). Repos are fictional (example-org/...);
response shapes follow GitHub's REST API docs, trimmed to the fields the tools read."""
import base64
import json

import httpx

REPOS = {
    "example-org/lighthouse": dict(description="A tiny MCP server framework", stargazers_count=4210, forks_count=312,
                                   open_issues_count=27, language="Python", topics=["mcp", "llm", "agents"],
                                   license={"spdx_id": "MIT"}),
    "example-org/tidepool": dict(description="Embedded vector database", stargazers_count=1830, forks_count=96,
                                 open_issues_count=12, language="Rust", topics=["vector-database"], license=None),
}


def repo_json(full_name: str) -> dict:
    return {"full_name": full_name, "html_url": f"https://github.com/{full_name}",
            "updated_at": "2026-09-20T10:00:00Z", **REPOS[full_name]}


def issue(n: int, title: str, pr: bool = False, labels=()) -> dict:
    d = {"number": n, "title": title, "state": "open", "user": {"login": f"user{n}"},
         "labels": [{"name": lb} for lb in labels], "comments": n % 5,
         "created_at": "2026-09-1%dT09:00:00Z" % (n % 10), "updated_at": "2026-09-20T09:00:00Z",
         "html_url": f"https://github.com/example-org/lighthouse/issues/{n}",
         "body": f"Details for issue {n}. " * 40}
    if pr:
        d["pull_request"] = {"url": "..."}
    return d


ISSUES = [issue(12, "Crash when tool returns None", labels=["bug"]),
          issue(11, "Add streaming support", pr=True),
          issue(10, "Docs: stdio example is outdated", labels=["docs"]),
          issue(9, "Support Python 3.13")]


def file_json(path: str, content: bytes) -> dict:
    return {"type": "file", "name": path.rsplit("/", 1)[-1], "path": path, "size": len(content),
            "encoding": "base64", "content": base64.b64encode(content).decode(),
            "html_url": f"https://github.com/example-org/lighthouse/blob/main/{path}"}


FILES = {
    "README.md": b"# Lighthouse\n\nA tiny MCP server framework.\n\n## Install\n\npip install lighthouse\n",
    "big.txt": b"x" * 250_000,
    "logo.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
}
ROOT = [{"name": "src", "path": "src", "type": "dir", "size": 0},
        {"name": "README.md", "path": "README.md", "type": "file", "size": 80},
        {"name": "pyproject.toml", "path": "pyproject.toml", "type": "file", "size": 900}]


class FakeGitHub:
    """Routes requests; records them so tests can assert on call counts and params."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.rate_limited = False
        self.fail_times = 0  # respond 502 this many times before succeeding

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path, q = request.url.path, dict(request.url.params)
        headers = {"x-ratelimit-remaining": "59", "x-ratelimit-reset": "1790000000"}
        if self.rate_limited:
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1790000000"},
                                  json={"message": "API rate limit exceeded for 203.0.113.7."})
        if self.fail_times:
            self.fail_times -= 1
            return httpx.Response(502, json={"message": "Server Error"})

        if path == "/search/repositories":
            if q.get("q", "").startswith("::"):
                return httpx.Response(422, json={"message": "Validation Failed",
                                                 "errors": [{"message": "The search query is invalid"}]})
            terms = q["q"].lower()
            items = [repo_json(n) for n in REPOS if any(t in json.dumps(repo_json(n)).lower()
                                                        for t in terms.split() if ":" not in t)]
            if "language:rust" in terms:
                items = [i for i in items if i["language"] == "Rust"]
            return httpx.Response(200, headers=headers, json={"total_count": len(items), "items": items})
        if path == "/repos/example-org/lighthouse/issues":
            return httpx.Response(200, headers=headers, json=ISSUES)
        if path == "/repos/example-org/lighthouse/contents/" or path == "/repos/example-org/lighthouse/contents":
            return httpx.Response(200, headers=headers, json=ROOT)
        if path.startswith("/repos/example-org/lighthouse/contents/"):
            p = path.removeprefix("/repos/example-org/lighthouse/contents/")
            if p == "huge.bin":
                return httpx.Response(200, json={"type": "file", "path": p, "size": 5_000_000, "encoding": "none",
                                                 "content": "", "html_url": "https://github.com/x"})
            if p == "submod":
                return httpx.Response(200, json={"type": "submodule", "path": p})
            if p in FILES:
                return httpx.Response(200, headers=headers, json=file_json(p, FILES[p]))
        return httpx.Response(404, json={"message": "Not Found"})
