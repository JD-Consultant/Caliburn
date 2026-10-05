"""Load fixed existing Memory, not a new model-generated analysis."""

import hashlib
import json
import re
from uuid import UUID, uuid4

from baseline_store import HERE, ROOT, require_research_database
from caliburn.adapters.database import Database
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.work_memory.candidates import CreateMemoryObject, MemorySnapshot
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryObjectRevision
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from pydantic import BaseModel


class FrozenMemory(BaseModel):
    snapshot: MemorySnapshot
    objects: tuple[MemoryObjectRevision, ...]


def read_memory_fixture() -> FrozenMemory:
    manifest = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    source = next(item for item in manifest["source_files"] if item["role"] == "memory")
    raw = (ROOT / source["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError("Frozen Memory hash changed")
    payload = json.loads(raw)
    # The old exporter serialized frozen-set members as repr strings. Parse only
    # this exact historical shape; never eval it or silently drop a link.
    pattern = re.compile(
        r"MemoryRevisionReference\(object_id=UUID\('([0-9a-f-]{36})'\), "
        r"revision_id=UUID\('([0-9a-f-]{36})'\)\)"
    )
    for item in payload["objects"]:
        references = []
        for value in item["work_situation_references"]:
            matched = pattern.fullmatch(value)
            if matched is None:
                raise ValueError("Unknown historical reference encoding")
            references.append({"object_id": matched[1], "revision_id": matched[2]})
        item["work_situation_references"] = references
    frozen = FrozenMemory.model_validate(payload)
    selected = {item.object_id: item for item in frozen.objects}
    if frozen.snapshot.covered_through_sequence != 104 or len(selected) != len(frozen.objects):
        raise ValueError("Unexpected Memory frontier or duplicate identity")
    for item in frozen.objects:
        for reference in item.work_situation_references:
            if reference.object_id not in selected or (
                selected[reference.object_id].revision_id != reference.revision_id
            ):
                raise ValueError("Memory source graph is not the fixed selected graph")
    return frozen


async def seed_memory(database: Database, file_id: UUID) -> UUID:
    require_research_database(database)
    frozen = read_memory_fixture()
    workflow = MemoryCandidateWorkflow(database.sessions)
    if await workflow.read_latest_snapshot(file_id) is not None:
        raise ValueError("Memory fixture already installed; do not overwrite")
    scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
    async with database.sessions.begin() as session:
        await executions.admit_execution(session, scope)
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
    stage = await workflow.start(writer, frozen.snapshot.through_source_id)
    if stage is None:
        raise ValueError("Expected an uncovered research Memory fixture")
    identities: dict[UUID, UUID] = {}
    for layer in (MemoryLayer.WORK_SITUATION, MemoryLayer.WORK_UNDERSTANDING):
        if layer == MemoryLayer.WORK_UNDERSTANDING:
            stage = await workflow.handoff(writer, stage, uuid4())
        for item in frozen.objects:
            if item.layer != layer:
                continue
            sources = (
                item.interview_references
                if layer == MemoryLayer.WORK_SITUATION
                else (
                    frozenset(identities[ref.object_id] for ref in item.work_situation_references)
                )
            )
            result = await workflow.edit(
                writer,
                CreateMemoryObject(
                    uuid4(),
                    stage,
                    layer,
                    item.content,
                    reference_ids=sources,
                ),
            )
            stage = result.position
            identities[item.object_id] = result.object_id
    snapshot = await workflow.publish(writer, stage, uuid4())
    return snapshot.snapshot_id
