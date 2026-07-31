# Job Analysis Attributed Live Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Use `superpowers:test-driven-development` for Tasks 1–2 and `superpowers:verification-before-completion` before every completion claim. Keep one task per commit and stop at every stated gate.

**Goal:** 以不超過 US$0.75、最多三次 generation call，確認現行 `app/job_analysis` 在 exact Opus 5／Anthropic OpenRouter route 上能跑完一條三回合 synthetic 顧問路徑，並留下可區分 provider、schema／verifier、prompt/rubric 與 commit/reload 問題的證據。

**Architecture:** 不建新 eval framework。production adapter 保持不變；只有一次性 CLI 的 recording transport opt in additive router metadata 並明確關 response cache。純 provider helper 解析 catalog／route／usage，但 metadata 不成為 runtime truth。CLI 使用真 `SqlAlchemyJobAnalysisUnitOfWork`、現行 `submit_employee_turn()` 與真 OpenRouter，raw capture 只寫 gitignored `output/`，Git 只收精簡 experiment report。

**Tech Stack:** Python 3.12、Pydantic v2、httpx、SQLAlchemy async、PostgreSQL 16、pytest、OpenRouter Chat Completions／Models API。

**Authority:** [研究紀錄](../specs/2026-07-31-job-analysis-openrouter-attribution-and-live-smoke-research.md)、[ADR 0035](../adr/0035-interview-vnext-openrouter-first-provider-boundary.md)、[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)、[ADR 0042](../adr/0042-r1-screening-stop-and-a6-first-version-default.md)、[Task Analysis Engine](../design/task-analysis-engine.md)。

## Global Constraints

- 保持 `anthropic/claude-opus-5`、provider `anthropic`、high effort、one-stage、light schema、4096 max output 不變。
- 不 import／copy `app.interview`、`app.interview_vnext`、`app.job_authoring` 或 `evals`；概念可參考，程式不得依賴。
- 最多三次 generation call；無 retry、fallback、grader、第二模型、第二 trial 或自動 prompt tuning。
- 總預算上限 US$0.75；每次 HTTP 前先通過 live catalog 與保守 cost reserve，不能事後才說超支。
- route metadata fail-open for product、fail-closed for quality attribution；不得寫入 PostgreSQL／Journal／domain state。
- raw capture 只含 synthetic 資料，寫入 `output/job-analysis-live-smoke/<run-id>/`；不得記錄 API key 或 Authorization header。
- live run 一旦出現 provider、parse、verifier、stale、truncation 或 semantic failure 就停止；不在同一 run 改 prompt 再試。
- 不新增 ADR。若實作需要 runtime 因 metadata 缺失而失敗、需要新 DB 欄位／通用 provider framework，或要換模型／prompt，停止並回報，先重新決策。

## Baseline

- [ ] 在 repo 根執行 `pwd`、`git branch --show-current`、`git status --short`，確認是目標 branch 且沒有混入其他人的變更。
- [ ] 在 `apps/api` 執行 `uv run pytest -q`，記錄現有 baseline；green-before 必須等於 green-after。
- [ ] 確認 `OPENROUTER_API_KEY` 未出現在 Git diff、shell output 或測試 fixture。

---

### Task 1: Additive OpenRouter route evidence seam（no network）

**Files:**

- Create: `apps/api/app/job_analysis/providers/openrouter_evidence.py`
- Modify: `apps/api/app/job_analysis/providers/__init__.py`
- Create: `apps/api/tests/test_job_analysis_openrouter_evidence.py`
- Modify: `docs/design/task-analysis-engine.md`

**Contract:**

```python
class OpenRouterEndpointSnapshot(DomainModel):
    model_id: NonEmptyText
    provider_name: NonEmptyText
    tag: NonEmptyText
    prompt_price_per_token: Decimal
    completion_price_per_token: Decimal
    supported_parameters: frozenset[NonEmptyText]

class OpenRouterExecutionEvidence(DomainModel):
    response_id: str | None = None
    requested_model: str | None = None
    response_model: str | None = None
    strategy: str | None = None
    attempt: int | None = None
    selected_provider: str | None = None
    selected_model: str | None = None
    pipeline_stage_names: tuple[str, ...] = ()
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: Decimal | None = None
    attribution_limitations: tuple[NonEmptyText, ...] = ()

    @property
    def quality_eligible(self) -> bool: ...

def select_catalog_endpoint(
    payload: Mapping[str, Any], *, expected_model: str, expected_tag: str
) -> OpenRouterEndpointSnapshot: ...

def inspect_openrouter_execution(
    payload: Mapping[str, Any],
    *,
    expected_model: str,
    expected_endpoint: OpenRouterEndpointSnapshot,
) -> OpenRouterExecutionEvidence: ...
```

`DomainModel` 僅作 typed provider DTO；這些物件不得進 Work Model／Proposal／Journal。價格使用 `Decimal(str(value))`，拒絕負值、NaN、Infinity 與空字串。

- [ ] **Step 1: Write failing catalog tests**

  以 2026-07-31 公開 model detail 的最小 fixture 測：exact `data.id`、恰好一個 `tag=anthropic` active endpoint、必要參數集合、價格正規化。缺 endpoint、重複 endpoint、status 非 0、model mismatch、缺必要參數、非法價格皆 typed fail；未知 additive 欄位被忽略。

  本產品目前 request 的 required capability set 固定為：

  ```python
  frozenset({
      "max_tokens",
      "reasoning",
      "reasoning_effort",
      "response_format",
      "structured_outputs",
  })
  ```

- [ ] **Step 2: Write failing route evidence tests**

  具品質歸因資格的 fixture 必須是 `requested == response model == configured model`、`strategy=direct`、
  `attempt=1`、恰好一個 selected endpoint、selected provider/name 與 catalog 相符、有非負 usage cost。

  下列各自測成 `quality_eligible == False` 並保留清楚 limitation：metadata 缺失、attempt > 1、零個／多個 selected、provider/model mismatch、cost 缺失或非法、context compression、response healing、plugin、server tools、blocked／flagged guardrail、未知 pipeline type。

  只有 stage type 是 `guardrail`，且 `data` 明確表示未 `flagged`／未 `detected`／未 `blocked` 時可保持 eligible，但 `pipeline_stage_names` 必須記錄。若資料不足以證明未作用，採保守 ineligible，不猜。

- [ ] **Step 3: Minimal implementation**

  parser permissively ignores unknown object fields；pipeline unknown type 只在 eligibility 上 fail closed。不要保存 free-form pipeline `data` 到 domain DTO，不建立 OpenRouter SDK、registry、retry 或 generic telemetry abstraction。

- [ ] **Step 4: Update living design**

  在 `docs/design/task-analysis-engine.md`「現在還沒有」表寫清楚：provider evidence parser 已存在但一般 runtime 不使用；metadata opt-in 留給待建的 smoke wrapper；endpoint catalog／quality 結論要由 live smoke 產生。不要先寫「品質已驗證」。

- [ ] **Step 5: Gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_openrouter_evidence.py tests/test_job_analysis_operation.py -q
  uv run pytest tests/test_job_analysis_dependencies.py -q
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/api/app/job_analysis/providers/openrouter_evidence.py apps/api/app/job_analysis/providers/__init__.py apps/api/tests/test_job_analysis_openrouter_evidence.py docs/design/task-analysis-engine.md
  git commit -m "feat(job-analysis): capture OpenRouter route evidence"
  ```

---

### Task 2: Build the three-turn smoke driver（no paid call）

**Files:**

- Create: `apps/api/scripts/job_analysis_live_smoke.py`
- Create: `apps/api/tests/test_job_analysis_live_smoke.py`
- Modify: `docs/design/task-analysis-engine.md`

**Public script API for tests:**

```python
@dataclass(frozen=True)
class SmokeTurn:
    operation_id: str
    employee_text: str

@dataclass
class LiveSmokeBudget:
    limit_usd: Decimal = Decimal("0.75")
    max_generation_calls: int = 3
    spent_usd: Decimal = Decimal("0")
    calls: int = 0

    def reserve_or_raise(
        self,
        *,
        request_body: Mapping[str, Any],
        endpoint: OpenRouterEndpointSnapshot,
        max_output_tokens: int,
    ) -> Decimal: ...

    def record_actual_or_raise(self, *, cost_usd: Decimal | None) -> None: ...

class RecordingTransport:
    responses: list[TransportResponse]
    calls: list[dict[str, Any]]

async def run_live_smoke(
    *,
    uow_factory: JobAnalysisUnitOfWorkFactory,
    adapter: OpenRouterAdapter,
    recording_transport: RecordingTransport,
    endpoint: OpenRouterEndpointSnapshot,
    output_dir: Path,
    budget: LiveSmokeBudget,
    document_id: UUID,
) -> SmokeRunSummary: ...
```

`RecordingTransport` 只包住現有 `httpx_chat_transport()`，不得重試；capture request body 與 response body，
永遠不把 request headers 寫入檔案。只有這個 wrapper 在 delegate 前加入：

```python
"X-OpenRouter-Metadata": "enabled"
"X-OpenRouter-Cache": "false"
```

一般 `OpenRouterAdapter` 與 FastAPI dependency 的 headers 不改。

- [ ] **Step 1: Write failing budget tests**

  `input upper tokens = len(canonical_request_json.encode("utf-8"))`；reserve 使用 catalog per-token prices 與 configured `max_output_tokens`。若 `spent + reserve > limit` 或 calls 已達 3，在 transport 前 raise。完成後使用 `usage.cost` 累計；cost 缺失／非法時保留當次 capture、停止剩餘回合。測 budget stop 時 transport call count 不增加。

- [ ] **Step 2: Write failing preflight tests**

  CLI 只 GET `https://openrouter.ai/api/v1/models/{author}/{slug}`；以 Task 1 parser 選 configured endpoint。HTTP、JSON、catalog 或 capability 失敗時，generation call count 必須是 0。不要自動改 model/provider。

  同一步測 `RecordingTransport` 恰好加入 metadata／no-cache headers、仍只 delegate 一次，且 capture 不含
  `Authorization`。metadata 缺失只讓 evidence ineligible，不改 `OpenRouterAdapter` 的 product outcome。

- [ ] **Step 3: Write a no-network PostgreSQL vertical test**

  使用 `postgres_session_factory`、`SqlAlchemyJobAnalysisUnitOfWork` 與三個 scripted `TransportResponse`，讓 driver 真正呼叫現有：

  ```python
  create_document(...)
  submit_employee_turn(...)
  load_document(...)
  ```

  驗證恰好三次 transport call、三次 employee／consultant committed turn、每次 state snapshot 與 route evidence 各寫一次、最終 reload 與最後 snapshot 相等；重送同 operation ID 由 product replay short-circuit，不能多一次 HTTP。

  這個測試只驗 orchestration／capture，不對 scripted semantic output 宣稱模型品質。

- [ ] **Step 4: Freeze the synthetic scenario**

  原樣使用以下三段，不在 live run 中臨場改題：

  ```text
  1. 我是內部系統維運工程師。我每週用 Python 和 Excel 整理服務錯誤與效能資料，做成營運週報給主管；也用 Java 維護門市資料匯入程式，確保每日資料準時進系統。版本上線時，我會協助正式環境部署。

  2. 更正一下，正式環境部署不是我負責，我只做上線前的測試與檢查；真正部署是平台組做的。

  3. 另外還有一項我剛才沒提：每月我會檢查門市帳號權限清單，將異常項目交給資訊安全窗口處理。
  ```

  不在回合間接受／拒絕 Proposal；這是刻意測試「待決提案存在時仍能繼續訪談與記住先前工作」。

- [ ] **Step 5: Capture exact artifacts**

  每次 run 建立全新 output directory，至少寫：

  ```text
  manifest.json       # commit SHA、dirty、model/provider、prompt/schema hash、budget
  catalog.json        # normalized endpoint snapshot，不含 key
  turn-01.json        # employee input、request body、raw response、route evidence、state before/after
  turn-02.json
  turn-03.json
  summary.json        # calls、cost、deterministic outcomes、limitations、document id
  ```

  任何檔案不得含 Authorization header。operation IDs 與 document UUID 可以保存，因為資料純 synthetic。

- [ ] **Step 6: Minimal CLI**

  CLI flags 只保留 `--budget-usd`（預設且最大 `0.75`）、`--max-generation-calls`（預設且最大 `3`）、
  `--output-root`（預設 repo `output/job-analysis-live-smoke`）。API key／database URL 只讀現有 settings；不接受命令列 secret。

  若 working tree dirty，CLI 在付費前停止；避免 report 的 commit SHA 無法對應輸入。新建 smoke document 可留在開發 DB，title 明確加 `[synthetic live smoke]`；不要為清理它新增 document delete 功能。

- [ ] **Step 7: Update living design**

  加一個「Attributed live smoke」操作說明與邊界：真 application＋PostgreSQL＋OpenRouter，不是 browser E2E、不進 runtime route、不形成常駐 framework。

- [ ] **Step 8: Gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_live_smoke.py tests/test_job_analysis_openrouter_evidence.py tests/test_job_analysis_operation.py tests/test_job_analysis_consultation.py tests/test_job_analysis_durable_turn_postgres.py -q
  $tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
  uv run pytest @tests -q
  ```

- [ ] **Step 9: Commit**

  ```powershell
  git add apps/api/scripts/job_analysis_live_smoke.py apps/api/tests/test_job_analysis_live_smoke.py docs/design/task-analysis-engine.md
  git commit -m "test(job-analysis): add attributed live smoke"
  ```

---

### Task 3: Execute once, inspect transcript, and record the bounded result

**Files:**

- Create after the run: `docs/experiments/2026-07-31-job-analysis-attributed-live-smoke/README.md`
- Modify: `docs/README.md`
- Modify: `docs/design/task-analysis-engine.md`
- Modify: `docs/plans/2026-07-31-job-analysis-attributed-live-smoke-plan.md`

- [ ] **Step 1: Prepaid gates**

  確認 Task 1–2 focused/full gates 已綠、PostgreSQL migration 是 head、working tree clean、`OPENROUTER_API_KEY`
  存在但不印值。先執行 CLI 的 catalog-only/dry preflight；若 exact endpoint、capability 或 reserve 不合格，停止，
  寫環境診斷，不送 generation request。

- [ ] **Step 2: Run exactly once**（working directory: `apps/api`）

  ```powershell
  uv run python scripts/job_analysis_live_smoke.py --budget-usd 0.75 --max-generation-calls 3
  ```

  不手動重跑失敗回合，不換 key/model/provider，不開 response cache。CLI 若在第 1／2 回合停線，就以實際 call 數
  結案，不為了「湊滿三次」再跑。

- [ ] **Step 3: Review every transcript and state diff**

  人工逐回合看 raw request、response 與 reload state，依下表裁決；不要只看 `VERIFIED`：

  | 檢查 | Pass 條件 |
  |---|---|
  | route | trial 具 quality eligibility；direct、attempt 1、exact model／Anthropic endpoint、cost 可核算 |
  | tools | Python／Excel／Java 只能是 enabler 或 Task 敘述的一部分，沒有只以工具命名的獨立 Task |
  | work boundaries | 週報與資料匯入可被辨識為有目的的工作；不能因同段文字而任意壓成一項或每個工具拆一項 |
  | correction | 「正式環境部署」不再是本人 active work；相關舊 Proposal 不可繼續 actionable；上線前測試可作新理解或待釐清 issue |
  | cross-turn memory | 第 3 回合新增權限檢查後，前兩回合尚未結束的 Task／issue／Proposal 仍在，沒有被新內容沖掉 |
  | grounding | 每個新增支持可回到逐字 employee quote；沒有顧問問題冒充員工依據 |
  | consultant question | 每回合只問一個可理解、與目前最高價值缺口相關的問題；不宣稱訪談完成 |
  | durability | 每回合 committed state 與重新 `load_document()` 相等；call count／Journal／generation 一致 |

  `VERIFIED` 只代表 schema＋deterministic verifier 通過，不等於上表 semantic pass。

- [ ] **Step 4: Classify failures without tuning**

  只選下列第一個適用類別並附原文證據：

  1. `provider_or_attribution`：catalog／route／pipeline／cost；
  2. `output_budget`：`finish_reason=length`／truncated；
  3. `schema_or_local_verifier`：invalid/rejected；
  4. `semantic_prompt_or_rubric`：結構合法但工具、責任、更正、邊界或下一題錯；
  5. `application_commit_or_reload`：模型結果正確但 state／Journal／Proposal 落地錯。

  本 Task 不修該問題、不改 prompt 再跑；把最小後續工作寫進 report。

- [ ] **Step 5: Write the tracked experiment report**

  報告必須列：run ID、commit SHA／dirty false、時間、catalog facts、request config、prompt/schema hashes、每回合
  operation outcome、route/pipeline/token/cost、總 cost、上表逐項 pass/fail/unknown、實際 transcript 摘要、失敗分類、
  可宣稱與不可宣稱的結論、raw artifact local path。

  若三次都成功，也只能使用研究紀錄 §6 的 bounded wording；不得寫「Task Discovery 通過」。

- [ ] **Step 6: Close living docs**

  在 `docs/README.md` 加 experiment 索引；在 `docs/design/task-analysis-engine.md` 把「尚未 live」更新成實際狀態與
  bounded 結論；在本 plan 末尾新增 execution record（commit、測試、call 數、cost、verdict）。不要將當日 catalog
  價格改寫成架構常數。

- [ ] **Step 7: Final gates**

  ```powershell
  uv run pytest -q
  ```

  在 repo 根執行：

  ```powershell
  git diff --check
  git status --short
  ```

- [ ] **Step 8: Commit report only; never commit raw capture**

  ```powershell
  git add docs/experiments/2026-07-31-job-analysis-attributed-live-smoke/README.md docs/README.md docs/design/task-analysis-engine.md docs/plans/2026-07-31-job-analysis-attributed-live-smoke-plan.md
  git commit -m "docs(job-analysis): record attributed live smoke"
  ```

  確認 `git status --short -- output/` 沒有追蹤項目。不要 push；完成 branch 時再依 repo 規則請 owner 決定 tag。

## Stop Conditions

- Catalog 無法唯一選中 configured endpoint，或 required capability／pricing 改變。
- 任一 generation request 將使 conservative reserve 超過 US$0.75。
- transport 將進行 retry，或實際 call count 超過 3。
- raw artifact 含 secret、非 synthetic 使用者資料，或 output directory 會被 Git 追蹤。
- 實作需要 import 舊 AI／eval 路徑、增加 DB／API／Web contract、通用 provider framework、grader、Graph 或第二模型。
- 實作者想因一次結果直接改 prompt／model／schema 或宣稱產品品質通過。
