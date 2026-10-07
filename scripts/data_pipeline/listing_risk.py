"""Trading eligibility is checked before financial risk and market-cap ranking."""
import json
from pathlib import Path

EVENTS = json.loads((Path(__file__).resolve().parents[2] / 'config/listing-risk-events.json').read_text(encoding='utf-8'))
snapshot_path = Path(__file__).resolve().parents[2] / 'public/data/listing-status.json'
SNAPSHOT = json.loads(snapshot_path.read_text(encoding='utf-8')) if snapshot_path.exists() else {}
TERMINAL = {'termination_decided', 'delisting', 'delisted'}


def listing_risk(stock, as_of='99999999', *, use_snapshot=False):
    code = stock.get('ts_code') or str(stock.get('code', ''))
    known = EVENTS.get(code) or next((v for k, v in EVENTS.items() if k.split('.')[0] == code), None)
    if known and known['published_at'] <= as_of:
        return known
    if use_snapshot and SNAPSHOT.get('as_of', '99999999') <= as_of:
        current = SNAPSHOT.get('stocks', {}).get(code, {})
        stock = {**stock, **current}
    name = str(stock.get('name', '')).strip()
    delist_date = str(stock.get('delist_date') or '')
    if not (len(delist_date) == 8 and delist_date.isdigit()):
        delist_date = ''
    if (stock.get('list_status') == 'D' and (not delist_date or delist_date <= as_of)) or (delist_date.isdigit() and delist_date <= as_of):
        return {'status': 'delisted', 'published_at': delist_date or SNAPSHOT.get('as_of', as_of), 'title': '证券基础信息标记已退市', 'source': {'title': '证券上市状态原始快照', 'url': 'data/listing-status.json'}}
    if name.endswith('退') or name.startswith('退市'):
        return {'status': 'delisting', 'published_at': SNAPSHOT.get('as_of', as_of), 'title': '证券简称包含退市整理标识', 'source': {'title': '证券上市状态原始快照', 'url': 'data/listing-status.json'}}
    if stock.get('listing_status') in TERMINAL:
        return {'status': stock['listing_status'], 'published_at': as_of, 'title': '已确认终止上市或退市状态'}
    return None
