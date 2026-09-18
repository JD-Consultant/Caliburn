# CT37：抽取提示與 medium／high 局部對照

2026-09-08 · LLM-Q019 · G5 局部完成／G8 OPEN

**結論：新版提示在 medium 的原案例仍漏記，不能採用為已修復。high 同提示單例保留了主要差別，值得下一步驗證，但不是整體升級依據。** 本輪候選已封存後還原；主顧問、背景與產品預設仍為原設定。沒有動舊 Memory、JD、schema、工具或排程。

## 1. 問題、依據與實驗範圍

- 根因、原始問答與官方映射由[診斷§2–4](2026-09-08-ct37-partial-answer-memory-fidelity-review.md)持有，不另寫一套 Memory 架構。
- Owner 核准局部 B1 提示校準及新帳本20次／US$0.10；最新補充是「注意 prompt 推薦寫法，真的不行可能改 high」。high 僅在 medium 已觀察到失敗後做一次隔離對照，沒有變更產品預設。
- 依 [OpenAI GPT-5.6 prompting guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6) 的簡化提示、來源 grounding、單獨比較 reasoning effort：替換兩條相近規則，加入不同職位的短例；沒有一直追加 MUST、模型必填欄位、額外審核模型或語意判定器。該頁以 Sol 為主，包含 GPT-5.6 家族建議；本案在 Luna 的效力仍以實测為準。
- [Codex consolidation prompt](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md) 的 `Preserve epistemic status` 與 [Anthropic hallucination guidance](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations) 支持保留來源及不確定性；**不能據此宣稱官方保證這個繁中提示有效**。本輪來源於2026-09-08核對，`main`／現行頁日後可變。
- 正式提示例子為「課程改版／證照輔導」；測試為售後、前端、設備維護、博物館。未將原案例答案塞入提示。

## 2. 如何驗證，哪些没有驗

使用現有 `ExtractionWorkflow`、`ChatOpenAI`／OpenAI Responses 與 MemoryArtifacts；原案例完整8則員工／顧問文字逐字核對。實驗採 InMemorySaver／InMemoryStore，未接 PostgreSQL、Web 服務或自動背景排程；此輪是 B1 抽取層真實 API 測試，不是完整產品入口驗收。

保持 Luna、`all_turns`、`store=false`、`truncation=disabled`、4,096輸出上限不變。先以旧提示 medium作baseline，再以同來源測新提示 medium；其後用相同新提示 high對照。#5／#9 的完整可見 `input` 全等，雜湊同為 `41c1db9d74f30075376d0275fce013dd56327feeeb8d72bc0efd1d0b67bb4c2c`。兩次 input均2,903tokens。檔案／來源地址是系統在保存時產生，不是模型猜ID。

**未驗項目：**B2整併、已發布舊Memory修復、長訪談、主顧問提問／工具選擇。medium原案例失敗後依停止條件，不拿未通過的B1往後宣稱驗收。high的單例成功也沒有被當作B2成功。

## 3. 完整結果，不只保留成功

| 真實請求 | 設定／案例 | 人工對照實際輸出的結果 |
|---|---|---|
| #1–3 | 舊提示 baseline／原案例 | 同一次SDK呼叫的3次連線嘗試，未取得HTTP回應／usage；不能當成模型語意失敗。已計入次數，未知費用預留不釋放 |
| #4 | 舊提示 medium／原案例 | 本次沒再把技師爭議寫成「無經驗」，但候選仍把「印象中營運主管核准」寫成肯定；代表結果有變動，不能說舊提示每次都犯同一錯 |
| #5 | 新提示 medium／原案例 | 兩欄都漏掉「技師判定爭議尚未回答」。詳記在案例段保留「印象中」，權限總結卻再寫成確定核准者；**未通過** |
| #6 | 新提示 medium／前端反例 | 醫院網站明確沒做過；出版社網站經驗／權限未回答。保留每週五所有專案範圍、不把一次修復變固定工時；本次指定檢查通過 |
| #7 | 新提示 medium／設備反例 | 保留核准者不確定，不採顧問的肯定回述；功能測試已知、記錄方式未答、絕緣測試未確認；本次指定檢查通過 |
| #8 | 新提示 medium／博物館反例 | 兩種工作都未實際做過，仍保留明確否定；館內開館前巡查／無修復權未丟；本次指定檢查通過 |
| #9 | 新提示 high／原案例 | 兩欄保留「拒絕兩選項未實際遇過」與「技師爭議尚未回答」，並明示退款核准者是「印象中」。案例辨識、頻率／工作量和時程適用範圍保留；**主要檢查通過一次** |

high並非完全無瑕：詳記標題「尚未由員工回答的問題」仍包住已回答「沒有經驗」的分支，只是內文有清楚區分；沒有新增驗證器去自動判定或改寫它。

兩個短反例的顧問末句已提醒尚待確認的範圍，難度低於原案例；不能用這三例稱為無提示情境成功率、整體正確率，或保證不漏員工完整工作。這是來源／輸出人工核對，不是另外付費給judge model。

### 成本與延遲

| 同提示／同輸入原案例 | medium #5 | high #9 |
|---|---:|---:|
| Input tokens | 2,903 | 2,903 |
| Output tokens（已含 reasoning） | 1,749 | 2,536 |
| 其中 reasoning tokens | 104 | 1,034 |
| 單請求觀察時間 | 17.42秒 | 26.08秒 |
| Usage估算 | US$0.0028244 | US$0.0037688 |

此例 high 約多33.4%估算費用／8.66秒；**不是一般費用／延遲倍率**。估價按[官方定價](https://developers.openai.com/api/docs/pricing)於2026-09-08核對的Luna短context標準價，分開計input／cache write／cached input／output。reasoning已包含於output，不重複收一次。

全輪9次嘗試、6次HTTP200完成，已知usage估 **US$0.0116942**；3次無usage的連線嘗試仍保留 **US$0.0627456**，合計帳本占用 **US$0.0744398 < US$0.10**。這不是帳單，也沒有把失敗當零費用。帳本已closed，不重開或自動追加。

## 4. 封存、回歸與獨立審核

- [完整證據JSON](evidence/2026-09-08-ct37-prompt-effort-comparison.json)：全部實際可見input／output、原與候選提示、各phase來源、實際effort、人工判讀、usage／費用預留、候選diff與driver內容。opaque只留型別／雜湊，不保存原生隱藏推理或憑證。SHA256：`0c2a7117a34dd3e4bbc847532753b460aabf9aadf62cad277f44c4f6c8fb3620`。
- 原封存失敗先以已知錯句斷言重現RED；不是新提示有效的測試，也不是產品裡的語意判定器。新提示要看真實生成輸出，不能用提示字串存在就宣稱修好。
- 候選僅改B1提示的AST核對通過，其餘程式無變。候選118項離線回歸通過（28.06秒），還原後同組118項再次通過（27.66秒）；首次試跑曾被Windows暫存目錄權限中斷，改用已核對的新隔離暫存路徑重跑，不將中斷視為通過。
- medium／high兩種實驗payload、closed、費用及次數停止條件的離線帳本自測通過。SDK自動重試全部經同帳本計數；沒有為了完成測試改產品保護或釋放未知預留。
- 審核者Newton唯讀核對提示範圍、baseline來源一致、帳務；沒有阻擋**失敗封存**的問題，並非核准升級。SR01指出腳本`pipeline`固定medium且重新抽取，不能冒稱接續#9；該mode本輪未執行。SR02短反例提示較強的外推限制已寫上。SR03證據與根register待辦已納入本頁收尾。
- driver作為證據保存，不宣称獨立可安裝套件；歷史local helper以雜湊定位，繼承的Ledger實作一併保存，足供檢查已記錄請求與計費公式。日後重跑須另核准／建新帳本，不執行closed測試。

## 5. 下一步與不應外推的結論

**建議下一個最小比較：只評估背景B1抽取使用high，主顧問先維持medium；再明確設定B2使用哪個effort，驗證正確的抽取結果能否整併且保留既有工作。** 這是待討論的局部升級，不是全面改high，也不必先換框架或增加Agent。

本輪新提示在medium尚不足，所以暫不套用為預設；已保存候選全文與原失敗後還原。high只比較一次，尚未比較「舊提示＋high」，不能把改善全部歸因於新提示、或宣稱已選出最佳組合。下一步可用這個缺口決定是否保留該提示，而非再堆更多警告。

此前零工具C漏存／額外final攔截停放政策不變。CT15／CT36舊Memory錯誤未被改成成功，也沒有覆寫歷史證據。完整訪談的語意品質驗收仍OPEN。
