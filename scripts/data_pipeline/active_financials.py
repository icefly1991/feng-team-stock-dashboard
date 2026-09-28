"""Point-in-time profitability and supporting disclosures for the active pool."""
from __future__ import annotations

import math
import pandas as pd


class Ineligible(ValueError):
    pass


def reports_as_of(frame: pd.DataFrame, as_of: str, consolidated=True) -> dict[str, dict]:
    if frame.empty:
        return {}
    rows = frame.copy()
    rows["end_date"] = rows.end_date.astype(str)
    rows["ann_date"] = rows.ann_date.fillna("").astype(str)
    actual = rows.get("f_ann_date", rows.ann_date).fillna("").astype(str)
    rows["disclosed_at"] = actual.where(actual.str.fullmatch(r"\d{8}"), rows.ann_date)
    valid = (rows.disclosed_at.str.fullmatch(r"\d{8}") & (rows.disclosed_at <= as_of) &
             rows.end_date.str.fullmatch(r"\d{4}(0331|0630|0930|1231)") &
             (rows.end_date <= rows.disclosed_at))
    if consolidated:
        valid &= rows.report_type.astype(str).isin(["1", "4", "1.0", "4.0"])
    rows = rows[valid].copy()
    rows["priority"] = rows.get("update_flag", pd.Series(0, index=rows.index)).astype(str).eq("1").astype(int)
    rows["type_priority"] = rows.get("report_type", pd.Series("", index=rows.index)).astype(str).isin(["4", "4.0"]).astype(int)
    rows = rows.sort_values(["end_date", "disclosed_at", "priority", "type_priority"]).groupby("end_date").tail(1)
    return {str(row["end_date"]): row for row in rows.to_dict("records")}


def number(reports: dict, period: str, field: str) -> float:
    value = reports.get(period, {}).get(field)
    if value is None or not math.isfinite(float(value)):
        raise Ineligible(f"缺少{period}的{field}")
    return float(value)


def ttm(reports: dict, period: str, field: str) -> float:
    current = number(reports, period, field)
    if period.endswith("1231"):
        return current
    previous_year = int(period[:4]) - 1
    return current + number(reports, f"{previous_year}1231", field) - number(reports, f"{previous_year}{period[4:]}", field)


def assess_profitability(income: pd.DataFrame, indicators: pd.DataFrame, as_of: str) -> dict:
    profits = reports_as_of(income, as_of)
    quality = reports_as_of(indicators, as_of, consolidated=False)
    annual = sorted(p for p in profits if p.endswith("1231") and p < f"{as_of[:4]}0101")
    if not annual:
        raise Ineligible("缺少年报")
    last_year = int(annual[-1][:4])
    # At most use the last annual report that should have been disclosed.
    required_year = int(as_of[:4]) - (1 if as_of[4:] >= "0501" else 2)
    if last_year < required_year:
        raise Ineligible("年报未更新至应披露年度")
    periods = [f"{year}1231" for year in range(last_year - 2, last_year + 1)]
    latest = max(profits)
    # Apr/Aug/Oct deadlines: no stale annual-only data masquerading as latest.
    year = int(as_of[:4])
    expected = (f"{year}0930" if as_of[4:] >= "1101" else f"{year}0630" if as_of[4:] >= "0901"
                else f"{year}0331" if as_of[4:] >= "0501" else f"{year-1}0930")
    if latest < expected:
        raise Ineligible("最新财报未更新至应披露报告期")
    rows = []
    for period in periods:
        profit = number(profits, period, "n_income_attr_p")
        recurring = number(quality, period, "profit_dedt")
        if profit <= 0 or recurring <= 0:
            raise Ineligible("最近三年存在归母或扣非利润不为正")
        rows.append({"period": period, "net_profit": profit, "recurring_profit": recurring,
                     "ann_date": profits[period]["disclosed_at"], "recurring_ann_date": quality[period]["disclosed_at"]})
    net = ttm(profits, latest, "n_income_attr_p")
    recurring = ttm(quality, latest, "profit_dedt")
    if net <= 0 or recurring <= 0:
        raise Ineligible("最近十二个月归母或扣非净利润不为正")
    five_year = all(p in profits and pd.notna(profits[p].get("n_income_attr_p")) and
                    math.isfinite(float(profits[p]["n_income_attr_p"])) and float(profits[p]["n_income_attr_p"]) > 0
                    for p in [f"{y}1231" for y in range(last_year - 4, last_year + 1)])
    same = f"{int(latest[:4])-1}{latest[4:]}"
    current = number(profits, latest, "n_income_attr_p")
    prior = profits.get(same, {}).get("n_income_attr_p")
    growth = (current / float(prior) - 1) * 100 if prior is not None and math.isfinite(float(prior)) and float(prior) > 0 else None
    components = [latest] if latest.endswith("1231") else [latest, f"{int(latest[:4])-1}1231", same]
    return {"annual_reports": rows, "five_year_profitable": five_year, "latest_period": latest,
            "latest_ann_date": profits[latest]["disclosed_at"], "ttm_net_profit": net,
            "ttm_recurring_profit": recurring, "profit_yoy_pct": growth,
            "ttm_evidence": [{"period": p, "net_profit": number(profits, p, "n_income_attr_p"),
                              "recurring_profit": number(quality, p, "profit_dedt"),
                              "ann_date": profits[p]["disclosed_at"], "recurring_ann_date": quality[p]["disclosed_at"]}
                             for p in components]}


def load_profitability(source, code: str, as_of: str) -> dict:
    start = f"{int(as_of[:4])-6}0101"
    income = source.query("income", ts_code=code, start_date=start, end_date=as_of,
                          fields="ts_code,ann_date,f_ann_date,end_date,report_type,n_income_attr_p,update_flag")
    # Avoid expensive quality requests for loss-making annual histories.
    reports = reports_as_of(income, as_of)
    annual = sorted(p for p in reports if p.endswith("1231") and p < f"{as_of[:4]}0101")
    if not annual:
        raise Ineligible("缺少年报")
    year = int(annual[-1][:4])
    if any(number(reports, f"{y}1231", "n_income_attr_p") <= 0 for y in range(year - 2, year + 1)):
        raise Ineligible("最近三年归母利润不全为正")
    if ttm(reports, max(reports), "n_income_attr_p") <= 0:
        raise Ineligible("最近十二个月归母净利润不为正")
    indicators = source.query("fina_indicator", ts_code=code, start_date=start, end_date=as_of,
                              fields="ts_code,ann_date,end_date,profit_dedt,update_flag")
    return assess_profitability(income, indicators, as_of)


def load_quality(source, code: str, as_of: str, financials: dict, industry: str) -> dict:
    start = f"{int(financials['latest_period'][:4])-2}0101"
    cash = reports_as_of(source.query("cashflow", ts_code=code, start_date=start, end_date=as_of,
             fields="ts_code,ann_date,f_ann_date,end_date,report_type,n_cashflow_act,update_flag"), as_of)
    balance = reports_as_of(source.query("balancesheet", ts_code=code, start_date=start, end_date=as_of,
             fields="ts_code,ann_date,f_ann_date,end_date,report_type,total_assets,total_liab,update_flag"), as_of)
    period = financials["latest_period"]
    operating_cash = ttm(cash, period, "n_cashflow_act")
    assets = number(balance, period, "total_assets")
    liabilities = number(balance, period, "total_liab")
    if assets <= 0 or liabilities < 0:
        raise Ineligible("资产负债表数值无效")
    financial_sector = any(label in industry for label in ("银行", "保险", "证券", "多元金融"))
    warnings = []
    if financial_sector:
        warnings.append("金融企业：现金流和负债率需按行业解读")
    else:
        if operating_cash <= 0:
            warnings.append("TTM经营现金流非正")
        if liabilities / assets >= .7:
            warnings.append("资产负债率不低于70%")
    if financials["profit_yoy_pct"] is not None and financials["profit_yoy_pct"] < -30:
        warnings.append("最新累计归母利润同比下降超过30%")
    components = [period] if period.endswith("1231") else [period, f"{int(period[:4])-1}1231", f"{int(period[:4])-1}{period[4:]}"]
    return {"ttm_operating_cashflow": operating_cash, "debt_asset_pct": liabilities / assets * 100,
            "quality_period": period, "cash_ann_date": cash[period]["disclosed_at"],
            "balance_ann_date": balance[period]["disclosed_at"], "financial_sector": financial_sector,
            "quality_warnings": warnings,
            "cashflow_evidence": [{"period": p, "value": number(cash, p, "n_cashflow_act"),
                                    "ann_date": cash[p]["disclosed_at"]} for p in components],
            "total_assets": assets, "total_liabilities": liabilities}
