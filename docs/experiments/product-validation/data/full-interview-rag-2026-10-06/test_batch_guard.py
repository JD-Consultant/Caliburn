"""Only test this experiment's external-spend fence, not the product agent loop."""

import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from hashlib import sha256
import json

import httpx2
import pytest

from batch_guard import BatchGuard, GuardedTransport


COUNT = {"model": "gpt-6-luna", "input": [{"role": "user", "content": "hello"}]}
CREATE = {**COUNT, "stream": True, "max_output_tokens": 16384, "service_tier": "default"}


def test_uncounted_request_cannot_leave():
    guard = BatchGuard(limit=Decimal("0.03"))
    with pytest.raises(RuntimeError, match="count"):
        guard.admit(CREATE)


def test_parallel_reservations_share_one_cap():
    guard = BatchGuard(limit=Decimal("0.01"))
    guard.count(COUNT, 1000)
    guard.admit(CREATE)
    with pytest.raises(RuntimeError, match="budget"):
        guard.admit(CREATE)


def test_deadline_prevents_new_calls():
    now = [0.0]
    guard = BatchGuard(limit=Decimal("0.03"), seconds=10, clock=lambda: now[0])
    guard.count(COUNT, 1000)
    guard.admit(CREATE)
    now[0] = 11
    with pytest.raises(RuntimeError, match="deadline"):
        guard.admit(CREATE)


def test_usage_settles_only_its_reservation():
    guard = BatchGuard(limit=Decimal("0.02"))
    guard.count(COUNT, 1000)
    first = guard.admit(CREATE)
    guard.admit(CREATE)
    guard.settle(first, {"input_tokens": 1000, "output_tokens": 100,
                         "total_tokens": 1100,
                         "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}})
    assert guard.occupied == Decimal("0.008467")


def test_unknown_usage_retains_reservation_and_stops():
    guard = BatchGuard(limit=Decimal("0.03"))
    guard.count(COUNT, 1000)
    attempt = guard.admit(CREATE)
    guard.settle(attempt, None)
    assert guard.occupied == Decimal("0.008317")
    with pytest.raises(RuntimeError, match="usage"):
        guard.admit(CREATE)


def test_nonapproved_model_never_leaves():
    guard = BatchGuard(limit=Decimal("0.03"))
    with pytest.raises(RuntimeError, match="model"):
        guard.count({**COUNT, "model": "another-model"}, 100)


def test_transport_preserves_stream_bytes_and_records_usage(tmp_path):
    usage = {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100,
             "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}}
    import json
    wire = b'data: {"type":"response.output_text.delta","delta":"a"}\n\n'
    wire += ("data: " + json.dumps({"type": "response.completed", "response": {
        "model": "gpt-6-luna", "service_tier": "default", "usage": usage, "error": None,
        "output": []}}) + "\n\n").encode()
    wire += b"data: [DONE]\n\n"

    async def run():
        async def handler(request):
            if request.url.path.endswith("input_tokens"):
                return httpx2.Response(200, json={"input_tokens": 1000})
            return httpx2.Response(200, content=wire, headers={"Content-Type": "text/event-stream"})
        guard = BatchGuard(limit=Decimal("0.03"))
        transport = GuardedTransport(guard, httpx2.MockTransport(handler), tmp_path / "trace.jsonl")
        async with httpx2.AsyncClient(transport=transport) as client:
            await client.post("https://api.openai.com/v1/responses/input_tokens", json=COUNT)
            async with client.stream("POST", "https://api.openai.com/v1/responses", json=CREATE) as response:
                actual = b"".join([chunk async for chunk in response.aiter_bytes()])
        assert actual == wire
        assert guard.occupied == Decimal("0.00015")
    asyncio.run(run())


def test_approved_resume_keeps_old_clock_and_unknown_reservation(tmp_path):
    journal = tmp_path / 'trace.jsonl'
    journal.write_text(json.dumps({'time': '2026-10-06T09:30:26+00:00',
                                  'occupied_usd': '0.02'}) + '\n', encoding='utf-8')
    state = {'journal_sha256': sha256(journal.read_bytes()).hexdigest(),
             'started_at': '2026-10-06T09:30:26+00:00', 'spent_usd': '0.012',
             'retained_reservations': {'old-429': '0.008'}}
    guard = BatchGuard.restore(state, journal, clock=lambda: 1000.0,
                              now=datetime(2026, 10, 6, 9, 50, 26, tzinfo=timezone.utc))
    assert guard.spent == Decimal('0.012')
    assert guard.occupied == Decimal('0.02')
    assert guard.started == -200.0
    guard.count(COUNT, 1000)
    guard.admit(CREATE)
    assert guard.occupied > Decimal('0.02')


def test_resume_refuses_modified_journal(tmp_path):
    journal = tmp_path / 'trace.jsonl'
    journal.write_text('{}\n', encoding='utf-8')
    with pytest.raises(RuntimeError, match='journal'):
        BatchGuard.restore({'journal_sha256': 'wrong'}, journal)


def test_explicit_new_window_keeps_original_spend_and_initial_start(tmp_path):
    journal = tmp_path / 'trace.jsonl'
    journal.write_text(json.dumps({'occupied_usd': '0.282'}) + '\n', encoding='utf-8')
    state = {'journal_sha256': sha256(journal.read_bytes()).hexdigest(),
             'started_at': '2026-10-06T09:30:00+00:00', 'spent_usd': '0.115',
             'retained_reservations': {'unreported': '0.167'}}
    now = [1000.0]
    guard = BatchGuard.restore(
        state, journal, clock=lambda: now[0],
        now=datetime(2026, 10, 6, 11, 10, tzinfo=timezone.utc),
        limit=Decimal('0.50'),
        deadline=datetime(2026, 10, 6, 11, 40, tzinfo=timezone.utc))
    assert guard.spent == Decimal('0.115')
    assert guard.occupied == Decimal('0.282')
    assert guard.started == -5000.0
    guard.count(COUNT, 1000)
    guard.admit(CREATE)
    assert guard.occupied == Decimal('0.290317')
    now[0] = 2800.0
    with pytest.raises(RuntimeError, match='deadline'):
        guard.admit(CREATE)


def test_explicit_new_window_rejects_its_expired_deadline(tmp_path):
    journal = tmp_path / 'trace.jsonl'
    journal.write_text(json.dumps({'occupied_usd': '0.282'}) + '\n', encoding='utf-8')
    state = {'journal_sha256': sha256(journal.read_bytes()).hexdigest(),
             'started_at': '2026-10-06T09:30:00+00:00', 'spent_usd': '0.115',
             'retained_reservations': {'unreported': '0.167'}}
    with pytest.raises(RuntimeError, match='boundary'):
        BatchGuard.restore(
            state, journal, now=datetime(2026, 10, 6, 11, 40, tzinfo=timezone.utc),
            limit=Decimal('0.50'),
            deadline=datetime(2026, 10, 6, 11, 40, tzinfo=timezone.utc))


def test_confirmed_429_is_returned_unchanged_and_still_occupied(tmp_path):
    async def run():
        async def handler(request):
            if request.url.path.endswith('input_tokens'):
                return httpx2.Response(200, json={'input_tokens': 1000})
            return httpx2.Response(429, json={'error': {'code': 'rate_limit_exceeded'}},
                                   headers={'retry-after': '10'})
        guard = BatchGuard(limit=Decimal('0.03'))
        transport = GuardedTransport(guard, httpx2.MockTransport(handler), tmp_path / 'trace.jsonl')
        async with httpx2.AsyncClient(transport=transport) as client:
            await client.post('https://api.openai.com/v1/responses/input_tokens', json=COUNT)
            response = await client.post('https://api.openai.com/v1/responses', json=CREATE)
        assert response.status_code == 429
        assert response.headers['retry-after'] == '10'
        assert guard.occupied == Decimal('0.008317')
        assert guard.stop_reason is None
        guard.admit(CREATE)
        assert guard.occupied == Decimal('0.016634')
    asyncio.run(run())


@pytest.mark.parametrize('body', [
    {'type':'error','code':'rate_limit_exceeded','message':'wait'},
    {'error':{'code':'rate_limit_exceeded','message':'wait'}},
])
def test_stream_rate_limit_preserves_wire_and_reservation(tmp_path, body):
    wire = ('data: ' + json.dumps(body) + '\n\n').encode()
    async def run():
        async def handler(request):
            if request.url.path.endswith('input_tokens'):
                return httpx2.Response(200, json={'input_tokens': 1000})
            return httpx2.Response(200, content=wire, headers={'Content-Type':'text/event-stream'})
        guard = BatchGuard(limit=Decimal('0.03'))
        transport = GuardedTransport(guard, httpx2.MockTransport(handler), tmp_path / 'trace.jsonl')
        async with httpx2.AsyncClient(transport=transport) as client:
            await client.post('https://api.openai.com/v1/responses/input_tokens', json=COUNT)
            response = await client.post('https://api.openai.com/v1/responses', json=CREATE)
        assert response.content == wire
        assert guard.stop_reason is None
        assert guard.occupied == Decimal('0.008317')
    asyncio.run(run())
