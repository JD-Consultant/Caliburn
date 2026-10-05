"""Project only the selected representation at the start of a new research episode."""

import hashlib
import json
from typing import Literal

from baseline_store import HERE, ROOT
from caliburn.adapters.database import Database
from caliburn.adapters.response_serialization import NativeItems
from caliburn.features.interviews.persistence import list_formal_interviews
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from jd_workspace import ResearchJdTurn

type StudyArm = Literal["raw", "summary", "memory"]


async def initial_reference(
    database: Database, turn: ResearchJdTurn, arm: StudyArm, memory: MemoryReadTools
) -> dict[str, object]:
    async with database.sessions() as session:
        messages = await list_formal_interviews(session, turn.writer.scope.job_file_id)
    if [m.interview_sequence for m in messages] != list(range(1, 106)):
        raise ValueError("A reset episode must begin at the frozen e052 frontier")
    selected = messages if arm == "raw" else messages[-5:]
    reference: dict[str, object] = {
        "data_kind": "research_reset_reference",
        "historical_interview": {
            "data_kind": "historical_interview",
            "messages": [
                {
                    "interview_sequence": m.interview_sequence,
                    "speaker": m.speaker.value,
                    "text": m.interview_text,
                }
                for m in selected
            ],
        },
    }
    if arm == "summary":
        manifest = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
        source = next(s for s in manifest["source_files"] if s["role"] == "flat_summary")
        raw = (ROOT / source["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError("Frozen summary changed")
        reference.update(work_summary=raw.decode("utf-8"), summary_through_sequence=104)
    elif arm == "memory":
        for layer in ("work_situation", "work_understanding"):
            mapping = json.loads(await memory.invoke(f"read_{layer}_map", "{}"))
            if "items" not in mapping:
                raise ValueError("Unable to load the fixed Memory map")
            reference[f"{layer}_map"] = mapping
        reference["memory_covered_through_sequence"] = 104
    return reference


def append_turn_input(
    history: NativeItems, reference: dict[str, object], employee_input: str
) -> NativeItems:
    """Do not flatten, rename, deduplicate or regenerate any native prior item."""
    return [
        *history,
        {"role": "user", "content": json.dumps(reference, ensure_ascii=False)},
        {"role": "user", "content": employee_input},
    ]
