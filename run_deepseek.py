"""DeepSeek 全量实测：20 题 × 3 采样并发采集 + 规则/LLM 双路标注"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_mvp import annotate, db, probes

PROJECT_ID = 2
CFG = json.load(open(os.path.join(db.ROOT, "data", "api_config.json"), encoding="utf-8"))
BASE_URL, KEY, MODEL = CFG["base_url"], CFG["api_key"], CFG["model"]
SAMPLES = 3
WORKERS = 5

proj = db.get_project(PROJECT_ID)
aliases = [a.strip() for a in (proj["aliases"] or "").replace("，", ",").split(",") if a.strip()]
prompts = db.list_prompts(PROJECT_ID)
print(f"project={proj['brand']} prompts={len(prompts)} samples={SAMPLES}")

run_id = db.create_run(PROJECT_ID, f"DeepSeek全量实测 {time.strftime('%m-%d %H:%M')}",
                       mode="api", platforms=["DeepSeek"],
                       note=f"model={MODEL}; no-web-search(知识口径); judge=deepseek-chat")

jobs = [(p, s) for p in prompts for s in range(SAMPLES)]
rows, errs = [], 0
t0 = time.time()
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = {ex.submit(probes.api_answer, p["text"], "DeepSeek", "web", s,
                      BASE_URL, KEY, MODEL, False): (p, s) for p, s in jobs}
    for k, fut in enumerate(as_completed(futs), 1):
        p, s = futs[fut]
        try:
            a = fut.result()
            a.prompt_id = p["id"]
            rows.append(a.to_row())
        except Exception as e:
            errs += 1
            print("ERR", p["text"][:15], str(e)[:100])
        if k % 10 == 0:
            print(f"collect {k}/{len(jobs)} elapsed={time.time()-t0:.0f}s")
print(f"collected={len(rows)} errors={errs} in {time.time()-t0:.0f}s")

db.insert_answers(run_id, rows)

# 双路标注：规则 + LLM 裁判（DeepSeek temperature=0）
answers = db.list_answers(run_id)
print("annotating", len(answers), "answers with LLM judge...")
t1 = time.time()
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = {ex.submit(annotate.llm_annotate, a["raw_text"], proj["brand"],
                      proj["competitors"], proj["facts"], BASE_URL, KEY, MODEL): a
            for a in answers if a["raw_text"]}
    for k, fut in enumerate(as_completed(futs), 1):
        a = futs[fut]
        rule = annotate.rule_annotate(a["raw_text"], proj["brand"], aliases,
                                      proj["competitors"], proj["facts"], a["citations"])
        merged = dict(rule)
        llm = None
        try:
            llm = fut.result(timeout=90)
        except Exception:
            llm = None
        if llm:
            merged.update({k: v for k, v in llm.items() if k in
                           ("mentioned", "position", "sentiment", "fact_score", "fact_note", "competitor_hits")})
            merged["judge"] = "llm"
        else:
            merged["judge"] = "rule"
        merged["sentiment_rule"] = rule["sentiment"]  # 保留规则口径作对比
        db.upsert_annotation(a["id"], **merged)
        if k % 15 == 0:
            print(f"annotate {k}/{len(answers)}")
print(f"annotated in {time.time()-t1:.0f}s")
print("RUN_ID:", run_id)
