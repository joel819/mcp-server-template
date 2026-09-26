from typing import Annotated, Literal

from pydantic import Field

from app.config import get_settings
from app.errors import tool_error
from app.github import get_github
from app.models import RepoSearchResult, RepoSummary


def to_summary(r: dict) -> RepoSummary:
    return RepoSummary(
        full_name=r["full_name"], description=r.get("description"), stars=r.get("stargazers_count", 0),
        forks=r.get("forks_count", 0), open_issues=r.get("open_issues_count", 0), language=r.get("language"),
        topics=r.get("topics") or [], license=(r.get("license") or {}).get("spdx_id"),
        updated_at=r.get("updated_at", ""), html_url=r["html_url"],
    )


async def search_repos(
    query: Annotated[str, Field(description="Search terms, e.g. 'vector database' or 'topic:mcp'. "
                                            "GitHub search qualifiers are allowed.")],
    language: Annotated[str | None, Field(description="Only repos in this language, e.g. 'python'")] = None,
    sort: Annotated[Literal["best-match", "stars", "forks", "updated"],
                    Field(description="Result order")] = "best-match",
    limit: Annotated[int, Field(ge=1, le=30, description="Number of results (1-30)")] = 10,
) -> RepoSearchResult:
    """Search public GitHub repositories. Returns name, description, stars, language, topics and URL."""
    query = query.strip()
    if not query:
        raise tool_error("invalid_input", "query must not be empty.")
    limit = min(limit, get_settings().max_search_results)
    q = f"{query} language:{language}" if language else query
    params = {"q": q, "per_page": limit}
    if sort != "best-match":
        params |= {"sort": sort, "order": "desc"}
    data = await get_github().get_json("/search/repositories", params)
    return RepoSearchResult(query=q, total_count=data.get("total_count", 0),
                            items=[to_summary(r) for r in data.get("items", [])[:limit]])
