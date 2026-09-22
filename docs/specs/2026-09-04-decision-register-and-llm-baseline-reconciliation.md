# Decision Register 與 LLM 基線 reconciliation

- 日期：2026-09-04
- 狀態：**Working decisions 的文件級 reconciliation；不授權 production 施工**
- Authority 入口：[`../current-decisions.md`](../current-decisions.md)
- 依循流程：[`../decision-process.md`](../decision-process.md)

## 1. 本次只處理什麼

本次修正主 checkout 與 `codex/memory-routing-canonical-read-spike` 隔離 worktree 之間的決策紀錄分叉：

1. 同一個 `MEM-Q005` 被用來指稱兩個不同決策；
2. 主決策表仍把 Memory read spike 寫成執行中，但實際已完成 revision 3 並停在 `FAIL_UNPROVEN`；
3. 隔離 worktree 留有已經 Product Owner 核准的 LLM／Agent Working Decisions，但尚未回到主決策入口；
4. 同一 worktree 亦有未經本次授權的 production code 變更，不能與文件決策一起帶入。

本次不重新研究 Memory、不重跑付費實驗、不採用 worktree 的 production code、不 merge、不 push，也不以 Working Decision 越過 Accepted ADR 0060。

## 2. Reconciliation 結果

### 2.1 Authority 與 ID

- 主 checkout 的 [`current-decisions.md`](../current-decisions.md) 繼續是唯一決策入口。
- `MEM-Q005` 固定指「Semantic Memory 持久化與 JD 待審變更的並列 effects」，不再重用。
- 原隔離 worktree 中以 `MEM-Q005` 記錄的 thread-cardinality 決策改登記為 `MEM-Q006`。
- Worktree 文件與 commit 可作 evidence，但未寫回主 register 的文字不自動取得 durable decision 效力。

### 2.2 Memory read spike 正式結束

隔離實驗完整報告保存在 branch `codex/memory-routing-canonical-read-spike` 的 commit `41e181d`：

```text
docs/experiments/2026-09-03-memory-routing-canonical-read/report.md
```

實際結論：

- revision 2 因 Windows 預設 `ProactorEventLoop` 與 Psycopg async 不相容而在資料庫入口停止；其後 bounded repair 已以 CLI regression test 驗證；
- revision 3 已通過專用 PostgreSQL、LangGraph Store 與 embedding 路徑；三個 embedding requests 共處理 274 tokens，已知費用 USD 0.00000548；
- 第一個 Luna chat request 在取得任何 model response 或 Tool call 前收到 OpenRouter HTTP 404；
- frozen request 同時傳送 `parallel_tool_calls: false` 與 `provider.require_parameters: true`，當時 OpenRouter 公開 endpoint metadata 沒有任何 Luna endpoint 宣告支援前者，因而沒有 eligible endpoint；
- 六個 Memory 語意品質判準全部為 `NOT_EVALUATED`。

所以 `FAIL_UNPROVEN` 的精確意思是：**實驗沒有證明 read path 的模型語意效果，也沒有反證它；失敗發生在 provider capability routing。**不得把 Store／embedding 通過寫成整個 Memory 方案成功，也不得把 404 寫成 Luna 或 Memory 品質失敗。

Product Owner 於 2026-09-04 決定保存此結果並結束該 spike；不執行 revision 4。若未來 production 設計仍採相同 provider gateway，capability compiler 必須另在對應 LLM gate 解決，不能藉由重跑本實驗偷渡契約變更。

### 2.3 Thread cardinality 改登記為 `MEM-Q006`

第一版維持：

- 一名員工對應一份隔離文件與一份 JD；
- 一份 JD 只有一個主要、可長期延續的訪談 thread；
- Semantic Memory 以 JD／document scope 隔離，不跨 JD 共用；
- thread 是 conversation／run continuity，不是長期 Memory 的擁有者；
- 未來只有同一 JD 真正出現多入口或多 conversation 的產品需求，才重開多 thread 設計。

這是 Caliburn 的產品 cardinality 選擇；OpenAI、Anthropic 與 LangGraph 公開機制支持 conversation state 與 long-term Memory 分層，但沒有要求單一聊天室產品一定預先建立多 thread。

## 3. 已核准 LLM／Agent Working Baseline

下表把隔離 worktree 中已經 Owner 核准、且仍符合後續討論的結論帶回主決策入口。這些都是 Working Decisions；production 仍須 successor ADR、G4 完整設計及 implementation gate。

| ID | Durable Working 結論 | 邊界 |
|---|---|---|
| `LLM-Q002` | 第一版 framework 方向採 LangChain stable 1.x＋LangGraph stable 1.x；不整包採 Deep Agents，也不引入第二套 agent loop／durable owner。 | 這是 Caliburn 選型，不冒充跨廠共同選型。 |
| `LLM-Q003` | 第一版以一個 LangChain `create_agent` compiled graph 作根 model↔Tool runtime；只有具體需求證明標準 loop 不足，才增加窄 StateGraph／Functional workflow。 | 不先固定 Tool、Memory、JD 或 UI schema。 |
| `LLM-Q004` | 每則被接納的新員工訊息啟動一次有界 logical invocation；內部可有多個 model／Tool steps。員工稍後再傳訊息是新的 invocation，不是持續占用上一個 HTTP request。 | 第一版不做 active steering；問題／interrupt 邊界由後續決策修正。 |
| `LLM-Q005` | completion、等待外部輸入、模型可修正的 Tool error、暫時性 retry、limit／cancel 與 terminal failure 必須依「誰能恢復」分流；不能全部顯示成「分析錯誤，只能重試」。 | exact enum、retry 次數與 UI 尚未決定。 |
| `LLM-Q006／Q011／Q012／Q013` | 第一版訪談問題以正常 assistant completion 結束；員工下一則文字再啟動新 invocation。沒有模型可觸發的通用 ask-user durable interrupt。只有會影響未來 JD 的未解工作資訊才進 Semantic Memory；問題卡可作 UI presentation，但不創造 pending execution。 | `LLM-Q007～Q010` 的 required-confirmation interrupt 方案維持 superseded；未來只有出現真正 unfinished workflow 才重開。 |
| `LLM-Q014` | 對人的內容走 canonical assistant message；需要讀寫 application state 的 machine effects 優先走 framework-native Tool；Runtime 可推導的 scope、ID、版本、時間、budget 等不讓模型填；structured output 只留給確有單一窄 machine-readable artifact 的工作。 | 父層方向已核准；Semantic Memory writer／timing 子節需依 `MEM-Q005` 重寫，尚未完成 G4。 |

`LLM-Q001` 的舊 provider-capability spike 保持 `PAUSED`。Revision 3 只證明舊 frozen wire contract 不可路由，不授權直接把 worktree 的 provider adapter 修改帶進 production。

## 4. 必須修正的舊衝突

隔離 worktree 的 `LLM-Q014` 草稿曾建議：「若同輪要依新資訊產生 JD 變更，必須先等待 Semantic Memory 成功發布。」這已被後來核准的 [`MEM-Q005`](2026-09-04-memory-persistence-and-jd-effect-reconciliation.md) 精確取代。

現行 Working 邊界是：

```text
canonical conversation + current Semantic Memory + current JD + current input
                                  ↓
                         已驗證的本輪理解
                            ↙           ↘
                 Memory mutation      JD pending change
```

- JD 依賴它實際讀到並通過驗證的語意內容，不依賴該內容先成功寫入 Store；
- Memory 技術性持久化失敗不刪除、不阻擋、也不自動標 stale 已通過自身驗證的 JD 候選；
- 只有新的語意分析改變理解，或 JD base state 改變，才觸發重新驗證／stale；
- 最終全面完整性檢查仍必須處理全部有效 Memory／來源，不能冒充完成。

## 5. 下一個唯一 blocking question

```text
Topic ID: LLM-Q014
Current stage: G4.1 需要依 MEM-Q005 重寫
Binding decisions:
  MEM-D001～D003、MEM-Q001～Q006、
  LLM-Q002～Q006、LLM-Q011～Q014 的父層方向
This turn's only blocking question:
  在一次 bounded invocation 中，如何由同一份已驗證理解形成、驗證並回報
  Semantic Memory mutation 與 JD pending change 兩個並列 effects，
  同時讓一般回合保持低延遲，且不建立第二套 agent loop？
Already reviewed evidence:
  OpenAI／Anthropic Tool contract、LangChain create_agent、LangGraph persistence、
  LangMem hot-path／background formation，以及 MEM-Q005 dependency reconciliation。
Out of scope / parking lot:
  exact Tool schema、retry 數字、背景 queue／worker、UI、Reference RAG、
  production migration、模型價格選型與任何 production code。
```

下一輪不得重跑 Memory revision 4，也不得先修 OpenRouter production adapter。先完成 `LLM-Q014` 的 G4 正常資料流、framework responsibility、錯誤矩陣與可證偽驗收；其中真正無法由官方資料回答、且會改變設計的項目，才可另提最小 spike。

## 6. 來源與可追溯性

### 實驗與本地 authority

- Memory read spike report：branch `codex/memory-routing-canonical-read-spike`，commit `41e181d`
- [`MEM-Q005 reconciliation`](2026-09-04-memory-persistence-and-jd-effect-reconciliation.md)
- [`Decision-to-Product 流程`](../decision-process.md)
- [`Accepted ADR 0060`](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)

### 官方／framework 直接來源

- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [Anthropic — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic — Tool runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [LangChain — Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain — Middleware](https://docs.langchain.com/oss/python/langchain/middleware/overview)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangMem](https://langchain-ai.github.io/langmem/)
- [OpenRouter — Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter — Require supported parameters](https://openrouter.ai/docs/guides/routing/provider-selection#requiring-providers-to-support-all-parameters)
- [Psycopg — Async／Windows event-loop limitation](https://www.psycopg.org/psycopg3/docs/advanced/async.html)

這些來源支持 framework／provider 的公開能力與限制；具體 ID、文件分層、Caliburn Tool-first 選擇、並列 effects 與無 revision 4 是 Caliburn 決策，不冒充廠商共同內部架構。

## 7. Closure

```text
Decision / finding:
  主 register 恢復為唯一入口；Memory spike 以 FAIL_UNPROVEN 結束且不再重跑；
  thread cardinality 改登 MEM-Q006；已核准 LLM baseline 回到主 register；
  LLM-Q014 舊 Memory hard gate 被 MEM-Q005 取代。
Status:
  Working reconciliation complete；production unchanged。
Why:
  消除同 ID 雙義、過期實驗狀態與跨 worktree 決策遺失，避免重複研究與錯誤施工。
Sources:
  本文 §6。
Affected artifacts:
  docs/current-decisions.md、docs/README.md、本文件。
Reopen trigger:
  找到 Owner 未核准卻被誤登的決策、commit/report 內容不符、或新的官方／實驗證據改變結論。
Next gate:
  LLM-Q014 G4.1；先設計，不施工。
```
