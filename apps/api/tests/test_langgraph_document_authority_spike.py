from __future__ import annotations

import asyncio
import os
from typing import Annotated, Any, TypedDict
from uuid import uuid4

import pytest
import pytest_asyncio
import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.channels import DeltaChannel
from langgraph.graph import END, START, StateGraph
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Command

import langgraph_document_authority_spike as spike
from langgraph_document_authority_spike import (
    SimulatedAnalysisCrash,
    build_document_graph,
    submit_source,
)


SPIKE_DATABASE_URL = os.environ.get(
    "LANGGRAPH_SPIKE_DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/caliburn_langgraph_spike?sslmode=disable",
)


def _merge_delta_source_batches(
    current: list[dict[str, str]], batches: list[list[dict[str, str]]]
) -> list[dict[str, str]]:
    merged = list(current)
    by_id = {event["input_event_id"]: event for event in merged}
    for batch in batches:
        for event in batch:
            existing = by_id.get(event["input_event_id"])
            if existing is None:
                merged.append(event)
                by_id[event["input_event_id"]] = event
            elif existing != event:
                raise ValueError(f"conflicting source event: {event['input_event_id']}")
    return merged


class DeltaSourceState(TypedDict, total=False):
    document_id: str
    payload: dict[str, Any]
    source_events: Annotated[
        list[dict[str, str]],
        DeltaChannel(_merge_delta_source_batches, snapshot_frequency=1000),
    ]


def _build_delta_source_graph(checkpointer):
    def accept_source(state: DeltaSourceState) -> DeltaSourceState:
        return {
            "source_events": [
                {
                    "input_event_id": state["payload"]["input_event_id"],
                    "speaker": "employee",
                    "text": state["payload"]["text"],
                }
            ]
        }

    builder = StateGraph(DeltaSourceState)
    builder.add_node("accept_source", accept_source)
    builder.add_edge(START, "accept_source")
    builder.add_edge("accept_source", END)
    return builder.compile(checkpointer=checkpointer)


@pytest_asyncio.fixture
async def postgres_saver():
    async with AsyncPostgresSaver.from_conn_string(SPIKE_DATABASE_URL) as saver:
        await saver.setup()
        yield saver


@pytest_asyncio.fixture
async def postgres_store():
    async with AsyncPostgresStore.from_conn_string(SPIKE_DATABASE_URL) as store:
        await store.setup()
        try:
            yield store
        finally:
            # AsyncBatchedBaseStore 1.2.9 has no public close API. The Store is
            # application-lifetime in production; this private cancellation only
            # keeps the disposable pytest event loop from reporting a pending task.
            task = store._task
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_source_checkpoint_survives_analysis_crash(postgres_saver) -> None:
    """Catches a graph that calls analysis before durably accepting employee input."""
    thread_id = f"source-first-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_document_graph(postgres_saver)

    with pytest.raises(SimulatedAnalysisCrash):
        await graph.ainvoke(
            submit_source(
                document_id="jd-1",
                input_event_id="answer-1",
                text="我每天先檢查缺料，再安排採購。",
                fail_after_source=True,
            ),
            config,
        )

    snapshot = await graph.aget_state(config)

    assert snapshot.values["source_events"] == [
        {
            "input_event_id": "answer-1",
            "speaker": "employee",
            "text": "我每天先檢查缺料，再安排採購。",
        }
    ]
    assert snapshot.values["processing_status"] == "source_saved"
    assert snapshot.values.get("work_model", {}) == {}
    assert snapshot.values.get("pending_proposals", {}) == {}

    await postgres_saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_source_reducer_appends_new_ids_and_deduplicates_replay(
    postgres_saver,
) -> None:
    """Catches overwrite loss and duplicate Source rows during retry or replay."""
    thread_id = f"source-idempotency-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_document_graph(postgres_saver)

    await graph.ainvoke(
        submit_source(
            document_id="jd-1",
            input_event_id="answer-1",
            text="我每天先檢查缺料。",
        ),
        config,
    )
    await graph.ainvoke(
        submit_source(
            document_id="jd-1",
            input_event_id="answer-2",
            text="接著依交期安排採購。",
        ),
        config,
    )
    await graph.ainvoke(
        submit_source(
            document_id="jd-1",
            input_event_id="answer-1",
            text="我每天先檢查缺料。",
        ),
        config,
    )

    snapshot = await graph.aget_state(config)
    assert [event["input_event_id"] for event in snapshot.values["source_events"]] == [
        "answer-1",
        "answer-2",
    ]

    await postgres_saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_store_owned_source_survives_crash_and_replay_is_idempotent(
    postgres_saver,
    postgres_store,
) -> None:
    """The framework Store is Source truth; State keeps no duplicate quote journal."""
    crash_thread = f"store-source-crash-{uuid4()}"
    replay_thread = f"store-source-replay-{uuid4()}"
    crash_document = f"jd-crash-{uuid4()}"
    replay_document = f"jd-replay-{uuid4()}"
    crash_config = {"configurable": {"thread_id": crash_thread}}
    replay_config = {"configurable": {"thread_id": replay_thread}}
    graph = spike.build_store_backed_document_graph(postgres_saver, postgres_store)

    try:
        with pytest.raises(SimulatedAnalysisCrash):
            await graph.ainvoke(
                submit_source(
                    document_id=crash_document,
                    input_event_id="answer-crash",
                    text="分析失敗也不能遺失這句員工原話。",
                    fail_after_source=True,
                ),
                crash_config,
            )

        stored_after_crash = await postgres_store.aget(
            ("job-analysis", crash_document, "sources"), "answer-crash"
        )
        assert stored_after_crash is not None
        assert stored_after_crash.value == {
            "document_id": crash_document,
            "input_event_id": "answer-crash",
            "speaker": "employee",
            "text": "分析失敗也不能遺失這句員工原話。",
            "processing_status": "pending",
        }
        crash_state = await graph.aget_state(crash_config)
        assert crash_state.values["last_source_id"] == "answer-crash"
        assert crash_state.values["processing_status"] == "source_saved"
        assert "source_events" not in crash_state.values

        await graph.ainvoke(
            submit_source(
                document_id=replay_document,
                input_event_id="answer-1",
                text="我每天先確認庫存，再安排採購。",
                analysis_result={"visible_turn": {"text": "已記下。"}},
            ),
            replay_config,
        )
        before_replay = await graph.aget_state(replay_config)

        await graph.ainvoke(
            submit_source(
                document_id=replay_document,
                input_event_id="answer-1",
                text="我每天先確認庫存，再安排採購。",
                analysis_result={"visible_turn": {"text": "不應重跑。"}},
            ),
            replay_config,
        )
        after_replay = await graph.aget_state(replay_config)
        assert after_replay.values["revision"] == before_replay.values["revision"]
        assert after_replay.values["visible_turn"] == {"text": "已記下。"}

        with pytest.raises(spike.SourceConflict):
            await graph.ainvoke(
                submit_source(
                    document_id=replay_document,
                    input_event_id="answer-1",
                    text="同一 ID 不得偷偷換成另一句話。",
                ),
                replay_config,
            )

        stored_after_conflict = await postgres_store.aget(
            ("job-analysis", replay_document, "sources"), "answer-1"
        )
        assert stored_after_conflict is not None
        assert stored_after_conflict.value["text"] == "我每天先確認庫存，再安排採購。"
        assert stored_after_conflict.value["processing_status"] == "complete"
        assert "source_events" not in after_replay.values
    finally:
        await postgres_saver.adelete_thread(crash_thread)
        await postgres_saver.adelete_thread(replay_thread)
        await postgres_store.adelete(
            ("job-analysis", crash_document, "sources"), "answer-crash"
        )
        await postgres_store.adelete(
            ("job-analysis", replay_document, "sources"), "answer-1"
        )


@pytest.mark.asyncio
async def test_store_pending_source_recovers_both_checkpoint_windows(
    postgres_saver,
    postgres_store,
) -> None:
    """A pending Store record is the durable inbox for either crash window."""
    accept_thread = f"store-accept-window-{uuid4()}"
    complete_thread = f"store-complete-window-{uuid4()}"
    accept_document = f"jd-accept-window-{uuid4()}"
    complete_document = f"jd-complete-window-{uuid4()}"
    accept_config = {"configurable": {"thread_id": accept_thread}}
    complete_config = {"configurable": {"thread_id": complete_thread}}
    graph = spike.build_store_backed_document_graph(postgres_saver, postgres_store)

    async def pending_keys(document_id: str) -> list[str]:
        items = await postgres_store.asearch(
            ("job-analysis", document_id, "sources"),
            filter={"processing_status": "pending"},
            limit=10,
        )
        return [item.key for item in items]

    try:
        with pytest.raises(spike.SimulatedAcceptanceCrash):
            await graph.ainvoke(
                submit_source(
                    document_id=accept_document,
                    input_event_id="answer-accept-window",
                    text="Store 寫入後、checkpoint 前中斷。",
                    fail_before_source_checkpoint=True,
                ),
                accept_config,
            )
        accept_state = await graph.aget_state(accept_config)
        assert "last_source_id" not in accept_state.values
        assert await pending_keys(accept_document) == ["answer-accept-window"]

        await graph.ainvoke(
            submit_source(
                document_id=accept_document,
                input_event_id="answer-accept-window",
                text="Store 寫入後、checkpoint 前中斷。",
                analysis_result={"visible_turn": {"text": "已從 pending Source 復原。"}},
            ),
            accept_config,
        )
        recovered_accept = await graph.aget_state(accept_config)
        assert recovered_accept.values["processing_status"] == "complete"
        assert recovered_accept.values["visible_turn"] == {
            "text": "已從 pending Source 復原。"
        }
        assert await pending_keys(accept_document) == []

        with pytest.raises(spike.SimulatedCompletionCrash):
            await graph.ainvoke(
                submit_source(
                    document_id=complete_document,
                    input_event_id="answer-complete-window",
                    text="分析 checkpoint 後、完成標記前中斷。",
                    fail_before_mark_complete=True,
                    analysis_result={"visible_turn": {"text": "分析只准執行一次。"}},
                ),
                complete_config,
            )
        before_completion_recovery = await graph.aget_state(complete_config)
        assert before_completion_recovery.values["processing_status"] == "analysis_complete"
        assert await pending_keys(complete_document) == ["answer-complete-window"]

        await graph.ainvoke(
            submit_source(
                document_id=complete_document,
                input_event_id="answer-complete-window",
                text="分析 checkpoint 後、完成標記前中斷。",
                analysis_result={"visible_turn": {"text": "若看到代表錯誤重跑。"}},
            ),
            complete_config,
        )
        after_completion_recovery = await graph.aget_state(complete_config)
        assert after_completion_recovery.values["processing_status"] == "complete"
        assert after_completion_recovery.values["visible_turn"] == {
            "text": "分析只准執行一次。"
        }
        assert (
            after_completion_recovery.values["revision"]
            == before_completion_recovery.values["revision"]
        )
        assert await pending_keys(complete_document) == []
    finally:
        await postgres_saver.adelete_thread(accept_thread)
        await postgres_saver.adelete_thread(complete_thread)
        await postgres_store.adelete(
            ("job-analysis", accept_document, "sources"), "answer-accept-window"
        )
        await postgres_store.adelete(
            ("job-analysis", complete_document, "sources"),
            "answer-complete-window",
        )


@pytest.mark.asyncio
async def test_store_backed_document_delete_is_complete_and_idempotent(
    postgres_saver,
    postgres_store,
) -> None:
    thread_id = f"store-delete-{uuid4()}"
    document_id = f"jd-store-delete-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    namespace = ("job-analysis", document_id, "sources")
    graph = spike.build_store_backed_document_graph(postgres_saver, postgres_store)

    for turn in range(2):
        await graph.ainvoke(
            submit_source(
                document_id=document_id,
                input_event_id=f"answer-{turn}",
                text=f"第 {turn + 1} 則員工原話。",
            ),
            config,
        )
    assert len(await postgres_store.asearch(namespace, limit=10)) == 2
    assert (await graph.aget_state(config)).values["revision"] == 4

    await spike.delete_store_backed_document(
        checkpointer=postgres_saver,
        store=postgres_store,
        thread_id=thread_id,
        document_id=document_id,
    )
    assert await postgres_store.asearch(namespace, limit=10) == []
    assert (await graph.aget_state(config)).values == {}

    await spike.delete_store_backed_document(
        checkpointer=postgres_saver,
        store=postgres_store,
        thread_id=thread_id,
        document_id=document_id,
    )


@pytest.mark.asyncio
async def test_semantic_changes_commit_in_one_checkpoint_without_touching_current_jd(
    postgres_saver,
) -> None:
    """Catches partial semantic writes or an AI path that mutates Current JD."""
    thread_id = f"semantic-atomicity-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_document_graph(postgres_saver)
    analysis_result = {
        "work_model": {
            "tasks": {
                "task-1": {
                    "statement": "檢查缺料並安排採購",
                    "source_ids": ["answer-1"],
                }
            }
        },
        "focus_plan": {"focus_id": "task-1", "mode": "task_deepening"},
        "progress_and_gaps": {
            "covered": ["task-1"],
            "gaps": ["task-1:opks"],
        },
        "pending_proposals": {
            "proposal-1": {
                "status": "pending",
                "source_ids": ["answer-1"],
                "after": {"tasks": [{"task_id": "task-1"}]},
            }
        },
        "visible_turn": {"text": "我先記下這項任務，接著釐清執行結果。"},
    }

    await graph.ainvoke(
        submit_source(
            document_id="jd-1",
            input_event_id="answer-1",
            text="我每天先檢查缺料，再安排採購。",
            analysis_result=analysis_result,
        ),
        config,
    )

    snapshot = await graph.aget_state(config)
    for key, expected in analysis_result.items():
        assert snapshot.values[key] == expected
    assert snapshot.values["current_jd"] == {}
    assert snapshot.values["processing_status"] == "complete"

    semantic_keys = set(analysis_result)
    history = []
    async for historical in graph.aget_state_history(config):
        history.append(historical)

    before_analysis = next(item for item in history if item.next == ("analyze",))
    after_analysis = next(
        item
        for item in history
        if item.metadata["step"] == before_analysis.metadata["step"] + 1
    )
    assert semantic_keys.isdisjoint(before_analysis.values)
    assert semantic_keys <= set(after_analysis.values)
    assert before_analysis.values["current_jd"] == after_analysis.values["current_jd"]

    await postgres_saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_proposal_review_survives_graph_and_connection_restart() -> None:
    """Catches an approval that exists only in process memory or bypasses authority."""
    thread_id = f"proposal-restart-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    proposal = {
        "status": "pending",
        "source_ids": ["answer-1"],
        "after": {
            "tasks": [
                {
                    "task_id": "task-1",
                    "statement": "檢查缺料並安排採購",
                }
            ]
        },
    }

    async with AsyncPostgresSaver.from_conn_string(SPIKE_DATABASE_URL) as saver:
        await saver.setup()
        graph_before_restart = build_document_graph(saver)
        await graph_before_restart.ainvoke(
            submit_source(
                document_id="jd-1",
                input_event_id="answer-1",
                text="我每天先檢查缺料，再安排採購。",
                analysis_result={"pending_proposals": {"proposal-1": proposal}},
            ),
            config,
        )

        paused = await graph_before_restart.ainvoke(
            {
                "action": "review_proposal",
                "document_id": "jd-1",
                "payload": {"proposal_id": "proposal-1"},
            },
            config,
        )
        assert paused["__interrupt__"][0].value == {
            "kind": "proposal_review",
            "proposal_id": "proposal-1",
            "proposal": proposal,
            "allowed_decisions": ["approve", "edit", "reject", "defer"],
        }

    async with AsyncPostgresSaver.from_conn_string(SPIKE_DATABASE_URL) as saver:
        graph_after_restart = build_document_graph(saver)
        paused_snapshot = await graph_after_restart.aget_state(config)
        assert paused_snapshot.next == ("review_proposal",)
        assert paused_snapshot.values["current_jd"] == {}

        await graph_after_restart.ainvoke(
            Command(resume={"decision": "approve"}),
            config,
        )
        accepted = await graph_after_restart.aget_state(config)

        assert accepted.values["current_jd"] == proposal["after"]
        assert accepted.values["pending_proposals"]["proposal-1"]["status"] == "accepted"
        assert accepted.next == ()

        await saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_direct_edit_query_export_stale_check_and_delete(postgres_saver) -> None:
    """Catches a checkpoint-only design that still needs a second writable JD store."""
    thread_id = f"direct-edit-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_document_graph(postgres_saver)
    await graph.ainvoke(
        submit_source(
            document_id="jd-1",
            input_event_id="answer-1",
            text="我每天先檢查缺料，再安排採購。",
        ),
        config,
    )
    before_edit = await graph.aget_state(config)
    expected_revision = before_edit.values["revision"]
    edited_jd = {
        "duties": [{"duty_id": "duty-1", "title": "物料供應管理"}],
        "tasks": [
            {
                "task_id": "task-1",
                "duty_id": "duty-1",
                "statement": "檢查缺料並安排採購",
            }
        ],
    }

    await graph.ainvoke(
        spike.direct_edit(
            document_id="jd-1",
            expected_revision=expected_revision,
            current_jd=edited_jd,
        ),
        config,
    )

    queried = await graph.aget_state(config)
    assert queried.values["current_jd"] == edited_jd
    assert queried.values["revision"] == expected_revision + 1
    assert spike.export_current_jd(queried.values) == edited_jd

    with pytest.raises(spike.StaleRevision):
        await graph.ainvoke(
            spike.direct_edit(
                document_id="jd-1",
                expected_revision=expected_revision,
                current_jd={"duties": [], "tasks": []},
            ),
            config,
        )

    after_stale = await graph.aget_state(config)
    assert after_stale.values["current_jd"] == edited_jd

    await postgres_saver.adelete_thread(thread_id)
    deleted = await graph.aget_state(config)
    assert deleted.values == {}


@pytest.mark.asyncio
async def test_deferred_proposal_stays_durable_without_changing_current_jd(
    postgres_saver,
) -> None:
    """Catches a pause model where defer either loses the proposal or applies it."""
    thread_id = f"proposal-defer-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_document_graph(postgres_saver)
    proposal = {
        "status": "pending",
        "source_ids": ["answer-1"],
        "after": {"tasks": [{"task_id": "task-1"}]},
    }
    await graph.ainvoke(
        submit_source(
            document_id="jd-1",
            input_event_id="answer-1",
            text="我每天先檢查缺料。",
            analysis_result={"pending_proposals": {"proposal-1": proposal}},
        ),
        config,
    )
    await graph.ainvoke(
        {
            "action": "review_proposal",
            "document_id": "jd-1",
            "payload": {"proposal_id": "proposal-1"},
        },
        config,
    )

    await graph.ainvoke(Command(resume={"decision": "defer"}), config)
    deferred = await graph.aget_state(config)

    assert deferred.values["pending_proposals"]["proposal-1"]["status"] == "deferred"
    assert deferred.values["current_jd"] == {}
    assert deferred.next == ()

    await postgres_saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_document_runtime_serializes_same_thread_stale_writers(
    postgres_saver,
) -> None:
    """Catches lost updates when two requests write one document concurrently."""
    thread_id = f"same-thread-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    runtime = spike.DocumentRuntime(build_document_graph(postgres_saver))
    await runtime.ainvoke(
        submit_source(
            document_id="jd-1",
            input_event_id="answer-1",
            text="我每天先檢查缺料。",
        ),
        config,
    )
    before = await runtime.aget_state(config)
    revision = before.values["revision"]

    outcomes = await asyncio.gather(
        runtime.ainvoke(
            spike.direct_edit(
                document_id="jd-1",
                expected_revision=revision,
                current_jd={"tasks": [{"task_id": "task-a"}]},
            ),
            config,
        ),
        runtime.ainvoke(
            spike.direct_edit(
                document_id="jd-1",
                expected_revision=revision,
                current_jd={"tasks": [{"task_id": "task-b"}]},
            ),
            config,
        ),
        return_exceptions=True,
    )

    assert sum(outcome is not None and not isinstance(outcome, Exception) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, spike.StaleRevision) for outcome in outcomes) == 1
    after = await runtime.aget_state(config)
    assert after.values["revision"] == revision + 1
    assert after.values["current_jd"] in (
        {"tasks": [{"task_id": "task-a"}]},
        {"tasks": [{"task_id": "task-b"}]},
    )

    await postgres_saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_completed_checkpoint_allows_additive_state_and_graph_evolution(
    postgres_saver,
) -> None:
    """Catches a persisted state format that cannot be opened by additive graph code."""

    class StateV1(TypedDict, total=False):
        document_id: str
        source_events: list[dict[str, str]]

    class StateV2(StateV1, total=False):
        schema_version: int
        focus_plan: dict[str, str]

    thread_id = f"schema-evolution-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    v1_builder = StateGraph(StateV1)
    v1_builder.add_node("persist", lambda state: state)
    v1_builder.add_edge(START, "persist")
    v1_builder.add_edge("persist", END)
    v1_graph = v1_builder.compile(checkpointer=postgres_saver)
    await v1_graph.ainvoke(
        {
            "document_id": "jd-1",
            "source_events": [
                {
                    "input_event_id": "answer-1",
                    "speaker": "employee",
                    "text": "我每天先檢查缺料。",
                }
            ],
        },
        config,
    )

    v2_builder = StateGraph(StateV2)
    v2_builder.add_node(
        "upgrade",
        lambda _state: {
            "schema_version": 2,
            "focus_plan": {"focus_id": "task-1"},
        },
    )
    v2_builder.add_edge(START, "upgrade")
    v2_builder.add_edge("upgrade", END)
    v2_graph = v2_builder.compile(checkpointer=postgres_saver)

    reopened = await v2_graph.aget_state(config)
    assert reopened.values["source_events"][0]["input_event_id"] == "answer-1"
    assert "schema_version" not in reopened.values

    await v2_graph.ainvoke({"document_id": "jd-1"}, config)
    upgraded = await v2_graph.aget_state(config)
    assert upgraded.values["schema_version"] == 2
    assert upgraded.values["focus_plan"] == {"focus_id": "task-1"}
    assert upgraded.values["source_events"][0]["text"] == "我每天先檢查缺料。"

    await postgres_saver.adelete_thread(thread_id)


async def _checkpoint_storage_bytes(thread_id: str) -> int:
    async with await psycopg.AsyncConnection.connect(SPIKE_DATABASE_URL) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT
                    COALESCE((
                        SELECT SUM(pg_column_size(checkpoint) + pg_column_size(metadata))
                        FROM checkpoints
                        WHERE thread_id = %s
                    ), 0)
                    + COALESCE((
                        SELECT SUM(octet_length(blob))
                        FROM checkpoint_blobs
                        WHERE thread_id = %s
                    ), 0)
                    + COALESCE((
                        SELECT SUM(octet_length(blob))
                        FROM checkpoint_writes
                        WHERE thread_id = %s
                    ), 0)
                """,
                (thread_id, thread_id, thread_id),
            )
            row = await cursor.fetchone()
            assert row is not None
            return int(row[0])


async def _checkpoint_storage_breakdown(thread_id: str) -> list[tuple[str, int, int]]:
    async with await psycopg.AsyncConnection.connect(SPIKE_DATABASE_URL) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT bucket, row_count, stored_bytes
                FROM (
                    SELECT
                        'checkpoints' AS bucket,
                        COUNT(*)::bigint AS row_count,
                        COALESCE(SUM(pg_column_size(checkpoint) + pg_column_size(metadata)), 0)::bigint AS stored_bytes
                    FROM checkpoints
                    WHERE thread_id = %s
                    UNION ALL
                    SELECT
                        'blob:' || channel AS bucket,
                        COUNT(*)::bigint AS row_count,
                        COALESCE(SUM(octet_length(blob)), 0)::bigint AS stored_bytes
                    FROM checkpoint_blobs
                    WHERE thread_id = %s
                    GROUP BY channel
                    UNION ALL
                    SELECT
                        'write:' || channel AS bucket,
                        COUNT(*)::bigint AS row_count,
                        COALESCE(SUM(octet_length(blob)), 0)::bigint AS stored_bytes
                    FROM checkpoint_writes
                    WHERE thread_id = %s
                    GROUP BY channel
                ) AS sizes
                ORDER BY stored_bytes DESC, bucket
                """,
                (thread_id, thread_id, thread_id),
            )
            rows = await cursor.fetchall()
            return [(str(row[0]), int(row[1]), int(row[2])) for row in rows]


async def _store_storage_bytes(document_id: str) -> int:
    prefix = f"job-analysis.{document_id}.sources"
    async with await psycopg.AsyncConnection.connect(SPIKE_DATABASE_URL) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT COALESCE(
                    SUM(
                        octet_length(prefix)
                        + octet_length(key)
                        + pg_column_size(value)
                    ),
                    0
                )
                FROM store
                WHERE prefix = %s
                """,
                (prefix,),
            )
            row = await cursor.fetchone()
            assert row is not None
            return int(row[0])


@pytest.mark.asyncio
async def test_accumulating_source_channel_is_rejected_for_quadratic_growth(
    postgres_saver,
) -> None:
    """Characterizes why a full immutable Source journal must not live in State."""
    short_thread = f"growth-25-{uuid4()}"
    long_thread = f"growth-50-{uuid4()}"
    graph = build_document_graph(postgres_saver)

    async def populate(thread_id: str, turns: int) -> None:
        config = {"configurable": {"thread_id": thread_id}}
        for turn in range(turns):
            await graph.ainvoke(
                submit_source(
                    document_id="jd-1",
                    input_event_id=f"answer-{turn:03d}",
                    text=f"{turn:03d}:" + ("這是一段員工工作細節與執行情境。" * 50),
                ),
                config,
            )

    try:
        await populate(short_thread, 25)
        await populate(long_thread, 50)
        short_bytes = await _checkpoint_storage_bytes(short_thread)
        long_bytes = await _checkpoint_storage_bytes(long_thread)
        growth_ratio = long_bytes / short_bytes
        print(
            "CHECKPOINT_GROWTH",
            {
                "turns_25_bytes": short_bytes,
                "turns_50_bytes": long_bytes,
                "ratio": round(growth_ratio, 3),
            },
        )
        print("CHECKPOINT_BREAKDOWN_25", await _checkpoint_storage_breakdown(short_thread))
        print("CHECKPOINT_BREAKDOWN_50", await _checkpoint_storage_breakdown(long_thread))
        assert growth_ratio > 3.0
    finally:
        await postgres_saver.adelete_thread(short_thread)
        await postgres_saver.adelete_thread(long_thread)


@pytest.mark.asyncio
async def test_store_owned_sources_have_linear_storage_growth(
    postgres_saver,
    postgres_store,
) -> None:
    """Full quotes live once in Store while graph checkpoints retain compact state."""
    short_thread = f"store-growth-25-{uuid4()}"
    long_thread = f"store-growth-50-{uuid4()}"
    short_document = f"jd-store-growth-25-{uuid4()}"
    long_document = f"jd-store-growth-50-{uuid4()}"
    graph = spike.build_store_backed_document_graph(postgres_saver, postgres_store)

    async def populate(thread_id: str, document_id: str, turns: int) -> None:
        config = {"configurable": {"thread_id": thread_id}}
        for turn in range(turns):
            await graph.ainvoke(
                submit_source(
                    document_id=document_id,
                    input_event_id=f"answer-{turn:03d}",
                    text=f"{turn:03d}:" + ("這是一段員工工作細節與執行情境。" * 50),
                ),
                config,
            )

    async def delete_sources(document_id: str) -> None:
        namespace = ("job-analysis", document_id, "sources")
        for item in await postgres_store.asearch(namespace, limit=100):
            await postgres_store.adelete(namespace, item.key)

    try:
        await populate(short_thread, short_document, 25)
        await populate(long_thread, long_document, 50)
        short_bytes = await _checkpoint_storage_bytes(short_thread) + await _store_storage_bytes(
            short_document
        )
        long_bytes = await _checkpoint_storage_bytes(long_thread) + await _store_storage_bytes(
            long_document
        )
        growth_ratio = long_bytes / short_bytes
        print(
            "STORE_BACKED_GROWTH",
            {
                "turns_25_bytes": short_bytes,
                "turns_50_bytes": long_bytes,
                "ratio": round(growth_ratio, 3),
            },
        )
        assert growth_ratio < 2.5
    finally:
        await postgres_saver.adelete_thread(short_thread)
        await postgres_saver.adelete_thread(long_thread)
        await delete_sources(short_document)
        await delete_sources(long_document)


@pytest.mark.asyncio
async def test_beta_delta_channel_has_linear_growth_but_keeps_full_journal_in_state(
    postgres_saver,
) -> None:
    """Measures the official beta alternative without making it the Source owner."""
    short_thread = f"delta-growth-25-{uuid4()}"
    long_thread = f"delta-growth-50-{uuid4()}"
    graph = _build_delta_source_graph(postgres_saver)

    async def populate(thread_id: str, turns: int) -> None:
        config = {"configurable": {"thread_id": thread_id}}
        for turn in range(turns):
            await graph.ainvoke(
                {
                    "document_id": "jd-1",
                    "payload": {
                        "input_event_id": f"answer-{turn:03d}",
                        "text": f"{turn:03d}:"
                        + ("這是一段員工工作細節與執行情境。" * 50),
                    },
                },
                config,
            )

    try:
        await populate(short_thread, 25)
        await populate(long_thread, 50)
        short_bytes = await _checkpoint_storage_bytes(short_thread)
        long_bytes = await _checkpoint_storage_bytes(long_thread)
        growth_ratio = long_bytes / short_bytes
        reopened = await graph.aget_state(
            {"configurable": {"thread_id": long_thread}}
        )
        print(
            "DELTA_CHANNEL_GROWTH",
            {
                "turns_25_bytes": short_bytes,
                "turns_50_bytes": long_bytes,
                "ratio": round(growth_ratio, 3),
            },
        )
        assert growth_ratio < 2.5
        assert len(reopened.values["source_events"]) == 50
        assert reopened.values["source_events"][0]["input_event_id"] == "answer-000"
        assert reopened.values["source_events"][-1]["input_event_id"] == "answer-049"
    finally:
        await postgres_saver.adelete_thread(short_thread)
        await postgres_saver.adelete_thread(long_thread)
