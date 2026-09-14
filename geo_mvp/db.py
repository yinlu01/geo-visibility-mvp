"""SQLite 数据层：项目 / 题库 / 采集批次 / 回答 / 标注。"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get(
    "GEO_MVP_DB", os.path.join(ROOT, "data", "geo_mvp.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    aliases TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    competitors TEXT DEFAULT '[]',
    products TEXT DEFAULT '[]',
    scenarios TEXT DEFAULT '[]',
    facts TEXT DEFAULT '[]',
    domain TEXT DEFAULT '',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    layer TEXT NOT NULL,
    text TEXT NOT NULL,
    intent TEXT DEFAULT '',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    mode TEXT DEFAULT 'demo',
    platforms TEXT DEFAULT '[]',
    note TEXT DEFAULT '',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    prompt_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    port TEXT DEFAULT 'web',
    sample_idx INTEGER DEFAULT 0,
    raw_text TEXT DEFAULT '',
    citations TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id INTEGER UNIQUE,
    mentioned INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,
    cited INTEGER DEFAULT 0,
    cite_domains TEXT DEFAULT '[]',
    sentiment TEXT DEFAULT 'neutral',
    fact_score REAL DEFAULT 0,
    fact_note TEXT DEFAULT '',
    competitor_hits TEXT DEFAULT '[]'
);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False)


def _lj(s) -> list:
    try:
        return json.loads(s) if s else []
    except Exception:
        return []


# ---------------- projects ----------------

def create_project(name: str, brand: str, industry: str = "", domain: str = "",
                   aliases: str = "", competitors: list | None = None,
                   products: list | None = None, scenarios: list | None = None,
                   facts: list | None = None) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO projects(name,brand,aliases,industry,competitors,products,scenarios,facts,domain,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (name, brand, aliases, industry, _j(competitors or []), _j(products or []),
             _j(scenarios or []), _j(facts or []), domain, _now()),
        )
        return cur.lastrowid


def update_project(pid: int, **kw) -> None:
    if not kw:
        return
    cols, vals = [], []
    for k, v in kw.items():
        if k in ("competitors", "products", "scenarios", "facts"):
            v = _j(v)
        cols.append(f"{k}=?")
        vals.append(v)
    vals.append(pid)
    with connect() as c:
        c.execute(f"UPDATE projects SET {','.join(cols)} WHERE id=?", vals)


def list_projects() -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("competitors", "products", "scenarios", "facts"):
            d[k] = _lj(d.get(k))
        out.append(d)
    return out


def get_project(pid: int) -> dict | None:
    with connect() as c:
        r = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("competitors", "products", "scenarios", "facts"):
        d[k] = _lj(d.get(k))
    return d


# ---------------- prompts ----------------

def add_prompts(project_id: int, items: list[dict]) -> int:
    with connect() as c:
        c.executemany(
            "INSERT INTO prompts(project_id,layer,text,intent,created_at) VALUES(?,?,?,?,?)",
            [(project_id, i["layer"], i["text"], i.get("intent", ""), _now()) for i in items],
        )
        return c.total_changes


def list_prompts(project_id: int) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM prompts WHERE project_id=? ORDER BY layer, id", (project_id,)
        ).fetchall()]


def clear_prompts(project_id: int) -> None:
    with connect() as c:
        c.execute("DELETE FROM prompts WHERE project_id=?", (project_id,))


# ---------------- runs ----------------

def create_run(project_id: int, name: str, mode: str, platforms: list, note: str = "") -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO runs(project_id,name,mode,platforms,note,created_at) VALUES(?,?,?,?,?,?)",
            (project_id, name, mode, _j(platforms), note, _now()),
        )
        return cur.lastrowid


def list_runs(project_id: int) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT r.*, (SELECT COUNT(*) FROM answers a WHERE a.run_id=r.id) AS n "
            "FROM runs r WHERE r.project_id=? ORDER BY r.id DESC", (project_id,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["platforms"] = _lj(d.get("platforms"))
        out.append(d)
    return out


def delete_run(run_id: int) -> None:
    with connect() as c:
        c.execute("DELETE FROM annotations WHERE answer_id IN (SELECT id FROM answers WHERE run_id=?)", (run_id,))
        c.execute("DELETE FROM answers WHERE run_id=?", (run_id,))
        c.execute("DELETE FROM runs WHERE id=?", (run_id,))


# ---------------- answers ----------------

def insert_answers(run_id: int, items: list[dict]) -> int:
    with connect() as c:
        c.executemany(
            "INSERT INTO answers(run_id,prompt_id,platform,port,sample_idx,raw_text,citations)"
            " VALUES(?,?,?,?,?,?,?)",
            [(run_id, i["prompt_id"], i["platform"], i.get("port", "web"), i.get("sample_idx", 0),
              i.get("raw_text", ""), _j(i.get("citations", []))) for i in items],
        )
        return c.total_changes


def list_answers(run_id: int) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            """SELECT a.*, p.layer, p.text AS prompt_text,
                      an.mentioned, an.position, an.cited, an.cite_domains, an.sentiment,
                      an.fact_score, an.fact_note, an.competitor_hits
               FROM answers a
               JOIN prompts p ON p.id = a.prompt_id
               LEFT JOIN annotations an ON an.answer_id = a.id
               WHERE a.run_id=? ORDER BY a.id""", (run_id,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("citations", "cite_domains", "competitor_hits"):
            d[k] = _lj(d.get(k))
        out.append(d)
    return out


def upsert_annotation(answer_id: int, **kw) -> None:
    kw = {k: (_j(v) if isinstance(v, (list, dict)) else v) for k, v in kw.items()}
    cols = ",".join(kw.keys())
    marks = ",".join("?" * len(kw))
    updates = ",".join(f"{k}=excluded.{k}" for k in kw)
    with connect() as c:
        c.execute("INSERT INTO annotations(answer_id) VALUES(?) ON CONFLICT DO NOTHING", (answer_id,))
        c.execute(
            f"INSERT INTO annotations(answer_id,{cols}) VALUES(?,{marks}) "
            f"ON CONFLICT(answer_id) DO UPDATE SET {updates}",
            [answer_id] + list(kw.values()),
        )
