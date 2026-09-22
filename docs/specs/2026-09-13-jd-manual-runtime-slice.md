# JD：持久操作紀錄與人工寫入執行流程

- 日期／查閱日：2026-09-13；JD-R002，RS-1／2→3 隔離接合。
- 承接[查詢／原身分恢復](2026-09-13-jd-query-api-and-recovery-identity-slice.md)及[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。本單位範圍是**單程序人工寫入 owner＋原生 PostgreSQL Saver**；完整宿主、AI 回合、App、G4／G6 尚未完成。
- 六章、十三張 JD 表、關聯式 current 權威、唯一工作稿、Memory／原話責任及 Excel 延後不變；框架可替換，不 import 舊實驗，0 產品模型呼叫。

## 1. 交付效果與責任

人工修改進入真正 SQL 前，先在文件的原生 root checkpoint 保存必要操作身分。已確認 JD 結果與操作收尾都完成後，才放行同文件下一次修改。等待回覆逾時不等於取消寫入；結果未知時保持可查回的狀態，不自動重播。

| 責任 | 本次實作 |
|---|---|
| 共同業務及交易 | 既有八個具名 command、`BoundEdit`、`JdStorage.execute`，正文／關係／revision／receipt 同一交易；本次不複製人工專用規則。 |
| 操作前紀錄 | `DocumentCheckpoints` 透過官方 `get_state`／`update_state`／readback 寫原生 root；只記原身分，不保存第二份候選、聊天或 Memory。 |
| 實際寫入者 | `ManualRuntime` 持有執行 SQL callable 的原生 `Future`；以同文件鎖保護操作接納、狀態與收尾。短 registry 鎖只管理字典／是否接新工作，沒有 DB I/O。 |
| 查回原結果 | `JdStorage.lookup(AdmittedIdentity)` 短唯讀交易核原 operation／意圖；同身分回原結果，同 key 不同意圖拒絕，未找到不代表舊 writer 已停止。 |
| 停寫後恢復 | 只有本程序已知從未提交 SQL，或其實際原 writer Future 已完成，才可用原身分執行既有 failure-only 對帳。先查原回執；不重建候選、不重跑 command。 |
| 訪談與 Memory | 此切片不啟動顧問、不補造 HumanMessage、不回滾對話或 Memory。root 直接掛 native consultant child，兩者同一 Saver；測試只使用合成 child。 |

不同文件的 owner 鎖互不覆蓋；共用原生 Saver／連線仍受框架自己的短 I/O 序列化，這不是全文件業務鎖。採本機有限 thread pool，沒有宣稱任意文件數都能同時寫入。

## 2. 官方依据與有限選型

下列為查閱日現行官方文件／發布資料；套件精確版本以本目錄 `uv.lock` 為準。官方契約、本案映射及尚未證明分開，沒有「所有大廠都用同一框架／資料欄位」的宣稱。

| 來源／版本、狀態、授權 | 官方事實 | 本案取捨及限制 |
|---|---|---|
| [AWS Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)，現行指引，無套件版本；文件參照 | 多種 client 可共用 domain，UI／DB 接點與業務規則分離；同時提醒額外 adapter 的維護代價。 | 人工與 AI 入口轉入同一具名 command／規則，保存與 runtime 各有接點；不因此引入 AWS 雲端服務、每表 repository 或通用框架。 |
| [AWS safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，現行 Builders' Library；文件參照 | 使用明確 request identifier 表達同次意圖，辨識相同 ID 的不同參數，保存 ID 與變更需原子性，重送可回語意相等結果。 | operation key＋意圖摘要＋原 receipt；逾時先查回。本案七欄 descriptor 與 SQL 表是映射，不是 AWS 規定。 |
| [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[persistence](https://docs.langchain.com/oss/python/langgraph/persistence)；LangGraph **1.2.11**、checkpoint **4.2.0**、PG Saver **3.1.2**，MIT、正式發布／非 preview | 原生 thread state、checkpoint、公開 state update、子圖繼承 Saver；執行 replay 有重做節點／task 的條件。 | 此次選擇原生圖與 Saver 直接保存必要狀態，符合根／子圖與獨立 JD SQL 邊界；checkpoint 本身不是鎖、OS 停止證明，也不與 JD SQL 自動成為一個 ACID 交易。 |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/running_agents/)、[0.22.2 發布](https://pypi.org/project/openai-agents/)（2026-09-09），MIT，非 preview；0.x 不解讀為介面永不變 | Session 保存對話、RunState 支持暫停／恢復；另有[官方 Temporal 整合](https://github.com/temporalio/sdk-python/blob/main/temporalio/contrib/openai_agents/README.md)。 | 不是沒有持久方案；Temporal 引入額外服務／worker，I/O 工具須按其 activity 契約接合。此次必要的本機 root metadata 不採新增 Temporal 服務；不否定此 SDK 的一般 Agent 能力。 |
| [Claude Agent SDK 0.2.152](https://pypi.org/project/claude-agent-sdk/0.2.152/)（2026-09-02）、[session storage](https://code.claude.com/docs/en/agent-sdk/session-storage)、[授權](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.152/LICENSE)；SDK MIT，PyPI Alpha，bundled CLI 有其他商業條款 | SessionStore 是 local transcript mirror；append 拒絕有短 backoff 最多三次、timeout 不重試，最終 mirror_error 可在 query 繼續時丟棄該批；eager flush 為 Alpha。 | 不可用此 mirror 當本案「確認持久化後才執行 SQL」屏障，也不能稱全套穩定 MIT OSS。這是本切片不採原因，不猜 Claude 產品內部資料庫。 |
| [Python 3.12 concurrent.futures](https://docs.python.org/3.12/library/concurrent.futures.html)，本機 **3.12.13**，穩定 stdlib／PSF 授權 | timeout 只停止等待；Future 提供執行／完成狀態，callback 可在 Future 已完成時於註冊方執行，executor shutdown 有獨立責任。 | owner 追實際 callable，不追 HTTP waiter。關閉先禁止新接納、等待 writer 及 checkpoint cleanup；不能把 timeout 或 Future.done 單獨當全部收尾完成。 |

新加入的直接依賴只有 LangGraph 1.2.11 與 PG Saver 3.1.2；必要傳遞依賴包含 langchain-core **1.6.3**、prebuilt **1.1.0**、SDK **0.4.4**、psycopg-pool **3.3.1**，依 lock 固定。沒有因舊目錄已裝 LangChain 而接入舊 runtime；完整 AI middleware 選型仍在實際接點前閉合。

停止本層廣搜：三方向的持久責任差異已能解釋取捨；剩餘工作是固定依賴下的實測與宿主接合。最新版本不是犧牲產品效果或採 preview 的理由。

## 3. 保存與失敗流程

1. 同文件取得 owner gate，先確認 root 無 native next／tasks／interrupts、沒有未解操作。
2. 用嚴格原身分唯讀查原 receipt；存在則回原結果，意圖不同則拒絕，無須再發 pending。
3. 保存 `jd_manual_pending`，欄位為 `format_version=1` 加原 `document_id`、`operation_id`、`base_revision_id`、`origin=manual`、`ai_run_id=null`、`request_digest`、`command_kind`。App 配发，模型不填。
4. update 後精確讀回；ACK 遺失同樣只讀回一次，不能重播 update。確認後交受管理的 native writer 執行 SQL，Storage 於寫入邊界核對 owner、原身分與實際工作執行狀態。
5. SQL 回已確認結果（包括確認的失敗）後，僅清除相同 pending。保存結果未知或 cleanup 未確認時保留 gate、身分及已知回執；下次明示查回，不自行重跑。
6. graceful close 的期限包含接納／checkpoint I/O、實際 Future 及 callback 收尾。逾時回未關閉，資源由 host 保留；不是使用者「取消這次修改」功能。

人工 root update 使用 `as_node="consultant"` 的原生 state update，讓節點路由停在 END，不 invoke child。未知版本、額外欄位、非 canonical UUID、跨文件、身份衝突、native pending work 都拒絕。已知 `document_busy` 保留其語意，不誤報為保存服務不可用。

一個新程序只看見持久 descriptor 時，**不能恢復宣稱原 writer 已死**。此 owner 保持阻擋，留待實際 host 單程序互斥／舊程序退出證據接好。這不是暫時自填 stopped=True 的接線。

## 4. 可重現實證

程式在 [隔離 App](../../experiments/jd-relational-app/README.md)。明示 `scripts/init_test_runtime.py` 只連本機 55436、固定合成 DB／user／PG18.6，先核 public 十三 JD 表＋Alembic `20260913_0001`；再為 `jd_runtime_test` 呼叫官方 `PostgresSaver.setup()`。原生四表為 `checkpoint_migrations`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`，不計入十三張 JD 表。

實際核已裝 Saver 原碼：連線 `autocommit=True`、`dict_row`、`prepare_threshold=0`；原生 migration 有 `CREATE INDEX CONCURRENTLY`，setup 不包外部交易。初始化已成功執行兩次，不清空資料；一般啟動／讀寫／測試 fixture 都不偷偷 setup。測試 serializer 採內建 allowlist，沒有開放任意 msgpack 型別。

| 實證層 | 驗證與界線 |
|---|---|
| native MemorySaver | 55 tests；三種合法 child checkpointer 組合另作有限獨立 probe，manual admit／close 不改 root messages 或子圖 namespaces，也不額外 invoke。不是正式 Memory Store 整合。 |
| 真 managed threads | 16 tests；同文件阻擋、不同文件在他檔 checkpoint I/O 中仍可完成、等待逾時不當取消、未知結果不自動重播、已保存結果在 cleanup 故障中保留、關閉期限及中斷。持久層為合成替身。 |
| 真 PG Saver＋真 JD SQL＋實際 owner | 8 tests；在真正 `UPDATE jd_profile` 前新連線已看見 descriptor，原 messages／native blocks 不變；admit ACK 遺失讀回或拒寫、COMMIT ACK 遺失回原 receipt、cleanup ACK／讀回遺失、native busy 阻擋、同／異文件與新連線、新 Python 程序續讀。不是自然模型或跨程序死亡證明。 |
| 原操作 lookup | 24 tests＝13 離線＋11 真 PG；只读、固定錯誤、原身分／衝突，不引入 candidate 或新 writer。 |

首敗保留：新增模組尚未存在；shutdown 原本未把 admission I/O 算進期限；PG runtime schema 未初始化（1 FAIL，沒有偷建）；獨立審查 R1 發現 worker／cleanup 的 BaseException 會令 attempt 永不 settle（2 FAIL＋2 teardown ERROR），R2 發現 admission 中斷亦留假 running（1 FAIL）。修後 worker exception 以 Future.exception() 作資料處理，cleanup 必收尾；主執行緒中斷仍傳遞，已知未提交 SQL 的狀態先記清。另修 native busy 錯誤分類。

最終全目錄離線 **955 PASS／108 PG SKIP**（20.28 秒）；受影響接合命令為 `tests/test_manual_runtime_postgres.py tests/test_operation_lookup.py tests/test_storage_service.py tests/test_runtime_checkpoints.py tests/test_manual_runtime.py`，**131 PASS＝84 離線＋47 真 PG**（10.47 秒）。生成 Python／TS 相等檢查及 TS 編譯通過；六份 schema／十二個生成物未變。前次 Starlette／AnyIO alias 的一個第三方棄用警告仍保留，沒有自行修改 vendor 或遮蔽。

獨立審查：`jd_format_audit` 核實際 owner，R1／R2 修後 16 tests 窄複核 PASS，無其他阻擋；`jd_command_semantics_review` 核 checkpoint adapter（55 PASS＋三種子圖配置 probe）及真 PG 接合（8 PASS＋四個 initializer guard 反例）；root 核原回執 lookup、資料權責、全部最終驗證與文件一致性。這些分組不再相加為另一個總數。

## 5. 下一接合範圍

下一單位接實際 host 的单程序互斥、跨重啟原 writer 退出證據與全部原 descriptor 對帳，再接同一業務保存的人工寫入 HTTP。AI 原 tool-call／run 綁定、前景回合 gate、實際 source owner／Memory 接點與人工變更通知依相依順序接合，不新增平行 run 或 catalog 權威。

六章管理畫面、autosave 暫存、來源、歷史／整輪 JD-only 撤回、日常啟停／備份與自然訪談驗收仍沿總計畫推進。本次沒有可使用的完整 App 畫面，也沒有正式產品切換。
