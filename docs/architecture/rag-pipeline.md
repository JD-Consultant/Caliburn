# 公版參考與 RAG 架構

RAG 負責把公版職能基準轉成可搜尋、可回讀來源的參考資料。JD App 依 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)明示啟用 HTTP 查讀，公版用來找追問與查漏線索；員工實際負責的工作仍須由訪談確認。基本訪談、人工 JD 與 JD PDF 匯出不依賴 RAG。

本頁維護元件分工、資料流及隔離邊界。啟停、設定、建索引與保存操作見 [RAG 操作手冊](../operations/rag.md)；端點與資料格式沿[公版參考 API 契約](../specs/2026-10-05-occupation-reference-api-design.md)。

## 1. 元件與責任

這條管線以 OCS（職能基準）的 PDF 及轉換後的 JSON 為來源。解析、檢索及模型運算各自安裝、測試與執行，不併入 JD App 程序。

| 元件 | 負責什麼 | 契約與依賴 |
|---|---|---|
| [pdf-to-json](../../apps/pdf-to-json/README.md) | 離線解析 PDF，產生 OCS JSON 與拒絕診斷 | 使用 `ocs-contract`；不建立向量索引、不寫 JD App 資料庫 |
| [ocs-indexer](../../apps/ocs-indexer/README.md) | 建立索引、查詢及回讀固定公版來源，管理 Qdrant 資料 | 使用 `ocs-contract` 與 `indexer-contract`；以 HTTP 呼叫模型服務 |
| [embedder](../../apps/embedder/README.md) | 提供 BGE-M3 向量及 BGE-reranker-v2-m3 配對評分 | 獨立 GPU 容器；模型權重不載入 indexer 或 JD App 程序 |
| Qdrant | 保存索引、固定來源及就緒標記 | 由 indexer 存取；App 經查詢 API 讀取，不直接連 collection |
| [ocs-contract](../../packages/ocs-contract/) | 維護 OCS JSON schema 及生成的 Python／TypeScript 型別 | 供解析與索引共用 |
| [indexer-contract](../../packages/indexer-contract/) | 維護檢索 API 的 request／response model | 由 producer 驗證 wire 格式；JD App 使用自己的 HTTP adapter 驗證服務邊界 |

## 2. 資料如何流動

1. **解析來源。** `pdf-to-json` 把 PDF 轉成 OCS JSON，正常輸出與拒絕診斷分開。解析結果與未支援版型由[PDF → JSON 契約](../specs/2026-10-03-public-ocs-pdf-to-json-design.md)及[批次補齊紀錄](../experiments/2026-10-04-ocs-json-repair/README.md)說明；有 JSON 不代表已逐字驗收原 PDF。
2. **選版與建索引。** 操作者明示選定來源 JSON，以 `index-references` 建立獨立公版 collection，內含整份正文與任務／概述的檢索點。來源內容與 hash 固定公版身分，完整寫入後才發布就緒標記（ready manifest）。啟動服務不自動選版、解析或建索引。
3. **搜尋與讀取。** indexer 透過模型服務計算向量與重排序，從 Qdrant 取得候選及固定來源。職位整體參考採兩路廣蒐、完整聯集重排序及公版去重；數量、評分含義與回傳格式只由[API 契約](../specs/2026-10-05-occupation-reference-api-design.md)維護，不把控制初值稱為通用最佳參數。
4. **訪談中使用。** App 經 HTTP 取得公版，顧問按需選用、讀取任務及保存員工明確否認的範圍。選用與排除資料由 App 保存，RAG 不判定 JD 已完成，也不把公版自動當成員工工作事實。角色權限與跨輪資格見[公版工具契約](../specs/2026-10-04-public-reference-completion-design.md)。

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
- **由設定與部署啟用。** App 的 composition root 在配置 URL 時建立 HTTP client；未配置時不增加公版工具。服務由操作者啟動，App 程序不管理 GPU、Qdrant 或容器；工具設定只影響尚未綁定的新請求，既存工作沿原請求恢復，依 ADR0080 與 [API 啟用說明](../../apps/api/README.md#公版參考工具的可選啟用)。
- **資料各自保存。** 檢索服務不寫 JD App PostgreSQL。公版用於參考，不能直接複製成 Memory／JD 的員工工作事實；查詢正文與明確否認範圍的使用規則由公版工具契約維護。
- **故障不能當查無資料。** 索引未 ready、模型身分不相容、無效模型回覆或連線失敗須回報錯誤，不以空結果代替，也不清除 App 已保存的選用資料。健康檢查不代替實際搜尋驗證。

## 5. 修改與追溯

| 要修改或查閱什麼 | 責任文件 |
|---|---|
| 解析保真、來源檢核與失敗隔離 | [PDF → JSON 契約](../specs/2026-10-03-public-ocs-pdf-to-json-design.md)；命令及程式位置見 [pdf-to-json README](../../apps/pdf-to-json/README.md) |
| 搜尋、固定來源讀取與 HTTP 格式 | [公版參考 API 契約](../specs/2026-10-05-occupation-reference-api-design.md)；設定、測試及程式位置見 [indexer README](../../apps/ocs-indexer/README.md) |
| 模型服務與 GPU 部署 | [embedder README](../../apps/embedder/README.md) |
| 顧問工具、公版選用及排除資料 | [公版工具契約](../specs/2026-10-04-public-reference-completion-design.md)與 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md) |
| 啟停、選版、建索引及更新保存 | [RAG 操作手冊](../operations/rag.md) |
| 品質候選、未決問題及實驗 | [目前決策](../current-decisions.md#獨立-rag-與公版參考)與[檢索實驗](../experiments/README.md#檢索與資料處理) |

早期保留與隔離的理由見 [2026-08-11 設計](../specs/2026-08-11-rag-bounded-context-retention-design.md)及 Proposed [ADR0057](../adr/0057-current-only-runtime-and-data-boundary.md)；當時未接消費端的描述不代表現況。其他退役設計由[歷史索引](../history.md)取回，不在架構頁重抄舊管線與 corpus 統計。
