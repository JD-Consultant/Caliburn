"""One canonical conversation; official per-invocation Agent checkpoints.

https://docs.langchain.com/oss/python/langgraph/use-subgraphs#subgraph-persistence
Only the messages and outcome cross the root/child boundary. Official persisted
thread counters therefore belong to one employee input, including its resumes,
not to the lifetime of the document. This is synchronous, not an API service.
"""
from collections.abc import Sequence

from langchain.agents.middleware import (
    AgentMiddleware, AgentState, ModelCallLimitMiddleware, ToolCallLimitMiddleware, hook_config,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from analysis_agent.runtime import build_agent


class ConversationState(MessagesState):
    turn_outcome: dict | None


class TurnState(AgentState):
    turn_outcome: dict | None
    invalid_json_count: int


class ToolJsonFeedback(AgentMiddleware):
    """Bridge adapter parse errors via public hooks, without executing a tool.

    ToolNode cannot validate a call that has no parsed arguments. Preserve the
    native function_call and its ID, append a matching error result, then route
    through the official model entry (including its persisted budget check).
    """
    state_schema = TurnState

    @hook_config(can_jump_to=['model', 'end'])
    def after_model(self, state, runtime):
        message = state['messages'][-1]
        if not message.invalid_tool_calls:
            return None
        call = message.invalid_tool_calls[0]
        if not call.get('id') or not call.get('name'):
            raise ValueError('Missing tool call identity; cannot fabricate a result')
        count = state.get('invalid_json_count', 0) + 1
        messages = [ToolMessage(
            'Tool not executed: arguments are not valid JSON. Send one corrected '
            'call with a JSON object matching the tool schema.',
            name=call['name'], tool_call_id=call['id'], status='error',
        )]
        if count >= 2:
            messages.append(AIMessage('工具參數格式仍有誤，本輪未完成。', additional_kwargs={
                'analysis_agent_origin': 'runtime_notice', 'analysis_agent_stop_reason': 'tool_error',
            }))
        return {'messages': messages, 'invalid_json_count': count,
                'jump_to': 'end' if count >= 2 else 'model'}


class TurnOutcome(AgentMiddleware):
    """Runtime outcome is not provider status, usage, or model-authored content."""
    state_schema = TurnState

    def before_agent(self, state, runtime):
        if not isinstance(state['messages'][-1], HumanMessage):
            raise ValueError('A new invocation requires a saved employee input; resume with None')
        return {'turn_outcome': None}

    def after_model(self, state, runtime):
        # This hook must run BEFORE limit middleware may append synthetic text.
        message = state['messages'][-1]
        if not isinstance(message, AIMessage) or message.response_metadata.get('status') != 'completed':
            raise ValueError('Incomplete model response; no tool execution')
        if len(message.tool_calls) + len(message.invalid_tool_calls) > 1:
            raise ValueError('Unexpected parallel tool calls; no tool execution')

    def after_agent(self, state, runtime):
        last = state['messages'][-1]
        completed = isinstance(last, AIMessage) and last.response_metadata.get('status') == 'completed' and not last.tool_calls
        human = next(m for m in reversed(state['messages']) if isinstance(m, HumanMessage))
        update = {'turn_outcome': {
            'input_id': human.id,
            'status': 'completed' if completed else last.additional_kwargs.get('analysis_agent_stop_reason', 'limit'),
            # Official persisted counts are successful model calls and admitted
            # tools, not actual HTTP attempts, successful effects or dollar use.
            'model_calls': state.get('thread_model_call_count', 0),
            'tool_calls': state.get('thread_tool_call_count', {}).get('__all__', 0),
        }}
        if not completed:
            # Tag only the framework-generated ending, never provider metadata.
            # Keep its stable message ID and canonical text; source readers may
            # now exclude this notice without matching English error strings.
            update['messages'] = [last.model_copy(update={'additional_kwargs': {
                **last.additional_kwargs, 'analysis_agent_origin': 'runtime_notice',
            }})]
        return update


def build_conversation(
    *, model: BaseChatModel, checkpointer: BaseCheckpointSaver, instructions: str,
    tools: Sequence[BaseTool] = (), middleware: Sequence[AgentMiddleware] = (),
    max_model_steps: int = 9, max_tool_calls: int = 8,
):
    """Compile the root and a directly registered, resumable Agent subgraph.

    New input is checkpointed on the root before the child starts. While the
    child is pending, inspect get_state(config, subgraphs=True); resume root with
    None and durability='sync'. Admission/cancellation belongs to the next slice.
    No outer retry policy: the provider SDK owns transient HTTP retry.
    """
    if any(type(n) is not int or n <= 0 for n in (max_model_steps, max_tool_calls)):
        raise ValueError('Conversation limits must be positive integers')
    child = build_agent(model=model, checkpointer=None, instructions=instructions, tools=tools,
        middleware=[
            ToolCallLimitMiddleware(thread_limit=max_tool_calls, exit_behavior='end'),
            *middleware, ToolJsonFeedback(),
            ModelCallLimitMiddleware(thread_limit=max_model_steps, exit_behavior='end'),
            TurnOutcome(),
        ])
    root = StateGraph(ConversationState)
    root.add_node('analysis', child)
    root.add_edge(START, 'analysis')
    root.add_edge('analysis', END)
    return root.compile(checkpointer=checkpointer)
