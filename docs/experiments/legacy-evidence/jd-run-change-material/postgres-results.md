# 整輪 JD 變更材料：獨立真 PostgreSQL 驗收

- 日期：2026-09-13。
- 實作者／驗收者：`jd_ref_signer_preflight`，不是 `HistoryReader.read_run_change` 作者。
- 唯一新增測試：[test_run_change_material_postgres.py](../../../../experiments/jd-relational-app/tests/test_run_change_material_postgres.py)。未修改產品、schema 或其他測試。
- 結論：**首次真 PG 執行 13 PASS／0 FAIL，7.76 秒**。沒有需要以測試放寬來通過的失敗。

## 實際執行與邊界

在隔離 App 執行 `uv run --frozen --offline pytest -q tests/test_run_change_material_postgres.py`，明示 `JD_RELATIONAL_TEST_DB=1`、`PYTHONUTF8=1`，沿現有 lock 與 uv cache。

使用既有 fixture：`127.0.0.1:55436`、`caliburn_jd_relational_test`。連線後先驗固定測試使用者、PostgreSQL **18.6／180006** 及 Alembic **20260913_0001**。沒有 setup、建立／刪除資料庫、啟動服務或讀取正式設定。

```text
collect-only: 13 tests collected in 0.80s
first real PG run: 13 passed, 1 warning in 7.76s
```

唯一警告是 pytest 無法寫入既有 cache 暫存位置（Windows 存取被拒）；測試執行與斷言全部完成，不是 setup error，也未因此重跑或修改權限。

測試透過實際 `JdStorage`／共同操作保存新的合成文件；`FakeAuthority` 只供測試建立資料，不代表真 AI writer 准入、原生 run 完整性或程序停止證明。查詢則使用實際 `HistoryReader` 與 PostgreSQL 交易。合成資料保留；損壞反例於 `finally` 僅恢復該測試自己剛建立的指定資料列。

## 通過範圍

| 情境 | 實際證明 |
|---|---|
| 空捕捉集合 | `none`、空 receipts、無端點 snapshot；只查文件存在，缺文件不假裝空結果。 |
| 多次修改再改回 | 三次 committed 保存全保留；首版／末版 snapshot 相等、純淨差異為空；較晚人工 head 不混入。 |
| 中途人工／另一 run | 兩個獨立案例均回 `discontinuous`，只包含指定 run 的 receipts，不提供可能混入他人修改的首末淨對照。 |
| 順序 | 刻意倒置 UUID 與 stored `created_at`，並打亂輸入順序；仍依實際 revision chain 排序。 |
| 捕捉後新增同 run | 後續已 committed 操作不會被擴入原先 operation IDs。 |
| 遺漏中間 ID | 即使三筆同 run，僅選首末仍不假造連續性。 |
| 同一讀取快照 | 首個查詢建立快照後，由另一連線修改指定 receipt 時間並實際提交同 run 新保存；原讀取仍得到舊 receipt 與舊端點。當場核 `repeatable read`／`transaction_read_only=on`；後續明示擴大捕捉才看見第三筆。 |
| 不合法保存範圍 | unknown、另一文件、另一 run、manual、`no_change`、`stale_view` ID 均回固定 `operation_missing`，不回部分材料。 |
| 儲存損壞 | 三案分別破壞 receipt 格式、中間操作 base、末端 digest，均回固定 `stored_content_mismatch`；沒有洩漏合成私密標記。恢復原列後正常讀取。 |
| 讀取負擔 | 1 筆與 8 筆捕捉使用相同查詢數（斷言上限 5），實際每次只回 2 份完整 snapshot；非連續／空集合不取完整 snapshot。 |
| 不使用目前稿／不寫資料 | 窄追蹤只有 SELECT、沒有 `jd_head` 查詢；正常讀取前後比對該文件全部 13 張業務表 counts 不變。 |

完整 snapshot 負擔由實際 PostgreSQL cursor 的輸出欄位及 row count 核對，不只以 SQL 字串中出現 `snapshot` 推定。返回 snapshot 的 caller-local 修改也不會改動下次讀取的原資料。

## 未涵蓋及不能宣稱

- 本檔最大真保存數為一輪 **8 筆**；不宣稱真 PG 已執行 96 筆上限或效能壓測。0..96 distinct UUID 的完整輸入界線由作者的獨立純測試負責。
- 為有界材料層反例，主要以 profile 文字產生真版本；不重複既有所有 task／relation／source 差異案例。
- 只完整驗證首末 snapshot，中間版本依 metadata／receipt 接續核對；不聲稱本方法逐一完整讀取或重新驗證所有中間 JSON 內容。
- operation IDs 的「原生 run 已完整且全部 committed」前提由上游 owner 負責；本檔不能將 `FakeAuthority`／測試選取 IDs 當成該前提的正式證據。
- 沒有模型／provider、HTTP、瀏覽器、Memory、取消／恢復或整輪撤回驗收。主代理另負責舊 history 的真 PG 回歸及整體整合，本輪不重跑其測試。
