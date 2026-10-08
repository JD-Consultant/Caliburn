"""B2 handoff projection from retained candidate positions, never a second diff store."""

from difflib import unified_diff

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import candidate_queries as queries
from caliburn.features.work_memory.candidates import MemoryBatchPosition, MemoryPermissionError
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryObjectRevision


async def read_situation_handoff_changes(
    session: AsyncSession, stage: MemoryBatchPosition
) -> list[dict[str, JsonValue]]:
    """Compare batch origin to the fixed B1 handoff; include additions without dependents.

    App IDs/revisions stay internal. Markdown hunks retain context and source changes;
    unchanged text after revisions is still a change, not evidence of analysis completion.
    No history-version parameter is exposed to the model.
    """
    if stage.phase != MemoryLayer.WORK_UNDERSTANDING:
        raise MemoryPermissionError("Only B2 receives situation impact information")
    batch = await queries.require_stage(session, stage)
    before = await queries.read_members(session, stage.job_file_id, batch.base_position_id)
    after = await queries.read_members(session, stage.job_file_id, stage.position_id)
    affected: dict[object, list[str]] = {}
    for members in (before, after):
        for identity in members:
            revision = await queries.read_selected(session, stage.job_file_id, members, identity)
            if revision.layer == MemoryLayer.WORK_UNDERSTANDING:
                for reference in revision.work_situation_references:
                    titles = affected.setdefault(reference.object_id, [])
                    if revision.content.title not in titles:
                        titles.append(revision.content.title)
    changes: list[dict[str, JsonValue]] = []
    for identity in sorted(before.keys() | after.keys()):
        if before.get(identity) == after.get(identity):
            continue
        old = (
            await queries.read_selected(session, stage.job_file_id, before, identity)
            if identity in before
            else None
        )
        new = (
            await queries.read_selected(session, stage.job_file_id, after, identity)
            if identity in after
            else None
        )
        selected = new if new is not None else old
        if selected is None or selected.layer != MemoryLayer.WORK_SITUATION:
            continue
        text_before = await _comparison_text(session, stage, old)
        text_after = await _comparison_text(session, stage, new)
        difference = "".join(
            unified_diff(
                text_before.splitlines(keepends=True),
                text_after.splitlines(keepends=True),
                fromfile="本批開始基準",
                tofile="本次情境交接",
                n=3,
            )
        )
        entry: dict[str, JsonValue] = {
            "change": "added" if old is None else "removed" if new is None else "modified",
            "target_title": selected.content.title,
            "affected_understanding_titles": list(affected.get(identity, [])),
            "diff": f"```diff\n{difference}\n```"
            if difference
            else "修訂身分已變更；目前淨文字與來源集合相同，仍需判斷。",
        }
        if old is not None and new is not None and old.content.title != new.content.title:
            entry["previous_title"] = old.content.title
        changes.append(entry)
    return changes


async def _comparison_text(
    session: AsyncSession, stage: MemoryBatchPosition, revision: MemoryObjectRevision | None
) -> str:
    if revision is None:
        return ""
    from caliburn.features.interviews import queries as interviews
    from caliburn.features.interviews.models import InterviewReadScope

    batch = await queries.require_stage(session, stage)
    sources = (
        await interviews.read_interview_sources(
            session,
            InterviewReadScope(stage.job_file_id, batch.through_sequence),
            source_ids=tuple(revision.interview_references),
        )
        if revision.interview_references
        else []
    )
    sequences = ", ".join(str(source.interview_sequence) for source in sources)
    return (
        f"標題：{revision.content.title}\n導覽：{revision.content.description}\n"
        f"訪談引用序號：{sequences}\n\n{revision.content.body}\n"
    )
