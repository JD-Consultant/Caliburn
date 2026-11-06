# 系統邊界與責任

Caliburn 的 Web、HTTP、Agent 及公版檢索共用同一後端應用。PostgreSQL 與 Qdrant 是獨立資料庫程序，與應用一起由部署入口啟停；模組不是獨立服務。

[系統規格](../../apps/backend/architecture.md#1-系統分區)維護系統邊界、模組歸屬及部署圖；[能力表](../../apps/backend/architecture.md#2-模組責任與公開能力)維護每個模組擁有及不擁有的責任。

## 接入與資料權威

- Web 呈現資料及提交操作；HTTP 與模型工具呼叫相同的 Application 用例，不能各自重寫業務驗證。
- Workspace 管檔案歸屬；JD、Interview、Memory 與 Plan 各自保存資料、版本及規則。
- Agent 保存及投影通用執行狀態，不解讀 JD、Memory 或問答專屬內容。Bundle 將可信範圍與版本交給能力模組。
- Model References 管 Workspace 內的持久短碼；解析成功不代表業務存在或引用合格。
- Occupation Reference 管公版 PDF、固定來源、索引、搜尋及回讀；公版不能證明員工實際工作。

能力資料與必要收尾不依 Plugin 是否選取而消失。停用某工具只改變模型可用能力，不是刪資料或撤銷已發生效果。具體依賴與配置沿[Bundle／Plugin 規格](../../apps/backend/architecture.md#4-bundleplugin-與依賴)。
