from __future__ import annotations

import copy
import json
import os
import re
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from deepagents.middleware.filesystem import FilesystemMiddleware, FilesystemState
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import Field

from app.adapters.langgraph.postgres import open_postgres_consultant_runtime
from app.consultant.candidate_publication import CandidatePublicationStale
from app.consultant.document_review import AtomicSubgroupIncomplete
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    OutputTokenParameter,
    RunPolicy,
    resolve_execution,
)
from app.consultant.run_service import execute_admitted_consultant_turn
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    DocumentChangeStatus,
    DocumentChangeSet,
    RunStatus,
)
from app.consultant.workspace_backend import build_consultant_workspace_backend
from app.consultant.workspace_resources import (
    WorkspaceCatalog,
    pending_action_handles,
    project_candidate_files,
)


EXPECTED_TOOLS = {
    "ls",
    "read_file",
    "grep",
    "write_file",
    "edit_file",
    "delete",
    "check_candidate_document",
}


def _database_url() -> str:
    return os.getenv("TEST_DATABASE_URL", "").replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


@pytest_asyncio.fixture(autouse=True)
async def cleanup_new_consultant_documents() -> AsyncIterator[None]:
    database_url = _database_url()
    if not database_url:
        yield
        return

    async def catalog_ids() -> set[UUID]:
        async with await psycopg.AsyncConnection.connect(
            database_url, autocommit=True
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT to_regclass('public.consultant_documents')"
                )
                row = await cursor.fetchone()
                if row is None or row[0] is None:
                    return set()
                await cursor.execute("SELECT document_id FROM consultant_documents")
                return {row[0] for row in await cursor.fetchall()}

    before = await catalog_ids()
    yield
    created = await catalog_ids() - before
    if not created:
        return
    async with open_postgres_consultant_runtime(database_url) as runtime:
        for document_id in created:
            await runtime.delete_document(document_id)
    async with await psycopg.AsyncConnection.connect(
        database_url, autocommit=True
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.executemany(
                "DELETE FROM consultant_documents WHERE document_id = %s",
                [(document_id,) for document_id in created],
            )


@pytest.fixture
def consultant_database_url() -> str:
    value = _database_url()
    if not value:
        pytest.skip("TEST_DATABASE_URL not set; consultant PostgreSQL test skipped")
    return value


def _document(document_id: UUID) -> ApprovedJobDocument:
    duty_id = uuid4()
    task_id = uuid4()
    return ApprovedJobDocument(
        document_id=document_id,
        job_title="採購專員",
        work_description="管理採購流程。",
        duties=(
            ApprovedDuty(
                duty_id=duty_id,
                statement="管理採購作業",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=task_id,
                duty_id=duty_id,
                statement="核對訂單",
                action="核對",
                object="訂單",
                purpose_result="避免錯誤出貨",
                display_order=0,
            ),
        ),
    )


def _execution():
    profile = ConsultantModelProfile(
        profile_id="primary-consultant",
        revision=1,
        requested_model="anthropic/claude-opus-5",
        provider_allowlist=("Anthropic",),
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=4096,
        output_token_parameter=OutputTokenParameter.MAX_TOKENS,
        reasoning_effort="high",
        timeout_seconds=90,
    )
    policy = RunPolicy(
        policy_id="interactive-consultation",
        revision=1,
        run_kind="interactive_consultation",
        allowed_skill_ids=CONSULTANT_SKILL_IDS,
        allowed_tool_ids=tuple(sorted(EXPECTED_TOOLS)),
        max_context_tokens=24_000,
        max_model_calls=8,
        max_lookup_waves=2,
        max_total_tool_calls=12,
        model_retry_count=0,
        tool_retry_count=0,
        max_elapsed_seconds=180,
        max_total_tokens=32_000,
        max_cost_usd=Decimal("2.00"),
    )
    return resolve_execution(profile, policy)


async def _prepare_runtime_run(runtime: Any, document_id: UUID, run_id: UUID) -> dict[str, Any]:
    created = await runtime.create_document(document_id, title="採購職務")
    seeded = await runtime.apply_direct_edit(
        document_id=document_id,
        expected_revision=created.revision,
        document=_document(document_id),
        source_id=uuid4(),
    )
    answer_source_id = uuid4()
    admitted, should_process = await runtime.admit_employee_answer(
        document_id=document_id,
        run_id=run_id,
        source_id=answer_source_id,
        text="我負責核對訂單並回報結果。",
    )
    assert should_process is True
    sources = await runtime.list_sources(document_id)
    catalog = WorkspaceCatalog.from_snapshot(
        admitted.approved_document,
        sources=sources,
    )
    return {
        "baseline": seeded.approved_document,
        "snapshot": admitted,
        "sources": sources,
        "catalog": catalog,
        "source_id": answer_source_id,
        "source_handle": catalog.source_handle_for_id(answer_source_id),
        "task_handle": catalog.handle_for_id(admitted.approved_document.tasks[0].task_id),
    }


def _add_output(
    files: dict[str, str],
    *,
    run_id: UUID,
    handle: str,
    text: str,
    task_handle: str,
    source_handle: str,
) -> None:
    path = f"/candidate/{run_id}/opks/o/{handle}.json"
    files[path] = (
        json.dumps(
            {
                "handle": handle,
                "kind": "output",
                "text": text,
                "task_handles": [task_handle],
                "indicator_handles": [],
                "evidence": [
                    {
                        "source_handle": source_handle,
                        "quote": "核對訂單",
                        "skill_ids": ["output"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


async def _check_and_publish(
    runtime: Any,
    *,
    document_id: UUID,
    run_id: UUID,
    files: dict[str, str],
    call_id: str,
    skill_ids: tuple[str, ...] = ("output",),
) -> tuple[Any, Any]:
    checked = await runtime.check_candidate_document(
        document_id=document_id,
        run_id=run_id,
        files=files,
        tool_call_id=call_id,
        selected_skill_ids=skill_ids,
        loaded_skill_ids=skill_ids,
    )
    assert checked.status == "checked", checked.issues
    published = await runtime.publish_checked_candidate(
        document_id=document_id,
        run_id=run_id,
        files=files,
    )
    return checked, published


class _FilesystemToolProbe:
    """Run real filesystem middleware tools inside a LangGraph state context."""

    def __init__(self, binding: Any) -> None:
        middleware = FilesystemMiddleware(
            backend=binding.composite_backend,
            tools=["ls", "read_file", "write_file", "glob"],
            system_prompt=None,
            tool_token_limit_before_evict=None,
            human_message_token_limit_before_evict=None,
            grep_max_count=None,
        )
        graph = StateGraph(FilesystemState)
        graph.add_node("tools", ToolNode(middleware.tools))
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        self._graph = graph.compile()
        self._state = {"files": copy.deepcopy(binding.initial_files)}

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


class ScriptedConsultantModel(FakeMessagesListChatModel):
    """A deterministic provider double that observes real Tool results."""

    run_id: UUID
    source_handle: str
    call_count: int = 0
    bound_tool_names: list[tuple[str, ...]] = Field(default_factory=list)
    observed_reads: list[str] = Field(default_factory=list)
    check_results: list[dict[str, Any]] = Field(default_factory=list)
    final_publication: dict[str, Any] | None = None

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ScriptedConsultantModel:
        del tool_choice, kwargs
        names = tuple(
            str(
                getattr(tool, "name", None)
                or getattr(tool, "__name__", None)
                or (tool.get("name", "") if isinstance(tool, dict) else "")
            )
            for tool in tools
        )
        self.bound_tool_names.append(names)
        return self

    @staticmethod
    def _tool_call(name: str, call_id: str, **args: Any) -> dict[str, Any]:
        return {
            "name": name,
            "args": args,
            "id": call_id,
            "type": "tool_call",
        }

    def _message(
        self,
        *,
        content: str = "",
        tool_calls: Sequence[dict[str, Any]] = (),
    ) -> ChatResult:
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=content,
                        tool_calls=list(tool_calls),
                        response_metadata={
                            "model_name": "anthropic/claude-opus-5-20260801",
                            "provider": "Anthropic",
                            "cost": "0.01",
                        },
                        usage_metadata={
                            "input_tokens": 100,
                            "output_tokens": 40,
                            "total_tokens": 140,
                        },
                    )
                )
            ]
        )

    def _final_content(self, messages: Sequence[BaseMessage]) -> str:
        checks: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, ToolMessage):
                continue
            if message.name == "read_file":
                self.observed_reads.append(str(message.content))
            if message.name != "check_candidate_document":
                continue
            checks.append(json.loads(str(message.content)))
        self.check_results = checks
        latest = checks[-1]
        if latest.get("status") != "checked":
            raise AssertionError(f"script expected a successful final check: {latest}")
        publication = {
            "candidate_revision": latest["candidate_revision"],
            "revision_digest": latest["resource_digest"],
            "action_handles": latest["action_handles"],
        }
        self.final_publication = publication
        return json.dumps(
            {
                "visible_reply": "我已整理出一項可供員工審核的候選成果。",
                "analysis_bases": [
                    {
                        "evidence": [
                            {
                                "source_handle": self.source_handle,
                                "quote": "核對訂單",
                                "occurrence": 0,
                                "skill_ids": ["output"],
                            }
                        ]
                    }
                ],
                "reply_basis_ordinal": 1,
                "used_skill_ids": ["output"],
                "understanding_changes": [],
                "attention_changes": [],
                "gaps": [],
                "candidate_publication": publication,
                "question": {
                    "kind": "none",
                    "text": "",
                    "answer_target": "",
                    "reason": "",
                    "current_understanding": "",
                    "choices": [],
                    "affected_work_ids": [],
                    "affected_branch": "",
                    "basis_ordinal": 0,
                },
                "sufficiency": {
                    "currently_enough": True,
                    "reason": "候選成果已準備好交由員工審核。",
                    "remaining_gap_reasons": [],
                    "continuing_benefit": "候選內容可供員工審核。",
                    "basis_ordinal": 1,
                },
            },
            ensure_ascii=False,
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        self.call_count += 1
        run_root = f"/candidate/{self.run_id}"
        output_path = f"{run_root}/opks/o/o-002.json"
        if self.call_count == 1:
            return self._message(
                tool_calls=(
                    self._tool_call(
                        "read_file",
                        "script-read-source",
                        file_path=f"/sources/current/{self.source_handle}.txt",
                    ),
                    self._tool_call(
                        "read_file",
                        "script-read-skill",
                        file_path="/skills/output/SKILL.md",
                    ),
                )
            )
        if self.call_count == 2:
            return self._message(
                tool_calls=(
                    self._tool_call(
                        "write_file",
                        "script-write-output",
                        file_path=output_path,
                        content=json.dumps(
                            {
                                "handle": "o-002",
                                "kind": "output",
                                "text": "完成採購核對",
                                "task_handles": ["task-001"],
                                "indicator_handles": [],
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                    ),
                )
            )
        if self.call_count == 3:
            return self._message(
                tool_calls=(
                    self._tool_call(
                        "check_candidate_document",
                        "script-check-invalid",
                    ),
                )
            )
        if self.call_count == 4:
            return self._message(
                tool_calls=(
                    self._tool_call(
                        "edit_file",
                        "script-repair-output",
                        file_path=output_path,
                        old_string='"indicator_handles": []\n}',
                        new_string=(
                            '"indicator_handles": [],\n'
                            '  "evidence": [\n'
                            '    {\n'
                            '      "source_handle": "'
                            + self.source_handle
                            + '",\n'
                            '      "quote": "核對訂單",\n'
                            '      "skill_ids": [\n'
                            '        "output"\n'
                            '      ]\n'
                            '    }\n'
                            '  ]\n'
                            '}'
                        ),
                    ),
                )
            )
        if self.call_count == 5:
            return self._message(
                tool_calls=(
                    self._tool_call(
                        "check_candidate_document",
                        "script-check-valid",
                    ),
                )
            )
        if self.call_count == 6:
            return self._message(content=self._final_content(messages))
        raise AssertionError(f"scripted consultant exceeded expected calls: {self.call_count}")


@pytest.mark.asyncio
async def test_real_agent_repairs_candidate_and_publishes_pending_only(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    seed_source_id = uuid4()
    answer_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        created = await runtime.create_document(document_id, title="採購職務")
        seeded = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=created.revision,
            document=_document(document_id),
            source_id=seed_source_id,
        )
        before_answer = seeded.approved_document
        admitted, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            text="我負責核對訂單並回報結果。",
        )
        assert should_process is True
        sources = await runtime.list_sources(document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            admitted.approved_document,
            sources=sources,
        )
        source_handle = catalog.source_handle_for_id(answer_source_id)
        model = ScriptedConsultantModel(
            responses=[],
            run_id=run_id,
            source_handle=source_handle,
        )

        completed = await execute_admitted_consultant_turn(
            runtime=runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=answer_source_id,
            execution=_execution(),
            model=model,
        )

        assert model.call_count == 6
        assert [item["status"] for item in model.check_results] == [
            "invalid",
            "checked",
        ]
        assert model.check_results[0]["issues"]
        assert model.final_publication == {
            "candidate_revision": model.check_results[1]["candidate_revision"],
            "revision_digest": model.check_results[1]["resource_digest"],
            "action_handles": model.check_results[1]["action_handles"],
        }
        assert set(EXPECTED_TOOLS) <= set().union(*model.bound_tool_names)
        assert any("我負責核對訂單並回報結果。" in item for item in model.observed_reads)
        assert any("output" in item.lower() for item in model.observed_reads)
        assert completed.approved_document == before_answer
        assert completed.latest_run is not None
        assert completed.latest_run["status"] == RunStatus.COMPLETED.value
        assert len(completed.review_queue) == 1
        bundle = next(iter(completed.review_queue.values()))
        assert len(bundle["actions"]) == 1
        assert bundle["actions"][0]["status"] == DocumentChangeStatus.PENDING.value
        assert bundle["actions"][0]["after"]["text"] == "完成採購核對"
        assert (await runtime.raw_state(document_id))["checked_candidate"] is None

        pending_bundle = DocumentChangeSet.model_validate(
            next(iter(completed.review_queue.values()))
        )
        pending_catalog = WorkspaceCatalog.from_snapshot(
            completed.approved_document,
            pending=(pending_bundle,),
            sources=sources,
        )
        binding = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            run_id=uuid4(),
            catalog=pending_catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        pending_paths = (
            "/index.json",
            "/reviews/review-001.json",
            "/actions/action-001.json",
        )
        pending_payloads = []
        for path in pending_paths:
            read = binding.pending_backend.read(path)
            assert read.error is None
            assert read.file_data is not None
            pending_payloads.append(json.loads(read.file_data["content"]))
        pending_surface = "\n".join(pending_paths) + json.dumps(
            pending_payloads, ensure_ascii=False
        )
        action_payload = bundle["actions"][0]
        raw_authority_ids = {
            bundle["changeset_id"],
            *bundle["source_ids"],
            *action_payload["source_ids"],
            *action_payload["depends_on_action_ids"],
            action_payload["action_id"],
        }
        for authority_id in raw_authority_ids:
            assert authority_id not in pending_surface
        assert re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}",
            pending_surface,
        ) is None
        assert pending_payloads[0] == {
            "approved": False,
            "status": "pending",
            "review_handles": ["review-001"],
            "action_handles": ["action-001"],
        }
        assert pending_payloads[1] == {
            "handle": "review-001",
            "approved": False,
            "status": "pending",
            "summary": "Verified virtual JD candidate",
            "action_handles": ["action-001"],
            "dependency_handles": [],
        }
        assert pending_payloads[2] == {
            "handle": "action-001",
            "approved": False,
                "status": "pending",
                "operation": "add",
                "path": "/opks",
                "target_handles": ["o-001"],
            "before": None,
            "after": {
                "kind": "output",
                "text": "完成採購核對",
                "task_handles": ["task-001"],
                "indicator_handles": [],
            },
            "dependency_handles": [],
        }


@pytest.mark.asyncio
async def test_runtime_partial_review_keeps_rejected_output_memory(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        prepared = await _prepare_runtime_run(runtime, document_id, run_id)
        files = project_candidate_files(prepared["catalog"], run_id=run_id)
        header_path = f"/candidate/{run_id}/header.json"
        header = json.loads(files[header_path])
        header["job_title"] = "資深採購專員"
        files[header_path] = json.dumps(header, ensure_ascii=False, indent=2) + "\n"
        # Two independent actions are the smallest equivalent of the planned
        # 9-accept/1-reject set: the invariant is partial review plus rejected-O memory.
        _add_output(
            files,
            run_id=run_id,
            handle="o-002",
            text="可接受輸出",
            task_handle=prepared["task_handle"],
            source_handle=prepared["source_handle"],
        )
        checked, published = await _check_and_publish(
            runtime,
            document_id=document_id,
            run_id=run_id,
            files=files,
            call_id="partial-review-check-001",
        )
        header_action = next(action for action in checked.actions if action.path == "/job_title")
        output_action = next(action for action in checked.actions if action.path == "/opks")

        accepted = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=published.revision,
            action="accept_changes",
            changeset_id=checked.receipt.changeset.changeset_id,
            action_ids=(header_action.action_id,),
        )
        assert accepted.approved_document.job_title == "資深採購專員"
        assert not accepted.approved_document.opks

        rejected = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=accepted.revision,
            action="reject_changes",
            changeset_id=checked.receipt.changeset.changeset_id,
            action_ids=(output_action.action_id,),
            rejection_reason="這項輸出尚未符合員工說法。",
        )
        bundle = DocumentChangeSet.model_validate(
            next(iter(rejected.review_queue.values()))
        )
        assert [action.status for action in bundle.actions] == [
            DocumentChangeStatus.ACCEPTED,
            DocumentChangeStatus.REJECTED,
        ]
        assert rejected.approved_document.job_title == "資深採購專員"
        assert not rejected.approved_document.opks

        pending_catalog = WorkspaceCatalog.from_snapshot(
            rejected.approved_document,
            pending=(bundle,),
            sources=await runtime.list_sources(document_id),
        )
        binding = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            run_id=uuid4(),
            catalog=pending_catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        approved_read = binding.approved_backend.read("/header.json")
        assert approved_read.error is None
        assert approved_read.file_data is not None
        approved_header = json.loads(approved_read.file_data["content"])
        assert approved_header["job_title"] == "資深採購專員"
        assert "可接受輸出" not in approved_read.file_data["content"]
        assert binding.approved_backend.read("/opks/o/o-002.json").error is not None
        assert all(
            "可接受輸出" not in content
            for content in binding.initial_candidate_files.values()
        )
        handles = pending_action_handles((bundle,))
        rejected_handle = handles[output_action.action_id]
        read = binding.pending_backend.read(f"/actions/{rejected_handle}.json")
        assert read.error is None
        assert read.file_data is not None
        rejected_view = json.loads(read.file_data["content"])
        assert rejected_view["approved"] is False
        assert rejected_view["status"] == "rejected"
        assert rejected_view["decision_reason"] == "這項輸出尚未符合員工說法。"
        assert rejected_view["after"]["text"] == "可接受輸出"

        retry_catalog = WorkspaceCatalog.from_snapshot(
            rejected.approved_document,
            pending=(bundle,),
            sources=await runtime.list_sources(document_id),
        )
        retry_files = project_candidate_files(retry_catalog, run_id=run_id)
        _add_output(
            retry_files,
            run_id=run_id,
            handle="o-002",
            text="可接受輸出",
            task_handle=prepared["task_handle"],
            source_handle=prepared["source_handle"],
        )
        retry = await runtime.check_candidate_document(
            document_id=document_id,
            run_id=run_id,
            files=retry_files,
            tool_call_id="partial-review-retry-001",
            selected_skill_ids=("output",),
            loaded_skill_ids=("output",),
        )
        assert retry.status == "invalid"
        assert any("rejected target" in issue for issue in retry.issues)


@pytest.mark.asyncio
async def test_runtime_defer_then_direct_edit_stales_only_pending_projection(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        prepared = await _prepare_runtime_run(runtime, document_id, run_id)
        files = project_candidate_files(prepared["catalog"], run_id=run_id)
        header_path = f"/candidate/{run_id}/header.json"
        header = json.loads(files[header_path])
        header["job_title"] = "候選採購專員"
        header["work_description"] = "候選工作描述"
        files[header_path] = json.dumps(header, ensure_ascii=False, indent=2) + "\n"
        checked_only = await runtime.check_candidate_document(
            document_id=document_id,
            run_id=run_id,
            files=files,
            tool_call_id="defer-unpublished-check-001",
            selected_skill_ids=("output",),
            loaded_skill_ids=("output",),
        )
        assert checked_only.status == "checked", checked_only.issues
        assert (await runtime.raw_state(document_id))["checked_candidate"] is not None
        checked_snapshot = await runtime.reopen_document(document_id)
        direct_before_publish = checked_snapshot.approved_document.model_copy(
            update={"work_description": "員工直接修訂工作描述"}
        )
        edited_before_publish = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=checked_snapshot.revision,
            document=direct_before_publish,
            source_id=uuid4(),
        )
        assert (
            edited_before_publish.approved_document.work_description
            == "員工直接修訂工作描述"
        )
        assert (await runtime.raw_state(document_id))["checked_candidate"] is None
        with pytest.raises(CandidatePublicationStale):
            await runtime.publish_checked_candidate(
                document_id=document_id,
                run_id=run_id,
                files=files,
            )

        post_edit_catalog = WorkspaceCatalog.from_snapshot(
            edited_before_publish.approved_document,
            sources=await runtime.list_sources(document_id),
        )
        files = project_candidate_files(post_edit_catalog, run_id=run_id)
        header = json.loads(files[header_path])
        header["job_title"] = "候選採購專員"
        header["work_description"] = "候選工作描述"
        files[header_path] = json.dumps(header, ensure_ascii=False, indent=2) + "\n"
        checked, published = await _check_and_publish(
            runtime,
            document_id=document_id,
            run_id=run_id,
            files=files,
            call_id="defer-check-002",
        )
        assert {action.path for action in checked.actions} == {
            "/work_description",
            "/job_title",
        }
        assert len(checked.actions) == 2
        deferred = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=published.revision,
            action="defer_changes",
            changeset_id=checked.receipt.changeset.changeset_id,
            action_ids=tuple(action.action_id for action in checked.actions),
        )
        assert deferred.approved_document == edited_before_publish.approved_document
        deferred_bundle = DocumentChangeSet.model_validate(
            next(iter(deferred.review_queue.values()))
        )
        assert all(
            action.status is DocumentChangeStatus.DEFERRED
            for action in deferred_bundle.actions
        )

        direct_document = deferred.approved_document.model_copy(
            update={"job_title": "員工直接修訂職稱"}
        )
        edited = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=deferred.revision,
            document=direct_document,
            source_id=uuid4(),
        )
        stale_bundle = DocumentChangeSet.model_validate(
            next(iter(edited.review_queue.values()))
        )
        assert edited.approved_document.job_title == "員工直接修訂職稱"
        actions_by_path = {action.path: action for action in stale_bundle.actions}
        assert actions_by_path["/job_title"].status is DocumentChangeStatus.STALE
        assert actions_by_path["/job_title"].stale_reason
        assert actions_by_path["/work_description"].status is DocumentChangeStatus.DEFERRED
        assert actions_by_path["/work_description"].rejection_reason is None
        assert edited.approved_document.work_description == "員工直接修訂工作描述"
        assert edited.approved_document.job_title == "員工直接修訂職稱"

        pending_catalog = WorkspaceCatalog.from_snapshot(
            edited.approved_document,
            pending=(stale_bundle,),
            sources=await runtime.list_sources(document_id),
        )
        pending_binding = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            run_id=uuid4(),
            catalog=pending_catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        pending_handles = pending_action_handles((stale_bundle,))
        pending_surface = json.dumps(
            {
                path: json.loads(
                    pending_binding.pending_backend.read(path).file_data["content"]
                )
                for path in (
                    "/index.json",
                    "/reviews/review-001.json",
                    *(
                        f"/actions/{handle}.json"
                        for handle in pending_handles.values()
                    ),
                )
            },
            ensure_ascii=False,
        )
        assert re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}",
            pending_surface,
        ) is None
        accepted = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=edited.revision,
            action="accept_changes",
            changeset_id=stale_bundle.changeset_id,
            action_ids=(actions_by_path["/work_description"].action_id,),
        )
        accepted_bundle = DocumentChangeSet.model_validate(
            next(iter(accepted.review_queue.values()))
        )
        accepted_by_path = {action.path: action for action in accepted_bundle.actions}
        assert accepted_by_path["/work_description"].status is DocumentChangeStatus.ACCEPTED
        assert accepted_by_path["/job_title"].status is DocumentChangeStatus.STALE
        assert accepted.approved_document.work_description == "候選工作描述"
        assert accepted.approved_document.job_title == "員工直接修訂職稱"
        assert accepted.approved_document.job_title != "候選採購專員"


@pytest.mark.asyncio
async def test_runtime_split_candidate_requires_atomic_review_decision(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        prepared = await _prepare_runtime_run(runtime, document_id, run_id)
        baseline = prepared["snapshot"].approved_document
        old_task_id = baseline.tasks[0].task_id
        split_document = baseline.model_copy(
            update={
                "opks": tuple(
                    ApprovedOpksItem(
                        item_id=uuid4(),
                        kind=kind,
                        text=text,
                        display_order=index,
                        task_ids=(old_task_id,),
                        evidence_source_ids=(prepared["source_id"],),
                    )
                    for index, (kind, text) in enumerate(
                        (
                            (ApprovedOpksKind.OUTPUT, "完成正確訂單"),
                            (ApprovedOpksKind.PERFORMANCE_INDICATOR, "訂單錯誤率低"),
                            (ApprovedOpksKind.KNOWLEDGE, "訂單規則"),
                            (ApprovedOpksKind.SKILL, "細節核對"),
                        )
                    )
                )
            }
        )
        prepared["snapshot"] = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=prepared["snapshot"].revision,
            document=split_document,
            source_id=uuid4(),
        )
        prepared["catalog"] = WorkspaceCatalog.from_snapshot(
            prepared["snapshot"].approved_document,
            sources=await runtime.list_sources(document_id),
        )
        files = project_candidate_files(prepared["catalog"], run_id=run_id)
        old_task_path = f"/candidate/{run_id}/tasks/{prepared['task_handle']}.json"
        del files[old_task_path]
        duty_handle = prepared["catalog"].handle_for_id(
            prepared["catalog"].document.duties[0].duty_id
        )
        for handle, statement in (
            ("task-101", "核對國內訂單"),
            ("task-102", "核對國際訂單"),
        ):
            files[f"/candidate/{run_id}/tasks/{handle}.json"] = (
                json.dumps(
                    {
                        "handle": handle,
                        "duty_handle": duty_handle,
                        "statement": statement,
                        "action": "核對",
                        "object": "訂單",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
        for prefix, skill_id in (
            ("o", "output"),
            ("p", "performance-indicator"),
            ("k", "knowledge"),
            ("s", "skill"),
        ):
            opks_path = f"/candidate/{run_id}/opks/{prefix}/{prefix}-001.json"
            opks = json.loads(files[opks_path])
            opks["task_handles"] = (
                ["task-101", "task-102"] if prefix in {"k", "s"} else ["task-101"]
            )
            opks["evidence"] = [
                {
                    "source_handle": prepared["source_handle"],
                    "quote": "核對訂單",
                    "skill_ids": [skill_id],
                }
            ]
            files[opks_path] = json.dumps(
                opks, ensure_ascii=False, indent=2
            ) + "\n"
        checked, published = await _check_and_publish(
            runtime,
            document_id=document_id,
            run_id=run_id,
            files=files,
            call_id="split-check-001",
            skill_ids=(
                "output",
                "performance-indicator",
                "knowledge",
                "skill",
            ),
        )
        split_bundle = DocumentChangeSet.model_validate(
            next(iter(published.review_queue.values()))
        )
        split_catalog = WorkspaceCatalog.from_snapshot(
            published.approved_document,
            pending=(split_bundle,),
            sources=await runtime.list_sources(document_id),
        )
        split_binding = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            run_id=uuid4(),
            catalog=split_catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        split_handles = pending_action_handles((split_bundle,))
        split_pending_paths = (
            "/index.json",
            "/reviews/review-001.json",
            *(f"/actions/{handle}.json" for handle in split_handles.values()),
        )
        split_pending_payloads = []
        for path in split_pending_paths:
            read = split_binding.pending_backend.read(path)
            assert read.error is None
            assert read.file_data is not None
            split_pending_payloads.append(json.loads(read.file_data["content"]))
        split_pending_surface = "\n".join(split_pending_paths) + json.dumps(
            split_pending_payloads,
            ensure_ascii=False,
        )
        assert re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}",
            split_pending_surface,
        ) is None, split_pending_surface
        relation_items = [
            item
            for payload in split_pending_payloads
            for side in ("before", "after")
            for item in (
                payload.get(side, [])
                if isinstance(payload.get(side), list)
                else [payload.get(side)]
            )
            if isinstance(item, dict) and "duty_handle" in item
        ]
        assert relation_items
        assert all(item["duty_handle"] == duty_handle for item in relation_items)
        assert all("duty_id" not in item for item in relation_items)
        atomic_actions = [
            action for action in checked.actions if action.atomic_subgroup_id is not None
        ]
        assert len(atomic_actions) >= 2
        with pytest.raises(AtomicSubgroupIncomplete):
            await runtime.decide_document_changes(
                document_id=document_id,
                expected_revision=published.revision,
                action="accept_changes",
                changeset_id=checked.receipt.changeset.changeset_id,
                action_ids=(atomic_actions[0].action_id,),
            )
        assert (await runtime.reopen_document(document_id)).approved_document == prepared[
            "snapshot"
        ].approved_document

        relation_action = next(
            action for action in atomic_actions if action.path.endswith("/task_ids")
        )
        accepted = await runtime.decide_document_changes(
            document_id=document_id,
            expected_revision=published.revision,
            action="edit_and_accept_changes",
            changeset_id=checked.receipt.changeset.changeset_id,
            action_ids=tuple(action.action_id for action in atomic_actions),
            edited_after_by_action_id={
                relation_action.action_id: relation_action.after,
            },
        )
        accepted_bundle = DocumentChangeSet.model_validate(
            next(iter(accepted.review_queue.values()))
        )
        accepted_catalog = WorkspaceCatalog.from_snapshot(
            accepted.approved_document,
            pending=(accepted_bundle,),
            sources=await runtime.list_sources(document_id),
        )
        accepted_binding = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            run_id=uuid4(),
            catalog=accepted_catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        accepted_handles = pending_action_handles((accepted_bundle,))
        accepted_paths = (
            "/index.json",
            "/reviews/review-001.json",
            *(f"/actions/{handle}.json" for handle in accepted_handles.values()),
        )
        accepted_payloads = []
        for path in accepted_paths:
            read = accepted_binding.pending_backend.read(path)
            assert read.error is None
            assert read.file_data is not None
            accepted_payloads.append(json.loads(read.file_data["content"]))
        accepted_surface = "\n".join(accepted_paths) + json.dumps(
            accepted_payloads,
            ensure_ascii=False,
        )
        assert re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}",
            accepted_surface,
        ) is None
        relation_handle = accepted_handles[relation_action.action_id]
        relation_view = json.loads(
            accepted_binding.pending_backend.read(
                f"/actions/{relation_handle}.json"
            ).file_data["content"]
        )
        assert relation_view["approved"] is False
        assert relation_view["status"] == "edit_accepted"
        assert relation_view["employee_after"] == [
            accepted_catalog.handle_for_id(UUID(str(raw_id)))
            for raw_id in relation_action.after
        ]


@pytest.mark.asyncio
async def test_new_candidate_run_cannot_read_previous_run_scratch(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    first_run_id = uuid4()
    second_run_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        prepared = await _prepare_runtime_run(runtime, document_id, first_run_id)
        first = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            run_id=first_run_id,
            catalog=prepared["catalog"],
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        scratch_path = f"/candidate/{first_run_id}/opks/o/scratch-001.json"
        assert first.candidate_backend.validate_candidate_file_path(scratch_path) == scratch_path
        first_probe = _FilesystemToolProbe(first)
        written = await first_probe.invoke(
            "write_file",
            file_path=scratch_path,
            content='{"text":"first-run-only"}\n',
        )
        assert written.status == "success"
        first_read = await first_probe.invoke("read_file", file_path=scratch_path)
        assert first_read.status == "success"
        assert "first-run-only" in str(first_read.content)

        second = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            run_id=second_run_id,
            catalog=prepared["catalog"],
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        second_probe = _FilesystemToolProbe(second)
        second_read = await second_probe.invoke("read_file", file_path=scratch_path)
        assert second_read.status == "error"
        assert "outside the current candidate run" in str(second_read.content)
        second_ls = await second_probe.invoke(
            "ls",
            path=f"/candidate/{first_run_id}/",
        )
        assert second_ls.status == "error"
        assert "outside the current candidate run" in str(second_ls.content)
        second_glob = await second_probe.invoke(
            "glob",
            pattern="**/scratch-001.json",
            path=f"/candidate/{first_run_id}/",
        )
        assert second_glob.status == "error"
        assert "outside the current candidate run" in str(second_glob.content)
        assert all(
            str(first_run_id) not in path for path in second.initial_candidate_files
        )


@pytest.mark.asyncio
async def test_failed_postgres_run_restarts_and_exact_admission_replays(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        admitted, should_process = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責核對訂單並回報結果。",
        )
        assert should_process is True
        failed = await runtime.mark_consultant_run_failed(
            document_id=document_id,
            run_id=run_id,
            error_code="model_timeout",
        )
        assert failed.latest_run is not None
        assert failed.latest_run["status"] == RunStatus.FAILED.value
        restarted, should_restart = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責核對訂單並回報結果。",
        )
        assert should_restart is True
        assert restarted.latest_run is not None
        assert restarted.latest_run["status"] == RunStatus.SOURCE_SAVED.value
        replay, should_replay = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            text="我負責核對訂單並回報結果。",
        )
        assert should_replay is False
        assert replay.revision == restarted.revision
