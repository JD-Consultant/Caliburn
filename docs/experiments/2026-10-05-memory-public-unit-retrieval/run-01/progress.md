# 執行進度

2026-10-05，隔離研究inline；保留jd-app-docker其他dirty變更。

- [x] 固定協定、八案二十查詢、來源／1,933舊封存／程式hash。
- [x] D/T/M六法真DB、24控制與144三輪暖機。
- [x] 同六法本機rerank、完整正文窗口、628品質pair及144任務／3,600fresh暖機pair。
- [x] 113重用＋45新增盲評，6唯一來源抄錄修正不改分；158唯一pair、96組逐份列0–3，估算US$0.044907465。
- [x] 獨立重算／負向probe、fresh review、清理及封存、入口；見verification-final、review、services-stopped與artifact-hashes。

Pre-flight：同query與D正文可跨方法共享品質rerank score，但暖機必逐方法重跑；兩路M每query融合後才取20，之後才跨理解融合。來源及評審仍指固定原話，不改Memory。

Task 1–4 complete：全部177,460cosine／D/T父序／M及跨query融合、628品質pair、3,600fresh暖機pair與窗口覆蓋、24控制、3個負向破壞probe、1,933舊檔hash通過；158pair證據有效。機制／非確定品質研究不是production TDD，不將解析成功當語意真值。

Ruling：全experiment封存格式不同 — 重用前輪RAG已核baseline並加Memory輪，仍逐檔重算1,933hash，排除無關家族 — 若錯會錯誤擴大保存／驗收範圍。

Ruling：controller可讀到worker未寫完的大型JSON — 原controller與錯誤留存，新02改等下一階段marker檔，後續144交接原已採rename — 若錯會誤報暖機或留下等待程序。

Ruling：API venv因未使用的chunk loader引入NumPy而失敗 — 新judge-only loader移除不必要計算依賴，payload／jobs／Prompt／schema不改，未安裝production依賴 — 若錯會造成評審輸入漂移；新舊source hash及raw request可核。

Ruling：6個模型引句抄錄不逐字吻合 — 限明示唯一同段來源，grade與全部非evidence欄位不變，另存final及before/after，不重跑provider — 若錯會把原評分沒有依據的內容當有據，保留語意未人工驗收限制。

自動核准曾拒絕45組外送，因18組授權不能擴張；人類使用者明確同意本45組後才執行。原拒絕及API import失敗均零provider request；45次模型回應無provider重試，原literal失敗紀錄保留。

Task 5 complete：同一次fresh reviewer重播驗證、核所有位置／時間／費用；Critical0／Important0。全部本輪服務停止／自然exit0，原有兩個JD PG仍運作；來源、引用、狀態及最後seal逐檔核對，入口更新只在本題。

Final: minor (deferred): 30個舊A判讀的輸入JSON欄位順序與本輪互換，83個raw request精確對上；內容及其餘設定等價，未驗順序不影響評審。README／review揭露，不重評或改原件。

Final: Ruling: 全庫Recall／真人職位／JD完整度未判 — 只作有限回歸，不當收尾或唯一職位 — 若錯會漏工作或過早收尾。

Final: Ruling: 158模型評分及既有Memory忠實度未全量人工驗 — 只核字面與重點語意，不當人工qrels — 若錯會把模型判讀當事實。

Final: Ruling: 多窗口GPU未實測 — 本輪628pair全部單窗口，最長正文2624tokens；完整正文已驗，不推出多窗口完成 — 若錯會高估長文涵蓋／低估成本。

Final: Ruling: 正式DB／ANN／App／端到端及p95未驗 — 固定exact與已載入模型，維持候選／研究 — 若錯會錯估產品延遲及排名。

Final: Ruling: reviewer未判入口／封存完成 — 主代理另核連結、狀態、manifest及逐檔hash readback，保留所有原件、不清工作目錄 — 若錯會損失追溯或將候選冒充現行。
