# 固定職位搜尋候選的第二輪驗證

授權：承接使用者自主測試及保留原件要求，2026-10-04「好繼續」。沿既有隔離研究流程執行；不改正式App、不commit/push。

方法責任：[本輪protocol](../experiments/2026-10-04-occupation-retrieval-generalization/protocol.md)，上位為前輪選型結果與ADR0079的RAG獨立界線。使用現行Memory指引、交易與模型接線，不造另一套Memory。

1. [x] 在新實驗目錄凍結14情境、答案/負例/界線；TDD核模型輸入不混labels、保存引用及缺漏的拒絕，生成前獨立核查。
2. [x] 重用已有PG/_test及公開trace工具，保守rate pacing與US$2上界，現行B1→B2→發布；按run保存快照、失敗及全部usage。
3. [x] 固定B2+TOP+exact dense+top10，與原話基準並列；查新holdout與負例，真Qdrantexact對离線分數/排名；不以本輪回调參數。
4. [x] 逐例核B2責任邊界，离線重算、manifest与原件封存、結果獨立核查、停止自有服務，回報通過與未定。
