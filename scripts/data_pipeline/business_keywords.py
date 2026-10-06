"""Concise business labels tied to the exact source statement, without inferred concepts."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def overrides():
    return json.loads((ROOT / 'config/business-keywords.json').read_text(encoding='utf-8'))


def business_keywords(code: str, text: str) -> list[str]:
    original = text.strip()
    match = overrides().get(code)
    if match and match['source_sha256'] == hashlib.sha256(text.encode()).hexdigest():
        return match['keywords']
    # For new/changed short descriptions only retain source noun phrases before
    # the routine production verbs. Never slice a phrase or reuse stale labels.
    subject = re.split(r'的(?:研发|研究|开发|设计|生产|制造)|研发、|研发设计|产品研发', original)[0]
    subject = re.sub(r'^(?:公司)?(?:主要|专业)?(?:从事|致力于)', '', subject).strip('。；,， ')
    if len(subject) > 36:
        return []
    phrases = [part.strip('。 ') for part in re.split(r'[、,，]', subject) if part.strip('。 ')]
    return phrases if 0 < len(phrases) <= 5 and all(len(part) <= 18 for part in phrases) else []
