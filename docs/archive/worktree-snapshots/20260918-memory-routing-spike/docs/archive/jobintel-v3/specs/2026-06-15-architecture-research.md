# jobintel-ai 重構 — 2026 架構研究筆記

> 本文件為本地研究記錄（不 commit）。日期：2026-06-15。
> 目的：在重構 jobintel-ai 前，先掃 2026 當下主流做法 / 熱門專案 / 最新技術，作為設計討論的共同基準。
> 一句話結論：研究**驗證**了先前討論的技術棧（LangGraph + CopilotKit/AG-UI）正是 2026 主流，但**否定**現況的用法（關鍵字字串路由、graph_state JSONB blob）。「不沿用之前的」= 實作模式重做，高層選型可沿用。

---

## A. 編排層（orchestration framework）

主流結論：做 **stateful + 分支 + human-in-the-loop** 流程，**LangGraph 仍是 2026 首選**。殺手鐧 = **checkpointer**：每個 state transition 持久化 → 可暫停 / resume / replay / 失敗恢復。

| 替代框架 | 定位 | 對 jobintel-ai |
|---|---|---|
| CrewAI | 角色化多 agent，起手快 | ✗ 要的是單一受控流程，非多 agent 團隊 |
| AutoGen / OpenAI Agents SDK | 對話式 / OpenAI 原生 | ✗ 綁供應商 or 偏對話 |
| LlamaIndex | RAG / 檢索 | ✗ 檢索已外包給 jd-ocs-indexer |
| Pydantic AI / Google ADK / Mastra | 新興、型別友善 | △ 可看，HITL 生態不如 LangGraph 成熟 |

意義：不是換框架，是**換用法**。現況 `route_after_*` parse 中文「確認/好」→ 主流改用 `interrupt()` + `Command(resume=...)`。

## B. Agent↔UI 互動層（新流程核心）

主流結論：**CopilotKit + AG-UI 已是事實標準**。AG-UI 被 Google / AWS / Microsoft / LangChain / Mastra / PydanticAI 採用；AWS Bedrock AgentCore（2026/3 加 AG-UI）、MS Agent Framework 內建；CopilotKit 2026/5 募 $27M。

可編輯清單的底層機制：
- `STATE_SNAPSHOT`（全量）+ `STATE_DELTA`（**JSON Patch RFC6902**：add/replace/remove/move）雙向同步
- 前端 `useCoAgent()` hook 即時綁 agent state；後端 LangGraph `copilotkit_emit_state()` 推
- 使用者編輯前端 state → agent 直接收到 = 任務 / K / S 可編輯清單的實現方式

替代：**assistant-ui**（React-only、chat UI 元件強、輕量；但偏聊天元件、非 agent runtime，shared-state/HITL 要自己接）。選型：要 shared-state + HITL + Python LangGraph 後端 → CopilotKit。

## C. HITL 模式（取代關鍵字確認）

`node 內 interrupt(payload)` 暫停 → 前端顯示/編輯/核准 → `Command(resume=編輯結果)`，checkpointer 用同 `thread_id` 還原。直接砍掉現況 `route_after_*` 中文比對；推進改由「使用者編完清單按確認 = 結構化事件」驅動。

## D. 狀態持久化

- 生產用 **LangGraph `PostgresSaver`**（非 MemorySaver），`thread_id` 為 key，可跨重啟還原。jobintel-ai 已在 Postgres，天然契合。
- ⚠️ 設計要解的張力：三個 state 家——CopilotKit shared-state / LangGraph checkpointer / 結構化 `company_tasks` 表——**誰是 source of truth**。脊椎第一個硬決策。

## E. 協定棧（2026 心智模型）

| 協定 | 管什麼 | 對 jobintel-ai |
|---|---|---|
| MCP | agent 怎麼拿外部工具/資料 | jd-ocs-indexer 可選「純 HTTP client」或「包成 MCP server」 |
| A2A | agent 之間協調 | 單流程，暫不需要 |
| AG-UI | agent↔user 互動 | 前端走這個 |

## F. 可直接抄 pattern 的熱門專案

| Repo | 為何相關 |
|---|---|
| CopilotKit/open-research-ANA | research canvas + HITL + LangGraph，最接近「agent 提結構→人編輯→agent 續」 |
| CopilotKit/CopilotKit `examples/canvas/langgraph-python` | Python + LangGraph + AG-UI canvas 官方起手式（原 canvas-with-langgraph-python 併入 monorepo） |
| open-multi-agent-canvas / OpenGenerativeUI / coagents-research-canvas | generative UI / 編輯畫布範例 |
| arxiv「Software as Content」(2603.21334) | 動態應用作為人機互動層的概念框架 |

## G. 觀念轉變

業界區分「真 agentic」vs「LLM+JSON prompt」：現況 `task_extraction`（丟 prompt 要 JSON）偏後者；新流程（catalog 取出 + 人 curate + 針對性深問 + reflection 品質迴圈）更靠近真 agentic。`reflection pattern`（generate→evaluate→revise）現況 `indicator` 品質重試已在做。

---

## 對 jobintel-ai 重構的意義（待設計時拍板）

1. **脊椎第一決策**：state source of truth（shared-state / checkpointer / company_tasks 表 三者關係）。
2. 流程反轉如何落到 graph：確定性選單節點（`/search`、`/task-pool`、`/pairs` → 可編輯清單）vs agentic 深問節點（STAR/5W2H 保留）如何共存。
3. `entry_router` + 關鍵字路由 → 改 `interrupt()`/`Command` + checkpointer。
4. `graph_state` JSONB blob → 結構化進已存在的 `company_tasks` / `ksa_items` 表（注意：這些表已定義但流程沒用）。
5. icap_matcher + icap_retriever + `icap_embeddings` 表 → 換成 jd-ocs-indexer API client（或 MCP）。
6. 前端 custom React（LiveDocPanel/TaskPanel/useInterview）→ CopilotKit `useCoAgent` 共享狀態。

## 開放設計問題（需先對齊使用者需求）

- 部署與規模（單機 / 內部多用戶 / 公開 SaaS 多租戶）→ 決定持久化、runtime、租戶隔離。
- 是否有現有用戶不能斷 + 時程壓力 → 決定漸進 vs 大膽重做。
- 前端重寫容忍度（全 CopilotKit vs 保留部分自製）。
- 深度訪談（STAR/5W2H）在新流程的份量（每任務都做 vs 選擇性觸發）。

---

## Sources

- 編排層：[Firecrawl 2026](https://www.firecrawl.dev/blog/best-open-source-agent-frameworks)、[LangChain 2026](https://www.langchain.com/resources/ai-agent-frameworks)、[gurusup 2026](https://gurusup.com/blog/best-multi-agent-frameworks-2026)
- AG-UI / shared state：[AG-UI State 文件](https://docs.ag-ui.com/concepts/state)、[AG-UI Introduction](https://docs.ag-ui.com/introduction)、[CopilotKit GitHub](https://github.com/copilotkit/copilotkit)、[CopilotKit AG-UI](https://www.copilotkit.ai/ag-ui)
- 採用動能：[TechCrunch CopilotKit $27M](https://techcrunch.com/2026/05/05/copilotkit-raises-27m-to-help-devs-deploy-app-native-ai-agents/)、[Microsoft Learn AG-UI](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/)、[Oracle A2UI×AG-UI](https://blogs.oracle.com/ai-and-datascience/announcing-agent-spec-for-a2ui-copilotkit-ag-ui)
- HITL / 持久化：[LangChain interrupt](https://www.langchain.com/blog/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt)、[LangChain Interrupts docs](https://docs.langchain.com/oss/python/langgraph/interrupts)、[Fastio LangGraph persistence 2026](https://fast.io/resources/langgraph-persistence/)
- 參考專案：[open-research-ANA](https://github.com/CopilotKit/open-research-ANA)、[canvas-with-langgraph-python](https://github.com/CopilotKit/canvas-with-langgraph-python)、[open-multi-agent-canvas](https://github.com/CopilotKit/open-multi-agent-canvas)
- 選型 / patterns：[assistant-ui vs CopilotKit](https://champsignal.com/comparisons/copilotkit.ai-vs-assistant-ui.com)、[Generative UI 2026](https://medium.com/@akshaychame2/the-complete-guide-to-generative-ui-frameworks-in-2026-fde71c4fa8cc)、[SitePoint agentic patterns 2026](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/)
