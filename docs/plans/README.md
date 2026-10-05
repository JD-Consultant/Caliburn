# 開發計畫

新架構 T01–T18 已於 2026-10-02 結案並完成本機正式切換。原施工計畫保留於本機封存，不隨 Git 發布；已提交版本依[歷史查閱方式](../history.md)取回。結案不表示所有品質情境都已驗證，實際範圍見[驗證說明](../architecture/verification.md)。

已被取代或結束的清單不再列作新任務；未採用的候選也不因封存改成「已完成」。報告需要的[實驗資料](../experiments/product-validation/README.md)獨立保存，不與施工日誌混放。

後續工作先由[目前決策](../current-decisions.md)找相關契約與尚待處理事項，再依[開發規範](../implementation/development-standard.md)界定切片。需要多步驟協作時才在本目錄建立新計畫，不另抄產品規格，也不重新執行已結案的 T01–T18。

2026-10-05：[公版職位參考 API](2026-10-05-occupation-reference-api.md)，使用者授權獨立 RAG API
及相關重構；該切片不含 JD App／Agent 接線。驗收、重播及模型實測證據由計畫路由。

2026-10-05：[公版參考工具與確認資料](2026-10-05-occupation-reference-tools.md)，完成獨立工具與保存切片；保留當輪未接模型的工程證據。[後續比較](../specs/2026-10-04-public-reference-completion-design.md#最小落地與驗證順序)由設計文件維護，不把工具完成當成顧問收尾品質達標。

2026-10-05：[公版參考工具接入顧問與 Memory](2026-10-05-occupation-reference-agent-integration.md)，使用者接續授權角色接線；A 五工具、B1／B2 唯讀排除範圍，明示設定啟用。原請求與恢復保留舊配置，不重啟正在測試的共用服務；實測範圍見計畫與證據。
