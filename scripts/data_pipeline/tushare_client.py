from __future__ import annotations

from typing import Any

import tushare as ts

from .config import RuntimeConfig, WatchlistItem
from .indicators import build_metrics, merge_name_and_metrics


class TusharePipelineClient:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        ts.set_token(config.tushare_token)

    def build_adjustment_rows(self) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
        rows_by_adjustment = {adjustment: [] for adjustment in self.config.adjustments}
        errors: list[dict[str, str]] = []

        for item in self.config.watchlist:
            for adjustment in self.config.adjustments:
                try:
                    rows_by_adjustment[adjustment].append(self.fetch_row(item, adjustment))
                except Exception as exc:  # noqa: BLE001
                    message = f"{adjustment}: {exc}"
                    errors.append(
                        {
                            "code": item.code,
                            "name": item.name,
                            "error": message,
                        }
                    )

        return rows_by_adjustment, errors

    def fetch_row(self, item: WatchlistItem, adjustment: str) -> dict[str, Any]:
        frame = ts.pro_bar(
            ts_code=normalize_ts_code(item.code),
            adj=None if adjustment == "none" else adjustment,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            fields="ts_code,trade_date,close,pct_chg",
        )
        if frame is None or frame.empty:
            raise ValueError("No daily bars returned from Tushare pro_bar.")

        metrics = build_metrics(frame, self.config.year_start)
        return merge_name_and_metrics(item.code, item.name, metrics)


def normalize_ts_code(code: str) -> str:
    if "." in code:
        return code.upper()
    prefix = code[:1]
    exchange = "SH" if prefix in {"5", "6", "9"} else "SZ"
    return f"{code}.{exchange}"
