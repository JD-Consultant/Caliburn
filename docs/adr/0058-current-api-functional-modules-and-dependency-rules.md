# 0058. Current API 採功能模組與可執行依賴規則

- **狀態**：Accepted
- **日期**：2026-08-10
- **核准**：2026-08-10，owner 核准交付實作者執行
- **研究**：[`2026-08-10-job-analysis-module-boundaries-research.md`](../specs/2026-08-10-job-analysis-module-boundaries-research.md)

## Context

`app/job_analysis` 是 ADR 0040 為隔離舊 AI runtime 而建立的 greenfield 容器。ADR 0057 hard cut 後，它已成為唯一 production 系統；繼續保留單一 `job_analysis` 大 namespace，會把已完成的開發隔離當成永久架構。

目前不只名稱重複：`application/__init__.py` 暴露過大 facade，documents／Task Analysis／OPKS／export 混在同一 application layer；application operation 直接依賴具體 `OpenRouterAdapter`，OpenPyXL renderer 也住在 application。單純把檔案搬到全域 `core/application/adapters` 仍不能建立功能邊界；把每個功能拆成獨立服務或獨立資料真相則會破壞共同 Current State 與 authority transaction。

## Decision

Caliburn current API 維持單一 process、單一資料庫與單一 modular monolith，但移除 `app/job_analysis` 作為 greenfield 隔離容器，改以功能模組作第一層 package：

- `core`：共同 Current State、authority transaction／ports、識別碼與真正被多模組共享的穩定 domain language。
- `documents`：文件生命週期、header、readiness、Duty／Task 員工直接編輯。
- `task_analysis`：Task context、LLM wire／prompt、operation、verifier、transition 與 Task Proposal。
- `opks`：OPKS context、child operation、scheduler、員工編輯、verifier 與 OPKS Proposal。
- `consultation`：員工回合的 orchestration；只能透過 `task_analysis`／`opks` public API 協調。
- `export`：純 deterministic export projection；OpenPyXL renderer 是外層 adapter。
- `adapters`：PostgreSQL、OpenRouter、XLSX 等具體 IO。
- `api`：按功能拆分的 FastAPI routes、transport mappers 與唯一 composition root。

Web 依實際 UI responsibility 對齊能力邊界，採 `features/documents`、`features/consultation`、`features/opks`、`features/export`；不為了與 backend 對稱而建立沒有獨立 UI 責任的 feature。Next.js pages 只負責 composition，`shared` 只放 HTTP／query／通用 UI，不放 domain policy。

依賴規範如下：

1. `core` 不得 import FastAPI、SQLAlchemy、HTTPX、OpenPyXL、provider、transport contract 或任何外層模組。
2. 功能模組只依賴自身 internals 與 `core`；唯一允許的跨功能方向是 `consultation → task_analysis/opks` 的 public API。
3. port 由需要外部能力的內層功能模組擁有；adapter 實作 port。application 不得用 `OpenRouterAdapter`、ORM model 或 framework DTO 作型別。
4. 跨模組只能 import 模組 root 明確 re-export 的 public API；不得 import 另一模組的 `internal` 或底層實作檔。不得建立聚合所有功能的全域 facade。
5. 模組依賴必須是 DAG，不得有 direct 或 indirect cycle。既有 AST dependency tests 擴充為 allowed-dependency、forbidden-import 與 API-only access checks；第一階段不新增 Import Linter 依賴。
6. 新增第一層功能模組必須能說明單一主要責任、列出 public use cases、隱藏 internal implementation，且加入依賴圖後仍無 cycle；不得只依團隊名稱、技術類型或假想的未來服務切目錄。
7. 型別／port 進 `core` 必須同時符合：至少兩個功能真的消費、語意穩定且共同、零 IO／framework／transport。假想重用不成立。
8. 所有 authority writer 仍走同一 commit seam；repository 不自行 commit，provider call 仍在 transaction 外，generation／read-set stale 保護不變。
9. API route、JSON Schema contract、`job_analysis_*` table、migration history 與產品行為不因內部 move-only 重構改名或改形狀。
10. Web feature 不得重算 readiness、Evidence 或 authority invariant；生成 contract 仍是 transport SSOT，跨 feature 協調由 workspace/page composition 完成；前後端目錄不要求機械對稱。
11. 目錄搬移與邏輯修改分開；每個 move task 先後跑同一組 characterization tests，維持 green-before == green-after，一個 task 一個 commit。

檔案超過 500 行、單一 facade 超過 25 個 public names，或一個檔案同時含兩種 IO／use-case 責任時，必須觸發拆分審查；這是 review trigger，不是允許任意機械拆檔的硬性正確性門檻。

## Consequences

功能名稱會直接反映產品能力，`job_analysis` 不再暗示仍有平行舊 runtime；Task／OPKS／文件／匯出的內聚、公開面與允許依賴可被測試。provider port 與 XLSX renderer 回到正確內外層後，換 adapter 不會迫使 application 依賴具體框架。

代價是大量 import、tests、docs 與 composition 路徑需要分批 move，且 shared core 必須持續防止膨脹。由於 public HTTP、contract 與 table names 保持不變，這是 source-level refactor，不建立相容 shim、第二套路徑或雙軌 runtime。
