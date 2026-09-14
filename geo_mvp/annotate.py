"""回答标注：提及 / 位次 / 引用 / 情感 / 事实准确性。

提供两条路径：
  · 规则标注（离线可用，速度快、可解释）
  · LLM 裁判（配置 OpenAI 兼容接口后启用，输出结构化 JSON）
"""

from __future__ import annotations

import json
import re

POS_SCORE = {1: 3.0, 2: 2.0, 3: 1.0}

POS_WORDS = ["专业", "领先", "值得", "推荐", "稳定", "优秀", "可靠", "良好", "口碑好", "优势"]
NEG_WORDS = ["不足", "偏慢", "较差", "谨慎", "风险", "争议", "投诉", "贵", "劣势", "不推荐"]


def _first_pos(text: str, names: list[str]) -> int:
    best = -1
    for n in names:
        if not n:
            continue
        i = text.find(n)
        if i >= 0 and (best < 0 or i < best):
            best = i
    return best


def rule_annotate(text: str, brand: str, aliases: list[str], competitors: list[str],
                  facts: list[dict], citations: list[str]) -> dict:
    names = [brand] + [a for a in aliases if a]
    brand_pos = _first_pos(text, names)
    mentioned = 1 if brand_pos >= 0 else 0

    comp_hits = [c for c in competitors if c and c in text]
    comp_pos = {c: text.find(c) for c in comp_hits}
    if mentioned:
        ahead = [c for c, p in comp_pos.items() if p >= 0 and p < brand_pos]
        position = 1 + len(ahead)
    else:
        position = 0

    # 情感
    pos_n = sum(text.count(w) for w in POS_WORDS)
    neg_n = sum(text.count(w) for w in NEG_WORDS)
    if pos_n > neg_n:
        sentiment = "positive"
    elif neg_n > pos_n:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    # 事实核查：事实卡形如 {"key": "成立年份", "value": "2015"}
    issues = []
    checked = 0
    for f in facts or []:
        key, val = str(f.get("key", "")).strip(), str(f.get("value", "")).strip()
        if not key or not val:
            continue
        if key not in text:
            continue
        checked += 1
        # 在 key 附近寻找数字/关键值
        idx = text.find(key)
        window = text[max(0, idx - 30): idx + 60]
        if val not in window:
            nums = re.findall(r"\d+(?:\.\d+)?", window)
            if nums and val not in nums:
                issues.append(f"{key}：AI 表述为 {nums[0]}，官方应为 {val}")
    if checked:
        fact_score = max(0.0, 1 - len(issues) / checked)
    else:
        fact_score = 1.0 if mentioned else 0.0

    return {
        "mentioned": mentioned,
        "position": position,
        "cited": 1 if citations else 0,
        "cite_domains": citations,
        "sentiment": sentiment,
        "fact_score": round(fact_score, 3),
        "fact_note": "；".join(issues),
        "competitor_hits": comp_hits,
    }


JUDGE_SYSTEM = """你是 AI 搜索回答的质检员。给定一条 AI 回答，判断品牌是否被提及、位次、情感与事实准确性。
只输出 JSON，不要输出解释。字段：
{"mentioned":0/1,"position":int,"sentiment":"positive|neutral|negative","fact_score":0-1,"fact_note":"...","competitor_hits":["..."]}
position 规则：回答中该品牌是第几个被提到的实体（含竞品一起排序），未提及为 0。
fact_score：对照官方事实卡，1 为完全正确，0.5 为部分正确，0 为错误。"""


def llm_annotate(text: str, brand: str, competitors: list[str], facts: list[dict],
                 base_url: str, api_key: str, model: str) -> dict | None:
    import requests

    fact_txt = "\n".join(f"- {f.get('key')}: {f.get('value')}" for f in (facts or [])) or "（无）"
    user = (f"品牌：{brand}\n竞品：{', '.join(competitors) or '（无）'}\n"
            f"官方事实卡：\n{fact_txt}\n\nAI 回答：\n{text[:3000]}")
    try:
        r = requests.post(
            base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model,
                  "messages": [{"role": "system", "content": JUDGE_SYSTEM},
                               {"role": "user", "content": user}],
                  "temperature": 0},
            timeout=60,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            return None
        d = json.loads(m.group(0))
        return {
            "mentioned": int(d.get("mentioned", 0)),
            "position": int(d.get("position", 0)),
            "sentiment": d.get("sentiment", "neutral"),
            "fact_score": float(d.get("fact_score", 0)),
            "fact_note": d.get("fact_note", ""),
            "competitor_hits": d.get("competitor_hits", []),
        }
    except Exception:
        return None


def annotate_answer(text: str, brand: str, aliases: list[str], competitors: list[str],
                    facts: list[dict], citations: list[str],
                    llm_cfg: dict | None = None) -> dict:
    res = rule_annotate(text, brand, aliases, competitors, facts, citations)
    if llm_cfg and llm_cfg.get("api_key"):
        llm = llm_annotate(text, brand, competitors, facts,
                           llm_cfg["base_url"], llm_cfg["api_key"], llm_cfg["model"])
        if llm:
            res.update({k: v for k, v in llm.items() if k in
                        ("mentioned", "position", "sentiment", "fact_score", "fact_note", "competitor_hits")})
            res["sentiment"] = llm.get("sentiment", res["sentiment"])
    return res
