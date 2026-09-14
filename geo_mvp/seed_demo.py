"""一键生成演示数据：示例项目 + 题库 + 采集批次 + 标注结果。

用法：
    python -m geo_mvp.seed_demo
"""

from __future__ import annotations

from . import db, prompts as P, probes, annotate, metrics

DEMO = dict(
    name="示例：启明智造资管（演示）",
    brand="启明智造",
    aliases="启明智造资管,启明资管",
    industry="资管",
    domain="qiming-am.example.com",
    competitors=["远见资本", "恒盛资产", "博远投研", "中泰智投"],
    products=["稳健增利系列", "量化中性 3 号", "启明智选 FOF"],
    scenarios=["1000 万闲置资金", "追求稳健收益时", "首次配置量化产品时"],
    facts=[
        {"key": "成立时间", "value": "2015"},
        {"key": "管理规模", "value": "1240"},
        {"key": "主动权益管理费率", "value": "1.2"},
    ],
)


def build(platforms=None, samples: int = 3, total_prompts: int = 120) -> int:
    platforms = platforms or ["DeepSeek", "豆包", "元宝", "文心一言"]
    existing = [p for p in db.list_projects() if p["name"] == DEMO["name"]]
    if existing:
        pid = existing[0]["id"]
        db.clear_prompts(pid)
        db.update_project(pid, **{k: v for k, v in DEMO.items() if k != "name"})
    else:
        pid = db.create_project(**DEMO)

    items = P.build_prompts(
        brand=DEMO["brand"], industry=DEMO["industry"],
        competitors=DEMO["competitors"], scenarios=DEMO["scenarios"],
        total=total_prompts,
    )
    db.clear_prompts(pid)
    db.add_prompts(pid, items)
    plist = db.list_prompts(pid)

    run_id = db.create_run(pid, "演示基线（Demo）", "demo", platforms,
                           note="内置仿真引擎生成，用于演示与回归测试")

    aliases = [a.strip() for a in DEMO["aliases"].split(",") if a.strip()]
    rows = []
    for p in plist:
        for pf in platforms:
            ports = probes.PLATFORMS.get(pf, {}).get("ports", ["web"])
            for port in ports:
                for s in range(samples):
                    a = probes.demo_answer(p["text"], DEMO["brand"], DEMO["competitors"],
                                           pf, port, s, p["layer"])
                    a.prompt_id = p["id"]
                    rows.append(a.to_row())
    db.insert_answers(run_id, rows)

    answers = db.list_answers(run_id)
    for a in answers:
        res = annotate.annotate_answer(
            a["raw_text"], DEMO["brand"], aliases, DEMO["competitors"],
            DEMO["facts"], a["citations"],
        )
        db.upsert_annotation(a["id"], **res)
    return pid


if __name__ == "__main__":
    pid = build()
    runs = db.list_runs(pid)
    answers = db.list_answers(runs[0]["id"])
    m = metrics.compute(answers)
    print(f"演示项目已生成：project_id={pid}, run_id={runs[0]['id']}, "
          f"样本 {m['overall']['n']} 条")
    print("整体提及率：", f"{m['overall']['mention_rate']*100:.1f}%",
          "｜SOV：", f"{m['overall']['sov']*100:.1f}%",
          "｜健康分：", metrics.health_score(m))
