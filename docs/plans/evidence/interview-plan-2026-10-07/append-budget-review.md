# 追加批次額度承接：獨立機械審查

範圍是 `append_batch.py`、`diagnostics/test_append_guard.py`、原 `manifest.py`、`guard.py`、共用 transport guard 與批次建立 guard 的接線。只讀程式、離線 fixture 及原 manifest 的 `frozen_at`／`limits` metadata；未讀 case 內容、訪談、組別輸出、最終 JD 或執行 console。未呼叫 provider、未更改凍結原件或原 phase。

原六項界線仍為 US$8、4 小時、1500 次 generation、16 次 compact、3500 次 outbound 與 40M counted input；另外正式每場仍最多 20 Turn。原 manifest 時間為 `2026-10-07T05:30:34.296467+08:00`，加四小時是 `2026-10-07T09:30:34.296467+08:00`。追加程式的固定 UTC deadline `2026-10-07T01:30:34+00:00` 比此早約 0.296 秒，沒有因常數本身延長時間。此審查不把候選 CPython `3.14.8` 字串 guard 當作 runtime 已驗證。

| 界線 | 承接方式與已核機械結果 |
| --- | --- |
| US$8 | 原 spent 及每筆 retained reservation 轉為 Decimal，重算 occupied 必須與原值一致。新生成 settlement 不釋放舊 unknown reserve；occupied 已滿時新生成拒絕。 |
| 4 小時 | 用原絕對 deadline 減當前 wall time 取得剩餘時間；下述起點取樣缺口已以入口 monotonic anchor 修正並獨立覆核。 |
| 1500 generation | 原 generations 複製進新 guard；等於設定上限時 admit 拒絕，包括後續 retry 的新 attempt。 |
| 16 compact | 原 compacts 複製；離線將既有值設成 16 後，新的匹配 compact admit 拒絕。舊 input count 不沿用，fresh case 須重新 count。 |
| 3500 outbound | 原 outbound 複製；離線將上限設為既有 77 時，新的 outbound_attempt 拒絕。 |
| 40M counted input | 原 counted_input 複製；等於設定上限時新正數 count 拒絕。 |

`prior_evidence()` 在讀取新批前比對 interruption audit 與原 journal 最末記帳欄位，並核原 source hash 與 formal LIMITS；新批再用新 freeze 的 `verify_frozen` 限制外送。這是程式接線審查，沒有讀取含訪談內容的 case journal，不能宣稱本次已獨立重算該 journal 全部 provider 用量。

現有四個 carry 離線測試實跑 `4 passed in 1.78s`。另外零外送 inline probes 實核：outbound 上限、compact 上限、occupied USD 上限、剩餘 deadline 到期均拒絕；新的已知 settlement 後仍保留 `original-unknown` 的 Decimal reserve。這些 probe 只用診斷 fixture，不建立產品訪談，也不宣稱候選 runtime 或 paid continuation 已通過。

## 起點取樣反例與修正狀態

原 `carried_guard` 先取 wall time 算 remaining，建立 guard 後才以另一個 `clock()` 值設定 started。離線將 guard 建構包成 wall／monotonic 同時前進 120 秒：原剩餘 90 秒，建構完成時已超過原 deadline 30 秒，但新 outbound 仍被接受，`started=220`、`seconds=90`。這證明建構／排程暫停會被補回可用時間，不符合原絕對截止界線。

已將精確反例傳 root 與 tools。tools 的窄修在函式入口、取 wall time 之前先取 monotonic anchor，最後使用同一 anchor 作 started；建構及承接期間的耗時計入原剩餘時間，並加入 construction-delay 測例。

修正後獨立重新讀取程式，實跑五個 carry tests，結果 `5 passed in 1.76s`。再以原先完全相同的 wall／monotonic 前進 120 秒 probe 回歸：現在 `started=100`、`seconds=90`，已超原 deadline 30 秒的新 outbound 正確拋出 deadline 錯誤。原機械 Red 已成 Green，起點缺口關閉；這不等於候選 runtime、paid continuation 或八場產品品質通過。

root 隨後授權重新監看匿名 disclosure queue。judge 已準備依原 SHA256 `dc770d1aa82d8b2d606848aeb8a3f3446cd7304ecbd1b52a08c759042df188c3` 政策核定 fresh case 待答題目；舊 decision 不改寫，不讀新 batch console、case、arm 或最終 JD。

## 後續補足批次的離線 metadata 審查

root 後續通知總界線改為 US$8／3000 generation／7000 outbound／180M counted input／32 compact／絕對 `2026-10-07T04:30:34Z`；原批仍依舊 cap 停止，必須完成 finally 及 server 關閉後才能啟新批。這是新的補足批次範圍，不回寫原凍結界線或原批證據；原已完成 closure 場次必須保留，不因品質重跑。

當時 `diagnostics/completion_batch.py` 只有 `remaining_cases` 和 `validate_accounting` 兩個離線 helper，尚無 provider entry point。實跑相應 tests 為 `22 passed in 0.03s`。已核記帳必須非負有限、四個計數為非負 int 且排除 bool、累計 spent 與計數不得倒退、每筆 inherited unknown reserve 精確保留；選案以 closure_submitted 加最後 completed 狀態判斷，不讀品質欄位。

另以零外送 inline probe 找到外層 completion evidence 的型別缺口：`remaining_cases([])` 與 `remaining_cases('')` 都回八個全未開場場次，沒有拒絕錯格式的未知證據。已向 root／tools 提供實際 Red；tools 在既有 helper 入口核 dict，加入空 list／string／None 反例後窄修。獨立重新讀取程式並實跑目前 tests，結果 `33 passed in 0.42s`，包含 mapping、carry、deadline、cap 與 USD cases。型別缺口已關閉。

當前 supplement `carried_guard` 使用入口 monotonic anchor、上述絕對 deadline、原 spent／所有 reserve／四 counter；並在建立 guard 前拒絕任何已滿的新 cap 或 US$8 occupied，沒有把舊已消耗額度重設。source／journal 與前批已停止閘仍待完整 entry point 接線覆核，未冒稱這些已 Green。匿名待答題保持優先，審查期間沒有 provider 呼叫或修改 frozen source。

## 磁碟中斷的精確承接與完整入口覆核

後續原批因 S 磁碟已滿而中斷，並非依原 cap 自然完成。root 要求保留原件、已完成 closure 與所有 unknown reserve，將新輸出改放核准的 C artifact 根，原 source、guide、production 與原 phase 不改。匿名 queue 在此期間停止，未把等待視為新外送授權。

獨立只抽取 journal 的記帳欄位重算，未輸出 request、回答或 JD。兩份 journal 分別有 743 與 256 個有效 JSON rows；合計 admitted 315、received 315。全部 journal 重建得 generation 350、compact 1、outbound 761、counted input 17,328,720；原 finally state 為 351／1／762／17,328,720，故精確未記錄差額是 generation 1、outbound 1、input 0、compact 0。相對最後含 guard-state 的 row，差額則是 generation 1、outbound 2、input 29,361；兩者不同是因之後尚有一筆已保存的 count event，不能重複扣減或漏算。

原 spent `0.341333835` 與最後 received 精確相符。原 occupied `0.366492710` 精確等於 spent 加上舊 reserve `0.013296750` 與新 reserve `0.011862125`。新 reserve 與凍結本機費率、29,361 input 及 16,384 output bound 的計算相符；保留它表示未推測最後准入是否已外送，並非供應商帳單保證。原 journal、state、manifest 與完成場次 result 的原件和 C copies 雜湊全部匹配。v2 audit SHA256 為 `114c1d694970e033d2741fd191d67ad57a4b789629a0a2ab8826cf9261f417f0`；v1 原件保留。

曾提出 0 bytes result 是否會被一般 JSON parser 阻斷的路徑疑點，實際 metadata 檢查已排除：0 bytes 是 `turn-12-result.json`，case `result.json` 確實不存在，因此窄 missing-completion 分支適用。不以此增設一般壞 JSON fallback。

重新讀取 `diagnostics/completion_batch.py`、`audit_disk.py`、`test_completion_batch.py` 與 `test_completion_gates.py`。磁碟分支必須核原 accounting、原件與 copy hashes、唯讀恢復 metadata、failed／未提交 closure、無 active execution、精確 journal totals／spent、固定 1 generation＋1 outbound 差額及精確 reserve basis；任何矛盾均拒絕。正常 resource-stop 分支仍要求自己的原 stop 原因，不提供任意 ledger mismatch bypass。

完整入口核原 frozen production／guide／harness hashes與 CPython 3.14.7，先拒絕仍監聽的原 8177 server；新 freeze 保存 supplement source 和全部 prior evidence exact bytes，並在每次 dispatch 前再核 source 與 prior hashes。新 batch、匿名 reviews 與 blind artifacts 指向核准 C 根；`completion_batch.HERE`、`manifest.HERE`、oracle source 與 ROOT 仍指向 S，只有重用 driver 的輸出 alias 改指 C。finally 在場次拋錯後仍保存完整 schedule、原 spent、reserve 與全部 counters。選案仍以 closure 加最後 completed 狀態保留完成場次，未使用品質或 Memory 成敗重跑。

獨立執行兩份 carry／gate tests：`56 passed in 3.24s`。第一次 sandbox 執行受既有 CPython 3.14.7／pytest `0o700` Windows ACL 問題阻擋 tmp_path，並非行為 Red；相同零 provider tests 以核准 C 根的新 scoped basetemp 經窄 sandbox escalation 通過，沒有改程式繞過權限。

另以實際原 metadata 執行入口 dry-run，將讀金鑰與 `run_case` 替換為禁止函式；結果 provider 0、credential read false、待補足七場、原 spent／兩筆 reserve／四 counters 全部保留，deadline 仍 `2026-10-07T04:30:34Z`，source ROOT 未改。此機械範圍沒有剩餘 P1／P2 finding；沒有啟 paid batch、未恢復匿名 watch，也不代表七場產品訪談或 JD 品質通過。

## 尚未啟動批次的截止 revision 2

啟動曾受自動 approval review 阻擋，沒有建立 actual new manifest 或新增外送。root 隨後確認本次合成資料／OpenAI 目的地授權，並明確將尚未啟動補足批次的截止修訂為 `2026-10-07T08:30:34Z`。此修訂只延長剩餘時間；總 US$8、3000 generation、7000 outbound、180M counted input、32 compact、每場 20 Turn，以及原累計 spent／counter／兩筆 reserve 均不重設。選問優先順序的後續議題未改原對照或披露政策，未建立額外付費測試。

新入口是 `diagnostics/completion_batch_v2.py`，新增 `test_completion_v2.py`；原 `completion_batch.py`、原 04:30 audit 和原 preflight exact bytes 保留。新入口以 `HISTORICAL_DEADLINE` 核原 audit 的 04:30 值，另以新 `DEADLINE` 建立剩餘時間。`LIMITS.seconds=39600` 明示為原 formal freeze 起算的 11 小時 metadata；真正 guard 仍使用 absolute deadline 減當前 wall time，先取 monotonic anchor，沒有開始新的 11 小時計時。

獨立讀取新舊入口的完整差異，新增變更僅涉及該時間／revision metadata、新檔快照及新 batch 預設名稱。實跑原 carry／gate 與 revision 三份 tests，`62 passed in 3.30s`，包含原截止後仍可在新界線內承接、到新截止拒絕、建構延遲仍耗用 remaining、原 audit 不改寫及原 accounting 保留。再用實際 metadata 執行 v2 main dry-run，禁止讀金鑰與啟動 case，結果零 provider／未讀 key、七場待補足與全部原 accounting 精確保留，新截止正確。

獨立核 C 根 `freeze-revision-v2/manifest.json` SHA256 為 `093ecc659c1effdaf7d2c874fb93c32a63a69ebb1f923ca77cb25dce038f8e24`；470 個 canonical source、9 個 supplement／scope-proof metadata 檔案與全部 prior evidence copies 逐 hash 匹配。新舊 manifest 的 original source hashes、effective model、guides、FOCUS、tools、共同披露政策及 runtime metadata 完全相同；除時間 metadata 外的 caps 與原 accounting 也相同。舊 preflight SHA256 `1b40fc87dcf6ae027d2f56094cf305d279cb3aee885b8746047097c863adafc7`、原 audit SHA256 `114c1d694970e033d2741fd191d67ad57a4b789629a0a2ab8826cf9261f417f0` 未變。

此 revision 的機械審查已 Green，沒有新增 load-bearing finding；這是 preflight，未將它當 actual paid launch。匿名 judge 只在 tools 通知合法 paid-ready 後恢復 C 根 queue，仍不讀正式 JD、訪談 source、notes 或品質 mapping。
