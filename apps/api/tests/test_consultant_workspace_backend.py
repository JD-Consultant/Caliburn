"""Focused characterization and policy tests for the consultant virtual workspace."""

from __future__ import annotations

import asyncio
import ast
import copy
from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any
from uuid import UUID, uuid4

import pytest
from deepagents.middleware.filesystem import FilesystemMiddleware, FilesystemState
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.consultant.skill_backend import skill_path
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    EmployeeSource,
    EmployeeSourceKind,
    SourceValidity,
)
from app.consultant.workspace_backend import (
    ConsultantWorkspaceBackendBinding,
    build_consultant_workspace_backend,
)
from app.consultant.workspace_resources import WorkspaceCatalog


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000101")
RUN_ID = UUID("00000000-0000-0000-0000-000000000102")
OTHER_RUN_ID = UUID("00000000-0000-0000-0000-000000000103")
DUTY_ID = UUID("00000000-0000-0000-0000-000000000201")
TASK_ID = UUID("00000000-0000-0000-0000-000000000202")
OLD_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000301")
CURRENT_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000302")
SECOND_CURRENT_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000303")


class FakeRuntime:
    def __init__(self, sources: tuple[EmployeeSource, ...]) -> None:
        self._sources = {source.source_id: source for source in sources}
        self.calls: list[tuple[str, UUID, UUID | None]] = []

    async def get_source(self, document_id: UUID, source_id: UUID) -> EmployeeSource:
        self.calls.append(("get_source", document_id, source_id))
        source = self._sources[source_id]
        assert source.document_id == document_id
        return source

    async def list_sources(self, document_id: UUID) -> tuple[EmployeeSource, ...]:
        self.calls.append(("list_sources", document_id, None))
        return tuple(
            source
            for source in sorted(
                self._sources.values(),
                key=lambda item: (item.created_at, str(item.source_id)),
            )
            if source.document_id == document_id
        )


class FilesystemToolHarness:
    """Run the real FilesystemMiddleware tools inside a LangGraph context."""

    def __init__(
        self,
        middleware: FilesystemMiddleware,
        initial_files: dict[str, dict[str, Any]],
    ) -> None:
        graph = StateGraph(FilesystemState)
        graph.add_node("tools", ToolNode(middleware.tools))
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        self._graph = graph.compile()
        self._state: dict[str, Any] = {"files": copy.deepcopy(initial_files)}

    @property
    def state(self) -> dict[str, Any]:
        return self._state

    async def invoke(self, name: str, **args: Any) -> ToolMessage:
        call = {
            "name": name,
            "args": args,
            "id": f"call-{uuid4()}",
            "type": "tool_call",
        }
        result = await self._graph.ainvoke(
            {
                "messages": [AIMessage(content="", tool_calls=[call])],
                "files": copy.deepcopy(self._state["files"]),
            }
        )
        self._state = result
        message = result["messages"][-1]
        assert isinstance(message, ToolMessage)
        return message

    async def invoke_many(
        self, calls: list[tuple[str, dict[str, Any]]]
    ) -> list[ToolMessage]:
        tool_calls = [
            {
                "name": name,
                "args": args,
                "id": f"call-{uuid4()}",
                "type": "tool_call",
            }
            for name, args in calls
        ]
        result = await self._graph.ainvoke(
            {
                "messages": [AIMessage(content="", tool_calls=tool_calls)],
                "files": copy.deepcopy(self._state["files"]),
            }
        )
        self._state = result
        messages = result["messages"][-len(calls) :]
        assert all(isinstance(message, ToolMessage) for message in messages)
        return messages

    def invoke_many_sync(
        self, calls: list[tuple[str, dict[str, Any]]]
    ) -> list[ToolMessage]:
        tool_calls = [
            {
                "name": name,
                "args": args,
                "id": f"call-{uuid4()}",
                "type": "tool_call",
            }
            for name, args in calls
        ]
        result = self._graph.invoke(
            {
                "messages": [AIMessage(content="", tool_calls=tool_calls)],
                "files": copy.deepcopy(self._state["files"]),
            }
        )
        self._state = result
        messages = result["messages"][-len(calls) :]
        assert all(isinstance(message, ToolMessage) for message in messages)
        return messages


class CancellationProbeMutex:
    """Instrument a real per-binding mutex without changing tool execution."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.contended = threading.Event()
        self.leaked_acquisition = threading.Event()
        self.mark_cancelled = False

    def acquire(self, blocking: bool = True) -> bool:
        if self._lock.locked():
            self.contended.set()
            if not blocking:
                return False
            acquired = self._lock.acquire()
            if self.mark_cancelled and acquired:
                self.leaked_acquisition.set()
            return acquired
        return self._lock.acquire(blocking)

    def release(self) -> None:
        self._lock.release()

    def force_release(self) -> None:
        if self._lock.locked():
            self._lock.release()


class NonblockingProbeMutex:
    """A mutex probe that makes any blocking async acquisition observable."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.contended = threading.Event()
        self.blocking_acquires = 0

    def acquire(self, blocking: bool = True) -> bool:
        if blocking:
            self.blocking_acquires += 1
            self.contended.set()
            return False
        if self._lock.locked():
            self.contended.set()
        return self._lock.acquire(False)

    def release(self) -> None:
        if self._lock.locked():
            self._lock.release()

    def force_release(self) -> None:
        if self._lock.locked():
            self._lock.release()


async def _wait_for_thread_event(
    event: threading.Event, *, timeout: float = 1.0
) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while not event.is_set() and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.001)
    return event.is_set()


def _sources() -> tuple[EmployeeSource, ...]:
    base_time = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)
    old = EmployeeSource.pending(
        source_id=OLD_SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="過時內容，不得出現在 current grep。",
        created_at=base_time,
    )
    current = EmployeeSource.pending(
        source_id=CURRENT_SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.DIRECT_EDIT,
        text="目前內容第一行。\n目前內容第二行。",
        supersedes_source_id=OLD_SOURCE_ID,
        created_at=base_time + timedelta(minutes=1),
    )
    old = old.model_copy(
        update={
            "validity": SourceValidity.SUPERSEDED,
            "superseded_by_source_id": CURRENT_SOURCE_ID,
        }
    )
    second_current = EmployeeSource.pending(
        source_id=SECOND_CURRENT_SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="目前內容來自第二個來源。",
        created_at=base_time + timedelta(minutes=2),
    )
    return old, current, second_current


def _catalog(sources: tuple[EmployeeSource, ...]) -> WorkspaceCatalog:
    document = ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        job_title="採購專員",
        work_description="管理採購流程。",
        competency_level=5,
        duties=(ApprovedDuty(duty_id=DUTY_ID, statement="管理採購作業", display_order=0),),
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
    return WorkspaceCatalog.from_snapshot(document, sources=sources)


@pytest.fixture
def workspace_binding() -> ConsultantWorkspaceBackendBinding:
    sources = _sources()
    runtime = FakeRuntime(sources)
    return build_consultant_workspace_backend(
        runtime=runtime,
        document_id=DOCUMENT_ID,
        run_id=RUN_ID,
        catalog=_catalog(sources),
        selected_skill_ids=("output",),
    )


@pytest.fixture
def real_filesystem_tools(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> FilesystemToolHarness:
    middleware = FilesystemMiddleware(
        backend=workspace_binding.composite_backend,
        tools=["ls", "read_file", "write_file", "edit_file", "delete", "grep"],
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
        grep_max_count=None,
    )
    return FilesystemToolHarness(middleware, workspace_binding.initial_files)


@pytest.mark.asyncio
async def test_workspace_binding_imports_and_exposes_only_five_roots(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    listing = await real_filesystem_tools.invoke("ls", path="/")

    assert listing.status == "success"
    assert ast.literal_eval(str(listing.content)) == [
        "/approved/",
        "/candidate/",
        "/pending/",
        "/skills/",
        "/sources/",
    ]


@pytest.mark.asyncio
async def test_only_current_candidate_namespace_is_mutable(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    current_new_path = f"/candidate/{RUN_ID}/tasks/task-002.json"
    assert (
        await real_filesystem_tools.invoke(
            "write_file", file_path=current_new_path, content='{"draft":true}\n'
        )
    ).status == "success"
    assert (
        await real_filesystem_tools.invoke(
            "edit_file",
            file_path=current_new_path,
            old_string='{"draft":true}',
            new_string='{"draft":false}',
        )
    ).status == "success"
    assert (
        await real_filesystem_tools.invoke("delete", file_path=current_new_path)
    ).status == "success"

    denied_writes = (
        f"/candidate/{RUN_ID}/header.json",
        f"/candidate/{OTHER_RUN_ID}/tasks/task-001.json",
        "/approved/header.json",
        "/sources/current/source-001.txt",
        "/skills/output/SKILL.md",
        "/pending/changesets/changeset-001.json",
    )
    for path in denied_writes:
        result = await real_filesystem_tools.invoke(
            "write_file", file_path=path, content="{}"
        )
        assert result.status == "error", path

    overwrite = await real_filesystem_tools.invoke(
        "write_file",
        file_path=f"/candidate/{RUN_ID}/header.json",
        content="{}",
    )
    assert overwrite.status == "error"

    replace_all = await real_filesystem_tools.invoke(
        "edit_file",
        file_path=f"/candidate/{RUN_ID}/header.json",
        old_string="採購專員",
        new_string="其他職務",
        replace_all=True,
    )
    assert replace_all.status == "error"

    delete_directory = await real_filesystem_tools.invoke(
        "delete", file_path=f"/candidate/{RUN_ID}/tasks/"
    )
    assert delete_directory.status == "error"

    other_run_read = await real_filesystem_tools.invoke(
        "read_file", file_path=f"/candidate/{OTHER_RUN_ID}/header.json"
    )
    assert other_run_read.status == "error"


@pytest.mark.asyncio
async def test_async_candidate_create_only_write_is_atomic_in_one_tool_wave(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    path = f"/candidate/{RUN_ID}/tasks/concurrent-001.json"
    messages = await real_filesystem_tools.invoke_many(
        [
            ("write_file", {"file_path": path, "content": '{"writer":1}\n'}),
            ("write_file", {"file_path": path, "content": '{"writer":2}\n'}),
        ]
    )

    assert sorted(message.status for message in messages) == ["error", "success"]
    assert real_filesystem_tools.state["files"][path]["content"] in {
        '{"writer":1}\n',
        '{"writer":2}\n',
    }


@pytest.mark.asyncio
async def test_cancelled_async_workspace_mutation_waiter_does_not_leak_mutex(
    workspace_binding: ConsultantWorkspaceBackendBinding,
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    candidate_backend = workspace_binding.candidate_backend
    original_mutex = candidate_backend._mutation_lock
    probe = CancellationProbeMutex()
    candidate_backend._mutation_lock = probe  # type: ignore[assignment]
    waiting_path = f"/candidate/{RUN_ID}/tasks/cancelled-001.json"
    later_path = f"/candidate/{RUN_ID}/tasks/cancelled-002.json"
    waiting = asyncio.create_task(
        real_filesystem_tools.invoke(
            "write_file", file_path=waiting_path, content='{"waiting":true}\n'
        )
    )
    try:
        probe.acquire()
        assert await _wait_for_thread_event(probe.contended)

        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting

        probe.mark_cancelled = True
        probe.release()
        leaked = await _wait_for_thread_event(
            probe.leaked_acquisition, timeout=0.25
        )
        if leaked:
            probe.release()

        later = await asyncio.wait_for(
            real_filesystem_tools.invoke(
                "write_file", file_path=later_path, content='{"later":true}\n'
            ),
            timeout=2.0,
        )
        assert leaked is False
        assert later.status == "success"
    finally:
        if not waiting.done():
            waiting.cancel()
        for _ in range(20):
            probe.force_release()
            await asyncio.sleep(0.001)
        candidate_backend._mutation_lock = original_mutex


@pytest.mark.asyncio
async def test_many_async_workspace_mutation_waiters_do_not_use_default_executor_for_mutex(
    workspace_binding: ConsultantWorkspaceBackendBinding,
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    candidate_backend = workspace_binding.candidate_backend
    original_mutex = candidate_backend._mutation_lock
    probe = NonblockingProbeMutex()
    candidate_backend._mutation_lock = probe  # type: ignore[assignment]
    executor = ThreadPoolExecutor(max_workers=1)
    asyncio.get_running_loop().set_default_executor(executor)
    calls = [
        (
            "write_file",
            {
                "file_path": f"/candidate/{RUN_ID}/tasks/wave-{index:03d}.json",
                "content": f'{{"writer":{index}}}\n',
            },
        )
        for index in range(100)
    ]
    try:
        assert probe.acquire(blocking=False)
        wave = asyncio.create_task(real_filesystem_tools.invoke_many(calls))
        assert await _wait_for_thread_event(probe.contended)
        probe.release()

        messages = await asyncio.wait_for(wave, timeout=10.0)
        assert all(message.status == "success" for message in messages)
        assert probe.blocking_acquires == 0
    finally:
        if not wave.done():
            wave.cancel()
            with pytest.raises(asyncio.CancelledError):
                await wave
        probe.force_release()
        candidate_backend._mutation_lock = original_mutex
        executor.shutdown(wait=True, cancel_futures=True)


def test_sync_candidate_create_only_write_is_serialized_in_one_tool_wave(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    path = f"/candidate/{RUN_ID}/tasks/concurrent-sync-001.json"
    messages = real_filesystem_tools.invoke_many_sync(
        [
            ("write_file", {"file_path": path, "content": '{"writer":1}\n'}),
            ("write_file", {"file_path": path, "content": '{"writer":2}\n'}),
        ]
    )

    assert sorted(message.status for message in messages) == ["error", "success"]
    assert real_filesystem_tools.state["files"][path]["content"] in {
        '{"writer":1}\n',
        '{"writer":2}\n',
    }


@pytest.mark.asyncio
async def test_framework_eviction_is_disabled_and_state_has_no_hidden_routes(
    workspace_binding: ConsultantWorkspaceBackendBinding,
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    middleware = FilesystemMiddleware(
        backend=workspace_binding.composite_backend,
        tools=["ls", "read_file", "write_file", "edit_file", "delete", "grep"],
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
    )
    assert middleware._tool_token_limit_before_evict is None
    assert middleware._human_message_token_limit_before_evict is None
    assert {tool.name for tool in middleware.tools} == {
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "delete",
        "grep",
    }
    assert not any(
        path.startswith(("/large_tool_results", "/conversation_history"))
        for path in real_filesystem_tools.state["files"]
    )


@pytest.mark.asyncio
async def test_source_projection_preserves_stable_read_lineage_and_current_grep(
    workspace_binding: ConsultantWorkspaceBackendBinding,
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    current_handle = workspace_binding.catalog.handle_for_id(CURRENT_SOURCE_ID)
    current = await real_filesystem_tools.invoke(
        "read_file", file_path=f"/sources/current/{current_handle}.txt"
    )
    assert current.status == "success"
    assert "目前內容第一行" in str(current.content)

    lineage = await workspace_binding.composite_backend.aread(
        f"/sources/lineages/{current_handle}/001.txt"
    )
    assert lineage.error is None
    assert lineage.file_data is not None
    assert lineage.file_data["content"] == "過時內容，不得出現在 current grep。"
    latest = await workspace_binding.composite_backend.aread(
        f"/sources/lineages/{current_handle}/002.txt"
    )
    assert latest.error is None
    assert latest.file_data is not None
    assert latest.file_data["content"].startswith("目前內容第一行")

    metadata = await workspace_binding.composite_backend.aread(
        f"/sources/current/{current_handle}.json"
    )
    assert metadata.error is None
    assert metadata.file_data is not None
    assert '"source_id":' in metadata.file_data["content"]
    assert '"validity": "current"' in metadata.file_data["content"]

    grep = await workspace_binding.composite_backend.agrep(
        "目前內容", path="/sources", max_count=1
    )
    assert grep.error is None
    assert grep.matches is not None
    assert len(grep.matches) == 1
    assert grep.matches[0]["path"].startswith("/sources/current/")
    assert grep.truncated is True
    assert all("過時內容" not in match["text"] for match in grep.matches)


@pytest.mark.asyncio
async def test_approved_and_pending_projections_are_readable_but_not_candidate_state(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    approved = await real_filesystem_tools.invoke(
        "read_file", file_path="/approved/header.json"
    )
    pending = await real_filesystem_tools.invoke(
        "read_file", file_path="/pending/index.json"
    )

    assert approved.status == "success"
    assert "採購專員" in str(approved.content)
    assert pending.status == "success"
    assert '"status": "pending"' in str(pending.content)
    assert all(
        path.startswith(f"/candidate/{RUN_ID}/")
        for path in real_filesystem_tools.state["files"]
    )


@pytest.mark.asyncio
async def test_missing_projection_download_uses_framework_file_not_found_code(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    responses = await workspace_binding.composite_backend.adownload_files(
        [
            "/approved/missing.json",
            "/sources/current/missing.txt",
        ]
    )

    assert [response.error for response in responses] == [
        "file_not_found",
        "file_not_found",
    ]


@pytest.mark.asyncio
async def test_skill_route_is_mount_relative_but_public_skill_path_is_stable(
    workspace_binding: ConsultantWorkspaceBackendBinding,
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    assert skill_path("output") == "/skills/output/SKILL.md"
    first = await real_filesystem_tools.invoke(
        "read_file", file_path=skill_path("output")
    )
    assert first.status == "success"
    assert "output" in workspace_binding.skill_backend.loaded_skill_ids

    duplicate = await real_filesystem_tools.invoke(
        "read_file", file_path=skill_path("output")
    )
    assert duplicate.status == "error"
    assert "already loaded" in str(duplicate.content)

    unselected = await real_filesystem_tools.invoke(
        "read_file", file_path="/skills/knowledge/SKILL.md"
    )
    assert unselected.status == "error"


@pytest.mark.asyncio
async def test_read_only_routes_reject_edit_and_delete_through_real_tools(
    real_filesystem_tools: FilesystemToolHarness,
) -> None:
    for path in (
        "/approved/header.json",
        "/sources/current/source-002.txt",
        "/skills/output/SKILL.md",
        "/pending/changesets/changeset-001.json",
    ):
        edited = await real_filesystem_tools.invoke(
            "edit_file", file_path=path, old_string="x", new_string="y"
        )
        deleted = await real_filesystem_tools.invoke("delete", file_path=path)
        assert edited.status == "error", path
        assert deleted.status == "error", path


def test_binding_keeps_initial_candidate_content_in_state_channel(
    workspace_binding: ConsultantWorkspaceBackendBinding,
) -> None:
    header_path = f"/candidate/{RUN_ID}/header.json"
    assert header_path in workspace_binding.initial_files
    assert workspace_binding.initial_files[header_path]["content"].endswith("\n")
    assert workspace_binding.initial_candidate_files[header_path].endswith("\n")
    assert workspace_binding.candidate_state_backend is not workspace_binding.composite_backend
