# 公版參考與 RAG 架構

RAG 負責把公版職能基準轉成可搜尋、可回讀來源的參考資料。JD App 明示啟用後，可經 HTTP 查讀公版，尋找追問與查漏線索；員工實際負責的工作仍須由訪談確認。基本訪談、人工 JD 與 JD PDF 匯出不依賴 RAG。

本頁維護元件分工、資料流及隔離邊界。啟停、設定、建索引與保存操作見 [RAG 操作手冊](../operations/rag.md)；端點與資料格式見[公版參考 API](../../apps/ocs-indexer/README.md)。

## 1. 元件與責任

這條管線以 OCS（職能基準）的 PDF 及轉換後的 JSON 為來源。解析、檢索及模型運算各自安裝、測試與執行，不併入 JD App 程序。

| 元件 | 負責什麼 | 契約與依賴 |
|---|---|---|
| [pdf-to-json](../../apps/pdf-to-json/README.md) | 離線解析 PDF，產生 OCS JSON 與拒絕診斷 | 使用 `ocs-contract`；不建立向量索引、不寫 JD App 資料庫 |
| [ocs-indexer](../../apps/ocs-indexer/README.md) | 建立索引、查詢及回讀固定公版來源，管理 Qdrant 資料 | 使用 `ocs-contract` 與 `indexer-contract`；以 HTTP 呼叫模型服務 |
| [embedder](../../apps/embedder/README.md) | 提供 BGE-M3 向量及 BGE-reranker-v2-m3 配對評分 | 獨立 GPU 容器；模型權重不載入 indexer 或 JD App 程序 |
| Qdrant | 保存索引、固定來源及就緒標記 | 由 indexer 存取；App 經查詢 API 讀取，不直接連 collection |
| [ocs-contract](../../packages/ocs-contract/) | 維護 OCS JSON schema 及目前生成的 Python 型別 | 供解析與索引共用 |
| [indexer-contract](../../packages/indexer-contract/) | 維護檢索 API 的 request／response model | 由 producer 驗證 wire 格式；JD App 使用自己的 HTTP adapter 驗證服務邊界 |

## 2. 資料如何流動

1. **解析來源。** `pdf-to-json` 把 PDF 轉成 OCS JSON，正常輸出與拒絕診斷分開。

   解析結果與未支援版型由[PDF 轉換與來源檢核](../../apps/pdf-to-json/README.md)及批次補齊紀錄說明；有 JSON 不代表已逐字驗收原 PDF。

2. **選版與建索引。** 操作者明示選定來源 JSON，以 `index-references` 建立獨立公版 collection，內含整份正文與任務／概述的檢索點。

   來源內容與 hash 固定公版身分，完整寫入後才發布就緒標記（ready manifest）。啟動服務不自動選版、解析或建索引。

3. **搜尋與讀取。** indexer 透過模型服務計算向量與重排序，從 Qdrant 取得候選及固定來源。

   職位整體參考採兩路廣蒐、完整聯集重排序及公版去重；數量、評分含義與回傳格式只由[公版參考 API](../../apps/ocs-indexer/README.md)維護，不把控制初值稱為通用最佳參數。

4. **訪談中使用。** App 經 HTTP 取得公版，顧問按需選用、讀取任務及保存員工明確否認的範圍。

   選用與排除資料由 App 保存，RAG 不判定 JD 已完成，也不把公版自動當成員工工作事實。角色權限與跨輪資格見[公版選用與否認資格](rag-pipeline.md#公版選用與明確否認的保存資格)。

線上查讀的服務關係重用[公版 RAG 容器圖](delivery-and-operations.md#2-最小部署視角)；該圖省略上述離線解析與建索引。既有 profile／task 管線仍保留自己的索引與 API，與職位整體參考的 collection 分開，實作見 [indexer 內部管線](../../apps/ocs-indexer/docs/pipeline.md)。

## 3. 保存與版本邊界

| 資料 | 保存責任 |
|---|---|
| 原始 PDF、OCS JSON 與解析診斷 | 解析流程及操作者；PDF 是重新產生 JSON 的來源，不能只當測試暫存 |
| 公版索引、固定來源及 ready manifest | indexer／Qdrant；來源或模型身分變更時建立新 collection，不在讀取時代換新版 |
| 模型權重快取 | embedder 的獨立儲存；由部署配置管理 |
| 員工訪談、Memory、JD、公版選用及排除範圍 | JD App／PostgreSQL；不由 RAG 保存或複製成另一份權威 |

職位整體參考的 `index-references` 拒絕覆寫既有 collection，失敗索引保持未 ready；不自動刪除或挪用舊資料。既有 profile／task 索引沿自己的更新語義，不能套用為同一套寫入契約。兩種索引的設定及來源讀取方式見 [indexer README](../../apps/ocs-indexer/README.md)。

Docker 基本模式與公版模式共用 JD App 及 PostgreSQL；公版模式另有 RAG 服務與儲存。獨立 RAG 開發 project 的 volume 不會自動成為公版模式的資料，位置、更新及停止方式由[操作手冊](../operations/rag.md#更新與保存)維護。

## 4. 與 JD App 的隔離及故障處理

- **只經 HTTP 接入。** 正式 App 不 import `jd_ocs_indexer`、`jd_pdf_to_json`、`ocs_contract`、`indexer_contract` 或 embedder 程式。RAG 內部共用契約是預期依賴，不受 App 的套件隔離限制。
- **由設定與部署啟用。** 模型執行環境啟用且已配置公版 URL 時，App 的 composition root 建立 HTTP client；未配置 URL 時不增加公版工具。服務由操作者啟動，App 程序不管理 GPU、Qdrant 或容器；工具設定只影響尚未綁定的新請求，既存工作沿原請求恢復，詳見 [API 啟用說明](../../apps/api/README.md#公版參考工具的可選啟用)。
- **連線範圍明示。** 獨立開發模式只把 Qdrant／模型服務發布到 loopback；正式 App 的公版 overlay 清除這些主機埠，由 Compose 內網連線。埠與部署差異見[部署視角](delivery-and-operations.md#2-最小部署視角)。
- **資料各自保存。** 檢索服務不寫 JD App PostgreSQL。公版用於參考，不能直接複製成 Memory／JD 的員工工作事實；查詢正文與明確否認範圍的使用規則由公版工具契約維護。
- **故障不能當查無資料。** 索引未 ready、模型身分不相容、無效模型回覆或連線失敗須回報錯誤，不以空結果代替，也不清除 App 已保存的選用資料。健康檢查不代替實際搜尋驗證。

### 公版選用與明確否認的保存資格

公版選用與排除範圍是 App 的獨立資料用途。選用 null 表示尚未選擇，空集合表示目前沒有合適參考；select 以全集取代前次選用，但保留排除紀錄。

排除只記員工明確否認的工作，未知、拒答及未回答不算否認；後續更正可以解除排除。公版選中或排除數量都不判定 JD 完成。

A 的 current state 是本輪候選。跨輪或 B1／B2 查讀時，只取同時符合以下條件的最新狀態：

- 同一檔案的 completed execution。
- 匹配正式交換。
- 員工訊息序號不超過該工作固定 frontier F。

空集合仍覆蓋舊選擇，後輪更正不回流既有批次。已保存 request 保持原 captured 能力，不因新設定追補工具或 context。

候選、原操作與採用查詢由 [occupation_references feature](../../apps/api/src/caliburn/features/occupation_references/)及[讀取工作流](../../apps/api/src/caliburn/workflows/occupation_reference_reads.py)實作；模型工具 shape 沿[工具 Schema](../../apps/api/contracts/tools/)。

## 5. 修改與追溯

| 要修改或查閱什麼 | 責任文件 |
|---|---|
| 解析保真、來源檢核與失敗隔離 | [PDF 轉換與來源檢核](../../apps/pdf-to-json/README.md)；命令及程式位置見 [pdf-to-json README](../../apps/pdf-to-json/README.md) |
| 搜尋、固定來源讀取與 HTTP 格式 | [公版參考 API](../../apps/ocs-indexer/README.md)；設定、測試及程式位置見 [indexer README](../../apps/ocs-indexer/README.md) |
| 模型服務與 GPU 部署 | [embedder README](../../apps/embedder/README.md) |
| 顧問工具、公版選用及排除資料 | 本頁 §4 的資格與對應 feature／Schema |
| 啟停、選版、建索引及更新保存 | [RAG 操作手冊](../operations/rag.md) |
