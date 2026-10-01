# 2026-09-30 安全點暫停交接

本頁保留歷次交接；先讀下方最新交接，較早的暫停、程序與未完事項均有時點，不是目前狀態。任務唯一狀態在[任務表](../tasks.md)，本頁只整理接手路由，不另立產品規格或完成條件。

## 最新交接（2026-10-01：核心已接通，尚未全案驗收）

Owner 問「除了品質以外是否完成、能否交接」。**可以接手現有成果，不需重寫；但仍有容量／完整旅程驗收、背景解阻及正式交付收尾，不是只剩 Prompt 品質。**本節取代下方歷史的接續順序，不改任務勾選、不豁免品質 gate，也不表示已正式切換。

### 接手基準與已可用範圍

- 本次核對位置 `S:\caliburn`、分支 `target-rebuild`，產品程式基準 `b3ce7f53`；整理本節前工作樹乾淨。其後本輪只更新交接／計畫入口。接手重新核 `git status`／`git log`，不倒回本記錄的 hash。
- 目前任務表為 **T01–T13、T15 完成；T14、T16、T17、T18 未完成**。已完成是各任務的證據層級，不代表完整產品品質已通過。
- 核心已有實作及相應證據：隔離職務檔案、訪談與公開中間訊息、A 工具編輯／候選預覽／正式保存、人工 JD 編輯、來源下鑽與 diff、B1→B2 共同發布 Memory、暫停／取消與首版恢復、正式中文 PDF。最近一次[跨層審查](../review.md#5-核心旅程跨層審查2026-10-01)未找到新的阻擋缺陷；不把那次局部回歸說成本輪重新跑過全套。
- 最新程式仍在本機分支；先前只推送了文件分支，**其他機器不能只 checkout 遠端文件分支就取得本次程式**。本輪不 push／merge／部署。跨機交接需另外安排程式傳遞及授權，不包含 `.env`、DB 或私人資料。
- 正式 authority 仍依 ADR0077；[ADR0079](../../../adr/0079-target-rebuild-production-cutover.md) 只是 Proposed。不要把根部舊入口當成新產品啟動方式；沿 [後端 README](../../../../apps/api/README.md)、[前端 README](../../../../apps/web/README.md)核對。

### 除品質以外，仍未收尾的項目

| 項目 | 已成立 | 接手仍須處理 |
|---|---|---|
| T16 容量與 provider | 最新已確認 A／B1／B2 輪前 128K、完整 Step 間中途 160K；門檻與真 PG 恢復 70 項通過，先前另有 A 輪前真 Luna 壓縮／保存證據 | 新數值下三角色的有界真長旅程尚未驗。帳戶實測 200K token 額度不是模型 context 上限；不得盲重送超額請求或以離線通過代替真 provider。[最新證據](t16-compaction-continuity.md#10-owner-確認門檻校準2026-10-01) |
| Memory 最終失敗後再啟動 | 有界重試、最終失敗收尾、A 繼續訪談成立；**2026-10-01 已接線**：失敗後正式訪談再前進 6（三輪完成）才允許一次新批次，只以訪談進度為條件 | 政策待 Owner 核對（若要更嚴，可加冷卻或次數上限）；真長旅程尚未實際觸發過這條路徑。[T11 更新](t11-memory-batch.md#任務完成對照2026-09-30-恢復後) |
| T17 完整產品旅程 | 真 A、背景 Memory、保存／重開、UI／PDF 與來源換版各有代表切片 | 尚未收斂為完整 Luna 品質與旅程通過。最近長旅程收尾遇服務錯誤而安全失敗；正式資料不變、無 active 殘留，但不能當成功收尾。[有界收尾結果](t17-course-administrator-journey.md#2026-10-01luna-長訪談收尾的有界接續) |
| T18 正式交付 | 同源接線、非 editable 安裝／migration、中文 PDF 預驗及精確退役盤點已做 | 前置 gate 後，仍要共同切換根入口／workspace／CI／文件、精確退役舊碼並做最後交付驗證。未刪舊碼，未正式切換。[交付證據](t18-same-origin-web.md) |

PDF 已知次要限制：畫面可正確呈現中文，但部分字型文字層的複製／搜尋會出現部首字元；目前依 Owner 減法不加字型加工流程。沿 [T13](t13-pdf-export.md)記錄，不把它誤當匯出功能缺失。

### 品質問題：接手不要重新猜的證據

1. **跨輪事實的 JD 來源漏選，尚未解決。**出席紀錄新任務結合第 8 則早期事實及本次輸入（完成後序號 10），但模型只選 `current_input`。建立前已讀工作情境／工作理解正文及舊 JD 的第 8 則來源；寫入後又讀新任務及第 8 則原話，仍未補引。App 保存的是模型實際選擇，沒有證據指向來源漏存或錯誤 Context 組裝。[原請求索引與定位](t14-job-analysis-quality.md#2026-10-01早期依據在-context-與-memory-的位置)。**可見不等於完成語意核對；內部漏選原因仍未證明。**
2. **專業提煉／資訊精度仍須有限驗收。**既有 Luna 樣本曾有任務包太大、Memory 將模糊人數寫得較精確等問題；後續已有 K／S 保存、任務拆分及 B1／B2 更正成功例，不能說相關能力完全沒有，也不能把短例成功視為全面修復。沿 [T14](t14-job-analysis-quality.md)既有反例與 rubric，不另造品質平台。
3. **不要把已試過且證據不足的方案重做一輪。**來源說明、欄位順序、提高 effort、原生壓縮等已有有限診斷；部分沒有重現原拆分行為，不能當漏引修好。只看到引用可回查或 `needs_recheck=false` 也不能證明來源涵蓋充分。新試驗應有不同且可區分的假說、保留例及停止條件。

模型固定 **Luna／high**，Owner 因成本拒絕改用 Sol；不再追加 Sol 對照或自動 fallback。不能機械複製全部父項來源、App 猜補員工事實、加固定 reviewer 或放寬測試來結案。來源 gate 是否可以列為試用限制尚未獲 Owner 同意；交接不代表同意豁免。

### 建議接續方式與本輪邊界

先讀 [計畫](../README.md)、[任務表](../tasks.md)、本節，再按當前切片讀工程／分析／工具責任文件。直接從上述未完事項續作；既有通過證據可重用，不從 T01 重來、不全量重跑所有模型場景。

- 優先針對 Luna 既有來源反例研究／驗證一個有證據的新方向；沒有新假說就先做不受影響的容量、解阻或交付收尾，不堆 Prompt。
- 解阻接線先明確「什麼可觀察條件代表可再嘗試」，再沿既有 owner／限額實作；會改重試產品政策時帶建議核對，不每收到通知就解鎖。
- 真模型僅全合成、有界 manifest；憑證安全載入 `apps/api/.env`，不輸出。維持 OpenAI 直連及完整原生接續，不以縮短歷史掩蓋品質問題。研究遵守官方當前契約與既有規範，停止無收益的反覆試驗。
- 前置 gate 未過，不切正式入口或退役舊碼；通過後按既有 T18 清單完成，不新增部署平台。表面可用、API 成功、離線通過及產品品質分開交代。

本輪只核對 Git／文件並整理交接，**沒有修改產品、啟停 Demo、操作 DB 或新增付費模型呼叫**；沒有重新確認目前 Demo 程序與資料狀態，下方歷史 PID／port 不可直接當成目前狀態。交接者須先核對實际執行者及安全點，不強停正在使用的工作。Goal 不宣告完成，未新增整項驗收結果。

## 恢復後進度（2026-09-30 晚，新 Goal）

Owner 以新 Goal 恢復；上述暫停條件已解除，以下各節保留為暫停當時的紀錄。接手時核對：`target-rebuild` 工作樹乾淨、HEAD `e7cccda1`；遠端文件分支 `66bf718d` 的本頁與本機逐行一致（只差換行字元），沒有更新的交接。環境：測試 PG 在 loopback 55439（`caliburn_t01_test`），Demo 後端 8100 與前端 5173 仍在跑；PATH 上的 Node 22 不合前端 24.x 需求且 `corepack` 簽章驗證失敗，前端測試改用 Node 24 執行檔直接呼叫 `apps/web/node_modules/.bin`。

依下方「建議接續順序」推進：

1. **T08 預載超量的有界回退——已補**：[T08 §7](t08-consultant-turn.md#7-近期訪談預載超量的有界縮減2026-09-30-恢復後)（Red 23 failed → Green 38 passed；真 PG 整合與 10 檔回歸 1058 passed）。真模型回讀行為仍歸 T14／T16。
2. **T06／T07／T08 gate 已收斂並勾選**：逐條 Red 與 E／JDT／V 對照 [T06 §21](t06-agent-execution.md#21-任務完成對照2026-09-30-恢復後)、[T07 §5](t07-jd-tools.md#5-任務完成對照2026-09-30-恢復後)、[T08 §8](t08-consultant-turn.md#8-任務完成對照2026-09-30-恢復後)。收斂時補了兩個守門測試（28 個工具的遞迴 strict schema 檢查、模型工具路徑的任務／協作對象／共通條件刪除），並補做任務要求一直缺的**真 API compact 預檢**（[T06 §20](t06-agent-execution.md#20-真-compact-協定預檢2026-09-30-恢復後)：5 次 HTTP、零重試，遠端接受）。完整後端 **1847 passed、2 skipped**（跳過的是需字型的 PDF 渲染，歸 T13）。
3. **T09 已勾選**：最小離線腳本化模型＋4 個瀏覽器旅程，整套 e2e 21 passed（含先前無法驗的兩項「A 已准入」），見 [T09 旅程證據](t09-consultant-journeys.md)。Owner 同時提醒**不要過度設計、以核心分析效果為主**，因此測試基礎設施到此為止，不再擴增旅程或評測平台。
4. **下一步（重心轉向核心分析效果）**：實際檢視顧問的訪談與 JD 品質（T14／T17 的失敗模式：來源選擇、更正範圍、漏來源），以最小的 Prompt／工具說明／Context 改動加有界真模型驗證；其後 T10／T11／T12 收斂、T13 乾淨交付、T15、T16、T18。順序與進度見任務表，不在本頁重複。

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
