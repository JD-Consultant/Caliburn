"""來源解析只用本輪固定發布版／精確標題，內容權威仍在 owner。"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from caliburn.bundles.job_description.services import JD_MEMORY_QUERIES
from caliburn.modules.job_description.domain.models.citation import MemoryReference
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.items import WorkSituation
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from tests.unit.bundles.job_description.test_write_tools import Harness, payload


class MemoryReader:
    def __init__(self, snapshot: MemorySnapshot) -> None:
        self.snapshot = snapshot

    def get_published(
        self, *, workspace_id: UUID, published_version: int | None
    ) -> MemorySnapshot | None:
        if (
            workspace_id != self.snapshot.workspace_id
            or published_version != self.snapshot.version
        ):
            raise AssertionError("工具不得暗換最新 Memory 版本")
        return self.snapshot


def prepare_memory(harness: Harness) -> MemoryReference:
    source = MemoryReference(
        workspace_id=harness.state["workspace_id"],
        published_version=3,
        item_id=UUID(int=76),
    )
    snapshot = MemorySnapshot(
        workspace_id=source.workspace_id,
        version=3,
        covered_through_message_id=UUID(int=77),
        published_at=datetime.now(UTC),
        items=(
            WorkSituation(
                id=source.item_id,
                workspace_id=source.workspace_id,
                content=MemoryContent(
                    title="盤點", description="定期盤點", body="核對庫存"
                ),
                interview_message_ids=(UUID(int=77),),
                changed_version=3,
            ),
        ),
    )
    harness.extra_services[JD_MEMORY_QUERIES] = MemoryReader(snapshot)
    harness.state["memory_published_version"] = 3
    harness.store.available_sources.add(source)
    return source


def test_memory_reference_uses_fixed_version_and_exact_title() -> None:
    harness = Harness()
    source = prepare_memory(harness)
    output = payload(
        harness.invoke(
            "revise_jd_profile",
            {
                "changes": [
                    {"action": "set_field", "field": "job_title", "value": "盤點員"},
                    {
                        "action": "add_source",
                        "source": {"kind": "work_situation", "target_title": "盤點"},
                    },
                ]
            },
        )
    )
    assert output["status"] == "updated"
    saved = harness.store.snapshot()
    assert saved.citations[0].source == source
    assert saved.citations[0].target_id == saved.job_description_id
    assert saved.citations[0].target_kind == "job_description"


@pytest.mark.parametrize(
    "source",
    [
        {"kind": "work_situation", "target_title": "盤點 "},
        {"kind": "work_understanding", "target_title": "盤點"},
        {"kind": "work_situation", "target_title": "自行摘要"},
    ],
)
def test_memory_title_or_layer_mismatch_rejects_entire_profile_edit(
    source: dict[str, str],
) -> None:
    harness = Harness()
    prepare_memory(harness)
    output = payload(
        harness.invoke(
            "revise_jd_profile",
            {
                "changes": [
                    {"action": "set_field", "field": "job_title", "value": "不該保存"},
                    {"action": "add_source", "source": source},
                ]
            },
        )
    )
    assert output["code"] == "source_not_available"
    assert harness.store.snapshot().job_title is None
    assert harness.store.commits == 0


def test_memory_confirmation_requires_fixed_runtime_version() -> None:
    harness = Harness()
    source = prepare_memory(harness)
    citation = harness.store.root.add_citation(
        target_kind="job_description", target_id=harness.store.root.id, source=source
    )
    harness.state["memory_published_version"] = None
    output = payload(
        harness.invoke(
            "revise_jd_profile",
            {
                "changes": [
                    {
                        "action": "confirm_reference_alignment",
                        "citation_ref": harness.ref("citation", citation),
                    }
                ]
            },
        )
    )
    assert output["code"] == "source_not_available"
    assert harness.store.commits == 0


def test_other_target_citation_cannot_be_removed_during_task_edit() -> None:
    harness = Harness()
    source = prepare_memory(harness)
    duty = harness.store.root.add_duty(name="職責")
    task = harness.store.root.add_task(name="任務")
    citation = harness.store.root.add_citation(
        target_kind="duty", target_id=duty, source=source
    )
    output = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": harness.ref("task", task),
                "changes": [
                    {"action": "set_field", "field": "name", "value": "不該保存"},
                    {
                        "action": "remove_source",
                        "citation_ref": harness.ref("citation", citation),
                    },
                ],
            },
        )
    )
    assert output["code"] == "target_not_found"
    assert harness.store.snapshot().tasks[0].name == "任務"
    assert harness.store.commits == 0


def test_memory_confirmation_advances_same_item_to_runtime_fixed_version() -> None:
    harness = Harness()
    current_source = prepare_memory(harness)
    old_source = current_source.model_copy(update={"published_version": 2})
    citation = harness.store.root.add_citation(
        target_kind="job_description",
        target_id=harness.store.root.id,
        source=old_source,
    )
    harness.store.root.set_citation_review(citation_id=citation, jd_changed=True)
    output = payload(
        harness.invoke(
            "revise_jd_profile",
            {
                "changes": [
                    {
                        "action": "confirm_reference_alignment",
                        "citation_ref": harness.ref("citation", citation),
                    }
                ]
            },
        )
    )
    assert output["status"] == "updated"
    saved = harness.store.snapshot().citations[0]
    assert saved.source == current_source
    assert saved.id == citation
    assert saved.jd_changed is False
