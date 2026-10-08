# 選問優先順序：隔離有限 probe 的接線與執行門檻

本候選已完成離線 guard 與凍結路徑準備，沒有真 PG、API、provider 或分析品質結果。正式施測由主代理管理；須先鎖定原八場及四份品質判讀，再在原費用授權內執行。研究假設、唯一 315→471 bytes 替換及判讀沿[候選協議](2026-10-07-priority-candidate-protocol.md)。production、指南、原 harness 均未改。

## 接線與資料界線

- [core](priority-probe-core.py)重用原 INTPLAN transport／有限 guard，繼承原 spent、兩筆未知預留及全部累計 counters。不是新的 Agent loop 或通用平台。
- [runner](priority-probe-run.py)重用前批 `seed_case`、`test_client`、原 SDK、原 Writer／ConsultantRunner、固定公版 fixture 及原 HTTP source reader。新 input 真正 POST `/api/job-files/{id}/inputs`，停用背景 dispatch，明確 claim 同一 execution writer，再由原 Runner 完成正式提交；JD、原話及固定 revision/source_ref 都由正式 HTTP 讀回。ASGITransport 是本機 HTTP 接線，沒有另啟公開 socket。
- 每格的新 App job file／schema／ID 由 App 或 harness 產生，模型沒有收到 case/arm/repeat/判準/private answer labels。三案可見起點機械共用原 prefix、JD、來源與空 Memory；兩組 notes 均關閉，保留同一 FOCUS、公版與工具。B1 只在新程序內綁定唯一 instruction bullet，檔案不改。
- 六案兩 arm 兩 repeat 共 24 格；探索三案各最多三段、unknown/refused/excluded 各一段，最多 48 個完成的正式顧問回覆。repeat 1 B0→B1，repeat 2 B1→B0，不挑成功結果重跑。
- 私人答覆只放 `manifest.reply_policy` 與匿名 `review-input/<opaque>.json`，供回答者判問句語意。packet 的 `answer_policy_rule` 提供已凍結 `reply_policy.rule` 原文，包含只有中立詢問該面向才可提供 target、超出已知資料用 unknown 的原政策；相同政策適用兩組，不是 keyword 自動注入，也不在第 n 輪主動披露。最後一段不再選未使用答案。只有實際 POST 且完成後正式原話存在、source_id 不在送出前 originals 的回答，才保存 `submitted-selection` 來源資格。
- 完整私人答案字串／private labels 的 byte fence 只驗可辨識的字串洩漏，不能證明所有片段或語意洩漏均不存在。初始 request 的可見原話、JD、Memory、公版仍需人工核對，不以此 fence 作品質評分。
- `review-input` 與 `blind-quality` 都用隨機 opaque 檔名，移除 arm/repeat/case key；private trial↔opaque map 另存每格。每格首次 input 前經正式 HTTP 保存 `formal-jd-before.json` 及其固定引用內容；品質包含 `starting_formal_jd`、起始固定 sources、前後正式 JD、實際問句／員工 originals，供評閱既有內容保留與來源。私有 `assessment` 只進匿名品質包：原四案沿原 `cases.json` criteria，三探索案 target 保留原私人答覆全文及未知限定；拒答／排除各依本 protocol 的明示界線，沒有挪用錯儲位判準。它不是已披露原話，未在實際 originals 取得的 target 不算已發現或有據入稿。公開 cases 不含 label/criteria，seed 只取公開可見材料；回答者不讀對照身分，品質評估在全部有效輸出封存後進行。

拒答 fixture 只有明示員工原話「搬運方式這一塊我不想回答；其他工作可以談」，沒有補造先前顧問問句。排除 fixture 也只是明示員工原話，沒有偷偷加入其他未知答案。

## 容量校準與有限成本

[原 24 段實測 §5](results.md#5-用量與原界線)是 96 次 generation＋104 次 count（共 200 次外送），1,502,916 usage input、69,864 output，含階段間判讀 17.45 分鐘，占用估算 US$0.073042255。因此 48 回覆的平均尺度約為 192 gen／400 out／34.9 分鐘，這只是前批比率外推，沒有保證本候選會用相同工具或時間。

主代理在凍結前於 2026-10-07 核准容量調整為新增最多 **256 gen／600 out／16M counted input／8 compact**、首次 outbound 准入後 **45 分鐘**，並取絕對截止 `2026-10-07T08:30:34Z` 較早者。計數 token 與 provider usage input 是不同量，不以 1.50M usage 推定 counted cap。等待回答判讀、失敗與分段均不重置。保守 native compact 預留約 US$0.7875 起，可能因 US$0.50 probe cap 提前被拒，有限結果照實留存。

probe 新增 occupied 最多 US$0.50；原八場＋probe 累計 occupied 最多 US$8。限額為 `min(8.00, prior_occupied+0.50)`，原兩筆預留永不釋放或轉成零。每次 count 先加 US$0.0001 的既有研究保守估算；它不是官方 count 單價。generation／compact 沿原 pricing reserve、實際 usage 結算及未知用量保留，SDK/product 每 request 只准一次 attempt，沒有新 retry 引擎。

新程式約 50–65 KB 存 S；凍結來源原始 bytes 約 1.53 MB（壓縮後較少）、24 格結果及 trace 全存 C。依 16M counted cap 和重複 request 序列，C 先保留 250 MB 即有餘裕；這是資源估算，不是實测 trace 大小。唯一新 schema 在已確認自有 `caliburn-intplan-postgres-20261007`、ID `13cf811f4c8bf4ff395339fbdf89e6f444971d3fd718fddb84862c68580c07ee`、`127.0.0.1:55447/caliburn_intplan_test`。execute 會先核 name/id/running/port/user/db，不能轉用舊容器或 55441。保留 schema、失敗與 lease，不自動刪資料或重啟服務。

## 原主線完成及品質鎖定的 carrier

主代理提供最新正式 `final ledger`（原 batch-state shape）及新 JSON lock。runner 不讀主線 blind bundle／JD／notes；品質判讀檔只核 bytes hash。lock 的 shape 為：

```json
{
  "all_quality_locked": true,
  "ledger_sha256": "最新正式 final ledger 的 SHA-256",
  "case_ids": ["warehouse-r1-P1", "warehouse-r1-P2", "course_admin-r1-P1", "course_admin-r1-P2", "warehouse-r2-P2", "warehouse-r2-P1", "course_admin-r2-P2", "course_admin-r2-P1"],
  "reviews": [
    {"path": "第一份已鎖品質判讀絕對路徑", "sha256": "其 SHA-256", "locked": true},
    {"path": "第二份已鎖品質判讀絕對路徑", "sha256": "其 SHA-256", "locked": true},
    {"path": "第三份已鎖品質判讀絕對路徑", "sha256": "其 SHA-256", "locked": true},
    {"path": "第四份已鎖品質判讀絕對路徑", "sha256": "其 SHA-256", "locked": true}
  ],
  "inherited_guard": "原已核 carrier 的完整 guard object，須含兩筆未知 reserve"
}
```

`inherited_guard` 實際是 JSON object，示例用文字提示避免捏造主線用量。ledger 的 `all_scheduled_cases`、`completed_cases` 都必須恰好含八個指定 case；四個 review path 要相異、locked 且 hash 一致。prior accounting 要有限非負、occupied=spent+reserve；最新 ledger 不得減少原 consumption/counter 或修改原 reserve。prepare 將 ledger、lock、材料、來源、工具、模型、runtime 全部 hash 凍結；execute 及每次外送核對。permanent 全局 execution lease 拒絕並行、reset 或第二次 execute。

## 主代理的去敏命令

repo root：`S:/caliburn`。以下不含 key 或 DB password。`$priorityFinalLedger`、`$priorityQualityLock` 必須先填主線實際完成及鎖定後的絕對路徑，不能使用 offline mock artifacts。

離線規則測試及無 carrier 的 fail-closed dry run：

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest docs/experiments/product-validation/data/jd-question-selection-2026-10-07/priority-probe-tests.py -q -p no:cacheprovider --tb=short
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/jd-question-selection-2026-10-07/priority-probe-run.py dry-run
```

原八場與全部品質已鎖後，先檢查 carrier，再凍結新的正式 probe；這兩步没有 PG/key/provider：

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/jd-question-selection-2026-10-07/priority-probe-run.py dry-run --ledger $priorityFinalLedger --quality-lock $priorityQualityLock
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/jd-question-selection-2026-10-07/priority-probe-run.py prepare --ledger $priorityFinalLedger --quality-lock $priorityQualityLock --name priority-probe-01
```

主代理工具審查後才執行的 exact command（本子代理未執行）：

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/jd-question-selection-2026-10-07/priority-probe-run.py execute --name priority-probe-01
```

所有產物根為 `C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/question-priority-probe`。回答者只讀 `priority-probe-01/review-input/*.json`，依中立問句語意選答，將下列新檔寫到 `decisions/<相同 opaque>.json`；文件要先完成再以原子 rename 發布，避免 runner 讀到半份 JSON。

```json
{"question_quote":"完整原問句，不改字","answer_kind":"target_answer 或 normal_clarification 或 unknown 或 stop","reason":"判問句語意的具體理由","review_method":"semantic_review"}
```

runner 必須完全匹配 question quote，取得檔案 hash，才向 HTTP 提交對應固定答案。`stop` 不再提交；`unknown` 用固定未知答覆。檔案有壞 JSON 或不符政策即停止，不猜答案、不放寬判準。

## 離線證據與未驗範圍

第一批唯一替換、reserve/counter 不重置、unused selection 不成來源及實際匹配來源的四項有缺行為 Red→Green。後續時間及 `.strip()` 兩項曾實際失敗，修後 Green；凍結前核准的 45 分鐘／256 gen 調整也先以舊 30 分鐘／128 gen 失敗再驗新值。pytest Windows tmp fixture 的 ACL 失敗屬環境，不計為機制 Red；改用普通 mkdir 權限、保留小型 C fixture。

目前 24 項 offline 通過，包含原 17 項與本次 count 接縫的 7 個案例，以及真 prepare 函式：使用明標 mock carrier，屏障會在任何 key/DB 接縫呼叫時失敗，實際凍結 403 檔並核 manifest；三份內容責任指南、`apps/api/pyproject.toml` 及 `apps/api/alembic.ini` 的列表與 hash 都有斷言。新增反例先因公開 cases 帶 case label 失敗，修後驗 labels/criteria 不進公開材料或合成 request，品質包同時含原始四案／兩界線判準、原答覆限定與前後 JD，能供既有內容保留比較；不是語意品質評分。指南只作分析責任來源保存，不送模型；目前 `migration_config()` 是 `Config()` 加 `caliburn:migrations`，不讀 ini，ini 保存為操作設定來源。`offline_only:true` 的 execute 必拒，沒有 lease／started／provider。下一輪純離線重跑會產生新 opaque 準備目錄，不覆寫先前證據。

獨立接線審查另確認有效 count 跨 counted-input cap 的核帳缺口：FakeCountTransport 已回 HTTP 200、`input_tokens=2`，起點 16,119,999、cap 16,120,000，原 guard 於加入最後消耗前拒絕，transport 亦於 trace 前中止。實際行為 Red 為 `(counted_input=16119999, count trace=[])`，但已完成消耗應為 16,120,001。修正只在新 `ProbeGuard.count` 的既有超 cap 拒絕接縫保留有效 tokens，新 `ProbeTransport` 補留該筆 count trace及停止時的累計，再傳播原停止；原 guard／主線凍結 source 均未改。超 cap 仍立即終止，後續 generation 外送為零；ledger如實記 cap+最後有效count，不把它裁成cap。正常 count 仍只入帳／記錄一次；boolean、負數、字串、非整數與 null 的無效 count 均沿原驗證拒絕，沒有有效 count trace或 generation。已停止 guard 重呼 count不再增加消耗。這不是新增費用或分析規則，24格／48回覆、原 reserves、counter上限、45分鐘與絕對deadline均未調整。

有界靜態審查另找到回答 packet 缺少原 `reply_policy.rule`：只讀 packet 的回答者可能對「所以你都是在冷藏區做嗎？」這類預設答案問句，依單純語意選 `target_answer`，而現有 `validate_selection` 只驗原問句／理由／語意評閱聲明，仍會接受選擇。修正僅將原完整 rule 接到 packet；實際 packet 行為測試先因缺欄位失敗、修後通過，不增加語意 validator、不改固定答案或分析規則。中立性與答案選擇仍由同一回答者政策判讀，程式沒有因此取得語意品質保證。

審查範圍是新 `core`／`runner` 與必要既有接縫：舊 driver 的 `test_client`／`seed_case`／公版 fixture、原 `collect_sources`／guard、現行 Runner 的指引組合及 context capture。逐段核過 private target／criteria／labels 的材料流、等待及正式 source 資格、C 輸出根、原 Selector portal 與自有 55447 DB 接線；沒有讀主線品質包、JD 或筆記。除上述已修的 packet 政策缺口，沒有在未經修改的凍結材料之正常執行路徑找到另一條私人資訊直送或 unused 答案作為原話來源的接線。這是靜態判斷，真 PG／SDK、實際 initial request 及回答者是否遵循政策仍待正式有界施測驗證。

尚未驗新的真 PG migration/HTTP/portal 路徑、真 SDK 流、實際 source chain、真人/模型回答者或品質。既有 Runner／SelectorEventLoop／source reader 機制可重用，但新接線沒有因 offline Green 自動變成正式施測通過。正式品質與效果只由本 probe 後續保存的原件及盲評判定。
