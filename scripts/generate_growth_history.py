"""Generate on-demand chart assets from a single five-year qfq price series."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts

try:
    from scripts.data_pipeline.tushare_client import normalize_ts_code
except ModuleNotFoundError:
    from data_pipeline.tushare_client import normalize_ts_code

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public/data/growth-history"


def build_history(frame: pd.DataFrame, code: str, name: str, trade_date: str, adjustment: str = "qfq") -> dict:
    if adjustment not in {"qfq", "none"}:
        raise ValueError("Unsupported adjustment")
    end = pd.Timestamp(trade_date)
    start = end - pd.DateOffset(years=5)
    if frame is None or frame.empty:
        raise ValueError("No historical bars returned")
    bars = frame.copy()
    bars["date"] = pd.to_datetime(bars["trade_date"], format="%Y%m%d", errors="raise")
    bars = bars[(bars["date"] >= start) & (bars["date"] <= end)].sort_values("date")
    if bars.empty or bars["date"].duplicated().any():
        raise ValueError("Empty or duplicate historical dates")
    for field in ["open", "high", "low", "close", "vol"]:
        bars[field] = pd.to_numeric(bars[field], errors="raise")
        if not bars[field].map(math.isfinite).all():
            raise ValueError(f"Invalid {field}")
    if ((bars[["open", "high", "low", "close"]] <= 0).any().any()
        or (bars["vol"] < 0).any()
        or (bars["high"] < bars[["open", "close", "low"]].max(axis=1)).any()
        or (bars["low"] > bars[["open", "close", "high"]].min(axis=1)).any()):
        raise ValueError("Invalid OHLC or volume")

    def pack(row) -> dict:
        return {"time": row.date.strftime("%Y-%m-%d"),
                **{k: round(float(getattr(row, k)), 6) for k in ["open", "high", "low", "close"]},
                "volume": round(float(row.vol), 2)}

    daily = [pack(row) for row in bars.itertuples()]
    # W-FRI assigns Monday-Friday sessions to the same week, including holidays.
    weekly = bars.groupby(bars["date"].dt.to_period("W-FRI")).agg(
        date=("date", "first"), open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"), vol=("vol", "sum"))
    high, low, close = float(bars.high.max()), float(bars.low.min()), float(bars.close.iloc[-1])
    return {
        "code": code, "name": name, "trade_date": trade_date, "adjustment": adjustment,
        "updated_at": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M"),
        "requested_start": start.strftime("%Y-%m-%d"), "actual_start": daily[0]["time"],
        "actual_end": daily[-1]["time"], "volume_unit": "手",
        "daily": daily, "weekly": [pack(row) for row in weekly.itertuples()],
        "metrics": {"high": high, "low": low, "close": close,
                    "position_pct": (close - low) / (high - low) * 100 if high != low else None,
                    "distance_high_pct": (close / high - 1) * 100},
    }


def generate(source: str = "growth") -> None:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN")
    filename = "dashboard.json" if source == "watchlist" else "growth-market-dashboard.json"
    dashboard = json.loads((ROOT / "public/data" / filename).read_text(encoding="utf-8"))
    trade_date = dashboard["trade_date"]
    start = (pd.Timestamp(trade_date) - pd.DateOffset(years=5)).strftime("%Y%m%d")
    pro = ts.pro_api(token)
    jobs = [(row, "qfq", OUTPUT) for row in dashboard.get("rows", [])]
    if source == "watchlist":
        jobs = [(row, adj, ROOT / "public/data/watchlist-history" / adj)
                for adj in ("qfq", "none") for row in dashboard["adjustments"][adj]["rows"]]
    failures = []
    for i, (row, adjustment, output) in enumerate(jobs):
        code = row["code"]
        try:
            time.sleep(0.4)
            frame = ts.pro_bar(ts_code=normalize_ts_code(code),
                               api=pro, adj=None if adjustment == "none" else adjustment, start_date=start, end_date=trade_date,
                               fields="ts_code,trade_date,open,high,low,close,vol")
            payload = build_history(frame, code, row["name"], trade_date, adjustment)
            if abs(payload["metrics"]["close"] - row["close"]) > 0.011:
                raise ValueError("Latest history close does not match dashboard")
            output.mkdir(parents=True, exist_ok=True)
            path = output / f"{code}.json"
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
            temp.replace(path)
            print(f"{i + 1}/{len(jobs)} {code} {adjustment}: {len(payload['daily'])} daily / {len(payload['weekly'])} weekly", flush=True)
        except Exception as exc:
            # Do not expose API request details (which can contain credentials).
            failures.append(f"{code}:{adjustment}")
            print(f"{code}: history unavailable ({type(exc).__name__}); previous file retained", flush=True)
    if failures:
        raise RuntimeError(f"History generation failed for {len(failures)} stocks: {','.join(failures)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("growth", "watchlist"), default="growth")
    generate(parser.parse_args().source)
