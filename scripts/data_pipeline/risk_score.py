"""User-supplied 18-indicator algorithm. Unknown inputs never mean safe.

Tiered scores are alternatives; combinations add to the raw total,
then floors apply. Ratios use decimals, growth differences percentage points.
"""
from __future__ import annotations

import math

MODULES = ("financial", "quality", "regulatory", "liquidity")
LABELS = {"financial": "财务风险", "quality": "财务质量", "regulatory": "审计 / 监管 / 治理", "liquidity": "生存 / 流动性"}


def level(score):
    return next(label for threshold, label in [(90, "HARD AVOID"), (75, "VERY SEVERE"),
                (60, "SEVERE"), (40, "HIGH"), (20, "WATCH"), (0, "CLEAN")] if score >= threshold)


def score_risk(metrics: dict, events: list[dict], as_of: str, *, event_coverage=False) -> dict:
    modules = {key: 0 for key in MODULES}
    triggers, missing, floors = [], [], []
    flags = set()

    def add(module, points, title, key=None, source=None):
        modules[module] += points
        triggers.append({"module": module, "points": points, "title": title,
                         "metric": key, "source": source})

    def value(key):
        v = metrics.get(key)
        if v is None or (isinstance(v, (int, float)) and not math.isfinite(v)):
            missing.append(key)
            return None
        return v

    def floor(points, title, source=None):
        floors.append({"score": points, "title": title, "source": source})

    if metrics.get('listing_status') in ('termination_decided', 'delisting', 'delisted'):
        source = {'title': metrics.get('listing_source_title', '退市状态依据'), 'url': metrics['listing_source_url']} if metrics.get('listing_source_url') else None
        floor(100, metrics.get('listing_risk_title') or '已决定终止上市 / 退市整理 / 已退市', source)

    deducted = value("deducted_net_profit")
    if deducted is not None and deducted < 0:
        add("financial", 8, "年度 / TTM 扣非净利润为负", "deducted_net_profit")
    years = value("consecutive_loss_years")
    if years is not None and years >= 2:
        add("financial", 12 if years >= 3 else 8, f"连续 {years} 年扣非亏损", "consecutive_loss_years")
    ratio = value("revenue_to_st_threshold")
    if ratio is not None and ratio < 1.5:
        add("financial", 15 if ratio < 1.2 else 8, f"年度 / TTM 营收为收入阈值的 {ratio:.2f} 倍", "revenue_to_st_threshold")
        flags.add("near_revenue")
    lowest = value("lowest_profit_metric")
    if (lowest is not None and lowest < 0) or metrics.get("profit_loss_known") is True:
        flags.add("loss")
    # A TTM approximation is an early warning, not formal annual ST evidence.
    if value("annual_st_trigger") is True:
        add("financial", 35, "正式年度 / 业绩预告收入低于阈值且利润孰低为负", "annual_st_trigger")
    growth = value("net_asset_growth")
    if growth is not None and growth < -30:
        add("financial", 8, f"净资产同比下降 {abs(growth):.1f}%", "net_asset_growth")
    negative = value("negative_net_assets")
    if negative is True:
        floor(90, "净资产为负")
    goodwill = value("goodwill_to_equity")
    if goodwill is not None and goodwill > .3:
        add("financial", 10 if goodwill > .5 else 5, f"商誉 / 净资产 {goodwill:.1%}", "goodwill_to_equity")
    cfo_years = value("cfo_negative_years")
    conversion = value("cash_conversion_3y")
    if cfo_years is not None and cfo_years >= 2:
        add("quality", 10 if cfo_years >= 3 else 5, f"经营现金流连续 {cfo_years} 年为负", "cfo_negative_years")
        flags.add("cfo_poor")
    if conversion is not None and conversion < .5:
        add("quality", 8, f"三年累计现金转化率 {conversion:.2f}", "cash_conversion_3y")
        flags.add("cfo_poor")
    ar_growth = value("ar_growth_minus_revenue_growth")
    if ar_growth is not None and ar_growth > 30:
        add("quality", 10 if ar_growth > 50 else 5, f"应收增速高于营收 {ar_growth:.1f} 个百分点", "ar_growth_minus_revenue_growth")
        flags.add("ar_growth")
    # The article supplies no numeric history/peer threshold. Accept verified input only.
    abnormal = value("ar_ratio_abnormal")
    if abnormal is True:
        add("quality", 5, "应收占营收显著高于历史 / 同行", "ar_to_revenue")
    other = value("other_receivables_to_equity")
    if other is not None and other > .1:
        add("quality", 10 if other > .2 else 5, f"其他应收款 / 净资产 {other:.1%}", "other_receivables_to_equity")

    visible, seen = [], set()
    for event in sorted(events, key=lambda e: (e["published_at"], e["id"])):
        if event["published_at"] > as_of or event.get("resolved_at", "99999999") <= as_of or event["id"] in seen:
            continue
        if not event.get("source", {}).get("url"):
            raise ValueError("Risk events require evidence links")
        seen.add(event["id"])
        visible.append(event)
    # Multiple downloads/replies to ONE letter are not second inquiries.
    inquiries = [e for e in visible if e["kind"] == "annual_inquiry"]
    letters = {e.get("letter_id", e["id"]) for e in inquiries}
    severe = any(e.get("severity") == "severe" for e in inquiries)
    if inquiries:
        classified = [e for e in inquiries if e.get("severity") in ("ordinary", "severe")]
        if len(classified) < len(inquiries):
            missing.append("inquiry_severity")
        if classified:
            e = next((e for e in classified if e.get("severity") == "severe"), classified[0])
            add("regulatory", 15 if severe else 5, e["title"], source=e["source"])
        if severe:
            flags.add("severe_inquiry")
    if len(letters) >= 2 or any(e["kind"] == "second_inquiry" for e in visible):
        e = next((e for e in visible if e["kind"] == "second_inquiry"), None)
        if e is None:
            e = inquiries[-1]
        add("regulatory", 10, "二次年报问询", source=e["source"])
        flags.add("second_inquiry")
    # Audit opinion uses latest published opinion, not an obsolete adverse opinion forever.
    for kind in ("audit_opinion", "internal_control_opinion"):
        opinions = [e for e in visible if e["kind"] == kind]
        if opinions:
            e = opinions[-1]
            if e.get("opinion") in ("adverse", "disclaimer"):
                if kind == "audit_opinion":
                    floor(90, e["title"], e["source"])
                else:
                    add("regulatory", 30, e["title"], source=e["source"])
                    floor(70, e["title"], e["source"])
                    flags.add("internal_abnormal")
            elif kind == "internal_control_opinion" and e.get("opinion") == "qualified":
                flags.add("internal_abnormal")
    for kind in ("csrc_investigation", "fund_occupation", "illegal_guarantee", "debt_overdue", "bank_freeze", "confirmed_fraud"):
        selected = [e for e in visible if e["kind"] == kind]
        if not selected:
            continue
        # Category scores once; distinct inquiry stages are scored separately above.
        e = selected[-1]
        source = e["source"]
        if kind == "csrc_investigation":
            add("regulatory", 35, e["title"], source=source)
            flags.add("csrc")
            if e.get("scope") in ("financial", "disclosure"):
                floor(70, "财务 / 信披问题立案：最低70分", source)
        elif kind in ("fund_occupation", "illegal_guarantee"):
            points = e.get("points")
            if points is None:
                missing.append("governance_points_25_to_40")
            elif not 25 <= points <= 40:
                raise ValueError("Governance points must be 25–40")
            if points is not None:
                add("regulatory", points, e["title"], source=source)
            if kind == "fund_occupation":
                flags.add("fund_occupation")
                if e.get("equity_ratio") is None:
                    missing.append("fund_occupation_equity_ratio")
                if e.get("major") is True or (e.get("equity_ratio") is not None and e["equity_ratio"] > .1):
                    floor(75, "重大资金占用" if e.get("major") is True else "资金占用超过净资产10%", source)
        elif kind == "debt_overdue":
            add("liquidity", 20, e["title"], source=source)
        elif kind == "bank_freeze":
            if e.get("major_account") is True:
                floor(80, "主要银行账户被冻结", source)
            elif e.get("major_account") is None:
                missing.append("freeze_major_account")
        else:
            floor(100, "明确财务造假", source)
    cash = None if metrics.get("no_short_debt") is True else value("cash_to_short_debt")
    interest = None if metrics.get("no_interest_expense") is True else value("interest_coverage")
    if cash is not None and cash < .5:
        add("liquidity", 8, f"现金 / 短债 {cash:.4f} 倍（低于0.5）", "cash_to_short_debt")
    if interest is not None and interest < 1.5:
        add("liquidity", 5, f"利息保障 {interest:.2f} 倍", "interest_coverage")
    combinations = []
    for left, right, points, title in [
        ("severe_inquiry", "second_inquiry", 10, "严重问询 + 二次问询"),
        ("severe_inquiry", "csrc", 15, "严重问询 + 证监会立案"),
        ("internal_abnormal", "fund_occupation", 15, "内控异常 + 资金占用"),
        ("cfo_poor", "ar_growth", 10, "现金流差 + 应收异常增长"),
        ("loss", "near_revenue", 15, "亏损 + 营收接近收入阈值")]:
        if {left, right} <= flags:
            combinations.append({"points": points, "title": title})
    if not event_coverage:
        missing.append("announcement_coverage")
    raw = sum(modules.values())
    combo = sum(c["points"] for c in combinations)
    risk_floor = max((f["score"] for f in floors), default=0)
    score = round(min(100, max(raw + combo, risk_floor)), 2)
    return {"score": score, "level": level(score), "complete": not missing,
            "modules": [{"key": k, "label": LABELS[k], "score": modules[k]} for k in modules],
            "raw_score": raw, "combination_points": combo, "floor": risk_floor,
            "triggers": triggers, "combinations": combinations, "floors": floors,
            "missing": sorted(set(missing)), "latest_warning": max((e["published_at"] for e in visible
            if e["kind"] not in ("audit_opinion", "internal_control_opinion") or e.get("opinion") != "standard"), default=None)}
