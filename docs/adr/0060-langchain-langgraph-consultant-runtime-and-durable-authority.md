# 0060. LangChain／LangGraph 職務顧問 runtime 與單一 durable authority

- **狀態**：Proposed
- **日期**：2026-08-13
- **研究**：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §9.7–§9.12
- **部分取代**：0043 的四表 Current State 形狀、0046 的自寫 durable turn、0047 的舊 open-issue closure 機制、0050–0051 的分立 Proposal persistence 形狀、0054 的固定 child-operation scheduler、0052／0056 的無確認直接匯出政策、0058–0059 對現行 AI 功能模組／shared kernel 的切割
- **保留**：本機單一操作者、多文件隔離、員工文件權威、來源與更正、Task／Duty／O／P／K／S 專業方法、deterministic verifier、公版匯出與 RAG bounded-context 隔離

## Context

現行產品已證明職務分析方法與員工 authority，但也為 Work Model、目前焦點、問題議程、進度、Task／OPKS operation、Proposal、Current JD、provider wire、context packet、durable turn 與多組 API／Web plumbing 各自實作生命週期。這些機制目的正確，卻使同一位顧問被切成許多相互協調的自寫元件；繼續逐元件補功能，會把主要時間花在重建 workflow、memory、HITL、provider 與 streaming framework 已有的能力。

2026-08-12 至 2026-08-13 的官方資料研究與可丟棄 probes 已驗證：

- LangChain 1.x 可承接 OpenRouter model／參數 profile、bounded tool loop、structured output、middleware context、按需 Skills 與 model／tool call limits；
- LangGraph 1.2.x 的 typed state、PostgreSQL Saver／Store、interrupt／resume 與 durable execution 可承接重啟、來源生命週期、動態訪談、可修正理解、可見 Gap、多筆非阻塞文件 patch、stale read-set、必要澄清與核准 artifact；
- FastAPI 0.135+ 已有原生 typed SSE；TanStack Query 與瀏覽器 `EventSource` 足以呈現 durable snapshot，不必引入完整 Agent Server；
- Pydantic AI Harness Planning 0.13.0 的真實 API 是 per-run ephemeral plan，沒有本產品需要的 stable identity、dependency、blocked／defer／reopen 或 durable store；
- 四個最後缺口以固定採購情境驗證為 `4 passed`；既有 PostgreSQL Saver／Store suite 為 `14 passed`。這是機制 conformance，不是模型品質 eval。

如果新 runtime 只在外層呼叫現行 Work Model／Proposal／Current JD writer，便仍會保留兩套生命週期，既無法得到框架完整能力，也無法降低維護風險。因此本案是受限 Big-bang，不是 adapter migration。

## Decision

### 1. 產品目的先於元件名稱

員工面對一位專業職務說明書顧問。顧問先形成可修訂的工作全貌，再以清楚焦點深入訪談；旁支與缺口被保留但不任意搶焦；Task、Duty、O、P、K、S 是同一訪談中按需組合的分析 Skills，不是固定 wizard。AI 可修正暫時理解，但任何準備進入核准職務文件的 LLM 內容，都必須讓員工接受、修改後接受、拒絕或延後。

新 production code 依這些目的命名，不保留 `WorkModel`、`ActiveQuestion`、`ScheduledOpks`、`Proposal`、`CurrentJd` 等舊 class／table／writer 作 compatibility layer。名稱不同不是目的；同目的成熟 primitive 能完整承接時，舊機制直接刪除。

### 2. 主框架與版本線

主方案採一套 runtime，不混用第二個 workflow owner：

- LangChain 1.x：model／tool binding、`create_agent` bounded loop、structured output、middleware 與 call limits；
- LangGraph 1.2.x：`StateGraph`、typed state／reducers、PostgreSQL checkpointer、Store、interrupt／resume 與 durable execution；
- `langchain-openrouter`：OpenRouter model／provider／參數 profile；
- Deep Agents 只取可獨立使用的 `SkillsMiddleware` 與唯讀 Skill loader，不採 `create_deep_agent`、自由 todo、subagent、shell 或寫檔；
- FastAPI 0.141.x 候選與原生 typed SSE；先跑完整 API gate，再 pin 可通過的 stable patch；
- PostgreSQL 仍是唯一預設基礎服務，不新增 Redis、graph database、DBOS、Camunda、Agent Server 或 LangSmith 服務依賴。

施工第一個 task 以研究時已實測的 stable 組合為起點：LangChain 1.3.15、LangGraph 1.2.11、`langgraph-checkpoint-postgres` 3.1.0、`langchain-openrouter` 0.2.7、Deep Agents 0.7.5。若 lock 時 stable patch 已更新，只能在相同 major／minor 能力線內升級並重跑 gate，不能順便換架構。

### 3. 每項持久事實只有一個 framework owner

| 持久事實 | 唯一可寫 owner | 限制 |
|---|---|---|
| 文件 catalog、title、tombstone、thread pointer | 最小 PostgreSQL catalog | 不複製顧問狀態或文件內容 |
| 員工原話、更正、quote anchor、Reference receipt 與大型 immutable artifact | LangGraph `AsyncPostgresStore` 的 document namespace | 其餘 state 只存穩定 reference／lineage，不複製全文 |
| 訪談工作單位、目前選擇、可見 Gap、可修正理解、待審變更、核准 artifact、必要澄清與 operation status | LangGraph `AsyncPostgresSaver` 的 typed checkpoint state | 不另建 relational／JSONB mirror writer；API／Web 只讀 projection |
| editor local draft 與 TanStack cache | Web 非權威狀態 | 不得覆蓋 dirty draft，也不得被模型當來源 |

Store 與 Saver 不重疊：前者保存 append-heavy immutable source，後者保存可演進的 semantic state 與 stable source references。Provider 呼叫期間不持有資料庫 transaction；每個有副作用的 node 必須符合 LangGraph durable-execution 的 deterministic／idempotent 規則。文件刪除同時清除 catalog、checkpoint thread 與 Store namespace。

### 4. 成熟 primitive 的直接替換帳本

| 產品目的 | 採用機制 | Caliburn 只留的薄政策 | 舊機制結果 |
|---|---|---|---|
| 動態訪談、旁支、延後返回、更正重開 | `StateGraph` transition＋checkpoint | work-unit eligibility、優先理由、完成／重開條件 | 刪除舊 question target、scheduler、active-question lifecycle |
| 可見進度與待處理問題 | typed state＋可重建 projection | coverage／depth／decision／gap reason；禁止假百分比 | 刪除舊進度／open-issue writer 與重複投影 |
| 記得員工原話與更正 | `AsyncPostgresStore`＋state lineage | source validity、supersession、quote／可信度規則 | 刪除舊 Journal-as-memory 與全文 context copy |
| 最小充分 context | LangChain middleware＋Store read tools＋token budget | 當輪 eligibility、有效更正、Context manifest 驗證 | 刪除舊 ContextPacket builders |
| Task／Duty／O／P／K／S 方法 | `SkillsMiddleware`＋唯讀 Skill source | repo 內已驗證的分析研究、當輪 Skill eligibility | 刪除固定巨型 prompt 與固定 Task→OPKS scheduler |
| 可換 model／provider／參數 | `ChatOpenRouter`／LangChain binding＋profile | allowlist、資料政策、成本／route receipt | 刪除手寫 OpenRouter wire 與 operation-specific provider wrapper |
| LLM 文件變更審核 | checkpointed typed operations／review queue | operation contract、path read-set、stale、deterministic verifier | 刪除 Task／OPKS 分立 Proposal class、table、writer |
| 必要結構化澄清 | LangGraph `interrupt`／`Command(resume)` | 必問門檻、affected branch、answer-as-source | 不與文件 patch 或一般 Gap 混用 |
| 核准職務文件與直接編輯 | checkpoint authority channel＋原子 graph command | 只有員工 command 可寫、export/readiness invariant | 刪除舊 Current JD relational／JSONB mirror writer |
| 瀏覽器恢復與狀態更新 | FastAPI typed SSE＋`EventSource`＋TanStack Query | product event／view contract、dirty-editor policy | 刪除同步 durable-turn response 與舊 consultation cache plumbing |

### 5. 一個 bounded 顧問回合

1. API 驗 document scope、idempotency key 與 payload hash；員工回答先以 pending source 寫入 Store，再建立 durable operation，立即回 202。
2. 每份文件同時只允許一個會改 semantic state 的 graph run；本機單 process 先用 per-document admission lock，restart 依 durable operation reconcile。
3. deterministic node 根據新 evidence 更新可修正理解、工作單位與 Gap，再選當前安全焦點；旁支不因被提到就搶焦。
4. context middleware 只帶當前焦點、必要理解、核准 artifact、有效更正、最近自然對話與少量高價值 source；其餘由 allowlisted read-only tool 按需取回。
5. eligible set 只暴露當輪可能需要的 Task／Duty／O／P／K／S Skill；模型採快速路徑，最多兩波唯讀補查，framework call limits 硬停。
6. 模型回傳 typed 顧問結果；deterministic verifier 另驗 source、quote、identity、dependency、Skill／context eligibility 與 authority。
7. 一個 semantic checkpoint 原子更新內部理解、焦點／Gap、可見顧問回覆與待審文件 operations。AI node 沒有寫核准 artifact 的 edge。
8. 若存在必須由員工裁決的重大衝突，只 interrupt 受影響分支；答案寫成新 employee source 後恢復。一般 Gap 與文件 review 都不使用這個 blocking channel。
9. 員工的 accept、edit-accept、reject、defer 或直接編輯是新的 typed graph command；重驗 path read-set 後，只有 authority node 能原子修改核准 artifact。

### 6. Contract、Web 與匯出

`packages/job-analysis-contract` 繼續是 API／Web 跨語言 JSON Schema SSOT，但 schema 依新產品 purpose 重寫，不保留舊 DTO compatibility。至少投影：目前訪談焦點與理由、可見工作範圍、coverage／depth／decision／Gap、顧問訊息、待審文件 operations、必要澄清卡、核准 artifact、operation／SSE snapshot 與 readiness。

Web 維持 `/workspace` 與文件詳情頁，改成固定顧問工作區：員工可看見現在訪談什麼、為什麼、還缺什麼；可繼續訪談並獨立處理多筆文件變更；必要澄清才阻塞受影響分支；核准 artifact 可直接編輯。現有 deterministic XLSX renderer、readiness 與 dirty-download 防線保留，輸入改由新核准 artifact projection 提供。

產品只有一個匯出入口。若仍有未分析、未分組、OPKS 缺口、必要澄清或待審文件變更，第一次操作先完整列出缺口並要求員工明確確認；員工仍可強制匯出。強制匯出不會接受待審變更、補造內容、隱藏孤立 Task 或改變核准 artifact。這部分取代 0052／0056 的「readiness 完全不阻擋匯出」：阻擋的是未確認的操作，不是強迫資料先填滿。

### 7. 受限 Big-bang 與明確延後

- 新 runtime 在隔離 worktree 完成，composition root 切換前不接舊 AI writer；切換後同一批次刪除舊 module、table、migration、route、contract 欄位與 Web plumbing。
- 不搬 spike code，只以 tests 與研究結論作驗收證據。
- 不接保留的 RAG bounded context；Reference／RAG 等核心顧問完成後再做 final gate。
- 不做完整模型品質 eval；只做 deterministic tests、fake model、restart／authority gates 與一個人工 live smoke。產品成品完成後另開 eval plan。
- 不引入 multi-agent、subagent、自由 planning、shell、code mode、多使用者、雲端、多 worker 或 exact token replay。

## Rejected alternatives

1. **保留現行 writers，再用 LangGraph 包裝。** 會形成兩套 authority 與 stale／recovery lifecycle，違反直接替換目的。
2. **PydanticAI V2＋Harness＋DBOS。** PydanticAI core 合格，但本案最依賴的 Planning 0.13.0 不具必要 durable semantics；再加入 DBOS 會多一個 workflow owner。
3. **完整 Deep Agents 或 Agent Server／`@langchain/react`。** 第一版不需要 subagent、shell、remote threads、exact event replay 或多人 client；採完整產品形狀會改變顧問邊界。
4. **Camunda／Microsoft Agent Framework／另一個 memory framework。** 四個直接產品效果已由主方案通過；依 stop rule，不為未發生的硬缺口堆第二套 runtime。
5. **為 CRUD／報表保留第二份 Current JD table。** 會產生雙 writer；第一版由最新 checkpoint projection 查詢與匯出。未來若真的需要跨文件分析，只能另開 read-only projection 決策，不能成為 authority。

## Consequences

正面：

- framework 接手 persistence、resume、interrupt、bounded loop、middleware、Skills、provider binding 與 SSE wire；Caliburn 聚焦職務分析方法、員工 authority 與 UX。
- 一份文件每項事實只有一個可寫 owner；關頁、失敗與重新啟動不需要自寫 replay protocol。
- Task、Duty、OPKS 不再被固定 operation 階段切開，可依證據按需組合，同時保持員工逐項控制正式文件。

成本與風險：

- 這是 current 產品 AI／document-state 的一次硬切，不是小型重構；舊 API／schema／Web／migration 要同步移除。
- checkpoint state 不適合任意 SQL 查詢；第一版以單文件 read／edit／export 為主。跨文件分析若成為真需求，要另開 projection ADR。
- framework schema evolution、checkpoint table setup、同 thread concurrency 與容量必須有 canary；版本只能精確 pin 並由 lockfile 管理。
- FastAPI 大版本跨度與 SSE 需要先過完整 API gate；不通過時保留現行 FastAPI，改用原生 `StreamingResponse`，不能因此引入第二個 agent server。
- 本 ADR 不聲稱模型品質已提升；長訪談與成品品質仍待完成產品後 eval。

## Acceptance gate

本 ADR 維持 Proposed，直到 owner 明確核准。核准後才可依配套 implementation plan 建 production worktree；完成前不得 merge／push。若實作必須保留任何舊 writer 或加入第二個 workflow／memory owner，必須先回到本 ADR 說明硬缺口，不能由實作者自行偏離。
