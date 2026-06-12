# Design Decisions

> 開發過程中所有關鍵設計決策的紀錄，含選了什麼、為什麼選、考慮過的替代方案、會在什麼條件下重新評估。
>
> 本文件不 commit，僅供專題報告與內部設計參考。

每筆採用統一格式：

```
## D-N: <一行決策標題>
- 背景 / 觸發
- 決策
- 為什麼
- 考慮過的替代方案
- 何時重新評估
- 對使用者體驗的影響
```

---

## D-1: indexer 與 RAG service 分 repo

### 背景 / 觸發
專案啟動時的第一個架構決策。要不要把「OCS 索引建置」與「JD 顧問對話」放同一個 repo？

### 決策
**分兩個 repo**：
- `jd-ocs-indexer`（本 repo）：只負責 OCS JSON → Qdrant collection 的建置與維護
- 未來 `jobintel-ai`（或類似名稱）：負責 LLM 顧問、使用者互動、JD 生成

### 為什麼

1. **責任邊界清楚**：indexer 是 batch / offline，consumer 是 online / interactive。混在一起會導致 indexer 為了 query 改 schema、consumer 為了 indexer schema 妥協對話設計
2. **變動頻率不同**：indexer schema 一年改 1-2 次，consumer 對話策略可能每週迭代。同 repo 會互相干擾
3. **資料規模對應的工程要求不同**：indexer 跑 80-100 min CPU、寫進 12,869 points；consumer 是 sub-second response。技術 stack 不同
4. **政策無關**：indexer 不應該知道「使用者問了什麼類型問題」、「LLM 怎麼挑 K/S」這類產品政策。consumer 也不應該知道「Qdrant collection 怎麼建」這類底層細節

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 同 repo，monorepo 結構 | 對小團隊負擔太重，且兩個服務的部署 / 版本管理本來就不同 |
| 同 repo，folder split | folder 不會強制職責邊界，最後仍會交叉依賴 |
| indexer 內建查詢 API | 違反「indexer 只負責寫」的職責，且 query 政策（哪些 filter 預設、score 怎麼算）會變很快 |

### 何時重新評估

- 如果發現 indexer 與 consumer 90% 改動都同時發生（強耦合信號），考慮合併
- 如果發現 consumer 為了 indexer 的 schema 拐很多彎，考慮把部分 schema 邏輯下放到 indexer

### 對使用者體驗的影響

無直接影響。對開發者體驗影響大：邊界清楚的設計減少跨 repo 衝突，加快迭代速度。

---

## D-2: 三層 chunk（profile / unit / block）不是兩層或四層

### 背景 / 觸發
ChunkBuilder 設計時，需要決定切分粒度。OCS JSON 結構是 4 層（profile → ocu_unit → task_group → competency_block）。

### 決策
**3 層**：profile / unit / block。task_group 不獨立成 chunk，併進 block 的 payload。

### 為什麼

1. **task_group 本身沒實質內容**：OCS JSON 裡 task 只有 code + name，所有具體工作活動都在底下的 competency_block。task 獨立成 chunk 會是空殼
2. **profile / unit / block 對應顧問訪談的問題粒度**：
   - profile = 「你是什麼職業？」
   - unit = 「你做哪類型的工作主題？」
   - block = 「具體怎麼做？用什麼工具？」
3. **2 層（profile / block）缺中間粒度**：直接從 profile 跳到 block 會失去「unit 內任務群組」的概念，gap detection 變難
4. **保留 task 資訊用 payload**：每個 block chunk payload 含 task_ids / task_titles，consumer 可以聚合，不需要獨立 chunk

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 2 層（profile / block） | 失去 unit 群組，gap detection 困難 |
| 4 層（profile / unit / task / block） | task chunk 沒實質內容，是冗餘 |
| 1 層（每份 JSON 一個大 chunk） | 失去粒度，retrieval 沒法定位到具體能力 |
| Sentence-level chunking | OCS 已是結構化資料，硬切會破壞語意 |

### 何時重新評估

- 如果 block 平均長度超過 BGE-M3 max_length 8192 token（目前約 200-500 字，安全）
- 如果新版 OCS schema 加入 sub-block 層級
- 如果使用者 query 模式高度集中在某一層，可考慮減層

### 對使用者體驗的影響

三層粒度讓顧問訪談可以從粗到細：先確定職業類型 → 確定工作主題 → 細問具體做法。對 progressive disclosure 流程很自然。

---

## D-3: BGE-M3 不是 OpenAI / 其他 embedding model

### 背景 / 觸發
選定 embedding provider。

### 決策
**BGE-M3**（local，FlagEmbedding library），dense 1024 + sparse lexical_weights。

### 為什麼

1. **中文 SOTA**：BGE-M3 是中文 retrieval 公開排行榜頂尖
2. **dense + sparse 一氣呵成**：單一模型同時產生兩種 vector。其他 model（OpenAI、Cohere）只給 dense，sparse 要另外接 BM25 或 SPLADE，多一層複雜度
3. **離線可用**：不依賴外部 API、不算 token cost、無 rate limit
4. **OCS 是中英混合術語**（職務名稱中文、Knowledge / Skill 名稱可能含英文工具如 SQL、Python）。BGE-M3 對混語料表現好
5. **開源**：MIT-like license，無 vendor lock-in

### 考慮過的替代方案

| Provider | 為何不採 v1 |
|---|---|
| OpenAI text-embedding-3-large | 雲端依賴、無 sparse、$$$、政策不明 |
| Voyage AI | 雲端依賴、中文不確定 |
| Cohere | 雲端依賴 |
| Sentence-Transformers paraphrase-multilingual | 老 model，比 BGE-M3 弱 |
| FastEmbed | Qdrant 生態整合好，但中文表現未知 |

### 何時重新評估

- BGE-M4 / M5 出來且實測勝過 M3
- 客戶有明確 data sovereignty 要求改用 OpenAI（會強制換 collection）
- 跑全量發現 retrieval 品質不滿意（觸發 A/B 測試）

### 對使用者體驗的影響

retrieval 品質直接影響「候選 OCS 是否準」、「使用者描述能否命中對應 block」。BGE-M3 在 fixture smoke test 上 dense 0.7+ / sparse 0.25+，質感不錯。

---

## D-4: hybrid (dense + sparse RRF) 是 query 預設

### 背景 / 觸發
有了 dense + sparse 兩條 vector，consumer 怎麼用？

### 決策
- `smoke-query` 只 dense（驗證用）
- `query` 預設 dense；`--hybrid` 開啟 dense + sparse RRF 融合
- 未來 consumer 應**預設 hybrid**

### 為什麼

1. **使用者描述混語料**：中文自然語言 + 英文工具 / 術語
   - 純 dense 可能漏精確術語（SQL Server 2022 + dbt）
   - 純 sparse 可能漏語意（「協助業務理解資料」找不到「需求訪談」）
   - 混 RRF 兩邊都不漏
2. **Qdrant 內建 RRF**：1.10+ 原生支援 fusion 查詢，不用自己實作 reciprocal rank
3. **單次查詢成本**：dense + sparse + RRF 約是純 dense 的 1.5x latency，但 recall 提升明顯

### 考慮過的替代方案

| 方案 | 為何不採預設 |
|---|---|
| 純 dense | 漏精確術語 |
| 純 sparse | 漏語意 |
| Hybrid 用 weighted sum 而非 RRF | 需要調權重，RRF 更 robust |
| Hybrid + cross-encoder rerank | rerank 是 consumer 端職責，不在 indexer |

### 何時重新評估

- 如果 sparse 不夠好（中文 BGE-M3 sparse 在中文工具術語上表現不彰），考慮 BM25 替代
- 如果 consumer 場景全是純語意搜尋（無術語），可降回 dense-only 節省 latency

### 對使用者體驗的影響

使用者描述自己工作時混工具與自然語言，hybrid 確保兩種命中模式都能用。Stage 1 候選排序更準。

---

## D-5: direct qdrant-client 而非 LlamaIndex / 其他 framework

### 背景 / 觸發
要不要用 LlamaIndex 的 IngestionPipeline 來組 reader → embedder → writer？

### 決策
**直接 qdrant-client + 自訂 ingestion pipeline**。不用 LlamaIndex / Haystack / LangChain。

### 為什麼

1. **chunk 邊界已決定**：我們是 schema-aware chunking，不需要 LlamaIndex 的 NodeParser
2. **payload schema 精準控制**：需要 named vectors / payload index / deterministic point id / source hash 等細節。framework 的抽象會擋路
3. **依賴最小化**：LlamaIndex 拉進來會額外帶 200+ dependencies，大部分用不到
4. **不需要 chat engine**：v1 沒有對話、沒有 agent。LlamaIndex 主要賣點對我們無用
5. **debug 友善**：自訂 pipeline 每一步看得到中間結果，framework 包一層後 debug 比較麻煩

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| LlamaIndex IngestionPipeline + QdrantVectorStore | abstraction 太多、payload 控制不夠細 |
| Haystack | 過於 search engine 導向，schema 控制有限 |
| LangChain | dependency 龐大，indexer 場景 overkill |
| 純手寫 + httpx | qdrant-client 已是好抽象，重寫一遍沒意義 |

### 何時重新評估

- 如果 future service 需要 chat engine + agent workflow，可考慮把 retrieval 部分搬上 LlamaIndex
- 但即使那時，indexer 本 repo 仍建議維持 direct client（職責分離）

### 對使用者體驗的影響

對 end user 透明。對開發者：debug 容易、依賴管理輕，但失去 framework 的 ecosystem（已建好的 reader / writer）。我們的 ecosystem 需求很小，影響不大。

---

## D-6: 完整 JSON 不塞 payload，只存相對路徑 + hash

### 背景 / 觸發
每個 chunk 應該存多少原始 JSON 資料進 Qdrant payload？

### 決策
- payload 只存「該 chunk 相關欄位」+ source trace（`source_root_alias` / `source_file` / `source_json_hash`）
- 完整 JSON 留在原檔，consumer 需要時用 `source_file` 讀回去

### 為什麼

1. **payload 大小可控**：完整 JSON 平均 ~50KB / 份，乘 908 份 = 45MB。雖然 Qdrant 撐得住但完全不必
2. **避免重複資料**：profile chunk 已含 OCS-wide 資訊，block 不應再重複整份 JSON
3. **變更追溯**：source_json_hash 可驗證 consumer 端讀到的 JSON 是 indexer 時的版本
4. **權責分離**：consumer 可以按需 load full JSON 組 LLM context，indexer 不該預判 consumer 想要什麼粒度

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 完整 JSON 塞每個 chunk payload | 大量重複資料，違反 DRY |
| 只塞 profile chunk 完整 JSON | block 仍要回頭讀檔 |
| 完全不存 source_file | consumer 沒法回原始資料補背景 |

### 何時重新評估

- 如果 consumer service 部署在跟 indexer 不同的環境，沒法存取 source_file，要考慮把 essential context 塞進 payload
- 如果 OCS JSON 規模膨脹到單份 >500KB，要重新檢視

### 對使用者體驗的影響

對 end user 透明。Future consumer 需要組 LLM context 時多一次 file I/O，但 OCS JSON 都在 SSD 上，影響可忽略。

---

## D-7: deterministic point id (uuid5 of chunk_key)

### 背景 / 觸發
Qdrant point id 怎麼生？

### 決策
`point_id = uuid5(NAMESPACE_UUID, chunk_key)`，其中 `chunk_key` 是邏輯 ID（如 `ocs:SMS2512-002v1:unit:T1`）。

### 為什麼

1. **idempotent upsert**：同一個 chunk 重跑 indexer 會產生同一個 id，覆寫舊資料而不是建新 point
2. **無 collision 風險**（在 namespace 內）：uuid5 是 SHA-1 hash-based
3. **跨工具友善**：UUID 是通用 ID format，consumer SDK / Qdrant CLI / Postman 都好用
4. **debug 容易**：知道 chunk_key 可立刻算 point_id 直接 retrieve

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 自增 int id | 不 idempotent，重跑會新增不覆寫 |
| Random UUIDv4 | 同上 |
| chunk_key 當 id | Qdrant 允許 string id 但部分 UI / SDK 對 UUID 較好 |
| MD5 / SHA hash | 比 UUID 更短但失去 namespace 概念 |

### 何時重新評估

- chunk_key 規則大改且需要保持 backward compatibility（不太會發生）
- 切換到非 Qdrant DB 且新 DB 對 ID 格式有特殊要求

### 對使用者體驗的影響

對 end user 透明。對 indexer operator：rebuild / incremental update 行為穩定可預測。

---

## D-8: LLM 當顧問而非一次性生成器

### 背景 / 觸發
最終 JD 怎麼產出？

### 決策
**LLM 多輪訪談**（顧問模式）：
1. 看到使用者粗描述
2. 給結構化選單讓使用者勾範圍
3. 對勾選項目細問
4. 主動 probe gap
5. 不斷迭代直到資訊夠了
6. 才產出 JD 草稿

### 為什麼

1. **一般人不會寫 JD**：HR、創業者、轉職者不熟「主要工作職責」、「核心技能」這種格式
2. **一次性生成的 4 大問題**：
   - 使用者沒法驗證每一條（事實 grounding 弱）
   - LLM 容易把使用者沒做的事寫進去
   - 掌控感低，使用者覺得 AI 寫的不可信
   - 不可迭代，要改就整段重生
3. **OCS 給 LLM 充足訪談素材**：每個 K/S/A/O/P 都可以變一道問題（「你用 SQL 嗎？」「你會寫需求訪談紀錄嗎？」）
4. **使用者主導事實，LLM 主導文字**：分工讓兩邊都做擅長的事

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 一次性生成 | 失控、幻覺、不可驗證 |
| 純表格填空 UI | 太呆板，無 follow-up，使用者寫不出細節 |
| 預先寫好 100 個問題依序問 | 不適應使用者狀況、太機械 |
| 使用者完全自己寫 | 違反產品價值（就是要降低門檻）|

### 何時重新評估

- 如果發現使用者有「我想要快速產出，不要被問」的需求，可加快速模式
- 如果 LLM 對話品質不穩，可加 hand-written question banks 當 fallback

### 對使用者體驗的影響

訪談模式對「無經驗使用者」最友善（被引導著做完），但對「已有 JD 想優化」的使用者可能太冗長。可未來加 mode toggle。

---

## D-9: 顧問訪談前先給工作選單（先選範圍再對話）

### 背景 / 觸發
LLM 顧問怎麼決定要問什麼？如果直接 LLM 自己決定，會很慢（OCS 每份 20-40 個 block，逐項問會卡死）

### 決策
**兩階段顧問**：
1. **批次選單階段**：把所有可能 task / K / S / A 一次列出，使用者快速勾範圍
2. **針對性對話階段**：LLM 只對勾選的項目細問

### 為什麼

1. **節省對話成本**：勾選 30 個 task 用滑鼠 1 分鐘 vs LLM 一個個問 30 分鐘
2. **使用者掌控感**：先看全圖再選，不會被 LLM 牽著走
3. **明確的對話範圍**：LLM 知道使用者選了什麼，問題更聚焦
4. **指數降複雜度**：完整對話 = O(N) 個項目 × M 輪細節 → 改成 O(K) 勾選 + K × M 輪，K << N

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 純對話（LLM 一個個問） | 太慢 |
| 純選單（沒對話） | 細節補不足，JD 品質低 |
| 對話為主 + 偶爾選單 | 時序不清楚，使用者會搞混 |

### 何時重新評估

- 如果發現使用者在選單階段「亂勾」，要加引導
- 如果使用者跳過選單直接問，要 fallback 到對話模式

### 對使用者體驗的影響

「先選單再對話」是這個產品最關鍵的 UX 設計。對使用者來說：先快速圈出範圍 → 再深入聊 → 不會迷失。對 LLM 來說：訪談有明確 scope。

---

## D-10: indexer 提供 all_*_pairs 但不預生對話問題

### 背景 / 觸發
顧問訪談每個 block 問 5 個 follow-up，indexer 要不要預生這些問題塞 payload？

### 決策
**不預生**。indexer 提供結構化詞彙池（`k_pairs` / `s_pairs` / `all_k_pairs` 等），LLM 顧問**在 runtime 自行生成問題**。

### 為什麼

1. **LLM 創意 > 預生問題**：好顧問會看上下文（使用者前面說了什麼）調整問法。預生問題僵化
2. **維護負擔**：K-name 改了，預生問題就過時。對 908 份 OCS × 平均 9 block × 5 questions = 41K 個問題要維護
3. **責任邊界**：問問題是顧問（consumer）的事，不是 indexer 該管
4. **payload 大小**：預生問題會讓 payload 膨脹 5-10x，成本不划算

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 預生 follow-up question bank | 維護負擔、僵化 |
| 預生 question type 標籤（「問頻率」「問工具」） | 限制 LLM、值不大 |
| 完全不存任何問題提示 | 已經是現狀，是對的 |

### 何時重新評估

- 如果 LLM 顧問品質不夠好，且預生 question bank 能明顯提升，再評估
- 如果 indexer 用量增加到「冷啟動 LLM 太貴」，可考慮快取常見問題

### 對使用者體驗的影響

LLM 顧問問題會更自然、更貼上下文，但 indexer 對問題質量沒直接幫助 — 全靠 consumer 端的 prompt engineering。

---

## D-11: code-name 平行陣列改 pair structure（v2）

### 背景 / 觸發
v1 schema 把 K-codes 和 K-terms 拆成兩個平行 list，存在 silent misalignment 風險（見 BUG_LOG #2）。

### 決策
**v2 改 pair structure**：`k_pairs = [{"code": "K01", "name": "..."}, ...]`。
保留 `k_codes` parallel array 給 Qdrant payload index filter 用，但**從 pairs 反推**而不是獨立 build。

### 為什麼

1. **修正 silent bug**：filter 條件不一致導致 misalignment（v1 真實 bug）
2. **配對保證**：pair 內 code 與 name 同生共死，永遠對齊
3. **LLM 配對安全**：consumer 拿 `k_pairs[0]` 就有完整 code+name，不會配錯
4. **保留 filter 效能**：parallel `k_codes` 仍是 Qdrant indexed field，filter 一樣快

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 不改 schema，靠 invariant check | 沒解決根本問題 |
| 只存 pair，不存 codes | Qdrant payload index 對 list of object 支援差 |
| 用 dict（{"K01": "..."}） | 失去順序，且 JSON serialize 後就是 object list 等價 |

### 何時重新評估

- 如果 Qdrant 未來原生支援 list[object] 的 sub-field index，可移除 parallel arrays
- 如果發現 pair structure 增加的 storage 成本不可接受（目前估 +30% payload size）

### 對使用者體驗的影響

直接影響：避免最終 JD 出現「K01 機器學習概論」但實際上 K01 是「資料庫原理」這種錯配。Trust 提升。

---

## D-12: profile chunk 加「核心知識領域 / 核心技能」技能雲（v2）

### 背景 / 觸發
v1 fixture 測試發現：使用者粗描述包含工具名稱（SQL、Python、Power BI）時，profile-level retrieval 命中率不高。原因是 profile chunk 只含官方 job_description（短）+ unit titles，沒有 tool-level term。

### 決策
**v2 profile markdown 加技能雲段落**：彙整所有子 block 的 K-names 與 S-names，去重後寫進 profile chunk text。

### 為什麼

1. **stage 1 retrieval 命中率**：使用者粗描述帶工具名 → profile 層直接 hit 而非靠 block 反推
2. **無新依賴**：彙整本來就有的資料，沒額外計算成本
3. **embedding 容量足夠**：profile text 從 ~500 字增至 ~1500 字，BGE-M3 max_length 8192 容得下
4. **sparse vector 受益**：技能雲含大量短 term，sparse hit 明顯改善

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 不加，靠 block-level reverse lookup | 多一輪查詢，且 profile 排序錯 |
| 加但只放 codes | 排除真實 query 模式（使用者打名字不打代碼） |
| 加 HyDE-style 假設活動描述 | 需要 LLM 預生，違反 indexer 不依賴 LLM 原則 |

### 何時重新評估

- 如果 profile text 變太長導致 sparse vector 過度膨脹（>50KB / point），調整去重策略
- 如果發現技能雲反而讓 profile 在「找到對的職務」場景變差（不太可能），revert

### 對使用者體驗的影響

stage 1 候選 OCS 排序更準。使用者輸入「我會用 Python 跟 SQL」直接命中對應職務 top-5，不會排到第 10 名。

---

## D-13: 所有 chunk payload 都含完整 source trace

### 背景 / 觸發
JD 要支援引用 OCS 來源、要支援使用者編輯時回頭看原 OCS、要支援 indexer 重 sync 時判斷是否需要更新。

### 決策
每個 chunk payload 必含：
- `source_root_alias` ("jd-pdf-to-json")
- `source_file` ("output/0518/<filename>.json")  — 相對路徑
- `source_json_hash` — 整份 JSON 的 sha256
- `chunk_content_hash` — 該 chunk Markdown 的 sha256
- `source_path` — JSON pointer 風格的路徑
- `source_labels` — 原始 OCS 標籤

### 為什麼

1. **JD citation**：使用者要看「這個 K05 在 OCS 哪份哪頁」，indexer 不存 source 就斷鏈
2. **不存絕對路徑**：`S:/jd-pdf-to-json/...` 綁死 Windows + 單一 machine。改相對路徑（`output/0518/...`）+ alias，部署時用 env 指 root
3. **hash 雙層**：source_json_hash 判斷檔案層級變動，chunk_content_hash 判斷單一 chunk 是否需要重 embed
4. **future-proof 增量更新**：未來如果做更細的增量（不是整檔重做），chunk hash 是 cache key

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 不存 source 路徑 | 失去回溯能力 |
| 存絕對路徑 | 綁機器、部署痛 |
| 只存 file hash 不存 chunk hash | 沒法做 per-chunk cache |

### 何時重新評估

- 如果 source 從 file system 改成 S3 / object storage，alias 規則要更新
- 如果 chunk_content_hash 沒被 consumer 用，可考慮拿掉（目前留著）

### 對使用者體驗的影響

對 end user：JD 引用永遠能回溯到原 OCS PDF / JSON。對 operator：rebuild 時 manifest 機制可信，不怕重複處理。

---

## D-14: 自訂內容的代碼 / SKA 生成在 curator 端，indexer 只給詞彙池

### 背景 / 觸發
使用者新增「LLM 模型部署」這種 OCS 標準沒有的活動，要產生對應的 T/P/O/K/S/A 代碼。誰負責？

### 決策
**curator (LLM) 在 runtime 生成代碼**，**indexer 提供完整 OCS 詞彙池（`all_k_pairs` 等）**讓 curator 從中挑選或建議。

### 為什麼

1. **創作行為 ≠ 索引行為**：生成代碼是 LLM 創作，indexer 是靜態索引，責任不同
2. **必要素材已備齊**：indexer 提供 cross-OCS hybrid search（找最像的標準 block）+ 完整 K/S/A pool，curator 該有的都有了
3. **避免硬 coupling**：如果 indexer 預生代碼，每次 OCS 更新都要重做。runtime 生成可彈性
4. **OCS 是參考不是模板**：使用者的編號 ≠ OCS 編號（D-15 進一步說明）

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| indexer 自己跑 LLM 預生「下一個可用 T 號」 | 違反 indexer 不依賴 LLM 原則 |
| 用簡單規則生（取 max + 1） | OCS 不是 template，編號規則不適用 |
| 完全不允許自訂 | 違反產品需求 |

### 何時重新評估

- 如果 curator 端生代碼品質太差，可在 indexer 預生「常見 LLM 應用」、「資料工程」等領域的 stock 代碼供參考
- 但這應該是 consumer 端 LLM prompt 工程的事，不是 indexer 改 schema

### 對使用者體驗的影響

自訂活動有完整代碼追溯（不是「自訂」二字了事），JD 品質與正式 OCS 內容看起來一致。

---

## D-15: OCS = 參考不是模板（v2 概念修正）

### 背景 / 觸發
初期設計把 OCS 當「填空模板」（使用者填 80%、改 20%）。實際做下去發現：

- 同職位 A 公司跟 B 公司可能差 60%（不是 20%）
- 沿用 OCS 編號（T1.1, T1.2）對使用者的 JD 反而不適合
- 使用者可能參考多份 OCS（「我半個資料分析師 + 半個 LLM 工程師」）

### 決策
**OCS = 詞彙庫 + 結構樣本**，**最終 JD 編號 JD-local**（這份 JD 自己的 T1, T2, T3），不沿用 OCS 編號。OCS 在 JD 裡只作為「參考來源」標註。

### 為什麼

1. **誠實**：JD 內容跟 OCS 90% 不同卻沿用編號是錯誤
2. **支援多參考**：Stage 1 可複選多份 OCS，沿用編號會衝突（兩份 OCS 都有 T1）
3. **支援自訂**：使用者新增的活動本來就不在 OCS 編號池內
4. **JD 自成完整文件**：讀者看 JD 不需要知道 OCS 規則就能看懂

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 沿用 OCS 編號 | 多 OCS 衝突、自訂編號無依據 |
| 用 hash / UUID 當代碼 | 對人類不可讀 |
| 不給代碼，純自然語言 | 失去結構化優勢 |

### 何時重新評估

- 如果使用者反饋「看不懂 T1/T2，建議用 OCS 原編號」（不太可能 — 不熟 OCS 的人本來就看不懂 T-code）
- 如果有產業要求 JD 必須對應 OCS 原編號（會強制 revert）

### 對使用者體驗的影響

JD 看起來像獨立、完整、為使用者客製的文件，而不是「OCS 抄寫本」。引用 OCS 是「參考來源」而非「填空模板」。

### 對 indexer schema 的影響

省掉了原本 v2 規劃的「`task_codes_used` / `indicator_codes_used` / `output_codes_used`」這幾個欄位 — 不需要追下個可用編號，因為 JD 不用 OCS 編號。v2 schema 因此更精簡。

---

## D-16: openresty body size 由使用者修，不採 gzip workaround

### 背景 / 觸發
雲端 Qdrant 反向代理擋住 BGE-M3 dense vector upsert（BUG_LOG #4）。三個解法可選。

### 決策
**請使用者調 openresty `client_max_body_size`**，不採 indexer 端 gzip + batch=1 workaround。

### 為什麼

1. **gzip workaround 是慢且脆弱**：batch=1 意味著 12,869 chunks 要 12,869 個 HTTP request。網路 round-trip 主導時間
2. **問題是部署環境，該在部署端修**：indexer 程式碼乾淨清晰，不該為了反向代理限制變形
3. **長期維護**：如果其他 service（不只 indexer）也要傳大 vector，body size 限制終究要解
4. **權限可及**：使用者有 LXC + NPM admin 權限，改 nginx config 不困難

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| gzip + batch=1 workaround | 慢、脆弱、indexer 程式碼複雜化 |
| 全部換本機 Qdrant | 改部署架構，副作用大 |
| 縮短 dense vector 維度 | BGE-M3 預設 1024，降維會傷品質 |
| 不存 dense，只存 sparse | 失去語意 retrieval 能力 |

### 何時重新評估

- 如果未來 dense 模型出來維度暴增（BGE-M5 用 4096 維），body size 又會吃緊
- 如果有 customer 部署環境完全不能改反向代理，indexer 要 fallback 到 streaming upsert

### 對使用者體驗的影響

部署成本一次性增加（改 nginx），之後 indexer 跑得乾淨。使用者輸入查詢的速度不受影響。

---

## D-17: 不用 pytest 測試框架，改 lightweight verify scripts

### 背景 / 觸發
v2 schema 改動需要驗證。是要建 pytest 框架還是簡單 verify script？

### 決策
**用 lightweight verify scripts**（`scripts/verify_v2_*.py`），不建 pytest 框架。

### 為什麼

1. **規模太小**：本 repo 程式碼約 1500 行，pytest setup + fixtures + assertion 框架對這規模 overkill
2. **驗證需求集中**：主要要驗證的是「schema 改完 fixture render 出來符合預期」，這是 script 就能做
3. **debug 友善**：script 出錯直接 print，不用懂 pytest 的 conftest / parametrize / mark
4. **避免框架債**：pytest 框架要維護、要升版、要學新語法。對單人 / 小團隊太重
5. **可以漸進加 pytest**：未來如果 indexer 規模翻倍，再評估

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| pytest 完整框架 | 對 1500 行 repo 過重 |
| unittest stdlib | 樣板代碼多 |
| doctest | 不適合多檔測試 |
| 完全不寫驗證 | schema 改動風險高 |

### 何時重新評估

- 程式碼超過 3000 行
- 需要 CI / GitHub Actions（pytest 在 CI 表現比 script 好）
- 有第二個開發者加入（pytest 提供統一規範）

### 對使用者體驗的影響

無直接影響。對開發者體驗：簡單但有效，未來要升級 pytest 也不會痛。

---

## D-18: schema_version 字串而非數字

### 背景 / 觸發
v2 升級時要怎麼標版本？

### 決策
用字串 `"ocs-index-v1"` / `"ocs-index-v2"`，不用 int。

### 為什麼

1. **可讀**：人眼看 payload 知道哪個 schema
2. **未來空間**：可以有 `"ocs-index-v1.1"`, `"ocs-index-v2-experimental"` 等
3. **filter 一致**：跟 `embedding_provider`, `chunk_level` 都是 keyword filter，同 type

### 對使用者體驗的影響

無直接影響。對 future audit / debug 易讀。

---

## D-19: 4 份設計文件不 commit（thesis 專用）

### 背景 / 觸發
使用者要求把設計討論 / bug log / 流程 / 決策寫到 docs/ 供專題報告用，但「這部分不用 git」。

### 決策
- `USER_FLOW.md` / `V2_PLAN.md` / `BUG_LOG.md` / `DESIGN_DECISIONS.md` 寫在 `docs/` 下但 gitignore（或顯式不 commit）
- 同 `docs/` 內既有的 `SCHEMA.md` / `CHUNKING.md` / `INGESTION.md` 等正式 spec 文件仍 commit
- 兩種文件用「是否 commit」區分

### 為什麼

1. **使用者明確指示**：「這部分不用 git」是直接要求
2. **內容性質不同**：4 份新 docs 含開發過程的反思、bug 學習、設計掙扎，是 thesis 素材，不是 production spec
3. **公開 repo 衛生**：bug log 含開發過程的試錯紀錄，不適合放在公開 commit history
4. **可以彈性變更**：thesis 寫完後使用者可重新評估要不要 commit

### 考慮過的替代方案

| 方案 | 為何不採 |
|---|---|
| 全 commit | 違反使用者指示 |
| 全放 `docs/notes/` 目錄 | 顯式 gitignore 該目錄，現在新 4 份還是放 `docs/` 直接層級保持顯眼 |
| 放 repo 外（私人筆記） | 失去跟程式碼的緊密連結，未來工程師讀不到 |

### 何時重新評估

- thesis 結束後是否要清理掉這 4 份（保留學習價值或刪除）
- 是否要把部分內容（如 D-8 顧問流程設計）提煉到 README 或正式 spec

### 對使用者體驗的影響

無 end user 影響。對 operator：repo 內 docs 多兩類（commit / 不 commit），需明確標記避免混淆。

---

## 統計總覽

| 決策類別 | 數量 |
|---|---|
| 架構 / 部署 (D-1, D-5, D-6, D-13, D-16, D-17) | 6 |
| 模型 / 演算法 (D-3, D-4, D-12) | 3 |
| Schema / 資料結構 (D-2, D-7, D-11, D-18) | 4 |
| Workflow / 產品 (D-8, D-9, D-10, D-14, D-15) | 5 |
| 文件 / 治理 (D-19) | 1 |
| **Total** | **19** |

---

## 對專題報告的可引用觀察

1. **小團隊 / 小規模 repo 該避開的 over-engineering**：D-5 (no LlamaIndex)、D-17 (no pytest)
2. **資料設計的「沉默 bug」是高風險區**：D-7 (deterministic id 防止重複)、D-11 (pair structure 防 misalignment)
3. **產品價值與技術設計緊密相連**：D-8 / D-9 / D-15 都是「先想清楚產品流程才設計 schema」
4. **抽象不夠 / 不足都是反模式**：D-1 (適度 abstraction 分 repo) vs D-5 (避免不必要 framework)
5. **責任邊界要清楚**：D-10 / D-14 / D-15 都在處理 indexer vs curator / consumer 的職責切分
