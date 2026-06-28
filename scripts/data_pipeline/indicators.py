from __future__ import annotations

from typing import Any

import pandas as pd


def build_metrics(frame: pd.DataFrame, year_start: str) -> dict[str, float]:
    ordered = normalize_history(frame)
    current_year = first_rows_of_year(ordered, year_start)
    latest = ordered.iloc[-1]
    previous = ordered.iloc[-2] if len(ordered) > 1 else None

    close = float(latest["close"])
    today_return_pct = compute_today_return_pct(latest, close, previous)
    # See docs/metric-definitions.md: MA250 uses the latest 250 trading rows for the
    # current adjustment series, and qfq/none are calculated independently upstream.
    ma250 = ordered["close"].tail(250).mean()
    year_start_close = float(current_year.iloc[0]["close"])
    # See docs/metric-definitions.md: 52-week high is the max intraday high over the
    # latest 252 trading rows for the same adjustment series, not the full history.
    high_52w = float(ordered["high"].tail(252).max())

    return {
        "close": round(close, 2),
        "today_return_pct": round(today_return_pct, 2),
        "distance_ma250_pct": round(percent_change(close, ma250), 2),
        "ytd_return_pct": round(percent_change(close, year_start_close), 2),
        "distance_52w_high_pct": round(percent_change(close, high_52w), 2),
    }


def normalize_history(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("No history returned from Tushare.")

    ordered = frame.copy()
    ordered["trade_date"] = ordered["trade_date"].astype(str)
    ordered["close"] = ordered["close"].astype(float)
    ordered["high"] = ordered["high"].astype(float)
    ordered = ordered.sort_values("trade_date").reset_index(drop=True)

    if len(ordered) < 252:
        raise ValueError("Not enough history to calculate MA250 and 52-week high metrics.")

    return ordered


def compute_today_return_pct(latest: pd.Series, close: float, previous: pd.Series | None) -> float:
    pct_chg = latest.get("pct_chg")
    if pd.notna(pct_chg):
        return float(pct_chg)
    if previous is None:
        raise ValueError("Missing previous close and pct_chg for latest row.")
    # See docs/metric-definitions.md: fall back to previous trading day's close when
    # pct_chg is unavailable for the current adjustment series.
    previous_close = float(previous["close"])
    return percent_change(close, previous_close)


def percent_change(current: float, base: float) -> float:
    if base == 0:
        raise ValueError("Cannot compute percent change with zero base.")
    return (current / base - 1) * 100


def first_rows_of_year(frame: pd.DataFrame, year_start: str) -> pd.DataFrame:
    filtered = frame[frame["trade_date"] >= year_start]
    if filtered.empty:
        raise ValueError("No trading rows found in the current year.")
    return filtered


def merge_name_and_metrics(code: str, name: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {"code": code, "name": name, **metrics}
