"""OPKS 漸進式蒐集的 attributed live smoke：真 application ＋ 真 PostgreSQL ＋ 真 OpenRouter。

**這不是 eval framework，也不會變成常駐設施。** 它只回答 scripted 測試回答不了的四件事
（ADR 0054 計畫 T18 的觀察點）：

1. specialist 在證據薄時**真的**會回 `uncertain`，還是硬編一個產出？
2. gap 摘要會不會被寫成問句（違反決定 16）？
3. 主顧問會不會把 K/S 問成「你是否具備⋯⋯能力」的認領題（違反 ADR 0048 決定 14）？
4. `issue_resolutions[]` 會不會被當成偷懶關閉的出口？ADR 0054 後果段已承認 verifier 擋不住
   `employee_unknown` 這條，只能靠實測看。

順帶第五點：修掉後門之後（`RESOLUTION_OPKS_GAP_NEEDS_ISSUE_RESOLUTION`），模型會不會仍然
想用 `resolves_open_issue_ordinal` 關缺口。撞到就是整輪被退，capture 裡看得到。

**與 `job_analysis_live_smoke.py` 的差別只有場景。** 那一支的三回合永遠不會有 Task 進
Current JD（訪談只產生 Proposal，沒有員工決策步驟），所以 pre-gate 一次都不會通過、child
一次都不會排定。這一支把單一 Task 直接種進 Current JD，訪談才走得到 0054 那條線。

**每回合可能有兩次 provider 呼叫**（主顧問 ＋ 排定的 OPKS child），所以 capture 逐 call 記錄、
成本逐 call 結算。`LiveSmokeBudget` 的呼叫數是硬上限，金額是估算——理由見
`job_analysis_live_smoke` 的 docstring。

場景在 run 之前凍結，**不在 live run 中臨場改題**。

已知不忠實之處（誠實記錄，不假裝沒有）：

- 種下的依據沒有出現在 transcript 裡。主顧問看得到那筆 Task 與它的引文，但看不到「員工什麼
  時候說的」。這與 `job_analysis_opks_live_smoke.py` 既有的取捨相同。
- 員工回合的文字是預先凍結的，接不上主顧問當下真正問出來的那一題。第 3 回合刻意寫成「怎麼
  做」的答案，因為缺口多半落在做法上；但它**不保證**對得上。
- 一次 run 不足以宣稱任何模型品質，也不是模型比較。

raw capture 寫到已 gitignore 的 ``output/``，內容純 synthetic；**request headers 永遠不落地**。

用法（working directory：``apps/api``）：

```powershell
uv run python scripts/job_analysis_opks_elicitation_live_smoke.py --max-generation-calls 0
uv run python scripts/job_analysis_opks_elicitation_live_smoke.py --budget-usd 1.80 --max-generation-calls 5
```
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
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
from app.job_analysis.application import (  # noqa: E402
    JobAnalysisUnitOfWorkFactory,
    submit_employee_turn,
)
from app.core.authority import commit_authority_change  # noqa: E402
from app.core.domain import (  # noqa: E402
    CurrentWorkModel,
    JdHeader,
    JdTask,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)
from app.core.state import JobAnalysisState  # noqa: E402
from app.opks.llm import (  # noqa: E402
    OPKS_INSTRUCTIONS,
    OPKS_RESULT_WIRE_SCHEMA_NAME,
    opks_result_wire_provider_schema,
)
from app.task_analysis.llm import (  # noqa: E402
    TASK_ANALYSIS_WIRE_SCHEMA_NAME,
    task_analysis_wire_provider_schema,
)
from app.task_analysis.llm.prompt import TASK_ANALYSIS_INSTRUCTIONS  # noqa: E402
from app.job_analysis.providers import (  # noqa: E402
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
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output" / "job-analysis-opks-elicitation-live-smoke"

#: 3 回合主顧問 ＋ 最多 2 次 child（第一次產生缺口、缺口被回答後再分析一次）。
#: 缺口 active 期間 pre-gate 會擋住同一個 Task，所以中間那回合不會再排定。
MAX_GENERATION_CALLS = 5
DEFAULT_BUDGET_USD = Decimal("1.80")

DOCUMENT_TITLE = "門市營運專員 [synthetic OPKS elicitation live smoke]"
SEEDED_TASK_ID = "task-1"

# ── 凍結場景 ────────────────────────────────────────────────────────────────
# 依據刻意只證明「有這份產出」，完全沒說怎麼做、用什麼、對到什麼程度算完成。
# 工作產出這一軸站得住，行為指標／知識／技能站不住——specialist 若把後三軸也編出來，
# 就是可歸因的 grounding 失誤，不是品味問題（觀察點 1）。

SEEDED_QUOTE = "我每個月初要做一份門市營運月報給區經理。"


@dataclass(frozen=True)
class SmokeTurn:
    operation_id: str
    employee_text: str
    why: str


SMOKE_TURNS: tuple[SmokeTurn, ...] = (
    SmokeTurn(
        operation_id="opks-elicit-turn-01",
        employee_text="除了月報，我平常也會處理店長臨時問的庫存問題。",
        why=(
            "換一個話題，讓主顧問的 next_question 大概率不指向 task-1，"
            "pre-gate 的最後一條因此放行、child 在這一回合排定。"
        ),
    ),
    SmokeTurn(
        operation_id="opks-elicit-turn-02",
        employee_text="臨時的庫存問題大多是問某個品項還有沒有貨，我查系統回他就好。",
        why="缺口這時已經在 packet 裡。看主顧問會不會問它、怎麼問（觀察點 2、3、5）。",
    ),
    SmokeTurn(
        operation_id="opks-elicit-turn-03",
        employee_text=(
            "月報我是先把各店 POS 的日結資料抓下來對過，數字對不起來就打電話問店長確認，"
            "都對上了才填進月報。"
        ),
        why=(
            "把做法講出來。看主顧問會不會用 issue_resolutions 的 answered ＋ 同輪 support_only "
            "收掉缺口（觀察點 4），以及新 digest 觸發的再分析會不會改出候選而不是再開一次缺口。"
        ),
    ),
)


def _seeded_task() -> Task:
    return Task(
        task_id=SEEDED_TASK_ID,
        statement="每月彙整門市營運月報",
        action="彙整",
        object="門市營運月報",
        purpose_result="讓區經理掌握各店營運狀況",
        context="每月初",
        support_links=(
            SupportLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="opks-elicit-seed-turn",
                ),
                quote=SEEDED_QUOTE,
            ),
        ),
    )


async def _seed(uow_factory: JobAnalysisUnitOfWorkFactory, document_id: UUID) -> None:
    """把單一 Task 種進 Current JD。零模型呼叫；走產品自己的 authority commit seam。

    **只種一個 Task**：pre-gate 是逐 Task 的，多一個就多一條 child，付費上限會失控。
    """

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
                work_model=CurrentWorkModel(tasks=(_seeded_task(),)),
                current_jd=(
                    JdTask(
                        task_id=SEEDED_TASK_ID,
                        statement="每月彙整門市營運月報",
                        display_order=0,
                    ),
                ),
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
        "reasoning_effort": "high",
        "consultant": {
            "schema_name": TASK_ANALYSIS_WIRE_SCHEMA_NAME,
            "prompt_sha256": sha256(
                TASK_ANALYSIS_INSTRUCTIONS.encode("utf-8")
            ).hexdigest(),
            "schema_sha256": sha256(
                canonical_request_json(
                    task_analysis_wire_provider_schema()
                ).encode("utf-8")
            ).hexdigest(),
        },
        "specialist": {
            "schema_name": OPKS_RESULT_WIRE_SCHEMA_NAME,
            "prompt_sha256": sha256(OPKS_INSTRUCTIONS.encode("utf-8")).hexdigest(),
            "schema_sha256": sha256(
                canonical_request_json(
                    opks_result_wire_provider_schema()
                ).encode("utf-8")
            ).hexdigest(),
        },
        "seeded_task_id": SEEDED_TASK_ID,
        "budget": {
            "limit_usd": str(budget.limit_usd),
            "max_generation_calls": budget.max_generation_calls,
        },
        "observations_sought": [
            "specialist answers uncertain on the thin axes instead of fabricating them",
            "gap summaries are statements, not questions (ADR 0054 decision 16)",
            "the consultant asks K/S as behaviour, never as a capability claim "
            "(ADR 0048 decision 14)",
            "issue_resolutions[] is not used as a lazy exit "
            "(employee_unknown without the employee saying so)",
            "the consultant does not try to close a gap through "
            "resolves_open_issue_ordinal",
        ],
        "limitations": [
            "seeded evidence is not in the transcript; the consultant sees the Task "
            "and its quote but not when it was said",
            "employee turns are frozen in advance and cannot answer the question the "
            "consultant actually asked",
            "one synthetic path, one trial; not a quality gate and not a model comparison",
        ],
    }


def _schema_name_of(request: dict[str, Any]) -> str | None:
    """這一次呼叫是主顧問還是 specialist —— 用送出去的 schema 名字認，不猜。"""

    body = request.get("body")
    if not isinstance(body, dict):
        return None
    response_format = body.get("response_format")
    if not isinstance(response_format, dict):
        return None
    json_schema = response_format.get("json_schema")
    if not isinstance(json_schema, dict):
        return None
    name = json_schema.get("name")
    return name if isinstance(name, str) else None


def _consultant_output(call: dict[str, Any]) -> dict[str, Any] | None:
    """主顧問那一次呼叫還原出來的 JSON。

    `submit_employee_turn()` 不回傳結果（產品不需要），所以觀察點只能從 capture 讀。
    讀原始回應而不是重跑一次 parser：這裡要看的是模型**實際送出**了什麼，包含被
    verifier 退掉的那些。
    """

    if call.get("schema_name") != TASK_ANALYSIS_WIRE_SCHEMA_NAME:
        return None
    body = call.get("response", {}).get("body")
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    try:
        parsed = json.loads(content)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _gap_views(state: Any) -> list[dict[str, Any]]:
    if state is None:
        return []
    return [
        {
            "issue_id": issue.id,
            "axis": issue.opks_axis.value if issue.opks_axis else None,
            "subject_task_id": issue.subject_task_id,
            "summary": issue.summary,
            "is_active": issue.is_active,
            "terminal_kind": (
                issue.terminal_resolution.kind.value
                if issue.terminal_resolution is not None
                else None
            ),
        }
        for issue in state.state.work_model.open_issues
        if issue.opks_axis is not None
    ]


def _observations(turns: list[dict[str, Any]], final_state: Any) -> dict[str, Any]:
    """**機械抽取，不下判斷。**

    「摘要是不是問句」用結尾標點判得出來，所以這裡直接標；「K/S 有沒有問成認領題」是語意
    判斷，只把問句原文列出來給人看，不假裝自動判得出來。
    """

    gaps = _gap_views(final_state)
    question_marks = tuple(
        gap["summary"] for gap in gaps if gap["summary"].rstrip().endswith(("?", "？"))
    )
    return {
        "gaps_final": gaps,
        "gap_summaries_ending_in_a_question_mark": question_marks,
        "consultant_questions": tuple(
            turn["consultant_question"]
            for turn in turns
            if turn.get("consultant_question")
        ),
        "issue_resolutions_emitted": tuple(
            {"turn": turn["index"], **resolution}
            for turn in turns
            for resolution in turn.get("issue_resolutions") or ()
            if isinstance(resolution, dict)
        ),
        "turns_that_did_not_commit": tuple(
            {"turn": turn["index"], "outcome": turn["outcome"], "detail": turn["detail"]}
            for turn in turns
            if turn["outcome"] != "committed"
        ),
        "specialist_calls": sum(
            1
            for turn in turns
            for call in turn.get("calls", ())
            if call.get("schema_name") == OPKS_RESULT_WIRE_SCHEMA_NAME
        ),
        "read_this_by_hand": [
            "consultant_questions: 有沒有把知識／技能問成「你是否具備⋯⋯」的認領題",
            "issue_resolutions_emitted: employee_unknown 是不是在員工根本沒說不知道時就出現",
            "gaps_final: 缺口摘要是不是只寫『缺什麼』，沒有夾帶問句或自行補上的內容",
            "turns_that_did_not_commit: 若 detail 帶 rejected，去 turn-NN.json 看模型送了什麼",
        ],
    }


async def _run(args: argparse.Namespace) -> int:
    api_key = settings.openrouter_api_key
    if not api_key:
        print(
            json.dumps(
                {"status": "stopped", "reason": "OPENROUTER_API_KEY is not configured"}
            )
        )
        return 1

    model = settings.job_analysis_model
    tag = settings.job_analysis_provider
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            endpoint = await fetch_endpoint_snapshot(
                client, model=model, tag=tag, api_key=api_key
            )
        except OpenRouterCatalogError as error:
            print(
                json.dumps(
                    {
                        "status": "stopped",
                        "reason": f"catalog preflight failed: {error}",
                    },
                    ensure_ascii=False,
                )
            )
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
        print(
            json.dumps(
                {"status": "preflight_only", "catalog": catalog_facts},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if _git("status", "--porcelain"):
        print(
            json.dumps(
                {"status": "stopped", "reason": "working tree is dirty"},
                ensure_ascii=False,
            )
        )
        return 1

    from app.database import AsyncSessionLocal
    from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork

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
    _write(
        output_dir / "scenario.json",
        {
            "seeded_task": _seeded_task(),
            "turns": [
                {
                    "operation_id": turn.operation_id,
                    "employee_text": turn.employee_text,
                    "why": turn.why,
                }
                for turn in SMOKE_TURNS
            ],
        },
    )

    await _seed(uow_factory, document_id)

    captured: list[dict[str, Any]] = []
    stopped_reason: str | None = None

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
                output_cap_parameter=endpoint.output_cap_parameter,
            ),
            api_key=api_key,
            transport=recording,
        )

        for index, turn in enumerate(SMOKE_TURNS, start=1):
            sent_before = len(recording.calls)
            state_before = await load_document(uow_factory, document_id)
            try:
                await submit_employee_turn(
                    uow_factory,
                    task_analysis_adapter=adapter,
                    opks_adapter=adapter,
                    document_id=document_id,
                    operation_id=turn.operation_id,
                    text=turn.employee_text,
                )
                outcome, detail = "committed", None
            except LiveSmokeBudgetExceeded as error:
                # 送出前的門擋下了。可能擋在主顧問，也可能擋在 child ——
                # `_run_scheduled_opks()` 只吞 job_analysis 的錯誤,預算例外會傳上來。
                stopped_reason = f"turn {index} stopped by the budget: {error}"
                outcome, detail = "stopped", str(error)
            except Exception as error:  # noqa: BLE001 — 每種失敗都要留在 capture 裡
                outcome, detail = "failed", f"{type(error).__name__}: {error}"

            state_after = await load_document(uow_factory, document_id)

            # **一回合可能有兩次呼叫**（主顧問 ＋ 排定的 child）。只取最後一次會漏掉
            # specialist 那一次的成本與內容,而那正是這支 smoke 要看的東西。
            calls: list[dict[str, Any]] = []
            cost_error: str | None = None
            for offset in range(sent_before, len(recording.calls)):
                request = recording.calls[offset]
                response = recording.responses[offset]
                evidence = inspect_openrouter_execution(
                    response.body or {},
                    expected_model=endpoint.model_id,
                    expected_endpoint=endpoint,
                )
                try:
                    budget.record_actual_or_raise(cost_usd=evidence.cost_usd)
                except (LiveSmokeBudgetExceeded, LiveSmokeCostUnknown) as error:
                    cost_error = f"{type(error).__name__}: {error}"
                calls.append(
                    {
                        "schema_name": _schema_name_of(request),
                        "request": request,
                        "response": {
                            "status_code": response.status_code,
                            "body": response.body,
                        },
                        "route_evidence": {
                            **evidence.model_dump(mode="json"),
                            "quality_eligible": evidence.quality_eligible,
                        },
                    }
                )

            consultant_output = next(
                (
                    parsed
                    for call in calls
                    if (parsed := _consultant_output(call)) is not None
                ),
                None,
            )
            record: dict[str, Any] = {
                "index": index,
                "operation_id": turn.operation_id,
                "employee_text": turn.employee_text,
                "why": turn.why,
                "outcome": outcome,
                "detail": detail,
                "cost_error": cost_error,
                "calls": calls,
                # 從 capture 讀而不是從 state 讀:被 verifier 退掉的那一輪不會寫進
                # `active_question`,但它送了什麼正是要看的東西。
                "consultant_question": (
                    (consultant_output or {}).get("next_question", {}).get("text")
                ),
                "issue_resolutions": (consultant_output or {}).get(
                    "issue_resolutions"
                ),
                "gaps_after": _gap_views(state_after),
                "state_before": state_before,
                "state_after": state_after,
            }
            _write(output_dir / f"turn-{index:02d}.json", record)
            captured.append(record)

            if outcome != "committed":
                stopped_reason = stopped_reason or f"turn {index} did not commit: {detail}"
                break
            if cost_error is not None:
                stopped_reason = f"turn {index} cost was not accountable: {cost_error}"
                break

    final_state = await load_document(uow_factory, document_id)
    observations = _observations(captured, final_state)
    _write(output_dir / "observations.json", observations)
    _write(output_dir / "final-state.json", final_state)

    print(
        json.dumps(
            {
                "status": "completed" if stopped_reason is None else "stopped",
                "catalog": catalog_facts,
                "run_id": run_id,
                "output_dir": str(output_dir),
                "document_id": str(document_id),
                "generation_calls": budget.calls,
                "specialist_calls": observations["specialist_calls"],
                "spent_usd": str(budget.spent_usd),
                "turn_outcomes": [turn["outcome"] for turn in captured],
                "stopped_reason": stopped_reason,
                "limitations": [
                    "a single trial cannot claim stable quality or compare models",
                    "frozen employee turns cannot answer the question actually asked",
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if stopped_reason is None else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "OPKS progressive elicitation attributed live smoke "
            f"(up to {MAX_GENERATION_CALLS} calls, at most US${DEFAULT_BUDGET_USD})"
        )
    )
    parser.add_argument("--budget-usd", type=Decimal, default=DEFAULT_BUDGET_USD)
    parser.add_argument(
        "--max-generation-calls", type=int, default=MAX_GENERATION_CALLS
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)

    # CLI 只能往下調,不能把上限調高。
    if not Decimal("0") <= args.budget_usd <= DEFAULT_BUDGET_USD:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "reason": f"--budget-usd must be between 0 and {DEFAULT_BUDGET_USD}",
                }
            )
        )
        return 1
    if not 0 <= args.max_generation_calls <= MAX_GENERATION_CALLS:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "reason": (
                        "--max-generation-calls must be between 0 and "
                        f"{MAX_GENERATION_CALLS}"
                    ),
                }
            )
        )
        return 1

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
