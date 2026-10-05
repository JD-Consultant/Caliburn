"""Serial study HTTP hooks; no credentials, dispatch, retry or native persistence.

Share one instance across R/S/M. Before attaching both hooks to the direct httpx2
client, assign guard.frozen_policy = manifest returned by verify_prepared().
No policy means no sends. HTTP errors, including 429, stop without rate retries.
trace.jsonl is an exclusive, fsynced admission/settlement journal, not a native
checkpoint. An unresolved send keeps its reserve and blocks all further sends;
reopening the same directory is refused, not treated as fresh spending authority.

Count/create shapes use the product ResponseRequest and OpenAI SDK 3.20.0.
https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count
https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint
Compact has no output-limit parameter: 128K is an explicit reservation assumption,
not a provider invoice guarantee. Known excess usage is recorded before stopping.
"""

import json
import os
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, Never

import httpx2
from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.openai_responses import ResponseRequest, compaction_payload
from openai.types.responses import Response
from openai.types.responses.compacted_response import CompactedResponse
from openai.types.responses.response_usage import ResponseUsage
from pydantic import ValidationError

COUNT_ESTIMATE_USD = Decimal("0.0001")
TOTAL_LIMIT_USD = Decimal("2")
# Finite research ceilings retained from the preceding study, not product policy.
MAX_OUTBOUND_CALLS = 2200
MAX_GENERATION_CALLS = 900
MAX_COMPACTION_CALLS = 16
MAX_INPUT_TOKENS = 35_000_000
MODEL = "gpt-6-luna"
COUNT_PATH = "/v1/responses/input_tokens"
CREATE_PATH = "/v1/responses"
COMPACT_PATH = "/v1/responses/compact"
_CREATE_OPTIONS = {
    "stream": False,
    "max_output_tokens": 16_384,
    "store": False,
    "background": False,
    "service_tier": "default",
    "include": ["reasoning.encrypted_content"],
}


class ResearchStop(BaseException):
    """Stop the study outside the product's Exception-based retry boundary."""


@dataclass(frozen=True)
class PendingRequest:
    request: httpx2.Request
    path: str
    payload: dict[str, Any]  # JSON/SDK boundary only; never a product domain value.
    body_sha256: str
    phase: dict[str, str]
    reserved_usd: Decimal
    started: float


class StudyGuard:
    def __init__(
        self,
        output_dir: Path,
        *,
        batch_usd: Decimal,
        seconds: int,
        prior_usd: Decimal = Decimal("1.322929315"),
    ) -> None:
        if (
            not isinstance(batch_usd, Decimal)
            or not batch_usd.is_finite()
            or batch_usd <= 0
            or not isinstance(prior_usd, Decimal)
            or not prior_usd.is_finite()
            or not 0 <= prior_usd <= TOTAL_LIMIT_USD
            or type(seconds) is not int
            or seconds <= 0
        ):
            raise ValueError("Require finite positive batch USD/time and prior USD within $2")
        self.phase: dict[str, str] = {}
        self._frozen_policy: dict[str, Any] | None = None
        self.prior_usd = prior_usd
        self.batch_usd = batch_usd
        self.seconds = seconds
        self.started = time.monotonic()
        self.outbound_calls = 0
        self.count_calls = 0
        self.generation_calls = 0
        self.compaction_calls = 0
        self.count_estimated_usd = Decimal(0)
        self.actual_estimated_usd = Decimal(0)
        self.admitted_input_tokens = 0
        self.stop_reason: str | None = None
        self.pending: PendingRequest | None = None
        self.counts: dict[str, int] = {}
        self.window_counts: dict[str, int] = {}
        self.usage = dict.fromkeys(
            (
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
                "total_tokens",
            ),
            0,
        )
        self.profile = model_profile(MODEL)
        self.trace_path = output_dir / "trace.jsonl"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with self.trace_path.open("x", encoding="utf-8"):
                pass
        except FileExistsError:
            raise ResearchStop("existing_journal") from None
        except OSError:
            raise ResearchStop("journal_failure") from None
        self._event({"event": "guard_started"})

    @property
    def frozen_policy(self) -> dict[str, Any] | None:
        return deepcopy(self._frozen_policy)

    @frozen_policy.setter
    def frozen_policy(self, manifest: dict[str, Any]) -> None:
        """Bind the verified manifest once; caller mutation cannot change the freeze."""
        if self._frozen_policy is not None:
            raise ValueError("Frozen policy already assigned")
        if not isinstance(manifest, dict):
            raise ValueError("Expected the verified manifest")
        self._frozen_policy = deepcopy(manifest)

    async def request(self, request: httpx2.Request) -> None:
        self._require_running()
        if self.pending is not None:
            self._stop("unsettled_prior_request")
        url = request.url
        if (
            request.method != "POST"
            or url.scheme != "https"
            or url.host != "api.openai.com"
            or url.port not in (None, 443)
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in (COUNT_PATH, CREATE_PATH, COMPACT_PATH)
            or request.headers.get("host") not in ("api.openai.com", "api.openai.com:443")
        ):
            self._stop("unapproved_endpoint")
        if self.outbound_calls >= MAX_OUTBOUND_CALLS:
            self._stop("call_limit")
        if set(self.phase) - {"arm", "case_id"} or any(
            not isinstance(value, str) for value in self.phase.values()
        ):
            self._stop("invalid_phase")
        try:
            payload = json.loads(await request.aread())
            self._validate_payload(url.path, payload)
        except ValueError, TypeError, KeyError, AttributeError:
            self._stop("unapproved_request")
        self._require_running()
        tokens = 0
        reserve = COUNT_ESTIMATE_USD
        if url.path == CREATE_PATH:
            counted_payload = ResponseRequest.from_snapshot(payload).count_payload()
            tokens = self._counted(self.counts, counted_payload)
            if self.generation_calls >= MAX_GENERATION_CALLS:
                self._stop("generation_limit")
            output_tokens = 16_384
        elif url.path == COMPACT_PATH:
            tokens = self._counted(self.window_counts, self._window(payload))
            if self.compaction_calls >= MAX_COMPACTION_CALLS:
                self._stop("compaction_limit")
            output_tokens = self.profile.max_output_tokens
        if url.path != COUNT_PATH:
            if (
                tokens > self.profile.max_input_tokens
                or tokens + output_tokens > self.profile.context_window_tokens
            ):
                self._stop("model_capacity_limit")
            if self.admitted_input_tokens + tokens > MAX_INPUT_TOKENS:
                self._stop("cumulative_input_limit")
            reserve = self.profile.pricing.reserve_response_cost(
                input_tokens=tokens, max_output_tokens=output_tokens
            )
        if self._over_budget(self._occupied() + reserve):
            self._stop("budget_limit")
        phase = self.phase.copy()
        self.pending = PendingRequest(
            request,
            url.path,
            payload,
            sha256(request.content).hexdigest(),
            phase,
            Decimal(0) if url.path == COUNT_PATH else reserve,
            time.monotonic(),
        )
        self.outbound_calls += 1
        self.admitted_input_tokens += tokens
        if url.path == COUNT_PATH:
            self.count_calls += 1
            self.count_estimated_usd += COUNT_ESTIMATE_USD
        elif url.path == CREATE_PATH:
            self.generation_calls += 1
        else:
            self.compaction_calls += 1
        # Every admitted call is durable before the hook returns to the transport.
        self._event(
            {
                "event": "request",
                "path": url.path,
                "request_id": self.outbound_calls,
                "request_sha256": self.pending.body_sha256,
                "reserve_usd": str(reserve),
                "counted_input_tokens": tokens,
                "payload": _public_document(payload),
            },
            phase=phase,
        )

    async def response(self, response: httpx2.Response) -> None:
        pending = self.pending
        if (
            pending is None
            or pending.request is not response.request
            or sha256(response.request.content).hexdigest() != pending.body_sha256
        ):
            self._stop("unadmitted_response")
        try:
            await response.aread()
        except Exception:
            self._stop("response_read_failure")
        event: dict[str, object] = {
            "event": "response",
            "path": pending.path,
            "request_id": self.outbound_calls,
            "request_sha256": pending.body_sha256,
            "http_status": response.status_code,
            "duration_seconds": time.monotonic() - pending.started,
        }
        if response.status_code != 200:
            # Error text can echo secrets; keep its identity, not arbitrary provider text.
            self._event(
                {**event, "body_sha256": sha256(response.content).hexdigest()}, phase=pending.phase
            )
            self._stop("provider_http_failure")
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Expected a response object")
        except ValueError:
            self._event(
                {**event, "body_sha256": sha256(response.content).hexdigest()}, phase=pending.phase
            )
            self._stop("unknown_usage")
        self._event({**event, "payload": _public_document(payload)}, phase=pending.phase)
        if pending.path == COUNT_PATH:
            tokens = payload.get("input_tokens")
            if (
                payload.get("object") != "response.input_tokens"
                or type(tokens) is not int
                or tokens < 0
            ):
                self._stop("invalid_remote_count")
            self.counts[_fingerprint(pending.payload, pending.phase)] = tokens
            key = _fingerprint(self._window(pending.payload), pending.phase)
            self.window_counts[key] = max(tokens, self.window_counts.get(key, 0))
        else:
            usage, cost = self._usage_cost(payload, pending.path)
            self.usage["input_tokens"] += usage.input_tokens
            self.usage["output_tokens"] += usage.output_tokens
            self.usage["total_tokens"] += usage.total_tokens
            self.usage["reasoning_tokens"] += usage.output_tokens_details.reasoning_tokens
            self.usage["cached_input_tokens"] += usage.input_tokens_details.cached_tokens
            self.usage["cache_write_input_tokens"] += usage.input_tokens_details.cache_write_tokens
            self.actual_estimated_usd += cost
        self.pending = None
        self._event(
            {"event": "settled", "path": pending.path, "request_id": self.outbound_calls},
            phase=pending.phase,
        )
        if self._over_budget(self._occupied()):
            self._stop("budget_limit_after_settlement")
        if pending.path == CREATE_PATH and payload.get("status") != "completed":
            self._stop("provider_incomplete")
        self._require_running()

    def summary(self) -> dict[str, object]:
        """JSON-safe totals; usage is observed, USD is a pinned text-token estimate."""
        return {
            **self.usage,
            "outbound_calls": self.outbound_calls,
            "count_calls": self.count_calls,
            "generation_calls": self.generation_calls,
            "compaction_calls": self.compaction_calls,
            "admitted_input_tokens": self.admitted_input_tokens,
            "prior_usd": str(self.prior_usd),
            "batch_limit_usd": str(self.batch_usd),
            "cumulative_limit_usd": str(TOTAL_LIMIT_USD),
            "count_estimated_usd": str(self.count_estimated_usd),
            "actual_estimated_usd": str(self.actual_estimated_usd),
            "pending_reserved_usd": str(self.pending.reserved_usd if self.pending else Decimal(0)),
            "batch_occupied_usd": str(self._occupied()),
            "cumulative_occupied_usd": str(self.prior_usd + self._occupied()),
            "pending_request_sha256": self.pending.body_sha256 if self.pending else None,
            "cost_basis": self.profile.pricing.cost_basis,
            "compact_output_reserve_tokens": self.profile.max_output_tokens,
            "elapsed_seconds": time.monotonic() - self.started,
            "seconds_limit": self.seconds,
            "stop_reason": self.stop_reason,
        }

    def _occupied(self) -> Decimal:
        return (
            self.actual_estimated_usd
            + self.count_estimated_usd
            + (self.pending.reserved_usd if self.pending else Decimal(0))
        )

    def _over_budget(self, occupied: Decimal) -> bool:
        return occupied > self.batch_usd or occupied + self.prior_usd > TOTAL_LIMIT_USD

    def _require_running(self) -> None:
        if self.stop_reason is not None:
            raise ResearchStop(self.stop_reason)
        if time.monotonic() - self.started >= self.seconds:
            self._stop("time_limit")

    def _stop(self, reason: str) -> Never:
        if self.stop_reason is None:
            self.stop_reason = reason
            self._event(
                {"event": "stopped", "reason": reason},
                phase=self.pending.phase if self.pending else None,
            )
        raise ResearchStop(self.stop_reason)

    def _counted(self, counts: dict[str, int], payload: dict[str, Any]) -> int:
        count = counts.get(_fingerprint(payload, self.phase))
        if count is None:
            self._stop("missing_count")
        return count

    def _validate_payload(self, path: str, payload: dict[str, Any]) -> None:
        policy = self._frozen_policy
        if policy is None:
            self._stop("missing_frozen_policy")
        arm = self.phase.get("arm")
        if (
            policy.get("model") != MODEL
            or policy.get("effort") != "high"
            or policy.get("max_output_tokens") != 16_384
            or self.phase not in policy["schedule"]
            or arm not in policy["instructions"]
            or arm not in policy["tools"]
        ):
            raise ValueError("Unapproved frozen phase or model policy")
        if not isinstance(payload, dict) or payload.get("model") != MODEL:
            raise ValueError("Unapproved model")
        if not isinstance(payload.get("input"), list):
            raise ValueError("Supply the complete native item list")
        if path == COMPACT_PATH:
            if payload != compaction_payload(model=MODEL, input_items=payload["input"]):
                raise ValueError("Unapproved compact parameters")
            return
        # A bare count is also useful for compact's complete input window.
        if path == COUNT_PATH and set(payload) == {"model", "input"}:
            return
        snapshot = {**payload, **_CREATE_OPTIONS} if path == COUNT_PATH else payload
        request = ResponseRequest.from_snapshot(snapshot)
        if (
            snapshot.get("reasoning", {}).get("effort") != "high"
            or snapshot.get("max_output_tokens") != 16_384
            or snapshot.get("stream") is not False
            or any(snapshot.get(key) != value for key, value in _CREATE_OPTIONS.items())
            or not isinstance(snapshot.get("instructions"), str)
            or not isinstance(snapshot.get("tools"), list)
            or any(tool.get("type") != "function" for tool in snapshot["tools"])
            or snapshot["instructions"] != policy["instructions"][arm]
            or snapshot["tools"] != policy["tools"][arm]
            or (path == COUNT_PATH and request.count_payload() != payload)
        ):
            raise ValueError("Unapproved generation/count contract")

    @staticmethod
    def _window(payload: dict[str, Any]) -> dict[str, Any]:
        return {"model": payload["model"], "input": payload["input"]}

    def _usage_cost(self, payload: dict[str, Any], path: str) -> tuple[ResponseUsage, Decimal]:
        try:
            usage = ResponseUsage.model_validate(payload.get("usage"), strict=True)
        except ValidationError:
            self._stop("unknown_usage")
        if not 0 <= usage.output_tokens_details.reasoning_tokens <= usage.output_tokens:
            self._stop("unknown_usage")
        snapshot = {**payload, "usage": usage}
        pricing = self.profile.pricing
        cost = (
            pricing.estimate_compaction_cost(CompactedResponse.model_construct(**snapshot))
            if path == COMPACT_PATH
            else pricing.estimate_response_cost(Response.model_construct(**snapshot))
        )
        if cost is None:
            self._stop("unknown_usage")
        return usage, cost

    def _event(self, payload: dict[str, object], *, phase: dict[str, str] | None = None) -> None:
        event = {
            **(self.phase if phase is None else phase),
            **payload,
            "timestamp": datetime.now(UTC).isoformat(),
            "elapsed_seconds": time.monotonic() - self.started,
            "accounting": self.summary(),
        }
        try:
            with self.trace_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError, ValueError, TypeError:
            self.stop_reason = "journal_failure"
            raise ResearchStop("journal_failure") from None


def _fingerprint(payload: dict[str, Any], phase: dict[str, str]) -> str:
    return sha256(
        json.dumps(
            {"phase": phase, "payload": payload},
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _public_document(value: object) -> object:
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in value.items():
            if "encrypted" in key.lower() or key.lower() in {"headers", "authorization", "api_key"}:
                encoded = (
                    item if isinstance(item, str) else json.dumps(item, sort_keys=True)
                ).encode()
                result[key] = {"sha256": sha256(encoded).hexdigest(), "bytes": len(encoded)}
            else:
                result[key] = _public_document(item)
        return result
    if isinstance(value, list):
        return [_public_document(item) for item in value]
    return value
