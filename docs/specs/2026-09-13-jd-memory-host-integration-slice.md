# JD App：Memory 宿主接合

2026-09-13，JD-R002／OI-02。基準 `8672d93122891a8a1bb47742214374ceb9aeb091`；沿[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)及[已驗核心](2026-09-13-jd-memory-core-adoption-slice.md)。隔離施工；ADR0074／0075 Proposed，正式產品 ADR0060 不變。

## 要完成的效果

App 啟動時打開既有 Memory 的保存資源，正常重開可以讀回修正後的工作理解。停止先等已登記工作排空，再關資源；初始化只由明示操作執行。這是接模型 Memory 工具及背景整理的必要生命週期，沒有新歷史操作介面。

本單位不宣稱自然模型品質、完整 B1/B2/C 或背景排程完成。先把同宿主資源接正確，不為未接背景工作增加泛用 job registry／worker 引擎；後續新增的工作必須納入實際排空與持久恢復責任，不能用目前前景／讀取測試代稱已覆蓋。

## 有界配置與資料責任

- 保留同一 `LocalConfiguration`、dataset 與資料庫，不增加設定欄位、另一個服務或資料權威。既有 `checkpoint_schema` 作此 App 的執行資料 schema，包含四張 Saver、兩張官方 Store 與兩張原 Memory publication 表；public 的十三張 JD 表與 Alembic 不变。
- Memory metadata 用既有 `PublicationStore`，以 SQLAlchemy `engine.execution_options(schema_translate_map={None: checkpoint_schema})` 固定映射。與 JD engine 共用 pool，但不改 JD search_path／全域 ORM metadata；每個 Session 固定單一 map。沒有多租戶或動態切換 schema。
- Host 額外開一條原生 PostgresStore psycopg connection，與 Saver 分開；`autocommit=True`、dict rows、已驗 prepare 設定。Store 不啟向量索引／TTL清除／shell。原生 SQL 索引／欄位由所選框架版本保留，不因本案未用 TTL 就自行刪除框架欄位。
- `build_document_graph` 使用官方 `compile(store=...)`；工具／節點從原生 Runtime 取得同一 Store。拒絕 child 預綁另一個 Store，避免兩份 Memory。原本沒有 Store 的純圖測試仍可使用框架原生空選项；一般 App host 必須有完整 Memory 保存前置。
- SourceReader 繼續委派同一原話 owner；模型不生成版本、操作身分或資料庫位置。JD 撤回不影響 Memory／案例／原始問答。

## 初始化、重開與停止

`setup_database` 僅在原 `initializing` 狀態及同安裝原生 lease 下執行。先核固定已知 JD／Saver／Store／publication 形狀與無使用資料，再用原 Alembic、官方 Saver／Store setup，以及同交易的 publication metadata create_all 完成初始化。原生 setup 的 DDL 已成功但版本記號未記下時，僅接受精確已知的下一步狀態；未知表、版本缺洞、錯欄位／索引與非預期資料不自動修復。

普通 open 只有唯讀前置核對，不呼叫上述 setup。尚未加入 Memory 的舊 ready 實驗資料庫會明示 schema mismatch，不能在正常開啟時偷補表或清資料；本案不安排舊資料搬移。獨立合成 host fixture 的必要補表由專用明示 script 處理，不把測試準備偷放進測試或產品啟動。

Host 先驗原生程序資格與已知配置，再開 JD engine／Saver、核已安裝結構，然後開 Store／schema-mapped engine view／graph。中途失敗清理已開資源，對外固定錯誤碼，不暴露 DSN、原話或 driver 訊息。

停止沿同 `ManualRuntime.close`：已登記讀取與前景／保存未結束時回未完成，Store／Saver／pool 全保留；排空後依序關 Store、Saver、共同 pool。單一 close 失敗仍嘗試其餘清理，整體結果為未確認。沒有按 port 任意 kill 或新增全域業務鎖。

## 官方依據與適用界線

查閱 2026-09-13；以下是正式公開能力，本案八表配置／初始化 profile 是映射，不稱為各大廠共同採用的資料表設計。

| 官方資料 | 本案使用／限制 | 版本與狀態 |
|---|---|---|
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | compile 可同時提供 checkpointer 與 Store；兩者保存不同內容。沿原生 Runtime 注入，不自製上下文儲存。 | LangGraph 1.2.11／checkpoint-postgres 3.1.2，MIT；本機 OSS，不採付費 Agent Server。 |
| [SQLAlchemy schema translation](https://docs.sqlalchemy.org/en/20/core/connections.html#translation-of-schema-names)／[execution_options](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Engine.execution_options) | ORM table schema 可固定映射；OptionEngine 共用原 pool，ORM 每 Session 單 map。只映射 Memory metadata，不改 JD。 | 2.0.52 穩定版、MIT；不採 2.1 beta，不把 raw SQL 視為會自動映射。 |
| [Psycopg concurrent operations](https://www.psycopg.org/psycopg3/docs/advanced/async.html) | 同連線的操作／交易有共同狀態；Saver 與 Store 各持連線，資源在持有程序建立及結束。 | 已鎖 3.3.5、LGPL；官網頁頭目前為 3.3.6.dev1，因此另核已安裝版本與真 PG，不依預覽特性。 |
| [AWS ports／adapters](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html) | 延續上單位已查的實際可替換來源埠；不增加沒有需要的分層／微服務。 | 現行官方文件條款，非框架或指定 schema。 |

LLM／App 責任仍沿[上一單位的 OpenAI／Anthropic 依據](2026-09-13-jd-memory-core-adoption-slice.md#官方依據與取捨)。本單位沒有更換 provider／LLM 工具契約，不重開已收斂的模型比較。

## 必要驗收

1. 純反例：普通 open 不 setup，部分資源失敗皆清理；已登記讀取未完成時不可關 Store／Saver；child 確实取得原生 Store，另綁不同 Store 被拒絕。
2. 真 PG：全新明示初始化、固定原生 prefix／版本記號遺失恢復；缺 Memory 的 ready 與未知形狀拒絕；public 不變。
3. 新程序：真 DPAPI 配置／Windows host 建立 JD 及合成原話，使用 host 的 Store 與 publication view 保存／修正；退出後另一程序讀原 Memory／原話／回執，schema OID 不變、無 setup／模型重播。
4. 回歸：受影響 host／配置／原生 checkpoint／已存在的真宿主旅程，固定合成 fixture 明示更新後再跑；不把四表純 Saver 測試強迫改成完整 host。

## 實際結果與下一工作

已完成原生 Store 注入、host 資源排空、Memory schema-mapped publication view 與明示初始化。最後受影響 **154 PASS**、初始化 **33 真 PG PASS**、新 Windows／PG Memory 旅程 **1 PASS**、原 JD／AI 三條新程序回歸 **3 PASS**；[獨立審查](evidence/jd-memory-host-integration/review.md)限定範圍無 P1／P2。[資源／原生結果](evidence/jd-memory-host-integration/runtime-results.md)、[初始化結果](evidence/jd-memory-host-integration/setup-results.md)保留首敗、修正、版本及各自驗證範圍；不累加重疊測試數。

同一設定的另一程序可讀修正後 Memory、原話與原回執；普通重開不建表、Memory 修補不改 JD。沒有新依賴／模型工具／provider 呼叫，production 未切換。

下一將已驗 Memory 的固定 head／導覽、只讀工具及原話按需回查接入實際顧問 context，再接既有 C／B1/B2 的真正執行與排空。以既有功能及已觀察缺口為準，不先造通用 scheduler／定位引擎；完整成品的未完事項仍在[单一收尾清單](2026-09-13-jd-app-open-issues.md)。
