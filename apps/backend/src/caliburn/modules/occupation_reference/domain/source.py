"""Preserve validated sources and project cleaned JSON into D/T search bodies."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from ocs_contract.models import OCSDocument, TaskGroup

from caliburn.modules.occupation_reference.domain.cleaning import clean_document

PREPROCESSING = "ocs_clean_document_v1"


@dataclass(frozen=True)
class TaskEntry:
    task_id: str
    unit_id: str
    group: TaskGroup


@dataclass(frozen=True)
class SearchChunk:
    chunk_id: str
    kind: str
    text: str
    task_id: str | None = None


@dataclass(frozen=True)
class ReferenceDocument:
    reference_id: str
    source_sha256: str
    source_file: str
    source_utf8: str
    source: OCSDocument
    document_text: str
    chunks: tuple[SearchChunk, ...]
    tasks: tuple[TaskEntry, ...]

    @property
    def ocs_code(self) -> str:
        return self.source.ocs_profile.ocs_code


def build_reference(source_utf8: str, *, source_file: str) -> ReferenceDocument:
    source = OCSDocument.model_validate_json(source_utf8)
    code = source.ocs_profile.ocs_code
    if not code.strip() or code == "Unknown":
        raise ValueError("a public source must have an OCS code")
    digest = hashlib.sha256(source_utf8.encode("utf-8")).hexdigest()
    reference_id = str(uuid5(NAMESPACE_URL, f"caliburn:ocs:{code}:{digest}"))
    cleaned = clean_document(source)
    profile = cleaned["ocs_profile"]
    overview = {key: value for key, value in cleaned.items() if key != "ocs_content"}
    chunks = [
        SearchChunk(
            "overview",
            "overview",
            json.dumps(overview, ensure_ascii=False),
        )
    ]
    tasks = []
    units = source.ocs_content.ocu_units if source.ocs_content else []
    # Cleaning preserves source collection shapes and order.
    cleaned_content = cleaned.get("ocs_content", {})
    assert isinstance(cleaned_content, dict)
    cleaned_units = cleaned_content.get("ocu_units", [])
    assert isinstance(cleaned_units, list)
    for unit_index, (unit, cleaned_unit) in enumerate(
        zip(units or [], cleaned_units, strict=True), 1
    ):
        unit_id = f"u{unit_index}"
        assert isinstance(cleaned_unit, dict)
        cleaned_groups = cleaned_unit.get("tasks", [])
        assert isinstance(cleaned_groups, list)
        for task_index, (group, cleaned_group) in enumerate(
            zip(unit.tasks or [], cleaned_groups, strict=True), 1
        ):
            task_id = f"{unit_id}-t{task_index}"
            tasks.append(TaskEntry(task_id, unit_id, group))
            text = json.dumps(
                {
                    "ocs_profile": profile,
                    "ocu_name": cleaned_unit.get("ocu_name"),
                    "task_group": cleaned_group,
                    "notes": cleaned.get("notes"),
                },
                ensure_ascii=False,
            )
            chunks.append(SearchChunk(task_id, "task", text, task_id))
    return ReferenceDocument(
        reference_id,
        digest,
        source_file,
        source_utf8,
        source,
        json.dumps(cleaned, ensure_ascii=False),
        tuple(chunks),
        tuple(tasks),
    )
