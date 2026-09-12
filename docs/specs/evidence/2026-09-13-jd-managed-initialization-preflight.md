# JD 受管理初始化：原生 migration／Saver 前置核對

- 查閱日期：2026-09-13；Topic：JD-R002／RS-3／DA-03。
- 狀態：有界官方文件與已安裝原碼核對，後續有限 helper 實證記於 §9；不代表完整日常啟動或產品驗收通過。本輪未讀真實訪談或呼叫模型。
- 上游：[本機持久配置前置](2026-09-13-jd-local-configuration-preflight.md)、[目前決策](../../current-decisions.md)、[施工計畫](../../plans/2026-09-13-jd-relational-app-implementation.md)、[資料層前置](2026-09-13-jd-relational-db-preflight.md)。正式權責仍依有效 ADR；本輪不改 production authority。

## 1. 推薦及初始化界線

**採明示初始化、原身分排他、固定 migration、原生 Saver setup，最後以同一份唯讀檢查確認可開啟。**不新增資料庫世代表、通用 migration 引擎或逐 SQL 的自製進度紀錄。

配置階段收斂為 `initialization_pending → initializing → ready`：第一階段尚未取得「這是空資料庫」的證據；第二階段已在持有原 host lease 時驗空且持久記錄，允許原初始化接續；最後階段才容許普通開啟。這細化了上游前置文件把首次建立直接稱為 `initializing` 的說法；使用現有配置的階段欄位，不另加 `setup_step`。`maintenance` 留給未來明示維護，不能被初始化入口當成可續作。

這些阶段名稱、資料所有權與接受條件是 **Caliburn mapping**，不是 Alembic／LangGraph 指定的設定格式。官方提供的交易、版本及 DDL 行為支撐這個有界接合；無法據此推定大廠內部採同名階段。

初始化只使用配置中已存在的 loopback PostgreSQL 資料庫。本輪不 `CREATE DATABASE`、不收編既有同名 JD 表、不改正式或舊資料庫、不執行降版／清空／自動修復。未知資料庫即使有正確 `alembic_version` 也不能當成新安裝。另一安裝直接連同一 DB、外部 SQL 改庫、繞 App 還原或替換 DB 不在受管理保證內；host lease 排除本安裝的 writer，不是 PostgreSQL 全域管理鎖。

## 2. 官方來源、版本及適用性

以下均於 2026-09-13 查閱。Python 套件版本及授權另與隔離目錄的 `pyproject.toml`、已安裝 distribution metadata 核對；沒有安裝或升級套件。

| ID | 官方來源 | 適用版本、穩定性／授權及限制 |
|---|---|---|
| MI-S01 | [Alembic Commands](https://alembic.sqlalchemy.org/en/latest/api/commands.html)、[Sharing a connection cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands) | **1.20.0**；現行文件與已裝版本相符、Production/Stable、MIT。正式接點為 `Config.attributes["connection"]` 配合 programmatic command。`stamp` 只記版本，不證明執行了 migration。 |
| MI-S02 | [Alembic Runtime Objects](https://alembic.sqlalchemy.org/en/latest/api/runtime.html#alembic.runtime.migration.MigrationContext.get_current_heads) | **1.20.0**、MIT；`MigrationContext.get_current_heads()` 可讀 DB 的所有 heads。已裝原碼另確認此路徑只檢查版本表存在性與 SELECT，不呼叫建立版本表的方法。版本正確仍不等於物件正確。 |
| MI-S03 | [SQLAlchemy Engine.begin](https://docs.sqlalchemy.org/en/20/core/connections.html#connect-and-begin-once-from-the-engine)、[Inspector](https://docs.sqlalchemy.org/en/20/core/reflection.html#fine-grained-reflection-with-inspector) | **2.0.52**；現行穩定 2.0 文件／已装版本相符、Production/Stable、MIT；不採 2.1 beta。交易 context 成功 commit、例外 rollback；Inspector 提供現有表、欄位、PK／FK／index 檢查。反射可能快取，DDL 後換新 Inspector 或 `clear_cache()`，不能用舊結果驗收。 |
| MI-S04 | PostgreSQL 18 [CREATE INDEX](https://www.postgresql.org/docs/18/sql-createindex.html)、[pg_index](https://www.postgresql.org/docs/18/catalog-pg-index.html) | 本案固定 **18.6**／`180006`，引用穩定 18 線、PostgreSQL License。併行建索引不能放 transaction block；失败可留下 invalid index；`IF NOT EXISTS` 不驗證同名 index 定義。`indisvalid`、`indisready`、`indislive` 各有獨立意義。 |
| MI-S05 | PostgreSQL 18 [Schemas](https://www.postgresql.org/docs/18/ddl-schemas.html) | 穩定 18 線、PostgreSQL License。未限定名稱按 `search_path` 找第一個符合物件，新物件落入第一個存在的 schema；路徑也隱含信任其中可建立物件的人。這不是本輪新增登入／ACL 的理由，而是避免錯 schema 的接線要求。 |
| MI-S06 | [langgraph-checkpoint-postgres 3.1.2 官方發行說明](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/)、[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | **3.1.2** 固定正式發行、MIT；首用明示 `.setup()`，自行建立 psycopg 連線必須 `autocommit=True`、`row_factory=dict_row`。發行說明未承諾能自動修好任意既存 schema；精確中斷行為須讀 MI-L01 原碼。 |
| MI-S07 | [Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html#autocommit-transactions) | 已鎖 **3.3.5**；官網目前標 3.3.6.dev1，本文只使用已装 3.3.5／Saver 3.1.2 確認的 autocommit 既有契約，不採 dev 新能力。Psycopg LGPL-3.0；binary 依其散布授權。未設定 autocommit 時，SELECT 也可能開始 transaction。 |
| MI-S08 | PostgreSQL 18 [System Information Functions](https://www.postgresql.org/docs/18/functions-info.html) | 穩定 18 線、PostgreSQL License；`pg_get_constraintdef` 與 `pg_get_expr` 重建 catalog 內的規則，不是取回原始輸入 SQL。採 `pretty=false`，官方說明一般格式較適合保存；本案仍只宣稱固定 **18.6** 相容，不以此保證跨版文字完全不變。 |

**MI-L01：已安裝原碼。**唯讀核對隔離目錄 `.venv/Lib/site-packages/langgraph/checkpoint/postgres/__init__.py` 的 `from_conn_string`、`setup`、`_cursor`，及同目錄 `base.py` 的 `MIGRATIONS`。版本由 `langgraph_checkpoint_postgres-3.1.2.dist-info/METADATA` 確認。這是可核的官方發行程式，不是其他產品內部實作的猜測。

| 原碼 | 本次 SHA-256 |
|---|---|
| `postgres/__init__.py` | `fb141317b3b865da672b946df0f2e64d33da23a640dd334815604cc06b36fe1f` |
| `postgres/base.py` | `34a76ad89892b7200b91d0574333060f78c3cd7afd3f61111b56fc871c3e9f79` |

本題是配置與 PostgreSQL 初始化，沒有改 LLM 工具／顧問行為；兩家模型與 AWS 業務依據延用[既有 App 責任及錯誤研究](2026-09-13-jd-app-boundaries-errors-logging-evidence.md)，不為同一機制重開無關廣搜。

## 3. 現有原生能力能做什麼

### 3.1 JD：一個固定且完整的 DDL transaction

已讀 [migration env](../../../experiments/jd-relational-app/migrations/env.py)、[固定第一版 migration](../../../experiments/jd-relational-app/migrations/versions/0001_jd_relational_initial.py) 及 [test DB 初始化](../../../experiments/jd-relational-app/scripts/init_test_database.py)。目前只有 `20260913_0001`，`down_revision=None`；升版建立十三張 JD 表及普通 index，沒有 `CONCURRENTLY` 或自主 commit。

因此可用 `engine.begin()`，將該 Connection 傳给 Alembic，執行固定 revision，再在原交易內核對結果。這沿 MI-S01／03 的原生共用交易模式。本案整個 migration 在同一 PG transaction 內，正常失敗回滾後應為原空狀態；成功則完整同版。**不需要把十三次建表變成十三個配置階段。**網路或程序中斷使 commit 確認不明時，配置保持 `initializing`，下次只讀重查，不能先宣稱已回滾。

初始化接受的 JD 續作狀態只需「仍空」或「完整固定版」。缺部分 JD 表、版本有洞／其他 head、同名不同形狀，不透過 `create_all`、`stamp` 或執行剩餘建表補齊。`env.py` 的 `include_object` 是 autogeneration 範圍過濾，不能充當未知資料庫安全檢查。

### 3.2 Saver：原生多步提交，有窄範圍續作能力

MI-L01 的同步 `setup()` 先執行第 0 個建立版本表命令，再只讀最大 `v`，依序執行下一個 migration SQL，**另一個 execute** 才插入該 `v`。`_cursor()` 預設不啟用 pipeline、不開 transaction；`from_conn_string` 使用 `autocommit=True`、`dict_row`、`prepare_threshold=0`。方法註解有「asynchronously」字樣，但本次讀的是同步實作，不能據此套用 async 流程。

| v | 3.1.2 的固定作用 | 中斷後要辨認的狀態 |
|---|---|---|
| 0 | 建立 `checkpoint_migrations(v INTEGER PRIMARY KEY)` | 表可能已在、版本列尚空；setup 一開始也會先執行此命令。 |
| 1–3 | 依序建立 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes`，各有原生複合 PK | 最後一張表可能已建立，但相對應版本列還沒保存。 |
| 4 | 將 `checkpoint_blobs.blob` 改成允許 NULL | 當前第 2 步已允許 NULL；本步保持既有相容性。 |
| 5 | `SELECT 1` 相容占位 | 沒有 schema 變更，不可因為是空操作自行移除版本。 |
| 6–8 | 三張資料表各建 `thread_id` 的 concurrent index | SQL 成功但版本列遺失可重讀；失敗留下的同名 invalid index 必須停止處理。 |
| 9 | 加入 `checkpoint_writes.task_path TEXT NOT NULL DEFAULT ''` | 欄位可能已在但 `v=9` 尚未插入；只接受原生形狀。 |

**官方事實：**此 setup 沒有驗證 migration 連續性或 index 有效性。**由原碼推論：**單一初始化者、無外部 schema 修改的前提下，一次中斷最多讓「下一個 migration 的 DDL 已完成」领先已保存的連續版本；不能因此接受任意已知名稱的物件子集合。

例如 `[0,1,2,3,4,5]`，第 6 個 index 正確且有效但尚無 `v=6`，原生 `IF NOT EXISTS` 可接續；同名 index 若 invalid／不是該表的 `thread_id` 普通 btree index，就不適用。只驗最大值或總數都無法分辨。一般版本列必須是 `0..k` 的完整前綴，允許初始空列，拒絕負值、洞、未來版與額外版本。已記版本對應的物件必須確實存在。

PG 官方給 invalid concurrent index 的修复方法包括重建或刪除後重建，但這些是額外維護動作。**本輪偵測後保留 `initializing` 並停止，不自動 DROP／REINDEX，也不改寫版本列讓初始化看似完成。**[MI-S04](https://www.postgresql.org/docs/18/sql-createindex.html)

## 4. 最小共用 preflight／setup／recheck 骨架

推薦三個窄責任，實際名稱由實作者決定；都是同 repo Python 內部接點，不新增跨 app JSON contract。

| 責任 | 允許的作用 | 明確界線 |
|---|---|---|
| `inspect / require` | 用現有連線讀身分、schema、物件、版本及必要 index，依 pending／initializing／ready 規則判斷 | SELECT／reflection；不呼叫 setup、stamp、ensure_version 或 create_all。初始化及普通開啟共用完整 ready 核對。 |
| `initialize` | 原配置 phase CAS、固定 Alembic migration、建立配置 schema、原生 Saver setup | 只有明示入口且持原 lease；每一類寫入前要先通過其 preflight。一次有限嘗試，故障留下可診斷進度。 |
| `recheck / publish` | 用新的讀取結果核完整狀態，將同一配置 CAS 到 ready | 不能用剛執行過哪些步驟推斷 DB 成功；配置發布失敗不開 writer，不重新配 id／key。 |

### 4.1 先取得原所有權，再驗空

1. 正常讀取配置不建立任何檔案、UUID、schema。首次明示建立透過既定排他發布產生唯一的 `initialization_pending` 配置；同一位置已有檔案就讀取或停止，不能覆蓋。
2. 用其中原 `installation_id` 取得既有 Windows host lease，證明前組已退出；整個初始化持有同一 lease。缺少原身分而可能存在舊宿主時，不以新 UUID 取得另一把鎖。固定位置首次建立／遺失判別沿配置層處理；DB schema 不能反推出原 host 身分。
3. 只連配置指定的已存在 DB；核 loopback、實際 DB／user、PG 精確版與 schema 名称。不能在失敗後試下一個 DSN／資料庫、建立 DB 或降級版本。
4. `initialization_pending` 只接受本輪定義的空資料庫：沒有額外使用者 schema、既有使用者表／view／sequence／foreign relation 或其他非基線使用者物件。內建 catalog、空 `public`、系統基線不當成使用者資料。檢查不能只數 `pg_tables` 而漏掉同名 view；未知 extension／routine／自訂型別亦須停止，不能靠隱藏或刪除後變成空庫。具體基線隨既有 PG18 測試 fixture 固定，不設自動掃描修復器。
5. 仍持 lease 時將**剛讀到的原配置** CAS 為 `initializing` 並讀回核對；只有成功後才做第一個 schema 寫入。驗空後寫配置失敗，就停止且零 DB mutation。

兩個地方的更新不是分散式共同交易。階段先持久、DB 進度可讀、最後發布 ready，是本案能接續的原因。沒有 DB epoch 的邊界沿上游前置；不宣稱辨識外部任意還原。

### 4.2 JD 與 Saver 使用各自正確的 transaction

1. `initializing` 先以 read-only preflight 接受空 JD 或已完成的固定 JD schema。當前單版 migration 可在 `engine.begin()` 裡執行 `command.upgrade(config, "20260913_0001")`，`Config.attributes["connection"]` 傳同一個 Connection；路徑從模組位置解析，不依 cwd。若仍使用 `head`，須先核它只有本輪已驗的固定 head，不能不知情跑未驗升級。
2. JD 結果核對後讓其交易結束。Saver 使用**獨立 psycopg autocommit connection、無 pipeline／外層 transaction**，不是把整個初始化包進 SQLAlchemy 同一交易。連線採 MI-S06／L01 的原生參數。
3. 建立配置中唯一指定的 checkpoint schema；既存 schema 先驗是本次可續作範圍，不以 `IF NOT EXISTS` 代替權責判斷。使用 `psycopg.sql.Identifier`，不可插入未驗字串。明確建立後將 `search_path` 設為**該 schema 本身**，不把 `public` 當 Saver 的候補位置；`pg_catalog` 保留 PG 的隱含正常處理。先用限定 schema 的查詢確認實際位置，再呼叫原生 setup。[MI-S05](https://www.postgresql.org/docs/18/ddl-schemas.html)
4. setup 前對已存在的 native 表／版本前綴及 index 做有限核對；若為合法續作才呼叫。setup 中途失敗保留原階段，下次須重新 preflight；不要在例外 handler 直接再跑一次 setup。

### 4.3 完整 ready 核對與普通開啟

完整結果至少包括：public 的十三表加 Alembic 版本表、唯一固定 head、必要欄位／PK／FK／約束與 index；指定 Saver schema 的四表、原生欄位／PK、`v=0..9` 及三個 native secondary index。所有必要 index 均核所屬表、欄位／形式及 `indisvalid`／`indisready`／`indislive`；同名不當同義。這是固定版本 compatibility guard，沿 SQLAlchemy Inspector／PG catalog 和現有 metadata 核，不新增泛用 DDL parser 或第二份 migration 執行器。[MI-S02](https://alembic.sqlalchemy.org/en/latest/api/runtime.html#alembic.runtime.migration.MigrationContext.get_current_heads)、[MI-S03](https://docs.sqlalchemy.org/en/20/core/reflection.html)、[MI-S04](https://www.postgresql.org/docs/18/catalog-pg-index.html)

初始化尚未開業務入口，續作時若 JD／checkpoint 資料表已有業務資料，不當成首次 setup 的合法中斷現場；拒絕收編，保留資料。讀取檢查只需要存在性，不載入或紀錄訪談正文。這不要求正常 `ready` 資料庫為空；普通開啟當然保留並讀回實際資料。

最後以新 Inspector／新讀取核對已提交狀態，再 CAS 原配置到 `ready`。若 DB 已成功而 ready 發布失败，後續明示續作能驗出完整狀態並再次發布；普通開啟仍拒絕 `initializing`，不能假設「大概完成」。

普通 `open` 僅載入 ready 配置、取得原 host lease、共用唯讀 ready preflight，然後由既有 runtime 完成 startup reconciliation 才受理寫入。**這裡的唯讀指 schema prerequisite；後續既有 operation／checkpoint 恢復可能有其原授權寫入，不能誤稱整個 host 啟動零 SQL 寫入。**普通 open 不執行任何 DDL／setup、不要以 `ensure_version` 或 Alembic `stamp` 補表。`MigrationContext.get_current_heads()` 可用，但必須另辨「沒有表」與「版本表存在但空列」。

## 5. 現有檔案不能直接沿用的假設

| 已讀檔案 | 可以保留的接點 | 本輪必要補足 |
|---|---|---|
| [host_runtime.py](../../../experiments/jd-relational-app/src/jd_relational/host_runtime.py) | bootstrap 在 DB resource 前、拒未知 PG 版、普通開啟不 setup、close 先等 runtime 排空 | 表名與版本列之外，共用必要 schema／index 檢查；Saver 不要 public fallback。持久配置入口必須沿原 installation／dataset。 |
| [init_test_database.py](../../../experiments/jd-relational-app/scripts/init_test_database.py) | 明示合成 DB、caller-owned transaction 與 Alembic Connection | 它接受已存在同版表是固定測試用途；不能當成新配置可收編任意既有 DB 的規則。產品不得 import 固定測試 credentials 或測試入口。 |
| [init_test_runtime.py](../../../experiments/jd-relational-app/scripts/init_test_runtime.py) | 明示 setup、autocommit、檢查原生版本、不清資料 | 已知表名子集合不夠：需 migration 前綴／合法 partial 形狀／index 有效性。schema 與 DB 必須來自受保護配置及明示階段。 |

此表描述查閱時基線；不是要求重写整个 runtime。共用有限驗證助手即可避免 initializer 與 normal open 各自維護一份相互漂移的 readiness 判斷。

## 6. 有限替代及未採路線

| 方案 | 能力及代價 | 判斷 |
|---|---|---|
| A：固定 Alembic migration＋原生 Saver setup＋共用唯讀檢查 | 使用已固定的資料權威、SQLAlchemy／Psycopg 接點；只補配置與可續作門檻 | **推薦。**會影響選擇的原生限制已查明，剩餘以反例驗證。 |
| B：SQLAlchemy `metadata.create_all` 後 Alembic stamp，再原生 Saver setup | Alembic cookbook 對全新 DB 有此正式做法；但本案已有固定 migration，會多一條初始化形狀來源，不能解決 Saver invalid index 或首次收編問題 | 本輪不採。它不是過時 API，只是沒有改善本案已識別的缺口。[MI-S01](https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch) |

沒有另評估自建 migration ledger、一般化 setup workflow 或自動 schema repair；本案不需要這些元件即可驗證正常與中斷流程。

## 7. 寫入與資料破壞分類

| 動作 | 是否寫入／破壞資料 | 本輪規則 |
|---|---|---|
| Catalog／version SELECT、Inspector、`get_current_heads` | 不改業務資料或 schema | normal open 與明示 init 可用；不輸出秘密或資料正文。 |
| DPAPI 配置 phase CAS | 寫本機配置，不是 DB 交易 | 保留原 installation／dataset／key；未確認發布不前進。 |
| 固定 migration upgrade、建立 checkpoint schema、Saver setup | 寫 schema／原生版本；只對已驗空且持久宣告管理的本次資料庫初始化，沒有刪除業務資料 | 明示 init 專用；不是「完全唯讀」或零影響。 |
| `CREATE DATABASE`、`DROP`／`TRUNCATE`、downgrade、版本列補寫、invalid index 自動修复、舊資料搬移 | 可能破壞／重解釋既有資料，或越過本輪範圍 | 不執行；保留診斷讓後續明示維護處理。 |

## 8. 反例與停止条件

| ID | 驗證情境 | 必須看到的結果 |
|---|---|---|
| MI-01 | pending 指向空的專用合成 DB | 原 installation lease→唯讀驗空→配置 initializing→固定 JD＋原生 Saver→重查→ready，無 provider。 |
| MI-02 | pending 指向已有同版十三表、版本表、其他表／view／schema／未知非基線物件 | 零 DDL、零收編、不刪除；不因版本相符放行。 |
| MI-03 | 驗空後配置 CAS 失败；首次初始化者競爭 | 失敗者零 DB setup，不能覆蓋配置、換 UUID 或另開 host。 |
| MI-04 | JD migration 中途故障／COMMIT 回覆遺失 | 原配置保留 initializing；新連線／新程序讀出空或完整，部分 JD schema 不自動修。 |
| MI-05 | Saver DDL 已提交，對應版本 INSERT 前中斷 | 原連續前綴＋下一步正確物件可接續；版本列和 schema 完整後才 ready。 |
| MI-06 | concurrent index 失敗留下 invalid；同名錯欄位／錯表 index | setup 前或最終 preflight 拒絕，不以 IF NOT EXISTS 當成功，不自动 DROP／REINDEX。 |
| MI-07 | Saver migration 洞、未來版、已記版本缺物件；unknown table／wrong column shape | 明示續作與普通 open 均拒絕；沒有 blind setup 或 stamp。 |
| MI-08 | DB 已完整但 ready 配置寫入失敗 | 原配置仍不供 ordinary open；明示續作重查後可發布，不重建 key／dataset。 |
| MI-09 | ready 普通開啟，schema 缺損／必要 index invalid | prerequisite 只讀、固定錯誤、不 setup；後續 runtime recovery 未受理。 |
| MI-10 | 原宿主活著且配置遺失／嘗試新身分；initializing 帶業務資料 | 不繞開原所有權，不清資料、不當首次安裝接管。 |
| MI-11 | Saver schema 不存在或錯置 public | 不 fallback 建在 public；明示 init 只建原配置 schema，normal open 直接拒絕。 |
| MI-12 | 新程序重開相同 ready 配置 | 真實 DB／版本／Signer scope 一致；純 fake 測試不能標真 PG 或跨程序通過。 |

前置研究完成時尚未執行以上測試；主代理其後明示授權有限 helper 與専用 `55436` 的新合成 database 反例，結果見 §9。證據已足以選 A，停止同層廣搜；若反例出現新缺口，只追該項原生行為，不重開框架品牌比較。

## 9. 後續有限 helper 實證（2026-09-13）

依主代理追加範圍，完成 [storage_setup.py](../../../experiments/jd-relational-app/src/jd_relational/storage_setup.py)、[純 gate／schema 測試](../../../experiments/jd-relational-app/tests/test_storage_setup.py)、[原生 PG 反例](../../../experiments/jd-relational-app/tests/test_storage_setup_postgres.py)。外部介面為 `check_empty_database(settings)`、`setup_database(settings, lease)`、`check_installed(connection, checkpoint_schema)`；不寫配置 phase、不建立 database、不改原 host runtime，由主代理接合。

- 首敗：測試收集時缺 `storage_setup`；符合先建反例的基線。第一次已知 PG 的唯讀核對另發現 SQLAlchemy 降冪 index expression 沒有 `.name`，已改用原生 `Index.columns`，兩份既有合成 Saver schema 都讀核通過。
- 首輪窄組 **37 PASS：21 純測＋16 真 PG（4.92 秒）**；其後 P2 修正的最終結果見 §10。包含空 DB 原生 setup、完整 initializing 再次結束、拒同版 DB 的 pending 收編、未知表／view／schema／function、四種原生合法 prefix／下一 DDL、版本洞／未來版／錯欄位／錯預設／錯 index，以及 normal installed 檢查不修補缺 index。
- 真 `CREATE UNIQUE INDEX CONCURRENTLY` 的合成重複值故障確實留下 invalid index；helper 拒絕，版本最大值仍為 5，兩列合成資料保留，沒有 DROP／REINDEX。這驗證 PG 原生失敗狀態，並非聲稱原生非唯一 index 必然以同一原因失敗。
- 首輪只有約束名稱及 partial predicate 存在性，不足以拒絕同名錯義規則；獨立審查列為 **P2，已接受並修正**。不能以受管理前提或「不做通用 SQL parser」免除檢查，現行實作依 §10 比對本版 PostgreSQL 實際規則文字。
- 兩輪真 PG 窄測共建立並保留 **31 個** `caliburn_jd_setup_test_<uuid>` 合成 database；每次先核 `55436` 的固定測試 DB／user／PG180006。僅測試 fixture 可建測試 database，產品 helper 沒有該能力。沒有碰 `5432`、正式／舊 DB，也沒有清除資料。
- 這組 PG 測試的 HostLease 是明示的分支 adapter，**不是 Windows 所有權實證**；真 DPAPI、原生 Windows、新程序完整 init／open／保存／重開由另一獨立工作包驗證。配置 CAS／檔案故障、實際 JD COMMIT 中斷及整份 matrix 尚不能因這 37 案例一併標通過。

本文件的相對檔案連結全數存在；有限檔案差異檢查通過。共用 helper 尚由主代理安排獨立審查及宿主接合，production authority 沒有在本子工作包切換。

## 10. P2 收尾：同名規則也必須有正確意義

獨立審查反例為 `ck_jd_revision_format_version` 名稱不變但改為 `format_version = 4`，以及 `uq_jd_revision_initial` 保持原欄位、唯一性與名稱但改為 `WHERE origin = 'manual'`。修正前兩個真 PG 測試均 **DID NOT RAISE**，證實原檢查有缺口。

採有界 [ddl_profile_v1.json](../../../experiments/jd-relational-app/src/jd_relational/storage/ddl_profile_v1.json)：在本輪另一個全新合成資料庫實際執行固定 `20260913_0001` migration，從 **PostgreSQL 18.6** 以 `pg_get_constraintdef(oid,false)` 擷取 **29 個 CHECK**，以 `pg_get_expr(indpred,indrelid,false)` 擷取 **12 個 partial predicates**。profile 記錄 PG 版、revision、來源 migration 與 schema metadata 的 SHA-256、查閱日期與用途；它是固定版本的相容性驗證材料，**不保存文件、不執行 DDL、不取代原 migration／current 資料權威**。migration 維持固定 `op.create_*`，沒有 import 即時 metadata；schema hash 是追溯 helper 的期望形狀／profile 名稱集合核對來源。兩個來源 hash 在測試核對，不在每次請求重新 hash。[MI-S08](https://www.postgresql.org/docs/18/functions-info.html)

normal open 與 initializing preflight 都只 SELECT 實際 catalog 重建值，與該版本 profile 精確比較。profile 的 CHECK／partial 名稱集合另與現有 metadata 核對；缺漏、改義、未知 profile／版本直接拒絕。沒有 AST parser、正規表示式 SQL 改寫或通用等價判斷；不同文字即使可能等價，也不悄悄當成已驗版本接受。套件／migration 升級需在新合成庫重新取得該版正式輸出並驗證，不從正在使用的資料庫重設期望值。

本次驗證：兩個真 PG 首敗 → **3 窄 PASS**（含 profile 來源核對）→ **40 PASS：22 純測＋18 真 PG（5.25 秒）**。原有 partial／prefix、錯欄位／預設及 invalid index 案例全部保留。既有 `55436` 合成 fixture 的 `public`＋`jd_runtime_test`、`public`＋`jd_host_test` 各再作純 SELECT 相容核對，均通過。

P2 驗證只在本次新庫替換一個 CHECK 或 index 來注入錯義，沒有刪除資料表／database 或接觸既有 fixture 的 DDL；產品 helper 仍沒有 DROP。P2 紅／綠及全組、profile 擷取合計另建並保留 **23 個**合成庫，加首輪共 **54 個**；命名與靜態測試端點驗證不變。程式與 tests 已停止寫入，送原獨立審查者窄複核。
