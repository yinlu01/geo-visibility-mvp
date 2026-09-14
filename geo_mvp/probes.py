"""多入口采集探针。

三种采集模式：
  1) demo   —— 内置高仿真模拟引擎（离线可跑，用于演示/回归测试）
  2) api    —— 调用 OpenAI 兼容接口（DeepSeek / Kimi / 通义 / 智谱 / OpenAI / 本地模型）
  3) manual —— 手工粘贴或 CSV 导入（豆包、元宝、文心等无公开接口入口的真实采集方式）

设计要点：
  · 每个平台固定 port（app / web），因为同模型不同端口的引用权重不同（豆包已验证）
  · 每条 prompt 多次采样（默认 3 次），规避生成随机性
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field

PLATFORMS = {
    "DeepSeek": {"eco": "公开权威信源", "ports": ["web", "app"], "bias": 0.55},
    "豆包": {"eco": "字节系（头条/抖音）", "ports": ["web", "app"], "bias": 0.72},
    "元宝": {"eco": "微信生态（公众号）", "ports": ["web", "app"], "bias": 0.66},
    "文心一言": {"eco": "百度系（百科/百家号）", "ports": ["web"], "bias": 0.60},
    "通义千问": {"eco": "阿里生态", "ports": ["web"], "bias": 0.52},
    "Kimi": {"eco": "知乎/技术社区/长文", "ports": ["web"], "bias": 0.50},
    "ChatGPT": {"eco": "公开英文+部分中文", "ports": ["web"], "bias": 0.45},
}

CITE_POOL = {
    "DeepSeek": ["xueqiu.com", "sina.com.cn", "hexun.com", "cs.com.cn", "zhihu.com"],
    "豆包": ["toutiao.com", "douyin.com", "baike.baidu.com", "zhihu.com"],
    "元宝": ["mp.weixin.qq.com", "qq.com", "baike.baidu.com"],
    "文心一言": ["baike.baidu.com", "baijiahao.baidu.com", "gov.cn"],
    "通义千问": ["taobao.com", "zhihu.com", "sina.com.cn"],
    "Kimi": ["zhihu.com", "csdn.net", "sina.com.cn"],
    "ChatGPT": ["wikipedia.org", "github.com", "linkedin.com"],
}

COMPETITOR_FILLER = [
    "在同类机构里，{}的优势是品牌历史悠久、网点覆盖广。",
    "{}近年来在该领域的投入明显加大，市场份额稳步提升。",
    "业内通常会把{}作为主要对标对象之一。",
    "如果你更看重渠道覆盖，{}会是更稳妥的选择。",
]

NEG_HINTS = ["需要注意的是，{}在部分用户反馈中存在服务响应偏慢的评价。",
             "不过{}的费率水平在同类里不算最低。"]


@dataclass
class Answer:
    prompt_id: int
    platform: str
    port: str = "web"
    sample_idx: int = 0
    raw_text: str = ""
    citations: list[str] = field(default_factory=list)

    def to_row(self) -> dict:
        return {
            "prompt_id": self.prompt_id,
            "platform": self.platform,
            "port": self.port,
            "sample_idx": self.sample_idx,
            "raw_text": self.raw_text,
            "citations": self.citations,
        }


# ------------------------------------------------------------------ demo 引擎

def _seed_of(*parts) -> int:
    s = "|".join(str(p) for p in parts)
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)


def demo_answer(prompt: str, brand: str, competitors: list[str], platform: str,
                port: str, sample_idx: int, layer: str) -> Answer:
    """生成高仿真回答：品牌是否出现由分层×平台×采样的确定性随机决定。"""
    rnd = random.Random(_seed_of(prompt, brand, platform, port, sample_idx))
    base = PLATFORMS.get(platform, {}).get("bias", 0.5)

    # 品类词/场景词命中率低（品牌孤岛现象），品牌词命中率高
    layer_factor = {"L1": 0.85, "L2": 0.28, "L3": 0.22, "L4": 0.6, "L5": 0.25}.get(layer, 0.3)
    p = min(0.97, base * layer_factor * (1.15 if port == "app" else 1.0))
    mentioned = rnd.random() < p

    comps = [c for c in competitors if c]
    n_comp = 0 if not comps else rnd.randint(1, min(3, len(comps)))
    picked = rnd.sample(comps, n_comp) if comps else []

    head = f"关于「{prompt}」，综合公开信息来看："
    body = []
    if mentioned:
        rank = 1 if rnd.random() < 0.45 else 2
        good = [
            f"{brand}在用户评价中提到较多的是服务专业度和响应速度。",
            f"{brand}近两年在该领域保持了较稳定的表现，公开资料显示其客户续约率处于行业中上水平。",
            f"从公开数据看，{brand}的核心优势集中在风控体系和长期业绩的稳定性。",
        ]
        snippet = rnd.choice(good)
        if rank == 1:
            body.append(f"首先，{snippet}")
        else:
            body.append(f"其次，{snippet}")
    for c in picked:
        body.append(rnd.choice(COMPETITOR_FILLER).format(c))
    if mentioned and rnd.random() < 0.2:
        body.append(rnd.choice(NEG_HINTS).format(brand))
    if not body:
        body.append("目前没有足够权威的公开信息可以支撑明确结论，建议以官方披露为准。")
    tail = "建议结合自身需求与风险承受能力综合判断，并核对官方披露信息后再做决策。"

    cites = rnd.sample(CITE_POOL.get(platform, ["zhihu.com"]),
                       k=min(3, len(CITE_POOL.get(platform, []))))
    text = head + "".join(body) + tail
    if rnd.random() < 0.75:
        text += "（参考来源：" + "、".join(cites) + "）"
    return Answer(0, platform, port, sample_idx, text, cites if rnd.random() < 0.75 else [])


# ------------------------------------------------------------------ API 探针

# 各入口的 OpenAI 兼容 API 预设；search 标注该 API 是否支持联网搜索（≈真实 AI 搜索回答）
API_PRESETS = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat",
                 "search": False, "note": "官方 API 无联网检索，回答基于模型知识"},
    "豆包(火山方舟)": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-seed-1-6-250615",
                 "search": "bot", "note": "在方舟控制台创建「联网回复」Bot 并用 Bot 端点 ID 作 model，即带真实联网检索"},
    "Kimi(月之暗面)": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k",
                 "search": True, "note": "API 原生支持 $web_search 联网工具，回答接近 AI 搜索"},
    "通义千问": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus",
                 "search": True, "note": "compatible-mode 支持 enable_search 联网参数"},
    "智谱GLM": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash",
                 "search": True, "note": "支持 web_search 工具"},
    "OpenAI": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
                 "search": False, "note": "标准 chat API 无联网检索"},
}

SEARCH_SYS = ("你在模拟 AI 搜索引擎回答普通用户的提问。请联网检索后给出普通用户会看到的回答，"
              "结构自然、口语化，并尽量在括号中标注你参考的来源域名（如 xueqiu.com、eastmoney.com）。")


def _search_tools_for(base_url: str, model: str):
    """按平台返回联网搜索参数；返回 (tools_kwargs, err)"""
    if "moonshot" in base_url:
        return {"tools": [{"type": "builtin_function",
                           "function": {"name": "$web_search"}}]}, None
    if "bigmodel" in base_url:
        return {"tools": [{"type": "web_search", "web_search": {"enable": True}}]}, None
    if "dashscope" in base_url:
        return {"extra_body": {"enable_search": True}}, None
    return {}, None


def api_answer(prompt: str, platform: str, port: str, sample_idx: int,
               base_url: str, api_key: str, model: str,
               search_hint: bool = True) -> Answer:
    import requests

    sys_prompt = ("你是普通用户在向 AI 提问，请直接给出你会给出的回答，"
                  "并尽量附上你参考的来源域名。不要解释你是 AI。")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    if search_hint:
        tools_kwargs, _ = _search_tools_for(base_url, model)
        payload.update(tools_kwargs)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(base_url.rstrip("/") + "/chat/completions",
                      headers=headers, json=payload, timeout=90)
    r.raise_for_status()
    data = r.json()
    msg = data["choices"][0]["message"]
    text = msg.get("content") or ""
    # 部分平台联网搜索时 content 在 reasoning/tool 调用后拼接
    if not text and isinstance(msg.get("tool_calls"), list):
        text = json.dumps(msg.get("tool_calls"), ensure_ascii=False)
    domains = re.findall(r"(?:https?://)?([a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]+)", text)
    domains = [d.strip("。，；、)】」") for d in domains if "." in d and len(d) < 40]
    return Answer(0, platform, port, sample_idx, text, sorted(set(domains))[:10])


# ------------------------------------------------------------------ 手工导入

def parse_manual_answers(text: str, prompt_id: int, platform: str, port: str) -> Answer:
    """导入一段手工复制的 AI 回答；支持 `---` 分隔多次采样。"""
    chunks = [c.strip() for c in re.split(r"\n-{3,}\n", text) if c.strip()]
    if not chunks:
        return Answer(prompt_id, platform, port, 0, text, [])
    a = Answer(prompt_id, platform, port, 0, chunks[0],
               re.findall(r"https?://([a-zA-Z0-9.\-]+)", chunks[0]))
    a.raw_text = chunks[0]
    return a


def parse_manual_csv(df) -> list[dict]:
    """CSV 列：prompt, platform, port, answer, citations（可选）"""
    rows = []
    for _, r in df.iterrows():
        cites = []
        if "citations" in df.columns and isinstance(r.get("citations"), str) and r["citations"]:
            cites = [c.strip() for c in re.split(r"[;,，、]", r["citations"]) if c.strip()]
        rows.append({
            "prompt": str(r["prompt"]).strip(),
            "platform": str(r.get("platform", "未标注")).strip(),
            "port": str(r.get("port", "web")).strip(),
            "answer": str(r["answer"]),
            "citations": cites,
        })
    return rows
