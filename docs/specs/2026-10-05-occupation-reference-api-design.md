# 公版職位參考 API

2026-10-05。狀態：**獨立 RAG API 已實作；App 可依 ADR0080 明示接入 HTTP consumer** 。本文件維護檢索、固定來源讀取及 RAG HTTP 契約；App 的工具、選用與否認 state 由[公版工具契約](2026-10-04-public-reference-completion-design.md)負責。用途沿[職位整體參考](2026-10-04-occupation-overview-reference-retrieval-design.md)，接線決策見 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)，實驗原件不改寫。

初次 API 授權為「先把 api 搞好，規範的搞，低耦合高內聚，命名方式也是」及「也不用整合，前面要改就好，要優化就優化」。後續「現在接入 tool」授權另行完成可選 App 接線，不把 RAG 變成預設啟動依賴。

## 效果及界線

輸入員工目前已知的實際工作文字，回傳最多五份去重公版，包含名稱、原始概述、全部已解析任務目錄、搜尋證據及固定來源定位。按需讀指定任務的 O/P/K/S 正文。公版只提供參考，不推定適用、不宣布 JD 完成、不保存 Memory／確認進度。多個查詢由呼叫端分別呼叫；不新增未驗過的跨查詢融合。

## API 與唯一契約

- `POST /occupation-references:search`：`query`（非空、至多 12,000 字元）及 `limit`（預設 5、1–5）。回傳 `references` 與本次 `retrieval_policy`。每份 reference 附 `retrieval_evidence`，不輸出「符合率」。
- `GET /occupation-references/{reference_id}`：相同來源的概述及完整已解析目錄。
- `GET /occupation-references/{reference_id}/tasks/{task_id}`：該來源內的任務群組正文，多個 T 名稱共用區塊不拆成假獨立任務。

名稱沿 ADR0019 的資源 kebab-case／自訂方法 `:verb`、Python snake_case／PascalCase。wire authority 延續 RAG 自有的 `packages/indexer-contract` Pydantic；HTTP OpenAPI 從它產生，內部用 dataclass，HTTP 才投影 DTO。舊 `/occupations:search` 等介面留存原語意，不能混充新實驗結果。

## 檢索、來源與生命週期

新 collection 與既有 `ocs_v4` 隔離；CLI 只能建立不存在的 collection，完成後才寫 ready manifest；失敗的 collection 不供查詢、不自動刪除。來源採呼叫者明示選用的 JSON 集合，不猜官方最新版本；重複 OCS code 拒絕，避免歷史版本悄悄重複。不可原地換版，需另建 collection。

每來源以 code＋原始 UTF-8 SHA256 生成 `reference_id`；任務以來源內單元／群組位置生成 `task_id`。原始 JSON 正文存於 document point，讀取校驗 hash 與 ID，不從檔名／同名新版代替。JSON 解析完整不代表 PDF 抽取完全。缺代碼、同代碼多群組、無正文任務仍在目錄；只有非空搜尋正文才向量化。

正文清理沿實驗：排除職位名稱、OPKS/T 代碼與表頭；保留概述、工作單元／任務名稱、O/P 正文。D 為整份去重正文；T 為任務群組正文＋獨立概述點。BGE-M3 1024d；Qdrant exact cosine 兩路各取 20 個**不同父公版** ，完整聯集去重後全部以完整 D 正文 rerank，才截最終 5。不先 RRF 截 20。20 是原話控制初值，服務端可改為 40，不宣稱通用最佳參數或全庫 Recall。

rerank 由既有 Linux GPU embedder 增加本機 HTTP 能力，indexer 不載入 torch。BAAI/bge-reranker-v2-m3 固定 revision，長正文以 token windows／overlap 64 全部評分取最大 logit；過長 query 明確拒絕，不靜默截斷。API 不宣稱已做任務適用性判斷。模型與連線在 FastAPI lifespan 建立／清理；依賴由建構注入，內部不得 import FastAPI／transport DTO。

## 失敗與驗收

模型權重沿凍結實驗版本：BGE-M3 `5617a9f61b028005a4858fdac845db406aefb181`、reranker
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`。HTTP adapter 驗證模型名稱、權重版本、
回傳數量及有限向量／分數；舊服務缺少身分欄位會拒絕，需一起更新 GPU 容器。

422 非法查詢／未知參數；404 未知來源或任務；409 未 ready、身分／前處理／embedding 不相容；502 無效上游結果；503 未設定參考 collection 或模型／Qdrant 不可用。零候選正常回空清單，不與故障混淆。一般 log 不印 query、JSON、模型正文或金鑰。

驗收：HTTP 契約、父公版去重、整個聯集送 rerank、未命中任務仍可讀、來源換版拒絕、無碼／共用區塊保真、上游數量／非有限值拒絕、長正文沒有丟尾、資源清理、真 Qdrant SDK 整合及既有 API 回歸。以既有凍結向量／logit重播另核新程式正文與結果；不把快取重播說成 fresh provider 或新的品質評分。

官方機制依據：[Qdrant grouping](https://qdrant.tech/documentation/search/search/)、[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[BGE reranker](https://bge-model.com/bge/bge_reranker_v2.html)，2026-10-05 查閱。上述演算法與契約是 Caliburn 本次取捨，非官方品質保證。
