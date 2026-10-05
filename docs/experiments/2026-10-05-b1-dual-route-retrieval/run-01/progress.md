# B1 雙路廣蒐實驗進度

- 使用者已同意試驗；先驗廣蒐，精搜與新增盲評不在本輪。
- 工作區：S:\caliburn，jd-app-docker；保留全部既有未提交改動，以新實驗目錄隔離研究原件，不建立乾淨checkout而遺失未提交的研究來源。
- Ruling: 離線新算exact排名並以舊真DB結果作控制 — 已有模型向量及同805／8068語料，先驗B1表示與候選涵蓋；若誤當fresh DB或產品效能，會選錯參數，報告須明列未測。
- Ruling: 用已知12來源／8面向固定清單及原疑義敏感度 — 不按新結果改分；若將其當全庫或人工真值，會高估涵蓋。
- Pre-flight: queries/vectors以query_id及text SHA綁定；D/T以parent與正文SHA綁定；候選按父而非chunk取N；不同query數的配對數與員工去重數分開。
- 待執行：Red–Green邊界測試、凍結來源、exact重算、96組比較、獨立核驗、紀錄/最後審查/封存。

- Task 1 complete：4反例測試觀察未實作Red（NotImplementedError），實作後4/4 Green；程式於freeze前固定。
- Task 2 complete：368輸入SHA凍結、1318舊seal核對；新算63query／126父rank／558999cosine，保存96候選組及48target追蹤。83舊排名／48深度控制不變，獨立核驗exit0。
- Task 3 complete：README／逐案report與機讀原件完成，5個可變路由文件更新；原封存實驗、production及他人工作不改。
- Final review：Critical0／Important0／Minor3（文案）；依原碼與資料逐項澄清，保留原生成程式及before/after紀錄，沒有排名或程式修正。未留未處理文案項。
- Final: Ruling: 補明順序、所測深度與配對分母 — 讓讀者正確理解回歸涵蓋及最低N，純文件核對，不改凍結分析；若錯會误認額度、樣本數或情境因果。
- Final: Ruling: reviewer set aside的語意／真人／新holdout、fresh DB／ANN、K5與服務延遲維持未驗 — 離線資料只能證固定已知清單；若錯會錯選正式方案或提前判JD完成。
- 最後待辦：fresh驗證、文件連結／差異檢查及SHA封存。未外送、未啟動service、未commit/push或清資料。

- 最終核驗exit0：558999cosine、126父rank、96候選組、83舊路／48深度控制、1318舊seal不變；6報告輸入SHA、原文及文案修正可逐字重建。文件連結檢查通過。待SHA封存，封存後不改run原件。
