from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"


@dataclass(frozen=True)
class WatchlistItem:
    code: str
    name: str


@dataclass(frozen=True)
class RuntimeConfig:
    token: str
    output_path: Path
    watchlist_path: Path
    watchlist: list[WatchlistItem]
    updated_at: str
    start_date: str
    end_date: str
    year_start: str


def build_runtime_config() -> RuntimeConfig:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN environment variable.")

    today = date.today()
    year_start = date(today.year, 1, 1)
    history_start = min(year_start, today - timedelta(days=500))
    watchlist_path = SCRIPTS_DIR / "stock_list.csv"

    return RuntimeConfig(
        token=token,
        output_path=ROOT / "public" / "data" / "dashboard.json",
        watchlist_path=watchlist_path,
        watchlist=load_watchlist(watchlist_path),
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
