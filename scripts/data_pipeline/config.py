from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"
STOCK_LIST_FILE = SCRIPTS_DIR / "stock_list.csv"
OUTPUT_JSON_FILE = ROOT_DIR / "public" / "data" / "dashboard.json"
SUPPORTED_ADJUSTMENTS = ("qfq", "none")


@dataclass(frozen=True)
class WatchlistItem:
    code: str
    name: str


@dataclass(frozen=True)
class RuntimeConfig:
    tushare_token: str
    root_dir: Path
    stock_list_file: Path
    output_json_file: Path
    watchlist: list[WatchlistItem]
    adjustments: tuple[str, ...]
    updated_at: str
    start_date: str
    end_date: str
    year_start: str


def build_runtime_config() -> RuntimeConfig:
    tushare_token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not tushare_token:
        raise RuntimeError(
            "Missing TUSHARE_TOKEN environment variable. Set TUSHARE_TOKEN before running scripts/generate_dashboard.py."
        )

    today = date.today()
    year_start = date(today.year, 1, 1)
    history_start = min(year_start, today - timedelta(days=500))

    return RuntimeConfig(
        tushare_token=tushare_token,
        root_dir=ROOT_DIR,
        stock_list_file=STOCK_LIST_FILE,
        output_json_file=OUTPUT_JSON_FILE,
        watchlist=load_watchlist(STOCK_LIST_FILE),
        adjustments=SUPPORTED_ADJUSTMENTS,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        start_date=history_start.strftime("%Y%m%d"),
        end_date=today.strftime("%Y%m%d"),
        year_start=year_start.strftime("%Y%m%d"),
    )


def load_watchlist(path: Path) -> list[WatchlistItem]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        items = [
            WatchlistItem(code=(row.get("code") or "").strip(), name=(row.get("name") or "").strip())
            for row in reader
        ]

    watchlist = [item for item in items if item.code and item.name]
    if not watchlist:
        raise RuntimeError(f"No watchlist rows found in {path}")
    return watchlist
