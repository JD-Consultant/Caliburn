"""Attributed live smoke driver:預算、錄製 transport 與真 PostgreSQL vertical。

**這裡沒有一次真實付費呼叫。** transport 全是 scripted:預算門在 HTTP 之前就要擋下
第四次呼叫,錄製只能發生在 delegate 真的被呼叫時。最後一段用真 PostgreSQL 跑完整
三回合,證明 driver 走的是現行 `submit_employee_turn()`,不是自己另做一條流程。
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.documents import load_document
from app.job_analysis.application import submit_employee_turn
from app.job_analysis.llm import (
    IdentityRelation,
    SignalDisposition,
    TaskAnalysisWire,
    WireAnchor,
    WireNextQuestion,
    WireSignal,
    WireTaskChange,
    WireTaskFields,
)
from app.job_analysis.providers import (
    OpenRouterAdapter,
    OpenRouterConfig,
    OpenRouterCatalogError,
    ProviderText,
    TransportResponse,
)
from scripts.job_analysis_live_smoke import (
    MAX_GENERATION_CALLS,
    METADATA_HEADERS,
    SMOKE_TURNS,
    LiveSmokeBudget,
    LiveSmokeBudgetExceeded,
    LiveSmokeCostUnknown,
    RecordingTransport,
    canonical_request_json,
    fetch_endpoint_snapshot,
    run_live_smoke,
)

from tests.test_job_analysis_openrouter_evidence import (
    MODEL,
    TAG,
    catalog_payload,
    endpoint_snapshot,
)


MAX_OUTPUT_TOKENS = 4096


# ── scripted plumbing ──────────────────────────────────────────────────────


class ScriptedTransport:
    """依序回固定回應。多要一次就是隱藏 retry,直接炸掉而不是悄悄過去。"""

    def __init__(self, responses: list[TransportResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self, *, url: str, headers: Any, body: Any, timeout: float
    ) -> TransportResponse:
        self.calls.append({"url": url, "headers": dict(headers), "body": dict(body)})
        if not self._responses:
            raise AssertionError("the driver asked for more provider calls than scripted")
        return self._responses.pop(0)


def metadata_block() -> dict[str, Any]:
    return {
        "requested": MODEL,
        "strategy": "direct",
        "attempt": 1,
        "endpoints": {
            "total": 1,
            "available": [{"provider": "Anthropic", "model": MODEL, "selected": True}],
        },
        "pipeline": [],
    }


def chat_response(
    content: str, *, cost: Any = 0.05, call: int = 1
) -> TransportResponse:
    return TransportResponse(
        status_code=200,
        body={
            "id": f"gen-smoke-{call:02d}",
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
            "usage": {
                "prompt_tokens": 2000,
                "completion_tokens": 800,
                "completion_tokens_details": {"reasoning_tokens": 500},
                "cost": cost,
            },
            "openrouter_metadata": metadata_block(),
        },
        text=content,
    )


def add_task_result(
    *, turn_ordinal: int, quote: str, statement: str, action: str, object_: str, question: str
) -> str:
    return TaskAnalysisWire(
        work_signals=(
            WireSignal(
                anchors=(WireAnchor(turn_ordinal=turn_ordinal, quote=quote),),
                relation=IdentityRelation.NO_MATCH,
                disposition=SignalDisposition.TASK_CHANGE,
                change=WireTaskChange.ADD,
                task=WireTaskFields(
                    statement=statement, action=action, object=object_
                ),
            ),
        ),
        next_question=WireNextQuestion(text=question),
    ).model_dump_json()


def scripted_three_turns() -> list[TransportResponse]:
    """三回合各加一項工作,anchor 逐字引用該回合的員工原文。"""
    return [
        chat_response(
            add_task_result(
                turn_ordinal=2,
                quote="我每週用 Python 和 Excel 整理服務錯誤與效能資料，做成營運週報給主管",
                statement="每週彙整服務錯誤與效能資料並產出營運週報",
                action="彙整",
                object_="營運週報",
                question="這份週報主要交給誰使用？",
            ),
            call=1,
        ),
        chat_response(
            add_task_result(
                turn_ordinal=4,
                quote="我只做上線前的測試與檢查",
                statement="在版本上線前執行測試與檢查",
                action="測試",
                object_="上線前版本",
                question="上線前檢查的結果會交給誰？",
            ),
            call=2,
        ),
        chat_response(
            add_task_result(
                turn_ordinal=6,
                quote="每月我會檢查門市帳號權限清單",
                statement="每月檢查門市帳號權限清單並轉交異常項目",
                action="檢查",
                object_="門市帳號權限清單",
                question="異常項目交出去後你還需要追蹤嗎？",
            ),
            call=3,
        ),
    ]


def build_recording(
    responses: list[TransportResponse], *, budget: LiveSmokeBudget | None = None
) -> tuple[ScriptedTransport, RecordingTransport, LiveSmokeBudget]:
    scripted = ScriptedTransport(responses)
    live_budget = budget or LiveSmokeBudget()
    recording = RecordingTransport(
        scripted,
        budget=live_budget,
        endpoint=endpoint_snapshot(),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    return scripted, recording, live_budget


def build_adapter(transport: Any) -> OpenRouterAdapter:
    return OpenRouterAdapter(
        config=OpenRouterConfig(
            model=MODEL,
            provider_order=(TAG,),
            max_output_tokens=MAX_OUTPUT_TOKENS,
            timeout_seconds=90.0,
        ),
        api_key="test-key-never-captured",
        transport=transport,
    )


# ── budget ─────────────────────────────────────────────────────────────────


def test_scenario_is_frozen_at_three_turns():
    assert len(SMOKE_TURNS) == MAX_GENERATION_CALLS == 3
    assert [turn.operation_id for turn in SMOKE_TURNS] == [
        "live-smoke-turn-01",
        "live-smoke-turn-02",
        "live-smoke-turn-03",
    ]
    assert "正式環境部署不是我負責" in SMOKE_TURNS[1].employee_text
    assert "門市帳號權限清單" in SMOKE_TURNS[2].employee_text


def test_precheck_estimate_is_derived_from_request_bytes_and_is_not_a_bound():
    """byte 數只是決定性的量級估算。**它不是 token 數的上界**——2026-08-02 實測
    3,744 bytes 對 12,168 prompt tokens，所以這個估算會低估，真正的保證是呼叫次數與
    回應後的實際 cost 結算。"""

    budget = LiveSmokeBudget()
    body = {"model": MODEL, "messages": [{"role": "user", "content": "工作內容"}]}
    estimated_input = len(canonical_request_json(body).encode("utf-8"))

    estimate = budget.precheck_or_raise(
        request_body=body,
        endpoint=endpoint_snapshot(),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    assert estimate == (
        Decimal(estimated_input) * Decimal("0.000005")
        + Decimal(MAX_OUTPUT_TOKENS) * Decimal("0.000025")
    )
    assert budget.calls == 1
    assert budget.spent_usd == Decimal("0")


def test_actual_spend_may_exceed_the_precheck_estimate_and_still_stops_the_run():
    """回歸守門:估算低估時,停線責任落在回應後的實際結算上。"""

    budget = LiveSmokeBudget(limit_usd=Decimal("0.20"))
    budget.precheck_or_raise(
        request_body={"model": MODEL},
        endpoint=endpoint_snapshot(),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    with pytest.raises(LiveSmokeBudgetExceeded, match="actual spend"):
        budget.record_actual_or_raise(cost_usd=Decimal("0.30"))


def test_precheck_refuses_once_the_call_ceiling_is_reached():
    budget = LiveSmokeBudget(calls=MAX_GENERATION_CALLS)

    with pytest.raises(LiveSmokeBudgetExceeded, match="generation call"):
        budget.precheck_or_raise(
            request_body={"model": MODEL},
            endpoint=endpoint_snapshot(),
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )


def test_precheck_refuses_when_the_estimate_alone_already_exceeds_the_cap():
    budget = LiveSmokeBudget(spent_usd=Decimal("0.70"))

    with pytest.raises(LiveSmokeBudgetExceeded, match="US\\$"):
        budget.precheck_or_raise(
            request_body={"model": MODEL},
            endpoint=endpoint_snapshot(),
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )


def test_actual_cost_accumulates_from_the_response():
    budget = LiveSmokeBudget()

    budget.record_actual_or_raise(cost_usd=Decimal("0.11"))
    budget.record_actual_or_raise(cost_usd=Decimal("0.09"))

    assert budget.spent_usd == Decimal("0.20")


@pytest.mark.parametrize("cost", [None, Decimal("-0.01")])
def test_unusable_actual_cost_stops_the_run(cost):
    budget = LiveSmokeBudget()

    with pytest.raises(LiveSmokeCostUnknown):
        budget.record_actual_or_raise(cost_usd=cost)


def test_actual_cost_over_the_limit_stops_the_run():
    budget = LiveSmokeBudget(spent_usd=Decimal("0.70"))

    with pytest.raises(LiveSmokeBudgetExceeded):
        budget.record_actual_or_raise(cost_usd=Decimal("0.10"))


async def test_budget_stop_happens_before_the_transport_is_touched():
    scripted, recording, _ = build_recording(
        scripted_three_turns(), budget=LiveSmokeBudget(spent_usd=Decimal("0.75"))
    )

    with pytest.raises(LiveSmokeBudgetExceeded):
        await recording(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": "Bearer secret"},
            body={"model": MODEL},
            timeout=90.0,
        )

    assert scripted.calls == []
    assert recording.calls == []


# ── recording transport ────────────────────────────────────────────────────


async def test_recording_transport_opts_into_metadata_and_disables_cache():
    scripted, recording, _ = build_recording(scripted_three_turns())

    await recording(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
        body={"model": MODEL},
        timeout=90.0,
    )

    assert len(scripted.calls) == 1
    sent = scripted.calls[0]["headers"]
    assert sent["X-OpenRouter-Metadata"] == "enabled"
    assert sent["X-OpenRouter-Cache"] == "false"
    assert sent["Authorization"] == "Bearer secret"
    assert METADATA_HEADERS == {
        "X-OpenRouter-Metadata": "enabled",
        "X-OpenRouter-Cache": "false",
    }


async def test_recording_transport_never_captures_the_authorization_header():
    _, recording, _ = build_recording(scripted_three_turns())

    await recording(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": "Bearer super-secret-key"},
        body={"model": MODEL},
        timeout=90.0,
    )

    captured = json.dumps(recording.calls, ensure_ascii=False)
    assert "super-secret-key" not in captured
    assert "Authorization" not in captured
    assert len(recording.responses) == 1


async def test_missing_metadata_does_not_change_the_product_outcome():
    """metadata 缺失只該讓歸因失效;產品仍照 model／parse／verifier 判定。"""
    response = chat_response("{}")
    assert response.body is not None
    response.body.pop("openrouter_metadata")
    _, recording, _ = build_recording([response])
    adapter = build_adapter(recording)

    outcome = await adapter.complete(
        instructions="x", packet_text="y", schema_name="z", schema={}
    )

    assert isinstance(outcome, ProviderText)


# ── catalog preflight ──────────────────────────────────────────────────────


def mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_preflight_reads_only_the_model_detail_endpoint():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=catalog_payload())

    async with mock_client(handler) as client:
        snapshot = await fetch_endpoint_snapshot(
            client, model=MODEL, tag=TAG, api_key="k"
        )

    assert seen == [
        "https://openrouter.ai/api/v1/models/anthropic/claude-opus-5/endpoints"
    ]
    assert snapshot.provider_name == "Anthropic"


@pytest.mark.parametrize(
    "handler, expected",
    [
        pytest.param(
            lambda request: httpx.Response(500, text="upstream down"),
            "HTTP 500",
            id="http-failure",
        ),
        pytest.param(
            lambda request: httpx.Response(200, text="not json"),
            "JSON",
            id="json-failure",
        ),
        pytest.param(
            lambda request: httpx.Response(200, json=[1, 2, 3]),
            "object",
            id="not-an-object",
        ),
        pytest.param(
            lambda request: httpx.Response(200, json={"data": {"id": MODEL, "endpoints": []}}),
            "matched 0",
            id="catalog-failure",
        ),
    ],
)
async def test_preflight_failures_stop_before_any_generation_call(handler, expected):
    async with mock_client(handler) as client:
        with pytest.raises(OpenRouterCatalogError) as caught:
            await fetch_endpoint_snapshot(client, model=MODEL, tag=TAG, api_key="k")

    assert expected in str(caught.value)


async def test_preflight_capability_loss_stops_before_any_generation_call():
    payload = catalog_payload()
    payload["data"]["endpoints"][0]["supported_parameters"].remove("reasoning_effort")

    async with mock_client(lambda request: httpx.Response(200, json=payload)) as client:
        with pytest.raises(OpenRouterCatalogError, match="reasoning_effort"):
            await fetch_endpoint_snapshot(client, model=MODEL, tag=TAG, api_key="k")


# ── real PostgreSQL vertical (no network) ──────────────────────────────────


async def test_three_turn_vertical_runs_the_product_path_on_postgresql(
    postgres_session_factory,
    cleanup_job_analysis_rows,
    tmp_path: Path,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    scripted, recording, budget = build_recording(scripted_three_turns())
    adapter = build_adapter(recording)
    output_dir = tmp_path / "run"

    summary = await run_live_smoke(
        uow_factory=uow_factory,
        adapter=adapter,
        recording_transport=recording,
        endpoint=endpoint_snapshot(),
        output_dir=output_dir,
        budget=budget,
        document_id=document_id,
    )

    assert len(scripted.calls) == 3
    assert summary.generation_calls == 3
    assert summary.stopped_reason is None
    assert summary.spent_usd == Decimal("0.15")
    assert summary.quality_eligible_calls == 3

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    # opening + 3 × (employee, consultant)
    assert len(loaded.conversation_turns) == 7
    assert [task.statement for task in loaded.state.work_model.tasks] == [
        "每週彙整服務錯誤與效能資料並產出營運週報",
        "在版本上線前執行測試與檢查",
        "每月檢查門市帳號權限清單並轉交異常項目",
    ]

    written = sorted(path.name for path in output_dir.iterdir())
    assert written == [
        "catalog.json",
        "manifest.json",
        "summary.json",
        "turn-01.json",
        "turn-02.json",
        "turn-03.json",
    ]
    for index in (1, 2, 3):
        turn = json.loads(
            (output_dir / f"turn-{index:02d}.json").read_text(encoding="utf-8")
        )
        assert turn["employee_text"] == SMOKE_TURNS[index - 1].employee_text
        assert turn["request"]["body"]["model"] == MODEL
        assert turn["response"]["body"]["model"] == MODEL
        assert turn["route_evidence"]["quality_eligible"] is True
        assert turn["outcome"] == "committed"
        assert turn["state_before"] != turn["state_after"]

    written_summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    last_turn = json.loads((output_dir / "turn-03.json").read_text(encoding="utf-8"))
    assert written_summary["final_state"] == last_turn["state_after"]
    assert written_summary["document_id"] == str(document_id)

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["model"] == MODEL
    assert manifest["provider"] == TAG
    assert manifest["budget"]["limit_usd"] == "0.75"
    assert len(manifest["prompt_sha256"]) == 64
    assert len(manifest["schema_sha256"]) == 64

    # 重送同一個 operation ID 由產品的 replay 短路,不得多花一次呼叫。
    await submit_employee_turn(
        uow_factory,
        adapter=adapter,
        document_id=document_id,
        operation_id=SMOKE_TURNS[-1].operation_id,
        text=SMOKE_TURNS[-1].employee_text,
    )
    assert len(scripted.calls) == 3


async def test_capture_never_contains_the_api_key(
    postgres_session_factory,
    cleanup_job_analysis_rows,
    tmp_path: Path,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    _, recording, budget = build_recording(scripted_three_turns())
    output_dir = tmp_path / "run"

    await run_live_smoke(
        uow_factory=uow_factory,
        adapter=build_adapter(recording),
        recording_transport=recording,
        endpoint=endpoint_snapshot(),
        output_dir=output_dir,
        budget=budget,
        document_id=document_id,
    )

    for path in output_dir.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "test-key-never-captured" not in text
        assert "Authorization" not in text


async def test_a_missing_cost_stops_the_run_but_keeps_that_turn_capture(
    postgres_session_factory,
    cleanup_job_analysis_rows,
    tmp_path: Path,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    responses = scripted_three_turns()
    assert responses[0].body is not None
    responses[0].body["usage"].pop("cost")
    scripted, recording, budget = build_recording(responses)
    output_dir = tmp_path / "run"

    summary = await run_live_smoke(
        uow_factory=uow_factory,
        adapter=build_adapter(recording),
        recording_transport=recording,
        endpoint=endpoint_snapshot(),
        output_dir=output_dir,
        budget=budget,
        document_id=document_id,
    )

    assert len(scripted.calls) == 1
    assert summary.generation_calls == 1
    assert summary.stopped_reason is not None
    assert (output_dir / "turn-01.json").exists()
    assert not (output_dir / "turn-02.json").exists()

    turn = json.loads((output_dir / "turn-01.json").read_text(encoding="utf-8"))
    assert turn["outcome"] == "committed"
    assert turn["route_evidence"]["quality_eligible"] is False


async def test_a_failed_turn_stops_the_run_and_records_the_failure(
    postgres_session_factory,
    cleanup_job_analysis_rows,
    tmp_path: Path,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    responses = scripted_three_turns()
    responses[0] = TransportResponse(status_code=500, body=None, text="upstream down")
    scripted, recording, budget = build_recording(responses)
    output_dir = tmp_path / "run"

    summary = await run_live_smoke(
        uow_factory=uow_factory,
        adapter=build_adapter(recording),
        recording_transport=recording,
        endpoint=endpoint_snapshot(),
        output_dir=output_dir,
        budget=budget,
        document_id=document_id,
    )

    assert len(scripted.calls) == 1
    assert summary.stopped_reason is not None
    turn = json.loads((output_dir / "turn-01.json").read_text(encoding="utf-8"))
    assert turn["outcome"] == "failed"
    assert "UncommittableOperationResult" in turn["detail"]


async def test_output_directory_is_never_reused(
    postgres_session_factory,
    cleanup_job_analysis_rows,
    tmp_path: Path,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    _, recording, budget = build_recording(scripted_three_turns())
    output_dir = tmp_path / "run"
    output_dir.mkdir()

    with pytest.raises(FileExistsError):
        await run_live_smoke(
            uow_factory=uow_factory,
            adapter=build_adapter(recording),
            recording_transport=recording,
            endpoint=endpoint_snapshot(),
            output_dir=output_dir,
            budget=budget,
            document_id=document_id,
        )
