# Interview AI vNext V2——Provider Port、Context Boundary 與 Capture 2026 再驗證

- 日期：2026-07-16（Asia/Taipei）
- 狀態：V2 實作前研究完成；本文細化 ADR 0034，不取代 ADR
- 範圍：provider-neutral LLM port、operation registry、失敗語意、context/provider state 邊界、Capture artifact/event/outbox/checkpoint
- 不在本階段：正式訪談 prompt、live provider adapter、資料庫 migration、production route、模型定案

## 1. 為什麼 V2 前再研究一次

vNext 的核心方向已由 ADR 0034 核准，但 2026 年供應商 API 仍快速變動。若直接把某家 SDK 的當期欄位寫成 domain contract，短期看似先進，之後會出現三類問題：

1. provider conversation、compaction 或 background job 被誤當成 Caliburn 的 durable state；
2. `200 OK`、schema 合格或正常停止被誤判為內容可信；
3. cache、sampling、reasoning 等供應商設定滲入 operation 定義，使同一 eval case 無法公平跨 provider 比較。

因此本輪逐頁閱讀 OpenAI 與 Anthropic 的官方 API／工程文件，重新檢查截至 2026-07-16 的現行做法、已公告退場項目及新 API 邊界。研究問題不是「哪個 SDK 最流行」，而是：

- 哪些能力應進 Caliburn 的穩定 port；
- 哪些能力只能留在 adapter；
- provider 回傳的各種完成、拒絕、截斷與錯誤如何正規化；
- 如何讓 Capture 足以重現輸入、判斷與 state transition，又不保存 hidden chain-of-thought；
- crash 後如何判斷重用 artifact、重做 verification 或重試 provider call。

## 2. 資料採用標準與閱讀範圍

只採一手來源：供應商官方 API 文件、官方工程文章及已核准架構規格。搜尋結果只用來定位頁面，結論建立在完整頁面或對應章節，不採社群文章、SEO 彙整、未標版本的教學或二手框架比較。

### 2.1 OpenAI 已閱讀頁面

| 官方頁面 | 本輪核對內容 | V2 影響 |
|---|---|---|
| [Migrate to the Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses) | Responses 的 typed items、structured output API shape、state 選項與 storage 預設 | 新 adapter 只考慮 Responses，不新增 Chat Completions／Assistants 核心依賴 |
| [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) | 手動 history、`previous_response_id`、Conversations、保存期限與 token 計價 | provider state 只作 optimization；Caliburn record/state 仍是權威 |
| [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | `text.format` strict schema、refusal、schema mismatch 與 user-input edge case | port 必須區分 parsed、refused、incomplete；schema 後仍跑 domain verifier |
| [Compaction](https://developers.openai.com/api/docs/guides/compaction) | server-side 與 standalone compaction、opaque compaction item | compaction item 可 round-trip，但不能成為 evidence 或 audit source |
| [Background mode](https://developers.openai.com/api/docs/guides/background) | async start、poll、cancel、terminal status | provider job ID 可支援長 call recovery，但不能取代 operation checkpoint |
| [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | exact-prefix、stable-first ordering、cache key／breakpoint／usage | cache policy 留在 adapter profile；Capture 保存 cache usage，不承諾 hit |
| [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | task-specific eval、workflow step eval、pairwise／classification、human calibration | 自有 eval harness 保留；每個 operation 單獨評測 |
| [Deprecations](https://developers.openai.com/api/docs/deprecations#2026-06-03-evals-platform) | 舊 Evals platform 2026 退場時程 | 不把唯一 dataset、grader 或歷史結果放在 provider dashboard |

### 2.2 Anthropic 已閱讀頁面

| 官方頁面 | 本輪核對內容 | V2 影響 |
|---|---|---|
| [Using the Messages API](https://platform.claude.com/docs/en/build-with-claude/working-with-messages) | stateless multi-turn、現行參數限制 | adapter 每次從 Caliburn context packet 組 request，不依賴隱含 session |
| [Create a Message](https://platform.claude.com/docs/en/api/messages/create) | Messages input/output 與 prior-turn contract | neutral port 不複製 SDK class，只保存可攜 metadata/artifact |
| [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | `output_config.format`、strict tools、schema limits、`max_tokens` edge case | schema 由 operation contract 產生；adapter 做 provider schema projection |
| [Stop reasons and fallback](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons) | `end_turn`、`max_tokens`、`pause_turn`、`refusal`、context-window stop | port 使用 normalized outcome/finish reason，不讓 workflow 判斷 Claude 字串 |
| [Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) | server-side compaction 與已 deprecated 的 SDK client compaction | 不新增 `compaction_control`；context 壓縮是可替換 adapter/harness 能力 |
| [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | exact-prefix、tools→system→messages hierarchy、automatic/explicit cache | stable content 前置；cache 只影響成本/延遲，不影響輸出語意 contract |
| [Scaling Managed Agents](https://www.anthropic.com/engineering/managed-agents) | durable session log 在 context window 外、harness 可替換、event slice retrieval | 驗證 Caliburn Record／Working State／Model Context 三層分離 |
| [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | task、trial、grader、transcript/trajectory、outcome、兩種 harness | Capture 同時保存 trajectory 與 outcome；release 不只看最後模型文字 |

## 3. 2026 官方資料的關鍵事實

### 3.1 Stateful provider API 不等於應用程式擁有狀態

OpenAI Responses 現在有三種延續方式：應用程式重送 items、以 `previous_response_id` 鏈接，或使用 Conversations 的 durable identifier。官方同時說明：top-level instructions 不會因 `previous_response_id` 自動沿用，provider response 有自己的 retention 規則，而且鏈中的舊 input tokens 仍會計入輸入。

Anthropic Messages 則明確維持 stateless multi-turn：呼叫端提供先前的 `user`／`assistant` turns。兩者表面不同，但對可攜產品的結論相同：

- Caliburn 必須能從自己的 transcript、working state、artifacts 與 reference snapshot 重建下一次 request；
- provider conversation/response/message ID 只能放 execution metadata；
- provider ID 可加速延續或協助 reconcile，遺失時不得使訪談不可恢復；
- stable instructions、schema 與 context policy 每次都由 operation definition 明確決定，不假設 provider 自動繼承。

### 3.2 Structured output 解決「形狀」，沒有解決「真實性」

OpenAI 以 `text.format` strict JSON Schema 提供 schema adherence，Anthropic 以 `output_config.format` 或 strict tool schema 提供 constrained output。這已是 2026 主流邊界，舊式「要求回 JSON，再用寬鬆 parser 修字串」不應進新架構。

但官方文件也列出不能忽略的 edge cases：

- OpenAI refusal 是獨立 content，不保證符合 requested schema；
- OpenAI 提醒：輸入與 schema 不相容時，模型仍可能為了填滿 schema 而產生錯誤內容；
- Anthropic `max_tokens` 可留下 incomplete、未符合 schema 的輸出；
- Anthropic 部分 enum casing 仍可能需要 adapter normalization；
- 兩家 strict schema 都只保證可解析／結構限制，不保證 quote 存在、員工真的說過、ownership 正確或 reference 沒被洗成 evidence。

所以 V2 使用兩層驗證：

1. **provider/contract validation**：輸出是否完整且符合 operation schema；
2. **domain semantic validation**：quote/span/lineage/polarity/time/ownership/evidence closure 與 state invariant 是否成立。

第一層通過不會自動 commit state。LLM 永遠只產 proposal，deterministic reducer 才有寫入權。

### 3.3 完成、拒絕、截斷與失敗不能只靠 HTTP status

Anthropic 明確指出 refusal 可以是成功 HTTP response，`pause_turn`、`max_tokens` 與 `model_context_window_exceeded` 也都有不同 continuation 意義。OpenAI Structured Outputs 同樣有 refusal，Responses/background execution 還有 queued、in-progress、completed、cancelled 或 failed 等生命週期。

因此 neutral result 不使用單一 `success: bool`，而是：

- `outcome=succeeded`：有完整 parsed proposal；
- `outcome=refused`：供應商明確拒絕，沒有可 commit proposal；
- `outcome=incomplete`：因 output/context limit、cancel、pause 或其他非完整終止，visible partial output 只作 artifact；
- `outcome=failed`：transport、timeout、rate limit、auth、invalid request、provider 5xx、schema validation 等失敗。

另保存 normalized `finish_reason` 與 provider 原值。workflow 只依 normalized enum 決定 retry/repair/recovery，provider 原值只供除錯與後續新增 mapping。

### 3.4 Compaction 是有損的 model-context primitive

OpenAI 的 server-side／standalone compaction 會回傳 opaque item，官方要求 round-trip 該 item；Anthropic 也把 server-side compaction 作為目前建議，並已標記 SDK 的 client-side `compaction_control` 為 deprecated。

Anthropic Managed Agents 進一步指出：壓縮、trim 或摘要都會做不可逆選擇，未來 turn 需要哪段資訊難以事先知道；其 durable session log 因此存在 context window 外，再由 harness 選 event slices。這直接否定兩種舊設計：

- 不可把 provider compaction item／summary 當員工 evidence；
- 不可只保存壓縮後 context 而刪原始 transcript/artifact。

Caliburn 可在 adapter 中 round-trip opaque provider item，也可產 episode summary，但它們都只是 derived model-context artifact。任何 JD claim、correction、review 或 audit 必須能回到自己的原始 record/evidence。

### 3.5 Prompt caching 是效能策略，不是記憶

兩家都要求 exact-prefix 才可能命中，並建議把穩定內容放前面、變動內容放後面。OpenAI 有 cache key／breakpoint 與 usage，Anthropic 有 tools→system→messages 的 prefix hierarchy。這支持 ContextBuilder 的固定排序，但不應把 provider-specific cache knob 放入 business contract。

V2 的分工是：

- operation 定義穩定 prompt/schema/context policy identity；
- ContextBuilder 產 deterministic packet 與 selection manifest；
- adapter 決定如何投影 cache key、breakpoint、TTL 或 provider profile；
- result 保存 provider 有提供的 cache read/write usage，缺值保存 `null` 與 limitation；
- correctness、recovery 與 state hash 永遠不依賴 cache hit。

### 3.6 Background execution 是 transport lifecycle，不是 workflow lifecycle

OpenAI background mode適合可能超過一般連線時間的長 reasoning call，並提供 poll/cancel。這對未來 `episode_code` 或 `global_consolidate` 有用，但 interview turn 的 workflow checkpoint 仍需存在：provider job 可能已完成而 local reducer 尚未 commit，也可能 local process 在取得 provider ID 前中斷。

因此 V2 先定義 provider-neutral operation/attempt/checkpoint；是否使用 background mode由 adapter/model profile 決定。即時 `turn_interpret` 不因 background API 流行就預設改成 polling。

### 3.7 自有 eval 與 Capture 不是重複造輪子

OpenAI 官方仍建議 eval-driven development、task-specific cases、逐 workflow step 評測、pairwise/classification 與人工校準，但舊 Evals platform 已公告 2026 年退場。Anthropic 則區分完整 trial transcript/trajectory 與環境 outcome，強調兩者都要評。

所以 Promptfoo、provider dashboard、OpenTelemetry 都是 exporter/consumer，不是唯一 source of truth。Caliburn 自己保存 versioned cases、operation artifacts、grader outputs、state outcome 與 run manifest，才能跨模型／provider／平台退場持續比較。

## 4. 選項比較與裁決

| 問題 | 選項 | 裁決 | 理由 |
|---|---|---|---|
| orchestration | provider Agents SDK／Managed Agents 當核心；自有明確 workflow | 自有 workflow | 訪談分析步驟與 invariants 已知；provider harness 只能作 adapter 或未來長任務選項 |
| provider state | Conversations/response ID 作唯一歷史；app-owned state | app-owned state | 可攜、可重播、可 crash recovery；官方 state API 仍有 retention/inheritance 差異 |
| output | JSON mode／parser repair；strict structured output | strict structured output | 兩家目前皆有正式 schema boundary；parser fallback 會掩蓋 incomplete/refusal |
| semantic correctness | schema 通過即寫 DB；domain verifier + reducer | verifier + reducer | schema 無法證明員工說過、quote 存在或 ownership 正確 |
| context growth | 永久全量 history；只留 summary；durable record + selected context | durable record + selected context | 同時保真、控制 token、允許重建與 ablation |
| compaction | client SDK compaction；provider server compaction；完全不使用 | 可選 server compaction，但非權威 | Anthropic client path 已 deprecated；兩家 compaction 都是 model-context optimization |
| eval | provider dashboard；自有 portable harness | 自有 harness，可 export | OpenAI 舊平台已公告退場；跨 provider 才能公平 bake-off |
| V2 provider SDK | 現在直接接兩家；先完成 neutral contracts + fake | 先 contracts + fake | 先以 contract tests 固定語意，V6 再用 operation eval 選 model/profile；避免 SDK object 污染 |

## 5. V2 穩定契約

### 5.1 Operation definition

`OperationSpec` 是「一類可評測語意工作」的不可變定義，不是一個 provider request。至少保存：

- stable `name` 與 semantic version；
- input/output schema ID 與 canonical schema hash；
- prompt template ID/version/hash；
- context policy ID/version/hash；
- quality profile；
- deadline、max attempts、max output tokens；
- allowed tool stable names；
- repair policy與 safety policy flags；
-由上述 canonical content 產生的 `definition_hash`。

registry 拒絕同名不同 definition，也拒絕用不同名稱偷偷註冊相同身份。部署層以 `(operation name, definition hash, environment)` 解析 provider/model profile；operation 本身不硬編某家模型名、temperature 或 beta header。

### 5.2 Request boundary

一個 model attempt 至少有：

- stable `operation_id`（跨 retry 不變）與唯一 `attempt_id`；
- one-based `attempt`；
- operation name/definition hash；
- idempotency root；
- instructions/messages 的 portable text representation；
- prompt、output schema、context packet與 selection manifest的 artifact reference/hash；
- requested quality profile、deadline/max output tokens；
- tracing parent IDs。

V2 不宣稱 provider call 本身 exactly-once。相同 operation 可有多個 attempts；每次都留下 request/result artifact。只有 reducer command 的 idempotency 與 local transaction能保證 state mutation 不重複。

### 5.3 Result boundary

`ModelCallResult` 至少保存：

- `outcome`、normalized `finish_reason`、provider 原 finish value；
- provider、requested/resolved model、request/message/response/job ID（metadata only）；
- parsed proposal或 normalized failure/refusal；
- visible response artifact；hidden chain-of-thought 不要求也不保存；
- input/output/cache read/cache write/reasoning usage；每欄可為 null；
- usage limitations；
- latency、started/completed timestamps；
- operation/attempt identity；
- prompt/schema/context/definition hashes。

資料不變量：

- `succeeded` 必須有 parsed proposal，不能同時有 failure/refusal；
- `refused` 必須有 normalized refusal，partial content 不可作 proposal；
- `incomplete` 可有 visible partial artifact，但不能有可 commit parsed proposal；
- `failed` 必須有 normalized failure；
- resolved model 與 promotion manifest 不符是可觀測 mismatch，不可靜默當成 requested model。

### 5.4 Normalized failure taxonomy

V2 初版分類：

- `transport_timeout`
- `transport_error`
- `rate_limited`
- `authentication_failed`
- `invalid_request`
- `provider_unavailable`
- `cancelled`
- `output_schema_invalid`
- `output_parse_failed`
- `resolved_model_mismatch`
- `unknown_provider_failure`

每個 failure 保存 `retryable`、stable reason code、safe message、provider error code與 visible artifact reference。workflow 不解析自然語言錯誤訊息決定 retry。

`refusal` 不混入 transport failure；`max_output_tokens`／`context_window_exceeded` 不混入 schema failure。這些差異會影響 retry、修 prompt、調 budget或安全回覆，必須可在 eval 中分開統計。

## 6. Capture vNext 精確資料模型

### 6.1 三種紀錄分開

| 紀錄 | 目的 | 可否改寫 | 是否足以重建 business state |
|---|---|---|---|
| Domain event/command | 業務 mutation 與 idempotent replay | append-only | command + initial state 可重播；event notification本身不一定含 payload |
| Execution event | workflow／model／verification 發生了什麼 | append-only | 否；它引用 artifacts/checkpoints |
| Artifact | request、visible result、parsed proposal、selection manifest、state snapshot等大 payload | immutable | 視 artifact kind；hash 可驗內容未變 |

三者不可共用一個含糊的 `log` row。execution event 描述執行，不宣稱自己是 domain fact。

### 6.2 Artifact

每個 artifact 有：

- unique ID、kind、media type；
- schema ID/version（沒有 schema 時為 null）；
- canonical content hash、byte size；
- run/session/turn/operation/attempt identity；
- created timestamp；
- inline JSON/text 或外部 object reference，二者恰一；
- retention/redaction/test-data metadata。

相同 artifact ID 重寫相同內容是 idempotent；不同內容必須 conflict。artifact hash 對 canonical payload 計算，不信任 caller 傳入的 hash。

### 6.3 Execution event與 hash chain

event envelope 維持 open-string `event_type` 與 `stage`，但必須通過 versioned taxonomy registry。taxonomy以完整 semver + content hash識別並保留歷史 document；新增名稱建立新版本，不覆寫舊 run引用的內容。至少保存 run-local sequence、previous event hash與 event hash。event hash 由除 `event_hash` 外的 canonical event content 計算。

validator 必須檢查：

- sequence 從 1 連續；
-第一筆沒有 previous hash，其餘必須指向前一筆；
- canonical hash 正確；
- run/session identity 不在鏈中途變更；
- referenced artifact ID/hash配對存在；
- completed manifest 的 event count/last hash吻合。

hash chain 用來偵測缺漏／改寫，不是加密簽章或惡意管理員防竄改保證；若未來有合規需求，再加入外部簽章／WORM storage。

### 6.4 Outbox

workflow transaction 把 execution event payload寫入 local outbox；外部 Capture/OTel/exporter 失敗不回滾已完成的 domain transaction。outbox contract 必須有：

- event/message stable ID的 idempotent enqueue；
- pending→leased→delivered或 retryable failed；
- lease expiry可被另一 worker接手；
- attempt count、next attempt、last error；
- exporter 以 event ID去重。

V2 in-memory fake只驗證狀態機與 idempotency；資料庫 row lock／`SKIP LOCKED` 等作法留到 persistence migration，不能由 fake 成功提前宣稱跨 process可靠。

### 6.5 Operation checkpoint與 recovery matrix

checkpoint 不使用含糊的 `started/completed` 二態。初版狀態：

| 狀態 | durable record 已有什麼 | recovery 動作 |
|---|---|---|
| `prepared` | operation definition、input/request artifact、idempotency root | 建立下一個 attempt並呼叫 provider |
| `calling` | active attempt request與 started event；所有較早 attempt result artifacts；可能有 provider job ID | 可查 provider則 reconcile；否則先保存本次 failure/incomplete artifact，再以遞增序號與新 attempt ID重試，不覆寫舊 attempt |
| `provider_completed` | normalized result與 visible/parsed artifact | 不再呼叫 provider；執行 schema/domain verification |
| `verified` | verification artifact與 accept/reject result | accepted 才以 idempotent command執行 reducer |
| `committed` | state after hash、domain command/result與 response artifact | 直接重用已保存 outcome |
| `failed` | terminal failure與 reason | 依 workflow policy回錯誤、人工處理或新 operation；不自動無限 retry |

允許 `provider_completed → failed`（結果不可驗）、`verified → failed`（reducer conflict／policy reject）與任一非 terminal state在明確取消後進 `failed`。`committed` 與 `failed` 是 terminal。重送相同 transition是 idempotent；跳過中間 durable artifact的 transition必須拒絕。

### 6.6 一致性宣稱邊界

完成 V2 contracts與 in-memory tests後可以宣稱：schema、hash、transition與 retry語意已定義且 deterministic。尚不能宣稱：

- DB transaction／outbox 已跨 process crash驗證；
- provider request exactly-once；
- live OpenAI／Anthropic mapping 正確；
- prompt、ContextBuilder或模型品質已達 production；
-整個訪談可只靠 execution events重建。

這些分別在 persistence migration、provider contract test、V3 fixed replay與 V6 bake-off取得證據。

## 7. Fake provider必要案例

`ScriptedLlmPort` 不只是回固定字串；它必須以 operation + attempt script 驗證 workflow：

1. valid structured proposal；
2. `output_schema_invalid`；
3. explicit refusal；
4. timeout／rate limit／provider unavailable；
5. incomplete output（output token/context window）；
6. requested/resolved model mismatch；
7. attempt 1 retryable failure、attempt 2 success；
8. unexpected operation、script exhausted、attempt順序錯誤時立即 fail test；
9. fake保存收到的 immutable requests，讓 tests檢查 hash與 idempotency沒有在 retry漂移。

fake不能 import OpenAI/Anthropic SDK，也不能模擬不存在的「provider 保證 exactly-once」。

## 8. 本輪實作順序與停止線

1. committed research delta與官方來源；
2. immutable `OperationSpec`、registry、request/result/failure contracts；
3. `ScriptedLlmPort`與 contract tests；
4. artifact、execution event、taxonomy、hash-chain、manifest；
5. outbox/checkpoint in-memory state machine與 recovery tests；
6. published JSON Schemas、dependency guard與 README；
7.全 API regression測試；
8. commit後才進資料庫 persistence或 V3 ContextBuilder。

若 neutral contract 開始需要 provider beta header、SDK response class、OpenAI `response_id` 或 Claude `stop_reason` 才能運作，立即停止並把 mapping退回 adapter。若測試只驗 Pydantic parse、沒有驗 outcome/retry/hash/recovery不變量，也不得宣稱 V2 完成。

## 9. 結論

截至 2026-07-16，最新大廠方向不是「把全部聊天交給一個更大的 agent framework」，而是：供應商提供更強的 structured output、state、compaction、background與cache primitives；應用程式仍需擁有 durable state、清楚 workflow、typed boundaries、可替換 context harness與 outcome eval。

V2 因此採用：

> **app-owned operation/checkpoint + provider-neutral structured attempt + immutable artifact/event/outbox + deterministic verifier/reducer boundary**。

OpenAI Responses／Conversations、Anthropic Messages／server-side compaction與兩家的 prompt cache都可在 adapter利用，但沒有任何一項可以取代 Caliburn 的 Evidence、State、Capture與 eval。這樣既跟上 2026 主流能力，也避免下一次 provider API 改版時重寫整個專業顧問核心。
