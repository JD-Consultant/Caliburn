# Context Map

Caliburn 由三個 bounded context 組成；各 context 只維護自己的領域語言，跨 context 關係與系統級決策由本檔與
`docs/adr/` 指引。

## Contexts

- **PDF 解析**：OCS PDF 到結構化 JSON；glossary 尚未建立，預定位置為 `apps/pdf-to-json/CONTEXT.md`。
- **OCS 檢索**：OCS 索引與參考知識查詢；glossary 尚未建立，預定位置為 `apps/ocs-indexer/CONTEXT.md`。
- [JD 著作](apps/api/CONTEXT.md)：員工訪談、職務分析、工作模型與職務說明書著作；Web 與 API 共用此語言。

## Relationships

- **PDF 解析 → OCS 檢索**：PDF 解析產出可索引的 OCS 文件；檢索 context 不回寫來源文件。
- **OCS 檢索 → JD 著作**：檢索提供參考候選；參考資料不是員工工作證據，也不能直接成為正式 JD。
- **JD 著作 → OCS 文件**：Current JD 可投影成 OCS 匯出格式；OCS 格式不限制內部工作模型。
