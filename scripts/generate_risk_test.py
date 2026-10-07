"""Generate a review-only risk page from real financial data and verified events.

Usage: .python311/python.exe scripts/generate_risk_test.py [--sample-size 12]
Announcements are manually verified samples, NOT an exhaustive feed.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts

from data_pipeline.active_source import CachedSource
from data_pipeline.active_financials import reports_as_of, ttm, number, Ineligible
from data_pipeline.risk_score import score_risk
from data_pipeline.listing_risk import listing_risk

ROOT = Path(__file__).resolve().parents[1]
RULES = json.loads((ROOT / "config/risk-score-rules.json").read_text(encoding="utf-8"))
EVENTS = json.loads((ROOT / "config/risk-test-events.json").read_text(encoding="utf-8"))
FIELDS = {
    "income": "ts_code,ann_date,f_ann_date,end_date,report_type,update_flag,revenue,total_profit,n_income_attr_p,ebit,fin_exp_int_exp",
    "balancesheet": "ts_code,ann_date,f_ann_date,end_date,report_type,update_flag,total_hldr_eqy_exc_min_int,goodwill,accounts_receiv,oth_receiv,money_cap,st_borr,non_cur_liab_due_1y",
    "cashflow": "ts_code,ann_date,f_ann_date,end_date,report_type,update_flag,n_cashflow_act",
    "fina_indicator": "ts_code,ann_date,end_date,profit_dedt,ebit",
    "fina_audit": "ts_code,ann_date,end_date,audit_result,audit_agency"
}


def safe(fn):
    try:
        v = fn()
        return float(v) if math.isfinite(float(v)) else None
    except (Ineligible, TypeError, ValueError, ZeroDivisionError, KeyError):
        return None


def divide(a, b):
    return None if a is None or b is None or b <= 0 else a / b


def consecutive(reports, annual, field):
    count = 0
    for i in range(3):
        v = safe(lambda: number(reports, f"{int(annual[:4])-i}1231", field))
        if v is None:
            return None
        if v >= 0:
            return count
        count += 1
    return count


def indicator_reports_as_of(frame, as_of):
    if frame.empty:
        return {}
    # Vendor sometimes repeats an identical period/disclosure with an empty
    # derivative row. Prefer the populated record only within the SAME version.
    rows = frame.copy()
    rows["filled"] = rows[[f for f in ("profit_dedt", "ebit") if f in rows]].notna().sum(axis=1)
    rows = rows.sort_values("filled", kind="stable").drop_duplicates(["end_date", "ann_date"], keep="last")
    return reports_as_of(rows, as_of, consolidated=False)


def extract(frames, market, as_of):
    income, balance, cash = [reports_as_of(frames[e], as_of) for e in ("income", "balancesheet", "cashflow")]
    indicator = indicator_reports_as_of(frames["fina_indicator"], as_of)
    periods = sorted(set(income) | set(balance) | set(cash) | set(indicator))
    if not periods:
        raise ValueError("没有在截止日前披露的财报")
    latest = periods[-1]
    annuals = sorted(p for p in income if p.endswith("1231"))
    if not annuals:
        raise ValueError("缺少年度报表")
    annual = annuals[-1]
    previous = f"{int(latest[:4])-1}{latest[4:]}"
    threshold = next((r["revenue_yuan"] for r in reversed(RULES["thresholds"])
                      if r["market"] == market and r["effective_from"] <= as_of), None)
    val = lambda reports, period, field: safe(lambda: number(reports, period, field))
    trailing = lambda reports, period, field: safe(lambda: ttm(reports, period, field))
    equity = val(balance, latest, "total_hldr_eqy_exc_min_int")
    equity_previous = val(balance, previous, "total_hldr_eqy_exc_min_int")
    revenue = trailing(income, latest, "revenue")
    deducted = trailing(indicator, latest, "profit_dedt")
    total_profit = trailing(income, latest, "total_profit")
    net_profit = trailing(income, latest, "n_income_attr_p")
    min_profit = min(total_profit, net_profit, deducted) if all(v is not None for v in (total_profit, net_profit, deducted)) else None
    annual_revenue = val(income, annual, "revenue")
    annual_profits = [val(income, annual, "total_profit"), val(income, annual, "n_income_attr_p"), val(indicator, annual, "profit_dedt")]
    # Tushare lacks adjusted annual revenue. Raw revenue below threshold suffices
    # as adjusted revenue cannot be higher; above threshold cannot clear this rule.
    annual_st = (True if any(v is not None and v < 0 for v in annual_profits) and
                 annual_revenue is not None and threshold and annual_revenue < threshold else
                 False if all(v is not None for v in annual_profits) and min(annual_profits) >= 0 else None)
    ar = val(balance, latest, "accounts_receiv")
    ar_prior = val(balance, previous, "accounts_receiv")
    # Compare same-period year-over-year receivables with same-period YTD revenue.
    revenue_ytd = val(income, latest, "revenue")
    revenue_prior = val(income, previous, "revenue")
    ar_delta = divide(ar, ar_prior)
    rev_delta = divide(revenue_ytd, revenue_prior)
    years = [f"{int(annual[:4])-i}1231" for i in range(3)]
    cfos = [val(cash, p, "n_cashflow_act") for p in years]
    profits = [val(income, p, "n_income_attr_p") for p in years]
    conversion = divide(sum(cfos), sum(profits)) if all(v is not None for v in cfos + profits) else None
    short_debt = [val(balance, latest, f) for f in ("st_borr", "non_cur_liab_due_1y")]
    debt = sum(short_debt) if all(v is not None for v in short_debt) else None
    interest = trailing(income, latest, "fin_exp_int_exp")
    ebit = trailing(income, latest, "ebit")
    if ebit is None:
        ebit = trailing(indicator, latest, "ebit")
    metrics = {
        "deducted_net_profit": deducted, "consecutive_loss_years": consecutive(indicator, annual, "profit_dedt"),
        "revenue_to_st_threshold": divide(revenue, threshold), "lowest_profit_metric": min_profit,
        "net_asset_growth": (equity / equity_previous - 1) * 100 if equity is not None and equity_previous is not None and equity_previous > 0 else None,
        "negative_net_assets": equity < 0 if equity is not None else None,
        "goodwill_to_equity": divide(val(balance, latest, "goodwill"), equity),
        "cfo_negative_years": consecutive(cash, annual, "n_cashflow_act"), "cash_conversion_3y": conversion,
        "ar_growth_minus_revenue_growth": (ar_delta - rev_delta) * 100 if ar_delta is not None and rev_delta is not None else None,
        "ar_to_revenue": divide(ar, revenue), "ar_ratio_abnormal": None,
        "other_receivables_to_equity": divide(val(balance, latest, "oth_receiv"), equity),
        "cash_to_short_debt": divide(val(balance, latest, "money_cap"), debt),
        "interest_coverage": divide(ebit, interest), "annual_st_trigger": annual_st,
        "annual_report_inquiry": None, "inquiry_severity": None, "second_inquiry": None,
        "audit_opinion": None, "internal_control_opinion": None, "csrc_or_governance_event": None,
        "profit_loss_known": any(v is not None and v < 0 for v in (total_profit, net_profit, deducted)),
    }
    # Zero debt/interest means no obligation rather than a division-by-zero risk.
    metrics["no_short_debt"] = debt == 0 if debt is not None else None
    metrics["no_interest_expense"] = interest == 0 if interest is not None else None
    latest_disclosed = max(r[latest]["disclosed_at"] for r in (income, balance, cash, indicator) if latest in r)
    annual_disclosed = max(r.get(annual, {}).get("disclosed_at", "") for r in (income, cash, indicator))
    metric_dates = {key: latest_disclosed for key in metrics}
    for key in ("consecutive_loss_years", "cfo_negative_years", "cash_conversion_3y", "annual_st_trigger"):
        metric_dates[key] = annual_disclosed
    context = {"period": latest, "annual_period": annual, "ann_date": latest_disclosed, "metric_dates": metric_dates,
               "revenue_ttm": revenue, "revenue_threshold": threshold, "annual_revenue": annual_revenue,
               "net_assets": equity, "ar_net": ar, "short_debt": debt, "interest_expense_ttm": interest}
    return metrics, context


def build_row(stock, frames, as_of, historical=False, report_url=None):
    metrics, context = extract(frames, stock["market"], as_of)
    status = listing_risk(stock, as_of, use_snapshot=not historical)
    if status:
        metrics.update(listing_status=status['status'], listing_risk_title=status['title'])
        if status.get('source'):
            metrics.update(listing_source_url=status['source']['url'], listing_source_title=status['source']['title'])
    events = list(EVENTS.get(stock["ts_code"], []))
    audit = frames["fina_audit"].copy()
    if not audit.empty:
        audit = audit[(audit.ann_date.astype(str) <= as_of) & (audit.end_date.astype(str) <= context["period"])].sort_values(["end_date", "ann_date"])
        if not audit.empty:
            a = audit.iloc[-1]
            # Verified company primary documents take precedence over vendor opinion.
            if not any(e["kind"] == "audit_opinion" and e["published_at"] <= as_of and e["id"].endswith("2025-audit") for e in events):
                opinion = str(a.audit_result)
                mapped = "disclaimer" if "无法表示" in opinion else "adverse" if "否定" in opinion else "standard" if "无保留" in opinion else "qualified" if "保留" in opinion else None
                if mapped:
                    events.append({"id": f"{stock['ts_code']}-vendor-audit-{a.end_date}", "kind": "audit_opinion", "opinion": mapped,
                        "published_at": str(a.ann_date), "title": f"{str(a.end_date)[:4]}年财报审计：{opinion}",
                        "source": {"title": "Tushare财务审计意见（供应商记录）", "url": "https://tushare.pro/document/2?doc_id=80"}})
    visible = [e for e in events if e["published_at"] <= as_of]
    metrics["annual_report_inquiry"] = True if any(e["kind"] == "annual_inquiry" for e in visible) else None
    metrics["inquiry_severity"] = next((e.get("severity") for e in visible if e["kind"] == "annual_inquiry"), None)
    metrics["second_inquiry"] = True if any(e["kind"] == "second_inquiry" for e in visible) else None
    metrics["audit_opinion"] = next((e.get("opinion") for e in reversed(visible) if e["kind"] == "audit_opinion"), None)
    metrics["internal_control_opinion"] = next((e.get("opinion") for e in reversed(visible) if e["kind"] == "internal_control_opinion"), None)
    metrics["csrc_or_governance_event"] = [e["kind"] for e in visible if e["kind"] not in ("audit_opinion", "annual_inquiry", "internal_control_opinion")]
    result = score_risk(metrics, events, as_of, event_coverage=False)
    if status:
        result['latest_warning'] = max(result['latest_warning'] or '', status['published_at'])
    raw_source = {"title": "本次Tushare原始财报记录", "url": f"data/risk-test-financials/{stock['ts_code']}.json"}
    warning_dates = [result["latest_warning"]] if result["latest_warning"] else []
    for trigger in result["triggers"]:
        if trigger["metric"]:
            trigger["source"] = raw_source
            warning_dates.append(context["metric_dates"][trigger["metric"]])
    if metrics["negative_net_assets"] is True:
        warning_dates.append(context["ann_date"])
        for item in result["floors"]:
            if item["title"] == "净资产为负":
                item["source"] = raw_source
    result["latest_warning"] = max(warning_dates, default=None)
    documents = [raw_source] + [{"title": f"{label} · {endpoint}", "url": f"https://tushare.pro/document/2?doc_id={doc_id}"}
                 for label, endpoint, doc_id in [("利润表", "income", 33), ("资产负债表", "balancesheet", 36), ("现金流", "cashflow", 44), ("扣非净利", "fina_indicator", 79)]]
    if report_url:
        documents.insert(0, {"title": "当时披露的公司财报原文", "url": report_url})
    return {"id": f"{stock['ts_code']}-{as_of}", "ts_code": stock["ts_code"], "name": stock["name"],
            "market": stock["market"], "as_of": as_of, "historical": historical,
            "context": context, "metrics": metrics, "risk": result, "documents": documents,
            "events": visible, "trend": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=12)
    args = parser.parse_args()
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    as_of = now.strftime("%Y%m%d")
    source = CachedSource(ts.pro_api(os.environ["TUSHARE_TOKEN"]), ROOT / ".cache-risk.local", as_of)
    pool = json.loads((ROOT / "public/data/small-cap-dashboard.json").read_text(encoding="utf-8"))
    stocks = pool["screened"]["rows"][:args.sample_size] + [
        {"ts_code": "688121.SH", "name": "卓然股份", "market": "科创板"},
        {"ts_code": "603718.SH", "name": "海利生物", "market": "主板"},
        {"ts_code": "301139.SZ", "name": "元道退", "market": "创业板"}]
    rows, errors = [], []
    for i, stock in enumerate(stocks):
        frames = {}
        for endpoint, fields in FIELDS.items():
            try:
                frames[endpoint] = source.query(endpoint, ts_code=stock["ts_code"], start_date="20200101", end_date=as_of, fields=fields)
            except RuntimeError:
                frames[endpoint] = pd.DataFrame()
                errors.append({"ts_code": stock["ts_code"], "stage": endpoint, "error": "来源暂不可用"})
        try:
            raw_dir = ROOT / "public/data/risk-test-financials"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw = {"ts_code": stock["ts_code"], "fetched_at": now.isoformat(timespec="seconds"),
                   "source": "Tushare", "query": {"start_date": "20200101", "end_date": as_of},
                   "tables": {endpoint: json.loads(frame.to_json(orient="records")) for endpoint, frame in frames.items()}}
            (raw_dir / f"{stock['ts_code']}.json").write_text(json.dumps(raw, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            rows.append(build_row(stock, frames, as_of))
            history = {
                "688121.SH": [("20250628", "https://static.cninfo.com.cn/finalpage/2025-04-22/1223196007.PDF"),
                              ("20250830", "https://dataclouds.cninfo.com.cn/shgonggao/2025/2025-08-30/46ae3faa84cf11f09dd8fa163e957f7a.pdf")],
                "603718.SH": [("20250828", "https://static.cninfo.com.cn/finalpage/2025-08-28/1224587431.PDF")]
            }
            for cutoff, url in history.get(stock["ts_code"], []):
                rows.append(build_row(stock, frames, cutoff, historical=True, report_url=url))
        except (ValueError, KeyError, AttributeError) as error:
            errors.append({"ts_code": stock["ts_code"], "stage": "financial", "error": str(error)})
        print(f"Risk sample {i+1}/{len(stocks)}: {stock['ts_code']}", flush=True)
    data = {"schema_version": 1, "updated_at": now.isoformat(timespec="seconds"), "as_of": as_of,
            "rules": RULES, "sample_note": f"默认沪深榜市值最小的{args.sample_size}只 + 卓然/海利/元道退案例；退市案例仅供回归验证，不进入股票榜。",
            "coverage_note": "公告仅含已核实样本，未接入完整公告扫描；未发现事件不能解释为没有风险。历史截面按披露日期过滤，供应商可能存在后续更正回填。",
            "rows": rows, "errors": errors}
    if not rows:
        raise RuntimeError("No usable samples; previous file preserved")
    output = ROOT / "public/data/risk-test.json"
    temp = output.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(output)
    print(f"Saved {len(rows)} snapshots; {len(errors)} source issues", flush=True)


if __name__ == "__main__":
    main()
