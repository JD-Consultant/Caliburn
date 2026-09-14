# Task 5 implementation／review handoff

狀態：**SOURCE FROZEN — 待 root 一次完整獨立 review**。施工與必要 affected 驗證已完成至下列範圍；本稿列出未直接觀測的條件，**不自宣 Task5 Spec PASS、Task6、自然模型、真人 IME 或成品通過**。

## 固定範圍及檔案

- Worktree `S:/caliburn/.worktrees/analysis-only-agent`；branch `codex/analysis-only-agent`；BASE `8eec072d51e97735b22c5f0df598b67101fe570b`；accepted Task4 tag `jd-editor-core-task4-20260910`。
- 精確 31 個 source 與 SHA256／bytes：[source-files.json](../docs/specs/evidence/jd-editor-task5/implementation/source-files.json)。另供機械處理：`scratch/task5-source-files.json`。
- Delivery 檔名／SHA256／bytes：`scratch/task5-delivery-files.json`。原始證據映射：[raw-files.json](../docs/specs/evidence/jd-editor-task5/implementation/raw-files.json)。所有本輪首敗、工具限制及修後 log 留存，未覆寫接受 Task4 證據。
- README 完整保留 root 提供 baseline（包含 prior11研究行）；封裝時以 `current.startswith(baseline)` 核對。Task5單獨patch為 `implementation/readme-task5-only.patch`；`tracked-source-with-prior-readme.diff` 的 README 包含原研究 dirty，**不可整份直接當 Task5 staging patch**。未 stage／commit／push／reset／cleanup；其餘 root-owned docs 不在 source list。
- root-owned pywin32 artifact／manual-recovery design review／bootstrap-handoff 各自保留於 `docs/specs/evidence/jd-editor-task5/`，本輪只新增 `implementation/`，未改其證據。完整設計採用由 root register／brief 處理。

## 最终實作

Windows `bootstrap()` 在 main thread 取得 private mutex、終止／觀測 exact old Job、建立不可重用的 fresh Job、設 kill-on-close 並驗實際 membership；`open_service` 要求真 bootstrap。Job/mutex handle 不傳子程序，保留至 API exit。pywin32312為既有官方 wheel 的 Windows-only direct dependency；uv.lock 保留官方312artifact/hash，未全機安裝。

Native owner 在 Popen 前保存 spawn責任，保留真正 handle／pipe／I/O workers，cleanup失敗／spawn未返回／thread未退出皆不 quiescent。BaseException 亦可找到原 handle。App保存前重核 native停止與取消；manual／read／selection／create的原 Python entry 在 shutdown 排空。selection等待移出全域鎖，同文件仍有admission reservation。HTTP read只接App shutdown獨立停止信號，AI stop 不永久禁止唯讀。

Manual Node前將唯一 operation/base/digest/origin/request_key 寫 root channel，不存candidate、不造HumanMessage/run。收尾按原 descriptor查原 receipt；停止證明先於 PG head FOR UPDATE，receipt 是其後獨立statement；absence才走原身分failure-only closure。JD close核對factory session／原input/message/call/args，遍歷全部pendingbindings，含已有unconfirmed ToolMessage與child-terminal分支；只補缺的原結果並傳遞已確認manifest。Memory policy不改。

人工恢復 App-only GET/POST 真Pydantic → export → generatedTS → API/session/UI。GET純投影，POST原key明示一次；available/unknown/no_pending皆由同server owner投影write_blocked/can_recover；clear失敗保留真terminal及另次清理出口。晚A不清B。Web重開不自動save；exactcache+no_pending另次明示完整原key/base/value，unknown不作未admit證據；成功只清匹配cache，failure/dirty保留；mutation使舊GET失效，gate讀取失敗保持blocked。三模型工具／JD core schema未改。

## 實際驗證與次數（重疊不可相加）

| Log（均在 implementation/raw） | 實際結果與效力 |
|---|---|
| task5-final-jd.log | 規定Task5集合36 PASS，74.55s；含admission/close/PG/transport/native/Windows/newprocess。這輪之後的新增有限case另列，不假稱同一輪全含。 |
| task5-final-web.log | 3 files、23 PASS；session/submissionCache/JdWorkspace。session mock是行為驗證，不是真browser人工操作。 |
| task5-final-types.log / task5-final-lint.log | tsc與affected ESLint無錯誤輸出。 |
| task5-final-codegen.log | actual DTO及SSOT生成一致。core JSON schema/generated native契約無diff。 |
| task5-final-memory-captured.log | 指定API／conversation／PGconversation／publication／PGpublication原63case：62 PASS、1 FAIL。失敗是Task5把JD after_model判據誤套Memory，已修回。 |
| task5-memory-fix-green.log | 修後只跑受影響原conversation+PGconversation組43 PASS，10.58s；與原63重疊，不能計成105。其餘原組沒有後續source影響。 |
| task5-last-affected.log | 最後terminalavailable/activeowner、no-store與JD限定判據改後，transport+JDclose 8 PASS，25.39s。 |
| task5-nl10-nl13.log | 額外3 PASS：A manual committed+B selection Node outstanding整Appcrash；create before/afterCOMMIT兩分支再同key重入。 |
| task5-nl11-nl12.log | 額外6 PASS：bootstrap assign前/後與oldJob termination後自身crash；PG headmissing/locktimeout/實際斷開自己backend三負例。 |
| task5-nl12-prelock.log | 額外1 PASS：舊writer真正PgSleep前置statement阻塞（尚未送headlock/後續mutation）時App自退出，新bootstrap後known-none原failure。 |
| task5-process-first.log | 四個初次真managedApp/PG/Saver程序案例4 PASS；native outstanding、nativecomplete前publish、COMMIT前、COMMIT後回覆遺失。新程序0native/0provider/no fakeinput/run。 |

共用命令 cwd `experiments/analysis-agent`：isolated uv Python3.12，`PYTHONUTF8=1`、本地 `.uv-cache`、scoped Node22.23.2 PATH、`PYTHONPATH=src`，每個測試根使用獨立 `Q019_LIFECYCLE_INSTALLATION=task5-<purpose>-<UUID>`。

```text
uv run python tests/task5_acceptance_runner.py tests/test_jd_admission.py tests/test_jd_close_reconcile.py tests/test_jd_postgres_recovery.py tests/test_jd_manual_recovery.py tests/test_jd_native_lifecycle.py tests/test_windows_lifecycle.py tests/test_jd_process_lifecycle.py -q --basetemp <unique task scratch>
uv run python tests/task5_memory_runner.py tests/test_api.py tests/test_conversation_lifecycle.py tests/test_postgres_conversation_lifecycle.py tests/test_publication.py tests/test_postgres_publication.py -q --basetemp <unique task scratch>
uv run python tests/task5_memory_runner.py tests/test_conversation_lifecycle.py tests/test_postgres_conversation_lifecycle.py -q --basetemp <unique task scratch>
```

JD PG僅既有 `q019_jd_app_20260910`、127.0.0.1:5432。Memory僅原 `caliburn-q019-postgres` 精確containerID／127.0.0.1:55433／q019_agent_test；wrapper在記憶體從已核容器取DB credentials，無DSN/secret寫檔或列印，未讀真.env/modelkey。沒有drop/reset；PG fixture保存隨機測試documents snapshots，Memory沿原fixture只清自己的隨機測試紀錄。所有provider是offline MockTransport，0付費。

## RED／診斷索引

首功能RED依序：native-red／native-block-red、windows-red、bootstrap-entry-red、admission-red3、manual-race-red、manual-pg-red、pg-red2、close-red／close-paired-red2、observer-red、transport-red、web-recovery-red2、native-io-red、selection-red。每個對應green或最後集合有實際結果。未為安心重跑接受Task4全部基底。

環境／fixture首敗分開保留：admission-red／red2為pytest私有暫存ACL；Windows green1為受限token私有mutex DACL；codegen與Web recovery-red為Node spawn EPERM。依tool機制正常user token執行成功，沒有放寬產品ACL。Windows faults1–3反映原fixture對external observerhandle/nested支持的假設錯，faults4及後續kernelcase保留真正觀測。selection-green初次錯在測試對空initial選range，改成先保存實際非空base後green2；drain-first read錯在pure-current read根本不進native，改用真selection-ref read後final36通過。Memory首次wrapper隱藏子程序未轉送stdout（exit0但無可核數字）不當PASS，改capture後才保存63case首FAIL及43修後PASS。

Root首次checkpoint中性default：`task5-admission-green1.log`保留rawdict首次不相等；`task5-manual-pg-green.log`保存actual PG before `{}`、after僅messages=[]／closed_turns={}中性具現加manualdescriptor、next=[]、provider=0。已存在closedturn與下一則真input在admission兩case驗證；沒有把任意欄位差異一概忽略。

## NL01–13證據及未直接觀測部分

| NL | 本輪實際證據／限制 |
|---|---|
| 01 | Rootdescriptor beforeNode、同stop Event、native後取消不發布candidate在admission。JD after_model限原latest及已知publicnodes，tools不當未開始。前景before-model既有流程保留；不把Task3forwarding單獨算完整kernel證據。 |
| 02–03 | 真Popen reaping回false後owner仍保存同process、再呼叫拒絕spawn；另次cleanup同handle；transport retained-token一次attempt/競爭409/unknown後另次closure。 |
| 04 | spawn尚未返回、thread constructor KeyboardInterrupt、process退出但I/O仍live均有具名case。stdout overflow沿既有引擎處理，本輪未新增獨立overflow故障case。 |
| 05–06 | 真PG+actualgraph jd_edit提交後missing或unconfirmedToolMessage、childterminal三參數case；原head不回退、原messages逐筆model_dump不改、manifest保留；stop無額外model/native。 |
| 07 | manual/read-selection/submit-selection/create四entry close實際同Event等unwind；AI純訪談/對話原組、JDclose集合。Windows新程序由真bootstrap先於DB/client/native。 |
| 08 | 真Node進程以CREATE_SUSPENDED停在入口，產品Job在API自exit時涵蓋子程序；**不稱JS transform執行中**。另有正常native完成/publish前、COMMIT前/後四實際時序。固定bridge為同步entry.run，沒有內部barrier；未改bridge或另建instrumentation engine以湊phase。 |
| 09 | PG負例三支、receipt/停止不確定保持unknown；既有owner/proof不因return/absence放行。 |
| 10 | 同一真managedApp A manual commit、B selection Node+I/O outstanding，自crash後A原terminal、B原revision不變、新Appgate正常、0重跑native/model。**A為manual非AI jd_edit，不能與NL05/06拼成已實測exact AI edit A+selection B crash**。 |
| 11 | 真mutex competitor、APIcrash childmembership、abandoned-owning-thread、assign前/後crash、newbootstrap terminateold後crash、handle不繼承。outerHANDLE UI限制本機實際nested成功；restricted Assign access用真Win32缺ASSIGN權限handle得到access-denied、beforeAppwork。**未實測nested-incompatible配置**。 |
| 12 | 真headlock-held commit/abort兩支；headmissing/locktimeout/自己backend實際terminated；prelock真正PgSleep舊writer後crash觀測later_mutations_sent=0；新SQL barrier原failure-only。 |
| 13 | unmanaged entry before resources、externalJobhandle拖住名稱時failclosed、release observer自身handle後另次explicitstartup；create舊txnCOMMIT/rollback後同key reentry各一次，唯一catalog/initial/head且無AIrun。 |

Windows parent harness只觸發fixture自crash／觀察，不代產品kill child取得proof。abandoned case parent保留原Popen觀測handle導致name仍存在，產品先拒；parent僅釋放已退出process觀測handle後另次startup。這個首拒raw不刪。一般crash新bootstrap讀到exactobject absent；不冒稱每次都走ActiveProcesses=0。測試終局finally善後與產品停止proof分開。

## MT01–14與實際HTTP

actual FastAPI TestClient/真PG/root測了GET純觀察及no-store、key-onlyfailureclosure、latekey不改current、active正常publisher不搶權、terminalclearfail仍available+blocked、terminalactive仍回原available且不可recover、competingrecovery一次attempt、archive結果優先、schemaextra422、DB503不當absence。五個transport測試同最後8集合。Web session mock測cachelost獨立恢復、load零POST、exactcache/no_pending明示完整原submission、unmount/lateA不覆B/newdirty、舊GET與freshgate failure不解鎖；actual DTO三分支必填bool生成驗證通過。

真8091已啟：hidden launcher PID15740 → worker12632；key `jd-editor-offline-20260910`，Node22.23.2，actualPG/Saver/Store及fixture固定provider。`task5-http-observed.json`為GET200/no_pending/write_blocked=false/can_recover=false；`task5-browser-server.json`保存bootstrap diagnostics。**此HTTP server啟動時source早於最後no-store及active-terminal小修；最後兩修有TestClient驗證，尚未重启HTTP載入**。真browser cachelost/明示按鈕交互本輪未跑；JdWorkspace元件與session測試不稱headed真人通過。

舊Task4未受管API切換的停止由root補授權／identity證據並經同auto-review批准，只停worker，整鏈自然退出：引用root-owned `bootstrap-handoff/`，不當產品NL自动停止proof。首次廣鏈終止被auto-review拒絕，subagent沒有替代方式繞過；最新觀察 `task5-legacy-observed.json`留存。

Task6沿README已更新bootstrap入口：設定同安裝穩定key及`Q019_TEST_EVIDENCE_PREFIX=task6`，scoped Node22.23.2後啟 `tests/jd_browser_server.py`；不使用rootmodel.env或真provider。**後端reload關閉，後續Task6/review測試須按精確own PID／commandline再受控重啟，不能按port殺**。無run/manualdescriptor但retainedread owner的狀態維持serverblocked；現有恢復出口是受控整API重開，沒有另造通用cancel route。

## 待review判定的限度

1. NL08未直接觀測JS transform中、NL10目前為manualA而非exactAIeditA、NL11本機未觸發nested-incompatible；如上精確分列，沒有將方法名或mock推成完整phase通過。root收束裁定不再加近似NL10 fixture：跨文件App/Job責任由manualA+selectionB、AI binding責任由NL05/06分別提供證據，exact組合仍未直接觀測；獨立review可提出具體缺口，沒有改写原設計。
2. MT有actualroute/PG及session/component，但cachelost真人browser點擊未觀測，0自然模型／0真人IME／0production切換。
3. Task5來源與raw證據交review；未將36+43+23+各focused重複加總成不實案例數。repo authority/current register由root負責採用，不以本報告改ADR0074 Proposed或production0060。
