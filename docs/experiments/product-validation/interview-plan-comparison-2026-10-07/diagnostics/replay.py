"""Finite no-key SDK cleanup/serde/original-saver diagnostic, never business writes.

Reconstructs terminal envelopes from saved public response output and usage. It
cannot reproduce private encrypted reasoning or original wire chunk boundaries.
Only local MockTransport and read-only original PostgreSQL saver access are used.
"""

import argparse
import asyncio
import gc
import json
import sys
import time
from pathlib import Path

import httpx2
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    create_response,
    create_responses_client,
)
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from guard import ObservedStream  # noqa: E402


class ReplayStream(httpx2.AsyncByteStream):
    def __init__(self, body):
        self.body = body

    async def __aiter__(self):
        created = {"type": "response.created", "response": {**self.body, "output": []}}
        completed = {"type": "response.completed", "response": self.body}
        for event in [created, completed]:
            await asyncio.sleep(0)
            yield ("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode()
        await asyncio.sleep(0)
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        return


def load():
    directory = HERE.parent / "formal/warehouse-r1-P1"
    rows = [json.loads(s) for s in (directory / "provider-trace.jsonl").read_text(encoding="utf-8").splitlines()]
    admitted = {r["attempt"]: r for r in rows if r["event"] == "admitted"}
    received = [r for r in rows if r["event"] == "received"]
    cases = [
        (admitted[r["attempt"]]["request"], r)
        for r in received
        if admitted[r["attempt"]]["request"]["stream"]
    ]
    case = json.loads((directory / "case.json").read_text(encoding="utf-8"))
    witnesses = [json.loads(s) for s in (directory / "checkpoint-witness.jsonl").read_text(encoding="utf-8").splitlines()]
    return cases, case, witnesses


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["serde", "streams", "combined"])
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        raise ValueError("Finite diagnostic must be at most two minutes")
    cases, case, witnesses = load()
    started = time.monotonic()
    serde = create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
    iterations = 0
    responses = 0
    read_checkpoints = 0
    queue = []
    template = json.loads((HERE.parents[4] / "apps/api/tests/fixtures/native-response.json").read_text(encoding="utf-8"))

    async def reply(request):
        if request.url.host != "api.openai.com" or request.url.path != "/v1/responses":
            raise RuntimeError("Diagnostic permits only local mocked responses")
        body = queue.pop(0)
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=ObservedStream(ReplayStream(body), lambda _: None),
        )

    connection = make_conninfo(
        "postgresql://intplan_test:intplan-local-test@127.0.0.1:55447/caliburn_intplan_test",
        options="-c search_path=" + case["schema"],
    )
    async with AsyncPostgresSaver.from_conn_string(connection, serde=serde) as saver:
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(reply)) as http:
            sdk = create_responses_client(api_key="offline-placeholder", timeout_seconds=10, http_client=http)
            while time.monotonic() - started < args.seconds and iterations < 2000:
                request, received = cases[iterations % len(cases)]
                if args.mode in {"serde", "combined"}:
                    encoded = serde.dumps_typed(request)
                    assert serde.loads_typed(encoded) == request
                    position = witnesses[iterations % len(witnesses)]
                    result = await saver.aget_tuple({"configurable": {"thread_id": position["thread_id"], "checkpoint_id": position["checkpoint_id"]}})
                    assert result is not None
                    read_checkpoints += 1
                if args.mode in {"streams", "combined"}:
                    body = {
                        **template,
                        "id": received["response_id"],
                        "model": "gpt-6-luna",
                        "service_tier": "default",
                        "output": received["output"],
                        "usage": received["usage"],
                        "status": "completed",
                    }
                    queue.append(body)
                    response = await create_response(sdk, ResponseRequest.from_snapshot(request))
                    assert response.id == received["response_id"]
                    responses += 1
                if iterations % 10 == 0:
                    gc.collect()
                    print(json.dumps({"iteration": iterations, "sdk_responses": responses, "checkpoint_reads": read_checkpoints}), flush=True)
                iterations += 1
            await sdk.close()
    result = {
        "mode": args.mode,
        "python": sys.version,
        "seconds": round(time.monotonic() - started, 2),
        "iterations": iterations,
        "sdk_responses": responses,
        "checkpoint_reads": read_checkpoints,
        "key_read": False,
        "provider_calls": 0,
        "business_writes": 0,
        "limits": "2000 iterations / <=120 seconds",
        "limitation": "public terminal-envelope replay; opaque reasoning and original chunk timing unavailable",
    }
    (HERE / (args.mode + "-result.json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
