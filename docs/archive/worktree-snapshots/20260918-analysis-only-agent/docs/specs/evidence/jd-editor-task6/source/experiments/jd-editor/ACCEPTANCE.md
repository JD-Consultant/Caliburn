# JD 隔離核心驗收

2026-09-12；Task1–5 已接受，Task6 工程驗收完成、獨立審查中。這是零產品模型呼叫的固定工程情境；尚未宣稱自然訪談品質或可交付成品。

## 已觀測的完整旅程

`fixtures/core-scenario.json` 明示合成設備維護案例與固定工具意圖。員工文字、預期內容固定；文件身分、來源、目標與 K/S 引用由真 App 發配。`analysis-agent/tests/jd_offline_service.py` 只替換 HTTP 模型回應，使用同一 AnalysisService、router、graph、PostgreSQL Saver／Store、JD service 與原生 Plate 運算；沒有 live fallback。

1. 由 `http://127.0.0.1:3001` 建立空白文件，開始訪談；資訊不足只追問，JD 不增版。
2. 補足工作後產生六章內容；首建及重新讀取後連結共享知識／技能各保存一次。兩項任務的成果與要求各自保留。
3. 指出月檢只適用於約定服務，修改對應條件；故障處理及其權限、判斷與交接全值不變。原畫面可查修改前後與原始問答，只有一份可編正文。
4. 在正文實際選取並輸入繁中更正、保存，再請 AI 續編；保留手改。API 固定案例另連續保存三次，核實下一輪模型請求中的人工變更通知計數與已知基準；不是偽造員工原话或更新 Memory。
5. 致謝／純訪談不改 JD。另在 API 注入提交後結果遺失，再取消對帳，僅一版、一份原工具結果且無模型重試；純聊天取消不假造 JD receipt。
6. 關閉瀏覽器、核實並中斷本次測試 API，再用同安裝範圍重新啟動。全新瀏覽器取得相同 current、五筆歷史、來源、原問答及原 run 結果。

真瀏覽器使用 Playwright 的 Chrome channel、headed 1500×1050，實際版本及 network 記在證據 JSON。網頁請求只有 3001／8091，無 8001 或外部 provider。繁中輸入為 DOM／鍵盤插入；**未測 Windows 真人輸入法**。

## 可重現檢查

只在 `S:/caliburn/.worktrees/analysis-only-agent`、既有精確 lock/runtime 與專用測試 DB 執行。Node 使用 `.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task4-runtime/node-v22.23.2-win-x64`；Python 使用 `analysis-agent` 的 uv 環境。Windows managed runner 在任何 DB／client／native 工作前 bootstrap；不能直接用未受管理的 pytest 取代生命週期驗收。

- `analysis-agent/tests/task5_acceptance_runner.py`：完整離線測試。PG opt-in 須另實際執行，不把 skip 稱成功。
- `task6-python-regression.py jd`：專用 `q019_jd_app_20260910`，真 JD PostgreSQL／native／新程序案例。
- `task6-python-regression.py memory`：只允許本機 55433 `q019_agent_test`，含四組實際 factory/model-role 檢查。明示 additive test setup，不重建或清空資料庫。
- `task6-web-checks.py`：契約生成一致性、原生／Web 測試、建置、型別及 lint；`--fix` 只重跑最後受影響建置檢查。
- `web/browser/task6-journey.mjs`：完整固定畫面旅程；`--reopened` 比對同份已保存證據。須先核對具名測試程序並經真重啟，參數本身不證明已重啟。

上述工作用 helpers 與 raw logs 已封存在[Task6 證據](../../docs/specs/evidence/jd-editor-task6/)。它們不是日常啟動入口，不要求員工操作研究腳本。固定 factory 可依核心計畫以明確測試 DB、穩定 installation key、單 worker／無 reload 的 8091 啟動；正式日常啟停、備份／還原及更新仍屬 P5。

## 證明界線

完整結果、首敗與修正、來源／版本及未驗項目見[核心接合結果](../../docs/specs/evidence/2026-09-10-jd-editor-core-integration.md)。不同測試群可能重疊，不加總為獨立案例數。CLI reviewer 的靜態判斷不冒稱測試執行。

仍未驗：自然模型自行判斷寫稿與工具選擇、不同職位專業品質、長訪談新 JD 影響、真人 IME／三名員工、正式 authority 切換、完整備份還原與日常入口。P3 產品模型測試另需資料／呼叫／費用授權；使用 Claude 作工程審查的授權不等於 P3 授權。
