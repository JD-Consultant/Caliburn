"""Tell the consultant when recent interviews are not in Memory yet.

Adopted effect from the verified consultant's `BackgroundAvailability`: a turn
that opens while consolidation is stuck should know that the employee's recent
answers are still only in the original conversation, so it does not treat them
as remembered. The wording is kept; the durable facts come from this App's own
owners instead of the old host's row -- the admission row says whether the work
is blocked, and the publication cursor says whether it turned out to be covered
anyway.

This reads. It never admits, starts, resumes or wakes background work, never
moves a cursor, and never speaks as the employee: the notice goes in as an App
system block, exactly like every other App-supplied context.
"""

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import HumanMessage, SystemMessage

NOTICE = ("最近一段訪談尚未成功整理進長期記憶；原始問答仍保存。"
          "不要假定記憶已包含這段資料，必要時回查訪談。"
          "這是程式的記憶可用性提示，不是員工工作事實；不要要求員工修理技術設定。")
RANGE_PREFIX = "\n本次尚未完整整理的訪談範圍："
BLOCK = "<background_memory_availability>\n{notice}\n</background_memory_availability>"


class BackgroundContextState(AgentState):
    background_notice: str
    background_turn_id: str


def availability_notice(admissions, publication, windows, document_id: str) -> str:
    """Empty unless this document's background work is really stuck and owed.

    A blocked row whose target the publication cursor already covers is not
    worth telling anyone about: the understanding did get published, and the
    block is stale. Coverage is asked of the source owner, never recomputed.
    """
    admission = admissions.read(document_id)
    if admission.status != "blocked" or admission.target_reference is None:
        return ""
    head = publication.current()
    covered = windows.plan_saved_batch(
        admission.target_reference, document_id,
        after_reference=head.processed_source if head is not None else None)
    if covered["source_reference"] is None:
        return ""
    return NOTICE + RANGE_PREFIX + admission.target_reference


class BackgroundAvailability(AgentMiddleware):
    """One read per employee input, carried on the turn's own state."""

    state_schema = BackgroundContextState

    def __init__(self, admissions, publication, windows, document_id: str):
        self._admissions, self._publication = admissions, publication
        self._windows, self._document_id = windows, document_id

    def before_agent(self, state, runtime):
        current = next((message.id for message in reversed(state["messages"])
                        if isinstance(message, HumanMessage)), None)
        if current is None or state.get("background_turn_id") == current:
            # Later model steps in the same turn reuse what was read once.
            return None
        return {"background_turn_id": current,
                "background_notice": availability_notice(
                    self._admissions, self._publication, self._windows, self._document_id)}

    def wrap_model_call(self, request, handler):
        notice = request.state.get("background_notice")
        if not notice:
            return handler(request)
        base = request.system_message.content if request.system_message else ""
        blocks = [{"type": "text", "text": base}] if isinstance(base, str) else list(base)
        blocks.append({"type": "text", "text": BLOCK.format(notice=notice)})
        return handler(request.override(system_message=SystemMessage(content=blocks)))
