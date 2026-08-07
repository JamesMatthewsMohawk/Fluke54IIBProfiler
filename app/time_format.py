"""Display-time formatting of stored UTC timestamps.

Every timestamp is always stored (in the database, in exports' raw
data columns) in UTC -- format_run_date only affects how a run_date is
*shown or labeled* for a human, never what's written to the runs table.
"""
from __future__ import annotations

from datetime import datetime


def format_run_date(run_date_utc: str, use_local_time: bool) -> str:
    """Format a stored UTC ISO 8601 run_date for display.

    Falls back to the raw string unmodified if it can't be parsed (e.g.
    an unexpected format from an older/foreign database), rather than
    raising and breaking a render or export.
    """
    if not use_local_time:
        return run_date_utc
    try:
        dt = datetime.fromisoformat(run_date_utc)
    except ValueError:
        return run_date_utc
    return dt.astimezone().isoformat(timespec="seconds")
