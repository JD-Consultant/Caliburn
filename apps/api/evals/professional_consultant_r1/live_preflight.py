"""R1 Segment 4 disposable live preflight.

本模組是一次性實驗儀器，不是 production provider framework。先放 pure catalog／
response seams；CLI 與真實請求接線只使用丟棄式案例。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from .assembler import AssembledStage
from .blind_grader import (
    build_blind_packets,
    build_grader_stage,
    merge_grader_passes,
)
from .capture import TrialCapture, verify_manifest
from .contracts import canonical_hash
from .matrix import arm_by_id, build_observation_plans
from .provider_request import ProviderConfig, build_chat_request
from .routing_facts import normalize_route_facts
from .runner import (
    HarnessFailure,
    ModelOutputFailure,
    ObservationResult,
    run_observation,
)
from .transport import OUTCOME_OK, WireResult, build_client, send_once

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DISPOSABLE_CASE_ID = "R1-PREFLIGHT-DISPOSABLE"
# owner 於 2026-07-27 將 disposable preflight 上限提高為 US$1。
MAX_PREFLIGHT_COST = Decimal("1.00")

MODEL_PROFILES = {
    "strongest": ("openai/gpt-5.6-sol-pro", "openai/flex"),
    "economical": ("openai/gpt-5.6-luna-pro", "openai/flex"),
    "grader": ("anthropic/claude-opus-5", "anthropic"),
}

REQUIRED_PARAMETERS = frozenset(
    {"max_tokens", "reasoning", "response_format", "structured_outputs"}
)

DISPOSABLE_CASE: dict[str, Any] = {
    "schema_id": "professional-consultant-r1-disposable-preflight.v1",
    "case_id": DISPOSABLE_CASE_ID,
    "case_revision": 1,
    "source_type": "constructed_edge",
    "case_family_id": DISPOSABLE_CASE_ID,
    "sources": [
        {
            "source_id": "turn-001",
            "source_kind": "consultant_turn",
            "text": "請描述一項你目前固定負責、完成後有明確結果的工作。",
        },
        {
            "source_id": "turn-002",
            "source_kind": "employee_turn",
            "text": "我每週整理客服回報，找出重複問題並交付問題趨勢摘要，讓產品團隊決定修正順序。",
        },
    ],
    "initial_work_model": {"task_candidates": []},
}


@dataclass(frozen=True)
class CatalogBinding:
    requested_model: str
    canonical_model: str
    endpoint_tag: str
    provider_name: str
    prompt_price: str
    completion_price: str
    snapshot_hash: str
    model_snapshot: dict[str, Any]
    endpoint_snapshot: dict[str, Any]


def _object_at(payload: Any, *path: str) -> dict[str, Any]:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            raise ValueError(f"catalog path {'.'.join(path)} was not an object")
        current = current.get(key)
    if not isinstance(current, dict):
        raise ValueError(f"catalog path {'.'.join(path)} was not an object")
    return current


def select_catalog_binding(
    model_payload: Any,
    endpoints_payload: Any,
    *,
    requested_model: str,
    endpoint_tag: str,
    required_parameters: set[str],
) -> CatalogBinding:
    """從當次官方 snapshots 選出恰一個 exact endpoint；任何缺漏都 fail closed。"""

    model = _object_at(model_payload, "data")
    if model.get("id") != requested_model:
        raise ValueError("catalog model id did not match the requested model")
    canonical = model.get("canonical_slug")
    if not isinstance(canonical, str) or not canonical:
        raise ValueError("catalog did not provide a canonical model slug")
    model_parameters = set(model.get("supported_parameters") or [])
    missing_model = required_parameters - model_parameters
    if missing_model:
        raise ValueError(f"model missing required parameters: {sorted(missing_model)}")

    endpoint_root = _object_at(endpoints_payload, "data")
    endpoints = endpoint_root.get("endpoints")
    if not isinstance(endpoints, list):
        raise ValueError("endpoint catalog did not contain an endpoints array")
    matches = [
        item
        for item in endpoints
        if isinstance(item, dict) and item.get("tag") == endpoint_tag
    ]
    if len(matches) != 1:
        raise ValueError(
            f"endpoint tag {endpoint_tag!r} matched {len(matches)} catalog entries"
        )
    endpoint = matches[0]
    endpoint_parameters = set(endpoint.get("supported_parameters") or [])
    missing_endpoint = required_parameters - endpoint_parameters
    if missing_endpoint:
        raise ValueError(
            f"endpoint missing required parameters: {sorted(missing_endpoint)}"
        )
    provider_name = endpoint.get("provider_name")
    if not isinstance(provider_name, str) or not provider_name:
        raise ValueError("endpoint catalog did not provide provider_name")
    pricing = endpoint.get("pricing")
    if not isinstance(pricing, dict):
        raise ValueError("endpoint catalog did not provide pricing")
    prompt_price = pricing.get("prompt")
    completion_price = pricing.get("completion")
    if not isinstance(prompt_price, str) or not isinstance(completion_price, str):
        raise ValueError("endpoint pricing was not expressed as decimal strings")

    return CatalogBinding(
        requested_model=requested_model,
        canonical_model=canonical,
        endpoint_tag=endpoint_tag,
        provider_name=provider_name,
        prompt_price=prompt_price,
        completion_price=completion_price,
        snapshot_hash=canonical_hash({"model": model, "endpoint": endpoint}),
        model_snapshot=model,
        endpoint_snapshot=endpoint,
    )


def parse_chat_payload(response_body: Any) -> Any:
    """解析 Chat Completions 的單一 structured-output message。

    只處理 provider envelope；輸出 schema 仍由 runner 的 local verifier 負責。
    """

    if not isinstance(response_body, dict):
        raise ValueError("chat response was not an object")
    choices = response_body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("chat response must contain exactly one choice")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ValueError("chat choice was not an object")
    if choice.get("finish_reason") not in ("stop", None):
        raise ModelOutputFailure(
            f"chat response did not finish cleanly: {choice.get('finish_reason')!r}"
        )
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("chat response did not contain a message object")
    if message.get("tool_calls"):
        raise ModelOutputFailure("chat response unexpectedly contained tool calls")
    content = message.get("content")
    if not isinstance(content, str):
        raise ModelOutputFailure("chat message content was not a string")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ModelOutputFailure(
            f"chat message content was not valid JSON: {exc}"
        ) from exc


def parse_grader_payload(
    payload: Any,
    *,
    expected_labels: set[str],
    expected_dimensions: set[str],
) -> dict[str, dict[str, str]]:
    """把 grader schema output 收斂成 merge_grader_passes() 的精確形狀。"""

    if not isinstance(payload, dict) or not isinstance(payload.get("grades"), list):
        raise ValueError("grader output did not contain a grades array")
    parsed: dict[str, dict[str, str]] = {}
    for grade in payload["grades"]:
        if not isinstance(grade, dict):
            raise ValueError("grader grade was not an object")
        label = grade.get("label")
        if not isinstance(label, str) or label in parsed:
            raise ValueError("grader labels were missing or duplicated")
        dimensions = grade.get("dimensions")
        if not isinstance(dimensions, list):
            raise ValueError("grader dimensions were not an array")
        values: dict[str, str] = {}
        for item in dimensions:
            if not isinstance(item, dict):
                raise ValueError("grader dimension was not an object")
            dimension = item.get("dimension")
            verdict = item.get("verdict")
            if (
                not isinstance(dimension, str)
                or dimension in values
                or verdict not in ("pass", "fail", "unknown")
            ):
                raise ValueError("grader dimensions were invalid or duplicated")
            values[dimension] = verdict
        if set(values) != expected_dimensions:
            raise ValueError("grader dimensions did not match the requested dimensions")
        parsed[label] = values
    if set(parsed) != expected_labels:
        raise ValueError("grader labels did not match the anonymous candidates")
    return parsed


def _load_env_value(path: Path, name: str) -> str:
    if not path.exists():
        raise ValueError(f"env file does not exist: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith(f"{name}="):
            value = raw.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value
    raise ValueError(f"{name} is missing or empty in {path}")


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    api_key: str,
) -> dict[str, Any]:
    response = await client.get(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    if response.status_code != 200:
        raise HarnessFailure(f"catalog GET failed: HTTP {response.status_code} {url}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise HarnessFailure(f"catalog GET returned a non-object: {url}")
    return payload


async def fetch_catalog_binding(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    requested_model: str,
    endpoint_tag: str,
) -> CatalogBinding:
    author, slug = requested_model.split("/", 1)
    model_payload = await _get_json(
        client,
        f"{OPENROUTER_BASE_URL}/model/{author}/{slug}",
        api_key=api_key,
    )
    endpoints_payload = await _get_json(
        client,
        f"{OPENROUTER_BASE_URL}/models/{author}/{slug}/endpoints",
        api_key=api_key,
    )
    return select_catalog_binding(
        model_payload,
        endpoints_payload,
        requested_model=requested_model,
        endpoint_tag=endpoint_tag,
        required_parameters=set(REQUIRED_PARAMETERS),
    )


def _attest_route(
    wire: WireResult,
    binding: CatalogBinding,
) -> tuple[str, str]:
    if wire.outcome != OUTCOME_OK or not isinstance(wire.body, dict):
        raise HarnessFailure(
            f"provider request failed before quality evaluation: {wire.outcome} "
            f"{wire.error_message or ''}".strip()
        )
    metadata = wire.body.get("openrouter_metadata")
    facts = normalize_route_facts(
        metadata,
        headers=wire.headers,
        requested_model=binding.canonical_model,
    )
    if not isinstance(metadata, dict):
        raise HarnessFailure("response did not contain openrouter_metadata")
    if metadata.get("requested") != binding.requested_model:
        raise HarnessFailure("router metadata requested model did not match")
    if metadata.get("strategy") != "direct":
        raise HarnessFailure(f"router strategy was not direct: {metadata.get('strategy')!r}")
    if metadata.get("attempt") != 1:
        raise HarnessFailure(f"router attempt was not 1: {metadata.get('attempt')!r}")
    endpoints = metadata.get("endpoints")
    if not isinstance(endpoints, dict):
        raise HarnessFailure("router metadata endpoints was not an object")
    total = endpoints.get("total")
    if isinstance(total, bool) or not isinstance(total, int) or total < 1:
        raise HarnessFailure("router metadata total endpoint count was not usable")
    available = endpoints.get("available")
    if not isinstance(available, list) or len(available) != 1:
        raise HarnessFailure("router metadata available endpoint count was not 1")
    selected_endpoint = available[0]
    if not isinstance(selected_endpoint, dict) or selected_endpoint.get("selected") is not True:
        raise HarnessFailure("router metadata available endpoint was not selected")
    if metadata.get("pipeline") not in (None, []):
        raise HarnessFailure("router pipeline altered or inspected the request")
    if not facts.usable:
        raise HarnessFailure(f"route facts were not usable: {list(facts.limitations)}")
    if facts.resolved_provider is None or (
        facts.resolved_provider.casefold() != binding.provider_name.casefold()
    ):
        raise HarnessFailure(
            f"resolved provider mismatch: {facts.resolved_provider!r} "
            f"!= {binding.provider_name!r}"
        )
    return facts.resolved_model or "", facts.resolved_provider


@dataclass
class LiveSession:
    client: httpx.AsyncClient
    api_key: str
    output_dir: Path
    bindings: dict[str, CatalogBinding]
    total_cost: Decimal = Decimal("0")
    call_index: int = 0

    async def send_structured(
        self,
        *,
        role: str,
        arm: str,
        system_instruction: str,
        user_content: str,
        output_schema: dict[str, Any],
        schema_name: str,
        prompt_version: str,
        context_version: str,
        context_packet: dict[str, Any],
        max_output_tokens: int,
    ) -> Any:
        if self.total_cost >= MAX_PREFLIGHT_COST:
            raise HarnessFailure(
                f"preflight cost cap reached: US${self.total_cost}"
            )
        binding = self.bindings[role]
        config = ProviderConfig(
            requested_model=binding.requested_model,
            provider_only=(binding.endpoint_tag,),
            provider_order=(binding.endpoint_tag,),
            reasoning_effort="high",
        )
        request = build_chat_request(
            config,
            system_instruction=system_instruction,
            user_content=user_content,
            output_schema=output_schema,
            schema_name=schema_name,
            max_output_tokens=max_output_tokens,
        )

        self.call_index += 1
        capture = TrialCapture(self.output_dir / f"call-{self.call_index:02d}-{role}")
        capture.write("catalog-model.json", binding.model_snapshot)
        capture.write("catalog-endpoint.json", binding.endpoint_snapshot)
        capture.write("context.json", context_packet)
        capture.write(
            "request.json",
            {
                "url": request.url,
                "headers": request.headers_without_secrets,
                "body": request.body,
                "body_hash": request.body_hash,
            },
        )

        wire = await send_once(self.client, request, api_key=self.api_key)
        capture.write(
            "response.json",
            {
                "status_code": wire.status_code,
                "headers": wire.headers,
                "body": wire.body,
                "latency_ms": wire.latency_ms,
                "usage": wire.usage.__dict__,
                "outcome": wire.outcome,
                "error_message": wire.error_message,
            },
        )

        resolved_model: str | None = None
        resolved_provider: str | None = None
        limitations = list(wire.limitations) + list(wire.usage.limitations)
        try:
            resolved_model, resolved_provider = _attest_route(wire, binding)
            payload = parse_chat_payload(wire.body)
            parse_outcome = "ok"
        except (HarnessFailure, ModelOutputFailure, ValueError) as exc:
            parse_outcome = "failed"
            limitations.append(str(exc))
            manifest = self._manifest(
                capture,
                arm=arm,
                prompt_version=prompt_version,
                context_version=context_version,
                request=request,
                wire=wire,
                binding=binding,
                resolved_model=resolved_model,
                resolved_provider=resolved_provider,
                parse_outcome=parse_outcome,
                limitations=limitations,
            )
            capture.write_manifest(manifest)
            raise

        if wire.usage.cost is None:
            raise HarnessFailure("OpenRouter response omitted usage.cost")
        self.total_cost += Decimal(wire.usage.cost)
        if self.total_cost > MAX_PREFLIGHT_COST:
            raise HarnessFailure(
                f"preflight exceeded US${MAX_PREFLIGHT_COST}: US${self.total_cost}"
            )

        manifest = self._manifest(
            capture,
            arm=arm,
            prompt_version=prompt_version,
            context_version=context_version,
            request=request,
            wire=wire,
            binding=binding,
            resolved_model=resolved_model,
            resolved_provider=resolved_provider,
            parse_outcome=parse_outcome,
            limitations=limitations,
        )
        capture.write_manifest(manifest)
        verified = verify_manifest(manifest, capture)
        if not verified.ok:
            raise HarnessFailure(
                "captured manifest failed verification: "
                + "; ".join(f.message for f in verified.findings)
            )
        return payload

    @staticmethod
    def _manifest(
        capture: TrialCapture,
        *,
        arm: str,
        prompt_version: str,
        context_version: str,
        request: Any,
        wire: WireResult,
        binding: CatalogBinding,
        resolved_model: str | None,
        resolved_provider: str | None,
        parse_outcome: str,
        limitations: list[str],
    ) -> dict[str, Any]:
        return {
            "case_id": DISPOSABLE_CASE_ID,
            "case_revision": 1,
            "case_family_id": DISPOSABLE_CASE_ID,
            "source_type": "constructed_edge",
            "suite_hash": "disposable-preflight-no-suite",
            "arm": arm,
            "round": 0,
            "attempt": 1,
            "prompt_version": prompt_version,
            "schema_hash": request.schema_hash,
            "context_assembler_version": context_version,
            "requested_model": binding.requested_model,
            "resolved_model": resolved_model,
            "resolved_provider": resolved_provider,
            "provider_config_hash": request.config_hash,
            "catalog_snapshot_hash": binding.snapshot_hash,
            "files": capture.files,
            "outcomes": {
                "transport": wire.outcome,
                "route": "ok" if resolved_model else "failed",
                "parse": parse_outcome,
                "local_verifier": "deferred-to-runner",
            },
            "usage": wire.usage.__dict__,
            "latency_ms": wire.latency_ms,
            "limitations": sorted(set(limitations)),
        }


@dataclass
class LiveModelPort:
    session: LiveSession

    async def complete(self, stage: AssembledStage) -> Any:
        role = arm_by_id(stage.arm_id).model_role
        return await self.session.send_structured(
            role=role,
            arm=stage.arm_id,
            system_instruction=stage.system_instruction,
            user_content=stage.user_content,
            output_schema=stage.output_schema,
            schema_name=stage.schema_name,
            prompt_version=stage.prompt_version,
            context_version=stage.context_assembler_version,
            context_packet=stage.context_packet,
            max_output_tokens=2048,
        )


async def run_live_preflight(
    *,
    env_file: Path,
    output_dir: Path,
) -> dict[str, Any]:
    api_key = _load_env_value(env_file, "OPENROUTER_API_KEY")
    output_dir.mkdir(parents=True, exist_ok=False)

    async with build_client(120.0) as client:
        bindings = {
            role: await fetch_catalog_binding(
                client,
                api_key=api_key,
                requested_model=model,
                endpoint_tag=endpoint,
            )
            for role, (model, endpoint) in MODEL_PROFILES.items()
        }
        session = LiveSession(
            client=client,
            api_key=api_key,
            output_dir=output_dir,
            bindings=bindings,
        )
        port = LiveModelPort(session)

        all_plans = build_observation_plans([DISPOSABLE_CASE])
        selected_arm_ids = ("A1", "A3", "A4")
        selected_plans = [
            next(plan for plan in all_plans if plan.arm.arm_id == arm_id)
            for arm_id in selected_arm_ids
        ]
        results: dict[str, ObservationResult] = {}
        for plan in selected_plans:
            result = await run_observation(DISPOSABLE_CASE, plan, port)
            results[plan.arm.arm_id] = result
            if result.outcome != "completed":
                raise HarnessFailure(
                    f"{plan.arm.arm_id} preflight was not completed: "
                    f"{result.outcome} {[str(f) for f in result.findings]}"
                )

        forward, reverse, label_to_arm = build_blind_packets(
            DISPOSABLE_CASE,
            results,
            seed=20260727,
        )
        dimensions = ("meaningful_outcome", "source_grounding")
        grader_outputs: list[dict[str, dict[str, str]]] = []
        for order_name, packet in (("forward", forward), ("reverse", reverse)):
            grader_stage = build_grader_stage(packet, dimensions=dimensions)
            raw_grade = await session.send_structured(
                role="grader",
                arm=f"GRADER-{order_name}",
                system_instruction=grader_stage.system_instruction,
                user_content=grader_stage.user_content,
                output_schema=grader_stage.output_schema,
                schema_name=f"r1_preflight_grader_{order_name}",
                prompt_version=grader_stage.prompt_version,
                context_version="r1-task-discovery-grader-context.1",
                context_packet=packet,
                max_output_tokens=2048,
            )
            grader_outputs.append(
                parse_grader_payload(
                    raw_grade,
                    expected_labels=set(label_to_arm),
                    expected_dimensions=set(dimensions),
                )
            )
        merged = merge_grader_passes(grader_outputs[0], grader_outputs[1])

    summary = {
        "run_id": output_dir.name,
        "status": "passed",
        "disposable_only": True,
        "quality_conclusion_eligible": False,
        "arms": list(selected_arm_ids),
        "generator_calls": sum(result.call_count for result in results.values()),
        "grader_calls": 2,
        "total_calls": session.call_index,
        "total_cost": str(session.total_cost),
        "bindings": {
            role: {
                "requested_model": binding.requested_model,
                "canonical_model": binding.canonical_model,
                "endpoint_tag": binding.endpoint_tag,
                "provider_name": binding.provider_name,
                "snapshot_hash": binding.snapshot_hash,
            }
            for role, binding in bindings.items()
        },
        "outcomes": {arm: result.outcome for arm, result in results.items()},
        "grader_merged": merged,
        "created_at": datetime.now(UTC).isoformat(),
        "limitations": [
            "disposable plumbing smoke; no model-quality or architecture conclusion"
        ],
    }
    root_capture = TrialCapture(output_dir)
    root_capture.write("summary.json", summary)
    return summary


def _default_output_dir() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path("output") / "professional-consultant-r1" / f"preflight-{stamp}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R1 disposable OpenRouter live preflight")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    output_dir = args.output_dir or _default_output_dir()
    try:
        summary = asyncio.run(
            run_live_preflight(env_file=args.env_file, output_dir=output_dir)
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "output_dir": str(output_dir),
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
