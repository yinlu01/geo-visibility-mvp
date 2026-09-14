"""⑤ 报告导出：生成可交付客户的 HTML 诊断报告"""

import os

import streamlit as st

from geo_mvp import advisory, db, metrics, report, tech, ui

st.set_page_config(page_title="报告导出 · GEO MVP", page_icon="📄", layout="wide")
ui.inject_css()
proj = ui.sidebar_project()

st.title("📄 报告导出")

if not proj:
    st.warning("请先在首页创建项目或载入演示数据。")
    st.stop()

runs = db.list_runs(proj["id"])
if not runs:
    st.warning("暂无采集批次。")
    st.stop()

opts = {r["id"]: f"{r['name']}（{r['created_at']}）" for r in runs}
rid = st.selectbox("选择批次", list(opts.keys()), format_func=lambda i: opts[i])

with st.expander("报告选项", expanded=False):
    site = st.text_input("站点地址（用于技术体检章节，可留空）", value=proj.get("domain") or "")
    include_tech = st.checkbox("执行站点技术体检并写入报告", value=False)

if st.button("🧾 生成 HTML 报告", type="primary", use_container_width=True):
    answers = db.list_answers(rid)
    m = metrics.compute(answers)
    h = metrics.health_score(m)
    audit = tech.audit_site(site) if (include_tech and site) else None
    adv = advisory.build(proj, m, h, audit)
    run = [r for r in runs if r["id"] == rid][0]
    path = report.export(proj, run, m, adv, h)
    st.session_state["last_report"] = path
    st.success(f"报告已生成：{path}")

path = st.session_state.get("last_report")
if path and os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    st.download_button("⬇️ 下载报告", html.encode("utf-8"),
                       file_name=os.path.basename(path), mime="text/html", type="primary")
    st.components.v1.html(html, height=900, scrolling=True)

st.divider()
out_dir = report.OUT_DIR
files = sorted([f for f in os.listdir(out_dir) if f.endswith(".html")], reverse=True)
if files:
    st.subheader("历史报告")
    for f in files:
        st.markdown(f"- `{out_dir}/{f}`")
