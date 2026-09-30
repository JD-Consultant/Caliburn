# T13 已完成 JD 修改的條件撤回

- 日期：2026-09-30；範圍：JD owner／workflow／HTTP 與真 PostgreSQL。UI、bootstrap 接線由主線承接；不據此勾選全部 T13。
- 依據：[T13](../tasks.md#t13-正式-pdf-與條件撤回)、[V23](../../../architecture/verification.md)、[完成後撤回](../../../architecture/delivery-and-operations.md#1-使用者看到的主要流程)、[介面交付](../../../implementation/interface-and-delivery.md)。
- 共享 `target-rebuild` 工作樹，起點 HEAD `acc06ca1`；保留其他代理的 dirty。沒有模型外送、讀取 `.env`、commit 或修改 Demo DB。

## 可用介面與整合

```python
from caliburn.transport.http import jd_undo
from caliburn.workflows.jd_undo import JdUndoWorkflow

app.state.jd_undo_workflow = JdUndoWorkflow(database.sessions)
app.include_router(jd_undo.router)
# await workflow.undo(job_file_id, execution_id) -> JdProfileRevision
```

`POST /api/job-files/{job_file_id}/consultant-turns/{execution_id}/undo-jd`，不接受 body／query／舊修訂參數；200 沿既有 JSON Schema 生成的 `JdProfileView`。這是原撤回結果的固定修訂，不保證仍為最新 head；UI 成功或重送確認後應重新 GET 目前 profile／work，不把舊 response 強寫成最新稿。

| 回應 | 效果 |
|---|---|
| 404 `consultant_turn_not_found` | 檔案不存在或 Turn 不在該檔案／角色 scope |
| 409 `jd_undo_unavailable` | 非 completed，或不存在原 adopted candidate |
| 409 `jd_undo_conflict` | 目前正式 JD 已離開原輪採用修訂，不覆蓋 |
| 409 `consultant_turn_active` | 同檔案有 active／paused A，不接受新撤回 |
| 409 `jd_command_conflict` | 原操作身分已被不同意圖使用 |
| 422 `unexpected_undo_arguments` | 偷帶任意 body／query |
| 503 `jd_undo_unconfirmed` | DB 操作／commit 確認失敗；沿同一 Turn 路徑重試確認，不改基準 |
| 503 `database_not_configured` | 尚未注入 workflow |

新增 [0018 migration](../../../../apps/api/src/caliburn/migrations/versions/0018_jd_completed_undo.py) **只擴充**既有 `jd_operations.kind` CHECK，沒有新增資料表、改正文、刪資料或自動 migration。既有 App namespace 須由主線明示升到 head；本切片僅在 fresh `_test` schema 執行。

共用 ORM `features/job_description/persistence.py` 的同名 kind CHECK 需同步加入 `undo_completed_turn`。該檔由其他代理修改，本切片未碰；已通知主線接線時同步。正式 DDL 已由 0018 驗證。

## 規則與重用

新 [undo_service.py](../../../../apps/api/src/caliburn/features/job_description/undo_service.py) 沿原 `jd_candidates` 取輪前／採用修訂，沿固定 revision／selection／source 與 `revision_editing.record_edit` 保存一個原操作；沒有第二套 undo ledger、snapshot 或 receipt。

- workflow 在同一短交易取得既有 job-file row lock，確認 scoped consultant Turn completed，再讀原撤回結果。已成立的重送只讀原結果，不再取得修改資格或移動 head。
- 新撤回須通過既有人工修改准入；正式 head 必須**仍等於原輪 adopted revision**。目前採保守整版條件，後續即使只改別欄，或改回相同文字但 revision 已變，均衝突。未實作不相交範圍的局部反向合併；不是任意歷史還原入口。
- 非 no-op 以輪前 profile、全部固定集合／排序／關係及原來源建立**新的**正式 revision，parent 接目前 adopted revision。不是把 head 直接指回舊 revision，所以不復活舊人工 CAS 基準，且下一輪 A 的人工差異仍可沿 ancestry 讀取。
- 不改 completed Turn、正式訪談、Memory snapshot/frontier、原 adopted candidate、context／compaction。來源保留原 identity、reviewed baseline 與 needs-review，不假造新來源或自行確認。
- 每 Turn 的撤回 command identity 由 App 固定導出；未知回應、同時雙送及晚到原 completion 都不再次套用撤回／正式採用。

研究核對 [PostgreSQL READ COMMITTED](https://www.postgresql.org/docs/current/transaction-iso.html#XACT-READ-COMMITTED) 與 [row locks](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS)：一般 SELECT 不提供跨 statement 的准入保證；更新／列鎖遇到 concurrent writer 會等待。Caliburn 沿已有同檔案 `FOR UPDATE`，鎖後讀目前 head 並比對原採用 revision，鎖與原操作／新 revision 一起 commit；不重造 CAS／重试引擎。

## 實際證據

- 行為 Red：最小已接路由在尚未套用撤回時，`test_undo_restores_base_as_new_revision_without_rewinding_interview_or_context` 真 PG 斷言原職稱應為 null 失敗；之後實作轉 Green。初次缺模組的 collection error 不算行為 Red。
- 追加回歸：後續同欄／別欄人工修改均衝突；撤回重送不蓋後來改稿；active／paused 排除；未完成／跨檔案排除；不接受 client revision；雙送相同原結果；集合／任務明細／K/S 關係／來源恢復，後發布 Memory 留存；交易中原操作記錄後故障全部回滾；下一輪可讀撤回造成的人工差異。
- 受控兩連線交錯：人工先持 file lock／撤回先持 file lock 各一例；第二操作實際等待共同鎖，只第一個符合原採用基準的效果成立，第二個得到 stale revision。不用 sleep 猜順序。
- 升級反例：0017 已有檔案／職稱／正式 head／原操作；舊 CHECK 拒絕新 kind，升到 0018 並重跑 upgrade 後既有每列不變，新 kind 可存。只使用 fixture 自建／自清 fresh test schema。
- 先前的 2 個測試 fixture 錯誤（暫停 helper 名稱、portal 巢狀呼叫）已修正，不當成產品 Red。import-boundary 測試抓到 HTTP 直接匯入 SQLAlchemy exception；已移至 workflow 翻成公開例外，再由 HTTP 投影。

從 `apps/api` 可重現：

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
./.venv-target/Scripts/python.exe -B -m pytest tests/integration/test_jd_undo.py tests/integration/test_jd_undo_migration.py -q -p no:cacheprovider --tb=short
```

此命令 **14 passed**（13 undo／HTTP／競爭、1 populated migration）。追加 `test_consultant_completion.py`、`test_database_migrations.py`、`tests/unit/test_import_boundaries.py` 的窄回歸合計 **46 passed**（24.89 秒；包含前述 14 例，不重複加總）。6 個新 code／test／migration 檔 Ruff check／format、3 個新增 production 模組 mypy 均通過。自審另核完工後 completion 重送不移 head、下一輪人工差異、來源舊基準保留；沒有派 reviewer／子代理。不宣稱 UI、真模型、程序硬崩潰或全套 T13 gate 已通過。
