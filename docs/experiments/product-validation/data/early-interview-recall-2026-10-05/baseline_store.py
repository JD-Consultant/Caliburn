"""Hydrate the frozen exported fixture into an empty research namespace.

This is not a product import/history-recovery feature. It installs one fixed JD
revision and formal source membership, not old executions or opaque checkpoints.
Subsequent changes must use the real product tools and completion workflow.
"""

import gzip
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from caliburn.adapters.database import Database
from caliburn.features.interviews.models import InterviewHistoryEntry, InterviewMessage
from caliburn.features.interviews.persistence import FormalInterviewRecord, InterviewTextRecord
from caliburn.features.job_description import (
    area_persistence,
    capability_persistence,
    collaborator_persistence,
    condition_persistence,
    persistence,
    source_persistence,
    task_persistence,
)
from caliburn.features.job_description.models import JdProfileRevision
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
)
from caliburn.features.job_description.work_queries import JdWorkRevision
from caliburn.features.job_files import service as job_files
from caliburn.features.job_files.models import CreateJobFile
from caliburn.features.job_files.persistence import JobFileRecord
from psycopg.conninfo import conninfo_to_dict
from pydantic import BaseModel
from sqlalchemy import func, select

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


class EvidenceEntry(BaseModel):
    citation_id: UUID
    source_kind: Literal["interview"]
    needs_recheck: bool
    jd_changed: bool
    source_changed: Literal[False]
    target: JdSourceTarget


class ExportedEvidence(BaseModel):
    entry: EvidenceEntry
    content: InterviewMessage


class ExportedBaseline(BaseModel):
    profile: JdProfileRevision
    work: JdWorkRevision
    evidence: tuple[ExportedEvidence, ...]
    interviews: tuple[InterviewHistoryEntry, ...]


class JdAnchor(BaseModel):
    profile: JdProfileRevision
    work: JdWorkRevision
    references: tuple[JdSourceReference, ...] = ()


class ReferenceBaselines(BaseModel):
    revision_id: UUID
    references: tuple[JdSourceReference, ...]
    anchors: tuple[JdAnchor, ...]


def read_reference_baselines(baseline: ExportedBaseline) -> ReferenceBaselines:
    manifest = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    source = next(
        item for item in manifest["source_files"] if item["role"] == "jd_review_baselines"
    )
    raw = (ROOT / source["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError("Frozen review anchor capture changed")
    captured = ReferenceBaselines.model_validate_json(gzip.decompress(raw))
    expected = tuple(
        JdSourceReference(
            item.entry.citation_id,
            item.entry.target,
            InterviewSource(item.content.source_id),
            needs_review=item.entry.needs_recheck,
        )
        for item in baseline.evidence
    )
    if captured.revision_id != baseline.profile.revision_id or len(captured.references) != len(
        expected
    ):
        raise ValueError("Review capture belongs to a different baseline")
    for actual, original in zip(captured.references, expected, strict=True):
        if (actual.citation_id, actual.target, actual.source, actual.needs_review) != (
            original.citation_id,
            original.target,
            original.source,
            original.needs_review,
        ):
            raise ValueError("Review capture differs from original exported evidence")
    return captured


def read_baseline() -> ExportedBaseline:
    manifest = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    source = next(
        item for item in manifest["source_files"] if item["role"] == "jd_and_formal_interviews"
    )
    raw = (ROOT / source["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError("Frozen baseline hash changed; do not silently replace it")
    baseline = ExportedBaseline.model_validate_json(raw)
    messages = {item.message.source_id: item.message for item in baseline.interviews}
    if (
        baseline.profile.revision_id != baseline.work.revision_id
        or [item.message.interview_sequence for item in baseline.interviews] != list(range(1, 106))
        or len(messages) != 105
        or any(messages.get(item.content.source_id) != item.content for item in baseline.evidence)
    ):
        raise ValueError("Baseline source identity, content or frontier mismatch")
    return baseline


def require_research_database(database: Database) -> None:
    info = conninfo_to_dict(database.settings.url)
    name = info.get("dbname")
    if (
        set(info) - {"host", "port", "dbname", "user", "password"}
        or any(
            os.environ.get(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
        )
        or info.get("host") not in {"127.0.0.1", "localhost", "::1"}
        or not isinstance(name, str)
        or not name.endswith("_test")
        or not re.fullmatch(r"(?:t02|eval_reset)_[0-9a-f]{32}", database.settings.schema)
    ):
        raise ValueError("Only a fresh loopback research/test namespace is allowed")


async def seed_baseline(database: Database) -> UUID:
    require_research_database(database)
    baseline = read_baseline()
    captured = read_reference_baselines(baseline)
    revisions = {anchor.profile.revision_id: anchor for anchor in captured.anchors}
    revisions[baseline.profile.revision_id] = JdAnchor(profile=baseline.profile, work=baseline.work)
    works = [anchor.work for anchor in revisions.values()]
    async with database.sessions.begin() as session:
        if await session.scalar(select(func.count()).select_from(JobFileRecord)):
            raise ValueError("Baseline loading requires an empty namespace; never overwrite")
        created = await job_files.create_job_file(
            session, CreateJobFile(uuid4(), "換窗比較：合成庫存管理", "合成員工")
        )
        file_id = created.job_file.job_file_id
        # Preserve original source IDs/sequences. Old execution IDs are intentionally
        # not imported: this experiment starts a new context episode at this boundary.
        for entry in baseline.interviews:
            message = entry.message
            session.add(
                InterviewTextRecord(
                    job_file_id=file_id,
                    source_id=message.source_id,
                    speaker=message.speaker,
                    interview_text=message.interview_text,
                )
            )
        await session.flush()
        session.add_all(
            [
                FormalInterviewRecord(
                    job_file_id=file_id,
                    source_id=entry.message.source_id,
                    interview_sequence=entry.message.interview_sequence,
                )
                for entry in baseline.interviews
            ]
        )
        for area in {
            (x.area_id, x.content_revision_id): x for w in works for x in w.areas
        }.values():
            await area_persistence.insert_area_content(session, file_id, area)
        for task in {
            (x.task_id, x.content_revision_id): x for w in works for x in w.tasks
        }.values():
            await task_persistence.insert_task_content(session, file_id, task)
        for capability in {
            (x.capability_id, x.content_revision_id): x for w in works for x in w.capabilities
        }.values():
            await capability_persistence.insert_capability_content(session, file_id, capability)
        for collaborator in {
            (x.collaborator_id, x.content_revision_id): x for w in works for x in w.collaborators
        }.values():
            await collaborator_persistence.insert_collaborator_content(
                session, file_id, collaborator
            )
        for condition in {
            (x.condition_id, x.content_revision_id): x for w in works for x in w.conditions
        }.values():
            await condition_persistence.insert_condition_content(session, file_id, condition)
        for anchor in revisions.values():
            work = anchor.work
            await persistence.insert_revision(
                session,
                file_id,
                anchor.profile,
                parent_revision_id=None,
                areas=work.areas,
                tasks=work.tasks,
                capabilities=work.capabilities,
                task_links=work.task_links,
                collaborators=work.collaborators,
                conditions=work.conditions,
            )
        for anchor in revisions.values():
            if anchor.profile.revision_id != baseline.profile.revision_id:
                await source_persistence.insert_source_references(
                    session, file_id, anchor.profile.revision_id, anchor.references
                )
        await source_persistence.insert_source_references(
            session,
            file_id,
            baseline.profile.revision_id,
            captured.references,
        )
        session.add(
            persistence.JobDescriptionRecord(
                job_file_id=file_id,
                initial_revision_id=baseline.profile.revision_id,
                current_revision_id=baseline.profile.revision_id,
            )
        )
    return file_id
