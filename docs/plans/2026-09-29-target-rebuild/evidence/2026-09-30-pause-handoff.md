# 2026-09-30 安全點暫停交接

Owner 明確要求暫停 Goal；本記錄是恢復入口，不是另一份產品規格或完成宣告。任務唯一狀態在[任務表](../tasks.md)。**收到明確恢復指示前，不繼續施工、付費測試或背景開發。**Demo 程序留給使用者試用，不等於 Goal 持續執行。

## 恢復後進度（2026-09-30 晚，新 Goal）

Owner 以新 Goal 恢復；上述暫停條件已解除，以下各節保留為暫停當時的紀錄。接手時核對：`target-rebuild` 工作樹乾淨、HEAD `e7cccda1`；遠端文件分支 `66bf718d` 的本頁與本機逐行一致（只差換行字元），沒有更新的交接。環境：測試 PG 在 loopback 55439（`caliburn_t01_test`），Demo 後端 8100 與前端 5173 仍在跑；PATH 上的 Node 22 不合前端 24.x 需求且 `corepack` 簽章驗證失敗，前端測試改用 Node 24 執行檔直接呼叫 `apps/web/node_modules/.bin`。

依下方「建議接續順序」推進：

1. **T08 預載超量的有界回退——已補**：[T08 §7](t08-consultant-turn.md#7-近期訪談預載超量的有界縮減2026-09-30-恢復後)（Red 23 failed → Green 38 passed；真 PG 整合與 10 檔回歸 1058 passed）。真模型回讀行為仍歸 T14／T16。
2. **T06／T07／T08 gate 已收斂並勾選**：逐條 Red 與 E／JDT／V 對照 [T06 §21](t06-agent-execution.md#21-任務完成對照2026-09-30-恢復後)、[T07 §5](t07-jd-tools.md#5-任務完成對照2026-09-30-恢復後)、[T08 §8](t08-consultant-turn.md#8-任務完成對照2026-09-30-恢復後)。收斂時補了兩個守門測試（28 個工具的遞迴 strict schema 檢查、模型工具路徑的任務／協作對象／共通條件刪除），並補做任務要求一直缺的**真 API compact 預檢**（[T06 §20](t06-agent-execution.md#20-真-compact-協定預檢2026-09-30-恢復後)：5 次 HTTP、零重試，遠端接受）。完整後端 **1847 passed、2 skipped**（跳過的是需字型的 PDF 渲染，歸 T13）。
3. **下一步**：T09 瀏覽器旅程（含需 A 准入的兩項 e2e）、T10／T11／T12 收斂、T13 乾淨交付、T14→T16→T17 品質與長訪談、T15、T18；順序與進度見任務表，不在本頁重複。

## 最新補記：文件推送與再次安全暫停

本節取代下方較早暫停時的「下一步」優先序；下方真旅程、程序 PID、DB 版本及資料筆數均為當時觀察，不是本次重新驗證的即時狀態。Owner 先要求只推送文件，接著明確要求推送後安全暫停以便交接。

### 接手位置與推送邊界

- **實作工作目錄／分支：**`S:\caliburn` 的 `target-rebuild`。最新程式提交 `595dc097`（產品取消金額攔截，付費測試仍可明設預算）；本補記只另作文件提交。接手先核 `git status`、`git log`，不要 reset 或重做既有成果。
- **文件分支：**`docs/target-rebuild-architecture-2026-09-30`，從既有遠端 `origin/main` 建立，只帶架構及相關規劃／證據 Markdown 差異。新程式、測試腳本、生成契約、`.env`、DB 及本機暫態資料不在本次上傳範圍；不 push `target-rebuild`、不 merge、不部署。
- **遠端文件不等於遠端程式：**文件描述的是本機實作與驗證；相對 `main` 未推送的程式仍只在本機實作分支。其他機器的實作者若需要接續程式，須另安排程式交接；不能在文件分支重做全部或宣稱取得最新可執行版本。文件中的程式／測試連結及研究腳本可能尚未存在於此遠端分支。
- **暫停狀態：**本次已啟動的測試已結束，沒有留下本代理待續測試或子代理開發；沒有啟動新付費模型呼叫，沒有切換／重啟 Demo、執行 Demo migration 或清理使用者資料。Demo 保留供使用者操作；接手須重新核對實際程序與 DB，不能依本文件舊 PID 執行停止。

### 已完成增量與本次驗證

前次暫停後已完成 UI 改版、目前 Turn 發現入口、本輪 JD 變更檢視、首版恢復減法與安全退出，以及產品取消金額 gate。各責任與歷次證據仍分別沿 [T09 UI](t09-ui-redesign.md)、[目前 Turn](t09-current-turn-discovery.md)、[本輪 JD 變更](t09-turn-jd-changes.md)、[T12](t12-consultant-process-recovery.md)及 [T06 §19](t06-agent-execution.md#19-產品移除金額攔截與按請求計數預留2026-09-30)，不在交接頁重寫規格。

本次針對程式 `595dc097` 做唯讀審查與以下新回歸，未改程式。命令工作目錄為 `apps/api`，既有 `.venv-target`；`CALIBURN_TEST_DATABASE_URL` 指向 loopback 55439 的 `caliburn_t01_test`，每案建立及回收自身測試 schema，非 Demo DB。模型使用合成／mock，不是新真模型品質驗證。

```powershell
# 共用執行、原件／工具、容量、壓縮與恢復
./.venv-target/Scripts/python.exe -B -m pytest tests/integration/test_graph_postgres.py tests/integration/test_response_step_postgres.py tests/integration/test_memory_tool_step.py tests/integration/test_context_preparation_postgres.py tests/integration/test_model_request_accounting.py tests/integration/test_execution_budgets.py tests/integration/test_request_capacity_postgres.py tests/integration/test_outbound_retry.py tests/integration/test_response_recovery_eligibility.py tests/integration/test_role_context_history.py -q -p no:cacheprovider --tb=line
# 67 passed in 59.34s

# unit／contracts 與 JD 真 PG（PDF、Undo 另有自身 gate，不在此命令）
$jdGateFiles = @(rg --files tests/integration | Where-Object { $_ -match '[\\/]test_jd.*\.py$' -and $_ -notmatch 'export|undo' })
$jdGateTemp = 'S:\caliburn\.research-tmp\pytest-t07-closeout-' + [guid]::NewGuid().ToString('N')
if (Test-Path -LiteralPath $jdGateTemp) { throw 'Fresh test path unexpectedly exists' }
./.venv-target/Scripts/python.exe -B -m pytest tests/unit tests/contracts @jdGateFiles -q -p no:cacheprovider --tb=line --basetemp=$jdGateTemp
# 1218 passed in 145.58s
```

前次同組 JD 回歸遇 sandbox 暫存目錄 ACL 錯誤，不能算通過；上述 1,218 是另用新 GUID 暫存路徑、正常權限重跑的成功結果。錯誤嘗試沒有當作產品 Red，也未刪除原暫存。兩組結果不代表整套 integration、UI、真 provider、PDF 或長訪談已在本次重新驗過。

### 未完成與建議接續順序

1. **收斂 T06／T07 gate。**本次共用執行審查未發現新的框架阻擋項；JD 八入口、來源與 diff 已有程式及上述回歸。因收到暫停指示，未完成最後逐條 gate 對照與狀態收尾，任務表仍不勾選。接手沿原 evidence 完成對照，可重用本次證據，不必重寫工具或另建驗證平台。完整真模型品質仍歸 T16／T17。
2. **T08 已定位缺口：近期訪談預載超量的有界回退。**[顧問 context 規格](../../../specs/2026-09-26-consultant-context-and-state-design.md)已要求在確實超過模型完整請求容量時，保留完整訊息的近期尾段與必要前問、說明未預載範圍，讓 A 用既有 `read_interview` 按需讀；不是到 128K 就刪歷史。現行 `context_binding.py` `_capture_data` 仍組装全部近期原話，`request_capacity.py` 超限會拒絕，尚未接上述 fallback。須先補行為反例再沿既有 owner 接線；不得刪本輪輸入、改寫原生接續歷史或取消同輪固定 Memory。這是靜態對照找到的實作缺口，尚未建立／執行專項 Red。
3. **T09–T15 尚有整合／交付驗收。**新的 UI／API 增量、來源下鑽／diff 的真瀏覽器旅程、完整故障競爭與容量、安全及乾淨環境 PDF 交付，依各任務未完範圍核對。不要因 API 已存在就勾完整旅程，也不要恢復已被 Owner 減去的罕見恢復系統。
4. **T16／T17 真模型與成果品質。**原代表旅程仍有漏引、更正泛化與失敗批次等品質缺口；金額 gate 的工程修正不會把舊失敗改成通過，見 [T17](t17-course-administrator-journey.md)。之後以有界 manifest 驗證，不拿 mock 或 API 200 代替 JD 效果。
5. **T18 未完成。**正式入口切換、精確舊碼退役與可重現交付仍待前置 gate；目前不改 production authority。接手以整體可用及計畫 §5 為完成標準，不能把此次文件推送當作產品交付。

恢復範圍以任務表頂部的 successor 與共用執行 §6.4／§6.5 為準；下方歷史「未明結果全面再准入」不再是首版必做項。**先核現況，再完成目前切片，不從 T01 重來；未收到恢復授權前停止施工。**

## 前次暫停紀錄（歷史觀察）

## 現在可用到哪裡

[開啟本機全合成 Demo](http://127.0.0.1:5173/job-files/b6e76e87-817c-4c9e-8c82-3564b329c7f2)。可以查看已保存內容、匯出 PDF，或由使用者自行開始下一次訪談。

| 能力 | 已有證據與限制 |
| --- | --- |
| 訪談 → AI 編輯 JD → 正式保存 | 四次真 `gpt-6-luna` 訪談完成，正式序號 1–9；三項工作由訪談產出，未人工代寫。重開能讀回同一正式稿及答覆。 |
| 背景 Memory | 三批 B1→B2 已共同發布；處理邊界分別 4、6、8。A 第三輪實際固定已發布 Memory、讀兩層資料，依員工更正修 JD。 |
| 暫停／接續 | 第三輪真 A 曾停妥、重開並續同一 execution，保留原 Memory；不能擴大為所有 crash 位置都已驗。 |
| 公開中間訊息 | 真 A 的 commentary 已保存、可歷史回看；不進正式訪談序號。尚未捕捉真模型完成前 delta 與斷流恢復的完整視覺證據。 |
| 來源回查 | 正式來源 UI 已接線，瀏覽器讀回序號 8 原話；Memory 固定鏈與差異有 HTTP／PG／component 證據，尚缺該路徑真瀏覽器驗證。 |
| PDF | 已實際渲染中文長短稿；暫停前再次從 UI 成功下載正式 JD，615,045 bytes。不匯出候選、不含姓名。 |

真旅程／費用／限制沿[T08 §5](t08-consultant-turn.md#5-顧問--背景整理的整合2026-09-30-1057-台北)與[T13](t13-pdf-export.md)，新唯讀来源沿[T09 整合證據](t09-source-viewer.md)。資料全為合成，不能據此宣稱一般長訪談或專業 JD 品質已全面達標。

## 暫停時安全狀態

- 分支 `target-rebuild`；本次來源切片以前的提交為 `1198509f`（公开串流）、`29b83bb1`（整合證據）。本記錄及來源切片一同作本地安全提交；恢復時先用 `git log -3`、`git status` 核對实际提交，不猜 commit hash。
- Demo DB `caliburn_target_demo`，loopback 55439、schema `caliburn`、migration 0018。只作唯讀核對：`executions` 為 **consultant_turn completed 4、failed 1；memory_batch completed 3**，無 active／paused；`memory_snapshots` 共 3 筆。歷史 failed 仍保留，不清掉它掩蓋失敗。
- 最新發布 snapshot `48c31c96-f1db-4fc2-a099-89c6a23103e6`，F=8；最後成功 A `e1178998-0df0-44da-929d-bbef0ce33ae0`，B `07be6b4c-d230-4c93-beb9-2d5fd1f710d5`。沒有半途候選需手動轉正式。
- 自有後端 loopback 8100，launcher PID 33124；前端 loopback 5173、PID 24936。這是觀察值，不可在後續不核程序身分就據 PID 停止；目前保留運行。啟動方式沿[backend README](../../../../apps/api/README.md#本機-ai-demo-啟動)，不動舊正式產品。
- 本機暫態 log：`.research-tmp/target-demo-backend-live8.{stdout,stderr}.log`、`target-demo-vite-source.{stdout,stderr}.log`。憑證只由既有 loader 載入 `apps/api/.env`；不複製到文件、命令或版本控制。
- 收到暫停後沒有發送新模型訪談／背景整理；最後只做唯讀 UI／DB、PDF 匯出及離線回歸。完整資料與程序保留，不刪 DB、volume 或 secrets。

## 尚未完成：恢復後從這裡續

1. T06／T08／T11／T12：已保存原件和已提交工具可承接，但跨程序 **未明 outbound attempt 的 production 核對／恢復接線**與完整故障競爭矩陣尚未完成。不要盲重送模型、重複業務效果或宣称任何中斷都自動恢复。
2. T09：真串流完成前呈現、斷流重連與跨 tab；來源的 Memory 鏈／diff 真瀏覽器驗證。獨立 reviewer 建議把「列表後再發布」的臨時探測補成永久 HTTP 回歸；不阻擋本次唯讀切片交接。
3. T14／T16／T17：分析指南／Prompt／工具共同品質校準、長訪談、更正及來源變動的代表情境，真 Compaction／容量門檻與成本驗證尚未全過。既有 11 種情境與 rubric 可沿用，不另造評測平台。
4. T15：完整安全／容量／大集合查詢和 context 量測；目前前端 build 的主 JS 約 907.80 kB、gzip 271.11 kB，仍有 chunk 警告，不調高門檻掩蓋。
5. T13／T18：乾淨環境安裝、PDF 字型／Chromium 交付、完整操作驗證與正式入口切換／精確舊碼退役未完成。未 push／merge／對外部署，旧正式 authority 未切換。

**恢復次序：**先讀本頁、tasks、相關 evidence，核分支／dirty／Demo 是否被使用者继续操作；不得以此快照倒回後續資料。先補原件／未明結果恢復接縫，再做受影響故障回歸與真旅程／品質 gate；沿原 T01–T18 推進，不從頭重做。

## 參考資料審核與本次驗證

Owner 新提供的 OpenAI Compaction 參考，已對照本機 SDK／接線與[官方 compaction 指南](https://developers.openai.com/api/docs/guides/compaction)：目前手動完整 `compacted.output` 取代旧接續視窗、不解析密文，保存／採用後才追加新資料，未啟用 server-side automatic compaction。33 項相關離線測例通過，**不是新增真 API compaction 驗證**；不因附件新增雙摘要或永久 event store。

來源差異仍是「所見新基準對原引用舊基準」，不要求追遍中間每次修訂，不增設「改回原文」特殊流程；既有明確確認引用對齊規則不變。

本次完整 unit／contracts **946 passed**、來源相關真 PG **13 passed**、來源 UI **20 passed**、Ruff／mypy 246 files／tsc／codegen check 通過。完整 web 115 項與 build 證據在[T09 UI](t09-source-viewer-ui.md)；不加總重複執行測例。新 sequence 圖實際渲染視檢。完整 PG suite 沒有在本來源切片重跑，不把較早 725 項全套冒稱本次全面回歸。
