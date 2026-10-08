# JD 工作計畫：2026-10-08 獨立程式複核

**結論：第二次診斷後，限定範圍內未留下阻擋新 revision 凍結的實質 finding。** 本紀錄保留工程審查的時間順序，不代表模型品質。第一次審查時尚未啟動本批 paid run；後續 v1 pilot 中斷及第二次複核如下。v2 先導及使用者縮減為各一場的正式比較均已完成，實際結果與最終機制／語意稽核沿[工程與比較證據](jd-work-plan-2026-10-08.md)。

## 第一次工程審查

依據為 [施工計畫 T1／T3／T4](../2026-10-07-jd-work-plan-alignment.md)、[架構分工 §2.1](../../architecture/system-boundaries.md#21-長任務的元件分工)、[Plan 設計 §10.7–11](../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md#107-使用時機定位局部更新返回整體與交付核對)、程式撰寫規範及[新比較協議](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/protocol.md)。本輪實作及測試授權依主代理提供的有效使用者指示判讀，未把舊文件頭部的施工準備狀態當成未授權。

T1／T3 審查範圍為 `planning_instructions.py`、Plan 模型工具、對應工具／role 組裝測試，以及 `InterviewPlan.tsx`、Plan API 文案、元件測試及 E2E locator。共同顧問方法與 Plan 專屬能力分離，舊未知限定已移除；範例測試擷取實際工具 description，經 prepare／execute／read 檢查建立、局部替換與未受影響原文。UI 保持同份唯讀 SafeMarkdown、空值／候選／採用版區分。未發現需修改 Memory 或 Changes 的缺口。

T4 審查範圍為新比較目錄的 `controls.py`、`frozen_manifest.py`、`journey.py`、`materials.py`、`events.py`、`observers.py`、`review_policy.py`、`runner.py`、離線測試、oracle、披露政策與盲評判準，並唯讀追查重用的舊 guard／runner／observer。

| 已報反例 | 影響與最後修正 | 複核 |
|---|---|---|
| 已有 pilot 原件，但累計 ledger 遺失 | 原實作可回零帳務；現在只要已有 case／provider trace 原件而缺 ledger，就拒絕開始。 | 已關閉；檢查缺帳本反例及原件／manifest 雜湊核對路徑。 |
| 複合問題同時含可答、拒答或需澄清子問 | 原實作只輸出可答與未知，會省略拒答／澄清；現在逐項加入實際回答，並保留凍結拒答範圍。 | 已關閉；候選狀態仍待當次 accepted source 正式可見後採用。 |
| 正式場 Plan 工具拒絕，但已有非空 Plan | 原實作仍會開始下一付費案例；現在 pilot／formal 共用 `plan_tool_audit`，保存拒絕原件並停止後續案例。 | 已關閉；檢查非空 Plan＋rejected 的反例。 |
| 先拒談特定投訴，再問匿名滿意度一般流程 | 初次修正把整個 evaluations 主題封鎖；現在只允許固定 `sensitive-evaluation` 的公開流程與明確拒答原字串，保留拒答範圍，不預先標記整個 fact 已披露。 | 已關閉；審查者以 Python `-B`、零 provider 分別重現修正前失敗及修正後通過。 |
| A completed，但背景 Memory 已 failed | 原實作只擋 settlement timeout；現在 failed／cancelled／paused／timeout 均停止後續案例。 | 已關閉；檢查 gate 及代表性 failed 測例。 |

審查者另外核對：generation 沿正式定價元件的 272K 費率邊界；compact 沿保守 reserve；未知帳務及原件不符不允許歸零續跑。人工編修使用正式 HTTP，披露核對當次 accepted source_id，受控 45K 只在 official saver 已採用並回讀驗證 A within-Work C 後解除。兩組共同工具與 Changes 能力一致，P1 無 Plan 能力；匿名成品 bundle 不含 arm、Plan 或成本。

最後收到實作者回報：新目錄 **37 個離線測試通過、Ruff 通過、零 key dry-run 通過**。這些是實作者執行結果；審查者未重跑整套測試、PG 或 provider，只做程式／測試靜態核對及上述無寫檔的 Python 反例。最後政策文字與修正邏輯一致；rubric 指向本批 oracle 的 SHA-256 `7455f4ac308e87ab4371a7f8c281890d44628ccf7c8aa0c3162e7be3ce8ac636`，審查者已實際重算相符。

第一次審查當時尚待主流程凍結實際 manifest、完成施測前核查、pilot gate、正式配對與全部匿名結論鎖定後解盲。自然語言 substring、離線測試及本次審查均不能證明模型會有效返回、保住未入稿工作或提升 JD 品質。本檔放在計畫 evidence，不加入實驗 frozen 材料，也不建立額外 skill ledger。

## 第二次診斷與新 revision 凍結前複核

v1 pilot 的 P2 在同一 Turn 先收到兩次 `invalid_patch`，之後建立成功，並在 Turn 2 成功局部修改及採用全文；主流程在 Turn 2 後中斷。審查者依實際 trace、正式 HTTP 回讀及後續 request 核對，留下 [v1 未通過 receipt](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v1/pilot/mechanism-review.json)。它依當時 strict gate 判為 `passed:false`，且缺 P2 最終 result 與 Memory settlement；不能據此說 Plan 從未建立、整批策略無效或完整 pilot 已通過。未讀匿名品質評閱或擔任披露裁決；沒有觀察到 A compact，不假定已驗跨窗。

第二次限定審查涵蓋工具 description、原 trace 回歸 fixture，以及新 runner 的 `carry.py`、`frozen_manifest.py`、`runner.py`、相應測試、README 與 protocol。沒有改動 v1 frozen source、manifest、ledger、trace 或 receipt。

| 修正 | 獨立複核證據與界線 |
|---|---|
| 明確區分正文行與控制行 | `interview_plans.py` 只改 `_BODY_DIFF_GUIDANCE` 相鄰字串，明示 `@@`／`*** End of File` 不加前綴，點出 `+*** End of File` 錯字。審查者以 AST 排除該賦值後比對 v1，其他程式結構相同；parser、matching、正式 input／output schema bytes 未改。253 字 fixture 與第一次被拒的實際 call arguments 完全相同，修正僅移除 EOF 前的 `+`。實作者回報 Red 1 fail → 57 pass；審查者未重跑該整套測試。 |
| 同一研究續帳，不歸零 | 審查者獨立按原 trace 與 frozen pricing 重算，再核 `load_carry`／`verify_carry`／guard seed：US$0.040769275、49 generations、104 outbound、1,077,584 counted input、0 compact、0 未知 reserve；49 admissions 均有 received。新 manifest 鎖定 [中斷核帳原件](../../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v1/interruption-accounting.json)及其來源 hash，每次外送前核 prior bytes。缺 received、未知 usage／reserve、counter 不符或原件漂移均拒絕續帳。 |
| Fresh pilot 仍使用累計配額 | `phase_start` 保持累計零基點，pilot 的 160 generations 已使用 49，剩 111；總費用與其他用量亦累計。審查者以無寫檔 Python 核 seed 數值及達 160 時拒絕。新 revision 才建立新樣本，source snapshot 含新增 carry 與現行完整來源，先凍結再施測；本次複核沒有建立新 freeze 或外送。 |
| 新 gate 對齊正式 ToolRejection 契約 | 主流程已決定新版保留可恢復的模型輸入拒絕及未完成修改成本，避免反覆 fresh 至零錯造成選樣。有限 code 白名單只分類，不把後來成功視為所有意圖已修復；scope、保存、App capacity 及未知 code 仍停止。非空正式 Plan、pilot 建立／局部修改／正式讀回／後續全文採用、Turn／Memory 完成及既有能力／帳務 gate 仍保留。審查者唯讀執行新 classifier 對 v1 原 trace，得到 2 updated、2 recoverable rejected、0 fatal，並確認原 v1 receipt 仍為 false；這不追認 v1 通過。 |

實作者最後回報 **48 個離線測試通過、15 個頂層 Python 檔案 Ruff check 通過且 format unchanged、零 key dry-run 通過**（`credential_read=false`、`provider_calls=0`、`database_calls=0`）。審查者核對新增 formal／pilot 反例：可恢復拒絕原件保留，未知 code 即使 receipt hashes 相符仍拒絕；既有 Memory failed 反例保持。這些整套執行結果屬實作者驗證，審查者實際執行範圍為上述唯讀重算、AST／bytes／fixture 比對、seed 邊界及 trace 分類，未重跑 provider、PG 或匿名品質評估。

第二次複核當時，新 revision 凍結、完整 pilot 機制 receipt、正式比較與盲評交由主流程接續；後續已按使用者各一場的範圍完成，結果沿本頁開頭的證據入口。本次複核無新增阻擋 finding，也沒有以離線通過代替模型品質結論。
