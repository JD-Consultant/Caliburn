# Caliburn 架構導覽

系統採單一 FastAPI 應用程序，能力模組管資料與規則，Agent 插件管模型接入，Core 管執行。完整模組圖、部署圖、資料所有權及跨模組流程由[系統架構與責任規格](../../apps/backend/architecture.md)維護。

## 依問題閱讀

| 問題 | 入口 |
|---|---|
| 哪些責任在同一程序、誰依賴誰 | [系統邊界](system-boundaries.md)、[程式組織](../standards/code-organization.md) |
| 誰保存資料、取消與恢復做什麼 | [保存與恢復](persistence.md) |
| 如何部署、有哪些信任限制 | [交付與運作](delivery-and-operations.md) |
| 公版如何解析、索引及搜尋 | [公版能力](rag-pipeline.md) |
| 已採用的主要取捨 | [設計取捨](design-decisions.md) |
| 測試能證明哪些範圍 | [驗證範圍](verification.md) |

## 架構與實作的維護分工

系統規格維護跨模組契約；各[模組及 Bundle](../../apps/backend/README.md#檔案位置)維護局部資料、交易、Prompt、工具及 Plugin 設定。正式 HTTP 欄位由 OpenAPI 產生，工具由其實際定義維護。本文與[實作導覽](../implementation/README.md)不另維護欄位清單、狀態機或第二套圖源。

圖面與規格說明責任，不能當作真資料庫、真瀏覽器或模型品質已驗收的證據。
