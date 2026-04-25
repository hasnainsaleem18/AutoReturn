"""Timezone helpers for Calendar integration."""

from __future__ import annotations

import os
from zoneinfo import available_timezones

try:
    from tzlocal import get_localzone_name
except Exception:  # pragma: no cover
    get_localzone_name = None


_TZ_ABBREV_MAP = {
    "UTC": "UTC",
    "GMT": "UTC",
    "PKT": "Asia/Karachi",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "EST": "America/New_York",
    "EDT": "America/New_York",
}


def get_local_timezone_name(default: str = "UTC") -> str:
    """Return a best-effort IANA timezone name for the system."""
    # Prefer tzlocal if available
    if get_localzone_name:
        try:
            name = get_localzone_name()
            if name in available_timezones():
                return name
        except Exception:
            pass

    # Check TZ environment variable
    tz_env = os.environ.get("TZ")
    if tz_env and tz_env in available_timezones():
        return tz_env

    return default


def normalize_timezone(tz_name: str | None, default: str = "UTC") -> str:
    """Normalize timezone into an IANA name supported by Google Calendar."""
    if not tz_name:
        return get_local_timezone_name(default)

    if tz_name in available_timezones():
        return tz_name

    # Map common abbreviations
    if tz_name in _TZ_ABBREV_MAP:
        return _TZ_ABBREV_MAP[tz_name]

    return default
