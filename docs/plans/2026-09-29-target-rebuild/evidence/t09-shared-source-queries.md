# T09 共享唯讀 JD Memory 來源查詢抽取

2026-09-30；狀態：**本有界 refactor 已驗證，可供主線接人工來源列表／深讀／差異；不代表 T09 HTTP／UI 或整體 Goal 完成。**

## 範圍與依據

- 沿 [JD 保存 §3.3／3.5](../../../implementation/jd-storage.md#33-直接來源按需讀取與候選模型寫入t07-增量) 的固定來源與差異權責，以及 [T07 差異證據](t07-jd-changes-source.md)。沒有新增保存、schema、migration、HTTP 或 UI。
- 起始 `S:\caliburn`／`target-rebuild` 工作樹乾淨；施工期間主線新增 HTTP 契約／生成物等變更，均未由本切片修改、清理或提交。
- 寫入僅三個 workflow 檔、獨立專項 PG 測試及本 evidence；未修改任務表、其他 owner、transport 或生成檔。
- 已使用 `superpowers:test-driven-development` 的行為測例與 refactor 回歸方式，以及 `superpowers:verification-before-completion` 的實測後回報原則。依本次明確指示，以原行為基準 → 測例 → 等價抽取 → 回歸執行，沒有製造 missing-import Red，也不宣稱這次有新行為 Red。

## 檔案與公開介面

[jd_source_queries.py](../../../../apps/api/src/caliburn/workflows/jd_source_queries.py) 提供：

```python
async def read_memory_source_titles(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    source: MemorySource,
    snapshot_id: UUID | None,
    interview_through_sequence: int,
) -> tuple[str | None, str | None, bool]: ...

async def read_memory_source_changes(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    reference: JdSourceReference,
    snapshot_id: UUID,
    interview_through_sequence: int,
) -> JdSourceChanges: ...

async def read_fixed_memory_source(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    source: MemorySource,
    interview_through_sequence: int,
) -> MemoryObjectRevision: ...
```

- `read_fixed_memory_source` 是前兩者共用的固定來源驗證：從原 Memory owner 讀指定檔案的發布 snapshot，驗 covered sequence 上界、snapshot membership 選中的 object／revision 及 layer。直接返回該固定修訂，不按標題搜尋、不追 latest。
- titles 保留 `(current_title, historical_title, changed)`：同名同修訂不變；改名保留歷史標題；固定新版 membership 證明缺席時返回 `(None, original_title, True)`。`snapshot_id=None` 仍是固定空比較端點，不自動改用最新發布。第三值不混入 JD 本身的 `needs_review`。
- changes 保留同身分前後修訂、理解所引用情境的鏈路差異與經原訪談 owner 驗證的正式序號。固定資料失效或基礎設施錯誤不吞成空結果／刪除，讀取不確認引用對齊。
- `MemorySourceChange`／`JdSourceChanges` 移到新模組；[jd_changes.py](../../../../apps/api/src/caliburn/workflows/jd_changes.py) 明確 import／re-export 原名稱，原 transport 的 import、投影及回傳型別持續可用。
- [jd_reads.py](../../../../apps/api/src/caliburn/workflows/jd_reads.py) 保留候選／execution 檢查、原引用選取及同來源標題快取，再呼叫共享 titles。`needs_recheck` 仍合併既有 `reference.needs_review`。
- `JdChangesWorkflow.read_source` 保留 execution kind／ACTIVE 或 PAUSED 檢查、自己的候選位置與 citation_ref 解析、訪談分支及缺 comparison endpoint 的拒絕，再呼叫共享 changes。

## 驗證結果與重現

以下測試命令工作目錄均為 `S:\caliburn\apps\api`，使用 `.venv-target/Scripts/python.exe`。PG 只用指定隔離 DB；既有 fixture 建立／清理本次隨機 schema，不操作 demo DB。

```powershell
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
& .venv-target/Scripts/python.exe -m pytest tests/unit/test_jd_source_rules.py tests/unit/test_jd_read_projection.py tests/contracts/test_jd_read_tool.py tests/contracts/test_jd_changes_wire.py tests/integration/test_jd_reads.py tests/integration/test_jd_changes.py tests/integration/test_jd_manual_changes.py -q -p no:cacheprovider
```

抽取前 **26 passed in 11.46s**。最初在 repo root 執行時，兩個既有 integration test 的 `tests.integration` import 未解析；轉到 API 工作目錄後正常。另停用 pytest cache，避開既有 cache 權限警告；這些環境問題不是業務 Red。

```powershell
& .venv-target/Scripts/python.exe -m pytest tests/unit/test_jd_source_rules.py tests/unit/test_jd_read_projection.py tests/contracts/test_jd_read_tool.py tests/contracts/test_jd_changes_wire.py tests/integration/test_jd_reads.py tests/integration/test_jd_changes.py tests/integration/test_jd_manual_changes.py tests/integration/test_jd_shared_source_queries.py tests/integration/test_jd_source_tool_memory.py -q -p no:cacheprovider
```

抽取後 **33 passed in 17.18s**：16 項 unit／contract、17 項真 PG，無 skip。

[新增 6 項專項 PG 測試](../../../../apps/api/tests/integration/test_jd_shared_source_queries.py) 包含：

- A 都已完成時，三個介面仍可直接查詢原固定來源；PG `SET TRANSACTION READ ONLY` 下通過，保留原正文、改名歷史、差異及 `needs_review`。
- title 的 `snapshot_id=None` 不追目前已有的新 snapshot。
- 真實但不屬於原 snapshot 的較新 revision、錯誤 layer、另一個真實 job file、原來源超過訪談上界，各由三個介面拒絕。
- 舊 snapshot 在訪談上界內但比較 snapshot 超界，titles／changes 均拒絕；深讀舊 snapshot 仍可用。

原受影響 PG 回歸另涵蓋理解正文不變但所引情境改動、晚到發布不漂移、刪除後同名重建不替換身分、取消後 A 不可讀、跨檔引用拒絕、缺 snapshot、storage exception、人工差異與來源確認流程。

```powershell
& .venv-target/Scripts/python.exe -m ruff check src/caliburn/workflows/jd_reads.py src/caliburn/workflows/jd_changes.py src/caliburn/workflows/jd_source_queries.py tests/integration/test_jd_shared_source_queries.py
& .venv-target/Scripts/python.exe -m ruff format --check src/caliburn/workflows/jd_reads.py src/caliburn/workflows/jd_changes.py src/caliburn/workflows/jd_source_queries.py tests/integration/test_jd_shared_source_queries.py
& .venv-target/Scripts/python.exe -m mypy --config-file pyproject.toml --follow-imports=silent --cache-dir nul src/caliburn/workflows/jd_reads.py src/caliburn/workflows/jd_changes.py src/caliburn/workflows/jd_source_queries.py
```

範圍內 Ruff check／format、3 個 production 檔 mypy 及 diff whitespace 檢查通過；不宣稱全專案型別檢查或全庫測試通過。

## 主線接線界線與風險

共享查詢是內部跨 owner 查詢，不是公開授權入口。主線人工 caller 必須先固定正式 JD 修訂、從該修訂選出允許的原引用，並提供同檔案的固定比較 snapshot 與正式訪談上界；不可把使用者任意輸入的 Memory identity 當成來源資格。A caller 已保留原 gate，沒有增加全歷史讀取入口。

理解含情境引用時，changes 會在共用固定來源驗證後，額外透過既有查詢讀原 snapshot／membership 以展開舊鏈；都指向同一不可變 snapshot，沒有新增快取／validator／保存或追 latest。未量測大型引用集合效能。

人工來源 HTTP、UI、原引用鏈導覽的產品接線與驗收由主線負責，本切片未測瀏覽器或真模型。未讀憑證、未付費、未 commit、未再委派。
