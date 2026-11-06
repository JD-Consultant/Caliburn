"""寫入工具以真 Application/Domain 驗行為；記憶體儲存不代表 PG 證據。"""

import asyncio
import importlib
import importlib.util
import json
from collections.abc import Collection
from typing import Any
from uuid import UUID

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.func import entrypoint
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from caliburn.bundles.job_description.services import (
    JD_QUERIES,
    JD_REFERENCES,
    JD_UOW_FACTORY,
)
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices, ServiceKey
from caliburn.modules.job_description.application.citation_sources import (
    CitationSourceView,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.citation import (
    InterviewReference,
    SourceReference,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.model_references.contracts import (
    ReferenceTarget,
    ResourceKind,
    UnknownModelReferenceError,
)
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


class References:
    def __init__(self) -> None:
        self.entries: dict[tuple[UUID, ReferenceTarget], str] = {}
        self.failure: Exception | None = None

    def get_or_create_refs(
        self, workspace_id: UUID, targets: Collection[ReferenceTarget]
    ) -> dict[ReferenceTarget, str]:
        if self.failure is not None:
            raise self.failure
        result = {}
        for target in targets:
            key = (workspace_id, target)
            if key not in self.entries:
                self.entries[key] = f"{target.resource_kind}_{len(self.entries) + 1}"
            result[target] = self.entries[key]
        return result

    def resolve_refs(
        self, workspace_id: UUID, refs: Collection[str]
    ) -> dict[str, ReferenceTarget]:
        available = {
            value: target
            for (workspace, target), value in self.entries.items()
            if workspace == workspace_id
        }
        for ref in refs:
            if ref not in available:
                raise UnknownModelReferenceError(ref, "PRIVATE REFERENCE DETAIL")
        return {ref: available[ref] for ref in refs}


class Store:
    def __init__(self) -> None:
        self.root = JobDescription.create(workspace_id=UUID(int=21))
        self.version = 4
        self.commits = 0
        self.correlation_id: str | None = None
        self.failure: Exception | None = None
        self.available_sources: set[SourceReference] = set()

    def require_available(self, *, source: SourceReference) -> None:
        from caliburn.modules.job_description.application.errors import (
            InvalidCitationSourceError,
        )

        if source not in self.available_sources:
            raise InvalidCitationSourceError("PRIVATE SOURCE DETAIL")

    def read(self, *, source: SourceReference) -> CitationSourceView:
        raise AssertionError("寫工具不應展開來源正文")

    def snapshot(self) -> JobDescriptionResult:
        return JobDescriptionResult.from_job_description(
            self.root, version=self.version
        )

    def get_job_description(
        self, *, workspace_id: UUID, job_description_id: UUID
    ) -> JobDescriptionResult | None:
        if (
            self.root.workspace_id == workspace_id
            and self.root.id == job_description_id
        ):
            return self.snapshot()
        return None

    def uow(self) -> RecordingUnitOfWork:
        if self.failure is not None:
            raise self.failure
        store = self

        class WriteUnitOfWork(RecordingUnitOfWork):
            @property
            def citation_sources(self) -> Store:
                return store

            def commit(self) -> None:
                super().commit()
                assert self.job_descriptions.root is not None
                assert self.job_descriptions.saved is not None
                store.root = self.job_descriptions.root
                store.version = self.job_descriptions.saved
                store.correlation_id = self.job_descriptions.correlation_id
                store.commits += 1

        return WriteUnitOfWork(self.root.model_copy(deep=True), version=self.version)


class Harness:
    def __init__(self) -> None:
        self.store = Store()
        self.references = References()
        self.extra_services: dict[ServiceKey[Any], object] = {}
        self.state: JobDescriptionToolState = {
            "workspace_id": self.store.root.workspace_id,
            "turn_id": UUID(int=22),
            "jd_id": self.store.root.id,
            "jd_version": self.store.version,
        }

    def ref(self, kind: ResourceKind, identity: UUID) -> str:
        target = ReferenceTarget(kind, identity)
        return self.references.get_or_create_refs(
            self.store.root.workspace_id, [target]
        )[target]

    def runtime(self) -> ToolRuntime[AgentContext, JobDescriptionToolState]:
        return ToolRuntime[AgentContext, JobDescriptionToolState](
            state=self.state,
            context=AgentContext(
                PluginServices(
                    {
                        JD_QUERIES: self.store,
                        JD_UOW_FACTORY: self.store.uow,
                        JD_REFERENCES: self.references,
                        **self.extra_services,
                    }
                )
            ),
            config={},
            stream_writer=lambda value: None,
            tool_call_id="write-call",
            store=None,
        )

    def invoke(self, name: str, arguments: dict[str, object]) -> object:
        module_name = "caliburn.bundles.job_description.write_tools"
        assert importlib.util.find_spec(module_name) is not None, "JD 寫工具尚未提供"
        module = importlib.import_module(module_name)
        selected = {tool.name: tool for tool in module.create_write_tools()}[name]
        runtime = self.runtime()

        @entrypoint()
        async def execute(value: bool) -> object:
            return await selected.ainvoke({**arguments, "runtime": runtime})

        result = asyncio.run(execute.ainvoke(True))
        if isinstance(result, Command):
            assert isinstance(result.update, dict)
            self.state["jd_version"] = result.update["jd_version"]
        return result


def payload(result: object) -> dict[str, Any]:
    if isinstance(result, Command):
        assert isinstance(result.update, dict)
        content = result.update["messages"][0].content
    else:
        content = result
    assert isinstance(content, str)
    decoded = json.loads(content)
    assert isinstance(decoded, dict)
    return decoded


def test_complete_task_is_one_commit_with_new_and_existing_definitions() -> None:
    harness = Harness()
    duty = harness.store.root.add_duty(name="設備")
    knowledge = harness.store.root.add_knowledge(name="安全")
    result = harness.invoke(
        "create_jd_task",
        {
            "parent_read_ref": harness.ref("duty", duty),
            "name": "維修",
            "description": "本人檢查設備",
            "competency_level": 3,
            "outcomes": [{"text": "可運作的設備"}],
            "requirements": [{"text": "遵守安全程序"}],
            "required_knowledge": [
                {
                    "kind": "existing",
                    "capability_read_ref": harness.ref("knowledge", knowledge),
                }
            ],
            "required_skills": [
                {"kind": "new", "name": "診斷", "description": "判讀異常"}
            ],
        },
    )
    saved = harness.store.snapshot()
    assert harness.store.commits == 1
    assert harness.store.correlation_id == str(harness.state["turn_id"])
    assert saved.version == 5
    assert saved.tasks[0].duty_id == duty
    assert saved.tasks[0].knowledge_ids == (knowledge,)
    assert saved.tasks[0].skill_ids == (saved.skills[0].id,)
    assert saved.tasks[0].outcomes[0].text == "可運作的設備"
    output = payload(result)
    assert output["status"] == "created"
    assert str(output["read_ref"]).startswith("task_")
    assert str(saved.job_description_id) not in json.dumps(output)
    assert harness.state["jd_version"] == 5


def test_seen_version_is_not_silently_replaced_by_fresh_snapshot() -> None:
    harness = Harness()
    harness.store.version = 5
    result = harness.invoke(
        "create_jd_item", {"item": {"kind": "duty", "name": "出貨", "scope": None}}
    )
    assert payload(result)["code"] == "target_stale"
    assert harness.store.commits == 0


def test_saved_task_result_survives_later_mapping_failure_without_recreating_item() -> (
    None
):
    from langgraph.checkpoint.memory import InMemorySaver

    from caliburn.bundles.job_description.write_tools import create_write_tools

    harness = Harness()
    tool = next(tool for tool in create_write_tools() if tool.name == "create_jd_item")
    runtime = harness.runtime()
    harness.references.failure = RuntimeError("mapping unavailable")

    @entrypoint(checkpointer=InMemorySaver())
    async def execute(value: bool) -> object:
        return await tool.ainvoke(
            {"item": {"kind": "duty", "name": "出貨"}, "runtime": runtime}
        )

    async def exercise() -> object:
        config: RunnableConfig = {"configurable": {"thread_id": "jd-write-recovery"}}
        with pytest.raises(RuntimeError, match="mapping unavailable"):
            await execute.ainvoke(True, config=config)
        assert harness.store.commits == 1
        harness.references.failure = None
        return await execute.ainvoke(None, config=config)

    result = asyncio.run(exercise())
    assert payload(result)["status"] == "created"
    assert harness.store.commits == 1
    assert len(harness.store.snapshot().duties) == 1


def test_application_rejection_rolls_back_all_changes_and_preserves_prior_success() -> (
    None
):
    harness = Harness()
    first = payload(
        harness.invoke(
            "create_jd_item", {"item": {"kind": "knowledge", "name": "既有知識"}}
        )
    )
    task = harness.store.root.add_task(name="原工作")
    rejected = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": harness.ref("task", task),
                "changes": [
                    {"action": "set_field", "field": "name", "value": "嘗試改名"},
                    {
                        "action": "create_capability",
                        "kind": "knowledge",
                        "name": "既有知識",
                    },
                ],
            },
        )
    )
    assert first["status"] == "created"
    assert rejected["code"] == "name_conflict"
    assert harness.store.commits == 1
    assert harness.store.snapshot().tasks[0].name == "原工作"
    assert harness.store.snapshot().knowledge[0].name == "既有知識"


def test_task_conflicting_detail_changes_are_rejected_before_mutation() -> None:
    harness = Harness()
    task = harness.store.root.add_task(name="工作", outcomes=("原成果",))
    outcome = harness.store.snapshot().tasks[0].outcomes[0].id
    outcome_ref = harness.ref("outcome", outcome)
    result = harness.invoke(
        "revise_jd_item",
        {
            "read_ref": harness.ref("task", task),
            "changes": [
                {
                    "action": "revise_detail",
                    "detail_read_ref": outcome_ref,
                    "text": "新成果",
                },
                {"action": "remove_detail", "detail_read_ref": outcome_ref},
            ],
        },
    )
    assert payload(result)["code"] == "invalid_arguments"
    assert harness.store.snapshot().tasks[0].outcomes[0].text == "原成果"
    assert harness.store.commits == 0
    assert harness.state["jd_version"] == 4


def test_invalid_later_task_change_does_not_commit_earlier_change() -> None:
    harness = Harness()
    task_id = harness.store.root.add_task(name="原工作")
    task_ref = harness.ref("task", task_id)
    knowledge = harness.store.root.add_knowledge(name="知識")
    result = harness.invoke(
        "revise_jd_item",
        {
            "read_ref": task_ref,
            "changes": [
                {"action": "set_field", "field": "name", "value": "更正工作"},
                {
                    "action": "revise_detail",
                    "detail_read_ref": harness.ref("knowledge", knowledge),
                    "text": "錯種類",
                },
            ],
        },
    )
    assert payload(result)["status"] == "rejected"
    assert harness.store.root.tasks[0].name.value == "原工作"
    assert harness.store.commits == 0


def test_technical_commit_uncertainty_stops_instead_of_returning_retry_advice() -> None:
    from caliburn.modules.job_description.application.errors import (
        JobDescriptionPersistenceError,
    )

    harness = Harness()
    harness.store.failure = JobDescriptionPersistenceError(commit_status="unknown")
    with pytest.raises(JobDescriptionPersistenceError) as caught:
        harness.invoke(
            "create_jd_item", {"item": {"kind": "duty", "name": "出貨", "scope": None}}
        )
    assert caught.value.commit_status == "unknown"


def test_mapping_failure_after_commit_is_not_a_business_rejection() -> None:
    harness = Harness()
    harness.references.failure = RuntimeError("映射暫時無法保存")
    with pytest.raises(RuntimeError, match="映射"):
        harness.invoke(
            "create_jd_item", {"item": {"kind": "duty", "name": "出貨", "scope": None}}
        )
    assert harness.store.commits == 1
    assert harness.store.root.duties[0].name.value == "出貨"


@pytest.mark.parametrize("value", [" ", "x\x00y", "x\ud800y"])
def test_invalid_optional_text_is_a_safe_rejection_without_writing(value: str) -> None:
    harness = Harness()
    result = harness.invoke(
        "create_jd_item", {"item": {"kind": "duty", "name": "工作", "scope": value}}
    )
    assert payload(result)["code"] == "invalid_arguments"
    assert harness.store.commits == 0


def test_profile_preserves_omitted_fields_and_clears_only_selected_field() -> None:
    harness = Harness()
    harness.store.root.update_details(
        job_title="原職稱",
        organization_unit="原單位",
        reports_to="主管",
        purpose="原目的",
        baseline_competency_level=2,
    )
    result = harness.invoke(
        "revise_jd_profile",
        {
            "changes": [
                {"action": "set_field", "field": "job_title", "value": "設備員"},
                {"action": "clear_field", "field": "purpose"},
                {"action": "set_baseline_competency_level", "value": 4},
            ]
        },
    )
    assert payload(result)["status"] == "updated"
    saved = harness.store.snapshot()
    assert (saved.job_title, saved.purpose, saved.baseline_competency_level) == (
        "設備員",
        None,
        4,
    )
    assert (saved.organization_unit, saved.reports_to) == ("原單位", "主管")
    assert harness.store.commits == 1


@pytest.mark.parametrize(
    "item",
    [
        {"kind": "duty", "name": "設備", "scope": "檢查"},
        {"kind": "knowledge", "name": "設備原理", "description": "設備結構"},
        {"kind": "skill", "name": "判讀", "description": "判讀異常"},
        {"kind": "collaboration", "collaborator_name": "維修組", "scope": "異常交接"},
        {
            "kind": "condition",
            "condition_kind": "work_environment",
            "text": "在現場工作",
        },
    ],
)
def test_create_revise_delete_item_keeps_one_identity(item: dict[str, str]) -> None:
    harness = Harness()
    created = payload(harness.invoke("create_jd_item", {"item": item}))
    ref = created["read_ref"]
    field = (
        "scope"
        if item["kind"] in ("duty", "collaboration")
        else "text"
        if item["kind"] == "condition"
        else "description"
    )
    edited = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": ref,
                "changes": [
                    {"action": "set_field", "field": field, "value": "更新正文"}
                ],
            },
        )
    )
    assert edited["status"] == "updated"
    assert len(harness.references.entries) == 1
    deleted = payload(harness.invoke("delete_jd_item", {"read_ref": ref}))
    assert deleted["status"] == "deleted"
    assert harness.store.version == 7
    assert len(harness.references.entries) == 1


def test_task_patch_combines_field_details_and_new_capability_once() -> None:
    harness = Harness()
    task = harness.store.root.add_task(
        name="維修", outcomes=("原成果",), requirements=("舊要求",)
    )
    saved = harness.store.snapshot().tasks[0]
    result = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": harness.ref("task", task),
                "changes": [
                    {"action": "set_field", "field": "name", "value": "維護設備"},
                    {"action": "set_competency_level", "value": 5},
                    {
                        "action": "revise_detail",
                        "detail_read_ref": harness.ref("outcome", saved.outcomes[0].id),
                        "text": "完成紀錄",
                    },
                    {
                        "action": "remove_detail",
                        "detail_read_ref": harness.ref(
                            "requirement", saved.requirements[0].id
                        ),
                    },
                    {
                        "action": "create_capability",
                        "kind": "skill",
                        "name": "診斷",
                        "description": None,
                    },
                    {"action": "add_detail", "kind": "outcome", "text": "可運作設備"},
                    {
                        "action": "create_capability",
                        "kind": "knowledge",
                        "name": "電路",
                        "description": None,
                    },
                    {"action": "add_detail", "kind": "requirement", "text": "按時完成"},
                ],
            },
        )
    )
    assert result["status"] == "updated"
    assert [ref.split("_")[0] for ref in result["created_refs"]] == [
        "skill",
        "outcome",
        "knowledge",
        "requirement",
    ]
    after = harness.store.snapshot()
    assert after.tasks[0].name == "維護設備"
    assert after.tasks[0].competency_level == 5
    assert [item.text for item in after.tasks[0].outcomes] == ["完成紀錄", "可運作設備"]
    assert [item.text for item in after.tasks[0].requirements] == ["按時完成"]
    assert after.tasks[0].skill_ids == (after.skills[0].id,)
    assert harness.store.commits == 1


def test_link_then_reorder_uses_application_ordered_changes() -> None:
    harness = Harness()
    first = harness.store.root.add_knowledge(name="A")
    second = harness.store.root.add_knowledge(name="B")
    task = harness.store.root.add_task(name="T", knowledge=(first,))
    result = harness.invoke(
        "revise_jd_item",
        {
            "read_ref": harness.ref("task", task),
            "changes": [
                {
                    "action": "set_capability",
                    "capability_read_ref": harness.ref("knowledge", second),
                    "relationship": "link",
                },
                {
                    "action": "reorder_capability",
                    "capability_read_ref": harness.ref("knowledge", second),
                    "before_read_ref": harness.ref("knowledge", first),
                },
            ],
        },
    )
    assert payload(result)["status"] == "updated"
    assert harness.store.snapshot().tasks[0].knowledge_ids == (second, first)


@pytest.mark.parametrize(
    "changes",
    [
        [
            {"action": "set_field", "field": "name", "value": "A"},
            {"action": "set_field", "field": "name", "value": "B"},
        ],
        [
            {"action": "set_field", "field": "name", "value": "A"},
            {"action": "add_detail", "kind": "outcome", "text": "不適用"},
        ],
    ],
)
def test_simple_item_invalid_change_rejects_entire_list(
    changes: list[dict[str, str]],
) -> None:
    harness = Harness()
    duty = harness.store.root.add_duty(name="原職責")
    result = harness.invoke(
        "revise_jd_item", {"read_ref": harness.ref("duty", duty), "changes": changes}
    )
    assert payload(result)["code"] == "invalid_arguments"
    assert harness.store.snapshot().duties[0].name == "原職責"
    assert harness.store.commits == 0


def test_task_detail_cannot_be_taken_from_another_task() -> None:
    harness = Harness()
    task = harness.store.root.add_task(name="A")
    harness.store.root.add_task(name="B", outcomes=("B成果",))
    outcome = harness.store.snapshot().tasks[1].outcomes[0].id
    result = harness.invoke(
        "revise_jd_item",
        {
            "read_ref": harness.ref("task", task),
            "changes": [
                {
                    "action": "revise_detail",
                    "detail_read_ref": harness.ref("outcome", outcome),
                    "text": "錯誤更正",
                }
            ],
        },
    )
    assert payload(result)["code"] == "target_not_found"
    assert harness.store.commits == 0


def test_mapped_target_must_still_exist_in_current_scoped_jd() -> None:
    harness = Harness()
    absent = harness.ref("duty", UUID(int=999))
    result = harness.invoke("delete_jd_item", {"read_ref": absent})
    assert payload(result)["code"] == "target_not_found"
    assert harness.store.commits == 0


def test_foreign_workspace_short_reference_is_rejected() -> None:
    harness = Harness()
    target = ReferenceTarget("duty", harness.store.root.add_duty(name="本地職責"))
    foreign = harness.references.get_or_create_refs(UUID(int=91), [target])[target]
    result = harness.invoke("delete_jd_item", {"read_ref": foreign})
    assert payload(result)["code"] == "target_not_found"
    assert "PRIVATE" not in str(result)
    assert harness.store.commits == 0


def test_delete_shared_knowledge_unlinks_tasks_instead_of_refusing_in_use() -> None:
    harness = Harness()
    knowledge = harness.store.root.add_knowledge(name="共用知識")
    harness.store.root.add_task(name="A", knowledge=(knowledge,))
    harness.store.root.add_task(name="B", knowledge=(knowledge,))
    output = payload(
        harness.invoke(
            "delete_jd_item", {"read_ref": harness.ref("knowledge", knowledge)}
        )
    )
    assert output == {"status": "deleted", "unlinked_task_count": 2}
    assert harness.store.snapshot().knowledge == ()
    assert all(task.knowledge_ids == () for task in harness.store.snapshot().tasks)


def test_move_task_with_companion_content_is_one_commit() -> None:
    harness = Harness()
    duty = harness.store.root.add_duty(name="目的職責")
    neighbor = harness.store.root.add_task(name="鄰項", duty_id=duty)
    task = harness.store.root.add_task(name="待移工作")
    output = payload(
        harness.invoke(
            "move_jd_item",
            {
                "read_ref": harness.ref("task", task),
                "destination": {
                    "kind": "task_parent",
                    "parent_read_ref": harness.ref("duty", duty),
                },
                "before_read_ref": harness.ref("task", neighbor),
                "content_changes": [
                    {"action": "set_field", "field": "description", "value": "新範圍"},
                    {"action": "add_detail", "kind": "outcome", "text": "新成果"},
                ],
            },
        )
    )
    assert output["status"] == "moved"
    moved = next(item for item in harness.store.snapshot().tasks if item.id == task)
    assert (moved.duty_id, moved.description) == (duty, "新範圍")
    assert [
        item.id for item in harness.store.snapshot().tasks if item.duty_id == duty
    ] == [task, neighbor]
    assert harness.store.commits == 1


def test_noop_revision_retains_seen_version() -> None:
    harness = Harness()
    duty = harness.store.root.add_duty(name="設備")
    result = harness.invoke(
        "revise_jd_item",
        {
            "read_ref": harness.ref("duty", duty),
            "changes": [{"action": "set_field", "field": "name", "value": " 設備 "}],
        },
    )
    assert payload(result) == {"status": "unchanged"}
    assert harness.state["jd_version"] == 4


def test_model_schema_rejects_hidden_runtime_identity_fields() -> None:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    from caliburn.bundles.job_description.write_tools import create_write_tools

    tools = create_write_tools()
    assert len(tools) == 6
    for tool in tools:
        public = convert_to_openai_tool(tool)
        properties = public["function"]["parameters"]["properties"]
        assert not set(properties).intersection(
            {"runtime", "workspace_id", "jd_id", "expected_version", "turn_id"}
        )
    harness = Harness()
    result = harness.invoke(
        "create_jd_item",
        {"item": {"kind": "duty", "name": "X"}, "workspace_id": str(UUID(int=92))},
    )
    assert payload(result)["code"] == "invalid_arguments"
    assert harness.store.commits == 0


def test_item_source_add_confirm_remove_are_scoped_to_one_target() -> None:
    harness = Harness()
    source = InterviewReference(
        workspace_id=harness.store.root.workspace_id, message_id=UUID(int=77)
    )
    harness.store.available_sources.add(source)
    created = payload(
        harness.invoke(
            "create_jd_item",
            {
                "item": {
                    "kind": "duty",
                    "name": "出貨",
                    "supporting_sources": [
                        {
                            "kind": "interview",
                            "message_ref": harness.ref("message", source.message_id),
                        }
                    ],
                }
            },
        )
    )
    assert created["status"] == "created"
    citation = harness.store.snapshot().citations[0]
    assert citation.source == source
    citation_ref = harness.ref("citation", citation.id)
    harness.store.root.set_citation_review(citation_id=citation.id, jd_changed=True)
    confirmed = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": created["read_ref"],
                "changes": [
                    {
                        "action": "confirm_reference_alignment",
                        "citation_ref": citation_ref,
                    }
                ],
            },
        )
    )
    assert confirmed["status"] == "updated"
    assert harness.store.snapshot().citations[0].jd_changed is False
    removed = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": created["read_ref"],
                "changes": [{"action": "remove_source", "citation_ref": citation_ref}],
            },
        )
    )
    assert removed["status"] == "updated"
    assert harness.store.snapshot().citations == ()


def test_unavailable_source_rejects_content_and_source_together() -> None:
    harness = Harness()
    message_ref = harness.ref("message", UUID(int=77))
    result = payload(
        harness.invoke(
            "create_jd_item",
            {
                "item": {
                    "kind": "duty",
                    "name": "出貨",
                    "supporting_sources": [
                        {"kind": "interview", "message_ref": message_ref}
                    ],
                }
            },
        )
    )
    assert result["code"] == "source_not_available"
    assert harness.store.commits == 0
    assert "PRIVATE" not in json.dumps(result)


def test_memory_source_without_fixed_runtime_version_is_rejected() -> None:
    harness = Harness()
    result = payload(
        harness.invoke(
            "revise_jd_profile",
            {
                "changes": [
                    {
                        "action": "add_source",
                        "source": {"kind": "work_situation", "target_title": "盤點"},
                    }
                ]
            },
        )
    )
    assert result["code"] == "source_not_available"
    assert harness.store.commits == 0


def test_consultant_edit_does_not_mark_retained_citation_changed() -> None:
    harness = Harness()
    duty = harness.store.root.add_duty(name="出貨")
    source = InterviewReference(
        workspace_id=harness.store.root.workspace_id, message_id=UUID(int=77)
    )
    harness.store.root.add_citation(target_kind="duty", target_id=duty, source=source)
    result = payload(
        harness.invoke(
            "revise_jd_item",
            {
                "read_ref": harness.ref("duty", duty),
                "changes": [
                    {"action": "set_field", "field": "scope", "value": "客戶出貨"}
                ],
            },
        )
    )
    assert result["status"] == "updated"
    assert harness.store.snapshot().citations[0].jd_changed is False


def test_move_task_updates_source_and_destination_duty_scopes_atomically() -> None:
    harness = Harness()
    origin = harness.store.root.add_duty(name="原職責", scope="原範圍")
    destination = harness.store.root.add_duty(name="新職責", scope="新範圍")
    task = harness.store.root.add_task(name="任務", duty_id=origin)
    result = payload(
        harness.invoke(
            "move_jd_item",
            {
                "read_ref": harness.ref("task", task),
                "destination": {
                    "kind": "task_parent",
                    "parent_read_ref": harness.ref("duty", destination),
                },
                "before_read_ref": None,
                "content_changes": [
                    {
                        "action": "set_duty_scope",
                        "duty_read_ref": harness.ref("duty", origin),
                        "scope": None,
                    },
                    {
                        "action": "set_duty_scope",
                        "duty_read_ref": harness.ref("duty", destination),
                        "scope": "新增任務的範圍",
                    },
                    {
                        "action": "set_field",
                        "field": "description",
                        "value": "更正任務正文",
                    },
                ],
            },
        )
    )
    assert result["status"] == "moved"
    after = harness.store.snapshot()
    assert after.tasks[0].duty_id == destination
    assert after.tasks[0].description == "更正任務正文"
    assert [item.scope for item in after.duties] == [None, "新增任務的範圍"]
    assert harness.store.commits == 1
