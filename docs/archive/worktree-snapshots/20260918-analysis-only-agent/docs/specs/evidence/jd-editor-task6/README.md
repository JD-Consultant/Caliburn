# Task6 證據入口

2026-09-12；固定工程驗收，最終獨立審查已通過，見[closure](review.md)。先讀[結果、修正與限制](../2026-09-10-jd-editor-core-integration.md)，操作方式見[ACCEPTANCE](../../../../experiments/jd-editor/ACCEPTANCE.md)。

- `source/`：32個精確Task6檔案的審查前快照；含合成fixture及方法。原碼之後若有修正，須在closure說明，不改寫此快照。
- `inputs/task-6-review.diff`、manifest：相對已接受Task5的完整變更；README原11行由pre-existing snapshot排除。
- `task6-final-all.log`、`task6-final-jd.log`、`task6-final-memory.log`：三組最後Python結果，PG組實際執行、可能與離線組重疊。
- `task6-review-dirty-red.log`／green、`task6-web-fix-*`：最後手改保護反例、41項Web、建置／型別／lint。
- `task6-browser-initial.json`／png：完整固定旅程；`task6-browser-reopened-before-review.*`：第一次API中斷後新程序／瀏覽器；`task6-browser-reopened.*`：最後built Web的重開核對。
- `task6-e2e-result.json`：合成問答、實際送給SDK的內容、保存結果、手改通知與來源；沒有真實員工資料或金鑰。
- 其餘 `first`／`red`／`fixed*`／`sandbox-denied` 檔案保留原失敗。失敗紀錄不是最後通過證據，詳主報告逐項歸因。
- `reviews/`：Claude Opus5限定審查的已授權範圍、輸入hash與實際結果。只讀靜態審查不冒稱執行測試；CLI成本欄是估價，非帳單。

`.gitattributes` 對此目錄保留 raw bytes。`artifact-manifest.json` 記封存輸入的SHA256；最终交付另核完整檔案集合。工作helpers在 `inputs/` 是封存副本，其相對路徑以原 `.superpowers/sdd/2026-09-10-jd-editor-core-implementation/` 為基準，不直接從此證據目錄啟動程序。

未驗自然模型、真人IME／試用、正式切換或備份還原，不能用上述綠燈代稱成品。
