# ADR 0001 — Monorepo（Turborepo + per-app uv），非 polyrepo

- **狀態**:Accepted（2026-06-27;Phase 1 已實作,tag `phase1-monorepo`）

## 脈絡

原本三個獨立 repo(`jobintel-ai`、`jd-ocs-indexer`、`jd-pdf-to-json`)共用 OCS JSON 契約,但契約只是 prose + 各自重編 → 飄移 bug(D29 `job_categories` 掉值)。跨 repo 改契約要多 PR、版本對不齊。開發者=單人。

## 決定

合併成一個 monorepo(`caliburn/`),用 **`git subtree`**(保留各 repo 完整歷史)併入 `apps/`。
- **Turborepo** 做任務編排(affected-only build/test/lint)。
- **npm workspaces**(非 pnpm —— 既有前端已用 npm,避免多裝全域工具)。
- **per-app uv** 管 Python 依賴(見 ADR 0005)。
- **不走 polyrepo**:三者由同一人擁有、互相消費、無對外發佈/合規隔離需求,沒有分 repo 的理由。

## 後果

- ✅ 原子化跨切變更(一個 PR 改契約+生產者+消費者);一次 clone;affected-only 仍保獨立部署。
- ✅ 三 repo git 歷史保留(subtree,非 squash)。
- ⚠️ 多學 Turborepo + npm workspaces 概念。
- ⚠️ subtree 舊 commit 保留原始路徑,`git log -- 新路徑` 追不到搬移前(歷史仍在圖中)。
- 🔁 日後若某塊需「不同人管 / 對外獨立發佈 / 合規隔離」,可再從 monorepo 抽成獨立 repo。

依據:Martin Fowler、Sam Newman、Google ACM monorepo 論文、LangChain.js(pnpm+turborepo)。
