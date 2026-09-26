"""GitHub REST client: cache first, clear errors, rate-limit awareness, retries on transient failures."""
import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.errors import tool_error
from app.github.cache import ResponseCache

log = logging.getLogger("mcp.github")


def cache_key(path: str, params: dict[str, Any] | None = None) -> str:
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    query = urlencode(sorted(clean.items()))
    return f"GET {path}" + (f"?{query}" if query else "")


def _reset_hint(headers: httpx.Headers) -> str:
    if retry_after := headers.get("retry-after"):
        return f"retry after {retry_after} seconds"
    if reset := headers.get("x-ratelimit-reset"):
        when = datetime.fromtimestamp(int(reset), UTC)
        mins = max(0, round((when.timestamp() - time.time()) / 60))
        return f"resets at {when:%H:%M} UTC (in about {mins} min)"
    return "try again later"


class GitHubClient:
    def __init__(self, settings: Settings, cache: ResponseCache, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.cache = cache
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mcp-server-template",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self.http = httpx.AsyncClient(
            base_url=settings.github_api_url, headers=headers, timeout=settings.http_timeout_seconds,
            transport=transport,
        )
        self.rate_limit_remaining: int | None = None

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        key = cache_key(path, params)
        if self.settings.offline_mode:
            entry = self.cache.get(key, max_age=None)
            if entry is None:
                raise tool_error("offline_miss",
                                 "Offline mode is on and this request isn't in the recorded fixtures. "
                                 "Try one of the example queries in the README, or turn OFFLINE_MODE off.")
            return entry.body

        fresh = self.cache.get(key, max_age=self.settings.cache_ttl_seconds)
        if fresh is not None:
            return fresh.body

        try:
            resp = await self._request(path, params)
        except httpx.TransportError as exc:
            return self._stale_or_raise(key, "network_error", f"Could not reach GitHub ({type(exc).__name__}).")

        remaining = resp.headers.get("x-ratelimit-remaining")
        if remaining is not None and remaining.isdigit():
            self.rate_limit_remaining = int(remaining)

        if resp.status_code == 200:
            body = resp.json()
            self.cache.set(key, body)
            return body
        if resp.status_code == 404:
            raise tool_error("not_found", "GitHub returned 404: the repository or path doesn't exist, or is private.")
        if resp.status_code in (403, 429) and (remaining == "0" or "retry-after" in resp.headers
                                               or "rate limit" in resp.text.lower()):
            return self._stale_or_raise(
                key, "rate_limited",
                f"GitHub API rate limit reached; {_reset_hint(resp.headers)}. "
                "Set GITHUB_TOKEN (a free token, no scopes needed) to raise the limit to 5,000/hour.",
            )
        if resp.status_code == 401:
            raise tool_error("bad_token", "GitHub rejected GITHUB_TOKEN. Remove it or create a new one.")
        if resp.status_code == 422:
            detail = _github_message(resp)
            raise tool_error("invalid_input", f"GitHub couldn't process the request: {detail}")
        if resp.status_code >= 500:
            return self._stale_or_raise(key, "upstream_error", f"GitHub returned {resp.status_code}.")
        raise tool_error("upstream_error", f"GitHub returned {resp.status_code}: {_github_message(resp)}")

    async def _request(self, path: str, params: dict[str, Any] | None) -> httpx.Response:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        attempt = 0
        while True:
            try:
                resp = await self.http.get(path, params=clean)
                if resp.status_code < 500 or attempt >= self.settings.http_retries:
                    return resp
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt >= self.settings.http_retries:
                    raise
            attempt += 1
            await asyncio.sleep(0.4 * 2 ** (attempt - 1))

    def _stale_or_raise(self, key: str, code: str, message: str) -> Any:
        stale = self.cache.get(key, max_age=None)
        if stale is not None:
            log.warning("%s; serving cached copy from %.0f min ago", message, stale.age() / 60)
            return stale.body
        raise tool_error(code, message)

    async def aclose(self) -> None:
        await self.http.aclose()


def _github_message(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except ValueError:
        return resp.text[:200]
    msg = data.get("message", "")
    errors = "; ".join(e.get("message") or e.get("code", "") for e in data.get("errors", []) if isinstance(e, dict))
    return f"{msg} {errors}".strip()[:300]
