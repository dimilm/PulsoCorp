"""Tests for the httpx-based career-portal adapters.

We mock the httpx layer with `httpx.MockTransport` rather than `respx` so the
suite stays dependency-free. Each adapter has at least one happy path and one
configuration-error path; the `*_path_int` adapters additionally verify the
nested-path traversal because that has historically been the most error-prone
piece of the legacy code.
"""
from __future__ import annotations

import asyncio
import json
from typing import Callable

import httpx
import pytest

from app.models.job_source import JobSource
from app.providers.jobs import (
    AdapterError,
    JsonGetArrayCountAdapter,
    JsonGetPathIntAdapter,
    JsonPostFacetSumAdapter,
    JsonPostPathIntAdapter,
    StaticHtmlAdapter,
    StaticTextRegexAdapter,
)


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


@pytest.fixture
def patch_httpx(monkeypatch):
    """Yield a setter that swaps httpx.AsyncClient for a transport-driven one."""

    def _set(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        transport = httpx.MockTransport(handler)
        original = httpx.AsyncClient

        def _factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", _factory)

    return _set


# ---------------------------------------------------------------------------
# StaticHtmlAdapter
# ---------------------------------------------------------------------------

class TestStaticHtmlAdapter:
    def test_counts_matching_elements(self, patch_httpx):
        html = """
        <html><body>
            <a class="job-card">A</a>
            <a class="job-card">B</a>
            <a class="job-card">C</a>
            <a class="other">X</a>
        </body></html>
        """
        patch_httpx(lambda req: httpx.Response(200, text=html))

        source = _make_source("static_html", {"count_selector": ".job-card"})
        count, meta = asyncio.run(StaticHtmlAdapter().fetch_job_count(source))

        assert count == 3
        assert meta["selector"] == ".job-card"

    def test_missing_selector_raises(self):
        source = _make_source("static_html", {})
        with pytest.raises(AdapterError):
            asyncio.run(StaticHtmlAdapter().fetch_job_count(source))


# ---------------------------------------------------------------------------
# JsonGetPathIntAdapter
# ---------------------------------------------------------------------------

class TestJsonGetPathIntAdapter:
    def test_reads_nested_integer(self, patch_httpx):
        body = {"meta": {"hits": 42}}
        patch_httpx(lambda req: httpx.Response(200, json=body))

        source = _make_source(
            "json_get_path_int",
            {"endpoint": "https://api.example.com/jobs", "value_path": "meta.hits"},
        )
        count, meta = asyncio.run(JsonGetPathIntAdapter().fetch_job_count(source))

        assert count == 42
        assert meta["value_path"] == "meta.hits"

    def test_missing_path_raises(self, patch_httpx):
        patch_httpx(lambda req: httpx.Response(200, json={"data": {}}))
        source = _make_source(
            "json_get_path_int",
            {"endpoint": "https://api.example.com/jobs", "value_path": "data.total"},
        )
        with pytest.raises(AdapterError):
            asyncio.run(JsonGetPathIntAdapter().fetch_job_count(source))

    def test_missing_endpoint_raises(self):
        source = _make_source("json_get_path_int", {"value_path": "x"})
        with pytest.raises(AdapterError):
            asyncio.run(JsonGetPathIntAdapter().fetch_job_count(source))


# ---------------------------------------------------------------------------
# JsonGetArrayCountAdapter
# ---------------------------------------------------------------------------

class TestJsonGetArrayCountAdapter:
    def test_counts_array_items(self, patch_httpx):
        patch_httpx(lambda req: httpx.Response(200, json={"jobs": [1, 2, 3, 4, 5]}))
        source = _make_source(
            "json_get_array_count",
            {"endpoint": "https://api.example.com/jobs", "array_field": "jobs"},
        )
        count, meta = asyncio.run(JsonGetArrayCountAdapter().fetch_job_count(source))

        assert count == 5
        assert meta["items"] == 5

    def test_missing_array_raises(self, patch_httpx):
        patch_httpx(lambda req: httpx.Response(200, json={"jobs": "not-a-list"}))
        source = _make_source(
            "json_get_array_count",
            {"endpoint": "https://api.example.com/jobs", "array_field": "jobs"},
        )
        with pytest.raises(AdapterError):
            asyncio.run(JsonGetArrayCountAdapter().fetch_job_count(source))


# ---------------------------------------------------------------------------
# JsonPostPathIntAdapter
# ---------------------------------------------------------------------------

class TestJsonPostPathIntAdapter:
    def test_posts_payload_and_reads_path(self, patch_httpx):
        captured: dict = {}

        def _handler(req: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(req.content.decode())
            return httpx.Response(200, json={"total": 17})

        patch_httpx(_handler)
        source = _make_source(
            "json_post_path_int",
            {
                "endpoint": "https://api.example.com/search",
                "payload": {"query": "engineer"},
                "value_path": "total",
            },
        )
        count, _ = asyncio.run(JsonPostPathIntAdapter().fetch_job_count(source))

        assert count == 17
        assert captured["body"] == {"query": "engineer"}

    def test_invalid_value_type_raises(self, patch_httpx):
        patch_httpx(lambda req: httpx.Response(200, json={"total": "abc"}))
        source = _make_source(
            "json_post_path_int",
            {
                "endpoint": "https://api.example.com/search",
                "payload": {},
                "value_path": "total",
            },
        )
        with pytest.raises(AdapterError):
            asyncio.run(JsonPostPathIntAdapter().fetch_job_count(source))


# ---------------------------------------------------------------------------
# JsonPostFacetSumAdapter
# ---------------------------------------------------------------------------

class TestJsonPostFacetSumAdapter:
    def test_sums_facet_counts(self, patch_httpx):
        body = {
            "facets": {
                "map": {
                    "country": [
                        {"label": "DE", "count": 100},
                        {"label": "IT", "count": 25},
                        {"label": "US", "count": 7},
                    ]
                }
            }
        }
        patch_httpx(lambda req: httpx.Response(200, json=body))
        source = _make_source(
            "json_post_facet_sum",
            {
                "endpoint": "https://api.example.com/facets",
                "payload": {"page": 0},
                "facet_field": "country",
            },
        )
        count, meta = asyncio.run(JsonPostFacetSumAdapter().fetch_job_count(source))

        assert count == 132
        assert meta["facet_field"] == "country"
        assert meta["items"] == 3

    def test_missing_facet_raises(self, patch_httpx):
        patch_httpx(lambda req: httpx.Response(200, json={"facets": {"map": {}}}))
        source = _make_source(
            "json_post_facet_sum",
            {
                "endpoint": "https://api.example.com/facets",
                "payload": {"page": 0},
                "facet_field": "country",
            },
        )
        with pytest.raises(AdapterError):
            asyncio.run(JsonPostFacetSumAdapter().fetch_job_count(source))


# ---------------------------------------------------------------------------
# StaticTextRegexAdapter
# ---------------------------------------------------------------------------

class TestStaticTextRegexAdapter:
    def test_extracts_count_with_thousands_separator(self, patch_httpx):
        html = "<html><body><h1>1,378 result(s)</h1></body></html>"
        patch_httpx(lambda req: httpx.Response(200, text=html))

        source = _make_source(
            "static_text_regex",
            {"regex_pattern": r"(\d[\d,]*)\s*result\(s\)"},
        )
        count, meta = asyncio.run(StaticTextRegexAdapter().fetch_job_count(source))

        assert count == 1378
        assert meta["pattern"] == r"(\d[\d,]*)\s*result\(s\)"
        assert "1,378" in meta["matched_text"]

    def test_no_match_raises(self, patch_httpx):
        html = "<html><body><h1>No jobs here</h1></body></html>"
        patch_httpx(lambda req: httpx.Response(200, text=html))

        source = _make_source(
            "static_text_regex",
            {"regex_pattern": r"(\d[\d,]*)\s*result\(s\)"},
        )
        with pytest.raises(AdapterError, match="regex did not match"):
            asyncio.run(StaticTextRegexAdapter().fetch_job_count(source))

    def test_missing_regex_pattern_raises(self):
        source = _make_source("static_text_regex", {})
        with pytest.raises(AdapterError, match="missing settings.regex_pattern"):
            asyncio.run(StaticTextRegexAdapter().fetch_job_count(source))
