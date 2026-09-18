# 0072. PostgreSQL 權威與 Qdrant 衍生 Memory 混合召回索引

- **狀態**：Proposed
- **日期**：2026-09-02
- **Owner 對齊**：Qdrant／Voyage 的比較與 compatibility 結果保留；2026-09-02 重驗後降為「只有代表性長訪談證明官方 Store recall 不足才啟用」的 deferred candidate，不屬 Memory foundation。完整 hybrid integration smoke、本機 service lifecycle 與新證據未收斂前維持 Proposed
- **上位產品契約**：[`2026-09-01-framework-independent-memory-contract.md`](../specs/2026-09-01-framework-independent-memory-contract.md)
- **框架複核**：[`2026-09-02-memory-framework-selection-revalidation.md`](../specs/2026-09-02-memory-framework-selection-revalidation.md)
- **版本／一致性研究**：[`2026-09-02-memory-versioning-concurrency-and-replay-research.md`](../specs/2026-09-02-memory-versioning-concurrency-and-replay-research.md)
- **最小切片重驗**：[`2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](../specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)；本文 Decision 只描述日後若缺口被證實時的候選架構，不得拿來提前施工 Qdrant、outbox、CAS 或 immutable revision platform
- **Supersedes when Accepted**：ADR 0057／0060 對 current runtime 不啟動或連接 Qdrant 的部分，以及 ADR 0071「第一版不固定 embedding retrieval／第二 Store index」的部分；**不取代** ADR 0057 對 OCS／PDF／indexer／embedder／Reference RAG bounded context 的隔離，也不取代 ADR 0060 的 PostgreSQL durable authority、員工核准或 provider-neutral runtime

## Context

Caliburn 的長訪談 Memory 需要兩種不同保證：

1. 日常回合只取回少量、真正相關的目前工作資訊，避免每輪重送全部 Memory；
2. 製作、重大重整或全面檢查 JD 時，能精確列舉同一 JD scope 的全部目前有效 Memory，不能因 relevance top-k 漏掉任何工作。

第二項是 authority／inventory 效果，foundation 先以 LangGraph 官方 PostgreSQL Store 的非語意 listing、可信 per-JD scope、single-writer checkpoint worklist 與 pinned-backend contract tests 驗證；這不宣稱官方 Store 已提供跨頁 snapshot，immutable revisions、CAS 與 snapshot manifest 也都只是有明確 trigger 才重開的強化。第一項是 retrieval relevance 問題；LangGraph PostgreSQL Store 沒有提供完整的繁中 lexical＋dense hybrid ranking，但這個能力邊界尚未被代表性長訪談證明為實際產品缺口。[LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores) · [官方 PostgreSQL Store 原始碼](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/store/postgres/base.py)

跨家官方資料的共同方向是：keyword／BM25 捕捉精確名稱、縮寫與代碼，dense retrieval 捕捉語意改寫，兩路結果以 rank fusion 合併，並先以可信 scope／metadata filter 限定候選。OpenAI Retrieval 公開 sparse text／embedding 的 RRF weights；Anthropic Contextual Retrieval 使用 BM25＋embedding＋rank fusion；Azure AI Search 與 Google Vector Search 也以 dense／sparse hybrid＋RRF 作正式能力。[OpenAI Retrieval](https://developers.openai.com/api/docs/guides/retrieval) · [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) · [Azure hybrid search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview) · [Google hybrid search](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/vector-search/about-hybrid-search)

PostgreSQL native FTS 對無空格 CJK 的 tokenizer 不足。PGroonga＋pgvector 可作單資料庫 fallback，但需要自訂 PostgreSQL extension／WAL 設定，且不是同一成熟引擎直接提供繁中 BM25、dense 與融合查詢。研究當日的 ParadeDB／VectorChord-BM25 在授權、版本成熟度或 CJK production 證據上也不足以取代首選。

Qdrant 1.19.0 是研究日官方 latest release。Qdrant 1.19 提供 native BM25、非空格語言的 `multilingual` tokenizer、以 payload filter 限定 IDF corpus、dense／sparse prefetch、RRF 與冪等 point API；這組能力最直接符合上述共同方向。[Qdrant releases](https://github.com/qdrant/qdrant/releases) · [BM25／multilingual tokenizer](https://qdrant.tech/documentation/search/text-search/full-text-search/) · [Hybrid queries／RRF](https://qdrant.tech/documentation/search/hybrid-queries/) · [Per-tenant IDF](https://qdrant.tech/documentation/manage-data/multitenancy/) · [Point idempotence](https://qdrant.tech/documentation/manage-data/points/)

## Decision（僅在日後缺口被證實且本 ADR Accepted 時）

### 1. 既有 PostgreSQL canonical owner 仍是唯一 Memory authority

本 ADR 不裁決 Semantic Memory 最終由 LangGraph checkpoint 或 Store 承接；它只要求屆時已 Accepted、以 PostgreSQL 為底層的 canonical owner 繼續保存並裁決 current Memory 與同一 JD scope 的完整 inventory。員工來源、JD authority 與審核結果也仍留在各自已 Accepted 的 canonical owners。Qdrant 的導入不得順便重定義 Memory foundation，也不得把下列條件式能力偷升格為本 ADR 的前置要求：immutable revision history、expected-version／hash CAS、獨立 operation-receipt table 或 persisted snapshot manifest。這些能力是否需要、由哪個 framework 承接，必須依屆時已觀察到的 writer／audit／盤點問題與 successor ADR 決定。

Qdrant 不保存任何只能在索引中找到的產品事實，也不得裁決 current、stale、accepted、rejected、完整性或員工權限。刪除整個 Qdrant collection 後，產品真相仍完整存在，索引必須能從 PostgreSQL current heads 重建。

### 2. Qdrant 1.19+ 只承接日常 hybrid recall

每筆可搜尋的 current Memory 以獨立 point 投影到 Qdrant，至少包含 Runtime 配發的 deterministic point ID、JD scope、Memory ID、canonical current-token／digest、可搜尋文字與必要 filter metadata。這個 token 只用來拒絕 stale derived hit；可由當時 canonical owner 已有的版本或內容 digest 承接，不要求為了索引先建立 immutable revision history。

日常召回採：

1. trusted per-JD scope filter；
2. `multilingual` BM25 lexical query；
3. dense semantic query；
4. Qdrant RRF 融合；
5. 有界 top-k ID／revision 候選；
6. 回 PostgreSQL 載入 canonical current head，丟棄 missing、retired、scope mismatch 或 revision mismatch hit。

Qdrant 的 top-k 結果只服務 Context selection。全面製作、重整與檢查 JD 一律直接從 PostgreSQL 的 verified inventory seam 列舉，不能以 Qdrant scroll、search score、導覽或模型自行判斷「已看夠」取代。

### 3. Canonical mutation 與索引投影採 transactional outbox

同一 PostgreSQL transaction 原子寫入 canonical Memory mutation 與小型 outbox event。本機 projector 讀取 event，以 deterministic point ID 呼叫 Qdrant 冪等 upsert／delete；成功後記錄投影進度。process crash、Qdrant unavailable 或重送事件時可以安全重試。

這是 Caliburn 根據成熟 transactional-outbox／derived-index 原則作出的 application mapping，不宣稱各供應商內部使用相同資料表。單機第一版不導入 Kafka、Debezium service、CDC cluster 或第二個 workflow runtime；Debezium 官方文件只作模式依據。[Debezium Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)

### 4. 核心繁中 lexical path 使用官方 Qdrant SDK

核心索引與查詢直接使用官方 `qdrant-client` 的 typed API，封裝在顧問 bounded context 的薄 adapter 後。LangChain 仍負責 agent runtime、Tool、Middleware 與 model binding；`QdrantVectorStore` 只有在不遮蔽必要能力時才可在 adapter 內使用。

不得把核心繁中 BM25 path 委託給預設 `FastEmbedSparse` wrapper，因為 Qdrant 官方文件明示 FastEmbed 不支援 `multilingual` tokenizer option。這是能力缺口，不是偏好手寫 SDK。[Qdrant full-text search](https://qdrant.tech/documentation/search/text-search/full-text-search/) · [LangChain Qdrant integration](https://docs.langchain.com/oss/python/integrations/vectorstores/qdrant)

### 5. Dense embedding 採可替換的 Voyage 4 Large leaf

2026-09-02 的窄 compatibility smoke 以 24 筆匿名繁中工作 Memory、12 個口語查詢比較 `voyageai/voyage-4-large`（1024 維）與 `google/gemini-embedding-2`（1536 維）；兩者都是 Top-1 12/12、Top-3 12/12、MRR 1.0。這只證明兩者通過當次 compatibility 門檻，不是正式 eval、普遍品質排名或當前採購決策。若代表性 recall 缺口日後真的觸發本 ADR，且重新核對版本、價格與可重跑 fixture 後仍無反證，Voyage 4 Large 才是目前優先候選。完整官方比較、資料形狀、限制與聚合結果見 [框架複核 §7.2.4](../specs/2026-09-02-memory-framework-selection-revalidation.md)。當次 probe 沒有留下可重跑 fixture，因此不得把 12/12 當 regression gate；Accepted 前的 hybrid integration smoke 必須補齊匿名 fixture、runner 與逐案預期結果。

OpenRouter request 必須固定 canonical slug `voyageai/voyage-4-large-20260727`、`allow_fallbacks=false`、1024 維、float 與 cosine；文件與 query 分別使用 provider `document`／`query` input type。另以 9-token probe 驗證該 canonical slug 可直接呼叫，實際回傳 `voyage-4-large` 與 1024 維向量。[Voyage embeddings](https://docs.voyageai.com/docs/embeddings) · [Voyage pricing](https://docs.voyageai.com/docs/pricing) · [OpenRouter Embeddings API](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings) · [OpenRouter model catalog](https://openrouter.ai/api/v1/embeddings/models)

若本候選被觸發，index manifest 至少固定 requested canonical model ID、provider／adapter revision、回傳 model ID、維度、dtype、distance、input-mode contract 與 index generation。任何不相容變更都建立新 generation／全量重建，不能在同一 collection 靜默混用不同 vector space。候選首版的文件與 query 使用同一 large model，不先引入 Voyage 4 asymmetric model mixing；本機 `voyage-4-nano` 只保留為有實際離線需求後的候選，不因此增加第二條 production path。[Voyage 4 shared embedding space](https://blog.voyageai.com/2026/01/15/voyage-4/) · [Voyage 4 Nano](https://huggingface.co/voyageai/voyage-4-nano)

不得為了省事直接 import 或重用 `apps/embedder`、`apps/ocs-indexer`、其 contracts、其 collection 或 Reference corpus。embedding model 變更必須建立新 index generation 或全量重建，不能在同一 collection 靜默混用不同 vector space。

### 6. 這不是把 Reference RAG 接回 current 產品

Qdrant Memory index 的 corpus 只有同一員工／同一 JD scope 的 current Semantic Memory projection。即使本候選日後啟用，仍不因此查 iCAP、OCS、PDF、公司文件或外部 Reference，不新增 Reference evidence type，也不讓 RAG bounded context import current API。

若本 ADR Accepted，Qdrant 會成為 current 顧問的本機 infrastructure dependency；現有 `rag` profile、`rag:down` 與 Qdrant 1.18.2 pin 必須在施工計畫中明確調整，確保 current Memory lifecycle 不會被 RAG command 停掉。可共用同一 Qdrant process 但必須使用隔離 collection、manifest 與 adapter；也可採獨立 service，最終 topology 以較少營運混淆且不破壞 bounded-context 隔離者為準。

### 7. 候選首版保持最小 retrieval stack

若 recall trigger 成立，候選首版也不預設加入 reranker、SPLADE、miniCOIL、GraphRAG、knowledge graph、query-planning agent 或第二個 retrieval model。BM25＋dense＋RRF 是跨家共同、成本較低且沒有 relevance labels 時假設較少的基線。

只有代表性繁中資料顯示固定 failure pattern，且新增元件的效果收益高於 latency、token／inference 成本與維護成本，才以 successor ADR 重開。不得因供應商文件列出功能就全部啟用。

### 8. Accepted／施工前的最小門檻

Dense leaf 的繁中 compatibility smoke 已完成；以下完整 hybrid integration smoke 仍不是正式 eval 平台，只驗證能否採用：

1. 繁中無空格詞與兩字詞能被 lexical path 找回；
2. 英文縮寫、法規名、專有名詞與精確短語不被 dense-only 漏掉；
3. 同義改寫能由 dense path 找回；
4. per-JD filter 與 IDF corpus 不跨 scope；
5. Qdrant stale／missing revision 在 PostgreSQL canonical read 被拒；
6. outbox event 重送、process restart 與全量 rebuild 冪等；
7. Qdrant unavailable 不破壞核准 JD、exact inventory 與 deterministic export；
8. index manifest 能阻止不同 embedding model／schema generation 混用。

若 1～4 無法通過，首選不能靠 prompt workaround 上線；回到 PGroonga＋pgvector fallback 或重開 retrieval engine 比較。

## Consequences

### Positive

- 日常 Context 同時保留繁中精確詞與語意改寫召回，符合 OpenAI、Anthropic、Microsoft、Google 的共同 hybrid 方向；
- Qdrant 原生完成 BM25、dense、filter 與 RRF，避免在 application 自行拼兩套 ranking／normalization；
- PostgreSQL 仍是唯一真相，索引延遲、遺失或重建不會改寫 Memory／JD authority；
- exact inventory 與 relevance retrieval 明確分工，不會用 top-k 假裝證明 JD 完整性；
- projector 與 Qdrant point API 可冪等重試，適合本機 process crash／restart；
- retrieval engine、embedding model 與 agent runtime 分層，未來可獨立替換。

### Negative

- current 產品新增一個本機服務、volume、health／startup／backup-ignore／upgrade 邊界；
- canonical Memory 與衍生索引是 eventual consistency，必須有 outbox、lag／rebuild observability 與 stale-hit validation；
- 每次新增／修訂 Memory 需要 dense embedding compute；
- Qdrant 1.19 導入會改變 ADR 0057 的 current infrastructure 邊界與既有 `rag:down` 語意；
- dense leaf 已通過窄繁中 smoke，但 Qdrant tokenizer、top-k／fusion 與整體 stale／replay 邊界仍需整合 smoke；不能把 12/12 compatibility 結果宣稱為普遍產品效果。

## Rejected alternatives

1. **只用 LangGraph Store semantic top-k。** 會漏掉專有名詞、縮寫與精確措辭，也不能完成跨家共同的 lexical＋semantic hybrid。
2. **每輪把全部 Memory 放進 prompt。** 成本與干擾隨訪談成長；也使 retrieval 品質問題被 token 堆疊掩蓋。
3. **用 Qdrant 作 canonical Memory 或 exact inventory。** 會形成第二 authority，且 relevance index 的 eventual consistency 不適合員工核准與完整盤點。
4. **PostgreSQL native FTS＋pgvector。** 單服務較簡單，但繁中斷詞與 BM25／fusion 效果不足，不能以程式較少取代產品召回品質。
5. **PGroonga＋pgvector 作首選。** 是正式 fallback，但會把全文索引 extension、WAL／crash-safe 設定與 vector fusion 壓進 authority DB；共同能力與官方整合度仍不如 Qdrant 1.19。
6. **ParadeDB／VectorChord-BM25 作第一版。** 研究日的授權、版本成熟度或 CJK production 證據不足。
7. **直接重用 RAG Qdrant／embedder bounded context。** 會把 Memory 與外部 Reference corpus、生命週期和 dependency graph 混在一起，違反現行產品邊界。
8. **第一版同時加入 reranker／SPLADE。** 在沒有代表性 labels 與明確 failure evidence 時，增加成本與複雜度但無法證明實質收益。

## Acceptance gate

1. §8 的繁中、隔離、stale、replay、rebuild 與 degraded-mode smoke 有可重跑證據；
2. dense embedding model、版本、維度、距離函式與 index manifest 已明確裁決；
3. current Qdrant service lifecycle 不受 `rag:down` 影響，RAG collection／adapter 仍保持隔離；
4. canonical mutation＋outbox 同 transaction，projector 可重試且 Qdrant 不存在任何唯一產品事實；
5. 日常 query 一律回 PostgreSQL 驗 canonical current revision；
6. 全面 JD build／audit 只走 PostgreSQL verified inventory seam，並有 pinned-backend 多頁、同排序值、restart 與 scope-isolation 測試；只有盤點期間確實允許並行 mutation 時，才另要求 snapshot／generation／manifest gate；
7. Qdrant unavailable、index lag 或 rebuild 中的 UI／API degraded contract 已定義，不會靜默回傳舊事實；
8. runtime boundary tests 證明 current 顧問沒有 import RAG apps／contracts，也沒有接入 Reference corpus；
9. 成本觀測可分辨 embedding、Qdrant query、模型 Context 與全面盤點；
10. ADR 0057、0060、0071、`AGENTS.md`、`docs/design/consultant-runtime.md` 與 `docs/design/rag-pipeline.md` 的 successor 邊界同步完成。
