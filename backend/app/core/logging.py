"""Structured logging setup and request-id propagation.

The goal is to make every log line emitted during a request carry the same
`request_id`, so a user-visible 500 can be traced through service +
provider logs without grepping by timestamps. The id flows like this:

1. `RequestIDMiddleware` (see `app.core.middleware`) reads the inbound
   `X-Request-ID` header or generates a fresh UUID, stores it in the
   `_request_id_var` contextvar, and echoes it back in the response.
2. `_RequestIDFilter` injects the current value into every log record so
   the format string can reference `%(request_id)s`.
3. Background work (e.g. the refresh runner) is not request-scoped, so
   the filter falls back to `-` for those entries.

`configure_logging()` is called once on FastAPI startup; it is safe to
call repeatedly — the filter is only attached once per handler.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar

# Public so middleware + tests can read/write the active id.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str) -> object:
    """Set the active request id. Returns the token for `reset_request_id`."""
    return _request_id_var.set(request_id)


def reset_request_id(token: object) -> None:
    _request_id_var.reset(token)  # type: ignore[arg-type]


class _RequestIDFilter(logging.Filter):
    """Inject the active `request_id` contextvar into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


_LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s"


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.addFilter(_RequestIDFilter())

    root = logging.getLogger()
    # Replace any handlers from a previous call (e.g. when uvicorn reloads)
    # so we don't double-log and so the formatter is guaranteed to include
    # the request_id placeholder.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
