"""One canonical conversation; official per-invocation Agent checkpoints.

https://docs.langchain.com/oss/python/langgraph/use-subgraphs#subgraph-persistence
Only the messages and outcome cross the root/child boundary. Official persisted
thread counters therefore belong to one employee input, including its resumes,
not to the lifetime of the document. This is synchronous, not an API service.
"""
from collections.abc import Sequence
from typing import Annotated
from uuid import uuid4

from langchain.agents.middleware import (
    AgentMiddleware, AgentState, ModelCallLimitMiddleware, ToolCallLimitMiddleware, hook_config,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from analysis_agent.runtime import build_agent
from analysis_agent.consolidation_request import REQUEST_TOOL_NAME, request_memory_consolidation


def merge_turns(previous: dict, update: dict) -> dict:
    return {**previous, **update}


class ConversationState(MessagesState):
    jd_last_model_view: dict | None
    jd_refs: dict
    jd_sources: dict
    jd_results: dict
    jd_selection: dict | None
    turn_outcome: dict | None
    closed_turns: Annotated[dict[str, dict], merge_turns]


class TurnState(AgentState):
    turn_outcome: dict | None
    invalid_json_count: int
    closed_turns: Annotated[dict[str, dict], merge_turns]


def turn_result(state, status):
    human = next(m for m in reversed(state['messages']) if isinstance(m, HumanMessage))
    return {'input_id': human.id, 'status': status,
            'model_calls': state.get('thread_model_call_count', 0),
            'tool_calls': state.get('thread_tool_call_count', {}).get('__all__', 0)}


def turn_boundary(outcome, end_id):
    return {outcome['input_id']: {'end_id': end_id, 'status': outcome['status']}}


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


class TurnValidation(AgentMiddleware):
    """Validate native output before other after-model hooks can add notices."""
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


class TurnOutcome(AgentMiddleware):
    """Final owned node: technical boundary, never provider/model-authored state."""
    state_schema = TurnState

    def after_agent(self, state, runtime):
        last = state['messages'][-1]
        completed = isinstance(last, AIMessage) and last.response_metadata.get('status') == 'completed' and not last.tool_calls
        outcome = turn_result(state, 'completed' if completed else last.additional_kwargs.get('analysis_agent_stop_reason', 'limit'))
        update = {'turn_outcome': outcome, 'closed_turns': turn_boundary(outcome, last.id)}
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
    max_model_steps: int = 16, max_tool_calls: int = 15,
):
    """Compile the root and a directly registered, resumable Agent subgraph.

    New input is checkpointed on the root before the child starts. While the
    child is pending, inspect get_state(config, subgraphs=True); resume root with
    None and durability='sync'. Worker/admission orchestration is Task3.
    No outer retry policy: the provider SDK owns transient HTTP retry.
    """
    if any(type(n) is not int or n <= 0 for n in (max_model_steps, max_tool_calls)):
        raise ValueError('Conversation limits must be positive integers')
    # close_turn can classify this one known function as side-effect-free.
    # A same-name replacement must not silently inherit that cancellation rule.
    supplied = [*tools, *(t for item in middleware for t in getattr(item, 'tools', ()))]
    if any(t.name == REQUEST_TOOL_NAME for t in supplied):
        raise ValueError('request_memory_consolidation is reserved for the pure notification tool')
    from analysis_agent.live_memory import MemorySession
    for session in (item for item in middleware if isinstance(item, MemorySession)):
        readers = {t.name: t for t in session.read_tools}
        if any(t.name in readers and t is not readers[t.name] for t in supplied):
            raise ValueError('Read tool names are reserved for the bound Memory readers')
    from analysis_agent.jd_tools import JdToolSession, JdExecutionIdentity, NAMES
    sessions = [item for item in middleware if isinstance(item, JdToolSession)]
    jd_tools = {t.name: t for session in sessions for t in session.tools}
    if len(sessions) > 1 or any(t.name in NAMES and t is not jd_tools.get(t.name) for t in supplied):
        raise ValueError("JD names are reserved for original factory tools")
    child = build_agent(model=model, checkpointer=None, instructions=instructions,
        tools=[*tools, request_memory_consolidation],
        middleware=[
            # after_agent runs in reverse order: this is the final owned node.
            TurnOutcome(),
            ToolCallLimitMiddleware(thread_limit=max_tool_calls, exit_behavior='end'),
            *middleware, ToolJsonFeedback(),
            ModelCallLimitMiddleware(thread_limit=max_model_steps, exit_behavior='end'),
            TurnValidation(),
            # Last wrapper sees the final tool after all prior overrides.
            *(JdExecutionIdentity(session) for session in sessions),
        ])
    root = StateGraph(ConversationState)
    root.add_node('analysis', child)
    root.add_edge(START, 'analysis')
    root.add_edge('analysis', END)
    return root.compile(checkpointer=checkpointer)


def require_latest(config):
    if config.get('configurable', {}).get('checkpoint_id') or config.get('configurable', {}).get('checkpoint_ns'):
        raise ValueError('Use the latest root document config, not a historical/child checkpoint')


def pending_memory_read(snapshot, memory_session):
    """Identify the current unpaired ToolNode call, not an exception/name hint.

    The caller supplies the MemorySession used to compose this conversation.
    Its factory-built read tools are reserved at composition; arbitrary tools
    cannot acquire this capability by returning a familiar model-authored name.
    """
    if memory_session is None or snapshot.next != ('analysis',):
        return None
    child = next((t.state for t in snapshot.tasks if t.name == 'analysis'), None)
    if not hasattr(child, 'values') or child.next != ('tools',):
        return None
    messages = child.values.get('messages', [])
    human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if (human is None or child.values.get('memory_turn_id') != human.id
            or snapshot.config['configurable']['thread_id'] != memory_session.source.document_id):
        return None
    last = messages[-1]
    if (not isinstance(last, AIMessage) or last.invalid_tool_calls
            or len(last.tool_calls) != 1):
        return None
    call = last.tool_calls[0]
    if call.get('id') and call['name'] in {t.name for t in memory_session.read_tools}:
        return call
    return None


def close_turn(graph, config, *, reason: str, quiescent: bool, memory_session=None):
    """Seal the pending root using public state APIs, without executing any node.

    Caller MUST have stopped/joined its worker and serialized this document.
    This function does not cancel threads. Close child first, then root; a lost
    root update can only leave an already-terminal child, not runnable tools.
    Historical checkpoints remain intact (never resume an old checkpoint to
    cancel). Use the latest document config at this entry.
    """
    from analysis_agent.publication import PublicationUncertain
    require_latest(config)
    if quiescent is not True:
        raise ValueError('A confirmed quiescent worker is required')
    if reason not in {'cancelled', 'configuration_error'}:
        raise ValueError('Expected cancelled or configuration_error')
    snapshot = graph.get_state(config, subgraphs=True)
    if not snapshot.values.get('messages'):
        raise ValueError('No saved input to close')
    if not snapshot.next:
        return snapshot.values
    if snapshot.next != ('analysis',):
        raise ValueError('Unexpected pending conversation node')
    task = next(t for t in snapshot.tasks if t.name == 'analysis')
    child = task.state
    # An admitted root input can precede the first child checkpoint. The public
    # state API returns an empty child snapshot, not necessarily None.
    if child and hasattr(child, 'values') and not child.values.get('messages'):
        child = None
    state = child.values if child and hasattr(child, 'values') else snapshot.values
    read_call = pending_memory_read(snapshot, memory_session)
    messages = list(state['messages'])
    human_index = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    saved = state.get('turn_outcome')
    boundary = state.get('closed_turns', {}).get(messages[human_index].id)
    if (child and not child.next and saved and saved['input_id'] == messages[human_index].id
            and boundary and boundary['end_id'] == messages[-1].id):
        graph.update_state(snapshot.config, {'messages': messages, 'turn_outcome': saved,
            'closed_turns': turn_boundary(saved, messages[-1].id)}, as_node='analysis')
        return graph.get_state(config).values
    updates = {}
    for index, message in enumerate(messages[human_index + 1:], human_index + 1):
        if not isinstance(message, AIMessage):
            continue
        for call in [*message.tool_calls, *message.invalid_tool_calls]:
            if any(isinstance(m, ToolMessage) and m.tool_call_id == call.get('id') for m in messages[index + 1:]):
                continue
            if not call.get('id') or not call.get('name'):
                raise PublicationUncertain('Unpaired call has no reliable identity')
            # after_model nodes precede ToolNode for this canonical response.
            # Merely having no task.error at tools does NOT prove not-started.
            not_started = child and child.next and all(n.endswith('.after_model') for n in child.next)
            if not_started:
                messages.append(ToolMessage('Tool not executed: this turn was closed before tool execution.',
                    name=call['name'], tool_call_id=call['id'], status='error'))
            elif call['name'] == REQUEST_TOOL_NAME:
                # Worker is quiescent. This registered tool has no external
                # effects; without a saved receipt no request was handed off.
                messages.append(ToolMessage('整理請求未成功交接；本輪已停止，記憶尚未因此更新。',
                    name=call['name'], tool_call_id=call['id'], status='error'))
            elif call == read_call:
                # A read may have run before its result was lost. Closing it
                # discards the unavailable result, not an external write effect.
                messages.append(ToolMessage('Read result unavailable/discarded: this turn was closed. '
                    'Do not infer absence of data from this result.',
                    name=call['name'], tool_call_id=call['id'], status='error'))
            elif call['name'] == 'repair_memory' and memory_session is not None:
                command = memory_session.reconcile(state, message, call, config)
                messages.extend(command.update['messages'])
                updates.update({k: v for k, v in command.update.items() if k != 'messages'})
            else:
                raise PublicationUncertain('Tool result is unknown; do not fabricate failure')
    outcome = turn_result(state, reason)
    # A neutral runtime notice gives a stable end ID, never provider completion.
    notice = AIMessage('本輪已結束，顧問未完成答覆。', id=str(uuid4()), additional_kwargs={
        'analysis_agent_origin': 'runtime_notice', 'analysis_agent_stop_reason': reason})
    messages.append(notice)
    terminal = {'messages': messages, 'turn_outcome': outcome,
                'closed_turns': turn_boundary(outcome, notice.id)}
    # The owned final middleware node routes to END. Head, paired result and
    # terminal status are one child checkpoint; neither update executes a node.
    if child and hasattr(child, 'values'):
        graph.update_state(child.config, {**updates, **terminal}, as_node='TurnOutcome.after_agent')
    graph.update_state(snapshot.config, terminal, as_node='analysis')
    return graph.get_state(config).values


def send_input(graph, config, message: HumanMessage, *, abandon_pending=False,
               quiescent=False, memory_session=None):
    """Synchronous local entry; worker/admission orchestration remains Task3."""
    require_latest(config)
    if not isinstance(message, HumanMessage) or not message.id:
        raise ValueError('A new employee message with a stable ID is required')
    snapshot = graph.get_state(config)
    if any(m.id == message.id for m in snapshot.values.get('messages', [])):
        raise ValueError('Input already saved; resume the existing turn instead')
    if snapshot.next:
        if not abandon_pending:
            raise ValueError('Conversation has pending work; explicitly resume or abandon it')
        close_turn(graph, config, reason='cancelled', quiescent=quiescent, memory_session=memory_session)
    return graph.invoke({'messages': [message]}, config, durability='sync')
