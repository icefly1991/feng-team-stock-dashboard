"""Refresh lifecycle facts independently of financial scores."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import tushare as ts
from data_pipeline.active_source import CachedSource

ROOT = Path(__file__).resolve().parents[1]

def main():
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    as_of = now.strftime('%Y%m%d')
    source = CachedSource(ts.pro_api(os.environ['TUSHARE_TOKEN']), ROOT / '.cache-listing.local', as_of)
    stocks = {}
    for status in ('L', 'P', 'D'):
        frame = source.all_rows('stock_basic', exchange='', list_status=status, fields='ts_code,symbol,name,list_status,list_date,delist_date')
        for row in json.loads(frame.to_json(orient='records')):
            stocks[row['ts_code']] = row
    if not stocks or not any(row['list_status'] == 'L' for row in stocks.values()):
        raise RuntimeError('Listing status unavailable; previous file preserved')
    output = ROOT / 'public/data/listing-status.json'
    temp = output.with_suffix('.tmp')
    temp.write_text(json.dumps({'as_of': as_of, 'updated_at': now.isoformat(timespec='seconds'), 'stocks': stocks}, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temp.replace(output)
    print(f'Listing lifecycle snapshot saved: {len(stocks)} securities')

if __name__ == '__main__':
    main()
