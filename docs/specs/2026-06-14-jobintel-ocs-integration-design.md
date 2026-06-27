# jobintel-ai × jd-ocs-indexer 整合設計

> OCS 知識服務 + 完整度導向的訪談流程
> 狀態：設計定稿，待拆 per-repo 實作計畫。
> 關聯：[jd-ocs-indexer USER_FLOW.md]、jd-ocs-indexer 查詢 API（`/search` `/task-pool` `/profile/{ocs_code}/pairs`）。

---

## 1. 背景與目標

**目標**：產出**滿分（完整、可追溯）的職務說明書**，同時**控制訪談時長**。

兩個現況問題：
1. **兩套平行 iCAP/OCS RAG**：jobintel-ai 自己一套（OpenAI 1536d → pgvector，`icap_retriever` 6 函式）；jd-ocs-indexer 另一套（BGE-M3 dense+sparse → Qdrant + 查詢 API）。索引同一份 iCAP 資料、重複維護。
2. **缺廣度完整度機制**：目前只有逐任務深度（indicator 7 維 quality_score），沒有「對標準比對、確保該有的任務/K/S/A 都覆蓋」的廣度機制。30–45 分鐘的純自由訪談有疲勞流失風險（研究：問卷超過 7–8 分鐘棄答率急升）。

**核心主張**：把 jd-ocs-indexer 當**單一 OCS 知識服務 + 完整度標尺**，jobintel-ai 退役自己的 pgvector RAG、改當純消費端；OCS 永遠是**參考與完整度標準，不是模板**；bottom-up 深度訪談的核心不變。

---

## 2. 角色分工（方案 A：完全統一檢索後端）

```
jd-ocs-indexer  =  官方 iCAP/OCS「標準知識服務」（檢索後端）
   擁有：ingest 標準、embedding、Qdrant、結構化檢索 + reranker
   端點：/search、/task-pool、/profile/{ocs_code}/pairs、/healthz、/stats
   → 單一真相：「官方標準怎麼說」+「該有什麼」（完整度標尺）

jobintel-ai     =  產品／應用（工作者實況 + 顧問 + 產出）
   擁有：訪談流程、任務萃取、STAR/5W2H、行為指標、OCS 文件組裝、
        evidence、完整度追蹤、前端、匯出
   → 消費上面的 API，不再維護任何 iCAP 索引（退役 icap_parser/ingest/retriever）
```

決策依據：2025–26 主流 RAG 正走向「把檢索解耦成 context engine / 服務層」（Search vs Retrieve 分離、multi-granularity chunk）。jd-ocs-indexer 的三層 chunk（profile/unit/block）+ pairs 正是這個 pattern。

---

## 3. 重新對齊後的訪談流程

**骨架不重寫**，是「4 個節點換後端 + 2 個新 stage + 完整度 UI」。bottom-up 的 `STAR→5W2H→indicator` 逐任務迴圈完全不動。

```
icap_rag          ← 換後端：/search level=profile&hybrid（+rerank），信心 gateway 重調
   │
   ▼
★ scoping（前置） ← 新增：/task-pool 拉「該 OCS 完整任務清單」→ 使用者勾選 + 加自訂
   │                = 廣度 gap 的前置實現（看過每個標準任務，不漏）
   ▼
interview         ← 改寫（降級）：對「勾選任務」做深度追問 + 捕捉自訂任務；
   │                注入 task-pool 讓 LLM 問得準。不再是冷啟動自由摸索
   ▼
task_extraction   ← 小改：併入 scoping 勾選的任務（seed）
   │
   ▼
responsibility_grouping   ← 不變
   │
   ▼
逐任務 [STAR → 5W2H → indicator]   ← 核心不變
   │   （5W2H 的 iCAP 參考提示來源換成 jd-ocs-indexer /search level=block）
   ▼
★ K/S/A 廣度 sweep ← 新增（輕量）：對勾選任務的 /pairs 預期 K/S/A，檢查訪談有沒有覆蓋
   │
   ▼
ocs_builder       ← 改寫：K/S/A→引用用 /pairs + LLM 名稱比對；自訂任務走全庫 /search
   │
   ▼
preview           ← 加完整度儀表（深度 quality_score + 廣度覆蓋%）
```

### 節點改動分類

| 節點 | 改動 | 內容 |
|---|---|---|
| `icap_rag` | 🔧 換後端 | `/search profile+hybrid+rerank`；信心 gateway 重調 |
| **scoping** | ➕ 新增 | `/task-pool` 任務清單勾選 + 自訂（前置廣度 gap） |
| `interview` | 🔧 改寫/降級 | 深度追問 + 自訂捕捉；注入 task-pool |
| `task_extraction` | ◽ 小改 | 併入勾選任務 |
| `responsibility_grouping` | ✅ 不變 | |
| `STAR→5W2H→indicator` 迴圈 | ✅ 核心不變 | 僅 5W2H 參考來源換 |
| **K/S/A 廣度 sweep** | ➕ 新增 | 對 `/pairs` 預期 K/S/A 檢查覆蓋 |
| `ocs_builder` | 🔧 改寫 | 引用改 `/pairs`+LLM 名稱比對；自訂走全庫 `/search` |
| `preview` | ◽ 小改 | 完整度儀表 |

### gap detection 拆兩軸（前置決策）

- **任務廣度** → **前置**到 scoping（看過每個標準任務、勾或不勾）。最省時、廣度保證、可量化。
- **K/S/A 廣度** → 自然落在逐任務迴圈之後（要先有任務內容才能比 K/S/A 覆蓋）。

> anchoring 風險控制：scoping 勾選只決定**廣度（要不要納入此任務）**；**深度內容永遠由 STAR/5W2H 從工作者口中萃取**。勾 ≠ 完成，每個勾的任務仍要講出「你實際怎麼做」。menu 定廣度、訪談定深度。

---

## 4. 完整度模型（「滿分」的操作型定義）

「滿分」= 兩軸都滿：

| 軸 | 定義 | 量測 | 來源 |
|---|---|---|---|
| **深度** | 每個任務含情境/目的/協作/工具/步驟/產出/品質時效 | indicator **7 維 quality_score**（已有） | STAR/5W2H |
| **廣度** | 該職務「該有」的任務/K/S/A/產出都被涵蓋或明確排除 | **覆蓋率 %**（新增） | `/task-pool` + `/pairs` |

> 覆蓋率 = (已納入 + 已明確排除的標準任務) / 標準任務總數；K/S/A 覆蓋率 = (訪談已觸及的預期 K/S/A) / (勾選任務的 `/pairs` 預期 K/S/A)。

**完整度儀表（preview + 訪談中）**：顯示「範圍內 N 個任務、已深入 X 個、深度滿分 Y 個」+「標準任務覆蓋 / K/S/A 覆蓋 %」。作用：
- 給滿分動力（看得到離滿分多遠）。
- 給控時長的心理錨（「今天補完這 3 個缺口就好」）。

**完成 gate（preview 進入條件）**：所有「範圍內」任務深度過關 **且** 廣度缺口都已解決（補上或明確標記「不適用」）；或使用者明確接受「夠了」（force complete，標記未滿分項）。

---

## 5. 引用 / 代碼對應（OCS-local 代碼的正確處理）

**關鍵事實**：iCAP 代碼是 **OCS-local**——同一個 `S01` 在不同 OCS 是不同東西、名字不同。有意義的單位是 `(OCS, 名稱)`，不是裸代碼。這正是 jd-ocs-indexer 存 **code-name pair** 的原因。

含意：
- 最終 JD 用**自己的編號**（不沿用 OCS 代碼）。
- ocs_builder 的「代碼對應」= **附參考引用**（「此能力參考 OCS-X 的 `Sn（名稱Y）`」），是出處/可信度，不是指派全域 ID。
- 系統任何地方**不得拿裸代碼當身份**——一律帶 `(ocs_code, code, name)` 三元組。

**引用機制**：

| 情況 | 做法 |
|---|---|
| 選定 OCS 內的 K/S/A 引用 | `/pairs`（1–3 份選定 OCS，~50–150 條帶名稱項）+ LLM 名稱比對挑最近一條或「自訂/無對應」 |
| **自訂任務**（公版沒有的工作） | **全庫 `/search level=block`（不限 ocs_code）** 找最像的 3–5 個 block → 該 block 自帶 k/s/output pairs 當引用 |

> 自訂任務的全庫檢索靠**既有的 block 層級 `/search`**，命中 block 帶 pairs，引用跟著來——**不需要 R2**。

**R2（全庫 K/S/A 名稱獨立 embed + 語意檢索）= backlog**：只有「技能脫離任何可比對任務、要單獨全庫搜 K/S/A 名稱」才需要；iCAP 的 K/S/A 掛在 block 底下，此情況罕見。目前不做。

---

## 6. 檢索品質：加 reranker

主流 production 預設是 **hybrid（dense+sparse RRF）+ cross-encoder reranker**（recall +~26% / precision +~28%）。jd-ocs-indexer 現在只有 hybrid、**缺 reranker**。

- 加 **`bge-reranker-v2-m3`**（BGE 家族、已在用 FlagEmbedding，self-host 零摩擦）。
- 接在 `/search` 的 hybrid 之後重排候選；候選職務、task 比對都會變準。
- **不做 GraphRAG / agentic RAG**：研究明示對簡單 lookup 是浪費、貴 3–10×。我們的查詢是直接檢索，hybrid+rerank 就是對的高度。

---

## 7. 時長 / UX（控時長 = bottom-up 能活的前提）

研究：對話式優於表單（completion +~40%、richer、less fatigue），但**前提是短、自適應**；**超過 7–8 分鐘棄答率急升**。jobintel-ai 目標 30–45 分鐘 → 必須主動降負擔，否則深度設計的價值被棄答吃掉。

三條腿（皆為合併流程的副產品）：
1. **問更少更準**：scoping 前置 + task-pool 注入 → 只深入勾的、只問缺的（呼應「3 題追問 > 12 題盲問」）。
2. **可恢復多 session**：graph_state 已持久化（技術已具備）→ **明確設計成「隨時可停、下次接續」**：進度可見、自然 checkpoint（每任務/每主要職責一段，每段落在 7–8 分鐘內）、dashboard 一鍵續做、（可選）提醒回來。
3. **完整度儀表**當心理錨：知道離滿分多遠、可分段收尾。

---

## 8. 遷移順序（每步可獨立 ship）

1. **確認資料源同一份**：jobintel-ai 的 iCAP 來源 == jd-ocs-indexer 的 jd-pdf-to-json 輸出？（前提）
2. **jd-ocs-indexer 加 reranker**（`/search` 接 bge-reranker-v2-m3）。
3. **信心 gateway 重調**：BGE-M3+rerank 分數 ≠ OpenAI cosine；候選信心改用**可閾值化的分數**（如 dense cosine 或 reranker 分數——RRF 融合分數是排名分、不適合當絕對閾值）重定 high/medium 門檻。
4. **換 icap_rag** → `/search level=profile`。
5. **加 scoping 前置 stage**（`/task-pool` 任務勾選 + 自訂）；`interview` 降級為深度追問 + 注入 task-pool。
6. **換 5W2H 參考提示 + ocs_builder 引用**（`/pairs`+LLM 比對；自訂走全庫 `/search`）。
7. **加 K/S/A 廣度 sweep + 完整度儀表 + 完成 gate**。
8. **加可恢復多 session UX**（checkpoint、進度、續做）。
9. **退役 pgvector**：刪 icap_parser/ingest/retriever，jobintel-ai 不再自建索引。

---

## 9. 工作分解（跨兩 repo）

**jd-ocs-indexer（小、獨立）**
- 加 `bge-reranker-v2-m3` 到 `/search`（可加 `rerank: bool` 參數）。
- 跨服務存取：API 目前 localhost/無 auth，需開放網路 + 用 `create_app` 擴充點加 API key。
- （backlog）R2：K/S/A 名稱獨立 chunk + 檢索端點。

**jobintel-ai（主體、建議分階段）**
- 後端換接（icap_rag、5W2H hints、ocs_builder 引用）+ 退役 pgvector。
- 新 stage：scoping（前置任務選單）、K/S/A 廣度 sweep。
- 完整度模型 + 儀表 + 完成 gate。
- 可恢復多 session UX。

→ 兩個獨立的 implementation plan（jd-ocs-indexer reranker 可先做，不阻塞 jobintel-ai）。

---

## 10. 風險

- **跨服務執行期依賴**：jobintel-ai 依賴 jd-ocs-indexer API 在線；要 auth + 部署協調。
- **embedding 過渡期共存**：遷移中舊 OpenAI 向量與新 BGE-M3 檢索並存，要管好切換點。
- **anchoring**：scoping 選單可能讓人照勾——靠「optional、勾你真的做的、深度仍 bottom-up」三重緩解。
- **資料源不一致**：若兩邊 iCAP 來源/版本不同，統一前需先對齊（步驟 1）。

---

## 11. 研究依據（2025–26）

- **bottom-up LLM 訪談**有效：LLMREI（LLM 訪談錯誤數 ≈ 人類）、LAAC（結構化 + 不確定性 metadata）。
- **RAG 驅動提問** = JudgeAgent「Agent-as-Interviewer」呼叫知識工具生成更好問題（= 注入 task-pool）。
- **檢索**：hybrid + reranker 為主流預設；Qdrant 原生支援 hybrid；GraphRAG/agentic 對 lookup 是浪費。
- **架構**：2025 RAG 走向「context engine / 檢索服務層」、multi-granularity（Search vs Retrieve 分離）。
- **taxonomy 對應**：ESCO/O*NET 用「抽取→檢索候選→LLM rerank」；但 iCAP 是 OCS-local，故簡化為「選定 OCS 的 /pairs + 名稱比對」。
- **UX**：對話式 completion 高但 7–8 分鐘疲勞懸崖；自適應問卷（AURA）只問該問的。

---

## 12. 範圍外 / backlog

- **R2**（全庫 K/S/A 語意檢索）。
- **AURA 式 RL 自適應**問題選擇。
- **evaluation 集**（檢索命中率 / 任務萃取 / 行為指標品質；RAGAS 精神；jobintel-ai roadmap #28）。
- 多職務比較、部門職責地圖等 jobintel-ai 既有 roadmap P2。
