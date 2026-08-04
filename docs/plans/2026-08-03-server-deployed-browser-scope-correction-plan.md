# 伺服器部署、瀏覽器存取產品範圍校正計畫

- 日期：2026-08-03
- 狀態：已完成
- 決策：[ADR 0057](../adr/0057-server-deployed-browser-product.md)
- 研究：[部署範圍校正](../specs/2026-08-03-server-deployed-browser-product-scope-research.md)

## Task 1 — 鎖定決策與語言

- 新增研究紀錄與 ADR 0057。
- 在 `CONTEXT-MAP.md` 定義 deployment、企業自管部署、我們代管部署與瀏覽器使用者。
- ADR 索引標示 0039／0041／0043 的部署字句由 0044 部分取代。

驗證：新 ADR 編號唯一；Accepted ADR 內容無修改；glossary 不含實作細節。

## Task 2 — 校正 active authority

- 更新 `AGENTS.md`、`ARCHITECTURE.md`、`docs/product-notes.md`、`docs/README.md`。
- 更新 `docs/design/professional-consultant-engine.md` 與 active R0–R9 roadmap。
- `local_workspace`／`local-workspace-contract` 規劃名稱改為 `job_workspace`／`job-workspace-contract`。
- 更新 `interview_vnext`、`job_authoring` 的局部 agent rules。

驗證：active orientation 不再宣稱服務在員工電腦運行，也不把「禁止共享 SaaS」誤寫成「禁止 server deployment」。

## Task 3 — 校正交付與維運路線

- 將 R8 改為 server-deployed browser release candidate。
- 更新 production cutover P5 與 final acceptance。
- 將 runbook 的舊 Pool + RLS SaaS 部署段改成 development／enterprise-managed／provider-managed 三個 profile，
  並明標 production Compose 尚未實作。

驗證：開發用 localhost 指令保留；產品使用者不再被要求啟停服務或設定 host／port；正式 exposure 受 access-policy gate 阻擋。

## Task 4 — 一致性與收尾

- 檢查 Markdown links、`git diff --check` 與 active-scope phrase guard。
- 本 task 不改 runtime；確認 tracked runtime diff 為零。
- 一個 docs commit，完成後打 tag；不 push。

## 執行證據

- `git diff --check`：通過。
- Changed Markdown local links：通過。
- Active-scope phrase guard：不再出現把產品定義為員工電腦執行或把 planned seam 稱為 `local_workspace` 的敘述。
- Tracked runtime diff：零；本 task 只改 Markdown authority／orientation。
- Accepted ADR 0039／0054／0056 原文未修改；由 ADR 0057 與索引記錄 partial supersession。
