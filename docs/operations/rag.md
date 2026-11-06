# 公版來源與索引維護

公版 PDF 解析、驗證、Embedding、索引、搜尋與回讀由後端 `occupation_reference` 管理，與應用共用程序；標準 Compose 同時啟動 Qdrant。Agent 的 Job Reference Plugin 只決定模型能否使用查讀工具，不控制模組部署。

完整配置、CLI、流程及限制由[公版模組 README](../../apps/backend/src/caliburn/modules/occupation_reference/README.md)維護；本頁說明與日常部署的連接。

## 準備順序

1. 保留原始 PDF 與來源識別；以模組 `convert-pdf` 轉換，輸出與診斷分目錄。拒絕資料不冒充已解析，也不自動 OCR。
2. 核對轉換結果及正式採用來源，每個 OCS code 選一份，放在獨立目錄；清洗副本不能當原始 OCS JSON 回灌。
3. 準備鎖定 revision 的 BGE-M3 與 BGE-reranker-v2-m3 權重。模組只使用既有本機 cache，不自動下載或載入 remote code。
4. 指定尚不存在的 collection，明示執行 `index`，核對 ready manifest；失敗 collection 保留診斷，不自動覆寫或刪除。
5. 更新應用公版配置，重啟並驗證搜尋及固定來源回讀，再讓 Agent 工具使用。

轉換、清洗、驗證與建索引的精確參數見[模組操作](../../apps/backend/src/caliburn/modules/occupation_reference/README.md#pdf-轉換與選版)。索引建立需要模型運算；CPU／CUDA、精度與前處理必須符合 manifest，不以同模型名稱推定相容。

## Docker 與原生位置

Docker 預設讀取 [docker/reference.json](../../docker/reference.json)，容器 cache 為 `/opt/caliburn/local/models`，對應根 `.local/models`。可在根 `.env` 設 `CALIBURN_REFERENCE_CONFIG_FILE` 更換配置，或設 `CALIBURN_LOCAL_DIRECTORY` 更換本機資源根目錄。掛載為唯讀，維護輸出使用另行指定的可寫目錄。

原生維護 CLI 在 `apps/backend` 執行，使用 `uv run --locked --extra local-models python -m caliburn.modules.occupation_reference`。若連根 Compose 的 Qdrant，配置 URL 為 `http://127.0.0.1:6335`；應用容器內則為 `http://qdrant:6333`。模型與來源路徑亦須按執行位置解析，不能直接混用。

## 驗證與保留

應用健康不代表索引可用；應以代表查詢核搜尋、任務回讀及來源版本。排名分數不是符合率或員工適用門檻。原始回讀與清洗搜尋正文的出口不同，不能假定工具會讀到索引全部欄位。

新 collection 切換不保證舊 collection 來源永久可回讀；切換前確認既有引用需求並保留來源與索引備份。公版資料、權重及 Qdrant volumes 不隨程式退役刪除，也不納入 Git 或 Python wheel。
