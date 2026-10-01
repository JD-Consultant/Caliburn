# C-W P3 自然縱切結果帳本（模板 v3）

2026-09-23；承接[卡包 v2](README.md)與[結果模板 v2](results-template.md)。本版只修正正式 A／B1／B2 模型輸出上限及執行接線欄位；W01–W10、W05 更正、M-W1、Q01–Q15、揭露規則與品質門檻均沿 v2，不重寫。舊模板保留迭代紀錄。

**狀態：NOT RUN／NOT AUTHORIZED。** 以下皆是空白欄位，不代表零成本或通過。C-W 是已曝光的公開 calibration；既有 AI controller 模擬員工，非真人、非盲。同操作者判讀不算獨立人工品質審查，P6 未見案例與真人試用另行驗收。

## Trial 與凍結依據

| 欄位 | 實際結果 |
|---|---|
| trial ID、起訖時間、AI controller 操作者、判讀者 | 待填 |
| Owner 本批付費授權引用、12 員工回合／180 provider requests／US$1.00 界線 | 待填；目前未授權 |
| C-W v2 manifest SHA256、模板 v3 SHA256、exact Git commit 與乾淨工作樹 | 待填 |
| Python／pnpm locks、Prompt／Skills／tool schema 與正式模型設定 | 待填；以 exact commit 與執行時設定核對 |
| A／B1／B2 路由、reasoning、max output、compaction | 待填；正式候選 A 8192、B1／B2 32768，執行時須再核實 |
| 當日 OpenRouter 費率來源與查閱時間、保守預留算法 | 待填；不得以快取折扣作保證 |
| Windows／Node／Python／pnpm／PostgreSQL、隔離 DB／document | 待填；不保存 DSN、密碼或金鑰 |
| 起始 JD／原話／Working State／Memory 為空的實證 | 待填 |
| 離線拒絕未授權、超回合／請求／費用與重新導向的證據 | 待填 |

## 逐輪、事件與來源

每次只記 controller 實際說出的子內容，不能把整張員工卡或 oracle 複製進 App；未知與未揭露保持未知。純手改 M-W1-DOC、後續 M-W1-CHAT 分兩筆。

| event／員工回合 | 時間、顧問實際問題與回答 | W 子項實際揭露／未揭露 | tool／request 可見 trace 位置 | JD before／after、operation／receipt | Working State／Memory／背景狀態 | 來源原話頁／更正關係 | 延遲／首敗 |
|---|---|---|---|---|---|---|---|
| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

可見對話與產品原話以正式 App 保存；研究記錄只引用必要識別與頁面，不保存 provider credential、內部 reasoning 原文或 opaque context。背景通知與真正 publication 分開記。

## 逐請求用量與費用

所有 A／B1／B2、摘要、錯誤與未知費用都由同一 P3 spend ledger 計入；B1／B2 的正式 max output 為 32768。此表是 provider usage 對帳，不冒稱帳單。

| attempt ID／角色／觸發 event | 開始、結束、HTTP／provider／actual model／tier | max output、input／output／cache usage | 預留、實際 cost、未知保留 | 累計 requests／USD／員工回合 | 停止或拒絕原因 |
|---|---|---|---|---|---|
| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

## Q01–Q15 品質判讀

逐項只用 PASS／FAIL／NOT_OBSERVED／NOT_APPLICABLE（附理由）。適用但未觸發的必測項不得記 PASS；品質標準、正反例與嚴重度依[有效品質材料](../../../specs/2026-09-10-jd-product-quality-acceptance.md)。顧問自評與準備者單人判讀都不是獨立核准。

| Q | 結果／適用與觸發 | 已揭露來源、JD 版本段落、trace | 首敗與判讀理由 |
|---|---|---|---|
| Q01 | 待評 | 待填 | 待填 |
| Q02 | 待評 | 待填 | 待填 |
| Q03 | 待評 | 待填 | 待填 |
| Q04 | 待評 | 待填 | 待填 |
| Q05 | 待評 | 待填 | 待填 |
| Q06 | 待評 | 待填 | 待填 |
| Q07 | 待評 | 待填 | 待填 |
| Q08 | 待評 | 待填 | 待填 |
| Q09 | 待評 | 待填 | 待填 |
| Q10 | 待評 | 待填 | 待填 |
| Q11 | 待評 | 待填 | 待填 |
| Q12 | 待評 | 待填 | 待填 |
| Q13 | 待評 | 待填 | 待填 |
| Q14 | 待評 | 待填 | 待填 |
| Q15 | 待評 | 待填 | 待填 |

## Browser／資料查回與收尾

- 新文件、自然訪談、AI 本輪 JD 改動與正確來源原話：待驗。
- M-W1 文件手改、後續澄清、更正、完整 JD 與 K／S 支持：待驗。
- 重開後對話／Memory／JD／receipt 一致，AI 本輪撤回只影響 JD：待驗。
- failed-final、transport unknown、背景衝突等實際觸發與安全降級：待驗；未觸發不能報 PASS。
- 首敗原始證據、修正、重跑是否污染、未觀測與停止原因：待填；不得抹掉首敗。
- 真 Chrome Browser 與 IAB／其他瀏覽器各自結果、真模型與固定回應各自結果：待填。
- 最終 JD 忠實度／完整度／專業性、使用者可交付性：待評；不能由單一 API 或工具綠燈推得。
- latency 原始樣本／中位／最長、provider requests／實際 USD、下一批是否需要新授權：待填。
