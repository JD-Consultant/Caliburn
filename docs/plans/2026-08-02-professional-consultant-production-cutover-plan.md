# 專業顧問第一條 production vertical：切換與退役計畫

- 日期：2026-08-02
- 狀態：R0 accepted；P1–P8 是後續施工順序，尚未授權實作，且須等待 R1–R5 gate
- 決策：[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)、
  [ADR 0041](../adr/0041-document-boundary-single-writer-cutover.md)、
  [ADR 0042](../adr/0042-hybrid-job-discovery-and-ttop-formation.md)、
  [ADR 0043](../adr/0043-real-employee-pilot-release-gate.md)
- 研究：[R0 架構真相與 production cutover](../specs/2026-08-02-r0-architecture-truth-and-production-cutover-research.md)

## 1. 交付目標

在不擴建現行 v3、不 dual-write 同一文件的前提下，交付第一條新 production vertical（PV1）：
建立新 JD、送出一段工作故事、得到下一題、建立具支持的 Task proposal、由員工決策、重啟後精確重開。
完成資料 inventory／必要匯入後，依 gate 退役舊 Web 寫入、route、domain 與 tables。
本計畫 P1–P8 與 technical cutover 完成後只形成 release candidate；第一版要稱為員工可用成品，仍須執行並通過另案核准的
R9 真實員工 pilot。高擬真 transcript、合成 eval 或內部自測不得替代。

## 2. 前置 gate

本計畫的 P1 以前不得開始 PV1 product wiring：

- ADR 0040 R1 Task Discovery exit gate 已通過並有固定 trial manifest／報告。
- R1 依 ADR 0042 驗證混合式職務發現中的 Task Discovery；暫定 Duty／reference 只作假說與補漏，不作文件真相。
- R2 multi-turn、R3 resume/context state、R4 Duty + O/P/K/S/A、R5 proposal/current-JD 各有自己的 plan、測試與完成 tag。
- `JobDocumentDraft.v2` 與 current-row storage 已有獨立 contract research、ADR／amendment、migration plan。
- `git status --short` 乾淨；baseline tests 記錄在開始實作的 plan execution section。

未通過任一項時，只能修該 gate，不能以 stub route 或舊 vNext loop 假裝 PV1。

## 3. Task 切片

### P0 — R0 architecture lock（本 task）

變更：

- 新增 R0 research、ADR 0041、本 plan、`docs/design/professional-consultant-engine.md`。
- 校正 `ARCHITECTURE.md`、ADR／docs/design 索引與會誤導實作者的 AGENTS／README。
- 明標現行 route、隔離 prototype、target、retirement gate。

驗證：

- Markdown links 指向存在檔案。
- `rg` 不再在 active orientation 中把 ADR 0038 稱為 post-R5 authority，或把「接 Web」稱為下一步。
- production router 仍無 vNext／job_authoring／local_workspace import。
- full no-network safety net green-before == green-after；本 task 不改 runtime。

提交：一個 docs task commit，tag `r0-architecture-truth`。

### P1 — PV1 cross-language contract

前置：R1–R5 gate 全通過。

變更：

- 依 `docs/contract-strategy.md` 開 contract research 與 ADR。
- 建立 `packages/local-workspace-contract` JSON Schema SSOT。
- 只定義 PV1 所需 document summary／workspace view／answer／direct edit／proposal decision／typed error。
- 生成 Pydantic 與 TypeScript，加入 regen + diff guard。

驗證：codegen zero-diff、Python/TS compile、schema examples valid。不得引用 OCS document、provider artifact 或 tenant UI DTO。

### P2 — current-row persistence vertical

變更：

- 依 v2 storage authority 建 additive migration、ORM、repository/UoW。
- Current State 與 Consultation Journal 同 transaction；proposal accept/edit/reject/stale 與 current rows 原子更新。
- legacy 0011 revision tables 保留但不再由新 service 寫入。

最低 real-PostgreSQL tests：

- 跨 document FK/linkage 拒絕。
- 顯示排序不改 UUID。
- reject 不改 current rows；accept/edit-accept 會改；stale 不覆蓋。
- transaction 失敗時 Current State、proposal、Journal 全回滾。
- 關閉／重開後狀態與 linkage 一致。

### P3 — `local_workspace` application seam

變更：

- 建立薄 application service，組合已通過 gate 的 consultant、Authoring、knowledge port 與 UoW。
- application command 擁有 UUID／idempotency；provider result 不穿越 seam。
- 不 import `app.interview`；不讀寫 `DocumentVersion` 或 `_pending`。

驗證：scripted no-network vertical 跑完整 PV1；重送同 command 不重複寫入；stale command typed conflict。

### P4 — FastAPI composition 與 route

變更：

- 在唯一 `app/api/router.py` 掛 PV1 router。
- request／response 只使用 generated contract adapter。
- dependency wiring 只在 composition root；新 route 不接 legacy `profile_id` ownership。
- `docs/design/professional-consultant-engine.md` 同 commit 更新真實 route、錯誤碼與 transaction。

驗證：API contract tests、real-PG vertical、OpenAPI snapshot／codegen guard；現行 legacy route characterization 仍綠。

### P5 — 最小本機 Web

變更：

- 新文件建立與 workspace page 只呼叫 PV1 API。
- 同畫面顯示 conversation、Current JD Task canvas、proposal before/after 與 accept/edit/reject。
- 一次只開一份文件；不顯示 user/profile/tenant/host/port。
- 不重用 OCS cache-as-state、`_pending` helper 或手寫 API DTO。

驗證：Vitest interaction、`npx tsc --noEmit`、lint；瀏覽器操作證明 create→answer→decision→reload。

### P6 — read-only inventory 與可選單向 importer

先執行 inventory：列出 legacy document 數量、status、可驗證性與是否需保存，不修改 DB。

- 若資料全可重建：記錄 owner 決定，跳過 importer。
- 若有需保存資料：另開 task 建逐 document importer、dry-run、reconciliation report 與 transaction rollback。
- importer 成功前不得改 writer ownership；不得靜默丟棄 unknown／unmapped 欄位。

驗證：fixture covering exact／partial／invalid mapping；原始 OCS JSON 在匯入後保持 byte-readable。

### P7 — 新文件 cutover

變更：

- 預設「建立新 JD」只建立 current-row document。
- legacy 文件入口保持但標示 transitional；新文件無法被舊 editor 開啟或寫入。
- 產出 `legacy_documents_remaining` 的 deterministic inventory 結果。

驗證：clean install、已有 legacy DB、restart 三條 golden；rollback 不更改新文件 authority。

### P8 — 舊路徑退役（至少三個獨立 task）

只有 `legacy_documents_remaining = 0` 且 owner 接受 PV1 操作結果後才開始：

1. 移除舊 Web 導航與 `DocumentVersion`／`_pending` 寫入 client；保留必要唯讀匯出。
2. 移除 legacy API routes、`app/interview` 與不再承重的 prototype；更新 composition／docs／tests。
3. 下一個 tagged release 後，以獨立 Alembic migration 刪除 legacy tables；執行前再次備份並列 exact table targets。

每一步 green-before == green-after、單 task 單 commit、各自可回復。不得在 code deletion task 順便 drop data。

## 4. 停線條件

出現任一項立即停止當前切片並回到研究／ADR：

- 同一 document 需要同時寫 OCS JSON 與 current rows 才能工作。
- 新 domain 必須 import v3 consultant/scribe/harvest/select 或舊 vNext operation/state。
- Web 必須讀 provider payload、ORM row、artifact 或 raw domain JSON。
- proposal 可在未經員工決策時修改 Current JD。
- mapping 只能靠靜默丟欄位才能完成。
- 為完成本機切換需要登入、SaaS、organization、ACL、message bus、Graph runtime 或新服務。
- R1–R5 任一 gate 失敗或只是與 baseline 持平。

## 5. 最終驗收

本節驗收的是 production vertical 與 technical cutover，不是第一版產品 release gate。

- PV1 可從一鍵本機啟動流程操作，不要求員工設定 host／port。
- create→answer→proposal→decision→restart→reload 端到端通過。
- Current JD 是唯一可寫文件真相；OCS 只由 projector 匯出。
- 每筆採用內容有合法 support／Evidence linkage；reference candidate 不冒充 employee Evidence。
- legacy inventory 為零後，舊寫路徑與 `_pending` 已移除；legacy tables 的刪除有獨立 migration、備份與 tag。
- living design 只描述真實存在的 route／contract／transaction／錯誤路徑，沒有預想 API。
- 產物標示為 release candidate；只有 ADR 0043 的 R9 真實員工 pilot 通過後，才改稱第一個員工可用成品。

## 6. R0 執行證據（2026-08-02）

- 本機 Markdown links：`LOCAL_MARKDOWN_LINKS_OK`。
- orientation stale phrase guard：通過；正式 router 對 `interview_vnext`／`job_authoring`／`local_workspace` 仍為零 import。
- `git diff --check`、trailing-whitespace、tracked runtime diff：通過；本 task 只有 Markdown 變更。
- `npx.cmd turbo test`：OCS contract build、Web `67 passed`、pdf-to-json `23 passed`、ocs-indexer `53 passed`；
  API `1163 passed / 218 skipped / 5 failed`。五個失敗全是既有 historical JSON frozen-byte hash assertion；
  逐檔比較證明 worktree bytes 與 `HEAD` blob 完全相同，而 `HEAD` 本身的 SHA-256 已不等於測試中的 expected hash。
  因此這是本 task 前已存在的 baseline mismatch，不由 R0 文件變更造成；本 task 不越界修改 frozen schema 或測試常數。
