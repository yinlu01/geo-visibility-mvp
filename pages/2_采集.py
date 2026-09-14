"""② 采集：多入口多端口多次采样"""

import io
import json

import pandas as pd
import streamlit as st

from geo_mvp import annotate, db, probes, ui

st.set_page_config(page_title="采集 · GEO MVP", page_icon="🛰️", layout="wide")
ui.inject_css()
proj = ui.sidebar_project()

st.title("🛰️ 采集执行")
st.caption("支持三种模式：**演示引擎**（离线仿真，随时可跑）/ **API 接口**（DeepSeek、Kimi、通义、OpenAI 等 OpenAI 兼容接口）/ "
           "**手工导入**（豆包、元宝、文心等无开放接口入口的真实采集方式，复制粘贴或 CSV 导入）。")

if not proj:
    st.warning("请先在首页创建项目或载入演示数据。")
    st.stop()

prompts = db.list_prompts(proj["id"])
if not prompts:
    st.warning("题库为空，请先到「测试集」生成。")
    st.stop()

mode = st.radio("采集模式", ["演示引擎", "API 接口", "手工导入"], horizontal=True)

platforms = st.multiselect("AI 入口", list(probes.PLATFORMS.keys()),
                           default=["DeepSeek", "豆包", "元宝", "文心一言"])
samples = st.slider("每条提问采样次数（规避生成随机性）", 1, 5, 3)
run_name = st.text_input("批次名称", value=f"采集-{pd.Timestamp.now().strftime('%m%d-%H%M')}")

aliases = [a.strip() for a in (proj["aliases"] or "").replace("，", ",").split(",") if a.strip()]
facts = proj["facts"]

# ---------------- 演示引擎 ----------------
if mode == "演示引擎":
    st.info("演示引擎基于确定性仿真：同一（提问×平台×端口×采样序号）永远产生同一结果，"
            "因此可重复、可回归，适合演示与流程验收。真实投放请切换到 API 或手工导入模式。")
    if st.button("▶️ 开始采集", type="primary", use_container_width=True):
        rows = []
        prog = st.progress(0)
        for i, p in enumerate(prompts):
            for pf in platforms:
                for port in probes.PLATFORMS.get(pf, {}).get("ports", ["web"]):
                    for s in range(samples):
                        a = probes.demo_answer(p["text"], proj["brand"], proj["competitors"],
                                               pf, port, s, p["layer"])
                        a.prompt_id = p["id"]
                        rows.append(a.to_row())
            prog.progress((i + 1) / len(prompts))
        rid = db.create_run(proj["id"], run_name, "demo", platforms, "内置仿真引擎")
        db.insert_answers(rid, rows)
        for a in db.list_answers(rid):
            db.upsert_annotation(a["id"], **annotate.annotate_answer(
                a["raw_text"], proj["brand"], aliases, proj["competitors"], facts, a["citations"]))
        st.success(f"采集完成：{len(rows)} 条样本（批次 ID {rid}）")
        st.rerun()

# ---------------- API ----------------
elif mode == "API 接口":
    c1, c2, c3 = st.columns([2, 1, 1])
    base_url = c1.text_input("API Base URL", value="https://api.deepseek.com")
    model = c2.text_input("模型", value="deepseek-chat")
    api_key = c3.text_input("API Key", type="password")
    st.markdown('<div class="hint">支持所有 OpenAI 兼容接口：DeepSeek / 月之暗面 Kimi / 通义千问 / 智谱 / OpenAI / '
                '本地 vLLM&Ollama。注意：普通对话接口不带联网检索，若需"AI 搜索"真实结果，'
                '请使用对应平台的联网模型或改用手工导入模式。</div>', unsafe_allow_html=True)
    if st.button("▶️ 开始采集", type="primary", use_container_width=True):
        if not api_key:
            st.error("请填写 API Key")
        else:
            rows, errs = [], 0
            prog = st.progress(0)
            for i, p in enumerate(prompts):
                for pf in platforms:
                    for port in probes.PLATFORMS.get(pf, {}).get("ports", ["web"])[:1]:
                        for s in range(samples):
                            try:
                                a = probes.api_answer(p["text"], pf, port, s, base_url, api_key, model)
                                a.prompt_id = p["id"]
                                rows.append(a.to_row())
                            except Exception as e:
                                errs += 1
                prog.progress((i + 1) / len(prompts))
            if rows:
                rid = db.create_run(proj["id"], run_name, "api", platforms, f"model={model}; errors={errs}")
                db.insert_answers(rid, rows)
                for a in db.list_answers(rid):
                    db.upsert_annotation(a["id"], **annotate.annotate_answer(
                        a["raw_text"], proj["brand"], aliases, proj["competitors"], facts, a["citations"]))
                st.success(f"采集完成：{len(rows)} 条（失败 {errs}）")
                st.rerun()
            else:
                st.error(f"全部请求失败（{errs}），请检查接口配置。")

# ---------------- 手工导入 ----------------
else:
    st.markdown("**方式 A：上传 CSV**（列：prompt, platform, port, answer, citations）")
    tpl = pd.DataFrame([{"prompt": "有哪些值得关注的量化私募", "platform": "豆包", "port": "app",
                         "answer": "综合公开信息来看……", "citations": "toutiao.com,zhihu.com"}])
    st.download_button("⬇️ 下载 CSV 模板", tpl.to_csv(index=False).encode("utf-8-sig"),
                       file_name="answers_template.csv", mime="text/csv")
    up = st.file_uploader("上传采集结果 CSV", type=["csv"])
    st.markdown("**方式 B：逐条粘贴**（适合小样本验收）")
    with st.form("manual_single"):
        q = st.selectbox("对应提问", prompts, format_func=lambda p: f"[{p['layer']}] {p['text']}")
        pf = st.selectbox("AI 入口", list(probes.PLATFORMS.keys()))
        port = st.selectbox("端口", ["web", "app"])
        ans = st.text_area("粘贴 AI 回答原文", height=160)
        ok = st.form_submit_button("保存这条")
    if ok and ans.strip():
        rid = None
        for r in db.list_runs(proj["id"]):
            if r["name"] == run_name and r["mode"] == "manual":
                rid = r["id"]
                break
        if rid is None:
            rid = db.create_run(proj["id"], run_name, "manual", platforms, "手工导入")
        citations = probes.parse_manual_answers(ans, q["id"], pf, port).citations
        db.insert_answers(rid, [{"prompt_id": q["id"], "platform": pf, "port": port,
                                 "sample_idx": 0, "raw_text": ans.strip(), "citations": citations}])
        for a in db.list_answers(rid):
            if not a.get("mentioned") and a.get("fact_score") in (None, 0):
                db.upsert_annotation(a["id"], **annotate.annotate_answer(
                    a["raw_text"], proj["brand"], aliases, proj["competitors"], facts, a["citations"]))
        st.success("已保存")
        st.rerun()
    if up is not None:
        df = pd.read_csv(up)
        need = {"prompt", "answer"}
        if not need.issubset(df.columns):
            st.error(f"CSV 缺少必要列：{need - set(df.columns)}")
        else:
            rows = probes.parse_manual_csv(df)
            pmap = {p["text"].strip(): p["id"] for p in prompts}
            n, miss = 0, 0
            rid = db.create_run(proj["id"], run_name, "manual",
                                sorted({r["platform"] for r in rows}), "CSV 导入")
            items = []
            for r in rows:
                pid = pmap.get(r["prompt"])
                if pid is None:
                    miss += 1
                    continue
                items.append({"prompt_id": pid, "platform": r["platform"], "port": r["port"],
                              "sample_idx": 0, "raw_text": r["answer"], "citations": r["citations"]})
                n += 1
            if items:
                db.insert_answers(rid, items)
                for a in db.list_answers(rid):
                    db.upsert_annotation(a["id"], **annotate.annotate_answer(
                        a["raw_text"], proj["brand"], aliases, proj["competitors"], facts, a["citations"]))
            st.success(f"导入 {n} 条（{miss} 条提问未匹配题库，已跳过）")
            st.rerun()

st.divider()
st.subheader("历史批次")
runs = db.list_runs(proj["id"])
if runs:
    st.dataframe(pd.DataFrame([{"ID": r["id"], "批次": r["name"], "模式": r["mode"],
                                "平台": "、".join(r["platforms"]), "样本": r["n"],
                                "时间": r["created_at"]} for r in runs]),
                 use_container_width=True, hide_index=True)
    del_id = st.number_input("删除批次 ID（不可恢复）", min_value=0, value=0, step=1)
    if st.button("删除该批次") and del_id:
        db.delete_run(int(del_id))
        st.warning(f"批次 {del_id} 已删除")
        st.rerun()
