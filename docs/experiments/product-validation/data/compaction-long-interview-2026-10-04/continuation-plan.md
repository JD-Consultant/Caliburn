# 2026-10-04：保留已完成前綴的四組續跑比較

這次沿用三層組已成功完成的 e001–e051，完成 e052–e061，再從空白職務檔案執行其餘三組。目標仍是相同員工來源、模型、提示、工具及判準下的四組比較；不要求三層組勝出，也不以外送成功代替品質判讀。

使用者確認：**累計 US$2，新一輪最多四小時**。main-01 保留 US$0.10，main-02 全部嘗試占用 US$0.483808190（含失敗第 52 段），新階段剩 US$1.416191810。所有未知回應保留預留，不靠 Prompt cache 免除 TPM 等待。900 生成／16 compact／2,200 外送／35M input 同樣保留 main-02 計數，四小時另從本次付費執行起算；護欄沒有放寬。

## 唯一執行修正

研究原設單輪 16 步，第 52 段有 16 份成功模型回應、33 次工具呼叫，尚未 final_answer，因此被研究上限停止。四組新執行統一使用產品既有 **64 步**；這是模型不可见的 Runtime 上限，不修改提示、員工輸入、工具、輸出容量或判準。既有 51 段未碰到舊上限，保留原回答而非重新抽樣；本比較是一次含續跑的個案，不是全新四組重複實驗。

## 原件與安全續跑

1. PostgreSQL 以官方 `CREATE DATABASE … TEMPLATE` 將既有隔離研究 DB 複製成 `caliburn_compaction_main03`；來源若有人連線即停止，不殺程序。不更改原 schema／checkpoint／trace。
2. 僅在副本，呼叫產品既有停止交易丟棄未完成 e052 的 JD 候選；正式訪談、正式 JD 與已採用輪前 compaction 必須保持相同。檢查結果保存於 `continuation-preflight.json`，模型外送零次。
3. 新 e052 使用新的 Turn 身分、同一員工原文，從已採用的安全 compaction 接續，不重用失敗 Step 候選或未正式答覆。e001–e051／前三批 Memory 原件只作帶雜湊的副本，標明 `prefix-origin.json`。
4. 另外三組各自從空白開始，獨立 schema；不給它們三層組的摘要、Memory、compaction 或顧問歷史。
5. 外送前保存 source／runtime／scenario／rubric／本計畫及 preflight 雜湊；執行期間不改凍結接線。不 push／merge，也不修改產品。

## 如何判讀

完成組別先取得 14 案的答覆、最終 JD、來源與查閱紀錄。品質按原事實單位及 12 工作領域人工判讀；比對數值、時點、責任、更正、回題及來源支持，錯誤同樣保留。效率分開計量 A、背景整理、count／compact 及工具回傳；用量不可代替品質。三層組的完整品質資料含原前綴，成本需分開「完成方法所用資料」與「整個研究實際支出」，不可隱藏失败 e052。

新 trace 只記本次外送，前綴 trace 仍在 main-02。接續審查以安全 compaction 身分及原件雜湊相接，不把失敗 e052 的末尾當成新請求應承接的基底。若四小時／預算先到，保存已完成組別，停止後再據資料回答可支持的範圍；不宣稱未完成組別通過。

參考：[PostgreSQL database templates](https://www.postgresql.org/docs/current/manage-ag-templatedbs.html)、[OpenAI evaluation practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)、[Prompt caching 與 TPM](https://developers.openai.com/api/docs/guides/prompt-caching#frequently-asked-questions)。本切片只增加有界研究續跑，不另造產品恢復機制。
