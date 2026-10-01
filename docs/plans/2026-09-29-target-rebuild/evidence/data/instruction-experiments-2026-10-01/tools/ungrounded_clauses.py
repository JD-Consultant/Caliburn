"""List JD clauses whose wording barely appears in anything the employee said (manual-review candidates).

Usage: ungrounded_clauses.py <result.json> [<result.json> ...] [--threshold 0.35]
A coarse screen, not a verdict: split every JD text into clauses and flag those whose character
bigrams overlap the employee's own words by less than the threshold. The reviewer then reads the
flagged clause against the transcript to decide whether it is a faithful paraphrase or an invention.
"""

import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
threshold = 0.35
paths = []
args = sys.argv[1:]
while args:
    arg = args.pop(0)
    if arg == "--threshold":
        threshold = float(args.pop(0))
    else:
        paths.append(arg)


def grams(text):
    text = re.sub(r"[\s，。；、：:（）()「」\"'．,;]", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)}


def texts(run):
    work, profile = run["jd"]["work"], run["jd"]["profile"]
    for field, value in profile.items():
        if isinstance(value, str):
            yield f"profile.{field}", value
    for area in work["areas"]:
        yield "area", f"{area['title']}：{area.get('scope_text') or ''}"
    for task in work["tasks"]:
        yield "task", f"{task['title']}：{task['description']}"
        for detail in task["outcomes"] + task["requirements"]:
            yield "detail", detail["text"]
    for capability in work["capabilities"]:
        yield capability["kind"], f"{capability['name']}：{capability.get('description') or ''}"
    for person in work["collaborators"]:
        yield "collaborator", f"{person.get('name') or ''}：{person.get('scope_text') or ''}"
    for condition in work["conditions"]:
        yield "condition", condition["text"]


total_flagged = total_clauses = 0
for path in paths:
    run = json.load(open(path, encoding="utf-8"))
    said = grams(" ".join(m["interview_text"] for m in run["_all_interviews"] if m["speaker"] == "employee")) if "_all_interviews" in run else None
    if said is None:
        said = grams(" ".join(t.get("employee") or "" for t in run["turns"]))
    flagged = []
    clauses = 0
    for kind, text in texts(run):
        for clause in re.split(r"[；。]", text):
            clause = clause.strip()
            mine = grams(clause)
            if len(mine) < 6:
                continue
            clauses += 1
            overlap = len(mine & said) / len(mine)
            if overlap < threshold:
                flagged.append((round(overlap, 2), kind, clause[:90]))
    total_flagged += len(flagged)
    total_clauses += clauses
    print(f"=== {path}: {len(flagged)} of {clauses} clauses below {threshold}")
    for overlap, kind, clause in sorted(flagged):
        print(f"  {overlap:.2f} [{kind}] {clause}")
print(f"\nTOTAL flagged {total_flagged} of {total_clauses}")
