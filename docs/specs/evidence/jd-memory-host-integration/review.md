# Memory 宿主接合：獨立審查

2026-09-13。結論：**PASS；本輪有界審查未發現可重現的 P1／P2**。基準 `8672d93122891a8a1bb47742214374ceb9aeb091`，依[本輪設計](../../2026-09-13-jd-memory-host-integration-slice.md)。唯讀核產品、初始化、測試前置及新程序 helper；只新增本紀錄，未修改產品／測試、初始化 DB、啟服務或呼叫 provider。

## 正常啟動與保存責任

[host_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/host_runtime.py) 的實際順序為原生 bootstrap／lease／配置重核，然後 JD engine 與 Saver connection、`check_installed` 唯讀前置，再建立獨立 Store connection、publication engine view、原生圖與 owner。一般 open 沒有 Saver／Store／publication setup；缺 Memory 的舊 ready 實驗庫被拒絕是本次明示規則，不需要相容 fallback。

Store 與 Saver 使用不同 psycopg connection；兩者仍由同宿主持有。`memory_engine = engine.execution_options(schema_translate_map={None: checkpoint_schema})` 是固定 OptionEngine，與 JD engine 共用 pool，沒有改 JD 的 public search_path 或全域 ORM table schema。初始化及新宿主 helper 都把這個 view 傳給原 `PublicationStore`，沒有另一份 current Memory 或新的發布引擎。

[runtime_checkpoints.py](../../../../experiments/jd-relational-app/src/jd_relational/runtime_checkpoints.py) 透過原生 `compile(store=...)` 注入；直接掛載的 consultant 若已綁另一個 Store 便拒絕。原生節點測試實際在 `Runtime.store` 取得同一實例並保存讀回；不是只比較 build 時傳入的參數。

## 關閉與故障

`ManualHost.close` 先呼叫原 [ManualRuntime.close](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py)；owner 未排空就不關 Store、Saver 或 pool。原 owner 的同步 materialized read token、startup、admission 與實際 foreground／writer Future 排空責任未被替換。排空後才依序關 Store、Saver、共同 pool；某一清理失敗仍嘗試其餘清理並回 False。Store／graph 建立途中失敗則清理已取得的兩連線與 pool，對外固定 `host_storage_unavailable`，不傳出原 DSN／driver 例外。

這個切片尚無產品 Memory API／B1／B2／C 或背景排程。直接拿 `host.store` 做未登記 I/O 不會被 owner 自動發現；後續正式工作必須沿已有 owner 的同步讀取／實際前景工作範圍，背景工作也必須另完成其真實排空與恢復接合。沒有把目前 foreground／read 的證據泛稱為全部 Memory 工作已受管理。

## 初始化與已知部分狀態

[storage_setup.py](../../../../experiments/jd-relational-app/src/jd_relational/storage_setup.py) 與 [storage_memory_profile.py](../../../../experiments/jd-relational-app/src/jd_relational/storage_memory_profile.py) 的 caller 已真正接上：

- `check_installed` 要求完整四張 Saver、兩張官方 Store、兩張原 publication；既有 public JD profile 維持原責任。
- `setup_database` 只在 `initializing`、原生同 installation lease 及無使用資料的條件下執行。全體已存在形狀先驗證，再做 Alembic／官方 Saver／Store setup；publication 兩表在同一 SQLAlchemy transaction 建立。
- Store 版本只接受連續整數前綴；部分狀態只容許精確已知前綴或下一個 DDL 已完成但版本尚未寫入。後序 Store／publication 表不得掩蓋未完成 Saver；publication 只接受全無或兩表完整。未記錄多步、版本缺洞、錯欄位／default／索引／predicate 不會自動修復。
- Memory 索引除名稱、欄位、唯一性、有效性與 predicate，還核原生 opclass／排序選項。`text_ops` 冒充官方 prefix 的 `text_pattern_ops`、DESC 或失效 concurrent index 均不能成為完成狀態。
- `store_migrations` 是版本記錄，不是使用內容；Store 或 publication 已有使用資料時，初始化續作停止。普通 ready 讀取則允許已有資料。

此 profile 是固定 PG 18.6／PostgresStore 3.1.2／既有 publication ORM 的相容檢查，不是自製 SQL parser、Store 或通用 migration 引擎。

## 測試前置與新程序證據邊界

[init_test_runtime.py](../../../../experiments/jd-relational-app/scripts/init_test_runtime.py) 只接受固定測試 DB 的三個具名 schema。純 Saver 的 `jd_runtime_test` 保留四表；兩個 host schema 才明示補四張 Memory 表。它重用上述 profile／固定 JD 核對及官方 setup，publication 用同交易 schema map。未知形狀在任何 DDL 前拒絕，已完整不重做 setup，沒有刪資料。host／AI host 測試只增加完整前置斷言，沒有把初始化偷放進測試或普通 open。

額外靜態核 [memory_host_journey.py](../../../../experiments/jd-relational-app/tests/memory_host_journey.py)、[test_memory_host_native.py](../../../../experiments/jd-relational-app/tests/test_memory_host_native.py) 與 [configured_host_worker.py](../../../../experiments/jd-relational-app/tests/configured_host_worker.py)：

- 真正 `open_managed_app` 使用同配置、原生 host、Store 及 schema-mapped publication view。首程序在主執行緒建立合成來源／artifact／發布與修補，第二程序讀原來源／舊回執與目前 Memory；沒有 provider 或產品 Memory workflow 的完成宣稱。
- 普通 open 的 setup 入口被測試 hook 明確禁止；schema OID、public JD 版次及 operation 數檢查另證沒有因 Memory 重開重建 JD。
- 排空反例確實由 `owner.inspect_document` 登記 callback，再以 Event 持住；短 close 回 False、兩連線仍開，放行後 callback 才完成且第二次 close 成功。它不是用父測試 bool 假裝 I/O 已停。
- 審查曾發現 helper 將 `MemoryArtifacts` 的 keyword-only `source` 誤傳位置參數；主代理只修 helper 為 `source=...`，目前檔案已核。這是新 fixture 執行阻擋，不是產品保存缺陷。

## 審查者實跑

工作目錄 `experiments/jd-relational-app`，既有安裝環境，`uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider`：

| 有界測試組 | 實際結果 | 能證明的層次 |
|---|---|---|
| `tests/test_host_runtime.py tests/test_runtime_checkpoints.py` | **71 PASS／4.08 秒** | fake OS／DB 的資源次序與故障、真原生 in-memory graph／Store 注入。 |
| `tests/test_memory_setup.py tests/test_storage_setup.py tests/test_init_test_runtime.py` | **56 PASS／7.52 秒** | 固定 profile／未知形狀拒絕／明示測試初始化次序。 |

兩次獨立窄組均首跑通過、無 warning，沒有與作者的重疊測數相加。審查者未重跑 PG／Windows host；schema 作者的真 PG 33 案及主代理新程序結果由各自實跑紀錄負責，不混入上述數字。

本 PASS 支持這次資源與初始化接合。Memory 自然品質、完整來源窗口、B1／B2／C、模型工具、背景工作生命週期及正式 adoption 仍由原計畫接續；ADR0060 未被本次隔離成果取代。
