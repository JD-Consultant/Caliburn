# Task5 fix2：stop 最後投影的 drain

2026-09-11；唯一原 R06 Important。獨立 fix1b review 已閉合 R01–05 及 R06 recovery；本輪不重開其他功能。

最小修正位於 service.stop 的 finally：在同一 entries_changed 鎖區內解除 closing、取得最後 get_run 結果，再以內層 finally 減 close_entries／notify。結果投影完成或拋錯才允許 shutdown 排空。native cleanup、PG reconcile 與 close_turn 仍在全域鎖外，不改 SQL／模型／Memory／UI 契約。

新 `tests/test_jd_stop_projection.py` 以實際 AnalysisService／graph／本機暫存 catalog 和 MockTransport，讓最後 get_run 入口暫停，再由另一執行緒關閉 App。兩種情境是正常投影與投影拋錯；都要求 close 不先返回、兩 thread 結束、計數歸零及 closing 清除，失敗如實拋出。

- `scratch/task5-fix2-red.log`：2 FAIL，20.17s，均於 close 提早返回的 assertion 重現原缺口。
- `scratch/task5-fix2-green.log`：**9 PASS／17 deselected，21.28s**；新兩項及既有 test_service 中 projection／stop／abandon 相關測試。
- scoped authored diff whitespace check PASS，僅 Git 換行提示。未重跑54／63／37；它們仍是 fix1b 對各自未改功能的證據，不能相加作新總數。
- 0產品provider／0付費／0真key讀取；本輪不新增PG／Win32／headed browser證據，原有限效力不變。

兩檔精確差異及hash：P/task-5-fix2-review.diff、task-5-fix2-review-manifest.json。其餘32個Task5來源逐檔與最後凍結hash相同。等待原reviewer只核R06 stop closure，未接受或提交Task5。
