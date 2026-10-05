# 原話與 B1 B2 比較執行紀錄

Plan: docs/plans/2026-10-04-memory-layer-retrieval.md。隔離研究；不 commit／push／production 接線。

- [x] 固定八案、30個原話查詢、125個可重用判讀；核1,775份舊封存檔，全部不變。
- [x] 現行 Memory parent 真 PostgreSQL＋真 provider 捕捉八份快照；35個B1情境／12個B2理解，來源及發布修訂核對。
- [x] 六組 D805 exact 搜尋、16個原話控制及144次暖機；93查詢，新embedding共2.093秒，與Memory成本分列。
- [x] 78唯一pair，60重用＋18新增盲評；原話及正文證據全部有效，逐份0–3分不相加。
- [x] 全部74,865cosine／fusion獨立重算、fresh review、服務身分核對後停止、封存與入口更新；見 verification-final.json、review.md、services-stopped.json、artifact-hashes.json。

Pre-flight：發布快照的 layer／content／revision／來源關係接入查詢 body；原話查詢 hash 必須沿前輪；評審接完整固定原話，不用 Memory 代替事實。多查融合沿前輪 RRF k2，沒有在本輪再調參。

Ruling：原 capture 在既有實驗 PostgreSQL 認證設定讀取時失敗，無寫入或 provider 請求；改用本輪新建的專用 PostgreSQL 18.6 容器、_test DB 與隨機 schema，保留原腳本／console及修訂 hash。理由：不猜測或更改他人服務認證。若環境不同會影響部署機制外推，但不改原話、Memory角色或檢索變因。

生成物及非確定品質 eval 不冒充 production TDD；確定性驗證依來源文字回讀、固定引用、DB exact與全部cosine／fusion獨立重算。未改 production 行為。

Task 1–4 complete：八份發布快照、48組前五、18新增盲評與全部排名／費用保存。模型80次Responses估算US$0.044934290。兩次盲評外送自動審查拒絕沒有送出請求；使用者明確同意18組送官方OpenAI後一次完成，無重試。原執行計畫及事前input manifest保留，不回改狀態。

Task 5 complete：主代理再次執行獨立verify，48組／240位置、78pair、93query／74,865cosine、16控制、144暖機及1,775舊檔全通過；39個owner source hash與封存時現況相符。fresh reviewer核47物件及重用判讀，Critical 0／Important 0。停止本輪Qdrant、專用PG與啟動的embedder，保留資料；既有兩個JD PostgreSQL仍運行。

Final: minor (deferred): F03性別、H03幣別及H02條件延伸有無來源細節；揭露於README／review，保留原快照與檢索，不修改Memory生成機制。

Final: minor (deferred): 完整39個API source hash於首五案後記錄，非全部事前pin；角色instructions已事前固定，記錄時點揭露，無法事後補造。

Final: Ruling: reviewer未判全庫Recall／真人職位正確率／JD完整度 — 本輪只作有限合成前五判讀，不作產品驗收 — 若錯會漏工作或過早收尾。

Final: Ruling: reviewer未判連續更新及模型重複穩定性 — 每案單一最終快照，仍待後續驗證，不推出更新後不必重搜 — 若錯會沿用失效參考。

Final: Ruling: reviewer未判服務清理、封存及入口 — 主代理完成身分／state／port核對、停止及hash／link檢查 — 若錯會留下耗資服務或損失追溯。

Final: Ruling: reviewer未自行重算74,865cosine — 主代理以獨立verify重新計全部cosine，reviewer另核正文、fusion、舊hash及費用，不混稱審查深度 — 若錯會誤報排名核對範圍。

Final: Ruling: 範圍外dirty production／文件 — 保留而不納入本輪驗收，沒有commit／push／接線 — 若錯會錯誤擴大完成範圍。
