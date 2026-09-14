"""HTML 诊断报告生成（可交付客户的正式报告）。"""

from __future__ import annotations

import os
from datetime import datetime
from html import escape

from jinja2 import Template

from .metrics import LAYER_NAMES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

TPL = Template("""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ project.brand }} · AI 可见性诊断报告</title>
<style>
 body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;color:#1a1d24;background:#fdfdfb;
      line-height:1.75;margin:0;font-size:15px}
 .wrap{max-width:960px;margin:0 auto;padding:44px 40px 70px}
 h1{font-size:27px;margin:0 0 8px}
 h2{font-size:20px;margin:38px 0 14px;border-left:4px solid #2f5fd0;padding-left:12px}
 h3{font-size:16px;margin:22px 0 8px}
 table{width:100%;border-collapse:collapse;margin:14px 0 20px;font-size:13.5px}
 th{background:#1a1d24;color:#fff;padding:9px 11px;text-align:left}
 td{padding:9px 11px;border-bottom:1px solid #e6e8ee;vertical-align:top}
 tr:nth-child(even) td{background:#fafbfd}
 .hero{border-bottom:3px solid #1a1d24;padding-bottom:22px;margin-bottom:28px}
 .kicker{font-size:12px;letter-spacing:3px;color:#2f5fd0;font-weight:700}
 .meta{font-size:12.5px;color:#8a90a0}
 .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}
 .card{border:1px solid #e6e8ee;border-radius:10px;padding:16px;background:#fff}
 .card .k{font-size:12px;color:#8a90a0}
 .card .v{font-size:26px;font-weight:700;color:#2f5fd0}
 .bar{height:9px;background:#eef1f7;border-radius:5px;overflow:hidden;margin-top:8px}
 .bar i{display:block;height:100%;background:#2f5fd0}
 .callout{border-left:4px solid #c0392b;background:#fdeeec;padding:14px 18px;border-radius:0 8px 8px 0;margin:14px 0}
 .callout.b{border-color:#2f5fd0;background:#eef3fd}
 .callout.g{border-color:#1e7a4f;background:#eaf6f0}
 .tag{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 9px;border-radius:999px;margin-right:6px}
 .tag.r{background:#fdeeec;color:#c0392b}.tag.b{background:#eef3fd;color:#2f5fd0}
 .tag.y{background:#fdf6e3;color:#b8860b}.tag.g{background:#eaf6f0;color:#1e7a4f}
 pre{background:#f4f6fa;border:1px solid #e6e8ee;border-radius:8px;padding:14px 16px;overflow-x:auto;font-size:12px}
 code{background:#f4f6fa;padding:1px 5px;border-radius:4px;font-size:12.5px}
 ol,ul{padding-left:22px}
 .small{font-size:12.5px;color:#8a90a0}
</style></head><body><div class="wrap">

<div class="hero">
  <div class="kicker">AI VISIBILITY DIAGNOSIS</div>
  <h1>{{ project.brand }} · AI 可见性诊断与 GEO 提升方案</h1>
  <div class="meta">行业：{{ project.industry or '—' }} ｜ 采集批次：{{ run.name }}（{{ run.mode }}）｜
  平台：{{ run.platforms|join('、') }} ｜ 样本量：{{ metrics.overall.n }} 条 ｜ 生成时间：{{ now }}</div>
</div>

<h2>一、总体结论</h2>
<div class="cards">
  <div class="card"><div class="k">AI 可见度健康分</div><div class="v">{{ health }}</div>
    <div class="bar"><i style="width:{{ health }}%"></i></div></div>
  <div class="card"><div class="k">品牌提及率</div><div class="v">{{ (metrics.overall.mention_rate*100)|round(1) }}%</div>
    <div class="bar"><i style="width:{{ (metrics.overall.mention_rate*100)|round(1) }}%"></i></div></div>
  <div class="card"><div class="k">声量份额 SOV</div><div class="v">{{ (metrics.overall.sov*100)|round(1) }}%</div>
    <div class="bar"><i style="width:{{ (metrics.overall.sov*100)|round(1) }}%"></i></div></div>
  <div class="card"><div class="k">被引用率</div><div class="v">{{ (metrics.overall.cited_rate*100)|round(1) }}%</div></div>
  <div class="card"><div class="k">事实准确率</div><div class="v">{{ (metrics.overall.fact_acc*100)|round(1) }}%</div></div>
  <div class="card"><div class="k">情感净分</div><div class="v">{{ (metrics.overall.sentiment_net*100)|round(1) }}</div></div>
</div>

{% for d in advisory.diagnosis %}
<div class="callout {% if d.level=='严重' %}''{% elif d.level=='提示' %}b{% else %}g{% endif %}">
  <span class="tag {% if d.level=='严重' %}r{% elif d.level=='提示' %}b{% else %}g{% endif %}">{{ d.level }}</span>
  <strong>{{ d.title }}</strong>：{{ d.detail }}
</div>
{% endfor %}

<h2>二、分层表现</h2>
<table><tr><th>提问层级</th><th>样本</th><th>提及率</th><th>SOV</th><th>位置分</th><th>被引用率</th><th>事实准确率</th></tr>
{% for l, r in metrics.by_layer.items() %}
<tr><td>{{ LAYER_NAMES[l] }}（{{ l }}）</td><td>{{ r.n }}</td>
<td>{{ (r.mention_rate*100)|round(1) }}%</td><td>{{ (r.sov*100)|round(1) }}%</td>
<td>{{ r.position_score }}</td><td>{{ (r.cited_rate*100)|round(1) }}%</td><td>{{ (r.fact_acc*100)|round(1) }}%</td></tr>
{% endfor %}</table>

<h2>三、分平台表现</h2>
<table><tr><th>AI 入口</th><th>样本</th><th>提及率</th><th>SOV</th><th>被引用率</th></tr>
{% for p, r in metrics.by_platform.items() %}
<tr><td>{{ p }}</td><td>{{ r.n }}</td><td>{{ (r.mention_rate*100)|round(1) }}%</td>
<td>{{ (r.sov*100)|round(1) }}%</td><td>{{ (r.cited_rate*100)|round(1) }}%</td></tr>
{% endfor %}</table>

<h3>AI 最常引用的来源域名</h3>
<table><tr><th>域名</th><th>被引用次数</th></tr>
{% for d, c in metrics.top_domains %}<tr><td>{{ d }}</td><td>{{ c }}</td></tr>{% endfor %}</table>

<h3>竞品声量排序</h3>
<table><tr><th>竞品</th><th>被提及次数</th></tr>
{% for d, c in metrics.top_competitors %}<tr><td>{{ d }}</td><td>{{ c }}</td></tr>{% endfor %}</table>

<h2>四、平台优先级与信源策略</h2>
<div class="callout b">行业策略提示：{{ advisory.industry_note }}
<br>垂类必选信源：{{ advisory.vertical_sources|join('、') }}</div>
<table><tr><th>平台</th><th>建议投入</th><th>核心信源</th><th>内容要点</th><th>当前提及率</th></tr>
{% for p in advisory.platform_plan %}
<tr><td><strong>{{ p.platform }}</strong></td><td>{{ p.weight }}%</td>
<td>{{ p.sources|join('、') }}</td><td>{{ p.focus }}；避免：{{ p.avoid }}</td>
<td>{% if p.current is not none %}{{ (p.current*100)|round(1) }}%{% else %}—{% endif %}</td></tr>
{% endfor %}</table>

<h2>五、内容改造清单（含改写示范）</h2>
{% for t in advisory.content_tactics %}
<h3>{{ loop.index }}. {{ t.name }}</h3>
<p class="small">原理：{{ t.why }}</p>
<table><tr><th>原文</th><th>GEO 改写建议</th></tr>
<tr><td>{{ t.before }}</td><td>{{ t.after }}</td></tr></table>
{% endfor %}

<h2>六、技术件清单</h2>
<table><tr><th>任务</th><th>说明</th><th>优先级</th></tr>
{% for name, desc, pr in advisory.tech_tasks %}<tr><td>{{ name }}</td><td>{{ desc }}</td><td>{{ pr }}</td></tr>{% endfor %}</table>
{% if advisory.tech_audit.checks %}
<h3>站点体检结果（{{ advisory.tech_audit.url }}）</h3>
<table><tr><th>检查项</th><th>状态</th><th>详情</th></tr>
{% for c in advisory.tech_audit.checks %}<tr><td>{{ c.item }}</td><td>{{ c.status }}</td><td>{{ c.detail }}</td></tr>{% endfor %}</table>
{% endif %}

<h3>llms.txt 模板</h3><pre>{{ llms }}</pre>
<h3>Organization Schema 模板</h3><pre>{{ schema }}</pre>

<h2>七、90 天路线图</h2>
<table><tr><th>阶段</th><th>目标</th><th>关键动作</th><th>验收指标</th></tr>
{% for r in advisory.roadmap %}
<tr><td><strong>{{ r.phase }}</strong></td><td>{{ r.goal }}</td>
<td><ol>{% for a in r.actions %}<li>{{ a }}</li>{% endfor %}</ol></td><td>{{ r.kpi }}</td></tr>
{% endfor %}</table>

<h2>八、风险与合规提示</h2>
<div class="callout">
<ul>
<li>本报告基于 AI 生成回答的抽样采集，结果受模型版本、采样时间与端口影响，请以趋势而非单点为准。</li>
<li>严禁采用批量虚构软文、伪造榜单等"投喂式"黑帽手法（2026 年央视 3·15 已曝光相关产业链）。</li>
<li>金融行业内容对外发布前须经合规审核，不得承诺收益或夸大业绩。</li>
<li>建议每四周使用同一题库重测，形成可对比的效果曲线。</li>
</ul></div>

<p class="small" style="margin-top:34px">由 GEO MVP 自动生成 · {{ now }} · 样本 {{ metrics.overall.n }} 条 / {{ run.platforms|length }} 个 AI 入口</p>
</div></body></html>""")


def render(project: dict, run: dict, metrics: dict, advisory: dict,
           health: int) -> str:
    from . import advisory as adv
    return TPL.render(
        project=project, run=run, metrics=metrics, advisory=advisory,
        health=health, LAYER_NAMES=LAYER_NAMES,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        llms=escape(adv.llms_txt(project)),
        schema=escape(adv.schema_jsonld(project)),
    )


def export(project: dict, run: dict, metrics: dict, advisory: dict, health: int) -> str:
    html = render(project, run, metrics, advisory, health)
    name = f"GEO诊断报告_{project['brand']}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
