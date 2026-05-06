"""Singleton Chromium pool used by the Playwright-based adapters.

The browser is launched lazily on first use, kept alive between scrapes,
and shut down only when the FastAPI app stops (see ``app.main`` lifespan).
Each scrape gets its own context+page so cookies do not leak between
sources.

Playwright is an **optional dependency** (``backend[playwright]``). If
the package is not installed the import below fails with a clear hint
that points at the install command. The HTTP-only adapters keep working
unchanged in that case because the registry imports the Playwright
adapters lazily (see ``app.providers.jobs.__init__``).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

try:  # pragma: no cover - exercised in CI by the playwright-extra job
    from playwright.async_api import Browser, Playwright, async_playwright
except ImportError as exc:  # pragma: no cover - exercised in unit tests
    raise ImportError(
        "Playwright is not installed. Install the optional extra with "
        "`pip install -e .[playwright]` and run "
        "`python -m playwright install chromium` once."
    ) from exc

if TYPE_CHECKING:
    from playwright.async_api import Page


class PlaywrightPool:
    """Process-local pool that owns a single headless Chromium.

    Acquiring a page yields a fresh context, so adapters do not have to
    worry about cookie / storage leakage. The pool itself is reused so
    we don't pay the ~1s Chromium launch tax per scrape — for a daily
    run with 5 sources that is the difference between 5s and 30s.
    """

    _instance: "PlaywrightPool | None" = None
    _instance_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._launch_lock = asyncio.Lock()

    @classmethod
    async def get_instance(cls) -> "PlaywrightPool":
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = PlaywrightPool()
            return cls._instance

    @classmethod
    async def shutdown(cls) -> None:
        """Close the browser if one was started. Safe to call multiple times."""
        async with cls._instance_lock:
            if cls._instance is not None:
                await cls._instance.close()
                cls._instance = None

    async def _ensure_browser(self) -> Browser:
        # Re-launch transparently if Chromium crashed between scrapes.
        if self._browser is not None and self._browser.is_connected():
            return self._browser

        async with self._launch_lock:
            if self._browser is not None and self._browser.is_connected():
                return self._browser
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            return self._browser

    @asynccontextmanager
    async def acquire_page(self) -> AsyncGenerator["Page", None]:
        browser = await self._ensure_browser()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()

    async def close(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:  # pragma: no cover - best-effort shutdown
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:  # pragma: no cover - best-effort shutdown
                pass
            self._playwright = None


COOKIE_BANNER_SELECTORS: tuple[str, ...] = (
    "button:has-text('Accept')",
    "button:has-text('Akzeptieren')",
    "button:has-text('Accept All')",
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Confirm')",
    "button:has-text('Confirm My Choices')",
    "[data-testid='cookie-accept']",
    "#onetrust-accept-btn-handler",
    ".cookie-accept",
    "button[id*='accept']",
)


async def dismiss_cookie_banner(page: "Page") -> bool:
    """Best-effort consent click. Returns True if a banner was clicked.

    Each selector gets a short visibility check (1s) so we don't burn
    the full timeout budget when the page simply has no banner.
    """
    for selector in COOKIE_BANNER_SELECTORS:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=1000):
                await btn.click()
                await page.wait_for_timeout(1000)
                return True
        except Exception:
            continue
    return False
