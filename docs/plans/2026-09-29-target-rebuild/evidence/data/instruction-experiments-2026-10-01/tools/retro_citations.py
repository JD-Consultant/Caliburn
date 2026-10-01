"""Recompute the citation audit for saved simulated-interview runs. Usage: retro_citations.py <version> [...]"""

import glob
import importlib.util
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("simulate_interview", r"S:\caliburn\apps\api\scripts\simulate_interview.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
personas = json.loads(sim.PERSONAS.read_text(encoding="utf-8"))
DIR = r"S:\caliburn\.research-tmp\eval"

total_checked = total_bad = 0
for version in sys.argv[1:]:
    for path in sorted(glob.glob(f"{DIR}\\{version}-*-?.json")):
        run = json.load(open(path, encoding="utf-8"))
        interviews = []
        for turn in run["turns"]:
            interviews.append({"speaker": "employee", "interview_text": turn["employee"]})
            if turn.get("consultant"):
                interviews.append({"speaker": "consultant", "interview_text": turn["consultant"]})
        collected = {
            "profile": run["jd"]["profile"],
            "work": run["jd"]["work"],
            "references": run["references"],
            "source_contents": run["source_contents"],
            "interviews": interviews,
        }
        audit = sim.citation_audit(personas[run["persona"]], collected)
        total_checked += audit["checked"]
        total_bad += len(audit["unsupported"])
        name = Path(path).stem
        print(f"{name:22s} checked {audit['checked']:3d} unsupported {len(audit['unsupported']):2d} rate {audit['support_rate']}")
        for row in audit["unsupported"][:6]:
            print("      ", row)
print(f"TOTAL checked {total_checked}, unsupported {total_bad}, rate {round(1 - total_bad / max(1, total_checked), 2)}")
