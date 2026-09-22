# RS-4：前景 AI 與人工共用文件執行權前置

查閱日期：2026-09-13。Topic：JD-R002／RS-4；這是可施工接點與反例清單，尚非 AI 執行／取消／重啟通過報告。範圍是新 relational App，不接回舊顧問程式、不建立第二份聊天、Memory 或 JD 權威。本次唯讀檢查原碼與官方文件，沒有啟動宿主、連接資料庫或呼叫模型。

上位依據：[目前決策](../../../current-decisions.md)、[人工 runtime](../../2026-09-13-jd-manual-runtime-slice.md)、[保存契約](../../2026-09-12-jd-relational-schema-and-write-contract.md)、[取消與恢復](../../2026-09-12-jd-history-and-recovery-design.md)、[整輪 JD 撤回](../../2026-09-12-jd-ai-turn-undo-design.md)。模型上下文與串流完成證據沿[既有前置](../2026-09-13-jd-consultant-context-preflight.md)，不在本稿重開品牌比較。

## 1. 結論與適用版本

**保留同一個 `ManualRuntime` 作文件執行權擁有者，新增整輪前景 AI reservation。**類名可在後續責任整理時調整，不為改名複製 runtime。人工保存、文件 metadata 修改及 AI 開始，必須在同一文件的 `_Slot.lock` 內核同一份 owner；純訪談回合也佔用 reservation。不同文件不因某文件等待模型或 SQL 而共用長時間 I/O 鎖。

AI coordinator 管原生 graph 執行與回合閉合；runtime 管 reservation、真實 Future、停止要求及 storage 寫入資格。二者不是兩套鎖。使用原生、分開且有界的 Agent／SQL executor，避免 Agent 佔滿 executor 後同步等待同池 SQL 的死鎖；executor 分開不代表可以各自解除文件 reservation。

| 核對來源 | 官方事實／實際原碼 | 本案映射與限制 |
|---|---|---|
| [Python 3.12 futures](https://docs.python.org/3.12/library/concurrent.futures.html)，穩定、PSF-2.0；示例另有 0BSD | running callable 不能由 `Future.cancel()` 取消；`result(timeout)` 只結束等待；done callback 可能立即同步執行；同池相依等待可能死鎖 | Event 表達停止要求；等待真 Future 及 checkpoint 收尾，不用 timeout 宣告死亡。Future 掛接須在 reservation 的同一受控提交內完成 |
| [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)，核 installed 1.2.11／checkpoint 4.2.0，MIT | `sync` 在下一步前保存；`update_state` 建新 checkpoint，`as_node` 影響路由；replay 會重執行後續節點及模型／外部呼叫 | binding 由原生 `after_model` node 更新，graph 使用 `durability="sync"`。不能在 active child 旁改 root 或靠 replay 解未知寫入 |
| installed LangChain 1.4.0 `agents/factory.py:1599`；LangGraph 1.2.11 `prebuilt/tool_node.py:792`，MIT | `after_model` 是獨立 graph node；ToolNode 原生同步 executor／非同步 gather，注入 ToolRuntime 的 state、context、call ID | 採既有中介層接點，業務工具不建立 Agent loop。不能假設 tool 在最外層 Agent Future 的原執行緒執行 |

以上支持的是執行／保存邊界；以下 reservation 方法名及 descriptor 欄位是本案最小映射，不稱為供應商指定介面。精確依賴與來源沿[版本附件](../jd-relational-context/adapter-versions.json)。

## 2. 現況會阻擋或漏接之處

| 目前函式／型別 | 必須保留的正確行為 | 本輪要補的接點 |
|---|---|---|
| `manual_runtime._Slot`、`submit`、`update_catalog` | 同文件人工 entry、catalog token 排他；registry 只碰記憶體狀態 | 加 foreground entry，人工／metadata 查同一欄；不可在 AI 尚未呼叫 JD 工具時放行 |
| `ManualRuntime.submit` | 原 immutable receipt lookup 先於新的 busy／admission 判定 | 已成功的原人工請求仍可查回；只有新的寫入需拒绝 AI busy，不把讀回原結果當新寫入 |
| `ManualRuntime.require_bound`／`require_stopped` | storage 執行和 failure-only reconcile 都核實際 owner | 新增受 reservation 約束的 AI 分支；原 `origin="manual"` 檢查不鬆綁成任意 AI 身分即可通過 |
| `DocumentCheckpoints.read`／`_checked_identity` | active root／child 的 next、tasks、interrupts 拒絕；manual descriptor 只收 manual | 新增唯讀 AI root／child 觀察，不把 AI operation 塞進 `jd_manual_pending`；manual 的忙碌檢查繼續有效 |
| `DocumentCheckpoints._update` | idle manual `update_state(..., as_node="consultant")` 加 exact readback | **不可拿來保存 active AI binding 或工具結果**。人工 callback 不應在原生 child 還在寫入時改同一 root |
| `ManualRuntime.status`／`ManualService.status` | 未知保存或 checkpoint 錯誤仍 blocked | AI 純訪談可 `running=true, write_blocked=true, operation_id=null`；已有 DTO 允許，不捏造人工 operation ID |
| `finish_startup` | 先 host proof，再全 catalog 掃描，包含封存文件；未知不推定可寫 | 讀到 AI descriptor／native child pending 時至少保留 `recovery_required`。本輪未完成的跨程序恢復不可當成 manual descriptor 自動消除 |
| `ManualRuntime.close`／`ManualHost.close` | admission 先關；實際工作與 callback 完成前不關 Saver／engine | 納入 AI Future、每次 SQL Future 和回合閉合；單獨 Agent Future.done 不夠；超時仍保留資源與 owner |

`JdStorage.execute`、`lookup`、`reconcile_stopped` 已有相同業務規則和 SQL receipt；`AdmittedIdentity`／`BoundEdit` 已接受 AI origin 與 run identity。沒有理由複製 AI 保存 service 或加另一張 operation 表。SQL row lock 不跨整轮模型等待持有。

## 3. 最小共用公 API 候選

以下是內部能力，不是 HTTP DTO／模型參數。由主代理按實作收斂命名；不需要先公布分離的 reserve／attach／release 三步，避免漏掛 Future 的空窗。

| 方法 | 責任與邊界 |
|---|---|
| `start_foreground(run_identity, run_callable) -> ForegroundHandle` | 在同一 doc slot 核 accepting／host／startup／metadata 未封存／沒有人工與 catalog owner／沒有未閉合 native 工作；建立 opaque token，runtime 自己 submit 原生 Agent Future 並掛接 callback。worker 在取得自家 slot 核驗前不能進 graph；失敗後不留下無法追蹤的已啟動工作 |
| `submit_foreground(reservation, bound_intent) -> WriterHandle` | 只接受目前 run、document、同一完整 persisted binding 的操作；原 receipt 查回優先。每個 operation identity 至多一個實際 SQL Future；同 ID 改意圖拒絕。使用 SQL pool；不呼叫 manual checkpoints.admit／close |
| `request_foreground_stop(document_id, run_id) -> status` | 精確比對目前 run 後 set Event，不立即 release、不篡改 receipt；重複取消同 run 可觀察原停止狀態，不能晚到取消下一輪 |
| `foreground_status(document_id, run_id)`／handle `wait(timeout)` | 回觀察結果；等待超時不能取消實際寫入。現有 document status 同時反映整輪阻擋，Web 不需自己拼兩套 gate |

不用公用 `release_foreground(bool)` 或 `stopped=True`。**清除 reservation 是內部完成 callback**：核該 generation 的 run Future 已停止、所有已派發 SQL Future 及其結果收尾已完成、coordinator 提供的持久回合閉合能以同一 run／checkpoint exact readback 核實，再清 slot。coordinator 任意丟出 `closed=True` 不是持久證明。

`require_bound` 的 AI 分支要核：同 doc slot 的 opaque token、run ID、exact `AdmittedIdentity`、本次實際 SQL Future 與 execution context。ContextVar 只在真 SQL callable 執行範圍設／重設；copy context、晚回 callback、相同字串 run ID 或跨 thread 重用，不能取代 live token／Future 檢查。ToolRuntime 提供可信 App context；模型不填 run／operation／版本身分。

**close／取消不能撤銷正在交易中的原意圖，卻先當作沒有寫入。**停止要求阻擋下一個新模型／新 operation，已派發 SQL 仍等待 commit／rollback／未知結果對帳。若已 admitted 尚未派發，取消後禁止首次寫入，沿其原 identity 確認未啟動後 failure-only 閉合；若根本沒有 binding，不造一筆假的失敗 operation。

catalog 的 create 使用獨立 request-key slot，可和其他文件 AI 並行，但仍受 startup／host close gate。既有文件 rename／archive／restore 的 metadata 更新，使用該文件同一 reservation；不新增全域模型鎖。

## 4. durable root 與 child 各保存什麼

建議 root 新增一個有格式版本的 **目前／最近 AI 回合 descriptor**，而不是一張 AI 草稿表或另一份聊天紀錄：

| 欄位 | 必要理由 |
|---|---|
| `format_version` | 嚴格解碼與升版拒絕；不是動態任意 metadata |
| `dataset_id`、`document_id` | 防舊資料集請求及跨文件串接；thread_id 仍須一致 |
| `run_id` | App 配發的穩定回合身分；可直接作該輪 HumanMessage ID，無須再存一個同義欄位 |
| `input_digest` | 同 run ID 的原送出意圖一致性；canonical 原問答仍在 messages，不在 descriptor 複製全文 |
| `status` | 有界 `active / completed / cancelled / failed`；terminal 字串仍須與 exact root snapshot／未解 bindings 核對，單憑字串不解除執行權 |

不用把某輪 `jd_model_view`／notice 基準當 JD 撤回起點。整輪撤回 S／E 已規劃從具 `ai_run_id` 的永久 SQL receipts 與 revision parent 鏈推導；本 slice 不加起終稿副本。run descriptor 不是所有歷史 run 的 API lookup 契約；若後續 HTTP 需要查很早以前的同 key，須從保留的原 canonical messages／native history 核原意圖，不能只看 last descriptor 就當新 key。

在 idle root admission 後，**在進入 consultant 前**持久化 run descriptor 與該輪原 HumanMessage，使用原生 graph input／node 路徑及 sync durability。新 caller 不能在持久 admission 回覆不明時重派一次相同 graph；先用原 run 讀回。若連 descriptor 是否已保存都未知，reservation 留下且不呼叫模型。

每個 JD 工具 binding 保存在 **child state**：原 `AdmittedIdentity` ＋實際 assistant message ID／tool-call ID 對應，及工具執行所需的原參數／基準材料。原參數是否可從同一 checkpoint 的 canonical AIMessage 取得，由 binding 作者維持單一來源；不得模型執行後重配 operation ID。`after_model` 是 native node，sync checkpoint 成功後才可進 ToolNode；result 回傳原 ToolMessage／Command，使真正結果與 binding 狀態在同一步保存。不在 active child 外另叫 root.update_state。

正常 child 結束後由 root 閉合路徑確認 pending 為空、保存 terminal descriptor，再由 runtime callback exact readback。正在執行的 callback 或已停止但還有 unresolved native child，不能偽稱 `as_node="consultant"` 完成而直接抹掉 pending 工作。原始完整回覆與 response-backed notice 沿既有 middleware 保存；取消、缺終端或 partial stream 不得推定已讀。

## 5. 取消、故障及重啟的有限閉合

1. **合作式取消：**stop Event 在下一模型呼叫及下一具名操作前檢查。已完成的模型／tool 訊息保留，以框架的有限停止路由結束本輪；不把取消當成整輪 JD 還原。
2. **模型 I/O 尚在執行：**可要求停止後續工作，但只有實際呼叫／response cleanup 結束才是本程序停止證據。SDK timeout、HTTP 斷線、Future 等待超時皆不能證明 SQL callable 死亡；close 等不到則不釋放。
3. **SQL 結果未知：**保留原 binding。未停止不能呼叫 `reconcile_stopped`；已停止後沿原 identity 查回或 failure-only 收尾，從不重跑業務 mutation。已成功第一項、第二項取消／失敗，第一項仍是 committed。
4. **原結果確定但 Saver 結果不明：**SQL receipt 仍是確認結果，document 繼續 blocked。只讀核同一原 checkpoint／binding，不能改口保存失敗或發新 operation。單一回覆遺失不要求重跑模型。
5. **graph 例外留下 native child 工作：**先保留 `recovery_required`。若本輪尚未驗證「原 child 訊息與 binding 的恢復／對帳／無模型閉合」流程，就停止在這個安全出口；不能略過 child 強寫 root terminal，亦不能用新 input 覆蓋未解 run。
6. **新程序：**沿既有 HostLease 真 OS 擁有權與前程序群結束證據；沒有 local Future 不等於已停止。startup 唯讀分辨 manual／AI／未知 descriptor，AI unresolved 的文件不能手改、改 metadata 或啟新 AI。沒有證據不 `invoke(None)` 或 replay；新程序恢復實驗可以下個有界單位完成，文件不可標可用。

本輪不需自造跨服務 recovery engine。最低完成條件是合作取消能收尾、固定故障可如實保留阻擋；要解除故障阻擋則必須另有原 identity／native checkpoint／真停止證據。若沿既有 startup 全域停止門閘保守阻擋全部寫入，須如實記錄可用性限制；不得悄悄跳過未解文件後仍把該文件顯示為可寫。

## 6. 必須先失敗再通過的反例

| ID | 情境與判定 |
|---|---|
| AO-01 | AI 純訪談尚無 JD operation；同 doc manual 新寫／archive／另一 AI 均拒絕。不同 doc 的人工保存可完成 |
| AO-02 | start 與 close 同時發生；不得出現 close 回成功後才啟動 Agent／Saver。executor.submit 拋錯、done callback 立即執行仍保留可核狀態 |
| AO-03 | 1 個 Agent worker 等待 1 個 SQL worker；可完成，不因同池 nested wait 卡死；測試用屏障，不靠 sleep 推定 |
| AO-04 | 相同 operation 重入只查回／共用原 Future；同 ID 改 payload／base 拒絕；AI reservation 存在仍可查人工原 receipt |
| AO-05 | after_model checkpoint 寫入前故障／写成功回覆遺失：工具 SQL 都未執行；後者原 child binding 可查、root 仍 pending，不呼叫 root manual update |
| AO-06 | AI 第一項 committed；第二項在 SQL／commit ACK 不明時取消；等待 Future 不會提前清 owner，後來只對帳原 identity，第一項保留 |
| AO-07 | 模型缺 message_stop、API error 或 callback 故障：不產生假的完整回覆／新 notice 基準；若 child 未閉合，manual／catalog 仍 blocked |
| AO-08 | 原 SQL 完成、tool／root checkpoint 保存失敗；結果仍 confirmed，沒有新寫入與 replay；恢復不得丟掉已保存的完整 model／tool 訊息 |
| AO-09 | 捕获的 token／ContextVar 在別 thread、原 Future 結束後、下一輪 reuse；storage authority 全拒絕。晚取消 run A 不影響 run B |
| AO-10 | close 先看到 Agent Future.done，但 SQL Future 或 callback／checkpoint 仍未完；close 不成功且不關 Saver／engine |
| AO-11 | 新專用 host 讀到 root active／child binding 或 malformed descriptor；真 previous-host proof 也不能直接當已閉合，沒有 provider／mutation replay，文件仍 blocked |
| AO-12 | 零 JD 保存的正常 AI 回合收尾；解除手改，不造 operation／revision；原問答與完整回應可在原 root 查回 |

已有 [native admission 探針](admission_checkpoint_probe.py)可檢查 after_model／sync／ToolNode 順序，但它是固定模型、原生 InMemorySaver、零 SQL 的合成驗證，不代替本表的真 Future、真 PostgreSQL 或新宿主案例。本稿只完成接點分析；後續結果按各自證據回寫。
