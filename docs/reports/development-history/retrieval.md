# 檢索與參考資料演進材料

回到[演進總覽](README.md)。這條線從 JobIntel 的 iCAP 檢索與獨立 indexer 開始，不從近期 Memory 當作起點。以下是既有原件的索引與簡述，不是重新選型；相似度、排序、事實依據是三種不同問題。

## 2026-05：最初的檢索與知識服務

### 05-20 至 05-26：pgvector 檢索接到固定訪談流程

早期 JobIntel 以 OpenAI embedding＋pgvector 取得 iCAP 參考，按信心程度分 reference／hybrid／company-defined 路線，再進訪談。5/26 的 matcher 又將任務、產出、工具及工作情境納入；不只是用職稱搜尋。

**引用：**[初始架構 §2–§4](../../archive/early-projects/2026-05-20-jobintel-architecture.md)、[初始 Graph](../../archive/early-projects/2026-05-20-jobintel-graph-pipeline.md)。程式線索：`git show 699f53a6383b9786485f4377509542e0164cfca7 -- backend/app/services/icap_matcher.py`。這些說明最初機制，沒有證明信心分數已校準成準確率。

### 05-26 至 05-27：另建 BGE-M3／Qdrant indexer

獨立 indexer 依 OCS 結構建立 profile／unit／block，不直接把全文切成固定 token 塊。選 BGE-M3 同時提供 dense／sparse，Qdrant 承接索引；dense 是初版預設，hybrid/RRF 是另一條可選路徑。此時 JobIntel 與 indexer 尚有兩套檢索，不是整體一開始就統一。

**引用：**[早期設計決策 D2–D5](../../../apps/ocs-indexer/docs/DESIGN_DECISIONS.md)。精確歷史原件：`73321973125a2147e32b0d56d501387b4670f19b:docs/ARCHITECTURE.md`、`68426cc1df7dc65aad747d63b16a296285e546ed:README.md`（以 `git show <提交>:<路徑>` 讀取）。初版 README 記錄三份 fixture／66 points、重跑跳過及 filter probe；這是索引功能驗證，不是全語料檢索品質評測。

## 2026-06：先碰到資料與粒度問題，再統一服務

### 06-12 至 06-13：少量 fixture 通過，擴大後才發現遺漏

第一類問題是 chunk key 碰撞：預期 48 點只留下 36 點，修正區塊定位後恢復。另一類是搜尋「SQL／Python」效果不佳，因 profile 可供 embedding 的文字未充分涵蓋 K/S，於是研究並補 skill cloud。這些不能只靠換向量庫解決。

全量 908 份資料又暴露 upsert timeout；當時縮小 batch、延長 timeout 並重試後，記錄一次約 5.4 小時、零失敗的 rebuild。但完成後再對帳，12,869 個輸入 chunks 只留下 12,810 點：四組來源 OCS code 重複造成覆寫。原紀錄將這列為上游資料品質問題，**沒有宣稱已修復**。

**引用：**[BUG_LOG：Bug 1、7、8](../../../apps/ocs-indexer/docs/BUG_LOG.md)、[設計決策 D12](../../../apps/ocs-indexer/docs/DESIGN_DECISIONS.md)。這段適合沿「觀察數量不符 → 對帳 → 查來源 → 區分 owner」追查。Bug 2 的平行陣列錯配另含潛在風險分析，不能把所有推測都算成實際事故。

### 06-14 至 06-30：搜尋粒度改了兩次，known-key 讀取不再走向量

v3 紀錄保留了兩次反轉：先想砍 unit，發現會漏沒有 block 的任務；補完整任務後，又發現真正被搜尋／選擇的是 task，最後從 profile／unit／block 改為 **profile＋task**。K/S 與活動句的聚合也跟著調整。

同時退役 JobIntel 自有 pgvector RAG，由 indexer 統一提供知識服務；已知 OCS 的任務樹、K/S 池走精確查詢，未知職務或改寫任務才需要語意搜尋。這是資料粒度、存取方式與維護責任的共同修改，不等於實驗證明 Qdrant 全面優於 PostgreSQL。

**引用：**[v3 決策 A1–A2、B2、B4、C、E4](../../../apps/ocs-indexer/docs/specs/2026-06-14-v3-decision-log.md)、[ADR0014](../../adr/0014-db-image-stock-postgres.md)。6/14 曾規劃 [reranker](../../../apps/ocs-indexer/docs/plans/2026-06-14-search-reranker.md)，後因局部 top-1 觀察與人工選擇流程而延後；沒有完整標注 query set，不能把當時的索引點數當成測試題數。

### 06-29：Windows 本機 embedding 崩潰，轉為服務邊界

BGE-M3 在 CLI 可運作，但 Windows API 環境出現 OpenMP／重複載入等崩潰，甚至多個依賴版本仍無法穩定服務。研究比較 TEI、Infinity、Triton 等，選擇 Linux GPU 容器中的 embedding service，以 HTTP 保留 BGE dense／sparse 能力。

**引用：**[事故與替代方案研究](../../research/retrieval/2026-06-29-embedder-service-bge-m3-research.md) §2–§5、[ADR0012](../../adr/0012-embedding-as-a-service.md)。這是部署／依賴問題的處理，不是搜尋品質提升證明；研究中的驗收條件也不全等於已保存的實測結果。

## 2026-07：真的相似，不等於可以合併

### 07-02：相似分數無法直接判斷「是不是同一工作」

多職類合併研究發現，**同一任務在不同版本的改寫，分數約 0.806；另一組不同任務，反而約 0.820**。軟體職類的三組配對有大量灰區；態度的同義／同文情況又不同。相似與等價的分數範圍重疊，不能找一個通用 threshold 就自動合併所有內容。

**引用：**[多 OCS 去重研究 §5、§5.1](../../research/retrieval/2026-07-02-multi-ocs-candidate-dedup-research.md)。原件有實際配對、分數及任務／態度差別，可作「為什麼要找其他方法」的材料；不是所有向量檢索都無效。

### 07-04：試 reranker 有改善，也留下錯誤高分

同一研究再用 20 對人工判讀配對測 BGE reranker：部分不同任務的分數明顯下降，四組真重複得到高分；但「製程品質巡檢」與「製程品質控管」仍得到約 **0.988** 的錯誤高分。因此選擇把它當灰區排序／過濾候選，而非最終等價判官，初版也沒有因此立即部署。

**引用：**[reranker 實測與裁決 §9.2](../../research/retrieval/2026-07-02-multi-ocs-candidate-dedup-research.md)、[ADR0022](../../adr/0022-similarity-matching-items-match.md)。目前入口是保存的結果表；本次未找到文中所有 scratchpad 原始程式與獨立執行 log，不宣稱可原樣重跑整次試驗。

### 07-04：按資料類型校準，仍未解決的先不開放

後續 task 灰區下限從 0.7 改到 0.8，三組比較的灰區縮為約 1–3；但 skills 仍有 67–145 對灰區與可疑合併，unit matching 則尚未接線。當時因此暫緩 K/S 的相似合併呈現，而不是把「程式能算分數」當成可用。

**引用：**[校準結果與未決項](../../specs/2026-07-04-similarity-matching-calibration.md)、[前一份研究 §9.6](../../research/retrieval/2026-07-02-multi-ocs-candidate-dedup-research.md)。不同輪次有不同 exact-collapse 數字，使用時需連同該次輸入與設定引用，不能拼成同一輪成果。

### 07-12 至 07-13：拓寬研究，但不把外部 benchmark 當成本專案結果

接著研究 Qwen3 embedding／reranker、contextual retrieval、HyDE、GraphRAG、late interaction 等，也重看 O*NET／ESCO／iCAP 對任務與職能的表示。原研究主張先建立自己的查詢、標準答案與比較條件；並非全部方法都值得導入。

**引用：**[檢索前沿研究與建議順序](../../research/retrieval/2026-07-12-ai-redesign-raw-retrieval-frontier.md)、[國際職能標準與差距](../../research/work-analysis/2026-07-13-ai-redesign-raw-intl-competency-standards.md)、[較早整合設計](../../archive/jobintel-v3/specs/2026-06-14-jobintel-ocs-integration-design.md)。尚未找到這些候選在 Caliburn 完整 A/B 評測的證據，也不能寫成已匯入整套 O*NET 資料庫。

## 2026-08 之後：參考知識與員工事實分開

### 08-01：檢索來的建議，不能直接變成員工工作事實

OPKS 證據規則逐步區分「員工實際說過／寫過」與「系統建議」。接受模型建議的動作不等於新增事實來源，參考資料也不能只因相似就成為此人的工作依據。

**引用：**[ADR0049：證據白名單及 reference 邊界](../../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)。這是產品證據權責的變化，不是檢索準確率實驗。後來原始訪談 → 情境 → 理解的發展另見[長訪談與記憶](memory-and-context.md)。

### 08-10 至 09-22：RAG 被隔離保留，不是抹掉所有前期研究

一次 hard cut 曾刪除 RAG 管線；Owner 隨後要求保留 PDF／JSON、parser、indexer、embedding 與契約，作為獨立領域，避免 JD App 重設計把有用研究一起刪掉。後續正式產品不依賴它，但研究與資料仍有獨立用途。

**引用：**[8/11 事件及保留範圍](../../specs/2026-08-11-rag-bounded-context-retention-design.md)、[ADR0057 草案](../../adr/0057-current-only-runtime-and-data-boundary.md)、[ADR0077 正式權責](../../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)、[RAG 領域入口](../../design/rag-pipeline.md)。不能把「範圍隔離」改寫成「某次搜尋失敗，所以完全放棄向量資料庫」。

## 後續取材注意

這條線至少包含資料解析、chunk 身分、搜尋粒度、執行環境、排序品質與事實權責六種不同問題。寫報告時可以沿原件挑一條問題鏈，但不要把它們合成單一「換資料庫就解決」故事。早期效能與品質數字都是當時設定下的紀錄，本次只做史料核對。
