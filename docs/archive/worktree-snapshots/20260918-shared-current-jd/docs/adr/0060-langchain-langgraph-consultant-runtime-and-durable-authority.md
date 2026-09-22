# 0060. LangChain／LangGraph 職務顧問 runtime 與單一 durable authority

- **狀態**：Accepted
- **日期**：2026-08-13；2026-08-14 依 owner 產品語意審核、最終框架覆蓋審核與明確施工授權修訂
- **研究**：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §0–§8、§9.7–§9.13
- **部分取代**：0043 的四表 Current State 形狀；0045 的舊 Web 契約與自寫 authority seam；0046 的自寫 durable turn；0047 的舊 open-issue closure；0049–0051 的分立 Proposal／Current JD persistence 形狀；0053 決定 4 對「職能基準名稱／工作描述只能由模型讀、不得提案」的限制；0054 的固定 child-operation scheduler；0052／0056 的無確認直接匯出政策；0058–0059 對現行 AI 功能模組／shared kernel 的切割
- **保留**：本機單一操作者、多文件隔離、員工文件權威、來源與更正、Task／Duty／O／P／K／S 專業方法、0048–0051 的 evidence／linkage／穩定 identity／員工決策不等於證據等語意（只取代舊 persistence／type shape）、0052 的外部正式代碼邊界、deterministic export，以及 0057 的 RAG bounded-context 隔離

## Context

現行產品已證明職務分析方法與員工 authority，但也為「持續理解員工工作、決定現在談什麼、保存待處理問題、呈現進度、讓員工審核 LLM 文件內容、保存核准成品、恢復失敗處理」各自建立一組元件、資料表與生命週期。舊程式稱它們為 Work Model、Focus、Progress、agenda、Proposal、Current JD、operation 等；這些名稱只用來辨識刪除範圍，不是新架構必須保留的 domain boundary。

2026-08-12 至 2026-08-13 的官方資料研究與可丟棄 probes 已驗證：

- LangChain 1.x 可承接 OpenRouter model／參數 profile、bounded tool loop、structured output、middleware context、按需 Skills 與 model／tool call limits；
- LangGraph 1.2.x 的 typed state、PostgreSQL Saver／Store、routing、interrupt／resume、command 與 durable execution 可承接動態訪談、可修訂理解、可見缺口、非阻塞文件變更審核、必要澄清、員工核准成品與重啟；
- FastAPI stable 版已有原生 typed SSE；TanStack Query 與瀏覽器 `EventSource` 足以呈現 durable snapshot，不必引入完整 Agent Server；
- Pydantic AI Harness Planning 0.13.0 的真實 API 是 per-run ephemeral plan，沒有本產品需要的 stable identity、dependency、blocked／defer／reopen 或 durable store；
- 四個中立產品目的以固定採購情境驗證為 `4 passed`；既有 PostgreSQL Saver／Store suite 為 `14 passed`。這是機制 conformance，不是模型品質 eval。

若新 runtime 只在外層呼叫舊 writers，便仍會保留兩套生命週期。本案因此採 AI 顧問子系統的受限 Big-bang：框架直接承接同目的通用機制，舊名稱、舊 store 與 compatibility layer 一起退出。

Owner 於 2026-08-14 另外確認：本次核心升級不串接 iCAP Reference／RAG。既有 PDF／OCS／indexer／embedder／Qdrant bounded context 繼續依 ADR 0057 保留與隔離，日後另行研究、討論與開 successor ADR。

## Decision

### 1. 產品行為先於元件名稱

員工面對一位專業職務說明書顧問。顧問先形成可修訂的工作全貌，再以清楚的訪談重點深入；旁支與缺口被保留但不任意搶焦。盤點工作、深入故事、Task boundary、Duty grouping、O／P／K／S 與完成度反方檢查是同一訪談中按需組合的 Skills，不是固定 wizard 或多個人格化 Agent。

產品必須符合以下行為：

1. LLM 回答後自然等待。員工想繼續就再傳訊息，想休息就停止傳訊息或關閉頁面；下次開啟同一文件自然續談。產品不建立「本輪可停」「暫停訪談」或「訪談結束」狀態。
2. 「目前已足夠」只是可重新計算的顧問建議，必須說明理由、剩餘缺口與繼續訪談可能改善之處；它不關閉對話，也不等於通過匯出檢查。
3. 凡 LLM 產生、準備進入職務文件的內容，都先成為待審 changeset。只有員工接受或修改後接受，內容才進入核准文件；拒絕與延後不修改核准文件。這項目的不要求物件叫 `Proposal`。
4. 員工可以直接編輯自己的核准文件，不需要再審核自己的修改。
5. 第一版 LLM 可處理職務名稱、工作描述、Duty、Task、重新分組、排序及 O／P／K／S。能力級別與 A 暫不交給 LLM，因為尚未完成對應研究與 Skill；既有欄位、員工直接編輯與 deterministic export 仍保留。
6. ADR 0052 的代碼分權保持有效：`職能基準代碼`／`職類別代碼` 由 iCAP 計畫執行單位配發，產品保持空白且員工／模型皆不可填；`職業別`／`行業別` 名稱與分類代碼可由員工填寫或日後由可信分類資料帶入，但 LLM 不得自由生成。

新 production code、contract 與 state channel 依產品目的或 framework primitive 命名，不保留 `WorkModel`、`ActiveQuestion`、`Progress`、`Agenda`、`Proposal`、`CurrentJd`、`ScheduledOpks` 等舊 class／table／writer 作 compatibility layer。舊名稱只可出現在 migration、刪除帳本與歷史說明。

### 2. 主框架與版本線

主方案只採一套 workflow／semantic-state runtime：

- LangChain 1.x：model／tool binding、`create_agent` bounded loop、structured output、middleware 與 call limits；
- LangGraph 1.2.x：`StateGraph`、typed state／reducers、routing、PostgreSQL checkpointer、Store、interrupt／resume、command 與 durable execution；
- `langchain-openrouter`：OpenRouter model／provider／參數 profile；
- Deep Agents 只取可獨立使用的 `SkillsMiddleware`，並搭配 `FilesystemMiddleware(tools=["read_file"])` 與限縮在版本化 `/skills` package resources 的唯讀 `BackendProtocol` adapter；不採 host `FilesystemBackend`、`create_deep_agent`、自由 todo、subagent、shell 或寫檔；
- FastAPI 0.141.1 stable 已在 Task 1 通過原生 SSE、既有 route／problem／health 與含 PostgreSQL 的完整 API gate，因此正式採用；不增加 `sse-starlette` 或第二個 agent server；
- PostgreSQL 仍是唯一預設基礎服務，不新增 Redis、graph database、DBOS、Camunda、Agent Server 或 LangSmith 服務依賴。

2026-08-14 已直接核對官方 PyPI 指定版本端點：production 候選精確 pin 為 LangChain 1.3.15、LangGraph 1.2.11、`langgraph-checkpoint-postgres` 3.1.2、`langchain-openrouter` 0.2.7、Deep Agents 0.7.5、FastAPI 0.141.1 與 HTTPX 0.28.1；均存在且未被 yank。LangChain／LangGraph 是 Production/Stable，Deep Agents 與 `langchain-openrouter` 仍標示 Beta，因此只使用窄介面並加 import／behavior canary。任何套件升級都不能順便更換架構或產品語意。[LangChain 1.3.15](https://pypi.org/project/langchain/1.3.15/) · [LangGraph 1.2.11](https://pypi.org/project/langgraph/1.2.11/) · [Postgres checkpointer 3.1.2](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/) · [OpenRouter integration 0.2.7](https://pypi.org/project/langchain-openrouter/0.2.7/) · [Deep Agents 0.7.5](https://pypi.org/project/deepagents/0.7.5/) · [FastAPI 0.141.1](https://pypi.org/project/fastapi/0.141.1/) · [HTTPX 0.28.1](https://pypi.org/project/httpx/0.28.1/)

### 3. 每項持久事實只有一個 framework owner

| 持久事實 | 唯一可寫 owner | 限制 |
|---|---|---|
| 文件 catalog、title、tombstone、thread pointer | 最小 PostgreSQL catalog | 不複製顧問狀態或文件內容 |
| 員工原話、更正、quote anchor 與大型 immutable artifact | LangGraph `AsyncPostgresStore` 的 document namespace | 其他 state 只存穩定 reference／lineage，不複製全文 |
| 可修訂理解、動態訪談工作、具體缺口、可信進度、待審文件變更、核准文件、理解校準、必要澄清與 run status | LangGraph `AsyncPostgresSaver` 的 typed checkpoint state | 不另建 relational／JSONB mirror writer；API／Web 只讀 projection |
| editor local draft 與 TanStack cache | Web 非權威狀態 | 不得覆蓋 dirty draft，也不得被模型當來源 |

Store 與 Saver 保存不同事實：前者保存 append-heavy immutable source，後者保存可演進 semantic state 與 source references。Provider 呼叫期間不持有資料庫 transaction；每個有副作用的 node 必須符合 LangGraph durable-execution 的 deterministic／idempotent 規則。文件刪除同時清除 catalog、checkpoint thread 與 Store namespace。

`langgraph-checkpoint-postgres` 必須設定 `LANGGRAPH_STRICT_MSGPACK=true` 或等價的明確 module allowlist，首次安裝執行 idempotent `.setup()`；若自行建立 psycopg connection，必須使用 `autocommit=True` 與 `row_factory=dict_row`。Store namespace 只接受 application 配發的固定格式 document UUID，不接受員工輸入或可含 `%`／`_` 的自由字串。這些是套件官方列出的 production／deserialization 邊界，須有整合測試，不能只依環境慣例。[Postgres checkpointer security and setup](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/)

### 4. 成熟 primitive 的直接替換帳本

| 產品目的 | 採用機制 | Caliburn 只留的薄政策 | 舊機制結果 |
|---|---|---|---|
| 動態選擇訪談重點、停放旁支、延後返回、更正重開 | `StateGraph` routing／transition＋checkpoint | work-unit eligibility、優先理由、暫時收束／重開條件 | 刪除舊 question target、scheduler、focus／agenda lifecycle |
| 持續修訂 AI 對工作的理解 | typed state／reducers＋source lineage | Task／Duty／OPKS identity、evidence dependency、選擇性失效 | 刪除舊 Work Model store／writer |
| 顯示 coverage／depth／decision／gap 與「目前已足夠」 | typed state＋deterministic projection | reason code、足夠性證據與 LLM 白話解釋；禁止假百分比 | 刪除舊 Progress／open-issue writer |
| 記得員工原話與更正 | `AsyncPostgresStore`＋state references | source validity、supersession、quote／可信度規則 | 刪除舊 Journal-as-memory 與全文 context copy |
| 最小充分 context | LangChain middleware＋Store read tools＋token budget | 受限全域索引、最新更正、當輪 eligibility、context-selection receipt | 刪除舊 ContextPacket builders |
| 盤點、故事、Task、Duty、O／P／K／S、完成度方法 | `SkillsMiddleware`＋`FilesystemMiddleware(read_file only)`＋限縮 Skill backend | repo 內已驗證方法與當輪 eligibility | 刪除固定巨型 prompt 與固定 Task→OPKS scheduler |
| 可換 model／provider／參數 | `ChatOpenRouter`／LangChain binding＋versioned profile | allowlist、資料政策、resolved snapshot、usage／route receipt | 刪除手寫 OpenRouter wire 與舊 use-case wrapper |
| bounded model／tool loop、重試與結構化輸出 | LangChain `create_agent`、`response_format`、`ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、`ModelRetryMiddleware`、`ToolRetryMiddleware` | retry eligibility、總 budget、idempotency、每次 attempt receipt | 刪除自寫 loop／wire parser／通用 retry plumbing |
| LLM 文件內容由員工審核 | checkpointed typed changeset／review queue＋command | change contract、dependency subgroup、path read-set、stale、verifier | 刪除分立 Proposal class、table、writer |
| 理解校準與重大歧義 | state projection；必要時 `interrupt`／`Command(resume)` | trigger、soft／branch-blocking、answer-as-source、與文件審核分離 | 刪除自寫 calibration／blocking lifecycle |
| 核准職務文件與直接編輯 | checkpoint authority channel＋deterministic command | 只有員工 command 可寫、文件 invariant、export/readiness | 刪除舊 Current JD mirror writer 與 authority seam 實作 |
| 瀏覽器恢復與狀態更新 | FastAPI typed SSE＋`EventSource`＋TanStack Query | product event／view contract、dirty-editor policy | 刪除同步 durable-turn response 與舊 cache plumbing |
| tracing、usage 與錯誤診斷 | LangChain callbacks／run metadata＋既有 OpenTelemetry | 本機 correlation IDs、resolved execution／attempt receipt、敏感值排除 | 刪除 provider-specific trace glue；不要求 LangSmith 服務 |

#### 4.1 成熟 middleware 的使用邊界

- `SkillsMiddleware` 只負責列出 metadata 與 progressive-disclosure 提示，本身不提供載入全文的 tool。實作必須共享同一個限縮 backend，另加只暴露 `read_file` 的 `FilesystemMiddleware`；backend 只讀版本化 `/skills` package resources，拒絕 traversal 與其他 namespace。官方明示 host `FilesystemBackend` 不適合 Web/API production，因此不得以 permissions 假裝成真正 sandbox，也不得暴露 `ls`／`glob`／`grep`／write／delete／execute。[Skills middleware](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware) · [Filesystem middleware](https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware)
- structured output 以 LangChain `response_format`／自動 provider-or-tool strategy 為第一層，再由 Pydantic 與 deterministic domain verifier 驗證；不得重寫通用 JSON repair loop。
- `SummarizationMiddleware`／`ContextEditingMiddleware` 只能壓縮非權威的近期對話副本與大型唯讀 tool result；員工逐字來源、最新更正、blocking contradiction、source lineage 與核准文件 slice 必須由 Store／state 依 ID 重新載入，不能被摘要取代。
- `ModelFallbackMiddleware` 預設不啟用。若維護者日後在 versioned profile 明確開啟，只能在 allowlist 內執行，且每次失敗與實際 route 都要寫入 attempt receipt；不能 silent fallback。
- 不採 `LLMToolSelectorMiddleware` 作第一版 Skill 選擇器：eligibility 可由 deterministic state 先縮小，額外 selector inference 只增加成本與另一個失敗點。出現具體 tool-surface 品質問題後才能重開。
- 不用 `HumanInTheLoopMiddleware` 代替文件審核 queue：它適合暫停目前 tool call，但本產品需要可延後、多筆並存、任意順序決策且不阻塞安全訪談的 changeset。required clarification 才使用 `interrupt`／`Command(resume)`。
- 不用 `TodoListMiddleware` 代替動態訪談工作與進度：它沒有產品需要的 stable identity、dependency、blocked／defer／reopen 與 correction lineage；LangGraph typed state／routing／checkpoint 承接通用生命週期，Caliburn 只定義 eligibility 與 reason code。[LangChain built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) · [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)

#### 4.2 OPKS、來源與待審 changeset 的既有語意不因換框架消失

LangGraph 直接取代舊 Proposal／OPKS persistence lifecycle，不代表可省略 0048–0051 已接受的安全規則：

1. 第一階段可作 evidence 的來源只有已保存的 employee turn 與 employee direct edit；模型是候選作者，不是新事實來源。不得預建尚未啟用的 Reference evidence 入口。
2. 每個 active K／S 候選或核准項目都要有非空 employee source refs。單純 accept／reject／defer 不是工作行為證據；只有員工真的改寫內容時，才為改寫部分鑄成新的 direct-edit source。
3. O／P 掛在 Task；K／S 是文件層項目，與 Task／Indicator 維持多對多 refs，不因 UI 顯示在單一 Task 下就複製或變成單一所有權。A 同為文件層，但第一階段模型不產生。
4. 操作型 Task 可以合法沒有實體 O；若連 meaningful outcome、維持狀態、避免後果或遵循規章都說不清，先挑戰 Task 邊界，不為填欄位補造 O。
5. 模型未取得員工逐字來源時，不得補數字、具名法規／SOP／規章或「依公司規定」「適當時間內」等假外部指涉；有逐字來源仍要保存 quote anchor 與可查核性標記。
6. 每個待審 patch action 在建立時由 application 配發穩定 identity；重播取得同一 ID，衝突／stale／拒絕記憶以 ID 與 path read-set 判斷，不靠文字相似度。
7. 待審狀態至少能表達 pending、deferred、accepted、edit-accepted、rejected 與 stale，並保存員工實際修改、拒絕理由與可呈現的 stale 原因；review bundle 只改 UI／原子群組呈現，不把互不相依項目偷偷綁成全收全退。

### 5. 一個 bounded 顧問回合

1. API 驗 document scope、idempotency key 與 payload hash；員工回答先以 pending source 寫入 Store，再建立 durable graph run，立即回 202。
2. 每份文件同時只允許一個會改 semantic state 的 graph run；本機單 process 先用 per-document admission lock，restart 依 durable run receipt reconcile。
3. deterministic node 先產生每輪必帶的**受限全域工作索引**：目前已知工作範圍、核准文件骨架、可修訂理解摘要、重要 gap／矛盾、待審變更與最新更正的穩定 ID／狀態。它是可重建定位投影，不是 LLM 自由摘要或第二份 authority。
4. context middleware 再加入目前訪談重點的足夠細節、相關來源、最近自然對話與 allowlisted lookup handles；超出 budget 時依明確降級順序裁切，不能移除當輪回答、最新有效更正或 blocking contradiction。
5. eligible set 只暴露本輪可能需要的盤點／故事／Task／Duty／O／P／K／S／完成度 Skills；Task 不需先永久穩定，數個 Skills 可在同一回合組合。能力級別、A 與 Reference Skill 不在第一版 eligible set。
6. 模型採快速路徑，最多三次 inference、兩波唯讀補查；framework call limits 硬停。模型與 provider 取自同一 active consultant profile，不因 Skill 自動換模型。
7. 模型回傳 typed 顧問結果；deterministic verifier 另驗 source、quote、identity、dependency、Skill／context eligibility、官方代碼邊界與文件 change path。
8. 一個 semantic checkpoint 原子更新可修訂理解、動態訪談工作、具體 gap、可信進度、可見顧問回覆與待審文件 changesets。AI node 沒有寫核准文件的 edge。
9. 「AI 目前理解」常駐投影可收合；一般重點切換、重大修訂或久後恢復可出現 soft calibration card。員工可確認、直接修正或稍後處理；確認是新的員工 evidence，不是文件接受。
10. 結構性待審變更若是後續 Task／Duty／OPKS 分析前提，只標記依賴分支 blocked；其他安全訪談工作繼續。員工延後時保存 blocked reason；沒有安全重點時才要求先處理。決定後重驗下游 changesets、gap 與 linkage。
11. 只有來源衝突、重大責任邊界或缺少只能由員工決定的事實時，才用 required-clarification interrupt。回答寫成新 employee source，絕不等同接受任何文件變更。
12. 員工 accept、edit-accept、reject、defer 或直接編輯是新的 typed graph command；重驗 path read-set 後，只有 authority node 能原子修改核准文件。
13. 若一則回答已保存但語意分析失敗／待處理，同一文件暫不接受新的 AI 訪談回答，直到它成功提交或被員工明確修正／取代；查看、審核、直接編輯、匯出與離開仍可使用。
14. 員工可以在任何時候關頁。若 run 尚未完成，回來時顯示已完成結果或可恢復／重試狀態；若已完成，直接回到原對話與 durable view，不新增 pause／resume command。

### 6. Contract、Web、足夠性與匯出

`packages/job-analysis-contract` 繼續作 API／Web 跨語言 JSON Schema SSOT，但 schema 依產品目的重寫，不保留舊 DTO aliases。至少投影：

- 目前訪談重點、理由與暫時收束條件；
- 常駐可收合的「AI 目前理解」、來源標記、revision 與 soft／branch-blocking 校準卡；
- 可見工作範圍、coverage／depth／decision／具體 gap 與「目前已足夠」建議／理由；
- 顧問訊息、待審 changeset／review bundle、必要原子子群組與 affected branch；
- required clarification、核准文件、durable run／SSE snapshot 與匯出 readiness。

Web 維持 `/workspace` 與文件詳情頁。員工可看見現在談什麼、為什麼、AI 目前怎麼理解、還缺什麼，以及哪些內容等待自己決定；沒有「本輪可停」「完成訪談」或專用 resume wizard。第一次使用時一次清楚揭露職務資料會送往外部 AI，不在每輪重複彈窗。

待審文件變更採可編輯 review bundle＋必要原子子群組。員工可逐項決定獨立變更；只有為維持結構 invariant 必須一起成立的操作才綁成一組。修改或部分接受後必須重驗剩餘 dependency，不留下無效 linkage。

核准文件保留完整既有官方欄位與 deterministic XLSX 語意，包括能力級別與 A；第一版只是不讓 LLM 分析或產生這兩類變更。產品只有一個匯出入口。若有未分析、未分組、OPKS gap、必要澄清或待審變更，先列出具體缺口並要求員工確認；員工仍可強制匯出。強制匯出不接受待審變更、不補造內容、不隱藏孤立 Task，也不改核准文件。

### 7. Model／provider 控制與執行證據

第一版只有一個 active consultant model profile，由本機維護者管理；員工不在訪談介面直接操作 temperature、reasoning effort、token limit 或 provider routing，也不為每個 Skill 選不同模型。

1. **Versioned model profile**：requested provider／model、能力需求、有效參數、provider order／fallback、資料政策與 secret reference；修改產生新 revision。
2. **Versioned run policy**：依 run kind 設定允許的 Skills／tools、typed contracts、context／output／call／time／cost budget、retry 與內部終止規則；它不等於另一個模型設定，也不建立員工可見的停止狀態。
3. **Resolved execution snapshot**：每個 model-bearing run 開始前合併 profile／policy revision，保存實際送出前可確定的 model、provider allowlist、參數、能力、budget、route policy 與 adapter version。
4. **Attempt receipt**：保存供應商回報的實際 model／endpoint、attempt chain、usage、成本、latency、cache、停止原因與錯誤。不得使用無紀錄的 silent fallback。

### 8. 受限 Big-bang 與明確延後

- 新 runtime 在隔離 worktree 完成，composition root 切換前不接舊 AI writer；切換後同一批次刪除舊 module、table、migration、route、contract 欄位與 Web plumbing。
- 不搬 spike code，只以 tests 與研究結論作驗收證據。
- 本次不接 RAG／Reference，不新增 current API／Web consumer、query contract、composition-root dependency 或預設服務；ADR 0057 的隔離規則保持有效，日後另行討論。
- 同一文件內按 stable ID／lineage 找回員工原話與更正，是本次必要的記憶／context lookup，不是公版 RAG；它只能讀 `AsyncPostgresStore` 的 employee sources，不得連到 ADR 0057 bounded context、外部 corpus 或 Reference source type。
- 不做完整模型品質 eval；只做 deterministic tests、fake model、restart／authority gates 與一個人工 live smoke。產品成品完成後另開 eval plan。
- 不讓 LLM 分析能力級別或 A；保留欄位與人工編輯，待方法研究與 Skill 完成後另案啟用。
- 不引入 multi-agent、subagent、自由 planning、shell、code mode、多使用者、雲端、多 worker、GraphRAG 或 exact token replay。

## Rejected alternatives

1. **保留現行 writers，再用 LangGraph 包裝。** 會形成兩套 authority 與 stale／recovery lifecycle，違反直接替換目的。
2. **把舊名稱直接搬進一個 `DocumentState`。** 只證明框架能儲存欄位，沒有證明通用生命週期已被替代；target state 必須按產品目的與 framework primitive 設計。
3. **PydanticAI V2＋Harness＋DBOS。** PydanticAI core 合格，但本案最依賴的 Planning 0.13.0 不具必要 durable semantics；再加入 DBOS 會多一個 workflow owner。
4. **完整 Deep Agents 或 Agent Server／`@langchain/react`。** 第一版不需要 subagent、shell、remote threads、exact event replay 或多人 client；採完整產品形狀會擴張顧問邊界。
5. **Camunda／Microsoft Agent Framework／另一個 memory framework。** 四個直接產品效果已由主方案通過；依 stop rule，不為未發生的硬缺口堆第二套 runtime。
6. **本次順便串接 RAG。** Owner 已明確延後；提前串接會改變 ADR 0057 邊界、啟動方式、失敗降級與 provenance contract，必須留待獨立討論。

## Consequences

正面：

- framework 接手 persistence、resume、interrupt、routing、bounded loop、middleware、Skills、provider binding 與 SSE wire；Caliburn 聚焦職務分析方法、員工 authority 與 UX。
- 一份文件每項事實只有一個可寫 owner；關頁、失敗與重新啟動不需要自寫 replay protocol。
- Task、Duty、OPKS 不再被固定 operation 階段切開，可依證據按需組合，同時保持員工控制正式文件。
- 員工能看見 AI 目前理解、訪談重點、真實缺口與足夠性，而不被迫操作暫停／完成狀態。

成本與風險：

- 這是 current 產品 AI／document-state 的一次硬切，不是小型重構；舊 API／schema／Web／migration 要同步移除。
- checkpoint state 不適合任意 SQL 查詢；第一版以單文件 read／edit／export 為主。跨文件分析若成為真需求，要另開 read-only projection ADR。
- framework schema evolution、checkpoint table setup、同 thread concurrency 與容量必須有 canary；版本精確 pin 並由 lockfile 管理。
- FastAPI 升級與 SSE 需要先過完整 API gate；失敗時回退 FastAPI 升級，不得因此引入第二個 agent server。
- 本 ADR 不聲稱模型品質已提升；長訪談與成品品質仍待產品完成後 eval。

## Acceptance gate

Owner 於 2026-08-14 在要求完成產品方向與成熟框架覆蓋審核後，明確授權審核通過即可開始施工；該審核記錄於 [`2026-08-14-consultant-runtime-north-star-audit-ledger.md`](../specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md)，因此本 ADR 改為 Accepted。依配套 implementation plan 建新的 production worktree，完成前不得 merge／push。

Big-bang 只描述最終切換方式，不表示長時間盲做。每個可獨立驗證的 Task／功能完成後，必須在同一審核帳本記錄：實際員工效果、採用的成熟 primitive、仍留的最薄產品政策、退出的舊機制、驗證證據與北極星偏移判斷。未通過就不得開始下一個 Task；若找到會改善產品效果的新方法，先與 owner 討論並更新研究／successor ADR，不能由實作者暗中改方向。

若實作必須保留任何舊 writer／舊 target component、加入第二個 workflow／memory owner、串接 RAG、讓 LLM 處理能力級別／A，或新增「暫停／完成訪談」狀態，必須先回到本 ADR 與 owner 討論，不能由實作者自行偏離。
