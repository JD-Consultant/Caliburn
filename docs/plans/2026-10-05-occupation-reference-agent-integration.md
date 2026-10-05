# 公版參考工具接入顧問與 Memory

2026-10-05。狀態：**程式接線及隔離驗證完成，現有共用服務維持原設定**。使用者已要求「現在接入 tool」，並提醒另有人正在測試。本次沿既有[公版工具契約](../specs/2026-10-04-public-reference-completion-design.md)接線，不改檢索政策或 B2 內容分析方法。

## 交付與隔離

- 明示配置 RAG URL 才啟用；既有無配置程序及測試保持原工具清單。
- A 提供搜尋、讀公版、讀 state、選用及更新否認五工具；B1／B2 只有 `read_excluded_work`。
- A 的使用指引只在啟用的新請求追加：主要工作明確、收尾需要查漏時按需使用；從肯定工作組 query，保留多職位參考；否認獨立保存且可更正。
- 原 preparation／initial context／native Step 內的工具與提示不因新設定而換版。重入沿原 command/result，既有 Graph 不倒帶，故不額外呼叫 reference restore。
- 不重啟現有後端、RAG 或 DB；不改既有環境檔、不套正式 migration、不執行付費模型、不改共用 B2 instructions。真 PostgreSQL 僅使用既有測試 DB 的隨機 schema。

啟動前已唯讀核對：共用後端仍在執行，程序未帶 reload；兩個 PostgreSQL 容器運作中。另一工作正在調整 B2 指引，故新增使用說明另置檔，不改該指引。原角色提示測試僅將 bare Mock saver 換成 InMemorySaver，以支援新增的原模板唯讀查詢；既有提示斷言保留。沿目前含未提交 RAG 元件的工作目錄，精確編輯，不 reset／stash／commit／push。

## 依賴與切片

1. 原模板接續：`RoleContextHistory.resolve_template` 讀本 execution／role 已存 preparation request；held recovery 仍需相符的原 saver 邊界，不能用未驗證的 held 取代請求。只還原模板，不另存配置，不放寬原快照核對。測 preparation 已保存但 adoption 中斷、adopt 後尚未 capture、換模板及錯誤 boundary。
2. 選用設定與資源：`Settings.occupation_references` 預設 None，明示 URL／有限 timeout；bootstrap 沿既有 AsyncExitStack 管理 httpx2 client。沒有配置不建立 HTTP client；模型設定與預設不變。
3. 角色接線：A 的 prepared reference command 直接用既有 JSON，依 kind 分派；B1／B2 的讀取沿現有持久 F。工具實際資格依原始 request.tools，而不是當前開關；原 A 請求需要 RAG 但缺 client 時先拒絕，不送模型。
4. 真接縫：合成 SDK 與公版 HTTP transport，真 PostgreSQL／native saver，驗 A 讀寫→正式完成→下一 Turn、B1／B2 讀固定排除範圍、提交後中斷重播、取消／失敗不跨輪，以及關閉時的舊路徑。
5. 收尾：受影響測試、完整 unit/contracts、Ruff／Mypy，更新操作說明與權責。此輪無 schema 生成或前端行為改動時不重建前端。機制驗證與真模型語意效果分開記錄。

## 審查焦點

- 舊準備 checkpoint 恢復時不可偷換工具／提示，也不可以今日工具配置繞過持久資格。
- 原 result 或 DB operation 已成功時不重送搜尋、模型請求或重置候選。
- B1／B2 不能選公版或寫否認；否認不自動加入搜尋 query。
- 未啟用時不碰 reference 資料表／HTTP client；啟用不以 migration 或全域 env 暗改他人程序。
- 所有 client 由建立者關閉；不讓 RAG 故障變成空公版結果或清空 state。

完整 unit/contracts 1,377 passed、受影響 PostgreSQL 70 passed；Ruff／format／Mypy 通過。獨立審查發現的無原 checkpoint held 邊界已用反例修正並複審；詳見[驗證原件](evidence/2026-10-05-occupation-reference-tools/agent-integration-verification.md)。正式服務啟用須在其他測試結束後，依獨立環境設定及安全啟停流程處理。
