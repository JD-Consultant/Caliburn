# Memory C 修補核心採用

2026-09-13，基準 `7d3f474a`。此頁是 `caliburn_memory.repair` 作者的有界 port 與驗收紀錄，非獨立審查。新 App 工具、owner、完整來源與恢復接合由主代理負責，本頁不代稱已完成。

## 採用與責任

由既有隔離 `analysis_agent/repair.py` 移植至獨立套件 `packages/consultant-memory/src/caliburn_memory/repair.py`，只依賴同套件的 artifacts／publication／staging／patch。保留 `seed → edit → validate → save → prepare → publish` 六個原生節點；每次 edit 保留 LangGraph checkpoint 邊界。C 沒有自己的模型、舊 runtime import、來源定位器、發布資料表或背景執行器。

`RepairWorkflow(artifacts, publication, source).graph` 是未指定獨立 Saver 的 compiled subgraph，繼承呼叫者 Saver。暫存檔沿 `FilesystemState`／`StateBackend`；真正 Memory 內容仍在原 Store，發布仍使用原 `PublicationStore` 短交易、expected revision 和操作回執。`kind=repair` 保存本次來源，不前進 B 的 `processed_source`。

新來源 port 的 `read(reference)` 只確認固定來源可讀；其返回物件由來源 owner 定義。C 不讀舊 `segments`、不自建原話副本、不把發布成功當作內容已專業核准。

## 官方能力與限制

- [LangGraph subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)：共享 state keys 可直接把 compiled child 加為 node；父圖 checkpointer 供子圖使用。這是六節點持久化的原生接點，並非自行寫 workflow／saver。
- [Deep Agents backends](https://docs.langchain.com/oss/python/deepagents/backends)：StateBackend 存在 graph state，隨 checkpoint 保存。另核已裝 0.7.13 `backends/state.py` 的公開 constructor、`upload_files`／`download_files` 使用方式；不抽取其私有 Pregel internals 自己實作。
- 版本沿原鎖定 LangGraph 1.2.11、Deep Agents 0.7.13、SQLAlchemy 2.0.52；公開 OSS MIT。patch 使用 OpenAI Agents SDK 0.22.0 的 `apply_diff`，其獨立來源／限制由本輪 patch 作者記錄；本核心不啟動 SDK Runner、client 或 provider。依賴鎖定與同步由主代理負責。

較新的官方網頁不等於本案採用未鎖定 API。採用的是上述已安裝穩定版本的既有接點；正常 graph 中斷／續跑與 OS 崩潰／外宿主停止證据分開，不從 Future timeout 宣稱安全重試。

## 已修正差距

1. 舊 `_validate` 捕捉所有 `ValueError`，會把來源或 Store I/O 包成 `invalid_edit`。先以兩個直接故障及真暫存內容帶 citation 的來源 I/O 重現，再改為只捕捉已知 `StagedMemoryValidationError`；未知來源／Store 故障仍向 App 傳遞並停止。
2. 舊 `_publish` 已取得 applied receipt 後，對最新 current 缺失／倒退仍可能回 `applied`。新增共用 `_current_after`：原結果與 current 都須屬本文件，且 current revision 至少為 applied revision，否則 `PublicationUncertain`。真正較新的 B3 不回退，仍回最新 head／guide 與原 applied head。
3. 舊 `reconcile(operation_id, source_reference, edits)` 沒有證據卻回傳 caller 傳入的 edits。新 ABI 為 `reconcile(request: PublishRequest)`，只接受原生已保存的原請求，核完整 digest、操作身分、repair kind／來源、文件、base revision 與原結果 memory／revision。回傳回執真正證明的 applied head、目前 head／guide、source_reference；**不接受或回傳 changes／caller edits**。未找到、不匹配及讀取故障一律不確定，不呼叫 publish、重建候選或重讀原話。

最後一項的必要限制：`PublishRequest.artifact_digest` 證明準備的內容，不等於證明原 patch 文字。App 要呈現原修改，必須另外使用原生保存的原 tool binding；本核心不創造新的修改證據權威。停止／恢復 owner 仍由 App 負責，查回回執不會自動清掉 native pending node。

## 首敗與實際結果

首次執行新檔的窄反例時 App 環境尚未完成主代理的依賴同步，結果 **1 collection ERROR／7.11s**：`ModuleNotFoundError: agents`，未進入測試本體；此失敗只屬環境準備，不當作已觀測行為反例。未自行安裝或改鎖檔。

依賴同步完成後，仍保留舊判斷先執行：

- typed validation／current head 反例：**6 FAIL／1 PASS／17 deselected／14.47s**。前兩個 ValueError 與真 source citation 驗證故障被吞成 invalid edit；current None／older 未拒絕，另一文件則太晚才由讀 guide 拋一般錯誤。
- 新 reconcile ABI：**8 FAIL／23 deselected／14.18s**。其中一例證明舊介面真的接受與原修補不同的 caller edits；其他例先因新 ABI 尚未實作而失敗。
- 有限修正後，當時新檔完整 **31 PASS／13.40s**。
- 補最後一個實際 publication commit 後回覆遺失反例：**1 PASS／31 deselected／10.88s**。真原生 child 保留 `publish` pending 與已保存 request；reconcile 查回 revision 2，publish 呼叫仍只有原一次，沒有偷偷 resume／清 pending。此後未改程式。
- 原 `test_publication.py` 與 `test_memory.py`：**34 PASS／6.19s**。

新檔共 32 個不同案例由 31＋1 分批驗過，不寫成同一次 32 全綠；原 34 回歸也是分開執行。各命令都有 pytest cache 存取警告，不冒稱沒有警告。

執行環境為新 App 已鎖定依賴，沒有讀入舊實驗模組：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q S:/caliburn/packages/consultant-memory/tests/test_repair.py
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q S:/caliburn/packages/consultant-memory/tests/test_publication.py S:/caliburn/packages/consultant-memory/tests/test_memory.py
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q S:/caliburn/packages/consultant-memory/tests/test_repair.py -k lost_publication_reply
```

覆蓋 1–8 patch／12,000 字元邊界、舊 old_text/new_text 拒絕、兩筆只成功第一筆時不發布、無 Memory 不由 C 初始化、stale base 不套用、來源返回 opaque object、來源不可用停止、逐 edit 原生中斷後新 workflow 同 Saver 續跑、不重做第一筆、原回執查回不回退最新 Memory、不推進 B 游標，以及上述三類修正。

測試是實際 LangGraph／InMemorySaver／StateBackend／InMemoryStore／SQLite ORM publication；來源 port 是明示合成 double。新 workflow 重建在同程序，不是新 OS 宿主。零 provider／真 PG／正式 DB 修改，沒有本頁作者的自然模型、完整顧問、跨程序停止、完整 App C 接線或真人品質證据。獨立 review 由主代理另外安排。
