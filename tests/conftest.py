"""Tests never touch the network: GitHub is a MockTransport, the LLM is mocked, no keys are needed."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="mcp-tests-")
os.environ.update(DATA_DIR=_tmp, OFFLINE_MODE="false", SEED_ON_STARTUP="false", GROQ_API_KEY="",
                  GITHUB_TOKEN="", CACHE_TTL_SECONDS="600")

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.github import set_github  # noqa: E402
from app.github.cache import ResponseCache  # noqa: E402
from app.github.client import GitHubClient  # noqa: E402
from tests.fake_github import FakeGitHub  # noqa: E402


@pytest.fixture
def fake():
    return FakeGitHub()


@pytest.fixture
def make_client(fake):
    def _make(**settings_overrides):
        settings = get_settings().model_copy(update={"http_retries": 2, **settings_overrides})
        client = GitHubClient(settings, ResponseCache(":memory:"), transport=httpx.MockTransport(fake))
        set_github(client)
        return client

    yield _make
    set_github(None)


@pytest.fixture
def gh(make_client):
    return make_client()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def instant(_):
        return None

    monkeypatch.setattr("app.github.client.asyncio.sleep", instant)
