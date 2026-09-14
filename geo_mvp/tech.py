"""站点技术体检：AI 能否顺畅地抓取、理解、引用你的内容。

可离线运行的真实 HTTP 检查：llms.txt、AI 爬虫放行、JSON-LD 结构化数据、sitemap 时效、标题与首段答案块。
"""

from __future__ import annotations

import json
import re

AI_BOTS = {
    "GPTBot": "ChatGPT / OpenAI",
    "PerplexityBot": "Perplexity",
    "ClaudeBot": "Claude / Anthropic",
    "Google-Extended": "Gemini / AI Overviews",
    "CCBot": "Common Crawl（多家模型训练集）",
    "Bytespider": "字节系（豆包）",
    "Baiduspider": "百度（文心）",
}

SCHEMA_KEYS = {
    "Organization": "组织实体（知识图谱对齐）",
    "Article": "文章（作者与时效）",
    "FAQPage": "FAQ（最易被直接抽取）",
    "Product": "产品/服务",
    "BreadcrumbList": "层级与主题聚类",
    "HowTo": "步骤型内容",
}


def audit_site(url: str, timeout: int = 15) -> dict:
    import requests

    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "未填写站点地址", "checks": [], "schema": [], "bots": []}
    if not url.startswith("http"):
        url = "https://" + url
    base = url.rstrip("/")
    ua = {"User-Agent": "Mozilla/5.0 (compatible; GEO-MVP-Audit/1.0)"}

    checks, schema_found, bot_status = [], [], []
    html, err = "", None
    try:
        r = requests.get(base, headers=ua, timeout=timeout)
        html = r.text
        checks.append({"item": "站点可访问", "status": "pass", "detail": f"HTTP {r.status_code}"})
    except Exception as e:
        err = str(e)
        checks.append({"item": "站点可访问", "status": "fail", "detail": err})

    # llms.txt
    try:
        r = requests.get(base + "/llms.txt", headers=ua, timeout=timeout)
        ok = r.status_code == 200 and len(r.text.strip()) > 20
        checks.append({"item": "llms.txt", "status": "pass" if ok else "warn",
                       "detail": "已部署，AI 可读到站点摘要" if ok else "未部署，建议补充站点摘要文件"})
    except Exception as e:
        checks.append({"item": "llms.txt", "status": "warn", "detail": f"无法访问（{e}）"})

    # robots.txt & AI 爬虫
    robots = ""
    try:
        r = requests.get(base + "/robots.txt", headers=ua, timeout=timeout)
        robots = r.text if r.status_code == 200 else ""
        checks.append({"item": "robots.txt", "status": "pass" if robots else "warn",
                       "detail": "已存在" if robots else "未找到"})
    except Exception:
        checks.append({"item": "robots.txt", "status": "warn", "detail": "无法访问"})
    for bot, who in AI_BOTS.items():
        blocked = bool(re.search(rf"User-agent:\s*\*?.*?Disallow:\s*/", robots, re.S)) and bot not in robots
        if bot in robots:
            seg = robots.split(bot, 1)[1][:200]
            blocked = "Disallow" in seg.split("User-agent")[0]
        bot_status.append({"bot": bot, "who": who, "blocked": blocked})

    # JSON-LD
    if html:
        for m in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S):
            try:
                data = json.loads(m.strip())
            except Exception:
                continue
            for obj in (data if isinstance(data, list) else [data]):
                t = obj.get("@type") if isinstance(obj, dict) else None
                for k in (t if isinstance(t, list) else [t]):
                    if k in SCHEMA_KEYS:
                        schema_found.append(k)
        schema_found = sorted(set(schema_found))
        checks.append({"item": "结构化数据 Schema.org",
                       "status": "pass" if schema_found else "warn",
                       "detail": "已部署：" + "、".join(schema_found) if schema_found else "未检测到 JSON-LD，AI 难以理解实体信息"})

        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        checks.append({"item": "标题语义化", "status": "pass" if title else "warn",
                       "detail": (title.group(1).strip()[:60] if title else "未检测到 title")})
        first_p = re.search(r"<p[^>]*>(.*?)</p>", html, re.S | re.I)
        if first_p:
            txt = re.sub(r"<[^>]+>", "", first_p.group(1)).strip()
            checks.append({"item": "首段答案块", "status": "pass" if len(txt) > 30 else "warn",
                           "detail": (txt[:60] + ("…" if len(txt) > 60 else "")) or "首段过短"})
    return {"ok": err is None, "url": base, "checks": checks,
            "schema": schema_found, "bots": bot_status,
            "missing_schema": [k for k in SCHEMA_KEYS if k not in schema_found]}
