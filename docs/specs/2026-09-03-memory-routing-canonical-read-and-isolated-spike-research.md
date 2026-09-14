# Memory Routing、Canonical Read 與 Isolated Spike 研究

- 日期：2026-09-03
- 狀態：**G4 read shape、isolated semantic-index mechanism 與兩個模型可見 Tool 名稱已獲 Product Owner 核准；framework contract audit 完成；Product Owner 已於 2026-09-03 核准 Revision 2 進入 G5 隔離實驗，但未授權 production 實作**
- 決策來源：[`../current-decisions.md`](../current-decisions.md) 的 `MEM-D000～MEM-D003`、`MEM-Q001～MEM-Q004`

> **2026-09-04 G4.3a 窄幅後繼裁決**：本文記錄的原 G5 search-result 實驗形狀曾排除 Store key／`memory_ref`；該實驗已以 `FAIL_UNPROVEN` 關閉，歷史驗收內容不回寫。後續 G4.1 選用 LangMem native `manage_memory` 後，官方契約顯示 update／delete 必須取得既有 `id`。Product Owner 因此核准 production Working contract 的每筆 search hit 增加 Runtime-issued、model-safe、LangMem-compatible `id`；模型只可原樣帶回，scope／namespace／version 等仍隱藏。最新裁決以 [`2026-09-04 G4 working design §8`](./2026-09-04-llm-machine-effects-and-sibling-results-working-design.md) 為準；本文其餘無 ID 的敘述只描述已結束的歷史 spike，不得再當最新 production input。
- 流程：[`../decision-process.md`](../decision-process.md)
- 本輪只處理：Semantic Memory routing、canonical message reference／read contract，以及驗證它們所需的最小 isolated spike

> 這份文件不是 successor ADR，也不是施工計畫。Production 仍以現行 code、`AGENTS.md` 與 Accepted ADR 0060 為準。舊的 [`2026-09-02-memory-foundation-isolated-spike.md`](../plans/2026-09-02-memory-foundation-isolated-spike.md) 保持 `PAUSED`，不可直接執行；它的 Store-source leaf 與 exact-inventory 前提已被 `MEM-Q001～Q003` 取代。

## 0. 結論先行

已核准的 G4 read shape 是：

```text
LangGraph Checkpointer
  └─ 每份 JD 的 canonical conversation
     ├─ runtime 指派的穩定 message ID
     ├─ 完整員工訊息
     └─ 完整 AI／tool 對話事件

LangGraph PostgreSQL Store
  └─ 同一份 JD 的 focused、可修訂 Semantic Memory collection
     ├─ rich self-contained current content
     ├─ 小型 routing label／title
     └─ runtime 附掛的 canonical message references（只存 pointer，不複製原話）

每次模型呼叫的暫時 Context
  ├─ 本輪輸入
  ├─ 有界近期 conversation
  ├─ 小型、可由 current Semantic Memory 重建的導覽（不是 conversation summary）
  ├─ 以自然語言 query 按需搜尋少量完整 Semantic Memory
  └─ 只有真的需要原句／問答脈絡時，才依 source reference 回讀局部 canonical 問答
```

第一個 spike 只驗證這條 read path。它不先實作 Memory manager prompt、不先決定 production schema、不改 JD，也不翻 production authority。Product Owner 已核准此 spike 只替 focused Semantic Memory 啟用 LangGraph Store semantic index／embedding；raw conversation 不建 semantic index。這不是 Reference RAG，也不能因名稱相近就偷接 Qdrant。

框架分工建議：

- LangGraph `AsyncPostgresSaver`：保存 thread-scoped canonical conversation 與 run／interrupt state；
- LangGraph `AsyncPostgresStore`：保存 application-defined Semantic Memory current collection；
- LangChain `ToolRuntime`：把 scope、Store、thread／run identity 隱藏注入工具，不讓模型填；
- LangGraph `AsyncPostgresStore.asearch`：可承接 namespace-scoped list／filter，配置 semantic index 後承接自然語言 similarity search；
- LangMem `create_search_memory_tool`：證明 `search_memory` 是成熟框架已有的 read-tool 形狀，但其預設 schema 另暴露 `limit／offset／filter`，不能未審核就直接當成 Caliburn 最小 tool contract；
- LangMem `create_memory_manager`：仍是後續 extraction／consolidation 的可替換候選，**不進本輪 read-path spike 的必要路徑**；
- `create_memory_store_manager`：本輪不採，因為它把 retrieval、model decision 與 Store side effects 綁在一起，且官方範例依賴 semantic index；這會同時引入本輪尚未需要驗證的變因。

## 1. 本輪問題與不得偷改的邊界

### 1.1 要回答的問題

在已核准的 `MEM-Q001～Q004` 下，最小 read path 能否同時做到：

1. conversation 只耐久保存一次，且關閉／重啟後仍完整；
2. 模型平常不攜帶整段長訪談；
3. 模型先用小型 Semantic Memory 導覽定向，再以自然語言 query 取得少量、逐筆完整且自成一體的目前理解；
4. 每筆命中只帶輕量 source references；需要核對原句或問答脈絡時，才依 reference 回讀 canonical conversation 的局部問答；
5. A／B 相似案例、員工更正與不存在 reference 不會被混淆；
6. 失敗時可觀察、可停止，不以猜測冒充找到資料；
7. 不先建立 raw-message semantic index，也不複製 employee-source text 到 Store。

### 1.2 本輪明確不決定

- Semantic Memory 的 production 正式 schema；
- Manager prompt、update cadence、hot path／background 的 production 選擇；
- JD 何時產生或如何編輯；
- 最終全量 JD coverage audit 的 pagination／inventory contract；
- production embedding model、top-k、threshold、pgvector、Qdrant 或 Reference RAG；
- UI、跨 JD Memory、跨員工資料共享；
- production migration、successor ADR 或現行資料搬移。

## 2. 已核准產品效果，不重新發明

本設計只承接下列既有 Working Decisions：

- Memory 的唯一產品目的，是讓長訪談後仍能完整理解員工工作與必要細節，以支援高品質 JD；Memory 不直接操控 JD。
- 一名員工只有一份隔離文件、一個持續 thread 與一份 JD；不需要跨 JD Memory。
- 日常回合不必攜帶全部 Memory；最後全面製作／檢查 JD 時，必須可驗證地處理全部有效 Memory。
- canonical conversation 保存完整原始互動；Semantic Memory 保存可修訂的目前理解。
- 相似案例不固定一案一筆 Memory：重複 no-op、補充 update、重要獨立差異才 add、更正 revise、未解衝突保留兩邊。
- 第一層先用 Semantic Memory／小型導覽 routing；需要證據才回讀 canonical conversation；第一版不替每則 raw message 建 semantic index。

完整理由分別在：

- [`2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](./2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md)
- [`2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md`](./2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md)
- [`2026-09-03-memory-canonical-conversation-search-read-reconciliation.md`](./2026-09-03-memory-canonical-conversation-search-read-reconciliation.md)

## 3. 官方共同邊界與差異

### 3.1 Official facts

#### LangGraph／LangChain

1. Checkpointer 以 `thread_id` 保存 graph state snapshot，官方用途包含 conversation continuity、human-in-the-loop、fault tolerance 與 resume。
2. Store 保存 graph state 外的 application-defined key-value data；namespace／key 由應用程式決定。
3. LangGraph 將 conversation history 放在 thread state；Store 可放可長期讀取的 semantic data。兩者可同時使用。
4. `add_messages` 對新 ID append、對相同 ID update，故 message identity 是 reducer 正確性的必要輸入。
5. `ToolRuntime` 的 state、Store、thread／run identity 由 runtime 注入，該參數不出現在模型 tool schema。
6. context engineering 可在單次 model call 前過濾／組裝 transient context，而不必改掉 persistent state。
7. Checkpointer 預設每個 super-step 保存完整 channel value；長 thread 可能增加儲存成本。`DeltaChannel` 可只存 delta，但目前仍為 beta，不能未量測就當 production 前提。
8. Store 以 namespace＋key 保存 JSON documents；`search(namespace, query=..., limit=...)` 可回傳完整 stored `value`，但 natural-language search 需要配置 embedding／semantic index，`AsyncPostgresStore` 預設關閉。
9. Checkpointer 可取 latest state 與 state history，但官方沒有提供 thread message content search 或單一 message-ID read primitive。

#### OpenAI

1. Agents SDK `Session` 保存完整 conversation items；每次 run 前讀取 history，run 後保存新的 user／assistant／tool items。
2. `session_input_callback` 可選擇、重排或縮減送進模型的 history，但不會把被過濾的舊資料當成刪除，也不會重新保存為新事件。
3. OpenAI Agent Memory 與 conversational Session 分開；目前公開的 sandbox Memory 是 beta。
4. Agent Memory read path 採 progressive disclosure：先注入小型 `memory_summary.md`，可能相關時再搜尋 `MEMORY.md`，需要細節才打開 rollout summary。
5. Agent Memory generation 公開為 conversation extraction 與 layout consolidation 兩階段；這是 OpenAI Agents SDK sandbox 的公開實作，不等於 ChatGPT／Codex 產品內部資料庫契約。

#### Anthropic

1. Memory tool 是 client-side protocol：Claude 只提出 `view／create／str_replace／insert／delete／rename`，真正儲存與權限由應用程式執行。
2. Claude 先查看 Memory 目錄，再按需讀取相關檔案；官方指引要求內容 coherent、organized，且非必要不要建立新檔。
3. Managed Agent Memory 建議使用多個小而聚焦的 Memory，不用少數超大檔案。
4. 每次 Memory 變更建立 immutable version；更新可帶 `content_sha256` precondition 做 optimistic concurrency。
5. Memory 可與 compaction 搭配：compaction 管 active model context，Memory 保存需要跨 context 存活的資訊。

#### LangMem

1. `create_memory_manager` 接收 conversation 與 existing memories，回傳 extracted／reconciled collection；可使用簡單字串或 Pydantic schema。
2. `create_memory_store_manager` 會先搜尋 Store、呼叫模型、再套用 Store side effects；官方範例使用 embedding index，並有 `query_limit`。
3. 官方同時提供 hot-path tools 與 background／reflection manager，沒有宣稱單一更新時機適合所有產品。
4. `create_search_memory_tool` 的預設 tool name 是 `search_memory`，以 Runtime config 展開 namespace；模型可見參數是 `query／limit／offset／filter`，結果可包含序列化 Memory 與 raw Store items。
5. PyPI 截至 2026-09-03 的最新發行仍是 `0.0.30`（2025-10-27），屬 pre-1.0；沒有 GitHub Releases。它可減少 extraction／consolidation／search-tool 程式，但不能被當成 authority、完整來源、exact inventory 或 domain completeness 的保證。

### 3.2 跨家共同設計

真正可由公開資料支持的共同點是：

1. **完整 conversation 與整理後 Memory 分層**；
2. **長期資料由 application-controlled durable storage 保存**；
3. **模型 context 是從耐久資料選出的暫時投影，不等於耐久資料本身**；
4. **先給小型導覽／相關項目，需要時再讀更深細節**；
5. **Memory 可更新，且應有版本／一致性保護或等效 guard**；
6. **工具只暴露模型需要決定的語意參數，scope／identity／retry metadata 由 runtime 注入**；
7. **conversation 壓縮與 Memory 保存是不同責任**。

### 3.3 不是跨家共同保證的事項

以下屬 Caliburn mapping 或待驗證，不得偽裝成廠商官方功能：

- 一份 JD 必須在最終檢查時處理全部有效 Memory；
- 不建立重複 employee-source Store leaf；
- Semantic Memory 自動帶 canonical message pointer；
- pointer read 自動回傳多少前後問答；
- 未命中時做多少範圍的 exact scan；
- 一個 Memory record 的正式欄位；
- 多少筆 Memory 算導覽過大；
- 哪一回合必須更新 Memory；
- 沒有 raw-message embedding 仍能達到 Caliburn 所需的 recall。

這些事項若已由 Owner 決定，就作為產品 constraint；若公開資料無法判斷效果，就交給最小 spike，不再用新的抽象層掩蓋未知。

## 4. 現行 code 與 G4 目標的差距

現行 production 並未符合 `MEM-Q001`，這是預期中的 authority 差距，而不是本輪要偷偷修的 bug：

1. [`state.py`](../../apps/api/app/consultant/state.py) 明寫 employee verbatim text 只在 Store；`messages` 雖使用 `add_messages`，但不是完整 canonical conversation。
2. [`run_service.py`](../../apps/api/app/consultant/run_service.py) 只在 agent invocation 暫時建立本輪 `HumanMessage`。
3. [`interview.py`](../../apps/api/app/consultant/interview.py) 將完成後的 `AIMessage` 寫進 graph state。
4. [`views.py`](../../apps/api/app/consultant/views.py) 只從 state 投影 `AIMessage`；員工文字仍走另一個 source owner。
5. Accepted ADR 0060 目前仍規定 Store owning employee source；因此任何 production 改動都必須由 successor ADR 承接。

結論：isolated spike 必須使用獨立目錄／namespace／測試資料，不可把 Q001 直接套進現行 production composition root。

## 5. 三個 G4 方案

### 5.1 方案 A — Canonical Checkpointer＋focused Store＋progressive read（建議）

```text
完整 conversation → Checkpointer messages channel
目前理解 collection → Store
小型導覽 → 每次由 Store current records 重建
相關理解 → 自然語言 query → 少量完整 Memory＋source references
來源深讀 → source reference → canonical message window
未命中 → 有界 exact scan 或澄清
```

優點：

- 完全承接 `MEM-Q001～Q003`；
- 不複製原話、不替每則 raw message 建 embedding；若採 Store semantic search，只索引 focused Semantic Memory；
- 接近 OpenAI Session＋Agent Memory 與 Anthropic session＋Memory 的 progressive disclosure；
- 可用現有 LangGraph PostgreSQL Saver／Store；
- 失敗時能明確知道是 routing miss、bad pointer、canonical read fail 或 context budget fail。

風險：

- LangGraph Store 的自然語言 similarity search 只有配置 semantic index／embedding 才成立；未配置時只能做 list／filter／exact get，不能把它寫成語意搜尋；
- 久遠細節若既沒有被整理成可 routing 的 Memory，也沒有可做 exact scan 的明確詞，可能只剩澄清；
- Checkpointer 長 thread 的儲存量需量測；
- pointer 附掛與相鄰問答窗口是 Caliburn contract，需要 spike 證明。

### 5.2 方案 B — 方案 A＋derived raw-message semantic index

為每則 canonical message 另建可重建向量／hybrid index；hit 後仍回讀 Checkpointer。

優點：可搜尋未進入 Semantic Memory、又被換句話說提起的久遠細節。

缺點：增加 raw text duplication、embedding、privacy、rebuild、staleness 與 ranking；公開大廠 read path 並未證明這是第一層共同必要能力。

判斷：**deferred**。只有方案 A 的代表性 smoke 出現不可接受 long-distance miss 才重開。

### 5.3 方案 C — Store 再保存一份 employee-source text

這是舊 9/2 plan 的前提。它讓來源 listing／read 容易，但形成第二份 canonical text owner，與 `MEM-Q001` 衝突。

判斷：**不採**。只有產品加入獨立 event export／retention，或真 PostgreSQL contract 證明 Checkpointer 無法可靠承擔 canonical conversation，才重開。

## 6. 建議的最小 contract

### 6.1 Canonical conversation

每個 canonical event 至少需要：

- runtime 指派的穩定 `message_id`；
- role；
- content；
- framework 原生可保存的 message／tool metadata。

規則：

1. 模型不填 `message_id`、thread scope、timestamp、version 或 retry metadata；
2. intake retry 使用同一穩定 ID；同 ID 同內容可視為同一事件，同 ID 不同內容必須失敗，而不是靜默覆寫；
3. 員工更正是新的 HumanMessage，不改寫歷史原句；Semantic Memory current head 才反映修訂後理解；
4. 任何 bounded context、trim 或 compaction 都只能改「本次模型看到什麼」，不得破壞 canonical state；
5. spike 需同時保存 HumanMessage、AIMessage 與必要 tool events，不能重演現行只存 AI 的不完整狀態。

第 2 點是 Caliburn 的 deterministic ingestion guard，不是 LangGraph 自動提供的產品語意；LangGraph 只提供 ID-aware reducer primitive。

### 6.2 Semantic Memory 測試表徵

本輪只需要能測 routing 的 fixture shape，不把它定為 production schema：

```text
memory_id      runtime-owned
title          短 routing label
content        rich self-contained current understanding
message_refs[] runtime-owned canonical employee-message references；可為空，但本 spike 的案例需有值
```

限制：

- `message_refs` 只存 pointer，不存 quote、offset 或整段對話；它明確表示 pointer 指向 canonical conversation 的特定 message，避免與整段 conversation ID 或 Reference／RAG source 混淆；
- 本 spike 的 fixture 由 Runtime seed 合法 references。Production 中一輪同時形成多筆 Memory 時，如何把各筆內容精確關聯到一或多則 canonical message，仍屬 Manager contract 未決事項；不得先宣稱 Runtime 能無歧義自動推導；
- Manager 未來仍只應提出最少的 semantic payload；message ID、scope 與儲存 metadata 不交給模型填；
- 本輪不新增 `kind／status／confidence／skill_ids／version／timestamp` 給模型填；
- 未解問題與衝突可先放在 rich content 裡，不因測試而發明 production enum。

### 6.3 小型導覽

導覽不是 conversation summary，也不是第二份 Memory authority；它是由 Store current records 即時重建的 transient projection：

```text
memory_id + title + deterministic short preview
```

它的用途只有讓模型先知道有哪些工作主題，並形成較好的自然語言 query。第一切片不另呼叫模型生成 conversation summary，也不另存導覽 current head。

若導覽在代表性規模下太大，後續才縮成更小 projection 或改成 search-first；不能先以任意 top-k 掩蓋尚未量測的問題。最終全量 JD 檢查仍直接列舉全部 current Memory，不使用導覽作完整性證明。

### 6.4 模型可見工具

Owner 已核准的**語意介面與名稱**最多暴露兩個窄 read tool：

```text
search_semantic_memory(query)
read_conversation_context(message_ref)
```

名稱不是 vendor 標準，而是把已核准責任直接寫進介面：第一個 Tool 搜尋整理後、可修訂的 Semantic Memory；第二個 Tool 依特定 canonical `message_ref` 回讀局部 conversation context。它們不叫 `work_memory` 或 `interview_ref`，避免把 Semantic Memory 誤解成 working memory，也避免把一則 message pointer 誤解成整場訪談 ID。

`search_semantic_memory(query)`：

- 模型唯一輸入是自然語言 `query`；
- Runtime 從目前開啟的 JD／文件取得 scope，固定 current-only filter、最大回傳筆數與權限；模型不填 employee ID、document ID、thread ID、namespace、`limit／offset／filter`；
- 只搜尋該文件的 current Semantic Memory collection；一名員工＝一份文件＝一個 thread，因此不會拿到另一名員工或另一份 JD 的 Memory；
- 回傳 `0..N` 筆完整 Memory。這裡的「有界」是限制筆數與總預算，不是把命中的單筆 Memory 從中間截斷；
- 模型可見成功結果採最小物件：`memories[]`；每筆只有短 `title`、完整 `content` 與 `message_refs[]`。空陣列是合法的「沒有相關結果」，不是錯誤；這是 G5 read-tool adapter 的結果視圖，不是提前決定 production Store schema；
- Store key／`memory_ref`、namespace、similarity score、timestamp、limit／offset 與 backend metadata 不進模型結果；若 spike 需要診斷，可留在 Runtime trace 或 LangChain `ToolMessage.artifact`，不得要求模型回填。

`read_conversation_context(message_ref)`：

- 在同一個目前 thread 的 canonical messages 中解析 reference；
- 成功時回傳 `context[]`，每項只有 `speaker: employee | consultant` 與完整 `text`；內容包含目標員工原話，以及足以還原語意的最小相鄰問答；
- 不存在、失效與其他文件 scope 的 reference 對模型一律是 `reference_unavailable`，Runtime trace 才保留實際原因；這可避免用錯誤差異探測另一份文件是否存在。

兩個 input schema 都只有一個必填字串，且禁止額外欄位：模型只填自然語言 `query`，或把前一個工具實際回傳的 `message_ref` 原樣交回。模型不自行產生 document ID、thread ID、namespace、before／after window、權限、limit、filter 或 retry；這些由 `ToolRuntime`／目前 graph state 注入。Provider 端須使用 strict tool schema；Runtime 仍須做 Pydantic／domain validation，不能把 provider strict 當授權檢查。

「最小相鄰問答」是 Caliburn 必須由 spike characterise 的 read policy，不是假稱 LangGraph 已提供 message-by-ID API。LangGraph 官方提供 latest state／state history；若 canonical `messages` 未被破壞，薄 adapter 可在目前 state 內依 stable message ID 定位。LangChain 官方 `SummarizationMiddleware` 會永久以摘要取代 state 中的舊 messages，故不能套在 canonical message channel；本輪應以 `wrap_model_call` 之類的 transient model-context projection 控制送模內容，而不改 checkpoint state。是否能在長 thread、restart、transient context projection 與更正情境下可靠回傳正確窗口，必須實測。

#### 6.4.1 實際拿誰的 Memory

Scope 來自員工目前開啟的那份 JD／文件，不來自 query，也不由模型選擇：

```text
目前文件 D42
  ├─ Runtime 解析 D42 對應的唯一 interview thread
  ├─ Runtime 解析 D42 對應的 Semantic Memory exact scope
  ├─ search_semantic_memory("接案網站驗收") → 只查 D42 的 current Memories
  └─ read_conversation_context(message_ref) → 只查 D42 thread 的 canonical messages
```

切換到另一份文件後，Runtime 注入的是另一個 scope；同一個 query 不會搜尋 D42。即使目前產品沒有登入／多租戶，這個 per-document 邊界仍是「每名員工一份文件、一個 thread、一份 JD」的資料隔離，不是可省略的 UI 假設。

LangGraph Store 的 `search` 參數是 `namespace_prefix`，不是自動的 exact-namespace security boundary。因此 adapter 必須由可信 `document_id` 建立完整 leaf scope，並驗證每個結果仍屬該完整 scope；模型永遠看不到或傳入這個 scope。實際 tuple 名稱留給 successor design，不在 G4 先定 production schema。

#### 6.4.2 成熟框架覆蓋與已核准 mechanism

- LangMem 官方已有 `create_search_memory_tool`，預設名稱就是 `search_memory`；它證明「由模型用自然語言搜尋 Store Memory」不是自創模式。
- 該 helper 預設讓模型填 `query／limit／offset／filter`。Caliburn 只需要 `query`，其餘是安全、成本與產品 policy，應由 Runtime 固定；因此可用 LangGraph `AsyncPostgresStore.asearch` 加一層極薄 LangChain tool adapter，而不是自建搜尋演算法。
- LangGraph Store semantic search 預設關閉，必須配置 embedding index；沒有 index 時仍可 namespace list／filter／exact get，但不能完成此處的自然語言 similarity search。
- LangGraph Checkpointer 沒有公開的 conversation 內容搜尋或單一 message-ID read primitive；`read_conversation_context` 是以官方 persisted state＋stable message ID 組成的 Caliburn adapter，必須由 isolated spike 證明，不得冒充 framework 內建能力。

Product Owner 已核准第一個 isolated spike 替 **focused Semantic Memory** 啟用 Store semantic index／embedding。這不等於替 raw conversation 建 RAG，也不改變 `MEM-Q003` 對 raw-message index 的 deferred 結論；若 spike 證明召回、scope、成本或延遲不可接受，依 reopen trigger 重開，不以臨時索引 raw messages 掩蓋失敗。

#### 6.4.3 Framework capability audit

下表區分「成熟框架直接提供」與「產品責任無法由框架代替」，避免一面說採框架、一面重寫它已提供的機制：

| 需要的能力 | 優先使用的成熟能力 | 還需要的最薄邏輯 | 判定 |
|---|---|---|---|
| 宣告單一、typed input | Pydantic `BaseModel`＋LangChain `@tool`／`StructuredTool` | 兩個一欄 schema 的描述與空字串檢查 | framework-first |
| Provider strict tool input | `ChatOpenRouter.bind_tools(..., strict=True)` | pinned integration 必須實測 strict 是否真的送出，不能只看型別宣稱 | framework-first；有 integration caveat |
| 隱藏 document/thread/scope/store | LangChain `ToolRuntime` | 從目前文件解析可信 scope | framework-first |
| Tool loop、參數 validation、tool-call/result linkage | LangChain `create_agent`／LangGraph `ToolNode` | 不另寫自製 tool loop | framework-native |
| Semantic Memory similarity search | LangGraph `AsyncPostgresStore.asearch`＋Store embedding index | 固定 current-only policy、最大結果數與 exact scope guard | framework-first |
| 控制哪些欄位被 embedding | LangGraph Store `fields`／per-item `index` | 只選 routing `title／content`，不索引 refs／metadata | framework-native configuration |
| 將現有 embedding SDK 接入 Store | LangGraph Store `ensure_embeddings`／`EmbeddingsLambda` 原生接受 sync／async callable；現行 `openrouter==0.10.8` SDK 有 `embeddings.generate_async` | 隔離實驗只需批次文字→固定維度向量的薄 callable；不自建 ranking、vector table 或 production provider abstraction | framework-first；pinned integration |
| 模型結果與診斷資料分離 | LangChain structured Tool result；必要時 `content_and_artifact`／`ToolMessage.artifact` | 決定最小模型內容；artifact 只在確有診斷需求時使用 | framework-native、非必加層 |
| 讀目前 thread state | `ToolRuntime.state["messages"]` | 依 stable `message_ref` 定位並選出最小連續問答 | framework＋薄 adapter |
| 保留 canonical state、只縮本次 model context | LangChain `wrap_model_call` transient override | 組裝本輪 bounded context | framework-first |
| 模型可修正的 tool error | Pydantic validation、`ToolNode(handle_tool_errors=...)`、執行期可選 `ToolErrorMiddleware`、`ToolMessage(status="error")` | 對外穩定 error code；內部例外留 trace | framework-first；須依錯誤階段選 hook |
| 有界 read-only retry | LangChain `ToolRetryMiddleware` | 套用既有最大次數，不讓模型填 retry | framework-native policy |

刻意**不直接採用** LangMem `create_search_memory_tool`，不是因為要自建搜尋：它預設把 `limit／offset／filter` 暴露給模型，並回傳 framework raw items；本產品已知 scope 與成本 policy 不應轉嫁給模型。薄 adapter 仍直接呼叫 `AsyncPostgresStore.asearch`，沒有自行實作 embedding、vector ranking 或 Store。

Pinned artifact 另有一項必驗 caveat：`langchain-openrouter==0.2.7` 的 `ChatOpenRouter.bind_tools` 支援 `strict=True`；但 `langchain==1.3.15` 的 `create_agent` 只會對其辨識為 `BaseChatOpenAI` 的 model 自動補 strict，而 `ChatOpenRouter` 不是該 subclass。因此 Stage 0 必須檢查實際送出的 tool definition，而不能因 final structured response 已 strict 就假設普通 read tools 也 strict。Isolated spike 可直接以官方 `bind_tools(strict=True, parallel_tool_calls=False)`＋`ToolNode` 驗證；production adapter 是否需要調整留給 successor design。

另有兩項 pinned contract 細節：

1. `ToolErrorMiddleware` 的公開說明明確指出，它只攔工具執行期間的例外；argument binding／Pydantic validation 在 `ToolNode` 更早轉成 `ToolInvocationError`。若要統一成 `invalid_input`，isolated graph 應使用 `ToolNode(handle_tool_errors=...)` 的公開 hook；不能寫成 middleware 自動涵蓋所有錯誤。
2. 現行 `langchain-openrouter` 只匯出 Chat integration，沒有 Embeddings class；但其 transitive、鎖定的 `openrouter==0.10.8` 已有 typed `embeddings.generate_async`，而 LangGraph Store 官方 `ensure_embeddings` 能直接把 async callable 包成 `EmbeddingsLambda`。因此 spike 不必加 `langchain-openai`、不改 production lock，也不必自製完整 Embeddings class；只保留 OpenRouter response→按 index 排序的向量陣列轉換與 receipt 記錄。

#### 6.4.4 最小 input／result／error contract 稽核

```text
search_semantic_memory
  model input:  { query: string }
  success:      { memories: [{ title, content, message_refs[] }] }
  no match:     { memories: [] }

read_conversation_context
  model input:  { message_ref: string }
  success:      { context: [{ speaker: employee | consultant, text }] }
  unavailable:  ToolMessage(
                  status="error",
                  tool_call_id=<runtime-issued>,
                  content='{"error":{"code":"reference_unavailable"}}'
                )
```

共同規則：

1. input object 所有欄位必填、`additionalProperties=false`，Provider tool binding 明確啟用 strict；目前沒有 optional、union、nested input 或模型生成 ID；
2. Tool result 是 **Runtime 產生並驗證**，不是第二份 Structured Output，也不是叫模型填欄位。成功函式可回傳上述 Python object，現行 LangChain 會將它 JSON-serialize 到 `ToolMessage.content`；`tool_call_id`／`status` 由 framework 維護；
3. success 不另加 `status: found`，因為有資料就是成功；搜尋空陣列是合法結果；
4. schema／空字串錯誤以 `ToolMessage(status="error")` 中可解析的 JSON `content` 回 `{"error":{"code":"invalid_input"}}`；不存在、失效與跨 scope pointer 同樣回 `reference_unavailable`；暫時性 backend failure 可依既有 read-only retry policy 有界重試，耗盡後回泛化 `temporary_failure`；未預期例外停止 run 並留內部 trace，不把 stack、SQL、namespace 或另一份文件資訊送模型。LangChain `ToolMessage` 沒有獨立的頂層 `code` 欄位，故不得實作成不存在的 framework field；
5. Tool description 必須寫明用途、何時用／不用、成功欄位、空結果與錯誤行為。`search_semantic_memory` 是 relevance-based bounded search，不能宣稱列舉全部 Memory；最終 JD 全量盤點走另一條 deterministic exact-scope pagination path，不把 pagination 參數塞進這兩個模型 Tool；
6. `message_ref` 只可使用本輪 Context 或 Tool 實際回傳的值；Runtime 仍要驗 scope，不能信任「模型應該不會捏造」。
7. `ToolErrorMiddleware` 不冒充 validation-error handler；若採 explicit `ToolNode`，以其公開 `handle_tool_errors` 正規化 `ToolInvocationError`，未預期例外仍向外拋出並停止。
8. Store 的 embedding adapter 使用 framework 支援的 async callable contract；deterministic test 可注入固定向量 callable，live smoke 才呼叫 OpenRouter embeddings，兩者皆不得另寫 similarity ranking。

這個 contract 符合 OpenAI「不要讓模型填應用程式已知參數、明確描述輸出與錯誤、strict schema」以及 Anthropic「清楚的 tool description、typed input、以 error tool result 回饋」的公開作法；具體名稱、每筆回傳欄位與同 scope error 合併是 Caliburn 對產品資料邊界的 mapping，不冒充兩家公司使用完全相同 JSON。

#### 6.4.5 本輪沒有假裝解決的事項

- LangGraph Store 目前這條路徑提供 semantic similarity，不等於 lexical＋vector hybrid ranking；第一個 spike 只驗證已核准的 focused-Memory semantic index。Production 是否需要 hybrid recall，要由代表性 miss 證據重開，不能先自建搜尋引擎。
- `search_semantic_memory` 是日常按需召回，不是 `MEM-D003` 的 final full-memory audit。後者可使用 Store 無 query 的 exact-scope listing＋pagination，但 pagination／mutation contract仍在本輪 out of scope。
- 若某項久遠原話從未被整理進任何 Semantic Memory，也沒有可用 `message_ref` route，這兩個 Tool 不保證憑空找到它；Stage 2 的缺 route 情境必須誠實澄清或觸發 reopen，不能用幻覺補齊。

### 6.5 有界 Context 組裝

一次 model call 的輸入概念如下：

```text
系統／Skill 指令
+ 本輪員工訊息
+ 少量近期 canonical messages
+ 小型 Memory 導覽
+ `search_semantic_memory` 按需讀回的少量完整 Memory
+ `read_conversation_context` 按需讀回的 canonical conversation window
```

「近期」與最大 token 數不在文件內拍腦袋定值。Spike 應記錄實際 token／latency，並以代表性 transcript 找到可接受界線。

不使用以下方式：

- 把完整 conversation 每輪傳給模型；
- 把完整 Semantic Memory 每輪傳給模型；
- 為了 context 縮短而刪除 canonical messages；
- 讓模型自行填 scope、ID 或 canonical read window；
- 把 prompt caching 當成縮短 context 的替代品。

## 7. G5 isolated spike 設計

### 7.1 假設

> 在不建立 raw-message semantic index、不複製 employee source、也不把完整歷史送入模型的前提下，小型導覽＋focused Semantic Memory search＋source-reference deep-read 能找回相似案例的重要久遠細節、更正後目前理解與必要原始問答；若不能，失敗會產生足以重開方案 B 的可觀察證據。

### 7.2 隔離與成本上限

- 建立 repo 內獨立 spike 目錄，不 import production composition root；
- 使用獨立 PostgreSQL namespace／thread IDs；
- 不改 `apps/api/uv.lock`，LangMem 如需比對只能以一次性 pin `0.0.30` 使用；
- deterministic stages 不呼叫模型；
- live stage 使用 `gpt-5.6-luna`、`medium`，最多 3 次 model calls、最多 2 次 tool round-trip／情境、不得自動無界重試；
- 不寫入 `.env`、不輸出 API key、完整 token／latency／attempt receipt 要留在實驗報告；
- 不接 production、UI、JD、Reference RAG、Qdrant 或 raw-conversation embedding。Spike 只替 focused Semantic Memory 啟用隔離的 Store semantic index，並記錄 embedding 成本與延遲。

### 7.3 Stage 0 — Framework contract characterization

不呼叫模型，確認實際 pinned artifact：

1. 現行 repo pins 是 `langchain==1.3.15`、`langgraph==1.2.11`、`langgraph-checkpoint-postgres==3.1.2`；截至 2026-09-03，PyPI 最新 stable 分別是 LangChain `1.3.18`、LangGraph `1.2.11`、PostgreSQL checkpointer `3.1.2`。Spike 先用現行 production-compatible pins 驗證 read contract；LangChain patch 升級另列 maintenance finding，不在本實驗偷改依賴。`1.4.0a*` 是 pre-release，不因「版本較新」就當 production baseline；
2. `HumanMessage／AIMessage` 可由 runtime 指定穩定 ID；
3. `add_messages` 對不同 ID append、相同 ID update；應用層 guard 能阻止 same-ID different-content；
4. `AsyncPostgresSaver` 可在同 thread restart 後取回完整最新 state；
5. `AsyncPostgresStore` 可依同一 JD scope 寫入／讀取 focused Memory；
6. 啟用 semantic index 後，`asearch(query=...)` 會回傳相同 document scope 的完整 stored value，而不是只有不可回讀的片段；另以未配置 index 的 characterization 明確證明該路徑不能假裝是 semantic search；
7. LangMem `create_search_memory_tool` 的實際 schema 與結果形狀只作 framework characterization；產品工具只把 `query` 暴露給模型；
8. 兩個產品 Tool 的 JSON Schema 各只有一個 required string、禁止 additional properties；實際 provider payload 確實是 strict，而不是只通過本機 Pydantic；
9. `ToolRuntime` scope 不出現在模型 schema；
10. latest checkpoint 的 canonical messages 不會因 transient context filter 被刪除；並用負向 characterization 證明不能把會永久取代 state messages 的 `SummarizationMiddleware` 放在 canonical channel；
11. 在 latest canonical `messages` 內可用 runtime-issued stable ID 找到目標訊息並取得相鄰問答；不存在或其他 scope 的 reference 對模型都只回 `reference_unavailable`；
12. search 的空陣列是成功；Tool 函式回傳物件時，現行 framework 產出的 `ToolMessage.content` 是可解析 JSON；schema／reference／暫時性 backend error 會分成穩定、無敏感細節的 `ToolMessage(status="error")`，且沒有自動無界重試；
13. async embedding callable 只收到 `title／content` 對應文字，回傳固定維度向量；`message_refs`、namespace 與 metadata 不進 embedding；
14. OpenRouter chat tool schema 與 embedding request 都經 SDK 公開接口組裝；測試必須觀察實際 request／response contract，不能只看本地型別。

### 7.4 Stage 1 — Deterministic long-thread fixture

建立至少 40 組員工↔顧問訊息，包含：

- A 案：餐飲預約網站，保留至少三個只屬 A 的細節；
- B 案：健身會員網站，與 A 都屬接案前端開發，但有至少三個不同細節；
- 通用理解：需求訪談、前端實作、串接、驗收等共同模式；
- 更正：先說 B 使用會員 API，後改為 CSV 匯入；
- 未回答問題：一項會影響工作理解但尚未獲答的問題；
- 很久後以專有名詞與換句話說各指涉一次 A／B。

Store 以 deterministic fixture seed focused current Memories，避免把 Manager prompt／schema 混進本輪 read-path 測試。

驗證：

1. latest checkpoint 仍有完整、有序的 Human／AI messages；
2. restart 後內容與 IDs 不變；
3. Store 沒有 employee-source text 副本；
4. 相似案例不是每則訊息一筆 Memory，也沒有把 A／B 獨有差異抹平；
5. 每個有效 pointer 都能在相同 scope 找到 canonical message；
6. bad／cross-scope pointer 對模型同樣回 `reference_unavailable`，Runtime trace 可診斷但不洩漏其他 JD；
7. 同一 intake retry 不產生重複 canonical event；
8. transient context 只含近期窗口＋導覽，不含完整 thread；
9. `search_semantic_memory` 不接受或洩漏 document／thread scope，且每筆命中完整返回；
10. `read_conversation_context` 只接受上一層實際回傳的 `message_ref`，能把孤立短答與前一個顧問問題一起還原；
11. model-visible search result 不含 Store key、score、namespace、timestamp 或分頁控制；
12. 兩個 Tool 可由 LangGraph `ToolNode` 完成 call/result linkage 與 Runtime injection，不另寫 agentic tool loop。

### 7.5 Stage 2 — Tiny Luna smoke

只測三個會改變架構選擇的問題：

1. **長距離 A 案細節**：模型從導覽形成 query，搜尋到完整 A Memory，再依 source reference 回讀 A 的問答，回答三個獨有細節；
2. **A／B 區分＋更正**：模型不得把兩案混成同一案例，且 B 採較新 CSV 說法，不把舊會員 API 當 current fact；
3. **缺 route**：導覽沒有相關 Memory 時，模型必須使用被提供的有界 fallback 結果或承認需要澄清，不可捏造。

每個 case 保存：實際 model input 的 message IDs／Memory IDs、tool calls、tool results、輸出、token、latency、attempt count 與 pass／fail。

### 7.6 Stage 3 — Storage growth characterization

不呼叫模型，建立 40／100／200 turn 三個 checkpoints fixture，量測：

- latest state 讀取時間；
- 每增加一組訊息的 checkpoint write 時間；
- PostgreSQL checkpoint rows／bytes 的成長；
- restart 後讀取與 state equality。

先量測目前穩定預設，不先採 beta `DeltaChannel`。只有預設在代表性規模不可接受，才另做 DeltaChannel side experiment；beta 結果不能自動成為 production 選擇。

### 7.7 Pass／fail

全部成立才算支持方案 A：

1. canonical conversation 完整、隔離、可重啟、可冪等；
2. 模型輸入沒有完整 conversation／完整 Memory collection；
3. A／B 獨有細節可由 natural-language Memory routing＋deep-read 找回；
4. 更正後 current fact 優先，舊原句仍可稽核但不重新生效；
5. bad／cross-scope reference 不造成資料洩漏或 silent miss；
6. 相似案例沒有近線性 Memory 膨脹；
7. Luna smoke 在 call／tool／token 預算內完成，沒有無界修正；
8. storage growth 有實測數據，而非宣稱「Checkpointer 應該沒問題」。

下列任一情況觸發 stop／reopen：

- 只索引 focused Semantic Memory 仍無法在 A／B／更正案例找回必要細節；
- 導覽在小型代表資料已超過可接受 context；
- canonical message pointer 無法穩定解析問答脈絡；
- Checkpointer 在合理 thread 規模出現不可接受儲存／延遲；
- LangGraph 現行 stable API 無法做到非破壞 context projection；
- 需要增加第三份 canonical text 才能通過。

失敗不以增加重試、放大全部 context 或臨時替 raw conversation 加 embedding 掩蓋；先寫 report，再回到 `MEM-Q003／MEM-Q004` 依失敗原因重開。

## 8. 為什麼這個 spike 不再比較 C1／C2

舊計畫比較 LangMem core manager（C1）與 Store manager（C2），當時尚未收斂 conversation owner、相似案例與 canonical read path。現在：

- `MEM-Q001～Q003` 已把本輪最重要未知縮成 read path；
- 既有 16-turn Luna 實驗已證明 `create_memory_manager` 在簡單資料可做 add／update／no-op，但沒有證明 durability／routing／deep read；
- 同時比較 C1／C2 會把 embedding retrieval、Store side effects、Manager schema 與 read path 混成一個實驗，失敗後無法歸因；
- LangMem 仍是 pre-1.0，可用於後續 manager leaf，但不應阻塞 framework-native persistence／read contract。

因此先完成 read-path spike；Manager contract 另開下一個單一決策題。這不是排斥框架，而是避免讓一個非穩定 helper 決定 authority。

## 9. G4 review checklist

Product Owner 已核准以下五點；framework contract audit 已完成，下一步才可寫 isolated spike plan：

1. 是否同意第一個 spike 只驗證 read path，不同時設計 Manager schema／prompt？
2. 是否同意模型只看到「自然語言搜尋工作 Memory」與「依 reference 深讀訪談脈絡」兩個窄語意工具，其餘 scope／limit／窗口由 Runtime 注入？
3. 是否同意小型導覽為 transient projection，不另存第二份導覽 Memory？
4. Isolated spike 為 focused Semantic Memory 啟用 LangGraph Store semantic index／embedding，同時維持 raw-message semantic index deferred。
5. 模型可見名稱採 `search_semantic_memory(query)` 與 `read_conversation_context(message_ref)`；輸入只保留一個語意參數，scope／限制／窗口／retry 均由 Runtime 管理。

下一步寫新的 `docs/plans/2026-09-03-...isolated-spike.md`。Plan 必須逐項引用本文件的 contract、caveat、stop/reopen 條件；Plan review 通過前不寫實作碼。

## 10. 本輪證據分類

| 主張 | 類別 | 結論 |
|---|---|---|
| Checkpointer 保存 thread state／conversation | Official fact | LangGraph 官方直接支持 |
| Store 保存 application-defined durable data | Official fact | LangGraph 官方直接支持 |
| model context 可過濾而不改 persisted session | Official fact | OpenAI Agents SDK 與 LangChain context engineering 直接支持 |
| progressive disclosure／按需深讀 | Official fact | OpenAI Agent Memory、Anthropic Memory tool／store 直接支持 |
| 多筆小而 focused Memory | Official fact | Anthropic Managed Agent Memory 直接建議；OpenAI layout 亦採 summary→index→detail 層次 |
| 同一 JD 仍用 Store 保存 Semantic Memory | Caliburn mapping | LangGraph Store 不限只能跨 thread；本產品以 document scope namespace 使用 |
| 不建立重複 source leaf | Working product decision | `MEM-Q001`；不是廠商通用保證 |
| pointer 只存 canonical message ID | Working product decision＋G4 contract | `MEM-Q001／Q003` 已允許；本文件補最小 read contract |
| LangMem 提供 `create_search_memory_tool` | Official fact | framework 已有 natural-language Memory search tool；預設另暴露 `limit／offset／filter` |
| Store natural-language search 需要 semantic index | Official fact | LangGraph／AsyncPostgresStore 官方明示 semantic search 預設關閉，須配置 embedding |
| Store embedding 可由 async callable 提供 | Official fact＋pinned integration | LangGraph `ensure_embeddings` 公開接受同步／非同步批次 embedding function；隔離 spike 可直接接現行 OpenRouter SDK 的 embeddings API，不必新增另一套 Embeddings framework 或自寫向量搜尋 |
| 模型只填 query，scope／limit／filter 由 Runtime 固定 | Caliburn mapping | 依 ToolRuntime hidden injection、單一 JD 隔離與 schema 簡化要求導出 |
| strict tool input＋Runtime validation | Official capability＋Caliburn mapping | OpenAI／Anthropic 均提供 strict tool schema；Pydantic／LangChain 驗證可用，但 OpenRouter pinned binding 必須實測 |
| Tool result 只回最小必要欄位 | Official guidance＋Caliburn mapping | LangChain structured result／artifact 可分流；OWASP 要求明確 response schema 與最小資料暴露；具體 `memories／context` 欄位是本產品的 G5 adapter view，不冒充 vendor 標準 |
| Tool result／error 的 payload 放在 JSON `ToolMessage.content` | Pinned framework fact＋Caliburn mapping | 現行 LangChain 會把 Tool 回傳 object JSON-serialize；`ToolMessage` 有 `status／content／artifact`，沒有頂層 `code`；穩定 public error code 由薄 adapter／middleware 正規化 |
| validation error 由 `ToolNode` 處理；tool execution error 才進 `ToolErrorMiddleware` | Official framework fact | LangGraph `ToolNode` 的 `handle_tool_errors` 明示涵蓋模型提供無效參數造成的 invocation error；LangChain `ToolErrorMiddleware` 明示 argument binding／validation 已在上游處理，不會進入其 handler |
| source deep-read 使用 stable message reference | Working product decision＋G4 contract | `MEM-Q001／Q003` 已允許；Checkpointer 沒有公開的 message-ID read primitive，需 spike characterise 薄 adapter |
| 不對模型區分 cross-scope 與 missing | Security mapping | Runtime 內部可診斷；模型只得一致的 unavailable，避免 object existence enumeration |
| canonical state 不使用 persistent summarization | Official fact＋Caliburn mapping | LangChain 明示 SummarizationMiddleware 會永久取代 state messages；本產品改用 transient model-context override |
| 不建立獨立 conversation summary | Working product decision | canonical conversation＋Semantic Memory＋可重建導覽已承擔所需責任；需要新 summary 的失敗證據出現前不加第四層 |
| final JD 全量處理全部有效 Memory | Working product requirement | `MEM-D003`；不是 vendor Memory 的普遍保證 |

## 11. 直接來源

### OpenAI

- [OpenAI Agents SDK — Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK — Session input callback](https://openai.github.io/openai-agents-python/ref/memory/util/)
- [OpenAI Agents SDK — Agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [OpenAI API — Function calling／strict mode 與 function 定義最佳實務](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI API — Model guidance／Tool output 與 error contract](https://developers.openai.com/api/docs/guides/latest-model)

### Anthropic

- [Anthropic — Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Context windows／compaction](https://platform.claude.com/docs/en/build-with-claude/context-windows)
- [Anthropic — Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Anthropic — Handle tool calls／`is_error`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)

### LangChain／LangGraph／LangMem

- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- [LangGraph — Graph API／`add_messages`](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [LangChain — Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — Short-term memory／trim、delete 與 persistent summarization 的差異](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [LangChain — Tools／`ToolRuntime`](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — Messages／`ToolMessage.artifact`](https://docs.langchain.com/oss/python/langchain/messages)
- [LangChain — Long-term Memory／Store namespace、JSON document 與 semantic search](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [LangGraph — Store reference／list、pagination 與 semantic search](https://docs.langchain.com/oss/python/langgraph/stores)
- [LangGraph — PostgreSQL Store／semantic search 預設關閉](https://reference.langchain.com/python/langgraph.store.postgres/aio/AsyncPostgresStore)
- [LangGraph — `ensure_embeddings` 接受 sync／async callable](https://reference.langchain.com/python/langgraph.store/base/embed/ensure_embeddings)
- [LangGraph — `ToolNode` 與 `handle_tool_errors`](https://reference.langchain.com/python/langgraph.prebuilt/tool_node/ToolNode)
- [LangChain — `ToolErrorMiddleware` 只處理 tool execution error](https://reference.langchain.com/python/langchain/agents/middleware/tool_error/ToolErrorMiddleware)
- [LangMem — `create_search_memory_tool`](https://langchain-ai.github.io/langmem/reference/tools/)
- [LangMem — Memory API](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem — PyPI 0.0.30](https://pypi.org/project/langmem/)
- [LangChain — PyPI release metadata](https://pypi.org/project/langchain/)
- [LangGraph — PyPI release metadata](https://pypi.org/project/langgraph/)
- [LangGraph PostgreSQL Checkpointer — PyPI release metadata](https://pypi.org/project/langgraph-checkpoint-postgres/)

### OpenRouter

- [OpenRouter — Submit an embedding request](https://openrouter.ai/docs/api/api-reference/embeddings/submit-an-embedding-request)
- [OpenRouter — List all embeddings models](https://openrouter.ai/docs/api/api-reference/embeddings/list-all-embeddings-models)
- [OpenRouter — Client SDKs](https://openrouter.ai/docs/client-sdks/overview)

### Security contract

- [OWASP API Security 2023 — Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- [OWASP API Security 2023 — Broken Object Property Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/)

## 12. Review closure（mechanism 已完成）

- Decision／finding：`MEM-Q004` read shape、focused Semantic Memory semantic-index mechanism、兩個 Tool 名稱與最小 contract 已收斂；成熟框架覆蓋與 pinned integration caveat 已完成稽核
- Owner decision：核准小型導覽 → `search_semantic_memory(query)` → 少量完整 Memory＋`message_refs[]` → 必要時 `read_conversation_context(message_ref)`；第一版不另建 conversation summary；只索引 focused Semantic Memory，不索引 raw conversation
- Status：G4 complete；Revision 2 plan 與 final audit 已完成，Product Owner 已於 2026-09-03 授權 G5 隔離實驗；production 仍未授權
- Affected artifacts：本文件與 [`../current-decisions.md`](../current-decisions.md)；未修改 ADR、plan 或 production
- Reopen trigger：isolated spike 無法在 scope、完整記憶、source deep-read、成本或延遲門檻內成立；或官方 primitive 改變
- Next gate：寫 isolated spike plan → plan review → 才能執行 G5
