# Memory 宿主接線：最小原生驗收前置

2026-09-13；OI-02。前置階段唯讀核對當前程式、既有驗收入口及必要官方契約，下列建議不代表已通過。主代理隨後授權的有限合成 fixture 初始化實作／結果記於文末；沒有執行 provider 或修改正式產品。

## 採用方案與邊界

主代理方案可沿現有責任接合：`checkpoint_schema` 容納原 4 個 Saver 表、官方 `store`／`store_migrations` 及原 2 個 Memory publication 表；`public` JD 仍由原 Alembic 管理。宿主建立獨立 `PostgresStore` psycopg connection，沒有 index、TTL 或新 pool。publication 使用既有 engine 的 `execution_options(schema_translate_map={None: checkpoint_schema})`，共享同一 pool。

這不是 Store、Saver、publication 跨交易的原子提交承諾。沿原 artifact 完整寫後讀回、準備版本，再以短交易發布 head／receipt；兩者的權責不改。原話仍在 Saver，Memory 不另存原話。

## 官方契約及適用限制

| 已核資料 | 官方事實 | 本案使用／版本 |
|---|---|---|
| [Psycopg 3.3.5 併發文件](https://github.com/psycopg/psycopg/blob/3.3.5/docs/advanced/async.rst) | Connection 可供不同執行緒使用，但同連線查詢串行，cursor 不可跨執行緒共用，且連線不可跨程序使用。 | 已鎖定穩定版 3.3.5，LGPL-3.0。Saver 與 Store 各有本程序 connection；每次重開新程序重新建立，不能把前程序物件帶過去。官網目前頁首是 3.3.6.dev1，本稿額外核對 3.3.5 tag，不把 dev 版當採用版本。 |
| [SQLAlchemy schema translation](https://docs.sqlalchemy.org/en/20/core/connections.html#translation-of-schema-names)、[Engine.execution_options](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Engine.execution_options)、[dispose](https://docs.sqlalchemy.org/en/20/core/connections.html#engine-disposal) | 表達式／ORM Table 的 schema 可映射；不改字串 SQL。OptionEngine 與原 engine 共享 pool。dispose 不會使借出的連線自動完成工作。 | 已鎖定穩定版 2.0.52，MIT。publication 的 ORM Session 固定使用此 OptionEngine，不逐 statement 切換。JD 原 engine 不加 map；共同 pool 最後由 host 排空後 dispose。 |
| [Python 3.12 Executor.shutdown](https://docs.python.org/3.12/library/concurrent.futures.html#concurrent.futures.Executor.shutdown) | `cancel_futures` 不取消正在執行的工作；等待者逾時不是執行已停止。 | 現有 Python 3.12，PSF。保留 owner 的真 Future／callback／read 排空；逾時回 False 且不關 DB，不能因 HTTP 離開或 executor 發取消而宣稱安全。 |
| [LangGraph persistence／Store](https://docs.langchain.com/oss/python/langgraph/persistence#memory-store)，已安裝 `langgraph/store/postgres/base.py:757–832,1115–1150` | Store 與 checkpoint 是不同持久能力；原生 Store constructor 接 connection，`index=None`／`ttl=None` 可用。setup 是明示首次初始化。 | 已鎖定 Postgres 套件 3.1.2、LangGraph 1.2.11，MIT。直接核已安裝源码：constructor 未啟動 sweeper，非向量 setup 為 2 表／4 migrations；未用新版本或自製 Store。官方 GitHub 該 tag 網頁本次工具讀取失敗，精確版本內容依已安裝 wheel，不宣稱已成功遠端核同一檔。 |

Windows bootstrap／Job 的背景依據沿既有 [lifecycle 設計](../../2026-09-10-jd-native-process-lifecycle-design.md)，新版實作以 `windows_host.py` 與其既有原生驗收為準；本輪沒有改 mutex／Job 規則，也不把關閉連線當作 OS worker 停止證明。

## 最小真 Windows＋PG 旅程

首選延伸現有 `tests/test_configured_host_native.py::test_real_initialize_open_edit_and_restart_keep_original_dataset_and_signer`，使用同檔 `fresh_database`、`worker`、`serving`、`finish` 及 `tests/configured_host_worker.py`。它已具備：專用 55436／PG18.6 scope 檢查、新合成 DB、repo 內 DPAPI、原生宿主、新程序重開、原 request 查回、schema OID 讀取及只處理自有 Popen 的退出證據。不要另建代理伺服器或 lifecycle 管理器。

Memory 內容情境可取 `test_memory_core_postgres.py::test_saved_sources_memory_correction_stale_publish_and_new_connection_reopen` 的原話→詳記→發布→更正→原版／目前版讀取斷言；**不要沿用該測試自行建立 engine／Store 的 `opened()`**，本輪必須使用新 host 所擁有的資源。

建議三個有限情境：

| 情境 | 最小接點與真正斷言 |
|---|---|
| H-M01 同宿主修正，正常退出後新程序重開 | initialize 後查 `public` 原 JD profile、runtime 8 表／Saver10與Store4 migrations；以 host-owned Store、同來源 service、mapped publication 保存兩個版本與 consolidation／repair 回執。repair 不前進 processed-source，原 publication 回取不倒退 head。正常 STOP 後新 worker 使用原 config 重開，dataset／signer／來源／版次／回執一致，原話及 JD 版本沒有被 Memory 修改；第二程序不執行模型或合成 graph。 |
| H-M02 讀取未完，不提早關資源 | 在 native worker 已完成 startup 後，以現有 `runtime.inspect_document(doc, callback)` 登記實際 Memory 讀取；callback 用測試 Event 暫停，在其他執行緒呼叫 host.close 短逾時應 False，Store/Saver connection 仍未 closed。放行後，callback 完成真 Store／來源讀取，Future 真結束，再 close 應 True 且兩連線已關。對應 `test_chat_boundary_review.py::test_chat_sync_reads_remain_in_owner_drain_until_materialized` 的有限測法；這證明 callback 壽命排空，不冒稱 DB 查詢本身卡住。 |
| H-M03 ready 檔但只有舊 4 Saver 表 | 以明確舊 fixture profile 的合成 DB＋ready config 普通 open；必固定拒絕，所有 Memory setup hook 零呼叫，前後 table/metadata/count／config 不變。不得在 open 自補表，也不得為通過舊測試把新 expected profile 放寬為 Memory 可有可無。明示更新程序另由既定初始化／維護流程處理。 |

`configured_host_worker.py` 現有 `child_graph()` 來自 `host_recovery_worker.py`，是 `MessagesState`＋禁止執行節點，只適合原 manual journey。H-M01 要驗實際原話來源時，改用已有 `test_memory_core_postgres.py` 的 `DocumentState` 合成 child 形狀，首程序才可明示產生固定回覆；重開使用相同 shape 只讀，不拿不相容圖投影空值當資料消失。這只是測試合成圖，不是 provider／自然模型驗收。

worker 的 `forbidden_setup` 現攔 `check_empty_database`、`setup_database`、`PostgresSaver.setup`、Alembic upgrade。應再攔 **PostgresStore.setup 與 PublicationStore.setup**；否則 `setup_calls=0` 尚未涵蓋新 Memory 接點。`.finished.json` 同時記 Store/Saver closed、實際退出及 setup 次數，避免只記單一布林。紀錄僅放合成 ID／計數／digest，不輸出 DPAPI、DSN 或完整原話。

所有 callback 返回前須 materialize；不可把 Store 的 lazy iterator／稍後工作的物件帶出 `inspect_document` 後繼續 I/O。現有 close 已會等待 read token，並拒絕同執行緒 callback 內重入 close 假裝已排空；不需要另一個 Memory reader registry。

## 已定位的測試影響

| 現有檔案／fixture | 有限更新點 |
|---|---|
| `test_host_runtime.py::resources` | 現只有一個 fake connection，需分出 Saver／Store、各自建立與 close 記錄；新增 fake PostgresStore，engine fake 支援 `execution_options` 並斷言共享 pool 的實際實作另由真 PG 補驗。原 `runtime.close=False` 案必新增 Store 不關的斷言。故障分支應驗僅清理已成功建立的資源。 |
| `test_configured_host.py::test_ordinary_open_uses_fixed_values_and_rechecks_file_at_host_boundary` | 若新 Memory 僅加在 ManualHost，外層 mock 簽名可不改；若 ConfiguredHost 組合新增參數，僅补實際傳遞斷言，不以 mock 發 source／Memory 存取。phase/init／檔案 CAS 原檢查保留。 |
| `test_managed_app.py::composed` | `opened.host` 現只有 graph／engine／runtime。若 root composition 新建立 Memory 服務，補 host.memory 等真新介面及同來源 owner 身分斷言；不可讓 fake composition 在 constructor 偷讀資料而未被測試察覺。 |
| `test_configured_host_native.py`／`configured_host_worker.py` | 正常新 DB 初始化會有新 8 表；保留普通 open schema OID 不變、零 setup、真新程序退出；加上上節 Memory 斷言。 |
| `test_host_recovery_postgres.py::installation`、`host_recovery_worker.py`、`manual_http_worker.py` | 固定 `jd_host_test` 目前只斷言 4 Saver 表，直接 `open_manual_host`；新 host 應拒絕這個舊 profile。需明示更新此合成 fixture 前置或採 fresh configured DB，不能在普通 open 隱式 setup。 |
| `test_ai_host_restart_postgres.py::dedicated_schema`、`ai_host_recovery_worker.py` | 是另一個固定 `jd_ai_host_test`，同樣精確 4 表；不要誤認與 `jd_host_test` 共用。其前置亦需明示更新。 |
| `scripts/init_test_runtime.py` 及只用 native Saver 的純／PG fixtures | initializer 現限制 `jd_runtime_test`／`jd_host_test` 4 表。只測 ManualRuntime／Saver、不開新版 host 的案例可保留原最小 fixture；需要 host 的情境另明示擴前置，不要求所有 isolated schema 都加 Memory。 |

這些是受影響範圍，不代表全套都需本輪重跑。先驗 root 新 host／schema 的窄反例與 H-M01–03；已通過的 provider、Web、完整 Agent 情境不因 Memory connection 新增而無據重跑。

## 明示合成 fixture 前置：實作與實際結果

主代理授權後，限定修改 `scripts/init_test_runtime.py`、`test_host_recovery_postgres.py`、`test_ai_host_restart_postgres.py`，新增 `test_init_test_runtime.py`。未修改宿主／worker／core package／production。

- script 只接受 `jd_runtime_test`、`jd_host_test`、`jd_ai_host_test`，固定專用 `127.0.0.1:55436` 合成 DB／user／PG18.6／public Alembic 身分；前者維持 4 表，後兩者要求完整 8 表。
- 重用 schema writer 的 `storage_setup._snapshot`、`_require_jd`、`_require_native`、`_require_runtime` 與 `storage_memory_profile`；未知既有 Memory 形狀、非法 native prefix、未知物件先拒絕，沒有另造 DDL profile。
- 只有合法缺失階段才呼叫官方 Saver／Store setup；publication 透過採用套件 metadata，在 `engine.begin()` 中以 `schema_translate_map` 建立。已有完整八表不再執行 setup；不使用一般初始化的「必須無資料」檢查來清空或拒絕既有合成對話。
- 兩個真 host fixtures 改要求八表與 Saver0–9／Store0–3 migrations，未放寬正式 `check_installed`。純 runtime/source 四表 fixture 不變。

首輪純反例：**1 PASS／6 setup ERROR，1.78s**，原 script 尚無 `PostgresStore` 接點，測試安裝 fake 時即 `AttributeError`；不是 PostgreSQL 故障。首次實作 **7 PASS／5.81s**；補齊完整八表不重做 setup 的反例後 **8 PASS／6.43s**。皆只有 pytest cache 目錄 ACL 警告；未把 fake 測試稱真 DB。

```powershell
# 工作目錄 experiments/jd-relational-app
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q tests/test_init_test_runtime.py
```

隨後先取專用 DB 的唯讀 REPEATABLE READ 快照，再明示執行兩次；兩次均 exit 0：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache python scripts/init_test_runtime.py --schema jd_host_test
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache python scripts/init_test_runtime.py --schema jd_ai_host_test
```

各次 stdout 確認 8 個 validated runtime 表、public JD unchanged、no data cleared。完成後另取一致唯讀快照，驗完整 shared profile 與 migration，並比對所有**原已存在表**的 row count 及按 row hash 排序聚合的內容 digest：

| schema | 之前／之後表數 | 實際核對 |
|---|---:|---|
| public | 14／14 | profile、全部既存資料計數與內容 digest 相同。 |
| jd_runtime_test | 4／4 | profile、全部原對話／checkpoint 資料計數與內容 digest 相同。 |
| jd_host_test | 4／8 | 原 4 Saver 表全部資料相同；新增 Store/pub 資料為空，Store migrations 為 0–3。 |
| jd_ai_host_test | 4／8 | 同上；原 Saver migration 仍 0–9，沒有重置或刪除。 |

證據：[`before.json`](../../../../.research-tmp/jd-memory-host-fixture-prep-ad778be60a1346f4924bf2408168f517/before.json)、[`after.json`](../../../../.research-tmp/jd-memory-host-fixture-prep-ad778be60a1346f4924bf2408168f517/after.json)。只記 scope、表名、計數、digest 與時間，沒有正文／DSN／DPAPI／provider key。

本小工作未重跑 native host suite、啟服務或呼叫模型；H-M01–03 的實際宿主結果仍由主代理驗收。這是明示修補**合成測試前置**，不是一般 ready 設定的自動升級程序。
