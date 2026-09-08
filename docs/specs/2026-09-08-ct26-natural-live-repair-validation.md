# CT26：CT25提示的自然即時修補驗證

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **首項FAIL、帳本closed；1次Luna／medium、估US$0.0024523。CT25提示未解決自然漏存，G8 OPEN。**

## 1. 本輪只驗什麼

- Owner在CT25離線接線後說「OK 繼續測試」。本輪自行設定更保守護欄：Luna／medium，合計最多12次請求／US$0.05（含主顧問、背景與SDK重試）；不是產品限制，亦非沿用CT22已封存額度。
- 基準`3af6466b`：[CT25核准提示與舊防線](2026-09-08-ct25-gpt-prompt-stack-and-live-repair-candidate.md#7-核准接線按錯誤類型整理不逐個bug堆句子)。不改prompt、模型、tool choice、Memory架構、JD或production。
- 既有證據：[CT22](2026-09-08-ct22-memory-prompt-contract-results.md)只有答覆更正、沒有保存。本次沿相同CT16合成售後職位完整資料庫建立**新的實驗副本**，不重跑長訪談／B1建庫，不把合成案例當真實員工資料。
- 官方再次確認[tool choice](https://developers.openai.com/api/docs/guides/function-calling#tool-choice)：auto容許零工具；本次測的是自然選擇，不強制工具。費用依[官方Pricing](https://developers.openai.com/api/docs/pricing#text-tokens)估計；不把usage估算當帳單保證。其餘研究沿CT25，不重複搜同題。

## 2. 順序與停止條件

1. **已談過但未保存的更正**：原樣重送「剛才月報日期我說錯了，是每月5日前，不是10日前；其他做法不變。」應先讀受影響Memory並修補正文及導覽，不只答覆5日。
2. 第一項通過才測**新更正**：5日→7日。其他案件去重、已匯款≠客戶確認、工作範圍、案例細節及來源引用不可被日期修改誤刪／錯套。
3. 前兩項通過才測**已存重述**：同樣7日、沒有新增；不應重寫或為同一更正另通知背景。
4. 有餘額才測**含糊說法**：不確定月報繳交日或主管回覆日，不應擅改已確認日期，應釐清。

每項看實際SDK可見system＋6工具、tool結果、持久正文／導覽前後、完整原Q/A及引用。除動態guide／版本／本輪地址外，SDK契約需與CT25核准fixture相等；不解析opaque reasoning。保守預留與逐次usage沿CT22已驗證ledger；每次呼叫前檢查額度，舊ledger不重新開啟。

**同類漏存或誤改一旦出現即停止後續品質試題及長訪談**；額度／API失敗也停並區分成因，不在本輪追加同義prompt或加Agent。正常API完成不代表Memory驗收成功；沒有寫入也不算「修改能保留細節」通過。

## 3. 執行紀錄

| 檢查 | 實際結果 |
|---|---|
| 真測前完整SDK契約 | 2 passed／7.18秒；已發布／空Memory及工具後續請求符合CT25 |
| 費用護欄離線檢查 | 第13次、費用不足、closed帳本均阻擋；零網路 |
| 首項自然更正 | HTTP200／completed，1次模型、0工具；回答5日，但正文與導覽仍10日，revision3不變 |
| 實際送出的提示／工具 | 對照CT25獨立fixture全等；6工具齊備、沒有強制tool choice，medium／all_turns不變 |
| 工具／背景／限額 | 未發出任何工具呼叫，無patch或API錯誤；背景idle未通知；沒有用盡步數／費用 |
| 來源與原問答 | 原42則＋新增2則逐字一致；4份詳記的來源／前文引用逐頁匹配canonical原文 |
| Memory其他內容 | 正文、導覽、processed_source與背景狀態前後全等；**因為沒有寫入，不能算修改保留能力已驗成** |
| 費用與停止 | 9229 input／121 output；usage估US$0.0024523，不是帳單。首項FAIL即封存，後3項及長訪談未跑 |

證據：[完整去敏JSON](evidence/2026-09-08-ct26-natural-correction.json)、[可見逐字對話](evidence/2026-09-08-ct26-natural-correction.transcript.md)。JSON含可見SDK請求、工具定義、回覆、Memory前後、原文核验、腳本及其hash，不含密鑰或opaque reasoning內容。SHA256：`ab4583fdf9660cedbae94016d2b00477dd6c4305029e6902f9cb542a53ab103e`。原CT22證據SHA256仍為`932529be827921343ffe5b31e11faeb648c753c0ed35b5760bdc7b12e0d9e3cc`。

inspect停用背景且實際零請求，但transport仍受試驗額度管控，不是強制禁止網路；audit另以明確禁止HTTP的接點核驗來源。正式turn使用既有背景排程。試驗腳本重用CT22，只換新試驗名字／基準／輸出位置，透過真正AnalysisService、PostgreSQL、LangChain及OpenAI SDK，非假的模型回覆。沒有改產品src/tests、提示、編輯器、Memory流程、模型或JD。

保留測試本身的問題：封存腳本第一次用浮點數精確比較「已結算預留≥usage」失敗，差約`2e-18`美元。改成封存時以`math.isclose(abs_tol=1e-12, rel_tol=0)`核對兩者相等，並各自維持小於US$0.05；**不改呼叫前的支出護欄或usage、不新增呼叫**。重新封存成功；這不是產品／模型失敗原因。

## 4. 結論、未知與下一gate

已知：這版仍在**模型沒有提出修補動作**處失敗，不是「提出後框架沒執行」。回答採用5日，不代表持久Memory更新。實際完整prompt已核對，不能再用「規則沒接進去」解釋。框架不能對從未收到的patch回傳修正錯誤；增加步數也無法直接解釋此次零工具。

未知：無法讀opaque reasoning，不能認定內部推理延續、模型能力、特定規則衝突或工具負擔是唯一原因；單次續談也不是統計A/B或整體失敗率。文字／工具描述改善有接上，**但未達成本情境所需效果**。

下一唯一gate：帶著本次實際輸入／輸出，回到C的自然動作選擇與完成條件診斷；先對照既有官方實作與不同於已失敗候選的可證偽差異，再與Owner討論。**[CT23§0](2026-09-08-ct23-memory-maintenance-responsibility-review.md)拒絕的逐輪／短尾批／強制維護方案不因本次失敗自動獲准**；不改B時機、不把未來背景追上當此次C成功，也不無限加同義prompt。這是停止真測回報，不是擅自選擇新架構。

獨立只讀review無Critical／Important finding；重算費用、完整SDK契約、42＋2問答、4份引用（11頁／48段）、逐字稿及hash均一致。CT26-R01／P3原文字將inspect與audit都稱為禁止網路，核對腳本後已改成上述實際界線；不是測試結果翻案。品質FAIL不阻擋本地保存反例，亦不授權promotion；commit／tag見主register收尾。
