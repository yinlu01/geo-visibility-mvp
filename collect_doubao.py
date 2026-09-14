"""豆包真实采集驱动：逐题新会话 → 发送 → 轮询生成完毕 → 提取回答 → 入库"""
import json, subprocess, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_mvp import db

SESSION = sys.argv[1] if len(sys.argv) > 1 else "cdru"
PROJECT_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 2
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 20
PLATFORM = "豆包"
BASE = "https://www.doubao.com/chat/"

def bsk(*args, timeout=60):
    r = subprocess.run(["bsk", *args, "--session", SESSION],
                       capture_output=True, text=True, timeout=timeout)
    out = r.stdout.strip()
    for line in out.splitlines():
        if "bsk version" in line:
            out = out.replace(line, "")
    return out.strip()

def bsk_json(expr):
    out = bsk("evaluate", expr, "--json", timeout=90)
    try:
        d = json.loads(out)
        return d.get("value", d.get("result"))
    except Exception:
        return None

STABLE_JS = """(()=>{const el=document.querySelector('[class*="message-list"]');const t=el?el.innerText:'';
const stop=!!(document.querySelector('[class*="stop-generate"]')||document.querySelector('[aria-label*="停止"]'));
return JSON.stringify({len:t.length,text:t,stop:stop})})()"""

run_id = db.create_run(PROJECT_ID, f"豆包真实采集 {time.strftime('%m-%d %H:%M')}",
                       mode="real", platforms=[PLATFORM],
                       note="bsk 浏览器自动化，豆包网页版未登录真实回答，每题新会话")
SKIP = int(sys.argv[4]) if len(sys.argv) > 4 else 0
prompts = db.list_prompts(PROJECT_ID)[SKIP:SKIP + LIMIT]
done = 0
for p in prompts:
    q = p["text"]
    bsk("navigate", BASE, "--timeout", "40000")
    time.sleep(4)
    # 找到输入框 ref
    snap = bsk("snapshot")
    ref = None
    for line in snap.splitlines():
        if "textbox" in line and "发消息" in line:
            ref = line.split()[0]
            break
    if not ref:
        print(f"[skip] no input ref for: {q}")
        continue
    bsk("fill", ref, "--value", q)
    bsk("press", "Enter")
    # 轮询生成完毕
    last_len, stable, text = -1, 0, ""
    for i in range(25):
        time.sleep(3)
        d = bsk_json(STABLE_JS)
        if not d:
            continue
        d = json.loads(d)
        text = d["text"]
        if d["stop"]:
            continue
        if d["len"] == last_len and d["len"] > 120:
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
        last_len = d["len"]
    # 清洗：去掉开头的问题本身
    body = text.strip()
    if q in body:
        body = body.split(q, 1)[1].strip()
    ans_id = None
    with db.connect() as c:
        cur = c.execute(
            "INSERT INTO answers(run_id,prompt_id,platform,port,sample_idx,raw_text,citations) VALUES(?,?,?,?,?,?,?)",
            (run_id, p["id"], PLATFORM, "web", 0, body, "[]"),
        )
        ans_id = cur.lastrowid
    done += 1
    print(f"[{done}/{len(prompts)}] {q} -> {len(body)} chars")
print("RUN_ID:", run_id, "collected:", done)
