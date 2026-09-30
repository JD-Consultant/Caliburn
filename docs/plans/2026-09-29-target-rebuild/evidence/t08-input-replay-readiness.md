# T08：輸入原接受結果不受模型 readiness 阻擋

- 日期：2026-09-30；狀態：**本切片已實作及真 PostgreSQL／合成 HTTP 回歸通過**，不是全庫或真模型品質驗收。
- Owner 本次授權：修 input transport 與原 workflow，已接受的同 command 核對原文並回原結果，不依 model readiness；新輸入仍先拒絕不可用狀態且不得保存；異文衝突維持 409。
- 責任依據：[訪談保存 §6](../../../implementation/interview-storage.md#6-輸入接受重送與新提交)、[程式撰寫規範](../../../implementation/coding-standard.md)。沿用原 command／原結果 owner，不建立第二套 receipt、重試或保存層。

## 根因與修正

原 `get_consultant_dispatch` 作為 FastAPI 依賴，在 route 執行前就對缺 model／已停止 supervisor 拋 503。因此既有的 command 即使可從 DB 核對，仍進不到 `InterviewInputWorkflow.accept`。F2 的具体原因碼是 `model_not_configured`，不是 startup race、共享 leader 未釋放或 DB 原結果遺失。

首次 read-only 診斷發現測試新建 App 未帶 admission-only fixture override；暫時補 override 能通過，但 Owner 後續明確選定**產品本身允許離線核對已接受結果**，因此正式修正不以替測試補 dispatch override 代替。

| 修改位置 | 效果 |
|---|---|
| `apps/api/src/caliburn/workflows/interview_inputs.py` | `read_accepted(command)` 經原 `interviews.service.find_accepted_input` 精確核原文字串並回不可變原 source／execution；只讀、不授予新准入 |
| `apps/api/src/caliburn/transport/http/interview_inputs.py` | readiness 依賴回明確的 unavailable 值、不提前拋錯；route 先核原結果，只有不存在時才以 readiness 限制新接受 |
| `apps/api/tests/integration/test_input_replay_readiness.py` | 真 PG 驗 model 未配置、supervisor 已停止兩種情境：replay 200 原結果、同 command 改原文 409、新 command 503 且無新增資料 |

新 command 通過 readiness 後仍呼叫原 `accept` 短交易：檔案列鎖→再次查 command→准入→原文與提交關係共同 COMMIT。前面的查無結果不是准入保證，不能省略交易內重查；併發重送仍只有一筆原文／execution。只有真正新增且提交完成才 `notify`；回原結果不重新啟動模型、不復活取消的 Turn，durable discovery 仍由既有 supervisor 負責。

這不是承諾 readiness 檢查後程序永不故障；已接受工作的恢復仍循既有 execution／supervisor。未配置／已停止時查無原結果，則在任何新原文或准入保存之前回 503。

## TDD 與驗證

1. Red：兩個新增 readiness 反例＋原 `test_acceptance_replays_after_app_instance_is_recreated`，**3 failed**，分別觀測 `model_not_configured`／`consultant_unavailable` 擋住 replay。
2. 實作後重跑碰到主線同期新接 Host guard：**22 failed**，預設 `testserver` 在進 route 前被拒絕。沒有關閉 guard、放寬正式 Host 或以此聲稱 F2 未修。
3. 僅在診斷程序把 TestClient 預設 base URL 改為合法 `http://127.0.0.1:8100`，相同回歸 **43 passed in 17.01s**；本切片自有測試亦明確使用合法本機 URL。
4. 主線／其他代理完成共用 fixture 與個別 TestClient 的合法 Host／Origin 接線後，以下**未使用診斷 plugin 的普通命令**再次 **43 passed in 18.43s**。

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
./.venv-target/Scripts/python.exe -m pytest tests/integration/test_input_replay_readiness.py tests/integration/test_input_acceptance.py tests/integration/test_consultant_http_execution.py tests/integration/test_consultant_memory_http_journey.py tests/integration/test_consultant_leader_release.py tests/unit/test_import_boundaries.py -q --tb=short -p no:cacheprovider
./.venv-target/Scripts/python.exe -m ruff check src/caliburn/workflows/interview_inputs.py src/caliburn/transport/http/interview_inputs.py tests/integration/test_input_replay_readiness.py
./.venv-target/Scripts/python.exe -m ruff format --check src/caliburn/workflows/interview_inputs.py src/caliburn/transport/http/interview_inputs.py tests/integration/test_input_replay_readiness.py
./.venv-target/Scripts/python.exe -m mypy src/caliburn/workflows/interview_inputs.py src/caliburn/transport/http/interview_inputs.py
```

Ruff／format／mypy 通過，差異無 whitespace error（工作區 CRLF 提示未隱藏）。回歸含原 F2、併發 command 重送、取消後原結果、保存失敗回滾、A HTTP 執行、A→B1/B2→publish→下一輪，以及原 leader-release 反例。新增測試直接核 DB 計數：新輸入被拒後沒有新 execution、interview input、原文或正式資格。

未修改 bootstrap、settings、security middleware、共用 fixture 或原 F2 測例；其 Host／Origin 更新由其他 owner 完成並保留。未改 schema／生成物，未 commit，未付費呼叫模型。未重跑全 PG／全 unit suite，不以此覆蓋主線其他失敗；leadership 修正證據仍在 [T11 §8](t11-memory-batch.md#8-共享-leader-的依賴收尾-callback已修正局部驗證)。
