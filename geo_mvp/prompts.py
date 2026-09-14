"""测试集（Prompt 题库）构建器。

按五层提问意图生成题库：
  L1 品牌词  L2 品类词  L3 场景词  L4 对比词  L5 长尾决策词
支持规则生成（离线可用）与可选 LLM 扩展（配置 API 后可用）。
"""

from __future__ import annotations

import itertools
import random

LAYERS = {
    "L1": "品牌词（已知品牌，检验 AI 是否认识、是否说对）",
    "L2": "品类词（核心战场：用户不知道你，AI 会不会提到你）",
    "L3": "场景词（用户在具体场景下求助 AI）",
    "L4": "对比词（与竞品的相对位次）",
    "L5": "长尾决策词（风险、流程、新手类疑问）",
}

LAYER_WEIGHT = {"L1": 0.2, "L2": 0.3, "L3": 0.3, "L4": 0.15, "L5": 0.05}


def _tpl_brand(brand: str) -> list[tuple[str, str]]:
    return [
        (f"{brand}怎么样", "品牌整体评价"),
        (f"{brand}是什么公司", "品牌识别"),
        (f"{brand}靠谱吗", "信任度"),
        (f"{brand}口碑如何", "口碑"),
        (f"介绍一下{brand}", "品牌介绍"),
        (f"{brand}的优势和劣势", "优缺点"),
        (f"{brand}值得选吗", "购买建议"),
        (f"{brand}客户服务怎么样", "服务评价"),
    ]


def _tpl_category(industry: str) -> list[tuple[str, str]]:
    return [
        (f"国内{industry}有哪些值得关注的", "品类推荐"),
        (f"{industry}排行榜前十", "品类排名"),
        (f"最好的{industry}有哪些", "品类推荐"),
        (f"推荐几个靠谱的{industry}", "消费级推荐"),
        (f"{industry}行业头部公司有哪些", "行业格局"),
        (f"有哪些新兴的{industry}", "新势力"),
        (f"{industry}哪个品牌口碑最好", "口碑排序"),
        (f"做{industry}的知名企业有哪些", "行业格局"),
    ]


def _tpl_scenario(industry: str, scenarios: list[str]) -> list[tuple[str, str]]:
    base = [
        ("{s}应该选哪家{ind}", "场景选型"),
        ("{s}推荐一下{ind}", "场景推荐"),
        ("{s}需要注意什么{ind}", "场景风险"),
        ("{s}怎么挑选{ind}", "选购方法"),
    ]
    out = []
    if not scenarios:
        scenarios = ["预算有限时", "追求稳健时", "首次尝试时"]
    for s, (tpl, tag) in itertools.product(scenarios, base):
        out.append((tpl.format(s=s, ind=industry), f"{tag}·{s}"))
    return out


def _tpl_compare(brand: str, competitors: list[str]) -> list[tuple[str, str]]:
    out = []
    for c in competitors:
        out.append((f"{brand}和{c}哪个好", f"对比·{c}"))
        out.append((f"{brand}与{c}有什么区别", f"差异·{c}"))
    return out


def _tpl_longtail(brand: str, industry: str) -> list[tuple[str, str]]:
    return [
        (f"选{industry}有哪些常见坑", "风险提示"),
        (f"新手怎么选{industry}", "新手引导"),
        (f"{industry}怎么判断靠不靠谱", "判断标准"),
        (f"为什么有人推荐{brand}", "推荐动因"),
        (f"{industry}的费用一般是多少", "价格认知"),
        (f"{industry}未来趋势如何", "行业趋势"),
    ]


def build_prompts(brand: str, industry: str, competitors: list[str],
                  scenarios: list[str], total: int = 120,
                  seed: int = 42) -> list[dict]:
    """按分层配比生成题库。total 为期望条数，实际按可用模板裁剪。"""
    rnd = random.Random(seed)
    pool: dict[str, list[tuple[str, str]]] = {
        "L1": _tpl_brand(brand),
        "L2": _tpl_category(industry),
        "L3": _tpl_scenario(industry, scenarios),
        "L4": _tpl_compare(brand, competitors),
        "L5": _tpl_longtail(brand, industry),
    }
    items: list[dict] = []
    for layer, lst in pool.items():
        quota = max(4, int(total * LAYER_WEIGHT[layer]))
        rnd.shuffle(lst)
        picked = lst[:quota] if len(lst) <= quota else rnd.sample(lst, quota)
        for text, intent in picked:
            items.append({"layer": layer, "text": text, "intent": intent})
    # 去重
    seen, uniq = set(), []
    for i in items:
        if i["text"] in seen:
            continue
        seen.add(i["text"])
        uniq.append(i)
    return uniq


def to_csv_rows(items: list[dict]) -> list[dict]:
    return [{"层级": i["layer"], "提问": i["text"], "意图": i.get("intent", "")} for i in items]


def parse_manual_prompts(text: str, default_layer: str = "L2") -> list[dict]:
    """从文本框解析用户手写的题库：每行一条，可用 `层级|提问` 前缀。"""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            layer, q = line.split("|", 1)
            layer = layer.strip().upper()
            if layer not in LAYERS:
                layer = default_layer
            out.append({"layer": layer, "text": q.strip(), "intent": "手工导入"})
        else:
            out.append({"layer": default_layer, "text": line, "intent": "手工导入"})
    return out
