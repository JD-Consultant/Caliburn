# Memory 核心：套件與真資料庫接合結果

2026-09-13，零 provider 呼叫；[設計](../../2026-09-13-jd-memory-core-adoption-slice.md)。這是已保存原話→Memory 核心的實證，尚未證明模型會正確整理工作，也未接日常宿主 Store／背景排程。

## 環境與可重現範圍

新 App Python 3.12.13／[lock](../../../../experiments/jd-relational-app/uv.lock)，PostgreSQL 18.6，固定合成 DB `127.0.0.1:55436/caliburn_jd_relational_test`。沿既有 `jd_runtime_test` 四張 Saver 表；另外明示初始化 `jd_memory_core_test` 的兩張官方 Store 表與兩張既有發布表。public 的十三張 JD 表／Alembic 不變；一般宿主 profile 尚未加入 Memory，不是正式初始化採用。

[初始化程式](../../../../experiments/jd-relational-app/scripts/init_test_memory.py)只接受固定合成 DB 身分，無刪除、清空或每次測試 setup。先設定 `PYTHONPATH=src`，再用新 App 的 `uv run --offline --frozen --no-sync python scripts/init_test_memory.py` 明示執行。首次漏設當前 App 的 Python path，入口 import 失敗、未連 DB；補足既有腳本呼叫方式後初始化成功。不指向舊研究路徑。

## 真 PG 縱向證據

[測試](../../../../experiments/jd-relational-app/tests/test_memory_core_postgres.py)：在 App 目錄設定 `JD_RELATIONAL_TEST_DB=1`，以其 lock 執行 `pytest tests/test_memory_core_postgres.py -q -s -p no:cacheprovider`。

- 原生合成 node 保存含繁中、CRLF／空白的員工原話；同來源 owner 發固定來源。
- 真 `PostgresStore`＋`StoreBackend` 保存詳記／候選與兩個 Memory 檔；發布原版，後續原話更正後發布修補版。
- 原固定 reader 不跟著目前版改變；修補不推進背景游標；過時整理要求被 CAS 拒絕且沒有回執。
- 關閉 Store 與 Saver 連線後，已提交操作仍由原 SQL 回執查回，不需重新讀原話或重做 artifact；目前版不倒退。
- 新連線／新 serializer／新 graph／新 owner 讀回完整原話、詳記與新舊 Memory；零重播。這是同程序資源重開，不冒稱跨 Windows 程序／正式 host 恢復。

首跑 **1 FAIL／8.17s**：測試把既有 `extraction_window()` 的 dict 誤當 tuple；只修 oracle，核心未改。最後 **1 PASS／7.81s**，合成 document `429c7172-11bc-4edf-81cf-762354ca7adc`；實際 head **2**、receipt **2**、artifact **6**，provider **0**。原話仍留 Saver，沒有另建對話表；資料保留供查核。

## 包裝與依賴

- [pyproject](../../../../packages/consultant-memory/pyproject.toml) 使用 Hatchling；`uv build --offline` 成功建立 sdist，並從 sdist 建 wheel。
- 在新的獨立 venv 安裝 wheel；以 `python -I` 實際 import 的位置為該 venv 的 `site-packages/caliburn_memory`。無 App／舊 `analysis_agent` 可匯入，sys.path 沒有舊 checkout 或 editable package 路徑。真 InMemoryStore／StoreBackend＋SQLite 保存／發布／原回執與讀取成功。這不冒稱 PG 測試。
- App lock 原 **86** 套件版本全部保留，新增 **16**；獨立 wheel 依已固定 constraint 安裝其 **61** 個依賴。Deep Agents 自帶 provider 套件，但核心不建立任何 provider。
- 首次 offline lock 缺 Deep Agents metadata；改從官方 PyPI 解析已選定精確版本。獨立 wheel 首次嘗試安裝全部 App export 時，offline cache 對部分 wheel 不完整；改為只安裝 wheel 的相依閉包、沿相同版本 constraint，安裝成功。沒有鬆動版本來迎合結果。
- 採用來源與最終核心 hash：[adoption.json](../../../../packages/consultant-memory/adoption.json)。本機 wheel／獨立 smoke 紀錄留 `.research-tmp/jd-memory-core-dist`、`jd-memory-core-wheel-result.json`，不是產品依賴。

## 受影響接線

原來源故障、context、工具、手改 service、managed App、AI runtime，加新 Memory source，共 **113 PASS／14.43s**。僅上游 Starlette 使用 AnyIO 已棄用 alias 的一則 DeprecationWarning；未因此升級或改動無關框架。核心 **44 PASS**、source **71 PASS** 及獨審 **98 PASS** 的重疊範圍分別見[核心](core-results.md)、[來源](source-results.md)、[審查](review.md)，不累加成獨立案例數。

未跑新畫面／自然模型，未重新執行全部無關 App 測試。未完成的模型 Memory 工具、B1/B2/C、宿主 Store／備份及專業品質仍在[唯一清單 OI-01／02／08／09](../../2026-09-13-jd-app-open-issues.md)。
