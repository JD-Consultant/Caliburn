# OpenAI Memory 流程對最新框架的功能交叉表

> 日期：2026-09-05
>
> Topic：`LLM-Q016`
>
> 狀態：**歷史 G3；主要元件優先順序已由 Q017 接續修訂，不授權 production 施工**
>
> Owner 後續暫時同意[Q017 框架接力](2026-09-05-openai-shaped-memory-framework-composition-research.md)：根 `create_agent` 不變，filesystem／StoreBackend 為主要候選，LangMem 紀錄工具為備選；本文保留原方案研究，不重新視為當前唯一組合。
>
> 2026-09-05 後續複核發現方案 B 未涵蓋整併中途按需深讀，且低估可獨立使用的
> Deep Agents filesystem 元件。先讀[通用流程審核 F01–F07](2026-09-05-generic-memory-flow-framework-crosswalk-audit.md)；
> 原核准保留作決策歷史，本文「最貼近／只剩薄 gap」不再作已證明結論。

## 0. Preflight

```text
Topic ID:
  LLM-Q016
Current stage:
  G3 Owner provisionally approved：OpenAI 已核實資料流 → 最新 framework 功能等價性。
Binding decisions:
  LLM-Q014：採 A 即時讀取、B 背景 extraction／consolidation、C 窄幅 live repair；
  LLM-Q015：最新 stable LangChain create_agent 作根，不採預設完整 Deep Agents harness；
  現行 production 仍受 Accepted ADR 0060 約束。
This turn's only blocking question:
  已回答：暫時核准方案 B；下一步轉入 LLM-Q017 artifact／primitive 級核對。
Already reviewed evidence:
  OpenAI Conversation／Compaction／Sandbox Memory 系統圖；Codex progressive-disclosure 深入研究；
  LangChain／LangGraph／Deep Agents／LangMem 官方完整流程事實圖；Harness 與 Compaction gap review。
Out of scope / parking lot:
  不在本稿選定 Compaction A／B、背景 job 的最終耐久機制、CAS、JD mutation、UI、Provider、
  model、production migration、實作、merge、push 或 PR。
```

## 1. 判定規則

本稿不以名稱相似判斷等價。只有下列四項同時相符，才算功能等價：

1. 輸入相同：讀的是 conversation、derived artifact，還是 current Memory；
2. 輸出相同：產生 continuation、候選、current Memory，還是 routing guide；
3. 生命週期相同：每輪、token 壓力時、conversation 封口後，或同輪明確修補；
4. authority 相同：框架只是產生候選，還是已實際寫入耐久 Store。

覆蓋等級：

- **Native**：一個官方 primitive 直接承接；
- **Official composition**：官方 primitives 可組成，需明確接線但不重寫其演算法；
- **Thin gap**：框架沒有該產品責任，只保留最薄 projection／policy／adapter；
- **Unresolved**：仍需獨立設計或 compatibility spike。

## 2. 最新版本基準

設計直接採研究當日最新公開版本，不受 Caliburn 現行 pin 限制：

| 套件 | 2026-09-05 最新公開版 | 成熟度 | 本稿用法 |
|---|---:|---|---|
| LangChain | 1.4.0 | Production/Stable | `create_agent`、middleware、model／Tool loop |
| LangGraph | 1.2.11 | Production/Stable | Checkpointer、Store、自訂 background graph |
| Deep Agents | 0.7.13 | Beta | 只評估公開 component，不作根 harness |
| LangMem | 0.0.30 | pre-1.0 | extraction／consolidation／search／manage primitives |

來源：[LangChain PyPI](https://pypi.org/project/langchain/)、
[LangGraph PyPI](https://pypi.org/project/langgraph/)、
[Deep Agents PyPI](https://pypi.org/project/deepagents/)、
[LangMem PyPI](https://pypi.org/project/langmem/)。現行 repo 版本只在未來 implementation gate
列為 migration gap；若施工日有更新版本，重新鎖定當日最新候選並驗證相容性。

## 3. OpenAI 真實責任形狀

OpenAI 公開的形狀不是單一「Memory 函式」，而是三條互補資料流。

### A. 即時讀取

```text
canonical conversation
  → 有界 continuation／compaction
  → 注入小型 Memory guide
  → 搜尋少量相關 durable Memory
  → 必要時深讀 rollout summary／原始 conversation
  → main agent 回答或使用 Tool
```

### B. 背景形成

```text
已封口 conversation segment
  → Phase 1 extraction
      ├─ segment／rollout summary
      └─ 0..N raw memory candidates
  → Phase 2 consolidation（讀 current durable Memory）
      ├─ 增量加入／補充／修訂／保守移除
      ├─ 更新 durable Memory
      └─ 最後重建小型 guide
```

### C. 執行中修補

```text
agent 深讀到一筆明確過時的 durable Memory
  → 同輪直接修正該 Memory
  → Tool 回傳成功／錯誤
  → 只有成功後，本輪後續推理才依賴新版
```

OpenAI 明確把 SDK conversation Session 與 sandbox Memory 分開；Memory read 採
`memory_summary.md → search MEMORY.md → rollout summaries` progressive disclosure，
conversation 結束後先 extraction、再 consolidation，live update 則讓 agent 修補 stale Memory。
上圖的「加入／補充／修訂／移除」是對公開責任的正規化描述，不宣稱 OpenAI 公開了一組
同名 typed enum。
直接依據：[OpenAI Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)、
[OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)、
[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)、
[Codex local memories](https://learn.chatgpt.com/docs/customization/memories)。

## 4. A 即時讀取：逐責任交叉比對

| OpenAI 責任 | 真實 I/O 與生命週期 | 最新框架等價物 | 覆蓋 | 邊界 |
|---|---|---|---|---|
| Canonical conversation | 每次 invocation 追加 message／Tool items；跨關閉恢復 | LangGraph PostgreSQL Checkpointer 保存 thread state／history | Native substrate | 只有不破壞原始 message state 才是 canonical；一般 LangChain summary 會永久替換舊 messages |
| Fault-tolerant agent loop | model↔Tool 反覆執行，Tool 結果回模型後續判斷 | LangChain `create_agent`，底層是 LangGraph compiled graph | Native | 不需自行重寫 agent loop |
| 每次 model call 的有界 Context | 只改本次 model-visible messages／tools／prompt | LangChain middleware `wrap_model_call`／dynamic prompt | Native | transient override 不等於持久修改 Checkpointer state |
| Conversation compaction | token 壓力時延續長對話，不能冒充 durable semantic Memory | Provider-native compaction、Deep Agents summarization component、LangMem summarization primitives | Unresolved | 已另立 Conversation／Compaction A／B gate；本稿不偷選 |
| 小型 Memory guide | 每輪固定注入高密度導航；durable Memory 成功更新後才更新 guide | middleware 可注入；LangGraph Store 可供讀取 | Thin gap | 框架沒有自動從 current Memory 重建 OpenAI 式 guide 的 primitive |
| 少量自動相關召回 | 本輪開始自動取少量相關 current Memory | LangGraph Store semantic search；middleware 注入結果 | Official composition | 可直接用本輪訊息作 query，第一版不必另呼叫 query model |
| 模型按需搜尋 Memory | 主顧問判斷需要更多時才搜尋 | LangMem `create_search_memory_tool`＋LangGraph Store | Native/close | 官方 Tool 暴露 query／limit／offset／filter；產品若只需 query，應以薄 facade 收窄模型 schema |
| 深讀完整 Memory | 搜尋命中後取得少量完整、自成一體內容 | Store item full value；LangMem search 可回 content＋artifact | Native/close | 若 search 已回完整 record，不必再造一個 read-by-ID Tool |
| 必要時回查原始 conversation | 只有需逐字、消歧或久遠案例細節時深讀 | Checkpointer history primitives＋應用層受限 read adapter | Thin gap | Checkpointer 提供 list/history，不提供現成的 model-facing semantic conversation search Tool |
| 按需載入分析 Skill／JD 區段 | 只有本輪需要時增加方法與文件內容 | Deep Agents SkillsMiddleware／LangChain dynamic tools；JD 由產品 Tool 讀取 | Official composition | Skills 是程序知識；JD 是產品文件，兩者不能混入 semantic Memory |

官方依據：[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、
[LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、
[LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)、
[LangMem tools](https://langchain-ai.github.io/langmem/reference/tools/)、
[Deep Agents context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)。

### A 的判定

框架已原生覆蓋 conversation substrate、agent loop、per-call context override、Store semantic
search 與 Memory Tool。真正未原生覆蓋的只有：

1. 從 current Memory 產生／重建小型 guide；
2. 把 Checkpointer history 安全暴露成按需原始 conversation read；
3. 選定不破壞 canonical conversation 的 compaction engine。

前兩項是很薄的產品 projection／adapter；第三項已是獨立決策，不在此自行發明。

## 5. B 背景形成：逐責任交叉比對

| OpenAI 責任 | 真實 I/O 與生命週期 | 最新框架等價物 | 覆蓋 | 邊界 |
|---|---|---|---|---|
| Conversation 封口／debounce | 閒置後批次處理新 segment，不阻塞每輪 | LangMem `ReflectionExecutor`；Deep Agents cron／scheduled-run recipe | Partial | local executor 是 process 內 worker、重啟不耐久；remote executor 依賴 Agent Server |
| Phase 1 segment extraction | 一段新 canonical conversation → summary＋0..N candidates；不寫 current Memory | LangMem `create_thread_extractor` 自訂 schema，或 `create_memory_manager` 的 stateless extraction | Official composition | 預設 extractor 只有 title＋summary；要同時輸出 candidates 必須提供明確 schema |
| Phase 1 derived artifact | 保存供 Phase 2／未來深讀的 segment summary；candidate 可傳入下一節點 | LangGraph background graph state＋Store | Native substrate | 是否長期保留 candidate 本身是產品 audit 決策；OpenAI 公開責任要求至少有可深讀 summary bridge |
| 取相關 current Memory | consolidation 前找少量可能重複／衝突的 current heads | LangGraph Store search；`create_memory_store_manager` 內建 retrieval | Native | StoreManager 預設 query limit 是 5；不能把它誤認為全量盤點 |
| Phase 2 incremental consolidation | candidates＋current Memory，遇歧義時再讀摘要 | create_agent＋search/read/edit；或 LangMem manager | Compose／部分 primitive | manager 只修訂既有工作集，沒有整併中的外部深讀；不能稱完整等價，見後續審核 F01 |
| 一步 retrieve＋consolidate＋write | raw conversation 直接更新 Store | LangMem `create_memory_store_manager` | Native alternative | 方便但合併了 OpenAI Phase 1／2，且不會自動留下獨立 segment summary／candidate artifact |
| Durable current Memory | current heads 可搜尋、可修訂 | LangGraph PostgreSQL Store | Native | Store 是 substrate，不決定何時 create／revise／retire |
| Guide 最後重建 | 只有 Memory 寫入成功後，guide 才反映新 current heads | background graph 的最後一個 projection node | Thin gap | LangMem／Deep Agents 沒有 OpenAI 式 guide rebuild primitive |
| 失敗隔離與恢復 | extraction 可空成功；需要處理部分成功與重試 | LangGraph node/checkpoint/retry semantics | Substrate；接力待設計 | 不自動回滾外部 Store writes；LangMem 多筆寫入非整批原子，不能承諾失敗零污染，見審核 F03 |

官方依據：[LangMem Memory API](https://langchain-ai.github.io/langmem/reference/memory/)、
[LangMem extraction source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)、
[LangMem delayed processing](https://langchain-ai.github.io/langmem/guides/delayed_processing/)、
[Deep Agents background consolidation](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)、
[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。

### B 的關鍵判定

`create_memory_store_manager` 提供「從 conversation 更新 Store」的現成 primitive，但它不是 OpenAI 的
兩階段 artifact pipeline：LangMem 的 `phases` 是同一批 in-memory candidates 的多次 refinement，
不是「先留下 segment summary／raw candidates，再由另一階段讀 current Memory 做 consolidation」。

若目標是保留 OpenAI 的責任分工，上一輪暫定以下組合；本輪審核指出第 4 步缺少整併中的
按需深讀，故須與 agent＋官方檔案工具候選比較，不能逕稱最貼合：

```text
LangGraph background graph
  1. 讀新封口 conversation segment
  2. LangMem thread extractor：segment summary＋0..N candidates
  3. LangGraph Store search：取相關 current heads
  4. LangMem memory manager：create／revise／no-op／保守 retire 候選
  5. Runtime 驗證後寫 LangGraph Store
  6. 成功後重建小型 guide
```

這裡自訂的是「節點接力與產品 policy」，不是重寫 extraction、consolidation、Store、semantic
search、retry 或 graph runtime。它也是框架存在的正常用途：LangGraph 官方定位就是組合
deterministic 與 agentic workflow、控制 latency 與狀態。

## 6. C live repair：逐責任交叉比對

| OpenAI 責任 | 最新框架等價物 | 覆蓋 | 邊界 |
|---|---|---|---|
| Agent 在本輪發現一筆明確 stale Memory | LangMem manage-memory Tool／LangGraph Store get | Native/close | 通用 Tool 可 create／update／delete，Caliburn 只需暴露窄 update contract |
| 以可信現有 ID 更新 | Store item key 由 Runtime 提供；model 只選已讀到的 ID | Official composition | ID、scope、version、time 不應由模型捏造 |
| Tool 成功／錯誤回模型 | LangChain Tool loop 與 ToolMessage pairing | Native | 格式／找不到／版本衝突可回精確可修正錯誤 |
| 成功後後續推理才依賴新版 | Tool completion ordering | Native | 同一批平行 sibling Tool calls不能假設彼此已成功 |
| B 後續讀最新 current head | LangGraph Store current value | Native substrate | background/live 同時寫同一 item 的序列化／CAS 尚未選定 |

官方依據：[LangMem tools](https://langchain-ai.github.io/langmem/reference/tools/)、
[LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)、
[Deep Agents memory／concurrent writes](https://docs.langchain.com/oss/python/deepagents/memory)。

### C 的判定

功能大多已有框架 primitives，不需另外造一套 Memory CRUD 引擎；但通用 manage Tool 權限比 C
需要的更廣。最薄且較安全的做法是沿用 LangGraph Store，向模型只公開「更新已深讀的一筆 current
Memory」的窄 Tool surface。這是權限收斂，不是另造 Memory framework。

## 7. 三個實質方案

### 方案 A：LangMem StoreManager 一站式

```text
create_agent
  + Checkpointer
  + Store
  + create_memory_store_manager
  + search/manage tools
```

**優點：**程式最少；retrieve、extract、consolidate、write 都有官方 primitive；可 hot path 或 delayed。

**缺點：**Phase 1／2 被合併，沒有獨立 segment summary bridge；不會自動重建小型 guide；
local delayed executor 不耐久；預設 top-k 不能支援最後全量盤點。

### 方案 B：OpenAI-shaped framework composition（推薦）

```text
主流程：latest stable LangChain create_agent
持久層：latest stable LangGraph PostgreSQL Checkpointer＋Store
Context：LangChain transient middleware；Compaction 元件另題選定
背景形成：薄 LangGraph graph＋LangMem extractor／manager primitives
召回：LangGraph Store search＋LangMem search primitive／窄 Tool facade
Live repair：窄 update Tool＋LangGraph Store
可選元件：Deep Agents Skills／summarization component，只有通過獨立 gate 才採用
```

**優點：**最貼近已核實的 OpenAI 資料流；穩定框架擁有 agent／graph／Store；模型工作交給
LangMem，而 Caliburn 只保留 framework 無法替代的 guide projection、conversation read adapter
與 domain policy；能獨立替換模型與 compaction capability。

**缺點：**不是一個開關；LangMem 仍是 pre-1.0，需鎖版本與 Postgres compatibility test；
durable local background trigger 及同 item concurrency 仍需後續窄決策。

### 方案 C：完整 Deep Agents harness＋filesystem Memory

**優點：**context compression、filesystem、hot-path file edit、Skills 與 background consolidation
recipe 齊全；長任務體驗完整。

**缺點：**Deep Agents `memory=` 指定檔案會固定載入，但可只指定小型導覽，其餘用檔案工具
按需讀取；所以這不是排除 progressive retrieval 的理由。背景
consolidation 是另一個 agent＋cron recipe，不是內建 pipeline；完整 harness 還帶入 filesystem、
subagent 等第一版未證明需要的模型表面，且目前仍是 Beta。

## 8. 推薦與理由

以下保留上一輪 **方案 B** 的推薦理由作決策歷史；「最吻合」判定受到本輪 F01／F02 新證據
挑戰。下一輪先比較元件級的 agentic consolidation，不自行撤銷 Owner 暫時核准：

1. LangChain／LangGraph 1.x 是最新 stable 基礎，直接擁有 agent loop、durable graph、Store、
   middleware 與 Tool lifecycle；
2. LangMem 是目前這組框架中最接近 extraction／consolidation／search／live update 的現成元件；
3. Deep Agents 的 component 可按責任取用，但不需要為了一兩項能力採完整 Beta harness；
4. OpenAI 有意拆開的 conversation、compaction、derived segment、current Memory、guide 與 raw
   lookup 不會被一個「memory」名稱糊成同一層；
5. 最終完整 JD 檢查可以另走 Store namespace 全量列舉／分批處理，不受日常 top-k recall 限制。

## 9. 明確不可誤判為已解決的事項

1. LangGraph Checkpointer **不是** Semantic Memory consolidation。
2. 一般 LangChain SummarizationMiddleware 會永久替換 state messages，不能直接宣稱保留 canonical conversation。
3. Deep Agents `memory=` 只固定注入選定 paths；可只放小 guide，再以檔案工具按需搜尋詳細內容，流程仍需組合。
4. LangMem `phases` **不是** OpenAI Phase 1／Phase 2 artifact pipeline。
5. LangMem StoreManager 的預設相關召回 **不是**最後全量 Memory 盤點。
6. `ReflectionExecutor` local mode **不是** restart-safe durable queue。
7. 有 CRUD Tool **不等於**已有 stale 判定、衝突 policy、CAS 或 sibling-effect ordering。
8. 本稿選最新版本能力 **不等於**現在 production 已升級或可直接接線。

## 10. 下一個窄 gate

若 Owner 暫時核准方案 B，後續不要一次寫 implementation plan；依序只處理：

1. **Conversation／Compaction gate：**在已核准的兩個候選中選能保留 canonical conversation、
   provider-neutral 且 bounded 的元件；
2. **Background durability gate：**比較 LangMem remote executor／LangGraph deployment 與本機
   restart-safe 最薄方案，決定封口 segment 如何不漏處理；
3. **Latest-version compatibility spike：**只驗證 LangMem extractor／manager／search／update 與
   LangGraph PostgreSQL Store 的 value shape、ID、update、search、no-op；
4. **Concurrency gate：**決定 background consolidation 與 live repair 是否序列化，或需要 version precondition；
5. 上述通過後才寫 successor ADR 與 production implementation plan。

Compaction exact engine、background scheduler、CAS、lineage 皆保持 OPEN；方案 B 的核准不會偷選它們。

## 11. Closure

```text
Decision / finding:
  最新框架沒有一個單一開關完整複製 OpenAI A／B／C，但 stable LangChain／LangGraph 加上
  LangMem primitives 可承接絕大多數責任；只剩 guide projection、canonical conversation read
  adapter、背景 durability／concurrency 等窄 gap。推薦 OpenAI-shaped framework composition。
Status:
  G3 Owner 暫時核准方案 B；不授權 production。
Why:
  已逐項比對真實 input、output、lifecycle、authority，排除名字相似但責任不同的誤映射；
  版本基準為研究當日最新公開版本，不受現行 repo pin 限制。
Sources:
  本稿 §2～§6 的 OpenAI、LangChain、LangGraph、Deep Agents、LangMem 官方文件與 PyPI。
Affected artifacts:
  本稿、current decision register、Harness／framework facts 版本基準；不改 ADR、API 或 Web。
Reopen trigger:
  上游新增等價的兩階段 durable Memory pipeline／guide builder；LangMem 或 Deep Agents 重大版；
  compatibility spike 否定本文契約；或 Owner 改變 OpenAI-shaped 目標。
Next gate:
  LLM-Q017 逐 artifact 核實 OpenAI 元件與 latest framework primitive；完成前不進 production。
```
