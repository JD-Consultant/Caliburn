"""Apply the pre-registered M1-M4 criteria and guardrails (T14 evidence) to two versions of runs.

Usage: compare_versions.py <baseline-version> <candidate-version> [schema]
Reads S:/caliburn/.research-tmp/eval/<version>-<persona>-<n>.json and, for cost and time, the
read-only eval schema. Prints the numbers; the verdict lines follow the registered wording.
"""

import glob
import json
import re
import statistics
import sys
from collections import defaultdict

import psycopg

sys.stdout.reconfigure(encoding="utf-8")
DIR = r"S:\caliburn\.research-tmp\eval"
URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test"
HIDDEN_ASPECTS = {"limits", "quality_roster", "risk_peak", "tools", "physical", "license"}
supplemental = "--supplemental" in sys.argv
argv = [a for a in sys.argv[1:] if not a.startswith("--")]
baseline, candidate = argv[0], argv[1]
schema = argv[2] if len(argv) > 2 else "eval_b"


def load(version):
    runs = defaultdict(list)
    for path in sorted(glob.glob(f"{DIR}\\{version}-*-?.json")):
        run = json.load(open(path, encoding="utf-8"))
        runs[run["persona"]].append(run)
    return runs


def grams(text):
    text = re.sub(r"\s+", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)}


def redundancy(run):
    repeated = total = 0
    for task in run["jd"]["work"]["tasks"]:
        base = grams(task["title"] + task["description"])
        for detail in task["outcomes"] + task["requirements"]:
            mine = grams(detail["text"])
            if mine:
                total += 1
                repeated += len(mine & base) / len(mine) >= 0.7
    return repeated, total


def cost_and_attempts(connection, run):
    row = connection.execute(
        "select coalesce(sum(a.reported_cost_usd),0)::float, count(*) filter (where a.failure_code is not null) "
        "from executions e left join execution_outbound_attempts a on a.execution_id = e.execution_id "
        "where e.job_file_id = %s",
        (run["job_file_id"],),
    ).fetchone()
    return row


def metrics(runs, connection):
    out = []
    for run in runs:
        c = run["checks"]
        work = run["jd"]["work"]
        rep, tot = redundancy(run)
        facts = c["facts"]
        hidden_asked = [k for k, v in facts.items() if v["kind"] == "hidden" and v["surfaced"]]
        aspects_asked = [k for k in hidden_asked if k in HIDDEN_ASPECTS]
        cost, failed_attempts = cost_and_attempts(connection, run)
        capabilities = work["capabilities"]
        restating = sum(
            max((len(grams(c["name"]) & grams(t["title"] + t["description"])) / max(1, len(grams(c["name"]))) for t in work["tasks"]), default=0) >= 0.6
            for c in capabilities
        )
        cit_items = {u["item"] for u in c["citations"]["unsupported"]}
        cor = c["correction"]
        out.append(
            {
                "purpose": bool(run["jd"]["profile"].get("purpose")),
                "caps_n": len(capabilities),
                "caps_restating": restating,
                "cit_items": len(cit_items),
                "tasks": c["shape"]["tasks"],
                "max_desc": max((len(t["description"]) for t in work["tasks"]), default=0),
                "cap": c["shape"]["capabilities"],
                "cond": c["shape"]["condition_items"],
                "collab": c["shape"]["collaborator_items"],
                "rep": rep,
                "tot": tot,
                "hidden": len(hidden_asked),
                "aspects": len(aspects_asked),
                "q_turn": c["style"]["questions_per_turn"],
                "chars_turn": c["style"]["mean_consultant_chars"],
                "correction_ok": cor["new_present"]
                and cor["old_left_as_current"] == 0
                and all(cor["unchanged_kept"]),
                "record_gaps": len(c["recording_gaps"]),
                "cit_checked": c["citations"]["checked"],
                "cit_bad": len(c["citations"]["unsupported"]),
                "failed_turns": sum(t.get("status") != "completed" for t in run["turns"]),
                "seconds": sum(t.get("seconds") or 0 for t in run["turns"]),
                "cost": cost,
                "failed_attempts": failed_attempts,
            }
        )
    return out


def mean(values):
    return round(statistics.mean(values), 2) if values else None


with psycopg.connect(URL, autocommit=True, options=f"-c search_path={schema} -c default_transaction_read_only=on") as conn:
    base_runs, cand_runs = load(baseline), load(candidate)
    base = {p: metrics(r, conn) for p, r in base_runs.items()}
    cand = {p: metrics(r, conn) for p, r in cand_runs.items()}

fields = ["tasks", "max_desc", "cap", "cond", "collab", "hidden", "aspects", "q_turn", "chars_turn", "record_gaps", "seconds", "cost"]
print(f"{'':14}{'persona':14}{'n':3} " + " ".join(f"{f:>10}" for f in fields))
for label, group in ((baseline, base), (candidate, cand)):
    for persona, rows in group.items():
        print(f"{label:14}{persona:14}{len(rows):<3} " + " ".join(f"{mean([r[f] for r in rows]):>10}" for f in fields))

all_base = [r for rows in base.values() for r in rows]
all_cand = [r for rows in cand.values() for r in rows]
print()
# M1 granularity (as clarified in the T14 evidence before any candidate run)
def persona_mean(group, persona, field):
    return mean([r[field] for r in group[persona]])


ceiling = {persona: max(r["tasks"] for r in rows) for persona, rows in base.items()}
at_or_above = sum(r["tasks"] >= ceiling[persona] for persona, rows in cand.items() for r in rows)
m1_a = (
    persona_mean(cand, "course_admin", "tasks") > persona_mean(base, "course_admin", "tasks")
    and persona_mean(cand, "course_admin", "max_desc") < persona_mean(base, "course_admin", "max_desc")
)
m1_b = persona_mean(cand, "warehouse", "tasks") >= persona_mean(base, "warehouse", "tasks")
m1_c = at_or_above >= 5
m1 = m1_a and m1_b and m1_c
print(
    f"M1 granularity: (a) course_admin tasks {persona_mean(base,'course_admin','tasks')}->{persona_mean(cand,'course_admin','tasks')} "
    f"and max task chars {persona_mean(base,'course_admin','max_desc')}->{persona_mean(cand,'course_admin','max_desc')}: {m1_a}; "
    f"(b) warehouse tasks {persona_mean(base,'warehouse','tasks')}->{persona_mean(cand,'warehouse','tasks')} not lower: {m1_b}; "
    f"(c) runs with tasks >= baseline persona max {at_or_above}/{len(all_cand)} (need >=5): {m1_c}  => {'MET' if m1 else 'NOT MET'}"
)
# M2 recording
runs_with = lambda rows, f: sum(r[f] > 0 for r in rows)
cap_gain = runs_with(all_cand, "cap") - runs_with(all_base, "cap")
cond_gain = runs_with(all_cand, "cond") - runs_with(all_base, "cond")
collab_ok = mean([r["collab"] for r in all_cand]) >= mean([r["collab"] for r in all_base])
m2 = cap_gain >= 2 and cond_gain >= 2 and collab_ok
print(f"M2 recording: runs with capabilities {runs_with(all_base,'cap')}->{runs_with(all_cand,'cap')} (gain {cap_gain}); "
      f"runs with conditions {runs_with(all_base,'cond')}->{runs_with(all_cand,'cond')} (gain {cond_gain}); collaborators not fewer={collab_ok}  => {'MET' if m2 else 'NOT MET'}")
# M3 redundancy
ratio = lambda rows: sum(r["rep"] for r in rows) / max(1, sum(r["tot"] for r in rows))
m3 = ratio(all_cand) < ratio(all_base)
print(f"M3 redundancy: repeated outcomes/requirements {round(ratio(all_base),3)} -> {round(ratio(all_cand),3)}  => {'MET' if m3 else 'NOT MET'}")
# M4 guidance
hid_up = mean([r["aspects"] for r in all_cand]) > mean([r["aspects"] for r in all_base])
q_ok = mean([r["q_turn"] for r in all_cand]) <= 1.3 * mean([r["q_turn"] for r in all_base])
c_ok = mean([r["chars_turn"] for r in all_cand]) <= 1.3 * mean([r["chars_turn"] for r in all_base])
m4 = hid_up and q_ok and c_ok
print(f"M4 guidance: hidden aspects asked per run {mean([r['aspects'] for r in all_base])} -> {mean([r['aspects'] for r in all_cand])}; "
      f"questions/turn within +30%={q_ok}; chars/turn within +30%={c_ok}  => {'MET' if m4 else 'NOT MET'}")
# M5 purpose (informational, not part of the adoption rule)
purpose_count = lambda rows: sum(r["purpose"] for r in rows)
print(f"M5 purpose written (informational): {purpose_count(all_base)}/{len(all_base)} -> {purpose_count(all_cand)}/{len(all_cand)} (expect >=5/6)")
# guardrails
g_cor = sum(r["correction_ok"] for r in all_cand)
g_rec = all(r["record_gaps"] <= 1 for r in all_cand)
rate = lambda rows: 1 - sum(r["cit_bad"] for r in rows) / max(1, sum(r["cit_checked"] for r in rows))
g_cit = rate(all_cand) >= rate(all_base)
g_fail = sum(r["failed_turns"] for r in all_cand) == 0
g_cost = mean([r["cost"] for r in all_cand]) <= 2 * max(1e-9, mean([r["cost"] for r in all_base]))
g_time = mean([r["seconds"] for r in all_cand]) <= 2 * mean([r["seconds"] for r in all_base])
print(f"guardrails: correction effective {g_cor}/{len(all_cand)} (need all); record gaps <=1 each={g_rec}; "
      f"citation support {round(rate(all_base),3)} -> {round(rate(all_cand),3)} (not lower={g_cit}); failed turns={g_fail}; "
      f"time <=2x={g_time}; cost <=2x={g_cost}")
print("(guardrail not computed here: manual transcript/JD read for fabricated facts or unknowns written as known)")
met_others = sum([m2, m3, m4])
verdict = m1 and met_others >= 2 and g_cor == len(all_cand) and g_rec and g_cit and g_fail and g_cost and g_time
print(f"\nREGISTERED RULE (before the manual read): M1={m1}, other metrics met={met_others}/3, guardrails computed all pass="
      f"{g_cor == len(all_cand) and g_rec and g_cit and g_fail and g_cost and g_time}  => {'ADOPT-CANDIDATE' if verdict else 'DO NOT ADOPT'}")


if supplemental:
    caps_total = sum(r["caps_n"] for r in all_cand)
    caps_restating = sum(r["caps_restating"] for r in all_cand)
    ratio_ks = caps_restating / max(1, caps_total)
    runs_with_caps = sum(r["caps_n"] > 0 for r in all_cand)
    m6 = ratio_ks <= 0.25 and runs_with_caps >= 3
    cit_items_total = sum(r["cit_items"] for r in all_cand)
    cit_ok = cit_items_total <= 1
    print(f"M6 knowledge/skill noise: {caps_restating}/{caps_total} restate a task ({ratio_ks:.0%}, need <=25%); runs with capabilities {runs_with_caps}/6 (need >=3)  => {'MET' if m6 else 'NOT MET'}")
    print(f"citation guardrail (amended): distinct flagged items {cit_items_total} (need <=1; read each by hand, none may contradict its source)  => {'WITHIN' if cit_ok else 'EXCEEDED'}")
    other_guardrails = g_cor == len(all_cand) and g_rec and g_fail and g_cost and g_time
    supplemental_verdict = m1 and met_others >= 2 and m6 and cit_ok and other_guardrails
    print(f"SUPPLEMENTAL RULE (before the manual read): M1={m1}, M2-M4 met={met_others}/3, M6={m6}, citation within={cit_ok}, other guardrails={other_guardrails}  => {'ADOPT-CANDIDATE' if supplemental_verdict else 'DO NOT ADOPT'}")
