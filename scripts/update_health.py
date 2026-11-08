"""OPS-008: dependency-independent checks of generated and published data."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]
CORE = ("dashboard.json", "growth-market-dashboard.json", "small-cap-dashboard.json")
AUX = ("listing-status.json", "risk-dashboard.json", "shareholder-watch.json", "stock-sectors.json")


def request_json(url, *, payload=None, headers=None, attempts=3):
    """Retry transport/429/5xx failures only; never print credentials or responses."""
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, data=None if payload is None else json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "feng-update-health", **(headers or {})},
            )
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise RuntimeError(f"HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        except (ValueError, UnicodeError):
            raise RuntimeError("Response is not valid JSON") from None
        if attempt < attempts - 1:
            time.sleep(2 ** attempt)
    raise RuntimeError("Request unavailable after 3 attempts")


def trading_calendar(now):
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN; cannot verify trading calendar")
    start, end = now.date() - timedelta(days=45), now.date() + timedelta(days=45)
    result = request_json("https://api.tushare.pro", payload={
        "api_name": "trade_cal", "token": token,
        "params": {"exchange": "SSE", "start_date": start.strftime("%Y%m%d"), "end_date": end.strftime("%Y%m%d")},
        "fields": "cal_date,is_open",
    })
    if result.get("code") != 0:
        raise RuntimeError("Trading calendar API rejected request; check token, permissions or quota")
    data = result.get("data") or {}
    fields = data.get("fields", [])
    days = {str(dict(zip(fields, row))["cal_date"]): str(dict(zip(fields, row))["is_open"])
            for row in data.get("items", [])}
    # Missing/partial calendar is an error, never a weekday-based guess.
    today = now.strftime("%Y%m%d")
    if today not in days or any(value not in ("0", "1") for value in days.values()):
        raise RuntimeError("Trading calendar is incomplete")
    past = start
    while past <= now.date():
        if past.strftime("%Y%m%d") not in days:
            raise RuntimeError("Trading calendar has missing days")
        past += timedelta(days=1)
    return {"days": days, "source": "Tushare trade_cal / SSE", "checked_at": now.isoformat()}


def expected_trade_date(calendar, now, *, morning=False):
    # Morning watchdog checks the preceding civil day, even on weekends/holidays.
    cutoff = now.date() if not morning and now.hour >= 16 else now.date() - timedelta(days=1)
    days = calendar["days"]
    if cutoff.strftime("%Y%m%d") not in days:
        raise ValueError("Calendar does not cover check date")
    eligible = [day for day, opened in days.items() if opened == "1" and day <= cutoff.strftime("%Y%m%d")]
    if not eligible:
        raise ValueError("No completed trading session in calendar")
    return max(eligible)


def validate_core(name, data, expected):
    if data.get("trade_date") != expected:
        raise ValueError(f"{name}: expected trade_date {expected}, got {data.get('trade_date')}")
    if not data.get("updated_at"):
        raise ValueError(f"{name}: missing generation time")
    errors = data.get("errors") or []
    if errors and name != "small-cap-dashboard.json":
        raise ValueError(f"{name}: {len(errors)} data generation errors; inspect generation logs")
    if errors and any(error.get("stage") not in ("history", "financial", "business") for error in errors):
        raise ValueError(f"{name}: unclassified generation error")
    missing_history = {error["code"] for error in errors if error.get("stage") == "history"}
    groups = [data.get("rows")]
    if name == "dashboard.json":
        adjustments = data.get("adjustments", {})
        groups = [adjustments.get(mode, {}).get("rows") for mode in ("qfq", "none")]
        for mode, rows in zip(("qfq", "none"), groups):
            total = adjustments.get(mode, {}).get("summary", {}).get("watchlist_total")
            if not isinstance(rows, list) or len(rows) != total:
                raise ValueError(f"{name}: incomplete {mode} watchlist")
    if name == "small-cap-dashboard.json":
        groups.append(data.get("screened", {}).get("rows"))
        if [len(group or []) for group in groups] != [250, 100]:
            raise ValueError(f"{name}: rankings must contain 250 and 100 rows")
        screened_codes = {row.get("code") for row in groups[1]}
        if any(error.get("stage") == "financial" and error.get("code") in screened_codes for error in errors):
            raise ValueError(f"{name}: screened financial data unavailable")
    for rows in groups:
        # A genuinely empty growth pool is permitted by its declared summary.
        if not isinstance(rows, list) or (not rows and not (
            name == "growth-market-dashboard.json" and data.get("summary", {}).get("displayed_total") == 0
        )):
            raise ValueError(f"{name}: missing rows")
        codes = [row.get("code") for row in rows]
        if any(not code for code in codes) or len(set(codes)) != len(codes):
            raise ValueError(f"{name}: missing or duplicate stock codes")
        if any(not (name == "small-cap-dashboard.json" and row.get("close") is None and row.get("code") in missing_history)
               and (not isinstance(row.get("close"), (int, float)) or not 0 < row["close"] < float("inf")) for row in rows):
            raise ValueError(f"{name}: invalid close price")
    return sum(len(group) for group in groups)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(directory):
    for name in ("six", "pandas", "tushare"):
        importlib.import_module(name)
    now = datetime.now(TZ)
    calendar = trading_calendar(now)
    write_json(directory / "update-context.json", {
        "started_at": now.isoformat(), "expected_trade_date": expected_trade_date(calendar, now),
        "calendar": calendar,
    })
    print("Dependency imports, credentials and trading calendar verified")


def recheck(directory):
    context = json.loads((directory / "update-context.json").read_text(encoding="utf-8"))
    now = datetime.now(TZ)
    calendar = trading_calendar(now)
    if context["expected_trade_date"] != expected_trade_date(calendar, now):
        raise ValueError("Saved artifact is stale; regenerate data instead of reusing it")
    context["calendar"] = calendar
    write_json(directory / "update-context.json", context)
    print("Saved artifact trading date is still current")


def seal(directory, run_id):
    context = json.loads((directory / "update-context.json").read_text(encoding="utf-8"))
    expected = context["expected_trade_date"]
    files, warnings = {}, []
    for name in CORE + AUX:
        raw = (directory / name).read_bytes()
        data = json.loads(raw)
        generated = datetime.fromisoformat(data["updated_at"])
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=TZ)
        # Existing outputs have minute precision. Reject retained repository snapshots.
        if generated + timedelta(minutes=1) < datetime.fromisoformat(context["started_at"]):
            raise ValueError(f"{name}: old output retained instead of regenerated")
        count = validate_core(name, data, expected) if name in CORE else None
        if name in AUX and not isinstance(data.get("stocks"), dict):
            raise ValueError(f"{name}: invalid stocks dictionary")
        for error in data.get("errors") or []:
            # Only identifiers, never provider exception messages or credentials.
            warnings.append(f"{name}: {error.get('code', 'unknown')} / {error.get('stage', 'source')}")
        files[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "updated_at": data["updated_at"], "rows": count}
    # Check chart assets too; a new table must not publish stale K-lines.
    main = json.loads((directory / "dashboard.json").read_text(encoding="utf-8"))
    growth = json.loads((directory / "growth-market-dashboard.json").read_text(encoding="utf-8"))
    small = json.loads((directory / "small-cap-dashboard.json").read_text(encoding="utf-8"))
    jobs = [(f"watchlist-history/{mode}/{row['code']}.json", row) for mode in ("qfq", "none") for row in main["adjustments"][mode]["rows"]]
    jobs += [(f"growth-history/{row['code']}.json", row) for row in growth["rows"]]
    unavailable = {error["code"] for error in small.get("errors", []) if error.get("stage") == "history"}
    jobs += [(f"small-cap-history/{expected}/{row['code']}.json", row) for row in small["rows"] + small["screened"]["rows"] if row["code"] not in unavailable]
    for name, row in jobs:
        chart = json.loads((directory / name).read_text(encoding="utf-8"))
        if chart.get("trade_date") != expected or abs(chart["metrics"]["close"] - row["close"]) > .011:
            raise ValueError(f"{name}: chart date/close mismatch")
    write_json(directory / "update-health.json", {
        "schema_version": 1, "run_id": run_id, "generated_at": datetime.now(TZ).isoformat(),
        "trade_date": expected, "calendar": context["calendar"], "files": files, "warnings": sorted(set(warnings)),
    })
    # Do not publish internal build context.
    (directory / "update-context.json").unlink()
    print(f"Validated all pages and chart assets for {expected}; release {run_id}")


def check_online(base_url, expected, run_id=None):
    nonce = str(time.time_ns())
    def fetch(name):
        try:
            return request_json(f"{base_url.rstrip('/')}/data/{name}?health={nonce}")
        except RuntimeError as exc:
            raise RuntimeError(f"{name}: cannot read online data ({exc})") from None
    manifest = fetch("update-health.json")
    if manifest.get("schema_version") != 1 or not manifest.get("run_id"):
        raise ValueError("Missing valid publication manifest")
    if run_id and manifest.get("run_id") != run_id:
        raise ValueError("Published release is not the current workflow run")
    if not expected <= manifest.get("trade_date", "") <= datetime.now(TZ).strftime("%Y%m%d"):
        raise ValueError(f"Published trade date {manifest.get('trade_date')} is older than {expected} or in the future")
    for name in CORE + AUX:
        # Fetch bytes to compare with the exact build artifact, not reserialized JSON.
        url = f"{base_url.rstrip('/')}/data/{name}?health={nonce}"
        try:
            raw = fetch_bytes(url)
        except RuntimeError as exc:
            raise RuntimeError(f"{name}: {exc}") from None
        entry = manifest.get("files", {}).get(name, {})
        if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
            raise ValueError(f"{name}: published file differs from release manifest")
        if name in CORE:
            validate_core(name, json.loads(raw), manifest["trade_date"])
    return manifest


def fetch_bytes(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Cache-Control": "no-cache"}), timeout=25) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise RuntimeError("Published data unavailable after 3 attempts") from None
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "recheck", "seal", "verify", "monitor"))
    parser.add_argument("--directory", type=Path, default=ROOT / "public/data")
    parser.add_argument("--base-url", default="https://icefly1991.github.io/feng-team-stock-dashboard/")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local") + "." + os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    parser.add_argument("--report", type=Path, default=ROOT / ".cache-update-health.local/report.json")
    args = parser.parse_args()
    try:
        if args.mode == "preflight":
            preflight(args.directory)
        elif args.mode == "recheck":
            recheck(args.directory)
        elif args.mode == "seal":
            seal(args.directory, args.run_id)
        else:
            if args.mode == "verify":
                # Verify this exact release, using its build-time target even across midnight.
                manifest = request_json(f"{args.base_url.rstrip('/')}/data/update-health.json?health={time.time_ns()}")
                expected = manifest.get("trade_date", "")
                if not expected:
                    raise ValueError("Missing published trade date")
            else:
                now = datetime.now(TZ)
                expected = expected_trade_date(trading_calendar(now), now, morning=True)
            result = check_online(args.base_url, expected, args.run_id if args.mode == "verify" else None)
            warnings = result.get("warnings") or []
            if args.mode == "monitor" and warnings:
                detail = f"行情日期已更新至 {result['trade_date']}，存在局部数据缺失，请核查：\n" + "\n".join(warnings)
                write_json(args.report, {"ok": False, "detail": detail})
                print(detail)
                raise SystemExit(1)
            write_json(args.report, {"ok": True, "detail": f"Online release {result['run_id']}, trade date {result['trade_date']}; expected >= {expected}"})
            print("Published data verified")
    except Exception as exc:
        # Errors above are controlled messages; no API response/token is logged.
        detail = str(exc).replace(os.environ.get("TUSHARE_TOKEN") or "\0", "[redacted]")
        write_json(args.report, {"ok": False, "detail": f"{args.mode}: {type(exc).__name__}: {detail}"})
        print(f"Update health check failed: {detail}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
