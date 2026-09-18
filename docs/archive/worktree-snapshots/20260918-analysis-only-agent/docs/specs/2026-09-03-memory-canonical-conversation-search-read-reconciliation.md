# Canonical conversation search／read reconciliation

- Topic ID：`MEM-Q003`
- 階段：**G3 Product Owner 已核准修正後方案 B**
- 狀態：**Working Decision；不是 production authority**
- 最後核對：**2026-09-03**
- 決策入口：[`../current-decisions.md`](../current-decisions.md)

## 0. 白話結論

OpenAI、Anthropic、Google、AWS 與 LangGraph 的最新公開機制都沒有提供「同一份 canonical conversation 同時就是完整歷史權威，又能直接做語意搜尋」的單一 primitive：

- Conversation／Session／Checkpointer 負責保存與分頁讀取原始事件；
- Vector Store／Memory Bank／Long-term Memory／LangGraph Store 另外負責語意搜尋；
- 原始事件 API 通常只支援 ID、時間、類型、metadata 與 pagination，不支援對全部原句做 semantic query。

因此 `MEM-Q003` 沒有一個可直接照抄的「廠商共同 conversation-search API」。進一步核對 OpenAI Codex／Agents SDK 與 Anthropic 公開的實際 read path 後，最貼近共同架構的候選修正為：

> **方案 B：Checkpointer 繼續是完整 conversation 的唯一 authority；日常先搜尋已核准的 Semantic Memory／小型導覽，命中後才依 Runtime 維護的 canonical message reference 回讀 Checkpointer 原始問答。只有 Memory 沒命中、員工要求精確舊原話或需要驗證時，才做有界 exact scan；第一版不替每則原始訊息建立 semantic locator。**

OpenAI 公開路徑採 `memory_summary.md → MEMORY.md 關鍵字搜尋 → 少量 rollout summaries／exact evidence` 的 progressive disclosure；Anthropic 採 Memory files 按需 `view`，並把 compaction、session transcript 與 persistent Memory 分開；Google／AWS 的 semantic retrieval 也搜尋整理後的 Memory records，而非 raw events。這些資料支持「先用整理後 Memory 導覽，再回原始來源」，**不支持宣稱每則原始訊息都應預設建立向量副本**。

若代表性長訪談證明上述路徑漏掉重要久遠細節，才重開方案 C：為 canonical conversation 建可重建的 raw-message locator／hybrid index。這是有證據後的升級，不是第一版預設。

本輪不改 production schema、graph、tool 或 UI，也不先接 Qdrant。

## 1. Preflight

```text
Topic ID: MEM-Q003
Binding decisions: MEM-D000～MEM-D003、MEM-Q001、MEM-Q002
Blocking question:
  canonical conversation 要用哪個成熟 search/read primitive，
  才能在長 thread 找回 A／B 案例原句與問答上下文，
  同時不形成第二份 conversation authority？
Out of scope:
  Semantic Memory 正式 schema、Manager prompt、JD 編輯、Reference RAG、
  production migration、Qdrant、跨 JD Memory。
```

不可被候選推翻的上游效果：

1. 一名員工／一份 JD／一個持續 thread；
2. Checkpointer 是員工＋顧問完整 conversation 與 graph／run／interrupt state 的 canonical owner；
3. Store 的 Semantic Memory 是可修訂目前理解，不取代原始 conversation；
4. 相似 A／B 案例的全部原始細節耐久保留；
5. 日常 Context 有界；長距離指涉可按需找回；
6. 搜尋失敗不能讓衍生索引冒充原始真相。

## 2. 需要的能力，不是要先選資料庫

`MEM-Q003` 要解的是下列能力：

- **exact scope**：只能搜尋目前 `document_id／thread_id`；
- **bounded recall**：不把整段歷史送入模型；
- **semantic recall**：即使員工換句話說，也能找到可能相關片段；
- **canonical read**：最後交給模型的是 Checkpointer 中的原始員工＋顧問訊息；
- **turn context**：不能只取「對／不是／那個」這類孤立回答，必須包含相鄰提問或必要上下文；
- **runtime-owned identity**：message ID、scope、時間、排序與 limit 都由 Runtime 提供，模型不填；
- **safe staleness**：索引漏寫、過期或損壞時，最多是召回退化，不能改變 conversation；
- **rebuildability**：索引可由 Checkpointer 全量重建；
- **clarify instead of guess**：候選不足以辨認「A 案」時，回到員工澄清。

## 3. 官方機制逐家核對

### 3.1 OpenAI

[Conversations Items List](https://developers.openai.com/api/reference/python/resources/conversations/subresources/items/methods/list) 可依 `after`、`limit`、`order` 分頁列出 conversation items；官方 schema 沒有文字或 semantic query。相對地，[Vector Store Search](https://developers.openai.com/api/reference/python/resources/vector_stores/methods/search) 另有 `query`、filter、ranking 與 query rewriting，搜尋的是 vector-store chunks，不是 Conversation Items 本身。

[OpenAI Codex read path](https://github.com/openai/codex/blob/main/codex-rs/ext/memories/templates/memories/read_path.md) 與 [OpenAI Agents SDK Agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/) 又提供了更具體的產品路徑：先注入小型 `memory_summary.md`，相關時以關鍵字搜尋 `MEMORY.md`，再只開啟 1～2 份相關 rollout summaries；需要精確命令、錯誤或 evidence 時才深入原始 rollout。Agents SDK 也明確把 conversational Session memory 與 distilled Agent memory 分開，並以兩階段 extraction／consolidation 建立上述導覽。

**直接事實**：OpenAI 將 canonical conversation 的 list/read、整理後 Memory 與獨立 retrieval resource 分開；其公開 Codex／Agents SDK read path 是 progressive disclosure＋keyword routing＋按需 evidence deep-read，不是替每則 raw message 建公開的 semantic index。

### 3.2 Anthropic

[Managed Agents List Events](https://platform.claude.com/docs/en/api/beta/sessions/events/list) 可依時間、event type、順序與 cursor 分頁讀取 user／agent events；沒有原句全文或 semantic search 參數。[Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) 則是另一套 client-side `/memories` 檔案 CRUD，由 Claude 按需 `view`；應用程式自己提供 storage。

[Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory) 將 Memory 表達成 path-addressed text documents，掛載到 session 後由 agent 用一般 file tools 按需讀寫；每次變更建立 immutable version。[Dreams](https://platform.claude.com/docs/en/managed-agents/dreams) 另以既有 Memory store＋1～100 份 past session transcripts 產生新的整理後 store，合併重複、替換 stale／contradicted entries，但目前仍是 research preview。Memory Tool 官方也建議長流程同時使用 compaction 與 persistent Memory：前者縮小 active context，後者保存不能被摘要丟失的資訊。

**直接事實**：Anthropic 保存完整 session events，也提供 JIT Memory read 與獨立 consolidation；公開機制沒有要求替每則 session message 建 semantic locator，也沒有公開「對 session 原始全文做 semantic search」的同一 primitive。

### 3.3 Google

[Agent Platform Sessions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions) 將 session events 定位為 conversation 與長期 Memory 的 definitive source。[events.list](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/v1beta1/projects.locations.reasoningEngines.sessions.events/list) 支援 pagination、timestamp filter 與排序，沒有文字／語意 query。[Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank) 另外從 session events 生成／更新 memories，再以 all-list 或 similarity search 取回。

**直接事實**：Google 明確分離 definitive session events 與可被語意取回的 Memory Bank。

### 3.4 AWS

[AgentCore Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html) 將 raw interactions 存為 short-term events，將抽取／consolidate 後的內容存成可 semantic search 的 long-term memory records。[ListEvents](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListEvents.html) 支援 session scope、pagination 與 metadata filter；一般 semantic query 位於 `RetrieveMemoryRecords`，不是 raw events。

**直接事實**：AWS 的 raw event 可用結構化 metadata 縮小範圍，但 semantic search 仍位於衍生 long-term records。

### 3.5 LangGraph／LangChain

[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 說明 Checkpointer 以 thread 保存每個 graph step 的 state snapshot，提供 `get_state`／`get_state_history`；[LangGraph backward-compatibility guidance](https://docs.langchain.com/oss/python/langgraph/backward-compatibility) 更直接說明 LangGraph 不維護 thread state 的內容搜尋索引。相對地，Store 提供 namespace、CRUD、list 與可選 semantic search。[AsyncPostgresStore 3.1.2 reference](https://reference.langchain.com/python/langgraph.store.postgres/aio/AsyncPostgresStore) 提供 PostgreSQL＋pgvector 的 optional vector search，且本 repo 已鎖定 `langgraph==1.2.11`、`langgraph-checkpoint-postgres==3.1.2`。

但「套件存在」不等於「目前已啟用」：本 repo 的 `docker-compose.yml` 仍使用一般 `postgres:16`，建立 `AsyncPostgresStore` 時也沒有提供 semantic index config。修正後方案 B 第一切片只需要 Store 的 namespace／list／exact routing 能力；只有方案 C 被實測缺口觸發時，才需要另外比較 pgvector-capable PostgreSQL、embedding binding 或 hybrid engine。是否改 production image／extension 只能由後續 successor ADR 裁決。

**直接事實**：現行框架可直接提供 durable checkpoint read 與 Store semantic search，但沒有現成的「從 Checkpointer message 自動建立 locator」產品政策；那一小段 projection 必須由 Caliburn 定義。

## 4. 跨家共同點與不能冒充共識的部分

### 4.1 可成立的共同方向

1. 原始 conversation／events 有獨立的 durable owner；
2. 原始歷史至少可依 scope 分頁／排序／讀取；
3. 整理後 Memory／registry 與原始 conversation 分層；
4. 日常採 progressive disclosure：先看小型摘要／導覽，再搜尋少量 Memory，最後才讀精確原始 evidence；
5. semantic retrieval 通常作用於整理後 Memory／retrieval Store，而 raw events 主要以 list／page／metadata／exact read 取回；
6. search data 與 canonical history 是不同責任；Memory hit 不是原始歷史本身；
7. raw-message semantic index 不是 OpenAI、Anthropic、Google、AWS 公開 Memory read path 的共同必要層。

### 4.2 官方資料沒有共同規定

- locator 必須存 message、turn 還是 chunk；
- 必須用 dense、lexical 或 hybrid retrieval；
- search index 是否保存全文、摘要或只有 embedding；
- 是否每回合自動 search，或由模型按需呼叫；
- index rebuild、stale handling 與 exact authority seam 的共同 schema。

Anthropic 的 Contextual Retrieval 與 OpenAI Vector Store 可以佐證大型知識庫的 lexical＋dense／reranking 能改善 retrieval，但那是 knowledge／RAG retrieval 能力，**不能反推 Claude／Codex 的 conversation Memory 一定用同一底層**。

因此下節是 **基於官方共同分層與 Caliburn 已核准效果做出的工程 mapping**，不是宣稱 OpenAI／Anthropic 內部使用同一張表或同一 schema。

## 5. 三個實質方案

### 5.1 方案 A — 只用 Checkpointer read／page／線性掃描

流程：需要舊資料時讀取目前或歷史 checkpoint，在應用程式記憶體內掃描 message，再只把命中片段送模型。

優點：

- 無耐久文字副本；
- authority 最單純；
- exact phrase／專有名詞可確定找回；
- 可作任何方案的故障 fallback。

缺點：

- Checkpointer 沒有內容搜尋索引；
- 每次長距離查找都可能讀完整 messages，成本與延遲隨 thread 增長；
- 換句話說或模糊指涉的 recall 弱；
- 若用 LLM 逐頁判斷，token／model-step 成本更高。

**判斷：保留為 fallback，不足以單獨滿足長距離 semantic recall。**

### 5.2 方案 B — Semantic Memory 導覽＋canonical evidence deep-read（建議）

流程：

1. Checkpointer 耐久保存完整員工＋顧問 conversation；
2. Memory manager 依 `MEM-Q002` 把 JD-relevant、可重用、可修訂的理解整理進 Semantic Memory；重要且需獨立搜尋的 A／B 案差異保留為 focused Memory；
3. Runtime 在 Memory 被接受寫入時附上 canonical message reference；模型不得自行捏造 message ID、scope 或時間；
4. 每輪先使用近期 context 與小型 Memory 導覽；只有相關時才搜尋少量 Semantic Memory；
5. 需要精確案例細節時，依 reference 回讀 Checkpointer 中的 canonical message 與相鄰問答；
6. 沒有 Memory hit、員工要求舊原話或需驗證時，才對目前 thread 做有界 exact scan；
7. 仍不能辨認時詢問員工，不讓搜尋結果自行裁決真相。

優點：

- 最貼近 OpenAI Codex／Agents SDK 的 progressive disclosure，以及 Google／AWS「raw events＋retrievable long-term Memory」的公開分層；
- 直接重用既有 Semantic Memory Store，不建立第二份 raw-message text projection；
- 日常成本最低：不需每則訊息 embedding，也不需先接 pgvector／Qdrant；
- 只在真的需要原句時讀 canonical evidence，且可保留問答脈絡；
- Memory 整理失敗與 conversation 保存失敗仍是兩個可觀察問題，不會互相冒充。

限制：

- 若某項久遠細節既未被整理成可搜尋 Memory，又無可猜中的 exact wording，可能需要較廣的 scan 或員工澄清；
- 方案是否足以找回所有 JD-relevant 案例細節，必須用 `MEM-Q002` 的 A／B／更正 transcript 驗證，不能只靠文件宣稱；
- canonical message reference 的附掛方式屬後續 G4 contract，不在本題先設計 schema。

**判斷：建議送 G3；第一切片先驗證效果，不先建立 raw-message semantic index。**

### 5.3 方案 C — 可重建 raw-conversation locator／hybrid index

只有方案 B 的代表性測試出現不可接受的 long-distance miss，才替 canonical conversation 建 derived search projection。最小版本可使用 LangGraph Store semantic search；若精確詞＋語意混合仍不足，再比較 PGVectorStore／Qdrant 等 hybrid retrieval。所有 hit 都必須以 pointer 回讀 Checkpointer。

優點：能直接救回未被 Memory consolidation 收錄、但語意相關的久遠原句；hybrid 可同時處理 proper noun、精確詞與換句話說。

缺點：複製可搜尋 raw text、增加 embedding／privacy／rebuild／staleness 與 infra 成本；而 OpenAI／Anthropic 公開 Memory read path 並未把它列成第一層共同必要機制。

**判斷：deferred upgrade，不是第一切片。方案 B 的 evidence-based smoke 失敗才重開。**

## 6. 「搜尋到舊說法」不等於舊說法重新生效

Conversation 是歷史，Semantic Memory 是目前理解；兩者不能混為一談。

若員工先說「B 案串會員 API」，後來更正「其實是匯入 CSV」：

- 兩則原話都留在 canonical conversation；
- Semantic Memory 的 current head 反映已核實的目前理解；
- conversation search 可能找回舊說法或更正，結果須包含時間順序與必要相鄰上下文；
- 顧問組裝 Context 時同時看 current Semantic Memory，不能把單一舊 hit 當現行事實；
- 若仍無法判斷適用範圍，詢問員工，而不是讓索引決定真相。

搜尋只解決「找到哪裡」，不解決「哪一句目前有效」。後者屬後續 Manager／consolidation contract。

## 7. 第一切片可驗證的最小 contract

G3 已核准方案 B；後續 isolated spike 應先驗證 progressive-disclosure 效果，不先做 production integration：

1. **專有名詞**：很久後提「飲料店網站」可找回 A 案；
2. **換句話說**：以不同措辭描述同一工作，可找回對應原句；
3. **問答完整性**：員工只回答「對」時，回傳窗口包含顧問原問題；
4. **相似 A／B**：可區分餐飲預約站與健身會員站，不把兩者混成一筆來源；
5. **更正**：舊說法存在，但 current Semantic Memory 與較新更正不被舊 hit 覆蓋；
6. **scope isolation**：絕不跨 `document_id／thread_id`；
7. **missing Memory route**：未命中 Semantic Memory 時可啟動有界 exact scan 或澄清，不靜默猜測；
8. **bad reference**：不存在或跨 scope 的 message reference 被忽略，canonical conversation 不受影響；
9. **bounded context**：模型只收到少量 Semantic Memory 與必要 canonical windows，不收到整段 thread；
10. **upgrade trigger**：只有上述情境出現不可接受的 long-distance miss，才形成方案 C 的可觀察重開證據。

不在第一切片承諾固定 top-k、threshold、embedding model 或最大 thread 長度；它們由代表性 transcript 量測後決定，不能先用任意數字冒充產品正確性。

## 8. G3 Product Owner 決策

Product Owner 於 2026-09-03 核准：

> **採修正後方案 B。Checkpointer 保存 canonical conversation；Semantic Memory／小型導覽先負責 routing，命中後才回讀 canonical message。第一切片保留有界 exact scan／澄清 fallback，不替每則原始訊息建立 semantic locator，也不先引入 pgvector／Qdrant。只有代表性 smoke 證明重要久遠細節無法找回，才重開方案 C。**

決策後果：

- `MEM-Q003` 已轉為 `WORKING`；
- `MEM-Q001` 的「第一版不建立重複 employee-source 文字 leaf」維持不變；
- 下一 gate 才研究 Semantic Memory Manager／Store contract、canonical message reference 與重寫 isolated spike；
- production 仍須 successor ADR，不能由本研究直接施工。

### 8.1 G3 closure

- **Decision／finding**：採修正後方案 B；官方共同邊界是 canonical event list/read 與整理後 Memory／retrieval 分離，OpenAI Codex／Agents SDK、Anthropic、Google、AWS 的公開 read path 支持 progressive disclosure，而不是預設替每則 raw message 建 semantic index。
- **Status**：`WORKING`；G3 Product Owner 已核准，但尚未成為 production authority。
- **Why**：A 單靠 scan 的 semantic recall 弱；B 重用既有 Semantic Memory 作 routing 並按需回 canonical evidence，最貼近公開大廠 read path；C 在沒有失敗證據前增加 raw-text duplication、embedding 與 ranking 複雜度。
- **Sources**：本文 §3 與 §9 的 OpenAI、Anthropic、Google、AWS、LangGraph 官方資料，以及本 repo dependency／compose 的 read-only 核對。
- **Affected artifacts**：本文與 [`../current-decisions.md`](../current-decisions.md)；不改 ADR、production code、schema、infra 或 tool。
- **Reopen trigger**：官方新增原生 Checkpointer conversation search；isolated spike 證明 B 的 recall、成本／延遲不可接受；或 Product Owner 改變完整細節找回要求。
- **Next gate**：進 G4／G5，收斂 Semantic Memory routing、canonical reference／read contract 與 isolated spike；在此之前不改 production。

## 9. 直接來源

- [OpenAI — List conversation items](https://developers.openai.com/api/reference/python/resources/conversations/subresources/items/methods/list)
- [OpenAI — Search vector store](https://developers.openai.com/api/reference/python/resources/vector_stores/methods/search)
- [OpenAI Codex — Memory read path](https://github.com/openai/codex/blob/main/codex-rs/ext/memories/templates/memories/read_path.md)
- [OpenAI Agents SDK — Agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [OpenAI Codex — Memory consolidation prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)
- [Anthropic — Managed Agents List Events](https://platform.claude.com/docs/en/api/beta/sessions/events/list)
- [Anthropic — Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Dreams](https://platform.claude.com/docs/en/managed-agents/dreams)
- [Anthropic — Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Google — Agent Platform Sessions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions)
- [Google — events.list](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/v1beta1/projects.locations.reasoningEngines.sessions.events/list)
- [Google — Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank)
- [AWS — Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)
- [AWS — ListEvents](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListEvents.html)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Backward compatibility／thread state search boundary](https://docs.langchain.com/oss/python/langgraph/backward-compatibility)
- [LangGraph — AsyncPostgresStore 3.1.2](https://reference.langchain.com/python/langgraph.store.postgres/aio/AsyncPostgresStore)
