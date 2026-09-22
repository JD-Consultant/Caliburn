"""Thin App assembly for document-scoped layered Memory resources."""

from copy import deepcopy
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from pydantic import Field
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.pool import StaticPool

from jd_relational.background_memory_app import build_background_memory_workflow
from jd_relational.background_memory_limits import FORMAL_BACKGROUND_MEMORY_LIMITS
from jd_relational.continuation_compaction import ContinuationCompactionMiddleware

from test_chat_history import native  # noqa: F401
from test_conversation_sources import service


class NoCallModel(BaseChatModel):
    requests: list = Field(default_factory=list)
    configured_max_tokens: list[int] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "background-memory-composition-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def model_copy(self, *, update=None, deep=False):
        if update and "max_tokens" in update:
            self.configured_max_tokens.append(update["max_tokens"])
        return super().model_copy(update=update, deep=deep)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests.append(deepcopy(messages))
        return ChatResult(generations=[ChatGeneration(message=None)])


def build(sources, document_id, store, saver, engine, case_model, understanding_model):
    return build_background_memory_workflow(
        service=sources,
        document_id=document_id,
        store=store,
        checkpointer=saver,
        memory_engine=engine,
        case_model=case_model,
        understanding_model=understanding_model,
    )


def test_formal_background_limits_match_the_reviewed_product_profile():
    limits = FORMAL_BACKGROUND_MEMORY_LIMITS

    assert limits.request_timeout_seconds == 300.0
    assert limits.compaction_trigger_input_tokens == 16000
    assert limits.compaction_keep_messages == 8
    assert (
        limits.case_max_output_tokens,
        limits.case_summary_max_output_tokens,
        limits.case_max_model_steps,
        limits.case_max_tool_calls,
        limits.case_max_completion_corrections,
    ) == (32768, 8192, 256, 240, 3)
    assert (
        limits.case_max_chars,
        limits.case_context_chars,
        limits.case_max_windows,
    ) == (24000, 6000, 16)
    assert (
        limits.understanding_max_output_tokens,
        limits.understanding_summary_max_output_tokens,
        limits.understanding_max_model_steps,
        limits.understanding_max_tool_calls,
        limits.understanding_max_completion_corrections,
    ) == (32768, 8192, 128, 120, 3)
    assert limits.max_stale_retries == 5


def test_build_binds_one_authority_per_document_without_io_or_model_calls(native):
    sources = service(native)
    first_document = native[2]
    second_document = str(uuid4())
    store, saver = InMemoryStore(), InMemorySaver()
    engine = sa.create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    statements = []
    event.listen(engine, "before_cursor_execute",
                 lambda *_args: statements.append(_args[2]))
    case_model, understanding_model = NoCallModel(), NoCallModel()
    try:
        first = build(
            sources, first_document, store, saver, engine,
            case_model, understanding_model,
        )
        second = build(
            sources, second_document, store, saver, engine,
            case_model, understanding_model,
        )

        for workflow, document_id in ((first, first_document), (second, second_document)):
            assert workflow.document_id == document_id
            assert workflow.case_workflow.reader.document_id == document_id
            assert workflow.understanding_workflow.reader is workflow.case_workflow.reader
            assert workflow.case_workflow.session.artifacts is workflow.artifacts
            assert workflow.understanding_workflow.session.artifacts is workflow.artifacts
            assert workflow.publication.artifacts is workflow.artifacts
        assert first.config["configurable"]["thread_id"] != \
            second.config["configurable"]["thread_id"]
        assert first.case_workflow.config["configurable"]["thread_id"] != \
            second.case_workflow.config["configurable"]["thread_id"]
        assert isinstance(
            first.case_workflow.context_middleware,
            ContinuationCompactionMiddleware,
        )
        assert first.case_workflow.context_middleware.summary_model is case_model
        assert first.case_workflow.context_middleware.profile.protect_latest_human_turn is True
        assert first.case_workflow.context_middleware.profile.preserve_initial_messages == 0
        assert first.case_workflow.context_middleware.profile.trigger_input_tokens == 16000
        assert first.case_workflow.context_middleware.profile.keep_messages == 8
        assert first.case_workflow.context_middleware.profile.main_output_reserve_tokens == 32768
        assert first.case_workflow.context_middleware.profile.summary_max_output_tokens == 8192
        assert first.case_workflow.max_chars == 24000
        assert first.case_workflow.context_chars == 6000
        assert first.case_workflow.max_windows == 16
        assert first.case_workflow.max_completion_corrections == 3
        assert first.case_workflow.recursion_limit == (256 * 3 + 6) * 16
        assert case_model.configured_max_tokens == [32768, 32768]

        assert isinstance(
            first.understanding_workflow.context_middleware,
            ContinuationCompactionMiddleware,
        )
        assert first.understanding_workflow.context_middleware.summary_model is understanding_model
        assert (
            first.understanding_workflow.context_middleware.profile.preserve_initial_messages
            == 1
        )
        assert (
            first.understanding_workflow.context_middleware.profile.protect_latest_human_turn
            is False
        )
        assert (
            first.understanding_workflow.context_middleware.profile.trigger_input_tokens
            == 16000
        )
        assert first.understanding_workflow.context_middleware.profile.keep_messages == 8
        assert (
            first.understanding_workflow.context_middleware.profile.main_output_reserve_tokens
            == 32768
        )
        assert (
            first.understanding_workflow.context_middleware.profile.summary_max_output_tokens
            == 8192
        )
        assert first.understanding_workflow.max_completion_corrections == 3
        assert first.understanding_workflow.recursion_limit == max(100, 128 * 6 + 16)
        assert first.max_stale_retries == 5
        assert understanding_model.configured_max_tokens == [32768, 32768]
        assert statements == [], "building must not set up or query database tables"
        assert case_model.requests == [] and understanding_model.requests == []
    finally:
        engine.dispose()
