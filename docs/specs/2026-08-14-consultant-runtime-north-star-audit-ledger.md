# AI 職務顧問 runtime：北極星審核與逐 Task 防偏帳本

- 日期：2026-08-14
- 狀態：Pre-implementation audit **Passed**；Tasks 1–7 **Passed**
- 決策：ADR 0060 Accepted
- 施工計畫：[`2026-08-13-langgraph-consultant-runtime-big-bang-plan.md`](../plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md)
- 產品 SSOT：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §1–§8、§9.12–§9.13

## 1. 審核目的

本帳本回答兩題：

1. ADR／plan 是否忠實實現已討論的產品方向，而不是被舊系統名稱或框架預設帶偏？
2. 現行自寫通用機制是否都由成熟 framework primitive 直接承接；若仍需自寫，是否確實只剩框架不知道的職務分析／員工 authority 薄政策？

Big-bang 只描述最終切換，不表示做到最後才審核。之後每完成一個 Task 或可獨立功能，都在 §7 加一筆，未通過不得進下一個 Task。

## 2. 產品北極星逐項核對

| 已確認產品方向 | ADR／plan 落點 | 結果 |
|---|---|---|
| 一位 AI 專業職務顧問，不是填表精靈、多 Agent 或固定 wizard | ADR 0060 §1、§5；plan Tasks 4–5 | 符合 |
| 先建立可修訂工作全貌，再以一個清楚焦點深入；完整回答中的旁支仍保存 | ADR §1、§5.3–5.5；Task 5 behavior tests | 符合 |
| AI 帶路，員工可跳題、補充、返回；關頁後自然續談 | ADR §1.1、§5.14；Tasks 5、8 | 符合；沒有 pause／finish 狀態 |
| Task／Duty／O／P／K／S 可隨證據雙向修正，Task 不必先永久穩定 | ADR §1.5、§5.5；Tasks 4–6 | 符合 |
| 工作盤點、故事、Task、Duty、O、P、K、S、完成度是按需 Skills | ADR §1、§4、§5.5；Task 4 九個 Skill | 符合；非每回合全載入 |
| AI 的可修訂理解不是核准文件 | ADR §1.3、§5.8–5.9；Tasks 2、5 | 符合 |
| 每個 LLM 文件內容都先讓員工接受、修改後接受、拒絕或延後 | ADR §1.3、§4.2、§5.10–5.12；Task 6 | 符合；員工 direct edit 不重審 |
| 重大衝突先問員工；一般 Gap 與待審文件變更不是 modal | ADR §5.10–5.11；Tasks 5–6 | 符合；只阻塞依賴分支 |
| 員工知道現在談什麼、為何、AI 怎麼理解、還缺什麼 | ADR §6；Tasks 5、7、8 | 符合；進度不用假百分比 |
| 「目前已足夠」只是一項可重算建議 | ADR §1.2、§6；Task 5 | 符合；不關閉對話、不等於匯出 readiness |
| 一個匯出入口；缺口可見，員工仍可強制匯出 | ADR §6；Task 9 | 符合；不自動接受、不補造、不隱藏孤立 Task |
| 員工原話與更正先保存，AI 失敗不要求重打 | ADR §3、§5.1、§5.13；Tasks 2、7–8 | 符合 |
| 第一版 LLM 處理名稱、描述、Duty、Task、分組、排序、O／P／K／S | ADR §1.5；Tasks 4、6 | 符合 |
| 能力級別與 A 暫不由 LLM 產生，但欄位、員工編輯、匯出保留 | ADR §1.5、§6、§8；Tasks 6、9 | 符合 |
| iCAP 配發代碼保持空白不可編輯；職業／行業分類只由員工或可信資料 | ADR §1.6；Tasks 4、6、9 | 符合 |
| 本輪不接 Reference／RAG | ADR §8；plan global constraint／Task 9 guard | 符合；既有 bounded context 原樣隔離 |
| 正式模型品質 eval 等產品完成後再做 | ADR §8；Task 10 只做一個 smoke | 符合 |

結論：沒有發現與 owner 目前大方向衝突的 blocker。

## 3. 成熟 framework 元件覆蓋稽核

| 中立產品／工程目的 | 採用的成熟元件 | Caliburn 尚留的最薄政策 | 審核 |
|---|---|---|---|
| 模型／provider／參數可換 | `ChatOpenRouter`＋LangChain model binding | provider/model allowlist、資料政策與 versioned profile | 已覆蓋 |
| bounded agent loop | LangChain `create_agent` | run kind 與總 budget | 已覆蓋 |
| structured output | LangChain `response_format`＋Pydantic | 職務文件 schema 與 domain error reason | 已覆蓋 |
| call limit／retry | `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、`ModelRetryMiddleware`、`ToolRetryMiddleware` | 哪些錯可重試、idempotency、每次 attempt receipt | 已覆蓋；plan 已補明 |
| durable execution／restart | LangGraph `StateGraph`＋`AsyncPostgresSaver` | node 的 deterministic／idempotent side-effect 邊界 | 已覆蓋 |
| 員工來源記憶 | LangGraph `AsyncPostgresStore` | employee-only source kind、validity、supersession、quote anchor | 已覆蓋 |
| 動態訪談重點、旁支、延後返回、更正重開 | typed state／reducers／routing／checkpoint | work-unit eligibility、priority reason、reopen rule | 已覆蓋；不是舊 Focus／agenda |
| 可修訂 AI 理解 | typed state／reducers＋source references | Task／Duty／OPKS identity、dependency、選擇性失效 | 已覆蓋；不是舊 Work Model |
| coverage／depth／decision／Gap 與足夠性 | typed state＋deterministic projection | 職務分析 reason code、足夠性 rubric、白話說明 | 已覆蓋；不是舊 Progress |
| 按需專業方法 | Deep Agents `SkillsMiddleware`＋`FilesystemMiddleware(read_file only)` | repo 已驗證方法、eligibility、限縮 package-resource backend 與輸出契約 | 已覆蓋；不使用 host filesystem，Beta 窄介面需 canary |
| 最小充分 context | LangChain middleware＋Store read tools＋token budget | 必帶來源、降級順序與 selection receipt | 已覆蓋 |
| 長 context 壓縮 | `SummarizationMiddleware`＋`ContextEditingMiddleware` | 只壓縮非權威副本；exact source／correction 必須重載 | 已覆蓋；plan 已補明 |
| 多筆、非阻塞文件變更審核 | LangGraph checkpointed typed queue＋`Command` | patch path、read-set、atomic subgroup、stale／reject memory | 通用生命週期已覆蓋；精確業務政策無現成替代 |
| 必要結構化澄清 | LangGraph `interrupt`＋`Command(resume)` | 必問門檻、affected branch、answer-as-source | 已覆蓋 |
| 核准文件 authority | checkpoint authority channel＋deterministic command | 只有 employee command 可寫、文件 invariant | 已覆蓋；不是舊 Current JD writer |
| input idempotency／失敗恢復 | Store＋Saver＋PostgreSQL constraint | payload hash、pending reconciliation、admission rule | 已覆蓋 |
| typed SSE／重連 | FastAPI native SSE＋browser `EventSource`＋TanStack Query | snapshot/event contract、dirty editor policy | 已覆蓋 |
| API／Web 契約 | JSON Schema＋Pydantic＋既有 codegen | Caliburn view／command schema | 已覆蓋 |
| tracing／usage | LangChain callback／run metadata＋既有 OpenTelemetry | local correlation、execution／attempt receipt、secret filtering | 已覆蓋；plan 已補明 |
| XLSX 匯出 | 現行 openpyxl renderer＋Pydantic document projection | iCAP 欄位與 force-export 規則 | 已是成熟 library；無 agent framework 替代必要 |

審核結果不是「所有東西都改成套件 API」。框架已承接通用生命週期；職務分析語意仍必須以薄 policy／typed fields 表達，否則框架不知道什麼是 Task 邊界、可信 K/S、孤立 Task 或員工文件權威。

### 3.1 現行 production module 退出／保留對照

| 現行範圍 | 目標處理 |
|---|---|
| `app/adapters/openrouter/openrouter*.py` | 由 `ChatOpenRouter`、LangChain structured output／middleware／callbacks 取代；刪除手寫 wire、retry、usage glue |
| `app/task_analysis/context.py`、`llm/**`、`operation.py`、`ports.py` | 由 LangChain context middleware、`create_agent`、`response_format`、Skills 與 call limits 取代 |
| `app/task_analysis/question_targets.py`、`transition.py` | 由 LangGraph routing／reducers／checkpointed typed state 取代；只把專業 eligibility／Task rubric 重寫進薄 policy／Skill |
| `app/task_analysis/proposal_decisions.py` | 由 checkpointed changeset commands 取代；只保留文件 invariant／read-set／stale 語意，不保留舊 class／writer |
| `app/opks/context.py`、`generation.py`、`llm/**`、`operation.py`、`ports.py`、`scheduler.py` | 由按需 O／P／K／S Skills、LangChain agent loop 與 LangGraph eligibility routing 取代；取消固定 child scheduler |
| `app/opks/proposals.py`、`authoring.py` | 併入同一 framework changeset／authority command；不再有 OPKS 特製 proposal lifecycle |
| `app/opks/verifier.py`、`digest.py` | 通用 schema／hash 交給 Pydantic、LangChain structured output、PostgreSQL／標準 hash；來源、quote、OPKS linkage 等 domain checks 重寫為薄 verifier |
| `app/consultation/durable_turn.py`、`turn.py` | 由 LangGraph durable execution／Saver、source-first Store 與 FastAPI typed SSE 取代 |
| `app/core/domain/work_model.py`、`journal.py`、`state.py` | 由 Saver typed state＋Store source namespace 取代；不保留 Work Model／Journal state lifecycle |
| `app/core/domain/proposal.py`、`opks_proposal.py`、`authority.py` | 由 framework changeset queue＋typed command／authority channel 取代 |
| `app/core/persistence.py` 與對應 Postgres model／repository | 由最小 catalog＋LangGraph Saver／Store tables 取代；不雙寫、不 mirror |
| `app/core/portable_schema.py`、`model_outcome.py` | 通用 shape 交給 Pydantic／JSON Schema／LangChain structured output；只保留新產品 contract 必需型別 |
| `app/core/domain/task.py`、`duty.py`、`opks.py`、`sources.py`、`jd_header.py` | 舊 class 不作 compatibility layer；其已驗證 invariant 以 purpose-first framework state schema／validator 重建 |
| `app/documents/authoring.py`、`duty_authoring.py` | 由同一 checkpoint authority command 取代；員工 direct edit 語意保留 |
| `app/documents/readiness.py`、`app/export/assembly.py`、XLSX adapter | 先以 characterization tests 審核；可保留純 deterministic 規則／renderer，但只能讀新 approved-document projection，不能 import 舊 state |
| `app/api/*_mapper.py`、舊 routes／deps | 由新 generated purpose-first contract、consultant mapper／routes 與 typed SSE 取代；通用 RFC 9457 problem mapping 可保留 |
| Web `features/consultation`、`features/opks`、舊 query／API hooks | 由一個 consultant workspace、durable snapshot、editable review bundles 與 `EventSource` invalidation 取代 |

這張表是 Task 9 的刪除驗收基準；實作期間可新增新 runtime，但在 composition root 硬切前不得呼叫舊 writer，硬切後上述 Replace 類不得留 production import／可寫 table／compatibility alias。

## 4. 確認沒有精確通用替代品、因此允許保留的薄政策

以下不是保留舊元件，而是寫在 framework state／command／middleware 邊界上的產品差額：

1. Task／Duty／O／P／K／S 分析方法與 completion red-team rubric。
2. 哪個訪談工作最值得深入、何時暫時收束、何時因更正重開。
3. employee source 的可信度、逐字 quote／position anchor、source dependency 與選擇性失效。
4. 待審 patch 的文件 path、read-set、stable action ID、dependency、必要原子子群組與 rejected/stale reason。
5. 什麼情況是一般 Gap、soft calibration、branch-blocking calibration 或 required clarification。
6. 核准文件 invariant、iCAP 代碼權限、OPKS 關係與 deterministic／force export 規則。
7. 員工畫面要如何區分 AI 理解、待審變更、核准內容與 local dirty draft。

一般 agent／workflow framework 沒有 Caliburn 的職務分析與 iCAP 業務語意；若刪掉這些 policy，只會得到一個可持久化的聊天 Agent，不會得到專業職務顧問。

## 5. 已研究但刻意不採用的成熟元件

- LangChain `TodoListMiddleware`：適合單一 run 的簡易 todo，不具跨回合 stable identity、dependency、blocked／defer／reopen 與 correction lineage，不能冒充可信訪談進度。
- LangChain `HumanInTheLoopMiddleware`：適合暫停當前 tool call；不能直接表達可延後、多筆並存、任意順序決策且訪談可繼續的文件 changeset。只在 required clarification 使用 LangGraph interrupt。
- LangChain `LLMToolSelectorMiddleware`：本輪 deterministic eligibility 已先把 Skill／tool surface 縮小，再花一次 inference 選 tool 沒有已知效果收益。
- `ModelFallbackMiddleware`：預設不啟用，避免 silent model drift；日後只有 versioned allowlist＋完整 attempt receipt 才能開。
- 完整 `create_deep_agent`：會帶入 subagent、廣泛 filesystem、shell、todo 與自由長任務 harness；本產品只取 `SkillsMiddleware` 與只暴露 `read_file` 的 `FilesystemMiddleware`。
- Agent Server／LangSmith 服務：本機單一操作者不需要第二個 runtime service；使用 FastAPI SSE 與本機 OpenTelemetry。
- DBOS／Camunda／Microsoft Agent Framework／另一套 memory framework：四個核心目的已由 LangGraph conformance 通過，再加入會形成第二個 workflow owner。
- RAG／Reference：owner 明確延後，不是框架缺口。

## 6. 施工前風險與已加的 gate

1. `langgraph-checkpoint-postgres` 3.1.2 精確 pin；啟用 strict msgpack／allowlist、idempotent `.setup()`、正確 psycopg connection options 與 UUID namespace isolation tests。
2. Deep Agents 0.7.5 與 `langchain-openrouter` 0.2.7 仍標示 Beta；只使用窄 public API，Task 1 加 import／behavior canary。`SkillsMiddleware` 不會自己提供全文讀取工具，故明確搭配 `FilesystemMiddleware(tools=["read_file"])`；production backend 只允許版本化 `/skills` package resources，不能因此接入完整 harness 或 host filesystem。
3. FastAPI 0.141.1 先跑完整 API compatibility gate；不相容只回退 FastAPI，不引入第二個 agent server。
4. `SummarizationMiddleware`／`ContextEditingMiddleware` 不得成為 authority；來源、更正、矛盾與核准文件 slice 必須由 ID 重載。
5. 每個功能一律先寫行為測試，再實作、跑 focused/full gate、做本帳本北極星回歸，最後才 commit。

## 7. 逐 Task 北極星紀錄

每筆至少記錄：commit、員工效果、成熟 primitive、剩餘薄 policy、退出／尚未退出的舊機制、測試證據、RAG／LLM scope／authority／自然續談檢查，以及 `Pass`／`Stop and discuss`。

### Task 0：施工前詳細審核

- 狀態：**Pass**
- 產品方向：§2 全數符合；RAG、能力級別／A model generation、eval 仍明確延後。
- 框架覆蓋：§3 所列通用機制均有成熟 primitive；§4 只剩框架無法知道的職務分析與 authority policy。
- 修正：施工計畫補入 built-in retry／limits／structured output、非權威 context 壓縮、OpenTelemetry、checkpointer security/setup、Beta canary、方法 conformance tests，以及每 Task 回歸 gate。
- 機制回歸：`UV_CACHE_DIR=S:\caliburn\.uv-cache-langgraph-spike uv run --offline --with langgraph==1.2.11 pytest tests/test_consultant_purpose_conformance_spike.py -q` → `4 passed in 0.92s`；只重驗動態工作／更正、非阻塞 review queue 與 required clarification，不是模型品質 eval。
- production worktree 基線：API `723 passed, 104 skipped`（未設定 PostgreSQL test URL）；Web `60 passed`、TypeScript、ESLint 全綠；contract codegen zero diff。首次命令暴露 `DEBUG=release` 與 sandbox temp/cache 權限，明確設 `DEBUG=false`、repo-scoped cache／basetemp 後重跑通過，沒有把環境錯誤當產品綠燈。
- owner decision：2026-08-14 明確表示審核通過即可開始；ADR 0060 因此 Accepted。

### Task 1：框架版本與 transport 相容性

- 狀態：**Pass**；同一 task commit 為 `build: add consultant runtime framework stack`。
- 員工效果：本 Task 不改顧問流程與文件內容，只建立後續 durable snapshot 所需的 FastAPI 原生 typed SSE，以及可替換 model／workflow／Skill 的鎖定框架底座。
- 成熟 primitive：FastAPI `EventSourceResponse`／`ServerSentEvent`、LangChain 1.3.15、LangGraph 1.2.11、PostgreSQL checkpoint package 3.1.2、`ChatOpenRouter`、Deep Agents `SkillsMiddleware`＋只讀 `FilesystemMiddleware`。沒有建立自寫 SSE parser、agent loop 或 Skill lifecycle。
- 實作中修正：resolver 證明 `langchain-openrouter` 需要 HTTPX ≥0.28.1，故明確 pin 0.28.1；`SkillsMiddleware` 只注入 metadata／提示而不提供全文讀取工具，故補成只暴露 `read_file` 的正式組合；FastAPI 0.141 對 included router 採 lazy representation，wiring test 改驗公開 OpenAPI 路由契約，實際 18 條 current routes 均存在。
- Beta 安全面：canary 的完整 tool set 僅 `{read_file}`；沒有 `execute`、write／edit／delete、subagent `task` 或 `write_todos`。Task 4 仍須實作 traversal-safe package-resource backend，不能使用 host `FilesystemBackend`。
- 既有機制：尚未接入 production composition root，也尚未刪除舊 writer；這符合 Task 1 僅建底座的界線，Task 2 才建立唯一 durable state owner。
- TDD／驗證：舊 FastAPI 先如預期因 `ModuleNotFoundError: fastapi.sse` 失敗；升級後 Task 1 canary `5 passed`，加 wiring regression 為 `8 passed`；無 DB 全套 `728 passed, 104 skipped`；新建並 migration 專用 `caliburn_consultant_runtime_test` 後，含 PostgreSQL 全套 `832 passed`；`git diff --check` clean。鎖檔與 runtime metadata 均精確回報核准版本。
- 北極星回歸：沒有 RAG／Reference、能力級別／A model generation、品質 eval、pause／finish、silent fallback、第二個 workflow owner 或 AI 直寫核准文件；自然續談與 authority 行為未更動。結果 **Pass**。

### Task 2：framework-owned durable source 與文件狀態

- 狀態：**Pass**；同一 task commit 為 `feat: establish durable consultant state`。
- 員工效果：本 Task 尚未切 production route／Web，因此沒有假裝已交付完整訪談 UI；它先保證日後員工送出的原話、更正與 direct edit 可在 process 重啟後精確恢復，模型失敗不必要求重打，且核准文件只有 authority graph command 能改。
- 成熟 primitive：LangGraph `StateGraph`＋`AsyncPostgresSaver` 直接持有唯一 semantic checkpoint；`AsyncPostgresStore` 直接持有完整 employee source；Pydantic 驗 durable schema；Alembic 管最小 catalog schema。沒有另寫 checkpoint engine、event store、第二份 artifact table、ORM mirror 或舊 writer adapter。
- Caliburn 薄政策：只補 framework 不知道的 employee-only source kind、exact-text hash、修正 supersession、quote／position anchor、同文件 evidence lookup、document invariant、stable UUID namespace、semantic revision、單 process admission、Store→checkpoint→committed crash reconciliation、direct-edit 員工文字欄位白名單與 tombstone／namespace cleanup。
- 詳細複審修正：原先 generic direct-edit diff 會把 UUID／enum 誤存成員工原話，已改成只擷取允許的員工文字欄位；employee turn／quote 不再 trim；未知或跨文件 OPKS evidence ID 在寫 source 前拒絕；catalog 改用 Alembic `create_table`／具名 constraint／index，且 semantic revision 會更新 `updated_at`。這些都是來源權威修正，不是新增舊元件。
- 框架邊界：production foundation 直接 import LangGraph graph／Saver／Store，AST guard 證明沒有 import 舊 `core`／`documents`／`task_analysis`／`opks`／`consultation` writers、舊 OpenRouter adapter或任何 RAG package；target state channel 也沒有舊 Work Model／Focus／Progress／Proposal／Current JD 名稱。
- 尚未誤稱已完成：`interview_work`、`understanding`、`gaps`、`review_queue` 與 run receipt 目前只是 durable channel/schema foundation，尚無模型或員工面功能；Task 3–6 必須各自把 context、Skills、routing、typed patch action／read-set／review command 做完。當前 generic changeset action payload 不可接 production，Task 6 的 typed contract gate 仍有效。
- TDD／驗證：最初以缺少 `app.adapters.langgraph` 呈現預期紅燈；複審又分別以缺少 evidence error、catalog `updated_at` 不變、原話／quote 被 trim 呈現紅燈。修正後 focused foundation／PostgreSQL suite 為 `17 passed`；含 migration cycle 的完整 API 為 `849 passed`。全新空 DB 由 Alembic 升到 0018，再由官方 Saver／Store `.setup()` 建 framework tables；catalog 有預期 PK／unique／check constraints 與 updated index。測試後專用 DB 的 catalog、consultant Store rows 與 checkpoints 均為 0；一次性 fresh DB 已刪除。
- 北極星回歸：沒有模型呼叫、RAG／Reference、Skill、能力級別／A 生成、pause／finish、品質 eval、舊 writer bridge、雙寫或第二 authority。員工原話與核准文件仍是不同 owner；direct edit 是員工 authority，不經 LLM review。結果 **Pass**。

### Task 3：可替換模型執行與最小充分 Context

- 狀態：**Pass**；同一 task commit 為 `feat: add consultant model and context runtime`。
- 員工效果：本 Task 尚未開放 production 對話，但已建立之後每次訪談都會共用的安全底座：維護者可用 versioned profile 換 model／provider／參數；每個實際 provider attempt 都有 route／usage／cost／latency／error receipt；模型每次只取得整份工作方向、當前焦點、必要澄清、具體 Gap、待審 handles 與本輪所需原話，不把全部歷史 transcript 反覆送出。
- 成熟 primitive：`ChatOpenRouter` 承接 wire；LangChain `create_agent`／`response_format` 承接 agent loop 與 structured output；`ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、`ModelRetryMiddleware`、`ToolRetryMiddleware`、`SummarizationMiddleware`、`ContextEditingMiddleware` 承接通用控制；LangChain callback＋既有 OpenTelemetry 承接 attempt observability；LangGraph Store／Saver 是 Context 唯一來源。沒有重寫 provider client、通用 retry loop、摘要器、tool-result compactor 或第二份 memory／Context store。
- Caliburn 薄政策：只保留框架不知道的單一 route／no-silent-fallback、可重試錯誤集合、run budget、來源 current／superseded 規則、required evidence、焦點核准 slice、necessary clarification、global orientation、同文件 lookup scope、明確降級順序與 payload-free selection receipt。
- 複審抓到並修正：原版把非權威 dialogue summary 一律丟掉、完全漏掉 required clarification、tool loop 第二次推論會把員工回答追加到 ToolMessage 後、LangChain 摘要可能移除 tagged source 而讓下一次推論失敗、每次模型 callback 會洩漏一個未結束 span、原始 provider exception 可能把員工內容帶進 telemetry、successful receipt 可缺 route／usage／cost、agent 可傳入 policy 外工具、把歷史中所有有效更正全文與所有 source ID 每輪載入，以及 `SummarizationMiddleware` 會暗中建立自己的三次 retry chain。現在 summary 在有預算時保留但明標非證據；necessary clarification 必帶；checkpoint 只留 source-ID placeholder，逐字本輪來源每次由 Store 重建；每個 primary／summarization／retry actual call 各一張 receipt／一個 span；錯誤只存安全分類；tool／metadata eligibility fail closed；框架的獨立摘要 retry 關閉；只有本輪＋required evidence 必帶，近期候選依預算加入，舊來源由同文件 search 按需找回。
- Context 成本／記憶邊界：完整員工原話與 correction lineage 永久留在 `AsyncPostgresStore`；`ContextSelectionReceipt` 不含文字。無關更正的全文與 ID 都不再每輪傳給模型，但仍可由同文件 lexical search 找到，再按 stable ID／lineage 取回。沒有配置 semantic index、外部 corpus、iCAP Reference 或 ADR 0057 RAG consumer。
- TDD／驗證：新增缺口都先以失敗測試重現；最終 model＋Context focused suite `17 passed`，其中涵蓋實際 LangChain retry 產生兩張 attempt receipt、摘要＋主推論各自有 receipt 且摘要無 hidden retry、OpenRouter route／cost round-trip、policy 外 tool 拒絕、payload-free provider error、摘要後重建逐字來源、必要澄清、summary 權限、tool-loop 訊息順序、無關更正不入 prompt 與 context 降級。最終含 PostgreSQL 的完整 API suite `866 passed`；沒有執行真實 LLM，也沒有宣稱模型品質。
- 舊機制狀態：本 Task 新 runtime 沒有呼叫舊 OpenRouter wire、舊 ContextPacket、舊 operation／Proposal writer 或 RAG；production composition 尚未切換，故舊模組會到 Task 9 hard cut 才刪除，不雙寫。
- 北極星回歸：單一顧問、自然停止／續談、LLM 文件內容先審核、能力級別／A 暫不生成、RAG 延後、正式 eval 延後、員工原話／核准文件權威與可強制匯出方向均未改。結果 **Pass**。

### Task 4：按需專業方法 Skills 與 typed semantic result

- 狀態：**Pass**；同一 task commit 為 `feat: add professional consultant skills`。
- 員工效果：同一位顧問可依當輪問題載入工作盤點、故事、Task、Duty、O、P、K、S 或 completion red-team 方法；員工仍只看到一段連貫回覆、可見理解／Gap／待審文件內容與至多一個主要問題。Task 不必先永久穩定，局部證據足夠時可同輪整理相關 OPKS，後續結構變動再重新驗證。
- 成熟 primitive：Deep Agents `SkillsMiddleware` 直接承接 metadata discovery／progressive disclosure，`FilesystemMiddleware(tools=["read_file"])` 直接承接模型全文讀取；LangChain `response_format`＋Pydantic 直接承接 structured output；既有 LangChain call／tool limit 續管總量。沒有自寫 prompt router、Skill parser、agent loop、host filesystem 工具或多 Agent harness。
- Caliburn 薄政策：只保留框架不知道的九種職務分析方法、當輪 eligibility、package-resource 路徑白名單、一次完整載入、lookup wave 定義、Task／Duty／OPKS 語意、employee source／quote requirement、可修改文件 path 與 anti-fabrication gate。typed output 使用 `UnderstandingChange`／`AttentionChange`／`VisibleGap`／`ReviewableDocumentChange` 等 purpose-first 名稱，不搬舊 Work Model／Focus／Progress／Proposal class 或相容層。
- 詳細複審修正：最初若直接使用框架預設 cache，前一輪 checkpoint 的 Skill metadata／ToolMessage 可能流進下一輪；現在互動 agent 不另擁有 checkpointer／Store，durable product graph只保存 semantic result／receipt，每次 run 依本輪 backend 強制重投影、清除 stale warning，並拒絕外部輸入夾帶舊 `read_file` ToolMessage。最初把兩次 lookup 限制套成「最多讀兩個 Skill」也會破壞多 Skill 組合；現在同一 model response 的平行 reads 算一波，三個以上 Skill 可在一波載入。backend 另拒絕 partial read、重複 read、traversal 與未選 Skill；結果 verifier 補上同文件 scope、實際 loaded Skill、nested payload、path／operation matching、O／P／K／S linkage 及可查核主張的 quote gate。A 從 model-facing enum 直接移除，不只依事後 verifier 擋。
- 方法回歸：九份 Skill 均有 eligibility、required evidence、outputs、gaps、anti-hallucination 與 reopen 規則。Story／Work Unit／Task 非一對一；Task 要有 action／object／meaningful outcome／current responsibility，工具／步驟／他人／過去／一次性不自動成 Task；Duty 可動態重組；O 可合法空白；P 必須可觀察且非人格；K 是名詞性、S 是應用動作，兩者皆為文件層多對多且須有 employee quote，不使用 `ability to`／「具備…之能力」或能力級別。
- Authority／範圍：`ConsultantResult` 沒有 `ApprovedJobDocument` 寫入欄位；模型只輸出待員工審核的語意變更，Task 6 才建立 stable patch action／read-set／decision command。沒有 Reference／RAG Skill、能力級別、A、分類／iCAP code、pause／finish、正式品質 eval、舊 writer bridge或 production composition 切換。
- TDD／驗證：預期紅燈先由缺少 `app.consultant.agent` 呈現；最終 Task 4 focused suite `33 passed`；上一輪 consultant foundation 組合 gate `53 passed, 17 skipped`（DB tests 在該次 focused command未注入 URL）；新增 stale Skill ToolMessage 防線後，指定既有隔離測試 DB `caliburn_consultant_runtime_test`、repo basetemp並在 sandbox 外重跑最終完整 API suite為 `899 passed`。較早的完整 command曾指到已不存在的 DB，另一次暴露 Windows sandbox tmp ACL；兩者均以正確 DB／隔離 basetemp重跑，未把環境錯誤當綠燈。`git diff --check` 於提交前另行重驗。
- 北極星回歸：一位顧問、前景單一焦點／背景全域吸收、Task／Duty／OPKS 動態演化、LLM 文件內容先審核、自然離開／續談、語意進度、單一可強制匯出，以及 RAG／能力級別／A／正式 eval 延後均未偏移。結果 **Pass**。

### Task 5：adaptive interview、可見理解與可信足夠性

- 狀態：**Pass**；同一 task commit 為 `feat: implement adaptive consultant interview`。
- 員工效果：首次進入可先看四句白話導航；顧問把完整回答整理成目前已知工作範圍，只維持一個清楚訪談重點並說明 why-now／還差什麼／下一步，旁支線索保持可見。員工可直接改談別題；Task、Duty、O／P／K／S 理解隨證據動態修訂。關頁或久後返回不需要 pause／resume／finish；同一 checkpoint 自然恢復。
- 成熟 primitive：LangGraph `StateGraph`／typed checkpoint／routing、`add_messages` reducer、`AsyncPostgresSaver` restart recovery 與既有 Store source lineage 直接承接跨回合狀態；Pydantic typed result／projection 承接 validation。沒有自寫 workflow engine、session manager、事件溯源器、Todo middleware wrapper、舊 Focus／Progress／Work Model store 或第二份 authority。
- Caliburn 薄政策：只保留框架不知道的職務訪談 priority、Task／Duty／OPKS work kind、source-dependent selective reopen、理解校準 trigger、branch dependency、Gap reason code、coverage／depth／employee-decision 投影與 sufficiency rubric。這些是產品語意，不是重寫 persistence／history／checkpoint 機制。
- 理解與校準：可修訂理解有 stable identity、version、source／work dependency 與 active／challenged／employee-confirmed／superseded／retired 生命週期。一般第一個焦點與低影響更新不跳卡；meaningful shift／long return／真正焦點切換為 soft card，contradiction／high-risk responsibility／structural premise 才只阻擋相依 branch。確認另記 employee source 且不動核准文件；later 不等於結束；direct correction 仍以新 employee source 進入。
- 進度與足夠性：進度只顯示「目前已知」coverage、每個工作範圍分軸的 Task／Duty／O／P／K／S depth、員工待決文件變更與具體 Gap。複審抓到 active Task 訪談曾錯把所有分析軸一起標成 interviewing、Task sufficient 曾錯把 Duty／OPKS 一起標成 sufficient；現已限定到實際 work kind，避免灌水。足夠性由 checkpoint 中可查的 work／blocking Gap／structural decision 證據與 LLM 理由／剩餘缺口／continuing benefit 共同產生；新 evidence 或 direct edit 使它立即待重算，不建立完成狀態。
- Context 複審修正：新版理解保存版本歷史後，舊 middleware 一度會把 superseded／retired 版本重新送入模型，而且 global orientation 只看核准 Duty／Task，漏掉訪談中新發現的工作範圍／假說；另缺少員工正在回答的上一個顧問問題。現在 global orientation 同時含 bounded work／current hypothesis／approved structure，細節只載 active／challenged 與焦點必要 slice，最近顧問回合最多兩筆並可降級為上一筆。完整來源仍在 Store，沒有把整段 transcript 每輪重送，也沒有接 RAG。
- TDD／驗證：行為紅燈先由缺少 `app.consultant.interview` 顯示；後續再用「首次焦點誤跳校準」「確認沒有來源 lineage」「深度多軸灌水」「superseded 理解進 prompt」「global index 漏工作範圍」「缺上一個顧問問題」逐項建立紅／綠回歸。focused consultant suite 為 `75 passed`；真正透過 PostgreSQL Saver 寫入 semantic result、關閉 runtime、重開後恢復 message／重點／理解／足夠性為 `1 passed`。完整 API 第一次因 sandbox basetemp `WinError 5` 無法完成 pytest session cleanup；改用新的 sandbox 外隔離 basetemp 重跑為 `907 passed`，不是沿用失敗結果。`git diff --check` 另於提交前重驗。
- 來源與裁決依據：產品語意沿用本研究稿 §3.1–§4.4、§7.2–§7.4、§7.9、§7.16 及 ADR 0060；外部機制依據仍是 LangGraph persistence／messages、LangChain context engineering、Google PAIR feedback／control、Microsoft multi-turn correction risk 與 OPM SME／job-analysis 原則。這些來源支持 durable state、可見控制、按需 context 與 SME 校準；職務分析 priority／OPKS linkage／足夠性 reason code 是 Caliburn 依既有研究作的 domain policy，未宣稱框架自動提供。
- 北極星回歸：一位主要顧問、先工作全貌再一個焦點、旁支保留、Task／Duty／OPKS 可反覆調整、AI 文件內容先審核、自然離開／續談、無假百分比、足夠性只是建議、單一可強制匯出，以及 RAG／能力級別／A／正式品質 eval 延後均未偏移。結果 **Pass**。

### Task 6：員工文件審核、結構依賴與必要澄清

- 狀態：**Pass**；同一 task commit 為 `feat: add employee document authority`。
- 員工效果：模型提出的職稱、工作描述、Duty、Task、排序、重新歸類與 O／P／K／S 內容都先進入可見審核；員工可逐項接受、修改後接受、拒絕或延後。無關項目不因同一 bundle 被綁死，真正不可拆的結構變更才原子處理。遇到只有員工能回答的重大歧義時顯示一個必要澄清；安全旁支、direct edit 與新來源仍可繼續。
- 成熟 primitive：LangGraph typed checkpoint／`StateGraph` command 直接承接持久化 review queue、決策與重啟後恢復；`interrupt()`／`Command(resume)` 直接承接必要澄清；Pydantic 直接驗 typed changeset／command。沒有建立舊 Proposal service、另一套 workflow engine、第二份文件 store 或自寫 pause／resume lifecycle。
- Caliburn 薄政策：只保留框架不知道的 stable document path、before／after、path read-set、來源／quote anchor、dependency、atomic subgroup、拒絕後新證據門檻、文件 invariant、員工可編輯欄位與 deterministic authority operation。`ApprovedJobDocument` 是新 graph state 的核准產物，不是舊 Current JD 相容 adapter。
- 詳細複審修正：審核決策原先可能誤清必要澄清／校準 blocker；atomic subgroup 一員 stale 時其餘成員未連帶 stale；OPKS payload 可偽裝 A；merge／split path 與 authority 不一致；一般 revise 可繞過 reassignment／reorder；既有必要澄清可能被安全新回合洗掉；來源更正未 selective-stale 相依 action且可能誤解鎖其他 blocker；一般 dependency 被錯升成 atomic；responsibility-role／withdraw 結構影響漏判；非法 edit-accept 可能在文件未提交時製造 evidence；同來源的 K／S rejection key 互相碰撞；既有 A item 可被偽裝成 K／S revise。上述均已以 deterministic gate 與回歸測試修正。
- 互動邊界：required clarification 的 answer 只建立員工 evidence，不接受文件變更；未回答的 request 不得被下一輪模型取代。accept／reject／defer 不製造工作事實，edit-accept 與 direct edit 只為員工實際改寫的 delta 建 source。結構決策只阻擋 affected work，決策後重驗 downstream gap／linkage；員工離開仍只是停止傳訊息，下次從 checkpoint 自然繼續。
- 範圍防線：model-facing patch 支援 job title／work description／Duty／Task／order／reassignment／O／P／K／S；能力級別、A 與官方代碼被 deterministic verifier 拒絕。沒有接 RAG／Reference、正式 eval、production route／Web 或舊 writer bridge。
- TDD／驗證：Task 6 focused consultant suite 為 `129 passed`，另有 foundation boundary canary `3 passed`；完整 PostgreSQL API gate 為 `936 passed`。第一次完整命令與後續 `-x` 診斷都在 pytest session cleanup 遭遇 sandbox 建立之 Windows basetemp `WinError 5`，其中第一個受影響的臨時 package 測試在正常 Windows 暫存環境單獨為 `1 passed`；同環境重跑全套才取得上述 `936 passed`，沒有把 ACL 中止當產品結果。Python compileall 與 `git diff --check` 於提交前另行重驗。
- 北極星回歸：單一顧問、動態 Task／Duty／OPKS、員工文件 authority、一般 Gap 與 required clarification 分流、自然離開／續談、無假完成狀態，以及 RAG／能力級別／A／正式 eval 延後均未偏移。結果 **Pass**。

### Task 7：跨語言契約與 production API transport

- 狀態：**Pass**；預定同一 task commit 為 `feat: expose consultant runtime contract`。
- 員工效果：新 API 已能建立／讀取／刪除文件、先保存回答再非同步處理、重開 durable snapshot、審核或修改後接受文件 changeset、理解校準、回答必要澄清、直接編輯，以及從同一入口查看缺口後明確強制匯出。沒有 pause／finish endpoint；員工停止傳訊息、關頁與日後重開仍是自然離開／續談。
- 成熟 primitive：JSON Schema codegen 直接產生 Pydantic／TypeScript contract；FastAPI lifespan 持有 application-scoped runtime，native `EventSourceResponse` 只送 refetch event；LangGraph Saver／Store／checkpoint command／interrupt 直接持有 durable snapshot、source-first run、authority command 與 restart；LangChain agent 已真正註冊同文件 source lookup tools、middleware、structured output 與 callback。沒有自寫第二套 event state、session manager、provider wire、workflow table 或 agent loop。
- Caliburn 薄政策：API mapper 只做產品 view projection；canonical payload hash、document scope、employee authority、source／quote、readiness、force-export 與 deterministic XLSX mapping 是通用框架不知道的產品差額。command receipt 與 authority update 同存一個 LangGraph checkpoint，不另建 idempotency table。
- 詳細複審修正：查到 source lookup 雖已實作卻未接到 production agent tool surface；request-local runtime 會讓同文件 lock 失效；run service 直接 import OpenRouter 破壞 composition boundary；Store-before-checkpoint 與 checkpoint-before-Store-status 兩個 crash window 未完整 reconcile；resolved execution／Context selection／attempt receipt 驗完後被丟棄；非對話 authority command 只靠 revision，無 payload-bound durable replay；新 route 未列入依賴 guard。Task 8 接線前又查到 codegen 後處理會誤刪 review edit map 的 `unknown` index signature，已把 schema 改成明列 JSON value union，讓 Python 與 TypeScript 都保留可編輯 payload 型別並補回歸測試。以上均已補 wiring、red／green regression 與完整 gate。
- Idempotency：document create 以 title 綁 key，answer 以 immutable source payload 綁 key；review／calibration／clarification／direct edit 以 stable command ID＋kind＋canonical payload hash 寫 checkpoint receipt。精確重送可帶舊 revision 成功返回；同 key 換 payload 回 409，且 direct-edit／confirm source 在 checkpoint 後 crash 可只補 committed status。
- 邊界誠實性：新 route 使用 purpose-first DTO，沒有把 raw graph state、Context receipt 或 model attempt 暴露給 Web。為了 Task 8 垂直切片，舊 route／舊 contract definitions 暫時仍在 repo，但新舊不雙寫、沒有 compatibility alias；Task 9 必須同一 hard-cut commit 刪除，否則最終 gate 不通過。
- 驗證：contract `18 passed`；codegen 前後 Python／TypeScript SHA-256 完全相同；consultant 群 `146 passed`；sandbox 外完整 PostgreSQL API gate `953 passed`。第一次完整 gate 的唯一 assertion 是 route allowlist 尚未加入 `consultant.py`，已修正；其餘 error 為 Windows pytest temp ACL，改用已確認的 sandbox 外 basetemp 重跑取得完整綠燈。compileall 與 `git diff --check` 另行通過。
- 北極星回歸：一位顧問、前景焦點／背景吸收、Task／Duty／OPKS 可動態修訂、AI 文件內容先審後入、必要澄清只擋相依 branch、可見 gap／可信進度、自然續談與單一可強制匯出均未偏移。九個方法 Skill 仍按需、能力級別／A 不由 LLM 生成，且 production tool／import／contract 沒有接入 RAG／Reference。結果 **Pass**。

## 8. 本次直接使用的一手來源

- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Deep Agents `SkillsMiddleware`](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware)
- [Deep Agents `FilesystemMiddleware`](https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware)
- [FastAPI Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [LangChain 1.3.15 PyPI](https://pypi.org/project/langchain/1.3.15/)
- [LangGraph 1.2.11 PyPI](https://pypi.org/project/langgraph/1.2.11/)
- [`langgraph-checkpoint-postgres` 3.1.2 PyPI／security setup](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/)
- [`langchain-openrouter` 0.2.7 PyPI](https://pypi.org/project/langchain-openrouter/0.2.7/)
- [Deep Agents 0.7.5 PyPI](https://pypi.org/project/deepagents/0.7.5/)
- [FastAPI 0.141.1 PyPI](https://pypi.org/project/fastapi/0.141.1/)
- [HTTPX 0.28.1 PyPI](https://pypi.org/project/httpx/0.28.1/)
