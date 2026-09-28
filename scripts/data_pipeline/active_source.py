"""Rate-limited, credential-free on-disk response cache for the active pool."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd


class CachedSource:
    def __init__(self, pro, root: Path, as_of: str):
        self.pro, self.root, self.as_of = pro, root, as_of
        self.last_call = 0.0

    def query(self, endpoint: str, *, immutable=False, **params) -> pd.DataFrame:
        key = json.dumps([endpoint, params, None if immutable else self.as_of], sort_keys=True)
        path = self.root / endpoint / (hashlib.sha256(key.encode()).hexdigest() + ".json")
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            return pd.DataFrame(value["rows"], columns=value["columns"])
        for attempt in range(3):
            time.sleep(max(0, .36 - (time.monotonic() - self.last_call)))
            self.last_call = time.monotonic()
            try:
                frame = getattr(self.pro, endpoint)(**params)
                if frame is None:
                    raise ValueError("Empty API response")
                break
            except Exception:
                if attempt == 2:
                    # API exceptions may embed request credentials.
                    raise RuntimeError(f"{endpoint} unavailable after 3 attempts") from None
                time.sleep(2 * (attempt + 1))
        if not frame.empty:
            path.parent.mkdir(parents=True, exist_ok=True)
            value = {"columns": frame.columns.tolist(), "rows": json.loads(frame.to_json(orient="records"))}
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            temp.replace(path)
        return frame

    def all_rows(self, endpoint: str, **params) -> pd.DataFrame:
        frames = []
        offset = 0
        while True:
            page = self.query(endpoint, limit=4000, offset=offset, **params)
            frames.append(page)
            if len(page) < 4000:
                break
            offset += len(page)
            if offset > 30000:
                raise RuntimeError("Unexpected pagination size")
        return pd.concat(frames, ignore_index=True)


def load_market(source: CachedSource, as_of: str):
    end = pd.Timestamp(as_of)
    calendar = source.query("trade_cal", exchange="SSE", is_open="1",
                            start_date=(end - pd.Timedelta(days=240)).strftime("%Y%m%d"),
                            end_date=as_of, fields="cal_date")
    dates = sorted(calendar.cal_date.astype(str).tolist())
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if as_of == now.strftime("%Y%m%d") and now.hour < 17:
        dates = [day for day in dates if day < as_of]
    # Use the latest open session. Do not silently fall back to a stale snapshot.
    dates = dates[-121:]
    if len(dates) != 121:
        raise RuntimeError("Need 121 market trading dates")
    basic = source.all_rows("stock_basic", exchange="", list_status="L",
                            fields="ts_code,symbol,name,market,industry,list_date")
    market = source.all_rows("daily_basic", trade_date=dates[-1],
                             fields="ts_code,trade_date,total_mv")
    if basic.empty or market.empty:
        raise RuntimeError("Latest market snapshot unavailable")
    frames = []
    for index, day in enumerate(dates):
        daily = source.all_rows("daily", trade_date=day,
                                fields="ts_code,trade_date,open,high,low,close,vol,amount")
        factors = source.all_rows("adj_factor", trade_date=day, fields="ts_code,trade_date,adj_factor")
        if daily.empty or factors.empty or daily.ts_code.duplicated().any() or factors.ts_code.duplicated().any():
            raise RuntimeError(f"Incomplete market response at {day}")
        joined = daily.merge(factors, on=["ts_code", "trade_date"], how="left", validate="one_to_one")
        frames.append(joined)
        if index % 10 == 0 or index == 120:
            print(f"Market history {index + 1}/121: {day}", flush=True)
    return basic, market, pd.concat(frames, ignore_index=True), dates
