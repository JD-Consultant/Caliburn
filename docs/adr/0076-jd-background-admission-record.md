# ADR0076：新 JD App 的背景准入列

**2026-09-16 MEM-L001 影響：**本 ADR 是 Proposed，且六欄決策主要承接一份文件的背景准入、固定 target、目前批次、錯誤與恢復次數；這些責任仍可作 G4 基礎。但下文把工作描述成「B1 固定窗口抽取 → B2 兩檔整併 → publication」的部分已由 [MEM-L001](../specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md) 取代。新流程為 B1 staged 案例層 → B2 staged 工作理解層 → 一次共同 publication；G4 必須核對現有六欄是否仍能無歧義恢復整個共同工作，不能直接以本 Proposed ADR 宣稱新流程已獲正式 authority 或已完成。

**狀態：**Proposed（2026-09-14）。隔離 JD App 範圍內採用；不改 production authority，不取代 [ADR0060](0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) 的正式顧問。

## 脈絡

新 JD App 的背景整理是 B1（訪談抽取）→ B2（整併）→ publication 三段。[窗口來源契約](../specs/2026-09-13-jd-interview-window-source-contract.md)與[採用映射 §3.6](../specs/2026-09-13-jd-consultant-b1-b2-adoption-mapping.md) 要求：准入時固定一個 target，之後的批次都從該 target 切出，後續訪談不得擴大它。

問題是這個 target 沒有地方放。[R3 實測](../specs/evidence/jd-b1-adoption/r3-notification-and-background-results.md)在真 PostgreSQL 上逐欄列出既有持久狀態：

- **B1 Saver state**：`source_reference`（本批）、`windows`、`position`、`files`、更正額度
- **B2 Saver state**：`source_reference`（本批）、`files`、`base_revision`、`attempt`、已用模型步／工具呼叫、`request`、`result`
- **publication head**：`revision`、`memory`、`processed_source`
- **`jd_document`**：`id`、`title`、`archived`、`metadata_version`、建立請求鍵與摘要、時間戳

`target_reference`、`status`、`error_code`、`recovery_count` 四項都不在其中。第二條案例進一步證明批次不能代替 target：丟掉 target 後只剩目前 head，而從 head 重推的範圍會隨員工繼續講話而變大，已准入的工作因此永遠不會收斂。

[映射 §3.3](../specs/2026-09-13-jd-consultant-b1-b2-adoption-mapping.md#33-背景排空歸屬) 已把已驗 `BackgroundRow` 的六欄責任列為候選，並要求「先驗證既有 Saver／catalog 是否確實無法承載」。該驗證已完成且缺口成立。

## 決策

在隔離 JD App 的同一資料庫、同一 Alembic 鏈新增一張 runtime 准入表 `jd_memory_admission`，**一文件至多一列**，六欄：

| 欄位 | 約束 | 單一責任 |
|---|---|---|
| `document_id` | PK；FK → `jd_document.id` ON DELETE RESTRICT | 不建立新文件身分；不含租戶／帳號／ACL |
| `status` | 非空；CHECK `idle`／`queued`／`running`／`blocked` | 准入狀態，不代替 LangGraph 的節點或 pending 狀態 |
| `target_reference` | 可空；簽章 window ref | 這次已准入工作的固定終點 |
| `source_reference` | 可空；簽章 window ref | 目前正在交接的固定批次；**不是**已處理游標 |
| `error_code` | 可空；有界安全碼 | 不保存 stack、金鑰或原話 |
| `recovery_count` | 非空整數；預設 0；CHECK ≥ 0 | 宿主恢復次數；與 B1 格式更正、B2 模型步分開 |

另加狀態組合約束：`queued` 必有 target；`running` 必有 target 與 source；`idle` 三者皆空。

狀態轉移、失敗分類與重開對帳程序見[背景准入設計](../specs/2026-09-14-jd-background-admission-design.md)。

## 界線（這個決策明確不主張什麼）

- **不主張 LangGraph 無法保存狀態。**它保存的是各 workflow 自己的執行進度；「哪一段範圍被准入」不屬於任何一個 workflow 的執行進度，這是 App 的工作責任。
- **不主張任何外部規範要求這六個欄位。**六欄沿用本案已驗 `BackgroundRow` 的責任劃分。PostgreSQL 的 PK／FK／CHECK 適合表達「一文件一列」與有效狀態組合，但不決定表名、欄位數或產品流程。
- **十三張 JD 內容表不增減欄位。**但 App 的總表數確實從十三增為十四，README 與 runbook 如實寫明。
- **不保存第二份原話、Memory 或已整併游標。**`processed_source` 仍只在 publication。
- **不要求跨 Saver、Store 與此表的單一交易。**三者各自持久，恢復程序對帳。
- `running`／`idle` **不證明**模型執行過或發布成功；那由 Saver checkpoint 與 publication receipt 證明。
- 普通 open 只檢查已安裝；建表是明示 migration。**此表存在不代表 production authority 已切換**，也不代表日常 AI 已啟用。

## 後果

- 背景整理可以跨批次與跨程序重開保留「已准入到哪、卡在哪、為什麼」，不必掃 Store 猜測。
- App 多一張表與一條 migration；初始化腳本的預期表集合隨之更新，漂移會被既有檢查擋下。
- 若日後證明這些事實能由既有擁有者無歧義承載，此表應以 successor ADR 退役，不是靜默保留。

## 未決

- 多宿主同時存取此列的租用與競爭條件沿既有宿主所有權，本 ADR 不新增第二套 lease。
- 長訪談超過 256 祖先的限制沿 OI-05，不在此處理。
