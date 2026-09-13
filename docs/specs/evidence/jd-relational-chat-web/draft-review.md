# 聊天瀏覽器暫存：獨立審查

查核日期：2026-09-13。範圍為本輪 `web/src/lib/drafts.ts` 差異、新增 `web/tests/chat-drafts.test.ts`，以及既有 `web/tests/drafts.test.ts` 的兩行格式預期調整。審查者未撰寫這次聊天暫存變更；僅唯讀查核程式與執行窄測，未修改實作或測試。

## 結果

**PASS：本次範圍未發現具體 P1／P2 阻擋。**這是資料轉換、接點及交易等待的程式審查結論；不代表原生 IndexedDB、兩頁升版或瀏覽器重開已實測。

| 查核事項 | 實際核對 |
|---|---|
| format 1 人工資料保留 | `validateStoredDraftRecord` 原樣讀取 v1；只有已持有文件 Web Lock 的 `claim` 將該筆轉成 v2。原 `draftId`、人工 request、版次 ref、涵蓋序號、文字及未完成表單均保留；變更 owner 並推進 generation。未知格式及損壞資料拒絕覆寫。 |
| IndexedDB 升版 | `openDB(..., 2)` 不批次重寫或清除列；首次建立才新增原有兩個 object store 與 index。現行 idb 8.0.3 的 `blocking` 接原生 `versionchange`，App 關閉舊 connection 並通知 owner；`blocked` 不當成已取得新連線。這部分已核原碼，原生兩頁行為留給後續瀏覽器驗收。 |
| 先保存原請求再 POST | `prepareChat` 保存完整原 `ChatStartInput` 與涵蓋序號，交易完成後才回傳。清除的 A 輸入仍完整存在 request 中；呼叫者後改物件不會污染已保存資料。 |
| A 回覆與 B 新輸入 | 聊天輸入使用共享單調序號；A 的 terminal saved ACK 只清同 run／submission generation 的原請求，保留 B。新 owner 阻擋舊頁輸入、ACK 與取回；晚到舊序號不能覆寫較新輸入。 |
| 已知未保存與未知 | `not_found`、running、closing、recovery_required、錯 scope／run 不能清除或取回原請求。取回已知 not_saved 須明示呼叫，且拒絕覆蓋非空 B；只將原文字放回輸入框，不修改後端對話或 JD。 |
| `ai_unavailable` | 狹窄取回函式依賴明示 caller precondition，而非冒造 `not_saved` run。另唯讀追至 `chat-session.ts`：只有原 start POST 捕獲經 API 解碼的該錯誤才呼叫；status GET／timeout 不走這條。後端 `AiRuntime._start` 先查原 run，確無原 run 才拒絕 execution disabled。原 run／generation／owner 仍須匹配，不接受別次請求的晚回。 |
| 手改與聊天交接 | 人工候選、未完成表單或未閉合人工 submission 阻擋聊天 prepare；聊天 submission 存在時拒絕手改寫入，但可保存下一段聊天 B。人工 ACK 保留尚未送出的聊天。 |
| 有界資料及故障 | 全列只接受有限深度／節點數及最多 4 MiB 的 plain JSON；送出 request 再套正式 schema 與文字／body 上限。更新等候 `tx.done`，commit 失敗不回成功。讀到 `false`、`0`、空字串或 `null` 損壞列不冒充不存在，也不以新列覆寫。 |

既有 `drafts.test.ts` 只將目前格式預期改為 2、未知格式反例改為 3；人工保存、未知結果、覆蓋範圍與晚回保護的原斷言未放寬。新測試明說其 transaction port 為 double，沒有把這項結果當成原生瀏覽器證據。

## 實際驗證

在 `experiments/jd-relational-app/web` 使用指定 Node 24.19.0：

```text
node --experimental-strip-types --test --test-isolation=none tests/drafts.test.ts tests/chat-drafts.test.ts
47 PASS / 0 FAIL / 0 SKIP，366.5165 ms
```

本審查無新增首敗或產品修改。未呼叫模型、未連資料庫、未啟動瀏覽器、未安裝套件。

## 留在後續原生驗收的範圍

- 舊 v1 分頁持有連線時開 v2，實際 `versionchange`／`blocked`、關閉及 Web Lock 交接。
- 新 v2 claim 後關頁重開，確認原人工 request、聊天 A 原請求與 B 新文字仍完整；回覆遺失時不得自動換 run 或重播。
- 真實 IndexedDB 保存失敗及頁面關閉的呈現與恢復。這些是原定瀏覽器驗收，不要求新增暫存引擎、broker 或資料權威。
