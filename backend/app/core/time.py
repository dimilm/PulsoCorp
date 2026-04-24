"""Single source of truth for "now" in UTC.

`datetime.utcnow()` is deprecated since Python 3.12 (scheduled for removal),
but the database columns and existing comparisons throughout the codebase
expect naive datetimes. We standardise on a tiny helper that returns the
naive UTC representation without using the deprecated API, so there's exactly
one place to revisit when we eventually move to timezone-aware columns.
"""
from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a *naive* `datetime`.

    Equivalent to the legacy `datetime.utcnow()` but built on the
    timezone-aware `datetime.now(UTC)` so it survives the removal of
    `utcnow` in future Python versions.
    """
    return datetime.now(UTC).replace(tzinfo=None)
