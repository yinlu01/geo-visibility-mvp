"""④ GEO 建议：诊断 → 平台策略 → 内容改造 → 技术件 → 90 天路线图"""

import streamlit as st

from geo_mvp import advisory, db, metrics, tech, ui

st.set_page_config(page_title="GEO 建议 · GEO MVP", page_icon="🛠️", layout="wide")
ui.inject_css()
proj = ui.sidebar_project()

st.title("🛠️ GEO 提升方案")

if not proj:
    st.warning("请先在首页创建项目或载入演示数据。")
    st.stop()

runs = db.list_runs(proj["id"])
if not runs:
    st.warning("暂无采集批次，请先到「采集」页面执行。")
    st.stop()

opts = {r["id"]: f"{r['name']}（{r['created_at']}）" for r in runs}
rid = st.selectbox("基于批次", list(opts.keys()), format_func=lambda i: opts[i])
answers = db.list_answers(rid)
m = metrics.compute(answers)
h = metrics.health_score(m)

st.subheader("站点技术体检（可选，真实 HTTP 检测）")
c1, c2 = st.columns([3, 1])
site = c1.text_input("官网地址", value=proj.get("domain") or "")
do_audit = c2.button("开始体检", use_container_width=True)
audit = None
if do_audit and site:
    with st.spinner("正在检测 llms.txt / robots.txt / 结构化数据…"):
        audit = tech.audit_site(site)
    st.session_state["audit"] = audit
audit = st.session_state.get("audit")
if audit and audit.get("checks"):
    st.dataframe(audit["checks"], use_container_width=True, hide_index=True)
    blocked = [b for b in audit.get("bots", []) if b["blocked"]]
    if blocked:
        st.warning("可能被 robots.txt 拦截的 AI 爬虫：" + "、".join(b["bot"] for b in blocked))
    if audit.get("missing_schema"):
        st.caption("建议补充的 Schema 类型：" + "、".join(audit["missing_schema"]))

adv = advisory.build(proj, m, h, audit)

st.divider()
st.subheader(f"综合健康分：{h} / 100")
st.progress(h / 100)

st.subheader("一、诊断结论")
for d in adv["diagnosis"]:
    st.markdown(f'{ui.level_tag(d["level"])} **{d["title"]}** — {d["detail"]}', unsafe_allow_html=True)

st.subheader("二、平台优先级与信源策略")
st.markdown(f'<div class="hint">{adv["industry_note"]}<br>'
            f'<b>垂类必选信源</b>：{"、".join(adv["vertical_sources"])}</div>', unsafe_allow_html=True)
for p in adv["platform_plan"]:
    cur = f'{p["current"]*100:.1f}%' if p["current"] is not None else "—"
    with st.expander(f'**{p["platform"]}** · 建议投入 {p["weight"]}% · 当前提及率 {cur}', expanded=False):
        st.markdown(f'- **核心信源**：{"、".join(p["sources"])}')
        st.markdown(f'- **内容要点**：{p["focus"]}')
        st.markdown(f'- **避坑**：{p["avoid"]}')
        st.markdown(f'- **适配场景**：{p["fit"]}')

st.subheader("三、内容改造清单（含改写示范）")
for i, t in enumerate(adv["content_tactics"], 1):
    with st.expander(f'{i}. {t["name"]}', expanded=(i <= 3)):
        st.caption("原理：" + t["why"])
        c1, c2 = st.columns(2)
        c1.markdown("**原文（优化前）**\n\n" + t["before"])
        c2.markdown("**GEO 改写示范**\n\n" + t["after"])

st.subheader("四、技术件清单")
st.table([{"任务": n, "说明": d, "优先级": p} for n, d, p in adv["tech_tasks"]])
t1, t2, t3 = st.tabs(["llms.txt 模板", "Organization Schema", "robots.txt"])
with t1:
    code = advisory.llms_txt(proj)
    st.code(code, language="markdown")
    st.download_button("⬇️ 下载 llms.txt", code.encode("utf-8"), file_name="llms.txt")
with t2:
    code = advisory.schema_jsonld(proj)
    st.code(code, language="json")
    st.download_button("⬇️ 下载 schema.json", code.encode("utf-8"), file_name="organization_schema.json")
with t3:
    code = advisory.robots_txt()
    st.code(code)
    st.download_button("⬇️ 下载 robots.txt", code.encode("utf-8"), file_name="robots.txt")

st.subheader("五、90 天路线图")
for r in adv["roadmap"]:
    with st.container():
        st.markdown(f'**{r["phase"]}｜{r["goal"]}** · 验收：{r["kpi"]}')
        for a in r["actions"]:
            st.markdown(f"- {a}")
        st.divider()

st.info("以上为白帽 GEO 建议：仅通过结构化表达、权威引用与事实核查提升被引用概率。"
        "严禁批量虚构软文、伪造榜单等投喂式黑帽手法（2026 年央视 3·15 已曝光相关产业链）；"
        "金融行业内容发布前须经合规审核。")
