"""Tool outputs. Trimmed to what an agent needs: GitHub's raw JSON is ~10x larger."""
from pydantic import BaseModel


class RepoSummary(BaseModel):
    full_name: str
    description: str | None
    stars: int
    forks: int
    open_issues: int
    language: str | None
    topics: list[str]
    license: str | None
    updated_at: str
    html_url: str


class RepoSearchResult(BaseModel):
    query: str
    total_count: int
    items: list[RepoSummary]


class IssueSummary(BaseModel):
    number: int
    title: str
    state: str
    author: str | None
    labels: list[str]
    comments: int
    created_at: str
    updated_at: str
    html_url: str
    body_preview: str


class IssueList(BaseModel):
    repo: str
    state: str
    count: int
    items: list[IssueSummary]


class DirEntry(BaseModel):
    name: str
    path: str
    type: str  # file | dir | symlink | submodule
    size: int


class FileContent(BaseModel):
    repo: str
    path: str
    ref: str | None
    type: str  # "file" or "dir"
    size: int | None = None
    content: str | None = None  # decoded UTF-8 text, for files
    truncated: bool = False
    entries: list[DirEntry] | None = None  # for directories
    html_url: str | None = None
