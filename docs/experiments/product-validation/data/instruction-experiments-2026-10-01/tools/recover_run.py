"""Rebuild the result file of a simulated interview whose harness died before it wrote one.

Usage: recover_run.py <persona> <label> <job_file_id> <stdout.log> <output.json> [--base-url URL]
The product kept everything: the formal interview, the JD and its sources. This reads them back through
the same HTTP endpoints and the same checks as scripts/simulate_interview.py, takes the per-turn seconds
from the harness's stdout log, and marks the file `"recovered": true` so a reader knows it was not
written by the harness itself. Nothing is sent to any model.
"""

import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, r"S:\caliburn\apps\api")
import httpx2  # noqa: E402

from scripts import simulate_interview as sim  # noqa: E402

persona_name, label, job_file_id, log_path, output = sys.argv[1:6]
base_url = sys.argv[sys.argv.index("--base-url") + 1] if "--base-url" in sys.argv else "http://127.0.0.1:8103"


async def main() -> None:
    persona = json.loads(sim.PERSONAS.read_text(encoding="utf-8"))[persona_name]
    async with httpx2.AsyncClient(base_url=base_url, timeout=60) as http:
        backend = sim.Backend(http)
        backend.file_id = job_file_id
        collected = await sim.collect(backend)
    messages = collected["interviews"]
    employee = [m for m in messages if m["speaker"] == "employee"]
    replies = [m for m in messages if m["speaker"] == "consultant"]
    seconds = [
        float(m.group(1)) for m in re.finditer(r"turn \d+: completed in ([0-9.]+)s", Path(log_path).read_text(encoding="utf-8"))
    ]
    turns = [
        {
            "turn": index + 1,
            "status": "completed" if index < len(replies) else "unknown",
            "seconds": seconds[index] if index < len(seconds) else None,
            "employee": message["interview_text"],
            "consultant": replies[index]["interview_text"] if index < len(replies) else None,
        }
        for index, message in enumerate(employee)
    ]
    result = {
        "persona": persona_name,
        "label": label,
        "started": datetime.now(UTC).isoformat(),
        "recovered": True,
        "recovery_note": "The harness stopped before writing this file (see the harness stderr); rebuilt from the stored interview and JD.",
        "job_file_id": job_file_id,
        "turns": turns,
        "events": [],
        "jd": {"profile": collected["profile"], "work": collected["work"]},
        "references": collected["references"],
        "source_contents": collected["source_contents"],
        "checks": sim.evaluate(persona, collected),
    }
    with Path(output).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
    print(f"recovered {len(turns)} turns -> {output}")


asyncio.run(main())
