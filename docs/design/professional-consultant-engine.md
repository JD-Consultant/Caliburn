---
title: 專業顧問引擎與 current-row JD — production 切換邊界
audience: agent-primary（也給人）
status: R0 architecture lock；新 production route 尚未實作
updated: 2026-08-02
---

# 專業顧問引擎與 current-row JD — production 切換邊界

> **目前沒有新專業顧問 route／Web seam。** `apps/api/app/api/router.py` 未掛 `interview_vnext`、
> `job_authoring` 或 `local_workspace`。本文件在 R0 只記錄真實現況、未來切換不變量與退役 gate；
> 不得把「PLANNED」內容當成已存在的端點。決策見 [ADR 0041](../adr/0041-document-boundary-single-writer-cutover.md)。

## 1. 目前可達的正式路徑（ACTIVE／TRANSITIONAL）

```text
Web /documents/[id]/interview
  -> POST /api/v1/job-profiles/{profile_id}/interview:turn
  -> app/interview
  -> op -> verify -> DocumentVersion.content._pending
  -> Web accept/reject helper
  -> PATCH /api/v1/job-profiles/{profile_id}/document
```

這條線仍承接現在的使用者流量，但只允許 maintenance。完整現行行為見
[訪談引擎 v3 設計](interview-engine.md)；它不是新顧問引擎的 domain 或 persistence authority。

## 2. 程式區域狀態

| 區域 | 狀態 | 可以做什麼 | 禁止 |
|---|---|---|---|
| `app/interview` | ACTIVE／TRANSITIONAL | 修阻斷、資料損毀、安全缺陷 | 新增新顧問 operation、擴充 `_pending` |
| `DocumentVersion.content` | ACTIVE／TRANSITIONAL | 保存既有 OCS editor 文件 | 成為新文件 authority、與 current rows dual-write |
| `app/interview_vnext` | ISOLATED PROTOTYPE／DONOR | 依 ADR 0040 逐項評估 provider、Capture、checkpoint 等基礎 | 直接掛 router；重用舊 gold/schema/operation/state |
| `app/job_authoring` v1 | ISOLATED PROTOTYPE | 保留既有測試與三表，不擴張 | 新增 revision-scoped entity；讓 `snapshot_json` 成為 v2 truth |
| current-row Authoring v2 | PLANNED／NOT IMPLEMENTED | 後續依核准 storage research 實作 | R0 建表、假裝 route 已存在 |
| 新 professional consultant | PLANNED／NOT IMPLEMENTED | R1 起依 ADR 0040 greenfield 驗證 | import/wrap v3；直接 promotion 現有 vNext loop |
| `local_workspace` seam | PLANNED／NOT IMPLEMENTED | R1–R5 過 gate 後組合第一條 production vertical | 在 R0 發明 request／response 或 route |

## 3. 第一條 production vertical（PV1，PLANNED）

PV1 的 outcome 已固定，介面尚未建立：

```text
建立新 JD
  -> 開始／恢復訪談
  -> 員工送出一段工作故事
  -> 保存 Source／Work Current State
  -> 回覆下一題
  -> 支持度足夠時建立 Task proposal
  -> 員工 accept／edit-accept／reject
  -> Current JD + proposal decision + Consultation Journal 同 transaction
  -> 關閉／重啟／重開仍一致
```

PV1 不含公版 reference challenger、完整 O/P/K/S/A 品質宣稱、完成判斷或正式匯出；這些分別由 R6／R7 gate 承擔。
PV1 只有在 R1–R5 gate 通過、實際 route 與 generated contract 落地後才可改標 ACTIVE。

## 4. 文件 ownership 與寫入不變量

1. 切換單位是整份 `document_id`；同一文件同一時間只有一個 writer generation。
2. legacy 文件只寫 `DocumentVersion.content`；新文件只寫 current-row Authoring。
3. AI output 只能建立 proposal；模型不能產生 application UUID，也不能直接更新 Current JD。
4. accept／edit-accept 才能修改 Current JD；reject 不修改；target 已變更時 proposal 必須 stale。
5. Current State、proposal decision 與 Consultation Journal 在同一 PostgreSQL transaction 寫入。
6. Journal 是歷史／診斷紀錄，不負責 replay 重建 Current State。
7. OCS JSON 是 import/export projection；不得回到 live workspace persistence。
8. Indexer 是 reference knowledge；不得把 reference candidate 當 employee Evidence 或直接寫正式 JD。

## 5. 切換流程

```text
R0 architecture lock
  -> R1 Task Discovery gate
  -> R2 multi-turn gate
  -> R3 resume/context-state gate
  -> R4 Duty + O/P/K/S/A gate
  -> R5 proposal/current-JD gate
  -> PV1 contract + API + Web + real-PG vertical
  -> 新文件切新 writer
  -> legacy inventory／必要時逐文件單向匯入
  -> legacy_documents_remaining = 0
  -> 移除舊 Web 寫入與 route
  -> 移除舊 domain/prototype code
  -> 獨立 migration 刪 legacy tables
```

不得跳過中間 gate，亦不得把 route cutover、code deletion、table deletion 合成一次 big-bang 變更。

## 6. 資料遷移與 rollback

- inventory 是 read-only；先判斷有沒有需保存的本機 JD。
- 可重建資料直接重建；需保存資料逐 document transaction 匯入並產 reconciliation report。
- mapping 不完整時不切 ownership，舊資料保持可讀寫；禁止靜默丟欄位。
- coexist 期間 legacy document 可繼續走舊 route；新 document 永不倒灌 `_pending`。
- LLM 失效時，新 workspace 以 direct edit／resume 降級；不以舊引擎接管新 document。
- legacy table 只在新 route 穩定、需保留資料完成切換且 owner 核准後，由獨立 migration 刪除。

## 7. 契約邊界

PLANNED `local_workspace` 是 Python／TypeScript seam，因此依 `docs/contract-strategy.md` 使用獨立 JSON Schema SSOT，
生成 Pydantic 與 TypeScript。它與 `ocs-contract` 平行：

```text
local-workspace-contract = 對話、Current Work／JD view、proposal decision 的 live contract
ocs-contract             = PDF ingest／OCS import/export contract
indexer-contract         = API 與 indexer 的 Python query contract
```

任何實作 commit 必須把本節替換成真實 package、schema ID、route、request、response、錯誤碼與 transaction；
在那之前不得建立手寫 TS DTO 假裝契約已定。

## 8. 退役禁令

- 不把 `turn.interpret`／`question.select`／舊 Evidence shape 改名後當新 R1。
- 不 import/wrap `app.interview.consultant`、`scribe`、`harvest`、`select`。
- 不擴充 `_pending`、`DocumentVersion.content`、`snapshot_json` 或 revision entity。
- 不做同文件 dual-write、雙向同步或自動 reverse migration。
- 不為切換新增登入、tenant product behavior、organization、ACL、雲端 gateway、message bus 或 Graph framework。
- 不在沒有 inventory、備份與 owner 核准時刪 legacy data/table。

## 9. 指路

- 產品範圍：[`../product-notes.md`](../product-notes.md)
- 顧問核心決策：[`../adr/0040-professional-consultant-engine-and-r1-validation-contract.md`](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)
- 切換決策：[`../adr/0041-document-boundary-single-writer-cutover.md`](../adr/0041-document-boundary-single-writer-cutover.md)
- current-row storage：[`../specs/2026-07-24-job-authoring-v2-relational-storage-research.md`](../specs/2026-07-24-job-authoring-v2-relational-storage-research.md)
- R0 研究：[`../specs/2026-08-02-r0-architecture-truth-and-production-cutover-research.md`](../specs/2026-08-02-r0-architecture-truth-and-production-cutover-research.md)
- R0／PV1 plan：[`../plans/2026-08-02-professional-consultant-production-cutover-plan.md`](../plans/2026-08-02-professional-consultant-production-cutover-plan.md)
