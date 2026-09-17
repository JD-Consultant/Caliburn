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
        case_max_output_tokens=4097,
        understanding_max_output_tokens=8191,
        case_max_model_steps=12,
        case_max_tool_calls=12,
        case_max_chars=24000,
        case_context_chars=1500,
        case_max_windows=16,
        understanding_max_model_steps=12,
        understanding_max_tool_calls=12,
        max_stale_retries=2,
    )


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
        assert first.case_workflow.context_middleware.profile.main_output_reserve_tokens == 4097
        assert case_model.configured_max_tokens == [4097, 4097]

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
            first.understanding_workflow.context_middleware.profile.main_output_reserve_tokens
            == 8191
        )
        assert understanding_model.configured_max_tokens == [8191, 8191]
        assert statements == [], "building must not set up or query database tables"
        assert case_model.requests == [] and understanding_model.requests == []
    finally:
        engine.dispose()
