from __future__ import annotations

import os
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
CIRCULATING_MARKET_CAP_LIMIT_YI = 20.0
SUPPORTED_PREFIXES = ("30", "688")


def main() -> None:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN environment variable.")

    ts.set_token(token)
    pro = ts.pro_api()
    today = date.today()
    latest_trade_date = get_latest_trade_date(pro, today)
    annual_periods = (f"{today.year - 2}1231", f"{today.year - 1}1231")

    candidates, universe_count = load_candidates(pro, latest_trade_date)
    company_business = load_company_business(pro)
    candidates = [
        {**candidate, "main_business": company_business.get(candidate["ts_code"], "")}
        for candidate in candidates
    ]
    profitable: list[dict[str, Any]] = []
    financial_errors: list[dict[str, str]] = []

    for candidate in candidates:
        try:
            profits = load_annual_profits(
                pro,
                candidate["ts_code"],
                annual_periods,
                today.strftime("%Y%m%d"),
            )
            if profits is not None and all(value > 0 for value in profits.values()):
                profitable.append({**candidate, "annual_profits": profits})
        except Exception as exc:  # noqa: BLE001
            financial_errors.append(error_row(candidate, f"financial: {exc}"))

    history_start = (today - timedelta(days=500)).strftime("%Y%m%d")
    rows: list[dict[str, Any]] = []
    history_errors: list[dict[str, str]] = []

    for candidate in profitable:
        try:
            frame = ts.pro_bar(
                ts_code=candidate["ts_code"],
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
                    "circulating_market_cap_yi": candidate["circulating_market_cap_yi"],
                    "distance_52w_high_pct": metrics["distance_52w_high_pct"],
                    "distance_52w_low_pct": metrics["distance_52w_low_pct"],
                    "position_52w_pct": metrics["position_52w_pct"],
                    "annual_net_profit": candidate["annual_profits"],
                    "main_business": candidate["main_business"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            history_errors.append(error_row(candidate, f"history: {exc}"))

    if not rows:
        status = "Kept existing growth-market-dashboard.json." if dashboard_exists(OUTPUT_FILE) else "No output written."
        raise RuntimeError(f"No growth-market rows generated. {status}")

    rows.sort(key=lambda row: row["position_52w_pct"], reverse=True)
    payload: dict[str, Any] = {
        "updated_at": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M"),
        "trade_date": latest_trade_date,
        "filters": {
            "code_prefixes": list(SUPPORTED_PREFIXES),
            "circulating_market_cap_lt_yi": CIRCULATING_MARKET_CAP_LIMIT_YI,
            "annual_periods": list(annual_periods),
            "annual_net_profit_rule": "n_income_attr_p > 0 for both periods",
            "adjustment": "qfq",
            "minimum_listed_trading_days": 5,
        },
        "summary": {
            "growth_market_total": universe_count,
            "market_cap_candidates": len(candidates),
            "profitable_candidates": len(profitable),
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
    print(f"Under {CIRCULATING_MARKET_CAP_LIMIT_YI:.0f} yi: {len(candidates)}")
    print(f"Profitable in both years: {len(profitable)}")
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
    return str(calendar["cal_date"].astype(str).max())


def load_candidates(pro: Any, trade_date: str) -> tuple[list[dict[str, Any]], int]:
    basic = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,market,list_date",
    )
    daily = pro.daily_basic(
        trade_date=trade_date,
        fields="ts_code,trade_date,close,circ_mv",
    )
    merged = basic.merge(daily, on="ts_code", how="inner")
    prefix_mask = merged["symbol"].astype(str).str.startswith(SUPPORTED_PREFIXES)
    market_mask = merged["market"].isin(["创业板", "科创板"])
    universe = merged[prefix_mask & market_mask & merged["circ_mv"].notna()].copy()

    eligible_list_dates = listed_more_than_five_trading_days(pro, universe, trade_date)
    universe = universe[universe["ts_code"].isin(eligible_list_dates)].copy()
    universe["circulating_market_cap_yi"] = universe["circ_mv"].astype(float) / 10000
    selected = universe[
        universe["circulating_market_cap_yi"] < CIRCULATING_MARKET_CAP_LIMIT_YI
    ].copy()

    candidates = [
        {
            "ts_code": str(row.ts_code),
            "symbol": str(row.symbol),
            "name": str(row.name),
            "circulating_market_cap_yi": round(float(row.circulating_market_cap_yi), 2),
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
    earliest = str(universe["list_date"].astype(str).min())
    calendar = pro.trade_cal(
        exchange="SSE",
        start_date=earliest,
        end_date=trade_date,
        is_open="1",
        fields="cal_date",
    )
    open_dates = sorted(calendar["cal_date"].astype(str).tolist())
    date_rank = {value: index for index, value in enumerate(open_dates)}
    latest_rank = date_rank[trade_date]
    eligible: set[str] = set()
    for row in universe.itertuples(index=False):
        first_rank = next((date_rank[value] for value in open_dates if value >= str(row.list_date)), None)
        if first_rank is not None and latest_rank - first_rank + 1 > 5:
            eligible.add(str(row.ts_code))
    return eligible


def load_annual_profits(
    pro: Any,
    ts_code: str,
    periods: tuple[str, str],
    announcement_end_date: str,
) -> dict[str, float] | None:
    frame = pro.income(
        ts_code=ts_code,
        start_date=f"{periods[0][:4]}0101",
        end_date=announcement_end_date,
        fields="ts_code,ann_date,end_date,report_type,n_income_attr_p,update_flag",
    )
    if frame is None or frame.empty:
        return None

    annual = frame[frame["end_date"].astype(str).isin(periods)].copy()
    annual = annual[annual["n_income_attr_p"].notna()]
    if annual.empty:
        return None
    annual["update_priority"] = pd.to_numeric(annual["update_flag"], errors="coerce").fillna(0)
    annual["ann_date"] = annual["ann_date"].fillna("").astype(str)
    annual = annual.sort_values(["end_date", "update_priority", "ann_date"])
    latest = annual.groupby("end_date", as_index=False).tail(1)
    profits = {str(row.end_date): float(row.n_income_attr_p) for row in latest.itertuples(index=False)}
    if any(period not in profits for period in periods):
        return None
    return {period: round(profits[period], 2) for period in periods}


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
    if low == 0 or high == low:
        raise ValueError("Invalid 52-week price range.")
    pct_chg = latest.get("pct_chg")
    today_return = float(pct_chg) if pd.notna(pct_chg) else 0.0
    return {
        "close": round(close, 2),
        "today_return_pct": round(today_return, 2),
        "distance_52w_high_pct": round((close / high - 1) * 100, 2),
        "distance_52w_low_pct": round((close / low - 1) * 100, 2),
        "position_52w_pct": round((close - low) / (high - low) * 100, 2),
    }


def error_row(candidate: dict[str, Any], message: str) -> dict[str, str]:
    return {"code": candidate["symbol"], "name": candidate["name"], "error": message}


if __name__ == "__main__":
    main()
