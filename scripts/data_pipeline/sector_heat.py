"""Sina concept market snapshot; strength is latest-session return, not news sentiment."""
import json
import math
import re

import requests

URL = 'https://money.finance.sina.com.cn/q/view/newFLJK.php?param=class'
SOURCE = 'https://vip.stock.finance.sina.com.cn/mkt/frames/sl_bk.html'


def parse_concept_quotes(text):
    payload = json.loads(text.split('=', 1)[1].strip().rstrip(';'))
    rows = []
    for value in payload.values():
        fields = value.split(',')
        if len(fields) < 9 or not fields[0].startswith('gn_'):
            continue
        try:
            change, amount = float(fields[5]), float(fields[7])
        except ValueError:
            continue
        if '\ufffd' in fields[1] or not fields[1] or not math.isfinite(change) or not math.isfinite(amount) or amount <= 0:
            continue
        rows.append({'name': fields[1], 'return_pct': change, 'amount_yi': amount / 100_000_000, 'leader': fields[8]})
    if len(rows) < 20:
        raise ValueError('Incomplete concept market snapshot')
    rows.sort(key=lambda row: (-row['return_pct'], -row['amount_yi'], row['name']))
    cutoff = max(1, math.ceil(len(rows) * .2))
    return {row['name']: {'rank': rank, 'return_pct': row['return_pct'], 'amount_yi': row['amount_yi'],
                         'hot': rank <= cutoff and row['return_pct'] > 0}
            for rank, row in enumerate(rows, 1)}, [row['leader'] for row in rows[:3]]


def quote_dates(text):
    dates = re.findall(r',([0-9]{4}-[0-9]{2}-[0-9]{2}),[0-9]{2}:[0-9]{2}:[0-9]{2},', text)
    if len(dates) != 3 or len(set(dates)) != 1:
        raise ValueError('Market reference dates unavailable or inconsistent')
    return dates[0]


def collect_heat(as_of):
    try:
        response = requests.get(URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        response.raise_for_status()
        concepts, leaders = parse_concept_quotes(response.content.decode('gb18030'))
        response = requests.get('https://hq.sinajs.cn/list=' + ','.join(leaders),
                                headers={'Referer': 'https://finance.sina.com.cn/'}, timeout=15)
        response.raise_for_status()
        trade_date = quote_dates(response.content.decode('gb18030'))
        if trade_date > as_of:
            raise ValueError('Future market date')
        return {'status': 'ok', 'trade_date': trade_date, 'source_url': SOURCE, 'concepts': concepts,
                'method': '最新交易日板块涨幅降序，成交额同值次序；正涨幅且排名前20%为热点候选'}
    except (requests.RequestException, ValueError, KeyError, IndexError, UnicodeError):
        return {'status': 'unavailable', 'source_url': SOURCE, 'concepts': {}}
