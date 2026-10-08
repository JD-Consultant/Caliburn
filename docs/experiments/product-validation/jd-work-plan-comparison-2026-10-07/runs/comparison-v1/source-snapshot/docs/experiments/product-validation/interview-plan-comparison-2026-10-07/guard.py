"""Finite extension of the existing transport fence; original SDK bodies pass intact.

No alternate agent loop or persistence. Only this experiment admits native compact.
The 1.05M compact output reservation is a conservative engineering bound, not a
provider parameter or guaranteed invoice cap. Unknown usage retains that reserve.
"""

import importlib.util
import json
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import httpx2

_source = (
    Path(__file__).resolve().parent.parent
    / "data/full-interview-rag-2026-10-06/batch_guard.py"
)
_spec = importlib.util.spec_from_file_location("existing_batch_guard", _source)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
fingerprint = _base.fingerprint
ObservedStream = _base.ObservedStream


def digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def public(value):
    if isinstance(value, list):
        return [public(item) for item in value]
    if isinstance(value, dict):
        return {
            key: public(item)
            for key, item in value.items()
            if key != "encrypted_content"
        }
    return value


def role(payload):
    names = {item.get("name") for item in payload.get("tools", [])}
    return "A" if "revise_jd_profile" in names else "Memory"


class BatchGuard(_base.BatchGuard):
    def __init__(
        self,
        *,
        limit=Decimal(8),
        seconds=14400,
        max_generations=900,
        max_compacts=16,
        max_outbound=2000,
        max_counted_input=40000000,
        verify_frozen=lambda: None,
        **kwargs,
    ):
        super().__init__(limit=limit, seconds=seconds, **kwargs)
        self.max_generations = max_generations
        self.max_compacts = max_compacts
        self.max_outbound = max_outbound
        self.max_counted_input = max_counted_input
        self.verify_frozen = verify_frozen
        self.generations = self.compacts = self.outbound = self.counted_input = 0
        self.compact_counts = {}
        self.compact_roles = {}
        self.case = None
        self.on_a_compact = lambda: None

    def refuse(self, reason):
        self.stop_reason = reason
        raise RuntimeError(reason)

    def outbound_attempt(self, payload):
        self.verify_frozen()
        self.check(payload)
        if self.outbound >= self.max_outbound:
            self.refuse("batch outbound attempt limit reached")
        self.outbound += 1

    def count(self, payload, tokens):
        super().count(payload, tokens)
        if self.counted_input + tokens > self.max_counted_input:
            self.refuse("batch counted input token limit reached")
        self.counted_input += tokens
        key = digest({"model": payload["model"], "input": payload.get("input", [])})
        self.compact_counts[key] = tokens
        self.compact_roles[key] = role(payload)

    def admit(self, payload):
        if self.generations >= self.max_generations:
            self.refuse("batch generation attempt limit reached")
        if payload.get("max_output_tokens") != 16384:
            self.refuse("unapproved generation output bound")
        attempt = super().admit(payload)
        self.generations += 1
        return attempt

    def compact_key(self, payload):
        return digest({"model": payload["model"], "input": payload.get("input", [])})

    def admit_compact(self, payload):
        self.check(payload)
        if (
            set(payload) != {"model", "input", "service_tier"}
            or payload["service_tier"] != "default"
        ):
            self.refuse("unapproved compact payload")
        if self.compacts >= self.max_compacts:
            self.refuse("batch compact attempt limit reached")
        tokens = self.compact_counts.get(self.compact_key(payload))
        if tokens is None:
            self.refuse("compact has no matching original input count")
        if tokens > 200000:
            self.refuse("compact input exceeds 200K experiment bound")
        # Complete model window, worst long-context cache-write + output rates.
        reserve = (
            Decimal(tokens) * Decimal("0.25") + Decimal(1050000) * Decimal("0.75")
        ) / 1000000
        if self.occupied + reserve > self.limit:
            self.refuse("batch budget reached before compact")
        attempt = str(uuid4())
        self.attempts[attempt] = reserve
        self.compacts += 1
        return attempt

    def state(self):
        return {
            "spent_usd": str(self.spent),
            "occupied_usd": str(self.occupied),
            "retained_reservations": {
                key: str(value) for key, value in self.attempts.items()
            },
            "generations": self.generations,
            "compacts": self.compacts,
            "outbound": self.outbound,
            "counted_input": self.counted_input,
            "stop_reason": self.stop_reason,
        }


class GuardedTransport(_base.GuardedTransport):
    def record(self, event, **fields):
        super().record(event, case=self.guard.case, **fields)

    async def handle_async_request(self, request):
        if (
            request.url.host != "api.openai.com"
            or request.url.scheme != "https"
            or request.method != "POST"
        ):
            raise RuntimeError("Only direct OpenAI POST HTTPS allowed")
        payload = json.loads(request.content)
        path = request.url.path
        if path not in {
            "/v1/responses",
            "/v1/responses/input_tokens",
            "/v1/responses/compact",
        }:
            raise RuntimeError("Endpoint not admitted by this experiment")
        self.guard.outbound_attempt(payload)
        if path == "/v1/responses/input_tokens":
            response = await self.inner.handle_async_request(request)
            await response.aread()
            if response.status_code == 200:
                tokens = response.json()["input_tokens"]
                self.guard.count(payload, tokens)
                self.record(
                    "count",
                    fingerprint=fingerprint(payload),
                    input_tokens=tokens,
                    role=role(payload),
                    input_sha256=digest(payload.get("input", [])),
                )
            return response
        compact = path.endswith("/compact")
        request_role = (
            self.guard.compact_roles.get(self.guard.compact_key(payload))
            if compact
            else role(payload)
        )
        try:
            attempt = (
                self.guard.admit_compact(payload)
                if compact
                else self.guard.admit(payload)
            )
        except RuntimeError as error:
            self.record("blocked", reason=str(error), **self.guard.state())
            raise
        items = payload.get("input", [])
        self.record(
            "admitted",
            attempt=attempt,
            endpoint=path,
            role=request_role,
            fingerprint=fingerprint(payload),
            instructions_sha256=digest(payload.get("instructions", "")),
            tools_sha256=digest(payload.get("tools", [])),
            input=public(items),
            request=public(payload),
            input_item_sha256=[digest(item) for item in items],
            **self.guard.state(),
        )

        def observe(body):
            if body and (body.get("error") or {}).get("code") == "rate_limit_exceeded":
                self.record("rate_limited", attempt=attempt, **self.guard.state())
                return  # Preserve reserve; the real bounded product retry owner decides.
            usage = body.get("usage") if body else None
            if (
                not compact
                and body
                and (
                    body.get("model") != "gpt-6-luna"
                    or body.get("service_tier") != "default"
                )
            ):
                usage = None
            self.guard.settle(attempt, usage)
            output = body.get("output", []) if body else []
            self.record(
                "received",
                attempt=attempt,
                endpoint=path,
                role=request_role,
                usage=usage,
                response_id=body.get("id") if body else None,
                output=public(output),
                output_item_sha256=[digest(item) for item in output],
                **self.guard.state(),
            )
            if compact and request_role == "A" and usage and not self.guard.stop_reason:
                self.guard.on_a_compact()

        try:
            response = await self.inner.handle_async_request(request)
        except BaseException:
            observe(None)
            raise
        if response.status_code == 200 and payload.get("stream"):
            return httpx2.Response(
                response.status_code,
                headers=response.headers,
                stream=ObservedStream(response.stream, observe),
                extensions=response.extensions,
            )
        await response.aread()
        if response.status_code == 429:
            self.record(
                "rate_limited", attempt=attempt, http_status=429, **self.guard.state()
            )
            return response
        observe(response.json() if response.status_code == 200 else None)
        return response
