"""目前或固定發布版的導覽、來源和 B1→B2 交接投影。"""

from collections.abc import Mapping, Sequence
from uuid import UUID

from caliburn.bundles.interview.context import (
    InterviewContextMessage,
    project_interview_context,
)
from caliburn.modules.agent.state import OpenAIItems
from caliburn.modules.interview.application.results import TranscriptMessage
from caliburn.modules.memory.application.results import MemoryInterviewMessage
from caliburn.modules.memory.domain.changes import describe_changes
from caliburn.modules.memory.domain.items import MemoryItem, MemoryKind, WorkSituation
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.shared.domain.text_editing.body_edits import describe_body_change


class ToolRejection(ValueError):
    def __init__(self, code: str, message: str, next_action: str) -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action


def source_unavailable() -> ToolRejection:
    return ToolRejection(
        "source_not_available",
        "至少一個來源無法在固定範圍完整取得。",
        "核對 message_* 引用或情境標題；範圍與保存問題由 App 處理。",
    )


def select_item(
    items: Sequence[MemoryItem], kind: MemoryKind, title: str
) -> MemoryItem:
    for item in items:
        if item.kind == kind and item.content.title == title:
            return item
    raise ToolRejection(
        "target_not_found",
        "目前可見導覽中沒有這個精確標題。",
        "重讀相應導覽，再選 target_title。",
    )


def item_header(item: MemoryItem) -> dict[str, str]:
    return {
        "target_title": item.content.title,
        "description": item.content.description,
    }


def map_items(
    items: Sequence[MemoryItem], kind: MemoryKind
) -> dict[str, list[dict[str, str]]]:
    return {"items": [item_header(item) for item in items if item.kind == kind]}


def item_view(
    item: MemoryItem, items: Sequence[MemoryItem], refs: Mapping[UUID, str]
) -> dict[str, object]:
    result: dict[str, object] = item.content.model_dump()
    if isinstance(item, WorkSituation):
        result["interview_references"] = [
            refs[message_id] for message_id in item.interview_message_ids
        ]
    else:
        by_id = {source.id: source for source in items}
        result["work_situation_references"] = [
            item_header(by_id[source_id]) for source_id in item.situation_ids
        ]
    return result


def historical_interview(
    selected: Sequence[UUID],
    *,
    messages: Sequence[MemoryInterviewMessage | TranscriptMessage],
    refs: Mapping[UUID, str],
) -> OpenAIItems:
    """保留 owner 順序並補必要原題，引用投影共用 Interview 的公開格式。"""
    by_id = {message.message_id: message for message in messages}
    if any(message_id not in by_id for message_id in selected):
        raise source_unavailable()
    selected_ids = set(selected)
    question_ids = {
        message.reply_to_message_id
        for message in messages
        if message.message_id in selected_ids
        and message.reply_to_message_id is not None
    }
    if not question_ids.issubset(by_id):
        raise source_unavailable()
    sources = tuple(
        InterviewContextMessage(
            TranscriptMessage(
                message_id=message.message_id,
                turn_id=message.turn_id,
                speaker=message.speaker,
                kind=message.kind,
                text=message.text,
                reply_to_message_id=message.reply_to_message_id,
            ),
            supporting_question=message.message_id not in selected_ids,
        )
        for message in messages
        if message.message_id in selected_ids or message.message_id in question_ids
    )
    return project_interview_context(sources, refs=refs)


def handoff_changes(
    baseline: MemorySnapshot | None,
    root: WorkMemory,
    refs: Mapping[UUID, str],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for change in describe_changes(baseline, root):
        before, after = change.before, change.after
        item = after if after is not None else before
        if not isinstance(item, WorkSituation):
            continue
        affected = {
            other.content.title
            for other in (*root.understandings, *(baseline.items if baseline else ()))
            if not isinstance(other, WorkSituation) and item.id in other.situation_ids
        }
        difference = describe_body_change(
            _comparison_text(before, refs),
            _comparison_text(after, refs),
        )
        entry: dict[str, object] = {
            "change": "added"
            if before is None
            else "removed"
            if after is None
            else "modified",
            "target_title": item.content.title,
            "affected_understanding_titles": sorted(affected),
            "diff": difference or "曾修改後改回，目前淨文字與來源相同，仍需判斷。",
        }
        if (
            before is not None
            and after is not None
            and before.content.title != after.content.title
        ):
            entry["previous_title"] = before.content.title
        results.append(entry)
    return results


def _comparison_text(item: MemoryItem | None, refs: Mapping[UUID, str]) -> str:
    if not isinstance(item, WorkSituation):
        return ""
    source_refs = ", ".join(refs[source] for source in item.interview_message_ids)
    return (
        f"標題：{item.content.title}\n導覽：{item.content.description}\n"
        f"訪談引用：{source_refs}\n\n"
        f"{item.content.body}"
    )
