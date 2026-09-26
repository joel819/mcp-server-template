import re

from app.errors import tool_error

_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def check_repo(owner: str, repo: str) -> None:
    for label, value in (("owner", owner), ("repo", repo)):
        if not _NAME.fullmatch(value or "") or value in (".", ".."):
            raise tool_error("invalid_input", f"{label} {value!r} is not a valid GitHub name.")


def check_path(path: str) -> str:
    path = (path or "").strip().strip("/")
    if any(part == ".." for part in path.split("/")) or len(path) > 500:
        raise tool_error("invalid_input", f"path {path!r} is not allowed.")
    return path
