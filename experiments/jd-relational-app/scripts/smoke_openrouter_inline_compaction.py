"""Bounded live smoke for the OpenRouter Responses compaction candidate.

This is deliberately outside the product composition root.  It sends only a
deterministic synthetic conversation and proves (or disproves) the one server
capability that the offline adapter contract cannot prove:

* OpenRouter emits an inline Responses compaction item for the pinned Luna
  route;
* the real ChatOpenAI adapter and LangGraph Saver preserve that opaque item;
* a rebuilt graph resumes from the request-only compaction view, omits the
  replaced plaintext setup, and can still perform a small local tool call.

The script never prints the credential, prompts, raw response bodies, opaque
payloads or tool arguments.  It has no retry, no provider fallback, a four
request ceiling and a conservative US$0.03 pre-send budget gate.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import secrets
from typing import Any

import httpx
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from jd_relational.consolidation_app import native_context_view
from jd_relational.consultant_model import (
    CONSULTANT_MODEL,
    OPENROUTER_BASE_URL,
    OPENROUTER_HEADERS,
    OPENROUTER_PROVIDER,
)
from jd_relational.provider_keys import read_key


COMPACT_THRESHOLD = 12_000
MAX_OUTPUT_TOKENS = 1_024
MAX_OUTBOUND_REQUESTS = 4
MAX_BUDGET_USD = Decimal("0.03")
INPUT_USD_PER_TOKEN = Decimal("0.20") / Decimal(1_000_000)
OUTPUT_USD_PER_TOKEN = Decimal("1.20") / Decimal(1_000_000)
# Covers tokenizer mismatch and unitemized inline-compaction work.  Every later
# request is re-evaluated from its actual serialized body before transport.
# UTF-8 bytes are an upper bound for BPE tokens and include the entire serialized
# JSON request.  This avoids a hidden tokenizer-data download during the smoke.
PREFLIGHT_SAFETY_MULTIPLIER = Decimal("1")
TARGET_SETUP_BYTES = 60_000
REQUEST_TIMEOUT_SECONDS = 90.0
SYNTHETIC_CODE = "CALIBURN-SMOKE-4729-TEAL"
FILLER_FIRST_MARKER = "synthetic-padding-row-00000"
FILLER_LAST_MARKER_PREFIX = "synthetic-padding-row-"
APP_ENV_PATH = Path(__file__).resolve().parents[3] / "apps" / "api" / ".env"


class SmokeStopped(RuntimeError):
    """A safe local guard stopped the smoke before another outbound request."""


@dataclass
class RequestRecord:
    index: int
    method: str
    path: str
    kind: str
    input_token_upper_bound: int = 0
    max_output_tokens: int = 0
    preflight_reserve_usd: Decimal = Decimal("0")
    status_code: int | None = None
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    accounted_cost_usd: Decimal | None = None
    cost_source: str | None = None
    provider: str | None = None
    model: str | None = None
    compaction_items: int = 0
    input_item_types: list[str] = field(default_factory=list)
    function_call_ids: list[str] = field(default_factory=list)
    function_output_ids: list[str] = field(default_factory=list)
    contains_setup_plaintext: bool = False
    contains_filler_plaintext: bool = False
    response_error_type: str | None = None


class BoundedLedger:
    def __init__(self) -> None:
        self.records: list[RequestRecord] = []
        self.last_response_payload: dict[str, Any] | None = None

    def _accounted_so_far(self) -> Decimal:
        total = Decimal("0")
        for record in self.records:
            if record.status_code is None:
                total += record.preflight_reserve_usd
            elif record.accounted_cost_usd is not None:
                total += record.accounted_cost_usd
            else:
                # A response whose usage cannot be accounted blocks later work
                # below.  Keep its original reserve visible in the report.
                total += record.preflight_reserve_usd
        return total

    @staticmethod
    def _selected_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("openrouter_metadata")
        endpoints = metadata.get("endpoints") if isinstance(metadata, dict) else None
        available = endpoints.get("available") if isinstance(endpoints, dict) else None
        if not isinstance(available, list):
            return {}
        return next(
            (
                item
                for item in available
                if isinstance(item, dict) and item.get("selected") is True
            ),
            {},
        )

    @staticmethod
    def _usage_number(usage: dict[str, Any], *names: str) -> int | None:
        for name in names:
            value = usage.get(name)
            if type(value) is int and value >= 0:
                return value
        return None

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            result = Decimal(str(value))
        except Exception:
            return None
        return result if result >= 0 and result.is_finite() else None

    def request_hook(self, request: httpx.Request) -> None:
        if request.url.host != "openrouter.ai":
            raise SmokeStopped("unexpected_host")
        if len(self.records) >= MAX_OUTBOUND_REQUESTS:
            raise SmokeStopped("request_ceiling_reached")
        if any(record.status_code is None for record in self.records):
            raise SmokeStopped("parallel_or_unsettled_request")
        if any(
            record.status_code is not None and record.accounted_cost_usd is None
            for record in self.records
            if record.kind == "model"
        ):
            raise SmokeStopped("previous_cost_unknown")

        path = request.url.path
        kind = "metadata" if request.method == "GET" and path.endswith("/generation") else "model"
        if kind == "model" and (request.method != "POST" or not path.endswith("/responses")):
            raise SmokeStopped("unexpected_endpoint")

        record = RequestRecord(
            index=len(self.records) + 1,
            method=request.method,
            path=path,
            kind=kind,
        )
        if kind == "model":
            try:
                payload = json.loads(request.content)
            except (ValueError, UnicodeError, TypeError):
                raise SmokeStopped("request_not_json") from None
            expected_route = {
                "only": [OPENROUTER_PROVIDER],
                "order": [OPENROUTER_PROVIDER],
                "allow_fallbacks": False,
                "require_parameters": True,
            }
            if payload.get("model") != CONSULTANT_MODEL:
                raise SmokeStopped("wrong_requested_model")
            if payload.get("provider") != expected_route:
                raise SmokeStopped("route_not_openai_only")
            if payload.get("store") is not False:
                raise SmokeStopped("provider_storage_not_disabled")
            if payload.get("context_management") != [
                {"type": "compaction", "compact_threshold": COMPACT_THRESHOLD}
            ]:
                raise SmokeStopped("compaction_not_configured")
            if payload.get("max_output_tokens") != MAX_OUTPUT_TOKENS:
                raise SmokeStopped("output_cap_not_fixed")
            if payload.get("parallel_tool_calls") is not False:
                raise SmokeStopped("parallel_tools_not_disabled")

            wire = request.content.decode("utf-8")
            record.input_token_upper_bound = len(request.content)
            record.max_output_tokens = MAX_OUTPUT_TOKENS
            base = (
                Decimal(record.input_token_upper_bound) * INPUT_USD_PER_TOKEN
                + Decimal(MAX_OUTPUT_TOKENS) * OUTPUT_USD_PER_TOKEN
            )
            record.preflight_reserve_usd = base * PREFLIGHT_SAFETY_MULTIPLIER
            input_items = payload.get("input")
            if isinstance(input_items, list):
                record.input_item_types = [
                    str(item.get("type") or item.get("role") or "unknown")
                    for item in input_items
                    if isinstance(item, dict)
                ]
                record.function_call_ids = [
                    str(item["call_id"])
                    for item in input_items
                    if isinstance(item, dict)
                    and item.get("type") == "function_call"
                    and item.get("call_id") is not None
                ]
                record.function_output_ids = [
                    str(item["call_id"])
                    for item in input_items
                    if isinstance(item, dict)
                    and item.get("type") == "function_call_output"
                    and item.get("call_id") is not None
                ]
            record.contains_setup_plaintext = SYNTHETIC_CODE in wire
            record.contains_filler_plaintext = FILLER_FIRST_MARKER in wire

        projected = self._accounted_so_far() + record.preflight_reserve_usd
        if projected > MAX_BUDGET_USD:
            raise SmokeStopped("budget_preflight_blocked")
        self.records.append(record)

    def response_hook(self, response: httpx.Response) -> None:
        response.read()
        record = self.records[-1]
        record.status_code = response.status_code
        try:
            payload = response.json()
        except (ValueError, UnicodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        self.last_response_payload = payload

        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        record.response_id = str(data["id"]) if data.get("id") is not None else None
        selected = self._selected_endpoint(payload)
        record.provider = (
            data.get("provider")
            or data.get("provider_name")
            or selected.get("provider")
        )
        record.model = selected.get("model") or data.get("model")

        output = data.get("output")
        if isinstance(output, list):
            record.compaction_items = sum(
                1
                for item in output
                if isinstance(item, dict) and item.get("type") == "compaction"
            )
        error = data.get("error")
        if isinstance(error, dict):
            value = error.get("type") or error.get("code")
            record.response_error_type = str(value) if value is not None else "remote_error"

        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        record.input_tokens = self._usage_number(usage, "input_tokens", "prompt_tokens")
        record.output_tokens = self._usage_number(usage, "output_tokens", "completion_tokens")
        direct_cost = self._decimal(usage.get("cost"))
        if direct_cost is None:
            direct_cost = self._decimal(data.get("total_cost"))
        if direct_cost is not None:
            record.accounted_cost_usd = direct_cost
            record.cost_source = "provider"
        elif record.input_tokens is not None and record.output_tokens is not None:
            # Standard, uncached published Luna price.  This deliberately does
            # not assume a cache discount.
            record.accounted_cost_usd = (
                Decimal(record.input_tokens) * INPUT_USD_PER_TOKEN
                + Decimal(record.output_tokens) * OUTPUT_USD_PER_TOKEN
            )
            record.cost_source = "usage_at_uncached_price"

    def model_records(self) -> list[RequestRecord]:
        return [record for record in self.records if record.kind == "model"]

    def report_records(self) -> list[dict[str, Any]]:
        result = []
        for record in self.records:
            result.append(
                {
                    "index": record.index,
                    "kind": record.kind,
                    "method": record.method,
                    "path": record.path,
                    "status_code": record.status_code,
                    "input_token_upper_bound_from_utf8_bytes": record.input_token_upper_bound,
                    "max_output_tokens": record.max_output_tokens,
                    "preflight_reserve_usd": str(record.preflight_reserve_usd.quantize(Decimal("0.00000001"))),
                    "input_tokens": record.input_tokens,
                    "output_tokens": record.output_tokens,
                    "accounted_cost_usd": (
                        str(record.accounted_cost_usd.quantize(Decimal("0.00000001")))
                        if record.accounted_cost_usd is not None
                        else None
                    ),
                    "cost_source": record.cost_source,
                    "response_id": record.response_id,
                    "provider": record.provider,
                    "model": record.model,
                    "compaction_items": record.compaction_items,
                    "input_item_types": record.input_item_types,
                    "function_call_ids": record.function_call_ids,
                    "function_output_ids": record.function_output_ids,
                    "contains_setup_plaintext": record.contains_setup_plaintext,
                    "contains_filler_plaintext": record.contains_filler_plaintext,
                    "response_error_type": record.response_error_type,
                }
            )
        return result


def _make_setup() -> tuple[str, int, str]:
    lines: list[str] = []
    byte_count = 0
    index = 0
    while byte_count < TARGET_SETUP_BYTES:
        digest = hashlib.sha256(f"synthetic-row-{index}".encode()).hexdigest()
        line = (
            f"synthetic-padding-row-{index:05d}: {digest}; "
            "this row has no product meaning and must not be used as a fact."
        )
        lines.append(line)
        byte_count += len((line + "\n").encode("utf-8"))
        index += 1
    last_marker = f"{FILLER_LAST_MARKER_PREFIX}{index - 1:05d}"
    message = (
        "SETUP. This is a synthetic transport test, not product or user data.\n"
        f"The one critical project code is {SYNTHETIC_CODE}. Retain it for the later EXECUTE step.\n"
        "All numbered rows below are meaningless padding. Do not treat them as facts.\n"
        + "\n".join(lines)
        + "\nEnd of meaningless padding. Keep the earlier critical project code. "
        "Do not call any tool and do not repeat the code. Reply with exactly READY."
    )
    return message, len(message.encode("utf-8")), last_marker


def _blocks(message: AIMessage) -> list[dict[str, Any]]:
    if not isinstance(message.content, list):
        return []
    return [block for block in message.content if isinstance(block, dict)]


def _visible_text(message: AIMessage) -> str:
    if isinstance(message.content, str):
        return message.content.strip()
    parts: list[str] = []
    for block in _blocks(message):
        if block.get("type") in {"text", "output_text"} and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts).strip()


def _last_ai(messages: list[Any]) -> AIMessage | None:
    return next((message for message in reversed(messages) if isinstance(message, AIMessage)), None)


def _route_matches(record: RequestRecord) -> bool:
    provider = (record.provider or "").casefold()
    model = (record.model or "").casefold()
    return provider == "openai" and "gpt-5.6-luna" in model


def _safe_error(error: Exception, key: str | None) -> str:
    value = str(error)
    if key:
        value = value.replace(key, "[redacted]")
    return value[:800]


def _read_smoke_key() -> tuple[str | None, str | None]:
    """Read the Owner-identified App .env without importing or logging it.

    The production composition still owns its Windows Credential Manager
    boundary.  This compatibility smoke only reads the already-existing App
    file in place; it never copies the key into this experiment or a report.
    """
    try:
        lines = APP_ENV_PATH.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        lines = []
    except (OSError, UnicodeError):
        raise SmokeStopped("app_env_unreadable") from None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != "OPENROUTER_API_KEY":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if value.strip() and "\0" not in value and len(value) <= 512:
            return value, "apps/api/.env (read-only)"
        raise SmokeStopped("app_env_key_invalid")
    key = read_key("openrouter")
    return (key, "Windows Credential Manager") if key is not None else (None, None)


def _base_report(setup_bytes: int, last_marker: str) -> dict[str, Any]:
    return {
        "classification": "PRECHECK",
        "model_requested": CONSULTANT_MODEL,
        "provider_policy": "OpenAI only; fallback disabled",
        "store": False,
        "automatic_retries": 0,
        "compact_threshold": COMPACT_THRESHOLD,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "request_ceiling": MAX_OUTBOUND_REQUESTS,
        "budget_ceiling_usd": str(MAX_BUDGET_USD),
        "preflight_safety_multiplier": str(PREFLIGHT_SAFETY_MULTIPLIER),
        "synthetic_setup_utf8_bytes": setup_bytes,
        "input_preflight_method": "serialized UTF-8 bytes as token upper bound",
        "synthetic_code_sha256": hashlib.sha256(SYNTHETIC_CODE.encode()).hexdigest(),
        "last_filler_marker": last_marker,
        "checks": {},
        "requests": [],
    }


def run_live() -> dict[str, Any]:
    setup, setup_bytes, last_marker = _make_setup()
    report = _base_report(setup_bytes, last_marker)
    try:
        key, key_source = _read_smoke_key()
    except SmokeStopped as error:
        report["classification"] = "PRECHECK-BLOCKED"
        report["stop_reason"] = str(error)
        return report
    if key is None:
        report["classification"] = "PRECHECK-BLOCKED"
        report["stop_reason"] = "openrouter_credential_missing"
        return report
    report["credential_source"] = key_source

    ledger = BoundedLedger()
    saver = InMemorySaver()
    graph_config = {
        "configurable": {"thread_id": "openrouter-inline-compaction-smoke-v1"},
        "recursion_limit": 8,
    }
    tool_observations: list[bool] = []

    @tool
    def verify_project_code(code: str) -> str:
        """Verify the exact synthetic project code retained from SETUP."""
        accepted = secrets.compare_digest(code, SYNTHETIC_CODE)
        tool_observations.append(accepted)
        return json.dumps({"accepted": accepted}, separators=(",", ":"))

    system_prompt = (
        "You are a deterministic transport-smoke agent. SETUP gives one critical synthetic "
        "project code among meaningless padding. For SETUP, never call a tool or repeat the "
        "code; answer exactly READY. When the user later sends exactly EXECUTE, call "
        "verify_project_code exactly once with the earlier code. Never guess or copy a code "
        "from tool output. After the tool reports accepted=true, answer exactly VERIFIED."
    )

    def build_agent(tools: list[Any]):
        model = ChatOpenAI(
            model=CONSULTANT_MODEL,
            api_key=key,
            base_url=OPENROUTER_BASE_URL,
            http_client=client,
            timeout=client.timeout,
            max_retries=0,
            use_responses_api=True,
            output_version="responses/v1",
            store=False,
            truncation="disabled",
            # ChatOpenAI's public constructor still names this max_tokens and
            # maps it to Responses `max_output_tokens` on the wire; the request
            # hook verifies the final serialized field before transport.
            max_tokens=MAX_OUTPUT_TOKENS,
            reasoning={"effort": "high", "context": "all_turns"},
            model_kwargs={"parallel_tool_calls": False},
            context_management=[
                {"type": "compaction", "compact_threshold": COMPACT_THRESHOLD}
            ],
            extra_body={
                "provider": {
                    "only": [OPENROUTER_PROVIDER],
                    "order": [OPENROUTER_PROVIDER],
                    "allow_fallbacks": False,
                    "require_parameters": True,
                }
            },
        )
        return create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            middleware=[native_context_view],
            checkpointer=saver,
        )

    client = httpx.Client(
        headers=OPENROUTER_HEADERS,
        trust_env=False,
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        event_hooks={
            "request": [ledger.request_hook],
            "response": [ledger.response_hook],
        },
    )
    try:
        first_agent = build_agent([])
        first_result = first_agent.invoke(
            {"messages": [HumanMessage(setup, id="synthetic-setup")]},
            graph_config,
            durability="sync",
        )
        first_ai = _last_ai(first_result["messages"])
        first_blocks = _blocks(first_ai) if first_ai is not None else []
        first_has_compaction = any(block.get("type") == "compaction" for block in first_blocks)
        first_reply = _visible_text(first_ai) if first_ai is not None else ""
        first_reply_safe = first_ai is not None and SYNTHETIC_CODE not in json.dumps(
            first_ai.content, ensure_ascii=False
        )
        first_record = ledger.model_records()[0]
        reported_above_threshold = bool(
            first_record.input_tokens is not None
            and first_record.input_tokens > COMPACT_THRESHOLD
        )
        report["checks"].update(
            {
                "server_emitted_compaction": first_has_compaction,
                "first_request_reported_above_threshold": reported_above_threshold,
                "setup_reply_exact_ready": first_reply == "READY",
                "setup_reply_did_not_repeat_code": first_reply_safe,
            }
        )
        if not first_has_compaction:
            report["classification"] = (
                "UNVERIFIED" if reported_above_threshold else "SMOKE-DESIGN-INVALID"
            )
            report["stop_reason"] = (
                "no_compaction_item_with_reported_input_above_threshold"
                if reported_above_threshold
                else "reported_input_did_not_cross_threshold"
            )
            return report
        if first_reply != "READY" or not first_reply_safe:
            report["classification"] = "SMOKE-DESIGN-INVALID"
            report["stop_reason"] = "post_compaction_tail_could_reveal_setup_answer"
            return report

        # New graph object, same Saver: this forces the second turn to load the
        # serialized checkpoint instead of receiving a hand-built message list.
        resumed_agent = build_agent([verify_project_code])
        resumed_before = resumed_agent.get_state(graph_config).values["messages"]
        saver_reloaded_compaction = any(
            isinstance(message, AIMessage)
            and any(block.get("type") == "compaction" for block in _blocks(message))
            for message in resumed_before
        )
        second_result = resumed_agent.invoke(
            {"messages": [HumanMessage("EXECUTE", id="synthetic-execute")]},
            graph_config,
            durability="sync",
        )
        canonical = second_result["messages"]
        model_records = ledger.model_records()
        post_compaction_wire = model_records[1] if len(model_records) >= 2 else None
        request_view_has_compaction = bool(
            post_compaction_wire
            and "compaction" in post_compaction_wire.input_item_types
        )
        request_view_omits_setup = bool(
            post_compaction_wire
            and not post_compaction_wire.contains_setup_plaintext
            and not post_compaction_wire.contains_filler_plaintext
        )
        paired_call = any(
            bool(set(record.function_call_ids) & set(record.function_output_ids))
            for record in model_records
        )
        canonical_retains_setup = any(
            isinstance(message, HumanMessage)
            and isinstance(message.content, str)
            and SYNTHETIC_CODE in message.content
            and FILLER_FIRST_MARKER in message.content
            and last_marker in message.content
            for message in canonical
        )
        canonical_retains_tool = any(isinstance(message, ToolMessage) for message in canonical)
        final_ai = _last_ai(canonical)
        final_text = _visible_text(final_ai) if final_ai is not None else ""
        route_confirmed = bool(model_records) and all(_route_matches(record) for record in model_records)
        report["checks"].update(
            {
                "saver_reload_retained_compaction": saver_reloaded_compaction,
                "next_request_used_compaction": request_view_has_compaction,
                "next_request_omitted_replaced_plaintext": request_view_omits_setup,
                "tool_received_exact_pre_compaction_code": tool_observations == [True],
                "tool_call_result_pair_preserved": paired_call,
                "canonical_history_retained_original": canonical_retains_setup,
                "canonical_history_retained_tool_result": canonical_retains_tool,
                "final_reply_exact_verified": final_text == "VERIFIED",
                "actual_route_confirmed_for_all_model_responses": route_confirmed,
            }
        )

        semantic_ok = all(
            report["checks"].get(name) is True
            for name in (
                "server_emitted_compaction",
                "saver_reload_retained_compaction",
                "next_request_used_compaction",
                "next_request_omitted_replaced_plaintext",
                "tool_received_exact_pre_compaction_code",
                "tool_call_result_pair_preserved",
                "canonical_history_retained_original",
                "canonical_history_retained_tool_result",
                "final_reply_exact_verified",
            )
        )
        if semantic_ok and route_confirmed:
            report["classification"] = "SERVER-SMOKE-PASS"
        elif semantic_ok:
            report["classification"] = "TRANSPORT-PASS-ROUTE-UNVERIFIED"
            report["stop_reason"] = "response_did_not_expose_complete_route_receipt"
        else:
            report["classification"] = "CONTEXT-CONTINUATION-FAILED"
            report["stop_reason"] = "one_or_more_acceptance_checks_failed"
    except SmokeStopped as error:
        report["classification"] = "PRECHECK-BLOCKED"
        report["stop_reason"] = str(error)
    except Exception as error:
        status = getattr(error, "status_code", None)
        if status in {400, 404, 405, 409, 415, 422}:
            classification = "EXPLICIT-SERVER-FAIL"
        elif status in {408, 429, 500, 502, 503, 504} or isinstance(
            error, (httpx.TimeoutException, httpx.NetworkError)
        ):
            classification = "TRANSIENT-STOP"
        else:
            classification = "SMOKE-ERROR"
        report["classification"] = classification
        report["stop_reason"] = type(error).__name__
        report["safe_error"] = _safe_error(error, key)
    finally:
        client.close()
        report["requests"] = ledger.report_records()
        costs = [
            record.accounted_cost_usd
            for record in ledger.records
            if record.accounted_cost_usd is not None
        ]
        report["actual_outbound_requests"] = len(ledger.records)
        report["accounted_total_cost_usd"] = str(
            sum(costs, Decimal("0")).quantize(Decimal("0.00000001"))
        )
        report["all_model_costs_accounted"] = all(
            record.accounted_cost_usd is not None for record in ledger.model_records()
        )
        del key
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Generate and count the synthetic setup without reading a key or making a request.",
    )
    args = parser.parse_args()
    setup, tokens, last_marker = _make_setup()
    del setup
    if args.preflight_only:
        report = _base_report(tokens, last_marker)
        report["classification"] = "LOCAL-PREFLIGHT-PASS"
    else:
        report = run_live()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["classification"] in {
        "LOCAL-PREFLIGHT-PASS",
        "SERVER-SMOKE-PASS",
        "UNVERIFIED",
        "TRANSPORT-PASS-ROUTE-UNVERIFIED",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
