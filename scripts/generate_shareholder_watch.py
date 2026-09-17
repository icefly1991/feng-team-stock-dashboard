"""Match a sourced, editable name watchlist against disclosed float-holder snapshots."""
from __future__ import annotations

import json
import math
import os
import time
import unicodedata
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


def normalized_name(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", str(value)).split())


def snapshot(frame: pd.DataFrame, period: str) -> dict:
    rows = frame[frame.end_date == period]
    announcement = rows.ann_date.max()
    rows = rows[rows.ann_date == announcement]
    holders = {}
    for row in rows.itertuples():
        name = normalized_name(row.holder_name)
        amount = float(row.hold_amount)
        if not name or name == "nan" or not math.isfinite(amount) or amount <= 0:
            raise ValueError("Invalid holder")
        ratio = getattr(row, "hold_float_ratio", None)
        ratio = float(ratio) if ratio is not None and pd.notna(ratio) else None
        if ratio is not None and (not math.isfinite(ratio) or not 0 <= ratio <= 100):
            raise ValueError("Invalid float ratio")
        holder = {"name": name, "shares": amount, "float_ratio_pct": ratio}
        if name in holders and holders[name] != holder:
            raise ValueError("Conflicting duplicate holder")
        holders[name] = holder
    return {"period": period, "ann_date": announcement, "complete": len(holders) == 10,
            "holders": sorted(holders.values(), key=lambda h: (-h["shares"], h["name"]))}


def build_stock(frame: pd.DataFrame, names: set[str], as_of: str) -> dict:
    if frame is None or frame.empty:
        return {"status": "unavailable", "reason": "未取得已披露股东数据", "matches": []}
    frame = frame.copy()
    for field in ["ann_date", "end_date"]:
        frame[field] = frame[field].astype(str)
        if not frame[field].str.fullmatch(r"\d{8}").all():
            raise ValueError("Invalid date")
        pd.to_datetime(frame[field], format="%Y%m%d", errors="raise")
    frame = frame[(frame.ann_date <= as_of) & (frame.end_date <= frame.ann_date)]
    periods = sorted(frame.end_date.unique(), reverse=True)
    if not periods:
        return {"status": "unavailable", "reason": "未取得已披露股东数据", "matches": []}
    current = snapshot(frame, periods[0])
    previous = snapshot(frame, periods[1]) if len(periods) > 1 else None
    now = {h["name"]: h for h in current["holders"]}
    before = {h["name"]: h for h in previous["holders"]} if previous else {}
    matches = []
    for name in sorted(names & (now.keys() | before.keys())):
        if name in now:
            state = "continuing" if name in before else "new" if previous and previous["complete"] else "unknown"
        elif current["complete"]:
            state = "exit"
        else:
            # Absence in a partial snapshot is not evidence of an exit.
            continue
        matches.append({"name": name, "state": state, "current": now.get(name), "previous": before.get(name)})
    return {"status": "ok" if current["complete"] else "partial", "current": current,
            "previous": previous, "matches": matches}


def generate() -> None:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN")
    roster = json.loads((ROOT / "config/investor-watchlist.json").read_text(encoding="utf-8"))
    names = {normalized_name(p["name"]) for p in roster["investors"]}
    if len(names) != len(roster["investors"]) or not names:
        raise ValueError("Duplicate or empty watchlist")
    for investor in roster["investors"]:
        if not investor["sources"] or any(s not in roster["sources"] for s in investor["sources"]):
            raise ValueError("Missing source")
    folder = ROOT / "public/data"
    main = json.loads((folder / "dashboard.json").read_text(encoding="utf-8"))
    growth = json.loads((folder / "growth-market-dashboard.json").read_text(encoding="utf-8"))
    stocks = {row["code"]: row["name"] for row in main["adjustments"]["qfq"]["rows"] + growth["rows"]}
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    as_of = now.strftime("%Y%m%d")
    start = (pd.Timestamp(as_of) - pd.DateOffset(years=2)).strftime("%Y%m%d")
    payload = {"schema_version": 1, "as_of": as_of, "updated_at": now.isoformat(timespec="seconds"),
               "source": "Tushare top10_floatholders", "source_url": "https://tushare.pro/document/2?doc_id=62",
               "roster": roster, "stocks": {}}
    pro = ts.pro_api(token)
    errors = 0
    for index, (code, name) in enumerate(sorted(stocks.items())):
        result = None
        for attempt in range(3):
            try:
                time.sleep(0.65 + attempt)
                frame = pro.top10_floatholders(ts_code=normalize_ts_code(code), start_date=start, end_date=as_of)
                result = build_stock(frame, names, as_of)
                break
            except Exception as exc:
                print(f"{code} attempt {attempt + 1}: {type(exc).__name__}", flush=True)
        if result is None:
            errors += 1
            result = {"status": "unavailable", "reason": "本次查询失败，请等待下次更新", "matches": []}
        payload["stocks"][code] = {"name": name, **result}
        print(f"{index + 1}/{len(stocks)} {code}: {result['status']} matches={len(result['matches'])}", flush=True)
    target = folder / "shareholder-watch.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(target)
    print(f"Completed {len(stocks)} stocks; failed queries: {errors}")


if __name__ == "__main__":
    generate()
