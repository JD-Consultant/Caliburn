"""Task 6 contract tests for the persistent JD working-draft model interface."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

import app.consultant.provider_wire as provider_wire
from app.config import Settings
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    OutputTokenParameter,
    RunPolicy,
    build_consultant_middleware,
    resolve_execution,
)
from app.consultant.results import ConsultantResult, DocumentChangeOperation
from app.consultant.state import (
    ConsultantCommandContext,
    ConsultantThreadState,
    DocumentPatchAction,
    DocumentPatchOperation,
)
from app.consultant.views import ConsultantSnapshot
from app.consultant.workspace_backend import ConsultantWorkspaceBackendBinding
from app.consultant.workspace_resources import WorkspaceDocumentDraft
from app.consultant.workspace_tools import (
    WORKSPACE_FILESYSTEM_TOOL_NAMES,
    WORKSPACE_TOOL_NAMES,
)


EXPECTED_WORKSPACE_TOOLS = frozenset(
    {"ls", "read_file", "grep", "write_file", "edit_file", "delete"}
)
_QUEUE_FIELD = "review" + "_" + "queue"
_CHECKPOINT_RECEIPT_FIELD = "checked" + "_" + "candidate"
_PUBLICATION_FIELD = "candidate" + "_" + "publication"
_PENDING_BACKEND_FIELD = "pending" + "_" + "backend"
_CANDIDATE_BACKEND_FIELD = "candidate" + "_" + "backend"


def _execution(*, max_model_calls: int = 8):
    profile = ConsultantModelProfile(
        profile_id="primary-consultant",
        revision=1,
        requested_model="anthropic/claude-opus-5",
        provider_allowlist=("Anthropic",),
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=4096,
        output_token_parameter=OutputTokenParameter.MAX_TOKENS,
        reasoning_effort="high",
        timeout_seconds=90,
    )
    policy = RunPolicy(
        policy_id="interactive-consultation",
        revision=1,
        run_kind="interactive_consultation",
        allowed_skill_ids=("work-discovery",),
        allowed_tool_ids=tuple(sorted(EXPECTED_WORKSPACE_TOOLS)),
        max_context_tokens=24_000,
        max_model_calls=max_model_calls,
        max_total_tool_calls=24,
        model_retry_count=0,
        tool_retry_count=0,
        max_elapsed_seconds=180,
        max_total_tokens=32_000,
        max_cost_usd=Decimal("2.00"),
    )
    return resolve_execution(profile, policy)


def test_agent_builder_has_only_the_workspace_binding_seams() -> None:
    from app.consultant.agent import build_professional_consultant_agent

    parameter_names = set(inspect.signature(build_professional_consultant_agent).parameters)
    assert parameter_names == {
        "model",
        "execution",
        "selected_skill_ids",
        "context_middleware",
        "context_schema",
        "workspace_binding",
    }


def test_workspace_codec_has_no_model_authored_review_group_payload() -> None:
    assert "review_groups" not in WorkspaceDocumentDraft.model_fields


def test_configured_execution_defaults_to_exactly_the_six_model_tools() -> None:
    from app.consultant.run_service import build_configured_execution

    execution = build_configured_execution(Settings())
    assert execution.allowed_tool_ids == (
        "ls",
        "read_file",
        "grep",
        "write_file",
        "edit_file",
        "delete",
    )


def test_configured_tool_budget_allows_observed_workspace_workflow() -> None:
    from app.consultant.run_service import build_configured_execution

    execution = build_configured_execution(Settings())
    middleware = build_consultant_middleware(
        model=FakeMessagesListChatModel(responses=[]),
        execution=execution,
    )
    limit = next(
        item for item in middleware if isinstance(item, ToolCallLimitMiddleware)
    )
    state: dict[str, object] = {}
    waves = (
        (
            "read_file",
            "ls",
            "read_file",
            "read_file",
            "read_file",
            "read_file",
            "read_file",
            "read_file",
            "read_file",
        ),
        ("read_file", "read_file", "ls", "ls", "ls"),
        ("edit_file",),
        ("read_file", "read_file"),
    )

    call_index = 0
    for wave in waves:
        calls = []
        for name in wave:
            call_index += 1
            calls.append(
                {
                    "name": name,
                    "args": {},
                    "id": f"workspace-{call_index}",
                    "type": "tool_call",
                }
            )
        state["messages"] = [AIMessage(content="", tool_calls=calls)]
        state.update(limit.after_model(state, runtime=None) or {})  # type: ignore[arg-type]

    assert state["run_tool_call_count"] == {"__all__": 17}


def test_configured_tool_budget_allows_forty_eight_and_rejects_forty_ninth() -> None:
    from app.consultant.run_service import build_configured_execution

    execution = build_configured_execution(Settings())
    middleware = build_consultant_middleware(
        model=FakeMessagesListChatModel(responses=[]),
        execution=execution,
    )
    limit = next(
        item for item in middleware if isinstance(item, ToolCallLimitMiddleware)
    )
    first_forty_eight = [
        {
            "name": "read_file",
            "args": {},
            "id": f"bounded-{index}",
            "type": "tool_call",
        }
        for index in range(1, 49)
    ]
    state: dict[str, object] = {
        "messages": [AIMessage(content="", tool_calls=first_forty_eight)]
    }

    state.update(limit.after_model(state, runtime=None) or {})  # type: ignore[arg-type]
    state["messages"] = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "read_file",
                    "args": {},
                    "id": "bounded-49",
                    "type": "tool_call",
                }
            ],
        )
    ]

    with pytest.raises(ToolCallLimitExceededError, match=r"49/48 calls"):
        limit.after_model(state, runtime=None)  # type: ignore[arg-type]


def test_provider_evidence_has_handle_quote_occurrence_without_model_offsets() -> None:
    assert getattr(provider_wire, "Output" + "QuoteAnchor", None) is None
    basis = provider_wire.OutputAnalysisBasis(
        evidence=(
            provider_wire.OutputEvidenceReference(
                source_handle="source-001",
                quote="核對訂單",
                occurrence=2,
                skill_ids=("work-discovery",),
            ),
        )
    )
    assert basis.evidence[0].source_handle == "source-001"
    assert basis.evidence[0].occurrence == 2


def test_execution_preserves_reasoning_and_output_token_configuration() -> None:
    execution = _execution()

    assert execution.effective_parameters.max_tokens == 4096
    assert execution.effective_parameters.max_completion_tokens is None
    assert execution.effective_parameters.reasoning is not None
    assert execution.effective_parameters.reasoning.effort == "high"
    assert execution.effective_parameters.reasoning.exclude is True


def test_framework_model_call_limit_allows_eight_and_rejects_ninth() -> None:
    execution = _execution()
    middleware = build_consultant_middleware(
        model=FakeMessagesListChatModel(responses=[]),
        execution=execution,
    )
    limit = next(
        item for item in middleware if isinstance(item, ModelCallLimitMiddleware)
    )
    state: dict[str, object] = {}
    for _ in range(8):
        assert limit.before_model(state, runtime=None) is None  # type: ignore[arg-type]
        state.update(limit.after_model(state, runtime=None) or {})  # type: ignore[arg-type]
    with pytest.raises(ModelCallLimitExceededError, match=r"run limit \(8/8\)"):
        limit.before_model(state, runtime=None)  # type: ignore[arg-type]


def test_model_tool_surface_is_exactly_the_six_filesystem_verbs() -> None:
    assert WORKSPACE_FILESYSTEM_TOOL_NAMES == EXPECTED_WORKSPACE_TOOLS
    assert WORKSPACE_TOOL_NAMES == EXPECTED_WORKSPACE_TOOLS


def test_checkpoint_and_command_context_have_no_old_review_lifecycle_fields() -> None:
    state_fields = set(ConsultantThreadState.__annotations__)
    command_fields = set(ConsultantCommandContext.__annotations__)
    assert _QUEUE_FIELD not in state_fields
    assert _CHECKPOINT_RECEIPT_FIELD not in state_fields
    assert _QUEUE_FIELD not in command_fields
    assert _CHECKPOINT_RECEIPT_FIELD not in command_fields
    assert not any("candidate" in str(value) for value in command_fields)


def test_result_models_do_not_echo_application_publication_state() -> None:
    assert _PUBLICATION_FIELD not in ConsultantResult.model_fields
    from app.consultant.model_output import ConsultantModelOutput

    assert _PUBLICATION_FIELD not in ConsultantModelOutput.model_fields


def test_snapshot_and_backend_binding_expose_only_derived_review() -> None:
    assert _QUEUE_FIELD not in ConsultantSnapshot.model_fields
    assert _PENDING_BACKEND_FIELD not in ConsultantWorkspaceBackendBinding.__dataclass_fields__
    assert not hasattr(ConsultantWorkspaceBackendBinding, _CANDIDATE_BACKEND_FIELD)
    assert not hasattr(ConsultantWorkspaceBackendBinding, "current_run_catalog")


def test_document_operations_use_general_dependency_aware_actions() -> None:
    expected = {"add", "revise", "withdraw", "reassign", "reorder"}
    assert {operation.value for operation in DocumentChangeOperation} == expected
    assert {operation.value for operation in DocumentPatchOperation} == expected
    target_field = "target_" + "ids"
    assert target_field not in DocumentPatchAction.model_fields
