"""V3-4 OpenAI Responses eval adapter — mocked-HTTP conformance tests.

規格:docs/plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md
不打 live API;所有 provider 行為經 httpx mock + 官方 SDK deserialization。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4, uuid5

import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.operation_documents import turn_interpret_operation
from app.interview_vnext.llm.port import MessageRole, ModelCallRequest, ModelMessage
from app.interview_vnext.llm.schema_exports import published_schema
from app.interview_vnext.observability.artifacts import ArtifactRef

from evals.interview_vnext.provider_config import OpenAIResponsesEvalConfig
from evals.interview_vnext.schema_catalog import (
    TURN_INTERPRET_OUTPUT_SCHEMA_ID,
    CatalogEntry,
    PublishedOutputSchemaCatalog,
    SchemaCatalogError,
)


RUN_ID = uuid5(uuid4(), "run")  # fresh per test session, stable within it
CREATED_AT = datetime(2026, 7, 17, 3, 0, 0, tzinfo=UTC)


def _text_ref(text: str, *, kind: str) -> ArtifactRef:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return ArtifactRef(
        artifact_id=uuid4(),
        kind=kind,
        media_type="text/markdown",
        content_hash=f"sha256:{digest}",
        byte_size=len(text.encode("utf-8")),
    )


def _json_ref(payload: Any, *, kind: str, schema_id: str | None = None) -> ArtifactRef:
    content = canonical_json(payload)
    return ArtifactRef(
        artifact_id=uuid4(),
        kind=kind,
        media_type="application/json",
        schema_id=schema_id,
        content_hash=canonical_hash(payload),
        byte_size=len(content.encode("utf-8")),
    )


def make_request(**overrides: Any) -> ModelCallRequest:
    operation = turn_interpret_operation()
    schema = published_schema("turn-interpret-output.v1.schema.json")
    attempt_id = overrides.pop("attempt_id", uuid4())
    values: dict[str, Any] = {
        "run_id": RUN_ID,
        "session_id": uuid4(),
        "turn_id": uuid4(),
        "operation_id": uuid4(),
        "attempt_id": attempt_id,
        "attempt": 1,
        "operation_name": operation.name,
        "operation_definition_hash": operation.definition_hash,
        "idempotency_key": f"turn-interpret/{attempt_id}/1",
        "provider": "openai",
        "requested_model": "gpt-5.6",
        "quality_profile": operation.quality_profile,
        "instructions": "You are the Caliburn turn interpreter. Test-only instructions.",
        "messages": (
            ModelMessage(role=MessageRole.USER, text="synthetic employee turn (test)"),
        ),
        "prompt_artifact": _text_ref("test-only prompt", kind="model.prompt"),
        "output_schema_id": TURN_INTERPRET_OUTPUT_SCHEMA_ID,
        "output_schema_artifact": _json_ref(
            schema, kind="model.output_schema", schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID
        ),
        "context_artifact": _json_ref({"context": "synthetic"}, kind="model.context"),
        "selection_manifest_artifact": _json_ref(
            {"selection": "synthetic"}, kind="model.selection_manifest"
        ),
        "deadline_at": CREATED_AT + timedelta(seconds=60),
        "created_at": CREATED_AT,
        "max_output_tokens": operation.max_output_tokens,
    }
    values.update(overrides)
    return ModelCallRequest(**values)


class TestOpenAIResponsesEvalConfig:
    def test_default_dump_and_hash_cover_hard_invariants(self):
        config = OpenAIResponsesEvalConfig()
        assert config.config_hash == OpenAIResponsesEvalConfig().config_hash
        dump = config.model_dump(mode="json")
        assert dump["schema_version"] == "openai_responses_eval_config.v1"
        assert dump["provider"] == "openai"
        assert dump["requested_model"] == "gpt-5.6"
        assert dump["accepted_resolved_models"] == ["gpt-5.6", "gpt-5.6-sol"]
        assert dump["reasoning_mode"] == "standard"
        assert dump["reasoning_effort"] == "medium"
        assert dump["service_tier"] == "default"
        assert dump["store"] is False
        assert dump["background"] is False
        assert dump["stream"] is False
        assert dump["truncation"] == "disabled"
        assert dump["sdk_max_retries"] == 0
        assert dump["contains_test_data"] is True

    def test_config_hash_tracks_versionable_eval_knobs(self):
        default = OpenAIResponsesEvalConfig()
        assert default.config_hash != OpenAIResponsesEvalConfig(
            reasoning_effort="high"
        ).config_hash
        assert default.config_hash != OpenAIResponsesEvalConfig(
            requested_model="gpt-5.6-sol"
        ).config_hash

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("provider", "anthropic"),
            ("reasoning_mode", "pro"),
            ("service_tier", "auto"),
            ("store", True),
            ("background", True),
            ("stream", True),
            ("truncation", "auto"),
            ("sdk_max_retries", 2),
            ("contains_test_data", False),
        ],
    )
    def test_hard_invariants_cannot_be_overridden(self, field, value):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(**{field: value})

    def test_config_is_frozen(self):
        config = OpenAIResponsesEvalConfig()
        with pytest.raises(ValidationError):
            config.requested_model = "gpt-5.6-sol"

    def test_secret_fields_are_rejected_and_absent(self):
        for secret_field in ("api_key", "organization", "project"):
            assert secret_field not in OpenAIResponsesEvalConfig.model_fields
            with pytest.raises(ValidationError):
                OpenAIResponsesEvalConfig(**{secret_field: "sk-eval-secret"})
        assert "sk-" not in canonical_json(OpenAIResponsesEvalConfig())

    @pytest.mark.parametrize(
        "models",
        [
            (),
            ("gpt-5.6", "gpt-5.6"),
            ("gpt-5.6-sol", "gpt-5.6"),
        ],
    )
    def test_accepted_resolved_models_must_be_nonempty_unique_sorted(self, models):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(accepted_resolved_models=models)

    def test_requested_model_need_not_be_in_allowlist(self):
        config = OpenAIResponsesEvalConfig(
            requested_model="gpt-5.6",
            accepted_resolved_models=("gpt-5.6-sol",),
        )
        assert config.requested_model not in config.accepted_resolved_models

    @pytest.mark.parametrize("seconds", [0.0, -1.0, 120.0])
    def test_connect_timeout_bounds(self, seconds):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(connect_timeout_seconds=seconds)


class TestPublishedOutputSchemaCatalog:
    def test_resolve_returns_exact_published_schema_and_hash(self):
        request = make_request()
        binding = PublishedOutputSchemaCatalog().resolve(request)
        assert binding.schema_id == TURN_INTERPRET_OUTPUT_SCHEMA_ID
        assert binding.openai_format_name == "turn_interpret_output_v1"
        assert binding.schema == published_schema("turn-interpret-output.v1.schema.json")
        assert binding.schema_hash == request.output_schema_hash
        assert canonical_hash(binding.schema) == request.output_schema_hash
        operation = turn_interpret_operation()
        assert binding.schema_hash == operation.output_contract.content_hash

    def test_resolve_returns_a_fresh_deep_copy(self):
        catalog = PublishedOutputSchemaCatalog()
        first = catalog.resolve(make_request())
        first.schema["properties"].clear()
        second = catalog.resolve(make_request())
        assert second.schema == published_schema("turn-interpret-output.v1.schema.json")

    def test_unknown_schema_id_fails_closed(self):
        request = make_request(
            output_schema_id="https://caliburn.local/schemas/unknown.v1.schema.json"
        )
        with pytest.raises(SchemaCatalogError, match="unknown output schema id"):
            PublishedOutputSchemaCatalog().resolve(request)

    def test_schema_hash_mismatch_fails_closed(self):
        tampered = published_schema("turn-interpret-output.v1.schema.json")
        tampered["properties"]["tampered"] = {"type": "string"}
        request = make_request(
            output_schema_artifact=_json_ref(
                tampered,
                kind="model.output_schema",
                schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID,
            )
        )
        with pytest.raises(SchemaCatalogError, match="hash does not match"):
            PublishedOutputSchemaCatalog().resolve(request)

    def test_catalog_entry_with_foreign_id_fails_on_schema_id(self):
        catalog = PublishedOutputSchemaCatalog(
            {
                TURN_INTERPRET_OUTPUT_SCHEMA_ID: CatalogEntry(
                    filename="turn-interpret-input.v1.schema.json",
                    openai_format_name="turn_interpret_output_v1",
                )
            }
        )
        with pytest.raises(SchemaCatalogError, match=r"\$id does not match"):
            catalog.resolve(make_request())

    def test_non_portable_published_schema_fails_lint(self):
        input_schema_id = (
            "https://caliburn.local/schemas/turn-interpret-input.v1.schema.json"
        )
        input_schema = published_schema("turn-interpret-input.v1.schema.json")
        catalog = PublishedOutputSchemaCatalog(
            {
                input_schema_id: CatalogEntry(
                    filename="turn-interpret-input.v1.schema.json",
                    openai_format_name="turn_interpret_input_v1",
                )
            }
        )
        request = make_request(
            output_schema_id=input_schema_id,
            output_schema_artifact=_json_ref(
                input_schema, kind="model.output_schema", schema_id=input_schema_id
            ),
        )
        with pytest.raises(SchemaCatalogError, match="not portable"):
            catalog.resolve(request)

    def test_operation_name_mismatch_fails_closed(self):
        request = make_request(operation_name="turn.receive")
        with pytest.raises(SchemaCatalogError, match="operation name"):
            PublishedOutputSchemaCatalog().resolve(request)

    def test_operation_definition_hash_mismatch_fails_closed(self):
        request = make_request(
            operation_definition_hash=f"sha256:{'0' * 64}",
        )
        with pytest.raises(SchemaCatalogError, match="definition hash"):
            PublishedOutputSchemaCatalog().resolve(request)
