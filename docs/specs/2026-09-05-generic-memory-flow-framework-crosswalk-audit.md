# 通用 Memory 流程與框架交叉表：審核與修正

日期：2026-09-05；Topic：`LLM-Q017`；狀態：**後續 Owner 已暫時同意主要檔案組合方向；本文保留比較沿革，不授權施工**。

最新決策讀[框架接力研究](2026-09-05-openai-shaped-memory-framework-composition-research.md)與 current register；下一個待審窄題為 [Q018 寫入協調／恢復](2026-09-05-memory-background-live-repair-coordination-research.md)。以下「候選未定」保留當時審核時序，不是目前仍待重新同意。

目前入口：§8 記錄 Owner 同意及下一層比較；§8.4–8.5 補核 OpenAI 背景中途補查的直接證據與框架接力缺口。§1–7 保存前一輪審核證據，不能把其中「尚待同意能力」當成仍未決。

## 0. 本輪範圍與閱讀路由

- Owner 最新要求：先研究通用 Memory 流程，以 OpenAI 公開概念為主軸；辨別跨家共同做法與框架真正缺口，不先套 Caliburn／JD。
- 本輪唯一決策題：**原先「LangMem primitives 已最貼近 OpenAI，只剩薄接線」的判定是否足夠？**
- 既有 `LLM-Q015／016` 暫時核准仍是歷史有效決策；本文提出有新證據的修正建議，不自行改選、不改 production。
- 本輪完整回讀：[OpenAI 系統圖](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[框架官方事實圖](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md)、[功能交叉表](2026-09-05-openai-memory-flow-to-latest-framework-functional-crosswalk.md)、[逐 artifact 交叉表](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md)，以及 current register／decision process。未讀 Owner 排除的 08-12 產品長稿，未以施工計畫或舊 code 決定新流程。
- 本文只保存**審核差異、通用流程與方案取捨**；artifact 詳解留在原表，來源細節留在官方事實圖。後續先讀本文，再依需要回查，避免複製另一份大型百科。

## 1. 先校正「共識」的意思

| 層級 | 本輪證據支持什麼 | 不可宣稱什麼 |
|---|---|---|
| 跨家共同方向 | 活躍 conversation/context 與可重用持久 Memory 分工；按需讀取；可修訂；控制固定 context 成本；由 runtime 執行讀寫 | 每家所有產品都用相同資料結構、排程或 prompt；共同出現就已證明效果最佳 |
| OpenAI／Claude Code 都可見 | 小型入口＋較詳細內容按需讀取 | 二者同名 `MEMORY.md` 承擔相同責任 |
| OpenAI 特定公開 pipeline | Phase 1 抽取、Phase 2 整併、摘要／候選中間產物、背景處理；Sandbox 另公開 live update | Anthropic 必定也有這套兩階段 pipeline；每次 invocation 都自動向量召回 |
| 可選實作 | 檔案或 JSON records、文字或語意檢索、背景或 hot path、衝突控制、保留政策 | 某個可選方案是跨家唯一正解 |

直接來源：[OpenAI local memories](https://learn.chatgpt.com/docs/customization/memories)、[OpenAI Sandbox Memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)、[Claude Code auto memory](https://code.claude.com/docs/en/memory#auto-memory)、[Anthropic Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)、[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。這是對**具名公開表面**的比較，不是對未公開內部系統的推測。

特別注意：Claude Code 的 `MEMORY.md` 是指向 topic files 的小型索引；Codex 的同名檔偏向詳細可檢索手冊，小入口另叫 `memory_summary.md`。**應映射用途，不映射檔名。**

## 2. 審核發現

### F01／High：LangMem manager 不能直接等同 OpenAI consolidation agent

- 位置：逐 artifact 表 §6「Consolidation model」、§7.2；功能表 §5。
- 證據：`MemoryManager` 以傳入的 messages／existing 為工作集，內部用 Trustcall schema extraction／patch 與可選 Done 反覆精煉；沒有供模型執行外部 Memory 搜尋或 summary 深讀的工具迴圈。`StoreManager` 先取相關資料，再進 manager，也不會在整併中途因歧義自行追加 source reads。
- 對照：OpenAI consolidation agent 能在處理候選時再讀相關 rollout summaries。這是**寫入路徑的按需取證能力**，不只是保存幾個中間欄位。
- 影響：只用 manager 可能在初始工作集不足時無法取得必要脈絡；增加 `max_steps` 不等於增加外部讀取能力。
- 要求／狀態：改為 **部分功能相近**。保留 manager 作結構化整併候選；新增 `create_agent`＋受限搜尋／讀取／編輯工具作比較，尚未改選。

依據：[LangMem 固定快照 extraction.py](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/knowledge/extraction.py) 的 `MemoryManager.ainvoke`／`MemoryStoreManager.ainvoke`、[OpenAI consolidation prompt](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md)。Codex 這個背景 prompt 明確不讀原始 rollout；不可把前台 raw fallback 混成 Phase 2 默認步驟。

### F02／High：Deep Agents 被評為「只差檔案形狀」，低估了可重用功能

- 位置：功能表 §7 方案 C、逐 artifact 表 `MEMORY.md physical file` 與 §5.9。
- 證據：`FilesystemMiddleware` 官方原始碼直接示範接到 `create_agent`；提供 ls／grep／read_file／write_file／edit_file 等。`StoreBackend` 讓這些虛擬檔案持久存在 LangGraph Store。
- `memory=[paths]` 固定注入的是**選定檔案**，不是 Store 裡所有檔案。只選小型導覽，詳細內容保留給檔案工具按需讀取，就能組成 progressive disclosure；但導覽內容與更新政策不會憑空自動生成。
- 要求／狀態：不能用「Memory 全部固定注入」排除這條路，也不能把「用檔案元件」與「採整套 Deep Agents harness」綁成同一選項。新增元件級候選，不改根 harness 決策。

依據：[官方 filesystem middleware 範例](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py)、[Backends](https://docs.langchain.com/oss/python/deepagents/backends)、[Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering#memory)。已另核對發佈 wheel 0.7.13 存在此 `create_agent` 範例與 StoreBackend read／grep／edit，非只看 main 未發佈功能。

### F03／High：Checkpoint／重試不保證多筆 Memory 全成或全敗

- 位置：功能表 §5「consolidation 失敗不污染 current Memory」；逐 artifact 表 §7.2「一次套用」。
- 證據：LangMem StoreManager 最終用多個 `aput`／`adelete` 並行寫入；不是對整批變更提供一個 transaction。Checkpointer 保護的是 graph state，不把外部 Store／檔案寫入自動納入同一原子交易。
- 影響：有可能部分寫入成功才發生錯誤；重新讀取、重試、同一 Memory scope 的 writer 協調與 guide 更新必須有明確邊界。
- 要求／狀態：移除原子性／失敗零污染的推定。先標「部分成功與恢復尚待設計」，不自行新增 CAS、版本表或自製交易引擎。

依據：[LangMem StoreManager 原始碼](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/knowledge/extraction.py)、[Deep Agents concurrent writes](https://docs.langchain.com/oss/python/deepagents/memory#concurrent-writes)、[LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)。

### F04／Medium：Rollout 不能直接映射成一次 LangGraph run

- 位置：逐 artifact 表 §4.2 與 §6 Rollout。
- Codex Phase 1 是 per-thread rollout extraction；Sandbox 會將多個 run segments 累積到同一 conversation file。LangGraph invocation／run、thread、checkpoint 是不同粒度。
- 要求／狀態：修正名詞，抽取輸入範圍與重處理邊界另外設計。不得從「rollout」推導成每次 user message 自動有一個固定切片／候選包。

依據：[Codex memories README](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/README.md)、[Sandbox multi-turn conversations](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/#multi-turn-conversations)。

### F05／Medium：搜尋目的相近，不代表搜尋機制相同

- 位置：逐 artifact 表 §6 Memory search；§7.1 自動 recall。
- Codex 公開路徑為文字搜尋與選段讀取；LangGraph Store 語意搜尋需要 embedding 設定，LangMem search Tool 只是呼叫 Store。`filter` 不是任意全文搜尋，top-k 不是完整列舉。
- Deep Agents StoreBackend 的 grep 是 literal text search；其實作會分頁取得 Store files 再匹配，不是自動擁有高效 DB 全文索引。不能只因有 grep 就宣稱任意規模都低成本。
- 要求／狀態：標成兩種可選檢索方式。少量自動召回是既有暫時選擇，但不是已證實的 OpenAI／Anthropic 每輪共同規則；本輪不自行取消，也不寫入「通用必備」。

依據：[Codex read prompt](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/read/templates/memories/read_path.md)、[LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores)、[StoreBackend 原始碼](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py)。

### F06／High：長對話延續不等於完整原始資料保留

- 位置：逐 artifact 表 §5.1／5.9；OpenAI 系統圖的 canonical 描述。
- Checkpointer 保存 state snapshots；若 messages 已被摘要替換，最新 state 不會因此仍包含原文。Deep Agents 額外保存的是 conversation 的**文字呈現**，不能推定與原始多模態／tool event bytes 完全等價，保存多久也取決於 backend／retention。
- 要求／狀態：保留「可回查原始內容」責任，但不要指定重複資料庫；精確 reader、非破壞性 context 組裝或原始 archive 的選項維持未決。通用流程不能承諾無限、無損保留。

依據：[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[Deep Agents context compression](https://docs.langchain.com/oss/python/deepagents/context-engineering#context-compression)、[Claude Code transcript／Memory retention](https://code.claude.com/docs/en/memory#storage-location)。

### F07／Medium：不是所有缺口都已證明很薄；LangMem 也不是必經依賴

- 位置：兩份交叉表的推薦理由與「只剩很薄」結論。
- Structured extraction 本身可用 LangChain model `with_structured_output`／`create_agent(response_format=...)`；需要 existing-aware schema patch 才是 LangMem／Trustcall 的專門價值。保留 OpenAI 兩階段概念，不等於必須引入 LangMem。
- 排程、跨 worker 協調、partial writes、保留／刪除與來源回查具有真實工程責任；「framework 有 node／Store」尚不足以估算只需薄接線。
- 要求／狀態：改成「能以官方元件組合，尚有接力契約」，成熟度與成本另列。不能聲稱沒有任何框架能承擔，只能說**本輪核對的元件未內建整條 pipeline**。

依據：[LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)、[Deep Agents background recipe](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)、[Agent Server](https://docs.langchain.com/langsmith/agent-server)。

## 3. 修正後的通用流程

下列是**參考 OpenAI 的候選組合**，不是聲稱各家逐步相同。暫不加入 JD、Task、OPKS、Focus 或產品 coverage loop。

```text
A 互動／讀取
保存並延續 conversation
  → 組裝有界 context（必要時 compaction／摘要）＋小型 Memory 入口
  → 主 agent 按需搜尋 → 讀詳細 Memory → 需要時讀 conversation summary／原始記錄
  → 回答或執行工具
  （自動相關召回是可加選項，不是上列路徑成立的必要前提）

B 背景形成
選定可處理的 conversation 輸入
  → extraction：產生來源脈絡摘要＋值得保留的候選
  → 保存中間產物
  → consolidation：讀候選及既有 Memory，必要時再搜尋／深讀摘要
  → 整併、修訂或不變 → 更新持久 Memory → 更新小型入口

C 執行中修補
主 agent 發現已核實的過時內容
  → 使用同一 Memory 的修改工具 → 取得實際成功／錯誤結果
  → 繼續工作；後續 B 仍須讀到當時的 current Memory
```

來源分工以 §1–2 連結為準。C 限一筆 ID、B 固定某段長度、所有錯誤必須先回滾等，都不是本圖暗中加入的通用規則。疑似衝突如何求證、何時詢問人、寫入失敗如何恢復仍須分清模型判斷與 runtime 結果。

## 4. OpenAI 元件 → 可用框架：修正後摘要

| OpenAI 責任／artifact | 框架材料 | 還沒有自動承擔什麼 |
|---|---|---|
| Conversation／Session；raw rollout | thread＋Checkpointer；可選原始記錄／Deep Agents conversation text | 完整原始事件保留與可讀取契約；rollout 範圍不等於 run |
| Compaction | provider native；LangChain／Deep Agents summarization | 不同引擎非逐字等價；retention 與 context 組裝須確認 |
| Extraction | LangChain structured output；或 LangMem thread extractor | 哪些內容值得保留的 prompt、抽取範圍、中間產物持久化 |
| `raw_memory`／`rollout_summary` | graph output＋Store item；或 StoreBackend files | 不是框架自動生成的固定欄位；summary 不等於原話 |
| `rollout_slug` | 可選短標籤；runtime key／path | slug 只是定位便利，不必為沒有實體檔名的方案增加 LLM 欄位 |
| Stage 1 records／候選 inventory | Store／graph job state；部署 queue | eligibility、消費範圍、重試與保留政策 |
| Consolidation | **agent＋search/read/edit tools**；或功能較窄的 LangMem manager | 前者需組合；後者不具整併中途外部深讀 |
| `MEMORY.md`／durable content | StoreBackend 檔案或 Store JSON records | 內容品質、組織方式與有效資訊保留 |
| `memory_summary.md` | 只注入小入口的 middleware；agent 可生成／修改入口 | 入口長度、更新時機及與正文的一致性 |
| Progressive read／live update | 檔案 middleware 的 grep/read/edit；或 Store search／manage tools | 檢索選型、權限、競爭寫入及恢復；不要求兩套並存 |

上述每列均可追到 §2 官方來源及原逐 artifact 表；**提供工具不等於已完成 pipeline**，但也不等於必須自行發明搜尋／編輯／agent-loop 引擎。

## 5. 下一個應討論的選擇

| 候選 | 效果／功能 | 成本與代價 |
|---|---|---|
| A：原先 LangMem records 組合 | existing-aware 結構化修訂；可保留兩階段 artifact | 整併工作集外資料須由外層補入；中途深讀不是 manager 原生；需檢查 hot/background value shape |
| B：`create_agent`＋受限檔案元件 | 可像 OpenAI 在整併中搜尋、讀摘要、編輯 Memory／導覽；同套工具也可前台讀／修補 | 可能多個 model/tool steps；檔案跨批次一致性與排程仍要做；StoreBackend grep 不是高效全文索引保證 |
| C：直接用 OpenAI Sandbox Memory | 最直接沿用其公開兩階段生命週期 | Beta、JS sandbox／workspace 前提、官方截斷及淘汰政策；是否接受整體 runtime 是另一選型，不偷偷改根 harness |

**本輪建議是先詳細比較 B 與 A，不再預設 A 最貼近。** B 可維持已選的 `create_agent` 根，不必採整套 Deep Agents。這是根據「整併時按需深讀」需求的比較推論，尚未由實測證明品質、成本或速度較好；也不是 Owner 已核准替換。

停止條件：已足以提出上述實質差異，不再廣泛重搜同義 Memory 名詞。下一輪只判斷要不要保留 agentic consolidation 的中途深讀能力，進而選主要方案；不先寫 production plan。

## 6. 可重現證據與版本

本輪重新讀取官方 PyPI metadata：LangChain **1.4.0**、LangGraph **1.2.11**、Deep Agents **0.7.13**、LangMem **0.0.30**。最新發布日期分別為 2026-09-03、2026-08-11、2026-09-02、2025-10-27；「最新」不等於「成熟度相同」。來源：[LangChain](https://pypi.org/project/langchain/)、[LangGraph](https://pypi.org/project/langgraph/)、[Deep Agents](https://pypi.org/project/deepagents/)、[LangMem](https://pypi.org/project/langmem/)。

原始碼固定快照：Codex `574a36ff99f0807a24f5b043f593122bf151908d`；LangMem `f8c7ebd6110c124a36995dab645a8cb0eb0b8210`；Deep Agents `4e5f9350e4d77b8bf19e472e8414662d3fa59dc0`。動態 docs 是 2026-09-05 讀取快照，不宣稱永久 API。

唯讀比對官方 wheel，未安裝／執行：LangMem 0.0.30 `knowledge/extraction.py` 與上述固定快照取得文字相同；wheel SHA-256 `142f040014493eebd67e1055c0642f9ab38868b5b1fde5c8f2d39add57f4ba5b`。Deep Agents 0.7.13 已確認所討論的獨立 filesystem middleware 範例與 StoreBackend 操作存在；**沒有宣稱整包 wheel 與 main 全檔相同**。

## 7. 前一輪 Closure（能力同意前）

- Finding：F01–F07；原表的責任分層多數成立，但等價程度、候選範圍與錯誤語意需校正。
- Status：研究修正完成；A/B/C 替換決策待 Owner 討論，未改既有 production authority。
- Affected：本文、原交叉表的相關敘述、OpenAI 系統圖的過時 artifact 引用、current register 與索引。
- Next：就 §5 的 agentic consolidation 差異討論，不重做既有 Memory 概念研究。
- Reopen：官方契約／選定版本變更，或最小實測推翻可用性；本輪未呼叫付費模型、未做產品品質 eval。

## 8. Owner 同意後：先固定能力，再比較兩種工具組合

### 8.1 本輪 preflight 與同意的效力

- Topic／stage：`LLM-Q017`；G3 能力暫時同意 → 元件組合的定向研究。
- Owner 在前輪審核後回覆「OK」；窄幅記錄為：**保留背景 consolidation 在處理途中按需搜尋／深讀資料的能力**，並繼續比較官方元件；不是選定檔案格式、Deep Agents 全套或正式替換 LangMem。
- Binding：延續通用 Memory A／B／C 的研究範圍；`LLM-Q015` 根 `create_agent` 方向不變；production authority 不變。
- 唯一 blocking question：保留這項能力後，**Agent＋紀錄型 Memory tools** 與 **Agent＋檔案 tools** 哪個能更完整承接讀取、整併與修補，且接合與運行代價合理？
- 已回讀：current register／decision process、本文全部、框架官方事實圖全部；重用前輪 OpenAI 固定來源，不重做整份系統圖。
- 不決定：Caliburn／JD 語意、最終 Memory schema、排程與鎖、原始對話 retention、exact budgets、provider、production 或 spike。

### 8.2 補正比較維度：manager 的限制不是整個 LangMem 的限制

**[官方事實]** LangMem 除了 manager，另有供 Agent 使用的 `create_search_memory_tool` 與 `create_manage_memory_tool`；後者可限制允許的動作，前者回傳 Store 命中內容。因此 §2 F01 只約束 **manager 的內部流程**，不能擴張成「LangMem 無法供 Agent 在中途搜尋與修改」。[LangMem tools API](https://langchain-ai.github.io/langmem/reference/tools/)、[Hot-path guide](https://langchain-ai.github.io/langmem/hot_path_quickstart/)

**[版本校正]** 該 LangMem quickstart 仍使用舊 `create_react_agent` 與舊模型例子；研究其工具責任，但不照抄舊入口。LangGraph v1 官方已將入口導向 `langchain.agents.create_agent`。把工具組到新入口是可研究的組合，尚未經本輪相容性實測。[LangGraph v1 migration](https://docs.langchain.com/oss/python/migrate/langgraph-v1)

| 比較項目 | Agent＋紀錄型 Memory tools | Agent＋官方檔案 tools |
|---|---|---|
| 外層模型／工具迴圈 | `create_agent`；不是把 manager 當成 Agent | 同一種 `create_agent`；不要求完整 Deep Agents harness |
| 整理途中搜尋／修改 | LangMem search／manage tools＋LangGraph Store | `FilesystemMiddleware` 的 grep／read_file／write_file／edit_file 等 |
| 選中的 summary 如何深讀 | 現有 search/manage 不是 summary 專用 reader；Store get 是 primitive，模型可用的定位／讀取介面仍須接合 | summary 若保存為 backend file，官方 `read_file` 可直接讀；產生／保存該 summary 仍不是自動的 |
| 明確定位 | 命中 ID／Store key | 命中路徑；路徑也是 locator，不是「不需要 ID」 |
| 內容修改方式 | 以紀錄 ID 提供更新內容；內容 schema 可配置 | 以路徑讀內容、字串編輯；不等於理解結構的語意 merge |
| 保存位置 | Store 中的 records | 可用 StoreBackend 保存虛擬檔案，也仍在 Store；不必落本機 OS 檔案 |

兩者都沒有自動提供完整 OpenAI 候選生命週期、小型導覽形成／更新、跨寫入一致性與耐久排程。

檔案組合來源：[官方 filesystem middleware](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1641-L1721)、[StoreBackend](https://docs.langchain.com/oss/python/deepagents/backends#storebackend-langgraph-store)。本輪再次讀取固定版本原始碼：官方示範獨立接 `create_agent`；`tools` 可選擇暴露哪些工具，但列表必須包含 `read_file`。檔案方案的目錄／讀取／修改可以重用，不能因此推定 readonly 路徑政策或所有錯誤恢復也已配妥。

### 8.3 不新增自製 loop 的接力方式（比較用，不是施工規格）

```text
已形成的 extraction 中間資料＋整併指示
  → consolidation agent（官方 create_agent loop）
      → 讀既有 Memory
      → 有需要才搜尋／深讀相關 summary
      → 模型決定整併、修改或不變
      → 官方工具執行，結果返回同一個 agent
      → agent 繼續補查／修正，或完成
  → Memory／小型導覽的更新結果交回背景流程
```

- **[官方事實]** LangChain Agent 支援 model ↔ tools 的多步迴圈；不必另寫 while-loop 引擎。[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- **[比較推論]** background／hot path 是執行時機，不決定必須使用 manager 或何種儲存格式；LangMem「hot-path tools」可作組合材料，不代表背景 pipeline 已由官方整包實現。
- **[成本界線]** 保留按需能力，不強制每次多查。工具讀寫本身不必另外呼叫生成模型；取得結果後若繼續推理，則仍會有下一個模型 step；語意檢索還可能有 embedding 成本。現階段不能宣稱兩方案哪個品質最高或最省。
- **[已知 recipe 缺口]** Deep Agents 官方 background recipe 的 `search_recent_conversations(query)` 範例實際依 metadata／時間篩選 threads，沒有用 query 做內容檢索。它是示範最近對話取得，不是已完成的語意搜尋或 OpenAI Phase 1 候選消費流程；不能直接照抄當完整解。[官方 background recipe](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)

### 8.4 OpenAI 真的在背景整併途中補查嗎？

**有；這次是直接核對官方 generation 說明與 consolidation prompt，不是從前台 read path 推論。**

- **[官方 SDK 說明]** OpenAI Sandbox Memory 的 Generate memory／Phase 2 明列 `opens conversation summaries when more evidence is needed`。也就是整併候選時，資訊不足可再開較詳細的 conversation summary；不是只能使用起始 prompt 已塞入的內容。這是該 Beta SDK 公開流程，不擴稱所有 OpenAI 產品都逐步相同。[Generate memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/#generate-memory)
- **[Codex 固定快照]** 背景 prompt 要求針對變更候選，在歧義、重複、衝突或需要較強佐證時深讀相關 rollout summaries；並明確禁止這條背景路徑打開 raw sessions／原始 rollout transcripts。所以補查不是任意上網、每次掃全部原話，亦不是要求員工介入。前台原始對話回查不能無條件搬入此處。[候選讀取與 raw 邊界](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L159-L167)、[深讀時機](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L413-L420)
- **[資料不存在時的邊界]** 該 prompt 要先盤點真正存在的 summary；缺檔不可自行捏造路徑或冒充已讀。補查也不能保證資料一定能解決矛盾。[summary inventory 與缺漏處理](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L824-L839)

以上重用並精確定位[既有 OpenAI 系統圖 §5.7](2026-09-05-openai-conversation-context-and-memory-system-map.md#57-第三個細部邊界phase-2-如何形成-durable-memory)的研究，不另建立一份 OpenAI 百科。Owner 本輪再確認同意能力，要求研究接法；尚未核准元件選型。

### 8.5 承接這項能力：可直接重用與仍需接合的責任

| 流程位置 | 已核實可重用 | 仍不能當成已完成 |
|---|---|---|
| 處理候選時發現資訊不足 | `create_agent` 的 model → tool → model 迴圈；agent 可中途要求資料 | 什麼資料值得補查、如何保留不確定性，是整併 instructions 的內容 |
| 找到並讀取 summary | 檔案組合已有 `ls`／`grep`／`read_file`；紀錄組合可用 LangMem search，精確深讀須接 Store get reader | Phase 1 產物必須真的保存且可定位；不由模型捏造不存在的 locator |
| 修改 Memory，取得結果 | 檔案工具 `edit_file`／`write_file` 或紀錄工具 manage；框架執行工具 | 字串／schema 成功不等於語意正確；未保證整批原子性 |
| 工具回報一般讀寫錯誤 | 檔案工具將 backend error 回成 `ToolMessage(status="error")`，agent 可據此重讀／調整 | 有界修正策略、未捕捉例外、仍失敗時如何結束，不能假設框架自動修好 |
| 完成後更新小型導覽 | 同一組工具可修改導覽；依 OpenAI 範例在 Memory 正文之後處理 | 不是 middleware 自動整理；下一次讀者取得新版導覽的 lifecycle 仍需接好 |

工具與載入細節集中於[框架官方事實圖 §5.2／5.4](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md#52-啟動-context)；Agent loop 與紀錄工具來源沿用 §8.2–8.3。

**新增接合發現：導覽 freshness。** 固定快照的 `MemoryMiddleware` 在 state 已有 `memory_contents` 時不重新下載；不能將「背景 Memory 已更新」等同「既有前台 context 自動刷新」。這是需要核對外層 lifecycle 的條件限制，不宣稱 production 已有 bug，也不自行新增版本表／同步引擎。背景 agent 透過 `read_file` 另行取得內容，與固定注入導覽是兩個不同讀取動作。

**本輪推薦不變，但理由更精確：** 先以 `create_agent`＋獨立 `FilesystemMiddleware`＋`StoreBackend` 作主要比較候選，因為補查 summary 與局部修改能直接重用官方工具；虛擬檔案仍可存在 Store，不必開放 OS shell，也不必採完整 Deep Agents harness。紀錄型工具仍是有效備選。這是功能吻合度的研究建議，尚未證明品質／成本優於紀錄型方案，不是框架已選定。

**尚未承諾的細節：** backend 路徑權限、背景與 live update 的 writer 協調、候選排程／重試、導覽刷新、原始資料 retention。獨立 filesystem middleware 的 `_permissions` 在該版本明列 private，不把私有參數當穩定公開接法；下一層須找公開 API／官方組合，不能只寫「薄接線」帶過。[獨立接法與 API 邊界](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1641-L1721)

### 8.6 本輪 closure

- Decision：整併中途補查能力 `WORKING`；**框架與表示方式未選定**。
- Finding：補齊 LangMem tools 路徑；前輪 manager 限制仍成立，但不再構成「只能選檔案」的二分。本輪以 SDK Phase 2 與 Codex prompt 直接確認背景補查範圍，核對官方工具結果與導覽載入限制。
- Recommendation：先用官方檔案組合做較完整的功能對照基準，因為它已有 summary 按路徑深讀／局部文字編輯；同時公平比較紀錄工具路徑缺少的 reader 與導覽接合，不因名稱或行數決定勝負。
- Next：Owner 審閱此功能候選及接合缺口；若繼續定向研究，先補公開 lifecycle／權限接法與紀錄 reader 對等性，再決定主要元件組合。不重問是否需要 Memory／OpenAI 是否有背景中途補查，不開新一輪廣泛名詞研究。
- Reopen：新版本／官方契約改變、後續最小驗證推翻可行性，或 Owner 改變目標。
- Verification scope：文件與公開來源定向核對；沒有安裝／執行新套件、沒有付費模型、沒有產品修改。

## 9. 接合研究續輪：公開接法已補足，候選仍待審閱

為避免本文繼續膨脹，本輪完整候選流程、用途核對、兩方案比較與新證據集中於[框架接力研究](2026-09-05-openai-shaped-memory-framework-composition-research.md)。

- **Finding：** guide 可用官方 Store-aware model hook 讀取；獨立 filesystem 可沿公開 backend policy 擴充；紀錄型精確 reader 可沿官方 ToolRuntime＋Store.get。這些是可組裝的公開接法，不是 turnkey pipeline，也未經本輪相容性實測。
- **新增限制：** LangMem update 要求 UUID 不等於驗證目標存在；Agent Server 同 thread enqueue 不等於 Store namespace 互斥；checkpointed task replay 不提供任意多筆寫入 exactly-once。
- **Recommendation：** filesystem／StoreBackend 維持主要比較候選，因其搜尋／分段深讀／局部編輯與目標互動較直接吻合；紀錄型工具仍可行。不宣稱檔案型品質或成本已優於紀錄型。
- **Status 更新：** Owner 已暫時同意 Q017 的主要 filesystem／StoreBackend 組合方向，Q015 不變，Q016 的 LangMem 優先組合接續為備選；尚未核准完整 artifact schema 或施工。
- **Next gate：** [Q018](2026-09-05-memory-background-live-repair-coordination-research.md) 已完成 B/C 協調與失敗恢復定向研究，策略待審；不重做「OpenAI 是否能背景補查」研究，不自行選排程器或 CAS。
- **Affected／sources：** 官方事實補回框架事實圖 §4.4／5.4／6.3；原始連結與固定 SHA 附於接力研究；current register／README 更新閱讀路由。
- **Reopen：** 官方契約／版本改變、後續最小相容性驗證推翻判斷，或 Owner 調整目的。
