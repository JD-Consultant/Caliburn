"""Drive the four background stop points, each as two real Windows processes."""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

APP = Path("S:/caliburn/experiments/jd-relational-app")
PROBE = APP / "tests" / "support" / "background_recovery_probe.py"
OUT = Path("S:/caliburn/docs/specs/evidence/jd-b1-adoption/new-process-recovery")
OUT.mkdir(parents=True, exist_ok=True)
STOPS = ("b1_model_saved", "b1_done", "b2_pending", "b2_published_reply_lost")

env = {**os.environ, "JD_RELATIONAL_TEST_DB": "1", "PYTHONUTF8": "1"}
report = {"format": 1, "probe": str(PROBE.relative_to(APP.parents[1])), "runs": []}

for stop in STOPS:
    target = Path("S:/caliburn/.research-tmp") / ("jd-b-recovery-" + uuid.uuid4().hex)
    run = {"stop": stop, "fixture": target.name}
    for mode in ("stage", "resume"):
        done = subprocess.run(
            ["uv", "run", "--offline", "--frozen", "--no-sync", "python", str(PROBE),
             mode, str(target), "--stop", stop],
            cwd=APP, env=env, capture_output=True, text=True, errors="replace")
        run[mode + "_exit"] = done.returncode
        if done.returncode != 0:
            run[mode + "_stderr"] = done.stderr.strip()[-600:]
            break
    for name in ("stage", "resume"):
        path = target / f"{name}.json"
        if path.exists():
            run[name] = json.loads(path.read_text(encoding="utf-8"))
    report["runs"].append(run)
    print(json.dumps({k: v for k, v in run.items() if not isinstance(v, dict)},
                     ensure_ascii=False), flush=True)

(OUT / "runs.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", OUT / "runs.json")
sys.exit(0 if all(r.get("resume_exit") == 0 for r in report["runs"]) else 1)
