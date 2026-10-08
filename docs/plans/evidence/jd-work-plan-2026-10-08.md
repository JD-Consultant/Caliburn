# JD 工作計畫：2026-10-08 工程對齊證據

依 [Accepted ADR0082](../../adr/0082-consultant-jd-work-plan.md)、[Plan §10–11](../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md#10-jd-工作計畫內容與用法)與[施工計畫](../2026-10-07-jd-work-plan-alignment.md)。T1／T3 工程及使用者縮減後的各一場比較已完成：Plan 的編輯與接續有實證，本對正式 JD **沒有可辨認的整體品質增益**。兩組皆有必要專業尚未探索的缺口，不由保存成功推定完整。成品、過程、限制及討論假說見[有限比較結果](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/results.md)；同版共同指引的 P1／P2 差異、合成回答、AI 匿名評閱及樣本界線統一由[實際比較方法](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/results.md#實際怎麼比較)說明。

## 實際效果與範圍

Plan 指引、read／edit 說明、V4A 範例及唯讀 UI 文案已對齊主要方向、目前焦點與剩餘訪談／分析／JD 整理工作。範例把盤點的未知改成已知待入稿工作並轉焦點到帶教，收貨與其他未知範圍逐字保留。共同顧問方法與 Plan 專屬指引仍分開；UI 稱「工作計畫」，保留同份 Markdown、未建立／刻意空／不可用及候選／採用版的區分。

原工具 wire、DB 表示、候選採用、原操作／captured request 恢復與壓後精確投影保持；Memory、Changes 及 JD 保存未改。T2 無施工項目，獨立 Changes 能力不作本計畫改造或比較前提。

## 驗證結果

| 層級 | 實際結果 | 證據支持的範圍 |
|---|---|---|
| T1 Red／baseline | **5 failed、50 passed** | 舊例仍以 A／B 待問呈現，缺新用途／可執行範例；既有純文字編輯能力已支持新正文，該部分為 baseline pass，不造人工 Red。 |
| T1 Green／EOF 反例 | **初版 55 passed；格式說明修正後 57 passed，1.55 秒** | 工具範例實際 patch／read roundtrip、局部原文保留、提示組裝及既有正文／契約反例。新測試使用先導原始 253 字輸入，確認錯誤 EOF 前綴拒絕且不保存，僅移除前綴後精確保存；回饋說明先有 1 failed／24 passed，再修正通過。 |
| 精確投影回歸 | **14 passed，1.26 秒** | 原 root／C 位置與精確 Plan 投影、既有邊界反例。 |
| 真 PostgreSQL | **46 passed，40.98 秒** | `test_interview_plan_context_binding.py`、`test_interview_plan_storage.py`、`test_interview_plan_http.py`；原能力／request、保存及 HTTP 相容回歸。未以缺配置 skip 算通過。 |
| T4 離線政策／dry-run | **新版 48 passed，2.69 秒；零 key dry-run 通過** | 主代理複跑所有頂層測試（排除凍結歷史 snapshot）；涵蓋初版 37 項與續帳、累計先導額度、可恢復／非可恢復拒絕分類的反例。未以離線結果判模型效果。 |
| T4 資料庫預檢 | **通過，provider_calls=0、credential_read=false** | 新 runner 的 `pilot --database-dry-run` 對真隔離 PostgreSQL 執行正式 HTTP 建檔、五項讀取、人工 JD 寫入及回讀；[receipt](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/database-preflight.json)記錄 schema `intplan_jdwork_preflight_e1c58a62`。這是 runner 入口預檢，不是 manifest 凍結或真模型比較。 |
| Web 元件／API | **9 passed／5 passed** | 工作計畫文案、Markdown、空值、候選／採用版及讀取 API。 |
| Web 靜態／建置 | **typecheck、四檔 ESLint／Prettier、build 通過** | 本輪受影響前端檔案及正式建置；Vite 仍有既有 500 KB chunk warning，未為純文案改動改拆包。 |
| 瀏覽器 | **4 passed，9.5 秒** | `interview-plan.spec.ts`：真隔離 App 建檔／idle GET；受控 status／plan 回覆驗證唯讀、折疊、刻意空及 completed／cancelled／failed 撤下候選、失敗／重讀。受控回覆不證模型執行資格或品質。 |
| 獨立工程審查 | **複核無未解實質 finding** | `/root/plan_implementation_review` 核對用途、範例、文案、續帳及新版 gate；已報反例與實際驗證層級見[審查紀錄](jd-work-plan-2026-10-08-review.md)，未以審查代替模型品質驗證。 |
| T4 正式有限比較 | **P1／P2 各一場、各 20 輪及 Memory 收尾完成；匿名結論為無可辨整體差異** | 兩案及配對先鎖定再解盲；共同未取得先到期先出、Excel 差異核對及重量判斷。完整原件、語意及機制稽核沿[結果](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/results.md)，不推論穩定平均效果。 |

本輪沙箱內非產品問題：async 測試受 Windows socketpair／loopback 邊界阻擋；typecheck 曾有依賴解析誤報。同一檢查在允許本機依賴與 loopback 的環境正常通過，因此沒有改產品來迴避沙箱限制。E2E 首跑缺 Playwright 預設 binary；後續重用匹配 Playwright 1.63.0、revision 1243 的本機 Chromium 153.0.8010.12，取得上述四項結果。

## 可重播命令與隔離環境

以下為本輪命令。重播需同一 lockfile／依賴環境與可用的 loopback PostgreSQL；不是資料處置或啟動另一個 product leader 的指令。測試目標是 `127.0.0.1:55448/caliburn_workplan_test`，使用無密碼的隔離本機測試身分 `caliburn`，無真員工資料或 provider key。pytest fixture 自建隨機 schema，不設定產品 schema。

後端命令的工作目錄為 `S:\caliburn\apps\api`，沿現有 `.venv`：

```powershell
& '.venv/Scripts/python.exe' -B -m pytest tests/unit/test_interview_plan_tools.py tests/unit/test_role_prompt_contracts.py tests/unit/test_interview_plan_body_edits.py tests/contracts/test_interview_plan_contracts.py -q -p no:cacheprovider
& '.venv/Scripts/python.exe' -B -m pytest tests/unit/test_interview_plan_projection.py tests/unit/test_interview_plan_projection_boundaries.py -q -p no:cacheprovider
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn@127.0.0.1:55448/caliburn_workplan_test'
& '.venv/Scripts/python.exe' -B -m pytest tests/integration/test_interview_plan_context_binding.py tests/integration/test_interview_plan_storage.py tests/integration/test_interview_plan_http.py -m postgres -q -p no:cacheprovider
```

前端命令的工作目錄為 `S:\caliburn`：

```powershell
pnpm --filter @caliburn/frontend test src/app/InterviewPlan.test.tsx src/features/interview/interview-plan-api.test.ts
pnpm --filter @caliburn/frontend typecheck
pnpm --filter @caliburn/frontend exec eslint src/features/interview/InterviewPlan.tsx src/app/InterviewPlan.test.tsx src/features/interview/interview-plan-api.ts tests/e2e/interview-plan.spec.ts
pnpm --filter @caliburn/frontend exec prettier --check src/features/interview/InterviewPlan.tsx src/app/InterviewPlan.test.tsx src/features/interview/interview-plan-api.ts tests/e2e/interview-plan.spec.ts
pnpm --filter @caliburn/frontend build
```

瀏覽器測試對本輪自有 API `8108`，沿 build 提供同源 UI；API 使用隔離 schema `workplan_ui_20261008`，與 pytest 隨機 schema 分開。驗證收尾已核 CIM command line 後停止無 key 的 UI backend launcher／server（PID 10008／15480），兩個 PID 與 `8108` listener 均確認不存在。PostgreSQL `55448` 是本機原生 cluster `tmp/jd-work-plan-pg-20261008-6d1f/data`，續供本次付費比較後已正常停止，資料保留；既有 product 程序未重啟。若重播需準備隔離 App，沿 [API 初始化與啟動](../../../apps/api/README.md)及 [runbook](../../runbook.md)指定測試 DB／schema，不使用產品資料庫。瀏覽器執行檔只適用於本輪已核版本：

```powershell
$env:CALIBURN_E2E_BASE_URL = 'http://127.0.0.1:8108'
$env:CALIBURN_E2E_CHROMIUM_PATH = 'S:\caliburn\.research-tmp\chromium-153.0.8010.12\chrome-win64\chrome.exe'
pnpm --filter @caliburn/frontend exec playwright test tests/e2e/interview-plan.spec.ts --reporter=line --output=../../tmp/jd-work-plan-e2e-20261008
```

## T4 前置驗證與付費先導證據

T4 已補零 provider 的資料庫預檢；從 `S:\caliburn` 重播下列命令只驗 HTTP／DB 入口，不讀模型憑證、不凍結 manifest：

```powershell
$env:CALIBURN_JDWORK_TEST_DSN = 'postgresql://caliburn@127.0.0.1:55448/caliburn_workplan_test'
& 'apps/api/.venv/Scripts/python.exe' -B docs/experiments/product-validation/jd-work-plan-comparison-2026-10-07/runner.py pilot --database-dry-run
```

runner 的[獨立複核](jd-work-plan-2026-10-08-review.md)與前置驗證完成後，`comparison-v1` 的[manifest](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v1/manifest.json)已凍結，SHA-256 為 `67adcafb850faa136b9a16e123e21b3cebdf86e26eff5fbafd1c5a253bed8554`。US$4.00 累計 guard 涵蓋 pilot＋formal；版本變更保留已付費帳務，不將先導花費另開帳歸零。

**comparison-v1 pilot 已停止，gate 不通過，formal 零場。** P1 六輪及 Memory 收尾完成；P2 只有兩輪 completed，但兩輪正式 Plan 均非空。P2 首輪兩次 `invalid_patch` 的實際輸入將結束標記寫成 `+*** End of File`，第三次移除 `+` 才成功；後來成功不能抹除拒絕，依本批 gate 停止，不作有效正式品質樣本。這是格式可靠性的反例，不是 Plan 皆未建立或未採用。

[獨立機制審查](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v1/pilot/mechanism-review.json)確認成功建立及正式回讀、次輪局部 patch 保留其餘方向，以及下一輪實際 request 採用前輪精確 Plan 全文。P2 全場／完整 Memory 收尾未驗；本 pilot 亦未形成 A within-Work C，不宣稱壓後投影、有效返回或品質增益由此通過。精確下一輪全文只證明資料已提供，不證明模型已正確理解或使用。

中斷後的原 trace 與累計用量核對沿[interruption-accounting](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v1/interruption-accounting.json)；本頁不建立第二份帳務 ledger。格式說明已區分正文行與控制行，解析器與 wire 不變。新版 gate 保留可恢復的模型輸入拒絕及負擔，避免只留下零拒絕樣本；仍核建立、局部修改、正式回讀與後輪全文，並在資料、保存、執行或帳務故障時停止。判準變動在新版外送前明載協議，原失敗版本及全部原件保留，不回填 pass。

`comparison-v2` 的兩場 fresh pilot 及[獨立機制審查](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/pilot/mechanism-review.json)已通過。兩組各六輪 completed、Memory 各七批 completed；P2 六次 updated、零 rejected，六份實際 diff 重放均等於正式 Plan，Turn 2–6 首 request 均含前輪精確全文，審查鎖定 30 份原件。兩組均無 A compact，因此先導不證明跨窗或語意效果。

**正式比較依使用者指示縮為各一場。** 原凍結協議排八場；倉儲 `warehouse-r1-P1`／`warehouse-r1-P2` 各 20 輪與 Memory 收尾完整完成後，使用者明示「共 8 場 太多太久了」「各一場就好 然後就可以詳細討論了」。營運側隨即停止 session 88124（exit 1），不再外送新案例；已啟動的 `course_admin-r1-P2` 只完成 Turn 1–4，保留為使用者中止紀錄，不列完整品質樣本。匿名裁決者同步停止，最後已提交 ID 為 `dd84453002894777a9d7fdf51c4ca795`。此縮減依使用者時間偏好，發生於營運側尚未讀取匿名品質結論前，不是按表現淘汰案例；原八場協議、manifest、已提交裁決及全部失敗／未完成原件保留。

有效品質範圍只有上述倉儲一對，兩份匿名成品及配對結論已鎖定後解盲，22 個相關檔案雜湊核對無差異，[解盲原件](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/unblinding.json)記錄對應。過程先以公開事件鎖定 11 項機會清冊，再讀 Plan，語意與機制稽核均完成。未執行的其他職務、第二配對條件與專設 45K 換窗觀察不得補稱通過；自然形成的三次 C 均為 pre-work，P2 壓後全文接續有實證，within-Work C 未形成。停止後已確認無本批 Python runner；核對自有 PostgreSQL PID 33860、精確 data 目錄及 port 55448 後正常停止，資料保留。

[新 manifest](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/manifest.json) SHA-256：`dacbb5d73dc849f56e3caed51a870a10653faab46e4c608128e6cbad41d0277b`。它承接 v1 已知 US$0.040769275 與所有用量，總額仍為 US$4.00，pilot 配額也不歸零。先導終了的累計費用為 US$0.104748280、125 generations、266 outbound、2,918,421 counted input，無未知 reserve。這是新樣本與新判準，不追認 v1 為有效完整 pilot。

使用者縮減後的最終帳務沿[中止核帳原件](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/interruption-accounting.json)，SHA-256 `a6d223c9765d0160fc77f62fe17175c1ef14a8f13257bdf3f771002874434679`；原 ledger 保持最後完整案例狀態，不當成中止後總額。逐 attempt 重算的累計已知估算為 US$0.711882955，另保留一筆未收到結果的 Memory 外送 reserve US$0.010732500，占用 US$0.722615455；不因停止程序而釋放。累計 614 generations、3 compacts、1,330 outbound、32,636,404 counted input 與 raw witness 一致。完整正式 P1 為 US$0.263589565、P2 為 US$0.320582750；部分課務案例已知 US$0.022962360，其餘是兩版先導。以上是凍結費率的用量估算，不是 provider 發票。

新 driver／材料及原排程沿[新比較協議](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/protocol.md)保留；使用者縮減後的比較已完成。本對兩組都依公開新線索返回盤點並成稿；P2 可保留已知待入稿及待修正，但未形成跨輪打斷後靠 Plan 回收的情境。兩組最終 JD 未呈現可辨整體差異，不能宣稱 Plan 穩定減少漏項或降低負擔。原 ADR0081 八案是歷史依據，不沿用為新方案結果。

正式批次首次人工改稿事件 `a0360959e6c249a096ce59b09d34fc63` 中，匿名裁決者已先決定公開語意，但政策未列回傳 JSON 欄位而請求補充。營運側僅轉述凍結 `events.py::manual_command` 的既有 `revise_task`／`create_task`／`no_op` 契約；未提供 arm、Plan 或 oracle，未更改語意規則或程式。此格式說明缺漏保留為施測限制，不冒稱材料從未需要澄清。
