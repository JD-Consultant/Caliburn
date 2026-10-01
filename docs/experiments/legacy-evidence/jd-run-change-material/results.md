# 固定 AI 操作集合的整輪材料：作者驗證

- 日期：2026-09-13；起始基準 `f098fcb2`。
- 本次作者範圍：`storage/history.py`、新 `tests/test_run_change_material.py` 及本紀錄。未改 schema／generated／API／模型／資料表，沒有 DB 或 provider 呼叫。
- 狀態：固定集合的 SQL 材料接點與純反例完成；**不證明 native 回合全集、terminal、CV-01 畫面或完整 App 已完成。**獨立審查與真 PG 由其他協作者分別記錄。

## 1. 實際介面與責任

[HistoryReader.read_run_change](../../../../experiments/jd-relational-app/src/jd_relational/storage/history.py) 接受 `document_id: str`、`run_id: str`、`operation_ids: tuple[UUID, ...]`，回 `RunChangeMaterial`：

| 欄位 | 語意 |
|---|---|
| `continuity` | `none`／`continuous`／`discontinuous`，只描述 caller 提供的固定 committed 集合 |
| `receipts` | 依 result revision number 排序的原 `SavedOperation`；不依 UUID 或 created_at 猜執行順序 |
| `base`／`result` | 連續時首筆 base／末筆 result 的既有 `HistoricalRevision`；其他情況為 `None` |

原生 owner 先驗過的 confirmed committed IDs 是 caller 責任。reader 嚴格要求 tuple、0..96 個不重複 UUID，保留既有非空 run 字串語意，不讀 Saver／current head、不推定 run 完成。

同一次既有 `READ ONLY REPEATABLE READ` 交易內先查文件存在；非空集合沿原 `_REVISION_READ` 的同文件 parent／producer join，批次選 metadata 並排除 snapshot。抽出的 `_revision_producer` 與原 `_verified_revision` 共用原回執、parent／版號／producer 及格式核對。固定集合連續才沿原 `_revision` 讀兩個完整端點，保留 snapshot／digest 嚴驗。純測觀察 empty 為 1 SELECT、不連續 2 SELECT、連續 4 SELECT；96 個操作也不逐筆讀完整快照。

缺少指定行或 scope／committed 過濾後不完整回 `operation_missing`，不退化成空集合；已取得列矛盾回 `stored_content_mismatch`；driver 故障沿原 `read_failed`。固定清單之外較晚同 run 操作不混入；中間有人工／別 run 版次時只回原回執，不提供誤歸屬的 S/E。

## 2. 首敗與最後結果

在 `experiments/jd-relational-app`、已鎖 Python 3.12 環境執行：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_run_change_material.py -q -p no:cacheprovider --tb=line
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_run_change_material.py -q -p no:cacheprovider --tb=short
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_run_operations.py tests/test_storage_history.py -q -p no:cacheprovider --tb=short
```

| 執行 | 實際結果 | 分界 |
|---|---|---|
| 新測試先於方法落檔 | **54 FAIL，1.39s** | 全部為 `HistoryReader.read_run_change` 尚不存在的 AttributeError，不是已執行 SQL 的產品錯誤 |
| 新方法落檔後同檔 | **54 PASS，0.98s** | 真 SQLAlchemy statement／shared receipt decoder／snapshot codec，connection 為有界 double，0 DB |
| 原 run operations／history 回歸 | **50 PASS／12 SKIP，0.98s** | 37 個 run operations＋13 個 history 純案例；12 個 PG 案未啟用，不稱已驗 |

新 [54 個案例](../../../../experiments/jd-relational-app/tests/test_run_change_material.py) 包含：反 UUID／時間順序、兩次連續寫入、同欄改回仍保留兩個事件、人工／別 run 插入、不同 parent identity、固定單筆排除較晚同 run、96 個操作固定查詢數、無效參數先拒、空集合仍核文件、缺列／錯 scope／壞 metadata／no_change／重複列、端點 digest／format／缺失，以及四個 SQL 階段的安全 driver 失敗。改回案例直接呼叫既有 `compare_snapshots` 確認淨結果為空，沒有新增 diff 演算法。

作者檢查 `git diff --check` 通過。這些測試不代證 PG planner／真交易可見性、原生 run 完整性或 Web 接合；真 PG／獨立審查另列，不將各次數字相加冒充單次驗收。
