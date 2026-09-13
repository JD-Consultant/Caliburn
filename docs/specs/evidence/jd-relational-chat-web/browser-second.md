# 首次讀取中斷的限定重現

日期：2026-09-13；root 實際 in-app browser tab 11，後端及 Web 為本機原生程序。只使用合成資料，沒有 provider 呼叫。

fixture `jd-ui-gate-4873515091cb44d78f5449aac30ffa10`，dataset `bda2e9c6-8eae-48f4-a4d5-18786b6e6ea7`。新 fixture 明示初始化一次，未重置第一組資料。相同 Web origin 3002／API origin 8767，新增 test-only HTTP 回應觀察。

## 實際結果與停止界線

1. 初始 GET 列表成功；建立「首次讀取限定重現」按一次。服務記錄兩個 POST 200；依既有程式為先 lookup 再 create，但原 trace 的 `other` 分類不能單獨證明各 route。Web 顯示 fetch `response_unknown`，對話框仍開啟，錯誤原先被遮在背景。
2. 取消對話框後原建立保留。明示查回、刷新、重開後再查回仍有立即 fetch 拒絕；無另造 request key。初始不帶 dataset header 的列表仍能讀到文件。停止繼續重送式排查。
3. 獨立代理只做一次帶 Origin／X-JD-Dataset 的 localhost GET：200、完整 JSON 一份文件 `76287bb7-3400-4195-8c4c-753533cc4224`；ACAO 與 `Vary: Origin` 各一，Content-Type 正確。既有 CORS 包裝一層，方法／標頭符合前端。這不證明瀏覽器已收妥，也不能據此宣稱 IAB 有 bug。
4. server trace 的 send-start／body-end 成功、Origin 比對為真，仍只代表 ASGI send 返回。該 Python 3.12 Windows `monotonic` 為 GetTickCount64，精度約 15.625 ms，因此 trace 的 0／15 ms 不能視為精確零耗時或 15 秒逾時。沒有充分資料定出兩組 fetch 首敗的共同原因。
5. 已修 `Workspace` 錯誤只在背景的缺口。新 production build 後，從列表選回已建立文件，開更名框，輸入「首次讀取限定重現（提示驗收）」並按保存；metadata 讀取失敗時，AX 直接在對話框內顯示連線錯誤，文字保持，取消可退出。此次驗的是共用 DialogContent 錯誤可見性；create 專属原 key 查回分支由已有四項回歸及程式審查承接，未額外聲稱真 browser 再次跑過 create 失敗分支。

本組沒有進入 AI 送出，SDK／JD writer 均為 0。不能把它計為第二份成功聊天旅程。第一組完整兩輪及真 DB 核對依[原結果](browser-first.md)保留，不被此限定重現覆蓋。

已關閉臨時 tab，API 以專用 stop 訊號正常關閉，Web 依已核對 PID／路徑／啟動時間停止；保留專用 DB 與原始 trace。後續需在可取得安全瀏覽器傳輸診斷的環境定位 fetch 失敗；不放寬 CORS、不自動重送，也不擴成泛用診斷系統。
