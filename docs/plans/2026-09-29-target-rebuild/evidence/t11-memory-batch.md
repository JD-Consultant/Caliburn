# T11：Memory 意圖、背景領取、B1/B2 交接與共同發布

- 日期：2026-09-30。
- 狀態：**最小 owner／parent 已實作、局部真 PG 驗證；不是 T11 全部完成或真模型品質驗收**。主線負責 bootstrap、A registry、完成提示接線；James 負責兩個角色。
- 責任規格：[Memory 生命週期](../../../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[共用執行 §7](../../../implementation/agent-execution.md#7-memory-背景工作)、[Memory 保存](../../../implementation/memory-storage.md)、[程式組織](../../../implementation/code-organization.md)、[程式撰寫](../../../implementation/coding-standard.md)。本頁只記實作、證據及接線，不另立產品規格。

## 1. 主線可立即使用的 API

**沒有新 migration、queue／broker 或第二套 receipt。A schema／handler／registry 未由本切片修改。**

```python
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.workflows.memory_supervisor import MemorySupervisor

memory_intents = MemoryConsolidationWorkflow(database.sessions)
memory_parent = MemoryBatchWorkflow(
    database.sessions,
    run_role=MemoryRoleDispatch(b1_runner, b2_runner),
)
memory_background = MemorySupervisor(
    database.sessions,
    run=memory_parent.run_supervised,
    check_leadership=leader_lock.check,
)
```

- A 工具 `request_memory_consolidation` 的模型參數為 `{}`；handler 呼叫 `await memory_intents.request(writer, command_id)`。兩個參數皆由 Runtime 提供，回傳只有模型可見的 `message`。
- A completion 的 COMMIT 成功後可呼叫 `memory_background.notify()`。這是低延遲 hint，不是持久保存：每秒掃描 completed A＋正式原員工輸入，漏掉 hint 或重啟不丟意圖。**無需把新 Memory 寫入放進 A completion 交易**；其完成 docstring 應由主線更新。
- 已取得 App leader 後 `await memory_background.start()`。關閉先 `await memory_background.close()`，才關閉 A supervisor／leader、checkpointer、client 及 DB。
- 必須包含**異常收尾**：ConsultantSupervisor 已提供 `before_leader_release=memory_background.close`，主線須注入此 callback，確保異常路徑也先停止 Memory tasks，不能只有正常 lifespan 按順序關閉（修正與驗證見 §8）。MemorySupervisor 自己不取得或釋放該鎖。
- `await memory_intents.failure_reason(job_file_id)` 回安全的已知終態失敗分類或 `None`，供下一個合法 A 資料交界提示；不是把 exception 原文送給模型。
- `release_block(failed_scope, condition_change_id=...)` 僅供系統在確認外部條件已變更後使用，不對 UI／模型開放，不因新通知自動解鎖。

James 的兩個 runner 建構參數為 `(sessions, checkpointer, client, settings)`。dispatch 只接其公開 `.run(...)`；主線不用複製角色分析或原生 context 邏輯。兩個角色使用自己的 context，沿相同 batch budget，不因交接歸零。

## 2. 已落地的不變量

1. A 工具只記原 Turn 的意圖及 employee source；cancelled／failed／尚未完成的 A 沒有 background 資格。正式序號從已提交的正式訪談 owner 讀，F 是**員工輸入**，不是後面的顧問答覆。
2. 領取在檔案鎖下協調 execution owner 與 candidate owner；已開始批次保留原 K/F／候選，不因後來訪談更新。多個已完成通知由最大有效 employee frontier 合併，既有批次結束後才處理下一批。
3. parent 順序執行 B1→B2；每次交接保存角色完成位置、必要結果及下一階段。B2 發現 gap 才回 B1；B1 收到限定情境問題，不收到 B2 理解正文／私有 trace。兩者保有自己上次分析結果的 native checkpoint 參照。
4. B2 收到本批開始基準→本次固定 B1 交接的情境差異，包括未被任何理解引用的新增情境、刪除、改名、正文／描述／訪談引用變更。差異由保留 positions 投影，不另存 diff。
5. 最後一次 B2 完成後，candidate publication、Memory head／coverage、兩角色 context 採用及 execution completion 用**同一短交易**提交。等待模型／工具不持有此交易。重入讀原 snapshot，不另生成新發布。
6. 原生模型／工具 Step 的恢復及有限外送重試沿既有 runner／ModelRequestExecutor；parent 不再包 provider retry。已知預算／容量／模型終態失敗回退候選，保留已發布 Memory；阻塞紀錄阻止反覆通知重開額度。
7. 背景關閉造成的 coroutine cancellation **不是**使用者取消 Memory，也不 discard。未知保存／提交結果保留原 exception／handoff、停止盲目重送；新 lifespan 可重查同一批次。已採用 compaction 的歷史 owner 不被本切片清除。

## 3. 檔案與責任

| 路徑（`apps/api/src/caliburn/`） | 責任 |
|---|---|
| `workflows/memory_consolidation.py` | 意圖資格、領取、已知最終失敗、系統解鎖；無模型 I/O |
| `workflows/memory_batch.py` | 同批 B1/B2 順序、必要回交、共同發布交易 |
| `workflows/memory_stage_changes.py` | 固定情境交接差異投影；不另存內容 |
| `workflows/memory_supervisor.py` | lifespan 有界本機 tasks、持久發現、原 task 退出；借入 leader |
| `agents/memory_analysis/dispatch.py` | 兩個公開 role API 的組裝轉接 |
| `features/work_memory/consolidation_requests.py` | 重用既有 `memory_operations` 記錄意圖／交接／失敗，不新增表 |
| `features/work_memory/batch_models.py` | 小型工作身分、來源及回交上限錯誤型別 |
| `features/executions/memory_discovery.py` | execution owner 對 active Memory 的公開查詢 |
| `features/executions/history.py`（窄修改） | 允許同 execution／role 的 native stage context 作完成參照；A 的 root 限制不變 |

最後一項只驗 execution／role namespace；parent 另核**確切目前 stage**。不是任意 foreign checkpoint 都可採用。並行主線對此檔的其他改動沒有覆寫。

## 4. 驗證與已知限制

實際使用 `.venv-target`、每測例隔離 schema 的 PostgreSQL（localhost:55439）；沒有付費模型請求。

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
./.venv-target/Scripts/python.exe -m pytest tests/integration/test_memory_batch_orchestration.py tests/integration/test_memory_supervisor.py tests/integration/test_memory_parent_roles.py tests/integration/test_role_context_history.py tests/integration/test_memory_candidates.py tests/integration/test_memory_source_windows.py tests/unit/test_import_boundaries.py -q --tb=short -p no:cacheprovider
```

第一次回歸結果 **54 passed、1 failed**。唯一失敗為現行 AST 邊界將 B1/B2 引用 `agents.memory_analysis` 判作跨角色；已回報主線／James，沒有停用測試。dispatch 依主線要求從 workflows 移至角色組裝層。

dispatch 移動後重跑三個本切片整合檔：**8 passed**。接著 James 將共用結果／runner 移至 `workflows/memory_analysis`；本切片 parent 改引用該唯一契約，dispatch 對兩個角色只依賴窄公開 Protocol，由 bootstrap 注入實例，不互相 import 私有角色模組。2026-09-30 10:52 Taipei 重跑上列完整命令：**55 passed in 22.64s**，包含 import-boundary；更新的兩個 source mypy、Ruff 均通過。沒有停用／放寬 AST 檢查。

- 自有 parent／supervisor 測例：未完成／取消意圖不啟動、F 不含 AI 答覆、通知合併、舊批次 frontier 固定、已知最終失敗不擋 A、系統解除條件後不跳過未發布訪談、B1 交接後中斷重進 B2、按需 gap 續原候選、shutdown 同批恢復、不用 polling 重送未知結果。
- `test_memory_parent_roles.py` 使用**真正兩個 role runner、原生 PostgreSQL checkpointer、真業務資料庫、合成 SDK transport**；驗 B1 建情境、B2 建理解、最終提交前故障無半版發布、重入沿用 B2 已保存 final（外送數不增加）、第二批沿角色歷史完成並保留第一版快照正文。
- 九個自有／窄修改 source 的 mypy 通過；自有 source＋三個 tests 的 Ruff 通過。`git diff --check` 通過（僅 CRLF 提示）。初期缺模組 Red 已觀測；新整合測例第一次因測試誤用候選 read 入口而失敗，改用正式 snapshot query 後通過，不把測試錯誤冒充產品缺陷。

**尚未完成／不得宣稱：**

- 沒有驗主線 bootstrap、A registry 或端到端真模型 Memory 品質；需主線合併接線及 James role 驗收。
- 目前情境差異是 changed hunks 直接提供 B2；大批次長文的按需差異展開、token 容量及效能仍需專項驗收，不以小合成測例證明可支援任意長訪談。
- 未知 COMMIT／已遺失程序原件的自動核對策略不擴充；既有外送與原件補存的 bounded retry 可用，但不可說所有崩潰都自動恢复。不能用重啟或通知無限重設費用。
- 角色 final 格式不符／refusal 已由後續 §6 補 typed error 與持久失敗分類；其他未知保存／程式錯誤仍不冒充同一終態。
- `max_feedback_rounds=2`、最多兩個並行檔案、1 秒發現為可注入的工程初值；不是新產品不可變決策。
- 原始例外／held response 只留程序內 recovery handoff，禁止原文輸出到 UI、log 或模型。只有已知終態分類持久化。

## 5. 研究依據與取捨

- [Python 3.14 asyncio tasks](https://docs.python.org/3/library/asyncio-task.html)：持有 task 強參照、觀察錯誤、取消傳遞與關閉收尾。本案將 tasks 綁到 lifespan，持久資格仍由既有 owner 管；不是把 task 當耐久 queue。
- [Azure Retry pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry)：有限、分類且單一責任的重試，避免疊層重試。沿已驗 ModelRequestExecutor，不給 parent／supervisor 第二套 provider retry。
- 具體 DB 領取及發布沿 repository 已有短交易、scope fence、candidate／history／operation owner；沒有新增框架或重造下層機制。本頁不將 Caliburn 的具體欄位／2 次回交初值稱作業界共識。

## 6. 模型 final 不合法的 typed 終態失敗（2026-09-30）

主線分派的修正已落地；只改 `workflows/memory_analysis/results.py`、`runner.py`、`workflows/memory_batch.py`，未改 A／bootstrap。

- `AnalysisOutcomeError(ValueError)` 帶有限安全 `reason_code`：`analysis_outcome_malformed`、`analysis_outcome_refused`、`analysis_outcome_not_allowed`。
- parser 只轉譯自身 Pydantic `ValidationError`；refusal 的具體分支直接拋 typed error。其他 `ValueError` 不被 parent catch 成模型失敗。繼承 ValueError 保留原 parser 例外大類，並不放寬捕捉範圍。
- parent 接 typed error，沿原 failure owner 的短交易 discard 本批候選、execution failed、持久分類，正式 head／coverage 不前進。不新增重试、不更改既有发布。
- 模型原文仍由原生 saver 保存；公開錯誤／持久 reason 不攜帶原輸出、Pydantic input value 或 refusal 正文。標準 traceback 的原始 validation chain 被抑制。

先跑兩個真实 role＋真 PG 反例，觀測 malformed 仍拋未處理 ValidationError、refusal 仍拋 ValueError（**2 failed**）；實作後 **2 passed**。補其他 ValueError 不得誤判的反例、parser 機密值不出現在公開 traceback、B1 不得回傳 B2 rework outcome。

```powershell
./.venv-target/Scripts/python.exe -m pytest tests/unit/test_memory_analysis_outcomes.py tests/integration/test_memory_outcome_failure.py tests/integration/test_memory_parent_roles.py tests/integration/test_memory_batch_orchestration.py tests/integration/test_memory_analysis_runners.py tests/unit/test_memory_analysis_tools.py -q --tb=short -p no:cacheprovider
```

結果 **18 passed in 11.39s**；三個修改 source mypy、修改 source／新增 tests Ruff 通過。包含 import 檢查的前次回歸另發現並行 `transport/http/jd_undo.py` 直接引用 SQLAlchemy 的違規，已回報其 owner；未修改／略去該失敗後冒稱全庫綠燈。

## 7. P1：A monitor 異常退出先釋放共享 leader（修正前診斷）

正常 lifespan LIFO 不涵蓋 A monitor 自己的 `finally`。當前路徑是 `ConsultantSupervisor._monitor_work` 停止自己的 A tasks 後 `lock.close()`；Memory monitor 要等下次掃描才發現失鎖並停止。

有界診斷檔 `.research-tmp/test_t11_leader_release_probe.py`（**不屬於 CI 回歸**）用隔離 test schema、真 PG／真 PostgresProcessLock，注入 A discovery 失敗並以 events 控制順序，確認：

```text
CONFIRMED: replacement leader acquired; old Memory task live and writer active
```

診斷命令：

```powershell
./.venv-target/Scripts/python.exe -m pytest ../../.research-tmp/test_t11_leader_release_probe.py -p tests.integration.conftest -q -s --tb=short -p no:cacheprovider
```

結果 1 passed（表示**成功重現缺口**，不是恢復驗收）；由 repo 外 pytest root 執行有 1 個 postgres marker 未註冊警告，沒有忽略失敗。

風險是新 leader 已能接管，而舊 Memory coroutine 尚未停止；業務 writer 在接管後雖會 fenced，但不等於原生 Graph checkpoint 寫入也有同一個 fence。不得用縮短 polling 取代「舊任務全退出才釋放本機鎖」。

當時提出的最小修法（後續主線依 Goal 分派及實作見 §8）：

1. A supervisor 注入單一具名 `before_leader_release: Callable[[], Awaitable[None]]`，bootstrap 傳 `memory_supervisor.close`；不是新 supervisor 框架。
2. 啟動失敗、monitor finally、顯式 close 的所有釋鎖路徑，先 await 依赖 Memory 收尾，再 close leader；正常重複 close 沿既有冪等 shutdown task。
3. callback 不回呼 A.close，避免互等；未確認 Memory 停止时不在 finally 強制釋放本機 fence。DB session 真失效时，本機 OS fence 仍須保留到收尾。
4. 回歸应证明：Memory cleanup 被 event 阻住期间，replacement lock 仍拒絕取得；放行 cleanup 後才可取得。A discovery 故障、正常 shutdown 兩條都驗，不以 API 200 代替。

## 8. 共享 leader 的依賴收尾 callback（已修正，局部驗證）

主線隨後明確分派修改 `workflows/consultant_supervisor.py`；本輪只修改該 source、新增 `tests/integration/test_consultant_leader_release.py` 及本 evidence。bootstrap 由主線同步接線，本切片未編輯；未新增 lock／registry／外部依賴。

```python
ConsultantSupervisor(
    sessions=database.sessions,
    run=consultant_runner.run,
    process_lock=leader_lock,
    before_leader_release=memory_supervisor.close,
)
```

`before_leader_release` 為可省略的 `Callable[[], Awaitable[None]]`，預設不新增依賴。Memory object 須先建構、啟動順序仍 A→Memory；正常 lifespan 關閉先 Memory→A。callback 不可回呼 A.close，避免循環等待。

- 正常 close、已取得 leader 後啟動掃描失敗、monitor 掃描失敗，均沿同一個有強參照且 shield 的一次性 release task：先等待 A runners 退出，再 await callback，最後釋放原 PG／本機 fence。
- callback 失敗時不進入 `lock.close()`；原錯誤保留，後續 close 重新拋出同一失敗，不重跑 callback、不另外造重試。啟動尚未取得 leader 就失敗，沒有需要收尾的借用者，仍只清理原 acquire 資源。
- monitor 異常收尾與顯式 close 共享此 task，不會彼此取消或重複釋鎖；monitor 保留原 scan failure，close 可取得 cleanup failure。這是程序生命週期處理，不是 Memory 產品取消／候選回退。
- 清理持續卡住時保留 fence、不承諾強制逾時後仍安全放行；程序退出後由 OS 釋放資源。沒有把「超時」當成所有借用者已停止。

TDD：新增六個真 PG 測例，先觀測缺少 constructor 參數造成 **6 failed**；實作後與既有 A／Memory supervisor 回歸 **13 passed**。三種退出路徑各驗：cleanup 未完成時 contender 不可取得 leader；放行後才可取得；cleanup 失敗與重複 close 仍持有 fence，且 callback 只執行一次。底層原缺口另已有 §7 的行為重現，不把 constructor Red 當作競爭風險本身的證據。

接主線新版 bootstrap 後執行：

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
./.venv-target/Scripts/python.exe -m pytest tests/integration/test_consultant_leader_release.py tests/integration/test_consultant_supervisor.py tests/integration/test_memory_supervisor.py tests/integration/test_consultant_memory_http_journey.py tests/integration/test_consultant_http_execution.py tests/integration/test_consultant_http_controls.py tests/unit/test_import_boundaries.py -q --tb=short -p no:cacheprovider
./.venv-target/Scripts/python.exe -m ruff check src/caliburn/workflows/consultant_supervisor.py tests/integration/test_consultant_leader_release.py
./.venv-target/Scripts/python.exe -m ruff format --check src/caliburn/workflows/consultant_supervisor.py tests/integration/test_consultant_leader_release.py
./.venv-target/Scripts/python.exe -m mypy src/caliburn/workflows/consultant_supervisor.py
```

結果 **41 passed in 17.34s**（含 HTTP A→B1/B2→publish→下一輪接線與 import-boundary）、Ruff／format／mypy 通過；`git diff --check` 無 whitespace error，既有工作區有 CRLF 提示。未跑全庫、未付費呼叫模型、未重啟主線 App、未 commit。主線若較早已載入舊 constructor，其測試中的 `unexpected keyword argument` 不能當新版結果，需重新啟動測試程序；本輪不宣稱主線另一次全庫 session 已完成。

## 任務完成對照（2026-09-30 恢復後）

沿[任務表 T11 的 Red 與完成條件](../tasks.md#t11-背景調度交接與共同發布)逐條對照既有測試。路徑相對 `apps/api/tests/integration`。

| T11 Red | 代表測例（真 PG） |
|---|---|
| A 完成後 crash 漏通知 | `test_memory_supervisor.py::test_shutdown_preserves_active_batch_and_restart_resumes_same_scope`、`test_memory_batch_orchestration.py::test_intent_requires_success_and_frontier_is_employee_not_reply` |
| 在途批次擴大 F | `test_memory_batch_orchestration.py::test_parent_publishes_once_and_coalesces_next_frontier`、`test_memory_candidates.py::test_batch_reentry_keeps_original_source_boundary` |
| B2 gap 後回到初始工作稿 | `test_memory_batch_orchestration.py::test_b2_gap_roundtrip_keeps_its_existing_understanding`、`test_memory_candidates.py::test_restore_invalidates_late_branch_and_preserves_prior_candidate` |
| 發布確認遺失重發新版 | `test_memory_candidates.py::test_publish_is_one_fixed_graph_and_replay_returns_original_snapshot`、`test_replay_retains_original_identity_after_rename_and_title_reuse`、`test_memory_parent_roles.py::test_actual_roles_publish_atomically_and_continue_next_batch` |
| 失敗後跳過未發布區間 | `test_memory_batch_orchestration.py::test_final_failure_blocks_repeated_notifications_not_consultant`、`test_memory_outcome_failure.py::test_invalid_b2_final_is_durable_failure_without_publish_or_retry`；系統解除後從已發布涵蓋處續處理、不跳號（本頁 §4 自有測例） |
| quota 未變仍無限重跑 | `test_memory_supervisor.py::test_unknown_runner_error_is_not_poll_retry`、上列最終失敗阻塞案 |

| T11 完成條件 | 對照 |
|---|---|
| V10–V15／E10／E13 | 上表；`test_memory_batch_orchestration.py::test_reentry_after_b1_handoff_skips_b1_and_preserves_work`（E10）；E13 的重啟自動找回、同檔唯一在途、舊批上界固定：supervisor／orchestration 各案 |
| B 讀寫同一候選、A 只讀已發布 | `test_memory_candidates.py::test_candidate_binding_tracks_new_situation_but_old_snapshot_never_changes`、`test_memory_read_workflow.py::test_navigation_follows_candidate_identity_but_consultant_stays_on_published_snapshot` |
| 系統重啟承接、最終失敗 A 可用原話工具繼續 | `test_memory_supervisor.py`、`test_consultant_context_binding.py::test_unresolved_memory_failure_is_reference_data_not_a_model_instruction`；真模型下 A 在背景整理失敗批次後仍完成同一旅程（[T17](t17-course-administrator-journey.md)） |

**結論：**T11 的背景調度、交接與共同發布在其範圍內成立，勾選。

**已知限制（如實記，不擅自設計新機制）：**`MemoryConsolidationWorkflow.release_block` 只在測試中被呼叫，**沒有 production 呼叫者**：背景整理一旦最終失敗，該檔案之後不再自動整理，直到有人呼叫這個系統掛鉤。規格把「怎麼偵測阻塞解除」明列為待細設（[產品概念](../../../product-concept.md)：不開放手動重跑、不無限自動重試）。實務影響有界：A 仍可用固定的已發布 Memory、完整近期原話與 `read_interview` 繼續（超過容量時走 [T08 §7](t08-consultant-turn.md#7-近期訪談預載超量的有界縮減2026-09-30-恢復後) 的縮減）；但單次模型失敗就永久停止整理，對很長的訪談偏嚴格。建議（待 Owner 確認，未實作）：後續完成的 A Turn 累積足夠新訪談（例如數輪）後，以一次新批次自然嘗試，失敗就再阻塞——這是以新資料為條件的有界重試，不是通知重設額度。
