"""三回合 attributed live smoke:真 application ＋ 真 PostgreSQL ＋ 真 OpenRouter。

**這不是 eval framework,也不會變成常駐設施。** 它只回答一個問題:目前的 prompt、
Context、Opus 5 與 Anthropic direct route 合在一起時,一條 synthetic 三回合路徑能不能
跑完 verified commit／reload,以及下一個最值得修的是哪一層。

硬界線(研究紀錄 §4.4):**最多 3 次 generation call、總額 US$0.75、沒有任何 retry**。
每次 HTTP 之前先用 live catalog 價格算保守 reserve;超過就在送出前停,不是事後才說超支。

只有這支 CLI 的 `RecordingTransport` 會 opt in router metadata 並明確關掉 response
cache——`OpenRouterAdapter` 與 FastAPI dependency 的 headers 一個字都沒改。診斷需求不該
讓每天的員工回合永久多帶用不到的 telemetry。

raw capture 寫到已 gitignore 的 `output/`,內容純 synthetic;**request headers 永遠不落地**,
所以 API key 沒有路徑進到檔案裡。

用法(working directory:`apps/api`):

```powershell
uv run python scripts/job_analysis_live_smoke.py --budget-usd 0.75 --max-generation-calls 3
```

`--max-generation-calls 0` 只做 catalog preflight:查完 endpoint 就印出結果離開,
不建文件、不送任何 generation request、不花錢。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel

# 直接以 `python scripts/…` 執行時,apps/api 還不在 sys.path 上。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.job_analysis.application import (  # noqa: E402
    JobAnalysisUnitOfWorkFactory,
    create_document,
    load_document,
    submit_employee_turn,
)
from app.job_analysis.llm import (  # noqa: E402
    TASK_ANALYSIS_RESULT_SCHEMA_NAME,
    task_analysis_result_provider_schema,
)
from app.job_analysis.llm.prompt import TASK_ANALYSIS_INSTRUCTIONS  # noqa: E402
from app.job_analysis.providers import (  # noqa: E402
    MODEL_ENDPOINTS_URL_TEMPLATE,
    OpenRouterAdapter,
    OpenRouterCatalogError,
    OpenRouterConfig,
    OpenRouterEndpointSnapshot,
    TransportResponse,
    httpx_chat_transport,
    inspect_openrouter_execution,
    select_catalog_endpoint,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output" / "job-analysis-live-smoke"
DEFAULT_BUDGET_USD = Decimal("0.75")
MAX_GENERATION_CALLS = 3

# 這一次 smoke 專用,不改 production adapter 的 headers。
METADATA_HEADERS = {
    "X-OpenRouter-Metadata": "enabled",
    "X-OpenRouter-Cache": "false",
}

DOCUMENT_TITLE = "內部系統維運工程師 [synthetic live smoke]"


class LiveSmokeBudgetExceeded(RuntimeError):
    """再送一次就會越過呼叫數或金額上限。**在 HTTP 之前**丟出。"""


class LiveSmokeCostUnknown(RuntimeError):
    """回應沒有可核算的成本。不猜一個數字補上,直接停掉剩餘回合。"""


@dataclass(frozen=True)
class SmokeTurn:
    operation_id: str
    employee_text: str


# 場景在 run 之前就凍結(研究紀錄 §4.3)。**不在 live run 中臨場改題**:
# 1 多工作＋工具;2 更正責任歸屬;3 途中新增工作。
SMOKE_TURNS: tuple[SmokeTurn, ...] = (
    SmokeTurn(
        operation_id="live-smoke-turn-01",
        employee_text=(
            "我是內部系統維運工程師。我每週用 Python 和 Excel 整理服務錯誤與效能資料，"
            "做成營運週報給主管；也用 Java 維護門市資料匯入程式，確保每日資料準時進系統。"
            "版本上線時，我會協助正式環境部署。"
        ),
    ),
    SmokeTurn(
        operation_id="live-smoke-turn-02",
        employee_text=(
            "更正一下，正式環境部署不是我負責，我只做上線前的測試與檢查；"
            "真正部署是平台組做的。"
        ),
    ),
    SmokeTurn(
        operation_id="live-smoke-turn-03",
        employee_text=(
            "另外還有一項我剛才沒提：每月我會檢查門市帳號權限清單，"
            "將異常項目交給資訊安全窗口處理。"
        ),
    ),
)


# ── serialization ──────────────────────────────────────────────────────────


def canonical_request_json(body: Any) -> str:
    """決定性序列化。也當作 input token 的上界基準——BPE token 數不會超過承載它的
    UTF-8 byte 數,所以拿 byte 數估價一定偏保守。"""
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: getattr(value, item.name) for item in fields(value)}
    if isinstance(value, (UUID, Decimal, Path)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(str(item) for item in value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _write(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, default=_jsonable, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ── budget ─────────────────────────────────────────────────────────────────


@dataclass
class LiveSmokeBudget:
    limit_usd: Decimal = DEFAULT_BUDGET_USD
    max_generation_calls: int = MAX_GENERATION_CALLS
    spent_usd: Decimal = Decimal("0")
    calls: int = 0

    def reserve_or_raise(
        self,
        *,
        request_body: Any,
        endpoint: OpenRouterEndpointSnapshot,
        max_output_tokens: int,
    ) -> Decimal:
        """保守 reserve。reasoning 與可見輸出共用同一個 output 上限,所以整條上限都算進來。"""
        if self.calls >= self.max_generation_calls:
            raise LiveSmokeBudgetExceeded(
                f"already used {self.calls} of {self.max_generation_calls} generation calls"
            )
        input_upper_tokens = len(canonical_request_json(request_body).encode("utf-8"))
        reserve = (
            Decimal(input_upper_tokens) * endpoint.prompt_price_per_token
            + Decimal(max_output_tokens) * endpoint.completion_price_per_token
        )
        if self.spent_usd + reserve > self.limit_usd:
            raise LiveSmokeBudgetExceeded(
                f"reserve would exceed the cap: US${self.spent_usd} + US${reserve} "
                f"> US${self.limit_usd}"
            )
        # 先記帳再送出:中途爆掉也不會把這次呼叫算成沒發生過。
        self.calls += 1
        return reserve

    def record_actual_or_raise(self, *, cost_usd: Decimal | None) -> None:
        if cost_usd is None or cost_usd < 0:
            raise LiveSmokeCostUnknown(
                f"response did not report an accountable cost: {cost_usd!r}"
            )
        self.spent_usd += cost_usd
        if self.spent_usd > self.limit_usd:
            raise LiveSmokeBudgetExceeded(
                f"actual spend passed the cap: US${self.spent_usd} > US${self.limit_usd}"
            )


# ── recording transport ────────────────────────────────────────────────────


class RecordingTransport:
    """包住既有 transport:加 metadata headers、記帳、錄下 request／response。

    **不重試**,delegate 一次呼叫對應一次 delegate。headers 永遠不進 `calls`——
    capture 檔案因此沒有任何路徑可以拿到 Authorization。
    """

    def __init__(
        self,
        delegate: Any,
        *,
        budget: LiveSmokeBudget,
        endpoint: OpenRouterEndpointSnapshot,
        max_output_tokens: int,
    ) -> None:
        self._delegate = delegate
        self._budget = budget
        self._endpoint = endpoint
        self.max_output_tokens = max_output_tokens
        self.responses: list[TransportResponse] = []
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self, *, url: str, headers: Any, body: Any, timeout: float
    ) -> TransportResponse:
        reserve = self._budget.reserve_or_raise(
            request_body=body,
            endpoint=self._endpoint,
            max_output_tokens=self.max_output_tokens,
        )
        response = await self._delegate(
            url=url,
            headers={**dict(headers), **METADATA_HEADERS},
            body=body,
            timeout=timeout,
        )
        self.calls.append(
            {"url": url, "body": dict(body), "reserved_usd": str(reserve)}
        )
        self.responses.append(response)
        return response


# ── catalog preflight ──────────────────────────────────────────────────────


async def fetch_endpoint_snapshot(
    client: httpx.AsyncClient, *, model: str, tag: str, api_key: str
) -> OpenRouterEndpointSnapshot:
    """付費前唯一的一次外部查核。零 generation call,任何看不懂都停線。"""
    author, _, slug = model.partition("/")
    url = MODEL_ENDPOINTS_URL_TEMPLATE.format(author=author, slug=slug)
    try:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )
    except httpx.HTTPError as error:
        raise OpenRouterCatalogError(f"catalog request failed: {error}") from error
    if response.status_code != 200:
        raise OpenRouterCatalogError(
            f"catalog request returned HTTP {response.status_code}"
        )
    try:
        payload = response.json()
    except ValueError as error:
        raise OpenRouterCatalogError(
            f"catalog response was not JSON: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise OpenRouterCatalogError("catalog response was not a JSON object")
    return select_catalog_endpoint(payload, expected_model=model, expected_tag=tag)


# ── driver ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SmokeRunSummary:
    run_id: str
    document_id: UUID
    output_dir: Path
    generation_calls: int
    spent_usd: Decimal
    quality_eligible_calls: int
    turn_outcomes: tuple[str, ...]
    stopped_reason: str | None


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def _manifest(
    *,
    run_id: str,
    document_id: UUID,
    endpoint: OpenRouterEndpointSnapshot,
    budget: LiveSmokeBudget,
    max_output_tokens: int,
) -> dict[str, Any]:
    schema_text = canonical_request_json(task_analysis_result_provider_schema())
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
        "schema_name": TASK_ANALYSIS_RESULT_SCHEMA_NAME,
        "prompt_sha256": sha256(
            TASK_ANALYSIS_INSTRUCTIONS.encode("utf-8")
        ).hexdigest(),
        "schema_sha256": sha256(schema_text.encode("utf-8")).hexdigest(),
        "budget": {
            "limit_usd": str(budget.limit_usd),
            "max_generation_calls": budget.max_generation_calls,
        },
        "limitations": [
            "one synthetic three-turn path; not a quality gate and not a browser E2E",
        ],
    }


async def run_live_smoke(
    *,
    uow_factory: JobAnalysisUnitOfWorkFactory,
    adapter: OpenRouterAdapter,
    recording_transport: RecordingTransport,
    endpoint: OpenRouterEndpointSnapshot,
    output_dir: Path,
    budget: LiveSmokeBudget,
    document_id: UUID,
) -> SmokeRunSummary:
    """跑固定三回合。每回合只呼叫產品自己的 `submit_employee_turn()`。

    任何一回合沒有 committed、成本無法核算或預算擋下,就停止剩餘回合——**不在同一個
    run 裡改 prompt 再試**。
    """
    output_dir.mkdir(parents=True, exist_ok=False)
    run_id = output_dir.name
    _write(
        output_dir / "manifest.json",
        _manifest(
            run_id=run_id,
            document_id=document_id,
            endpoint=endpoint,
            budget=budget,
            max_output_tokens=recording_transport.max_output_tokens,
        ),
    )
    _write(output_dir / "catalog.json", endpoint)

    await create_document(uow_factory, document_id=document_id, title=DOCUMENT_TITLE)

    outcomes: list[str] = []
    eligible = 0
    stopped_reason: str | None = None

    for index, turn in enumerate(SMOKE_TURNS, start=1):
        sent_before = len(recording_transport.calls)
        state_before = await load_document(uow_factory, document_id)
        try:
            await submit_employee_turn(
                uow_factory,
                adapter=adapter,
                document_id=document_id,
                operation_id=turn.operation_id,
                text=turn.employee_text,
            )
            outcome, detail = "committed", None
        except LiveSmokeBudgetExceeded as error:
            # reserve 在 HTTP 之前就擋下了,這一回合沒有送出、也沒有 capture。
            stopped_reason = f"turn {index} was not sent: {error}"
            break
        except Exception as error:  # noqa: BLE001 — 每種失敗都要留在 capture 裡
            outcome, detail = "failed", f"{type(error).__name__}: {error}"

        state_after = await load_document(uow_factory, document_id)
        sent = len(recording_transport.calls) > sent_before
        request = recording_transport.calls[-1] if sent else None
        response = recording_transport.responses[-1] if sent else None
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

        _write(
            output_dir / f"turn-{index:02d}.json",
            {
                "index": index,
                "operation_id": turn.operation_id,
                "employee_text": turn.employee_text,
                "outcome": outcome,
                "detail": detail,
                "cost_error": cost_error,
                "request": request,
                "response": (
                    {
                        "status_code": response.status_code,
                        "body": response.body,
                    }
                    if response is not None
                    else None
                ),
                "route_evidence": (
                    {
                        **evidence.model_dump(mode="json"),
                        "quality_eligible": evidence.quality_eligible,
                    }
                    if evidence is not None
                    else None
                ),
                "state_before": state_before,
                "state_after": state_after,
            },
        )

        outcomes.append(outcome)
        if evidence is not None and evidence.quality_eligible:
            eligible += 1
        if outcome == "failed":
            stopped_reason = f"turn {index} did not commit: {detail}"
            break
        if cost_error is not None:
            stopped_reason = f"turn {index} cost was not accountable: {cost_error}"
            break

    final_state = await load_document(uow_factory, document_id)
    summary = SmokeRunSummary(
        run_id=run_id,
        document_id=document_id,
        output_dir=output_dir,
        generation_calls=budget.calls,
        spent_usd=budget.spent_usd,
        quality_eligible_calls=eligible,
        turn_outcomes=tuple(outcomes),
        stopped_reason=stopped_reason,
    )
    _write(
        output_dir / "summary.json",
        {
            "run_id": run_id,
            "document_id": str(document_id),
            "generation_calls": budget.calls,
            "spent_usd": str(budget.spent_usd),
            "quality_eligible_calls": eligible,
            "turn_outcomes": list(outcomes),
            "stopped_reason": stopped_reason,
            "final_state": final_state,
            "limitations": [
                "route evidence reports what OpenRouter said; it is not a vendor signature",
                "a single trial cannot claim stable quality or compare models",
            ],
        },
    )
    return summary


# ── CLI ────────────────────────────────────────────────────────────────────


def _fail(message: str) -> int:
    print(json.dumps({"status": "stopped", "reason": message}, ensure_ascii=False))
    return 1


async def _run(args: argparse.Namespace) -> int:
    api_key = settings.openrouter_api_key
    if not api_key:
        return _fail("OPENROUTER_API_KEY is not configured")

    model = settings.job_analysis_model
    tag = settings.job_analysis_provider
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            endpoint = await fetch_endpoint_snapshot(
                client, model=model, tag=tag, api_key=api_key
            )
        except OpenRouterCatalogError as error:
            return _fail(f"catalog preflight failed: {error}")

    catalog_facts = {
        "model": endpoint.model_id,
        "provider": endpoint.provider_name,
        "tag": endpoint.tag,
        "prompt_price_per_token": str(endpoint.prompt_price_per_token),
        "completion_price_per_token": str(endpoint.completion_price_per_token),
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
        return _fail(
            "working tree is dirty; the report could not name the inputs that produced it"
        )

    # asyncpg 在 Windows 的 Proactor loop 上不穩;和測試設定保持一致。
    from app.database import AsyncSessionLocal
    from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_root) / run_id
    budget = LiveSmokeBudget(
        limit_usd=args.budget_usd, max_generation_calls=args.max_generation_calls
    )

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
            ),
            api_key=api_key,
            transport=recording,
        )
        summary = await run_live_smoke(
            uow_factory=lambda: SqlAlchemyJobAnalysisUnitOfWork(AsyncSessionLocal),
            adapter=adapter,
            recording_transport=recording,
            endpoint=endpoint,
            output_dir=output_dir,
            budget=budget,
            document_id=uuid4(),
        )

    print(
        json.dumps(
            {
                "status": "completed" if summary.stopped_reason is None else "stopped",
                "catalog": catalog_facts,
                "run_id": summary.run_id,
                "output_dir": str(summary.output_dir),
                "document_id": str(summary.document_id),
                "generation_calls": summary.generation_calls,
                "spent_usd": str(summary.spent_usd),
                "quality_eligible_calls": summary.quality_eligible_calls,
                "turn_outcomes": list(summary.turn_outcomes),
                "stopped_reason": summary.stopped_reason,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if summary.stopped_reason is None else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Job Analysis attributed live smoke (three turns, at most US$0.75)"
    )
    parser.add_argument("--budget-usd", type=Decimal, default=DEFAULT_BUDGET_USD)
    parser.add_argument("--max-generation-calls", type=int, default=MAX_GENERATION_CALLS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)

    # 上限只能往下調。命令列不收 API key、資料庫位址或模型——那些只從既有設定讀。
    if not Decimal("0") <= args.budget_usd <= DEFAULT_BUDGET_USD:
        return _fail(f"--budget-usd must be between 0 and {DEFAULT_BUDGET_USD}")
    if not 0 <= args.max_generation_calls <= MAX_GENERATION_CALLS:
        return _fail(f"--max-generation-calls must be between 0 and {MAX_GENERATION_CALLS}")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(_run(args))


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
