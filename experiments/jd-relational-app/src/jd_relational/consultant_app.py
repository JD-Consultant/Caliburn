"""A application wiring: the conversation consultant the employee talks to.

This assembles the verified interview method, the analysis Skills it may read
on demand, the Memory actions it may take, and the notice it gets when recent
interviews have not reached Memory. The JD tools, Memory read tools, repair and
the consolidation-request tool are registered elsewhere and only gathered here.

The consultant model is assembled through OpenRouter on its pinned OpenAI Luna
route. Nothing here opens a connection, creates a document, starts background
work or grants writer authority.
"""

from .background_availability import BackgroundAvailability
from .consultant_context import build_consultant_node
from .consultant_guidance import build_consultant_guidance
from .consultant_model import MAX_OUTPUT_TOKENS
from .consultant_tools import AiToolMiddleware
from .continuation_compaction import (
    A_COMPACTION_PROFILE,
    ContinuationCompactionMiddleware,
)
from .memory_context import build_consultant_tools


def analysis_skills_middleware():
    """The three analysis methods, offered as names and read paths only.

    The package owns the assets and the official Skills middleware. Listing
    them costs one short block per turn; a method's own SKILL.md is read
    through the consultant's existing read_file only when it is wanted.
    """
    from caliburn_memory.skills import SkillAssets, analysis_skills
    return analysis_skills(SkillAssets())


def build_consultant(model, *, admissions=None, windows=None, tools=None, guidance=None,
                     context_middleware=None):
    """The shared consultant, with its method, Skills and run-scoped notices.

    Background availability is included only when the callers that own those
    App-wide readers supply them. The current document and turn-start Memory
    baseline come from each invocation's trusted runtime context, never graph
    assembly or model input. Explicit C refreshes stay run-scoped. A host without background wiring still gets a consultant that
    can interview, read Memory and write JD.
    """
    background = (admissions, windows)
    if any(value is None for value in background) and any(value is not None for value in background):
        raise ValueError("incomplete_background_availability")
    middleware = [AiToolMiddleware(), analysis_skills_middleware()]
    if all(value is not None for value in background):
        middleware.append(BackgroundAvailability(admissions, windows))
    if context_middleware is None:
        profile = A_COMPACTION_PROFILE.model_copy(update={
            "main_output_reserve_tokens": MAX_OUTPUT_TOKENS,
        })
        context_middleware = ContinuationCompactionMiddleware(
            summary_model=model,
            profile=profile,
        )
    return build_consultant_node(
        model,
        tools=build_consultant_tools() if tools is None else tools,
        guidance=build_consultant_guidance() if guidance is None else guidance,
        context_middleware=context_middleware,
        extra_middleware=tuple(middleware))
