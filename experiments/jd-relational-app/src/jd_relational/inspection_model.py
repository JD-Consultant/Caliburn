"""Native Agent layout for checkpoint inspection, with execution disabled.

BaseChatModel is LangChain's public integration interface. This model never
returns an AI response, reads configuration or constructs a provider SDK.
Wrap-only guards add no graph nodes/channels; the existing after_model hook
also guards its inspection mode. Callers use get_state/get_tuple, not invoke.
A rejected invoke can still write native input/error checkpoints.
"""

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.chat_models import BaseChatModel


class InspectionExecutionDisabled(ValueError):
    def __init__(self):
        self.code = "execution_disabled"
        super().__init__(self.code)


class InspectionOnly(BaseChatModel):
    @property
    def _llm_type(self):
        return "jd-checkpoint-inspection-only"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, *args, **kwargs):
        raise InspectionExecutionDisabled()

    async def _agenerate(self, *args, **kwargs):
        raise InspectionExecutionDisabled()


class InspectionGuard(AgentMiddleware):
    """First/outermost native wraps: do not call any subsequent handler."""

    def wrap_model_call(self, request, handler):
        raise InspectionExecutionDisabled()

    async def awrap_model_call(self, request, handler):
        raise InspectionExecutionDisabled()

    def wrap_tool_call(self, request, handler):
        raise InspectionExecutionDisabled()

    async def awrap_tool_call(self, request, handler):
        raise InspectionExecutionDisabled()


def build_inspection_consultant_node():
    """Use the shared native factory and the actual JD tool/middleware layout."""
    from .consultant_context import build_consultant_node
    from .consultant_tools import AiToolMiddleware, build_jd_tools
    return build_consultant_node(InspectionOnly(cache=False, output_version=None),
        tools=build_jd_tools(), guidance="Checkpoint inspection only; execution is disabled.",
        extra_middleware=[AiToolMiddleware()])
