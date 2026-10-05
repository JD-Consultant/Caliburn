# 固定 Memory 比較：執行紀錄

## 為何這樣測

使用者同意先固定 Memory 處理讀後漏項，並要求繼續研究大數據。本輪核對 BigQuery 共讀資料組織、DuckDB 投影／過濾下推、Databricks／Enzyme 增量維護，方法與不可類推處寫回[研究 §8](../../../../research/agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md#8-從查詢與增量系統進一步借鑑)。這些方法沒有替模型保證語意正確，因此本批不新增索引、Memory 層或 Agent。

工作分析與 JD 指南支持「必要限定保留、無關內容不照搬」。候選不是重複要求所有欄位必填，而是先按任務範圍選取，再判斷縮寫是否改義。完整任務與單一片段都有反例；判準先凍結，結果不能倒過來改分母。

## 離線及凍結

- 新增四個 runner 邊界測試，先在未實作函式看到四個 `NotImplementedError`（Red），再完成同快照隔離、未來訪談拒絕、雜湊核對及只能付費一次的接線。讀取上界測例依既有直接方法採 `ValueError` 契約；模型工具外層才轉錯誤回傳。
- 四項通過後，沿用 Workspace、episode、輸出契約等受影響回歸共 **30 passed**，1.96 秒。命令：`apps/api/.venv/Scripts/python.exe -m pytest docs/experiments/product-validation/data/jd-scope-preservation-2026-10-05 docs/experiments/product-validation/data/memory-coherent-units-2026-10-05 docs/experiments/product-validation/data/memory-structure-incremental-2026-10-05 -q -p no:cacheprovider --basetemp=.research-tmp/jd-scope-regression-01`。離線測試不代表語意通過。
- Ruff 首次抓到測試 import 分組，修正後通過；沒有為此修改產品。測試在隔離暫存目錄跑，未清理其他程序或資料。
- 先驗前批 manifest，再凍結本批模型、工具、語料、兩個生成快照、指引及判準。本批兩組共用完全相同快照，每題從空白讀者 context 開始；reader 只拿問題與 map，不拿 grading。完整原話仍在唯讀工具的合法上界內。
- 本批授權為 US$0.05／900 秒，前批累計占用 US$1.285104650。`live-01` 只能啟動一次；不沿用前批餘額、不換目錄補跑。API 失敗、容量或本批界線觸發即結案，保留已完成及未完成題目。

## 執行

先完成 `reader_study.py prepare`／`verify`（無外送），再於本批有效授權下執行 `run`。首次 prepare 為 2026-10-05T06:27:50Z；exec session 75560。此處時間僅用於原件追溯，不作產品品質主張。獨立指標投影 `analyze_reader.py` 在外送期間新增，不參與模型上下文或凍結判準；此分析膠合程式不是 TDD 產物，沿用既有事件統計，結案時另對 trace 與帳目核算。

## 結案核對

session 75560 以 exit 0 結束，16／16 episode 保存，run-summary 為 completed、failure 為 null。本批計時 556.93 秒，占用 US$0.010167325，累計 US$1.295271975。沒有補跑或增加付費請求。

重新執行 `reader_study.py verify`，凍結雜湊符合；再執行 `analyze_reader.py` 重算全批資料，取代執行期間的部分投影。原始 trace、manifest、問題、判準、快照及結果不改寫。離線另核對：

- 38 次模型請求、38 次 input-token 請求，各自 request／response key 一一對應；38 次模型回應均 completed。
- 每次 request 都有 strict 完成 schema，且只有一則本題 user 輸入。22 次相鄰模型步驟按正式 `response_input_items` 序列化前次回應，比對下一次 input 前綴及 function_call_output 的 call_id，均一致。
- 16 份最終引用都指向本題實讀理解，其固定來源鏈涵蓋凍結判準的最小必要訪談來源。此核對不替代正文語意判讀。
- 最大 input 2,987 tokens，沒有 compact 請求、provider 失敗或工具錯誤。trace 的 38 次 rate_wait 是既定節流，不是 38 次失敗。
- 生成估算 sum(settled.estimated_usd) = US$0.006367325；38 次 token-count 暫留合計 US$0.0038，加總等於 run-summary 占用。所有 HTTP 回應均已收到，pending 欄表示未解除的保守費用占用，不是未完成請求。

76 份實際 request 也逐一對過凍結的組別指引、tools 與完成 schema；模型皆為 gpt-6-luna、high，8 個配對初始 Context 逐位元相同。這項核對看的是實際外送，不只看 runner 預設值。結案時 Ruff check／format 通過，7 份本批及研究 Markdown 的 56 個本機連結與章節定位均有效；逐題表加總為 21 C／4 P 與 24 C／1 P。資料包未檢出金鑰格式字串；這是有限模式檢查，不等同完整資安稽核。

語意判讀與新發現另存 [semantic-review.md](semantic-review.md)，不寫回凍結 grading。結果及下一步見 [results.md](results.md)。本批只對已知小型反例比較，沒有重跑正式 B1／B2、資料庫、長訪談或超容量測試。

結案另由一位只讀助理審查者複核 16 份輸出、判準、來源、trace 的數值投影及結論界線，未提出需更正項目；21 C／4 P、24 C／1 P、token 與本批占用加總一致。審查者看過本次報告，不是盲測，也沒有回溯審計所有前批帳務。複核未新增付費請求或改動原件。
