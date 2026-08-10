"""OPKS 的單次 attributed live smoke：真 application ＋ 真 PostgreSQL ＋ 真 OpenRouter。

**這不是 eval framework，也不會變成常駐設施。** 它只回答一個問題：目前的 OPKS prompt、
packet、wire schema 與產品配置的模型合在一起時，一次真呼叫能不能走完
generate → verify → proposal，以及下一個最值得修的是哪一層。

硬界線：**最多 1 次 generation call、沒有任何 retry、回應後照實際 cost 結算並在超過
``--budget-usd`` 時停線**（ceiling 見 ``DEFAULT_BUDGET_USD``，CLI 只能往下調）。送出前那道估算會低估（input 拿不到 provider tokenizer；輸出上限管不管得住
reasoning per-provider 不同），所以它不是保證——理由與實測數字見
``job_analysis_live_smoke`` 的 docstring。預算、錄製與 catalog preflight 直接重用該模組，
不另建一套。

場景在 run 之前凍結，**不在 live run 中臨場改題**。單一 Task、單一呼叫，同時觀察：
O／P／K／S 四類是否都出、`reuse_existing` 會不會用在已存在的知識上、沒有數字的依據會不會
被自行補上門檻、依據不足時會不會用 `uncertain`、以及會不會產生逐字精確重複。

這支 CLI 直接串 ``prepare_opks_generation`` → ``run_opks_operation`` →
``commit_opks_generation``——就是 ``generate_opks_proposals()`` 自己的組合，拆開只為了在
verifier 判不通過時仍能留下 report；不是另一條產品路徑。

raw capture 寫到已 gitignore 的 ``output/``，內容純 synthetic；**request headers 永遠不落地**。

用法（working directory：``apps/api``）：

```powershell
uv run python scripts/job_analysis_opks_live_smoke.py --max-generation-calls 0   # 只做 preflight，不花錢
uv run python scripts/job_analysis_opks_live_smoke.py --budget-usd 0.60 --max-generation-calls 1
```
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.documents import load_document  # noqa: E402
from app.documents.authoring import create_document  # noqa: E402
from app.core.persistence import JobAnalysisUnitOfWorkFactory  # noqa: E402
from app.core.authority import commit_authority_change  # noqa: E402
from app.core.state import JobAnalysisState  # noqa: E402
from app.opks import (  # noqa: E402
    commit_opks_generation,
    compute_analysis_input_digest,
    prepare_opks_generation,
    render_opks_context_packet,
    run_opks_operation,
)
from app.core.domain import (  # noqa: E402
    CurrentJdOpks,
    CurrentWorkModel,
    JdHeader,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)
from app.opks.llm import (  # noqa: E402
    OPKS_INSTRUCTIONS,
    OPKS_RESULT_WIRE_SCHEMA_NAME,
    opks_result_wire_provider_schema,
)
from app.adapters.openrouter import (  # noqa: E402
    OpenRouterAdapter,
    OpenRouterCatalogError,
    OpenRouterConfig,
    OpenRouterEndpointSnapshot,
    httpx_chat_transport,
    inspect_openrouter_execution,
)

from job_analysis_live_smoke import (  # noqa: E402
    LiveSmokeBudget,
    LiveSmokeBudgetExceeded,
    LiveSmokeCostUnknown,
    RecordingTransport,
    _git,
    _write,
    canonical_request_json,
    fetch_endpoint_snapshot,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output" / "job-analysis-opks-live-smoke"
DEFAULT_BUDGET_USD = Decimal("0.60")
MAX_GENERATION_CALLS = 1

DOCUMENT_TITLE = "門市營運專員 [synthetic OPKS live smoke]"
SELECTED_TASK_ID = "task-1"
OPERATION_ID = "opks-live-smoke-01"

# ── 凍結場景 ────────────────────────────────────────────────────────────────
# 依據刻意「說了流程但沒說數字」：quote 2 只說『差異超過一定數量』。prompt 禁止自行補
# 數字，所以模型若生出具體門檻，就是可歸因的 grounding 失誤，不是品味問題。
# quote 3 對應到一筆**已存在但連到別的 Task** 的知識，用來觀察 reuse_existing。

EMPLOYEE_QUOTES = (
    "我每個月底會盤點門市庫存，把 POS 匯出的帳面數量跟實際數量對起來。",
    "差異超過一定數量我要查原因，通常是收貨沒登錄或報廢沒扣帳，我會寫成差異說明給店長。",
    "對不上的我不能自己改帳，要走報廢或調整單，店長核過才生效。",
)

EXISTING_KNOWLEDGE_TEXT = "門市報廢與庫存調整單的核准流程"


def _selected_task() -> Task:
    return Task(
        task_id=SELECTED_TASK_ID,
        statement="每月盤點門市庫存並釐清帳實差異",
        action="盤點",
        object="門市庫存",
        purpose_result="讓帳面與實際庫存一致，避免補貨誤判",
        context="每月底，使用 POS 匯出報表與 Excel 比對",
        support_links=tuple(
            SupportLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id=f"opks-live-smoke-turn-{index:02d}",
                ),
                quote=quote,
            )
            for index, quote in enumerate(EMPLOYEE_QUOTES, start=1)
        ),
    )


def _other_task() -> Task:
    return Task(
        task_id="task-2",
        statement="每日登錄門市收貨資料",
        action="登錄",
        object="收貨資料",
        support_links=(
            SupportLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="opks-live-smoke-turn-04",
                ),
                quote="收到貨我當天就要在系統登錄，不然帳會對不起來。",
            ),
        ),
    )


def _existing_knowledge() -> OpksItem:
    """已在文件裡、但只連到 task-2 的知識：正確做法是 reuse_existing，不是 add_new。"""

    return OpksItem(
        entity_id="direct-seed-knowledge-knowledge",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text=EXISTING_KNOWLEDGE_TEXT,
        task_refs=("task-2",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.DIRECT_EDIT,
                    id="opks-live-smoke-seed",
                ),
            ),
        ),
    )


async def _seed(
    uow_factory: JobAnalysisUnitOfWorkFactory, document_id: UUID
) -> None:
    """一次寫入凍結場景。零模型呼叫；走的是產品自己的 authority commit seam。"""

    await create_document(uow_factory, document_id=document_id, title=DOCUMENT_TITLE)
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        await commit_authority_change(
            uow,
            record=record,
            state=JobAnalysisState(
                jd_header=JdHeader(),
                current_duties=(),
                work_model=CurrentWorkModel(tasks=(_selected_task(), _other_task())),
                current_jd=(
                    JdTask(
                        task_id=SELECTED_TASK_ID,
                        statement="每月盤點門市庫存並釐清帳實差異",
                        display_order=0,
                    ),
                    JdTask(
                        task_id="task-2",
                        statement="每日登錄門市收貨資料",
                        display_order=1,
                    ),
                ),
                current_opks=CurrentJdOpks(items=(_existing_knowledge(),)),
            ),
            updated_at=datetime.now(UTC),
        )


def _manifest(
    *,
    run_id: str,
    document_id: UUID,
    endpoint: OpenRouterEndpointSnapshot,
    budget: LiveSmokeBudget,
    max_output_tokens: int,
) -> dict[str, Any]:
    schema_text = canonical_request_json(opks_result_wire_provider_schema())
    return {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "document_id": str(document_id),
        "commit_sha": _git("rev-parse", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "model": endpoint.model_id,
        "provider": endpoint.tag,
        "provider_name": endpoint.provider_name,
        "max_output_tokens": max_output_tokens,
        "schema_name": OPKS_RESULT_WIRE_SCHEMA_NAME,
        "prompt_sha256": sha256(OPKS_INSTRUCTIONS.encode("utf-8")).hexdigest(),
        "schema_sha256": sha256(schema_text.encode("utf-8")).hexdigest(),
        "selected_task_id": SELECTED_TASK_ID,
        "budget": {
            "limit_usd": str(budget.limit_usd),
            "max_generation_calls": budget.max_generation_calls,
        },
        "observations_sought": [
            "O/P/K/S coverage in one call",
            "reuse_existing on the pre-seeded document-level knowledge",
            "no fabricated numeric threshold (evidence says 『一定數量』 only)",
            "uncertain instead of filling every slot",
            "exact duplicate add_new against packet or batch",
        ],
        "limitations": [
            "one synthetic Task, one trial; not a quality gate and not a model comparison",
            "one trial cannot settle consultant quality for whichever model is configured",
        ],
    }


async def _run(args: argparse.Namespace) -> int:
    api_key = settings.openrouter_api_key
    if not api_key:
        print(json.dumps({"status": "stopped", "reason": "OPENROUTER_API_KEY is not configured"}))
        return 1

    model = settings.job_analysis_model
    tag = settings.job_analysis_provider
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            endpoint = await fetch_endpoint_snapshot(
                client, model=model, tag=tag, api_key=api_key
            )
        except OpenRouterCatalogError as error:
            print(json.dumps({"status": "stopped", "reason": f"catalog preflight failed: {error}"}, ensure_ascii=False))
            return 1

    catalog_facts = {
        "model": endpoint.model_id,
        "provider": endpoint.provider_name,
        "tag": endpoint.tag,
        "prompt_price_per_token": str(endpoint.prompt_price_per_token),
        "completion_price_per_token": str(endpoint.completion_price_per_token),
        "output_cap_parameter": endpoint.output_cap_parameter,
    }
    if args.max_generation_calls == 0:
        print(json.dumps({"status": "preflight_only", "catalog": catalog_facts}, ensure_ascii=False, sort_keys=True))
        return 0

    if _git("status", "--porcelain"):
        print(json.dumps({"status": "stopped", "reason": "working tree is dirty"}, ensure_ascii=False))
        return 1

    from app.database import AsyncSessionLocal
    from app.adapters.postgres import SqlAlchemyJobAnalysisUnitOfWork

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    document_id = uuid4()
    budget = LiveSmokeBudget(
        limit_usd=args.budget_usd, max_generation_calls=args.max_generation_calls
    )
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(AsyncSessionLocal)  # noqa: E731

    _write(
        output_dir / "manifest.json",
        _manifest(
            run_id=run_id,
            document_id=document_id,
            endpoint=endpoint,
            budget=budget,
            max_output_tokens=settings.job_analysis_max_output_tokens,
        ),
    )
    _write(output_dir / "catalog.json", endpoint)

    await _seed(uow_factory, document_id)
    seeded = await load_document(uow_factory, document_id)
    assert seeded is not None
    seeded_task = seeded.state.work_model.task_by_id(SELECTED_TASK_ID)
    assert seeded_task is not None
    snapshot = await prepare_opks_generation(
        uow_factory,
        document_id=document_id,
        task_id=SELECTED_TASK_ID,
        # child 只跑被排定的那一份輸入(ADR 0054 決定 10)。這支 CLI 自己種資料、
        # 種完立刻取,所以預期值就是剛落地的那份。
        expected_digest=compute_analysis_input_digest(seeded_task),
    )
    _write(output_dir / "packet.json", snapshot.packet)
    (output_dir / "packet.txt").write_text(
        render_opks_context_packet(snapshot.packet), encoding="utf-8"
    )

    stopped_reason: str | None = None
    committed: Any = None
    async with httpx.AsyncClient() as client:
        recording = RecordingTransport(
            httpx_chat_transport(client),
            budget=budget,
            endpoint=endpoint,
            max_output_tokens=settings.job_analysis_max_output_tokens,
        )
        adapter = OpenRouterAdapter(
            config=OpenRouterConfig(
                model=model,
                provider_order=(tag,),
                max_output_tokens=settings.job_analysis_max_output_tokens,
                timeout_seconds=settings.job_analysis_timeout_s,
                # catalog 說支援哪個就送哪個;不猜、也不硬換成偏好的新名字。
                output_cap_parameter=endpoint.output_cap_parameter,
            ),
            api_key=api_key,
            transport=recording,
        )
        try:
            operation_result = await run_opks_operation(
                packet=snapshot.packet, adapter=adapter, operation_id=OPERATION_ID
            )
        except LiveSmokeBudgetExceeded as error:
            print(json.dumps({"status": "stopped", "reason": f"not sent: {error}"}, ensure_ascii=False))
            return 1

        response = recording.responses[-1] if recording.responses else None
        request = recording.calls[-1] if recording.calls else None
        evidence = (
            inspect_openrouter_execution(
                response.body or {},
                expected_model=endpoint.model_id,
                expected_endpoint=endpoint,
            )
            if response is not None
            else None
        )
        cost_error: str | None = None
        try:
            budget.record_actual_or_raise(
                cost_usd=evidence.cost_usd if evidence is not None else None
            )
        except (LiveSmokeBudgetExceeded, LiveSmokeCostUnknown) as error:
            cost_error = f"{type(error).__name__}: {error}"

        if operation_result.is_applicable:
            try:
                committed = await commit_opks_generation(
                    uow_factory,
                    snapshot=snapshot,
                    operation_id=OPERATION_ID,
                    operation_result=operation_result,
                )
            except Exception as error:  # noqa: BLE001 — 失敗也要留在 capture 裡
                stopped_reason = f"commit failed: {type(error).__name__}: {error}"
        else:
            stopped_reason = f"operation was not committable: {operation_result.outcome.value}"

    final_state = await load_document(uow_factory, document_id)
    _write(
        output_dir / "call-01.json",
        {
            "operation_id": OPERATION_ID,
            "outcome": operation_result.outcome.value,
            "detail": operation_result.detail,
            "cost_error": cost_error,
            "request": request,
            "response": (
                {"status_code": response.status_code, "body": response.body}
                if response is not None
                else None
            ),
            "route_evidence": (
                {**evidence.model_dump(mode="json"), "quality_eligible": evidence.quality_eligible}
                if evidence is not None
                else None
            ),
            "parsed_result": operation_result.result,
            "verification_report": operation_result.report,
            "committed": committed,
            "final_state": final_state,
        },
    )

    print(
        json.dumps(
            {
                "status": "completed" if stopped_reason is None else "stopped",
                "catalog": catalog_facts,
                "run_id": run_id,
                "output_dir": str(output_dir),
                "document_id": str(document_id),
                "generation_calls": budget.calls,
                "spent_usd": str(budget.spent_usd),
                "outcome": operation_result.outcome.value,
                "quality_eligible": bool(evidence and evidence.quality_eligible),
                "stopped_reason": stopped_reason,
                "limitations": [
                    "a single trial cannot claim stable quality or compare models",
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if stopped_reason is None else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OPKS attributed live smoke (one call, at most US$0.20)"
    )
    parser.add_argument("--budget-usd", type=Decimal, default=DEFAULT_BUDGET_USD)
    parser.add_argument("--max-generation-calls", type=int, default=MAX_GENERATION_CALLS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)

    if not Decimal("0") <= args.budget_usd <= DEFAULT_BUDGET_USD:
        print(json.dumps({"status": "stopped", "reason": f"--budget-usd must be between 0 and {DEFAULT_BUDGET_USD}"}))
        return 1
    if not 0 <= args.max_generation_calls <= MAX_GENERATION_CALLS:
        print(json.dumps({"status": "stopped", "reason": f"--max-generation-calls must be between 0 and {MAX_GENERATION_CALLS}"}))
        return 1

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_run(args))


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
