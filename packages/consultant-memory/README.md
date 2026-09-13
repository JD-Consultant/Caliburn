# Caliburn Consultant Memory

工作詳記、目前工作理解／導覽及發布回執的獨立 Python 套件。新 JD App 以一般套件依賴使用；不 import 舊 checkout，不含 JD 編輯、HTTP、排程或模型執行。

## 保存與來源

- `MemoryArtifacts` 使用 Deep Agents `StoreBackend`／`CompositeBackend` 保存不可變詳記與準備版本；`ReadOnlyFiles` 提供固定版本讀取。正式內容不寫到操作者的檔案系統。
- `PublicationStore` 以 SQLAlchemy 的版本檢查，將目前版與操作回執寫入同一短交易；重取舊回執不倒退目前版。修補不推進背景整理游標。
- App 提供 `SourceReader(document_id, validate_reference, read)`。`validate_reference` 只驗格式／簽章／文件範圍，不讀資料庫；`read` 必須讀原先固定的來源，不能換成最新內容。本套件不擁有原始對話。
- `caliburn_memory.read_tools.readonly_file_tools(backend)` 提供原生 `ls`／`grep`／`read_file`，不掛檔案 middleware 的訊息 hooks。0.7 不支援 backend factory；App 用公開工具替換接點綁固定 reader，見[工具實證](read-tools-results.md)及[新 App 接合](../../docs/specs/2026-09-13-jd-memory-read-integration-slice.md)。
- 沿用原 `q019-memory` namespace 及 `q019_document_memory_head`／`q019_memory_publication_receipt` 表，沒有另建平行權威。`setup()` 是明示初始化，禁止在一般開啟或每次回合呼叫。

程式採用來源、hash 與實際調整見 [adoption.json](adoption.json)；三核心僅分離來源依賴，沒有重寫 Memory 引擎。[完整接合設計與結果](../../docs/specs/2026-09-13-jd-memory-core-adoption-slice.md)保存官方依據、限制與驗證層級。

## 安裝與驗證

Python 3.12。App 的 `uv.lock` 固定實測組合；獨立 wheel 由 Hatchling 產生。

```powershell
# 在 experiments/jd-relational-app 使用其正式本地依賴
uv sync --frozen
uv run --offline --frozen pytest ../../packages/consultant-memory/tests -q -p no:cacheprovider

# 在本套件目錄建 wheel，輸出至指定暫存目錄
uv build --out-dir ../../.research-tmp/jd-memory-core-dist
```

Deep Agents 的標準 distribution 會連帶安裝 Anthropic／Google 等 provider 套件；本核心沒有建立 provider 或呼叫模型。未為減少套件數自行複製框架 backend。已驗新版 App 的共同依賴沒有升降版；後續變更按具體相容性驗證，不追逐版本號。

目前完成核心套件與新原話接點、真 PostgreSQL Store／發布及獨立 wheel 驗證。新 App 的[宿主資源／初始化／登記讀取排空與新程序重開](../../docs/specs/2026-09-13-jd-memory-host-integration-slice.md)、[固定 Memory 與原話只讀工具](../../docs/specs/2026-09-13-jd-memory-read-integration-slice.md)亦已接入；即時修補與背景整理、專業指引及完整備份尚須接合，不能以只讀工具通過代稱完整顧問可用。
