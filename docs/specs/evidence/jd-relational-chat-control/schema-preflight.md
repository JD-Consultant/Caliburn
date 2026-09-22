# RS-4：聊天控制契約與原回合格式前置

查閱日期：2026-09-13。程式基準：`36cc1cb9`，隔離 `experiments/jd-relational-app`。本輪僅新增此文件；沒有更改 schema、生成物、程式或設定，沒有 DB／provider 呼叫。已做程式呼叫盤點與一次已安裝 Pydantic 的純離線解析探針。

建議採 **新請求 format 2、歷史保留 format 1**。Web 只送原話與 App 配發的原 request 身分／已確認 JD 引用；App 在共用 owner 內核准入。公開聊天契約仍由 JSON Schema 生成，內部 run record 仍是單一 Python 型別模組，不另建立持久 run 表或一般 migration 引擎。

## 1. 依據、效力與版本

本稿細化[前置契約](../jd-relational-ai-restart/chat-contract-preflight.md)，不重開已閉合的品牌調查；[最新有效狀態](../../../current-decisions.md)與[契約策略](../../../contract-strategy.md)維持入口。新宿主恢復已在[結果](../../2026-09-13-jd-ai-restart-recovery-slice.md)驗收，本稿不再將它列為未實作；聊天 HTTP／Web、Memory／來源與自然品質仍未完成。

| 證據 | 可證事實與本案映射 |
|---|---|
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)、[conversation state](https://developers.openai.com/api/docs/guides/conversation-state#manually-manage-conversation-state)，現行官方 API 指南，商業服務參照 | App 執行工具、按原 call ID 回結果；完整模型內容與工具結果保留。run ID、JD 版次和 HTTP 保存狀態由本 App 管理，並非要求模型代填的工具欄位。精確先前查閱與限制見前置契約 §2。 |
| [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)、[streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)，現行官方 Messages 指南，商業服務參照 | tool use/result 原身分配對；公開文字不等於完整訊息或整個 Agent 回合。沿既有完整終端驗證、native AIMessage／ToolMessage 保存；不在聊天 DTO 複製 provider 格式。 |
| [AWS safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，現行方法文 | 同 caller token 必須核同意圖。此處 digest 納 canonical start revision；相同已受理原請求查回優先，不能因目前 JD 已更新就重做。AWS 不規定本案 PG 表或宿主結構。 |
| [Pydantic discriminated unions](https://pydantic.dev/docs/validation/latest/concepts/unions/#discriminated-unions-with-string-discriminators)、[TypeAdapter](https://pydantic.dev/docs/validation/latest/concepts/type_adapter/)，本輪已開啟官方正文；已安裝 `2.13.5`，穩定、MIT | 原生依共同 literal 欄位選分支；TypeAdapter 可直接驗 union，並建議重用 adapter。用既有 format_version 當 discriminator，不寫自製舊格式升級器。 |
| 現 [generator](../../../../experiments/jd-relational-app/scripts/generate_contract.py) 與 [pyproject](../../../../experiments/jd-relational-app/pyproject.toml) | `datamodel-code-generator 0.79.0`／`json-schema-to-typescript` 沿既有 lock；新增一個 catalog schema 與兩個生成物。Python external-ref mapping 重用既有 DTO，不能手改生成物。`LangGraph 1.2.11`／Saver `3.1.2` 原生 checkpoint 保留。 |

以上是官方機制與本案映射，不把下列欄位／枚舉稱為兩家指定的通用聊天標準。

## 2. 新原請求與舊保存的確切差別

### 2.1 內部 record：兩個合法、互斥的 Python 分支

| 欄位 | `AiRunRecordV1`：只讀／恢復舊保存 | `AiRunRecordV2`：新 start 唯一輸出 |
|---|---|---|
| `format_version` | integer literal `1` | integer literal `2` |
| `dataset_id`、`document_id`、`run_id` | 原 canonical UUID 字串 | 同規則 |
| `request_digest` | 原 64 小寫 hex；原演算法不改 | 64 小寫 hex，新演算法如下 |
| `status` | `running / completed / cancelled / failed` | 同規則 |
| `start_revision_id` | **不存在**；不得補 null 或猜值 | required canonical UUID 字串 |

兩分支 `strict=True / extra=forbid / frozen=True`。新 builder 建議簽名 `new_run_record(dataset_id, document_id, run_id, text, *, start_revision_id)`；只產 V2。`AiRuntime.start(document_id, run_id, text, *, expected_revision_id)` 必填，建議沿內部 `UUID` 型別；builder 保存 `str(expected_revision_id)`。HTTP mapper 從真 signed revision ref 解出它，模型不用知道此欄。

- V1 digest 保持目前 `sha256(canonical_json({dataset_id, document_id, text}))`。
- V2 digest 建議 `sha256(canonical_json({format_version: 2, dataset_id, document_id, start_revision_id, text}))`。
- canonical JSON 沿現 `_canonical`：UTF-8、排序 keys、緊密 separator、非有限值拒絕；**原話不 trim、不換行轉換、不 Unicode 正規化**。run ID 是外層冪等 key，不用文字相等代替它。
- 同 run 改原話或改 canonical revision 必須 conflict；同版換不同合法 opaque token 不 conflict。舊 run lookup 不依賴客戶端重新提供原話或猜版。
- V1 仍能 observe／discover／lookup／合法 stopped recovery，閉合只將原 status 改為 terminal，**保持 format 1 與原 digest**。V1 不允許經新 `start` 假裝通過 V2 版次准入；若相同 run 碰到 V1，回明確 original lookup 所需狀態，由只讀查回處理。

原生方案：`Annotated[AiRunRecordV1 | AiRunRecordV2, Field(discriminator="format_version")]`＋模組級單一 `TypeAdapter`。內部 consumers 使用共同 `parse_run_record`／`parse_run_record_json` 薄函式；只作 shape／型別驗證與固定錯誤映射，不升級資料。

**已證的有限限制：**Pydantic 2.13.5 對 union 的 `Literal[1]` 即使 `strict=True` 仍接受 `true`、`1.0`，並正規化為 1；原有 strict int `Field(ge=1, le=1)` 會拒絕。本輪純離線結果為 `1→V1、2→V2、true→V1、1.0→V1、"1"→拒絕、3→拒絕`。因此薄 parser 在 native union 前，明確檢查 JSON object 的 `type(format_version) is int`，再委派 TypeAdapter；JSON 路徑也經同一檢查。此一欄防線保留既有格式規範，不是通用解析／migration 引擎。公開 DTO boolean literal 同樣沿既有狹窄出口防線，勿以 generated strict 宣稱已全部覆蓋。

### 2.2 START、Human、notice 與工具的影響

原 native START envelope 仍只有四欄 `jd_ai_run / messages / jd_ai_bindings / jd_ai_read`；**不新增第二個 start revision 欄在 envelope 或 HumanMessage**。原 Human 的 ID 仍是 run ID，content 仍是原話。`_initial_material` 要以新共用 parser 讀原 START record 和前一個 terminal record，允許 V1→V2、V2→V2；仍拒未知格式、錯 scope、錯 digest、混合 manual/AI pending。

`_material` 必須依實際 record 版本驗 digest，不能對 V1 使用 V2 演算法。原 root／child record 相等、前序 Human 保留、固定 checkpoint、原 binding 及 tool-call/result 核對維持。`AiRunObservation.record`、`DocumentCheckpoints.read` 也須改走同一 parser；只改 new builder 會令 manual gate 或新宿主拒絕合法 V2。

start revision 是**員工送出時已確認的 JD 准入基準**；`jd_model_view` 是**某次完整模型回覆所配 App notice 邊界**；`jd_ai_read.revision_id` 是**本輪真正 `jd_read` 的內容基準**。三者不互相填補或改名：

1. 新 run 先核 current head == expected revision，再在同文件 reservation 保留期間進 native input；核對與取得 reservation 之間不得開放 manual/catalog writer。
2. 純 `inspect_foreground_start` 讀完再釋鎖、稍後才 `start_foreground`，中間仍有競爭窗。建議 owner 的 `start_foreground` 在登記／派 Future 前、同 slot 內接受 App 驗版 callback；不保持 SQL transaction 到模型完成。
3. `_run` 第一次 current／turn_notice 可再核同基準，失配停止，不偷偷採新 head。已有原 request 的查回應先於這項「新准入」檢查。
4. 後續模型／工具可以正常令 JD 前進；工具須真正讀目前稿後才綁寫入，不要求整輪一直停在 start revision。`AiToolBinding`／read binding／`ModelView` 的格式仍是各自現有 format 1，不需一起加到 2。
5. input 前 notice／DB 失敗：既有 actual Future＋exact before-state 規則才可證 `input not_saved`。不因新增 expected revision 就改為「exception 一律沒保存」。

## 3. 公開 JSON Schema 的最小候選

新增 `contracts/jd-chat-http.schema.json`，沿 catalog root `$defs`＋具名 oneOf 分支；生成 `generated/chat_http.py`／`jd-chat-http.ts`。所有 object exact keys。以下是可施工候選，不是本輪已發布契約。

### 3.1 `ChatStartInput`

| 欄位 | 約束／來源 |
|---|---|
| `run_id` | canonical UUID 字串；Browser App 在明示送出一次時配發並先保存原 request。 |
| `text` | 非空非全白、無 NUL；原 128 KiB UTF-8 限制，外層 HTTP 1 MiB。JSON Schema 的 code-point maxLength 不代替 UTF-8 bytes 檢查。 |
| `expected_jd_revision_ref` | opaque nonempty string ≤4096；Browser flush 並確認後得到的原版 ref。 |

document 在 route，dataset 沿 `X-JD-Dataset`，body 不重複；新增 unsafe route 仍先核 Origin／dataset。服務解析既有 codec `revision` role、`history / observation` purpose，轉 canonical UUID 再交 runtime。此 Input 絕不成為 LLM tool schema。

### 3.2 `ChatRunState`：不以一個 success 代表三件事

所有分支共用 required `dataset_id / document_id / run_id / write_state`；三 ID canonical UUID，`write_state` **external ref** 到 `jd-manual-http.schema.json#/$defs/ManualDocumentState`，不抄其旗標與规则。

另有 `run_status / input_state / response_message_id / stop_requested / jd_effects`，依下表建立具名合法分支；表中的 `null` 是必填 null，不是省略欄位。

| `run_status`（App 觀察投影） | `input_state` | `response_message_id` | `stop_requested` | 約束 |
|---|---|---|---|---|
| `not_found` | `unconfirmed` | null | null | lookup 未找到完整原 request；不代表沒有在途請求，effects 不得 settled。 |
| `running` | `saved / unconfirmed` | 本輪已保存公開回覆 ID 或 null | bool | 僅真本機 owner Future 尚在執行；accepted 不等於 input 已存。 |
| `closing` | `saved / unconfirmed` | 同上 | bool 或 null | 真執行已停，App 持久收尾正在進行。 |
| `recovery_required` | `saved / unconfirmed` | 同上 | bool 或 null | 已知未解，GET 不擅自修復；write gate 繼續阻擋。 |
| `completed / cancelled / failed`，已存分支 | `saved` | 本輪已保存公開回覆 ID 或 null | null | 原 record terminal＋closure 已核，effects 必須 settled。completed 不表示 JD 已專業完整。 |
| `failed`，確知未存分支 | `not_saved` | null | null | 只限本地原 attempt 的既有證據；effects settled 且空。跨重啟查不到不得宣稱此分支。 |

`run_status` 中 running/closing/recovery_required/not_found 是**即時 App 投影**，不得寫回原 record 的四種 durable status。取消旗標不持久；terminal 不猜舊 Event 狀態。status 的 scope/run 與 write_state 是觀察，後續 mutation 仍重新准入。已存 AI tool-call-only 訊息沒有公開正文時，不拿它或前一輪訊息冒充本輪 response_message_id。

`jd_effects` 最小形狀：`{state: "unconfirmed" | "settled", results: BoundResult[]}`。`BoundResult` **只組外部 `$ref`**：既有 `CommittedResult / NoChangeResult / Confirmed* / Unconfirmed* / UnknownOutcomeResult`，排除 `Unbound*`；不重寫 `MutationResult` 的 status／error／refs 組合。既有 `operation_ref` 已提供查回身分，不再額外抄一次 operation_id。

- `settled` = 此原 run 已閉合、全部已綁寫入皆有確定回執、與該 run 的 SQL receipts 核對完整；results 只能是 confirmed 分支。純訪談可 settled＋空。
- `unconfirmed` = 尚不可宣告原 run 全部效果已知；可包含已 confirmed A 和 bound unknown B。空不表示「沒有改動」。未來可能發出的工具不先造假 operation。
- 第一控制切片可限定 results ≤96，對應本 runtime 既有 `recursion_limit=96`、單次不平行工具的上界；服務遇到超界舊資料須固定失敗而不截斷後稱 settled。若之後放寬 run 上界或需要更長 effects，另以固定原 run 分頁；本輪不先加通用事件頁或新表。這是本 App 的有界初版選擇，不是 provider 限制。
- 真結果從 `jd_operation.ai_run_id`／原 bindings 配對讀出並沿現 `project_observation`；不能只從最新 `_latest` 或模型文字猜。`confirmed committed + run failed` 是合法而且必要的組合。

對未解分支，`write_state.write_blocked` 必須 true；對 terminal／not_found 不能反向強制 false，因為目前可能是另一个 run、人工保存或封存阻擋。JSON oneOf 先限制本物件分支；原身分／SQL／complete／checkpoint 之間的證據由 App service 核，不交 Web 重算。

### 3.3 `ChatHistoryPage` 與 `ChatMessage`

推薦 page exact fields：`dataset_id, document_id, anchor, messages, next_cursor`。anchor／next_cursor 為同既有上限的 opaque string，未有任何 checkpoint 時 anchor=null、messages=[]、next_cursor=null。每頁 messages ≤50；選定固定 root／child 保存上界後才切頁，不能每頁讀 latest 造成重複／漏訊息。

`ChatMessage` exact fields：`message_id, run_id, role, text`。role 為 `user / assistant`，text 是已保存的公開文字；ID 保持真 native ID，run ID 從原 Human 到下一個 Human 的實際序列決定，不拿目前 run 代填。無可信 timestamp 不造 timestamp；不回 system／tool args／ToolMessage／thinking／signature／usage 或整個 provider JSON。無公開文字的 assistant message 可不列 UI；canonical Saver 原訊息仍完整保留。

history cursor 需綁 dataset／document／固定 root checkpoint／必要 child checkpoint／頁位置，使用已有 `itsdangerous` 的具名用途簽章接點。**目前 `ReadCursor` 只支援 JD 視圖，不能把聊天塞成 `history` view 或覆用 JD revision_ref 當 checkpoint ref。**可新增一個內部 typed cursor 與固定 salt，不建立一般 cursor framework。頁範圍是同一個已保存對話的 projection，不是把 `get_state_history` 每份完整 messages 疊加。

### 3.4 `ChatProblem` 與 HTTP 結果

沿 RFC9457 exact `type/about:blank, title, status, detail, instance/urn:uuid, code, next_action`。最低 code 取前置契約：`invalid_input, invalid_ref, document_missing, dataset_changed, stale_view, run_conflict, busy, recovery_required, service_unavailable, origin_not_allowed`；固定 status 403/404/409/422/500/503 與 next_action `correct_input/reread/lookup_run/wait/recover/stop`。route/service 固定映射，不能將底層原 error 填 detail。

start／cancel／recover 未閉合 202＋Location，原 terminal 200；GET 查詢成功 200 即使 run failed；document missing 404。不是所有 lookup 的 not_found 都能立刻輸出：原歷史 locator 尚未窮盡時要繼續有界查找或明確 unavailable，不讓「掃到上限」冒充不存在。原請求接收失敗 Problem 不宣稱原 Human/JD rollback。兩個開始／結果端點都回同一 `ChatRunState`，不另造 StartResponse 成功布林。

## 4. 基準程式的實際影響盤點

2026-09-13 以 `rg` 加 Python AST 盤點本 checkout，沒有讀設定或連 DB。位置是本基準行號，後續實作以符號為準。

| 位置 | 要調整的內容／數量 |
|---|---|
| [ai_checkpoints.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) | 原 `AiRunRecord`＋builder＋digest；5 個原 `AiRunRecord.model_validate*` 讀點改共用 parser：`_material`、`AiRunObservation.record`、START record、prior record、root record。close 保持所讀版本，只更 status。 |
| [runtime_checkpoints.py](../../../../experiments/jd-relational-app/src/jd_relational/runtime_checkpoints.py) | 第146–148行 manual idle gate 的一個 record 解析點；否則 V2 會被 manual/catalog/close 當成損壞。 |
| [ai_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py) | 唯一 src `new_run_record` caller；start 新必填版次、same intent 查回順序、同 slot 核版本、beforeinput／notice一致性。public status/history port 尚缺，不能 HTTP 直讀私有 `_latest`。 |
| [test_ai_runtime.py](../../../../experiments/jd-relational-app/tests/test_ai_runtime.py) | 14 個直接 `.start(...)`（含 reopened）＋2 個 `pool.submit(runtime.start, ...)`，共16處。`SyntheticRuntime._run` 跳過 production preinput，需另測真 `_run` 版次／notice規則；fake Storage 須提供明確 head。 |
| [test_ai_runtime_postgres.py](../../../../experiments/jd-relational-app/tests/test_ai_runtime_postgres.py) | 6 個 start；repeat 第二轮時要留原 start revision，不能即時讀較新 head來填舊原 request。 |
| [ai_host_recovery_worker.py](../../../../experiments/jd-relational-app/tests/ai_host_recovery_worker.py) | 3 個 start，均由各文件實際已確認 head 取得；重啟讀舊合成 V1 仍須維持成功，不清測試 schema。 |
| [test_ai_restart.py](../../../../experiments/jd-relational-app/tests/test_ai_restart.py) | 2 個 start＋1 builder。若 fixture刻意保留 V1，重啟結果改走原 lookup，不能把它升级 V2後才聲稱驗到舊相容。 |
| [test_ai_checkpoints.py](../../../../experiments/jd-relational-app/tests/test_ai_checkpoints.py) | 8 個 builder；有 `isinstance(record, AiRunRecord)` 與直接 `AiRunRecord.model_validate` 假設，需改 new V2／共用 parser。另保留直接定義原 V1 原文／digest 的 golden cases，不能全部 helper 改V2令V1覆蓋消失。 |
| [test_consultant_inspection.py](../../../../experiments/jd-relational-app/tests/test_consultant_inspection.py) | 2 個 builder，仍只測檢視不可執行。 |

合計 **25 個直接 start／4 個 test/helper 檔，另2個 executor轉交 =27處**；new_run_record **12處 =src1＋tests11**。這是語法呼叫位置數，不是測試案例數；未把 `.start_foreground`、thread.start 等不相關呼叫混入。

另有間接依賴 `test_ai_checkpoint_discovery.py`（讀 checkpoints fixture）、`test_foreground_restart.py`／原 owner與manual測試，以及 notices/tools 的共同接合。修改量不只給 start 多一參數：新 v2 混合讀、late原 run lookup、原子准入是這單位的實際正確性工作。

## 5. 精確一致性缺口与施工門檻

1. **歷史位置缺口：**目前 `_start.inspect_original` 可看到舊 Human 卻只 observe latest run；需先完成固定歷史 run locator。否則「T已完成→U已完成→重送T」既不能查回，也不能安全發新執行。
2. **准入空窗：**current read與owner reservation不能分開；先保留原 request 早於 stale檢查。測同key同版回原結果、同key不同版 conflict、新key舊版拒絕且Human未存。
3. **原始格式型別：**V1／V2分别原生嚴格解碼；unknown version、true/float version、缺／多 start欄、錯UUID、錯digest全部拒；混合V1歷史＋V2 START可觀察與閉合。
4. **三事實不可合併：**start202且input未知；savedHuman＋failedrun＋committedJD；closing時禁止manual；純訪談terminal且零effects；原PUT全失敗的本地not_saved；重啟缺run只unconfirmed。raw schema、generated Python與TS consumer都要驗分支。
5. **資料權威：**history固定同一snapshot、Human逐字、AI公開文字按原序列、工具與reasoning不洩漏；not_found必須已完成原範圍查找。effects核同run receipts，不依當前bindings或時間推斷。
6. **同一格式來源：**生成器加新schema及 external mappings，不更改舊schema以搬移權責。DTO字面型別測試與狹窄semantic mapper責任分清；不手寫Web重複types、不改模型工具參數。

依上述範圍可進入小切片：先 v2原record＋v1讀相容與原run locator／owner expected版准入，再新SSOT＋public service＋HTTP。既有userflow與SDK完整性已收斂，不需要為本切片再做全品牌研究、重選資料庫或引入聊天broker。真正待閉合的是上述可驗的接點，沒有需要再問使用者的產品選項。
