"""V3-4R OpenRouter config + model/endpoints catalog tests (spec §5/§6/§14.2).

不打 live API;catalog HTTP 行為經 `httpx.MockTransport`,snapshot/preflight
全部走 committed fixtures。

規格:docs/plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4, uuid5

import httpx
import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json

from evals.interview_vnext.openrouter_model_catalog import (
    CATALOG_ARTIFACT_KIND,
    MODEL_SNAPSHOT_LABEL,
    CatalogProbeError,
    OpenRouterEndpointSnapshot,
    OpenRouterModelCatalogClient,
    OpenRouterModelSnapshot,
    PreflightError,
    build_catalog_snapshot_artifact,
    matched_endpoints,
    preflight,
)
from evals.interview_vnext.openrouter_provider_config import (
    DISABLED_PLUGINS,
    ConfigConstructionError,
    OpenRouterChatEvalConfig,
    OpenRouterProbeInputs,
    build_openrouter_eval_config,
)


FIXTURES = Path(__file__).parent / "fixtures" / "interview_vnext" / "openrouter_chat"
API_KEY = "sk-or-eval-test-not-a-real-key"
NOW = datetime(2026, 7, 17, 3, 0, 0, tzinfo=UTC)

REQUESTED_MODEL = "testlab/analyst-large"
ENDPOINT_SLUG = "testhost"


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text("utf-8"))


def model_snapshot(raw: dict[str, Any] | None = None) -> OpenRouterModelSnapshot:
    return OpenRouterModelSnapshot(
        requested_model=REQUESTED_MODEL,
        fetched_at=NOW,
        url_path=f"/model/{REQUESTED_MODEL}",
        http_request_id="req_fx_catalog_model",
        raw=raw if raw is not None else fixture_json("catalog-model.json"),
    )


def endpoint_snapshot(raw: dict[str, Any] | None = None) -> OpenRouterEndpointSnapshot:
    return OpenRouterEndpointSnapshot(
        requested_model=REQUESTED_MODEL,
        fetched_at=NOW,
        url_path=f"/models/{REQUESTED_MODEL}/endpoints",
        http_request_id="req_fx_catalog_endpoints",
        raw=raw if raw is not None else fixture_json("catalog-endpoints.json"),
    )


def probe_inputs(**overrides: Any) -> OpenRouterProbeInputs:
    values: dict[str, Any] = {
        "requested_model": REQUESTED_MODEL,
        "upstream_endpoint_slug": ENDPOINT_SLUG,
        "data_collection": "deny",
        "zdr_required": False,
        "reasoning_effort": "medium",
    }
    values.update(overrides)
    return OpenRouterProbeInputs(**values)


def build_config(**overrides: Any) -> OpenRouterChatEvalConfig:
    return build_openrouter_eval_config(
        probe_inputs(**overrides), model_snapshot(), endpoint_snapshot()
    )


def run_preflight(**overrides: Any):
    values: dict[str, Any] = {
        "model_snapshot": model_snapshot(),
        "endpoint_snapshot": endpoint_snapshot(),
        "requested_model": REQUESTED_MODEL,
        "upstream_endpoint_slug": ENDPOINT_SLUG,
        "reasoning_effort": "medium",
        "reasoning_max_tokens": None,
        "required_output_tokens": 4096,
        "now": NOW,
    }
    values.update(overrides)
    return preflight(**values)


class TestOpenRouterChatEvalConfig:
    def test_builder_derives_identity_and_hard_invariants(self):
        config = build_config()
        assert config.provider == "openrouter"
        assert config.api_format == "chat_completions"
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.requested_model == REQUESTED_MODEL
        assert config.catalog_canonical_model == "testlab/analyst-large-20260717"
        assert config.accepted_resolved_models == (REQUESTED_MODEL,)
        assert config.upstream_endpoint_slug == ENDPOINT_SLUG
        assert config.expected_upstream_provider_name == "TestHost"
        assert config.provider_order == (ENDPOINT_SLUG,)
        assert config.provider_only == (ENDPOINT_SLUG,)
        assert config.allow_fallbacks is False
        assert config.require_parameters is True
        assert config.reasoning_exclude is True
        assert config.stream is False
        assert config.choice_count == 1
        assert config.response_format == "json_schema"
        assert config.strict_schema is True
        assert config.router_metadata is True
        assert config.disabled_plugins == DISABLED_PLUGINS
        assert config.transport_retries == 0
        assert config.response_cache is False
        assert config.session_sticky_routing is False
        assert config.contains_test_data is True
        assert config.model_catalog_hash == model_snapshot().snapshot_hash
        assert config.endpoint_catalog_hash == endpoint_snapshot().snapshot_hash
        assert config.config_hash == build_config().config_hash

    def test_config_dump_and_hash_are_secret_free(self):
        config = build_config()
        dump = canonical_json(config)
        assert API_KEY not in dump
        assert "sk-or" not in dump
        assert "Authorization" not in dump
        for secret_field in ("api_key", "authorization", "workspace_secret"):
            assert secret_field not in OpenRouterChatEvalConfig.model_fields
            with pytest.raises(ValidationError):
                build_openrouter_eval_config(
                    probe_inputs(**{secret_field: "sk-or-secret"}),
                    model_snapshot(),
                    endpoint_snapshot(),
                )

    @pytest.mark.parametrize(
        "model",
        [
            "openrouter/auto",
            "openrouter/free",
            "testlab/analyst-large:free",
            "testlab/analyst-large:nitro",
            "testlab/analyst-large:floor",
            "testlab/analyst-large:online",
            "testlab/analyst-large:latest",
            "~testlab/analyst-large",
            "testlab/latest",
            "testlab/analyst-latest",
            " testlab/analyst-large",
            "testlab/analyst-large ",
            "no-author-slug",
            "testlab/analyst/large",
        ],
    )
    def test_alias_auto_free_latest_variant_shortcuts_rejected(self, model):
        with pytest.raises((ValidationError, ValueError)):
            probe_inputs(requested_model=model)

    def test_accepted_models_must_be_exactly_the_requested_model(self):
        config = build_config()
        for models in ((), (REQUESTED_MODEL, "testlab/analyst-mini"), ("testlab/other",)):
            with pytest.raises(ValidationError, match="accepted resolved models"):
                OpenRouterChatEvalConfig(
                    **{
                        **config.model_dump(),
                        "accepted_resolved_models": models,
                    }
                )

    def test_provider_lists_must_be_exactly_the_endpoint_slug(self):
        config = build_config()
        for field in ("provider_order", "provider_only"):
            for value in ((), (ENDPOINT_SLUG, "otherhost"), ("otherhost",)):
                with pytest.raises(ValidationError, match="endpoint slug"):
                    OpenRouterChatEvalConfig(
                        **{**config.model_dump(), field: value}
                    )

    def test_disabled_plugins_must_equal_fixed_tuple(self):
        config = build_config()
        for plugins in (
            (),
            DISABLED_PLUGINS[:-1],
            (*DISABLED_PLUGINS, "extra-plugin"),
            tuple(reversed(DISABLED_PLUGINS)),
        ):
            with pytest.raises(ValidationError, match="disabled plugins"):
                OpenRouterChatEvalConfig(
                    **{**config.model_dump(), "disabled_plugins": plugins}
                )

    def test_reasoning_effort_and_max_tokens_are_mutually_exclusive(self):
        with pytest.raises(ValidationError, match="mutually exclusive"):
            probe_inputs(reasoning_effort="medium", reasoning_max_tokens=4096)
        config = build_config()
        with pytest.raises(ValidationError, match="mutually exclusive"):
            OpenRouterChatEvalConfig(
                **{
                    **config.model_dump(),
                    "reasoning_effort": "medium",
                    "reasoning_max_tokens": 4096,
                }
            )
        assert build_config(reasoning_effort=None).reasoning_enabled is False

    def test_hard_invariants_cannot_be_overridden(self):
        config = build_config()
        for field, value in (
            ("provider", "openai"),
            ("allow_fallbacks", True),
            ("require_parameters", False),
            ("reasoning_exclude", False),
            ("stream", True),
            ("choice_count", 2),
            ("response_format", "json_object"),
            ("strict_schema", False),
            ("router_metadata", False),
            ("transport_retries", 1),
            ("response_cache", True),
            ("session_sticky_routing", True),
            ("contains_test_data", False),
            ("base_url", "https://example.com/v1"),
        ):
            with pytest.raises(ValidationError):
                OpenRouterChatEvalConfig(**{**config.model_dump(), field: value})

    def test_privacy_and_route_profile_enter_config_hash(self):
        base = build_config()
        assert base.config_hash != build_config(data_collection="allow").config_hash
        assert base.config_hash != build_config(zdr_required=True).config_hash
        assert base.config_hash != build_config(reasoning_effort="high").config_hash
        assert (
            base.config_hash
            != build_config(reasoning_effort=None, reasoning_max_tokens=2048).config_hash
        )

    def test_builder_rejects_foreign_or_ambiguous_snapshots(self):
        foreign_model = model_snapshot().model_copy(
            update={"requested_model": "testlab/other-model"}
        )
        with pytest.raises(ConfigConstructionError, match="model snapshot"):
            build_openrouter_eval_config(
                probe_inputs(), foreign_model, endpoint_snapshot()
            )
        missing_canonical = deepcopy(fixture_json("catalog-model.json"))
        missing_canonical["data"]["canonical_slug"] = None
        with pytest.raises(ConfigConstructionError, match="canonical_slug"):
            build_openrouter_eval_config(
                probe_inputs(), model_snapshot(missing_canonical), endpoint_snapshot()
            )
        with pytest.raises(ConfigConstructionError, match="exactly one endpoint"):
            build_openrouter_eval_config(
                probe_inputs(upstream_endpoint_slug="regionhost"),
                model_snapshot(),
                endpoint_snapshot(),
            )
        with pytest.raises(ConfigConstructionError, match="exactly one endpoint"):
            build_openrouter_eval_config(
                probe_inputs(upstream_endpoint_slug="missinghost"),
                model_snapshot(),
                endpoint_snapshot(),
            )

    def test_full_variant_slug_uniquely_matches(self):
        config = build_openrouter_eval_config(
            probe_inputs(upstream_endpoint_slug="regionhost/us"),
            model_snapshot(),
            endpoint_snapshot(),
        )
        assert config.upstream_endpoint_slug == "regionhost/us"
        assert config.expected_upstream_provider_name == "RegionHost"


class TestPreflightGates:
    def test_valid_snapshots_pass_and_expose_endpoint_identity(self):
        facts = run_preflight()
        assert facts.canonical_slug == "testlab/analyst-large-20260717"
        assert facts.endpoint.tag == ENDPOINT_SLUG
        assert facts.endpoint.provider_name == "TestHost"
        assert facts.model_context_length == 200000
        assert facts.top_provider_max_completion_tokens == 32000
        assert facts.limitations

    def test_model_id_mismatch_rejected(self):
        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["id"] = "testlab/analyst-mini"
        with pytest.raises(PreflightError, match="model_id_mismatch"):
            run_preflight(model_snapshot=model_snapshot(raw))

    def test_distinct_permanent_canonical_slug_is_captured_not_rejected(self):
        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["canonical_slug"] = "testlab/analyst-large-2026-07"
        facts = run_preflight(model_snapshot=model_snapshot(raw))
        assert facts.requested_model == REQUESTED_MODEL
        assert facts.canonical_slug == "testlab/analyst-large-2026-07"

    @pytest.mark.parametrize("canonical_slug", [None, "", "   "])
    def test_missing_permanent_canonical_slug_rejected(self, canonical_slug):
        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["canonical_slug"] = canonical_slug
        with pytest.raises(PreflightError, match="canonical_slug_missing"):
            run_preflight(model_snapshot=model_snapshot(raw))

    def test_expired_model_rejected(self):
        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["expiration_date"] = "2026-07-01T00:00:00Z"
        with pytest.raises(PreflightError, match="model_expired"):
            run_preflight(model_snapshot=model_snapshot(raw))
        raw["data"]["expiration_date"] = "2026-12-01T00:00:00Z"
        assert run_preflight(model_snapshot=model_snapshot(raw))

    def test_missing_text_modalities_rejected(self):
        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["architecture"]["output_modalities"] = ["image"]
        with pytest.raises(PreflightError, match="modalities_missing_text"):
            run_preflight(model_snapshot=model_snapshot(raw))

    @pytest.mark.parametrize(
        "removed", ["structured_outputs", "response_format", "max_tokens"]
    )
    def test_missing_model_capability_rejected(self, removed):
        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["supported_parameters"].remove(removed)
        with pytest.raises(PreflightError, match="model_parameters_missing"):
            run_preflight(model_snapshot=model_snapshot(raw))

    def test_reasoning_gates(self):
        raw = deepcopy(fixture_json("catalog-model.json"))
        del raw["data"]["reasoning"]
        with pytest.raises(PreflightError, match="reasoning_unsupported"):
            run_preflight(model_snapshot=model_snapshot(raw))
        assert run_preflight(
            model_snapshot=model_snapshot(raw), reasoning_effort=None
        )

        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["reasoning"] = {"supports_max_tokens": True}
        with pytest.raises(PreflightError, match="reasoning_effort_unsupported"):
            run_preflight(model_snapshot=model_snapshot(raw))

        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["reasoning"]["supported_efforts"] = ["low"]
        with pytest.raises(PreflightError, match="reasoning_effort_unsupported"):
            run_preflight(model_snapshot=model_snapshot(raw), reasoning_effort="medium")

        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["reasoning"]["supported_efforts"] = None
        assert run_preflight(
            model_snapshot=model_snapshot(raw), reasoning_effort="medium"
        )

        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["reasoning"]["supports_max_tokens"] = False
        with pytest.raises(PreflightError, match="reasoning_max_tokens_unsupported"):
            run_preflight(
                model_snapshot=model_snapshot(raw),
                reasoning_effort=None,
                reasoning_max_tokens=2048,
            )

    def test_reasoning_budget_must_fit_inside_output_budget(self):
        with pytest.raises(PreflightError, match="reasoning_budget_exceeds_output"):
            run_preflight(
                reasoning_effort=None,
                reasoning_max_tokens=4096,
                required_output_tokens=4096,
            )
        assert run_preflight(
            reasoning_effort=None,
            reasoning_max_tokens=2048,
            required_output_tokens=4096,
        )

    def test_context_budget_gates(self):
        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["top_provider"]["max_completion_tokens"] = 1024
        with pytest.raises(PreflightError, match="context_budget_exceeded"):
            run_preflight(model_snapshot=model_snapshot(raw))
        raw = deepcopy(fixture_json("catalog-model.json"))
        raw["data"]["context_length"] = 1024
        with pytest.raises(PreflightError, match="context_budget_exceeded"):
            run_preflight(model_snapshot=model_snapshot(raw))

    def test_endpoint_snapshot_gates(self):
        raw = deepcopy(fixture_json("catalog-endpoints.json"))
        raw["data"]["endpoints"] = []
        with pytest.raises(PreflightError, match="endpoints_empty"):
            run_preflight(endpoint_snapshot=endpoint_snapshot(raw))

        raw = deepcopy(fixture_json("catalog-endpoints.json"))
        raw["data"]["id"] = "testlab/other-model"
        with pytest.raises(PreflightError, match="endpoints_model_mismatch"):
            run_preflight(endpoint_snapshot=endpoint_snapshot(raw))

    def test_base_slug_matching_must_be_unique(self):
        snapshot = endpoint_snapshot()
        assert tuple(item.tag for item in matched_endpoints("regionhost", snapshot)) == (
            "regionhost/us",
            "regionhost/eu",
        )
        with pytest.raises(PreflightError, match="endpoint_match_ambiguous"):
            run_preflight(upstream_endpoint_slug="regionhost")
        with pytest.raises(PreflightError, match="endpoint_match_none"):
            run_preflight(upstream_endpoint_slug="missinghost")
        facts = run_preflight(upstream_endpoint_slug="regionhost/us")
        assert facts.endpoint.tag == "regionhost/us"

    def test_endpoint_level_capability_must_be_proven(self):
        # regionhost/eu lacks structured_outputs even though the model lists it.
        with pytest.raises(PreflightError, match="endpoint_parameters_missing"):
            run_preflight(upstream_endpoint_slug="regionhost/eu", reasoning_effort=None)

    def test_endpoint_must_support_reasoning_when_requested(self):
        raw = deepcopy(fixture_json("catalog-endpoints.json"))
        raw["data"]["endpoints"][0]["supported_parameters"].remove("reasoning")
        with pytest.raises(PreflightError, match="endpoint_parameters_missing"):
            run_preflight(endpoint_snapshot=endpoint_snapshot(raw))
        assert run_preflight(
            endpoint_snapshot=endpoint_snapshot(raw), reasoning_effort=None
        )

    def test_endpoint_missing_provider_identity_rejected(self):
        raw = deepcopy(fixture_json("catalog-endpoints.json"))
        del raw["data"]["endpoints"][0]["provider_name"]
        with pytest.raises(PreflightError, match="endpoint_missing_identity"):
            run_preflight(endpoint_snapshot=endpoint_snapshot(raw))


def catalog_client(handler) -> tuple[OpenRouterModelCatalogClient, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def transport_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        outcome = handler(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    client = OpenRouterModelCatalogClient(
        api_key=API_KEY,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)),
        now=lambda: NOW,
    )
    return client, calls


class TestCatalogClient:
    async def test_fetch_builds_snapshots_from_exact_urls(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/endpoints"):
                return httpx.Response(
                    200,
                    json=fixture_json("catalog-endpoints.json"),
                    headers={"x-request-id": "req_fx_catalog_endpoints"},
                )
            return httpx.Response(
                200,
                json=fixture_json("catalog-model.json"),
                headers={"x-request-id": "req_fx_catalog_model"},
            )

        client, calls = catalog_client(handler)
        model = await client.fetch_model(REQUESTED_MODEL)
        endpoints = await client.fetch_endpoints(REQUESTED_MODEL)
        await client.aclose()
        assert [str(call.url) for call in calls] == [
            f"https://openrouter.ai/api/v1/model/{REQUESTED_MODEL}",
            f"https://openrouter.ai/api/v1/models/{REQUESTED_MODEL}/endpoints",
        ]
        for call in calls:
            assert call.headers["authorization"] == f"Bearer {API_KEY}"
        assert model.http_request_id == "req_fx_catalog_model"
        assert endpoints.http_request_id == "req_fx_catalog_endpoints"
        assert model.raw == fixture_json("catalog-model.json")
        assert endpoints.raw == fixture_json("catalog-endpoints.json")

    @pytest.mark.parametrize("status", [401, 402, 429, 500, 503])
    async def test_catalog_http_failure_raises_and_never_reaches_inference(
        self, status
    ):
        client, calls = catalog_client(
            lambda request: httpx.Response(
                status,
                json={"error": {"message": "denied", "code": status}},
                headers={"x-request-id": f"req_fx_catalog_{status}"},
            )
        )
        with pytest.raises(CatalogProbeError) as excinfo:
            await client.fetch_model(REQUESTED_MODEL)
        await client.aclose()
        assert len(calls) == 1
        error = excinfo.value
        assert error.reason_code == "openrouter.catalog_probe_failed"
        assert error.http_status == status
        assert error.request_id == f"req_fx_catalog_{status}"

    async def test_catalog_transport_and_decode_failures_raise(self):
        client, _ = catalog_client(
            lambda request: httpx.ConnectError("connection refused")
        )
        with pytest.raises(CatalogProbeError, match="transport failure"):
            await client.fetch_model(REQUESTED_MODEL)
        await client.aclose()

        client, _ = catalog_client(
            lambda request: httpx.Response(200, text="<html>gateway</html>")
        )
        with pytest.raises(CatalogProbeError, match="non-JSON"):
            await client.fetch_model(REQUESTED_MODEL)
        await client.aclose()


class TestCatalogSnapshotArtifact:
    def test_artifact_is_run_scoped_deterministic_and_secret_free(self):
        run_id = uuid4()
        session_id = uuid5(run_id, "session")
        snapshot = model_snapshot()
        record = build_catalog_snapshot_artifact(
            snapshot, run_id=run_id, session_id=session_id, created_at=NOW
        )
        assert record.ref.artifact_id == uuid5(
            run_id, f"{MODEL_SNAPSHOT_LABEL}/{REQUESTED_MODEL}"
        )
        assert record.ref.kind == CATALOG_ARTIFACT_KIND
        assert record.run_id == run_id
        assert record.session_id == session_id
        assert record.attempt_id is None
        assert record.operation_id is None
        assert record.retention_class == "eval"
        assert record.contains_test_data is True
        assert record.ref.content_hash == snapshot.snapshot_hash
        assert record.ref.content_hash == canonical_hash(snapshot)
        assert API_KEY not in record.inline_content
        assert "Authorization" not in record.inline_content
