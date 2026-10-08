# 工作條件探索：新舊顧問指引對照

本批使用者已確認新增最多 US$0.10／20 分鐘。目的是比較指引能否從正常流程進一步探索重要條件，同時避免重問未知、已確認答案或違反員工停止。前批[漏問診斷](../jd-analysis-full-journey-2026-10-06/exploration-followup.md)與全部原件保留。

## 固定範圍

八份合成案例，新舊各一次、獨立職務檔案，順序交錯。模型固定 `gpt-6-luna`／high、16,384 輸出上限；舊指引取前批 `freeze/sources.zip`，新指引取本機已確認修改。正式 Runner、工具、Context 組裝、候選提交與來源契約不變。

先各執行一次同一份可見員工輸入，判讀顧問下一問。只在問法確實涵蓋目標面向時，才可提供 `private-answers.json` 中該題的固定後續回答；不靠字串觸發，不把答案或判準放進模型輸入。後續若執行，沿用同一檔案與原生接續，仍共享原截止及剩餘預算，不重跑首次回答。

三項倉庫條件分別為環境、差錯及工作量變化；另有帳務與軟體維護案例，以及已確認穩定、特定未知及明確停止三項反例。案例刻意聚焦某項工作，這是局部診斷，不當成完整訪談能自動找出所有隱藏工作。八案為探索性案例，不宣稱盲測或重複統計。

種子訪談的「已記錄」回覆是 fixture，不是真模型的先前訪談。起始 JD 透過既有編輯 API 建立，任務有種子原話來源。公版工具可用，但 HTTP 使用同一份通用合成參考，不含私人答案；本批不驗真 RAG 檢索品質，不啟動 Memory 背景外送。

## 隔離與界線

只在既有測試 PostgreSQL `caliburn_docker_test`、55441 新建隨機 schema。既有 8105／8106 產品、資料及容器不啟停。金鑰沿後端唯一讀取器取得，不輸出或保存。首次外送啟動時間護欄，輸入計數、模型及可能壓縮一同計入費用；未取得用量的請求保留預留。限流／護欄停止保留原件，不暗中重開或重置。

使用既有 `run_comparison.py`、`StudyGuard` 及不可覆寫凍結紀錄；本目錄的薄接線只更換案例與基準來源，不另造 Agent loop。準備時凍結共用腳本、前批基準包、本批案例與正式程式，後續驗證雜湊。新 case 名稱與私人判準不給模型作分析指令。

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/jd-condition-exploration-2026-10-07/run_comparison.py prepare
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/jd-condition-exploration-2026-10-07/run_comparison.py execute
```

## 判讀與保存

依實際問題語意及員工可答範圍判讀，不要求唯一問句或工具順序。分開記錄中立探索、未重問、事實邊界、停止與揭露後 JD／來源正確性；其他有意義的問題保留為實際行為，不能硬算命中目標面向。工程代理依原判準逐案審閱並列出原話位置，不冒稱真人盲評。

用量、執行失敗與品質分開；第一次只問對問題不代表後續已完整整理。配對少或有未完成時直接列出，不以 API 成功、低 token 或欄位有字替代品質。方法沿[OpenAI 評測建議](https://developers.openai.com/api/docs/guides/evaluation-best-practices)，採本產品具體判準，不套用其示例摘要分數。

狀態：已結案，16 次首輪加 6 次探索性接續正常完成；見[結果與下一步](results.md)及[首輪判讀](first-question-review.md)。未證明三項漏問已解決：新版在上架案轉問負荷，但環境與常見差錯仍未取得。占用估算 US$0.057300990、約 14.51 分鐘，沒有追加外送。

本頁已同步最終狀態；準備當時的文字、案例、提示與腳本版本仍保存在 `live-01/sources.zip` 及 `live-02/sources.zip`。原始 manifest、trace、回覆及判準不改寫，也不重跑已執行的資料包。
