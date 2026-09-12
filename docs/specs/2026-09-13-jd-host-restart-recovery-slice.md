# JD：Windows 宿主互斥與跨重啟恢復

- 日期／查閱日：2026-09-13；JD-R002，RS-2→3 隔離接合。
- 承接[人工持久執行流程](2026-09-13-jd-manual-runtime-slice.md)與[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。本單位接真 Windows 宿主与 PostgreSQL 恢復；寫入 HTTP、完整管理畫面、AI 回合及 G6 仍未完成。
- 同一安裝、同一 Windows 登入 session、本機資料集；不新增登入／ACL 產品功能、多程序 worker、雲端、舊資料搬移或模型呼叫。業務正文仍十三張 JD 表。

## 1. 使用效果與實際接法

App 重啟先確認上一組受管程序已退出，再查每份文件的原操作。JD 已提交就保留原成功；原操作確定未提交時，只記原操作失敗。所有文件處理完成後才開放新修改；不重跑訪談、不重播 JD 指令、不清 Memory 或原話。

| 接點 | 實作與責任 |
|---|---|
| `windows_host.bootstrap_host` | 主執行緒取得固定安裝 named mutex，清查同名舊 Job，證實舊組退出，再把新宿主納入新 Job。只處理 OS 所有權，不推定 SQL 已提交／回滾。 |
| `HostLease` | 程序內 capability，核本次 singleton、PID、主執行緒仍存活及 exact Job membership。沒有 caller 填 stopped=true、PID 資料表或 TTL。 |
| `open_manual_host` | native bootstrap／lease 成功後才建立 engine／Saver 連線；只 SELECT 核 PG、schema、migration，缺初始化就拒絕，不自動 setup。返回的 runtime 仍不可寫。 |
| `ManualRuntime.finish_startup` | startup→ready→closing。逐頁掃同一 `jd_document` 全 catalog，包含封存文件；逐個原 root 的 pending 沿 managed Future／原恢復交易／checkpoint cleanup 閉合，全部完成才 ready。 |
| `JdStorage.lookup`／`JdReader.document_ids` | 原回執優先；無回執還須確認文件存在，避免保存無法由 catalog 列舉的孤立 root。catalog 僅 ID、keyset、短唯讀交易，不複製 run／checkpoint／對話。 |
| 關閉 | 先停新接納，等待 startup I/O、managed writers 與 cleanup；未完成時保留 Saver／DB。OS job／mutex handles 交程序最終退出關閉，不在一般 close 中提早釋放。 |

正常 CRUD 仍按文件區分鎖。安裝 mutex 只排除第二個宿主世代；startup lock 只保護一次完整恢復掃描，不是把所有文件的日常業務串成一把鎖。

## 2. 官方契約與本案映射

| 現行官方來源、版本／狀態／授權 | 直接支持的事實與適用限制 |
|---|---|
| [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)，Win32 正式 API；本機 Windows 10.0.26200，非 preview 契約；文件參照非複製程式授權 | Job 管程序組；普通 child 預設繼承 membership；KILL_ON_JOB_CLOSE 有最後 handle 的終止語意，不能設定 breakaway 後仍宣稱全組受管。Job 等待 signaled 有特定 time-limit 語意，不當一般整組退出條件。 |
| [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)、[CreateMutexW](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw) | WAIT_ABANDONED 只表示 mutex 持有 thread 結束，不表示 process 或其他 threads 結束；timeout 不授權本案啟動。 |
| [Job accounting](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)、[CreateJobObjectW](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw) | exact Job 的 ActiveProcesses 是原生查詢；同名 CreateJob 回既存物件及 ERROR_ALREADY_EXISTS，不能把它當 fresh Job 加入。 |
| [Restricted Tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens)，Win32 正式契約 | restricted token 的存取判斷涉及一般及 restricting SID。只自行加入 TokenUser ACE，不能保證受限制程序可重新存取該物件。CreateMutex／CreateJob 的預設 security descriptor 取 creator token 的 default DACL。 |
| [pywin32 b312](https://github.com/mhammond/pywin32/releases/tag/b312)、[PyPI](https://pypi.org/project/pywin32/312/)、[授權入口](https://github.com/mhammond/pywin32/blob/b312/README.md)、[PyHANDLE 原碼](https://github.com/mhammond/pywin32/blob/b312/win32/src/PyHANDLE.cpp)；**312**（2026-06-04），Production/Stable，cp312 Windows wheel；各組件混合授權，不稱整包 MIT | 提供 Windows 原生 API 接點。PyHANDLE 回收會 Close，Detach 移轉 wrapper 所有權而不 close；適合本案必須保留至 OS 程序退出的 self-job handle。 |
| [PG18 locking](https://www.postgresql.org/docs/18/explicit-locking.html)，實測 **18.6**／PostgreSQL License；[LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)，沿已核 1.2.11／PG Saver3.1.2、MIT | OS 停止不能代替 DB 交易結束。仍沿 document→head row lock，下一 statement 查原 receipt；原生 checkpoint 保存 pending 身分，不能以 replay 代替業務對帳。 |

這是依平台公開契約組合的本案設計，不宣稱 AWS、OpenAI 或 Anthropic 的內部宿主皆用此方式。[AWS 業務分層／安全重試及兩家 Agent 持久責任比較](2026-09-13-jd-manual-runtime-slice.md#2-官方依据與有限選型)仍有效；這次不再重開同層品牌廣搜。

相較替代方向：单一 file／mutex lock 的釋放不足以證明另存活 thread 或 DB 工作已停；另外常駐 supervisor／分散式 lease 不是本機單人的必要依賴。選 Windows Job＋mutex 與 native PG 對帳，沒有自建跨平台程序管理引擎。

## 3. 本次實測修正的兩個 Windows 細節

**安全描述元：**最初僅 TokenUser 的自建 DACL 在本機 restricted token 下令第二程序 CreateMutex 回 ERROR_ACCESS_DENIED（首輪 3 FAIL／22 PASS）。改用 Win32 creator token 的原生 default DACL，保持不繼承 handles；不放寬 Everyone、不自行猜測全部 SID。這取代[舊生命周期設計 §6.3](2026-09-10-jd-native-process-lifecycle-design.md#63-api-自持-job-的最小啟動順序)的自拼 private ACL 細節，產品權限範圍不變。

**舊物件退休：**舊組 ActiveProcesses 已為零，仍可能短暫取得同名既存 Job（DACL 修後 1 FAIL／24 PASS）。保持第一次替代啟動成功的驗收：在同一 monotonic 啟動預算內，只關閉該既存 candidate handle 並有限等待 fresh Job；不再次 Terminate、不 assign／重用舊 Job，不重播 DB／模型動作。持續有外部 handle 阻止退休時，到期仍 `host_job_conflict`，不開 App 資源。這取代舊設計對瞬間 ERROR_ALREADY_EXISTS 立即要求再啟動的細節。

成功 self-assignment 後 Job／mutex 都 Detach 成程序私有 raw handle，由 OS 最終退出清理；不提供早釋放方法／context manager／atexit Close。原生 nested Job 已在本機受管執行環境驗證；不使用 breakaway fallback。bootstrap 失敗後該專用宿主退出，不能在同一 Python 程序換安裝 key 重試。

## 4. startup 與 SQL 的恢復界線

外來 pending 的 `_Entry.previous_host` 與「本程序從未提交 SQL」分開。每次 Storage 要求停止證明都重核 live HostLease；不存在本地 Future 本身不提供證據。foreign pending 若意外消失而未持有 confirmed 原 receipt，保持 `checkpoint_conflict`，不能套本地 known-unsubmitted 捷徑。

恢復 timeout 保留同一實際 Future；同程序再次明示 finish_startup 不新增並行恢復。已確認 receipt、只差 checkpoint 清理時，只重試清理。部分文件已完成而其他文件失敗，不重做前者，也不提早放行新修改。native next／tasks／interrupts、未知 checkpoint 版本或損壞身分均阻擋，沒有抹去舊 tasks 或強制 END。

枚舉的前提是所有正常入場文件均存在同一 catalog、無永久刪 catalog、同資料集所有寫入入口共用固定安裝 key，完整掃描前不開 catalog mutation。分頁本身不是跨頁持續 DB snapshot。這是目前單程序／單操作者設計，不覆蓋繞過宿主的 SQL client 或另一套安裝／Windows session；新機制也不能回套未受管的舊產品程序。

## 5. 實證與重現

[隔離 App README](../../experiments/jd-relational-app/README.md)維護命令。新增 Windows-only `pywin32==312`，其他既有版本不升級。明示 `scripts/init_test_runtime.py --schema jd_host_test` 只在 55436 合成 DB 新建另一組四張原生 Saver 測試表；public 十三 JD 表／Alembic及原 `jd_runtime_test` 不變。分開 schema 使舊 native-busy 反例不被這批正常 host 恢復測試清除；普通宿主沒有 setup。

| 實證層 | 本次驗證 |
|---|---|
| 原生 Windows | 30 tests＝26 輸入／假 OS 分支＋4 真 Windows 情境。self-assignment 僅在獨立 CREATE_NO_WINDOW helpers；nested membership、same-key contention、abandoned 舊 process 仍存活、child membership／父退出後 child 終止、有限舊物件退休及額外 handle 阻擋。沒有將 pytest／工具自身加入 Job。 |
| startup／資源合成 | 全 catalog 分頁／封存、未 ready 禁止寫入、lease 失效、部分 cleanup／原結果保留、timeout 不另排 Future、關閉期限含 scan I/O；只有測試替身的層級明示，不算 OS／DB。 |
| 真 Windows＋PG | 四案例：durable admit 後 SQL 前 crash→原 failure-only receipt；COMMIT ACK lost crash→精確原 committed receipt，revision 不增加；第二宿主在 DB 前 busy，原 writer 正常完成；兩文件含 archived pending 全部閉合。 |
| 同值／程序證據 | 新程序重讀 snapshot、原 messages／opaque native blocks、archived 及 receipt 原身分；崩潰 helper exit73、新宿主 exit0，恢復數1／1／2、競爭者 DB attempts0。父 harness 只操控自己的程序，不提供 stopped boolean。 |

首敗另含新接口／helper 尚不存在、startup scan I/O 沒算入 close deadline，以及不存在 catalog 文件仍能保存 pending；均保留後修。原 lookup 對不存在文件的 None 斷言改為 `document_missing`，現存文件無 receipt 仍為 None，原 receipt 仍優先。原始合成程序證據留在 repo `.research-tmp/jd-host-recovery-*`，測試可以重新產生，不是交付時依賴的 runtime 目錄。

最終全組 **1026 PASS／117 PG SKIP（22.39 秒）**；受影響接合組 **211 PASS（37.37 秒）**＝155 非 PG（含 4 真 Windows）＋56 真 PG（含上述 4 跨程序案例）。兩組有重疊，不能相加當獨立案例數。生成檢查與 TypeScript 編譯通過；0 產品模型呼叫。保留一筆既有第三方 Starlette TestClient／AnyIO deprecation warning，未更動第三方程式。

獨立審查通過 startup／資源／lookup 界線與四組跨程序原始證據，另窄跑原生三檔測試 **30 PASS（1.93 秒）**，核對 default DACL、不繼承、Detach 生命週期、同一期限等待新 Job 及失敗出口，無阻擋項。額外 lease 失效、分頁失敗、部分 cleanup、close 期限及 native-busy root 反例均維持禁止誤放行；自有 helper 已確認退出。這些證據限本機人工操作宿主與指定合成資料庫，不延伸為 AI 回合或完整 App 驗收。

## 6. 下一工作

接共享業務保存的人工寫入 HTTP、操作查回與資源狀態，並供 RS-3 六章管理畫面使用；不以測試 stdin 的 CRASH／STOP 當產品 endpoint。資料集識別／簽章持久設定、選區、source owner、autosave、catalog 管理、歷史／整輪 JD-only 撤回、AI run/call 綁定及日常啟停仍按相依順序完成。

本單位驗證人工舊操作恢復，不代表 AI 中斷回合已能恢復，也不代表可使用 App、自然訪談或正式產品切換已完成。
