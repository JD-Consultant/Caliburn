# R1 T4 blind grader、CLI dry-run 與 OpenRouter preflight seam 實作研究

- 日期：2026-08-04
- 狀態：Research complete；供 R1 T4 使用
- 範圍：blind grader 契約與盲化投影、offline CLI、exact model／endpoint preflight seam、resolved facts fail-closed policy
- 不含：live／付費呼叫、exact model slug 選定、shortlist、pass³、R1 gate 判定、DB／route／Web

## 1. 結論

T4 三個交付都留在 `evals.professional_consultant.r1` 外圈，**不改 T1–T3 的 core contracts、verifier、prompts、schema
projection 或 runner**。三項的共同要求是「證據只能從實際發生的東西取得」：grader 只能看去除產生器自辯後的 artifact、
CLI 只能報告實際讀到的 manifest、preflight 只能由 response／generation evidence 認定 resolved model／provider／endpoint。

三項的邊界裁決：

1. **blind grader 用獨立型別，不共用 generator 的 operation seam。** grader 有自己的 `GraderProvider.grade()` port、
   `grader_id`、prompt artifact、output schema 與 capture root。若共用 `OperationName` 與
   `StructuredOutputProvider.generate()`，ADR 0040 §17「不共用 prompt、範例與輸出目的」在型別層就失去保護。
2. **盲化是投影型別，不是執行期過濾。** grader input model **根本沒有** rationale／self-assessment 欄位，
   因此「忘記過濾」不是可能的失誤模式，而是編譯不過的形狀錯誤。
3. **preflight 只做 attestation，不做 eligibility 裁決，也不猜。** 缺 router metadata、selected 不唯一、resolved model
   不在 accepted 集合、provider 不符或有 fallback 痕跡時，`resolved_endpoint` 一律留空並回 typed refusal code，
   絕不回填 requested 值。

## 2. 一手來源與實作含義

### OpenRouter

- [Structured Outputs](https://openrouter.ai/docs/features/structured-outputs) 定義
  `response_format: {"type": "json_schema", "json_schema": {"name", "strict": true, "schema"}}`，並說明支援度依 model／provider
  而異。含義：T2 的 portable `schema_text` 必須**原樣 parse 後嵌入** `json_schema.schema`，preflight 才算「實送 portable schema」；
  若只送 schema ID 或重新產生一份 schema，preflight 證明的就不是實際會用的契約。
- [Provider Routing](https://openrouter.ai/docs/features/provider-routing) 定義 `provider.order`、`provider.only`、
  `allow_fallbacks`、`require_parameters`、`data_collection`。含義：exact endpoint 綁定＝`order == only == (endpoint,)`
  且 `allow_fallbacks: false`、`require_parameters: true`；`require_parameters` 讓不支援 `response_format` 的 endpoint
  在路由階段就被排除，而不是靜默降級成自由文字。
- [Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata) 說明 routing metadata 需 opt in
  （`X-OpenRouter-Metadata: enabled`），成功回應才帶 `endpoints.selected` 與 `attempts`，且 cache hit 或部分早期 failure
  會沒有 metadata。含義：metadata 缺席是**證據缺失**，不是「照請求執行」的證明；preflight 必須 fail closed。
- [Model Fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks) 明示最終模型由 response body 的 `model` 回報；
  [Get Generation](https://openrouter.ai/docs/api/api-reference/generations/get-generation) 以 generation ID 回傳 `model`
  與 `provider_name`。含義：`resolved_model` 取 body `model`、`resolved_provider` 取 metadata `endpoints.selected.provider`
  或 generation `provider_name`；**exact endpoint slug 官方契約並未在回應中直接回報**，只能在「outbound 綁死單一 endpoint
  且 response facts 與之唯一一致」時才可認定，這與 T3 研究 §2 留下的問題一致。

### Pydantic

- [Unions](https://docs.pydantic.dev/latest/concepts/unions/) 與 [Models](https://docs.pydantic.dev/latest/concepts/models/)：
  strict 模式下 `Literal` 欄位是最便宜的「不可被呼叫端覆寫的不變量」表示法。含義：`allow_fallbacks: Literal[False]`、
  `require_parameters: Literal[True]`、`ranking_claim: Literal["none"]` 這類值寫進型別，就不需要靠測試巡邏呼叫端。

### Python 標準庫

- [`argparse`](https://docs.python.org/3/library/argparse.html) 的 `parse_args` 在錯誤時 `SystemExit(2)`；
  含義：CLI 應提供可測的 `main(argv) -> int`，把 usage error 與業務失敗都收斂成 exit code，而不是讓測試去攔 `SystemExit`。
- [`open()` mode `x`](https://docs.python.org/3/library/functions.html#open)：report 沿用 T3 的 create-only 語意，
  避免同一 capture root 被反覆覆寫成不同結論。

## 3. Repo 現況診斷

- T1 的 `JobAnalysisQualityRubric` 已是單一 rubric 資產且已被 loader 嚴格驗證，可直接作 grader 的唯一判準來源；
  `expectations.json`／`adjudication.md` 是人工裁決，**不進 grader input**，否則 LLM grader 會退化成答案比對而非 rubric 評分。
- T2 的 `StructuredOperationRequest` 已明確不含 provider wire fields，因此 preflight 必須另有一層 wire payload builder；
  它讀 neutral request 的 prompt／schema／input，產生 OpenRouter body，方向單向，不回灌 core。
- T3 的 `ResolvedResponseFacts` 已把 requested 與 resolved 分欄，且 `resolved_endpoint` 可為 null。T4 preflight 正好是
  這個欄位的唯一合法生產者：attested 才給值。
- `app/interview_vnext/providers/openrouter_*.py` 是既有 OpenRouter 知識來源（wire shape、`X-OpenRouter-Metadata`、
  selected endpoint 正規化、endpoint attestation 條件）。依 ADR 0040 §3 只能**逐項作 donor**：T4 重寫成小型 greenfield
  contract 與新測試承重，不 import、不 wrap、不沿用其 domain base、hashing、policy 或 conformance 型別。
- 現有 eval 模組沒有 CLI；`ScriptedProvider`／`ObservedScriptedProvider` 是唯一 external boundary fake，T4 的 dry-run
  provider 應延續同一模式（記錄 request、不捏造 output）。

## 4. 盲化投影的具體邊界

grader 看得到（判準所需的產物本身）與看不到（產生器自辯／自評）：

| 產生器欄位 | grader | 理由 |
|---|---|---|
| `SourceClaim` 全欄（含 anchors、ownership、time_scope、typicality、polarity） | 可見 | `source_grounding`／`role_responsibility` 的判準對象 |
| `Story.summary`／`claim_ids`／`outcome` | 可見 | `boundary_coherence` 的判準對象 |
| `WorkUnit`／`TaskCandidate` 的 statement 與 linkage | 可見 | Task 邊界與支持度的判準對象 |
| `ReconciliationDecision.kind`／linkage | 可見 | merge／split／no-op 是產物 |
| `NextQuestion.text` | 可見 | question rules 的判準對象 |
| `TaskCandidate.boundary` | **不可見** | 產生器對「grader 要評的六個維度」的自評；看了等於抄答案 |
| `TaskCandidate.limitations`、`WorkUnit.unresolved_boundary`、`Story.gaps` | **不可見** | 自陳限制＝自辯 |
| `ReconciliationDecision.rationale`／`missing_information` | **不可見** | 明確的 rationale |
| `UnmappedSignal.significance`／`missing_information` | **不可見** | 自評重要性 |
| `NextQuestion.action`／`target_gap` | **不可見** | 產生器自述意圖；question rules 只需題目本文 |
| arm ID、model tier、schema profile、harness profile、trial ID、requested/resolved model | **不可見** | 盲測；`submission_id` 由 `trial_id` 的 SHA-256 導出，關聯留在 grader manifest |

A1 minimal output 走同一投影，只是 claims／stories／work units 為空。這是 harness 本身的差異，不是標籤洩漏；
投影不得為了對齊而替 A1 補造結構。

## 5. 選項比對與 T4 裁決

| 選項 | 問題 | 裁決 |
|---|---|---|
| grader 共用 `OperationName` 與 generator provider port | 型別上無法阻止共用 prompt/model/capture，違反 ADR 0040 §17 | 不採 |
| grader 讀 `expectations.json` 當答案 | 變成答案比對，且人工裁決會被 LLM 分數污染 | 不採 |
| 執行期以字串過濾去掉 rationale | 新增欄位時會靜默洩漏 | 不採 |
| grader input model 完全沒有 rationale 欄位 + 位元組層測試 | 形狀即保證，新增欄位需顯式加入才會出現 | **採用** |
| CLI 也能寫 Trial Manifest | 沒有實際 trial 卻有 manifest，會被誤讀成 observation | 不採；manifest 只由執行過的 trial 發布 |
| dry-run 自行複製一份 request 組裝邏輯 | 會與 runner 漂移，dry-run 顯示的不是實際會送的東西 | 不採 |
| dry-run 用「記錄 request 後拒答」的 provider 走真實 runner | 顯示的就是實際 request；stage 2 因 fail-fast 不存在，正好誠實顯示 planned≠actual | **採用** |
| preflight 缺 endpoint evidence 時沿用 requested endpoint | 產生假證據，正是 ADR 0040 §22 禁止的 | 不採；fail closed |

以上都是 ADR 0040 §15／§17／§22／§26 已接受邊界的局部實現，沒有新的不可逆決策，**不需新 ADR**。

## 6. 明確留給 T5

T4 不選 strongest／cheap 的 exact model slug、不建立 HTTP transport 實作、不送任何 request、不查 generation endpoint、
不跑 8 案快篩、不做 shortlist／pass³、不計算實質改善門檻。`OpenRouterTransport` 只有 Protocol；CLI 的 `--live` 一律
以 exit code 2 拒絕並指向 owner 授權。取得付費授權後，T5 才實作 transport、執行 live preflight 與 48/80 快篩。
