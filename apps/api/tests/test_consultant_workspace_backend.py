"""Focused characterization and policy tests for the consultant workspace."""

from __future__ import annotations

import asyncio
import ast
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.memory import InMemoryStore

from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    EmployeeSource,
    EmployeeSourceKind,
    SourceProcessingStatus,
    SourceValidity,
)
from app.consultant.workspace_backend import (
    ConsultantWorkspaceBackendBinding,
    build_consultant_workspace_backend,
)
from app.consultant.workspace_resources import WorkspaceCatalog, parse_workspace_files
from app.consultant.workspace_review import (
    WorkspaceReviewDecision,
    WorkspaceReviewDecisionKind,
    derive_workspace_review,
)
from app.consultant.workspace_state import (
    StoreBackedWorkspace,
    WorkspaceDiagnostic,
    WorkspaceValidationStatus,
    workspace_resource_digest,
)
from app.consultant.workspace_validation import (
    evidence_basis_digest,
    validate_workspace_payload,
)
from app.consultant.workspace_tools import WORKSPACE_TOOL_DESCRIPTIONS


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000101")
OTHER_DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000103")
DUTY_ID = UUID("00000000-0000-0000-0000-000000000201")
TASK_ID = UUID("00000000-0000-0000-0000-000000000202")
OLD_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000301")
CURRENT_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000302")


class FakeRuntime:
    def __init__(self, sources: tuple[EmployeeSource, ...]) -> None:
        self._sources = {source.source_id: source for source in sources}
        self.review_decisions: tuple[WorkspaceReviewDecision, ...] = ()

    async def get_source(self, document_id: UUID, source_id: UUID) -> EmployeeSource:
        source = self._sources[source_id]
        assert source.document_id == document_id
        return source

    async def list_sources(self, document_id: UUID) -> tuple[EmployeeSource, ...]:
        return tuple(
            source
            for source in sorted(
                self._sources.values(),
                key=lambda item: (item.created_at, str(item.source_id)),
            )
            if source.document_id == document_id
        )

    async def workspace_review_decisions(
        self,
        document_id: UUID,
    ) -> tuple[WorkspaceReviewDecision, ...]:
        assert document_id == DOCUMENT_ID
        return self.review_decisions


class FilesystemToolHarness:
    """Run the real filesystem tools with no LangGraph files state channel."""

    def __init__(self, middleware: FilesystemMiddleware) -> None:
        graph = StateGraph(MessagesState)
        graph.add_node("tools", ToolNode(middleware.tools))
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        self._graph = graph.compile()

    async def invoke(self, name: str, **args: Any) -> ToolMessage:
        result = await self._graph.ainvoke(
            {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": name,
                                "args": args,
                                "id": f"call-{uuid4()}",
                                "type": "tool_call",
                            }
                        ],
                    )
                ]
            }
        )
        assert "files" not in result
        message = result["messages"][-1]
        assert isinstance(message, ToolMessage)
        return message


def _sources() -> tuple[EmployeeSource, ...]:
    created = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)
    old = EmployeeSource.pending(
        source_id=OLD_SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="過時內容，不得出現在 current grep。",
        created_at=created,
    ).model_copy(
        update={
            "validity": SourceValidity.SUPERSEDED,
            "superseded_by_source_id": CURRENT_SOURCE_ID,
        }
    )
    current = EmployeeSource.pending(
        source_id=CURRENT_SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.DIRECT_EDIT,
        text="目前內容第一行。\n目前內容第二行。",
        supersedes_source_id=OLD_SOURCE_ID,
        created_at=created + timedelta(minutes=1),
    ).model_copy(update={"processing_status": SourceProcessingStatus.COMMITTED})
    return old, current


def _document(document_id: UUID = DOCUMENT_ID) -> ApprovedJobDocument:
    return ApprovedJobDocument(
        document_id=document_id,
        job_title="採購專員",
        work_description="管理採購流程。",
        competency_level=5,
        duties=(
            ApprovedDuty(
                duty_id=DUTY_ID,
                statement="管理採購作業",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=TASK_ID,
                duty_id=DUTY_ID,
                statement="整理需求",
                action="整理",
                object="採購需求",
                display_order=0,
                competency_level=4,
            ),
        ),
    )


async def _binding() -> ConsultantWorkspaceBackendBinding:
    sources = _sources()
    catalog = WorkspaceCatalog.from_snapshot(_document(), sources=sources)
    workspace = StoreBackedWorkspace(store=InMemoryStore(), document_id=DOCUMENT_ID)
    await workspace.ensure_initialized(
        approved_document=catalog.document,
        approved_revision=0,
    )
    return build_consultant_workspace_backend(
        runtime=FakeRuntime(sources),
        document_id=DOCUMENT_ID,
        workspace=workspace,
        catalog=catalog,
        selected_skill_ids=("output",),
    )


@pytest_asyncio.fixture
async def workspace_binding() -> ConsultantWorkspaceBackendBinding:
    return await _binding()


@pytest_asyncio.fixture
async def real_filesystem_tools(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> FilesystemToolHarness:
    return FilesystemToolHarness(
        FilesystemMiddleware(
            backend=workspace_binding.composite_backend,
            tools=["ls", "read_file", "write_file", "edit_file", "delete", "grep"],
            system_prompt=None,
            tool_token_limit_before_evict=None,
            human_message_token_limit_before_evict=None,
            grep_max_count=None,
        )
    )


@pytest.mark.asyncio
async def test_store_backed_workspace_seeds_once_and_survives_reopen() -> None:
    store = InMemoryStore()
    workspace = StoreBackedWorkspace(store=store, document_id=DOCUMENT_ID)
    initialized = await workspace.ensure_initialized(
        approved_document=_document(),
        approved_revision=0,
    )
    path = "/workspace/tasks/task-new-001.json"
    content = (
        '{"handle":"task-new-001","statement":"追蹤交期",'
        '"action":"追蹤","object":"交期"}\n'
    )
    assert (await workspace.backend.awrite(path, content)).error is None

    unchanged = await workspace.ensure_initialized(
        approved_document=_document().model_copy(update={"job_title": "不得重建"}),
        approved_revision=1,
    )
    reopened = await StoreBackedWorkspace(
        store=store,
        document_id=DOCUMENT_ID,
    ).read_snapshot()

    assert unchanged.approved_baseline_revision == initialized.approved_baseline_revision
    assert reopened.files[path] == content
    assert "不得重建" not in reopened.files["/workspace/header.json"]


@pytest.mark.asyncio
async def test_store_backed_workspace_does_not_seed_over_partial_files_or_manifest() -> None:
    partial = StoreBackedWorkspace(store=InMemoryStore(), document_id=DOCUMENT_ID)
    assert (
        await partial.backend.awrite(
            "/workspace/header.json",
            '{"job_title":"保留殘存內容"}\n',
        )
    ).error is None
    manifest = await partial.ensure_initialized(
        approved_document=_document(),
        approved_revision=0,
    )
    assert (await partial.read_snapshot()).files == {
        "/workspace/header.json": '{"job_title":"保留殘存內容"}\n'
    }
    assert manifest.validation_status is WorkspaceValidationStatus.UNVALIDATED

    manifest_only = StoreBackedWorkspace(
        store=InMemoryStore(),
        document_id=OTHER_DOCUMENT_ID,
    )
    first = await manifest_only.ensure_initialized(
        approved_document=_document(OTHER_DOCUMENT_ID),
        approved_revision=0,
    )
    assert (await manifest_only.backend.adelete("/workspace")).error is None
    second = await manifest_only.ensure_initialized(
        approved_document=_document(OTHER_DOCUMENT_ID).model_copy(
            update={"job_title": "不得重建"}
        ),
        approved_revision=1,
    )
    assert second.approved_baseline_revision == first.approved_baseline_revision
    assert (await manifest_only.read_snapshot()).files == {}


@pytest.mark.asyncio
async def test_store_backed_workspace_marks_digest_mismatch_unvalidated() -> None:
    binding = await _binding()
    assert (
        await binding.workspace_backend.aedit(
            "/workspace/header.json",
            '"採購專員"',
            '"資深採購專員"',
        )
    ).error is None

    snapshot = await binding.workspace.read_snapshot()

    assert snapshot.manifest.validation_status is WorkspaceValidationStatus.UNVALIDATED
    assert snapshot.manifest.resource_digest == workspace_resource_digest(snapshot.files)


@pytest.mark.asyncio
async def test_workspace_binding_uses_initialized_store_backend_without_files_state() -> None:
    binding = await _binding()

    assert binding.workspace_backend.store_backend is binding.workspace.backend
    legacy_backend_field = "candidate_" + "state_backend"
    assert not hasattr(binding, legacy_backend_field)
    assert not hasattr(binding, "initial_files")
    assert not hasattr(binding, "run_id")
    assert (await binding.composite_backend.aread("/workspace/header.json")).error is None


@pytest.mark.asyncio
async def test_write_file_contract_creates_parseable_linked_workspace_resources(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    middleware = FilesystemMiddleware(
        backend=workspace_binding.composite_backend,
        tools=["read_file", "write_file"],
        custom_tool_descriptions=WORKSPACE_TOOL_DESCRIPTIONS,
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
    )
    write_tool = next(tool for tool in middleware.tools if tool.name == "write_file")
    examples = [
        json.loads(line.removeprefix("CREATE_EXAMPLE "))
        for line in write_tool.description.splitlines()
        if line.startswith("CREATE_EXAMPLE ")
    ]
    harness = FilesystemToolHarness(middleware)
    for example in examples:
        message = await harness.invoke(
            "write_file",
            file_path=f"/workspace/{example['path']}",
            content=json.dumps(example["content"], ensure_ascii=False) + "\n",
        )
        assert message.status == "success"

    snapshot = await workspace_binding.workspace.read_snapshot()
    draft = parse_workspace_files(
        DOCUMENT_ID,
        snapshot.files,
        handle_registry=workspace_binding.catalog.handle_to_stable,
        baseline_document=workspace_binding.catalog.document,
    )
    duty = next(item for item in draft.document.duties if item.statement == "管理供應商交期")
    task = next(item for item in draft.document.tasks if item.statement == "核對供應商交期")
    output = next(item for item in draft.document.opks if item.text == "已核對的供應商交期")
    assert task.duty_id == duty.duty_id
    assert output.task_ids == (task.task_id,)


@pytest.mark.asyncio
async def test_workspace_binding_exposes_exactly_six_roots(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    listing = await real_filesystem_tools.invoke("ls", path="/")
    assert listing.status == "success"
    entries = ast.literal_eval(str(listing.content))
    assert {entry.removesuffix("/") for entry in entries} == {
        "/workspace",
        "/approved",
        "/review",
        "/sources",
        "/skills",
    }


@pytest.mark.asyncio
async def test_workspace_policy_keeps_create_only_and_protected_resource_rules(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    backend = workspace_binding.workspace_backend
    header = "/workspace/header.json"
    new_task = "/workspace/tasks/task-999.json"

    assert (await backend.awrite(header, "{}\n")).error is not None
    assert (
        await backend.aedit(header, "採購專員", "採購管理師", replace_all=True)
    ).error is not None
    assert (await backend.adelete(header)).error is not None
    assert (await backend.awrite("/workspace/not-a-resource.json", "{}\n")).error is not None
    assert (await backend.awrite(new_task, "{}\n")).error is None
    assert (await backend.adelete(new_task)).error is None


@pytest.mark.asyncio
async def test_async_create_only_write_is_atomic_for_one_workspace(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    path = "/workspace/tasks/task-999.json"
    results = await asyncio.gather(
        workspace_binding.workspace_backend.awrite(path, "first\n"),
        workspace_binding.workspace_backend.awrite(path, "second\n"),
    )
    assert sum(result.error is None for result in results) == 1
    read = await workspace_binding.workspace_backend.aread(path)
    assert read.file_data is not None
    assert read.file_data["content"] in {"first\n", "second\n"}


@pytest.mark.asyncio
async def test_cancelled_workspace_mutation_waiter_does_not_leak_lock(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    backend = workspace_binding.workspace_backend
    backend._mutation_lock.acquire()  # noqa: SLF001 - cancellation characterization
    waiter = asyncio.create_task(
        backend.awrite("/workspace/tasks/task-998.json", "cancelled\n")
    )
    await asyncio.sleep(0)
    waiter.cancel()
    backend._mutation_lock.release()  # noqa: SLF001

    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert (
        await asyncio.wait_for(
            backend.awrite("/workspace/tasks/task-999.json", "survived\n"),
            timeout=1,
        )
    ).error is None


@pytest.mark.asyncio
async def test_approved_and_review_projections_remain_readable(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    approved = await real_filesystem_tools.invoke(
        "read_file",
        file_path="/approved/header.json",
    )
    review = await real_filesystem_tools.invoke(
        "read_file",
        file_path="/review/index.json",
    )

    assert approved.status == review.status == "success"
    assert "採購專員" in str(approved.content)
    assert '"group_handles"' in str(review.content)


@pytest.mark.asyncio
async def test_review_projection_rechecks_store_bytes_and_never_serves_a_stale_group(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    backend = workspace_binding.review_backend
    assert "async" in (backend.read("/index.json").error or "")

    assert (
        await workspace_binding.workspace_backend.aedit(
            "/workspace/tasks/task-001.json",
            '"整理需求"',
            '"複核需求"',
        )
    ).error is None
    unvalidated = await workspace_binding.composite_backend.aread("/review/index.json")
    assert unvalidated.error is None
    assert unvalidated.file_data is not None
    assert json.loads(unvalidated.file_data["content"])["diagnostic_count"] == 1

    snapshot = await workspace_binding.workspace.read_snapshot()
    payload = validate_workspace_payload(
        snapshot.files,
        catalog=workspace_binding.catalog,
        selected_skill_ids=("output",),
        loaded_skill_ids=("output",),
    )
    assert payload.document is not None
    await workspace_binding.workspace.commit_validation(
        expected_resource_digest=snapshot.manifest.resource_digest,
        evidence_basis_digest=evidence_basis_digest(payload.current_sources),
        validation_status=WorkspaceValidationStatus.VALID,
        diagnostics=(),
        entity_ids_by_handle=snapshot.manifest.entity_ids_by_handle,
    )
    valid = await workspace_binding.composite_backend.aread("/review/index.json")
    assert valid.error is None
    assert valid.file_data is not None
    assert json.loads(valid.file_data["content"])["group_handles"] == ["group-001"]
    group = await workspace_binding.composite_backend.aread(
        "/review/groups/group-001.json"
    )
    assert group.error is None
    assert group.file_data is not None
    group_payload = json.loads(group.file_data["content"])
    assert group_payload["actions"][0]["path"] == "/tasks/task-001/statement"
    assert "read_set" not in group_payload["actions"][0]
    assert "source_ids" not in group_payload["actions"][0]

    assert (
        await workspace_binding.workspace_backend.aedit(
            "/workspace/tasks/task-001.json",
            '"複核需求"',
            '"再次複核需求"',
        )
    ).error is None
    stale_group = await workspace_binding.composite_backend.aread(
        "/review/groups/group-001.json"
    )
    assert stale_group.error is not None


@pytest.mark.asyncio
async def test_review_projection_loads_durable_decisions_after_backend_construction() -> None:
    sources = _sources()
    runtime = FakeRuntime(sources)
    catalog = WorkspaceCatalog.from_snapshot(_document(), sources=sources)
    workspace = StoreBackedWorkspace(store=InMemoryStore(), document_id=DOCUMENT_ID)
    await workspace.ensure_initialized(
        approved_document=catalog.document,
        approved_revision=0,
    )
    binding = build_consultant_workspace_backend(
        runtime=runtime,
        document_id=DOCUMENT_ID,
        workspace=workspace,
        catalog=catalog,
        selected_skill_ids=("output",),
    )
    assert (
        await binding.workspace_backend.aedit(
            "/workspace/tasks/task-001.json",
            '"整理需求"',
            '"複核需求"',
        )
    ).error is None
    snapshot = await workspace.read_snapshot()
    validation = validate_workspace_payload(
        snapshot.files,
        catalog=catalog,
        selected_skill_ids=("output",),
        loaded_skill_ids=("output",),
    )
    await workspace.commit_validation(
        expected_resource_digest=snapshot.manifest.resource_digest,
        evidence_basis_digest=evidence_basis_digest(validation.current_sources),
        validation_status=WorkspaceValidationStatus.VALID,
        diagnostics=(),
        entity_ids_by_handle=snapshot.manifest.entity_ids_by_handle,
    )
    validated = await workspace.read_snapshot()
    projection = derive_workspace_review(
        catalog.document,
        validation,
        validated.manifest,
        (),
    )
    group = projection.groups[0]

    runtime.review_decisions = (
        WorkspaceReviewDecision.from_group(
            WorkspaceReviewDecisionKind.DEFER,
            group,
            workspace_digest=projection.workspace_digest,
        ),
    )
    deferred = await binding.composite_backend.aread(
        "/review/groups/group-001.json"
    )
    assert deferred.error is None
    assert deferred.file_data is not None
    assert (
        json.loads(deferred.file_data["content"])["actions"][0]["status"]
        == "deferred"
    )

    runtime.review_decisions = (
        WorkspaceReviewDecision.from_group(
            WorkspaceReviewDecisionKind.REJECT,
            group,
            workspace_digest=projection.workspace_digest,
        ),
    )
    rejected = await binding.composite_backend.aread("/review/index.json")
    assert rejected.error is None
    assert rejected.file_data is not None
    assert json.loads(rejected.file_data["content"])["group_handles"] == []


@pytest.mark.asyncio
async def test_conflicted_review_keeps_unaffected_groups_and_real_store_document(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    task_path = "/workspace/tasks/task-001.json"
    header_path = "/workspace/header.json"
    workspace = workspace_binding.workspace
    task_before = (await workspace.read_snapshot()).files[task_path]
    header_before = (await workspace.read_snapshot()).files[header_path]
    assert (
        await workspace_binding.workspace_backend.aedit(
            task_path,
            '"整理需求"',
            '"AI整理需求"',
        )
    ).error is None
    assert (
        await workspace_binding.workspace_backend.aedit(
            header_path,
            '"採購專員"',
            '"新職稱"',
        )
    ).error is None

    snapshot = await workspace.read_snapshot()
    validation = validate_workspace_payload(
        snapshot.files,
        catalog=workspace_binding.catalog,
        selected_skill_ids=("output",),
        loaded_skill_ids=("output",),
    )
    assert validation.document is not None
    conflict = WorkspaceDiagnostic(
        code="workspace-rebase-conflict",
        path=f"{task_path}/statement",
        message="AI value retained while employee authority is committed.",
    )
    await workspace.commit_validation(
        expected_resource_digest=snapshot.manifest.resource_digest,
        evidence_basis_digest=evidence_basis_digest(validation.current_sources),
        validation_status=WorkspaceValidationStatus.CONFLICTED,
        diagnostics=(conflict,),
        entity_ids_by_handle=snapshot.manifest.entity_ids_by_handle,
    )

    index = await workspace_binding.composite_backend.aread("/review/index.json")
    assert index.error is None
    assert index.file_data is not None
    index_payload = json.loads(index.file_data["content"])
    assert len(index_payload["group_handles"]) == 2

    groups = []
    for handle in index_payload["group_handles"]:
        group = await workspace_binding.composite_backend.aread(
            f"/review/groups/{handle}.json"
        )
        assert group.error is None
        assert group.file_data is not None
        groups.append(json.loads(group.file_data["content"]))
    assert sum(bool(group["diagnostics"]) for group in groups) == 1
    assert sum(not group["diagnostics"] for group in groups) == 1
    assert (await workspace.read_snapshot()).files[task_path] != task_before
    assert (await workspace.read_snapshot()).files[header_path] != header_before


@pytest.mark.asyncio
async def test_missing_projection_download_uses_framework_not_found_code(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    responses = await workspace_binding.composite_backend.adownload_files(
        ["/approved/missing.json", "/sources/current/missing.txt"]
    )

    assert [response.error for response in responses] == [
        "file_not_found",
        "file_not_found",
    ]


@pytest.mark.asyncio
async def test_skill_route_is_read_only_and_selection_scoped(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    selected = await real_filesystem_tools.invoke(
        "read_file",
        file_path="/skills/output/SKILL.md",
    )
    unselected = await real_filesystem_tools.invoke(
        "read_file",
        file_path="/skills/knowledge/SKILL.md",
    )

    assert selected.status == "success"
    assert unselected.status == "error"


@pytest.mark.asyncio
async def test_source_projection_keeps_lineage_and_current_grep(
    workspace_binding: ConsultantWorkspaceBackendBinding,
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    current_handle = workspace_binding.catalog.handle_for_id(CURRENT_SOURCE_ID)
    current = await real_filesystem_tools.invoke(
        "read_file",
        file_path=f"/sources/current/{current_handle}.txt",
    )
    lineage = await workspace_binding.composite_backend.aread(
        f"/sources/lineages/{current_handle}/001.txt"
    )
    grep = await workspace_binding.composite_backend.agrep(
        "目前內容",
        path="/sources",
        max_count=1,
    )
    assert current.status == "success"
    assert lineage.error is None
    assert grep.error is None
    assert "目前內容第一行" in str(current.content)
    assert lineage.file_data is not None
    assert "過時內容" in lineage.file_data["content"]
    assert grep.matches is not None
    assert all("過時內容" not in match["text"] for match in grep.matches)


@pytest.mark.asyncio
async def test_read_only_routes_reject_mutation_through_real_tools(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    for path in (
        "/approved/header.json",
        "/review/index.json",
        "/sources/current/source-002.txt",
        "/skills/output/SKILL.md",
    ):
        edited = await real_filesystem_tools.invoke(
            "edit_file",
            file_path=path,
            old_string="x",
            new_string="y",
        )
        deleted = await real_filesystem_tools.invoke("delete", file_path=path)
        assert edited.status == deleted.status == "error"
