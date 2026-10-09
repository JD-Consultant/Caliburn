# 後端文件入口

本目錄提供現行後端的閱讀入口。`apps/api` 已依 ADR0079 成為正式產品後端；舊 API 曾使用相同目錄名稱，追查歷史時須核對當時版本，不能沿用 `app/core` 等退役模組指引施工。

- 安裝、執行與已知限制：[後端 README](../README.md)。
- 模組、契約、保存與執行設計：[實作文件入口](../../../docs/implementation/README.md)。
- 後續任務及驗收狀態：[目前決策](../../../docs/current-decisions.md)、計畫入口；原重建計畫已結案，供追溯施工與驗證。
- 正式產品權責依 [ADR0079](../../../docs/adr/0079-target-rebuild-production-cutover.md)，公版工具的可選接線依 [ADR0080](../../../docs/adr/0080-opt-in-public-reference-agent-tools.md)；[ADR0077](../../../docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)是舊產品沿革。

此處不複製第二套設計文件。舊 API 的退役脈絡見 [ADR0057](../../../docs/adr/0057-current-only-runtime-and-data-boundary.md)及歷史入口；本頁原文可從 `def9c248:apps/api/docs/README.md` 讀回。
