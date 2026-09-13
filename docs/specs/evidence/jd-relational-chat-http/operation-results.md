# 原 AI 回合的已保存 SQL 操作查核

- 日期：2026-09-13；施工基準 `2734b82b025adcd8a032f947a9a688c7e1ea626f`。
- 狀態：此唯讀 SQL 接點與有限反例已完成；不是聊天 HTTP／完整 App 或自然模型驗收。
- 範圍：只新增 `HistoryReader.read_run_operations`、兩份測試及本證據。未改 schema、index、migration、回執格式、依賴或 writer authority，0 provider。
- 責任沿[既有讀取切片](../../2026-09-13-jd-read-change-implementation.md)與[共同保存交易](../../2026-09-13-jd-transaction-service-slice.md)；本文件不另定 run 或 operation 的資料權威。

## 1. 接點與結果語意

[實作](../../../../experiments/jd-relational-app/src/jd_relational/storage/history.py)：

```python
HistoryReader.read_run_operations(
    document_id: str,
    run_id: str,
    *,
    limit: int = 96,
) -> tuple[SavedOperation, ...]
```

每次沿原有 `_read()`，在第一個 query 前設定 `READ ONLY REPEATABLE READ`；同一次短交易先核文件存在，再查 `jd_operation` 的 exact `document_id`、`ai_run_id` 及 `origin='ai'`。沒有跨來源呼叫、writer gate、head／snapshot 讀取或逐列查回。

每行沿原有 `_receipt` 呼叫 [SavedOperation.from_row](../../../../experiments/jd-relational-app/src/jd_relational/storage/receipts.py)，與 `JdStorage.get_operation` 共用永久回執解碼／結果一致性檢核。回傳原 operation ID、request digest、origin、run、base/result IDs、status、receipt body 及時間；沒有複製正文、生成模型文案或發 refs。

`committed`、`no_change` 與已確認失敗都是原本已保存的行，全部保留。`committed` 不表示「這輪所有操作成功」；`no_change` 不增加版次；失敗行沒有結果版。後來 head 前進，不會把原回合的 result IDs 升級為新 head。

順序是 `operation_id` 升序，只供穩定呈現；不聲稱交易提交序、工具呼叫序或時間排序。呼叫端必須按 native bindings 的原順序配對，並核對身分、意圖及結果。SQL 清單不能取代 native run 的生命週期權威。

輸入的 document/run 沿既有持久 identifier 語意：非空白字串、有效 UTF-8、無 NUL，不將既存非 UUID run 重新解釋或截改。HTTP／coordinator 的 canonical UUID、dataset／run scope 仍由其正式 decoder 負責。`limit` 是嚴格整數 `1..96`，不接受 bool。

| 情況 | 結果／固定錯誤 |
|---|---|
| 文件存在，該 snapshot 沒有匹配行 | 空 tuple；不能推斷 run 不存在、operation 失敗或 writer 已停止 |
| 文件不存在 | `HistoryError('document_missing')` |
| 超過 caller limit | 查 `limit+1` 證明超界後回 `run_operations_limit_exceeded`；不回部分 tuple 假稱完整 |
| 非法輸入 | `invalid_input`，尚未取得 DB 連線 |
| 永久回執內容／結果矛盾 | `stored_content_mismatch`，不公開原始內容或例外鏈 |
| 連線或 SQL 讀取失敗 | `read_failed`，不公開 driver payload 或例外鏈 |

此接點的完整性只涵蓋該次 SQL snapshot 內可見、匹配 scope 的全部行。terminal run 的 exact set 檢核由 coordinator 與 native bindings 對照；active run 的前後讀取可能交錯，不能只憑一個空 tuple 或一份子集合標成 confirmed／完成。本接點不執行 recovery，也不將查不到的 operation 寫成失敗。

## 2. 首敗與最後實測

兩份新測試分別為[離線反例](../../../../experiments/jd-relational-app/tests/test_run_operations.py)及[真 PostgreSQL 接合](../../../../experiments/jd-relational-app/tests/test_run_operations_postgres.py)。

| 執行 | 實際結果 | 證據界線 |
|---|---|---|
| 新離線測試先於實作 | **37 FAIL，0.66s** | 全部精確落在尚無 `read_run_operations` 的 AttributeError；不是業務 SQL 已執行後失敗 |
| 新方法落地後，同一離線檔 | **37 PASS，0.29s** | 固定 SQL 結構、read options 先於 begin、輸入、8 種原回執狀態、共用 mapper、超界、壞回執及安全錯誤；無 DB |
| 新 PG 檔首次執行 | **5 PASS，1.45s** | 真 SQL／COMMIT 與 RR 交錯，未使用 provider |
| 既有 `test_storage_history.py` 回歸 | **25 PASS，1.83s** | 此次明示 PG opt-in；13 個離線案例、12 個真 PG 案例，與新測試分開記錄 |

真 PG 新案例：

1. 同原 run 的 committed、no_change、stale_view 全部查回；人工與其他 AI 回合／其他文件排除。後來 head 已前進，原 base/result 仍保持；與既有 `get_operation` 的原回執相同。讀取只發兩個 SELECT，該文件十三表的列數前後相同。
2. 只在另一份文件有相同 run 字串時，本文件回空 tuple；不存在文件明確拒絕，不越 scope 查找。
3. 真 PG 以 limit=1 驗正好一行成功、第二行存在時明確超界；limit=2 可取全。預設 96 對應 SQL LIMIT 97 另由離線 SQL assertion 驗證，沒有冒稱真 PG 已建立 97 行。
4. 第一個文件 SELECT 已建立 read snapshot 後，用另一條 PG 連線提交同 run 的第二筆操作；當次仍只讀到第一筆，下次才看到兩筆。測試現場查得 `transaction_isolation='repeatable read'`、`transaction_read_only='on'`；故障／交錯 hook 必須命中。
5. 只暫改本案例新建操作的 receipt JSON 為未知版本及合成私有 marker，讀取回固定 `stored_content_mismatch`；finally 恢復本案例原 receipt，確認可再讀。沒有刪除資料。

PG 沿[既有測試 engine](../../../../experiments/jd-relational-app/tests/test_storage_postgres.py)，僅 `JD_RELATIONAL_TEST_DB=1` 啟用 `127.0.0.1:55436/caliburn_jd_relational_test`。fixture 實查 PostgreSQL **18.6** 與既有 migration `20260913_0001`；沒有 setup／drop。合成文件與操作保留。`FakeAuthority` 僅供準備資料，不是 AI admission、真 Future 停止或宿主 ownership 的證据。

## 3. 可重現方式與有限採用依據

在 `experiments/jd-relational-app` 使用已鎖 runtime：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_run_operations.py -q -p no:cacheprovider
$env:JD_RELATIONAL_TEST_DB='1'
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_run_operations_postgres.py -q -p no:cacheprovider
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_storage_history.py -q -p no:cacheprovider
```

版本沿 app lock：SQLAlchemy **2.0.52**、Psycopg **3.3.5**、Python **3.12**，未升級或新增套件。官方來源沿 2026-09-13 [既有資料層前置](../2026-09-13-jd-relational-db-preflight.md)、[讀取前置](../2026-09-13-jd-read-reference-preflight.md)及共同保存交易的 PostgreSQL isolation／SQLAlchemy transaction 證據；本次只增固定 schema 的查詢，沒有新框架行為缺口，未重開品牌研究或把本案 96 上限稱為官方限制。

本案 96 上限、exact doc/run query、超界停止及 native binding 順序配對，是這個有界接點的產品／技術選擇。未宣稱兩家模型供應商公開採用相同 SQL、未驗聊天 HTTP／真瀏覽器或自然模型，也不涵蓋跨 SQL／Saver 的單一交易快照。上層完成態配對與 active 競爭的保守投影仍須其獨立驗證。
