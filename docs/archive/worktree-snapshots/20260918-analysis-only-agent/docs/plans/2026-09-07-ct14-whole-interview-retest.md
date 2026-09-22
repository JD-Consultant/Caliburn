# CT14：修復後整份工作長訪談複測

2026-09-07 · LLM-Q019 · isolated G8 · 固定基準 `e3ffddb9`。

## Preflight 與效力

Owner 本輪要求「開始複測 長 完整 訪談」。承接 [CT13 修復結果](../specs/2026-09-07-ct13-local-repair-results.md)；不重新設計 Memory，不改 prompt／工具／模型或產品上限，不接 JD／UI／production。

- 目的：對整份工作的理解是否完整正確、自然提問與收尾是否可用；不是完成一個 Task。
- 唯一待驗：修復後自然訪談／背景記憶／回查的技術與語意效果。
- 已讀：current register、decision-process、CT09/CT12 驗收計畫、CT12 逐項結果、CT13 結果與新回查測試。
- 本輪新帳本：Luna／medium，最多 120 次 HTTPS 生成嘗試、US$0.50 保守護欄；沿前次長訪談等級，含主顧問、背景及獨立回查。不是沿用已關閉舊額度，不達成功條件不得宣稱完成。
- 本輪不改設計；找到產品問題先保存 trace，再查已有研究／官方契約討論。安全、資料或來源錯誤立即停相應路徑；內容瑕疵可繼續觀察但不能當作通過。

## 執行

1. 沿既有長訪談 driver、全新專用 `q019_ct14_*` DB／文件，服務每輪重新開啟。只從隔離設定讀 key，不輸出；送出的都是合成訪談。
2. 沿 CT09 封存的電商售後專員 oracle：8 工作範圍、4 案例、後補與更正、未知及低頻工作。oracle 不傳給顧問，不預先填 Memory。由主測試者依實際問題扮演員工回答，不另付費生成員工。
3. 目標一般 20–30 輪，依實際提問／涵蓋調整，不硬湊長度。先觀察顧問是否自主釐清與收尾；有漏項時以員工自然補充，另記「受提醒」而不冒充自主完成。不為縮短測試跳過整份工作。
4. 真服務觸發背景整理，不手動代跑；逐輪保存 source、詳記／候選、理解／導覽、工具結果、模型 status、用量。真實壓縮是否觸發據 wire 判定，不能靠輪數推論。
5. 完成後對照全部已揭露工作，核對範圍、條件、頻率、責任界線、案例差異、更正與未知。完整原文逐頁唯讀核對。
6. 獨立回查不帶近期訪談，沿 CT13 的 `build_conversation + memory_access`、同樣 9 model / 8 tool 與完成 validator；不用舊 bare-reader。診斷時在 startup 前停背景排程，確保不重跑整理污染成本。
7. 技術完成、語意品質、收尾、記憶覆蓋分開判定；保存逐字稿／evidence／短結果，回寫 register，未完成明列。無新 evidence 不稱改善。

## 來源／限制

- 方法與原始 oracle 見 [CT09 計畫](2026-09-07-long-interview-acceptance.md)；內容取捨依既有職務分析研究，不以字串命中當語意驗收。
- [OpenAI 官方價格](https://developers.openai.com/api/docs/pricing) 2026-09-07再次查閱：Luna Standard 每百萬短 input／cached／cache write／output 為 $0.20／$0.02／$0.25／$1.20。依 usage 估算，非帳單；保守預留以較高長 context rate。
- 工具與提示依據沿 CT13；這是代表性合成職位測試，不能證明所有職位百分之百完美。

## 狀態

已完成20輪實際訪談、2批自然背景發布、3次獨立回查及完整原話唯讀核對。59次生成／usage估US$0.08724903，帳本關閉。**技術主訪談完成，品質未通過，G8 OPEN**；晚期Memory缺漏、案例混淆、條件泛化及回查未完成等見唯一[CT14結果](../specs/2026-09-07-ct14-whole-interview-retest-results.md)。沒有修改產品或手動補整理，未觸發compaction／live repair／patch；不覆寫CT12歷史。下一步先就CT14-Q02研究局部修法與Owner討論，不自動追加測試。
