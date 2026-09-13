# Memory 宿主：明示初始化與唯讀前置結果

2026-09-13；基準 `8672d93122891a8a1bb47742214374ceb9aeb091`。依[本單位設計](../../2026-09-13-jd-memory-host-integration-slice.md)，完成固定 schema 前置；**48 純測與 33 真 PG 情境通過**。這裡不包含新程序／真宿主排空驗收，亦沒有 provider 呼叫。

## 實際修改

- [storage_setup.py](../../../../experiments/jd-relational-app/src/jd_relational/storage_setup.py)保留 JD／Saver 原檢查及 lease／phase 門閘。一般 `check_installed` 必須有四 Saver＋兩 Store＋兩 publication 表；缺 Memory 不自動補建。
- [storage_memory_profile.py](../../../../experiments/jd-relational-app/src/jd_relational/storage_memory_profile.py)只描述已鎖 PostgresStore 3.1.2、Memory core 0.1.0 在 PG18.6 的有限形狀；不是 Store 實作、SQL parser 或 migration engine。
- `setup_database` 仍只接受同安裝原生 lease 下的 `initializing`。先核未知表／形狀／版本與使用資料，再按既有 JD → Saver → 官方 Store.setup → publication ORM 同交易 create_all 完成；最後重用唯讀完整核對，不改配置 phase。
- publication 表透過 `schema_translate_map={None: checkpoint_schema}` 建立，不修改 ORM 定義或 JD schema。設定欄位、public 的 13 張 JD 表＋Alembic 沒有增加或更名。
- 新初始化檢查允許已知 Store prefix 與下一個 DDL 已完成但版本尚未記錄的狀態；不接受超過一步、版本缺洞／未來版本、部分 publication 兩表、錯索引或未知物件。Memory 已有資料時停止，不清資料；migration 記號不是使用資料。

## 官方原生細節與固定 profile

已讀本次 venv 所安裝 `langgraph-checkpoint-postgres==3.1.2` 的 `PostgresStore.setup`／`MIGRATIONS`／`_cursor` 原碼；[原碼身分與 migrations digest](../../../../.research-tmp/jd-memory-setup-native-profile.json)保留實際版本、來源檔路徑及摘要。

- Store.setup 先建立 `store_migrations`，再執行四個 native migration。`store_prefix_idx` 含 `CREATE INDEX CONCURRENTLY`，所以沿原生獨立 autocommit connection 執行，不包進 publication 的交易。
- 第三、四個 migration 的 TTL 欄位與索引是 native 固定結構，即使 App 不啟用 TTL 清除仍須存在；沒有向量設定，所以不建立 vector 表或 extension。
- `store_prefix_idx` 必須是 `text_pattern_ops`，不能只看同名／同欄位。保留原 JD／Saver snapshot tuples，另對有限 Memory 索引核對官方 operator class 及排序。`expires_at` 的固定 partial predicate 也精確核對。
- publication 使用原 core 的兩張表，由 SQLAlchemy 同交易 create_all。真 PG 故障證明第二張表建立失败時，第一張也回滾；已完成的 Store 保留，明示續作才建好 publication。

上述 profile 已與真正執行官方 setup／原 publication ORM 後的 PG catalog 比對通過。這是本案相容性界線，不宣稱所有大廠採用八張表或相同 metadata 命名。更换版本须重验，不能把未知等價 SQL 自動收編。

## 首敗與實際驗收

| 證據 | 結果與範圍 |
|---|---|
| [首敗](../../../../.research-tmp/jd-memory-setup-first.txt) | `test_saver_only_database_is_not_ready_for_memory_host` **1 FAIL／2.12 秒**：舊 checker 對只有四張 Saver 的狀態沒有拒絕。 |
| [純測](../../../../.research-tmp/jd-memory-setup-pure-first.txt) | **48 PASS／6.48 秒**。既有 JD／Saver 門閘與新 Store prefix、migration 數列、shape、operator／方向、完整八表、資料門閘。 |
| [真 PG 首組](../../../../.research-tmp/jd-memory-setup-pg-first.txt) | **1 PASS／7.91 秒**。新資料庫明示初始化、完整八表、ready 配置回覆遺失情境的同 initializing 續作與只讀核對。 |
| [真 PG 其餘](../../../../.research-tmp/jd-memory-setup-pg-rest.txt) | **32 PASS／1 deselected／30.52 秒**，排除上一組相同案例；與首組聯集為 33 案，沒有重複相加。 |

真 PG 使用每案新建、保留的 `caliburn_jd_setup_test_<random>` 合成資料庫。建立前核專用 `127.0.0.1:55436`、`caliburn_jd_relational_test`／`jd_test`／PG `180006`；沒有變更共享 test schema、日常設定、正式資料或既有產品資料庫。

真 PG 新情境包括：Saver-only 的 ordinary check 不補表；六種官方 Store prefix／下一 DDL；同名錯 operator class／降冪／partial predicate／default／publication 欄位；已有 Store 或 publication 資料不得初始化；兩 publication 表的交易故障與明示續作。亦回歸舊 JD／Saver 的未知物件、版本缺洞、真正 invalid concurrent index、同名錯 CHECK／predicate 等案例。

測試程式：[test_storage_setup.py](../../../../experiments/jd-relational-app/tests/test_storage_setup.py)、[test_memory_setup.py](../../../../experiments/jd-relational-app/tests/test_memory_setup.py)、[test_storage_setup_postgres.py](../../../../experiments/jd-relational-app/tests/test_storage_setup_postgres.py)。PG 故障只修改當案新建的空合成表／索引，所有資料庫保留；測試 lease 是 HostLease 分支 adapter，不冒充 Windows 程序證據。

工作目錄 `experiments/jd-relational-app`，沿本次 lock／venv：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_storage_setup.py tests/test_memory_setup.py -q -p no:cacheprovider
$env:JD_RELATIONAL_TEST_DB='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_storage_setup_postgres.py -q -p no:cacheprovider
```

## 界線

只讀檢查允許正常已保存資料，但初始化續作仍要求既有 JD／Saver／Memory 無使用資料；不是舊 ready 資料的升級 API。原生 Store connection 的開啟／排空／關閉、新程序重開、共享測試 fixture 的明示補表及獨立審查由主代理另記。未接完整 B1/B2/C、背景排程、自然模型或 Memory UI，production authority 未變。
