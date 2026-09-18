# Caliburn Memory／顧問 Runtime 框架選擇複核

- 日期：2026-09-02
- 狀態：**Working Research；2026-09-02 已校正 foundation 與條件式強化的邊界**
- 決策層級：框架研究選擇，不是 ADR、schema、施工計畫或實作授權
- 上位契約：[`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md)
- 完整推導：[`2026-08-30-caliburn-memory-requirements-mapping-working-research.md` §9.41～§9.46](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md)

> **閱讀規則**：本文只決定目前應優先採用哪組成熟框架。框架不得改寫上位產品契約、職務分析方法或員工核准權。若本文與較早候選結論衝突，以本文為目前選型結論；若要翻案，必須先提出新的官方能力、代表性產品證據或已驗證的實作品質差異，再與 Owner 討論。

> **2026-09-02 重驗校正**：[`2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](./2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md) 確認 LangGraph／PostgreSQL 仍是第一切片首選，但 custom immutable-revision／CAS adapter、operation receipt、inventory manifest、Qdrant 與 Voyage 都不是 foundation 的共同必要條件。本文目前施工優先序只看 §1 與 §7.1；§7.2 全部是由代表性 recall 缺口才啟用的 deferred research，不能因內容詳細就提前施工。

> **較新機制稽核（2026-09-02）**：[`Memory 實作機制與成熟框架共識稽核`](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md) 保留 LangGraph／LangChain 作整體 runtime 首選候選，但確認它的 Store 沒有原生 CAS／durable operation idempotency／snapshot-grade exact inventory。故「整體 runtime 首選」不等於「每個 Memory 底層 primitive 已選完」；mutation safety、exact inventory 與 Semantic writer 尚未獲 Owner 裁決，本文不得直接轉施工計畫。

> **已否決的歷史切片候選（2026-09-02）**：[`Memory Foundation 最小垂直切片設計`](./2026-09-02-memory-foundation-vertical-slice-design.md) 的先前版本曾提出以 LangGraph Checkpointer current state 保存單一 JD／thread 的完整 Memory collection。後續能力／共識稽核已否決此責任映射；該文件現已重寫為 Store-first 待審方案，仍不能直接轉成施工計畫。

> **後續能力稽核校正（2026-09-02）**：上段 Checkpointer current collection 候選已否決，不再等待容量 gate 才改回長期 Memory Store。容量測試只能回答「能不能塞」，不能回答「是否符合成熟系統的責任分層、召回方式與產品 M1～M11」。目前最新判讀以 [`Memory 實作機制與成熟框架共識稽核` §10](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md) 與重寫後的 [`Memory Foundation 最小垂直切片設計`](./2026-09-02-memory-foundation-vertical-slice-design.md) 為準：Checkpointer 只承接 thread／run state；可修訂 Semantic Memory 使用每份 JD 隔離的長期 Store／notebook primitive。具體第一切片仍待 Owner 複核，尚未授權施工。

## 1. 結論

目前 **整體顧問 runtime foundation** 首選組合是：

```text
LangChain 1.x
  + LangGraph 1.x LTS
  + 官方 PostgreSQL Checkpointer
  + LangChain stable Tools／Structured Output／Middleware
  + OpenTelemetry framework-independent observability
  + provider adapter 使用各 provider 原生 cache／compaction／tool search
```

正式第二名是 `Pydantic AI V2＋Harness＋DBOS`。第一版不混用兩套完整 agent runtime。

單一 JD Semantic Memory 的**第一 substrate 候選**改為 LangGraph PostgreSQL Store；Checkpointer 只保存 thread／run state。`LangMem core create_memory_manager` 與 `create_memory_store_manager` 是兩個待窄實驗比較的 Semantic Memory writer／consolidator 介面，不得直接決定 JD。先用官方 Store primitive 驗證 persistence／isolation／current-head／inventory，再用 tiny model smoke 比較兩個 LangMem 介面。

Pydantic Harness 仍是正式備選：它的 notebook、CAS 與 durable idempotency 較完整，但目前是 0.x 且沒有 M9 所需的 iterate-all listing 契約。只有 LangGraph Store contract 真正失敗時才回來比較，不能同時接成第二套 agent loop。

Qdrant／Voyage 的研究保留為**只有代表性長訪談證明官方 Store search 不足時才啟用**的 derived-recall 候選；不屬 foundation，也不進第一個實作計畫。若日後採用，Qdrant 只能承接日常有界召回，不能承接目前內容、員工核准、JD authority 或 exact-scope 全量盤點。ADR 0072 Accepted 前，現行 production 邊界不變。

這項結論不是因為現行程式已使用 LangGraph，也不是因為少寫程式。它是在 12 項硬門檻全部納入後，依序比較最終 JD 效果、正確性、可靠性、功能、成本、延遲與複雜度所得的整套 runtime 結論。

## 2. 比較方法

### 2.1 先過硬門檻，再比較便利性

候選必須共同承接：

1. 本機、自架、PostgreSQL；
2. provider／model 可替換；
3. durable conversation 與關閉後 resume；
4. durable、可修訂 Semantic Memory；
5. bounded recall、按需 search／read 與來源回查；
6. exact-scope list-all／pagination；
7. trusted per-JD isolation；
8. replay 不重複；若候選實際允許多 writer，才再要求 stale／並行保護；
9. typed tool 與 failure contract；
10. 員工審核與跨關閉保存的待審內容；
11. 來源、Memory、召回、失敗、成本與延遲可觀察；
12. 可維護的正式版本政策。

完整語意見[上位契約 §8](./2026-09-01-framework-independent-memory-contract.md)。某個候選若只在單一 Memory 元件、Tool typing 或 Prompt 人體工學上較強，不能因此抵銷 durable authority、完整盤點或資料隔離缺口。

### 2.2 權重

```text
最終 JD 效果與資料正確性
  > durable consistency／員工審核／完整盤點
  > 功能完整度
  > 成本與延遲
  > 實作複雜度與程式碼量
```

「少寫程式」只有在效果與可靠性相當時才是優勢。

### 2.3 研究與施工護欄

1. 先以 OpenAI、Anthropic、Microsoft、Google 等官方文件能共同支持的效果與責任分工為預設，不從單一 blog、套件 demo 或既有 Caliburn 元件反推需求；
2. 共同做法無法滿足上位 Memory 契約時，才比較各家成熟的差異能力；選用差異能力必須說明它補哪個產品缺口；
3. 「供應商公開事實」「Caliburn 根據事實作出的架構推論」「尚待驗證的假設」三者必須分開寫，不能把 application mapping 冒充大廠內部實作；
4. 實作優先使用官方 SDK 與穩定 primitive；只有 authority、隔離、revision、完整盤點或職務語意等 framework 無法替代的責任，才寫最薄的產品邏輯；
5. 版本、授權、security advisory 與語言能力以研究當日的官方 release／documentation 重新核對；「最新」不代表自動採用，仍須通過效果、可靠性、成本與本機部署門檻；
6. 若後續證據顯示另一成熟方案效果明顯更好，先更新研究與 ADR，再改實作；不得因已投入程式碼而保留較差方案。

## 3. 候選結果

| 候選 | 成熟能力 | 主要缺口或風險 | 結論 |
| --- | --- | --- | --- |
| **LangChain 1.x＋LangGraph 1.x＋PostgreSQL** | LTS runtime、checkpoint、Store、interrupt／resume、fault tolerance、typed tools、structured output、middleware | Store 缺原生 CAS／durable idempotency／snapshot pager；沒有完整內建 lexical＋vector hybrid ranking | **整體 foundation 首選**；Checkpointer 承接 thread／run state，Store 承接 per-JD durable source＋Semantic Memory；CAS／revision／Qdrant 依實際 trigger 再加 |
| **Pydantic AI V2＋Harness＋DBOS** | Harness Memory 有 PostgreSQL、bounded notebook／讀取／搜尋、optimistic CAS 與冪等；typed ergonomics 很強 | Harness 仍是 0.x；所有 read／list 都刻意有界，沒有 M9 所需的完整 inventory 契約；官方也明示 memory records 不帶 verified provenance；durable runtime 分散在多個接縫 | **正式第二名**；保留翻案資格，不與首選混搭成雙 runtime |
| **Letta** | 持久 agent、conversation、Memory、MemFS／檔案式按需讀取與背景整理 | 導入的是整套 agent platform；0.x 且部署與記憶介面仍快速變動；公開契約不足以證明符合本案 exact inventory／provider-neutral hard gates | 第一版不採；作長期產品參考 |
| **OpenAI Agents SDK＋Sandbox Memory** | Sessions、SQLAlchemy session、compaction 與兩階段 Memory pattern | Sandbox Memory 為 Beta，與 Session 分離且偏 workspace／file；不能單獨承擔本機 provider-neutral Semantic Memory authority | 參考其 Context／Memory pattern，不作 primary runtime |
| **Anthropic Memory Tool／Managed Agents Memory** | JIT file CRUD；managed 版本另有 immutable versions 與 content-hash concurrency | Memory Tool 的 storage／scope／validation 仍由應用實作；managed memory 綁供應商與雲端 | 參考按需讀取、修訂與版本治理，不作本機 primary authority |
| **Google Memory Bank／AWS AgentCore Memory** | managed extraction、search、list／pagination、revision 或 strategy 能力 | 雲端 control plane 與 provider lock-in 不符合第一項硬門檻 | 只作設計證據與翻案參考 |

## 4. 為何整套選 LangGraph

### 4.1 同一個成熟 runtime 覆蓋完整生命週期

LangGraph 的 checkpointer 保存 thread-scoped graph state，適合長訪談、關閉後續談、interrupt／resume、人工審核與故障恢復；Store 保存 graph state 外的長期 application data。官方 PostgreSQL backend 讓兩者可留在本產品既有 PostgreSQL 邊界內。

這讓下列流程不必跨兩套 agent runtime 拼接：

```text
員工訊息
  → durable 顧問 run
  → 有界 Context 與按需 Memory search／read
  → 必要時 interrupt 等員工確認
  → 形成可跨關閉保存的待審 JD 變更
  → 員工接受／修改後接受／拒絕
  → deterministic authority command
  → resume 下一輪訪談
```

### 4.2 它不是所有單項功能的冠軍

Pydantic Harness 的 Memory notebook、CAS、冪等與 tool ergonomics 在單一元件比較中更完整。首選 LangGraph 的原因是整體產品還需要 conversation durability、完整盤點、持久審核、fault recovery、PostgreSQL 與 provider-neutral model binding；LangGraph 以較少 runtime 接縫完整承接這些高權重需求。

### 4.3 框架不負責職務分析

LangGraph／LangChain 只提供 execution、persistence、search、tool、structured output 與 middleware。下列內容仍屬 Caliburn 的產品方法：

- 哪些員工工作資訊值得形成或修訂 Memory；
- 如何區分補充、更正、不同案例、未知與未解衝突；
- Task／Duty／OPKS 與高品質 JD 的分析方法；
- 何時應修改 JD、如何形成一組可審核變更；
- 哪些狀況必須向員工澄清；
- 員工核准與正式 JD authority。

這些方法應放在版本化 Prompt／Skill 與薄的 deterministic policy，而不是假裝 framework 會自動理解職務分析。

## 5. 成熟元件的預定責任

| 產品效果 | 成熟元件 | 尚待後續決定 |
| --- | --- | --- |
| 長訪談、關閉後續談、故障恢復 | LangGraph thread＋PostgreSQL checkpointer | thread／JD identity、保留期限 |
| 可修訂 Semantic Memory | LangGraph PostgreSQL Store＋LangMem core／Store manager 窄比較；完整 conversation 是另一責任 | Memory admission／conflict 語意；retire 尚未設計 |
| 一般 Context | LangChain middleware；後續才接 bounded recall 與按需 read/search | recent window、token budget、read substrate 與代表性召回門檻；Qdrant／Voyage 尚未啟用 |
| 按需 Skill／Tool | LangChain stable dynamic prompt／tool middleware；provider 支援時用原生 tool search | 職務分析 Skill 內容、觸發描述與版本 |
| 全量製作／檢查 JD | Store 非語意 exact-scope listing 逐頁走完 current collection；正式 JD batch workflow 後續設計 | pinned PostgreSQL backend 的 pagination 完整性 contract；有並行 writer 時才重開 snapshot 選擇 |
| 必要員工確認 | LangGraph durable interrupt／resume | blocking 判準與員工可讀問題 |
| 一般待審 JD 變更 | durable working state＋deterministic review command | 變更分組與 authority policy |
| 驗證、錯誤與恢復 | LangChain middleware＋LangGraph retry／fault tolerance／call limits | 少量 domain error code 與 sanitized feedback |
| 成本與診斷 | provider usage＋OpenTelemetry；provider-native caching／compaction | 預算、門檻與內容安全政策 |

此表固定責任邊界，不固定 graph node、資料表、API 或正式 schema。

## 6. LangMem 的限制

LangMem 的 `create_memory_manager` 能依既有 memories 與新對話提出 insert／update／delete／no-op，適合作為可替換的語意 writer 候選；本機小型實驗也證明它能在簡單資料上完成 reconcile。

但截至本次複核，LangMem 仍是 pre-1.0 的 `0.0.x` 套件。必須區分兩個官方元件：core `create_memory_manager` 只回傳修訂後的 `ExtractedMemory` collection；`create_memory_store_manager` 才搜尋並寫入 LangGraph Store。兩者都只能作可替換 leaf，須用同一份窄案例比較。因此：

1. core manager 可以接 conversation＋existing collection，產生保留未變項目的修訂後 collection；
2. Store manager 可直接使用 LangGraph BaseStore 的搜尋／upsert／delete；若它的隱含召回或寫入行為無法滿足產品效果，改採 core manager＋極薄 Runtime apply seam；
3. Canonical current collection 由 LangGraph PostgreSQL Store 發布；LangMem 是 semantic writer，不是 authority；
4. 不把 LangMem 的成功回傳等同於已安全發布；
5. 它必須隔離在可替換 leaf 後，版本 contract canary 失敗就停止。

本機實驗只覆蓋 16 個合成訪談回合、6 次模型呼叫、11,658 tokens、零重試與簡單 reconcile；它沒有證明 PostgreSQL crash／restart、exact inventory、較大 Memory 集合、來源 mapping 或 revision safety。完整紀錄見 [`2026-08-29-langmem-domain-semantic-memory-spike-experiment.md`](./2026-08-29-langmem-domain-semantic-memory-spike-experiment.md)。

## 7. 首選的能力邊界與條件式強化

### 7.1 Immutable revision／current head／CAS

LangGraph Store 的一般 `put` 是 upsert，沒有文件化的 `expected_version` precondition。只把 revision 放進 JSON 後再 `put`，不能防止兩個 writer 同時讀舊值後互相覆蓋。

> **2026-09-02 重驗結論**：共同效果是可重放副作用不得重複；實際存在多 writer 時不能 silent lost update。Anthropic 的 hash precondition、Google／Anthropic revisions、AWS client token 與 LangGraph task idempotency 是不同機制，不能綁成所有第一版都必須自建的一套平台。
>
> 最新 foundation 候選使用每份 JD 隔離的 PostgreSQL Store 保存 current collection。第一切片仍不預建 receipt table、revision platform 或自訂 CAS；先以現行單一 writer 產品邊界和框架 task／upsert contract 測試 replay 不重複。只有實際出現多 writer／lost update，才依 [`2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](./2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md) 重開相應機制。

### 7.2 真正的 lexical＋vector hybrid recall（條件式後續候選；非目前施工）

LangGraph Python PostgreSQL Store 已提供 search／filter 與無 query/filter 的列舉 primitive，但列舉的 M9 完整性仍以 pinned-backend tests 驗證，不能寫成已有 snapshot-grade exact listing。它也沒有一個可直接宣稱完成「專有名詞／精確文字＋語意向量」融合排序的內建 PostgreSQL hybrid retriever。這是已知能力邊界，**不是第一切片已證明的產品缺口**；以下研究只有在代表性長訪談召回失敗後才啟用。

#### 7.2.1 跨家共同方向

官方資料可共同支持的不是某個資料庫品牌，而是以下 retrieval 形狀：

1. lexical／keyword ranking 捕捉專有名詞、縮寫、法規名、代碼與精確措辭；
2. dense semantic retrieval 捕捉同義改寫與概念相關性；
3. 兩路並行後用 rank fusion 合併；沒有代表性 relevance labels 前，以 RRF 作低假設基線；
4. 先以可信 scope／metadata filter 限定候選，再作 relevance ranking；
5. relevance top-k 只服務日常 Context，不得取代 canonical exact inventory。

OpenAI Retrieval 公開 `hybrid_search.embedding_weight／text_weight`，以 RRF 融合 sparse keyword 與 semantic embedding；Anthropic Contextual Retrieval 以 BM25＋embedding＋rank fusion 作標準 retrieval，並指出 exact term 與語意召回互補；Azure AI Search 同樣並行 BM25／vector 並用 RRF；Google Vector Search 也把 dense＋sparse hybrid 與 RRF 列為正式模式。因此「hybrid」是跨家共同方向，不是 Caliburn 自行發明。[OpenAI Retrieval](https://developers.openai.com/api/docs/guides/retrieval) · [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) · [Azure AI Search hybrid search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview) · [Google Vector Search hybrid search](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/vector-search/about-hybrid-search)

#### 7.2.2 候選比較

| 候選 | 符合共同方向的程度 | 繁中與營運風險 | 結論 |
| --- | --- | --- | --- |
| PostgreSQL native FTS＋pgvector | 維持單一服務；可自行平行查詢與融合 | PostgreSQL 原生 parser／dictionary 對無空格 CJK 不足；要自行補斷詞、BM25 等價性與融合 | 不作首選；不能因「少一個服務」犧牲召回效果 |
| PGroonga＋pgvector | PGroonga 成熟、支援全部語言與繁中全文搜尋；可留在 PostgreSQL | 需要自訂 PostgreSQL image／extension；不是同一引擎原生 dense＋BM25；crash-safe 模式仍有額外設定與 write 成本 | **正式 fallback**；若產品不能接受第二個 current service 才重開 |
| **Qdrant 1.19+** | 同一引擎提供 dense、native BM25 sparse、payload filter、RRF、冪等 upsert | 增加一個本機服務與衍生副本；self-hosted dense embedding 仍由 client 產生 | **若 recall trigger 成立時的 deferred 首選候選**；目前不施工 |
| ParadeDB／VectorChord-BM25 | PostgreSQL 內的 BM25／vector 方向有吸引力 | 研究當日版本、授權或 CJK production 證據仍不如前兩者穩定；VectorChord-BM25 官方明示主要只測英文 | 不作第一版 authority／retrieval dependency；保留日後翻案資格 |

PGroonga 官方說明 PostgreSQL 內建全文檢索不適合 CJK，並提供 all-language 索引；其 crash-safe 功能仍需專用 WAL resource manager，文件也明示有 write performance trade-off。[PGroonga](https://pgroonga.github.io/) · [PGroonga crash-safe](https://pgroonga.github.io/reference/crash-safe.html) · [PGroonga WAL resource manager](https://pgroonga.github.io/reference/modules/pgroonga-wal-resource-manager.html)

Qdrant 1.19.0 是研究日官方 latest release；其 BM25 支援 `multilingual` tokenizer，官方直接用「村上春樹」示範非空格語言，並新增以 payload filter 限定 IDF corpus 的 per-tenant statistics。Query API 原生支援 dense／sparse prefetch 與 RRF，point API 也明示相同 ID 的重試是冪等。[Qdrant releases](https://github.com/qdrant/qdrant/releases) · [Qdrant full-text／BM25／multilingual](https://qdrant.tech/documentation/search/text-search/full-text-search/) · [Qdrant hybrid queries／RRF](https://qdrant.tech/documentation/search/hybrid-queries/) · [Qdrant per-tenant IDF](https://qdrant.tech/documentation/manage-data/multitenancy/) · [Qdrant point idempotence](https://qdrant.tech/documentation/manage-data/points/)

#### 7.2.3 已研究的 deferred candidate architecture

```text
PostgreSQL
  = canonical current Memory＋屆時已核准的 concurrency／audit 機制
  = 經驗證的 exact-inventory seam；不能用 Qdrant top-k 取代

同一 PostgreSQL transaction
  = 發布 canonical mutation＋小型 outbox event

本機 projector
  = 讀 outbox，以 deterministic point ID 冪等 upsert／delete Qdrant

Qdrant 1.19+
  = per-JD filter＋multilingual BM25＋dense vector＋RRF 的可重建日常召回索引

顧問讀取
  = Qdrant 回 memory ID／revision → PostgreSQL 載入 canonical current head → 丟棄 stale／missing hit

全面製作／檢查 JD
  = 只從 PostgreSQL 經驗證的 inventory seam 處理全部目前 Memory；完全不以 Qdrant top-k 證明完整性
```

這裡的 PostgreSQL outbox＋projector 是 **Caliburn 根據成熟 transactional-outbox 與 derived-index 原則做出的架構映射**，不是宣稱 OpenAI、Anthropic 或 Qdrant 內部使用同一資料表。outbox 的必要性來自一個具體 invariant：canonical Memory 與「稍後需投影」的事件必須同 transaction 成功，才能在 process crash 後可靠重試。單機產品不因此導入 Kafka、Debezium service 或第二個 distributed workflow；Debezium 官方 outbox 文件只作模式依據。[Debezium Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)

核心路徑直接使用官方 `qdrant-client`，不強迫走 LangChain `QdrantVectorStore`。原因不是排斥框架，而是 Qdrant 官方文件明示 `multilingual` tokenizer option 不受 FastEmbed 支援；繁中 lexical path 若被通用 wrapper 隱藏，反而會失去本案選用 Qdrant 1.19 的主要效果。LangChain integration 可留在不遮蔽必要能力的薄 adapter 外圍。[Qdrant full-text search](https://qdrant.tech/documentation/search/text-search/full-text-search/) · [LangChain Qdrant integration](https://docs.langchain.com/oss/python/integrations/vectorstores/qdrant)

若日後 trigger 成立，候選最小 retrieval stack 也不預設 reranker、SPLADE、GraphRAG 或第二個 retrieval model。Anthropic 的研究顯示 reranking 可提高效果，但也明示增加 latency／cost，應依代表性資料調校；目前沒有 relevance labels，BM25＋dense＋RRF 只是較少假設、較低成本的候選基線。dense embedding 已依下節的小型繁中 compatibility smoke 排出候選順序；仍不得靜默重用 ADR 0057 的 RAG embedder。

#### 7.2.4 Dense embedding 選型與繁中 compatibility smoke

2026-09-02 以最新官方資料比較目前可用的多語候選：OpenAI 仍把 `text-embedding-3-large` 定位為英文與非英文最強 embedding，價格為每百萬 token USD 0.13；Google 的 2026 `gemini-embedding-2` 支援 100+ 語言、文字價格 USD 0.20／百萬 token，並要求文字 retrieval 以官方 query／document 格式加入 task instruction；Voyage 4 是 2026 retrieval-specific 系列，`voyage-4-large` 官方定位為系列最高品質，價格 USD 0.12／百萬 token，支援明確的 `query`／`document` input type、1024 預設維度與正規化向量。OpenRouter 現行 Embeddings API 已提供 Google、OpenAI 與 Voyage 4，且可沿用本產品既有 provider boundary。[OpenAI `text-embedding-3-large`](https://developers.openai.com/api/docs/models/text-embedding-3-large) · [Gemini Embedding 2](https://ai.google.dev/gemini-api/docs/embeddings) · [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) · [Voyage embeddings](https://docs.voyageai.com/docs/embeddings) · [Voyage pricing](https://docs.voyageai.com/docs/pricing) · [OpenRouter Embeddings API](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings) · [OpenRouter current embedding models](https://openrouter.ai/api/v1/embeddings/models)

供應商 benchmark 不能直接代替本案判斷：Voyage 4 公開評測比較的是 Gemini Embedding 001，而不是 2026 的 Gemini Embedding 2；各家官方資料也沒有共同的繁中職務訪談測試集。因此本輪只做 **compatibility smoke**，不宣稱建立正式 eval 或證明任何模型在所有繁中 retrieval 情境普遍最佳。

固定 smoke 使用 24 筆匿名繁中工作 Memory 與 12 個具唯一預期答案的口語查詢，包含同義改寫、否定責任邊界、近似工作、法規用語、`SOP`／`KPI`、網站開發／維護、設備維修／採購、一般申訴／職場不法侵害等 hard negatives。比較參數與結果如下：

| 候選 | 輸入方式 | 維度／距離 | 實際回傳 | token | Top-1 | Top-3 | MRR |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `voyageai/voyage-4-large` | 文件 `input_type=document`；查詢 `input_type=query` | 1024／cosine | `voyage-4-large` | 869 | 12/12 | 12/12 | 1.0000 |
| `google/gemini-embedding-2` | 官方 `title/text` 文件格式＋`task: search result` 查詢格式 | 1536／cosine | `gemini-embedding-2` | 1044 | 12/12 | 12/12 | 1.0000 |

這是一次性 in-memory probe；API key、模型輸出向量與完整合成語料都沒有寫入 repo。故上表只能作本輪選型的 compatibility evidence，不能當成可重跑 regression gate。ADR 0072 Accepted 前的 hybrid integration smoke 必須另存匿名 fixture、runner 與逐案預期結果，才能承擔後續版本／adapter 變更的回歸判斷。

兩者都通過目前窄門檻，Gemini 沒有在本測試呈現可抵銷較高價格、額外 task-format contract 與多模態無關能力的效果收益。因此，**若未來代表性 recall 缺口觸發 Qdrant 候選且重新核對價格／版本後仍無反證**，目前 dense leaf 優先候選是 **Voyage 4 Large**；這不是當前 Memory foundation 的採購或施工決策：

- OpenRouter request 固定使用 canonical slug `voyageai/voyage-4-large-20260727`，並關閉 provider fallback；另以 9-token 匿名 probe 驗證該 canonical slug 可直接呼叫，回傳 `voyage-4-large` 與 1024 維向量。
- 文件與 query 候選都使用同一 `voyage-4-large`，不先採 asymmetric model mixing；只有未來代表性資料與成本證據支持時，才利用 Voyage 4 shared space 改用 lite／nano query lane。
- 輸出固定 1024 維、float、cosine；文件與查詢分別使用 provider 的 `document`／`query` input type。
- 若實際採用，index manifest 至少固定 requested canonical model ID、provider／adapter revision、回傳 model ID、維度、dtype、distance、input-mode contract 與 index generation。任何不相容變更都建立新 generation／全量重建，不在既有 collection 混用。
- 本輪只驗 dense leaf 與 OpenRouter contract；Qdrant 1.19 multilingual BM25、RRF、per-JD isolation、stale rejection、outbox replay、rebuild 與 degraded mode 仍須施工前的整合 smoke。

`voyage-4-nano` 是 Apache 2.0、可本機執行且與 Voyage 4 系列共享向量空間的 fallback 候選，但官方定位偏 local development／prototyping；不為尚未存在的離線需求增加模型下載、推論 runtime 與硬體差異。[Voyage 4 release](https://blog.voyageai.com/2026/01/15/voyage-4/) · [Voyage 4 Nano model card](https://huggingface.co/voyageai/voyage-4-nano)

#### 7.2.5 邊界與最小驗證

- 這是 **Memory retrieval**，不是外部 Reference RAG；不 import、wrapper 或重用 `apps/ocs-indexer`、`apps/embedder`、RAG contracts 或其 collection。
- 現有 `docker-compose.yml` pin `qdrant/qdrant:v1.18.2` 且只在 `rag` profile 啟動；1.19 能力不可假裝已存在。若 ADR 0072 Accepted，須明確調整 current infrastructure lifecycle 與 ADR 0057 邊界。
- Qdrant collection／payload 不是權威；可整庫刪除並由 PostgreSQL current heads 重建。Qdrant unavailable 或索引落後不得阻止 exact inventory、員工核准或 deterministic export。
- 施工前只做窄 compatibility smoke，不建立正式 eval 平台：繁中無空格詞、英文縮寫／專有名詞、同義改寫、per-JD isolation、stale revision rejection、outbox replay 與全量 rebuild。若未通過，回到 PGroonga fallback；不得用 prompt workaround 掩蓋 retrieval 缺陷。

## 8. Production 版本與安全門檻

1. `langchain`／`langgraph` 採受支援的相容 `1.x` minor，鎖定 dependency lockfile；
2. `langgraph-checkpoint-postgres` **不得低於 `3.1.1`**；官方 advisory 指出 `<3.1.1` 的 namespace prefix／suffix 比對可能跨 segment 讀到其他 scope；
3. per-JD namespace 使用 Runtime 產生的固定長度不可猜 identity，不能讓模型或未驗證輸入指定；
4. 升級前查看 release notes、security advisories，並重跑 isolation／pagination／resume／replay 測試；
5. Deep Agents、LangMem、Harness 等 pre-1.0 套件若作 leaf integration，必須隔離在可替換 adapter 後；不得成為 authority。

研究日 PyPI 的 `langgraph==1.2.11` 是 latest；本 repo 已一致。`langgraph-checkpoint` latest 是 `4.2.0`，本 repo transitive lock 是 `4.1.1`；不因 patch／minor 數字較新就直接升級，先確認 `langgraph-checkpoint-postgres==3.1.2` 的相容範圍並重跑 Store inventory／isolation／replay gates。

## 9. 明確不做

- 不在容量 gate 前宣稱 Checkpointer 一定能承載長期全部 Semantic Memory，也不先用 beta delta／自訂 pruning 掩蓋風險；
- 不把 Store 的任意 JSON 或 semantic top-k 當成完整 Memory 系統；
- 不混用 LangGraph 與 Pydantic AI 兩套完整 agent runtime；
- 不以 provider-managed Memory 作本機 primary authority；
- 不為第一版導入 knowledge graph、episodic engine、**外部 Reference RAG** 或跨 JD Memory；Proposed ADR 0072 的 derived Memory index 不得被擴張成 Reference corpus；
- 不固定每輪第二個模型、每輪摘要或額外 LLM Tool Selector；
- 不在本輪決定正式 schema、graph node、API 或 migration。

## 10. 翻案條件

符合任一條件時，應回到 12 項硬門檻重新比較：

1. Pydantic Harness 出貨穩定的 PostgreSQL conversation／step persistence、exact inventory pagination 與一體化 durable tool contract；
2. 代表性長訪談證明其他方案在細節保真、衝突修訂或完整盤點上顯著較佳；
3. Deep Agents／LangMem 等進入穩定版本，且其能力成為第一版的實際硬需求；
4. LangGraph 無法用薄 adapter 滿足 current-head consistency、exact inventory、隔離或長訪談成本門檻；
5. 新的官方 security／release policy 讓目前組合不再適合 production。

翻案不能只憑套件熱度、名稱、示範程式碼較短或單項 feature list。

## 11. 下一步

1. 先由 Owner 複核 [`Memory 實作機制與成熟框架共識稽核` §10](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md) 的 Checkpointer／Store 分工；未核准前不施工；
2. 核准後重寫 Stage 0／1 計畫：contract canary、真 PostgreSQL Store、restart／isolation／replay、current-head 與全量 listing；
3. foundation 綠燈後才做極小 `gpt-5.6-luna` smoke，比較 LangMem core／Store manager，驗證 rich Memory add／revise／remove／no-op 與未提及細節保留；
4. 只有 Store contract 或代表性長訪談出現具體缺口，才依 trigger 回到 §7 選 Harness、CAS、history、snapshot 或 derived hybrid recall；
5. Proposed ADR 0072 與 Voyage compatibility research 保留為候選資料，不因存在文件就進 production；
6. 任何 authority cutover 仍需 successor ADR，且不得順便接入 Reference RAG。

## 12. 官方來源

### LangChain／LangGraph

- [Release policy：LangChain 1.0／LangGraph 1.0 LTS 與 SemVer](https://docs.langchain.com/oss/python/release-policy)
- [Persistence：checkpointer 與 Store 的分工](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [Tools／ToolRuntime／Store](https://docs.langchain.com/oss/python/langchain/tools)
- [Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [PostgreSQL／SQLite namespace scope security advisory GHSA-47pj-3jcm-6whg](https://github.com/langchain-ai/langgraph/security/advisories/GHSA-47pj-3jcm-6whg)

### Pydantic AI

- [Harness Memory](https://pydantic.dev/docs/ai/harness/memory/)
- [Harness Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/)
- [Durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)
- [DBOS integration](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)
- [Version policy](https://pydantic.dev/docs/ai/project/version-policy/)

### 其他正式候選與設計參考

- [OpenAI Agents SDK Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK Sandbox Memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [Anthropic Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic Dreams](https://platform.claude.com/docs/en/managed-agents/dreams)
- [Letta Agent SDK Sessions](https://docs.letta.com/agent-sdk/sessions/)
- [Letta Agent SDK Memory](https://docs.letta.com/agent-sdk/memory/)
- [Letta deployment](https://docs.letta.com/agent-sdk/deployment/)
- [LangMem Memory API](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem PyPI release metadata](https://pypi.org/project/langmem/)

### Hybrid retrieval、Qdrant 與一致性

- [OpenAI Retrieval：semantic／text hybrid ranking 與 RRF weights](https://developers.openai.com/api/docs/guides/retrieval)
- [Anthropic Contextual Retrieval：BM25＋embeddings＋rank fusion](https://www.anthropic.com/engineering/contextual-retrieval)
- [Azure AI Search：BM25／vector parallel query＋RRF](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview)
- [Google Vector Search：dense／sparse hybrid＋RRF](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/vector-search/about-hybrid-search)
- [Qdrant releases](https://github.com/qdrant/qdrant/releases)
- [Qdrant full-text／BM25／multilingual tokenizer](https://qdrant.tech/documentation/search/text-search/full-text-search/)
- [Qdrant hybrid queries／RRF](https://qdrant.tech/documentation/search/hybrid-queries/)
- [Qdrant per-tenant IDF](https://qdrant.tech/documentation/manage-data/multitenancy/)
- [Qdrant point idempotence](https://qdrant.tech/documentation/manage-data/points/)
- [Qdrant inference boundary](https://qdrant.tech/documentation/inference/)
- [LangChain Qdrant integration](https://docs.langchain.com/oss/python/integrations/vectorstores/qdrant)
- [Debezium transactional outbox pattern](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [PGroonga](https://pgroonga.github.io/) · [crash-safe](https://pgroonga.github.io/reference/crash-safe.html) · [WAL resource manager](https://pgroonga.github.io/reference/modules/pgroonga-wal-resource-manager.html)
- [ParadeDB repository／license](https://github.com/paradedb/paradedb) · [releases](https://github.com/paradedb/paradedb/releases)
- [VectorChord-BM25 limitations](https://github.com/supervc-stack/VectorChord-bm25) · [releases](https://github.com/supervc-stack/VectorChord-bm25/releases)

### Dense embedding 候選與 provider boundary

- [OpenAI `text-embedding-3-large`](https://developers.openai.com/api/docs/models/text-embedding-3-large)
- [Gemini Embedding 2：多語、task formatting、維度與 migration](https://ai.google.dev/gemini-api/docs/embeddings)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Voyage 4 models／input type／維度](https://docs.voyageai.com/docs/embeddings)
- [Voyage pricing](https://docs.voyageai.com/docs/pricing)
- [Voyage 4 release／shared embedding space](https://blog.voyageai.com/2026/01/15/voyage-4/)
- [Voyage 4 Nano official model card](https://huggingface.co/voyageai/voyage-4-nano)
- [OpenRouter Embeddings API](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings)
- [OpenRouter current embedding model catalog](https://openrouter.ai/api/v1/embeddings/models)
