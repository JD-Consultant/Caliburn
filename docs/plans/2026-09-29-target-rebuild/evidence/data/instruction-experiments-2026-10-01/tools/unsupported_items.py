"""Explain every item the citation audit flags: what it says, what it cites, where the fact was said.

Usage: unsupported_items.py <result.json> [<result.json> ...]
For each flagged (fact, item): the item text, the cited interview sequences with a snippet, and the
employee sequences whose text contains the fact's markers. A real omission cites a turn that does not
say the fact while another turn does; a marker artifact shows the cited turn saying it in other words.
"""

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
PERSONAS = json.load(open(r"S:\caliburn\apps\api\tests\fixtures\job_analysis_quality\personas.json", encoding="utf-8"))


def items_of(run):
    work, profile = run["jd"]["work"], run["jd"]["profile"]
    items = {}
    for area in work["areas"]:
        items["area", area["area_id"]] = f"{area['title']} {area.get('scope_text') or ''}"
    for task in work["tasks"]:
        items["task", task["task_id"]] = f"{task['title']} {task['description']}"
        for detail in task["outcomes"] + task["requirements"]:
            items["detail", detail["detail_id"]] = detail["text"]
    for person in work["collaborators"]:
        items["collaborator", person["collaborator_id"]] = f"{person.get('name') or ''} {person.get('scope_text') or ''}"
    for condition in work["conditions"]:
        items["condition", condition["condition_id"]] = condition["text"]
    for field, value in profile.items():
        if isinstance(value, str):
            items["profile_field", field] = value
    return items


for path in sys.argv[1:]:
    run = json.load(open(path, encoding="utf-8"))
    persona = PERSONAS[run["persona"]]
    items = items_of(run)
    cited = {}
    for reference in run["references"]:
        target = reference["target"]
        key = (target["kind"], target["field"] or target["item_id"])
        cited.setdefault(key, []).append(reference)
    employee = [
        (index + 1, m["interview_text"])
        for index, m in enumerate(run["_messages"])
        if m["speaker"] == "employee"
    ] if "_messages" in run else []
    print(f"=== {path}: {len(run['checks']['citations']['unsupported'])} flagged of {run['checks']['citations']['checked']}")
    facts = {f["id"]: f for f in persona["facts"]}
    for flagged in run["checks"]["citations"]["unsupported"]:
        fact = facts[flagged["fact"]]
        kind_label = flagged["item"].split(":")[0]
        for key, text in items.items():
            if key[0] != kind_label or not text.startswith(flagged["item"].split(":", 1)[1][:20]):
                continue
            print(f"- fact {fact['id']} keys={fact['keys']}")
            print(f"  item {key[0]}: {text[:160]}")
            for reference in cited.get(key, []):
                content = run["source_contents"].get(reference["citation_id"], {})
                print(f"  cites {reference['source_label']}: {(content.get('interview_text') or str(content))[:110]}")
            break
