"""Streamlit 公共组件：侧边栏项目选择、指标卡、样式。"""

from __future__ import annotations

import streamlit as st

from . import db

CSS = """
<style>
.block-container{padding-top:1.6rem;max-width:1180px}
.kpi{border:1px solid #e6e8ee;border-radius:10px;padding:14px 16px;background:#fff}
.kpi .k{font-size:12px;color:#8a90a0}
.kpi .v{font-size:25px;font-weight:700;color:#2f5fd0;line-height:1.3}
.kpi .s{font-size:11.5px;color:#a0a6b5}
.bar{height:8px;background:#eef1f7;border-radius:5px;overflow:hidden;margin-top:7px}
.bar i{display:block;height:100%;background:#2f5fd0}
.hint{font-size:12.5px;color:#8a90a0;line-height:1.6}
.lv{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 9px;border-radius:999px;margin-right:6px}
.lv.r{background:#fdeeec;color:#c0392b}
.lv.b{background:#eef3fd;color:#2f5fd0}
.lv.g{background:#eaf6f0;color:#1e7a4f}
.lv.y{background:#fdf6e3;color:#b8860b}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def sidebar_project() -> dict | None:
    with st.sidebar:
        st.markdown("### GEO MVP")
        projects = db.list_projects()
        if not projects:
            st.info("还没有项目，请在首页创建或一键载入演示数据。")
            return None
        names = {p["id"]: f"{p['name']}" for p in projects}
        pid = st.selectbox("当前项目", list(names.keys()), format_func=lambda i: names[i],
                           key="sel_project")
        st.caption("如需新建项目，请回到首页。")
        return db.get_project(pid)


def kpi(label: str, value: str, sub: str = "", pct: float | None = None) -> None:
    bar = f'<div class="bar"><i style="width:{max(0,min(100,pct))}%"></i></div>' if pct is not None else ""
    st.markdown(
        f'<div class="kpi"><div class="k">{label}</div><div class="v">{value}</div>'
        f'<div class="s">{sub}</div>{bar}</div>', unsafe_allow_html=True)


def level_tag(level: str) -> str:
    cls = {"严重": "r", "提示": "b", "正常": "g"}.get(level, "y")
    return f'<span class="lv {cls}">{level}</span>'


def pct(x: float) -> str:
    return f"{x*100:.1f}%"
