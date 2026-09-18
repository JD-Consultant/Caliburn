# CT43：沿既有地址回查，保留記憶語意失敗

2026-09-09 · LLM-Q019 · G7/G8 isolated · Owner授權持續局部優化，重大改變才問。

## Preflight

- 目的：長訪談後能正確且有效率找回案例／原始問答，不重做Memory架構。
- 現況：[CT42](../specs/2026-09-09-ct42-long-interview-results.md)封存105次；短地址resolver已存在但模型未優先使用。B2 high修舊未知，其他保留性仍審查中。
- 唯一阻塞：既有工具路由是否足以讓精確回查不抄錯長碼、減少無關深讀？
- 不做：新增Agent、資料索引、工具schema、模糊地址修復、強制C、production/JD。CT41／42帳本不重開。

## 官方事實 → 局部映射

[OpenAI GPT-5.6](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)的 Tool routing／Grounding／Migration 指引：工具說明涵蓋使用時機、必要先查、錯誤；依失敗只改一組指令；保留足夠證據而不是為少步犧牲正確；high需實測收益，不全域max。

[Anthropic工具工程](https://www.anthropic.com/engineering/writing-tools-for-agents)的 Returning meaningful context／Analyzing results：難以解讀的識別碼增加引用／工具參數錯誤，應利用有意義已知地址；重複呼叫与非法參數需檢查工具描述及實際軌跡。此處不新造ID，因既有summary path已可由程式解析原話。

本輪映射：在共用read guidance中以一處明確規則說明：需要精確原話時以找到的summary path呼叫 `read_conversation`，不重抄其metadata長碼；最終來源也用已讀地址。正文引用未回答問題時，可直接grep所有詳記找相關段落，不把第一條引用當必讀。不規定每題走到底。直接 `conversation:` 仍供沒有詳記的既有live修補來源，schema與儲存不改。

## 工作與驗收

- [x] 先加入離線SDK提示接線RED，保留CT25／41 golden原始證據，只追加CT43 delta。
- [x] 修改一組共用路由指令；直接resolver／錯誤／分页／隔離及完整Context原生延續回歸。
- [x] 相同CT42 Memory，空近期Context，只讀精確回查，仍Luna high，先使用**產品9模型／8工具額度**；再核對不同案例的精確原話，不預先提供地址答案；失敗與12/11對照分記。
- [x] 帳本單寫入者、保留所有失敗，38請求／US$0.02671177；請求護欄調整見下方，費用護欄不變。前兩輪封存總US$0.45876694。
- [x] 審查B2 high對照的保留性，漏重要既有內容故不採用；CT44局部方案另記錄。
- [x] [結果／問答／軌跡](../specs/2026-09-09-ct43-read-routing-results.md)封存，獨立review無Critical／Important；Minor引文標點差異保留。557離線＋41真PG通過；G8仍OPEN。

## 實測後局部對照

第一回查9次已改用所有summary path且無地址錯抄，最後找到缺少的早期詳記，但第9工具被既有8次額度攔下，還未讀其原話、未生成答案，原FAIL保留。不是工具失敗重試loop。對照只讓診斷讀者使用12模型／11工具（增加3次），提示和Memory不再改，不直接調產品設定；成功才判讀取效果與費用是否值得採用。依[LangChain Model/Tool call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)原有可設定額度控制，不發明特殊重試或清零計數。

兩個9/8測試皆因額度中止；第一個12/11對照完成，實際9模型／8工具。為完成第二個不同案例對照，僅將本實驗請求護欄32→42，US$0.12不變，改動事件入帳；不是抹除失敗後只算成功費用。

獨立review確認CT42 high全文重寫刪掉「API文件不清楚先問後端／不假定能力」與「依案件一次主要功能操作說明」；不採此high結果為改善版。待回查切片完成，再解語意保留，不能只升模型遮掩。
