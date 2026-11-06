# 現行設計取捨

本頁記錄產品已採用的主要架構選擇與限制。完整責任規格位於 [apps/backend/architecture.md](../../apps/backend/architecture.md)；候選研究與施工歷史不在現行正文維護。

| 選擇 | 理由與界線 |
|---|---|
| 模組化單體 | 一個 FastAPI 應用程序組裝 Web、Agent 與業務能力；不為每個角色或模組建立服務。 |
| 能力模組與 Agent Plugin 分責 | 模組持有規則、資料及公開用例；Plugin 決定模型如何使用它。啟停 Plugin 不取消模組資料與必要清理責任。 |
| PostgreSQL＋官方 Saver | 業務交易與原生執行保存分責，不自行發明第二套 Checkpoint 格式或恢復平台。 |
| JD 直接保存及完整版本 | 人工與 AI 使用相同 Application 用例；每次有效操作形成版本，取消依模組恢復。 |
| 公版能力內聚 | PDF 解析、Embedding、rerank、索引與回讀位於 `occupation_reference`；Qdrant 是標準部署依賴。公版 Agent 工具仍可選取。 |
| 工作記憶單向分析 | B1 整理情境，B2 建立理解，完成後發布；角色沿 Memory Bundle 配置，共用 Core。 |
| 持久短碼 | Workspace 內由 Model References 提供穩定定位，正式關聯仍使用 UUID；短碼不授予權限。 |
| 明示恢復相容版本 | 破壞性執行契約變更更新 `resume_version`；不相容未完成輪拒絕恢復，不猜測舊格式。 |

技術與套件的實際位置見[技術接線](../implementation/technology-decisions.md)，資料與取消限制見[保存與恢復](persistence.md)。本機單 worker、沒有登入與多租戶，以及模型品質未經真人使用驗證等界線仍適用。
