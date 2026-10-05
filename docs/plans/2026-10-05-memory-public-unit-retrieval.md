# B2與原話的公版粒度／合併／rerank比較計畫

狀態：2026-10-05，使用者已同意接續比較，沿既有inline隔離研究執行；執行前計畫保留，實際完成狀態見實驗progress。沒有production、commit、push或資料清除授權。

責任來源：[職位整體搜尋候選](../specs/2026-10-04-occupation-overview-reference-retrieval-design.md)、[代表評分v2](../specs/2026-10-04-representative-occupation-scoring-protocol.md)、[B1/B2六組原件](../experiments/2026-10-04-memory-layer-retrieval/run-01/README.md)、[本輪事前協定](../experiments/2026-10-05-memory-public-unit-retrieval/run-01/protocol.md)。本輪是機制／品質研究，不改產品；既有fusion重用，生成排名依真DB及獨立重算驗證，不表演產品TDD。

1. 固定20個O-W／B2-S查詢、既有D/T向量與805正文、判讀pool、全部舊封存hash，保存新協定與程式hash。檢查查詢完整body／固定revision。
2. 真Qdrant只讀，D／T／M六法先執行：每query20父，M兩路RRF後20父，跨理解RRF後全域K5。核16個D及8個O-T控制，三輪暖機並列兩路成本。
3. 相同六法各加本機rerank，完整D正文、不截斷、同20父；保存品質全部pair／window與三輪fresh推論。查query及document hash，無新embedding。
4. 聯集新pair沿相同Prompt／模型做盲評，重用相同舊判讀；核字面證據、費用及未知／失敗，逐份列分不相加。若外送審查拒絕，保留精確jobs與具體授權問題，先完成不依賴評分的核驗。
5. 獨立重算全部ranking／fusion／controls／usage；負向破壞probe、fresh review、服務清理及封存。整理哪些主要代表改善／退步、在哪一段候選丟失，不據單案例宣布最佳；更新入口。

接口：封存body／vector → D/T父20 → M每query父20 → optional完整D rerank父20 → 跨queryRRF → K5 → 固定原話pair判讀。M路數及候選聯集與成本明記，不讓更多chunk或重疊query直接灌票。

Review Focus：雙路M是否先去重及公平取20；跨理解是否重複投票／再次抹掉主責；rerank是否真的fresh暖機且完整正文、不以局部chunk冒充整體；同原話舊評分能否重用；控制是否不變；不把3分、公版數、速度差當全庫涵蓋或JD完整。
