# JD 成品：既有顧問／Memory 正式採用與本機保存設計

2026-09-10；JD-R002/R5、LLM-Q019。G4 有限設計審查 PASS，結果見[基線審查](evidence/2026-09-10-jd-product-baseline-review.md)與[生命週期補充審查](evidence/2026-09-10-jd-native-lifecycle-review.md)；ADR0074仍Proposed，production尚未採用。依[成品總計畫](../plans/2026-09-10-jd-product-delivery.md)與[主設計§4.1](2026-09-09-jd-editor-app-integration-design.md#41-接合目標與正式切換邊界)，本單位只閉合正式採用接點。原隔離六切片可繼續，production依§5準備核心／P3證據與採用manifest，再通過本設計／successor ADR 的G6。

## 1. 已核對的現況

| 面向 | 2026-09-10本地事實 | 採用要求 |
|---|---|---|
| Current | `apps/api/app/main.py`組合ADR0060、OpenRouter、舊pending/approved；Web仍8001 | 不能只改API URL或套新畫面便稱正式採用 |
| 隔離成果 | `.worktrees/analysis-only-agent` HEAD `622e548d9d37ce4f8adb2ac0f0e61ce0d7aad3d9`；CT49–51之後README等既有dirty另留 | 在核心驗收後固定實際採用commit／逐檔hash；不混入未審改動 |
| Python/框架 | 隔離Python3.12；LangChain1.4.0、LangGraph1.2.11、Checkpoint4.2.0、Postgres3.1.2、DeepAgents0.7.13、OpenAI3.8.0、langchain-openai1.6.0；current Python>=3.13／LangChain1.3.15／DeepAgents0.7.5 | 採受測3.12 stack，精確lock；不借接線升級或強套舊lock |
| 原始來源 | `sources.py:33–47`以graph.get_state(thread_id,checkpoint_id)讀Saver；缺指定checkpoint明確失敗，不用最新版冒充 | 與ADR0060「來源Store唯一owner」不同，須獨立successor |
| Memory | `memory.py`使用官方StoreBackend、文件namespace；`publication.py`僅保存head／receipt／來源進度 | Store內容＋發布metadata，不再把checkpoint中的另一份理解當可寫真相 |
| 初始化 | 隔離`api.open_service`有q019_本機DB保護，但啟動會Saver/Store.setup、catalog/publication.create_all；`BackgroundDispatcher.__init__`也會catalog.setup | 全部移入明示維護setup；日常啟動不從dispatcher偷建schema，不能移除保護後指向舊DB |
| 生命週期 | 單一API worker，service.start對帳、service.close停止接納／join前景背景後關資源 | 保留已驗取消與恢復；前景JD效果按六切片加入，不以shutdown取消Future冒稱安全 |
| Catalog | `q019_document`僅id/title/created_at；run有同document/request_key唯一约束，message bodies在Saver | lifecycle增補沿[R2/R3](2026-09-10-jd-employee-journey-design.md)，沒有現成刪除／封存能力 |

CT49–51證明的範圍沿原紀錄，不代稱加入JD後的自然模型品質。舊ADR／README中的模型預設、來源owner、pending或刪除政策不自動沿用。

## 2. 正式保存責任

這是本案採用映射，不是OpenAI／Anthropic或LangGraph規定的完整產品schema。

| 事實 | 唯一owner／正式讀取 |
|---|---|
| 文件身分、名稱、建立時間、封存與metadata版本、建立去重 | 最小catalog；App注入文件scope，封存不是刪除 |
| 原始員工對話、AI/Tool實際項目、回合／子流程恢復狀態 | 官方PostgresSaver，原始來源由既有ConversationReader按確切checkpoint及message身分讀；API只呈現可見原文，不揭露隱藏reasoning |
| 詳記、工作理解內容與導覽、已保存Memory版本 | 官方PostgresStore／StoreBackend；既有發布head/receipt決定有效版本，raw Store存在不代表已發布 |
| Memory發布進度／回執 | 既有PublicationStore薄SQLmetadata；不重存正文、不混入JD版本 |
| 背景接納、待處理target/source、錯誤及recovery_count | 既有`q019_background_admission`映為正式catalog內的`consultant_background_admission`；只存admission/error metadata，B1/B2進度仍由Saver及發布回執負責 |
| 唯一當前JD、不可變JD版本、已發配操作結果 | ADR0073的jd_head/jd_revision/jd_operation，沿v2；checkpoint只引用，不存第二份可寫JD |
| 前端未保存內容／待對帳提交 | 非權威UI候選；不得覆寫保存稿、來源或Memory；詳R2 |

任何來源引用使用既有`conversation:`契約；不能以Memory檔名代替確切原話。手改JD是文件變更，其差異可讓LLM知道，但不偽造新的原始訪談。Saver與Store的完整文件scope都由App身分決定，沒有跨文件自動召回。

**封存**沿R2的metadata條件式修改，保留所有Saver、Store、發布與JD紀錄。拒絕新前景／人工寫入，前景writer安全結束及必要效果對帳後才完成封存；不等背景歸零。已收到來源的背景B1/B2與既有修復／受控恢復政策繼續，包括尚未首次排程及部分批次；封存本身不額外發起新工作。內部scheduler須枚舉含archived的完整catalog，不共用UI列表active-only預設。舊receipt和狀態查詢不被封存遮斷，恢復不重播已完成操作。首版不自動剪除checkpoint／Memory版本／JD歷史，因確切來源仍可能引用它們；容量列入長訪談觀測，未來清理須先證明引用安全。

## 3. 採用路線及最小正式化

推薦將受測runtime整體轉為正式受版控模組，保留已驗語意與公開框架接點，另外接合設定／生命周期／HTTP mapper。既有analysis-agent不是應再次研究的替代方案；不從production import worktree，不複製成兩套可執行顧問。

### 3.1 程式與依賴

- 正式runtime放`apps/api/app/consultant/runtime/`，由採用清單機械轉換`analysis_agent` imports；顧問Skill資產隨正式套件保存。這個runtime含框架整合，不假稱所有模組都是framework-free domain。純JD內部type/service與transport mapper仍依既有契約策略分開。
- `apps/api`的唯一composition root組合此runtime、模型binding、官方Saver/Store、catalog、Memory publication與JD service。Web只消費正式API，無研究資料夾／主checkout絕對路徑。
- 採用隔離已驗Python3.12與精確依賴；既有API必需的設定／migration／測試依賴另作依賴差異核對，不用一次無關升級解相依。
- Node原生編輯模組轉為正式`packages/jd-editor-native`，只收固定入口的JSON，無DB／原文／Memory／任意shell能力。JD defs納入`packages/job-analysis-contract`既有SSOT/codegen；隔離contract package退出production引用，不手改生成物。
- 正式Web沿既有Next/React工作區，導入同一profile renderer。來源與改動都在文件畫面唯讀展開；舊pending、approved及XLSX下載入口退出。舊保存路由須不可再寫第二份稿，測試API而不只刪UI按鈕。

### 3.2 新資料初始化與版本

- 首次採用使用明示的新本機資料庫`caliburn_jd`，保留現有`caliburn`及`q019_`證據DB。不對它們執行drop/truncate／migration，沒有舊資料搬移。
- 由新的fresh-root migration `0019_jd_consultant_root`（`down_revision=None`）建立catalog/run/background-admission、Memory發布metadata及JD三表；0018移出active migration路線作歷史保存，不以執行0018再轉換舊資料的方式初始化。
- ORM正式表名為`consultant_document`、`consultant_run`、`consultant_background_admission`、`consultant_memory_head`、`consultant_memory_receipt`；JD三表沿0073。BackgroundRow保留既有document/target_reference/source_reference/status/error_code/recovery_count語意。Store namespace改固定`('caliburn-memory',document_id,...)`，只替換隔離前綴；正文／MemoryVersion／conversation refs語意保留。名稱變更屬fresh setup，不兼容雙讀。
- 官方Saver/Store tables由同一明示setup流程呼叫其正式`.setup()`管理，不能手寫一份framework DDL。api factory、PublicationStore與BackgroundDispatcher constructor的schema建立全部移至維護setup；日常啟動僅核對migration/profile與官方schema可用，不執行`create_all`或自動升级。
- 設定明示預期DB、host/port及profile；loopback guard保留並改成正式目標校驗，不能泛化成任意主機／任意dbname。profile不符停止寫入並提供維護訊息。
- 未來已有成品資料的格式演進：先完整備份，明示版本轉換、保真驗收及還原程序後才執行；v1研究fixture不列搬移項目，現在不預造通用migration引擎。

### 3.3 設定與日常生命週期

- 一套typed runtime設定由composition root注入；既有Luna/high、各角色及8192輸出上限／原生context配置沿CT50採用清單，舊OpenRouter／Opus／自動重試預設不混入。逾時及背景參數從實際受測設定核對，不補暗中fallback。
- 模型設定缺漏時仍提供明確App狀態；閱讀／人工保存與模型服務可用性分開，AI入口回typed unavailable。不得用固定假回答或別的模型冒充成功；採用實作測試驗證無key啟動不發外部請求。
- 正式API保持单worker／loopback，前景按文件admission。FastAPI lifespan先初始化本機資源，再啟動服務；關閉先停止接納、停止排程並join前景／背景／Node工作，最後關HTTP與DB clients。
- 日常啟動入口檢查PG、建置assets、設定與端口後開同一工作入口。stop只處理該啟動入口持有的程序，不能依端口任意kill其他程序；Windows背景程序Hidden。
- 自動重啟只對前景做保存效果對帳與顯示狀態，不默默重開付費前景回合；背景Memory仍依既有已收到來源／admission與受控恢復規則調度，完整catalog包含archived。API開機health check不是付費模型smoke。

## 4. 備份、恢復與診斷

采用PG16官方`pg_dump` custom archive／`pg_restore`，備份同一DB的catalog、完整Saver/Store、Memory publication及JD資料；不是只存JD JSON。維護命令接受明示輸出路徑，資料保留於本機；不做自動上傳或外部備份服務。

1. 正式更新／手動備份先暫停新工作，安全結束正在進行的工作並確認效果；保存記錄未閉合時明示狀態，不假稱所有回合已完成。
2. 建立完整DB archive及清單：app版本／依賴lock hash、migration head、JD profile、備份时间及archive checksum。金鑰不寫入清單／一般log；恢復使用本機設定。
3. 初次還原演練到獨立明示DB，用官方restore的錯誤停止／單交易選項；不對目前DB原地覆寫。不自動刪現有DB。
4. 驗catalog數量、封存狀態、確切JD/head/receipt、Memory head／內容、原始來源checkpoint回查、未閉合工作，以及background admission的queued/partial/blocked target/source/status/error/recovery_count；回覆遺失操作仍只查同回執，不重複新增，重啟不得重置恢復計數。
5. 確認演練通過才記「可恢復」。正式切換到還原DB需明示維護操作，維持原資料備份；不以服務啟動成功代稱內容已驗。

診斷只輸出操作／run身分、狀態、錯誤分類、延遲／usage及必要有界訊息；不默認記完整員工對話、JD或金鑰。測試trace另以合成資料保存。成本及延遲沿R6逐例量測，不用增強重試或自動換模型掩蓋故障。

## 5. 正式採用施工及退出門檻

| 單位 | 必須交付與驗證 |
|---|---|
| A1 採用manifest | 固定已通過核心的runtime/Skill/schema/native版本與逐檔hash、完整依賴差異；限定舊writers退役清單 |
| A2 ADR及契約 | G6前：本設計獨立審查、Memory/source successor与0073各自取代範圍、正式契約映射設計；G6後：正式SSOT生成及API/Web mapper實作測試 |
| A3 fresh storage | 明示新DB、root migration、官方setup、重跑setup／版本不合／DB未就緒負例；不碰舊資料 |
| A4 runtime採用 | 單composition、import邊界與取消／原文／Memory接點回歸；正式namespace及來源歷史可回查；無research imports |
| A5 Web與lifecycle | 一個JD工作面，原review/approved writers與下載入口退出；兩文件切換、更名／封存／恢復，終局receipt查回不受archive阻擋；archived既存背景批次仍由內部完整catalog枚舉並按原規則續行 |
| A6 operational | 無key本機讀寫、正常啟停／服務失敗提示、完整備份還原、更新profile核對；固定provider不發實際請求 |
| A7 closure | code/design/ADR/register/README/runbook同步，獨立review無阻擋；真provider及真人效果依P3/P6的已授權證據，不假報 |

G6輸入為已授權核心／P3證據、A1採用manifest及A2設計／取代範圍審查；G6之後才執行A2契約實作、A3–A6正式施工／驗證、A7 closure。不能要求先完成正式施工才接受ADR。本文候選A1–A7均未通過；正式API/Web、setup與備份未實作，未呼叫付費模型。核心Task1–6可按既有批准繼續。

2026-09-10 review修正：PDR-01封存／背景政策對齊R2；PDR-02拆G6前後；PDR-04補background admission及全部setup入口。同reviewer定點複核已將四项finding全部CLOSED，有限設計PASS，見[審查紀錄](evidence/2026-09-10-jd-product-baseline-review.md)。ADR0074仍Proposed；尚未實作／驗收正式接線。

## 6. 官方依據與效力

查閱2026-09-10。版本／授權依已鎖套件LICENSE與原研究盤點；LangGraph/LangChain OSS採用，不使用付費Agent Server或另增Redis。

- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[Stores](https://docs.langchain.com/oss/python/langgraph/stores)：公開契約區分thread checkpoints與application store；可按確切checkpoint取state。它不規定本案原話一定放Store，也不保證外部JD副作用已提交。舊durable-execution URL本日redirect到Persistence，引用以現行頁為準。
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)：共享資源以lifespan取得及釋放；本案single worker／join／scope是受測runtime的採用，不是framework自動產品能力。
- [PostgreSQL16 dump/restore](https://www.postgresql.org/docs/16/backup-dump.html)：單DBdump提供一致快照，restore須檢查錯誤；全體資料及還原演練是本案映射。
- OpenAI／Anthropic工具結果／context／副作用界線沿[現有官方稽核](2026-09-10-jd-responsibility-and-evidence-audit.md)與[context研究](2026-09-10-jd-context-change-and-source-research.md)。未公開vendor內部DB或Memory owner保持未知，不把本稿表名稱為大廠schema。


**2026-09-10只讀接合補核：**[A1/A2精確前置](evidence/jd-product-adoption-preparation/README.md)已核170個主／隔離正式產品檔，166 byte一致、4僅換行不同。上文「舊pending」是產品簡稱；實際為Store workspace對checkpoint approved派生review，不是checkpoint pending queue。正式退役須包含模型workspace writers、rebase／恢復與graph direct_edit／workspace_authority_commit，及HTTP/UI舊writers；原話／run／基礎責任逐項映射，不能整檔誤刪。這是既定退出範圍的具體化，不新增產品選擇或現在刪除。Task4接受版89項Git輸入僅预覽，Task5/6後須重建A1最終manifest，G6仍未通過。
