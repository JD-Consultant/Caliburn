from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
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
from app.consultant.workspace_resources import WorkspaceCatalog
from app.consultant.workspace_backend import WorkspacePolicyBackend
from app.consultant.workspace_state import (
    StoreBackedWorkspace,
    WorkspaceValidationStatus,
    approved_document_digest,
    workspace_resource_digest,
)
import app.consultant.workspace_validation as workspace_validation
from app.consultant.workspace_validation import WorkspaceValidationService


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000901")
DUTY_ID = UUID("00000000-0000-0000-0000-000000000902")
TASK_ID = UUID("00000000-0000-0000-0000-000000000903")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000904")
CORRECTED_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000905")


def _document() -> ApprovedJobDocument:
    return ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        job_title="採購專員",
        work_description="管理採購流程。",
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
                statement="核對訂單",
                action="核對",
                object="訂單",
                display_order=0,
            ),
        ),
    )


def _source(
    *,
    source_id: UUID = SOURCE_ID,
    text: str = "核對訂單，核對訂單。",
    validity: SourceValidity = SourceValidity.CURRENT,
    supersedes_source_id: UUID | None = None,
    superseded_by_source_id: UUID | None = None,
    created_at: datetime | None = None,
) -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=source_id,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text=text,
        supersedes_source_id=supersedes_source_id,
        created_at=created_at,
    ).model_copy(
        update={
            "processing_status": SourceProcessingStatus.COMMITTED,
            "validity": validity,
            "superseded_by_source_id": superseded_by_source_id,
        }
    )


class MutableSourceLoader:
    def __init__(self, sources: Sequence[EmployeeSource]) -> None:
        self.sources = tuple(sources)
        self.calls = 0

    async def __call__(self) -> tuple[EmployeeSource, ...]:
        self.calls += 1
        return self.sources


class LoadedSkills:
    def __init__(self, loaded_skill_ids: tuple[str, ...] = ("output",)) -> None:
        self.loaded_skill_ids = loaded_skill_ids


@dataclass
class ValidationRuntimeContext:
    workspace_validation: object | None = None


class CountingWaveModel(FakeMessagesListChatModel):
    call_count: int = 0

    def bind_tools(self, tools: Any, **kwargs: Any) -> CountingWaveModel:
        del tools, kwargs
        return self

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        self.call_count += 1
        return super()._generate(*args, **kwargs)


@pytest_asyncio.fixture
async def validation_harness() -> tuple[
    StoreBackedWorkspace,
    WorkspaceValidationService,
    MutableSourceLoader,
]:
    document = _document()
    source = _source()
    workspace = StoreBackedWorkspace(store=InMemoryStore(), document_id=DOCUMENT_ID)
    await workspace.ensure_initialized(
        approved_document=document,
        approved_revision=7,
    )
    loader = MutableSourceLoader((source,))
    validator = WorkspaceValidationService(
        workspace=workspace,
        catalog=WorkspaceCatalog.from_snapshot(document, sources=(source,)),
        source_loader=loader,
        selected_skill_ids=("output",),
    )
    return workspace, validator, loader


def _output_resource(
    *,
    quote: str = "核對訂單",
    occurrence: int | None = 2,
    task_handles: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "handle": "o-001",
            "kind": "output",
            "text": "完成核對的訂單",
            "task_handles": task_handles or ["task-001"],
            "indicator_handles": [],
            "evidence": [
                {
                    "source_handle": "source-001",
                    "quote": quote,
                    "occurrence": occurrence,
                    "skill_ids": ["output"],
                }
            ],
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


@pytest.mark.asyncio
async def test_digest_mismatch_forces_validation_instead_of_trusting_manifest(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    workspace, validator, _loader = validation_harness
    task_path = "/workspace/tasks/task-001.json"
    snapshot = await workspace.read_snapshot()
    old = snapshot.files[task_path]
    invalid = old.replace('"duty_handle": "duty-001"', '"duty_handle": "duty-999"')
    assert (await workspace.backend.aedit(task_path, old, invalid)).error is None

    result = await validator.validate_current(loaded_skill_ids=("output",))

    assert result.manifest.validation_status is WorkspaceValidationStatus.INVALID
    assert result.manifest.resource_digest == workspace_resource_digest(
        (await workspace.read_snapshot()).files
    )
    assert result.document is None
    assert result.diagnostics[0].code == "linkage"
    assert result.diagnostics[0].path == task_path


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "content", "expected_code"),
    [
        ("/workspace/header.json", "{not-json\n", "json-syntax"),
        (
            "/workspace/tasks/task-001.json",
            '{"handle":"task-001","statement":"缺少 action 與 object"}\n',
            "schema",
        ),
        (
            "/workspace/opks/o/o-001.json",
            _output_resource(task_handles=["task-999"]),
            "linkage",
        ),
        (
            "/workspace/opks/o/o-001.json",
            _output_resource(task_handles=["task-001", "task-001"]),
            "jd-invariant",
        ),
    ],
)
async def test_validation_returns_short_structured_resource_diagnostics(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
    path: str,
    content: str,
    expected_code: str,
) -> None:
    workspace, validator, _loader = validation_harness
    current = await workspace.read_snapshot()
    if path in current.files:
        assert (await workspace.backend.aedit(path, current.files[path], content)).error is None
    else:
        assert (await workspace.backend.awrite(path, content)).error is None

    result = await validator.validate_current(loaded_skill_ids=("output",))

    assert result.document is None
    assert result.diagnostics
    assert result.diagnostics[0].code == expected_code
    assert result.diagnostics[0].path == path
    assert len(result.diagnostics[0].message) <= 240
    assert "採購流程" not in result.diagnostics[0].message


@pytest.mark.asyncio
async def test_exact_quote_occurrence_and_loaded_skill_are_validated(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    workspace, validator, _loader = validation_harness
    path = "/workspace/opks/o/o-001.json"
    ambiguous = _output_resource(occurrence=None)
    assert (await workspace.backend.awrite(path, ambiguous)).error is None

    ambiguous_result = await validator.validate_current(loaded_skill_ids=("output",))
    assert ambiguous_result.document is None
    assert ambiguous_result.diagnostics[0].code == "evidence-quote"

    exact = _output_resource(occurrence=2)
    assert (await workspace.backend.aedit(path, ambiguous, exact)).error is None
    unloaded = await validator.validate_current(loaded_skill_ids=())
    assert unloaded.document is None
    assert unloaded.diagnostics[0].code == "skill-unloaded"

    valid = await validator.validate_current(loaded_skill_ids=("output",))
    assert valid.manifest.validation_status is WorkspaceValidationStatus.VALID
    assert valid.document is not None

    reset_receipts = await validator.validate_current(loaded_skill_ids=())
    assert reset_receipts.document is None
    assert reset_receipts.manifest.validation_status is WorkspaceValidationStatus.INVALID
    assert reset_receipts.diagnostics[0].code == "skill-unloaded"


@pytest.mark.asyncio
async def test_source_correction_revalidates_unchanged_files_and_invalidates_old_basis(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    workspace, validator, loader = validation_harness
    path = "/workspace/opks/o/o-001.json"
    assert (await workspace.backend.awrite(path, _output_resource())).error is None
    first = await validator.validate_current(loaded_skill_ids=("output",))
    files_before = dict((await workspace.read_snapshot()).files)
    created = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
    loader.sources = (
        _source(
            validity=SourceValidity.SUPERSEDED,
            superseded_by_source_id=CORRECTED_SOURCE_ID,
            created_at=created,
        ),
        _source(
            source_id=CORRECTED_SOURCE_ID,
            text="更正：只需回報結果。",
            supersedes_source_id=SOURCE_ID,
            created_at=created + timedelta(minutes=1),
        ),
    )

    corrected = await validator.validate_current(loaded_skill_ids=("output",))

    assert first.document is not None
    assert corrected.document is None
    assert corrected.manifest.generation == first.manifest.generation + 1
    assert corrected.manifest.resource_digest == first.manifest.resource_digest
    assert corrected.manifest.evidence_basis_digest != first.manifest.evidence_basis_digest
    assert corrected.diagnostics[0].code == "evidence-source-stale"
    assert (await workspace.read_snapshot()).files == files_before


@pytest.mark.asyncio
async def test_invalid_draft_is_retained_and_repair_advances_generation_to_valid(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    workspace, validator, _loader = validation_harness
    path = "/workspace/header.json"
    before = (await workspace.read_snapshot()).files[path]
    invalid = "{invalid json\n"
    assert (await workspace.backend.aedit(path, before, invalid)).error is None
    failed = await validator.validate_current(loaded_skill_ids=("output",))

    assert failed.document is None
    assert (await workspace.read_snapshot()).files[path] == invalid

    assert (await workspace.backend.aedit(path, invalid, before)).error is None
    repaired = await validator.validate_current(loaded_skill_ids=("output",))

    assert repaired.document is not None
    assert repaired.manifest.validation_status is WorkspaceValidationStatus.VALID
    assert repaired.manifest.generation == failed.manifest.generation + 1


@pytest.mark.asyncio
async def test_approved_basis_mismatch_fails_closed_without_trusting_valid_status(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    workspace, validator, _loader = validation_harness
    first = await validator.validate_current(loaded_skill_ids=("output",))
    changed = _document().model_copy(update={"job_title": "員工已直接修訂"})
    await workspace._put_manifest(  # noqa: SLF001 - stale-basis crash characterization
        first.manifest.model_copy(
            update={
                "approved_baseline_digest": approved_document_digest(changed),
                "validation_status": WorkspaceValidationStatus.VALID,
            }
        )
    )

    result = await validator.validate_current(loaded_skill_ids=("output",))

    assert result.document is None
    assert result.manifest.validation_status is WorkspaceValidationStatus.INVALID
    assert result.diagnostics[0].code == "approved-basis-stale"

    cached = await validator.validate_current(loaded_skill_ids=("output",))
    assert cached.revalidated is False
    assert cached.manifest.generation == result.manifest.generation


@pytest.mark.asyncio
async def test_stale_manifest_identity_registry_is_revalidated_against_workspace(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    workspace, validator, _loader = validation_harness
    first = await validator.validate_current(loaded_skill_ids=("output",))
    stale_registry = dict(first.manifest.entity_ids_by_handle)
    stale_registry["task-001"] = UUID("00000000-0000-0000-0000-000000000099")
    await workspace._put_manifest(  # noqa: SLF001 - stale-manifest characterization
        first.manifest.model_copy(update={"entity_ids_by_handle": stale_registry})
    )

    result = await validator.validate_current(loaded_skill_ids=("output",))

    assert result.document is None
    assert result.manifest.validation_status is WorkspaceValidationStatus.INVALID
    assert result.diagnostics[0].code == "identity"
    assert result.diagnostics[0].path == "/workspace/tasks/task-001.json"


@pytest.mark.asyncio
async def test_validation_middleware_validates_one_complete_mutation_wave_once(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    middleware_type = getattr(
        workspace_validation,
        "WorkspaceValidationMiddleware",
        None,
    )
    assert middleware_type is not None
    workspace, validator, _loader = validation_harness
    middleware = middleware_type(validator=validator, skill_backend=LoadedSkills())
    filesystem = FilesystemMiddleware(
        backend=WorkspacePolicyBackend(workspace.backend),
        tools=["read_file", "edit_file"],
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
    )
    model = CountingWaveModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "edit_file",
                        "args": {
                            "file_path": "/workspace/header.json",
                            "old_string": "採購專員",
                            "new_string": "採購管理師",
                        },
                        "id": "edit-header",
                        "type": "tool_call",
                    },
                    {
                        "name": "edit_file",
                        "args": {
                            "file_path": "/workspace/tasks/task-001.json",
                            "old_string": "核對訂單",
                            "new_string": "複核訂單",
                        },
                        "id": "edit-task",
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(content="完成"),
        ]
    )
    context = ValidationRuntimeContext()
    graph = create_agent(
        model=model,
        tools=(),
        middleware=(filesystem, middleware),
        context_schema=ValidationRuntimeContext,
    )

    await graph.ainvoke(
        {"messages": [HumanMessage(content="更新草稿")]},
        context=context,
    )

    snapshot = await workspace.read_snapshot()
    assert model.call_count == 2
    assert snapshot.manifest.validation_status is WorkspaceValidationStatus.VALID
    assert snapshot.manifest.generation == 2
    assert context.workspace_validation is not None
    assert context.workspace_validation.generation == 2

    cached = await validator.validate_current(loaded_skill_ids=("output",))
    assert cached.revalidated is False
    assert cached.manifest.generation == 2


@pytest.mark.asyncio
async def test_invalid_final_gets_only_one_framework_native_repair_jump(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    middleware_type = getattr(
        workspace_validation,
        "WorkspaceValidationMiddleware",
        None,
    )
    assert middleware_type is not None
    workspace, validator, _loader = validation_harness
    path = "/workspace/header.json"
    before = (await workspace.read_snapshot()).files[path]
    assert (await workspace.backend.aedit(path, before, "{invalid\n")).error is None
    middleware = middleware_type(validator=validator, skill_backend=LoadedSkills())
    runtime = SimpleNamespace(context=ValidationRuntimeContext())
    await middleware.abefore_model({}, runtime)
    final_state = {"messages": [AIMessage(content="直接完成") ]}

    first = await middleware.aafter_model(final_state, runtime)
    second = await middleware.aafter_model(
        {
            **final_state,
            "workspace_validation_repair_requested": True,
        },
        runtime,
    )

    assert first == {
        "workspace_validation_repair_requested": True,
        "jump_to": "model",
    }
    assert second is None
    assert runtime.context.workspace_validation.status is WorkspaceValidationStatus.INVALID
    assert runtime.context.workspace_validation.diagnostics[0].code == "json-syntax"
    assert not hasattr(middleware.aafter_model, "__can_jump_to__")


def _invalid_then_final_model() -> CountingWaveModel:
    return CountingWaveModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "edit_file",
                        "args": {
                            "file_path": "/workspace/header.json",
                            "old_string": '"採購專員"',
                            "new_string": "not-json",
                        },
                        "id": "break-header",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="直接完成"),
            AIMessage(content="仍然完成"),
        ]
    )


def _validation_loop(
    *,
    workspace: StoreBackedWorkspace,
    validator: WorkspaceValidationService,
    model: CountingWaveModel,
    model_limit: int | None = None,
) -> Any:
    middleware: list[Any] = []
    if model_limit is not None:
        middleware.append(
            ModelCallLimitMiddleware(run_limit=model_limit, exit_behavior="error")
        )
    middleware.extend(
        [
            FilesystemMiddleware(
                backend=WorkspacePolicyBackend(workspace.backend),
                tools=["read_file", "edit_file"],
                system_prompt=None,
                tool_token_limit_before_evict=None,
                human_message_token_limit_before_evict=None,
            ),
            workspace_validation.WorkspaceValidationMiddleware(
                validator=validator,
                skill_backend=LoadedSkills(),
            ),
        ]
    )
    return create_agent(
        model=model,
        tools=(),
        middleware=tuple(middleware),
        context_schema=ValidationRuntimeContext,
    )


@pytest.mark.asyncio
async def test_invalid_direct_final_adds_exactly_one_model_repair_call(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    workspace, validator, _loader = validation_harness
    model = _invalid_then_final_model()
    graph = _validation_loop(workspace=workspace, validator=validator, model=model)

    await graph.ainvoke(
        {"messages": [HumanMessage(content="破壞後直接完成")]},
        context=ValidationRuntimeContext(),
    )

    assert model.call_count == 3
    assert (
        await workspace.read_snapshot()
    ).manifest.validation_status is WorkspaceValidationStatus.INVALID


@pytest.mark.asyncio
async def test_invalid_repair_jump_remains_bounded_by_model_call_hard_guard(
    validation_harness: tuple[
        StoreBackedWorkspace,
        WorkspaceValidationService,
        MutableSourceLoader,
    ],
) -> None:
    workspace, validator, _loader = validation_harness
    model = _invalid_then_final_model()
    graph = _validation_loop(
        workspace=workspace,
        validator=validator,
        model=model,
        model_limit=2,
    )

    await graph.ainvoke(
        {"messages": [HumanMessage(content="受 hard guard 限制")]},
        context=ValidationRuntimeContext(),
    )

    assert model.call_count == 2
