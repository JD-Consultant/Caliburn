"""Markdown results table for one version of simulated-interview runs (the T14 evidence layout).

Usage: results_table.py <version> [schema]
One row per run: structure of the final JD, questioning style, citation audit, time, A model calls,
estimated cost, plus counted input tokens (what the account's tokens-per-minute limit sees).
"""

import glob
import json
import re
import sys

import ormsgpack
import psycopg

sys.stdout.reconfigure(encoding="utf-8")
version = sys.argv[1]
schema = sys.argv[2] if len(sys.argv) > 2 else "eval_b"
URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test"
HIDDEN = {"limits", "quality_roster", "risk_peak", "tools", "physical", "license"}


def grams(text):
    text = re.sub(r"\s+", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)}


def decode(blob):
    return ormsgpack.unpackb(bytes(blob), ext_hook=lambda c, d: d, option=ormsgpack.OPT_NON_STR_KEYS)


print("| 人設 | 次 | 輪數 | 任務 | 最大任務字數 | 知識技能（近似任務改寫） | 條件 | 協作對象 | 成果／要求近重抄 | 職務目的 | 隱藏面向被問到 | 問句／輪 | 字／輪 | 引用審計（檢／未支持） | 分鐘 | A 模型呼叫 | 輸入 token（百萬） | 失敗嘗試／嘗試 | 估算 US$ |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
with psycopg.connect(URL, autocommit=True, options=f"-c search_path={schema} -c default_transaction_read_only=on") as c:
    for path in sorted(glob.glob(rf"S:\caliburn\.research-tmp\eval\{version}-*-?.json")):
        r = json.load(open(path, encoding="utf-8"))
        w, ck = r["jd"]["work"], r["checks"]
        rep = tot = 0
        for t in w["tasks"]:
            base = grams(t["title"] + t["description"])
            for d in t["outcomes"] + t["requirements"]:
                m = grams(d["text"])
                if m:
                    tot += 1
                    rep += len(m & base) / len(m) >= 0.7
        dup = sum(
            max((len(grams(cap["name"]) & grams(t["title"] + t["description"])) / max(1, len(grams(cap["name"]))) for t in w["tasks"]), default=0) >= 0.6
            for cap in w["capabilities"]
        )
        asked = sum(1 for k, v in ck["facts"].items() if k in HIDDEN and v["surfaced"])
        fid = r["job_file_id"]
        cost, calls_total, failed = c.execute(
            "select coalesce(sum(a.reported_cost_usd),0)::float, count(a.attempt_id), count(a.attempt_id) filter (where a.failure_code is not null) from executions e left join execution_outbound_attempts a on a.execution_id=e.execution_id where e.job_file_id=%s",
            (fid,),
        ).fetchone()
        calls = c.execute(
            "select count(*) from executions e join execution_outbound_attempts a on a.execution_id=e.execution_id where e.job_file_id=%s and e.kind='consultant_turn' and a.kind='model'",
            (fid,),
        ).fetchone()[0]
        tokens = sum(int(decode(b)["input_tokens"]) for (b,) in c.execute("select blob from checkpoint_blobs where thread_id like %s and channel='input_count'", (f"{fid}:%",)))
        secs = sum(t.get("seconds") or 0 for t in r["turns"])
        failed_turn = sum(t.get("status") not in ("completed", None) for t in r["turns"])
        name = "課程行政" if r["persona"] == "course_admin" else "倉庫"
        turns = f"{len(r['turns'])}" + (f"（{failed_turn} 輪失敗）" if failed_turn else "") + ("（復原）" if r.get("recovered") else "")
        print(
            f"| {name} | {r['label'][-1]} | {turns} | {ck['shape']['tasks']} | {max((len(t['description']) for t in w['tasks']), default=0)} | {len(w['capabilities'])}（{dup}） | {ck['shape']['condition_items']} | {ck['shape']['collaborator_items']} | {rep}/{tot} | {'有' if r['jd']['profile'].get('purpose') else '無'} | {asked} | {ck['style']['questions_per_turn']} | {ck['style']['mean_consultant_chars']} | {ck['citations']['checked']}／{len(ck['citations']['unsupported'])} | {round(secs / 60, 1)} | {calls} | {tokens / 1e6:.2f} | {failed}／{calls_total} | {round(cost, 3)} |"
        )
