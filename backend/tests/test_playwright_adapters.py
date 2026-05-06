"""Tests for the Playwright-based career-portal adapters.

We do not launch a real Chromium browser in the suite — that would push
CI cost and runtime through the roof. Instead, the ``PlaywrightPool`` is
swapped for a fake whose ``acquire_page`` yields a hand-rolled
``FakePage`` that records goto/wait calls and answers ``content``,
``evaluate`` and ``locator`` from data the test sets up.

Tests are skipped (not failed) on backends without the optional
Playwright extra, so dev machines that did not run
``pip install -e .[playwright]`` keep a green pytest run.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Callable

import pytest

# Skip the whole module — including the adapter imports below — when
# the optional extra is missing. Otherwise importing
# ``app.providers.jobs.playwright_*`` would explode at collection time.
pytest.importorskip("playwright")

from app.models.job_source import JobSource  # noqa: E402
from app.providers.jobs import (  # noqa: E402
    AdapterError,
    PLAYWRIGHT_AVAILABLE,
)
from app.providers.jobs.playwright_api_fetch import PlaywrightApiFetchAdapter  # noqa: E402
from app.providers.jobs.playwright_css_count import PlaywrightCssCountAdapter  # noqa: E402
from app.providers.jobs.playwright_text_regex import PlaywrightTextRegexAdapter  # noqa: E402

assert PLAYWRIGHT_AVAILABLE, "registry should pick up the playwright adapters here"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeLocator:
    """Stand-in for `page.locator(...)`.

    * ``.first`` returns self so chained ``.first.is_visible()`` works.
    * ``is_visible()`` is always False so the cookie-banner loop falls
      through cleanly without clicking anything.
    * ``count()`` returns whatever the test put into ``count_value``.
    """

    def __init__(self, count_value: int = 0) -> None:
        self.count_value = count_value

    @property
    def first(self) -> "_FakeLocator":
        return self

    async def is_visible(self, *, timeout: int = 0) -> bool:
        return False

    async def count(self) -> int:
        return self.count_value

    async def click(self) -> None:  # pragma: no cover - never reached
        return None


class _FakePage:
    def __init__(
        self,
        *,
        url: str,
        html: str = "",
        visible_text: str = "",
        evaluate_results: dict[str, Any] | None = None,
        locator_counts: dict[str, int] | None = None,
    ) -> None:
        self.url = url
        self._html = html
        self._visible_text = visible_text
        self._evaluate_results = evaluate_results or {}
        self._locator_counts = locator_counts or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.calls.append(("goto", {"url": url, "wait_until": wait_until}))
        self.url = url

    async def wait_for_selector(self, selector: str, *, state: str, timeout: int) -> None:
        self.calls.append(("wait_for_selector", {"selector": selector, "state": state}))

    async def wait_for_timeout(self, ms: int) -> None:
        self.calls.append(("wait_for_timeout", {"ms": ms}))

    async def content(self) -> str:
        return self._html

    async def evaluate(self, script: str, args: Any = None) -> Any:
        # `text_regex` calls evaluate("() => document.body.innerText")
        # without args — return the visible text in that case. The
        # api_fetch adapter passes (endpoint, method, payload) as args.
        if args is None:
            return self._visible_text
        if "innerText" in script:
            return self._visible_text
        # Pick the result by endpoint so a single fixture can serve
        # multiple adapter calls if we ever need it.
        endpoint = args[0]
        if endpoint not in self._evaluate_results:
            raise KeyError(f"no evaluate stub for {endpoint!r}")
        result = self._evaluate_results[endpoint]
        if isinstance(result, Exception):
            raise result
        return result

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self._locator_counts.get(selector, 0))


class _FakePool:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    @asynccontextmanager
    async def acquire_page(self):
        yield self._page


@pytest.fixture
def patch_pool(monkeypatch):
    """Swap ``PlaywrightPool.get_instance`` with a fake pool factory."""

    def _set(page: _FakePage) -> None:
        from app.providers.jobs import playwright_pool

        async def _get_instance() -> _FakePool:
            return _FakePool(page)

        monkeypatch.setattr(playwright_pool.PlaywrightPool, "get_instance", _get_instance)

    return _set


def _make_source(adapter_type: str, settings: dict, *, portal_url: str = "https://example.com") -> JobSource:
    return JobSource(
        id=1,
        isin=None,
        name="Example",
        portal_url=portal_url,
        adapter_type=adapter_type,
        adapter_settings=settings,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# PlaywrightTextRegexAdapter
# ---------------------------------------------------------------------------


def test_text_regex_matches_inside_html(patch_pool):
    page = _FakePage(
        url="https://careers.example.com/",
        html="<h2>1,234 results found</h2>",
        visible_text="1,234 results found",
    )
    patch_pool(page)

    source = _make_source(
        "playwright_text_regex",
        {
            "wait_for_selector": "h2",
            "regex_pattern": r"(\d[\d,]*)\s*results?\s*found",
        },
    )

    count, meta = asyncio.run(PlaywrightTextRegexAdapter().fetch_job_count(source))
    assert count == 1234
    assert meta["pattern"] == r"(\d[\d,]*)\s*results?\s*found"
    assert "1,234" in meta["matched_text"]


def test_text_regex_falls_back_to_inner_text(patch_pool):
    # The HTML preview only carries the empty SPA shell, but the
    # rendered visible_text has the count. The adapter must still hit.
    page = _FakePage(
        url="https://careers.example.com/",
        html="<div id='app'></div>",
        visible_text="We found 42 results today",
    )
    patch_pool(page)
    source = _make_source(
        "playwright_text_regex",
        {
            "wait_for_selector": "#app",
            "regex_pattern": r"We found (\d+) results",
        },
    )
    count, _ = asyncio.run(PlaywrightTextRegexAdapter().fetch_job_count(source))
    assert count == 42


def test_text_regex_raises_when_no_match(patch_pool):
    page = _FakePage(
        url="https://careers.example.com/",
        html="<h2>no jobs here</h2>",
        visible_text="no jobs here",
    )
    patch_pool(page)
    source = _make_source(
        "playwright_text_regex",
        {"wait_for_selector": "h2", "regex_pattern": r"(\d+) results"},
    )
    with pytest.raises(AdapterError, match="regex did not match"):
        asyncio.run(PlaywrightTextRegexAdapter().fetch_job_count(source))


def test_text_regex_requires_settings():
    with pytest.raises(AdapterError, match="wait_for_selector"):
        asyncio.run(
            PlaywrightTextRegexAdapter().fetch_job_count(
                _make_source("playwright_text_regex", {"regex_pattern": r"(\d+)"})
            )
        )
    with pytest.raises(AdapterError, match="regex_pattern"):
        asyncio.run(
            PlaywrightTextRegexAdapter().fetch_job_count(
                _make_source("playwright_text_regex", {"wait_for_selector": "h2"})
            )
        )


# ---------------------------------------------------------------------------
# PlaywrightCssCountAdapter
# ---------------------------------------------------------------------------


def test_css_count_returns_locator_count(patch_pool):
    page = _FakePage(
        url="https://careers.example.com/",
        locator_counts={".job-card": 17},
    )
    patch_pool(page)
    source = _make_source(
        "playwright_css_count",
        {"count_selector": ".job-card"},
    )
    count, meta = asyncio.run(PlaywrightCssCountAdapter().fetch_job_count(source))
    assert count == 17
    assert meta["selector"] == ".job-card"
    assert meta["wait_for_selector"] == ".job-card"


def test_css_count_uses_separate_wait_selector(patch_pool):
    page = _FakePage(
        url="https://careers.example.com/",
        locator_counts={"li.job": 3},
    )
    patch_pool(page)
    source = _make_source(
        "playwright_css_count",
        {"count_selector": "li.job", "wait_for_selector": "ul.results"},
    )
    count, meta = asyncio.run(PlaywrightCssCountAdapter().fetch_job_count(source))
    assert count == 3
    assert any(call == ("wait_for_selector", {"selector": "ul.results", "state": "attached"}) for call in page.calls)


def test_css_count_requires_selector():
    with pytest.raises(AdapterError, match="count_selector"):
        asyncio.run(
            PlaywrightCssCountAdapter().fetch_job_count(
                _make_source("playwright_css_count", {})
            )
        )


# ---------------------------------------------------------------------------
# PlaywrightApiFetchAdapter
# ---------------------------------------------------------------------------


def test_api_fetch_walks_value_path(patch_pool):
    page = _FakePage(
        url="https://careers.example.com/",
        evaluate_results={
            "https://careers.example.com/api/jobs": {
                "data": {"summary": {"totalJob": 256}}
            }
        },
    )
    patch_pool(page)
    source = _make_source(
        "playwright_api_fetch",
        {
            "endpoint": "https://careers.example.com/api/jobs",
            "value_path": "data.summary.totalJob",
        },
    )
    count, meta = asyncio.run(PlaywrightApiFetchAdapter().fetch_job_count(source))
    assert count == 256
    assert meta["method"] == "POST"


def test_api_fetch_supports_get(patch_pool):
    page = _FakePage(
        url="https://careers.example.com/",
        evaluate_results={
            "https://careers.example.com/api/jobs": {"totalJob": 7}
        },
    )
    patch_pool(page)
    source = _make_source(
        "playwright_api_fetch",
        {
            "endpoint": "https://careers.example.com/api/jobs",
            "value_path": "totalJob",
            "method": "GET",
        },
    )
    count, meta = asyncio.run(PlaywrightApiFetchAdapter().fetch_job_count(source))
    assert count == 7
    assert meta["method"] == "GET"


def test_api_fetch_rejects_unknown_method():
    source = _make_source(
        "playwright_api_fetch",
        {
            "endpoint": "https://careers.example.com/api/jobs",
            "value_path": "totalJob",
            "method": "PATCH",
        },
    )
    with pytest.raises(AdapterError, match="GET or POST"):
        asyncio.run(PlaywrightApiFetchAdapter().fetch_job_count(source))


def test_api_fetch_raises_when_value_path_missing(patch_pool):
    page = _FakePage(
        url="https://careers.example.com/",
        evaluate_results={
            "https://careers.example.com/api/jobs": {"summary": {}}
        },
    )
    patch_pool(page)
    source = _make_source(
        "playwright_api_fetch",
        {
            "endpoint": "https://careers.example.com/api/jobs",
            "value_path": "summary.totalJob",
        },
    )
    with pytest.raises(AdapterError, match="not found"):
        asyncio.run(PlaywrightApiFetchAdapter().fetch_job_count(source))


def test_api_fetch_propagates_in_browser_failure(patch_pool):
    page = _FakePage(
        url="https://careers.example.com/",
        evaluate_results={
            "https://careers.example.com/api/jobs": RuntimeError("HTTP 403")
        },
    )
    patch_pool(page)
    source = _make_source(
        "playwright_api_fetch",
        {
            "endpoint": "https://careers.example.com/api/jobs",
            "value_path": "totalJob",
        },
    )
    with pytest.raises(AdapterError, match="in-browser fetch failed"):
        asyncio.run(PlaywrightApiFetchAdapter().fetch_job_count(source))


def test_api_fetch_requires_settings():
    with pytest.raises(AdapterError, match="endpoint"):
        asyncio.run(
            PlaywrightApiFetchAdapter().fetch_job_count(
                _make_source("playwright_api_fetch", {"value_path": "x"})
            )
        )
    with pytest.raises(AdapterError, match="value_path"):
        asyncio.run(
            PlaywrightApiFetchAdapter().fetch_job_count(
                _make_source(
                    "playwright_api_fetch",
                    {"endpoint": "https://careers.example.com/api/jobs"},
                )
            )
        )
