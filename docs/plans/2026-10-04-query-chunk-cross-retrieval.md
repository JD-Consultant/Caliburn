# 員工分段與公版切塊的交叉檢索

2026-10-04。使用者同意接續比較員工工作主題分段各查公版chunk，再合併整體參考。延續隔離研究及自行測試／詳細保存授權，不改production、不commit。沿已同意研究probe inline執行，末尾一次唯讀review。

1. 固定前五合成需求／三完整A訪談的原whole與既有segments，重用30向量及前輪公版D/T/U三collection。先Red–Green驗每段父去重、RRF同來源合併、單段不改名次與固定同分序；保留前輪已知共通第一句重複。
2. 本機真Qdrant exact分組各查20父×3chunk，按max／mean3得到每段父序，再多段RRF k2留全域K5。whole×D/T/U是控制，segments×D/T/U是新增；D只有max、T/U含mean3，共80組／400位置。核90真DB質量查詢與全point分數，記3次暖機及每段候選／最後合併排名。
3. 只評新增員工×完整D pair，重用前輪117個有來源的grade；同F/H Prompt、schema／Luna high，US$1／100calls／SDK重試0／批次30分鐘，原引用失敗與費用保留。無新Memory／真人或訪談。
4. 逐份0–3不相加、比較已評強來源在哪一段進候選及在哪階段掉出前五。保存輸入hash、原件、benchmark、有限結論、獨立review與seal；停止自有Qdrant，不動其他服務及旧資料。

驗收為可核對的交叉實驗，不要求結果改善，不把模型grade当全庫Recall或正式最佳方法；未測整份＋chunk雙路混合、rerank／門檻、Memory及JD/PDF收尾。

[協定](../experiments/2026-10-04-query-chunk-cross-retrieval/run-01/protocol.md)、[ledger](../experiments/2026-10-04-query-chunk-cross-retrieval/run-01/progress.md)。
