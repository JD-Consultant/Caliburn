"""Pure fixed-revision handoff projection; no database or execution resources."""

from dataclasses import dataclass
from difflib import unified_diff
from uuid import UUID

from pydantic import JsonValue

from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryObjectRevision


@dataclass(frozen=True, slots=True)
class SituationRevision:
    content: MemoryContent
    interview_sequences: tuple[int, ...]

    @classmethod
    def from_revision(
        cls, revision: MemoryObjectRevision, sequences: dict[UUID, int]
    ) -> SituationRevision:
        return cls(
            revision.content,
            tuple(sorted(sequences[source] for source in revision.interview_references)),
        )


@dataclass(frozen=True, slots=True)
class SituationChange:
    before: SituationRevision | None
    after: SituationRevision | None
    affected_understanding_titles: tuple[str, ...]


def build_situation_handoff_changes(
    snapshot: tuple[SituationChange, ...],
) -> list[dict[str, JsonValue]]:
    changes: list[dict[str, JsonValue]] = []
    for change in snapshot:
        old, new = change.before, change.after
        selected = new if new is not None else old
        if selected is None:
            raise ValueError("A situation change requires a fixed revision")
        difference = "".join(
            unified_diff(
                _comparison_text(old).splitlines(keepends=True),
                _comparison_text(new).splitlines(keepends=True),
                fromfile="本批開始基準",
                tofile="本次情境交接",
                n=3,
            )
        )
        entry: dict[str, JsonValue] = {
            "change": "added" if old is None else "removed" if new is None else "modified",
            "target_title": selected.content.title,
            "affected_understanding_titles": list(change.affected_understanding_titles),
            "diff": f"```diff\n{difference}\n```"
            if difference
            else "修訂身分已變更；目前淨文字與來源集合相同，仍需判斷。",
        }
        if old is not None and new is not None and old.content.title != new.content.title:
            entry["previous_title"] = old.content.title
        changes.append(entry)
    return changes


def _comparison_text(revision: SituationRevision | None) -> str:
    if revision is None:
        return ""
    sequences = ", ".join(str(sequence) for sequence in revision.interview_sequences)
    return (
        f"標題：{revision.content.title}\n導覽：{revision.content.description}\n"
        f"訪談引用序號：{sequences}\n\n{revision.content.body}\n"
    )
