# 新比較 runner 的操作入口

本目錄依 [protocol.md](protocol.md) 執行新工作計畫比較，重用舊官方 HTTP／PG runner、費用 guard、正式來源收集與已修正 stream ownership；舊實驗原件保持原樣。新材料、指引與實際 ordered tools 一起凍結。這個入口沒有模型評分器，沒有自動重跑，沒有整批時間截止。

在 `S:\caliburn` 執行，沿已配置的 `.venv`。本環境 Windows sandbox 的 asyncio socketpair 會卡住，async runner／pytest 用已核准的 sandbox 外執行；這不改 runtime。下列資料庫為本輪自有 loopback `_test` DB，新案例各用 `intplan_jdwork_*` schema；不清除舊資料。

```powershell
$env:CALIBURN_JDWORK_TEST_DSN='postgresql://caliburn@127.0.0.1:55448/caliburn_workplan_test'
& apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/jd-work-plan-comparison-2026-10-07/runner.py pilot --dry-run
& apps/api/.venv/Scripts/python.exe -m pytest docs/experiments/product-validation/jd-work-plan-comparison-2026-10-07 -q --basetemp docs/experiments/product-validation/jd-work-plan-comparison-2026-10-07/.pytest-tmp
```

由主代理做真 PG 零 key 預檢；這只使用正式 HTTP 建新檔、讀空態、人工新增 task 與正式 revision 讀回，不啟 listener、不讀 key、不呼叫 provider：

```powershell
& apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/jd-work-plan-comparison-2026-10-07/runner.py pilot --database-dry-run
```

待工程／協議已完成、獨立審查沒有阻擋問題、主代理核對當前費率與有效本輪授權後，凍結新研究。費用為 US$4.00 上界，pilot＋正式同帳，不把舊批餘額帶入；可設定更小上界，入口不能自行加大。`authorization-reference` 記有效使用者授權與主代理採此較嚴上界的來源，不能用這個參數創造授權。

```powershell
& apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/jd-work-plan-comparison-2026-10-07/runner.py pilot --batch-name comparison-v1 --freeze-only --limit-usd 4.00 --authorization-reference '本輪使用者開始實作測試與歷史真API授權；主代理核採US$4上界'
```

輸出在 `runs/comparison-v1/manifest.json` 及同層 source-snapshot；此步不讀 key或外送。freeze 後所有 top-level Python／材料／協議或 production source bytes 改動都會阻止外送。後續不再帶 limit／authorization 參數。

```powershell
& apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/jd-work-plan-comparison-2026-10-07/runner.py pilot --batch-name comparison-v1
```

pilot 兩組各一场、最多六 Turn，必須完成正式採用與 Memory 收尾。任何 Plan read／edit 拒絕、P2 全場沒有正式非空 Plan、Turn 不成功或 Memory 不成功／收尾逾時，都停止下一個付費 case並保留原件。單次 Turn 觀察700秒、Memory180秒、語意裁決300秒；批次用固定場次、Turn、成本／用量限制，沒有日期截止。

營運操作者只管理原件、HTTP／provider／checkpoint 與帳務。另用沒有繼承 arm／Plan／成本脈絡的匿名裁決者（例如 `fork_turns="none"` 的專用代理），只授 [disclosure-policy.md](disclosure-policy.md) 與 `reviews/<opaque>/pending.json`。runner 每次列印匿名 pending 路徑。裁決者以暫存檔完成 JSON 後原子移至同目錄 `decision.json`，不得讀營運目錄或另一組原件。

員工裁決 `review_kind=employee_disclosure`：

```json
{"question_id":"pending中的id","mode":"answer","fact_ids":["refund"],"reason":"一般流程可答，特殊情境未知","subquestions":[{"quote":"退費流程？","mode":"answer","fact_ids":["refund"],"reason":"相關且可取得"},{"quote":"特殊情境是否普遍適用？","mode":"unknown","fact_ids":[],"reason":"凍結oracle未提供"}]}
```

純拒答或 compound 的拒答子問帶 `refused_topic:"evaluations"`；未知／拒答／澄清不放任何 fact_id。無問題為 `no_question`，有界提醒後仍無主動推進即共同收束。未知與拒答不可透過 keyword 放行。只有當次 HTTP accepted source_id 在正式員工原話可見才更新披露狀態；selected、未送 cue 或歷史同句原話不能充數。

人工改稿裁決 `review_kind=manual_jd_edit`，只見匿名目前 JD、初始公開原話及固定文字：

```json
{"question_id":"pending中的id","action":"revise_task","task_id":"目前JD的task_id","description":"包含pending.required_text並保留其他有效細節的局部描述","reason":"按公開初始分工修訂"}
```

等價改用 `action:"no_op"`、reason；無相關 task 改用 `action:"create_task"`、title、description、reason，保持 area_id=null，不捏造 identity。此事件在第10 Turn completed後、下一次員工輸入前發生；未達時點或已收束記未發生。正式 command、原 revision、前後差異與保存结果留在 case。

pilot 完成後，主代理根據實際 Plan 建立、至少一次局部 patch、正式讀回及後續 Turn 使用原件，保存 `runs/comparison-v1/pilot/mechanism-review.json`：

```json
{"passed":true,"plan_local_patch_verified":true,"plan_next_turn_use_verified":true,"artifact_sha256":{"warehouse-r1-P2/provider-trace.jsonl":"實際sha256","warehouse-r1-P2/formal-plan.json":"實際sha256"},"limitations":"依實際觀察填寫；不以pilot推定有C"}
```

沒有實證不能填 true。只有 gate與累計帳務完整才可正式八場；任何已付費跡象而 ledger缺失、原件變動、保留未知 reserve或guard停止均拒絕歸零續跑。

```powershell
& apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/jd-work-plan-comparison-2026-10-07/runner.py formal --batch-name comparison-v1
```

四對全部保留；匿名成品放同一 `runs/comparison-v1/blind-input/`，只含正式JD、員工原話、固定來源及必要公開人工改稿脈絡。`blind-map.json` 留營運側，全部品質結論鎖定前不解盲。實際C／同位置Plan projection沿 checkpoint與provider原件判斷；未形成情境記未觀察。中斷不發 fresh 答案重播，本入口不提供自動恢復或重設帳務。
