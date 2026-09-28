"""Screen profitable, persistently active A shares and generate chart assets."""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts

try:
    from scripts.data_pipeline.active_source import CachedSource, load_market
    from scripts.data_pipeline.active_metrics import activity_metrics, rank_candidates, snapshot_metrics
    from scripts.data_pipeline.active_financials import Ineligible, load_profitability, load_quality
    from scripts.generate_growth_history import build_history
except ModuleNotFoundError:
    from data_pipeline.active_source import CachedSource, load_market
    from data_pipeline.active_metrics import activity_metrics, rank_candidates, snapshot_metrics
    from data_pipeline.active_financials import Ineligible, load_profitability, load_quality
    from generate_growth_history import build_history

ROOT = Path(__file__).resolve().parents[1]
TARGET = 100


def adjusted_history(raw: pd.DataFrame) -> pd.DataFrame:
    bars = raw.sort_values("trade_date").copy().reset_index(drop=True)
    factors = pd.to_numeric(bars.adj_factor, errors="coerce")
    if not factors.map(lambda v: math.isfinite(v) and v > 0).all():
        raise ValueError("Missing adjustment factor")
    for field in ("open", "high", "low", "close"):
        bars[field] = pd.to_numeric(bars[field], errors="raise") * factors / factors.iloc[-1]
    return bars


def market_candidates(basic, market, raw, dates):
    merged = basic.merge(market, on="ts_code", validate="one_to_one")
    a_share = ((merged.ts_code.str.endswith(".SH") & merged.symbol.str.startswith("6")) |
               (merged.ts_code.str.endswith(".SZ") & merged.symbol.str.startswith(("0", "3"))) |
               merged.ts_code.str.endswith(".BJ"))
    merged = merged[merged.market.isin(["主板", "创业板", "科创板", "北交所"]) &
                    a_share & ~merged.name.str.contains("ST|退", case=False, na=True)].copy()
    merged["total_market_cap_yi"] = pd.to_numeric(merged.total_mv, errors="coerce") / 10000
    merged = merged.loc[merged.total_market_cap_yi.map(lambda v: math.isfinite(v) and v > 0).astype(bool)]
    info = merged.set_index("ts_code").to_dict("index")
    rows = []
    rejected = Counter()
    for code, frame in raw.groupby("ts_code"):
        if code not in info:
            continue
        if sorted(frame.trade_date.astype(str).tolist()) != dates or not (frame.vol > 0).all():
            rejected["行情不连续或无成交"] += 1
            continue
        try:
            metrics = activity_metrics(adjusted_history(frame))
            if metrics["avg_amount_60d_yi"] is None or metrics["median_amount_60d_yi"] is None:
                raise ValueError("Invalid amount")
            if metrics["avg_amount_60d_yi"] < .5 or metrics["median_amount_60d_yi"] < .3:
                rejected["成交额不足"] += 1
                continue
            if metrics["avg_range_60d_pct"] < 2 or metrics["avg_range_120d_pct"] < 2:
                rejected["持续波幅不足"] += 1
                continue
            item = info[code]
            rows.append({"ts_code": code, "code": item["symbol"], "name": item["name"],
                         "market": item["market"], "industry": item["industry"] or "未分类",
                         "total_market_cap_yi": float(item["total_market_cap_yi"]), **metrics})
        except ValueError:
            rejected["行情字段无效"] += 1
    return rank_candidates(rows), len(merged), dict(rejected)


def load_long_history(source, code, trade_date):
    start = (pd.Timestamp(trade_date) - pd.DateOffset(years=5)).strftime("%Y%m%d")
    params = {"ts_code": code, "start_date": start, "end_date": trade_date}
    raw = source.all_rows("daily", **params, fields="ts_code,trade_date,open,high,low,close,vol,amount")
    factors = source.all_rows("adj_factor", **params, fields="ts_code,trade_date,adj_factor")
    bars = adjusted_history(raw.merge(factors, on=["ts_code", "trade_date"], how="left", validate="one_to_one"))
    if str(bars.trade_date.iloc[-1]) != trade_date:
        raise ValueError("Stale stock history")
    return bars


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(path)


def main():
    today = datetime.now(ZoneInfo("Asia/Shanghai"))
    as_of = today.strftime("%Y%m%d")
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN")
    source = CachedSource(ts.pro_api(token, timeout=25), ROOT / ".cache-active.local", as_of)
    basic, market, raw, dates = load_market(source, as_of)
    ranked, universe, exclusions = market_candidates(basic, market, raw, dates)
    print(f"Eligible universe {universe}; activity candidates {len(ranked)}", flush=True)
    rows, histories, audit, errors = [], {}, [], []
    trade_date = dates[-1]
    for index, item in enumerate(ranked):
        try:
            financials = load_profitability(source, item["ts_code"], as_of)
            quality = load_quality(source, item["ts_code"], as_of, financials, item["industry"])
            bars = load_long_history(source, item["ts_code"], trade_date)
            check = activity_metrics(bars)
            for field in ("avg_range_60d_pct", "avg_range_120d_pct", "avg_amount_60d_yi"):
                if not math.isclose(check[field], item[field], rel_tol=1e-7, abs_tol=1e-7):
                    raise ValueError("Screen and chart data disagree")
            metrics = snapshot_metrics(bars)
            history = build_history(bars, item["code"], item["name"], trade_date)
            row = {**item, **metrics, "financials": {**financials, **quality},
                   "source_url": "https://www.cninfo.com.cn/new/fulltextSearch?keyWord=" + item["code"]}
            rows.append(row)
            histories[item["code"]] = history
            audit.append({"code": item["code"], "status": "selected"})
            print(f"Selected {len(rows)}/{TARGET}: {item['code']} {item['name']}; reviewed {index+1}", flush=True)
        except Ineligible as exc:
            audit.append({"code": item["code"], "status": "ineligible", "reason": str(exc)})
        except Exception as exc:
            # Never serialize upstream exception text: it may contain API credentials.
            errors.append({"code": item["code"], "stage": "financial/history", "error": type(exc).__name__})
            audit.append({"code": item["code"], "status": "unavailable"})
        if (index + 1) % 20 == 0:
            print(f"Reviewed {index+1}/{len(ranked)}; selected {len(rows)}; errors {len(errors)}", flush=True)
        if len(rows) == TARGET:
            break
    if not rows or (len(errors) > max(5, len(audit) * .1)):
        raise RuntimeError(f"Active data incomplete: {len(rows)} selected, {len(errors)} request/history failures; previous output retained")
    payload = {"schema_version": 1, "updated_at": today.strftime("%Y-%m-%d %H:%M"),
               "trade_date": trade_date, "financial_as_of": as_of, "adjustment": "qfq",
               "summary": {"universe": universe, "activity_candidates": len(ranked), "reviewed": len(audit),
                           "selected": len(rows), "target": TARGET},
               "filters": {"avg_amount_60d_min_yi": .5, "median_amount_60d_min_yi": .3,
                           "avg_range_60d_min_pct": 2, "avg_range_120d_min_pct": 2,
                           "ranking_weights": [50, 35, 10, 5]},
               "market_exclusions": exclusions, "rows": rows, "errors": errors}
    # Stage and serialize everything before replacing any public asset.
    staging = ROOT / ".cache-active.local" / "staging"
    for code, history in histories.items():
        write_json(staging / "history" / f"{code}.json", history)
    write_json(staging / "dashboard.json", payload)
    write_json(staging / "audit.json", {"trade_date": trade_date, "financial_as_of": as_of, "rows": audit})
    output = ROOT / "public/data"
    history_output = output / "active-history" / trade_date
    history_output.mkdir(parents=True, exist_ok=True)
    for code in histories:
        (staging / "history" / f"{code}.json").replace(history_output / f"{code}.json")
    (staging / "audit.json").replace(output / "active-audit.json")
    (staging / "dashboard.json").replace(output / "active-dashboard.json")
    print(f"Finished: {len(rows)} stocks; errors {len(errors)}", flush=True)


if __name__ == "__main__":
    main()
