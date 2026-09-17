"""App-owned assembly for one document's layered background Memory workflow.

Provider selection, credentials, schema setup and scheduling stay with the
host. This module only binds the already-open resources and explicit role
limits to the package workflow.
"""

from typing import Any

from caliburn_memory import (
    BackgroundMemoryWorkflow,
    CaseMaintenanceSession,
    CaseMaintenanceWorkflow,
    MemoryArtifacts,
    PublicationStore,
    UnderstandingMaintenanceSession,
    UnderstandingMaintenanceWorkflow,
)
from langgraph.checkpoint.base import BaseCheckpointSaver

from .background_memory_limits import (
    FORMAL_BACKGROUND_MEMORY_LIMITS,
    BackgroundMemoryLimits,
)
from .conversation_sources import ConversationSourceService
from .continuation_compaction import (
    B1_COMPACTION_PROFILE,
    B2_COMPACTION_PROFILE,
    ContinuationCompactionMiddleware,
)
from .extraction_app import ExtractionSourceAdapter
from .memory_sources import MemorySourceReader


def build_background_memory_workflow(
    *,
    service: ConversationSourceService,
    document_id: str,
    store,
    checkpointer: BaseCheckpointSaver,
    memory_engine,
    case_model: Any,
    understanding_model: Any,
    limits: BackgroundMemoryLimits = FORMAL_BACKGROUND_MEMORY_LIMITS,
) -> BackgroundMemoryWorkflow:
    """Bind one document without choosing a provider or opening resources.

    The App-owned profile is explicit at this boundary so package test defaults
    cannot silently become product policy. Tests may inject a complete profile;
    production callers use the reviewed formal profile.
    """
    reader = ExtractionSourceAdapter(service, document_id)
    artifacts = MemoryArtifacts(
        store,
        document_id,
        source=MemorySourceReader(
            service,
            document_id,
            window_references=True,
        ),
    )
    case_session = CaseMaintenanceSession(artifacts)
    case_compaction = ContinuationCompactionMiddleware(
        summary_model=case_model,
        profile=B1_COMPACTION_PROFILE.model_copy(update={
            "trigger_input_tokens": limits.compaction_trigger_input_tokens,
            "keep_messages": limits.compaction_keep_messages,
            "main_output_reserve_tokens": limits.case_max_output_tokens,
            "summary_max_output_tokens": limits.case_summary_max_output_tokens,
        }),
    )
    case_workflow = CaseMaintenanceWorkflow(
        reader,
        case_session,
        case_model,
        checkpointer,
        max_model_steps=limits.case_max_model_steps,
        max_tool_calls=limits.case_max_tool_calls,
        max_chars=limits.case_max_chars,
        context_chars=limits.case_context_chars,
        max_windows=limits.case_max_windows,
        max_completion_corrections=limits.case_max_completion_corrections,
        max_output_tokens=limits.case_max_output_tokens,
        context_middleware=case_compaction,
    )
    understanding_session = UnderstandingMaintenanceSession(
        artifacts,
        case_session,
    )
    understanding_compaction = ContinuationCompactionMiddleware(
        summary_model=understanding_model,
        profile=B2_COMPACTION_PROFILE.model_copy(update={
            "trigger_input_tokens": limits.compaction_trigger_input_tokens,
            "keep_messages": limits.compaction_keep_messages,
            "main_output_reserve_tokens": limits.understanding_max_output_tokens,
            "summary_max_output_tokens": limits.understanding_summary_max_output_tokens,
        }),
    )
    understanding_workflow = UnderstandingMaintenanceWorkflow(
        reader,
        understanding_session,
        understanding_model,
        checkpointer,
        max_model_steps=limits.understanding_max_model_steps,
        max_tool_calls=limits.understanding_max_tool_calls,
        max_completion_corrections=limits.understanding_max_completion_corrections,
        max_output_tokens=limits.understanding_max_output_tokens,
        context_middleware=understanding_compaction,
    )
    publication = PublicationStore(memory_engine, artifacts)
    return BackgroundMemoryWorkflow(
        case_workflow,
        understanding_workflow,
        publication,
        checkpointer,
        max_stale_retries=limits.max_stale_retries,
    )
