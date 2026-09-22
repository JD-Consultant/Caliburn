# 檢索/知識層前沿技術調查(2025–2026)

> 場景假設(貫穿全文的判定基準):**繁體中文、政府職能基準、結構化 JSON、數千文件量級、品質優先於成本**。
> 現況:BGE-M3(dense+sparse 混合)+ Qdrant，做相似比對與知識供給。
> 來源紀律:只採模型/檢索廠官方文件、原論文、官方 benchmark。二手來源(教學站、平台轉述)僅在補充延遲/實務數字時使用並標註。

---

## 執行摘要(給忙碌讀者)

對本場景,能把檢索品質往上推、**最划算的兩件事**是:
1. **加一層 reranker**(cross-encoder 重排 top-k)—— 官方數字顯示這是單一 CP 值最高的升級,中文支援成熟。**強烈建議用**。
2. **升級/雙跑嵌入模型**(Qwen3-Embedding 系列已在 MTEB 多語榜超越 BGE-M3)—— 品質優先場景值得評測換裝。**建議評測**。

**Contextual Retrieval** 對「已結構化的短 JSON 文件」邊際效益低(它是為了救「chunk 切碎後失去上下文」而生,你的資料本來就有 schema),**可選擇性試、非必要**。
**GraphRAG** 對「本來就有 schema 的結構化資料」價值存疑,建圖成本高,**多數情況不用**(除非要回答跨全庫的宏觀彙總問題)。
**Query 端技術(HyDE / 改寫 / 分解)**:證據混雜,HyDE 在 zero-shot 有效但會引入幻覺;**單項可試,別當預設**。
**Late interaction(ColBERT)**:品質好但儲存成本 O(tokens),對數千文件量級可負擔,**可當進階選項試**,但 reranker 通常先做。

---

## 1. Contextual Retrieval(Anthropic, 2024-09)

**白話**:傳統 RAG 把長文件切成 chunk 再嵌入,chunk 一旦離開原文就失去上下文(例:「該公司營收成長 3%」——哪家公司?哪一季?)。Contextual Retrieval 的做法是:嵌入前,先用一個便宜 LLM 為每個 chunk 生成 50–100 token 的情境說明(「本段出自 ACME 2023 Q2 財報,說明營收…」),把說明**接在 chunk 前面再嵌入**,同時也餵給 BM25 索引。

**官方證據**(Anthropic, "Introducing Contextual Retrieval", 2024-09-19):
- Contextual Embeddings 單獨:top-20 檢索失敗率 **降 35%**(5.7% → 3.7%)。
- + Contextual BM25(即混合檢索):**降 49%**(5.7% → 2.9%)。
- 再 + Reranking:**降 67%**(5.7% → 1.9%)。
- 生成情境的一次性成本:用 prompt caching 約 **$1.02 / 百萬 document tokens**(用 Claude 3 Haiku)。
- 官方明確門檻:**知識庫 < ~200,000 tokens 時不需要**——直接把全部塞進 prompt(prompt caching)即可,別做這套。
- 官方建議 retrieve top-20 chunks 效果最佳。
- URL: https://www.anthropic.com/news/contextual-retrieval

**適用時機**:長文件被迫切碎、chunk 脫離上下文會語意殘缺時。
**成本**:一次性 LLM 生成成本(便宜)+ 需重建索引;之後查詢期零額外成本。
**不該用的情況**:文件本身短、已結構化、每個單位自帶足夠上下文;或整庫小到能塞進 prompt。

**對本場景判定:可試(優先度低)。** 職能基準是政府發布的**結構化 JSON**,每個欄位(職能項目、行為指標、知識技能)本來就帶語意邊界,不是「被切碎失去上下文」的長敘事文。真正的價值不在自動生成情境,而在**「用你已有的 schema 當情境」**——嵌入時把 `職類 > 職能 > 指標` 的路徑、文件標題等 metadata 拼進待嵌文字(等同人工版 contextual embedding,零 LLM 成本)。這個變體強烈建議做;Anthropic 那套全自動 LLM 生成情境對你屬 overkill。

---

## 2. Reranker 2026 現況

**白話**:第一階段檢索(向量/BM25)為了快,用的是「查詢和文件各自獨立編碼」的 bi-encoder,精度有天花板。Reranker 是 **cross-encoder**:把「查詢+候選文件」一起餵進模型算相關性,精度高但慢,所以只用來**重排第一階段的 top-k(如 top-50 → top-10)**。這是「先廣撒網再精挑」的第二關。

**官方證據**:
- **Voyage rerank-2.5 / 2.5-lite**(Voyage AI 官方 blog, 2025-08-11):NDCG@10 相對 **Cohere Rerank v3.5 高 7.94% / 7.16%**;相對 **Qwen3-Reranker-8B 高 2.25% / 1.47%**;MAIR benchmark 上高 12.70% / 10.36%。**32K context**(Cohere v3.5 的 8×),涵蓋 31 語言 51 資料集,支援 instruction-following。新用戶前 200M tokens 免費。URL: https://blog.voyageai.com/2025/08/11/rerank-2-5/
- **Cohere Rerank 3.5**(Cohere, 2024-12-02;規格細節見 Azure/Oracle 官方平台文件):支援 **100+ 語言**,在 10 大商業語言(含**中文**)達 SOTA。URL: https://cohere.com/blog/rerank-3pt5 ;規格 https://ai.azure.com/catalog/models/Cohere-rerank-v3.5
- **BGE-reranker-v2-m3**(BAAI 官方文件):多語、可自架、開源;社群普遍當「安全預設」。URL: https://bge-model.com/bge/bge_reranker_v2.html
- **Qwen3-Reranker**(Qwen 官方 blog, 2025-06-05):0.6B/4B/8B,Apache-2.0,可自架,支援 instruction。MTEB-R 上 Qwen3-Reranker-8B **69.02** vs BGE-reranker-v2-m3 **57.03**。URL: https://qwenlm.github.io/blog/qwen3-embedding/

**延遲代價**(二手,標註):Cohere 3.5 對 <2k token chunk 約 +80–150ms p50,>3k token 可破 200ms p99;Voyage 2.5 平均約 595–603ms(ZeroEntropy / Agentset benchmark，非原廠)。

**適用時機**:第一階段召回夠但排序不夠準(top-1~3 常漏正解);品質優先。**這是本場景 CP 值最高的單一升級**(Anthropic 數字:加 reranking 讓失敗率再從 2.9%→1.9%)。
**成本**:每查詢一次額外模型呼叫,+100–600ms;自架(BGE / Qwen3-Reranker)則吃 GPU。
**不該用的情況**:第一階段召回本身就差(rerank 救不了沒被撈進 top-k 的正解);或延遲預算極緊的即時場景。

**對本場景判定:強烈建議用。** 品質優先、數千文件、可接受數百 ms。首選路線:**自架 `bge-reranker-v2-m3` 或 `Qwen3-Reranker-4B`**(與現有 embedder GPU 容器同構、資料不出境、中文強、開源可控);若可接受 API 且要最省事,Cohere 3.5 / Voyage 2.5 中文皆 SOTA。契合你「embedder 走 HTTP、torch 不進 app 進程」的架構——reranker 同樣掛在 GPU 容器後面。

---

## 3. 嵌入模型 2026 SOTA

**白話**:BGE-M3(2024)之後,更強的多語/中文嵌入模型出現了。榜單主要看 MTEB(多語)與 C-MTEB(中文)。

**官方證據**:
- **Qwen3-Embedding**(Qwen 官方 blog, 2025-06-05):0.6B/4B/8B,32K context,dim 1024/2560/4096,**Apache-2.0**。8B 在 **MTEB 多語榜達 70.58,發布時榜首**。**dense-only**(dual-encoder),官方未提 sparse。URL: https://qwenlm.github.io/blog/qwen3-embedding/
- **Gemini Embedding (gemini-embedding-001)**(Google, 2025-03 起,GA 公告):MTEB 多語榜首(平均約 68.32),3072 dim + Matryoshka 可截斷,2K token 輸入,100+ 語言,**閉源 API**。URL: https://developers.googleblog.com/gemini-embedding-available-gemini-api/
- **BGE-M3**(BAAI, arXiv 2402.03216):仍是唯一在**單一模型內同時輸出 dense + sparse + multi-vector(ColBERT 式)**的主流開源模型;100+ 語言、8192 token。這是它現在最大的差異化(見 §8 late interaction)。URL: https://huggingface.co/BAAI/bge-m3
- **官方 MTEB/C-MTEB leaderboard**(權威榜單,非轉述):https://huggingface.co/spaces/mteb/leaderboard (C-MTEB = 35 tasks / 6 task types)。

**dense+sparse 混合還是主流嗎?** 是。混合檢索(dense 抓語意 + sparse/BM25 抓精確詞面)仍是 2026 生產級 RAG 的標配;新旗艦(Qwen3、Gemini)雖 dense 更強,但**多數只出 dense**,sparse 部分你仍需另配(BGE-M3 的 sparse、或 Qdrant 內建 BM25)。

**late interaction(ColBERT 系)實用性**:見 §8。

**適用時機**:品質優先、想壓低第一階段召回失誤時,換更強的 dense 模型直接抬升召回天花板。
**成本**:換模型 = 全庫重嵌入 + 重建索引(數千文件成本很低);自架大模型吃 GPU/VRAM。
**不該用的情況**:現有召回已飽和(瓶頸在排序而非召回)——那應先做 §2 reranker 而非換嵌入。

**對本場景判定:建議評測換裝(或雙跑)。**
- 首選評估 **Qwen3-Embedding-4B/8B**:中文強、Apache-2.0 可自架(資料不出境,符合多租戶隔離)、與現有 GPU 容器同構。
- **關鍵取捨**:Qwen3 是 dense-only。你現在靠 BGE-M3 一顆同時供 dense+sparse。換 Qwen3 dense 後,sparse 要改用 **Qdrant 內建 BM25 / 中文分詞 sparse**(見 §6)。務必用你自己的 ground-truth(§8)A/B,而非只信 MTEB——MTEB 未必涵蓋「政府職能基準」這種窄域文體。
- 保守作法:**保留 BGE-M3 當 sparse + 基線 dense,並列評測 Qwen3 dense**,誰在你的評測集贏用誰。品質優先,值得這一輪評測工。

---

## 4. GraphRAG / 知識圖譜檢索

**白話**:GraphRAG(Microsoft)先用 LLM 把整批文件抽成**實體-關係知識圖**,再把圖分群(community)並為每群生成摘要;查詢時走 **local search**(針對特定實體)或 **global search**(彙整全庫回答宏觀問題,如「整批資料的主題趨勢?」)。解決的是「向量 RAG 答不了需要縱覽全庫的問題」。

**官方證據**:
- Microsoft GraphRAG 官方文件:global search = 回答「全庫主題/趨勢」類抽象問題;local search = 結合圖的結構化資料 + 原文,回答特定實體問題。URL: https://microsoft.github.io/graphrag/
- **LazyGraphRAG**(Microsoft Research, 2024-11):指出標準 GraphRAG **前期建圖(LLM 抽實體+社群摘要)成本高**,LazyGraphRAG 延後建圖以降本。URL: https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- Microsoft 亦提醒:**針對結構化/半結構化資料(財報、帳表),為敘事文優化的實體抽取 prompt 會漏掉真正重要的表格與階層關係。**

**適用時機**:語料是**大量非結構化敘事文**,且查詢型態是「跨文件、需縱覽全庫的彙總/主題/多跳」問題。
**成本**:高——全庫 LLM 抽圖 + 社群摘要 + 維護圖;資料更新要重抽。
**不該用的情況**:語料本來就有明確 schema/階層;查詢是「找相似職務/供給某條知識」的點檢索;或量級小、更新頻繁。

**對本場景判定:多數情況不用。** 你的職能基準**本身就是知識圖**——`職類→職能→行為指標→知識/技能` 的階層與關聯已在 JSON schema 裡,不需要用 LLM 去「猜」抽取(還可能抽錯、丟關係)。**正確做法是直接用既有結構**:把 schema 關係存成 Qdrant payload / 關聯欄位,查詢時用 metadata filter + 圖式 join(§7),而不是套 GraphRAG 那套為敘事文設計的抽取管線。
**唯一例外(可試):** 若日後要回答「橫跨數千職能基準的宏觀彙總」(如「製造業職類近年新增哪些數位技能指標?」),這類 global 問題向量檢索天生答不好,屆時可針對該用途小範圍試 global-search 式彙整——但那是分析型功能,不是核心相似比對。

---

## 5. Query 端技術(rewriting / decomposition / HyDE / multi-query / agentic)

**白話**:
- **HyDE**:先讓 LLM 依查詢**生成一篇「假想的理想答案文件」**,再拿這篇的嵌入去檢索(而非用短查詢直接檢索)——因為「假答案」在向量空間更接近真文件。
- **Query rewriting / decomposition / multi-query**:把口語/複雜查詢改寫、拆成多個子查詢分別檢索再合併。
- **Agentic retrieval**:讓模型自主決定「何時查、查什麼、要不要再查」,多輪邊想邊查,對付多跳問題。

**官方證據**:
- **HyDE 原論文**(Gao et al., "Precise Zero-Shot Dense Retrieval without Relevance Labels", ACL 2023 / arXiv 2212.10496):在**無標註資料的 zero-shot** 設定下顯著有效;但生成的假文件是「fake」、**可能含幻覺**。URL: https://arxiv.org/abs/2212.10496
- **"Searching for Best Practices in RAG"**(arXiv 2407.01219):實測 **query rewriting / decomposition 對檢索效果提升不如其他方法**;**Hybrid Search + HyDE** 綜合最佳,被推為預設檢索法。URL: https://arxiv.org/pdf/2407.01219
- **Agentic search**(業界重要信號):**Anthropic 於 2025-05 把 Claude Code 內的向量檢索(embedding pipeline + 本地向量庫 + chunking)整套移除,改用 agentic search(grep)**——理由是 agentic 多輪搜尋效果更好,且更簡單、免去 staleness/隱私/可靠性問題。這是「單發向量檢索並非萬靈丹」的一手佐證(但情境是**程式碼庫**,與你的窄域中文語料不同)。

**適用時機**:查詢與文件用詞差距大(口語 vs 公文)、多跳問題、探索式問答。
**成本**:每項都多一次(或多次)LLM 呼叫 + 額外檢索輪次;agentic 成本與延遲最高。
**不該用的情況**:查詢已能一次撈到正解;延遲/成本敏感;或缺評測會盲目疊技巧反傷精度(改寫可能引入雜訊)。

**對本場景判定:HyDE 可試(單項、要評測把關);agentic 目前不用。**
- 你的痛點很可能是**查詢語彙 vs 職能基準公文語彙的落差**(顧問用白話問、文件是制式術語)。HyDE 正好對症:先讓 LLM 生成一段「像職能基準的描述」再檢索。**值得在評測集上單獨試 HyDE**,贏了才留。
- **decomposition / multi-query** 官方證據顯示收益有限,別當預設。
- **agentic retrieval**:對「相似比對 + 知識供給」這種**單發就能解**的點檢索是殺雞用牛刀,徒增延遲成本。留給未來若出現真正多跳的分析問句再說。

---

## 6. 中文/CJK 特有注意

**白話**:中文沒有空格分詞,**sparse/BM25 檢索完全取決於分詞(tokenization)品質**——分詞爛,詞面比對就爛。dense 嵌入受影響較小,但 sparse 這關中文是硬骨頭。

**官方/一手證據**:
- **BGE-M3 論文**(arXiv 2402.03216):在 194 語言無監督資料上訓練,含中文標註微調(MIRACL / Mr.TyDi);明言 **sparse 表徵的 tokenizer 選擇是值得深究的方向**——即 sparse 品質對分詞敏感。URL: https://arxiv.org/html/2402.03216v3
- 通則(社群/實作共識):中文 sparse/BM25 前**須先做中文斷詞**(jieba、或 Qdrant/ES 的 CJK analyzer)才餵 BM25;日文需 MeCab/SudachiPy、泰文無空格需專用 tokenizer。
- **繁中特有坑**(據來源整理,需自行驗證):簡繁字形差異、異體字、全形/半形、政府公文的專門術語與縮寫——這些會同時影響 dense(訓練語料多簡體)與 sparse(斷詞詞典未收術語)。

**適用時機**:凡是走 sparse/BM25 的中文檢索都必須正視分詞;繁中窄域(政府術語)尤甚。
**成本**:配置中文 analyzer / 自訂詞典的一次性工;維護專有術語詞典的持續小成本。
**不該用的情況**:純 dense 檢索可略過分詞;但放棄 sparse 會失去精確詞面比對(職能術語、代碼、專名的精準命中),對本場景不划算。

**對本場景判定:必須處理(硬性)。**
- **繁簡**:BGE-M3 / Qwen3 訓練語料以簡體為主。務必測繁中效果;必要時查詢與文件**正規化到統一字集**(如檢索期繁→簡對齊)以提升召回,但要保留原繁中顯示。
- **sparse 分詞**:若換 Qwen3(dense-only),sparse 那半必須**自己配中文斷詞的 BM25**(Qdrant 支援自訂 sparse 向量 / analyzer)。並**為政府職能術語建自訂詞典**(職類名、能力指標代碼),否則斷詞會把專名切碎。
- **建一個繁中專有名詞/術語表**當分詞詞典 + 同義詞擴充,是本場景性價比極高的一步。

---

## 7. 結構化資料的檢索(metadata filtering + 向量)

**白話**:你的資料本來就是 JSON,有天然欄位(職類、產業、版本、發布年、能力等級)。這些**該用精確過濾(filter)處理,而非丟給向量去猜**。正解是「**先用 metadata filter 縮小候選集,再在其中做向量/混合檢索**」。

**官方證據(Qdrant 官方文件)**:
- **建 payload index**:對要 filter 的欄位建 payload index,且**最好在灌資料前先建**,查詢才快。URL: https://qdrant.tech/documentation/concepts/indexing/
- **filterable HNSW / cardinality**:預過濾 vs filterable HNSW 取決於 filter 基數;基數太低的 filter 會破壞圖連通性——需按欄位分佈調。URL: https://qdrant.tech/articles/vector-search-filtering/
- **混合融合**:dense(cosine,有界)與 sparse(BM25,無界)分數尺度不同且逐查詢漂移,**別用固定 alpha 加權原始分數**;用 **RRF(依排名位置融合)或 DBSF**。典型 pattern:prefetch 內用 RRF/DBSF 融多路,再用 formula query 疊 recency/boost 等排序邏輯。URL: https://qdrant.tech/documentation/concepts/hybrid-queries/

**適用時機**:資料有明確可過濾欄位(你的場景 100% 符合)。
**成本**:建 payload index 的少量儲存/設定;設計 filter schema 的一次性思考。
**不該用的情況**:欄位基數極低(如只有 2 個值)且分佈極不均時,單靠 filter 可能傷 HNSW 圖——需測。

**對本場景判定:強烈建議用(近乎必做)。** 這是「結構化語料」最直接的品質槓桿:
- 把 JSON 的 `職類 / 產業別 / 發布年 / 能力等級 / 版本` 全存成 Qdrant **payload 並建 index**;查詢先 filter(如「限製造業、限現行版」)再向量比對——**大幅減少誤召回**,對相似比對精度提升立竿見影。
- 融合用 **RRF**(Qdrant 內建),別自己調 alpha。
- 這一步不需新模型、風險低、收益確定,**應排在所有升級的最前面**。

---

## 8. 評測檢索品質(retrieval evals)

**白話**:任何檢索改動(換模型、加 reranker、開 HyDE)**能不能上,取決於有沒有一把尺**。尺 = 一組 (查詢 → 正解文件) 的 ground truth + 標準指標(recall@k、MRR、NDCG@k)。沒有評測集,所有「升級」都是盲改。

**官方/一手方法**:
- **Anthropic 的作法**(contextual retrieval 一文即示範):以 **top-20 chunk 檢索失敗率**為單一北極星指標,對每種組合(embedding / +BM25 / +rerank)量測並比對——**recall@k / 失敗率是官方採用的檢索評估法**。URL: https://www.anthropic.com/news/contextual-retrieval
- **標準指標**:Recall@k(正解有沒有進 top-k,對兩階段檢索最關鍵)、MRR、NDCG@k(排序品質,rerank 前後對比常用)。
- **ground truth 建法**:從真實查詢/顧問實際使用情境,人工標註「這個查詢的正解文件是哪幾份」;數千文件量級,標 50–200 條高品質 query-doc 對即足以驅動決策。
- **官方 benchmark 當外部參照**:MTEB / C-MTEB retrieval 子集(https://huggingface.co/spaces/mteb/leaderboard )可當選型初篩,但**不能取代你自己窄域的評測集**——政府職能基準文體特殊,泛榜分數未必轉移。

**適用時機**:任何時候。這是所有其他升級的前提設施。
**成本**:一次性建評測集(人工標註)+ 每次改動跑一次評測的 CI 成本(低)。
**不該用的情況**:無。**沒有評測就別動檢索**——否則 §1–7 全是賭博。

**對本場景判定:必做(且應最先做)。** 具體建議:
1. 收集/構造 **50–200 條 (顧問實際查詢 → 正解職能文件)** 的 ground truth。
2. 指標定 **Recall@10 + Recall@20(召回關)與 NDCG@10(排序關,測 reranker 用)**。
3. 把它接進測試流程(對齊你們 `green-before == green-after` 的紀律),讓「換 Qwen3 / 加 reranker / 開 HyDE」都能被同一把尺驗證,**贏了才 merge**。
4. 這把尺一旦建好,§2/§3/§5 的所有評估才有意義——**它是整個升級路線的地基**。

---

## 建議落地順序(品質優先、風險遞增)

1. **建 retrieval eval 集(§8)** —— 地基,無此免談。
2. **metadata filtering + payload index + RRF 融合(§7)** —— 低風險、收益確定、貼合結構化語料。
3. **中文 sparse 分詞 + 繁中術語詞典 + 繁簡對齊(§6)** —— 修 sparse 這關的中文硬傷。
4. **加自架 reranker(§2)** —— 單一 CP 值最高的品質跳升。
5. **評測 Qwen3-Embedding 換裝 / 雙跑(§3)** —— 抬召回天花板(用 §8 的尺定奪)。
6. **(選)HyDE 對付語彙落差(§5)、schema-as-context 嵌入(§1 變體)** —— 單項試、評測把關。
7. **(暫不)GraphRAG(§4)、agentic retrieval(§5)** —— 除非出現真正的全庫彙總/多跳需求。

---

## 來源總表

| # | 來源 | 類型 | 日期 | URL |
|---|------|------|------|-----|
| 1 | Anthropic — Introducing Contextual Retrieval | 廠商官方 | 2024-09-19 | https://www.anthropic.com/news/contextual-retrieval |
| 2 | Voyage AI — rerank-2.5 / 2.5-lite | 廠商官方 blog | 2025-08-11 | https://blog.voyageai.com/2025/08/11/rerank-2-5/ |
| 3 | Cohere — Introducing Rerank 3.5 | 廠商官方 | 2024-12-02 | https://cohere.com/blog/rerank-3pt5 |
| 4 | Cohere Rerank v3.5 規格(Azure catalog) | 官方平台文件 | 2024-12 | https://ai.azure.com/catalog/models/Cohere-rerank-v3.5 |
| 5 | BAAI — BGE-reranker-v2 文件 | 廠商官方 | 2024– | https://bge-model.com/bge/bge_reranker_v2.html |
| 6 | Qwen — Qwen3 Embedding & Reranker | 廠商官方 blog | 2025-06-05 | https://qwenlm.github.io/blog/qwen3-embedding/ |
| 7 | Google — Gemini Embedding GA | 廠商官方 blog | 2025 | https://developers.googleblog.com/gemini-embedding-available-gemini-api/ |
| 8 | BAAI — BGE-M3 (HF model card) | 廠商官方 | 2024– | https://huggingface.co/BAAI/bge-m3 |
| 9 | BGE-M3 論文 (M3-Embedding) | 原論文 | 2024 (arXiv 2402.03216) | https://arxiv.org/html/2402.03216v3 |
| 10 | MTEB / C-MTEB 官方 leaderboard | 官方 benchmark | 持續更新 | https://huggingface.co/spaces/mteb/leaderboard |
| 11 | Microsoft — GraphRAG 官方文件 | 廠商官方 | 2024– | https://microsoft.github.io/graphrag/ |
| 12 | Microsoft Research — LazyGraphRAG | 廠商官方 blog | 2024-11 | https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/ |
| 13 | HyDE 原論文 (Gao et al., ACL 2023) | 原論文 | 2022-12 (arXiv 2212.10496) | https://arxiv.org/abs/2212.10496 |
| 14 | Searching for Best Practices in RAG | 原論文 | 2024-07 (arXiv 2407.01219) | https://arxiv.org/pdf/2407.01219 |
| 15 | Qdrant — Hybrid Queries 文件 | 廠商官方 | 2024– | https://qdrant.tech/documentation/concepts/hybrid-queries/ |
| 16 | Qdrant — Vector Search Filtering | 廠商官方 | 2024– | https://qdrant.tech/articles/vector-search-filtering/ |
| 17 | Qdrant — Multivectors & Late Interaction | 廠商官方 | 2024– | https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/ |
| 18 | Jina — ColBERT v2 (multilingual late interaction) | 廠商官方 | 2024 | https://jina.ai/news/jina-colbert-v2-multilingual-late-interaction-retriever-for-embedding-and-reranking/ |

> 註:延遲數字(Cohere/Voyage 毫秒級)引自 ZeroEntropy / Agentset 第三方 benchmark,非原廠,已於 §2 標註;繁中特有坑部分為社群實作共識,建議在自有評測集上驗證。

## Late interaction(ColBERT)補充(§3 延伸)

**白話**:一般嵌入把整段文件壓成**一顆**向量;ColBERT 式 late interaction 為文件的**每個 token 各留一顆向量**,查詢時逐 token 比對取最大相似(MaxSim),精度更高(尤其長文件精準定位)。BGE-M3 本身就內建這個 multi-vector 輸出。
**官方證據**:Qdrant 自 v1.10 支援 multi-vector 與 late-interaction(可直接接 jina-colbert-v2);儲存成本 **O(P×L) 隨文件 token 數線性成長**,遠高於單向量的 O(P)。URL 見來源表 #17、#18。
**判定:可試(進階選項)。** 數千文件量級,multi-vector 儲存成本可負擔;BGE-M3 你已在用、其 multi-vector 幾乎免費附送,可當「第一階段召回後的精排」替代或搭配 reranker。但**一般先做 cross-encoder reranker(§2)投報率更高**,late interaction 留作進一步榨精度的選項。
