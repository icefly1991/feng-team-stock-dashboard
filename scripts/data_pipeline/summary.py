from __future__ import annotations

from datetime import datetime
from typing import Any


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "watchlist_total": len(rows),
        "today_up": sum(1 for row in rows if row["today_return_pct"] > 0),
        "today_down": sum(1 for row in rows if row["today_return_pct"] < 0),
    }


def build_dashboard_payload(
    rows_by_adjustment: dict[str, list[dict[str, Any]]],
    errors: list[dict[str, str]],
    updated_at: str | None = None,
) -> dict[str, Any]:
    payload = {
        "updated_at": updated_at or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "adjustments": {
            key: {"summary": summarize_rows(rows), "rows": rows}
            for key, rows in rows_by_adjustment.items()
        },
    }
    if errors:
        payload["errors"] = errors
    return payload
