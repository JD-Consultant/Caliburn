# AI 職務顧問 runtime 設計

- Durable authority 決策：[ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)
- 共用目前 JD 與語意核准：[ADR 0069](../adr/0069-shared-current-jd-working-copy-and-semantic-approval.md)；它取代 ADR 0066／0067 的雙主編輯面、`defer`、review blocker 與 direct-edit conflict 部分，保留 Store-backed workspace、derived review 與 approved-only export
- 實作：`apps/api/app/consultant`、`apps/api/app/adapters/langgraph`、`apps/api/app/adapters/openrouter/langchain.py`

現行 production runtime 是一位 AI 職務分析顧問：它以目前焦點帶領訪談、吸收背景線索，並在員工與 AI 共用的一份持久「目前 JD」中持續整理 Duty、Task 與 O／P／K／S。底層另保留只讀的核准基線作部分接受、拒絕還原與匯出 authority；員工只操作目前 JD，AI 差異仍須員工接受、修改後接受或拒絕才會進入核准基線。

## 產品與持久化資料流

```text
employee source／natural correction ───────▶ LangGraph PostgreSQL Store
                                                    │
                                                    v
LangChain／Deep Agents agent ── six VFS Tools ──▶ StoreBackend /workspace
             │                                      │
             │                                      v
             │                         automatic JD／Evidence validation
             │                                      │
             v                                      v
 concise consultant reply              validated current_document
                                                    │
approved_document in Saver ───────────▶ derived semantic /review
                                                    │
employee accept／edit-accept／reject ────────────────┤
employee direct current-document edit ──────────────┘
                         │
                         v
        deterministic server-derived authority seam
                         │
                         v
          approved_document ──▶ export
```

目前 JD 跨員工訊息、provider failure、頁面關閉與 process restart 保留。模型 final 只交付顧問回覆、理解／訪談工作／Gap、下一題或必要澄清與足夠性判斷；workspace revision、digest、review identity、action handle 與 Evidence offset 都由 application 從真實持久狀態建立，不要求模型回傳。

## Saver、Store 與 catalog 分工

每項持久事實只有一個 owner：

| 事實 | 唯一 owner |
|---|---|
| 文件 ID、library title、thread pointer、tombstone | Alembic 管理的 `consultant_documents` 最小 catalog |
| 核准職務說明書、可修訂理解、訪談工作、Gap、可見顧問結果、必要澄清、run／command receipt 與 source reference | LangGraph `AsyncPostgresSaver` checkpoint |
| 員工逐字來源、direct-edit 文字、來源更正 lineage | LangGraph `AsyncPostgresStore` 的 document-scoped source namespace |
| 唯一 active current working document 的 canonical resources | Deep Agents `StoreBackend`，固定 namespace `("caliburn", "consultant", <document_id>, "workspace")` |
| 目前 JD manifest、可恢復 authority plan、reject decision memory | 同一 LangGraph Store 的獨立 document-scoped metadata／decision namespaces |
| `/approved` 與 `/review` | 即時唯讀 projection；不另存第二份核准文件或 durable review copy |

Saver 負責可恢復的顧問 thread 與文件 authority；Store 負責跨 execution 仍需由 agent 與 employee command 共同讀寫的資料。Saver 不保存 workspace files，Store 不保存第二份核准職務說明書。互動 agent loop 也不建立自己的 checkpointer 或第二個 Store。

fresh root migration `0018_consultant_runtime_root` 只建立最小 catalog；`npm run consultant-storage:setup` 由 LangGraph 官方 `.setup()` 建立 Saver／Store tables。Caliburn 不自建 workspace table、host filesystem mirror、Git repository 或 framework-state mirror。

## Storage 與 runtime safety

- Saver 使用 `JsonPlusSerializer(allowed_msgpack_modules=None, pickle_fallback=False)`；framework payload 不得退回任意 pickle。
- 官方 PostgreSQL connection factory 提供 `autocommit=True`、`prepare_threshold=0` 與 `dict_row`。Saver／Store `.setup()` 可重跑；catalog schema 仍只由 Alembic 管理。
- Windows 的 psycopg async connection 使用 Selector event loop；storage setup 與 live entrypoint 必須在建立 loop 前設定。
- 每個 HTTP authority command 都有 checkpoint-owned command receipt，綁 stable command ID、command kind 與 canonical payload hash。exact replay 可補完 crash reconciliation；同 key 換 payload 直接拒絕。
- document 刪除先 tombstone catalog，再清除 checkpoint thread 與該 document 的 Store namespaces。namespace 只能由 application-issued UUID 組成，不接受使用者自由字串。

## 五個 VFS namespace

模型只看見一個 document-scoped `CompositeBackend`，其中五個目的 namespace 的權限固定：

| Namespace | 內容 | 權限與來源 |
|---|---|---|
| `/skills/**` | 本輪 eligible 職務分析方法 | package-backed、唯讀；完整 `SKILL.md` 按需載入 |
| `/sources/**` | current 員工原話、metadata 與更正 lineage | Store-backed 唯讀 projection |
| `/approved/**` | 唯一核准職務說明書基線 | Saver checkpoint 的唯讀 projection |
| `/workspace/**` | 唯一持久 current working document；不是 export authority | `StoreBackend` 可讀寫；只有此 root 可被模型改動 |
| `/review/**` | approved ↔ workspace 的語意差異、狀態與 diagnostics | application 即時計算的唯讀 projection |

這五個 VFS namespace 是 model-facing 視圖，不代表五份可寫資料或五個產品生命週期。`/review` 不是模型撰寫的內容，也不是另一份 JD；`/approved` 與 `/review` 都不能透過 VFS 寫入。

## 六個 model-facing Tool

正式 surface 精確只有六個低階 filesystem Tool：

| Tool | 唯一目的 |
|---|---|
| `ls` | 列出 scoped VFS entries |
| `read_file` | 讀取一份 Skill、來源、核准／工作資源或 review projection |
| `grep` | 在允許的 VFS scope 做 literal text search |
| `write_file` | 在 `/workspace` 建立一份新的 canonical JSON resource |
| `edit_file` | 對 `/workspace` resource 做一次 exact unique replacement |
| `delete` | 刪除允許的 workspace entity resource；header 與 directory 不可刪 |

`document_id`、Store namespace、路徑權限、stable ID、revision 與 digest 都由 application 注入。沒有 Duty／Task／OPKS 專用 write Tool、shell、execute、任意 network、跨文件查詢、MCP catalog 或 Tool Search。拆分、合併、重組與重新歸類由一般 create／edit／delete 組合，再由 application 依語意相依性分組。

backend 只接受 canonical absolute POSIX path；`write_file` 是 create-only、`edit_file` 禁止 replace-all，同一 tool wave 的重疊 mutation path 會在任何 handler 執行前整波拒絕。互不重疊的 resource mutation 可由 framework 同波執行，完成後只驗證一次完整 after-state。

## 目前 JD 生命週期與自動驗證

每份 JD 第一版只有一個 active workspace。第一次開啟且 Store 尚無 workspace files 時，才從當下 approved JD seed；後續 turn、重試或重開都直接續編既有 Store bytes，不從 approved 重建覆蓋。若已存在 files 但 manifest 缺失，系統保留實際 files 並先標成 `unvalidated`。

manifest 是薄 metadata，只含 generation、canonical resource digest、approved baseline revision／digest、Evidence basis digest、validation status、短 diagnostics 與 handle→stable-ID registry；它不含第二份 JD JSON。每次讀取都以實際 Store bytes 重算 digest。bytes 與 manifest 不符時，實際 bytes 保留，manifest 降為 `unvalidated`，review 會 fail closed；下一個 agent model boundary 會重新驗證，rebase recovery 也會驗證自己的 after-state。

`WorkspaceValidationMiddleware` 在每個 model call 前讀取完整 Store after-state，因此一波 mutation 完成後、下一次模型推論前會自動執行：

1. canonical JSON／Pydantic parse 與允許的 resource shape；
2. document scope、handle／stable identity、Duty／Task／OPKS linkage 與完整 JD invariant；
3. current employee source、exact quote、occurrence、已載 Skill 與 claim-support 規則；
4. approved baseline、Evidence basis 與實際 resource digest 一致性；
5. rebase conflict 的 path-local diagnostics。

可由模型修復的錯誤以最多五筆短 diagnostics 放回下一次 context；模型若試圖在 invalid workspace 直接結束，middleware 可在同一受限 run 內要求一次 repair。invalid workspace 仍持久保存，讓下一輪可續修，但不產生可接受 review、不修改 approved，也不被 export。`conflicted` 表示 canonical document 仍可解析，但某些路徑有 Evidence 或 rebase 衝突；只有受影響 group 的 accept／edit-accept 被阻擋，安全旁支仍可訪談或審核。

## Derived semantic review

`/review` 與 API 的待審文件變更都由 application 以目前 approved JD、已驗證 workspace、manifest 與 decision metadata 即時計算；沒有另一份 durable review queue。semantic differ 忽略 JSON 格式與 key order，只比較職稱／工作描述、Duty、Task、排序、歸屬與 O／P／K／S 等職務語意。

每個 review group 包含 semantic before／after、Evidence anchor、read-set、dependency 與必要的 atomic subgroup。一般 dependency 只表示接受順序，不自動變成全有或全無；只有會造成非法中間態的結構變更才必須同組決策。員工介面呈現可理解的欄位與關係，不呈現 raw file diff、Tool JSON、VFS path、graph state 或 digest。

authority command 在 server 端綁定 exact approved revision、workspace generation、workspace resource digest、changeset ID、group digest 與所選 action IDs。任一重疊內容改動後，舊 command fail stale；不重疊差異會從新基線重新投影，仍可繼續決策。相同 idempotency key 只有在 canonical payload 相同時可 exact replay。

## 員工 authority 與可恢復提交

模型與 VFS 永遠沒有 approved write edge。員工有三種 review decision，另可直接編輯目前 JD：

- `accept`：驗證所選 action、dependency／atomic subgroup 與 exact review identity，套用到 prospective approved JD。
- `edit-and-accept`：先以員工提供的 after value 取代所選 action，再走相同 authority invariant；只有員工實際改寫的文字 delta 會成為 direct-edit employee source。
- `reject`：approved 不變；先保存 rejection reason 與 selected-action semantic／Evidence／boundary fingerprints，再把所選差異從 active workspace 撤回。無關的新員工訊息或 workspace 變動不會讓相同內容偷偷復活；只有該內容、相關 Evidence 或工作邊界實質改變時才形成新的可審語意。
- direct edit：員工以目前 JD 為 before-state 直接編輯，不需審自己的內容。server 依 exact workspace generation／digest 重新讀 before／after，自行推導 touched semantic components；touched 值同步成為 current 與 approved，重疊 AI 差異由員工值取代，無關 pending 完整保留。client 不提供可信 paths，stale 提交回 409 並保留瀏覽器輸入。

accept／edit-and-accept 與 direct edit 使用可恢復的持久 authority plan：

```text
persist exact decision + rebase plan in Store
    -> commit approved JD + command receipt in Saver checkpoint
    -> rebase Store workspace onto the new approved baseline
    -> validate actual Store bytes
    -> mark decision completed and remove the plan
```

Store file mutation 與 Saver checkpoint 不是同一筆資料庫 transaction，因此不能宣稱跨兩者的 ACID 原子性。若 process 在 approved checkpoint 成功後、workspace reconciliation 前中斷，`reopen` 或 exact replay 會以 command receipt、approved digest 與持久 plan 完成剩餘步驟；不會先撤回 workspace 差異再嘗試寫 approved。reject 先保存可重播 decision record 與 plan，再把該 group 的 current 值還原到 approved；direct edit 先保存 server-derived semantic delta plan、提交 touched approved 範圍，最後讓 current 收斂。export 始終只讀 Saver 中的 approved JD。

## Process-local document admission

同一 application process 以 document UUID 維護 admission state 與 `asyncio.Lock`：model run 開始時拒絕同文件已進場的 employee mutation；review／direct-edit route 從 preflight 起保留 employee admission，並拒絕與同文件 active model run 交錯。真正的 checkpoint／Store command seam 仍在 per-document lock 內執行；不同 document 不共享這把鎖，例外離開 context manager 後會釋放 admission。

這是本機單一操作者、單一 API process 的第一版保護，不是 distributed lock。現行實作沒有跨 process CAS、lease 或多 writer 協調，因此不得宣稱 multi-process／multi-instance safety。若未來要多 process 或多人同時編輯，必須另開 ADR 設計真正的 compare-and-set／lease 與衝突政策。

## 員工來源、精確 Evidence 與更正

員工回答先進 Store，再開始任何 model-bearing work：

1. 以 application-issued stable source ID、document scope 與原始文字 hash 寫成 `pending` immutable source；
2. 在 Saver checkpoint 加入 source reference、run receipt 與 correction lineage；
3. 將 Store source 標成 `committed`。crash window 由 exact replay 補完，其他新輸入在 reconciliation 完成前被擋住。

前後空白、換行與 Unicode code point 都按原文處理，不 trim、不 normalize、不 fuzzy match。模型在 workspace Evidence 只填 model-safe source handle、逐字 quote、occurrence 與實際載入的 Skill IDs；quote 唯一時 workspace 值為 `null`，重複時使用 1-based occurrence。provider strict wire 以 `0` 代表唯一 quote，再由 application 轉回 `None`。stable source UUID 與 start／end offset 由 deterministic resolver 對 immutable source 計算，模型不能填 offset。

更正由員工在一般聊天自然表達。每則新回答仍先成為 immutable source；模型只有在語句明確完整取代一個可唯一辨識的舊來源時才回傳 source handle，application 驗證 document scope、current status 與唯一 target，再以 `supersedes_source_id` 建立 lineage。補充或限定不 supersede；有多個可能 target 時建立 required clarification。Evidence basis 改變會觸發未改 workspace files 的重新驗證：引用舊來源的路徑得到 `evidence-source-stale`，只阻擋直接受影響的 review group；無關 group 與 approved JD 保持可用。主要 UI 不提供逐段來源更正操作，lineage 留給進階追溯。

只有 employee turn、edit-and-accept 或 direct edit 中員工實際輸入的文字可鑄成 Evidence。單純 accept、reject、模型文字與未啟用的 Reference 都不是員工工作事實。

## 模型執行與最小充分 Context

- Versioned model profile 只決定 requested model、唯一 provider、參數與 timeout；versioned run policy 決定 eligible Skills、六個 Tools、context／call／token／time／cost guards 與 retry。Skills 不選模型，第一版固定單一路由且禁止 provider fallback。
- `ChatOpenRouter` 承接 provider wire。compact `ConsultantModelOutput` 只含顧問回覆、可修訂理解、訪談工作、Gap、下一題／必要澄清、足夠性與其 Evidence basis；pure mapper 再還原 application result。
- 每次模型推論由 middleware 依 Saver snapshot 與 Store 重建最小充分 Context：目前焦點、相關核准 slice、有效理解、Gap、review 摘要、workspace validation 摘要、本輪原話與必要的近期來源。完整 Skills、sources、approved、workspace 與 review details 由模型按需 `read_file／grep`，不把完整 workspace 自動注入 prompt。
- 本輪原話、required Evidence、必要澄清、blocking Gap、焦點理解與核准 slice 不被非權威對話摘要取代；Context selection receipt 只保存 ID、hash、原因、revision、Skills、token 與降級資訊，不複製員工文字。
- 每個 run 都從 versioned policy 解析 model／Tool／context／token／cost／elapsed guards；LangChain `ModelCallLimitMiddleware` 與 `ToolCallLimitMiddleware` 分別把每輪總 model calls／Tool calls 固定在十一／四十八的 ceiling，另有 24k 單次 context、160k 累計 raw tokens、US$2、180 秒與窄 retry。依 [ADR 0068](../adr/0068-framework-run-budgets-replace-lookup-wave-cap.md)，不再以自訂 path counter 限制外部資料讀取波數；讀取仍必須有新資料依賴、獨立 reads 要平行、結果足夠時立即停止。
- callback 為每個真實 provider attempt 保存 payload-free usage／route／cost evidence 與 telemetry。它們用於恢復、成本與診斷，不是職務內容 authority。

同一位主要顧問按需組合工作盤點、故事訪談、Task 邊界、Duty 分組、O、P、K、S 與完成度反方檢查等 Skills。Skill 是方法與 progressive-disclosure 邊界，不是人格化 Agent、固定 stage 或獨立 state owner。

## Adaptive interview、API 與 Web

LangGraph `StateGraph`、typed checkpoint 與 `interrupt()`／`Command(resume)` 承接跨回合 routing、自然恢復與必要澄清；沒有另建 pause／resume／finish lifecycle。一般 Gap 只留在待處理投影，只有無法安全自行消解的重大歧義才暫停 affected branch，安全旁支仍可繼續。焦點與一般 Gap 是內部訪談語意，不要求綁到現有 Duty／Task／OPKS ID。

- 「AI 目前理解」是可修訂、可收合的 projection，不是第二份文件。來源更正只挑戰直接相依的理解與工作，無關內容及來源歷史保留。
- 可信進度並列呈現工作 coverage、各工作範圍的 Task／Duty／O／P／K／S depth，以及待員工決定的文件差異與 Gap；不保存假百分比。
- 「目前已足夠」是 deterministic Evidence 與模型白話判斷的交集，不會關閉對話，也不等於 export readiness。新員工來源或 direct edit 會要求重新計算。

`/api/v1/job-analysis/consultant-documents` 只輸出 purpose-first projection，不暴露 raw checkpoint、Store manifest、command／Context／attempt receipt 或內部 digest。JSON Schema 生成 Pydantic 與 TypeScript 型別；SSE 只發送 refetch notification，durable snapshot 才是狀態權威。

Web 只有 `/workspace` 與文件詳情頁，以 TanStack Query 管理 server cache、原生 `EventSource` 接收 refetch 通知，並保護目前 JD 尚未送出的 browser draft。主要畫面是同一個 Duty → Task → O／P／K／S 階層的目前 JD；工作地圖與訪談欄可在 responsive in-flow layout 中收合。`審核變更` 在相同文件骨架內以紅色 before／移出與綠色 after／移入呈現 semantic diff，atomic subgroup 只有一個員工決定；`匯出版本` 只讀 approved baseline，不是第三個 editor。不要求員工操作 VFS path、Tool、JSON、digest、action ID 或 graph state。

- 員工逐字回答、更正 lineage 與 `source_saved／completed／failed` run 狀態都由 durable snapshot 重建。provider／analysis 失敗後 textarea 仍可輸入；retry 是快捷方式，不是唯一操作。新訊息可補充或自然表達「我剛剛說錯了」，不要求員工選舊原話。
- 目前 JD 的 browser draft 是 document-scoped 暫存輸入，不是 server authority；background refetch 不覆蓋 dirty draft。409 stale response 會觸發 refetch，同時保留尚未送出的員工編輯。
- pending 文件差異不阻擋聊天，也沒有 `defer`。只有真正缺少員工決定的來源衝突或重大邊界歧義才走 required clarification；一般 Gap 繼續可見但不強制立即回答。

匯出只有一個入口；有具體 readiness gap 時先顯示問題，員工明確 `force=true` 後仍只匯出目前 approved 內容。未接受的 workspace 差異不會被暗中接受或匯出。

## 現行產品邊界

- 本機單一操作者、每份 JD 一個 active workspace、一位主要 AI 顧問；沒有 multi-agent、planner／writer／critic 或 subagent 產品拓撲。
- 沒有 auto-accept／Auto mode；任何 AI 產生的內容都必須由員工 accept、edit-and-accept 或直接改寫該範圍，才會進入 approved／export authority。
- current API／Web 沒有 RAG、Reference、semantic retrieval 或外部知識 Tool；`/sources` 的同文件 exact lookup 是員工來源記憶，不是 RAG。repo 保留的 RAG bounded context 仍與 current runtime 隔離。
- 沒有多 workspace、branch、fork、Git／PR、workspace 版本歷史 UI 或 multi-process 保證。
- 能力級別與 A 不由 LLM 產生；官方 iCAP 配發代碼不由模型、員工或 export 補造。
- 沒有正式 quality eval 平台或 billing subsystem；execution receipts 只提供目前 runtime 的窄量測與 fail-closed guard。
