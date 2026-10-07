"""Build a screened Shanghai/Shenzhen 100 and an independent all-market 250."""
from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts
try:
    from scripts.data_pipeline.listing_risk import listing_risk
except ModuleNotFoundError:
    from data_pipeline.listing_risk import listing_risk

try:
    from scripts.data_pipeline.business_keywords import business_keywords
except ModuleNotFoundError:
    from data_pipeline.business_keywords import business_keywords

try:
    from scripts.data_pipeline.active_source import CachedSource
    from scripts.data_pipeline.active_financials import reports_as_of
    from scripts.data_pipeline.active_metrics import activity_metrics, snapshot_metrics
    from scripts.generate_active_dashboard import load_long_history, write_json
    from scripts.generate_growth_history import build_history
    from scripts.generate_growth_market_dashboard import get_latest_trade_date, normalize_tushare_text
except ModuleNotFoundError:
    from data_pipeline.active_source import CachedSource
    from data_pipeline.active_financials import reports_as_of
    from data_pipeline.active_metrics import activity_metrics, snapshot_metrics
    from generate_active_dashboard import load_long_history, write_json
    from generate_growth_history import build_history
    from generate_growth_market_dashboard import get_latest_trade_date, normalize_tushare_text

ROOT = Path(__file__).resolve().parents[1]
TARGET = 250


def select_smallest(basic: pd.DataFrame, market: pd.DataFrame, *, include_st=True, include_bj=True, target=TARGET, as_of=None):
    merged = basic.merge(market, on="ts_code", validate="one_to_one")
    a_share = ((merged.ts_code.str.endswith(".SH") & merged.symbol.str.startswith("6")) |
               (merged.ts_code.str.endswith(".SZ") & merged.symbol.str.startswith(("0", "3"))) |
               (merged.ts_code.str.endswith(".BJ") & include_bj))
    merged = merged[a_share].copy()
    merged = merged.loc[[not listing_risk(row, as_of or '99999999', use_snapshot=as_of is not None) for row in merged.to_dict('records')]].copy()
    if not include_st:
        merged = merged[~merged.name.str.contains("ST", case=False, na=False)].copy()
    merged["total_market_cap_yi"] = pd.to_numeric(merged.total_mv, errors="coerce") / 10000
    valid = merged.total_market_cap_yi.map(lambda v: math.isfinite(v) and v > 0)
    eligible = merged.loc[valid].sort_values(["total_market_cap_yi", "symbol"])
    return (eligible if target is None else eligible.head(target)).to_dict("records"), len(eligible)


def assess_losses(frame: pd.DataFrame, as_of: str) -> dict:
    reports = reports_as_of(frame, as_of)
    annual = sorted(p for p in reports if p.endswith("1231") and p < f"{as_of[:4]}0101")
    periods = [f"{y}1231" for y in range(int(annual[-1][:4]) - 2, int(annual[-1][:4]) + 1)] if annual else []

    def profit(period):
        value = reports.get(period, {}).get("n_income_attr_p")
        return float(value) if value is not None and pd.notna(value) and math.isfinite(float(value)) else None

    latest = max(reports) if reports else None
    values = {p: profit(p) for p in periods}
    reasons = [f"{p[:4]}年归母净利润亏损" for p, v in values.items() if v is not None and v < 0]
    if latest and profit(latest) is not None and profit(latest) < 0:
        reasons.append(f"最新财报（{latest}）累计归母净利润亏损")
    complete = len(periods) == 3 and all(v is not None for v in values.values()) and latest is not None and profit(latest) is not None
    return {"annual_periods": periods, "annual_net_profit": values,
            "annual_ann_dates": {p: reports.get(p, {}).get("disclosed_at") for p in periods},
            "latest_report": {"period": latest, "ann_date": reports[latest]["disclosed_at"], "net_profit": profit(latest)} if latest else None,
            "loss_status": "loss" if reasons else "no_loss" if complete else "unknown",
            "financial_complete": complete, "loss_reasons": reasons}


def screen_non_loss(candidates, load_financial, target=100, progress=None):
    selected, audit = [], []
    for item in candidates:
        if listing_risk(item) or item['ts_code'].endswith('.BJ') or 'ST' in str(item.get('name', '')).upper():
            continue
        report = load_financial(item)
        audit.append({"code": str(item['symbol']), "total_market_cap_yi": item['total_market_cap_yi'],
                      "loss_status": report['loss_status'], "financial_complete": report['financial_complete']})
        if report['loss_status'] == 'no_loss' and report['financial_complete']:
            selected.append(item)
        if progress:
            progress(len(audit), len(selected))
        if len(selected) == target:
            break
    return selected, audit


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude-st", action="store_true")
    parser.add_argument("--exclude-bj", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN")
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    as_of = now.strftime("%Y%m%d")
    pro = ts.pro_api(token)
    source = CachedSource(pro, ROOT / ".cache-small-cap.local", as_of)
    trade_date = get_latest_trade_date(pro, now.date())
    basic = source.all_rows("stock_basic", exchange="", list_status="L",
                            fields="ts_code,symbol,name,market,industry,list_date")
    market = source.all_rows("daily_basic", trade_date=trade_date, fields="ts_code,trade_date,close,total_mv")
    candidates, universe = select_smallest(basic, market, include_st=not args.exclude_st, include_bj=not args.exclude_bj, as_of=as_of)
    if len(candidates) != TARGET:
        raise RuntimeError(f"Cannot generate the smallest {TARGET}: incomplete market snapshot")
    business = {}
    errors = []
    for exchange in ("SSE", "SZSE", "BSE"):
        try:
            companies = source.all_rows("stock_company", exchange=exchange, fields="ts_code,main_business")
            business.update({r.ts_code: normalize_tushare_text(str(r.main_business)) if pd.notna(r.main_business) else "" for r in companies.itertuples()})
        except Exception:
            errors.append({"code": exchange, "stage": "business", "error": "主营业务未能获取"})
    rows = []
    financials = {}
    def load_financial(item):
        code = str(item['symbol'])
        if code not in financials:
            try:
                income = source.all_rows("income", ts_code=item["ts_code"], start_date="19900101", end_date=as_of,
                                         fields="ts_code,ann_date,f_ann_date,end_date,report_type,n_income_attr_p,update_flag")
                financials[code] = assess_losses(income, as_of)
            except Exception:
                errors.append({"code": code, "stage": "financial", "error": "财报未能获取"})
                financials[code] = assess_losses(pd.DataFrame(), as_of)
        return financials[code]

    screened_candidates, screened_universe = select_smallest(basic, market, include_st=False, include_bj=False, target=None, as_of=as_of)
    def progress(checked, selected):
        if checked % 10 == 0 or selected == 100:
            print(f"Financial scan: {checked} checked, {selected}/100 selected", flush=True)
    screened, audit = screen_non_loss(screened_candidates, load_financial, progress=progress)
    if len(screened) != 100:
        raise RuntimeError('Cannot verify the smallest 100 non-loss Shanghai/Shenzhen stocks; previous snapshot retained')

    full_codes = {str(item['symbol']) for item in candidates}
    combined = candidates + [item for item in screened if str(item['symbol']) not in full_codes]
    for i, item in enumerate(combined):
        code = str(item["symbol"])
        row = {"code": code, "name": item["name"], "ts_code": item["ts_code"],
               "market": str(item["market"]) if pd.notna(item["market"]) else "",
               "industry": str(item["industry"]) if pd.notna(item["industry"]) else "", "market_cap_rank": i + 1,
               "total_market_cap_yi": item["total_market_cap_yi"], "main_business": business.get(item["ts_code"], ""),
               **{k: None for k in ("close", "today_return_pct", "distance_ma250_pct", "position_52w_pct", "avg_range_60d_pct", "large_move_60d_pct", "avg_amount_60d_yi")},
               **assess_losses(pd.DataFrame(), as_of)}
        row.update(load_financial(item))
        try:
            bars = load_long_history(source, item["ts_code"], trade_date)
            row.update(snapshot_metrics(bars))
            row.update(activity_metrics(bars))
            # A 60-day metric requires 61 observations AND coverage of the latest 60 market sessions.
            calendar = source.query("trade_cal", exchange="SSE", is_open="1",
                                    start_date=(pd.Timestamp(trade_date) - pd.Timedelta(days=150)).strftime("%Y%m%d"),
                                    end_date=trade_date, fields="cal_date")
            sessions = sorted(calendar.cal_date.astype(str))[-61:]
            row["activity_observations"] = len(bars.tail(61)) - 1
            if len(sessions) != 61 or bars.tail(61).trade_date.astype(str).tolist() != sessions:
                for key in ("avg_range_60d_pct", "large_move_60d_pct", "avg_amount_60d_yi"):
                    row[key] = None
                row["activity_note"] = "近60个交易日行情不足或有停牌，暂不比较活跃度"
            else:
                row["large_move_60d_days"] = round(row["large_move_60d_pct"] * 60 / 100)
            history = build_history(bars, code, row["name"], trade_date)
            write_json(ROOT / f"public/data/small-cap-history/{trade_date}/{code}.json", history)
        except Exception:
            errors.append({"code": code, "stage": "history", "error": "行情不足或非最新，指标暂缺"})
        row["main_business_keywords"] = business_keywords(code, row["main_business"])
        rows.append(row)
        print(f"{i + 1}/{len(combined)} {code}: {row['loss_status']}", flush=True)
    by_code = {row['code']: row for row in rows}
    screened_rows = [{**by_code[str(item['symbol'])], 'market_cap_rank': i + 1} for i, item in enumerate(screened)]
    rows = rows[:TARGET]
    payload = {"schema_version": 2, "trade_date": trade_date, "updated_at": now.strftime("%Y-%m-%d %H:%M"),
               "financial_as_of": as_of, "adjustment": "qfq", "filters": {"include_st": not args.exclude_st, "include_bj": not args.exclude_bj, "exclude_delisting": True, "target": TARGET},
               "summary": {"universe": universe, "selected": len(rows)}, "rows": rows,
               "screened": {"target": 100, "include_st": False, "universe": screened_universe, "checked": len(audit), "audit": audit, "rows": screened_rows}}
    if errors:
        payload["errors"] = errors
    write_json(ROOT / "public/data/small-cap-dashboard.json", payload)


if __name__ == "__main__":
    main()
