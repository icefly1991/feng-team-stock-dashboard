from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import tushare as ts

from .config import RuntimeConfig, WatchlistItem
from .indicators import build_metrics, merge_name_and_metrics


@dataclass(frozen=True)
class PipelineRunResult:
    rows_by_adjustment: dict[str, list[dict[str, Any]]]
    errors: list[dict[str, str]]
    latest_trade_date: str | None
    successful_stocks: int
    failed_stocks: int


class TusharePipelineClient:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        ts.set_token(config.tushare_token)
        self.pro = ts.pro_api()

    def build_adjustment_rows(self) -> PipelineRunResult:
        rows_by_adjustment = {adjustment: [] for adjustment in self.config.adjustments}
        errors: list[dict[str, str]] = []
        latest_trade_date: str | None = None
        successful_stocks = 0
        failed_stocks = 0

        for item in self.config.watchlist:
            stock_failed = False
            for adjustment in self.config.adjustments:
                try:
                    row, trade_date = self.fetch_row(item, adjustment)
                    rows_by_adjustment[adjustment].append(row)
                    latest_trade_date = max_known_trade_date(latest_trade_date, trade_date)
                except Exception as exc:  # noqa: BLE001
                    stock_failed = True
                    message = f"{adjustment}: {exc}"
                    errors.append(
                        {
                            "code": item.code,
                            "name": item.name,
                            "error": message,
                        }
                    )

            if stock_failed:
                failed_stocks += 1
            else:
                successful_stocks += 1

        return PipelineRunResult(
            rows_by_adjustment=rows_by_adjustment,
            errors=errors,
            latest_trade_date=latest_trade_date,
            successful_stocks=successful_stocks,
            failed_stocks=failed_stocks,
        )

    def fetch_row(self, item: WatchlistItem, adjustment: str) -> tuple[dict[str, Any], str]:
        frame = ts.pro_bar(
            ts_code=normalize_ts_code(item.code),
            adj=None if adjustment == "none" else adjustment,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            fields="ts_code,trade_date,close,high,pct_chg",
        )
        if frame is None or frame.empty:
            raise ValueError("No daily bars returned from Tushare pro_bar.")

        metrics = build_metrics(frame, self.config.year_start)
        trade_date = str(frame["trade_date"].astype(str).max())
        return merge_name_and_metrics(item.code, item.name, metrics), trade_date

    def get_latest_market_trade_date(self) -> str | None:
        try:
            calendar = self.pro.trade_cal(
                exchange="SSE",
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                is_open="1",
                fields="cal_date",
            )
        except Exception:  # noqa: BLE001
            return None

        if calendar is None or calendar.empty:
            return None
        return str(calendar["cal_date"].astype(str).max())


def normalize_ts_code(code: str) -> str:
    if "." in code:
        return code.upper()
    prefix = code[:1]
    exchange = "SH" if prefix in {"5", "6", "9"} else "SZ"
    return f"{code}.{exchange}"


def max_known_trade_date(current: str | None, candidate: str | None) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    return max(current, candidate)
