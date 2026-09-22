# ADR0077：關聯式 JD App 正式權責與 pnpm 單一入口

**狀態：**Accepted（2026-09-22；Owner 核准硬切換，實作與驗收證據由本次交付補齊）。

## 脈絡

`experiments/jd-relational-app` 已完成關聯式 JD、同頁訪談、A／B1／B2／C、分層 Memory、App-side continuation compaction、OpenRouter／Luna、來源查看與本輪 JD 撤回的逐層實作及驗收。相較之下，根目錄仍把已退役的 `apps/api`、`apps/web`、PostgreSQL 16 Compose 與 npm／Turbo 指令呈現為正式入口，Accepted ADR0060 也仍是名義上的 production authority。

這造成兩個正式權責同時存在：GitHub 讀者與操作者可能啟動舊系統，後續實作者也可能依舊架構繼續施工。Owner 已明確決定不保留舊程式或舊資料相容性，應直接採用已驗證的新 App；研究、設計、實驗與結果文件則必須完整保留，以呈現專案迭代與問題解決過程。

Node.js 24 是 Active LTS 線；pnpm 12 是目前正式主線，workspace 以根目錄 `pnpm-workspace.yaml` 與單一 lockfile 管理。pnpm 的 Node 相容矩陣與 workspace 要求見[官方安裝文件](https://pnpm.io/installation)及[官方 workspace 文件](https://pnpm.io/workspaces)。

## 決策

### 1. 正式產品權責

- `experiments/jd-relational-app`、其 `web` 與 `packages/consultant-memory` 成為 Caliburn 唯一正式 JD App 實作。
- 目錄名稱保留是為了保留迭代路徑；是否日後搬移目錄只是機械重構，不影響正式性，也不是本次交付條件。
- 現有關聯式 JD、receipt、Saver／Store、Memory publication、A／B1／B2／C、Working State、來源回查、App-side compaction、OpenRouter／Luna 與 Windows 認證管理員權責全部沿用；本 ADR 不重新設計它們。
- `apps/api`、`apps/web` 與 `packages/job-analysis-contract` 的可執行程式、生成物和依賴檔退役並移除。其 README 與深文件只作歷史索引，不得再成為 production dependency 或啟動入口。

### 2. 資料切換

- 正式 JD App 只使用由其明示 `init` 建立並記錄的 PostgreSQL 18.6 空資料庫。
- 不搬移舊資料、不雙讀、不雙寫、不建立舊 schema adapter，也不自動刪除操作者機器上的舊資料庫或 volume。
- 根目錄 Compose 不再提供舊 PostgreSQL 16；只保留明示 profile 才會啟動的隔離 RAG 基礎服務。

### 3. Node／TypeScript workspace

- 正式基線為 Node.js `>=24.19.0 <25`、pnpm `12.5.1` 與 TypeScript；版本由根目錄 `package.json` 的 `engines`／`packageManager` 及 `pnpm-lock.yaml` 鎖定。
- 根目錄 `pnpm-workspace.yaml` 只列正式 JD App 與仍保留的隔離套件；整個 workspace 使用單一 `pnpm-lock.yaml`。
- npm lockfile、Turbo 任務圖與舊 workspace 定義退役；不提供 npm 相容命令。
- Python 仍由 uv 與 App 自己的 `uv.lock` 管理；不把 Python 依賴搬進 JavaScript package manager。

### 4. 唯一操作入口

- 根目錄 `pnpm dev`／`pnpm start` 是正式日常入口；API 與 Web 由同一個前景程序群組啟動，保留各自輸出並由 Ctrl+C 正常關閉。
- 啟動器只向既有安全設定讀取已核准的 loopback API origin，再投影成 Web 的 `JD_API_ORIGIN`；不讀出資料庫密碼或 OpenRouter key，不猜連接埠，也不另存第二份設定。
- 設定未完成或處於 maintenance 時 fail closed；不啟動半套服務。
- 不按端口終止程序、不自動 migration、不清資料、不重建 volume、不啟用 fallback provider。
- `pnpm app:init`、`app:resume-init`、`app:set-key`、`app:remove-key` 與 `app:status` 是根目錄管理入口；底層 uv 命令保留作診斷與恢復。

### 5. 文件與歷史

- `README.md`、`docs/runbook.md`、`docs/current-decisions.md`、ADR 索引及新 App README 必須指向同一正式入口。
- `docs/archive`、`docs/specs`、`docs/plans`、Accepted／Proposed／Rejected ADR、實驗案例與結果不得因硬切換刪除或改寫成當時不存在的結論。
- 舊目錄留下的文件必須醒目標示為歷史資料，避免與正式操作說明混淆。

## 取代範圍

- 本 ADR 是 ADR0074、ADR0075、ADR0076 所描述隔離 App 的採用 successor，將其已實作且通過 gate 的部分提升為正式產品權責。
- 本 ADR 取代 ADR0060、ADR0066、ADR0067、ADR0069 中仍把舊 `apps/api`／`apps/web` runtime 或舊工作稿形狀視為 production authority 的部分；其研究理由仍保留作歷史。
- ADR0057 的 RAG 隔離原則維持：RAG 不是目前 JD App 的預設依賴。
- 本 ADR 不翻案後續已確認的 Memory、compaction、引用、版本並行、JD 業務或安全收尾規則。

## 驗收條件

1. pnpm frozen install、唯一 lockfile 與 workspace 列表通過。
2. 新 App contract codegen、Python 測試、Web 測試、typecheck 與 production build 通過。
3. 根目錄管理命令能讀取既有設定；根目錄啟動器能啟動同一套 API／Web，並可正常停止。
4. repository 不再含舊 API／Web／舊 contract 的可執行 authority；歷史文件仍可由 GitHub 找到。
5. Git 差異檢查、秘密與生成物檢查通過後才提交、推送及合併。

## 後果

- 操作者與實作者只有一條正式路徑，不再因舊入口造成分流。
- 不承擔舊資料與舊 API 的相容成本；需要舊內容時只能從 Git 歷史與保留文件查閱。
- `experiments` 路徑名稱暫時看似特殊，但文件、ADR、根入口與測試都明確宣告正式性；避免為了改名製造大範圍低價值 diff。
- RAG 仍可獨立研究或啟動，但不能成為 JD App 的隱含必要服務。
