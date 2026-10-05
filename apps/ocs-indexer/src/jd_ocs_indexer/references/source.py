"""Project validated source JSON into complete catalogs and title-free D/T bodies."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from ocs_contract.models import OCSDocument, TaskGroup

PREPROCESSING = "ocs_top_body_v1"


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


def clean_body(text: str) -> str:
    """Same body normalization as the frozen retrieval experiments; no K/S input."""
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*#{1,6}\s+", "", line)
        line = re.sub(r"(?<![A-Za-z0-9])[TOPKS]\d+(?:[.\-]\d+)*(?=\s|[:：、,，;；)]|$)", "", line)
        line = re.sub(r"^\s*[-*•⚫]\s*", "", line).replace("**", "")
        line = re.sub(r"\s+", " ", line).strip()
        if line and line not in {"工作產出", "行為指標", "知識", "技能", "工作內容"}:
            lines.append(line)
    return "\n".join(lines)


def _body(parts: list[str]) -> str:
    return "\n".join(
        dict.fromkeys(value for part in parts if (value := clean_body(part).replace("\n", "")))
    )


def build_reference(source_utf8: str, *, source_file: str) -> ReferenceDocument:
    source = OCSDocument.model_validate_json(source_utf8)
    code = source.ocs_profile.ocs_code
    if not code.strip() or code == "Unknown":
        raise ValueError("a public source must have an OCS code")
    digest = hashlib.sha256(source_utf8.encode("utf-8")).hexdigest()
    reference_id = str(uuid5(NAMESPACE_URL, f"caliburn:ocs:{code}:{digest}"))
    parts = [source.ocs_profile.job_description or ""]
    chunks = []
    if overview := _body(parts):
        chunks.append(SearchChunk("overview", "overview", overview))
    tasks = []
    units = source.ocs_content.ocu_units if source.ocs_content else []
    for unit_index, unit in enumerate(units or [], 1):
        unit_id = f"u{unit_index}"
        parts.append(unit.ocu_name or "")
        for task_index, group in enumerate(unit.tasks or [], 1):
            task_id = f"{unit_id}-t{task_index}"
            tasks.append(TaskEntry(task_id, unit_id, group))
            task_parts = [item.name or "" for item in group.task_codes or []]
            for block in group.competency_blocks or []:
                task_parts.extend(item.name or "" for item in block.outputs or [])
                task_parts.extend(item.text or "" for item in block.indicators or [])
            parts.extend(task_parts)
            if text := _body([unit.ocu_name or "", *task_parts]):
                chunks.append(SearchChunk(task_id, "task", text, task_id))
    return ReferenceDocument(
        reference_id,
        digest,
        source_file,
        source_utf8,
        source,
        _body(parts),
        tuple(chunks),
        tuple(tasks),
    )
