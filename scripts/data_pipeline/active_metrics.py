"""A-share activity measures; all percentages are percentage points, not ratios."""
from __future__ import annotations

import math
import pandas as pd


def price_history(frame: pd.DataFrame) -> pd.DataFrame:
    bars = frame.copy().sort_values("trade_date").reset_index(drop=True)
    if bars.empty or bars.trade_date.duplicated().any():
        raise ValueError("Empty or duplicate price history")
    for field in ("high", "low", "close"):
        bars[field] = pd.to_numeric(bars[field], errors="raise")
        if not bars[field].map(lambda v: math.isfinite(v) and v > 0).all():
            raise ValueError("Invalid price")
    if ((bars.high < bars.close) | (bars.low > bars.close) | (bars.high < bars.low)).any():
        raise ValueError("Inconsistent OHLC")
    return bars


def activity_metrics(frame: pd.DataFrame) -> dict:
    bars = price_history(frame)
    previous = bars.close.shift(1)
    true_range = pd.concat([bars.high - bars.low, (bars.high - previous).abs(),
                            (bars.low - previous).abs()], axis=1).max(axis=1)
    normalized = 100 * true_range / previous
    returns = 100 * (bars.close / previous - 1)
    result = {}
    for window in (60, 120):
        result[f"avg_range_{window}d_pct"] = (
            float(normalized.tail(window).mean()) if len(bars) >= window + 1 else None)
    result["large_move_60d_pct"] = (
        float((returns.tail(60).abs() >= 3).mean() * 100) if len(bars) >= 61 else None)
    if "amount" in bars and len(bars) >= 60:
        amount = pd.to_numeric(bars.amount.tail(60), errors="coerce")
        valid = amount.map(lambda v: math.isfinite(v) and v >= 0).all()
        # Tushare daily.amount is in thousands of RMB; 100,000 thousands = 1 yi.
        result["avg_amount_60d_yi"] = float(amount.mean() / 100_000) if valid else None
        result["median_amount_60d_yi"] = float(amount.median() / 100_000) if valid else None
    return result


def rank_candidates(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    table = pd.DataFrame(rows)
    # Percentile score is selection only. The visible range column retains an
    # absolute interpretation and is not a percentile or expected return.
    table["activity_score"] = 100 * (
        .50 * table.avg_range_60d_pct.rank(pct=True) +
        .35 * table.avg_range_120d_pct.rank(pct=True) +
        .10 * table.large_move_60d_pct.rank(pct=True) +
        .05 * table.total_market_cap_yi.rank(pct=True, ascending=False))
    return table.sort_values(["activity_score", "total_market_cap_yi", "code"],
                             ascending=[False, True, True]).to_dict("records")


def snapshot_metrics(frame: pd.DataFrame) -> dict:
    bars = price_history(frame)
    if len(bars) < 2:
        raise ValueError("Need previous close")
    close = float(bars.close.iloc[-1])
    latest_year = str(bars.trade_date.iloc[-1])[:4]
    year = bars[bars.trade_date.astype(str).str.startswith(latest_year)]
    ma250 = float(bars.close.tail(250).mean()) if len(bars) >= 250 else None
    high = float(bars.high.tail(252).max()) if len(bars) >= 252 else None
    low = float(bars.low.tail(252).min()) if len(bars) >= 252 else None
    return {"close": round(close, 2), "today_return_pct": (close / float(bars.close.iloc[-2]) - 1) * 100,
            "ytd_return_pct": (close / float(year.close.iloc[0]) - 1) * 100,
            "distance_ma250_pct": (close / ma250 - 1) * 100 if ma250 else None,
            "distance_52w_high_pct": (close / high - 1) * 100 if high else None,
            "distance_52w_low_pct": (close / low - 1) * 100 if low else None,
            "position_52w_pct": (close-low)/(high-low)*100 if high is not None and high > low else None}
