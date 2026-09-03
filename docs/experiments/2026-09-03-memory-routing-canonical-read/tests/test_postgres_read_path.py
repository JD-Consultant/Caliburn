from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.store.memory import InMemoryStore
from pydantic import ValidationError

from memory_read_spike.canonical import (
    ReferenceUnavailableError,
    StableMessageIdConflictError,
    append_canonical_round,
    latest_canonical_messages,
    read_canonical_context,
)
from memory_read_spike.embeddings import DeterministicEmbeddingSpy
from memory_read_spike.fixtures import (
    load_canonical_rounds,
    semantic_memory_fixtures,
)
from memory_read_spike.runtime import (
    SemanticIndexUnavailableError,
    open_spike_runtime,
    search_current_memories,
    seed_current_memories,
)
from memory_read_spike.scope import TrustedReadScope, issue_message_ref
from memory_read_spike.settings import DatabaseIdentityError, SpikeSettings


EXPECTED_DATABASE = "caliburn_memory_routing_spike"
DEFAULT_SPIKE_URL = (
    "postgresql://postgres:password@127.0.0.1:5432/"
    f"{EXPECTED_DATABASE}"
)


def _settings() -> SpikeSettings:
    database_url = os.environ.get("MEMORY_ROUTING_SPIKE_DATABASE_URL")
    expected_database = os.environ.get("MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE")
    if not database_url or not expected_database:
        pytest.fail(
            "set MEMORY_ROUTING_SPIKE_DATABASE_URL and "
            "MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE"
        )
    return SpikeSettings(
        database_url=database_url,
        expected_database=expected_database,
        production_database_url=os.environ.get("DATABASE_URL"),
    )


def _scope(*, run_id: UUID | None = None, thread_id: str | None = None) -> TrustedReadScope:
    return TrustedReadScope(
        run_id=run_id or uuid4(),
        document_id=uuid4(),
        thread_id=thread_id or f"memory-routing-spike-{uuid4()}",
    )


@pytest.mark.parametrize(
    ("database_url", "expected_database", "production_database_url"),
    [
        (
            f"postgresql://postgres:password@db.internal:5432/{EXPECTED_DATABASE}",
            EXPECTED_DATABASE,
            None,
        ),
        (DEFAULT_SPIKE_URL, "some_other_database", None),
        (
            "postgresql://postgres:password@127.0.0.1:5432/caliburn_experiment",
            "caliburn_experiment",
            None,
        ),
        (DEFAULT_SPIKE_URL, EXPECTED_DATABASE, DEFAULT_SPIKE_URL),
    ],
)
def test_settings_reject_unsafe_database_identity(
    database_url: str,
    expected_database: str,
    production_database_url: str | None,
) -> None:
    with pytest.raises(ValidationError):
        SpikeSettings(
            database_url=database_url,
            expected_database=expected_database,
            production_database_url=production_database_url,
        )


def test_settings_never_falls_back_to_application_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MEMORY_ROUTING_SPIKE_DATABASE_URL", raising=False)
    monkeypatch.delenv("MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE", raising=False)
    monkeypatch.setenv("DATABASE_URL", DEFAULT_SPIKE_URL)

    with pytest.raises(ValidationError):
        SpikeSettings.from_environment()


@pytest.mark.asyncio
async def test_framework_setup_is_not_reached_before_database_identity_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import memory_read_spike.runtime as runtime_module

    setup_reached = False

    async def mismatched_identity(_connection_string: str) -> str:
        return "wrong_database"

    class SetupMustNotRun:
        @classmethod
        def from_conn_string(cls, *_args, **_kwargs):
            nonlocal setup_reached
            setup_reached = True
            raise AssertionError("framework setup opened before identity validation")

    monkeypatch.setattr(runtime_module, "_read_current_database", mismatched_identity)
    monkeypatch.setattr(runtime_module, "AsyncPostgresSaver", SetupMustNotRun)
    monkeypatch.setattr(runtime_module, "AsyncPostgresStore", SetupMustNotRun)

    settings = SpikeSettings(
        database_url=DEFAULT_SPIKE_URL,
        expected_database=EXPECTED_DATABASE,
    )
    with pytest.raises(DatabaseIdentityError) as exc_info:
        async with open_spike_runtime(
            settings,
            embed=DeterministicEmbeddingSpy(),
        ):
            pass

    assert exc_info.value.public_message == "disposable database identity mismatch"
    assert setup_reached is False


@pytest.mark.asyncio
async def test_canonical_conversation_survives_runtime_restart() -> None:
    settings = _settings()
    scope = _scope()
    rounds = load_canonical_rounds()

    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as runtime:
        for human, assistant in rounds:
            await append_canonical_round(runtime, scope, human, assistant)
        before_restart = await latest_canonical_messages(runtime, scope)

    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as restarted:
        after_restart = await latest_canonical_messages(restarted, scope)
        restored_context = await read_canonical_context(
            restarted,
            scope,
            issue_message_ref(scope, "h-021"),
        )

    assert len(before_restart) == 80
    assert [message.id for message in before_restart] == [
        message.id for pair in rounds for message in pair
    ]
    assert [type(message) for message in after_restart] == [
        type(message) for message in before_restart
    ]
    assert [message.id for message in after_restart] == [
        message.id for message in before_restart
    ]
    assert [message.content for message in after_restart] == [
        message.content for message in before_restart
    ]
    assert [item.speaker for item in restored_context.context] == [
        "consultant",
        "employee",
    ]


@pytest.mark.asyncio
async def test_message_idempotency_collision_guard_and_append_only_correction() -> None:
    settings = _settings()
    scope = _scope()
    (first_human, first_assistant), *_ = load_canonical_rounds()

    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as runtime:
        await append_canonical_round(runtime, scope, first_human, first_assistant)
        checkpoints_before_no_op = len(
            [item async for item in runtime.saver.alist(scope.checkpoint_config)]
        )
        await append_canonical_round(runtime, scope, first_human, first_assistant)
        assert len(await latest_canonical_messages(runtime, scope)) == 2
        assert len(
            [item async for item in runtime.saver.alist(scope.checkpoint_config)]
        ) == checkpoints_before_no_op

        conflicting_human = HumanMessage(
            id=first_human.id,
            content="同一 ID 卻換成另一段內容。",
        )
        with pytest.raises(StableMessageIdConflictError):
            await append_canonical_round(
                runtime,
                scope,
                conflicting_human,
                first_assistant,
            )
        assert len(await latest_canonical_messages(runtime, scope)) == 2
        assert len(
            [item async for item in runtime.saver.alist(scope.checkpoint_config)]
        ) == checkpoints_before_no_op

        correction = HumanMessage(
            id="h-correction",
            content="我剛才說錯了，應改成每日 CSV。",
        )
        acknowledgement = AIMessage(id="a-correction", content="收到並保留更正脈絡。")
        await append_canonical_round(runtime, scope, correction, acknowledgement)
        messages = await latest_canonical_messages(runtime, scope)

    assert [message.id for message in messages] == [
        first_human.id,
        first_assistant.id,
        "h-correction",
        "a-correction",
    ]
    assert messages[0].content == first_human.content


@pytest.mark.asyncio
async def test_store_contains_only_three_focused_current_memories() -> None:
    settings = _settings()
    scope = _scope()
    embed = DeterministicEmbeddingSpy()
    memories = semantic_memory_fixtures(scope)

    async with open_spike_runtime(settings, embed=embed) as runtime:
        await seed_current_memories(runtime, scope, memories)
        rows = await runtime.store.asearch(scope.semantic_namespace, limit=100)
        namespaces = await runtime.store.alist_namespaces(
            prefix=scope.semantic_namespace[:-1],
            max_depth=10,
        )

    exact_rows = [row for row in rows if row.namespace == scope.semantic_namespace]
    assert len(exact_rows) == 3
    assert {row.key for row in exact_rows} == {memory.memory_id for memory in memories}
    assert namespaces == [scope.semantic_namespace]
    serialized_values = " ".join(str(row.value) for row in exact_rows)
    assert "會員 API" not in serialized_values
    assert "過敏欄位不是自由備註" not in serialized_values
    assert "employee-source" not in serialized_values
    assert "conversation-summary" not in serialized_values


@pytest.mark.asyncio
async def test_semantic_index_embeds_only_title_content_and_query() -> None:
    settings = _settings()
    scope = _scope()
    embed = DeterministicEmbeddingSpy()
    memories = semantic_memory_fixtures(scope)

    async with open_spike_runtime(settings, embed=embed) as runtime:
        await seed_current_memories(runtime, scope, memories)
        result = await search_current_memories(runtime, scope, "每日 CSV 會員匯入")

    allowed = {
        text
        for memory in memories
        for text in (memory.title, memory.content)
    } | {"每日 CSV 會員匯入"}
    assert embed.seen_texts
    assert set(embed.seen_texts) <= allowed
    forbidden = {
        ref
        for memory in memories
        for ref in memory.message_refs
    } | {
        str(scope.run_id),
        str(scope.document_id),
        scope.thread_id,
    }
    assert all(
        forbidden_text not in embedded
        for embedded in embed.seen_texts
        for forbidden_text in forbidden
    )
    assert result.memories[0].title == "B 案：健身房會員網站"
    assert "每日" in result.memories[0].content
    assert "CSV" in result.memories[0].content


@pytest.mark.asyncio
async def test_search_returns_full_values_and_enforces_exact_namespace() -> None:
    settings = _settings()
    run_id = uuid4()
    scope = _scope(run_id=run_id, thread_id="shared-thread-name")
    other_scope = _scope(run_id=run_id, thread_id="shared-thread-name")
    memories = semantic_memory_fixtures(scope)

    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as runtime:
        await seed_current_memories(runtime, scope, memories)
        await runtime.store.aput(
            scope.semantic_namespace + ("child",),
            "child-item",
            {
                "memory_id": "child-item",
                "title": "每日 CSV 子命名空間",
                "content": "這筆即使相似也不得回傳。",
                "message_refs": [],
            },
        )
        await runtime.store.aput(
            other_scope.semantic_namespace,
            "other-document-item",
            {
                "memory_id": "other-document-item",
                "title": "每日 CSV 另一文件",
                "content": "這筆屬於另一份文件。",
                "message_refs": [],
            },
        )

        result = await search_current_memories(runtime, scope, "每日 CSV")

    assert result.memories
    assert all(hit.title != "每日 CSV 子命名空間" for hit in result.memories)
    assert all(hit.title != "每日 CSV 另一文件" for hit in result.memories)
    expected = next(memory for memory in memories if memory.memory_id == "memory-b")
    actual = next(hit for hit in result.memories if hit.title == expected.title)
    assert actual.content == expected.content
    assert actual.message_refs == expected.message_refs


@pytest.mark.asyncio
async def test_no_index_store_cannot_masquerade_as_semantic_search() -> None:
    settings = _settings()
    scope = _scope()

    no_index_store = InMemoryStore()
    with pytest.raises(SemanticIndexUnavailableError):
        await search_current_memories(
            SimpleNamespace(store=no_index_store),
            scope,
            "每日 CSV",
        )


@pytest.mark.asyncio
async def test_stable_reference_reads_minimal_adjacent_question_and_answer() -> None:
    settings = _settings()
    scope = _scope()
    rounds = load_canonical_rounds()

    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as runtime:
        for human, assistant in rounds[:21]:
            await append_canonical_round(runtime, scope, human, assistant)
        result = await read_canonical_context(
            runtime,
            scope,
            issue_message_ref(scope, "h-021"),
        )

    assert result.model_dump(mode="json") == {
        "context": [
            {"speaker": "consultant", "text": "退款例外由誰核准？"},
            {
                "speaker": "employee",
                "text": "我先補充，我也會整理每次版本交付的項目。",
            },
        ]
    }


@pytest.mark.asyncio
async def test_bad_missing_and_cross_scope_references_share_public_error() -> None:
    settings = _settings()
    run_id = uuid4()
    current_scope = _scope(run_id=run_id, thread_id="same-thread")
    other_scope = _scope(run_id=run_id, thread_id="same-thread")
    (human, assistant), *_ = load_canonical_rounds()

    async with open_spike_runtime(
        settings,
        embed=DeterministicEmbeddingSpy(),
    ) as runtime:
        await append_canonical_round(runtime, current_scope, human, assistant)
        await append_canonical_round(
            runtime,
            other_scope,
            HumanMessage(id=human.id, content="另一份文件的同 ID 員工訊息。"),
            AIMessage(id=assistant.id, content="另一份文件的顧問回覆。"),
        )
        assert (await latest_canonical_messages(runtime, current_scope))[0].content == (
            human.content
        )
        assert (await latest_canonical_messages(runtime, other_scope))[0].content == (
            "另一份文件的同 ID 員工訊息。"
        )
        probes = [
            ("not-a-reference", "malformed"),
            (issue_message_ref(current_scope, "h-missing"), "missing"),
            (issue_message_ref(other_scope, human.id or "h-001"), "cross_scope"),
        ]
        for message_ref, internal_reason in probes:
            with pytest.raises(ReferenceUnavailableError) as exc_info:
                await read_canonical_context(runtime, current_scope, message_ref)
            assert exc_info.value.public_payload == {
                "error": {"code": "reference_unavailable"}
            }
            assert exc_info.value.internal_reason == internal_reason
            assert str(current_scope.document_id) not in str(exc_info.value)
            assert current_scope.thread_id not in str(exc_info.value)
