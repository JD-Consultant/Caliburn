# 2026-10-04：已完成回提的局部語意核對

依原 [grading-cases.json](../grading-cases.json) 核對三層組 e053–e060 的正式顧問答覆。九個案例、32 個事實單位中，30 個完整符合，兩個只回答部分內容；沒有把部分遺漏記為答對。這是單一旅程的局部結果，不是四組比較、最終 JD 全稿或 Memory 因果效果的分數。

判讀者為本次工程代理，逐項閱讀原件及來源後作語意判讀，未外送付費評分模型；不是第二位盲測人工評分，也不是關鍵詞自動計分。以完整符合／部分遺漏區分，沒有改動原判準。

## 逐案結果

| 案例／正式原件 | 完整符合單位 | 判讀依據與遺漏 |
|---|---:|---|
| return_schedule／[e053](compaction_hierarchical_memory/exchange-053.json) | 3／3 | 週一 08:50、週二至週五 08:35、09:10 前交客服均正確，更正未擴大到其他工作日。 |
| return_conditions／[e053](compaction_hierarchical_memory/exchange-053.json) | 3／3 | 常溫由倉庫確認；冷藏看溫度紀錄，由品質判定；未知溫度門檻未補造。 |
| threshold_scope／[e054](compaction_hierarchical_memory/exchange-054.json) | 4／4 | 分母為本批實際驗收件數；>5% 而非 ≥5%；安全疑慮另行隔離通知；設備備品 5% 未混用。 |
| receiving_boundaries／[e055](compaction_hierarchical_memory/exchange-055.json) | 5／6 | 每日 15–20 張、倉庫清點與員工核對、兩／四工作日、帳物相符才結案、採購決策及不保證交期均符合。`cutoff` 只提當日下班前登錄，未交代月底歸屬由財務決定、不自行回填，記部分遺漏。 |
| report_distinctions／[e056](compaction_hierarchical_memory/exchange-056.json) | 4／4 | 三張表的用途、窗口及 09:10／次月第一工作日／週五 16:00 分開，沒有互相覆蓋。 |
| ambiguous_report／[e057](compaction_hierarchical_memory/exchange-057.json) | 2／2 | e056 剛說明三張表，沒有唯一目標，具模糊施測資格。顧問先詢問是否指帳齡表；沒有直接改稿。trace 此段無工具呼叫。 |
| clarification_resolution／[e058](compaction_hierarchical_memory/exchange-058.json) | 2／2 | 保留次月第一工作日，待主管確認；其他兩表維持不變，trace 此段無工具呼叫。 |
| counting_and_audit／[e059](compaction_hierarchical_memory/exchange-059.json) | 4／5 | 全盤簽核與抽盤結果分開、ERP 需核准單、全盤與稽核成果分開、財務／稽核權限及不補造文件符合。`cycles` 只提每月月底全盤，未完整說明每週三抽盤及異常／主管要求加做，記部分遺漏。 |
| uncertainty／[e060](compaction_hierarchical_memory/exchange-060.json) | 3／3 | 溫度與保存年限均未知；沒有推定堆高機證照。 |

`adjustment` 判為完整符合，是因 e059 明確陳述員工不能自行改 ERP、須有核准調整單，沒有設定小額例外；不因未重複「不論差額大小」六字便判錯。`cutoff`、`cycles` 則缺少原判準中的獨立已知資訊，不以 JD 可能有寫來替正式答覆補分。

## 改稿與來源的界線

e053–e060 的 trace 只出現讀取工具或沒有工具；沒有任何 JD 寫入呼叫，因此模糊輸入未寫入未確認的每週頻率，澄清也未覆蓋其他工作。需要修改與否仍是模型對既有成品的判斷；這份核對只評原判準中的正式答覆，不把「已核對」自報當成來源支持已通過。

來源支持率、四批 Memory 的逐項保留率、12 領域最終 JD 涵蓋及 e061 的 19 個實際主張單位尚未在本頁評分。e061 沒有正式答覆，不能當作正確、錯誤或零分塞進同一分母。更早的首批範圍偏移仍保留在 [main-02 首批觀察](../main-02/first-batch-observation.md)，不因本頁回提表現較佳就撤回。

e053 的原生 user items 仍保留 e001–e052 原文；本頁只能說系統在既有 Context 與 Memory 共存時可正確回答多數精確回提，不能說這 30 個符合單位都由 Memory 找回。
