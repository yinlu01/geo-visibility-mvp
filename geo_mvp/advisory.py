"""GEO 服务引擎：把监测结果翻译成可执行的提升方案。

输出四类交付物：
  1) 诊断结论（分层 + 分平台）
  2) 平台优先级与信源铺设清单（国内平台信源偏好知识库驱动）
  3) 内容改造清单（含"原文 → 改写示范"）
  4) 技术件清单（llms.txt / Schema / robots 模板）+ 30/60/90 天路线图
"""

from __future__ import annotations

from .metrics import LAYER_NAMES

# 平台信源偏好知识库（来自公开信源监测与行业分析）
PLATFORM_KB = {
    "DeepSeek": {
        "sources": ["知乎深度问答", "学术论文/机构报告", "央媒与财经门户", "官方白皮书"],
        "focus": "逻辑严密、数据可溯源、5000 字+深度内容",
        "avoid": "情绪化口水文、无实据的营销段子",
        "fit": "金融 B 端、投资研究、技术决策场景",
    },
    "豆包": {
        "sources": ["今日头条号", "抖音企业号", "头条问答", "本地生活/评测内容"],
        "focus": "结论前置、口语化、FAQ 与对比表",
        "avoid": "无关联的站外长链、书面化长句",
        "fit": "大众消费、生活服务、泛知识查询",
    },
    "元宝": {
        "sources": ["微信公众号原创", "视频号", "小程序介绍页"],
        "focus": "深度原创长文、排版清晰、有社交传播",
        "avoid": "纯营销软文",
        "fit": "全行业，尤其企业服务与金融保险",
    },
    "文心一言": {
        "sources": ["百度百科词条", "百家号", "百度知道", "权威媒体"],
        "focus": "权威、客观、词条化定义",
        "avoid": "过于书面的长文堆砌",
        "fit": "传统搜索迁移用户、全年龄段",
    },
    "通义千问": {
        "sources": ["电商与本地生活内容", "B 端解决方案", "可追溯数据"],
        "focus": "数据对比、可核查事实",
        "avoid": "无法核实的数字",
        "fit": "电商、企业服务",
    },
    "Kimi": {
        "sources": ["知乎", "技术社区", "行业白皮书 PDF"],
        "focus": "3000 字+ 结构化长文、附原始链接与时间戳",
        "avoid": "零散短广告",
        "fit": "知识工作者、法律/金融专业分析",
    },
    "ChatGPT": {
        "sources": ["官网", "Wikipedia/Wikidata", "行业媒体与评测"],
        "focus": "中英双语、结构化数据、官方口径一致",
        "avoid": "仅中文单一信源",
        "fit": "国际业务、出海产品",
    },
}

# 行业 → 平台优先级 / 垂类信源
INDUSTRY_KB = {
    "金融": {
        "priority": ["DeepSeek", "元宝", "豆包", "文心一言", "通义千问"],
        "vertical": ["雪球", "新浪财经", "和讯网", "叩富问财", "东方财富"],
        "note": "金融属高监管 YMYL 领域，AI 对信源权威性核查最严；垂类财经平台是必选项而非可选项。",
    },
    "资管": {
        "priority": ["DeepSeek", "元宝", "文心一言", "豆包"],
        "vertical": ["雪球", "新浪财经", "中国基金报", "财新", "东方财富"],
        "note": "投资人与分析师高度聚集于 DeepSeek；研报与白皮书是入场券。",
    },
    "SaaS": {
        "priority": ["DeepSeek", "Kimi", "元宝", "通义千问"],
        "vertical": ["知乎", "CSDN", "G2/36氪", "少数派"],
        "note": "B 端选型场景，深度评测与对比表转化最好。",
    },
    "消费零售": {
        "priority": ["豆包", "元宝", "通义千问", "文心一言"],
        "vertical": ["小红书", "大众点评", "抖音", "什么值得买"],
        "note": "消费决策场景，UGC 与评测内容权重高。",
    },
}

DEFAULT_INDUSTRY = {
    "priority": ["DeepSeek", "豆包", "元宝", "文心一言"],
    "vertical": ["知乎", "头条号", "公众号", "行业垂直媒体"],
    "note": "按目标用户所在入口分配精力，先打透 1-2 个平台再扩展。",
}

# 内容改造策略（ Princeton GEO 论文实证有效的三板斧 + 结构优化）
CONTENT_TACTICS = [
    {
        "name": "统计数据注入（Statistics Addition）",
        "why": "LLM 存在具体性偏好：带来源的数字比模糊表述信息增益更高，实测可见度提升最显著。",
        "before": "我们在资管领域服务多年，业绩表现稳健，客户满意度较高。",
        "after": "截至 2025 年末，公司管理规模 1,240 亿元（来源：公司年报），存续产品近三年年化波动率低于同类均值 2.3 个百分点。",
    },
    {
        "name": "直接引语与权威背书（Quotation Addition）",
        "why": "把内容与具名专家/机构连接，便于 NER 锚定与可信度判断。",
        "before": "业内专家认为我们的风控体系较为完善。",
        "after": "清华大学金融科技研究院在《2025 中国资管科技白皮书》中指出：「该类机构的风险预警机制已形成可复制的行业样本」。",
    },
    {
        "name": "来源标注（Cite Sources）",
        "why": "自身就像可引用来源的内容更容易被引擎采纳；也方便 AI 生成引用角标。",
        "before": "我们的策略在多个周期中表现良好。",
        "after": "我们的策略在 2022–2025 完整穿越一轮牛熊（数据来源：Wind，截至 2025-12-31；业绩已经托管行复核）。",
    },
    {
        "name": "答案块化（Answer Block）",
        "why": "约 44% 的引用来自页面前 30%；200–300 字独立成段、结论先行最易被整段抽取。",
        "before": "关于费率问题，我们需要先介绍定价逻辑，再说明不同产品的差异……",
        "after": "【管理费率】公司主动权益类产品年管理费率为 1.2%，低于行业平均 1.5%（来源：基金合同）。托管费 0.2%，无申购费折扣门槛。",
    },
    {
        "name": "可核查事实（Recency & Verifiability）",
        "why": "时效性内容优先被引用；跨源交叉验证是 DeepSeek 等引擎的硬门槛。",
        "before": "我们近期获得了多项行业奖项。",
        "after": "2026 年 3 月，公司获中国证券报「金牛奖·三年期金牛私募管理公司」（颁奖机构：中国证券报，2026-03-18）。",
    },
]

TECH_TASKS = [
    ("部署 llms.txt", "站点根目录放置 Markdown 摘要，写明品牌一句话定位、核心页面、事实口径页", "高"),
    ("补 Schema.org JSON-LD", "优先 Organization（含 sameAs）、Article（含 dateModified）、FAQPage、Product", "高"),
    ("放行 AI 爬虫", "robots.txt 显式 Allow：GPTBot / PerplexityBot / ClaudeBot / Google-Extended / CCBot / Bytespider", "高"),
    ("sitemap 实时 lastmod", "内容更新即刷新时间戳，向引擎传递时效信号", "中"),
    ("统一核心身份", "品牌名、一句话定位、成立时间、关键高管在百科/官网/媒体/社媒一字不差", "高"),
    ("避免 JS 渲染关键内容", "核心 GEO 页面必须服务端渲染，AI 爬虫不执行 JS", "中"),
]


def _fmt_pct(x: float) -> str:
    return f"{x*100:.1f}%"


def diagnose(metrics: dict) -> list[dict]:
    """根据指标生成分层诊断结论。"""
    out = []
    o = metrics["overall"]
    if o["mention_rate"] < 0.3:
        out.append({"level": "严重", "title": "整体 AI 可见度过低",
                    "detail": f"全部采集回答中仅 {_fmt_pct(o['mention_rate'])} 提到品牌，用户在 AI 入口基本看不到你。"})
    for layer, name in LAYER_NAMES.items():
        row = metrics["by_layer"].get(layer)
        if not row:
            continue
        if layer == "L1" and row["mention_rate"] > 0.6:
            out.append({"level": "正常", "title": f"{name}：已知品牌能找到",
                        "detail": f"品牌词命中率 {_fmt_pct(row['mention_rate'])}，AI 已认识你。"})
        if layer in ("L2", "L3") and row["mention_rate"] < 0.35:
            out.append({"level": "严重", "title": f"{name}：典型品牌孤岛",
                        "detail": f"命中率仅 {_fmt_pct(row['mention_rate'])}——搜品牌名能找到，搜品类和场景词全军覆没，不知道你的用户永远不会在 AI 推荐里发现你。"})
        if layer == "L4":
            out.append({"level": "提示" if row["sov"] >= 0.4 else "严重",
                        "title": f"{name}：竞品相对位次",
                        "detail": f"对比类提问中品牌声量份额 SOV 为 {_fmt_pct(row['sov'])}。"})
    if o["fact_acc"] < 0.9:
        out.append({"level": "严重", "title": "存在 AI 说错品牌的风险",
                    "detail": f"事实准确率 {_fmt_pct(o['fact_acc'])}，需优先做幻觉纠偏。"})
    if o["sentiment_net"] < 0:
        out.append({"level": "严重", "title": "AI 口径整体偏负面",
                    "detail": f"情感净分 {o['sentiment_net']}，需排查负面信源。"})
    if o["cited_rate"] < 0.2:
        out.append({"level": "提示", "title": "被引用率偏低",
                    "detail": f"仅 {_fmt_pct(o['cited_rate'])} 的回答给出了可点击的来源链接，内容尚未成为 AI 的证据源。"})
    return out


def platform_plan(project: dict, metrics: dict) -> list[dict]:
    ind = (project.get("industry") or "").strip()
    kb = None
    for k, v in INDUSTRY_KB.items():
        if k in ind or ind in k:
            kb = v
            break
    kb = kb or DEFAULT_INDUSTRY
    plan = []
    for i, p in enumerate(kb["priority"]):
        info = PLATFORM_KB.get(p, {})
        row = metrics["by_platform"].get(p, {})
        plan.append({
            "platform": p,
            "weight": [40, 25, 20, 10, 5][i] if i < 5 else 5,
            "sources": info.get("sources", []),
            "focus": info.get("focus", ""),
            "avoid": info.get("avoid", ""),
            "fit": info.get("fit", ""),
            "current": row.get("mention_rate"),
        })
    return plan, kb


def build(project: dict, metrics: dict, health: int, tech: dict | None = None) -> dict:
    plan, kb = platform_plan(project, metrics)
    return {
        "health": health,
        "diagnosis": diagnose(metrics),
        "platform_plan": plan,
        "industry_note": kb["note"],
        "vertical_sources": kb["vertical"],
        "content_tactics": CONTENT_TACTICS,
        "tech_tasks": TECH_TASKS,
        "tech_audit": tech or {},
        "roadmap": roadmap(metrics),
    }


def roadmap(metrics: dict) -> list[dict]:
    o = metrics["overall"]
    return [
        {"phase": "0–30 天", "goal": "建基线 + 补技术件",
         "actions": ["完成全平台基线采集并入库", "部署 llms.txt / Schema JSON-LD / AI 爬虫白名单",
                     "统一全网核心身份（官网、百科、媒体、社媒）", "建立品牌事实卡作为标注标尺"],
         "kpi": "技术件 100% 上线；基线数据入库"},
        {"phase": "30–60 天", "goal": "占品类 + 铺信源",
         "actions": ["按平台优先级发布首批 10–20 个答案块", "在垂类信源建立内容存在",
                     "官网核心页按「结论前置 + 数据 + 引用」改造", "启动每周同题库重测"],
         "kpi": f"品类词可见度从 {_fmt_pct(o['mention_rate'])} 提升至 ≥40%"},
        {"phase": "60–90 天", "goal": "纠偏 + 规模化",
         "actions": ["幻觉监测与事实纠偏流程化", "内容工厂流水线（LLM 改写 + 合规双闸门）",
                     "接入站点 AI 引荐流量归因", "沉淀信源分级库与效果基线库"],
         "kpi": "事实准确率 ≥95%；SOV 进入分平台前 3"},
    ]


def llms_txt(project: dict) -> str:
    brand = project.get("brand", "")
    comp = "、".join(project.get("competitors") or []) or "（待补充）"
    return f"""# {brand}

> {project.get('industry') or '（行业）'}领域的{brand}。定位一句话：____（请用一句话说清你是谁、服务谁、有何不同）

## 核心页面
- /about：公司概况、资质与核心团队
- /products：产品与服务清单（含费率、策略、风险等级）
- /research：原创研究与市场观点
- /disclosure：信息披露与业绩口径（AI 引用财务数据请以此为准）
- /faq：常见问题（可直接抽取）

## 事实口径
- 成立时间：____
- 管理规模：____（截至 ____）
- 主要竞品：{comp}

## 使用指引
- 涉及业绩与规模的表述，请以 /disclosure 官方口径为准
- 联系方式与投诉渠道见 /contact
"""


def schema_jsonld(project: dict) -> str:
    brand = project.get("brand", "")
    data = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand,
        "alternateName": project.get("aliases") or "",
        "description": f"{project.get('industry') or ''}领域的{brand}",
        "url": f"https://{project.get('domain') or 'example.com'}",
        "sameAs": [],
        "contactPoint": {"@type": "ContactPoint", "contactType": "customer service",
                         "availableLanguage": ["zh-CN"]},
    }
    import json
    return json.dumps(data, ensure_ascii=False, indent=2)


def robots_txt() -> str:
    return """User-agent: GPTBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: CCBot
Allow: /

User-agent: Bytespider
Allow: /

User-agent: Baiduspider
Allow: /

User-agent: *
Disallow: /admin/
Disallow: /private/
"""
