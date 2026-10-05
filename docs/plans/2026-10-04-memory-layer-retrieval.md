# 原話與 B1 B2 的六組檢索比較計畫

狀態：使用者已同意六組比較及以實際 B1／B2 輸出作輸入；隔離研究，尚未完成。不修改 production，不 commit、push 或清除既有資料。

責任來源：[既有比較範圍](2026-10-04-public-reference-retrieval-design.md#下一輪原話與-b1-b2-輸入比較)、[Memory 定義](../product-concept.md#核心概念與資訊關係)、[分析方法](../guides/2026-09-09-complete-work-analysis-guide.md#9-工作理解正文要寫到多清楚2026-09-25-研究補核對)、[事前協定](../experiments/2026-10-04-memory-layer-retrieval/run-01/protocol.md)。

1. 固定八案、既有公版與模型版本；保存事前協定及來源 hash。
2. 使用現行 Memory parent、B1／B2 runner 及真 PostgreSQL，在新隔離 schema 產生並發布八份快照。保留完整工具軌跡、正文、固定關係及費用；人工語意核對，不修輸出迎合搜尋。
3. 以六組輸入搜尋同一 D805 公版整份 collection；逐查 N20，單查保留 native 排名，多查用既有零起算 RRF k=2，全域去重 K5。核 exact cosine 與舊原話控制。
4. 相同來源 pair 評一次；沿既有 Prompt／模型／rubric，重用完全相同組合的舊評分，只盲評新 pair。逐案逐份列出，不平均／相加。
5. 核全部排名、證據、輸入與輸出 hash；記三輪暖機搜尋和新 query embedding 時間，Memory 費用另列。補 fresh reviewer，封存實驗，更新入口與下一步。

接口：已發布快照 → 原物件 body 查詢 → 同模型 dense → 同 D805 DB → 固定 fusion → K5 → 固定原話評審。拒絕跨案例／修訂混用，title 不代替 body。生成與品質 eval 不是 production TDD；確定核對機制用真輸出重算與負向破壞檢查。

Review Focus：B1／B2 是否真正經現行 parent 發布；是否偷塞預期職位或只摘有利正文；責任否定／更正／次要工作是否保留；評分是否仍看原話；舊資料不變；時間及模型成本有否混計；不把 3 分或全五名當全庫 Recall／JD 完整。
