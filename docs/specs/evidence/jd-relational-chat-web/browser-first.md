# 第一個真瀏覽器聊天旅程

日期 2026-09-13。操作者為 root，使用 Codex in-app browser 的實際 AX／DOM 與截圖觀察；不是瀏覽器 mock 或自然模型。

- fixture：`.research-tmp/jd-ui-gate-89efc61691f442b9bffd5e16ee6d57a9`，明示 prepare／initialize 一次；真 managed host／DPAPI、SQL／Saver、原生 Agent／Anthropic SDK，provider HTTP 僅用固定 MockTransport。
- Web：修後 production build，127.0.0.1:3002；API：127.0.0.1:8767。文件 `f3249666-14fa-4134-9d34-2ee2f763711e`；dataset `0d9beb32-cbc1-42b1-b557-76bb86eaa09e`。
- 瀏覽器 tab 9 建立「聊天與JD保存合成驗收」，最後關閉 tab 9，再以新 tab 10 開回同文件。只有合成文字。

| 實际操作 | 直接觀察 |
|---|---|
| 送出前打兩行工作描述，重新載入並選回文件 | 輸入區保留完整兩行文字；沒有自動送出，JD 仍空白。證明此流程實際經瀏覽器暫存重開，未證明所有 v1 upgrade 故障或斷電。 |
| 送出第一輪 | 回覆先為 running，手改欄位 disabled；原話保留於待確認區。**隨後 fresh 的 fetch 出現 response_unknown**，自動觀察停止；沒有宣稱 JD 回滾。 |
| 按「重新查看」一次 | 找到原 user／AI 已保存文字，顯示本輪完成、已保存 1 次 JD 修改。右側有 1 個設備檢查任務、2 個成果、1 個要求，手改恢復。原輪 ID `f8fd4e7b-f41b-4cdb-9a9a-a4113a5e5f31`；沒有另送 start。 |
| 點「查看第 1 次實際改動」 | 原畫面右側展開四項新增的 before／after；包含任務說明／名稱、兩項成果與要求，並仍有唯一可編輯 JD。瀏覽器截圖確認雙欄沒有彈到第二份可編輯文件。 |
| 手改職稱為「設備檢查人員（合成驗收）」，再送第二輪純訪談 | 先有第 3 版人工歷史，接著 AI 執行，手改暫停；第二輪完整回覆正常出現，顯示「本輪沒有修改 JD」。 |
| 另輸入第三段候選，保持未送出 | 第二輪完成後文字仍留在輸入區。此手動操作不能精確證明每種微秒級 A/B 交錯，交錯反例由單測承接。 |
| 關閉 tab，再開新的 tab、選回原文件 | 原兩輪 user／assistant 共四則、相同職稱、任務與三項明細均在；第三段尚未送出的候選也在。沒有再次送出。DOM 顯示第二輪 completed、本輪未改 JD、欄位可編輯。 |

## 首敗與限制

第一輪的 fetch 拒絕是真實首敗，不能改稱首次正常通過。API 的型別化 Problem／JSON 失敗與此錯誤不同；讀碼只能確認它来自 fetch，沒有資料可確定 timeout、CORS 或連線原因。原 helper 僅記入口次數，没有 status／send 完成／耗時，因此此輪根因仍未知。原回合查回已實際有效且沒有重複新增；第二輪沒有重現。

後續僅加有限 HTTP 測試觀察，再用新 fixture 重現一次。未因未知原因加自動重送、換 request key 或重建原資料庫。

此旅程不代表真模型專業判斷、完整 CV-01、整輪撤回、v1 舊頁持有連線的升版競爭、實體 IME、取消故障及全場景保存完成。`tab.content.export` 在此 in-app browser 不支援；本稿是實際 AX／DOM／截圖的人工驗收紀錄，沒有捏造自動匯出檔。
