# R1 離線契約、fixture 與 deterministic verifier 實作研究

- 日期：2026-08-03
- 狀態：Research complete；供 R1 第一個離線 task 的 plan 使用
- 範圍：greenfield domain／operation contracts、8 個重新裁決 fixture、deterministic verifier
- 不含：prompt、runner、provider adapter、OpenRouter preflight、付費／live eval、DB、route、Web

## 1. 結論

第一個切片應在 `apps/api` 內建立全新的 `app/professional_consultant` Python package，使用目前已鎖定的
Pydantic 2.13.4 表達不可變、封閉且版本化的 operation values；另以純函式 verifier 檢查需要同時讀取來源與結果的
關係不變量。fixture 沿用 repo 的「一案例一目錄」擺放慣例，但不得 import 或複製 vNext 的 schema、gold、loader、grader
或 operation 名稱。

本切片是內部、全 Python、單一 app 的 seam，依 `docs/contract-strategy.md` 不需要先建立跨語言 JSON Schema package；
Pydantic class 是本階段的 typed SSOT。`model_json_schema()` 只作未來 provider schema 的來源，不能把它原封不動視為
OpenRouter portable contract。

## 2. 一手來源與實作含義

### Pydantic 2

- [Strict Mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)：預設會做型別 coercion；可在 validation call、
  field 或 `ConfigDict(strict=True)` 開啟 strict。官方亦明示 JSON input 在 strict mode 下可能比 Python object input 寬鬆。
  因此契約入口要固定：外部 JSON 用 `model_validate_json()`，內部建構傳入正確 Python 型別，不可依賴隱式轉型。
- [Configuration](https://docs.pydantic.dev/latest/api/config/)：`extra` 預設為 `ignore`，所以新契約必須明寫
  `extra="forbid"`；`frozen=True` 是 faux-immutability，只阻止 attribute assignment，並非遞迴凍結。所有 collection
  應使用 tuple，且不可在 model 內放可變 `dict`／`list`。
- [JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)：Pydantic 產生 Draft 2020-12／OpenAPI 3.1 相容 schema；
  `model_json_schema()` 預設輸出 validation mode。這只證明可產生完整 local schema，不代表任一模型端點接受所有 keyword。
- [Validators](https://docs.pydantic.dev/latest/concepts/validators/)：after field validator 在內建型別驗證後執行；after
  model validator 在整個 model 驗證後執行。適合放「單一 value 自足」的不變量，不適合偷偷查 transcript 或外部 state。

本機以 repo 的 Pydantic 2.13.4 驗證：`ConfigDict(strict=True)` 下，Python `list` 不會被轉成 tuple，但同一內容經
`model_validate_json()` 可由 JSON array 形成 tuple；`"1"` 仍不會成為 integer。另確認 `extra="forbid"` 會在
generated object schema 產生 `additionalProperties: false`。這個差異必須有 regression tests 固定。

### Python 標準函式庫

[Python `json` 文件](https://docs.python.org/3/library/json.html)說明 `sort_keys=True` 可產生穩定鍵序，
`allow_nan=False` 才是嚴格 JSON；預設 decoder 會接受重複 object key 並只留下最後一個。fixture／verification report
若需要穩定 bytes，應統一 `ensure_ascii=False, sort_keys=True, allow_nan=False`；fixture loader 應拒絕 duplicate key，
避免人工裁決被靜默覆蓋。

### OpenRouter

- [Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)要求 `response_format.type=json_schema`、
  `strict: true`，並要求先確認模型支援的 parameters。
- [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)明示預設路由可能把請求送到忽略未知
  parameter 的 provider；`require_parameters: true` 才會排除它，且 exact endpoint 需使用完整 provider slug、關閉 fallback。
- [Model endpoints API](https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints)提供逐模型 endpoint inventory。

官方目前沒有承諾「所有 OpenRouter endpoint 共用完整 Draft 2020-12 keyword 集合」。因此以下是保守推論，也符合
ADR 0040：provider schema 只承擔 object／array／基本型別、required、enum、required-but-nullable、
`additionalProperties: false` 與基本巢狀；local verifier 永遠再次驗證。quote 是否真的存在、reference 是否存在、
Task 是否錯收工具／過去／他人／一次性內容，都不是 structured output 能證明的事。

## 3. Repo 現況診斷

- `apps/api/pyproject.toml` 已 pin `pydantic==2.13.4`、Python `>=3.13`、pytest 8；本切片不需新 dependency。
- `app/job_authoring/contracts.py` 與 `app/interview_vnext/domain/base.py` 都採 `extra="forbid", frozen=True`；
  前者的測試亦固定 tuple、unknown field、schema generation 與 deterministic writer。可沿用測試風格，不能 import 它們。
- 兩處 docstring 都稱 value「strict」，但共同 base 並未設定 `strict=True`，且 job-authoring 測試刻意接受 list→tuple。
  新核心不可只複製名稱；需明確選擇真正的 strict config 並鎖住 JSON／Python 兩種入口行為。
- vNext 已有 provider schema projection、fixture loader 與 case layout；ADR 0040 明令其 schema、operation、gold、loader、
  grader 不可重用。唯一可採的是 repo 慣例：case directory、`transcript.jsonl`、獨立 adjudication，以及測試確保 runtime
  input 不會讀到答案。
- `docs/specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md` 已固定 8 類案例與
  Message → Claim／Unmapped → Story／Work Unit → Task Candidate → 一個下一問；本輪缺的是新的可執行資料形狀與局部不變量。

## 4. 選項比對

| 選項 | 優點 | 主要問題 | 裁決 |
|---|---|---|---|
| A. frozen dataclass + 手寫 parser/schema/verifier | domain 無第三方 dependency | schema、parser、Python type 三份真相；provider schema 很快 drift | 不採 |
| B. 所有規則都塞進 Pydantic validators | 檔案少、建構時立即失敗 | validator 拿不到允許來源；混淆 shape、跨物件引用與人工語意；錯誤文字成為不穩定契約 | 不採 |
| C. Pydantic intrinsic contracts + 純 deterministic verifier + 分離 adjudication fixture | 一份 typed shape；跨來源規則可測；未來 runner 可直接組合；不誤稱 schema 能驗語意 | 多一個 report／issue vocabulary | **採用** |

此選擇只是落實 ADR 0040 的既定責任分工，且可在 app 內局部替換，不需新增 ADR。若日後 R8 的 Web 要消費這些
internal analysis shapes，必須重新依 contract strategy 評估；不得提前把它們塞入 `job-workspace-contract`。

## 5. 建議的最小契約

共用 base：`ConfigDict(extra="forbid", frozen=True, strict=True)`；collection 一律 tuple；每個 top-level operation input／
output 帶固定 `schema_version: Literal[...]`。provider-facing output 欄位不使用「有 default 的 optional」：未知值使用
required nullable，零個項目使用空 array，避免 schema 必填逼出假 Task。

最小 value vocabulary：

- 來源：`EmployeeMessage(message_id, text)`、`QuestionContext`、`SourceSpan(message_id, start, end, quote)`；span 採
  Python Unicode code-point 的半開區間 `[start, end)`。
- 理解：`SourceClaim`（actor／ownership、time scope、typicality、polarity、certainty、correction target、anchors）、
  `UnmappedSignal`、`Story`。
- 整併：`WorkUnit`（claim/story refs、outcome、責任／穩定性資訊、support／counter refs）、`TaskCandidate`
  （support refs、boundary status）、`NextQuestion`（單一 object，action 僅 broaden／deepen_story／clarify_boundary）。
- operation：`TurnUnderstandInput/Output`、`WorkReconcileDecideInput/Output`，以及一次呼叫 arm 使用的
  `TaskDiscoveryInput/Output`。兩條架構共用同一組 leaf values，不共用舊 vNext type。

Pydantic validators 只處理自足規則：空白、長度／offset 非負、tuple 內 local ID 不重複、correction 有 target、
nullable 欄位組合。跨 message／claim／story／work-unit 的存在性與有效性留給 verifier。

## 6. Fixture 與 verifier 邊界

建議位置為 `apps/api/evals/professional_consultant/r1/cases/TI-R1-01-*` 至 `TI-R1-08-*`。每案至少四份：

1. `case.json`：`case_id`、無預設值的 `source_type`、`case_family_id`、版本與檔案 references；本批人工構造案例全標
   `constructed_edge`。
2. `transcript.jsonl`：只放 runner 未來可見的 source messages。
3. `expectations.json`：machine-readable critical expectations，例如允許的 task 數量範圍、必須保留的 qualifier、
   禁止升格類別、下一問 action；它不是逐字唯一 gold。
4. `adjudication.md`：依新 Task rubric 說明為何 merge／split／no-op／supersede，以及哪些判斷只能人工／blind grader 做。

loader API 必須把 runtime input 與 expectations/adjudication 分開，並有測試證明 runtime path 不讀後兩者。

`verify_task_discovery(source, result) -> VerificationReport` 應是無 I/O、無模型、無全域狀態的純函式。Report 使用固定
issue code、結構化 path/entity ID，最後按 `(code, path, entity_id)` 排序；測試不得把 Pydantic 的英文 message 當公共契約。
最小檢查集合：

- source message／span 存在、offset 有界且 `text[start:end] == quote`；每個正式 claim／work unit／task 至少一個 anchor；
- ID 唯一，所有 claim/story/work-unit/correction/support/counter reference 都存在；superseded claim 不得繼續作有效支持；
- actor、time、ownership、typicality 的明確 disqualifier 不得作 Task 的唯一正向支持；Task array 可為空；
- 同一 relation／同一 source span 的 exact duplicate 禁止；文字近義重複仍交給 rubric，不能假裝 deterministic；
- `next_question` 只有一個 object、非空，且不與 transcript 中最近 AI 問句 exact-normalized 重複。

verifier **不判斷** outcome 是否有意義、兩故事是否語意同一 Task、工具名是否一律非 Task、問題是否自然／引導，
也不以關鍵字 blacklist 取代 Task rubric。這些屬 `expectations.json` + 人工／後續 blind grader。

## 7. 明確不做與下一步證據

- 不 import/wrap `app.interview` 或 `app.interview_vnext`；加 AST dependency guard。
- 不複製 vNext `DomainModel`、portable-schema projector、hash、Evidence、loader、gold 或 grader。
- 不建立 provider port、prompt、runner、CLI、Trial Manifest、capture、DB、route、Web；這些是後續 task。
- 不呼叫 OpenRouter，不選 model／endpoint，不把 offline tests 稱為 R1 gate passed。
- 不產生跨語言 package；R1 internal contract 仍在 Python app 內。

下一份 plan 應逐檔安排：先寫 contract/JSON-entry tests與 import guard，再建立 8 案 fixture contracts／loader tests，最後
以失敗案例驅動 verifier issue codes；完成條件至少包含 targeted pytest、8 案全載入、預先製作的 invalid outputs 全被擋、
valid boundary outputs 全通過、schema vocabulary snapshot、`git diff --check`。本切片完成狀態只能是 R1 的局部
IMPLEMENTED／OFFLINE-READY 證據，不得建立 `r1-task-discovery-gate` tag。
