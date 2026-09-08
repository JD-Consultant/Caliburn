# CT43：原話回查使用既有詳記地址

2026-09-09 · LLM-Q019 · 隔離局部採用，G8仍OPEN。
[計畫／官方依據](../plans/2026-09-09-ct43-memory-read-routing.md) · [問答](evidence/2026-09-09-ct43-transcript.md) · [完整軌跡](evidence/2026-09-09-ct43-read-routing.json) · [前輪未過項](2026-09-09-ct42-long-interview-results.md)。

## 改動及理由

只替換一組共用read guidance：需要原句時，用真實讀到的詳記地址交給既有 `read_conversation` 解引用；不要抄其metadata長碼，回答也引用該地址。正文／引用未找到相關資訊時，可grep `/interviews` 找詳記，不強迫每次由第一條來源讀起，不強迫普通提問讀到底。工具schema、Canonical原話、資料owner、分頁及錯誤處理完全不變。

依[OpenAI GPT-5.6提示指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)保留必要路由、按單一失敗類型修改；依[Anthropic工具工程](https://www.anthropic.com/engineering/writing-tools-for-agents)降低難抄識別碼與無關工具工作。這是框架既有能力的局部用法，不宣稱特定提示是各家通用標準。

## 真實結果

相同CT42已存Memory／原話，只讀、空近期Context、Luna high；背景不啟動，不重跑訪談、不種理想答案。

| 情境 | 模型／工具額度 | 實際模型次數 | 結果 | 估費用 |
|---|---|---:|---|---:|
| 交付文件原話 | 9／8 | 9 | 最後需要的原話讀取遭額度攔截，FAIL保留 | US$0.00512910 |
| 兩個網站案例原話 | 9／8 | 9 | 同樣被額度截斷，FAIL保留 | US$0.00498421 |
| 交付文件相同問題 | 12／11 | 9 | 完成，原句／短地址正確 | US$0.00719025 |
| 兩案例相同問題 | 12／11 | 11 | 完成，案例差異／原句／短地址正確 | US$0.00940821 |

所有回查原話操作均使用已知summary path，不再模型抄長碼；兩次成功結果所引用詳記皆已讀，真正原話可核對。獨立review無Critical／Important，但Minor CT43-R01：兩案例回覆將引文內層引號／末尾逗號正規化，意思未變，不能稱嚴格每字相同。失敗是既有額度太小，不是locator错误；不能把兩次失敗刪掉。兩次成功不是統計可靠度保證，路徑仍有可省的查找，但不能為少幾步而省必要原句。

合計 **38次／估US$0.02671177**；護欄32→42次（事件保留）、US$0.12不變，帳本closed。封存時衍生分情境費用曾誤標為預留總和，已保留原數值並更正標籤／加入usage估費，原始請求與總費用完全未變。費用不是供應商帳單。

成功前後PG快照一致；最終audit維持rev9、背景idle。沿用舊audit的 `all_employee_exact`／`all_ai_exact` 為false，因本讀者帳本沒有turn phases，檢查器拿原11輪與空expected相比；這兩項測法不適用，不當成逐字PASS或資料遺失。`reference_segments_exact=true`，有效的引用片段核查仍成立。原逐字canonical驗收見CT42；本輪亦核查只讀工具、相同起始／結束快照及實際讀回原句。失敗phase沒有final snapshot，不能冒稱各自有相同final audit。CT43-R02 review欄名修正已完成。

## 採用界線

採用此路由指令，並將隔離app前景預設9模型／8工具調至**12模型／11工具**，原生[LangChain call-limit middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)不換、不清零重試計數、不取消成本防護。這是最大可用額度，不強迫每輪多呼叫；不調B2／C上限，不全面high／max。

離線SDK接線先3 fail／18 pass（原缺路由），修正後80 pass；中間完整556 pass／41 skip。額度接線先RED，新增測試另因fixture漏建publication表而中斷，補fixture未改產品恢復機制；63項接線／服務測試通過。**最後完整557 pass／41 skip，另41項真PostgreSQL pass**，只剩既有Starlette棄用警告。mock測試只驗接線，自然模型選擇由上表支持。

下一項只处理CT42全文整併漏子句：既有high對照未通過保留，不能採用為完整改善。[CT44](../plans/2026-09-09-ct44-preserve-unchanged-clauses.md)「寫前對照刪除部分」候選45離線通過，但付費命令被工具安全審查拒絕，未發CT44請求；候選已封存、B2還原未採用，需外部處理明確許可續測。production／JD、merge／push均不在本輪。
