"""This batch's transparent SDK transport fence; no product state or alternate loop.

Reserve worst-case text cost before dispatch, settle using observed usage, and fail
closed on missing usage. Full native responses pass through untouched. Journals omit
credentials and opaque reasoning; the product DB remains their original owner.
"""

import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import httpx2

from caliburn.adapters.openai_pricing import GPT_6_LUNA_STANDARD_2026_09_30 as PRICING

CREATE_ONLY = {"stream", "max_output_tokens", "store", "background", "service_tier", "include"}


def fingerprint(payload):
    context = {key: value for key, value in payload.items() if key not in CREATE_ONLY}
    return sha256(json.dumps(context, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def public_items(items):
    return [{key: value for key, value in item.items() if key != "encrypted_content"}
            for item in items]


class BatchGuard:
    def __init__(self, *, limit=Decimal("0.30"), seconds=3600, clock=time.monotonic):
        self.limit = limit
        self.seconds = seconds
        self.clock = clock
        self.started = None
        self.stop_reason = None
        self.counts = {}
        self.attempts = {}
        self.spent = Decimal(0)
        self.resume_journal_digest = None

    @classmethod
    def restore(cls, state, journal, *, clock=time.monotonic, now=None,
                limit=Decimal("0.30"), deadline=None):
        """Keep original accounting; extend a boundary only with explicit approval."""
        source = Path(journal)
        digest = sha256(source.read_bytes()).hexdigest()
        if digest != state['journal_sha256']:
            raise RuntimeError('resume journal does not match approved evidence')
        guard = cls(clock=clock, limit=limit)
        guard.spent = Decimal(state['spent_usd'])
        guard.attempts = {key: Decimal(value) for key, value in state['retained_reservations'].items()}
        last = json.loads(source.read_text(encoding='utf-8').splitlines()[-1])
        if guard.occupied != Decimal(last['occupied_usd']):
            raise RuntimeError('resume journal occupancy mismatch')
        started = datetime.fromisoformat(state['started_at'])
        if deadline is not None:
            guard.seconds = (deadline - started).total_seconds()
        elapsed = ((now or datetime.now(timezone.utc)) - started).total_seconds()
        if elapsed < 0 or elapsed >= guard.seconds or guard.occupied >= guard.limit:
            raise RuntimeError('resume outside original batch boundary')
        guard.started = clock() - elapsed
        guard.resume_journal_digest = digest
        return guard

    @property
    def occupied(self):
        return self.spent + sum(self.attempts.values(), Decimal(0))

    def check(self, payload):
        if self.stop_reason:
            raise RuntimeError(self.stop_reason)
        if payload.get("model") != "gpt-6-luna":
            raise RuntimeError("unapproved model")
        if self.started is None:
            self.started = self.clock()
        if self.clock() - self.started >= self.seconds:
            self.stop_reason = "batch deadline reached"
            raise RuntimeError(self.stop_reason)

    def count(self, payload, tokens):
        self.check(payload)
        if type(tokens) is not int or tokens < 0:
            raise RuntimeError("invalid count")
        self.counts[fingerprint(payload)] = tokens

    def admit(self, payload):
        self.check(payload)
        if payload.get("service_tier") != "default":
            raise RuntimeError("unapproved pricing tier")
        tokens = self.counts.get(fingerprint(payload))
        if tokens is None:
            raise RuntimeError("request has no matching input count")
        reserve = PRICING.reserve_response_cost(
            input_tokens=tokens, max_output_tokens=payload.get("max_output_tokens"))
        if self.occupied + reserve > self.limit:
            self.stop_reason = "batch budget reached"
            raise RuntimeError(self.stop_reason)
        attempt = str(uuid4())
        self.attempts[attempt] = reserve
        return attempt

    def settle(self, attempt, usage):
        if not isinstance(usage, dict):
            self.stop_reason = "unknown provider usage; reservation retained"
            return
        input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        if (type(input_tokens) is not int or type(output_tokens) is not int
                or min(input_tokens, output_tokens) < 0
                or usage.get("total_tokens") != input_tokens + output_tokens):
            self.stop_reason = "invalid provider usage; reservation retained"
            return
        rates = PRICING.long_context if input_tokens > 272000 else PRICING.short_context
        details = usage.get("input_tokens_details") or {}
        cached, writes = details.get("cached_tokens"), details.get("cache_write_tokens")
        if (type(cached) is int and type(writes) is int and min(cached, writes) >= 0
                and cached + writes <= input_tokens):
            weighted = ((input_tokens - cached - writes) * rates.input_usd_per_million
                        + cached * rates.cached_input_usd_per_million
                        + writes * rates.cache_write_usd_per_million)
        else:
            # Missing cache breakdown: settle conservatively, not as zero input cost.
            weighted = input_tokens * rates.cache_write_usd_per_million
        cost = (weighted + output_tokens * rates.output_usd_per_million) / 1000000
        reserve = self.attempts.pop(attempt)
        self.spent += cost
        if cost > reserve or self.occupied > self.limit:
            self.stop_reason = "observed usage exceeded reservation"


class ObservedStream(httpx2.AsyncByteStream):
    def __init__(self, original, observer):
        self.original = original
        self.observer = observer
        self.pending = b""
        self.terminal = False

    async def __aiter__(self):
        async for chunk in self.original:
            self.pending += chunk
            while b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                if line.startswith(b"data: ") and line[6:].strip() != b"[DONE]":
                    event = json.loads(line[6:])
                    if event.get("type") in {"response.completed", "response.incomplete", "response.failed"}:
                        self.observer(event["response"])
                        self.terminal = True
                    elif isinstance(event.get('error'), dict):
                        # openai._streaming.AsyncStream accepts nested errors even
                        # without a type/event field. Use the same actual contract.
                        self.observer({'error': {'code': event['error'].get('code')},
                                       'error_event_keys': list(event)})
                        self.terminal = True
                    elif event.get('type') == 'error':
                        # The official stream can report a provider error without
                        # HTTP 429 or a Response object. Preserve it for SDK handling.
                        self.observer({'error': {'code': event.get('code')}})
                        self.terminal = True
            yield chunk

    async def aclose(self):
        try:
            await self.original.aclose()
        finally:
            if not self.terminal:
                self.observer(None)


class GuardedTransport(httpx2.AsyncBaseTransport):
    def __init__(self, guard, inner, journal):
        self.guard = guard
        self.inner = inner
        self.journal = Path(journal)
        if self.journal.exists() and self.guard.resume_journal_digest != sha256(self.journal.read_bytes()).hexdigest():
            raise RuntimeError("Use a fresh batch journal; never reset prior spending")
        if self.journal.exists():
            self.record('approved_continuation', original_journal_sha256=self.guard.resume_journal_digest,
                        occupied_usd=str(self.guard.occupied), spent_usd=str(self.guard.spent),
                        limit_usd=str(self.guard.limit),
                        remaining_seconds=self.guard.seconds - (self.guard.clock() - self.guard.started))

    def record(self, event, **fields):
        with self.journal.open("a", encoding="utf-8") as output:
            output.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                     "event": event, **fields}, ensure_ascii=False) + "\n")
            output.flush()

    async def handle_async_request(self, request):
        if request.url.host != "api.openai.com" or request.url.scheme != "https":
            raise RuntimeError("Only direct OpenAI HTTPS allowed")
        payload = json.loads(request.content)
        self.guard.check(payload)
        path = request.url.path
        if path == "/v1/responses/input_tokens":
            response = await self.inner.handle_async_request(request)
            await response.aread()
            if response.status_code == 200:
                tokens = response.json()["input_tokens"]
                self.guard.count(payload, tokens)
                self.record("count", fingerprint=fingerprint(payload), input_tokens=tokens)
            return response
        if path != "/v1/responses":
            # This short batch does not authorize unbounded compact output spending.
            self.record("blocked_endpoint", path=path)
            raise RuntimeError("Endpoint not admitted by this experiment")
        try:
            attempt = self.guard.admit(payload)
        except RuntimeError as error:
            self.record("blocked", reason=str(error), occupied_usd=str(self.guard.occupied))
            raise
        self.record("admitted", attempt=attempt, occupied_usd=str(self.guard.occupied),
                    fingerprint=fingerprint(payload), model=payload["model"],
                    instructions_sha256=sha256(payload.get("instructions", "").encode()).hexdigest(),
                    input=public_items(payload.get("input", [])))

        def observe(body):
            if body and (body.get('error') or {}).get('code') == 'rate_limit_exceeded':
                self.record('rate_limited', attempt=attempt, provider_code='rate_limit_exceeded',
                            delivery='stream', error_event_keys=body.get('error_event_keys'),
                            occupied_usd=str(self.guard.occupied))
                return
            usage = body.get("usage") if body else None
            if body and (body.get("model") != "gpt-6-luna" or body.get("service_tier") != "default"):
                usage = None
            self.guard.settle(attempt, usage)
            self.record("received", attempt=attempt, occupied_usd=str(self.guard.occupied),
                        usage=usage, response_id=body.get("id") if body else None,
                        status=body.get("status") if body else None,
                        output=public_items(body.get("output", [])) if body else [],
                        stop_reason=self.guard.stop_reason)

        try:
            response = await self.inner.handle_async_request(request)
        except BaseException:
            observe(None)
            raise
        if response.status_code == 200 and payload.get("stream"):
            return httpx2.Response(response.status_code, headers=response.headers,
                stream=ObservedStream(response.stream, observe), extensions=response.extensions)
        await response.aread()
        if (response.status_code == 429
                and response.json().get('error', {}).get('code') == 'rate_limit_exceeded'):
            # Preserve the response/Retry-After for the product's bounded retry owner.
            # Do not assume zero billing: this attempt's reserve remains occupied.
            self.record('rate_limited', attempt=attempt, http_status=429,
                        provider_code='rate_limit_exceeded',
                        retry_after=response.headers.get('retry-after'),
                        occupied_usd=str(self.guard.occupied))
            return response
        observe(response.json() if response.status_code == 200 else None)
        return response

    async def aclose(self):
        await self.inner.aclose()
