# T04：受訪者工作記憶保存證據

- 日期：2026-09-29；更新：2026-09-30；狀態：**施工中，未完成 T04**。接續 T03 `4e673cf8`，唯一進度入口為[任務表](../tasks.md#t04-memory-可變候選不可變修訂與快照)。
- 責任：[Memory 保存接線](../../../implementation/memory-storage.md)、[資料保存](../../../architecture/persistence.md)。本頁記實測，不另定模型工具、角色或發布語意。

## 1. 第一切片：內容、引用集合與標題純規則

新增 `features/work_memory/models.py`／`changes.py`：

- 必填且非空白的 `title`／`description`／Markdown `body`，原字串保持；局部改動不修改未指定欄位。內部 body 參數是後續受控 patch 的結果，不是模型整文覆寫工具。
- 身分集合引用增刪：省略成員保留，新增已存在成員無效果；又加又刪、移除不存在及新增不允許來源拒絕；移除至空集合合法。
- 目前單層 map 精確 title → ID；不 trim、大小寫折疊或 Unicode 正規化。同名多筆視為資料不一致，不默取第一筆。原引用／重入操作已绑定的 ID 不隨名稱重用重定向。
- 新純規則加入既有依賴檢查，禁止 SQLAlchemy 等 I/O 框架侵入；不另造架構分析工具。

子代理只負責四個純值／測試檔，主代理審核與整合。寫入邊界、適用責任文件、禁止新增 schema／服務／提交均在委派中明確限定。研究與保存設計由主代理完成；[官方機制比較](../../../implementation/memory-storage.md#4-官方機制比較與取捨)區分 MVCC、ORM 並行計數器與業務歷史，不假稱採用版本套件即可滿足 Memory 快照。

### 1.1 Red／Green 與實際命令

工作目錄 `S:/caliburn/apps/api`，Python 3.14.7（`.venv-target`）：

```powershell
.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_work_memory_values.py -q -p no:cacheprovider
```

子代理先寫測試及未驗證的最小 dataclass，**15 failed**（預期的 `InvalidMemoryChangeError` 未發生，不是環境／匯入失敗）；補實作後 **61 passed**。主代理另先加入 `work_memory.changes` 越界 import 反例，**1 failed、12 passed**；補檢查後重跑整合：

```powershell
.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_work_memory_values.py tests/unit/test_import_boundaries.py -q -p no:cacheprovider
.venv-target/Scripts/python.exe -B -m ruff check --no-cache src/caliburn/features/work_memory tests/unit/test_work_memory_values.py tests/unit/test_import_boundaries.py
.venv-target/Scripts/python.exe -B -m ruff format --check --no-cache src/caliburn/features/work_memory tests/unit/test_work_memory_values.py tests/unit/test_import_boundaries.py
.venv-target/Scripts/python.exe -B -m mypy --cache-dir ../../.research-tmp/mypy-t04 src/caliburn/features/work_memory
```

主代理結果：**74 passed**；Ruff 通過，5 檔格式通過；mypy 3 source files 通過。標題原文／Unicode、局部更新、引用資格集合、空集合及原身分保留均有反例。

本片沒有改公開契約、HTTP／UI 或已接線保存流程，依風險只跑純值及依賴測試；不重跑 T03 已通過的 405 項及瀏覽器旅程。10 份相關文件的 206 個本地連結／anchor、code fence 及差異空白檢查通過；新增 Memory 圖以 Mermaid 11.17.2／Chromium 實際渲染並檢視，無截斷。未使用 OpenAI、未讀取密鑰、未外送訪談，模型費用 US$0。

### 1.2 未驗邊界與下一步

純函式中的 `allowed` 和單層 map 由呼叫者提供；不證明來源已正式化、在 F 以內、同檔案或角色有權。**目前沒有 Memory PostgreSQL 候選／發布服務**，不把值測試當成真正版本、交易、恢復或可用 Agent。

下一片建立最小真 PG 路徑：有效訪談來源 → 情境候選 → 理解候選 → 固定發布快照讀回；再覆蓋修改／刪除／回退、原結果及未變重用。V4A 與模型 schema 留在 T05，Agent 與完成資格接線留在 T10／T11。T04 保持未勾選。

## 2. 第二切片：正式來源身分與 Memory 固定範圍

2026-09-30 接續 `5c5b09b8`，先交付上一節垂直路徑中的有效來源邊界；無新 migration、原文副本或模型 API：

- 訪談 owner 增加 `read_interview_sources`，用內部 ID 選取已正式化來源；SQL 保持同檔案與指定上界。整筆資格檢查、去重排序及原文保留不另造第二個來源服務。
- `work_memory/sources.py` 根據原要求的正式員工來源身分解出 F，不拿目前最後答覆／最大序號或奇偶規則代替。`MemorySourceWindow` 保留固定 `(K,F]`；已涵蓋的合法要求不產生空批。
- 必處理區間沿原文讀取，引用可查更早 `≤F` 的合法來源；取消／未完成、跨檔案、不存在、越 F 任何一筆均不允許混入。Memory 空引用合法，因此空集合不被來源查詢的「空選取錯誤」誤傷。

### 2.1 實測與審查

主代理先建批次範圍測例和明確 stub，真 PG **13 failed**（`NotImplementedError`，非環境失敗）；補實作後通過。子代理限於訪談 owner 查詢及其測試，**9 failed → 9 passed**；其與既有訪談讀取合跑 **35 passed**。主代理審核後完整跑受影響集合：

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
.venv-target/Scripts/python.exe -B -m pytest tests/integration/test_memory_source_windows.py tests/integration/test_interview_source_queries.py tests/integration/test_interview_reads.py tests/unit/test_work_memory_values.py tests/unit/test_import_boundaries.py -q -p no:cacheprovider
.venv-target/Scripts/python.exe -B -m ruff check --no-cache src tests
.venv-target/Scripts/python.exe -B -m ruff format --check --no-cache src tests
.venv-target/Scripts/python.exe -B -m mypy --cache-dir ../../.research-tmp/mypy-t04 src
```

cwd `apps/api`；結果 **122 passed**（48 真 PG，22 為本片新增，0 skip），16.52 秒；Ruff 全部通過、116 檔格式通過；mypy **94 source files** 通過。每項 PG 使用既有 fixture 的獨立隨機 schema，僅回收自己的測試 namespace。沒有執行模型、沒有憑證存取、模型費用 US$0。

關鍵反例：正式員工 F=5、其後答覆=6；即使再有員工=7、答覆=8，延後 bind 同一原來源仍是 F=5。K=2 時新資料為 3–5，引用仍可指 1–2；已涵蓋至 5／7 則不重造同一批。非員工 K/F、非法數值、缺失或不可用來源均拒絕。測例刻意不用員工必為偶數的假設。

子代理對主代理的 Memory 範圍接線另做只讀審核，未發現阻擋缺陷；它沒有代跑主代理測試。pending／cancelled／跨檔案／不存在的細節在正式來源 owner 測例驗證，Memory bind 未重複每一組相同參數。10 份相關文件 207 個本地連結／anchor 與差異空白通過；本片未改圖形，沿用第一切片的實際渲染。

### 2.2 限制與後續

本片驗證的是**正式來源解析與固定讀取**。尚無 Memory 批次保存、恢復 writer／generation、候選修訂、固定選用、發布及原操作結果；也未證明模型不會誤解訪談。新批次呼叫方必須從正式 intent 及同一已發布基底給來源身分／K；同批恢復沿持久 window，不重新 bind。這些接線仍由後續 T04／T08／T11 完成與驗證。

下一切片沿 §1.2 做候選 → 快照真 PG 保存，重用本片來源查詢；不再從頭設計來源身分或另存原話。T04 仍未勾選。

## 3. 第三切片：固定物件修訂與正文重用

2026-09-30 接續 `acc5e85e`。先完成候選／發布所需的固定修訂保存，不假裝已接成候選或正式快照入口。schema 與生命週期只在 [Memory 保存接線 §2.1](../../../implementation/memory-storage.md#21-已落地固定物件修訂) 維護。

主代理負責領域 service 與真 PG 反例；子代理的唯一寫入範圍為 revision persistence、migration `0011` 及 `env.py` 註冊。主代理整合審閱 migration 的延後封存、引用鎖定、同檔案／層別 FK 與實際測試，不將子代理完成當 T04 完成。

### 3.1 Red／Green 與驗證

主代理先建 7 項保存測例及明確 stub，**7 failed**（未實作，不是環境錯誤）；完成後加歷史竄改、半套提交與非法來源反例，共 **12 項真 PG passed**，4.93 秒。

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
.venv-target/Scripts/python.exe -B -m pytest tests/integration/test_memory_revisions.py -q -p no:cacheprovider
.venv-target/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider
.venv-target/Scripts/python.exe -B -m ruff check --no-cache src tests migrations
.venv-target/Scripts/python.exe -B -m ruff format --check --no-cache src tests migrations
.venv-target/Scripts/python.exe -B -m mypy --cache-dir ../../.research-tmp/mypy-t04 src
```

cwd `apps/api`。新增全庫 migration，故整合驗證升至全後端而非只測 12 項：首次 **501 passed／1 failed**，172.73 秒。唯一失敗是舊 JD migration 測試升至 `head` 卻硬斷言仍為 `0010`；改為明確升至該測例真正負責的 `0010_jd_candidates`，仍保留升級／重跑、原結果不變及拒絕破壞歷史的全部斷言。其所在 `test_jd_candidate_storage.py` **13 passed**，4.63 秒。沒有因純測試目標修正再重跑未受影響的全套，也沒有把首次全套說成零失敗。

Ruff 通過、132 檔格式通過，mypy **97 source files** 通過。子代理另外在獨立真 PG schema 驗升級／重跑升級、Alembic metadata 對齊及 deferred trigger 設定，均通過，未改既有 schema。10 份相關文件的 209 個本地連結／anchor、code fence 與差異空白通過；Memory 兩張 Mermaid 圖實際渲染，新增 schema 圖已目視檢查，文字／箭頭無截斷。

關鍵反例：

- 只改 title／引用重用正文；同內容與來源無效果；修改正文後再改回仍新修訂，不回到舊身分。
- 情境換版後，理解新固定修訂指新版、舊修訂仍指舊版；理解正文未改可重用。
- 11 種歷史 UPDATE／DELETE 及兩種封存後引用 INSERT 被 DB 拒絕；未封存標頭到 COMMIT 仍被拒絕，沒有留下半套修訂。
- 未正式來源、錯層、跨檔案、同物件混用兩個來源修訂被拒絕；外層 transaction 失敗撤回所有本次資料。

### 3.2 未驗邊界

固定修訂 service 不持有 current pointer、角色、候選位置、執行分支或原操作回執；這些是下一片的必要接線，不可直接拿本函式暴露成 B1／B2 工具。尚無候選 CRUD／位置回退、固定快照 map/read、整版發布與發布原結果。尚未證明完整 A／B1／B2 或模型語意品質。未呼叫模型、未讀密鑰、費用 US$0。
