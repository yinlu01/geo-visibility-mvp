"""指标聚合：可见度 / 引用率 / 位置加权分 / 情感净分 / 事实准确率 / SOV。"""

from __future__ import annotations

from collections import defaultdict

from .annotate import POS_SCORE

LAYER_NAMES = {
    "L1": "品牌词", "L2": "品类词", "L3": "场景词", "L4": "对比词", "L5": "长尾词",
}


def _agg(rows: list[dict]) -> dict:
    n = len(rows) or 1
    mentioned = sum(r.get("mentioned") or 0 for r in rows)
    cited = sum(r.get("cited") or 0 for r in rows)
    pos_score = sum(POS_SCORE.get(r.get("position") or 0, 0.0) for r in rows)
    pos_score += sum(0.5 for r in rows if (r.get("position") or 0) > 3)
    brand_hits = mentioned
    comp_hits = sum(len(r.get("competitor_hits") or []) for r in rows)
    sent = defaultdict(int)
    for r in rows:
        sent[r.get("sentiment") or "neutral"] += 1
    fact = [r.get("fact_score") for r in rows if r.get("fact_score") is not None]
    return {
        "n": len(rows),
        "mention_rate": round(mentioned / n, 4),
        "cited_rate": round(cited / n, 4),
        "position_score": round(pos_score / n, 3),
        "sov": round(brand_hits / (brand_hits + comp_hits), 4) if (brand_hits + comp_hits) else 0.0,
        "sentiment_net": round((sent["positive"] - sent["negative"]) / n, 4),
        "fact_acc": round(sum(fact) / len(fact), 4) if fact else 0.0,
        "sent_break": dict(sent),
    }


def compute(answers: list[dict]) -> dict:
    """answers: list_answers() 的返回（已含标注字段）。"""
    overall = _agg(answers)
    by_layer, by_platform = {}, {}
    for layer in LAYER_NAMES:
        rows = [a for a in answers if a.get("layer") == layer]
        if rows:
            by_layer[layer] = _agg(rows)
    for p in sorted({a.get("platform") for a in answers}):
        rows = [a for a in answers if a.get("platform") == p]
        by_platform[p] = _agg(rows)

    dom = defaultdict(int)
    for a in answers:
        for d in a.get("cite_domains") or []:
            dom[d] += 1
    top_domains = sorted(dom.items(), key=lambda x: -x[1])[:15]

    comp = defaultdict(int)
    for a in answers:
        for c in a.get("competitor_hits") or []:
            comp[c] += 1
    top_competitors = sorted(comp.items(), key=lambda x: -x[1])[:10]

    risk = [a for a in answers if (a.get("fact_note") or "") or (a.get("sentiment") == "negative")]
    return {
        "overall": overall,
        "by_layer": by_layer,
        "by_platform": by_platform,
        "top_domains": top_domains,
        "top_competitors": top_competitors,
        "risk_items": risk[:30],
    }


def health_score(m: dict) -> int:
    """0-100 综合健康分：可见度 40% + SOV 25% + 事实准确 20% + 情感 15%。"""
    o = m["overall"]
    s = (o["mention_rate"] * 40 + o["sov"] * 25 + o["fact_acc"] * 20
         + max(0.0, (o["sentiment_net"] + 1) / 2) * 15)
    return int(round(max(0, min(100, s))))
