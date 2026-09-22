# AI 職務顧問 runtime：北極星審核與逐 Task 防偏帳本

- 日期：2026-08-14
- 狀態：Pre-implementation audit **Passed**；Task 1 尚未開始
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
| 按需專業方法 | Deep Agents `SkillsMiddleware` progressive disclosure | repo 已驗證方法、eligibility 與輸出契約 | 已覆蓋；Beta 窄介面需 canary |
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
- 完整 `create_deep_agent`：會帶入 subagent、filesystem、shell、todo 與自由長任務 harness；本產品只取 `SkillsMiddleware`。
- Agent Server／LangSmith 服務：本機單一操作者不需要第二個 runtime service；使用 FastAPI SSE 與本機 OpenTelemetry。
- DBOS／Camunda／Microsoft Agent Framework／另一套 memory framework：四個核心目的已由 LangGraph conformance 通過，再加入會形成第二個 workflow owner。
- RAG／Reference：owner 明確延後，不是框架缺口。

## 6. 施工前風險與已加的 gate

1. `langgraph-checkpoint-postgres` 3.1.2 精確 pin；啟用 strict msgpack／allowlist、idempotent `.setup()`、正確 psycopg connection options 與 UUID namespace isolation tests。
2. Deep Agents 0.7.5 與 `langchain-openrouter` 0.2.7 仍標示 Beta；只使用窄 public API，Task 1 加 import／behavior canary，不能因此接入完整 harness。
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
- owner decision：2026-08-14 明確表示審核通過即可開始；ADR 0060 因此 Accepted。

## 8. 本次直接使用的一手來源

- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Deep Agents `SkillsMiddleware`](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware)
- [FastAPI Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [LangChain 1.3.15 PyPI](https://pypi.org/project/langchain/1.3.15/)
- [LangGraph 1.2.11 PyPI](https://pypi.org/project/langgraph/1.2.11/)
- [`langgraph-checkpoint-postgres` 3.1.2 PyPI／security setup](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/)
- [`langchain-openrouter` 0.2.7 PyPI](https://pypi.org/project/langchain-openrouter/0.2.7/)
- [Deep Agents 0.7.5 PyPI](https://pypi.org/project/deepagents/0.7.5/)
- [FastAPI 0.141.1 PyPI](https://pypi.org/project/fastapi/0.141.1/)
