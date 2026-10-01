# Caliburn 架構

> 正式權責以 [ADR0079](docs/adr/0079-target-rebuild-production-cutover.md)、
> [目前決策](docs/current-decisions.md)與各責任設計文件為準。本頁只提供鳥瞰，不複製完整規則；
> 全產品設計入口見[目標架構地圖](docs/target-architecture-map.md)。

Caliburn 是本機 Web AI 職務分析與職務說明書（JD）App。員工可直接編輯 JD，也可與顧問持續訪談，
由 AI 透過與人工相同的 App 業務規則讀寫 JD。單一操作者可管理多份彼此隔離的職務檔案；目前沒有登入、
ACL、多租戶、計費、雲端部署或多人協作，只綁定 loopback。

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
其中的層方向由測試鎖定。

## 權責不變量

- PostgreSQL 的關聯式表是正式資料 owner；LangGraph checkpoint 只保存模型接續位置，不充當正式業務結果；Web 不保存第二份正式 JD，也不重算領域規則。
- 人工編輯與模型工具可使用不同入口，但經過同一套 JD service、驗證、版本與保存規則；候選（模型本輪的改動）在 Turn 完整成功前不成為正式 JD。
- 原始訪談完整保存並可引用回查；工作情境與理解（Memory）由背景 B1／B2 分層整理並發布為不可變快照。compaction 只管理模型接續 context，不能取代原話或 Memory。
- 文件、版本、scope、引用解析與寫入條件由 App 管理，不要求模型自行生成或猜測；訪談、Memory、JD 與工具回傳的文字一律作資料，不能改指令或權限。
- `request_memory_consolidation` 是非等待式要求；背景整理最終失敗後，訪談再前進三輪才允許一次新批次，A 不因 Memory 失敗而停用。
- 本輪 JD 撤回只撤回該輪 JD 的效果，不撤回原始訪談、來源或 Memory。
- OpenAI key 只在後端使用，不進 prompt、工具、Web bundle、URL、log 或資料庫；沒有 key 時人工 JD 仍可使用，AI 明示停用。

詳細責任見[系統責任與資料流](docs/architecture/system-boundaries.md)、
[資料責任與交易](docs/architecture/persistence.md)、
[共用執行](docs/specs/2026-09-27-shared-agent-execution-and-state-design.md)及
[runbook](docs/runbook.md)。

## RAG（保留、隔離）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract` 與
`packages/indexer-contract` 是可獨立執行的 RAG bounded context，目前沒有正式 JD App consumer。
只有 `pnpm rag:*` 才會明示啟動；詳見 [RAG 設計](docs/design/rag-pipeline.md)。
