# Caliburn — agent orientation

Caliburn 是給員工使用的**本機 Web AI 職務分析與職務說明書應用程式**。目前只保留新的 Job Analysis 系統：本機單一操作者、可保存多份彼此隔離的職務說明書，不做登入、帳密、多租戶、organization/member/ACL、計費、雲端部署或多人協作。維護者使用繁體中文，回覆也用繁中。

`AGENTS.md` 與 `docs/` 是本 repo 權威；`CLAUDE.md` 只 import 本檔。若歷史文檔與本檔衝突，以現行 code、current-only ADR 0057 與本檔為準。

## 工作紀律

1. 重大變更先研究，將來源、診斷、選項與取捨寫入 `docs/specs/<date>-*.md`。
2. 架構決策寫 Nygard 式 ADR，預設 `Proposed`，並更新 `docs/adr/README.md`；翻案開新號。
3. 多步變更先寫 `docs/plans/`，拆成可獨立驗證的工作。
4. 保留測試作安全網；綠燈後一個 task 一個 commit，收尾建立本地 tag。
5. 新 API／共用格式依 [`docs/contract-strategy.md`](docs/contract-strategy.md) 選契約機制。
6. 不 push、不做對外動作，除非 owner 明確要求。
7. 改跨 app seam 或子系統時，同 commit 更新對應 `docs/design/` 或 app README。

## 現行架構

- Monorepo 只有 `apps/api`、`apps/web` 與 `packages/job-analysis-contract`；PostgreSQL 是唯一 Docker 基礎服務。
- API 的 Job Analysis 是唯一 production AI 工作面：`domain` → `application` → `llm/providers`，資料庫邊界在 `app/adapters/job_analysis_postgres`，HTTP 組裝在 `app/api`。
- Web 只提供 `/workspace` 與文件詳情頁，吃 `job-analysis-contract` 生成的 TypeScript 契約。
- 新資料從 current-only migration 0012–0017 建立，舊資料不搬移、不雙寫、不相容。若需開發環境，直接依 runbook 重建資料庫。
- 已刪除的 `app.interview`、`app.interview_vnext`、`app.job_authoring`、OCS／indexer／embedder／PDF ETL 不得重新 import、wrapper 或接回 production。

## 本地開發與驗證

```text
npm install
npm run up              # PostgreSQL + API/Web dev
npm run db:migrate      # apps/api Alembic head
npx turbo test
```

API：`cd apps/api && uv sync && uv run pytest -q`。Web：`cd apps/web && npm run test && npx tsc --noEmit && npm run lint`。改契約後執行 `npm run check-codegen -w @caliburn/job-analysis-contract`。

Windows 上動手前確認 `pwd` 與 `git branch --show-current`；後端 reload 已關閉，改碼要重啟。`uv` 環境不用 pip；CJK 指令設定 `PYTHONUTF8=1`。

## 指路

[`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/README.md`](docs/README.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/runbook.md`](docs/runbook.md) · [`docs/design/task-analysis-engine.md`](docs/design/task-analysis-engine.md) · [`docs/adr/0057-current-only-runtime-and-data-boundary.md`](docs/adr/0057-current-only-runtime-and-data-boundary.md)
