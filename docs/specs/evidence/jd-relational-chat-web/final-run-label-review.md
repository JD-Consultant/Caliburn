# 聊天原回合與輸入狀態：最後窄複核

- 查閱日期：2026-09-13。
- 審查者：`jd_ref_signer_preflight`；本輪不是 controller／ChatPanel 作者。
- 結論：**限定以下兩項 P2 已關閉，未見新增可重現 P1／P2。** 不代表完整聊天、真模型或全部瀏覽器情境完成。
- 本次只寫本報告；沒有修改產品、啟動服務、連接模型或寫資料庫。

## 1. 新原回合 B 不再沿用 A 的結果

核對 [controller](../../../../experiments/jd-relational-app/web/src/lib/chat-session.ts) 的 `selectRun`、`send`、`status`、`retry`、`cancel`、`recover` 與 `latestRun`：

- 確定新的原請求 B 後，先將選定 `runId` 改成 B，並清除不同回合 A 的 `run`，再等待網路回覆。
- B 的 POST／GET／cancel／recover 回覆未知時，保留 B 的原請求及選定身分；不再顯示 A 的完成／修改結果。
- `status` 回覆仍先核資料集、文件及原回合身分。這個 UI 修正不重造請求、不改 request key、不新增自動 POST。
- 原先同一回合的更新保持既有內容；切換回合才移除不同身分的狀態。

作者提供的首敗為 **29 PASS／4 FAIL**，四個具體反例是新 B 送出、重查另一筆原 B、取消 B、恢復 B 仍留 A 狀態。審查者沒有重演舊版；已獨立閱讀反例及修正後重新執行下列測試。

## 2. 畫面只呈現匹配回合與已證輸入狀態

核對 [ChatPanel](../../../../experiments/jd-relational-app/web/src/components/ChatPanel.tsx)：

- 使用回合狀態前，要求 `chat.run.run_id === chat.runId`；若有本機原請求，還要求其 `request.run_id` 相同。
- 原話未出現在目前對話頁，不等於未保存。`input_state=saved` 明示已保存但此頁未顯示；`not_saved` 明示未保存；`unconfirmed` 或尚無匹配狀態保留不確定說明。
- 舊 A 的完成、沒有修改 JD、已保存修改按鈕，不會被套在新 B 上。
- 只有匹配、已確認 `not_saved` 的原輸入顯示取回編輯入口；保留原有恢復業務判定。

## 3. 審查者實際驗證

使用已鎖 Node **24.19.0**，沒有新增依賴。

```text
node --experimental-strip-types --test-isolation=none --test \
  tests/chat-session.test.ts \
  tests/chat-controller-review.test.ts \
  tests/chat-handoff-review.test.ts

38 PASS / 0 FAIL / 272.9204 ms
```

其中 controller 33 案包含上述四個反例；獨立 review 5 案保留原先刷新、同版頁面、人工保存交接及 RAM 原話恢復驗收。這些使用有界 API／port doubles，不稱真 DB、IDB 或瀏覽器證據。

另外，直接讀取本版 `ChatPanel.tsx`，使用現有 Next bundled Babel 轉譯，再以實際 React／MUI 的 `renderToStaticMarkup` 核對 **7 PASS**：

1. 回覆屬 A、選定 B，隱藏 A 完成／無修改標籤。
2. 回覆與選定均 A，但本機原請求 B，隱藏 A 標籤。
3. 匹配 B、原話 saved、頁面未顯示，提示已保存。
4. 匹配 B、原話 unconfirmed，不誤報已保存或未保存。
5. failed／not_saved 保留原文並提供取回編輯。
6. failed／saved 保留已保存事實，不顯示未保存的取回入口。
7. 沒有本機 pending 的匹配完成回合仍正常顯示。

静態 probe 首次嘗試誤用已不由 TypeScript 7.0.2 套件根出口提供的 `transpileModule`，在呈現前即失敗；這是驗收腳本問題，不是 App 失敗。改用本版 Next 已帶的 Babel 後，七個實際元件呈現分支均通過。沒有使用該失敗結果冒充 UI 紅例。

## 4. 範圍與仍須分清的證據

- 七案是 React 靜態 HTML，不是新 build 的瀏覽器 DOM、AX tree、點擊、焦點或原生 IME 驗收。
- 主代理另已回報新 build 的 Workspace 更名錯誤在對話框內可見、輸入保留及取消返回；create 專屬失敗分支沒有重演。本次不將它擴稱建立流程的完整真瀏覽器驗收。
- 本報告不重審已通過的全部業務邏輯，也不宣稱自然模型品質、Memory 接合或所有故障恢復完成。
