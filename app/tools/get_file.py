import base64
from typing import Annotated

from pydantic import Field

from app.config import get_settings
from app.errors import tool_error
from app.github import get_github
from app.models import DirEntry, FileContent
from app.tools.validation import check_path, check_repo


async def get_file_contents(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    path: Annotated[str, Field(description="File or directory path, e.g. 'README.md' or 'src'. "
                                           "Empty string for the repository root.")] = "",
    ref: Annotated[str | None, Field(description="Branch, tag or commit SHA (default branch if omitted)")] = None,
) -> FileContent:
    """Read a text file from a public repository, or list a directory's entries.
    Large files are truncated; binary files are refused."""
    check_repo(owner, repo)
    path = check_path(path)
    data = await get_github().get_json(f"/repos/{owner}/{repo}/contents/{path}", {"ref": ref})
    full = f"{owner}/{repo}"

    if isinstance(data, list):  # a directory
        entries = [DirEntry(name=e["name"], path=e["path"], type=e["type"], size=e.get("size", 0)) for e in data]
        entries.sort(key=lambda e: (e.type != "dir", e.name.lower()))
        return FileContent(repo=full, path=path or "/", ref=ref, type="dir", entries=entries)

    if data.get("type") != "file":
        raise tool_error("unsupported_type", f"{path} is a {data.get('type')}, not a file or directory.")
    if data.get("encoding") != "base64" or data.get("content") is None:
        # GitHub omits content for files over 1 MB
        raise tool_error("too_large", f"{path} is {data.get('size', 0):,} bytes; GitHub doesn't inline files this "
                                      f"large. Open it at {data.get('html_url')}.")
    raw = base64.b64decode(data["content"])
    if b"\x00" in raw[:8000]:
        raise tool_error("unsupported_binary", f"{path} is a binary file; only text files can be read.")
    limit = get_settings().max_file_bytes
    text = raw[:limit].decode("utf-8", errors="replace")
    return FileContent(repo=full, path=path, ref=ref, type="file", size=data.get("size"), content=text,
                       truncated=len(raw) > limit, html_url=data.get("html_url"))
