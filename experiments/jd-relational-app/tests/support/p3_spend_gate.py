"""Fail-closed spend gate for the authorized P3 OpenRouter acceptance run.

This is test support, not production runtime.  It deliberately serializes the
caller-owned HTTP clients so the next request is never sent until the previous
request's provider-reported cost has been durably accounted for.  Request or
response bodies are never persisted.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
from threading import Condition, RLock
from time import monotonic
from typing import Any

import httpx
from langchain_core.callbacks import BaseCallbackHandler


class BudgetGateError(RuntimeError):
    """The paid acceptance request cannot safely proceed."""


_ROLE_OUTPUT_LIMITS = {
    "consultant": 8192,
    "background-case-maintainer": 32768,
    "background-understanding-maintainer": 32768,
}
_ROLE_SUMMARY_LIMITS = {
    "consultant": 8192,
    "background-case-maintainer": 8192,
    "background-understanding-maintainer": 8192,
}
_active_model_role: ContextVar[str | None] = ContextVar("p3_model_role", default=None)


class TrialRoleCapture(BaseCallbackHandler):
    """Carry the formal model's existing component tag to its HTTP boundary."""

    run_inline = True
    raise_error = True

    def on_chat_model_start(self, serialized, messages, *, metadata=None, **kwargs):
        _active_model_role.set((metadata or {}).get("caliburn_component"))

    def on_llm_end(self, response, **kwargs):
        _active_model_role.set(None)

    def on_llm_error(self, error, **kwargs):
        _active_model_role.set(None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class LunaBudgetPolicy:
    """Pinned P3 wire contract and conservative per-request reservation."""

    MODEL = "openai/gpt-6-luna"
    # OpenRouter's public model lookup resolves this request slug to the
    # canonical snapshot below (checked 2026-09-23). Pin the accepted reply
    # identity; a later alias change must stop this trial for re-verification.
    RESPONSE_MODELS = (MODEL, "openai/gpt-6-luna-20260922")
    ENDPOINT = "https://openrouter.ai/api/v1/responses"
    PROVIDER = {
        "only": ["openai"],
        "order": ["openai"],
        "allow_fallbacks": False,
        "require_parameters": False,
    }
    ROLE_OUTPUT_LIMITS = frozenset({2048, 8192, 32768})

    # The full 1.05M context is reserved at the documented cache-write rate.
    # Output is reserved at the documented >272K long-context output rate.
    CONTEXT_TOKENS = Decimal("1050000")
    CACHE_WRITE_USD_PER_MILLION = Decimal("0.25")
    LONG_OUTPUT_USD_PER_MILLION = Decimal("0.75")
    MILLION = Decimal("1000000")

    _DISALLOWED_KEYS = frozenset(
        {
            "models",
            "plugins",
            "service_tier",
            "transforms",
            "web_search_options",
        }
    )

    def request_payload(self, request: httpx.Request) -> dict[str, Any]:
        if request.method != "POST" or str(request.url) != self.ENDPOINT:
            raise BudgetGateError("request_contract_endpoint")
        if request.headers.get("X-OpenRouter-Metadata") != "enabled":
            raise BudgetGateError("request_contract_metadata")
        try:
            value = json.loads(request.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise BudgetGateError("request_contract_json") from None
        if type(value) is not dict:
            raise BudgetGateError("request_contract_body")
        if value.get("model") != self.MODEL:
            raise BudgetGateError("request_contract_model")
        if value.get("provider") != self.PROVIDER:
            raise BudgetGateError("request_contract_provider")
        if value.get("parallel_tool_calls") is not False:
            raise BudgetGateError("request_contract_parallel_tools")
        if value.get("reasoning") != {"effort": "high"}:
            raise BudgetGateError("request_contract_reasoning")
        if value.get("store") is not False:
            raise BudgetGateError("request_contract_store")
        if value.get("include") != ["reasoning.encrypted_content"]:
            raise BudgetGateError("request_contract_reasoning_continuation")
        if type(value.get("input")) is not list:
            raise BudgetGateError("request_contract_input")
        if value.get("stream") is True:
            raise BudgetGateError("request_contract_streaming")
        tools = value.get("tools")
        if tools is not None and (
            type(tools) is not list
            or any(
                type(tool) is not dict
                or tool.get("type") != "function"
                or type(tool.get("name")) is not str
                or type(tool.get("parameters")) is not dict
                for tool in tools
            )
        ):
            raise BudgetGateError("request_contract_server_tool")
        max_tokens = value.get("max_output_tokens")
        if type(max_tokens) is not int or max_tokens not in self.ROLE_OUTPUT_LIMITS:
            raise BudgetGateError("request_contract_max_output_tokens")
        if self._DISALLOWED_KEYS.intersection(value):
            raise BudgetGateError("request_contract_disallowed_feature")
        return value

    def reserve_for(self, payload: dict[str, Any]) -> Decimal:
        max_tokens = payload.get("max_output_tokens")
        if type(max_tokens) is not int or max_tokens not in self.ROLE_OUTPUT_LIMITS:
            raise BudgetGateError("request_contract_max_output_tokens")
        input_reserve = (
            self.CONTEXT_TOKENS
            * self.CACHE_WRITE_USD_PER_MILLION
            / self.MILLION
        )
        output_reserve = (
            Decimal(max_tokens) * self.LONG_OUTPUT_USD_PER_MILLION / self.MILLION
        )
        return input_reserve + output_reserve

    def validate_response(self, response: httpx.Response) -> tuple[Decimal, dict[str, Any]]:
        if response.status_code != 200:
            raise BudgetGateError(f"provider_http_{response.status_code}")
        try:
            value = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            raise BudgetGateError("provider_response_json") from None
        if type(value) is not dict:
            raise BudgetGateError("provider_response_body")
        if value.get("status") != "completed" or value.get("error") is not None:
            raise BudgetGateError("provider_response_incomplete")
        model = value.get("model")
        if model not in self.RESPONSE_MODELS:
            raise BudgetGateError("provider_model_mismatch")
        provider = value.get("provider")
        routing = value.get("openrouter_metadata")
        endpoints = routing.get("endpoints") if type(routing) is dict else None
        available = endpoints.get("available") if type(endpoints) is dict else None
        selected = ([item for item in available if type(item) is dict
                     and item.get("selected") is True]
                    if type(available) is list else [])
        if len(selected) > 1:
            raise BudgetGateError("provider_mismatch")
        selected_provider = selected[0].get("provider") if selected else None
        if provider is not None and selected_provider is not None and (
            type(provider) is not str or type(selected_provider) is not str
            or provider.casefold() != selected_provider.casefold()
        ):
            raise BudgetGateError("provider_mismatch")
        if provider is None:
            provider = selected_provider
        if selected and selected[0].get("model") not in (None, *self.RESPONSE_MODELS):
            raise BudgetGateError("provider_model_mismatch")
        if type(provider) is not str or provider.casefold() != "openai":
            raise BudgetGateError("provider_mismatch")
        if value.get("service_tier") not in (None, "default"):
            raise BudgetGateError("provider_service_tier_mismatch")
        usage = value.get("usage")
        if type(usage) is not dict or "cost" not in usage:
            raise BudgetGateError("usage_cost_missing")
        raw_cost = usage["cost"]
        if type(raw_cost) not in (str, int, float) or isinstance(raw_cost, bool):
            raise BudgetGateError("usage_cost_invalid")
        try:
            cost = Decimal(str(raw_cost))
        except InvalidOperation:
            raise BudgetGateError("usage_cost_invalid") from None
        if not cost.is_finite() or cost < 0:
            raise BudgetGateError("usage_cost_invalid")
        metadata: dict[str, Any] = {
            "actual_model": model,
            "actual_provider": provider,
            "actual_service_tier": value.get("service_tier"),
        }
        response_id = value.get("id")
        if type(response_id) is str and 0 < len(response_id) <= 128:
            metadata["response_id"] = response_id
        router_generation_id = response.headers.get("X-Generation-Id")
        if router_generation_id and len(router_generation_id) <= 128:
            metadata["router_generation_id"] = router_generation_id
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            count = usage.get(field)
            if type(count) is int and count >= 0:
                metadata[field] = count
        details = usage.get("input_tokens_details")
        if type(details) is dict:
            for field in ("cached_tokens", "cache_write_tokens"):
                count = details.get(field)
                if type(count) is int and count >= 0:
                    metadata[field] = count
        return cost, metadata

    @staticmethod
    def response_identity_facts(response: httpx.Response) -> dict[str, Any]:
        """Keep bounded route identifiers on failure, never the response body."""
        if response.status_code != 200:
            return {}
        try:
            value = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return {}
        if type(value) is not dict:
            return {}
        facts: dict[str, Any] = {}

        def keep(source: dict[str, Any], field: str, name: str) -> None:
            item = source.get(field)
            if type(item) is str and 0 < len(item) <= 128:
                facts[name] = item

        for field in ("model", "provider", "service_tier"):
            keep(value, field, f"observed_{field}")
        usage = value.get("usage")
        facts["observed_cost_present"] = type(usage) is dict and "cost" in usage
        routing = value.get("openrouter_metadata")
        endpoints = routing.get("endpoints") if type(routing) is dict else None
        available = endpoints.get("available") if type(endpoints) is dict else None
        selected = ([item for item in available if type(item) is dict
                     and item.get("selected") is True]
                    if type(available) is list else [])
        if len(selected) == 1:
            keep(selected[0], "model", "observed_selected_model")
            keep(selected[0], "provider", "observed_selected_provider")
        return facts


class P3SpendGate:
    """Durable, serialized admission control for one bounded paid trial."""

    FORMAT = 1
    _ATTEMPT_EXTENSION = "caliburn_p3_attempt"

    def __init__(
        self,
        path: Path,
        *,
        trial_id: str,
        authorized: bool,
        usd_cap: Decimal,
        request_cap: int,
        wait_timeout_seconds: float,
        policy: LunaBudgetPolicy | None = None,
    ) -> None:
        if not trial_id or type(trial_id) is not str:
            raise BudgetGateError("configuration_trial_id")
        if type(authorized) is not bool:
            raise BudgetGateError("configuration_authorized")
        if not isinstance(usd_cap, Decimal) or not usd_cap.is_finite() or usd_cap <= 0:
            raise BudgetGateError("configuration_usd_cap")
        if type(request_cap) is not int or request_cap <= 0:
            raise BudgetGateError("configuration_request_cap")
        if (
            type(wait_timeout_seconds) not in (int, float)
            or not math.isfinite(wait_timeout_seconds)
            or wait_timeout_seconds <= 0
        ):
            raise BudgetGateError("configuration_wait_timeout")

        self.path = Path(path)
        self.trial_id = trial_id
        self.authorized = authorized
        self.usd_cap = usd_cap
        self.request_cap = request_cap
        self.wait_timeout_seconds = float(wait_timeout_seconds)
        self.policy = policy or LunaBudgetPolicy()
        self._condition = Condition(RLock())
        self._state = self._load_or_create()

        with self._condition:
            if self._state["in_flight"]:
                retained = self._decimal(self._state["retained_unknown_usd"])
                retained += sum(
                    self._decimal(attempt["reserve_usd"])
                    for attempt in self._state["in_flight"]
                )
                self._state["retained_unknown_usd"] = str(retained)
                for attempt in self._state["in_flight"]:
                    self._settle_attempt(attempt["attempt_id"], "unknown_after_restart")
                self._state["in_flight"] = []
                self._state["status"] = "stopped"
                self._state["stop_reason"] = "recovered_in_flight_unknown"
                self._persist()

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise BudgetGateError("ledger_invalid_decimal") from None
        if not result.is_finite() or result < 0:
            raise BudgetGateError("ledger_invalid_decimal")
        return result

    def _new_state(self) -> dict[str, Any]:
        return {
            "format": self.FORMAT,
            "trial_id": self.trial_id,
            "usd_cap": str(self.usd_cap),
            "request_cap": self.request_cap,
            "status": "active",
            "stop_reason": None,
            "attempt_count": 0,
            "spent_usd": "0",
            "retained_unknown_usd": "0",
            "in_flight": [],
            "attempts": [],
        }

    def _load_or_create(self) -> dict[str, Any]:
        if not self.path.exists():
            state = self._new_state()
            self._state = state
            self._persist()
            return state
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise BudgetGateError("ledger_unreadable") from None
        if (
            type(state) is not dict
            or state.get("format") != self.FORMAT
            or state.get("trial_id") != self.trial_id
            or state.get("usd_cap") != str(self.usd_cap)
            or state.get("request_cap") != self.request_cap
            or state.get("status") not in {"active", "stopped"}
            or type(state.get("in_flight")) is not list
            or type(state.get("attempts")) is not list
            or type(state.get("attempt_count")) is not int
        ):
            raise BudgetGateError("ledger_configuration_mismatch")
        self._decimal(state.get("spent_usd"))
        self._decimal(state.get("retained_unknown_usd"))
        return state

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(self._state, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError:
            self._state["status"] = "stopped"
            self._state["stop_reason"] = "ledger_persist_failed"
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise BudgetGateError("ledger_persist_failed") from None

    def _settle_attempt(self, attempt_id: int, outcome: str, **values: Any) -> None:
        for attempt in self._state["attempts"]:
            if attempt["attempt_id"] == attempt_id:
                attempt["outcome"] = outcome
                attempt.update(values)
                return
        raise BudgetGateError("ledger_attempt_missing")

    def _active_attempt(self, request: httpx.Request) -> dict[str, Any] | None:
        attempt_id = request.extensions.get(self._ATTEMPT_EXTENSION)
        if type(attempt_id) is not int:
            return None
        return next(
            (
                attempt
                for attempt in self._state["in_flight"]
                if attempt["attempt_id"] == attempt_id
            ),
            None,
        )

    def _stop_unknown(
        self, request: httpx.Request, reason: str, *, http_status: int | None = None,
        router_generation_id: str | None = None,
        observed: dict[str, Any] | None = None,
    ) -> BudgetGateError | None:
        attempt = self._active_attempt(request)
        if attempt is None:
            return None
        reserve = self._decimal(attempt["reserve_usd"])
        retained = self._decimal(self._state["retained_unknown_usd"]) + reserve
        self._state["retained_unknown_usd"] = str(retained)
        facts: dict[str, Any] = {"reason": reason, "ended_at_utc": _utc_now()}
        if http_status is not None:
            facts["http_status"] = http_status
        if router_generation_id and len(router_generation_id) <= 128:
            facts["router_generation_id"] = router_generation_id
        if observed:
            facts.update(observed)
        self._settle_attempt(attempt["attempt_id"], "unknown", **facts)
        self._state["in_flight"] = []
        self._state["status"] = "stopped"
        self._state["stop_reason"] = reason
        self._persist()
        self._condition.notify_all()
        return BudgetGateError(reason)

    def begin(self, request: httpx.Request, *, role: str | None = None) -> None:
        payload = self.policy.request_payload(request)
        if role is not None and payload["max_output_tokens"] not in {
            _ROLE_OUTPUT_LIMITS.get(role), _ROLE_SUMMARY_LIMITS.get(role),
        }:
            raise BudgetGateError("request_role_mismatch")
        reserve = self.policy.reserve_for(payload)
        with self._condition:
            if not self.authorized:
                raise BudgetGateError("not_authorized")
            deadline = monotonic() + self.wait_timeout_seconds
            while self._state["in_flight"]:
                if self._state["status"] == "stopped":
                    raise BudgetGateError(self._state["stop_reason"] or "gate_stopped")
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise BudgetGateError("in_flight_wait_timeout")
                self._condition.wait(remaining)
            if self._state["status"] == "stopped":
                raise BudgetGateError(self._state["stop_reason"] or "gate_stopped")
            if self._state["attempt_count"] >= self.request_cap:
                raise BudgetGateError("request_cap")
            committed = self._decimal(self._state["spent_usd"])
            unknown = self._decimal(self._state["retained_unknown_usd"])
            if committed + unknown + reserve > self.usd_cap:
                raise BudgetGateError("usd_cap")

            attempt_id = self._state["attempt_count"] + 1
            attempt = {
                "attempt_id": attempt_id,
                "model": payload["model"],
                "max_output_tokens": payload["max_output_tokens"],
                "reserve_usd": str(reserve),
                "outcome": "in_flight",
                "started_at_utc": _utc_now(),
            }
            if role is not None:
                attempt["role"] = role
            self._state["attempt_count"] = attempt_id
            self._state["attempts"].append(dict(attempt))
            self._state["in_flight"] = [attempt]
            request.extensions[self._ATTEMPT_EXTENSION] = attempt_id
            self._persist()

    def complete(self, response: httpx.Response) -> None:
        request = response.request
        with self._condition:
            attempt = self._active_attempt(request)
            if attempt is None:
                raise BudgetGateError("response_not_admitted")
            try:
                cost, metadata = self.policy.validate_response(response)
            except BudgetGateError as error:
                stopped = self._stop_unknown(
                    request, str(error), http_status=response.status_code,
                    router_generation_id=response.headers.get("X-Generation-Id"),
                    observed=self.policy.response_identity_facts(response),
                )
                raise stopped or error

            reserve = self._decimal(attempt["reserve_usd"])
            spent = self._decimal(self._state["spent_usd"]) + cost
            self._state["spent_usd"] = str(spent)
            self._settle_attempt(
                attempt["attempt_id"], "settled", actual_cost_usd=str(cost),
                http_status=response.status_code, ended_at_utc=_utc_now(), **metadata,
            )
            self._state["in_flight"] = []
            if cost > reserve:
                self._state["status"] = "stopped"
                self._state["stop_reason"] = "cost_exceeded_reserve"
            elif spent + self._decimal(self._state["retained_unknown_usd"]) > self.usd_cap:
                self._state["status"] = "stopped"
                self._state["stop_reason"] = "usd_cap_exceeded"
            self._persist()
            self._condition.notify_all()
            if self._state["status"] == "stopped":
                raise BudgetGateError(self._state["stop_reason"])

    def fail(self, request: httpx.Request, reason: str) -> None:
        with self._condition:
            error = self._stop_unknown(request, reason)
            if error is not None:
                return

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            return deepcopy(self._state)


class GuardedClient(httpx.Client):
    """httpx client whose every send is admitted and settled by one gate."""

    def __init__(self, gate: P3SpendGate, *, require_role: bool = False, **kwargs: Any) -> None:
        self._spend_gate = gate
        self._require_role = require_role
        super().__init__(**kwargs)

    def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        admitted = False
        try:
            if kwargs.get("follow_redirects") is True:
                raise BudgetGateError("request_contract_redirect_override")
            kwargs["follow_redirects"] = False
            role = _active_model_role.get() if self._require_role else None
            if self._require_role and role not in _ROLE_OUTPUT_LIMITS:
                raise BudgetGateError("request_role_missing")
            self._spend_gate.begin(request, role=role)
            admitted = True
            response = super().send(request, **kwargs)
            response.read()
            self._spend_gate.complete(response)
            return response
        except Exception:
            if admitted:
                self._spend_gate.fail(request, "transport_unknown")
            raise


class GuardedAsyncClient(httpx.AsyncClient):
    """Async equivalent that does not block the event loop while serialized."""

    def __init__(self, gate: P3SpendGate, *, require_role: bool = False, **kwargs: Any) -> None:
        self._spend_gate = gate
        self._require_role = require_role
        super().__init__(**kwargs)

    async def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        admitted = False
        try:
            if kwargs.get("follow_redirects") is True:
                raise BudgetGateError("request_contract_redirect_override")
            kwargs["follow_redirects"] = False
            role = _active_model_role.get() if self._require_role else None
            if self._require_role and role not in _ROLE_OUTPUT_LIMITS:
                raise BudgetGateError("request_role_missing")
            await asyncio.to_thread(self._spend_gate.begin, request, role=role)
            admitted = True
            response = await super().send(request, **kwargs)
            await response.aread()
            await asyncio.to_thread(self._spend_gate.complete, response)
            return response
        except Exception:
            if admitted:
                await asyncio.to_thread(
                    self._spend_gate.fail, request, "transport_unknown"
                )
            raise
