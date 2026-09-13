# 完成窗口：游標 lineage／完整邊界與查找上限

2026-09-13；JD-R002／OI-01、OI-02。依[實作審查](../2026-09-13-jd-window-source-implementation-review.md) F-01（P1）與 F-03（P2）修正。基準 `bdc28ce2`／tag `jd-window-contract-scenarios-20260913`。0 provider、沒有新增資料表。

## F-01：游標比較確實漏了 lineage 與完整邊界

審查說得對，而且這是我實質的漏。契約 §7.2 明寫「**同 ID 不足以證明 lineage**」，但原本的 `_after_cursor`／`follows` 只做兩件事：解析簽章、確認 `position.last` 出現在目前訊息 ID 清單。**從頭到尾沒有打開游標自己的固定 root。**

我先前在[第二片結果稿](window-read-results.md)寫「lineage 以訊息序列精確前綴證明」——那句對 `safe_turns` 的逐輪終局成立，但我讓它讀起來像是也涵蓋了游標比較，屬**過度宣稱**。

實際後果由新反例示範：第二輪含一則 tool message，游標若停在那裡（簽章完全合法），原本會把 admission 直接推過**整個**第二輪，靜默丟掉其後的員工原話。

### 修法

新增 `AiRunHistory.ancestor_of(document_id, checkpoint_id, config)`：沿 `find` 用的同一組公開 parent 連結、同一個 `MAX_PARENT_LOOKUPS` 上限走鏈。走到鏈首代表**不是**祖先；走滿上限代表**無法證明**，明示回報而不是猜。放在既有負責走鏈的類別，不另造第二套走鏈。

`ConversationSourceService._cursor_boundary` 為 `_after_cursor` 與 `follows` **共用**，依序要求：

1. 在游標**自己的固定位置**讀回（不是假設它存在）
2. 該位置的訊息序列是目前對話的**精確前綴**
3. 游標的 root 與目前 root 相同，或經 `ancestor_of` 證明為**真祖先**
4. 游標的 `last` 必須**正好**等於某個已安全收尾回合的 `last`

任一不成立即 `invalid_ref`：不 fallback 最新、不重設游標、不當成已處理。

### 三個新反例

| 反例 | 原本 | 現在 |
|---|---|---|
| 合法簽章但停在回合中間（tool message） | 接受，並跳過該輪其後原話 | `invalid_ref` |
| 游標自己的 root 讀不到 | 接受（根本沒讀） | 明示失敗 |
| **同內容**的兄弟鏈（同一 root 兩次 update 產生，訊息完全相同） | 接受 | `invalid_ref` |

第三個是關鍵：訊息前綴相同、ID 也相同，只有走鏈能分辨。我第一次的分支構造是錯的——`update_state` 會讓 fork 成為**新 head**，游標反而正確地變成它的祖先；改用同一 root 產生兩個兄弟才真正觸發 `ancestor_of`。

## F-03：超過查找上限

補上 `>MAX_PARENT_LOOKUPS` 的固定鏈案例：在既有兩個安全回合之後累積超過上限的 checkpoint，確認 `safe_turns` 仍**明示** `original_run_lookup_required`。上限是查找限制，不是「更早的回合或其原話不存在」的證據。缺鏈案例保留，兩者分開。沒有因此改寫歷史查找器。

## 實際驗證

首敗：三個游標反例全部 **DID NOT RAISE**，與審查描述一致。

| 範圍 | 結果 |
|---|---|
| 本檔案案例（累計） | **34 passed／5.67s** |
| App 全離線測試 | **2774 passed／257 skipped／64.31s** |
| Memory 套件全測 | **130 passed／6.53s** |
| 真 PG：C 接合＋原話來源＋Memory 核心＋AI runtime | **18 passed／17.50s** |

## 仍然開著的（不在本片）

- **F-02／W-13**：只有 `validate_saved_window` 的 source 層部分證據。真正的 `reextract` 與「正常 B1 輸入位置不前進」要等 B1 adapter，**不現在偷接一套 B1**。
- **F-04**：保存的 source/context pair 尚未驗證「是同一個規劃 pair」，兩個同 root 的合法 context token 可交叉配對。依審查判斷**留給 B1 artifact adapter**，不現在另造通用配對引擎。
- **F-05**：`MemorySourceReader` 仍只能驗證 window／context，不能讀取；要等 B1／B2 adapter。
- 整理通知的工具註冊、結果分類與停止／恢復路徑仍是一個完整工作單位，未開始。

## 界線

1. 本片只修 F-01／F-03，**不代表 H4、B1／B2 或完成窗口能力已接通**。
2. W-13、W-14 的完整涵蓋仍未成立：W-13 缺 B1 證據，W-14 現在缺鏈與上限兩案都有，但仍只是 source 層。
3. 全部為離線與固定 fixture，沒有 provider 呼叫；日常 AI 未啟用。
4. 沒有新增資料表、第二份游標或第二個原話 owner；C repair 與四個只讀工具未改。
