"""One A run pins a Memory view; only explicit C feedback refreshes it."""
from dataclasses import asdict
import json
from uuid import NAMESPACE_URL, uuid5

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from analysis_agent.memory import MemoryVersion
from analysis_agent.memory_tools import MEMORY_EDIT_GUIDANCE, MEMORY_READ_GUIDANCE, memory_read_tools
from analysis_agent.repair import MemoryEdit, RepairWorkflow
from analysis_agent.memory_patch import PATCH_GUIDANCE


class MemorySessionState(AgentState):
    memory_turn_id: str
    memory_initial_guide: str
    memory_initial_revision: int
    memory_source_reference: str
    memory_read_head: dict | None
    memory_repair_failures: int
    memory_repair_binding: dict | None


class MemorySession(AgentMiddleware):
    state_schema = MemorySessionState

    def __init__(self, publication, source, *, skill_assets=None):
        self.publication, self.source = publication, source
        self.skill_assets = skill_assets
        self.artifacts = publication.artifacts
        self.repair = RepairWorkflow(self.artifacts, publication, source)

        @tool
        def repair_memory(edits: list[MemoryEdit], runtime: ToolRuntime) -> Command:
            """Repair previously read memory with a small atomic batch of V4A patches.

            Only /memory/knowledge.md and /memory/guide.md, 1–8 edits, 12000
            combined diff characters. Each edit has path and diff only.
            Update the guide if routing changed. A failed patch prevents the
            whole batch from being published; retry against current published Memory.
            On stale read the new head and reconsider. On ambiguous employee
            meaning ask them; this tool checks format, not semantic truth.
            """
            result = self.repair.graph.invoke({"base": runtime.state["memory_read_head"],
                "operation_id": runtime.state["memory_repair_binding"]["operation_id"],
                "edits": [edit.model_dump() for edit in edits], "index": 0, "outcome": None,
                "source_reference": runtime.state["memory_source_reference"]})
            return self._command(result["outcome"], runtime.state, runtime.tool_call_id)

        repair_memory.description += "\n\n" + PATCH_GUIDANCE + "\n\n" + MEMORY_EDIT_GUIDANCE

        # Keep the actual factory-built capability separate from the write tool.
        # Conversation composition rejects same-name replacements before binding.
        self.read_tools = tuple(memory_read_tools(self.artifacts, None, source, skill_assets=self.skill_assets))
        self.tools = [*self.read_tools, repair_memory]

    def _scope(self, config):
        if config["configurable"]["thread_id"] != self.artifacts.document_id:
            raise ValueError("Memory session belongs to another document")

    def before_agent(self, state, runtime):
        from langgraph.config import get_config
        self._scope(get_config())
        current = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        if current is None or not current.id:
            raise ValueError("A saved employee input is required")
        if state.get("memory_turn_id") == current.id:
            return None
        head = self.publication.current()
        return {"memory_turn_id": current.id, "memory_read_head": asdict(head) if head else None,
            "memory_initial_guide": self.artifacts.guide(head.memory) if head else "No memory has been published yet.",
            "memory_initial_revision": head.revision if head else 0,
            "memory_source_reference": self.source.capture_input(current.id), "memory_repair_failures": 0,
            "memory_repair_binding": None}

    def wrap_model_call(self, request, handler):
        base = request.system_message.content if request.system_message else ""
        blocks = [{"type": "text", "text": base}] if isinstance(base, str) else list(base)
        blocks.append({"type": "text", "text": (
            MEMORY_READ_GUIDANCE +
            "This input starts with the fixed initial guide below. "
            "Only C tool feedback whose source_reference matches the Current input reference "
            "supersedes this input's initial guide/read version, when it provides a refreshed head/guide. "
            "Previous-input C feedback is historical and cannot override this input's initial view. "
            "Repair is on demand, not routine background consolidation. If published Memory "
            "conflicts with a verified correction in the current conversation, read the affected "
            "text and use repair_memory before your final response. Correct outdated facts in "
            "knowledge and, if present, the guide; preserve unaffected details and references. "
            "A corrected deadline, frequency or case condition matters even when the common "
            "work pattern is unchanged. If the meaning is unclear, ask instead of guessing. "
            "If repair cannot preserve the correction, follow request_memory_consolidation's "
            "guidance and report only what the tool results confirm. Do not reveal hidden reasoning.\n"
            # Old pending checkpoints have no proven initial revision. Neither
            # the refreshed read head nor the latest publication can supply it.
            f"Initial guide publication revision: {request.state.get('memory_initial_revision', 'unknown')}\n"
            f"<initial_memory_guide>\n{request.state['memory_initial_guide']}\n</initial_memory_guide>\n"
            f"Current input reference (copy only if useful): {request.state['memory_source_reference']}"
        )})
        return handler(request.override(system_message=SystemMessage(content=blocks)))

    def after_model(self, state, runtime):
        message = state["messages"][-1]
        if not isinstance(message, AIMessage) or message.response_metadata.get("status") != "completed":
            raise ValueError("Incomplete model response; no tool execution")
        if len(message.tool_calls) > 1:
            raise ValueError("Unexpected parallel tool calls; no tool execution")
        if message.invalid_tool_calls:
            raise ValueError("Invalid tool call encoding; no tool execution")
        if message.tool_calls and message.tool_calls[0]['name'] == 'repair_memory':
            call = message.tool_calls[0]
            if not message.id or not call.get('id'):
                raise ValueError('Missing repair call identity; no tool execution')
            # Runtime-only identity, checkpointed BEFORE tools. No namespace
            # parsing, hidden graph discovery, model-authored IDs or new store.
            identity = json.dumps([self.artifacts.document_id, state['memory_turn_id'],
                                   message.id, call['id']])
            return {'memory_repair_binding': {'message_id': message.id, 'call_id': call['id'],
                'operation_id': str(uuid5(NAMESPACE_URL, 'q019-c:' + identity))}}

    def reconcile(self, state, message, call, config):
        """Read-only cancellation path; never invoke C or create a publication."""
        from analysis_agent.publication import PublicationUncertain
        self._scope(config)
        binding = state.get('memory_repair_binding')
        if not binding or binding['message_id'] != message.id or binding['call_id'] != call['id']:
            raise PublicationUncertain('Repair operation identity is unavailable')
        feedback = self.repair.reconcile(binding['operation_id'], state['memory_source_reference'], call['args']['edits'])
        return self._command(feedback, state, call['id'])

    def _command(self, feedback, state, call_id):
        failed = feedback["status"] in {"invalid_edit", "stale", "no_memory"}
        failures = state["memory_repair_failures"] + int(failed)
        feedback = {**feedback, "retryable": failed and failures < 2,
            "source_reference": state["memory_source_reference"]}
        update = {"memory_repair_failures": failures,
            "messages": [ToolMessage(json.dumps(feedback, ensure_ascii=False), tool_call_id=call_id,
                status="error" if failed or feedback['status'] == 'repair_limit' else "success")]}
        if "head" in feedback:
            update["memory_read_head"] = feedback["head"]
        return Command(update=update)

    def wrap_tool_call(self, request, handler):
        self._scope(request.runtime.config)
        if request.tool_call["name"] == "repair_memory":
            if request.state["memory_repair_failures"] >= 2:
                return self._command({"status": "repair_limit", "detail": "Repair retry budget exhausted for this input. Do not keep calling repair."}, request.state, request.tool_call["id"])
            result = handler(request)
            if isinstance(result, ToolMessage) and result.status == "error":
                # ToolNode converts schema failures into an error ToolMessage
                # before this wrapper sees them. Keep its native field guidance
                # and count this failed attempt too. Infrastructure errors still
                # propagate (ToolNode's default only handles invocation errors).
                return self._command({"status": "invalid_edit", "detail": str(result.content)[:1200],
                    "read_paths": ["/memory/knowledge.md", "/memory/guide.md"]}, request.state, request.tool_call["id"])
            return result
        head = request.state["memory_read_head"]
        version = MemoryVersion(**head["memory"]) if head else None
        replacements = {t.name: t for t in memory_read_tools(self.artifacts, version, self.source,
                                                           skill_assets=self.skill_assets)}
        replacement = replacements.get(request.tool_call["name"])
        return handler(request.override(tool=replacement)) if replacement else handler(request)
