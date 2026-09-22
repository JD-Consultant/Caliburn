# 0054. 以文件為邊界的單寫者切換與舊著作路徑退役

- 狀態：**Accepted**（owner 於 2026-08-02 指示執行 R0 架構真相校正與第一條 production vertical 切換／退役設計）
- 編號說明：本 ADR 原以 `0041` 起草於離線分支，合併回 `main` 時該編號已由另一條線的[0041-r1-p0-closure-first-version-context-and-holdout](0041-r1-p0-closure-first-version-context-and-holdout.md) 佔用，故發布為 `0054`。決策內容未更動。
- 日期：2026-08-02
- 範圍：現行 v3、新專業顧問引擎、current-row Authoring、本機 Web 的 coexist、cutover、rollback 與 retirement
- 延伸：[0040](0040-professional-consultant-engine-and-r1-validation-contract.md)
- 研究：[R0 架構真相與 production cutover](../specs/2026-08-02-r0-architecture-truth-and-production-cutover-research.md)

## 脈絡

正式 router／Web 目前仍以 `job_profile`、`DocumentVersion.content`、`app/interview` v3 與 `_pending` 為可寫真相；
`app/interview_vnext` 和 revision-based `app/job_authoring` v1 雖有大量已測程式，皆未掛 composition root，且 ADR 0040
已明定它們不是新專業顧問引擎的前提。產品目標則是本機單一操作者、current-row relational JD、AI proposal 與員工決策。

若把新引擎直接接到舊 OCS editor，或讓 OCS JSON、revision snapshot 與 current rows 長期 dual-write，系統會有多份可寫真相，
且 Evidence、Task linkage、proposal stale 與 `_pending` 無法可靠雙向映射。另一方面，在 R1–R5 gate 之前刪除現行 v3，會失去唯一可操作產品與 rollback。

## 決定

1. 採漸進替換，但切換單位是整份 `document_id`。同一文件同一時間只有一個 writer generation；
   不做欄位級、operation 級或同文件 dual-write。
2. 現行 `app/interview` + `DocumentVersion.content` 在第一條新 production vertical 前維持使用者路徑，
   但進入 maintenance-only：只修安全、資料損毀與阻斷性缺陷，不新增產品能力。
3. `app/interview_vnext` 與 `app/job_authoring` v1 都是隔離 prototype／donor，不直接 promotion：
   只有重新符合 ADR 0040 operation、rubric、state 與 current-row authority 的元件才可明確搬入新路徑。
4. 第一條 production vertical（PV1）固定為：建立新 JD → 一段員工工作故事 → 新顧問保存 Source／Work Current State並回下一題
   → 有支持時建立 Task proposal → 員工 accept／edit-accept／reject → 同交易更新 Current JD、proposal 與 Consultation Journal
   → restart 後精確重開。PV1 須先通過 R1–R5 exit gates。
5. PV1 透過新的 `local_workspace` application seam 組合 domain；route 不得直接組合 prototype repository，Web 不得讀 provider、artifact、
   Qdrant point、`DocumentVersion` 或 `_pending`。
6. Python／TypeScript seam 依契約判準使用獨立 JSON Schema SSOT 與生成的 Pydantic／TypeScript；
   `ocs-contract` 僅為 import/export shape，不是 live workspace truth。
7. 新文件只寫 current-row tables。舊文件在明確匯入前仍由 legacy writer 擁有；匯入採逐文件單向 transaction 與 reconciliation report。
   資料可重建時直接一次切換；有需保留資料時保留舊 OCS JSON 唯讀備查。禁止長期 dual-write、雙向同步與靜默 reverse migration。
8. coexist rollback 只在文件所有權邊界切換：legacy 文件可回舊 route；新文件保留在新 writer，LLM 故障時以 direct edit／resume 降級，
   不倒灌 `_pending`。
9. 退役必須按順序分 task：
   - 新文件建立流切到 PV1；
   - 完成需保留 legacy 文件的 inventory／匯入，`legacy_documents_remaining = 0`；
   - 移除舊 Web 導航與寫 route；
   - 移除 v3 與不再承重的 prototype code；
   - 最後以獨立 migration 刪除 legacy tables。
   route cutover、code deletion、table deletion 不得塞進同一 commit。
10. `docs/design/professional-consultant-engine.md` 在沒有新 route 的 R0 階段必須明寫「尚未實作」；
    之後每條真實 route、contract、transaction 與錯誤路徑跟碼同 commit 更新。不得把研究中的預想 API 寫成已存在。

## 後果

### 正面

- 每份文件的 authority 與 rollback 都可判定，不需要同步三套資料模型。
- 現行產品可維持可用，同時不再吸收新產品需求。
- 新引擎的 Source／Work／Document 邊界不受 OCS deep JSON、`_pending` 或 revision snapshot 污染。
- legacy 刪除有可驗證 gate，不會因「新碼存在」就過早拆除，也不會讓 coexist 永久化。

### 負面與成本

- 過渡期 repo 仍保留兩個使用者路徑，orientation 與 route ownership 必須持續清楚標示。
- 若有需保留的舊 JD，要增加一次性 importer、reconciliation report 與唯讀保留期。
- PV1 必須等待 R1–R5 品質 gate，不能用先接 UI 取代 domain 驗證。

### 禁令與未決

- 不新增 SaaS、登入、organization/member/ACL、雲端 gateway 或訊息匯流排來實作此切換。
- R0 不決定 PV1 的確切 HTTP payload；該形狀由後續 contract research／plan 與生成契約固定。
- 實作前的 read-only inventory 才能決定「重建資料」或「單向匯入」，不得在沒有盤點時刪資料。
