"""Dedicated background worker for the stock-refresh pipeline.

Why a separate event loop?
    The refresh pipeline is long-running (network I/O for every stock plus an
    optional AI call) and used to be scheduled via `asyncio.create_task` from
    inside FastAPI request handlers and APScheduler's worker thread. Both
    paths shared the HTTP event loop, which meant:

    * an in-flight refresh slowed every other request because the loop was
      busy iterating over hundreds of stocks, and
    * APScheduler had to call `asyncio.run(...)` on its own thread, creating
      and tearing down a fresh loop on every cron tick.

    Moving the work onto a single, long-lived thread with its own event loop
    isolates the pipeline from the HTTP loop and gives us one canonical place
    to enforce concurrency (one refresh at a time).
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RefreshWorker:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._run, name="refresh-worker", daemon=True
            )
            self._thread.start()
            self._ready.wait(timeout=5)
            if not self._loop:
                raise RuntimeError("refresh worker failed to start")

    def stop(self) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            self._loop = None
            self._thread = None
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread and thread.is_alive():
            thread.join(timeout=5)

    def submit(self, coro_factory: Callable[[], Awaitable[T]]) -> "asyncio.Future[T]":
        """Schedule `coro_factory()` on the worker loop and return a future.

        We accept a factory rather than a coroutine so the coroutine itself is
        created on the worker thread. That avoids "coroutine was never
        awaited" warnings if the worker is restarted between submission and
        execution.
        """
        if not self._loop or not self._loop.is_running():
            self.start()
        assert self._loop is not None
        return asyncio.run_coroutine_threadsafe(_invoke(coro_factory), self._loop)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()


async def _invoke(factory: Callable[[], Awaitable[T]]) -> T:
    return await factory()


# Module-level singleton. Imported by main.py (lifespan) and the scheduler.
worker = RefreshWorker()
