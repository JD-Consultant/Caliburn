# T2：訪談筆記保存、原結果及完成交易

2026-10-07。T2 已接上固定基底、完整正文操作、原結果恢復與正式採用資格。受影響範圍共 93 個測試通過：64 個真 PostgreSQL 整合測試、28 個 import boundary 測試及 1 個 packaged migration 測試。這是資料及交易證據，尚不代表模型使用、換窗投影、UI 或 JD 品質通過。

責任來源：[施工計畫 T2](../../2026-10-07-interview-plan-implementation-and-comparison.md#t2候選原操作與採用完成交易)、[INTPLAN §6.5–6.9](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md#65-資料庫表示完整正文候選指標與原結果)。沿用 `consultant-jd-analysis` 及開始前的未提交工作；沒有 commit、push 或產品資料升級。

## 效果與反例

- 每輪 candidate 只有 base／current 指標；operation 保存完整 nullable `TEXT`。start 重入讀原 base，當輪修改不覆寫初始正文；未建立、刻意空及純空白均精確保留。
- apply 保存固定 v1 意圖摘要及 prepare 的逐字 `result_text`。unchanged 仍建立 revision；先核原操作，同 ID 換位置、diff、正文或結果拒絕。較早成功／unchanged 重播回原結果，current 不倒退。
- 活躍 writer 在檔案鎖後保存效果，pending pause 不丟已飛結果；真正 paused／cancelled／failed 拒絕效果。completed 先由原 execution owner 核原 writer，只能經 `recover_prepared` 讀已保存同意圖操作；查無原操作拒絕，恢復分支沒有 append 或 head mutation。
- 採用資格由 interviews 的匹配正式 exchange metadata 與 executions 的 completed consultant IDs 批次查詢交集形成。plan owner 僅 join 自己的兩表與參數化 typed VALUES，按 employee input sequence 降冪 `LIMIT 1`；不讀其他 feature ORM，不載入訪談或所有候選正文。reply 在固定 frontier 後仍可使用其 input；勝出正文為 null／空時不找較早 fallback。只有 completed 或只有正式 exchange 均無資格。
- completion 同交易核最終 plan head；缺位置／過期位置使正式訪談、JD 及 context 一起回滾。取消競爭只有一個完整結果。completed 跨行程恢復入口只核原 writer、完成 context、原 exchange／reply 和原 plan head，較後 Turn 不倒退，active 不因恢復呼叫取得 completed 資格。
- 0026 明寫同 scope FK、CHECK、expected 參照索引及 cascade。operation 個別 UPDATE／DELETE 被 guard 拒絕；合法整檔刪除可移除新表資料並保住另一檔案。Alembic metadata／CHECK 名稱與真 DDL 核對通過。

## Red → Green

以下皆使用本次新建 PG 18.6 容器，僅 loopback `55447` 的 `_test` DB；既有 fixtures 每例新建隨機 schema 並只清理該 schema。資料是合成內容，沒有模型呼叫或私人訪談外送。

| Red | 觀察 | Green |
|---|---|---|
| 兩表不存在 | 真 PG catalog 回空集合，預期 owned candidate／operations。 | migration、ORM 登錄及 DDL 對照通過。 |
| start 尚無持久效果 | 最小 API scaffold 只回記憶體 snapshot，跨交易 `read_current` 為 None，與原 snapshot 不相等。不是 module／import 失敗。 | 插入完整 start 與 candidate；重入回原 base。 |
| 原 completion 略過 plan | candidate 已保存後，既有 complete 未拋 `PlanStateError`。 | 同交易加 `validate_final`，缺位置／過期位置拒絕並回滾。 |
| completed 原操作被 active-only guard 擋住 | 已完成、同 writer 的原操作無法取回，觀察為 None，預期原 `PlanEditResult`。 | 窄 read-only owner 恢復及 completed writer fencing；new operation 仍拒絕。 |

測試先列了 body／操作／資格／完成／隔離反例，再擴充用例及接線。原操作未知確認測例在真 DB 提交後注入 App 回覆確認遺失，再以同命令查回；它不宣稱模擬 PostgreSQL wire 層遺失 COMMIT ACK。native checkpoint／provider 失 ACK 及 initial capture 缺口由 T3 相應測試負責。

## 實際檢查

PowerShell 使用 workspace UV cache 與既有鎖定環境：`UV_CACHE_DIR=S:/caliburn/tmp/uv-cache-intplan`、`uv run --project apps/api --locked --no-sync`。測試 DSN 僅注入 `CALIBURN_TEST_DATABASE_URL`，本文不保存憑證。

```powershell
uv run --project apps/api --locked --no-sync pytest `
  apps/api/tests/integration/test_interview_plan_storage.py `
  apps/api/tests/integration/test_consultant_completion.py `
  apps/api/tests/integration/test_database_migrations.py `
  apps/api/tests/integration/test_job_file_deletion.py `
  apps/api/tests/unit/test_import_boundaries.py -q -p no:cacheprovider
# 92 passed in 63.09s；其中新 plan storage 為 29 個測例。

uv run --project apps/api --locked --no-sync pytest `
  apps/api/tests/unit/test_packaged_migrations.py -q -p no:cacheprovider `
  --basetemp=<本次新的 workspace 暫存目錄>
# 1 passed in 0.95s；此單一既有測試由 require_escalated 執行。
```

Ruff check／format 僅處理 T2 owned 檔案，最後 check 通過。mypy 對 `features/interview_plans`、`features/interviews`、`features/executions` 及兩個 workflows 的 23 個 source files 通過。`git diff --check` 通過；Git 只提示既有 Windows LF／CRLF 規則。

環境限制保留：預設 UV cache 存取被拒，改用 workspace cache／`--no-sync`；pytest `tmp_path` 的 Windows 受限 token 建立後不可讀，預設 Temp、workspace 及允許的 visualization 新路徑皆有 WinError 5。含 packaged test 的合併執行在該 fixture／清理失敗，未算通過。自動 review 核准只對該既有測試使用 `require_escalated`，先驗證新 basetemp 的絕對路徑仍在指定 workspace 前綴；沒有改 ACL、測試條件或產品路徑。之後取得上述 92＋1 的確定成功結果。

## 審查與未驗範圍

已逐項核對：沒有正式正文副本／採用 flag／restore generation；service 不 commit；網路或 checkpoint I/O 不在 plan 交易鎖內；completed 恢復不呼叫 active-only JD preview 或重新採用 JD；正式資格查詢失敗直接傳播，不偽裝成空；模型及 wire 不持有 App scope。root 仍負責整體 spec／code quality 審查與 T3–T5 接線。

新 VALUES 讀取沿鎖定 SQLAlchemy 2.1.1，核對 [SQLAlchemy 2.1 Values.cte 官方契約](https://docs.sqlalchemy.org/en/21/core/selectable.html#sqlalchemy.sql.expression.Values.cte)；FK／CHECK／索引及 cascade 的責任分界核對 [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)。官方能力不代替本案資格判定；以上實際 SQL 和交易結果由真 PG 測試驗證。

## T3 審查後補：active projection 讀取

新增 `InterviewPlanWorkflow.read_active(writer) -> PlanSnapshot | None`。同一 `sessions.begin()` 依 file lock → active writer lock → owner current 讀取；scope-only `read_current` 繼續供 terminal 原結果及 UI 使用，不冒充 active capture 的資格交易。

四個真 PG 反例先使用 scope-only 委派 scaffold，觀察取消／替換 writer 均未拒絕；owner current 查詢期間，另一 connection 的 `FOR UPDATE NOWAIT` 亦能取 row，這是行為 Red，不是缺 method／import。實作後四例 Green：取消／替換 writer 拒絕、pending pause 仍可讀；current 查詢時 file／execution 兩 row 均仍被同交易鎖住，正常完成及注入讀取故障回滾後兩鎖都解除。

storage 全檔現為 33 例；連同獨立投影 boundary 三例共 **36 passed in 30.22s**。三個受影響檔 Ruff check／format 通過；上述 T2 mypy 範圍仍為 **23 source files** 通過。原 93 例證據保留，新增四例不重算成同一個全範圍執行；T3 adapter 接線與其獨立審查沿 [T3 review](t3-storage-review.md)。
