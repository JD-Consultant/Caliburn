# CT31：先查目前 Memory，再決定更正路由

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **G5完成：候選不採用、提示已還原；10次／估US$0.01225069，帳本closed；G8 OPEN。**

## 1. 單一假設與邊界

依[CT30§6–7](2026-09-08-ct30-missed-memory-write-official-controls.md)已同意的區分，僅比較「先核對目前已存內容，再判定是否處理過」的提示入口。不是根因已確定；[CT28](2026-09-08-ct28-live-repair-context-contrast.md)短context成功、原歷史0工具失敗仍保留。不清空延續context、不加Stop／判斷Agent、不強制tool、不改patch／schema／Memory架構／B時機或模型，不接production／JD。

**Official fact：**[OpenAI tool routing](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#tool-routing)要求不能因答案看似明確而省略必要查閱，且工具應說清用途／時機／回傳／錯誤。2026-09-08重讀該節；是GPT-5.6 Sol文件的一般原則，不是Luna專屬效果保證。[同輪live update及兩家差異](2026-09-08-ct30-missed-memory-write-official-controls.md#71-官方實際區分不把產品混成一套)不重研，仍為OpenAI可寫Memory模式的映射，不能稱精確時機是各家完全共識。

**Candidate（驗前設定，現已不採用）：**[完整獨立提示fixture](evidence/2026-09-08-ct31-memory-routing-candidate.json)。只替換CT25的Live repair段；保留背景段落、正反例、六工具全部描述／schema、patch／來源／案例防錯、角色、Skills、guide及版本規則。未新增模型欄位；runtime仍不讀docs。新入口要求更正曾談工作或guide與證據不一致時查相關已存Memory；已正確不修、無目標不初始化、未釐清先問、已核實過時同輪final前修補。這是驗前假設；實測結果見§3，不能當成有效的新產品規則。

## 2. 本輪執行清單

- [x] 回讀register／decision-process、CT30全文、CT28全文、CT25完整相關候選／接線／歷史保護及現有提示；兩項原SDK-boundary基線 **2 passed／5.21s**。
- [x] 新fixture／舊提示 **2 failed／5.50s**；僅換一個常數後SDK接線＋live repair／通知／patch安全網 **54 passed／7.60s**。只證實接線，不是自然模型效果。
- [x] 真測沿既有服務入口與四份合成DB，保留完整延續／opaque。背景worker暫不啟動以隔離C成效（通知仍可記錄），不改產品排程。新帳本最多20次Luna／medium請求、US$0.10，含重試，不重開CT28。
- [x] 正例仍漏用，因此不再調參；完成已存正確、完全無已發布Memory、含糊更正三反例。四DB重開保存、原文／引用皆核驗；結果不改判。
- [x] 失敗候選及完整接線保存在獨立證據；本輪改動的提示與fixture接線已還原，沒有promote進產品。
- [x] 還原後離線回歸 **544 passed／41 skipped／45.80s**；41項PostgreSQL整套回歸未設測試DSN而跳過，不算通過。本輪四DB的實際保存／回查另已核驗。一則既有Starlette／AnyIO棄用警告，不改依賴。
- [x] 本地引用及證據hash核對、`src/tests`相對HEAD無淨差異、diff check通過；獨立唯讀審核無阻擋性發現。結果與下一gate已回寫register；保存範圍只有本輪四份文檔證據，不攜帶既有dirty、不push。

壓力測試的RED是CT28實際漏存結果及本輪存儲結果斷言，不以常數包含MUST當語意測試。自然語意仍須人工讀實際工具與最終內容；最多4種情境不代表長訪談可靠率。

## 3. 結果與下一gate

**Observed，候選不採用：**[封存實驗證據](evidence/2026-09-08-ct31-memory-routing-results.json)，包含真實請求可見內容、工具回執、前後Memory、原文回查、使用量與實驗腳本；opaque只保存摘要雜湊，不保存可解讀思考或金鑰。SHA256：`a63f9f5ad2c8c2cbdbed5331bf37d41c42f410672797066e52dc900a667ad913`。

| 情境 | 模型／工具次數 | 保存結果 | 判定 |
|---|---:|---|---|
| 已存10日，明確更正同一月報為5日，沿原42則可見歷史 | 1／0 | 回答5日；正文／導覽仍10日，revision 3 | FAIL：原漏存仍在 |
| 已存5日，再確認5日 | 1／0 | 維持5日，revision 4 | 不重寫通過；沒有證實模型實際查閱正文 |
| 不確定5／10日是否不同報表 | 7／6 | 嘗試兩次改為「日期尚未確認」，兩次被拒；revision 3未變；另送B通知 | 未達本輪「先釐清、不修補」預期；不是把5日誤寫成已確認 |
| 完全尚無已發布Memory，短更正10→5日 | 1／0 | 正常回覆5日，revision 0，不初始化、不通知B | 此反例通過；不代表已測「部分Memory缺此事實」 |

### 3.1 不把不同問題混在一起

- **CT31-F1／blocking、OPEN：**過時正例仍0工具。已核對真實SDK請求只有Live repair段改變；六工具、其他system內容及歷史／opaque一致（runtime來源地址只做等價正規化比較）。提示確有送到；不能說是漏接、patch拒絕、步數不夠或已證明reasoning有問題。
- **CT31-F2／反例不符、記錄待審：**含糊時嘗試將確定日期改成未確認，而非硬選新日期；它沒有詢問員工，最後只說先不判定。與本輪窄驗收不符。尚無同情境舊提示對照，**不能聲稱是新提示造成退步，也不能把「保存不確定性」本身宣稱為跨廠禁止**。
- **CT31-F3／既有patch契約邊界、PARKED：**兩次diff均以裸`***`結尾，非允許的`*** End Patch`；runtime均回`invalid_edit`，第一次可重試、第二次不可重試。這不是本輪新增guard，也沒有放寬匹配。錯誤細節及完整參數見證據；若重開編輯介面議題再審，不能拿它解釋F1零工具。
- B工具只回「收到通知、尚未執行」。worker刻意關閉，沒有重新抽取／整併；不得把通知當修補成功。四組已發布Memory、processed source及背景狀態均未變。

### 3.2 保留與成本核驗

四份DB均以禁止模型網路的方式重開核驗：原對話前綴逐字一致、新問答一致；三份既有Memory的詳記引用仍能回查來源分頁，片段逐字匹配canonical訊息。canonical訊息數只按新問答／tool pair增加，沒有要求「訪談後訊息數也不變」。封存腳本初次把訊息計數一起比較而失敗，查明只有正常新增訊息後改為分開斷言；沒有改保存結果或重跑模型。

合計 **10次Luna／medium、input 98,092（其中cached 87,747）、output 6,644，估US$0.01225069**。依[官方定價](https://developers.openai.com/api/docs/pricing#text-tokens)及API usage計算，非帳單保證；所有請求completed／HTTP200，沒有用盡20次／US$0.10上限。帳本closed，不因剩額再追加測法。

## 4. 收尾與唯一下一gate

本候選不採用；已還原`live_memory.py`及SDK契約測試的本輪修改。獨立candidate fixture及證據保留；要重現，須在隔離副本使用證據中`candidate_sources`的原始提示／測試及`scripts`，不能直接用已還原的程式重跑而宣稱同一條件。無production／JD／模型／工具／背景排程變更。

**下一gate：**與Owner審「下一個實質不同的修法／診斷」，沿[CT30§4](2026-09-08-ct30-missed-memory-write-official-controls.md#4-三個候選與建議未授權施工)已研究的context隔離或完成檢查，不重做同義prompt提醒。建議先沿已有A1/A2差異拆查歷史上下文的影響，不停用reasoning作產品解法；若轉用完成前檢查，須另確認語意判斷、成本及框架接線，不能自動新增逐輪驗證Agent或強制repair。

G8 OPEN，**尚不能宣稱即時修補穩定或長訪談驗收完成**。只有新的測法、官方契約或Owner範圍調整，才重開本候選；不能重跑直到碰巧通過。
