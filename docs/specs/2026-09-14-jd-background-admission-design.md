# 背景准入：狀態、失敗與恢復條件

2026-09-14；JD-R002／OI-01、OI-02。[H4 計畫 §4 R3](../plans/2026-09-14-jd-h4-runtime-integration.md) 的施工前設計，把[採用映射 §3.3](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md#33-背景排空歸屬) 的候選六欄收斂成選定方向。決定紀錄見 [ADR0076](../adr/0076-jd-background-admission-record.md)。

**本稿只定義狀態機與恢復程序，不是完成報告。**

## 1. 為什麼需要一個落點

缺口不是推論，是實測：[真 PG 案例](evidence/jd-b1-adoption/r3-notification-and-background-results.md)逐一列出 B1 Saver state、B2 Saver state、publication head 與 `jd_document` 的全部欄位，`target_reference`、`status`、`error_code`、`recovery_count` 四項都不在其中。

`source_reference`（本批）確實是持久的——兩個 workflow 都存它——但**批次是 target 的前綴，不是 target**。第二條案例證明：丟掉 target 之後只剩目前 head，而從 head 重推的範圍會隨員工繼續講話而變大，已准入的工作因此永遠不會收斂。這正是窗口契約禁止的「用 latest 取代已保存 target」。

**這是 App 自己的工作責任跨批次、跨重開要保存。**不是 LangGraph 無法保存狀態——它保存的是各自 workflow 的執行進度，而「哪一段範圍被准入了」不屬於任何一個 workflow 的執行進度。也不是任何外部規範要求這六個欄位；六欄沿用已驗 `BackgroundRow` 的責任劃分，是本案選擇。

## 2. 三個位置，三個不同的事實

| 位置 | 回答什麼 | 誰擁有 |
|---|---|---|
| `target_reference` | **這次已准入工作的固定終點。**後續訪談不得擴大它 | 准入列 |
| `source_reference` | **目前正在交接的固定批次。**invoke B1 前先提交 | 准入列 |
| `publication.processed_source` | **唯一已發布進度。**只由已確認的發布結果推進 | publication |

B1／B2 的節點、`files`、模型與工具預算、更正額度**仍由原 Saver 負責**，不複製進准入列。准入列不保存第二份原話、Memory 或已整併游標。

## 3. 狀態機

四個狀態沿用已驗 `BackgroundRow`：

| 狀態 | 意義 | 欄位約束 |
|---|---|---|
| `idle` | 沒有已准入的工作 | target／source／error 皆空 |
| `queued` | 已固定 target，尚未切出批次 | target 非空 |
| `running` | 已固定 target 與本批，B 工作可執行 | target 與 source 皆非空 |
| `blocked` | 有具名原因停住 | error_code 非空；target／source 可空（規劃前就受阻） |

轉移：

| 從 → 到 | 條件 | 同時寫入 |
|---|---|---|
| `idle` → `queued` | 有安全收尾且未被游標涵蓋的有效整理請求，且 `require_handed_over` 通過 | 由 owner 以 `unprocessed_source(after=cursor)` 的範圍發出固定 target |
| `queued` → `running` | `plan_saved_batch(target, after=cursor)` 切出批次 | `source_reference`＝該批次；**先提交再 invoke B1** |
| `running` → `queued` | B2 已發布本批，且 target 仍有尾端 | 清 `source_reference`，**保留 target** |
| `running` → `idle` | B2 已發布，且 target 已被涵蓋 | 清 target／source／error；`recovery_count` 歸零 |
| 任一 → `blocked` | 具名有界原因（來源受限、預算耗盡、模型不可用） | 寫 `error_code`；**保留**現有 target／source |
| `blocked` → `queued`／`running` | 觀察到根因確實改變（例如未收尾回合已收尾） | 清 `error_code` |

**`recovery_count` 只在確立新工作或完成舊 target 時歸零**，不因重開程式歸零。

## 4. 准入列證明不了什麼

`running` 不證明模型執行過；`idle` 不證明發布成功。這兩件事分別由 **Saver 的 checkpoint** 與 **publication 的 receipt** 證明。准入列只回答「哪一段被准入、目前卡在哪、為什麼」。

**不要求跨 Saver、Store 與准入列的單一大交易。**三者各自持久，恢復程序負責對帳。

## 5. 重開時的對帳順序

依序讀准入列、B1 snapshot、B2 snapshot、publication head／receipt，再決定下一步：

| 觀察到的持久事實 | 唯一允許的下一步 |
|---|---|
| B1 有 pending checkpoint | 以原 config `resume()`；**不得用新來源重新 start** |
| B1 完成、B2 未開始 | 把原 `files` 交給 B2；不覆寫 B1 最近輸入 |
| B2 有 pending checkpoint | 原工作續作；已有原 receipt 則沿原對帳路徑收尾 |
| B2 已發布、准入列尚未更新 | 以 publication 為準修正准入列；不重跑 B1／B2 |
| 已發布且 target 仍有尾端 | 由唯一 publication cursor 切下一批；**target 保留** |
| 已發布且 target 已涵蓋 | 轉 `idle` |
| `blocked` 且根因未變 | 維持 `blocked`；不每次喚醒重試、不重啟清額度 |

## 6. 並行、喚醒與封存

- **同文件 B2 尚未發布，不得開始下一批 B1。**由既有 `require_handed_over` 以 publication head 判定，不在准入列另存一份判斷。
- **重複喚醒是冪等的**：`running` 且原工作仍在時不重複執行、不替換 target、不重置 `recovery_count`。
- **新訪談中的有效通知保留待後續評估**，不覆寫當前 target，也不寫進准入列。
- 沿用**既有有限 worker、宿主所有權與排空機制**；不新增通用排程器、分散式 queue 或第二套 lease。
- **封存停止新准入**（不再 `idle`→`queued`）；執行中的有限批次可完成；准入列保留，不刪除、不重設額度。恢復文件後核原工作續作。

## 7. 表與界線

一文件至多一列。**十三張 JD 內容表不增減欄位**；此列是 runtime 准入表，與 JD 內容分開。**App 的總表數確實增加一張**，README 與 runbook 須如實寫明，不能以「JD 表沒變」掩蓋。

普通 open **只檢查已安裝**，不建表、不清資料；migration 是明示初始化。此表存在不代表 production authority 已切換。

## 8. 驗收範圍

准入提交後尚未啟動、B1 完成但 B2 未開始、發布成功但准入尚未更新、原 target 尚有尾端時新增訪談、重複喚醒、`blocked` 與恢復額度跨重開、封存／恢復。真 PG 與真新 Windows 程序證據沿 R3；**零 provider**。
