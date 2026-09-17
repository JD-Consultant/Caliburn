# JD 錯誤與恢復契約：ER01–03 收斂依據

日期：2026-09-10。Topic：JD-R002/C03。效力：Owner 同意契約補正後的有限工程推薦，供主稿、共用 schema 與六切片計畫統一；不是 production 已接線或故障恢復已通過的證據。狀態以 [current register](../../current-decisions.md) 為準。本文只新增此附件，未修改 schema、程式、資料庫、Memory 或模型配置，未安裝或付費呼叫。

> **2026-09-18 successor：**本文的 Node／SQL／receipt 每階段 1 attempt、0 automatic replay 及未知副作用先對帳規則完全保留。只有模型收到可修正工具結果後的 correction budget，改由 [A 主顧問執行額度與安全收尾](../2026-09-18-consultant-execution-budget-and-safe-finalization.md)明定為原始失敗後最多兩次替代提交；它不是 Node、SQL、transport 或整輪 Agent replay，也不改寫本文的歷史研究證據。

閱讀基線：[責任稽核 §4](../2026-09-10-jd-responsibility-and-evidence-audit.md#4-錯誤重試與停止的責任)、[工具契約 §6–7](../2026-09-10-jd-app-tool-contract.md#6-結果與錯誤契約)、[正式契約 §4](../2026-09-10-jd-editor-contract-schema.md)、[主設計 §6–7](../2026-09-09-jd-editor-app-integration-design.md#6-成功失敗及回覆遺失)及[六切片計畫](../../plans/2026-09-10-jd-editor-core-implementation.md)。共用文件與 schema 由主工作單位修改；本文記錄選擇理由與驗收邊界，不成為第二份 schema owner。

## 1. 結論與官方證據的效力

採一份人編／AI 共用結果、兩層 write matrix，以及單一 typed read failure 出口。模型可以在允許的情況修參數、重讀與重新規劃；App 獨占執行、保存、回執對帳、程序清理及停止責任。`wait`／`reconcile_operation` 是 App 動作，不新增模型 retry 工具，不增加泛用 `retryable` 布林。

v1 每個明定執行階段最多 **1 attempt、0 automatic replay**。Node 控制預算 30 秒；終止等待 5 秒，再強制終止並回收等待 5 秒。SQL attempt 控制預算 30 秒，保留連線 5 秒／單 statement 10 秒／等鎖 5 秒限制。這些是本案可配置起始值，已交主工作單位採用；官方支持的是有限執行、適當取消、可證明副作用及避免重試放大，沒有規定這組秒數或必須零重試。

取捨是短暫故障不會當場自動自癒，但首版不把模型、引擎、SQL 與回執迴圈疊成未證明安全的重播鏈。將來增加 retry 需要實測 transient 類型、可證明的前次結果、完整 transaction 邊界、attempt／elapsed budget、取消與退避；不是只把上限從 0 改大。

## 2. ER01：先判斷回執閉合，再選下一動作

`document_effect` 回答這次操作對文件的效果；`receipt_durability` 回答 terminal receipt 是否已持久確認。**已知未改但回執未閉合，仍是 `unchanged`，不能為了進入恢復流程改報 `unknown`。** `operation_conflict` 的 `unchanged` 只指被拒絕的衝突 payload，不能推論原操作也未改。

### 2.1 第一層：必須優先的恢復條件

| 條件 | 唯一允許的 `next_action` | App 責任 |
|---|---|---|
| `status=outcome_unknown` | `reconcile_operation` | 必須有原 `operation_ref`，效果為 `unknown`、回執 `unconfirmed`；查原結果，禁止配置替代 operation |
| 任一確定 write error，`operation_ref != null` 且 `receipt_durability=unconfirmed` | `reconcile_operation` | 效果保留 `unchanged`；先閉合原 binding／回執，不能讓模型先另發修正版 call |
| `operation_conflict`、原操作回執未確認 | `reconcile_operation` | 必帶原 `operation_ref`，只處理原 request；不保存衝突 payload，也不覆寫原結果 |

此層優先於下表。`busy` 發生在 admission 前，嚴禁帶 operation，因此不能藉 `busy` 掩蓋已發配而未閉合的寫入。任何 `operation_ref=null` 的結果都不能聲稱 terminal receipt `confirmed`。

### 2.2 第二層：已閉合，或尚未發配 operation 的完整 matrix

表中動作以第一層不適用為前提。多個動作表示 producer 可依實際原因選其中一個，不能一次要求全部動作。

| `status` | `document_effect` | receipt／identity 條件 | 允許的 `next_action` | 執行責任與限制 |
|---|---|---|---|---|
| `committed` | `committed` | `confirmed`，有 operation／base／result／change | `continue` | App 回傳實際結果；模型依 actual changes 續談 |
| `no_change` | `unchanged` | `confirmed`，有 operation 與可對帳結果 | `continue` | 不造內容 revision，不聲稱改了不存在的文字 |
| `invalid_input` | `unchanged` | binding 前無 operation、`unconfirmed`；binding 後 terminal 已 `confirmed` | `correct_arguments` 或 `stop` | 可修參數才產生新 call；不改已綁定的 exact request |
| `unsupported_content` | `unchanged` | 同上 | `correct_arguments` 或 `stop` | 寫入要求可改用支持方式時才修正；不得刪掉有效內容以求過測 |
| `target_missing` | `unchanged` | 同上 | `reread_current` 或 `stop` | 用實際可讀 current／新 refs 重新規劃，不猜相似目標 |
| `stale_base` | `unchanged` | 同上 | `reread_current` 或 `stop` | 不重播舊位置／舊 command；重新規劃會形成新 call |
| `engine_failed` | `unchanged` | 同上；候選丟棄，故障原因不能一律當參數錯 | `stop` | App 處理引擎、程序與輸出故障；不叫模型修基礎設施 |
| `save_failed` | `unchanged` | 權威保存層證明未發布；此表限回執已閉合或 binding 前 | `stop` | App 處理保存失敗；保留人工候選，不再延長已終局失敗 |
| `outcome_unknown` | `unknown` | 只適用第一層 | `reconcile_operation` | 不存在可跳過對帳的第二層出口 |
| `operation_conflict` | `unchanged` | 必帶原 operation；原 terminal receipt `confirmed` | `stop` | 拒絕此次 payload，保留並可回查原結果；衝突回覆本身不覆寫 receipt |
| `busy` | `unchanged` | `operation_ref=null`、`unconfirmed` | `wait` 或 `stop` | App 等既有工作閉合或结束本次請求；不讓模型忙迴圈重送 |

所有確定 error 均有有界 `error`，`actual_changes=null`；成功的 `error=null` 且 actual changes 由 App 產生。六種確定 failure、`busy` 與 `outcome_unknown` 的 `result_revision_ref`／`change_ref` 必為 null，不能把候選版或失敗回執偽裝成已發布變更；確定失敗由 `operation_ref` 回查即可。只有 `operation_conflict` 可以攜帶已查得的原結果 refs 作定位，mapper 必須證明其屬原 receipt，而非本次衝突 payload 的效果。此 matrix 不替代原 schema 對各成功 reference 的要求。跨欄位相等、refs 歸屬、真正提交及 receipt 真實性仍由 producer／保存層驗證。

### 2.3 同 DTO、不同執行者；結果重播不能變形

`JdManualSaveResult` 與 `JdEditResult` 沿同一 `JdWriteResult`。`correct_arguments` 是可行動錯誤分類，人工介面不要求員工修改 JSON；可提示可讀原因並保留原候選，無法在當前人工流程修正時選 `stop`。actor 來自已知呼叫路徑，不要求模型回填。

terminal receipt 已保存後，同 operation／digest 返回原結果，包含原 `next_action`；不得因現在 busy、額度耗盡或 UI 模式而改寫 immutable receipt。當前 runtime 的取消、無進展或額度限制仍可停止後續步驟，這是執行 gate，不是把 durable result 改成另一個結果。回執尚未存在時的 provisional `reconcile_operation` 回覆，不等於已保存 terminal receipt。

修參數或重讀後重新規劃是**新的模型 call／新的意圖**，必須先閉合原操作。HTTP 傳輸重試與顯式 resume 則保留原 identity 和 exact payload。App 不因錯誤代碼帶有 transient 含義，就重跑一整輪模型或配置新的寫入 identity。

## 3. ER02：固定 typed read failure 出口

`JdReadFailure` 增加 `status=read_failed`，`JdChangeReadFailure` 繼續引用同一型別；`jd_read`、`jd_change_read` 及其同型人工回讀入口一致。讀取沒有 operation，`document_effect=unchanged`、`receipt_durability=unconfirmed` 表示這次讀取未產生文件寫入／沒有持久 write receipt，**不代表有待對帳寫入，也不代表文件沒有被其他已知流程改過。**

| read failure `status` | 允許的 `next_action` | 判斷責任 |
|---|---|---|
| `invalid_input` | `correct_arguments` 或 `stop` | 輸入形狀、參數或 reference 用法有可識別錯誤 |
| `unsupported_content` | `stop` | 無法讀取既存內容／profile；不可叫模型改輸入 shape 修復保存資料 |
| `target_missing` | `reread_current` 或 `stop` | 已權威確認目標不存在或不可用；歷史查詢不能偷偷改回 current 作為答案 |
| `busy` | `wait` 或 `stop` | 真正 admission／讀取資源忙碌，由 App 控制等待或停止 |
| `read_failed` | `stop` | 讀取依賴暫不可用、查詢逾時、傳輸失敗或可分類的資料解碼故障；此次不自動重試 |

`read_failed` 由 read adapter 在已知例外邊界建立，error 使用既有 `JdToolErrorDetail`，`command_index=null`；message 誠實說明未取得所請內容，不洩漏 DSN、SQL 參數、堆疊或原始敏感內容。具體 error code 由 adapter 固定為可觀察分類，不把 `read_failed` 當成所有例外的 catch-all。缺少資料與資料庫無法回答分開；程序 bug／協定錯誤須保留診斷並走既有 runtime failure，取消、預算耗盡或缺少有效 tool call identity 也不得被包成模型可修的 read error。

結果仍經既有 harness 以原 tool call ID 回傳。若調用已取消或框架無法配對結果，沿原 runtime closure 處理，不能虛構 ID／內容。之後員工顯式重讀或重開可觸發一次新的唯讀請求；當前 `stop` 不等於永久禁止閱讀。

`jd_change_read` 若仍可提供完整 immutable 前後內容，只是沒有可靠高亮／native operations，應走成功＋`presentation_limitations`，不誤報 `read_failed`，也不捏造精細差異。當確切歷史內容不可取得時則誠實失敗，不以 current 代替。

## 4. ER03：執行、停止及逾時由 App 負責

### 4.1 v1 attempt 與時間策略

一次 attempt 是一個已明示階段的執行，並非一條 SQL、一次讀 socket，亦非整個 Agent turn。每個階段的 deadline 使用 monotonic elapsed time，不能在每次 I/O 或收到部分資料時重置。所有時間配置必須是正的有限值。

| 階段 | v1 次數／控制預算 | 耗盡或失敗後 |
|---|---|---|
| Node transform request | 1 次；`node_request_timeout_seconds=30`，涵蓋啟動等待、完整 stdin／stdout、轉換及回應驗證的控制預算 | 進入程序清理，不再自動執行 Node。只在完整驗證成功後才有可交保存層的候選 |
| Node cleanup | terminate 後最多等待 5 秒；必要時 kill，另等 reap 最多 5 秒 | 未證明退出就維持 writer 未靜止，不能因逾時宣稱取消成功或解除 gate；UI 改為可恢復失敗／待確認呈現 |
| SQL 發布 attempt | 完整短交易最多 1 次；`jd_sql_attempt_timeout_seconds=30` | 不自動重跑 transaction／Node／模型。已證明 abort 才能回確定失敗；COMMIT 結果不明改走原 operation 對帳 |
| terminal failure receipt 持久化 | 必要時另做 1 次、不發布文件的閉合交易；同 SQL attempt 30 秒預算 | 這不是重送文件。失敗則保持原 error／`unchanged`，receipt `unconfirmed`，先恢復原 operation |
| 每次顯式 receipt reconcile | 最多 1 次唯讀 lookup，0 自動 polling；套用同一 storage attempt 30 秒控制預算 | 查無不證明未執行；查詢失敗也不猜成終局。未閉合時維持恢復入口與 gate，等待另次顯式 resume／重開 |
| 一般 JD read | 每次明示讀取 1 次，0 自動 retry；DB 讀取受同一 storage attempt 預算約束 | 可分類基礎設施失敗回 `read_failed + stop`；不能反覆叫模型讀來繞過預算 |

已存在的 [api.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/api.py) 129–130 行使用 `connect_timeout=5`、`statement_timeout=10000` ms、`lock_timeout=5000` ms。本案沿用這些內層限制，新增上表 App 控制預算；不默認既有 DSN 已實作總 deadline。

**Node 限制：**Python 官方說明有些 OS process creation 無法被 timeout 立即中斷。因此由 spawn 前起算的 30 秒是監督預算，不能保證 OS 卡在 spawn 時 30 秒內返回；spawn 返回後若預算已耗盡，應立即清理。Windows 的強制停止行為與 POSIX signals 不同，不能只因呼叫 `terminate`／`kill` 就宣稱 graceful shutdown 或已退出；必須確認子程序已回收。worker quiescence 要由實際 worker／process 狀態證明。

**SQL 限制：**`statement_timeout` 限一條 statement，`lock_timeout` 限等鎖，不等於整個 transaction 或 App request 的總時間。App 每次開連線／發 statement 前檢查剩餘預算，所設內層 timeout 不得超過可用剩餘值，並監督目前 await 的取消；預算耗盡後不能繼續送普通 SQL。必要的 rollback／連線清理與結果對帳另據真實狀態收尾，不能把 request cancellation 當作 server 已 rollback。Task 2 必須驗證這些取消／清理接點，文檔選定 deadline 不代表已具硬性 end-to-end 時限。

Node、發布交易、失敗回執閉合及顯式對帳是不同階段，可能各自消耗預算；**不能宣稱整個保存請求最多 30 秒**。觀測須分列各階段 elapsed／attempts、取消／清理結果及總 elapsed；回應等到停止後，也不能以時間耗盡取代文件效果的證據。

### 4.2 SQL abort、unknown 與顯式恢復

PG16 文件要求若要重試 serialization failure，需重試完整 transaction，包含決定 SQL／值的邏輯；deadlock 或部分 unique／exclusion violation 的可重試性亦須按原因判斷。本案保持 Read Committed＋同文件 head 鎖，**v1 不自動重試 `40001`、`40P01`、`23505` 或 `23P01`**。SQLSTATE 不等於安全重送授權，也不能用 statement 局部重跑代替完整交易。

已知失敗只在權威保存層能證明本 attempt 沒有發布時成立；COMMIT 已送出而連線中斷，先保留 `outcome_unknown`。保存 transaction 內的 head、revision 與成功 receipt 同一 ACID 邊界；引擎 disposable editor 中的部分改動不屬 durable partial success。本案不提供 `partial_committed`，也不能從供應商通用 tool error flag 推得零副作用。

顯式 resume／重開先讀同 operation 的 receipt。已有任何 terminal receipt（成功、no-change、確定失敗）即返回原結果，不再執行；同 identity 不同 digest 一律 conflict。查無 receipt 仍不足以重送。只有既有 storage ownership／recovery 接點同時證明原 writer 已停止、原交易確實未提交、原 exact request／digest 可恢復且沒有 terminal receipt，才能在另次顯式觸發中走已定義的受控恢復；不加泛用「unknown 工具重跑」白名單，也不將恢復變成新模型 call。

這不要求持久 operation row 充當 running 狀態表：checkpointed binding／writer owner 管 issued 未閉合狀態；DB operation row 只收已確認 terminal receipt。unknown 或衝突回覆不能覆寫既有 receipt。對應 FK、唯一 producing revision 及同列真實性由 [DB 關係稽核](2026-09-10-jd-storage-relations-audit.md)及[同輪 DB closure](2026-09-10-jd-storage-contract-closure.md)固定。

### 4.3 SDK 與模型額度不代替上述策略

OpenAI／Anthropic Python SDK 的現行 transport 文件均說明特定連線與 HTTP 錯誤預設自動 retry 2 次，且可配置。這是該 SDK HTTP 請求的契約，不能推得本案 LangChain／OpenRouter wrapper 的實際 retry 設定，也不等於重新執行 JD tool、Node 或 SQL。既有 `conversation.py` 已避免外加一層 HTTP retry；沿用此責任邊界，接線時核對實際 adapter 配置與觀測值，避免 SDK retry 再乘整個 Agent run 重啟。

模型可以修可修的參數，但受既有 invalid JSON、模型／工具額度、取消及無進展限制；本文不新增或改寫那組額度。供應商對模型「通常會再嘗試」的行為描述不是可靠停止機制，`next_action` 也不是無限循環許可。錯誤結果須告知具體可做的下一步；遇到保存／讀取基礎設施失敗，不能用「修參數再試」代替 App 恢復。

### 4.4 UI 不永久轉圈，writer gate 不提早解除

到達控制預算後停止無止境 spinner，顯示真實狀態與有限恢復入口。若文件效果未知，可說明「保存結果待確認，可重新確認」；若已知未改但回執未閉合，則說明「此次未保存完成，正在等待恢復確認」。兩者都保留閱讀與必要診斷／人工恢復入口，但不把按鈕做成偷偷重送新文件。

解除手編限制的條件是 **writer quiescent、所有已發配 JD operation 閉合、turn closure 完成**。未閉合保持 gate，但不要求 UI 永遠忙碌；已閉合的 `save_failed` 不因想再試而延長既有 run。人工候選按既有 request key／exact payload 保存；終局失敗後可開始明確的新提交，unknown 時則不能換 key 重送。取消後已提交的內容也不能由模型 final 失敗自行回滾。

## 5. 必要驗收與停止研究條件

| 驗收 | 可證偽的必要結果 |
|---|---|
| ER01 schema matrix | 每個 status 的允許／禁止 `next_action` 均有離線反例；拒絕 `save_failed + correct_arguments`、`stale_base + continue`、bound＋unconfirmed＋`stop`、busy 帶 operation、conflict 不帶 operation、無 operation 卻 confirmed |
| ER01 producer／runtime | known-unchanged＋unconfirmed 走 reconcile 而不改 effect；已持久 terminal result 重播完全一致；模型／UI 無法另配 identity 繞過未閉合操作 |
| ER02 typed read | 資料庫 unavailable／逾時不冒充 target missing；unsupported existing content 不叫模型修 shape；兩 read 工具一致；取消／缺 call identity 不虛構 ToolMessage；只有高亮缺失仍可讀完整前後 |
| ER03 Node | 用完整 canonical r2 及最大合法操作批次記錄 bytes、startup／transform／validation elapsed；注入 hang、stdout 截斷、超界、取消，證明不自動重跑，正確清理且不早解 gate |
| ER03 SQL | 測 head 鎖等待、statement timeout、總 budget、已知 abort、COMMIT 回覆遺失及 failure receipt 保存失敗；核對沒有自動重送或重跑 Node／模型，未知結果只以同 identity 對帳 |
| ER03 receipt／UI | 每次恢復只做一次 lookup；查無不假報失敗；停止 spinner 而保留可明示恢復的入口；終局失敗返回原 receipt，沒有同 key 後來轉成功 |
| 多層預算 | 觀測 SDK HTTP attempts、工具 call、Node attempts、發布 transaction、receipt closure／lookup 分開計數；單階段 timeout 不冒充整個請求耗時上限 |

本單位完成的是推薦收斂與文檔證據；主工作單位的離線 schema 結果另記，不在此預先宣稱通過。runtime、真 SQL cancel／COMMIT 中斷、Node 完整批次 deadline 及 UI gate 必須按原 Task 2／3／6 接線驗證。剩餘不確定性可由這些有界驗收回答，不需再廣搜或額外呼叫付費模型。

## 6. 精確官方來源、版本與不能推出的主張

以下均於 2026-09-10 核對／沿用同日已讀官方資料。滾動 API／SDK 文件未固定 release 的地方明列，不把查閱日當軟體版號；此處沒有採用或升級新依賴。

| 官方來源與版本 | 直接支持的事實 | 本案映射／限制 |
|---|---|---|
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)，現行 Responses 指引，頁面無固定 release | App 執行模型要求的工具，結果以 call ID 配對；output 可表示錯誤或 JSON 等自訂內容 | 支持結果由 App 建立；沒有規定本案 status／next_action／SQL retry |
| [OpenAI apply patch：Handling common errors](https://developers.openai.com/api/docs/guides/tools-apply-patch#handling-common-errors)，現行官方指南 | failed output 應提供有用原因，模型可據此調整後續 patch；整合端需自行決定原子範圍 | 支持修參數與執行責任分開；failed 不保證其他操作都未寫入 |
| [Anthropic handle tool calls：is_error](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)，現行 Messages client tools | App 用匹配 tool_use_id 的 tool_result 回結果／錯誤，錯誤可提供原因與下一步 | 支持既有 harness 原生結果通道；不證明 receipt、DB 原子性或安全自動重播 |
| [AWS Well-Architected REL05：limit retries](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_limit_retries.html)，現行滾動指引 | 限制 retry／elapsed，避免多層放大；區分可重試錯誤與非冪等副作用，適用時使用退避／jitter，驗證故障情境 | 支持明定 owner 與預算。1 attempt、0 replay 和 30／5／5 秒是本案起始配置，不是 AWS 數值 |
| [AWS Builders’ Library：idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，2021 原文、現行官方仍公開引用 | 同意圖保留 client token，同 token 不同參數拒絕；token 記錄與副作用須在一致持久邊界，重試回語意等價結果 | 本案 exact digest＋immutable terminal receipt 較一般語意等價契約更嚴；沒有借此要求通用 retry service |
| [AWS Prescriptive Guidance：retry with backoff](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html)，現行指南 | transient、idempotency、可限制的退避與永久錯誤應分開處理 | 支持未來若增加 retry 的判斷；不是現在自動重送的授權 |
| [OpenAI Python SDK retries](https://github.com/openai/openai-python#retries)、[Anthropic Python SDK retries](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python#retries)，現行公開文件，本文未固定安裝 release | 特定 connection／HTTP 408、409、429、5xx 錯誤預設 retry 2 次，可配置 max_retries | 只證 transport 預設；本案實際 provider wrapper 另核對，不等於 JD 操作可重播 |
| [PostgreSQL 16 §13.5](https://www.postgresql.org/docs/16/mvcc-serialization-failure-handling.html)、[§13.3 locks](https://www.postgresql.org/docs/16/explicit-locking.html) | 若 retry 要重跑完整 transaction；40001、40P01 與部分 constraint violation 的語意不同，deadlock 會 abort，鎖順序可降低風險 | v1 零自動重跑是保守本案政策；不把所有 SQLSTATE 包成通用 retryable |
| [PostgreSQL 16 statement_timeout](https://www.postgresql.org/docs/16/runtime-config-client.html#GUC-STATEMENT-TIMEOUT)，相鄰 lock_timeout 條目 | statement 與等鎖有各自 timeout；它們的界線不是整個應用程式請求 | App 30 秒總控制預算是另需接線的能力，不能假裝 DSN 已完成 |
| [Python 3.12 subprocess](https://docs.python.org/3.12/library/subprocess.html#subprocess.Popen.communicate)，查閱時 3.12.14 文件 | timeout 與 kill／wait／drain 有明確責任；communicate timeout 不自動殺程序，初始啟動未必能即時中斷 | deadline 和真正 quiescence 必須分開驗；不能假造跨 OS 絕對牆鐘保證 |

官方共同支持可歸因錯誤、App 執行責任、明確副作用與有限恢復；**沒有官方資料證明本案這套 JD DTO、兩層 matrix、資料表或秒數是跨廠共識。**它們是針對既有工作稿、單 writer、原子保存及同 call 正確回填所作的 Caliburn mapping。
