"""Shared timezone-aware UTC clock for persisted timestamps."""
from datetime import datetime, timezone


def utc_now():
    """Return an aware UTC datetime; database columns should use timezone=True."""
    return datetime.now(timezone.utc)
