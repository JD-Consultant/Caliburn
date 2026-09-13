"""Final B2 content validation stays inside the existing bounded Agent loop."""
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage

from .staging import StagedMemoryValidationError, staged_texts


def completed_messages(state):
    """Shared final-response defenses for the feedback hook and outer collect."""
    last = state["messages"][-1]
    messages = [m for m in state["messages"] if isinstance(m, AIMessage)]
    if (not isinstance(last, AIMessage) or last.tool_calls
            or any(m.response_metadata.get("status") != "completed" for m in messages)):
        raise ValueError("Consolidation response is not complete; no publication")
    if any(m.invalid_tool_calls for m in messages):
        raise ValueError("Consolidation has invalid tool calls; not a successful no-op")
    if any(b.get("type") == "refusal" for m in messages for b in m.content if isinstance(b, dict)):
        raise ValueError("Consolidation refused; no publication")
    return messages


class ConsolidationFeedback(AgentMiddleware):
    def __init__(self, artifacts):
        self.artifacts = artifacts

    @hook_config(can_jump_to=["model"])
    def after_model(self, state, runtime):
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        completed_messages(state)  # Refusal/incomplete/malformed is not a repair.
        try:
            staged_texts(self.artifacts)
        except StagedMemoryValidationError as error:
            # This is private B2 context, not employee speech or a tool result.
            # Returning to model traverses the existing before_model quota gate.
            return {"messages": [HumanMessage(
                "Runtime validation feedback (private B2; not employee source): "
                f"{error}\nNothing has been published. Edit the staged files to fix "
                "this error. Runtime checks again when you finish; validate_memory is an optional preflight. "
                "The existing model/tool limits still apply.")], "jump_to": "model"}
        return None
