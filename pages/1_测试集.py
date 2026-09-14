"""① 测试集：分层 Prompt 题库构建"""

import pandas as pd
import streamlit as st

from geo_mvp import db, prompts as P, ui

st.set_page_config(page_title="测试集 · GEO MVP", page_icon="🧪", layout="wide")
ui.inject_css()
proj = ui.sidebar_project()

st.title("🧪 测试集构建")
st.caption("按五层提问意图生成题库：L1 品牌词 / L2 品类词 / L3 场景词 / L4 对比词 / L5 长尾词——"
           "这是全部监测与效果对比的基准，一经确定不要轻易改动。")

if not proj:
    st.warning("请先在首页创建项目或载入演示数据。")
    st.stop()

with st.expander("项目参数（题库生成依据）", expanded=False):
    c1, c2, c3 = st.columns(3)
    brand = c1.text_input("品牌名", proj["brand"])
    industry = c2.text_input("行业", proj["industry"])
    comps = c3.text_input("竞品（逗号分隔）", "，".join(proj["competitors"]))
    scen = st.text_input("目标场景（逗号分隔）", "，".join(proj["scenarios"]))
    if st.button("保存参数", type="secondary"):
        db.update_project(proj["id"], brand=brand, industry=industry,
                          competitors=[x.strip() for x in comps.replace("，", ",").split(",") if x.strip()],
                          scenarios=[x.strip() for x in scen.replace("，", ",").split(",") if x.strip()])
        st.success("已保存")
        st.rerun()

st.subheader("生成题库")
c1, c2, c3 = st.columns([1, 1, 2])
total = c1.slider("目标条数", 20, 300, 120, 10)
seed = c2.number_input("随机种子", 0, 9999, 42)
gen = c3.button("⚙️ 生成 / 覆盖题库", type="primary", use_container_width=True)

if gen:
    items = P.build_prompts(brand or proj["brand"], industry or proj["industry"],
                            [x.strip() for x in comps.replace("，", ",").split(",") if x.strip()],
                            [x.strip() for x in scen.replace("，", ",").split(",") if x.strip()],
                            total=total, seed=int(seed))
    db.clear_prompts(proj["id"])
    db.add_prompts(proj["id"], items)
    st.success(f"已生成 {len(items)} 条题库")
    st.rerun()

st.subheader("手工补充题库")
st.markdown('<div class="hint">每行一条；可用 <code>层级|提问</code> 指定层级（如 <code>L2|有哪些值得关注的量化私募</code>），'
            '不写层级默认归入 L2 品类词。建议从客服记录、知乎问题、搜索下拉词里捞真实问法。</div>',
            unsafe_allow_html=True)
txt = st.text_area("批量导入", height=110, placeholder="L2|有哪些值得关注的量化私募\nL3|1000万闲置资金怎么配置")
if st.button("导入"):
    items = P.parse_manual_prompts(txt)
    if items:
        db.add_prompts(proj["id"], items)
        st.success(f"导入 {len(items)} 条")
        st.rerun()

st.divider()
prompts = db.list_prompts(proj["id"])
st.subheader(f"当前题库（{len(prompts)} 条）")
if prompts:
    df = pd.DataFrame([{"层级": p["layer"], "层级说明": P.LAYERS[p["layer"]],
                        "提问": p["text"], "意图": p["intent"]} for p in prompts])
    tab1, tab2 = st.tabs(["分层视图", "统计"])
    with tab1:
        layer_filter = st.multiselect("筛选层级", list(P.LAYERS.keys()), default=list(P.LAYERS.keys()))
        st.dataframe(df[df["层级"].isin(layer_filter)], use_container_width=True, height=420)
    with tab2:
        st.bar_chart(df["层级"].value_counts().sort_index())
    csv = pd.DataFrame(P.to_csv_rows(prompts)).to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ 导出题库 CSV", csv, file_name=f"prompt_bank_{proj['brand']}.csv",
                       mime="text/csv", type="primary")
else:
    st.info("题库为空，请点击「生成题库」。")
