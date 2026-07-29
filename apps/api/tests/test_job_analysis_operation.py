"""T5:one-stage operation ＋ 薄 OpenRouter adapter。

全程 no-network:transport 是 mock,每個測試都斷言它**只被呼叫一次**——隱藏 retry
會讓「一次 operation ＝ 一次呼叫」這條 wire invariant 悄悄失效,而且付費。
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from app.job_analysis.application import (
    ConversationTurn,
    OperationOutcome,
    TurnSpeaker,
    build_context_packet,
    render_context_packet,
    run_task_analysis_operation,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
    TaskFields,
)
from app.job_analysis.llm import (
    TASK_ANALYSIS_INSTRUCTIONS,
    TASK_ANALYSIS_RESULT_SCHEMA_NAME,
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    SignalAnchor,
    SignalDisposition,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
    task_analysis_result_provider_schema,
)
from app.job_analysis.providers import (
    CHAT_COMPLETIONS_URL,
    OpenRouterAdapter,
    OpenRouterConfig,
    ProviderFailureKind,
    TransportResponse,
)


EMPLOYEE_TEXT = "我每週要出一份營運週報"

CONFIG = OpenRouterConfig(
    model="anthropic/claude-opus-5",
    provider_order=("anthropic",),
    max_output_tokens=4096,
    timeout_seconds=90.0,
)


class RecordingTransport:
    """記錄每一次呼叫;`raises` 用來模擬 transport 層的例外。"""

    def __init__(self, response: TransportResponse | None = None, raises=None):
        self.response = response
        self.raises = raises
        self.calls: list[dict] = []

    async def __call__(self, *, url, headers, body, timeout):
        self.calls.append(
            {"url": url, "headers": headers, "body": body, "timeout": timeout}
        )
        if self.raises is not None:
            raise self.raises
        return self.response


def chat_response(content: str, **overrides) -> TransportResponse:
    choice = {"message": {"content": content, "refusal": None}, "finish_reason": "stop"}
    choice.update(overrides)
    return TransportResponse(status_code=200, body={"choices": [choice]})


def packet():
    return build_context_packet(
        transcript=(
            ConversationTurn(
                turn_id="turn-1", speaker=TurnSpeaker.CONSULTANT, text="說說你的一週?"
            ),
            ConversationTurn(
                turn_id="turn-2", speaker=TurnSpeaker.EMPLOYEE, text=EMPLOYEE_TEXT
            ),
        ),
        current_turn_id="turn-2",
        work_model=CurrentWorkModel(
            tasks=(
                Task(
                    task_id="task-1",
                    statement="每週彙整營運週報",
                    action="彙整",
                    object="營運週報",
                    support_links=(
                        SupportLink(
                            source_ref=SourceRef(
                                kind=SourceKind.EMPLOYEE_TURN, id="turn-2"
                            ),
                            quote=EMPLOYEE_TEXT,
                        ),
                    ),
                ),
            )
        ),
    )


def valid_result_json(quote: str = EMPLOYEE_TEXT) -> str:
    return TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(SignalAnchor(turn_ordinal=2, quote=quote),),
                identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.ADD,
                    task_fields=TaskFields(
                        statement="每週追蹤缺料", action="追蹤", object="缺料狀況"
                    ),
                ),
            ),
        ),
        next_question=NextQuestion(text="週報交給誰?", purpose="釐清產出對象"),
    ).model_dump_json()


async def run(transport) -> tuple:
    adapter = OpenRouterAdapter(
        config=CONFIG, api_key="sk-test", transport=transport
    )
    current = packet()
    return await run_task_analysis_operation(packet=current, adapter=adapter), current


# ── wire invariants(ADR 0040 決定 26)──────────────────────────────────────


async def test_a_verified_round_makes_exactly_one_call_with_the_pinned_route():
    transport = RecordingTransport(chat_response(valid_result_json()))
    result, _ = await run(transport)

    assert result.outcome is OperationOutcome.VERIFIED
    assert result.report.is_valid
    assert len(transport.calls) == 1

    call = transport.calls[0]
    body = call["body"]
    assert call["url"] == CHAT_COMPLETIONS_URL
    assert call["headers"]["Authorization"] == "Bearer sk-test"
    assert body["model"] == "anthropic/claude-opus-5"
    assert body["stream"] is False
    assert body["provider"] == {
        "order": ["anthropic"],
        "only": ["anthropic"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": TASK_ANALYSIS_RESULT_SCHEMA_NAME,
            "strict": True,
            "schema": task_analysis_result_provider_schema(),
        },
    }


async def test_the_provider_only_ever_sees_the_rendered_packet():
    """packet 的內部模型沒有路徑可以送出去,內部 ID 也就不會外洩。"""
    transport = RecordingTransport(chat_response(valid_result_json()))
    _, current = await run(transport)

    messages = transport.calls[0]["body"]["messages"]
    assert messages[0] == {"role": "system", "content": TASK_ANALYSIS_INSTRUCTIONS}
    assert messages[1] == {"role": "user", "content": render_context_packet(current)}

    wire = json.dumps(transport.calls[0]["body"], ensure_ascii=False)
    for internal_id in ("task-1", "turn-1", "turn-2"):
        assert internal_id not in wire


@pytest.mark.parametrize(
    ("model", "provider_order"),
    [
        ("openrouter/auto", ("anthropic",)),
        ("anthropic/claude-opus-5:free", ("anthropic",)),
        ("~anthropic/claude-opus-5", ("anthropic",)),
        ("claude-opus-5", ("anthropic",)),
        ("anthropic/claude-opus-5", ()),
    ],
)
def test_the_route_must_be_exact(model, provider_order):
    with pytest.raises(ValidationError):
        OpenRouterConfig(
            model=model,
            provider_order=provider_order,
            max_output_tokens=4096,
            timeout_seconds=90.0,
        )


# ── 每種結局都有名字,而且都只呼叫一次 ────────────────────────────────────


async def test_output_that_is_not_the_frozen_contract_is_invalid_output():
    transport = RecordingTransport(chat_response('{"work_signals": []}'))
    result, _ = await run(transport)
    assert result.outcome is OperationOutcome.INVALID_OUTPUT
    assert "TaskAnalysisResult.v1" in result.detail
    assert result.result is None
    assert len(transport.calls) == 1


async def test_output_that_breaks_a_deterministic_rule_is_rejected_with_its_report():
    transport = RecordingTransport(chat_response(valid_result_json("我從來沒說過這句")))
    result, _ = await run(transport)
    assert result.outcome is OperationOutcome.REJECTED
    assert result.result is not None
    assert not result.report.is_valid
    assert not result.is_applicable
    assert len(transport.calls) == 1


async def test_a_refusal_is_not_a_failure():
    transport = RecordingTransport(
        TransportResponse(
            status_code=200,
            body={"choices": [{"message": {"refusal": "I can't help with that."}}]},
        )
    )
    result, _ = await run(transport)
    assert result.outcome is OperationOutcome.REFUSED
    assert result.detail == "I can't help with that."
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("make_transport", "expected"),
    [
        (
            lambda: RecordingTransport(raises=httpx.TimeoutException("deadline")),
            ProviderFailureKind.TIMEOUT,
        ),
        (
            lambda: RecordingTransport(raises=httpx.ConnectError("refused")),
            ProviderFailureKind.CONNECTION,
        ),
        (
            lambda: RecordingTransport(TransportResponse(status_code=503, text="upstream")),
            ProviderFailureKind.HTTP_STATUS,
        ),
        (
            lambda: RecordingTransport(TransportResponse(status_code=200, body={})),
            ProviderFailureKind.MALFORMED_RESPONSE,
        ),
        (
            lambda: RecordingTransport(chat_response("{partial", finish_reason="length")),
            ProviderFailureKind.TRUNCATED,
        ),
    ],
)
async def test_provider_failures_are_typed_and_never_retried(make_transport, expected):
    transport = make_transport()
    result, _ = await run(transport)
    assert result.outcome is OperationOutcome.FAILED
    assert result.detail.startswith(expected.value)
    assert len(transport.calls) == 1
