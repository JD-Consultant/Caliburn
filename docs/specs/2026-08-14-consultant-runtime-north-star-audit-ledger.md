# AI 職務顧問 runtime：北極星審核與逐 Task 防偏帳本

- 日期：2026-08-14
- 狀態：Pre-implementation audit **Passed**；Tasks 1–9 **Passed**；Task 10 schema-only 修正與 Task 11 Tool surface 已通過完整 deterministic gates，paid live canary／最終產品交付仍待另行授權與後續
- 決策：ADR 0060 **Accepted**；ADR 0061 **Accepted（schema-only）**；ADR 0062 **Accepted（四個受限唯讀 Tool）**
- 施工計畫：[`2026-08-13-langgraph-consultant-runtime-big-bang-plan.md`](../plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md)
- 產品 SSOT：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §1–§8、§9.12–§9.16

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
| bounded consultant loop＋按需工具 | LangChain `create_agent`＋Deep Agents Skills／Filesystem middleware＋三個 LangChain source tools | document scope、lookup wave、總 budget、typed availability | **已實作**；四個唯讀 Tool、精簡 description、application-bound args 與依賴驅動 lookup 依 ADR 0062 |
| compact model-facing result | Pydantic compact DTO＋LangChain structured output | 職務語意、pure mapper 的 fail-closed 規則 | **已實作**；LangChain-facing schema 為 0 optional／0 union／0 open object、depth 4，rich framework state 不直接送 provider |
| contingency finalization | 只在 exact canary 失敗時使用 LangChain tool-free `response_format` | 同 run handoff 與三次總上限 | 非預設；未證實需要前不增加 node／call |
| call limit／retry | `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、`ModelRetryMiddleware`、`ToolRetryMiddleware` | 哪些錯可重試、idempotency、每次 attempt receipt | 已覆蓋；plan 已補明 |
| durable execution／restart | LangGraph `StateGraph`＋`AsyncPostgresSaver` | node 的 deterministic／idempotent side-effect 邊界 | 已覆蓋 |
| 員工來源記憶 | LangGraph `AsyncPostgresStore` | employee-only source kind、validity、supersession、quote anchor | 已覆蓋 |
| citation transport／來源定位／lineage | LangChain `Citation`、W3C Web Annotation selectors、W3C PROV vocabulary | adapter conformance、source revision、speaker／document authority、語意支持判斷 | 通用形狀已覆蓋；原生 citation 非必要且不得成為第二份 evidence truth |
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
6. Task 10 真模型已證明完整 read tools＋約 10 KB minified `ConsultantResult` schema 同一 request 會撞 provider grammar complexity；當時曾推論 finalization 必須移除 Skill／source read tools。後續找回 compact-wire 實證並把 provider schema 降成 0 optional／0 union 後，這個「必須」已撤回：tool-free finalization 只是在 exact conformance 仍失敗時才評估的 contingency，不能在 Tool 討論前先施工。ToolStrategy 曾產生錯誤的多重輸出工具呼叫，所以 strategy 仍須由 versioned profile 依 conformance 明確選擇，不可自動 fallback。Anthropic citations 與 structured outputs 不相容，`langchain-openrouter==0.2.7` 也未保存 citation annotations，因此 native citation 只能在 conformance 後作選配，不能取代 provider-neutral quote anchor。

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

### Task 8：員工顧問工作區

- 狀態：**Pass**；預定同一 task commit 為 `feat: deliver consultant workspace`。
- 員工效果：文件庫可建立或重開職務分析；同一頁清楚分開訪談對話、目前焦點／理由、可收合的「AI 目前理解」、旁支線索、具體 Gap、Task／Duty／O／P／K／S 分軸進度、足夠性建議、必要澄清、AI 待審文件變更與員工核准正式文件。關頁不需 pause／finish；重新開啟可看到先前員工原話、顧問回覆與 durable saved／processing／failed 狀態。
- 成熟 primitive：Next.js 16 App Router／React 19 承接頁面與互動元件；TanStack Query 5 承接 revision-monotonic durable projection cache、mutation、失效與衝突後 refetch；瀏覽器 `EventSource` 承接自動重連，FastAPI SSE 只通知 refetch；JSON Schema codegen 承接 Python／TypeScript transport；標準 `localStorage`＋before-unload guard 承接 document-scoped、非權威的可恢復 local draft。沒有自寫 Web state store、SSE reconnect engine、framework checkpoint decoder或第二份 server 訪談／文件狀態。
- Caliburn 薄政策：只保留框架不知道的四種員工畫面邊界、外部 AI 告知文字、atomic subgroup／accept dependency 選取、dirty draft 衝突處理、職務文件欄位與 OPKS 關聯、具體 readiness gap 與 force-export 語意。Web 不重算 server authority，direct edit 仍由 API deterministic invariant 重驗。
- 第一輪詳細複審修正：原本 direct-edit write contract 沿用 view，會迫使瀏覽器提交或偽造 OPKS evidence ID；已拆出沒有 evidence 欄位的 `ApprovedOpksItemWrite`，由 server 對實際員工改寫鑄造來源。原 snapshot 只有顧問回覆，員工重開後看不到自己的原話；已加入只投影 employee-turn source 的 `EmployeeMessageView`。failed run 雖能在 runtime 原地重啟，Web 重開後卻沒有原 idempotency key；已新增 same-run／same-source retry command。直接編輯刪除 Task／indicator 後可能留下 K／S dangling relation；現於送出前 deterministic 清理且由 server 再驗。UI 另把 raw status／JSON pointer 改成員工白話，不顯示 technical revision。
- 第二輪獨立審查共確認六項缺口：失敗回答只能原樣 retry、不能明確更正；純結構 edit-accept 因 candidate source ID 被誤拒；延遲 mutation response 可讓 TanStack cache revision 倒退且 409 未可靠重抓；server 的 blocked-branch projection 未落到 UI；所謂 UI 測試只有純函式；直接編輯草稿可能因 App Router／browser Back 遺失。現已分別補成 `supersedes_source_id` correction admission、只有文字 delta 才鑄 evidence、單調 revision cache＋409 refetch、branch-level answer guard、真實 jsdom component integration tests，以及 document-scoped browser-local recoverable draft。另將結構化審核的 raw JSON textarea 換成 Duty／Task／OPKS 員工欄位；UUID、source、evidence 與 system order 不顯示且原樣保存，重新歸類／排序仍能 typed edit-accept。
- 第三輪窄複審又確認兩項缺口：欄位級 `enablers`／`task_ids`／`indicator_ids` 曾被誤當 entity 或文字，且 failed run 的一般回答只由 server 擋、UI 仍可誤送。現已依完整 path 深度分流為專用 editor／preview，並在 failed 時只開放 retry 或更正 failed source；無關回答與其他來源更正先停用並說明原因。相同審查者再次逐項複核後回報 clean，未留 P1／P2。
- 自然續談與 authority：`source_saved` 時第二則 AI 回答被擋，但 read／review／direct edit／export 仍可用；required clarification 只標 affected branch且不 modal-lock 回答區。AI changeset 支援 accept、edit-accept、reject、defer，多 bundle 可並存；只有 accept／edit-accept 改核准文件。能力級別與 A 只在員工直接 editor 中存在，沒有 model-facing path。
- 實際啟動煙霧：以正式 `run_live.py` 在 Windows Selector loop 啟動 API，`/healthz` 回 `db=true`；Next `/workspace` 回 200。使用獨立 PostgreSQL DB 實際建立／重開文件、直接改核准內容、一般匯出取得 409 gap confirmation、`force=true` 取得 200 XLSX（6114 bytes），全程未送出模型回答。in-app browser 當時沒有任何可連線 browser instance，故沒有把視覺點擊假稱已驗；Task 10 的真模型／真 UI smoke 仍保留。
- TDD／驗證：修正後 Web `12 files／82 passed`、`npx tsc --noEmit`、ESLint 全綠；component suite 實際涵蓋 SSE lifecycle、branch blocker、force export、draft 離開／返回、delayed response、409 conflict、failed-source correction、結構化 Duty edit-accept，以及 field-level 關聯／enabler request 型別。contract `19 passed`；正式 codegen 的 Python／TypeScript 生成物連續重跑 SHA-256 不變。獨立 Windows temp 下完整 PostgreSQL API `958 passed`；工作區內首次重跑雖執行到 100%，但 pytest session 收尾被 Windows ACL 阻擋，因此沒有冒充通過，改用 sandbox 外隔離 temp 取得可信綠燈。`next build` 在進入產品編譯前因 sandbox 阻止 Next SWC lock repair且 `next/font` 無法連 Google Fonts而中止，未列為通過，也未讓自動 lockfile repair 混入變更。
- 舊機制誠實性：新 App Router 頁面只掛載 `features/consultant`，但舊 `_components`、舊 route／contract／writer 仍暫留 repo，沒有被新頁面引用也不雙寫。Task 9 必須 hard cut 刪除並以 AST／`rg`／fresh-root migration 證明關閉；Task 8 不能提前宣稱 Big-bang 完成。
- 北極星回歸：一位顧問、前景焦點／背景吸收、Task／Duty／OPKS 動態演化、員工原話記憶、AI 文件先審後入、澄清／Gap／審核分流、可信語意進度、自然離開／續談與單一可強制匯出均符合。沒有 RAG／Reference consumer、能力級別／A 生成、multi-agent、假百分比、pause／finish、第二 authority或 framework internals UI。結果 **Pass**。

### Task 9：唯一匯出、舊機制 hard cut 與 fresh-root 切換

- 狀態：**Pass**；預定同一 task commit 為 `refactor: hard-cut to consultant runtime`。
- 員工效果：產品現在只有一個匯出入口；有具體 readiness gap 時先回 409 並顯示問題，員工明確確認 `force=true` 後仍可取得目前核准內容。匯出只讀 `ApprovedJobDocument`，不接受、混入或暗示 pending changeset；未分 Duty 的 Task 仍出現在正式 Task 欄且 Duty 留白。
- 匯出政策：新的 frozen Pydantic export model 是 renderer-neutral projection，OpenPyXL 只負責公版 XLSX。Duty／Task 依 display order＋stable ID 決定代碼；O／P 保持 Task 層，K／S 只建立一組文件層 stable code 再多對多投影到相依 Task；O 可空白。員工直接維護的能力級別、A 與職類／職業／行業名稱保留；模型不能生成這些欄位，官方 iCAP code cells 固定留白。員工輸入一律寫成 string cell，公式形狀文字不會被 XLSX 執行。
- 成熟 primitive 與薄政策：LangGraph Saver／Store 仍是 semantic state／員工原話唯一 owner，JSON Schema codegen 仍是跨語言契約 owner，Pydantic 承接 export shape，OpenPyXL 承接 renderer。Caliburn 只保留框架不知道的 iCAP 欄位權限、OPKS linkage、deterministic position code、孤立 Task 可見性與 force-export 規則；沒有重建第二個 Work Model、Focus、Progress、Proposal、Current JD、workflow、memory 或 document store。
- hard cut：production filesystem 只剩 `app/consultant`、`adapters/langgraph`、`adapters/openrouter`、`export`／`adapters/xlsx` 與 `api`。舊 `app.core`、`documents`、`task_analysis`、`opks`、`consultation`、`models`、`adapters.postgres`、舊 OpenRouter wire、routes／mappers／scripts、舊 Web features、舊 contract definitions 與對應 tests 已刪除；沒有 compatibility alias、雙寫或舊 table writer。AST、schema、migration 與 import canary 為 `21 passed`；混合目錄殘留的舊 `.pyc`／`__pycache__` 已在驗證根路徑後清除，重跑後確認零 legacy bytecode。
- fresh root：Alembic 只保留 `0018_consultant_runtime_root.py`，`down_revision=None`，只建立最小 `consultant_documents` catalog。另在全新 `caliburn_consultant_fresh_root_20260814_task9` 實跑 Alembic＋官方 `consultant-storage:setup`，public schema 精確只有 `alembic_version`、`consultant_documents`、Saver 的 `checkpoint_blobs`／`checkpoint_migrations`／`checkpoint_writes`／`checkpoints` 與 Store 的 `store`／`store_migrations`；沒有舊 Job Analysis table，驗證後刪除一次性 DB。舊本機 DB 不作成功證據，也不提供 migration／converter。
- 文件與邊界：`AGENTS.md`、`ARCHITECTURE.md`、API／Web README、runbook、contract README 與 active design 已同步 ADR 0060；自審另抓到並修正 active design 開頭仍宣稱 hard cut 未完成，以及 `AGENTS.md` 權威順序漏列 ADR 0060。ADR 0057 的 RAG bounded context 仍只保留在 monorepo，current API／Web／contract 沒有 RAG import、HTTP consumer、route、tool、compose default 或 UI hook；同文件原話 lookup 不是外部 RAG。
- 獨立複審：只讀 reviewer 依 ADR 0060、active design、Task 9、新 export／migration／hard-cut guard 與 current tree 檢查北極星、成熟 primitive、唯一 authority、匯出與零 RAG。它最初把 `Path(__file__).resolve().parents[3]` 誤讀為 `API_ROOT.parents[3]` 並回報 guard 可能指向外層 checkout；主審依實際 expression 重算後要求複核，reviewer 正式撤回，確認 root 正是目前 worktree。除此之外沒有已確認 P1／P2；未為假 finding 製造無效修改。
- 驗證：含真 PostgreSQL 的完整 API `169 passed`；Web `5 files／27 passed`、TypeScript、ESLint 全綠；contract `8 passed`；正式 codegen 連續重跑 SHA-256 不變；`npx turbo test --env-mode=loose --output-logs=errors-only --force` 為 `5 successful／0 cached`；`git diff --check` clean。fresh-root table 證據與上述 gate 分開取得，沒有用 cached Turbo 取代 API／Web／contract 實跑。
- 北極星回歸：一位自適應專業顧問、員工原話記憶、前景焦點／背景吸收、Task／Duty／OPKS 動態演化、AI 文件先審後入、必要澄清／Gap／審核分流、可信語意進度、自然離開／續談及單一可強制匯出均未偏移。能力級別／A 仍僅員工直接編輯，RAG／Reference、正式品質 eval、multi-agent、pause／finish、假百分比與第二 authority 均未引入。結果 **Pass**。

### Task 10：真模型 smoke 診斷與施工前再次回歸

- 狀態：**Stop and correct confirmed P1；schema mechanism corrected**。產品北極星未退回；owner 已核准 ADR 0061 的 schema-only 範圍，Task 10 的 Tool／live canary／最終交付尚未完成。
- 真實觀察：現行 `create_agent` 同一 request 同時帶 Skill／source tools 與完整 `ConsultantResult` strict schema。schema 約 `10,317 bytes`，離線量測為 18 defs、68 object properties、**28 optional、20 union／`anyOf` sites、最深約 15 層**；在不計 tools 前已超過 Anthropic 公開的 24 optional／16 union 合併上限。真模型在生成 token 前拒絕；ToolStrategy 另產生錯誤的多重輸出工具呼叫。byte 數不是通用閾值。
- 補回的 repo 證據：2026-07-31 同類錯誤已用 compact provider wire＋pure mapper 修正；union 17→0、properties 54→32、nesting 9→6、wire 6,818→4,084 bytes 後 Opus 5 真 request HTTP 200，後續三個模型的三回合場景完成。前一輪只看到 tool-free rich-schema 成功就直接選兩段式，漏掉這份較直接的既有證據。
- 當時 Proposed 修正同時混合 schema 與 Tool／Skill 排程。owner 後續明確收斂為「先解 schema，Tool 之後討論」；因此本輪只落 compact provider DTO＋pure mapper，未更改工具集合、Tool Search、selector、provider beta、`read_file` contract 或 lookup wave 排程。
- Evidence 複核：LangGraph Store、LangChain `Citation`、W3C selectors／PROV、Pydantic、LangChain callbacks／OpenTelemetry與 LangGraph command 已分別承接 persistence、citation transport、anchor／lineage shape、typed validation、execution evidence與 review durability。Caliburn 只留 employee authority、correction、document scope、exact quote與「引文是否支持 Task／Duty／OPKS」政策。Anthropic native citations 與 structured output 不相容，且目前 OpenRouter adapter不保留 annotations，因此不列第一版核心依賴、不提前接 RAG。
- schema 實作：新增 Pydantic `ConsultantModelOutput`，所有欄位 required；文件候選由 typed target／stable ID／field／fixed payload 表達，不再暴露自由 JSON Pointer／任意 `after`。employee source／quote／Skill basis 正規化成單一 `analysis_bases` 表，以 1-based ordinal 引用；越界、未引用、sentinel／payload、application-owned ID 與 OPKS linkage 矛盾皆 fail closed。pure mapper 還原完整 `ConsultantResult` 後，既有 deterministic verifier／authority seam 繼續執行。
- schema 證據：LangChain 實際轉換後量測為 **0 optional、0 union、0 open object、object depth 4、約 9,754 minified bytes**；bytes 只記錄粗略訊號，不作 provider 上限。compact schema／mapper、LangChain conversion、agent wiring、model runtime 與 run-service focused suite 為 `86 passed`；完整 `test_consultant*.py` 面為 `137 passed, 26 skipped`（未注入 PostgreSQL URL 的 durable tests 依既有條件跳過）。付費 Opus 5 canary 未獲本輪授權、未執行。
- 北極星回歸：一位顧問、動態 Task／Duty／OPKS、員工原話記憶、文件先審後入、必要澄清／Gap／審核分流、自然續談、可信進度、單一強制匯出、能力級別／A／RAG／eval 延後均未改。判定是**provider contract 形狀修正，無產品偏移**；Tool／Skill loading 應另議，不得從 schema 接線推定已核准。

### Task 11：Tool surface 正式裁決、實作與北極星回歸

- 狀態：**Pass（完整 deterministic gates）**。owner 在 schema-only ADR 0061 完成後，另行核准依最新主流 Tool Calling 做法直接施工；決策記於 ADR 0062，沒有事後改寫 ADR 0060／0061。
- 官方共識：OpenAI、Anthropic、Google 都把 Tool Calling 用於外部資料、系統或動作，把 typed final response 留給 Structured Output；LangChain 對應為 Tool／middleware 與 provider-native response format。Anthropic 強調少量高價值、目的清楚、回傳高訊號且受限的 Tool，Google 建議清楚名稱與強型別，OpenAI 建議不要讓模型填 application 已知參數。
- Tool Search 更正：先前「約 10 個 Tool 就建議」不是官方通用門檻。Anthropic 目前以數百至數千 Tool catalog 為主要情境，並指出選擇品質常在約 30–50 個才開始下降；OpenAI Tool Search 亦有大型 namespace 與 model/provider 前提。現行四個 Tool 不啟用 Tool Search、MCP catalog、dynamic LLM selector 或 provider beta。
- 正式 surface：`read_file`、`employee_source_get`、`employee_source_lineage`、`employee_source_search`。全部唯讀且 document-scoped；application 注入 document ID、權限與搜尋上限。source payload 保留 stable ID、exact text、speaker、validity、timestamp 與 correction lineage。
- primitive 分工：ADD／REVISE／WITHDRAW／MERGE／SPLIT 等是 Structured Output 的 typed review draft，不是模型 write Tool；accept／edit-accept／reject／defer 是 employee authority command；必要澄清是 typed result＋LangGraph interrupt；Focus／Gap／Progress 是 durable graph state／projection。
- lookup 政策：context 足夠時零呼叫；獨立 Skill／source 可同波平行；只有前一結果產生新依賴才用第二波。保留三次 model call／兩波 lookup 的硬上限，不保留固定「先 Skill、後 Source」順序。
- 實作證據：source builder 的 TDD 紅燈先由缺少 `build_employee_source_tools` 呈現；加入新名稱、server-bound `limit=5`、speaker 與 correction metadata 後，真 PostgreSQL targeted `2 passed`，`context`＋`run_service` 回歸 `10 passed`。`read_file` description 的紅燈實際捕捉到 framework 通用 PDF／image／edit／pagination 文案；改用 `FilesystemMiddleware.custom_tool_descriptions` 後，agent＋model runtime 回歸 `56 passed`。沒有重寫 Tool loop 或 Skill loader。
- 完整 gates：Tool／Context／Agent／Model runtime targeted `66 passed`；真 PostgreSQL API `198 passed`；Web `5 files／27 passed`、TypeScript、ESLint；contract codegen clean；sandbox 外 Turbo `5 successful／0 cached`；`git diff --check` clean。首次 codegen／Turbo 分別因使用者全域 uv cache ACL 與 Vite child-process `spawn EPERM` 在進入 assertion 前中止，改綁 workspace cache並依規則在 sandbox 外重跑取得上述綠燈，沒有把環境中止假稱為通過。
- 差異稽核：production 只有三個 `@tool` source definitions 加 framework `read_file`；沒有舊 Tool ID、business write Tool、Tool Search、RAG 或模型可呼叫的 review command。Accepted ADR 0060 工作檔雖因 Windows line-ending stat 顯示 modified，但 working blob 與 `HEAD` SHA-1 同為 `2c065952649784218509dbac243a872f24399eec`，內容零差異且未 stage。
- 北極星回歸：這次只替換／收斂通用讀取機制，沒有把產品變成 Tool 操作台或多 Agent，也沒有改動動態 Task／Duty／OPKS、員工原話記憶、文件先審後入、澄清／Gap／審核分流、自然離開／續談與單一強制匯出。沒有接 RAG、能力級別／A 或正式 eval。最終判定 **Pass**。

### ADR 0063 Task 1：拆分 final wire 與候選編輯 wire

- 狀態：**Pass**；同一 task commit 為 `refactor: split consultant candidate wire`。
- 範圍：只將 shared provider evidence wire 抽至 `provider_wire`，並新增 strict `CandidateEditBatch`／同批 local ref resolver；final `ConsultantModelOutput` 的 mapping 行為維持不變。Duty、Task、O／P local ref 只在同一 replacement batch 內以 document ID 與 materialization run ID 的 UUID5 穩定解析；duplicate／unknown／跨批 ref、change dependency cycle／self dependency、非本批 dependency、非法 atomic group ref 與 ADD 偽造 UUID 全部 fail closed。
- Authority／北極星：沒有新增 agent Tool、approved-document write、RAG、A、UI、第二 authority、workflow 或文件 store；模型仍只提出待審候選，不能直接改變核准文件。單一顧問、動態 Task／Duty／OPKS、員工原話與先審後入方向均未偏移。結果 **Pass**。
- 驗證：candidate Tool input schema 為 0 defs、62 properties、depth 4、5,669 bytes、0 optional、0 union／`anyOf`、0 open object；bytes 僅作比較訊號，非 provider 官方上限。focused suite 為 `84 passed`。

### ADR 0063 Task 2：唯一 product graph 的 durable candidate workspace

- 狀態：**Pass**；同一 task commit 為 `feat: add durable consultant candidate workspace`。
- 員工效果：同一顧問 run 可在 LangGraph checkpoint 內反覆建立、替換並於 runtime reopen 後恢復候選文件；候選尚未發布時，核准文件、review queue、semantic revision、catalog `updated_at`、export 與一般 snapshot 完全不變。模型失敗後以相同 run 重試會保留最後成功候選；新來源／更正、direct edit 或任一員工 review decision 都會清除舊候選。
- 成熟 primitive：沿用唯一 `StateGraph` typed state／command／checkpoint、既有 `AsyncPostgresSaver` 與 `AsyncPostgresStore`，並在既有 per-document adapter lock 內重讀 checkpoint、驗證、映射與 `graph.ainvoke`。durable candidate 只是 framework checkpoint 的 run-scoped 暫存 channel，不是員工文件、第二份文件 authority、第二個 graph／Saver／Store、transaction table、event store 或 candidate table。
- Caliburn 薄政策：pure reducer 管 first／replacement revision、canonical changeset digest、payload-bound tool-call replay／conflict、stale base 與失敗不寫入；application 在 lock 內由 current approved document／明示 conditional baseline，以及 pending／deferred review dependency closure 推導 entity／action allowlists，再交給 strict candidate mapper，同批 local refs 仍只由 application 生成。未明列 dependency 時絕不混入 pending candidate。
- 依賴與審核：明示外部 action dependency 會建立完整、拓撲順序的 pending／deferred closure並套到核准文件 copy；不存在、rejected、stale、cycle 或無效 conditional baseline fail closed。local dependency、explicit atomic group、merge／split grouping 與 supersession metadata 進入既有 `DocumentChangeSet`／`DocumentPatchAction`；前置未核准時 dependent subgroup不能接受，前置 rejected／stale 使下游 stale，明確 superseded 的 unresolved action於後續 publication seam 原子標 stale並保留理由。
- Evidence：從既有 result verifier 抽出 candidate document path／payload／operation／OPKS linkage／source scope／current validity／exact quote anchor／selected-loaded Skill gate；adapter 只從既有 Store載入 batch basis引用的 committed employee sources。修正 extraction 時排除 application-owned UUID／display order等結構 metadata，仍只對真正語意文字執行數量、具名規範與外部主張的 quote 規則。
- TDD／驗證：初始 exact RED 因缺少 `app.consultant.candidate_workspace` 於 collection 得到 `2 errors in 0.78s`；Docker Desktop 未啟動曾使 PostgreSQL連線逾時，環境恢復後由 repo migration升到 0018並執行官方 storage setup。candidate PostgreSQL逐案證據為 `9 passed, 21 deselected`、無 skip；brief指定完整 focused authority gate為 `118 passed in 81.86s`、無 skip。autouse fixture刪除本次建立的 document namespace，驗後 `consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store` 均為 0。
- 北極星回歸：AI仍只能建立待後續發布的候選，不能改核准文件或繞過員工裁決；沒有 RAG／Reference、能力級別／A、品質 eval、Web contract、舊 writer bridge、雙寫、第二 workflow owner或第二 persistence authority。單一顧問、動態 Task／Duty／OPKS、員工原話、先審後入、自然離開／續談與單一可強制匯出方向均未偏移。結果 **Pass**。

### ADR 0063 Task 3：第五個候選編輯 Tool 與真實結果回饋

- 狀態：**Pass（Task 3 focused deterministic gates）**；本 task 的 commit 為 `feat: add consultant candidate edit tool`。
- Tool／schema：model-facing surface 恰好新增一個 `job_document_candidate_edit`；`StructuredTool` 的 model-facing `tool_call_schema` 精確為 strict `CandidateEditBatch` 四欄。`ToolRuntime` 只留在 execution validation schema 取得 provider tool-call ID，document、run、baseline、selected Skills、loaded-Skill receipt 與 runtime 均由 closure 注入，模型 schema 不含這些欄位，也不讀 raw state 或 checkpoint。
- 真實結果與可修正失敗：candidate Tool 回傳 checkpoint 已保存的 `CandidateEditReceipt`，其中 action projection 直接來自實際 materialized `DocumentChangeSet`，含 candidate revision／digest、before／after、action handles、dependencies、atomic subgroup、pending/stale reason與 supersession action IDs；不回顯 provider batch 當成功。adapter 對 stale base、local ref／mapping、document invariant、Evidence、source-current與 rejected-without-new-evidence等窄 deterministic 例外轉成含 current baseline／candidate revision與 actionable issue 的 rejected JSON；未知 infrastructure 例外保留給 `ToolRetryMiddleware`／既有 failure classification。錯誤 batch不寫 checkpoint，後續同 base修正版可成功。
- 成熟 primitive 與 authority：LangChain `StructuredTool`／`ToolRuntime` 承接 Tool invocation與 provider call identity，LangChain built-in model／tool call limits承接五步與總 Tool budget，既有唯一 LangGraph graph／PostgreSQL Saver／Store／document lock仍承接候選 durable effect與 current employee source重讀。沒有內層 agent checkpointer／Store、candidate table、operation-per-tool、accept/reject Tool、Tool Search、MCP、RAG、shell、VFS、multi-agent或 auto-accept；candidate仍沒有 approved-document write edge。
- Assembly／budget：只在 explicit binding 時把 candidate Tool 加到 agent；與 `read_file`、三個 document-scoped employee source Tool 合計恰好五個。lookup-wave names仍只有四個 read Tool，candidate edit不計 lookup wave；interactive ceiling放寬到五個 model step，第六步被 middleware拒絕，候選呼叫仍計入既有總 Tool cap，其他 retry／token／cost／elapsed／recursion限制未改。
- TDD／驗證：baseline `tests/test_consultant_agent_and_skills.py tests/test_consultant_model_runtime.py` 為 `65 passed in 1.50s`；RED command 因 candidate Tool module不存在得到預期 `1 error in 1.12s`。brief GREEN command `tests/test_consultant_candidate_tool.py tests/test_consultant_agent_and_skills.py tests/test_consultant_model_runtime.py` 為 `70 passed in 1.49s`。workspace／durable receipt focused command為 `18 passed, 30 skipped in 0.63s`；skip 是未提供 PostgreSQL test URL 的既有條件，未把它當成 PostgreSQL integration 綠燈。LangChain schema adapter 的 injection/subset 行為以 ToolRuntime graph test覆蓋，沒有用自寫 agent loop繞過。
- 北極星回歸：一位顧問、動態 Task／Duty／OPKS、employee source memory、必要澄清／Gap、員工唯一 authority、自然離開／續談與單一可強制匯出均未更動；本 task 未開始 Task 4 的 run-service hard switch。RAG／Reference、能力級別／A generation、正式 eval、multi-agent與 auto-accept仍明確延後。結果 **Pass**。

### ADR 0063 Task 3：pre-review PostgreSQL regression alignment

- 狀態：**Pass**；follow-up 只修正 integration regression assertion 與 Task 3 證據，沒有改 production behavior，也未開始 Task 4。
- 契約：payload-bound 同一 tool-call ID 換 payload、unbound entity handle，以及 exact replay 遇到已 superseded source，均應由 adapter 回傳 framework-neutral `CandidateEditRejected`（含 current baseline／candidate revision 與 actionable issue）；source replay 保留窄 `SourceConflict` 為 `__cause__`，wire mapping 保留 `CandidateWireMappingError` 為 `__cause__`。候選、核准文件與 review queue 在拒絕後仍不變。
- concurrency 診斷與清理：先前 07:25–07:28 重疊 pytest 導致 local disposable DB 留下 8 個已列舉的孤立 checkpoint thread及 1 個已列舉 source prefix/key；`consultant_documents=0` 且 metadata 集合沒有額外目標。owner 明確授權後，以 parameterized SQL 只刪除這些目標，FK-safe 順序為 writes（77）→ blobs（29）→ checkpoints（22）→ 單一 Store row（1）；沒有 truncate、drop、catalog或其他 namespace刪除。
- 順序驗證：Task 3 non-DB focused gate `70 passed in 1.48s`；其後唯一的 real PostgreSQL gate `48 passed in 86.45s`、零 skip。post-gate 查詢 `consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store` 全為 0，因此沒有把 concurrency residue 誤判成產品 cleanup defect。

### ADR 0063 Task 3：review receipt-evidence fix

- finding A 處置：pre-Task-3 Task 2 checkpoint 的 receipt shape 不含新 private projection，技術上確有 backward-compatibility 問題；但 Task 2／3 均是同一未 push、未 merge 的 big-bang feature branch 內中間 commit，從未部署／發布，disposable local DB 亦為 0。依 current-only direction，這不是 release blocker；沒有為未發布的中間開發狀態加入 speculative migration、versioning 或 compatibility code。
- finding B 修正：exact replay 原本錯誤重驗 active latest changeset 的 source IDs。每個 durable internal `CandidateToolReceipt` 現保存其自身 materialized `DocumentChangeSet.source_ids`；latest receipt 必須與 workspace changeset 的 source IDs 完全相同；replay 改讀 `replay.source_ids`。公開 `CandidateEditReceipt`／model success JSON 未增加 source IDs，未知 infrastructure error 仍向外傳播。
- TDD／驗證：以 A 建 revision 1、B 建 revision 2，僅讓 A superseded 並保留 checkpoint。corrected RED 得到 `DID NOT RAISE CandidateEditRejected`，證明舊 code 會誤用 latest B；最小修正後 PostgreSQL regression `1 passed, 32 deselected in 3.35s`，同時證明 rev-1 拒絕且 cause 為 `SourceConflict`、state 不變、latest rev-2 replay 成功。workspace invariant suite `17 passed in 0.25s`；順序 Task 3 non-DB gate `70 passed in 1.51s`；順序 real PostgreSQL gate `50 passed in 89.43s`、零 skip；五張 persistence table 全為 0。

### ADR 0063 Task 4：final Structured Output hard-switch 至 candidate publication

- 狀態：**Pass**；final contract 不再承載 Duty／Task／OPKS draft，唯一文件效果是引用 checkpoint 中最新、完整、經驗證的 candidate receipt。neutral triplet 不發佈文件，只有 semantic commit 成功後才清除 candidate；整個 model run 失敗仍保留 candidate 供同一 run retry。
- Authority：graph 同一 semantic checkpoint transition 核對 candidate run、baseline semantic revision、latest candidate revision、SHA-256 digest、完整且有序 action IDs 與 candidate Skill subset；成功才把 exact persisted `DocumentChangeSet` 放入 review queue、stale superseded actions、block dependent work 並清除 workspace。approved JD 在 employee accept/edit-accept 前不變。unknown／old revision、digest mismatch、subset、reorder、duplicate handle、other run、stale baseline、Skill mismatch 與 candidate evidence source 在 Tool 與 final 間 superseded 均 fail closed。
- Source／Skill gate：run service 與持有同一 document lock 的 PostgreSQL adapter 都重讀 active candidate；adapter 在 graph 前重新驗 candidate sources 為 current/committed。這是必要的 publication authority seam，沒有新 Store、Saver、graph、candidate table 或 fallback。final used Skills 必須涵蓋 candidate Skills，既有 selected/loaded verification 保留。
- Tool／schema：model-facing surface 恰為 `read_file`、三個 read-only employee source Tools 和 `job_document_candidate_edit`；沒有 model accept/reject/defer Tool、router、RAG 或 auto-accept。model ceiling 正式為五次。review fix 改以實際建出的 candidate Tool `tool_call_schema` 及 `build_consultant_agent` 所建 ProviderStrategy 的 `schema_spec.json_schema` 量測，candidate input 與 final response 各自維持 zero optional／union／open object。合併 grammar 實測為 **6 schemas、0 defs、129 properties、2 optional、0 union、4 open objects、max depth 4、13,426 bytes**；總 bytes 僅記錄，不設虛構門檻。
- 必要偏差：brief 的檔案清單未列 `context.py`，但 hard switch 必須讓 prompt 指示模型先呼叫 candidate Tool、final 只引用最新 receipt 或 neutral，故做最小 prompt 變更。`adapters/langgraph/postgres.py` 的 10 行 publication 前 source revalidation 同樣未列，但用來覆蓋 Tool→final 更正 race；兩者皆只落在既有唯一 authority path。
- Safety-net audit：早期暫時 wholesale rewrite `test_consultant_model_output.py` 曾意外移除 calibration test 的 `now`；已從 HEAD 回復全部既有 coverage，再只移除 obsolete final full-document payload assertions並以 publication contract／mapper／authority tests替換。單獨 calibration 回歸為 `1 passed, 33 deselected in 2.77s`。非文件 output mapping、evidence basis、clarification、contradiction safety tests均保留。
- TDD／驗證：initial hard-cut RED 為缺 `OutputCandidatePublication`／`CandidatePublication` 的 `2 collection errors in 1.36s`；schema/run-service GREEN `26 passed in 1.17s`；latest model schema GREEN `23 passed in 1.13s`；publication/neutral/Skill/source-current narrow GREEN `4 passed, 33 deselected in 11.57s`。controller 由 committed HEAD 以 real `TEST_DATABASE_URL` 順序重跑指定 six-file gate，exit 0：**`88 passed in 103.64s (0:01:43)`、zero skips**。立即 residue query 的 `consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store` 均為 0；這份 controller evidence 取代先前 host stdout 分離的觀察。
- 北極星回歸：一位顧問、動態 Task／Duty／OPKS、員工原話與 correction、必要澄清／Gap、可信進度、自然續談、單一強制匯出、員工唯一審核 authority 均未變。沒有 Proposal legacy、第二 persistence authority、RAG、能力級別／A generation、multi-agent、hidden fallback或 auto-accept。結果 **Pass**；controller gate 已提供可觀測的完整 pass/skip 證據。

### ADR 0063 Task 4：review fix round 1（publication closure）

- 狀態：**Pass**；同一修正 commit 為 `fix: complete candidate publication hard cut`。publication seam 在 explicit supersession 標 stale、插入新 bundle 後立即復用既有 `revalidate_review_queue`。因此 bundle C 取代 A 時，依賴 A 的 B 依現有 dependency rule 轉 stale並保留前置理由，無關 action 維持 pending；沒有新 review engine、atomic-group 規則或第二 authority。
- Hard-cut safety-net：三個舊測試檔曾因從 `model_output` import `OutputDocumentChange` collection error；現 final/agent tests 用 neutral/exact candidate publication，review effect 直接走 `DocumentChangeSet`／`published_changeset`。不恢復 `reviewable_document_changes` channel。舊 final draft assertions 在 hard cut 後不可表示，其 wire/path/evidence coverage 已由 candidate wire、candidate Tool、review 與 authority tests承接。全檔 collection `249 tests collected`。
- Duplicate finding 處置：既有 exact-publication fail-closed test 4.11s 通過；不合法 `model_construct` receipt nested 進 `ConsultantResult` 時，`CandidatePublication` validator 先拒絕 duplicate action handles，故不加冗餘 graph validator。run-service test 另精確核對 candidate edit binding 的 runtime、document_id、run_id、baseline_revision、selected_skill_ids 均為 application injected 值。
- 驗證：supersession RED `1 failed, 24 deselected`，GREEN `1 passed, 24 deselected`；grammar/binding `27 passed in 1.22s`；三個遷移檔 `61 passed in 1.51s`。controller 先在九檔 gate 得到 `1 failed, 148 passed`，診斷為本機被殺掉的 96% pytest run 留下兩個 catalog orphan document；fixture cleanup 後五表已歸零。自 verified-clean DB 順序重跑完全相同九檔 command，exit 0：**`149 passed in 103.61s`、zero skips**；立即 query 的 consultant_documents/checkpoints/checkpoint_blobs/checkpoint_writes/store 均為 0，沒有平行 DB pytest。實際 schema 指標為 6 schemas、129 props、2 optional、0 union、4 open、depth 4、13,426 bytes；candidate/final individually 均為 0 optional/union/open。

### ADR 0063 Task 5：明示非核准 candidate overlay 與員工決策記憶

- 狀態：**Pass**；context 只從既有 LangGraph checkpoint 的 approved document、review queue 與同 run active candidate 讀取。沒有新增 candidate table、memory store、RAG、LLM progress 或任何 approved-document write edge。
- Authority／投影：approved slice 仍只序列化 `ApprovedJobDocument`。pending/deferred 為 `<pending_document_overlay authority="candidate" approved="false">`，含 operation、path、before／after、source IDs、dependencies、atomic subgroup、status 與各 status omitted count；rejected／stale／edit-accepted 為 `<document_decision_history authority="employee_decision" approved="false">`，保留 target 與員工 decision reason，edit-accepted 同時顯示模型原候選與員工採用值。三者都不是 JD baseline。
- Retry／budget：`<active_candidate_workspace authority="none" approved="false">` 只在 request run ID 等於 active candidate run ID 時出現，帶 revision、digest 及最多 32 個實際 changeset action；一般新 run 不見舊 candidate。pending 以 current work／approved focus 相交優先、僅補同 changeset dependency closure，最多 12；decision history 依 created revision、changeset ID、action order 穩定排序，保留最近 8，均提供 omitted counts。token receipt 仍以完整 prompt 計算並受既有 budget gate 約束。
- TDD／驗證：baseline `27 passed, 6 skipped`；新增 RED 為 **`4 failed, 27 passed, 6 skipped`**，四項均因缺三個 overlay section 而失敗。最終指定四檔 gate 為 **`36 passed, 6 skipped in 0.64s`**。測試覆蓋 semantic pending/deferred payload、rejected/stale/edit-accepted memory、九項已接受 Task 與一項 rejected O 分離、same-run retry、deterministic caps/order/omitted count，以及 staging 不改 semantic progress。
- PostgreSQL fixture hygiene：controller 初次 real-DB 四檔 gate 為 `42 passed in 14.41s`、zero skip，但 `consultant_documents` 留下 7 筆且全部 `deleted_at` 非空；checkpoints／blobs／writes／store 已為 0。診斷為 context tests 的 production soft-delete 正確清 namespace，卻少了 test-only catalog hard cleanup。依 durable-authority 既有 pattern 加入本檔 autouse fixture：每 test snapshot catalog IDs，teardown 只對差集逐筆 runtime cleanup 後 parameterized hard delete，沒有改 production delete semantics、truncate 或碰既有 ID。先精確驗證並刪除 controller 列出的 7 個 soft-delete UUID，五表歸零；修正後 real-DB sequential gate 為 **`42 passed in 16.19s`、zero skip**，立即五表 `0/0/0/0/0`。
- 北極星回歸：一位顧問、動態 Task／Duty／OPKS、員工原話、必要澄清／Gap、deterministic coverage／depth／decision／gap、自然續談與單一強制匯出均未改變。沒有 Proposal legacy、第二 persistence authority、multi-agent、auto-accept 或 pending/rejected 進 approved slice。結果 **Pass**。

### ADR 0063 Task 5：review fix round 1（materialized relevance／atomic overlay／test ownership）

- 狀態：**Pass**；同一修正 commit 為 `fix: harden semantic candidate context`。context 仍只是既有 checkpoint state 的 deterministic projection，未新增 authority、Store、graph、candidate table、RAG 或 progress 計算。
- 真實 relevance：`create_document_changeset` 的一般 task revise／withdraw 維持空 `target_ids`；projection 只讀明示 `target_ids`、canonical `/duties|tasks|opks/{uuid}` path／target_key，以及白名單 document linkage（`duty_id`、`task_id(s)`、`item_id`、`indicator_id(s)`）。OPKS 欄位 patch 的裸值只在 canonical `/opks/{uuid}/<linkage-field>` 下解碼，絕不掃描任意 UUID／source 欄位。實際 materialization 覆蓋 task revise、withdraw 與 OPKS `task_ids` focus-direct 排序。
- Cap／rendering：同一 changeset 的 dependency 與 atomic subgroup 被視為不可拆 connected component；直接相關 component 優先、stable fill 次之，只有全組可放入 12 才投影。12 dependency + focused consumer 的 13 件組完整省略並正確回報 omitted，11 + consumer 的 12 件組保留 persisted action order。JSON 以 stable `sort_keys` 並轉義 `<`／`>`／`&`；pending／active action 固定保留 `before`、`after`（ADD／withdraw 為 explicit `null`），hostile text 維持 JSON round-trip、不能關閉 XML-like section。
- 真實 authority path：PostgreSQL runtime test 走 `stage_candidate_revision → commit publication → accept → edit_and_accept → reject → snapshot → build_consultant_context`。同一 materialized bundle 的空 `target_ids` 不再遮蔽 relevance；approved slice 僅含 accept／employee edit 值，未決 action 僅在 pending，reject/edit-accept 僅在 decision history。
- Test-only cleanup：移除 catalog before/after snapshot。每個 DB context test 以 wrapper 在 `create_document` 前記錄自有 UUID；teardown 逐一嘗試 runtime namespace cleanup，並在 `finally` parameterized hard-delete 僅 registry UUID，即使其中一個 cleanup 失敗。未顯式設定 `TEST_DATABASE_URL`、非 localhost 或非 `caliburn*` DB 一律拒絕，沒有 production fallback、truncate 或 production delete semantics 變更。
- TDD／驗證：RED `4 failed, 10 deselected`；narrow GREEN `4 passed, 10 deselected`；runtime projection `1 passed, 14 deselected in 4.57s`；完整 context／receipt regression `18 passed in 19.84s`。最終 explicit `TEST_DATABASE_URL` 四檔 sequential gate 為 **`50 passed in 19.96s`、zero skips**；post-gate `checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store`、`consultant_documents` 全為 0。
- 北極星回歸：employee acceptance／edit-accept 仍是模型內容進 approved JD 的唯一路徑；pending/deferred 是 conditional hypothesis，rejected/stale/edit-accepted 是記憶而非 JD。單一顧問、動態 Task／Duty／OPKS、員工原話、澄清／Gap、自然續談與單一強制匯出保持不變。結果 **Pass**。

## 8. 本次直接使用的一手來源

- [Anthropic — Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
- [Anthropic — What's new in Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5)
- [Anthropic — Mid-conversation system messages and tool changes](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages)
- [Anthropic — Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic — Tool search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [Anthropic — Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI — Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI — Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [Google Gemini — Function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Google Gemini — Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [LangChain — Tools](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain `Citation`](https://reference.langchain.com/python/langchain-core/messages/content/Citation)
- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Deep Agents `SkillsMiddleware`](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware)
- [Deep Agents `FilesystemMiddleware`](https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware)
- [FastAPI Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [WHATWG HTML — Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [TanStack Query — Query invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation)
- [Next.js — Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)
- [LangChain 1.3.15 PyPI](https://pypi.org/project/langchain/1.3.15/)
- [LangGraph 1.2.11 PyPI](https://pypi.org/project/langgraph/1.2.11/)
- [`langgraph-checkpoint-postgres` 3.1.2 PyPI／security setup](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/)
- [`langchain-openrouter` 0.2.7 PyPI](https://pypi.org/project/langchain-openrouter/0.2.7/)
- [Deep Agents 0.7.5 PyPI](https://pypi.org/project/deepagents/0.7.5/)
- [FastAPI 0.141.1 PyPI](https://pypi.org/project/fastapi/0.141.1/)
- [HTTPX 0.28.1 PyPI](https://pypi.org/project/httpx/0.28.1/)
