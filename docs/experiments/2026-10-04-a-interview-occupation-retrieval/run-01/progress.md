# SDD ledger — plan: docs/plans/2026-10-04-a-interview-occupation-retrieval.md

- 已讀有效狀態及本輪來源；保留 jd-app-docker 工作樹全部其他變更。本輪隔離研究 inline，不改產品、不提交、不重播 A。
- Task 1：進行中。先測必要問題與員工回答的對齊、顧問證據拒絕，再凍結三來源與查詢。
- Ruling：現有自然 A 原件為三個職務家族，採各一份；不把同人設重複 run 當五個獨立員工。此輪無全端訪談，因此不宣稱修復全端漏搜。
- Ruling：比較四法的完整原文，另以第一則回答的整段 I01/I02 對照，避免為短開場強造分段；初始候選仍依完整員工事實評判。
- Pre-flight：源轉換產生的固定正文／原話定位供 embedding、rerank及評審；排名不讀評審答案。必要顧問問題可以進查詢脈絡，卻不能作員工證據。

- Task 1：完成。新問答來源轉換先 Red（projection 缺失），後 Green 4/4：對齊前一輪問題、單段問題不掉首字、失敗輪拒絕、顧問句不可作員工證據。三源SHA與原始保存清單核對，分段聯集涵蓋69員工回答。
- Task 2：18 個新 BGE-M3 向量及18次真Qdrant exact初搜已完成，查詢1024維及全庫805排名一致；rerank進行中。

- 分析準備：引句只修逗號／空白的兩筆另存；首次建立analysis manifest時相對／絕對path混用，未產生報告或更改排名。改用resolve後凍結，保留原31筆評分與失敗summary。

- Task 2：完成。18×805全排名與18次真Qdrant初搜一致，360 fresh品質pairs；先等模型及初次排序完成後，18組各三次暖機共54 trial，1080 fresh benchmark pairs，沒有混入載入；模型載入39.691秒、新embedding另列。
- Task 3：完成模型批次，語意有效性未驗收。33唯一盲評／US$0.047436980，31自動逐字核對、2回應僅三處逗號／空白恢復來源；沒有改分或重評。原33responses、失敗summary及31原judgments保留。
- Task 4：完成。報告逐份分級、不加總；三組已判3公版的階段追蹤不冒充完整Recall。獨立唯讀review核機制一致，列額外責任給2、孤立通知給2及共通第一句重複限制，保存原分。更新當前RAG路由，未改舊封存資料。
- 停止自有Qdrant51672，嵌入與rerank容器均exited0。第一個即時cleanup計所有connection狀態有2，cleanup-02再核process不存在／0 listening；兩份保留，沒有刪weights／storage或動產品服務。
- 結果：原開場已找到本批全部已有3來源；完整訪談有局部名次改善／退步，分段／rerank未新增強代表。R01保留控制基線，沒有正式贏家或門檻。初期不適合、更多原文必然更準、全端已修復、Memory及JD/PDF完成均未證明。
- 本輪不commit、push、merge；全部原件、失敗、分析修訂及核對封存於本研究目錄。
