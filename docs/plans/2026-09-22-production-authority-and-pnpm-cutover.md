# 新 JD App 正式權威、根目錄入口與 pnpm 切換計畫

2026-09-22；承接 Owner 已完成的新 App 元件、真 Luna、真 PostgreSQL 與瀏覽器驗收。本計畫只把已驗收產品變成 repo 的正式預設入口，不重新設計 A／B1／B2、Memory、compaction、JD 業務規則或資料庫。

## 目標與停止線

- `experiments/jd-relational-app` 保留原路徑與已驗證 import／證據，正式成為目前唯一 JD App authority；本輪不為目錄美觀搬檔。
- 根目錄採 Node.js 24 LTS、pnpm 12、TypeScript 與一份 active workspace lockfile；舊 `apps/api`／`apps/web` 不再是預設 workspace 或啟動目標。
- 根目錄 `pnpm dev`／`pnpm start` 以前景方式協調既有 API 與 Web。API origin 從既有受保護設定的非秘密投影取得，不猜 port、不讀密碼、不另存設定。
- Ctrl+C 由前景程序樹正常關閉；不保留舊 `kill-port`／PostgreSQL 16 自動啟動，不按端口終止未知程序。
- RAG 保留隔離、明示啟動；研究與封存資料內的歷史 lockfile／命令不改寫。
- Owner 後續明確裁決舊架構可淘汰，因此移除舊可執行程式與生成物；研究、設計、實驗、結果、歷史 README 與 Git 沿革保留。不搬舊資料，不新增 fallback、登入、ACL、雲端、多租戶或第二份 package／process manager。

## 施工順序

1. 以失敗測試固定安全 `api-origin` 投影：只有 ready 設定可輸出 loopback API origin，且不得輸出任何秘密。
2. 加入 `pnpm-workspace.yaml` 與 pnpm 12.5.1 精確 pin；active workspace 納入新 App／Web、共用 packages 與隔離 RAG 工具，排除舊 API／Web。
3. 將新 App package manifest 補為正式 operator scripts；根目錄加入單一 Node 前景協調器，供 `dev`／`start` 共用。它沿 `npm_execpath` 執行目前 pnpm 12，不依賴全機舊 pnpm 或 PowerShell 字元／續行解析。
4. 產生單一 `pnpm-lock.yaml`，移除 active npm lockfiles與 Turbo／kill-port 預設編排；封存證據不動。
5. 新增 successor ADR，更新 current register、README、runbook、repo map 與 current docs；歷史計畫／證據保留原文與順序。
6. 先做 pnpm frozen install／workspace scripts／launcher smoke，再跑新 App Python、Web、codegen、真 PostgreSQL與必要瀏覽器驗收。沒有新的付費模型缺口，不重跑 Luna。
7. 稽核秘密、大檔、署名與 diff；提交全部目前進度，整合最新 `origin/main`，再驗一次後 push、開 PR、等待檢查並 merge。

## 完成條件

- 根目錄不再啟動舊架構或 PostgreSQL 16；`pnpm dev`／`pnpm start` 只指向新 App。
- pnpm frozen install、Python／Web／codegen 及受影響真實接合檢查通過。
- 新 ADR Accepted，入口文件與程式一致；舊碼由 Git 歷史追溯，保留文件則明示歷史身分。
- Git 作者只使用 ArIs0x145；無 `.env`、credential、測試秘密或本機設定進入 commit。
- PR checks 通過後合併 `main`；若 GitHub 保護規則阻止合併，保留 PR 並回報確切 gate，不繞過。

## 2026-09-22 執行結果

- [ADR0077](../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md) 已 Accepted；根 README、runbook、repo 指引與 App README 已改指同一正式入口。
- `pnpm-workspace.yaml`、單一 `pnpm-lock.yaml`、Node `>=24.19.0 <25`、pnpm `12.5.1` 與 uv package build 已落地；frozen install 與 lockfile 完整性檢查通過。
- PowerShell 啟動器的首輪 parser／程序問題保留為失敗證據，最終以 Node 24 官方 `child_process.spawn` 的薄協調器取代；pnpm 官方多 filter＋`--parallel --stream` 負責兩個既有長程序，不另造 process manager。
- 根入口實際啟動 Node 24 的 Next 16.3.5 Web 與 Python API；Web `/`、API `/openapi.json` 均 HTTP 200，API 有 17 條正式路由，Ctrl+C 後 3002／8772 無殘留 listener。
- `pnpm check` exit 0：launcher 5 tests、Python 3,115 passed／322 skipped、Web 310 passed、TypeScript、codegen 與 production build 全數通過。未重送 Luna，零 provider request／零費用。
- 提交、push、PR 與 merge 仍是本計畫最後一個外部交付步驟；精確證據見[正式切換證據](../specs/evidence/2026-09-22-production-authority-and-pnpm-cutover.md)。
