"""GEO MVP · 首页总览"""

import streamlit as st

from geo_mvp import db, metrics, seed_demo, ui

st.set_page_config(page_title="GEO MVP · 品牌 AI 可见性工作台", page_icon="📡", layout="wide")
ui.inject_css()

st.title("📡 GEO MVP")
st.caption("品牌 AI 可见性监测与优化工作台 · 测试集 → 多入口采集 → 标注看板 → GEO 提升方案 → 报告导出")

projects = db.list_projects()
with st.sidebar:
    st.markdown("### 项目")
    if projects:
        st.caption(f"共 {len(projects)} 个项目")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("新建监测项目")
    with st.form("new_project", clear_on_submit=True):
        name = st.text_input("项目名称", placeholder="例如：XX资管 2026 Q3 AI 可见性")
        brand = st.text_input("品牌名", placeholder="例如：启明智造")
        c1, c2 = st.columns(2)
        industry = c1.text_input("行业", placeholder="资管 / 金融 / SaaS / 零售")
        domain = c2.text_input("官网域名", placeholder="example.com")
        aliases = st.text_input("品牌别名（逗号分隔）", placeholder="启明智造资管,启明资管")
        competitors = st.text_input("竞品（逗号分隔）", placeholder="远见资本,恒盛资产")
        products = st.text_input("核心产品/服务（逗号分隔）", placeholder="稳健增利系列,量化中性3号")
        scenarios = st.text_input("目标场景（逗号分隔）", placeholder="1000万闲置资金,追求稳健收益时")
        facts = st.text_area("品牌事实卡（每行 键: 值，用于事实核查标注）",
                             placeholder="成立时间: 2015\n管理规模: 1240\n主动权益管理费率: 1.2",
                             height=90)
        submit = st.form_submit_button("创建项目", type="primary")
    if submit:
        if not name or not brand:
            st.error("项目名称与品牌名为必填项。")
        else:
            def _split(s):
                return [x.strip() for x in (s or "").replace("，", ",").split(",") if x.strip()]
            fact_list = []
            for line in facts.splitlines():
                if ":" in line or "：" in line:
                    k, v = line.replace("：", ":").split(":", 1)
                    if k.strip():
                        fact_list.append({"key": k.strip(), "value": v.strip()})
            pid = db.create_project(name=name, brand=brand, industry=industry, domain=domain,
                                    aliases=aliases, competitors=_split(competitors),
                                    products=_split(products), scenarios=_split(scenarios),
                                    facts=fact_list)
            st.session_state["sel_project"] = pid
            st.success(f"项目已创建（ID {pid}），请前往「测试集」生成题库。")
            st.rerun()

with col2:
    st.subheader("快速体验")
    st.markdown('<div class="hint">一键生成内置演示项目：4 个 AI 入口、多端口、3 次采样，'
                '共 800+ 条真实结构的采集样本，用于演示完整流程与客户验收。</div>',
                unsafe_allow_html=True)
    if st.button("🚀 载入演示数据", type="secondary", use_container_width=True):
        with st.spinner("正在生成演示项目与基线数据…"):
            pid = seed_demo.build()
        st.session_state["sel_project"] = pid
        st.success("演示数据已生成！")
        st.rerun()

st.divider()
st.subheader("项目总览")
if not projects:
    st.info("暂无项目。左侧创建新项目，或点击「载入演示数据」快速体验。")
else:
    for p in projects:
        with st.expander(f"**{p['name']}** · 品牌：{p['brand']} · 行业：{p['industry'] or '—'}", expanded=True):
            pr = db.list_prompts(p["id"])
            runs = db.list_runs(p["id"])
            c = st.columns(4)
            c[0].metric("题库条数", len(pr))
            c[1].metric("采集批次", len(runs))
            c[2].metric("竞品数", len(p["competitors"]))
            c[3].metric("事实卡条目", len(p["facts"]))
            if runs:
                r = runs[0]
                answers = db.list_answers(r["id"])
                m = metrics.compute(answers)
                st.caption(f"最近批次：{r['name']}（{r['created_at']}）｜样本 {m['overall']['n']} 条")
                k = st.columns(5)
                ui.kpi("健康分", str(metrics.health_score(m)), "0-100 综合", metrics.health_score(m))
                k[1].markdown("")
                ui.kpi("提及率", ui.pct(m["overall"]["mention_rate"]), "被 AI 提到",
                       m["overall"]["mention_rate"] * 100)
                ui.kpi("SOV", ui.pct(m["overall"]["sov"]), "声量份额", m["overall"]["sov"] * 100)
                ui.kpi("事实准确率", ui.pct(m["overall"]["fact_acc"]), "AI 是否说对",
                       m["overall"]["fact_acc"] * 100)
                ui.kpi("被引用率", ui.pct(m["overall"]["cited_rate"]), "成为信源",
                       m["overall"]["cited_rate"] * 100)
            else:
                st.caption("尚无采集批次，请前往「采集」页面。")

st.divider()
st.markdown("""
**工作流**：① 测试集（构建分层 Prompt 题库）→ ② 采集（演示/API/手工导入三种模式，多入口多端口多次采样）
→ ③ 看板（可见度、SOV、位次、情感、事实准确率）→ ④ GEO 建议（平台优先级、内容改造、技术件、90 天路线图）
→ ⑤ 报告导出（可交付客户的 HTML 报告）
""")
