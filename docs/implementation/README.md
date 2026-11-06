# 實作與契約入口

程式的能力、交易與接線就近維護在 `apps/`。本頁按修改責任提供入口，不再複製模組 README 的資料表、狀態機或工具定義。

| 修改範圍 | 責任入口 |
|---|---|
| Host 組裝、資源與部署 | [後端](../../apps/backend/README.md)、[系統規格](../../apps/backend/architecture.md) |
| Workspace 建立與整份刪除 | [Workspace](../../apps/backend/src/caliburn/modules/workspace/README.md) |
| JD 內容、來源、版本與 PDF | [JD 模組](../../apps/backend/src/caliburn/modules/job_description/README.md)、[JD Bundle](../../apps/backend/src/caliburn/bundles/job_description/README.md) |
| 訪談與逐題問答 | [Interview](../../apps/backend/src/caliburn/modules/interview/README.md)、[Human Questions](../../apps/backend/src/caliburn/modules/human_questions/README.md) |
| Memory 內容與分析發布 | [Memory 模組](../../apps/backend/src/caliburn/modules/memory/README.md)、[Memory Bundle](../../apps/backend/src/caliburn/bundles/memory/README.md) |
| Plan 讀改與取消基準 | [Plan 模組](../../apps/backend/src/caliburn/modules/plan/README.md)、[Plan Bundle](../../apps/backend/src/caliburn/bundles/plan/README.md) |
| 通用模型執行、恢復、取消與串流 | [Agent](../../apps/backend/src/caliburn/modules/agent/README.md) |
| 窗口與原生壓縮 | [Context Bundle](../../apps/backend/src/caliburn/bundles/context/README.md) |
| 顧問主提示 | [Consultant Bundle](../../apps/backend/src/caliburn/bundles/consultant/README.md) |
| 公版與模型查讀工具 | [Occupation Reference](../../apps/backend/src/caliburn/modules/occupation_reference/README.md)、[Job Reference Bundle](../../apps/backend/src/caliburn/bundles/job_reference/README.md) |
| 共用模型短碼 | [Model References](../../apps/backend/src/caliburn/modules/model_references/README.md) |
| Web、資料快取與使用者互動 | [前端](../../apps/frontend/README.md) |

跨邊界格式與生成見[資料與契約](data-and-contracts.md)，技術責任見[技術接線](technology-decisions.md)，測試分工見[驗證責任](verification-plan.md)。工程品質與修改要求沿[公開規範](../standards/README.md)。
