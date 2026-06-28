from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "dashboard.json"

BASE_ROWS = [
    {"code": "600519", "name": "贵州茅台", "close": 1520.5, "today_return_pct": 1.2, "distance_ma250_pct": 2.3, "ytd_return_pct": -8.7, "distance_52w_high_pct": -15.2},
    {"code": "300750", "name": "宁德时代", "close": 231.8, "today_return_pct": -0.6, "distance_ma250_pct": -3.5, "ytd_return_pct": 12.4, "distance_52w_high_pct": -9.6},
    {"code": "000858", "name": "五粮液", "close": 129.3, "today_return_pct": 0.8, "distance_ma250_pct": 5.1, "ytd_return_pct": -3.2, "distance_52w_high_pct": -18.9},
    {"code": "600036", "name": "招商银行", "close": 44.7, "today_return_pct": 1.5, "distance_ma250_pct": 1.2, "ytd_return_pct": 7.9, "distance_52w_high_pct": -6.1},
    {"code": "002594", "name": "比亚迪", "close": 278.6, "today_return_pct": 2.4, "distance_ma250_pct": 8.8, "ytd_return_pct": 24.6, "distance_52w_high_pct": -4.4},
    {"code": "601318", "name": "中国平安", "close": 52.4, "today_return_pct": -1.1, "distance_ma250_pct": -6.8, "ytd_return_pct": 5.3, "distance_52w_high_pct": -12.2},
    {"code": "600276", "name": "恒瑞医药", "close": 49.6, "today_return_pct": 0.7, "distance_ma250_pct": 3.6, "ytd_return_pct": 14.8, "distance_52w_high_pct": -7.5},
    {"code": "000333", "name": "美的集团", "close": 71.2, "today_return_pct": 1.9, "distance_ma250_pct": 6.4, "ytd_return_pct": 18.3, "distance_52w_high_pct": -5.8},
    {"code": "601899", "name": "紫金矿业", "close": 19.8, "today_return_pct": -0.4, "distance_ma250_pct": 9.1, "ytd_return_pct": 21.7, "distance_52w_high_pct": -3.9},
    {"code": "688111", "name": "金山办公", "close": 286.4, "today_return_pct": 1.1, "distance_ma250_pct": 4.5, "ytd_return_pct": 16.2, "distance_52w_high_pct": -8.6},
    {"code": "601012", "name": "隆基绿能", "close": 21.5, "today_return_pct": -2.2, "distance_ma250_pct": -11.4, "ytd_return_pct": -13.6, "distance_52w_high_pct": -28.1},
    {"code": "002475", "name": "立讯精密", "close": 35.2, "today_return_pct": 0.4, "distance_ma250_pct": 2.7, "ytd_return_pct": 9.8, "distance_52w_high_pct": -10.5},
    {"code": "600887", "name": "伊利股份", "close": 29.4, "today_return_pct": -0.8, "distance_ma250_pct": -2.1, "ytd_return_pct": -4.7, "distance_52w_high_pct": -17.4},
    {"code": "000651", "name": "格力电器", "close": 40.6, "today_return_pct": 0.9, "distance_ma250_pct": 7.3, "ytd_return_pct": 11.5, "distance_52w_high_pct": -6.9},
    {"code": "300760", "name": "迈瑞医疗", "close": 312.7, "today_return_pct": -1.7, "distance_ma250_pct": -4.9, "ytd_return_pct": -2.8, "distance_52w_high_pct": -14.8},
    {"code": "002371", "name": "北方华创", "close": 358.9, "today_return_pct": 2.6, "distance_ma250_pct": 12.8, "ytd_return_pct": 27.4, "distance_52w_high_pct": -2.6},
    {"code": "601166", "name": "兴业银行", "close": 18.3, "today_return_pct": 0.3, "distance_ma250_pct": 1.8, "ytd_return_pct": 6.1, "distance_52w_high_pct": -9.9},
    {"code": "002415", "name": "海康威视", "close": 31.8, "today_return_pct": -1.4, "distance_ma250_pct": -7.6, "ytd_return_pct": -6.2, "distance_52w_high_pct": -19.1},
    {"code": "600309", "name": "万华化学", "close": 84.1, "today_return_pct": 1.6, "distance_ma250_pct": 5.9, "ytd_return_pct": 13.2, "distance_52w_high_pct": -8.1},
    {"code": "002714", "name": "牧原股份", "close": 43.5, "today_return_pct": -0.5, "distance_ma250_pct": -3.2, "ytd_return_pct": -9.9, "distance_52w_high_pct": -21.6},
]


def round1(value: float) -> float:
    return round(value, 1)


def summarize(rows: list[dict]) -> dict[str, int]:
    return {
        "watchlist_total": len(rows),
        "today_up": sum(1 for row in rows if row["today_return_pct"] > 0),
        "today_down": sum(1 for row in rows if row["today_return_pct"] < 0),
    }


def build_none_rows(rows: list[dict]) -> list[dict]:
    adjusted_rows = []
    for index, row in enumerate(rows):
        item = deepcopy(row)
        drift = (index % 5) - 2
        item["close"] = round1(row["close"] * (0.984 + index * 0.0008))
        item["today_return_pct"] = round1(row["today_return_pct"] - 0.3 + drift * 0.1)
        item["distance_ma250_pct"] = round1(row["distance_ma250_pct"] - 0.6 + drift * 0.2)
        item["ytd_return_pct"] = round1(row["ytd_return_pct"] - 1.4 + drift * 0.3)
        item["distance_52w_high_pct"] = round1(row["distance_52w_high_pct"] - 1.1 - drift * 0.4)
        adjusted_rows.append(item)
    return adjusted_rows


def build_payload() -> dict:
    qfq_rows = deepcopy(BASE_ROWS)
    none_rows = build_none_rows(BASE_ROWS)
    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "adjustments": {
            "qfq": {"summary": summarize(qfq_rows), "rows": qfq_rows},
            "none": {"summary": summarize(none_rows), "rows": none_rows},
        },
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(build_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
