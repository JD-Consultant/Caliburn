# 公版來源、索引與檢索

公版是後端的 `occupation_reference` 能力模組，負責 PDF 轉換、內容驗證、固定來源、索引、搜尋與回讀。它使用 Qdrant 與同程序本機 Embedding／Reranker，不另開解析、索引或 GPU HTTP 服務。

[公版模組](../../apps/backend/src/caliburn/modules/occupation_reference/README.md)維護匯入與搜尋流程圖、配置、來源身分、索引版本及限制；[Job Reference Bundle](../../apps/backend/src/caliburn/bundles/job_reference/README.md)維護模型提示與唯讀工具。這兩個責任不可混為一個開關：公版維護與 HTTP 查讀不以 Agent 啟用為前提。

## 資料與使用界線

原始來源、清洗檢索副本與模型工具回讀各有用途。搜尋排名是查找證據，不是員工符合率，也不代表原文被完整讀取或內容已經員工確認。來源及任務以固定身分定位；本版不保存公版選用／否認集合。

新索引建立於新的 collection，通過點數及 manifest 檢查後才可切換配置。來源與權重須事先備妥，應用啟動不下載模型、不建索引、不刪失敗 collection。更換 collection 也不保證舊來源永久可回讀。

`packages/ocs-contract` 定義公版文件交換格式；`packages/indexer-contract` 定義公版查讀形狀，兩者都是目前模組的正式依賴。操作見[公版維護](../operations/rag.md)，契約原則見[契約策略](../standards/contract-strategy.md)。
