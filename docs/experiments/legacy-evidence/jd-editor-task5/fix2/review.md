# Spec Compliance

✅ **PASS：原 R06 stop projection／drain 缺口 CLOSED；Task5 已無未閉合 Important finding。** 原 R01–R05 及 R06 recovery 的 fix1b closure 延續。本判定僅接受既定 Task5 隔離實作範圍，不代表 Task6、natural model、OS 真人 IME 或產品成品通過。

2026-09-11；worktree `S:/caliburn/.worktrees/analysis-only-agent`。僅讀本輪兩檔差異與具名控制流程，沒有重開未改機制。

# Strengths

- ✅ `experiments/analysis-agent/src/analysis_agent/service.py:803–811`：stop 在同一 `entries_changed` 鎖區解除 closing、完成 `get_run`，再於內層 finally 減 close_entries 並 notify。成功時結果已是本地值才離開鎖；投影拋錯時先執行計數清理，再退出鎖並傳遞例外。close 不能在原最後讀取仍待執行時先排空資源；沒有晚到的 finally 留在鎖外覆蓋新 owner。
- ✅ 同檔 `:793–799` 的 native cleanup／close_turn／對帳仍在全域 lock 外；此尾段修正沒有撤銷 R04，也沒有改 SQL／checkpoint authority、模型或 Web 契約。
- ✅ `experiments/analysis-agent/tests/test_jd_stop_projection.py:8–64` 使用實際 service／graph 與 MockTransport，在最後投影入口設 barrier；成功與拋錯兩個參數都確認 close 不提早返回、兩執行緒完成、close_entries 歸零且 closing 清除。失敗案例確認原投影錯誤保留，成功案例確認 cancelled 結果。

# Issues

- **Critical：無。**
- **Important：無；T5-R06 CLOSED。**
- **Minor：無新增。** 原 R07 upstream Starlette／AnyIO 警告已記錄並保留 raw，沿 fix1b 判定，不要求無關依賴升級。

# Checks／證據效力

- ✅ 逐檔核 manifest／snapshot SHA256 相符：service＝`422179128b9951466cd43f160bb64307daec374146c32f3a586ca3b98473d880`；新 test＝`033aebc0a05ba90eaa2656f73cfa3b9e7917698f11b99b31a4dc2b97a35197f1`。
- ✅ 已完整讀 `task-5-fix2-review.diff`（5865 bytes），SHA256＝`117c9b75157bea4aa125080a0886233814dd7a5d5a60bfb15bdd7d3c7082d83b`。service 的 before hash 對應本人已審 fix1b；修改限定 stop 尾段及新測試。
- ✅ 直接讀 `scratch/task5-fix2-red.log`：兩個參數都在「Shutdown returned before stop projection unwound」失敗，2 FAIL／20.17s，反例確實命中原缺口。
- ✅ 直接讀 `scratch/task5-fix2-green.log`：9 PASS／17 deselected／21.28s，涵蓋新兩項與既有相關 stop／abandon／projection 測試。這是已存 raw 的核對，沒有宣稱 reviewer 重跑測試；依本輪窄審要求，不重跑 54／63／37，也不把重疊輪次相加。
- ⚠️ 本輪沒有新增真 PostgreSQL、Win32 或 headed browser 的證據。原 NL08 suspended child、NL10 manual A＋selection B、NL11 nested 成功／真 access-denied 的有限效力，以及日常啟停 UI 尚屬 P5，全部保留。
- ✅ 僅新增本 review；未修改 code／測試／原 raw，未操作 git、真 key、產品 provider、DB 或既有程序，零付費及 production 0060 隔離邊界不變。

# Assessment

**Task quality：Approved（Task5 既定隔離範圍）。** 原六項 Important 均已閉合；本輪源碼與具名 RED→GREEN 回歸足以支持最後停止讀取的 drain 邊界。root 可依既定流程接受 Task5，精確 commit／tag 仍由 root 執行，本 review 不宣稱它們已完成。
