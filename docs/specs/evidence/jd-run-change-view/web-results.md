# 當輪改動畫面：整合驗證與收尾

2026-09-13；主代理整合。依 Owner 最新範圍，只提供當輪 AI 已保存改動；不加入從舊對話選輪的狀態、入口或額外查詢。既有逐次歷史保留。實作、測試與獨審停止寫入後再做最後整合檢查。

## 最後版本的實際結果

| 檢查 | 結果及證據層級 |
|---|---|
| 作者新 UI 窄組 | 18 PASS／2369.9943ms；包括 R02 的同名任務原所屬反例 |
| 獨立 UI 窄複核 | 18 PASS／2558.4723ms；[R02 CLOSED、R01 依 Owner 範圍覆寫](ui-review.md)，無剩餘 P1／P2 |
| 主代理全 Web | **293 PASS／0 FAIL／0 SKIP，3135.3472ms**；同一 `tests/*.test.ts`，原生 Node `--test-isolation=none` |
| 完整 TypeScript | `tsc --noEmit` PASS；先前並行作者寫入期間的暫態語法錯誤不再存在 |
| Next.js 生產建置 | **build PASS**；Next16.3.5／Turbopack、TypeScript、4 workers 產頁及最佳化均完成 |
| 範圍核對 | `ChatPanel.tsx` 與 HEAD 無差異；沒有歷史選輪 state／helper／控制器，也沒有新增 `chatStatus` 呼叫 |

Node 使用已固定 **24.19.0** 的專案 runtime；沒有依賴升級。全 Web 涵蓋原 API／保存候選／聊天與新整輪讀取，不將各組重疊數字累加成另一個總數。新 UI 中 7 案使用真正 React／MUI `renderToStaticMarkup`；其餘投影／scope 與既有控制器測試不冒稱瀏覽器。

## 首敗與必要修正

- 初版新 UI module 尚不存在時先失敗；第一次初版全 Web 289 PASS，其後補例再窄驗。這些較早數字不是最後版本的全組結果。
- R02 首個反例 **1 FAIL**：職責 A／B 底下各有同名任務與要求，分別刪除要求產生完全相同 HTML。修正只沿現有 view 的 item/container 所屬關係呈現「職責／任務」，沒有新增欄位或修改資料庫。最後刪除原文及完整所屬位於收合區外。
- R01 曾以舊需求提出舊對話整輪入口反例；Owner 明確縮小範圍後，擴充及其新測試全部撤去。記為 `SUPERSEDED_BY_OWNER_SCOPE`，不是修好或未處理 bug，也不悄悄加回後續必做清單。
- 主代理最後第一次標準 Node test runner 因 sandbox 禁止 spawn 回 `EPERM`，未執行各檔案例。改用 Node 原生 `--test-isolation=none` 跑同一套 tests，293 案全部通過；未刪除／跳過測試。
- 第一次 Next build 已完成編譯（7.7s），TypeScript worker 的 spawn 被 sandbox 拒絕。相同程式與相同 build 命令經必要權限執行後 PASS：編譯650ms、TypeScript2.2s、靜態產頁1272ms；不把首敗當成程式型別失敗，也沒有停用檢查。

## 核實效果與未驗界線

當輪面板只取 matching run，狀態輪詢沒有新 committed 集合時不反覆重讀；完整頁由原 API 組裝。目前欄位提示還須符合原 E、相同資料集／文件、沒有未保存文字或表單。切輪／文件及人工候選時最終 render gate 拒絕舊標記，較晚回覆透過原 effect cleanup 不取代新 selection。這包含原碼與純條件驗證，**沒有真瀏覽器 effect／點擊／捲動／網路競爭的完成宣稱**。

同頁可見新增／修改／刪除／移動與引用，完整欄位前後仍沿原保存差異；改後改回保留保存事實，非連續只引導當輪原操作。新增標記不用顏色作唯一訊息；没有接受或已讀狀態。來源原話尚未接合時明示限制，不用 metadata 假裝回查成功。

本輪未啟服務、未做新瀏覽器旅程、未呼叫產品模型。先前 Fetch 根因與其餘成品工作集中於[收尾清單](../../2026-09-13-jd-app-open-issues.md)；通過上述分層測試不等於自然 AI／Memory／完整 App 已交付。
