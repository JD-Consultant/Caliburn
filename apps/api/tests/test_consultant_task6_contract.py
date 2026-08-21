"""Task 6 contract tests for the virtual-JD model interface."""

from __future__ import annotations

import inspect
from decimal import Decimal
from uuid import uuid4

import pytest
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

import app.consultant.provider_wire as provider_wire
from app.config import Settings
from app.consultant.agent import LookupWaveLimitExceeded, LookupWaveLimitMiddleware
from app.consultant.candidate_publication import CandidateCheckResult
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    OutputTokenParameter,
    RunPolicy,
    build_consultant_middleware,
    resolve_execution,
)
from app.consultant.workspace_tools import _serialize_check_result


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
        allowed_tool_ids=(
            "ls",
            "read_file",
            "grep",
            "write_file",
            "edit_file",
            "delete",
            "check_candidate_document",
        ),
        max_context_tokens=24_000,
        max_model_calls=max_model_calls,
        max_lookup_waves=2,
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
        "candidate_check_binding",
    }


def test_configured_execution_defaults_to_exactly_the_seven_model_tools() -> None:
    from app.consultant.run_service import build_configured_execution

    execution = build_configured_execution(Settings())
    assert execution.max_model_calls == 8
    assert execution.allowed_tool_ids == (
        "ls",
        "read_file",
        "grep",
        "write_file",
        "edit_file",
        "delete",
        "check_candidate_document",
    )


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


def test_check_observation_is_compact_and_does_not_expose_receipt_or_changeset() -> None:
    result = CandidateCheckResult.model_construct(
        status="checked",
        run_id=uuid4(),
        candidate_revision=3,
        resource_digest="a" * 64,
        action_handles=("action-001",),
        actions=(),
        receipt={"changeset": {"actions": [{"before": "secret"}]}},
        issues=(),
        review_queue={},
    )

    payload = _serialize_check_result(result)

    assert "receipt" not in payload
    assert "changeset" not in payload
    assert "secret" not in payload
    assert '"status":"checked"' in payload
    assert '"action_handles":["action-001"]' in payload
    assert "action_ids" not in payload
    assert str(result.run_id) not in payload


def test_lookup_wave_counts_only_path_aware_external_workspace_reads() -> None:
    middleware = LookupWaveLimitMiddleware(
        tool_names=frozenset({"ls", "read_file", "grep"}),
        run_limit=2,
    )
    candidate_read = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/candidate/run-1/job.json"},
                        "id": "candidate-read",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }
    external_read = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/sources/current/source-001.txt"},
                        "id": "source-read",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }

    assert middleware.after_model(candidate_read, runtime=None) is None  # type: ignore[arg-type]
    assert middleware.after_model(external_read, runtime=None) == {
        "run_lookup_wave_count": 1
    }


def test_composite_grep_paths_consume_lookup_waves_but_candidate_grep_does_not() -> None:
    middleware = LookupWaveLimitMiddleware(
        tool_names=frozenset({"ls", "read_file", "grep"}),
        run_limit=2,
    )

    def state(path: str | None, count: int = 0) -> dict[str, object]:
        args = {} if path is None else {"path": path}
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "grep",
                            "args": args,
                            "id": "grep",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "run_lookup_wave_count": count,
        }

    assert middleware.after_model(state(None), runtime=None) == {
        "run_lookup_wave_count": 1
    }
    assert middleware.after_model(state("/", count=1), runtime=None) == {
        "run_lookup_wave_count": 2
    }
    assert middleware.after_model(
        state("/candidate/run-1", count=2), runtime=None
    ) is None
    with pytest.raises(LookupWaveLimitExceeded):
        middleware.after_model(state(None, count=2), runtime=None)


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
