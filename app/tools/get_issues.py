from typing import Annotated, Literal

from pydantic import Field

from app.config import get_settings
from app.github import get_github
from app.models import IssueList, IssueSummary
from app.tools.validation import check_repo

PREVIEW_CHARS = 400


async def get_issues(
    owner: Annotated[str, Field(description="Repository owner, e.g. 'fastapi'")],
    repo: Annotated[str, Field(description="Repository name, e.g. 'fastapi'")],
    state: Annotated[Literal["open", "closed", "all"], Field(description="Issue state")] = "open",
    labels: Annotated[str | None, Field(description="Comma-separated label names, e.g. 'bug,help wanted'")] = None,
    limit: Annotated[int, Field(ge=1, le=50, description="Number of issues (1-50)")] = 10,
) -> IssueList:
    """List issues in a public repository, newest first. Pull requests are excluded."""
    check_repo(owner, repo)
    limit = min(limit, get_settings().max_issues)
    # GitHub's issues endpoint also returns PRs; over-fetch so enough real issues remain after filtering.
    params = {"state": state, "labels": labels, "per_page": min(100, max(limit * 2, 20)),
              "sort": "created", "direction": "desc"}
    data = await get_github().get_json(f"/repos/{owner}/{repo}/issues", params)
    items = []
    for i in data:
        if "pull_request" in i:
            continue
        body = " ".join((i.get("body") or "").split())
        items.append(IssueSummary(
            number=i["number"], title=i["title"], state=i["state"], author=(i.get("user") or {}).get("login"),
            labels=[lb["name"] for lb in i.get("labels", []) if isinstance(lb, dict)], comments=i.get("comments", 0),
            created_at=i["created_at"], updated_at=i["updated_at"], html_url=i["html_url"],
            body_preview=body[:PREVIEW_CHARS] + ("…" if len(body) > PREVIEW_CHARS else ""),
        ))
        if len(items) == limit:
            break
    return IssueList(repo=f"{owner}/{repo}", state=state, count=len(items), items=items)
