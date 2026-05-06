"""Career-portal scrape adapters.

The httpx-based adapters are always available. The Playwright-based
adapters are guarded by the ``backend[playwright]`` optional dependency:
if Playwright is missing, the registry simply omits them and the API
returns a clear ``adapter_type not installed`` error instead of crashing
at import time.

That way the default backend install stays slim (no Chromium download),
and operators who actually need the JS-rendered portals opt in with::

    pip install -e .[playwright]
    python -m playwright install chromium
"""
from __future__ import annotations

from app.providers.jobs.base import AdapterError, BaseJobAdapter
from app.providers.jobs.json_get_array_count import JsonGetArrayCountAdapter
from app.providers.jobs.json_get_path_int import JsonGetPathIntAdapter
from app.providers.jobs.json_post_facet_sum import JsonPostFacetSumAdapter
from app.providers.jobs.json_post_path_int import JsonPostPathIntAdapter
from app.providers.jobs.static_html import StaticHtmlAdapter
from app.providers.jobs.static_text_regex import StaticTextRegexAdapter

ADAPTER_REGISTRY: dict[str, type[BaseJobAdapter]] = {
    "static_html": StaticHtmlAdapter,
    "static_text_regex": StaticTextRegexAdapter,
    "json_get_path_int": JsonGetPathIntAdapter,
    "json_get_array_count": JsonGetArrayCountAdapter,
    "json_post_path_int": JsonPostPathIntAdapter,
    "json_post_facet_sum": JsonPostFacetSumAdapter,
}

# Adapter names that require Playwright. Listed even when the import
# below fails so the API can surface a precise "extra not installed"
# error to the user instead of "unknown adapter_type".
PLAYWRIGHT_ADAPTER_NAMES: tuple[str, ...] = (
    "playwright_api_fetch",
    "playwright_css_count",
    "playwright_text_regex",
)

try:
    from app.providers.jobs.playwright_api_fetch import PlaywrightApiFetchAdapter
    from app.providers.jobs.playwright_css_count import PlaywrightCssCountAdapter
    from app.providers.jobs.playwright_text_regex import PlaywrightTextRegexAdapter

    ADAPTER_REGISTRY["playwright_api_fetch"] = PlaywrightApiFetchAdapter
    ADAPTER_REGISTRY["playwright_css_count"] = PlaywrightCssCountAdapter
    ADAPTER_REGISTRY["playwright_text_regex"] = PlaywrightTextRegexAdapter
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def is_playwright_adapter(adapter_type: str) -> bool:
    return adapter_type in PLAYWRIGHT_ADAPTER_NAMES


# Names that are valid configuration values regardless of whether the
# extra is installed. The schema layer uses this so users can edit a
# Playwright source on a backend without Chromium without losing it.
ALL_KNOWN_ADAPTERS: tuple[str, ...] = tuple(ADAPTER_REGISTRY.keys()) + tuple(
    name for name in PLAYWRIGHT_ADAPTER_NAMES if name not in ADAPTER_REGISTRY
)


__all__ = [
    "ADAPTER_REGISTRY",
    "ALL_KNOWN_ADAPTERS",
    "AdapterError",
    "BaseJobAdapter",
    "JsonGetArrayCountAdapter",
    "JsonGetPathIntAdapter",
    "JsonPostFacetSumAdapter",
    "JsonPostPathIntAdapter",
    "PLAYWRIGHT_ADAPTER_NAMES",
    "PLAYWRIGHT_AVAILABLE",
    "StaticHtmlAdapter",
    "StaticTextRegexAdapter",
    "is_playwright_adapter",
]
