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

from .conversation_sources import ConversationSourceService
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
    case_max_model_steps: int,
    case_max_tool_calls: int,
    case_max_chars: int,
    case_context_chars: int,
    case_max_windows: int,
    understanding_max_model_steps: int,
    understanding_max_tool_calls: int,
    max_stale_retries: int,
) -> BackgroundMemoryWorkflow:
    """Bind one document without choosing a provider or opening resources.

    The limits are deliberately explicit. Current decisions have not adopted
    the old extraction role's numbers as the formal B1/B2 product profile, so
    this boundary must not silently turn package test defaults into policy.
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
    case_workflow = CaseMaintenanceWorkflow(
        reader,
        case_session,
        case_model,
        checkpointer,
        max_model_steps=case_max_model_steps,
        max_tool_calls=case_max_tool_calls,
        max_chars=case_max_chars,
        context_chars=case_context_chars,
        max_windows=case_max_windows,
    )
    understanding_session = UnderstandingMaintenanceSession(
        artifacts,
        case_session,
    )
    understanding_workflow = UnderstandingMaintenanceWorkflow(
        reader,
        understanding_session,
        understanding_model,
        checkpointer,
        max_model_steps=understanding_max_model_steps,
        max_tool_calls=understanding_max_tool_calls,
    )
    publication = PublicationStore(memory_engine, artifacts)
    return BackgroundMemoryWorkflow(
        case_workflow,
        understanding_workflow,
        publication,
        checkpointer,
        max_stale_retries=max_stale_retries,
    )
