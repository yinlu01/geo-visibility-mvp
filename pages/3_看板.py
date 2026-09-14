"""③ 看板：可见度 / SOV / 位次 / 情感 / 事实准确率"""

import pandas as pd
import plotly.express as px
import streamlit as st

from geo_mvp import db, metrics, ui
from geo_mvp.metrics import LAYER_NAMES

st.set_page_config(page_title="看板 · GEO MVP", page_icon="📊", layout="wide")
ui.inject_css()
proj = ui.sidebar_project()

st.title("📊 效果看板")

if not proj:
    st.warning("请先在首页创建项目或载入演示数据。")
    st.stop()

runs = db.list_runs(proj["id"])
if not runs:
    st.warning("暂无采集批次，请先到「采集」页面执行。")
    st.stop()

opts = {r["id"]: f"{r['name']}（{r['created_at']} · {r['n']} 条）" for r in runs}
rid = st.selectbox("选择批次", list(opts.keys()), format_func=lambda i: opts[i])

compare = st.checkbox("对比另一批次（GEO 前后效果对照）")
rid2 = None
if compare and len(runs) > 1:
    rid2 = st.selectbox("对照批次", [i for i in opts if i != rid], format_func=lambda i: opts[i])

answers = db.list_answers(rid)
if not answers:
    st.warning("该批次无样本。")
    st.stop()

m = metrics.compute(answers)
h = metrics.health_score(m)
o = m["overall"]

st.markdown(f"**{proj['brand']}** · 行业：{proj['industry'] or '—'} · 样本 {o['n']} 条 · 入口 {len(m['by_platform'])} 个")

c = st.columns(6)
with c[0]:
    ui.kpi("健康分", str(h), "综合 0-100", h)
with c[1]:
    ui.kpi("提及率", ui.pct(o["mention_rate"]), "被 AI 提到", o["mention_rate"] * 100)
with c[2]:
    ui.kpi("SOV", ui.pct(o["sov"]), "声量份额 vs 竞品", o["sov"] * 100)
with c[3]:
    ui.kpi("位置分", f"{o['position_score']}", "第1位=3分", min(100, o["position_score"] / 3 * 100))
with c[4]:
    ui.kpi("事实准确率", ui.pct(o["fact_acc"]), "AI 是否说对", o["fact_acc"] * 100)
with c[5]:
    ui.kpi("情感净分", f"{o['sentiment_net']:.2f}", "-1~1", (o["sentiment_net"] + 1) / 2 * 100)

if rid2:
    m2 = metrics.compute(db.list_answers(rid2))
    o2 = m2["overall"]
    st.markdown("**GEO 前后对比**（左：基线，右：对照）")
    d = pd.DataFrame({
        "指标": ["提及率", "SOV", "被引用率", "事实准确率", "情感净分"],
        "基线": [o["mention_rate"], o["sov"], o["cited_rate"], o["fact_acc"], o["sentiment_net"]],
        "对照": [o2["mention_rate"], o2["sov"], o2["cited_rate"], o2["fact_acc"], o2["sentiment_net"]],
    })
    d["变化"] = (d["对照"] - d["基线"]).map(lambda x: f"{x*100:+.1f}pp" if abs(x) < 2 else f"{x:+.2f}")
    st.dataframe(d, use_container_width=True, hide_index=True)

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("分层可见度")
    dl = pd.DataFrame([{"层级": LAYER_NAMES[k], "提及率": v["mention_rate"], "SOV": v["sov"],
                        "样本": v["n"]} for k, v in m["by_layer"].items()])
    fig = px.bar(dl, x="层级", y=["提及率", "SOV"], barmode="group",
                 color_discrete_sequence=["#2f5fd0", "#b8860b"], height=340)
    fig.update_layout(legend_title_text="", margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
with col2:
    st.subheader("分平台可见度")
    dp = pd.DataFrame([{"入口": k, "提及率": v["mention_rate"], "被引用率": v["cited_rate"],
                        "样本": v["n"]} for k, v in m["by_platform"].items()])
    fig2 = px.bar(dp, x="入口", y=["提及率", "被引用率"], barmode="group",
                  color_discrete_sequence=["#2f5fd0", "#1e7a4f"], height=340)
    fig2.update_layout(legend_title_text="", margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig2, use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    st.subheader("AI 最常引用的来源")
    st.dataframe(pd.DataFrame(m["top_domains"], columns=["域名", "次数"]),
                 use_container_width=True, hide_index=True, height=260)
with col4:
    st.subheader("竞品声量")
    if m["top_competitors"]:
        st.dataframe(pd.DataFrame(m["top_competitors"], columns=["竞品", "被提及次数"]),
                     use_container_width=True, hide_index=True, height=260)
    else:
        st.caption("未检测到竞品提及")

st.subheader("⚠️ 风险样本（事实错误或负面表述）")
if m["risk_items"]:
    for a in m["risk_items"][:12]:
        tag = "r" if a.get("fact_note") else "y"
        label = "事实偏差" if a.get("fact_note") else "负面表述"
        st.markdown(f'<span class="lv {tag}">{label}</span> **{a["platform"]}**（{a["port"]}）· '
                    f'{a["prompt_text"]}', unsafe_allow_html=True)
        if a.get("fact_note"):
            st.caption("核查：" + a["fact_note"])
        with st.expander("查看原文"):
            st.write(a["raw_text"][:800])
else:
    st.success("未发现明显风险样本。")

st.divider()
st.subheader("样本明细")
show = pd.DataFrame([{"层级": a["layer"], "提问": a["prompt_text"], "入口": a["platform"],
                      "端口": a["port"], "提及": "是" if a.get("mentioned") else "否",
                      "位次": a.get("position") or "-", "情感": a.get("sentiment"),
                      "事实分": a.get("fact_score"), "引用": "、".join(a.get("cite_domains") or [])}
                     for a in answers])
st.dataframe(show, use_container_width=True, height=380)
st.download_button("⬇️ 导出明细 CSV", show.to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"answers_{rid}.csv", mime="text/csv")
