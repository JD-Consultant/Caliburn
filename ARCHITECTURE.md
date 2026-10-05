# Caliburn 架構

Caliburn 是本機 Web AI 職務分析與職務說明書（JD）應用程式。員工透過持續訪談說明工作，AI 逐步編修 JD；人也可直接編輯同一份文件，兩種入口遵循相同的業務規則。

單一操作者可管理多份資料隔離的職務檔案。服務僅綁定本機回環位址（loopback），目前不提供登入、存取控制清單（ACL）、多租戶、計費、雲端部署或多人協作。本頁提供程式組成的簡短入口，詳細契約由各主題文件維護。

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
  features      領域資料與規則：職務檔案、訪談、JD、Memory、執行資格與限制
  adapters      OpenAI Responses（直連 SDK）、LangGraph 官方 PostgreSQL saver、PDF renderer
        │                     │
        ▼                     ▼
PostgreSQL               OpenAI Responses API（經授權的工作資料；store=false）
  關聯式 JD／訪談／Memory／執行資格
  LangGraph checkpoint（原生接續歷史）
```

程式位於 `apps/api`（後端）與 `apps/web`（介面）。上圖呈現未啟用公版參考的基本組成。後端採模組化單體：訪談、JD 與 Memory 各自管理資料和規則，由工作流程協調；三個 AI 分析角色共用模型與工具執行機制，不各自部署成服務。Web 呈現資料與提交操作，正式結果統一由後端保存。

## 資料與執行的基本規則

- PostgreSQL 的關聯式資料表保存正式資料；LangGraph checkpoint 只保存模型接續位置，不取代正式業務結果；Web 不另存一份正式 JD，也不重新計算領域規則。
- 人工編輯與模型工具可使用不同入口，但都經過同一個 JD 服務，遵循相同的驗證、版本與保存規則；候選（模型本輪的改動）在 Turn 完整成功前不成為正式 JD。
- 原始訪談完整保存，可供引用與回查；工作情境與理解（Memory）沿 B1 → B2 → 發布的單向流程形成不可變快照。上下文壓縮只管理模型接續資料，不能取代原話或 Memory。
- 公開中間訊息與可讀推理摘要支援串流及歷史回看，與正式答覆分開；未保存的片段不承諾恢復，也不授予正式訪談或引用資格。完整內部推理不公開。
- 文件、版本、資料範圍、引用解析與寫入條件由 App 管理，不要求模型自行生成或猜測；訪談、Memory、JD 與工具回傳的文字一律視為資料，不能改變指令或權限。
- `request_memory_consolidation` 是非等待式要求。現行機制在背景整理最終失敗後，須讓訪談再前進三輪才允許一次新批次；這項政策仍待確認，A 不因 Memory 失敗而停用。
- 本輪 JD 撤回只撤回該輪 JD 的效果，不撤回原始訪談、來源或 Memory。
- OpenAI 金鑰僅供後端使用，不放入提示、工具、Web 建置檔、URL、紀錄或資料庫；未設定金鑰時，人工 JD 編輯仍可使用，AI 功能則明確顯示為停用。

整體流程與各章閱讀入口見[架構導覽](docs/target-architecture-map.md)。模組之間的關係見[系統責任與資料流](docs/architecture/system-boundaries.md)，保存與恢復機制見[資料責任與交易](docs/architecture/persistence.md)。測試結果與適用範圍見[驗證與限制](docs/architecture/verification.md)。

## 獨立的檢索研究

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract` 與 `packages/indexer-contract` 構成獨立 RAG 領域，分別處理公版轉換、索引、向量與 API 契約。

依 [ADR0080](docs/adr/0080-opt-in-public-reference-agent-tools.md)，JD App 可在明示設定後透過 HTTP 查讀公版；RAG 不由 App 自動部署或啟動，也不保存員工訪談與 JD。選用公版及明確否認範圍由 App 自己保存，工具資格與跨輪規則沿原執行流程。啟停仍使用 `pnpm rag:*`，詳細分工見 [RAG 設計](docs/design/rag-pipeline.md)。
