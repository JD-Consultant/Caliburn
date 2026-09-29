# T04：受訪者工作記憶保存證據

- 日期：2026-09-29；狀態：**施工中，未完成 T04**。接續 T03 `4e673cf8`，唯一進度入口為[任務表](../tasks.md#t04-memory-可變候選不可變修訂與快照)。
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
