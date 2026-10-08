# T3：保存切片的獨立接線審查

2026-10-07。由 T2 implementer 對未自行實作的 T3 production 檔案只讀審查，對照 [INTPLAN §6.6／6.9](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md#69-captured-能力與換窗投影的施工契約)。審查核到兩個契約缺口及一個修正過嚴的 pending 分支；已交 root 按反例修正。沒有用保存或單元測試結果宣稱模型／JD 品質通過。

範圍為 `context_binding.py`、`interview_plan_context.py`、`interview_plan_projection.py`、`planning_instructions.py`、`runner.py`、`agent_execution/context_compaction.py` 及 `bootstrap.py`。另沿現有 RoleContextHistory、native response loop／compaction、saver 與 completion 公開能力核對呼叫順序，未改 T3 production 檔案。

## Findings 與裁決

| Finding／精確反例 | 結果與責任 |
|---|---|
| P2：initial capture 可靠確認不存在，但 prior plan start 已提交；今日 template 沒有 plan toolkit。原 guard 只在今日有 toolkit 時查 prior base，可用今日 v1 重新捕捉同 Turn。 | root 補無論今日能力都查 prior base 的缺失 guard，完全缺失的 capture 不重建。初始位置不能代替原 Memory／frontier／request。 |
| 修正反例：原 capture graph 仍保存原 template、node pending，start 已提交但尚無完整 binding。若 `_capture_data` 因 prior base 一律拒絕，會把 §6.6 允許的原 `None` resume 當成 unrecoverable。 | root 撤回 node 的 unconditional guard，原 pending graph 沿原 toolkit 重入、讀本輪 base，第一個完整可靠 binding 才固定 Memory／F；不把尚未保存的 binding 說成已恢復。新測例區分完全缺 graph與原 pending template。 |
| P2 契約接線：projection 的 `ensure_active()` 與 `read_current(scope)` 分別開交易，current 查詢沒有同 file／writer fence。guard 後可取消／替換 writer，scope-only 讀取仍成功。最後 guard 可阻止窗口回傳，但不能說讀取本身已核 writer。 | root 授權 T2 補窄 `read_active(writer)`，同交易核 file／active writer／current。真 PG Red–Green 詳見 [T2 增補](t2-storage.md#t3-審查後補active-projection-讀取)；再核 root 的 projection default adapter 已接此 API。沒有新增 native I/O 鎖或公開 metadata。 |

其餘所讀路徑未核到具體 P1／P2 結果錯誤：strict v1／v2 binding 依原完整 toolkit 分派；缺一工具／不相容 schema／版本與原 request 不符會拒絕；v1 不新增 plan handler／wrapper，v2 null／空仍帶 start；模型 item 僅有同份正文。wrapper 先委派原 C 恢復及核帳，再核 projection；原 saved binding 包括 raw `__start__` 固定 exact C，完整 projection 原樣返回 item；completed 入口讀原 execution 完成 binding、exact native final、原 capability 及 same-execution plan head，原 formal reply／writer／position 再於短交易核對，不讀後輪採用版或重跑 JD preview。

## 獨立故障測試

依 root 授權新增 `apps/api/tests/unit/test_interview_plan_projection_boundaries.py`，共三例，重用既有 projection scenario 與真 LangGraph `InMemorySaver`：

- raw projection `__start__` 已保存後失 ACK，同時阻止 expanded checkpoint／pending writes 保存；確認 raw 只有原 start binding，之後加入較晚 C checkpoint。恢復仍返回原 exact C，沒有換成 latest C；純 capture node只執行一次讀取。
- 完整 projection 已保存，parent 的新 request checkpoint **保存前**失敗，且 pending writes 亦未保存。`None` resume 的後續模型 input 是完整原 C＋原 plan item，reader 與 compact 各一次。
- 完整 projection 已保存，parent 的新 request checkpoint **保存後**失 ACK。恢復原 request；同樣保住原 item、完整 C，沒有重讀今日 head 或重 compact。

三例對現有 projection 行為直接通過；施工 scratch 的 thread／checkpoint namespace 注入錯誤已修正，沒有把 harness 失敗冒充 production Red。這些是 native graph 故障與完整模型 input 證據，使用合成資料及 provider fake，不是真 provider／PG wire 層 ACK 測試。

```powershell
uv run --project apps/api --locked --no-sync pytest `
  apps/api/tests/unit/test_interview_plan_projection.py `
  apps/api/tests/unit/test_interview_plan_projection_boundaries.py `
  apps/api/tests/unit/test_context_compaction.py `
  apps/api/tests/unit/test_consultant_tools.py -q -p no:cacheprovider
# 48 passed in 1.81s

uv run --project apps/api --locked --no-sync pytest `
  apps/api/tests/integration/test_interview_plan_storage.py `
  apps/api/tests/unit/test_interview_plan_projection_boundaries.py -q -p no:cacheprovider
# 36 passed in 30.22s；其中 storage 為 33 個真 PG 反例。
```

新增 boundary test、T2 workflow 及 storage test 的 Ruff check／format 通過，T2 mypy 23 source files 通過。以上執行使用本次專用 loopback `_test` PG／隨機 schema。root 新增的跨行程 completed runner、原 unfinished v1／v2 與完全缺 initial capture 測試，驗證結果由 root 的 T3 證據另記；本文沒有冒領尚未執行的範圍。沒有 commit／push。
