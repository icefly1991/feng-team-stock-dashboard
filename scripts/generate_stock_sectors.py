"""Collect current Sina industry/concept classifications for all three pages."""
from __future__ import annotations

import json
import time
import re
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

try:
    from scripts.data_pipeline.sector_heat import collect_heat
except ModuleNotFoundError:
    from data_pipeline.sector_heat import collect_heat

ROOT = Path(__file__).resolve().parents[1]


def collect(code: str, as_of: str) -> dict:
    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpOtherInfo/stockid/{code}.phtml"
    cache = ROOT / f".cache-sectors.local/sina/{as_of}/{code}.json"
    for attempt in range(3):
        try:
            if cache.exists():
                data = json.loads(cache.read_text(encoding="utf-8"))
            else:
                response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                response.raise_for_status()
                response.encoding = "gb18030"
                data = parse_sina(response.text, code)
            value = data
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return {**value, "source_url": url}
        except Exception:
            if attempt < 2:
                time.sleep(1 + attempt)
    return {"industry": [], "concepts": [], "status": "unavailable", "source_url": url}


def parse_sina(text: str, code: str) -> dict:
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if not title or code not in title.group(1):
        raise ValueError("Mismatched stock page")
    result = {"industry": [], "concepts": []}
    found = set()
    for table in re.findall(r'<table\b[^>]*class=["\']comInfo1["\'][^>]*>.*?</table>', text, re.I | re.S):
        kind = "industry" if "所属行业板块" in table else "concepts" if "所属概念板块" in table else None
        if not kind:
            continue
        found.add(kind)
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.I | re.S):
            cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.I | re.S)
            if len(cells) != 2:
                continue
            value = unescape(re.sub(r"<[^>]+>", "", cells[0])).strip()
            if value and value != "-" and "\ufffd" not in value:
                result[kind].append(value)
    if not found:
        raise ValueError("Classification sections unavailable")
    return {**{kind: list(dict.fromkeys(tags)) for kind, tags in result.items()},
            "status": "ok" if len(found) == 2 and result["industry"] else "partial"}


def main(extra_rows=()):
    folder = ROOT / "public/data"
    dashboard = json.loads((folder / "dashboard.json").read_text(encoding="utf-8"))
    rows = [r for adjustment in dashboard["adjustments"].values() for r in adjustment["rows"]]
    for filename in ("growth-market-dashboard.json", "small-cap-dashboard.json"):
        pool = json.loads((folder / filename).read_text(encoding="utf-8"))
        rows.extend(pool["rows"])
        rows.extend(pool.get('screened', {}).get('rows', []))
    rows.extend(extra_rows)
    codes = sorted({r["code"] for r in rows})
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    stocks = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(collect, code, now.strftime("%Y%m%d")): code for code in codes}
        for job in as_completed(jobs):
            code = jobs[job]
            stocks[code] = job.result()
            print(f"{len(stocks)}/{len(codes)} {code}: {stocks[code]['status']}", flush=True)
    failures = sum(value["status"] == "unavailable" for value in stocks.values())
    if failures == len(stocks):
        raise RuntimeError("All classification queries failed; existing file retained")
    payload = {"schema_version": 1, "source": "新浪财经（申万行业 / 新浪概念）", "updated_at": now.strftime("%Y-%m-%d %H:%M"),
               "timezone": "Asia/Shanghai", "stocks": dict(sorted(stocks.items())), "unavailable": failures,
               "heat": collect_heat(now.strftime('%Y-%m-%d'))}
    path = folder / "stock-sectors.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    main()
