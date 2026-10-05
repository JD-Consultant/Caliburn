# 執行進度

2026-10-05，inline隔離研究。計畫：docs/plans/2026-10-05-initial-retrieval-depth.md；保留其他dirty與全部舊原件。

Pre-flight：產生端完整D/T排名每query各805父，使用端按父prefix而非chunk prefix；158評判來源給12個grade3，其main_work必須對固定major_work_facets；一份代表可支持多面向，多來源不可重複計面向。

- [x] 截斷邊界／候選去重／面向去重／無標註unknown反例Red→Green；7測試通過，原logs保留。
- [x] 凍結18 inputs與581舊seal；48組候選、24target paths與最小N診斷、敏感度及候選量保存。
- [x] 177460已存chunk scores重聚成40×805父rank、20N20控制、48候選及12target／面向／所有工作量通過；零新推論／外送／費用。
- [x] 一次fresh review無Critical／Important／Minor；五個mutable檢索路由更新，文件／連結與封存readback由主代理另核。

Ruling：已知pool retention與全庫Recall分開 — 全805尚未逐份判讀，未知不能當負例 — 若錯會誤稱全部召回。

Ruling：代表來源保留與工作面向支持分開 — 同面向可有多份參考，員工工作不與公版1對1 — 若錯會為重複公版過度增加候選或把來源數當工作涵蓋。

Ruling：語意疑義只做預先敏感度，不回改grade — 排除多媒體／資材的影響可查，保留原判讀 — 若錯會用結果倒推標註、誇大檢索品質。

Ruling：只測初搜prefix與候選量 — 不同時調rerank模型或假稱fresh速度 — 若錯會混淆階段或低估時間。

結果：O N20/N40/N80均12/12來源與8/8已知面向；B2 N20 11/12與7/8、N40/80找回F01網站系統（D24/T41）。H01無grade3，unknown不納100%。候選pair O247/480/926、B2 381/748/1438；排除疑義後10/10與9/10→10/10，結論不變。

報告診斷另凍結report-input-manifest，只讀舊N20 U-R，沒有新N40/80排序；原話初搜12來源→舊R/K5留9，B2 11→5。冷氣B2 T7已召回，舊U-R17，不能把排序／K5損失歸初搜不足。stage-diagnosis逐份保留。

Final: Ruling: 舊模型3與人工真值未判 — 忠實沿原判讀／引句／敏感度，不把布林retention當人工作業驗收 — 若錯會把模型分數當事實。

Final: Ruling: 未評公版／全庫Recall／真人泛化／JD完整度未判 — 只檢固定已知pool，H01 unknown，保留補測 — 若錯會漏工作或過早收尾。

Final: Ruling: fresh延遲及N40/80 rerank/K5未判 — 只列初搜候選工作量與舊N20階段診斷，下一輪再驗R適配 — 若錯會誤選參數或宣稱省時。

Final: Ruling: review未判文件／路由／seal — 主代理另核來源、數值、差異、連結、SHA／bytes及逐檔readback — 若錯會失去追溯或把候選冒充現行。

Final: minor (deferred): 無。事前協定／計畫／code凍結，全部來源與原件保留；不commit／push／啟服務／清資料。
