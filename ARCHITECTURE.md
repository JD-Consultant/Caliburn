# Caliburn 架構

> 正式架構與職責以 [ADR0079](docs/adr/0079-target-rebuild-production-cutover.md)、
> [目前決策](docs/current-decisions.md)與各專題設計文件為準。本頁提供整體概覽，詳細規則見各專題；
> 全產品設計入口見[目標架構地圖](docs/target-architecture-map.md)。

Caliburn 是在本機執行的 Web AI 職務分析與職務說明書（JD）應用程式。員工可直接編輯 JD，也可與顧問持續訪談，
由 AI 依照與人工編輯相同的業務規則讀寫 JD。單一操作者可管理多份資料彼此隔離的職務檔案；目前不提供登入、
存取控制清單（ACL）、多租戶、計費、雲端部署或多人協作，服務僅綁定本機回環位址（loopback）。

## 組成

```text
瀏覽器（React／MUI，建置後由後端同源提供）
        │ HTTP／SSE（同源；精確 Host／Origin 檢查）
        ▼
FastAPI 單程序（apps/api，loopback :8100）
  transport     HTTP routers／DTO；模型工具的薄入口
  agents        A 顧問、B1 情境整理、B2 工作理解（prompt、允許的工具、起始 context）
  workflows     跨領域用例：訪談輸入、JD 讀寫、Memory 批次、PDF、撤回
  agent_execution  共用的原生模型／工具迴圈、Step 恢復、暫停／取消、compaction
  features      領域與其 SQL：職務檔案、訪談、JD、Memory、執行資格與額度
  adapters      OpenAI Responses（直連 SDK）、LangGraph 官方 PostgreSQL saver、PDF renderer
        │                     │
        ▼                     ▼
PostgreSQL 18.6          OpenAI Responses API（經授權的工作資料；store=false）
  關聯式 JD／訪談／Memory／執行資格
  LangGraph checkpoint（原生接續歷史）
```

程式位於 `apps/api`（後端）與 `apps/web`（介面）；層次與依賴方向、命名與寫法見
[程式組織](docs/implementation/code-organization.md)與[程式撰寫規範](docs/implementation/coding-standard.md)，
各層的依賴方向由測試檢查。

## 權責不變量

- PostgreSQL 的關聯式資料表保存正式資料；LangGraph checkpoint 只保存模型接續位置，不取代正式業務結果；Web 不另存一份正式 JD，也不重新計算領域規則。
- 人工編輯與模型工具可使用不同入口，但都經過同一個 JD 服務，遵循相同的驗證、版本與保存規則；候選（模型本輪的改動）在 Turn 完整成功前不成為正式 JD。
- 原始訪談完整保存，可供引用與回查；工作情境與理解（Memory）由背景 B1／B2 分層整理，再發布為不可變快照。上下文壓縮只管理模型接續資料，不能取代原話或 Memory。
- 文件、版本、資料範圍、引用解析與寫入條件由 App 管理，不要求模型自行生成或猜測；訪談、Memory、JD 與工具回傳的文字一律視為資料，不能改變指令或權限。
- `request_memory_consolidation` 是非等待式要求。現行機制在背景整理最終失敗後，須讓訪談再前進三輪才允許一次新批次；這項政策仍待確認，A 不因 Memory 失敗而停用。
- 本輪 JD 撤回只撤回該輪 JD 的效果，不撤回原始訪談、來源或 Memory。
- OpenAI 金鑰僅供後端使用，不放入提示、工具、Web 建置檔、URL、紀錄或資料庫；未設定金鑰時，人工 JD 編輯仍可使用，AI 功能則明確顯示為停用。

詳細責任見[系統責任與資料流](docs/architecture/system-boundaries.md)、
[資料責任與交易](docs/architecture/persistence.md)、
[共用執行](docs/specs/2026-09-27-shared-agent-execution-and-state-design.md)及
[操作手冊](docs/runbook.md)。

## RAG（保留、隔離）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract` 與
`packages/indexer-contract` 構成可獨立執行的 RAG 領域，目前未供正式 JD 應用程式使用。
僅透過 `pnpm rag:*` 明確啟動；詳見 [RAG 設計](docs/design/rag-pipeline.md)。
