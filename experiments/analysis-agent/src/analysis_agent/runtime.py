"""Synchronous analysis-agent composition, without a second workflow/state layer."""

from collections.abc import Callable, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from analysis_agent.context import server_compaction_view


@wrap_model_call
def native_context_view(
    request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Override the model request, never return a messages update to graph state.

    https://docs.langchain.com/oss/python/langchain/context-engineering
    System instructions stay in request.system_message outside the conversation.
    Only supports the responses/v1 inline-compaction contract of build_model.
    """
    return handler(request.override(messages=server_compaction_view(request.messages)))


def build_agent(
    *,
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver,
    instructions: str,
    tools: Sequence[BaseTool] = (),
) -> CompiledStateGraph:
    """Return the official compiled loop; caller owns saver/client lifetimes.

    Invoke with a stable thread_id and durability="sync". After a failed pending
    step, resume with input=None rather than appending the employee message again.
    This slice is synchronous; async/streaming and concurrent-run admission are
    deliberately not claimed by this factory.
    """
    return create_agent(
        model=model,
        tools=list(tools),
        system_prompt=instructions,
        middleware=[native_context_view],
        checkpointer=checkpointer,
    )
