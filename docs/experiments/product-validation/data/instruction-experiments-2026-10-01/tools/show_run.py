"""Print one simulated-interview run: transcript, produced JD, and key checks. Usage: show_run.py <file> [--no-transcript]"""

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
if "--no-transcript" not in sys.argv:
    for t in d["turns"]:
        print(f"--- turn {t['turn']} [{t.get('status')}] {t.get('seconds', '')}s")
        print("員工:", t["employee"])
        print("顧問:", t.get("consultant"))
        print()
w = d["jd"]["work"]
p = d["jd"]["profile"]
caps = {c["capability_id"]: c for c in w["capabilities"]}
print("=========== JD")
print("基本資料:", {k: v for k, v in p.items()})
for a in w["areas"]:
    print(f"\n【職責】{a['title']} — {a['scope_text']}")
    for t in [t for t in w["tasks"] if t["area_id"] == a["area_id"]]:
        print(f"  ▸ {t['title']}: {t['description']}")
        for o in t["outcomes"]:
            print(f"      成果: {o['text']}")
        for r in t["requirements"]:
            print(f"      要求: {r['text']}")
        for l in [l for l in w["task_links"] if l["task_id"] == t["task_id"]]:
            c = caps[l["capability_id"]]
            print(f"      能力: [{c['kind']}] {c['name']}")
un = [t for t in w["tasks"] if t["area_id"] is None]
for t in un:
    print(f"  ▸(未歸屬) {t['title']}: {t['description']}")
print("\n知識/技能:", [(c["kind"], c["name"]) for c in w["capabilities"]])
print("協作對象:", [(c.get("name"), c.get("scope_text")) for c in w["collaborators"]])
print("條件:", [(c.get("kind"), c.get("text")) for c in w["conditions"]])
c = d["checks"]
print("\n=========== checks")
print("recording_gaps:", c["recording_gaps"], "| elicitation_gaps:", c["elicitation_gaps"])
print("correction:", c["correction"])
print("profile_sources:", json.dumps(c["profile_sources"], ensure_ascii=False))
print("shape:", c["shape"]); print("style:", c["style"])
