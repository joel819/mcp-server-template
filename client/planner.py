"""No-API-key fallback: a rule-based planner that still goes through MCP.

Picks one tool from the question (owner/repo + "issue" -> get_issues, owner/repo + a file
-> get_file_contents, otherwise search_repos), calls it over the protocol, and formats the
structured result. Less flexible than the LLM agent: one tool call, no follow-ups.
"""
import re

from mcp import ClientSession

from client.tools import call

REPO_REF = re.compile(r"\b([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)\b")
FILE_REF = re.compile(r"\b([\w./-]+\.(?:md|py|toml|txt|json|ya?ml|cfg|ini|rst|js|ts|go|rs))\b", re.I)
LANGUAGES = ["python", "javascript", "typescript", "go", "rust", "java", "kotlin", "swift", "ruby", "php",
             "c++", "c#", "scala", "elixir", "haskell", "dart", "zig"]
STOP = set("find show me list the a an of for with in on about what which are is top best popular most good "
           "some repos repositories repo projects project github written language please any".split())


def plan(question: str) -> tuple[str, dict]:
    q = question.strip()
    low = q.lower()
    repo = next((m for m in REPO_REF.finditer(q) if not FILE_REF.fullmatch(m.group(0))), None)
    if repo:
        owner, name = repo.group(1), repo.group(2)
        if "issue" in low or "bug" in low:
            state = "closed" if "closed" in low else "open"
            return "get_issues", {"owner": owner, "repo": name, "state": state, "limit": 5}
        file_match = FILE_REF.search(q.replace(repo.group(0), ""))
        if file_match or "readme" in low:
            return "get_file_contents", {"owner": owner, "repo": name,
                                         "path": file_match.group(1) if file_match else "README.md"}
        if any(w in low for w in ("files", "structure", "folder", "directory", "contents")):
            return "get_file_contents", {"owner": owner, "repo": name, "path": ""}
        return "get_issues", {"owner": owner, "repo": name, "state": "open", "limit": 5}
    language = next((lang for lang in LANGUAGES if re.search(rf"\b{re.escape(lang)}\b", low)), None)
    words = [w for w in re.findall(r"[a-z0-9+#.-]+", low) if w not in STOP and w != language]
    sort = "stars" if any(w in low for w in ("popular", "top", "most", "best", "stars")) else "best-match"
    return "search_repos", {"query": " ".join(words) or q, "language": language, "sort": sort, "limit": 5}


def format_result(tool: str, data: dict) -> str:
    if tool == "search_repos":
        if not data["items"]:
            return f"No repositories found for '{data['query']}'."
        lines = [f"Top results for '{data['query']}' ({data['total_count']:,} matches):"]
        for r in data["items"]:
            lang = f", {r['language']}" if r["language"] else ""
            desc = f": {r['description']}" if r["description"] else ""
            lines.append(f"- {r['full_name']} ({r['stars']:,} stars{lang}){desc}")
        return "\n".join(lines)
    if tool == "get_issues":
        if not data["items"]:
            return f"No {data['state']} issues in {data['repo']}."
        lines = [f"Latest {data['state']} issues in {data['repo']}:"]
        lines += [f"- #{i['number']} {i['title']} ({i['comments']} comments)" for i in data["items"]]
        return "\n".join(lines)
    if data["type"] == "dir":
        names = [f"{e['name']}/" if e["type"] == "dir" else e["name"] for e in data["entries"]]
        return f"{data['repo']}/{data['path'].strip('/')} contains: " + ", ".join(names)
    head = "\n".join((data["content"] or "").splitlines()[:25])
    more = "\n… (truncated)" if data["truncated"] or len((data["content"] or "").splitlines()) > 25 else ""
    return f"First lines of {data['repo']}/{data['path']}:\n\n{head}{more}"


async def answer(session: ClientSession, question: str, trace: list) -> str:
    tool, args = plan(question)
    ok, text, structured = await call(session, tool, args, trace)
    if not ok:
        return f"The {tool} tool returned an error: {text}"
    return format_result(tool, structured)
