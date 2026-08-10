"""One-stage OPKS operation；全程 mock transport、零網路。"""

from __future__ import annotations

import json

import pytest

from app.job_analysis.application import (
    OperationOutcome,
    build_opks_context_packet,
    render_opks_context_packet,
    run_opks_operation,
)
from app.core.domain import (
    CurrentJdOpks,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)
from app.job_analysis.llm import (
    OPKS_INSTRUCTIONS,
    OPKS_RESULT_WIRE_SCHEMA_NAME,
    OpksDecision,
    OpksResultWire,
    OpksWireItem,
    opks_result_wire_provider_schema,
)
from app.job_analysis.providers import (
    OpenRouterAdapter,
    OpenRouterConfig,
    TransportResponse,
)


CONFIG = OpenRouterConfig(
    model="anthropic/claude-opus-5",
    provider_order=("anthropic",),
    max_output_tokens=1024,
    timeout_seconds=90,
)


class RecordingTransport:
    def __init__(self, response: TransportResponse):
        self.response = response
        self.calls: list[dict] = []

    async def __call__(self, *, url, headers, body, timeout):
        self.calls.append(
            {"url": url, "headers": headers, "body": body, "timeout": timeout}
        )
        return self.response


def source(source_id: str = "turn-private") -> SourceRef:
    return SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=source_id)


def packet():
    task = Task(
        task_id="task-private",
        statement="彙整營運週報",
        action="彙整",
        object="營運週報",
        support_links=(
            SupportLink(
                source_ref=source(),
                quote="我每週彙整營運週報",
            ),
        ),
    )
    knowledge = OpksItem(
        entity_id="knowledge-private",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運指標定義",
        evidence_links=(
            OpksEvidenceLink(
                source_ref=source("turn-old"),
                quote="我會先確認營運指標定義",
            ),
        ),
    )
    return build_opks_context_packet(
        selected_task=task,
        current_opks=CurrentJdOpks(items=(knowledge,)),
    )


def response(content: str, *, status: int = 200) -> TransportResponse:
    if status != 200:
        return TransportResponse(status_code=status, text="upstream")
    return TransportResponse(
        status_code=200,
        body={
            "model": CONFIG.model,
            "choices": [
                {
                    "message": {"content": content, "refusal": None},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def valid_json() -> str:
    return OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.KNOWLEDGE,
                decision=OpksDecision.REUSE_EXISTING,
                target_ordinal=1,
                text="",
            ),
        )
    ).model_dump_json()


async def run(content: str):
    transport = RecordingTransport(response(content))
    adapter = OpenRouterAdapter(
        config=CONFIG,
        api_key="sk-test",
        transport=transport,
    )
    current = packet()
    outcome = await run_opks_operation(
        packet=current,
        adapter=adapter,
        operation_id="operation-1",
    )
    return outcome, transport, current


async def test_verified_operation_uses_only_the_opks_contract_and_calls_once():
    outcome, transport, current = await run(valid_json())

    assert outcome.outcome is OperationOutcome.VERIFIED
    assert outcome.report is not None and outcome.report.is_valid
    assert len(transport.calls) == 1
    body = transport.calls[0]["body"]
    assert body["messages"] == [
        {"role": "system", "content": OPKS_INSTRUCTIONS},
        {"role": "user", "content": render_opks_context_packet(current)},
    ]
    assert body["response_format"]["json_schema"] == {
        "name": OPKS_RESULT_WIRE_SCHEMA_NAME,
        "strict": True,
        "schema": opks_result_wire_provider_schema(),
    }
    rendered_request = json.dumps(body, ensure_ascii=False)
    for internal_id in (
        "task-private",
        "knowledge-private",
        "turn-private",
        "turn-old",
    ):
        assert internal_id not in rendered_request


async def test_parseable_output_that_breaks_mapping_is_rejected():
    bad = OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.OUTPUT,
                decision=OpksDecision.REUSE_EXISTING,
                target_ordinal=1,
                text="",
            ),
        )
    ).model_dump_json()
    outcome, transport, _ = await run(bad)

    assert outcome.outcome is OperationOutcome.REJECTED
    assert outcome.report is not None and not outcome.report.is_valid
    assert len(transport.calls) == 1


async def test_invalid_output_is_named_and_not_retried():
    outcome, transport, _ = await run('{"items":"not-an-array"}')

    assert outcome.outcome is OperationOutcome.INVALID_OUTPUT
    assert OPKS_RESULT_WIRE_SCHEMA_NAME in outcome.detail
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("transport_response", "expected"),
    [
        (
            TransportResponse(
                status_code=200,
                body={
                    "model": CONFIG.model,
                    "choices": [{"message": {"refusal": "無法處理"}}],
                },
            ),
            OperationOutcome.REFUSED,
        ),
        (response("", status=503), OperationOutcome.FAILED),
    ],
)
async def test_refusal_and_failure_are_named_and_never_retried(
    transport_response, expected
):
    transport = RecordingTransport(transport_response)
    adapter = OpenRouterAdapter(
        config=CONFIG,
        api_key="sk-test",
        transport=transport,
    )

    outcome = await run_opks_operation(
        packet=packet(),
        adapter=adapter,
        operation_id="operation-1",
    )

    assert outcome.outcome is expected
    assert len(transport.calls) == 1
