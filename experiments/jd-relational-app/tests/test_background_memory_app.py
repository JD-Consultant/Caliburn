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

from test_chat_history import native  # noqa: F401
from test_conversation_sources import service


class NoCallModel(BaseChatModel):
    requests: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "background-memory-composition-test"

    def bind_tools(self, tools, **kwargs):
        return self

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
        assert statements == [], "building must not set up or query database tables"
        assert case_model.requests == [] and understanding_model.requests == []
    finally:
        engine.dispose()
