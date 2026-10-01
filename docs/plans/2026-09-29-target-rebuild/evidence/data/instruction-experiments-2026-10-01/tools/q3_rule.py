"""Apply the Q3 pre-registered adoption criteria (T14 evidence, "Q3 登記") to Q1 vs Q3.

Usage: q3_rule.py [schema]
Numbers only; the human reads of citations and fabrication are separate and recorded in the evidence.
"""

import glob
import json
import re
import statistics
import sys

import ormsgpack
import psycopg

sys.stdout.reconfigure(encoding="utf-8")
schema = sys.argv[1] if len(sys.argv) > 1 else "eval_b"
URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test"
HIDDEN = {"limits", "quality_roster", "risk_peak", "tools", "physical", "license"}


def grams(text):
    text = re.sub(r"\s+", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)}


def decode(blob):
    return ormsgpack.unpackb(bytes(blob), ext_hook=lambda c, d: d, option=ormsgpack.OPT_NON_STR_KEYS)


def load(version, conn):
    rows = []
    for path in sorted(glob.glob(rf"S:\caliburn\.research-tmp\eval\{version}-*-?.json")):
        run = json.load(open(path, encoding="utf-8"))
        work, ck = run["jd"]["work"], run["checks"]
        rep = tot = 0
        for task in work["tasks"]:
            base = grams(task["title"] + task["description"])
            for detail in task["outcomes"] + task["requirements"]:
                mine = grams(detail["text"])
                if mine:
                    tot += 1
                    rep += len(mine & base) / len(mine) >= 0.7
        fid = run["job_file_id"]
        tokens = sum(
            int(decode(b)["input_tokens"])
            for (b,) in conn.execute(
                "select blob from checkpoint_blobs where thread_id like %s and channel='input_count'", (f"{fid}:%",)
            )
        )
        cor = ck["correction"]
        rows.append(
            {
                "persona": run["persona"],
                "tasks": ck["shape"]["tasks"],
                "max_desc": max((len(t["description"]) for t in work["tasks"]), default=0),
                "rep": rep,
                "tot": tot,
                "aspects": sum(1 for k, v in ck["facts"].items() if k in HIDDEN and v["surfaced"]),
                "purpose": bool(run["jd"]["profile"].get("purpose")),
                "correction_ok": cor["new_present"] and cor["old_left_as_current"] == 0 and all(cor["unchanged_kept"]),
                "record_gaps": len(ck["recording_gaps"]),
                "failed_turns": sum(t.get("status") not in ("completed", None) for t in run["turns"]),
                "q": ck["style"]["questions_per_turn"],
                "chars": ck["style"]["mean_consultant_chars"],
                "minutes": sum(t.get("seconds") or 0 for t in run["turns"]) / 60,
                "tokens_m": tokens / 1e6,
                "cit_items": len({u["item"] for u in ck["citations"]["unsupported"]}),
                "cap": ck["shape"]["capabilities"],
                "cond": ck["shape"]["condition_items"],
                "collab": ck["shape"]["collaborator_items"],
            }
        )
    return rows


with psycopg.connect(URL, autocommit=True, options=f"-c search_path={schema} -c default_transaction_read_only=on") as conn:
    base, cand = load("q1", conn), load("q3", conn)
mean = lambda rows, key: statistics.mean(r[key] for r in rows)
by = lambda rows, persona: [r for r in rows if r["persona"] == persona]
print(f"runs: Q1 {len(base)}, Q3 {len(cand)}")
asked_mean = mean(cand, "aspects")
asked_runs = sum(r["aspects"] >= 1 for r in cand)
a = asked_mean >= 1 and asked_runs >= 4
print(f"(a) hidden aspects asked/run {mean(base,'aspects'):.2f} -> {asked_mean:.2f}; runs with >=1: {asked_runs}/{len(cand)} (need mean>=1 and >=4/6)  => {a}")
purposes = sum(r["purpose"] for r in cand)
b = purposes == len(cand) == 6
print(f"(b) purpose written {sum(r['purpose'] for r in base)}/{len(base)} -> {purposes}/{len(cand)} (need 6/6)  => {b}")
ca_c, ca_b = by(cand, "course_admin"), by(base, "course_admin")
wh_c, wh_b = by(cand, "warehouse"), by(base, "warehouse")
c = (
    bool(ca_c) and bool(wh_c)
    and mean(ca_c, "tasks") > mean(ca_b, "tasks") and mean(ca_c, "max_desc") < mean(ca_b, "max_desc")
    and mean(wh_c, "tasks") >= mean(wh_b, "tasks")
)
if ca_c and wh_c:
    print(f"(c) course_admin tasks {mean(ca_b,'tasks'):.2f}->{mean(ca_c,'tasks'):.2f}, max chars {mean(ca_b,'max_desc'):.0f}->{mean(ca_c,'max_desc'):.0f}; warehouse tasks {mean(wh_b,'tasks'):.2f}->{mean(wh_c,'tasks'):.2f}  => {c}")
ratio = lambda rows: sum(r["rep"] for r in rows) / max(1, sum(r["tot"] for r in rows))
d = ratio(cand) <= 0.30
print(f"(d) near-copy outcomes/requirements {ratio(base):.3f} -> {ratio(cand):.3f} (need <=0.30)  => {d}")
print("--- no-harm")
h1 = all(r["correction_ok"] for r in cand)
h2 = all(r["record_gaps"] <= 1 for r in cand)
h3 = sum(r["failed_turns"] for r in cand) == 0
h4 = sum(r["cit_items"] for r in cand)
h5 = mean(cand, "tokens_m") <= 1.15 * mean(base, "tokens_m")
h6 = mean(cand, "minutes") <= 1.3 * mean(base, "minutes")
h7 = mean(cand, "q") <= 1.3 * mean(base, "q") and mean(cand, "chars") <= 1.3 * mean(base, "chars")
print(f"correction effective all: {h1}; record gaps <=1 each: {h2}; failed turns 0: {h3} ({sum(r['failed_turns'] for r in cand)})")
print(f"flagged distinct citation items (read each by hand; need real omissions <=1): {h4}")
print(f"mean counted input tokens {mean(base,'tokens_m'):.2f}M -> {mean(cand,'tokens_m'):.2f}M (limit {1.15*mean(base,'tokens_m'):.2f}M): {h5}")
print(f"mean minutes {mean(base,'minutes'):.1f} -> {mean(cand,'minutes'):.1f} (limit {1.3*mean(base,'minutes'):.1f}): {h6}; questions/chars per turn within +30%: {h7}")
print(f"informational: K/S {mean(base,'cap'):.2f}->{mean(cand,'cap'):.2f}; conditions {mean(base,'cond'):.2f}->{mean(cand,'cond'):.2f}; collaborators {mean(base,'collab'):.2f}->{mean(cand,'collab'):.2f}")
effects = a and b and c and d
harm = h1 and h2 and h3 and h5 and h6 and h7
print(f"\nREGISTERED Q3 RULE (before the manual read of citations/fabrication): effects={effects}, no-harm numbers={harm}  => {'ADOPT-CANDIDATE' if effects and harm else 'DO NOT ADOPT'}")
