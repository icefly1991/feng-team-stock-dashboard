from __future__ import annotations

import math
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts

try:
    from scripts.data_pipeline.exporter import dashboard_exists, export_dashboard
except ModuleNotFoundError:  # Direct execution adds scripts/ rather than the repo root to sys.path.
    from data_pipeline.exporter import dashboard_exists, export_dashboard


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT_DIR / "public" / "data" / "growth-market-dashboard.json"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
TOTAL_MARKET_CAP_LIMIT_YI = 25.0
SUPPORTED_PREFIXES = ("30", "688")


def main() -> None:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN environment variable.")

    pro = ts.pro_api(token)
    today = datetime.now(BEIJING_TZ).date()
    latest_trade_date = get_latest_trade_date(pro, today)
    annual_periods = tuple(f"{year}1231" for year in range(today.year - 3, today.year))

    candidates, universe_count = load_candidates(pro, latest_trade_date)
    company_business = load_company_business(pro)
    candidates = [
        {**candidate, "main_business": company_business.get(candidate["ts_code"], "")}
        for candidate in candidates
    ]
    profitable: list[dict[str, Any]] = []
    annual_profitable_count = 0
    financial_errors: list[dict[str, str]] = []

    for candidate in candidates:
        try:
            # Expanded pools can exceed the income API's 200 requests/minute quota.
            time.sleep(0.35)
            financials = load_financials(
                pro,
                candidate["ts_code"],
                annual_periods,
                today.strftime("%Y%m%d"),
            )
            if financials is not None and all(value > 0 for value in financials["annual_net_profit"].values()):
                annual_profitable_count += 1
                latest_profit = financials["latest_report"]["net_profit"]
                if latest_profit is not None and latest_profit >= 0:
                    profitable.append({**candidate, **financials})
        except Exception as exc:  # noqa: BLE001
            financial_errors.append(error_row(candidate, f"financial: {exc}"))

    history_start = (today - timedelta(days=500)).strftime("%Y%m%d")
    rows: list[dict[str, Any]] = []
    history_errors: list[dict[str, str]] = []

    for candidate in profitable:
        try:
            frame = ts.pro_bar(
                ts_code=candidate["ts_code"],
                api=pro,
                adj="qfq",
                start_date=history_start,
                end_date=latest_trade_date,
                fields="ts_code,trade_date,close,high,low,pct_chg",
            )
            metrics = build_52w_metrics(frame)
            rows.append(
                {
                    "code": candidate["symbol"],
                    "name": candidate["name"],
                    "close": metrics["close"],
                    "today_return_pct": metrics["today_return_pct"],
                    "total_market_cap_yi": candidate["total_market_cap_yi"],
                    "distance_ma250_pct": metrics["distance_ma250_pct"],
                    "distance_52w_high_pct": metrics["distance_52w_high_pct"],
                    "distance_52w_low_pct": metrics["distance_52w_low_pct"],
                    "position_52w_pct": metrics["position_52w_pct"],
                    "annual_net_profit": candidate["annual_net_profit"],
                    "latest_report": candidate["latest_report"],
                    "main_business": candidate["main_business"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            history_errors.append(error_row(candidate, f"history: {exc}"))

    if not rows:
        status = "Kept existing growth-market-dashboard.json." if dashboard_exists(OUTPUT_FILE) else "No output written."
        error_samples = (financial_errors + history_errors)[:5]
        raise RuntimeError(
            f"No growth-market rows generated. Candidates: {len(candidates)}; "
            f"profitable: {len(profitable)}; error samples: {error_samples}. {status}"
        )

    rows.sort(key=lambda row: (row["total_market_cap_yi"], row["code"]))
    payload: dict[str, Any] = {
        "updated_at": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M"),
        "trade_date": latest_trade_date,
        "filters": {
            "code_prefixes": list(SUPPORTED_PREFIXES),
            "total_market_cap_lt_yi": TOTAL_MARKET_CAP_LIMIT_YI,
            "annual_periods": list(annual_periods),
            "annual_net_profit_rule": "n_income_attr_p > 0 for all three periods",
            "latest_report_net_profit_rule": "n_income_attr_p >= 0 (consolidated year-to-date)",
            "financial_as_of": today.strftime("%Y%m%d"),
            "adjustment": "qfq",
            "minimum_listed_trading_days": 5,
        },
        "summary": {
            "growth_market_total": universe_count,
            "market_cap_candidates": len(candidates),
            "profitable_candidates": annual_profitable_count,
            "latest_report_candidates": len(profitable),
            "displayed_total": len(rows),
        },
        "rows": rows,
    }
    errors = financial_errors + history_errors
    if errors:
        payload["errors"] = errors

    export_dashboard(OUTPUT_FILE, payload)
    print(f"Latest trade date: {latest_trade_date}")
    print(f"30/688 universe: {universe_count}")
    print(f"Total market cap under {TOTAL_MARKET_CAP_LIMIT_YI:.0f} yi: {len(candidates)}")
    print(f"Profitable in all three years: {annual_profitable_count}")
    print(f"Latest report nonnegative: {len(profitable)}")
    print(f"Displayed rows: {len(rows)}")
    print(f"Errors: {len(errors)}")
    print(f"Output file path: {OUTPUT_FILE}")


def get_latest_trade_date(pro: Any, today: date) -> str:
    calendar = pro.trade_cal(
        exchange="SSE",
        start_date=(today - timedelta(days=30)).strftime("%Y%m%d"),
        end_date=today.strftime("%Y%m%d"),
        is_open="1",
        fields="cal_date",
    )
    if calendar is None or calendar.empty:
        raise RuntimeError("No open trading date returned.")
    open_dates = sorted(calendar["cal_date"].astype(str).tolist(), reverse=True)
    for trade_date in open_dates:
        daily = pro.daily_basic(trade_date=trade_date, fields="ts_code")
        if daily is not None and not daily.empty:
            return trade_date
    raise RuntimeError("No recent trade date with daily_basic data returned.")


def load_candidates(pro: Any, trade_date: str) -> tuple[list[dict[str, Any]], int]:
    basic = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,market,list_date",
    )
    daily = pro.daily_basic(
        trade_date=trade_date,
        fields="ts_code,trade_date,close,total_mv",
    )
    merged = basic.merge(daily, on="ts_code", how="inner")
    merged["total_mv"] = pd.to_numeric(merged["total_mv"], errors="coerce")
    valid_market_cap = (merged["total_mv"] > 0) & (merged["total_mv"] < float("inf"))
    prefix_mask = merged["symbol"].astype(str).str.startswith(SUPPORTED_PREFIXES)
    market_mask = merged["market"].isin(["创业板", "科创板"])
    st_mask = merged["name"].fillna("").astype(str).str.contains("ST", case=False)
    universe = merged[prefix_mask & market_mask & ~st_mask & valid_market_cap].copy()

    eligible_list_dates = listed_more_than_five_trading_days(pro, universe, trade_date)
    universe = universe[universe["ts_code"].isin(eligible_list_dates)].copy()
    universe["total_market_cap_yi"] = universe["total_mv"].astype(float) / 10000
    selected = universe[
        universe["total_market_cap_yi"] < TOTAL_MARKET_CAP_LIMIT_YI
    ].copy()

    candidates = [
        {
            "ts_code": str(row.ts_code),
            "symbol": str(row.symbol),
            "name": str(row.name),
            "total_market_cap_yi": float(row.total_market_cap_yi),
        }
        for row in selected.itertuples(index=False)
    ]
    return candidates, len(universe)


def load_company_business(pro: Any) -> dict[str, str]:
    frames = [
        pro.stock_company(exchange=exchange, fields="ts_code,main_business")
        for exchange in ("SZSE", "SSE")
    ]
    available = [frame for frame in frames if frame is not None and not frame.empty]
    if not available:
        raise RuntimeError("No company business information returned.")
    companies = pd.concat(available, ignore_index=True)
    companies["main_business"] = (
        companies["main_business"].fillna("").astype(str).map(normalize_tushare_text).str.strip()
    )
    return dict(zip(companies["ts_code"].astype(str), companies["main_business"], strict=False))


def normalize_tushare_text(value: str) -> str:
    if not value:
        return ""
    try:
        repaired = value.encode("latin1").decode("gb18030")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return repaired if repaired else value


def listed_more_than_five_trading_days(pro: Any, universe: pd.DataFrame, trade_date: str) -> set[str]:
    trade_day = datetime.strptime(trade_date, "%Y%m%d").date()
    calendar = pro.trade_cal(
        exchange="SSE",
        start_date=(trade_day - timedelta(days=30)).strftime("%Y%m%d"),
        end_date=trade_date,
        is_open="1",
        fields="cal_date",
    )
    open_dates = sorted(calendar["cal_date"].astype(str).tolist())
    if trade_date not in open_dates or len(open_dates) < 6:
        raise RuntimeError("Not enough recent trading dates to validate listing age.")
    latest_index = open_dates.index(trade_date)
    if latest_index < 5:
        raise RuntimeError("Not enough trading dates before the latest trade date.")
    oldest_eligible_list_date = open_dates[latest_index - 5]
    eligible = universe[universe["list_date"].astype(str) <= oldest_eligible_list_date]
    return set(eligible["ts_code"].astype(str))


def load_financials(
    pro: Any,
    ts_code: str,
    periods: tuple[str, ...],
    announcement_end_date: str,
) -> dict[str, Any] | None:
    frame = pro.income(
        ts_code=ts_code,
        start_date=f"{periods[0][:4]}0101",
        end_date=announcement_end_date,
        fields="ts_code,ann_date,f_ann_date,end_date,report_type,n_income_attr_p,update_flag",
    )
    if frame is None or frame.empty:
        return None

    reports = frame.copy()
    # 1/4 are consolidated cumulative statements; exclude single-quarter,
    # parent-only and superseded pre-adjustment statements.
    reports = reports[pd.to_numeric(reports["report_type"], errors="coerce").isin([1, 4])].copy()
    actual = pd.to_datetime(reports["f_ann_date"], format="%Y%m%d", errors="coerce")
    announced = pd.to_datetime(reports["ann_date"], format="%Y%m%d", errors="coerce")
    reports["disclosed_at"] = actual.fillna(announced).dt.strftime("%Y%m%d")
    reports["end_date"] = pd.to_datetime(reports["end_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y%m%d")
    reports = reports[
        reports["disclosed_at"].notna()
        & (reports["disclosed_at"] <= announcement_end_date)
        & reports["end_date"].notna()
        & (reports["end_date"] <= reports["disclosed_at"])
        & reports["end_date"].str.endswith(("0331", "0630", "0930", "1231"), na=False)
    ].copy()
    if reports.empty:
        return None
    reports["update_priority"] = pd.to_numeric(reports["update_flag"], errors="coerce").fillna(0)
    reports["type_priority"] = pd.to_numeric(reports["report_type"], errors="coerce")
    reports["n_income_attr_p"] = pd.to_numeric(reports["n_income_attr_p"], errors="coerce")
    reports = reports.sort_values(["end_date", "disclosed_at", "update_priority", "type_priority"])
    latest_versions = reports.groupby("end_date", as_index=False).tail(1)
    annual = latest_versions[latest_versions["end_date"].isin(periods)]
    profits = {str(row.end_date): float(row.n_income_attr_p) for row in annual.itertuples(index=False)}
    if any(period not in profits or not math.isfinite(profits[period]) for period in periods):
        return None
    # Select the newest period before checking its value; never fall back to
    # an older profitable report when the latest report is missing or negative.
    latest = latest_versions.iloc[-1]
    latest_profit = float(latest["n_income_attr_p"])
    return {
        "annual_net_profit": {period: profits[period] for period in periods},
        "latest_report": {
            "period": str(latest["end_date"]),
            "ann_date": str(latest["disclosed_at"]),
            "net_profit": latest_profit if math.isfinite(latest_profit) else None,
        },
    }


def build_52w_metrics(frame: pd.DataFrame | None) -> dict[str, float]:
    if frame is None or frame.empty:
        raise ValueError("No qfq daily bars returned.")
    ordered = frame.copy()
    for column in ("close", "high", "low"):
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce")
    ordered = ordered.dropna(subset=["trade_date", "close", "high", "low"])
    ordered["trade_date"] = ordered["trade_date"].astype(str)
    ordered = ordered.sort_values("trade_date").reset_index(drop=True)
    if len(ordered) < 252:
        raise ValueError("Not enough history for a 252-trading-day range.")

    window = ordered.tail(252)
    latest = ordered.iloc[-1]
    close = float(latest["close"])
    high = float(window["high"].max())
    low = float(window["low"].min())
    ma250 = float(ordered["close"].tail(250).mean())
    if low == 0 or high == low or ma250 == 0:
        raise ValueError("Invalid 52-week price range.")
    pct_chg = latest.get("pct_chg")
    today_return = float(pct_chg) if pd.notna(pct_chg) else 0.0
    return {
        "close": round(close, 2),
        "today_return_pct": round(today_return, 2),
        "distance_ma250_pct": round((close / ma250 - 1) * 100, 2),
        "distance_52w_high_pct": round((close / high - 1) * 100, 2),
        "distance_52w_low_pct": round((close / low - 1) * 100, 2),
        "position_52w_pct": round((close - low) / (high - low) * 100, 2),
    }


def error_row(candidate: dict[str, Any], message: str) -> dict[str, str]:
    return {"code": candidate["symbol"], "name": candidate["name"], "error": message}


if __name__ == "__main__":
    main()
