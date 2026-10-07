"""Score the dashboard union using the already approved risk algorithm."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts

from data_pipeline.active_source import CachedSource
from data_pipeline.tushare_client import normalize_ts_code
from generate_risk_test import ROOT, RULES, FIELDS, build_row
from data_pipeline.listing_risk import listing_risk


def stock_union(folder: Path, scope="all"):
    watch = json.loads((folder / "dashboard.json").read_text(encoding="utf-8"))
    stocks = {r["code"]: {**r, "ts_code": normalize_ts_code(r["code"])}
              for r in watch["adjustments"]["qfq"]["rows"]}
    if scope != "watchlist":
        growth = json.loads((folder / "growth-market-dashboard.json").read_text(encoding="utf-8"))
        small = json.loads((folder / "small-cap-dashboard.json").read_text(encoding="utf-8"))
        other = growth["rows"] + small["rows"] + small["screened"]["rows"]
        if scope == "small-cap":
            stocks = {}
            other = small["rows"] + small["screened"]["rows"]
        stocks.update({r["code"]: {**r, "ts_code": r.get("ts_code") or normalize_ts_code(r["code"])} for r in other})
    for stock in stocks.values():
        # Dashboard sources already carry actual market labels for the pools.
        if "market" not in stock:
            code = stock["code"]
            stock["market"] = "科创板" if code.startswith("688") else "创业板" if code.startswith(("300", "301")) else "主板"
    return sorted(stocks.values(), key=lambda r: r["ts_code"])


def generate(scope="all", workers=2, sample=False):
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    as_of = now.strftime("%Y%m%d")
    stocks = stock_union(ROOT / "public/data", scope)
    stocks = [stock for stock in stocks if not listing_risk(stock, as_of, use_snapshot=True)]
    if sample:
        watch = json.loads((ROOT / "public/data/dashboard.json").read_text(encoding="utf-8"))
        growth = json.loads((ROOT / "public/data/growth-market-dashboard.json").read_text(encoding="utf-8"))
        small = json.loads((ROOT / "public/data/small-cap-dashboard.json").read_text(encoding="utf-8"))
        codes = {r["code"] for r in watch["adjustments"]["qfq"]["rows"][:3] + growth["rows"][:3] + small["screened"]["rows"][:3]}
        codes |= {"688121", "603718"}
        stocks = [s for s in stocks if s["code"] in codes]
    token = os.environ["TUSHARE_TOKEN"]

    def fetch_stock(stock):
        source = CachedSource(ts.pro_api(token), ROOT / ".cache-risk.local", as_of)
        frames, errors = {}, []
        for endpoint, fields in FIELDS.items():
            try:
                frames[endpoint] = source.query(endpoint, ts_code=stock["ts_code"], start_date="20200101", end_date=as_of, fields=fields)
            except RuntimeError:
                frames[endpoint] = pd.DataFrame()
                errors.append({"code": stock["code"], "stage": endpoint, "error": "财报来源暂不可用"})
        try:
            row = build_row(stock, frames, as_of)
            raw_dir = ROOT / "public/data/risk-test-financials"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw = {"ts_code": stock["ts_code"], "fetched_at": now.isoformat(timespec="seconds"), "source": "Tushare",
                   "query": {"start_date": "20200101", "end_date": as_of},
                   "tables": {endpoint: json.loads(frame.to_json(orient="records")) for endpoint, frame in frames.items()}}
            (raw_dir / f"{stock['ts_code']}.json").write_text(json.dumps(raw, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            return stock["code"], row, errors
        except (ValueError, KeyError, AttributeError) as error:
            errors.append({"code": stock["code"], "stage": "financial", "error": "财报缺失或数据不完整"})
            return stock["code"], None, errors

    rows, errors, unavailable = {}, [], {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for i, (code, row, issues) in enumerate(executor.map(fetch_stock, stocks)):
            errors.extend(issues)
            if row:
                rows[code] = row
            else:
                unavailable[code] = issues[-1]["error"]
            if (i+1) % 10 == 0 or i+1 == len(stocks):
                print(f"Dashboard risk {i+1}/{len(stocks)}; scored={len(rows)} unavailable={len(unavailable)}", flush=True)
    if not rows:
        raise RuntimeError("No risk data generated; previous file preserved")
    payload = {"schema_version": 1, "updated_at": now.isoformat(timespec="seconds"), "as_of": as_of,
               "rules": RULES, "scope": scope, "sample": sample, "target_count": len(stocks), "stocks": rows,
               "unavailable": unavailable, "errors": errors,
               "coverage_note": ("当前先展示少量股票样本，其余显示待核实。" if sample else "") + "问询、立案及治理公告未完整扫描，评分为已知风险下限。"}
    # Preserve removed securities as separately auditable exclusions, never as ranked rows.
    previous = ROOT / 'public/data/risk-dashboard.json'
    excluded = {}
    if previous.exists():
        old = json.loads(previous.read_text(encoding='utf-8'))
        for code, record in {**old.get('excluded_stocks', {}), **old.get('stocks', {})}.items():
            if listing_risk(record, as_of, use_snapshot=True) and code not in rows:
                path = ROOT / f"public/data/risk-test-financials/{record['ts_code']}.json"
                if path.exists():
                    raw = json.loads(path.read_text(encoding='utf-8'))
                    excluded[code] = build_row(record, {key: pd.DataFrame(value) for key, value in raw['tables'].items()}, as_of)
    payload['excluded_stocks'] = excluded
    output = ROOT / "public/data/risk-dashboard.json"
    temp = output.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(output)
    print(f"Saved {len(rows)}/{len(stocks)} current risk records", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["all", "watchlist", "small-cap"], default="all")
    parser.add_argument("--workers", type=int, choices=[1, 2], default=2)
    parser.add_argument("--sample", action="store_true", help="Preview only a few stocks from each page")
    args = parser.parse_args()
    generate(args.scope, args.workers, args.sample)
