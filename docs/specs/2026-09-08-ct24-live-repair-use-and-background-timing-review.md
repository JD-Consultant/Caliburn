# CT24：即時修補的使用條件與背景時機對齊

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **G2研究完成；局部候選待Owner審核，G8 OPEN。未改程式、未新增付費生成。**

## 1. 本輪只處理什麼

Owner要求研究C何時／如何使用，並順便檢查B時機；不是重開Memory分層。優先遵守[CT23§0](2026-09-08-ct23-memory-maintenance-responsibility-review.md)：**B以LLM適當段落通知為主、累積文字量後備；資訊太少先累積。C處理已核實的過時Memory，不用B追上冒充即時修補通過。**本次允許檢查B現有政策的局部對齊，不復活CT23三個被拒絕方案。

閱讀入口：[主register](../../../../docs/current-decisions.md)、[討論流程](../../../../docs/decision-process.md)。沿用並回讀[CT18診斷](2026-09-08-ct18-live-repair-selection-diagnosis.md)、[CT20官方提示](2026-09-08-ct20-official-memory-tool-prompt-audit.md)、[CT21完整契約](2026-09-08-ct21-memory-prompt-contract-review.md)、[CT22原始結果](2026-09-08-ct22-memory-prompt-contract-results.md)；另完整回讀[時機研究](../../../../docs/specs/2026-09-06-memory-generation-cadence-and-continuity-review.md)、[通知接線](../../../../docs/specs/2026-09-06-memory-consolidation-request-wiring-design.md)。不讀Owner排除的舊產品流程长文、不重研五種Memory產物。

## 2. 兩家的實際做法與框架邊界

| 問題 | OpenAI公開做法 | Anthropic公開做法 | 本案判斷 |
|---|---|---|---|
| 何時修補 | Sandbox Memory live update授權工作中編輯；官方SDK指令要求核实替代內容後，同輪結束前更新。依據不只使用者明講更正，也包含可信的當前工具／工作證據 [O1][O2] | 專用Memory tool提供工作中讀寫；啟用該工具時附帶維護指引 [A1] | 兩家支持工作中可修訂Memory；**同輪必寫這段具體指令有OpenAI依據，不能說兩家保證相同** |
| 如何修補 | 模型使用可寫檔案工具，程式執行並回傳；不是SDK自動解析員工更正句 [O1][O2] | 模型請求操作、應用執行、回傳tool result；`str_replace`是精確匹配，失敗回錯誤 [A1] | 保留既有讀取→SDK patch→結果流程；不為模仿名稱而換回曾出問題的精確字串替換 |
| 怎樣才算完成 | 官方提示區分採用正確資訊工作、以及真正寫回Memory [O2] | 工具回傳代表操作結果；光在回答說記住不等於工具已執行 [A1] | 檢查發布後正文／導覽，不用回答正確代替保存驗收 |
| 背景何時執行 | Sandbox執行期間收集segments，session關閉時抽取／整併；既有底層trace見CT23§3.1 [O1] | Memory tool沒有替應用定義一套LLM段落通知背景排程 [A1] | **LLM段落通知＋文字量後備是本案已選策略，不冠名兩家完全相同的排程共識** |

LangChain官方區分hot path與背景：前者有即時性，但主模型同時訪談與維護記憶會有延遲及品質取捨；背景可批次，觸發方式由應用選擇 [F1]。這支持保留B/C分工，**不證明本次漏用必然由多工造成**。

框架能執行模型已提出的工具呼叫、回傳結果／錯誤及繼續流程；不能把「從未發出呼叫」當成patch失敗來重試。現有C由LangGraph執行既有workflow；Memory驗證、原子發布與版本衝突回饋是本案已接好的應用政策，不是LangGraph自帶的語意修補器。本輪沒有找到必須另換Store、增加維護Agent或擴大工具上限的證據。

## 3. 舊反例與本輪確實補到的差異

**CT22仍是：回答5日、0工具、Memory正文／導覽仍10日。**本輪重新讀實際SDK請求的system、C/B定義與最後可見問答，而非只讀報告。工具已綁定、無同名；沒有patch錯誤、API錯誤或用盡工具步數。對話上一輪其實已採用5日，但持久Memory未修；這是CT18／CT21已知案例，不當成新發現。opaque reasoning／compaction不能解碼，不猜它裡面有什麼。

| 核對項目 | 結果 | 是否解釋CT22 |
|---|---|---|
| 本已要求核實更正先C再final | 是；CT21還整理了工具WHEN及讀取停止條件，CT22仍失敗 | 排除「完全沒告知需保存」；**真正漏選原因仍未確定** |
| C條件現在聚焦`verified employee correction` | 官方OpenAI還涵蓋工作中核實的其他證據；本案也可能沿原始訪談回查發現整理錯誤，不一定等員工再說一次 | 是使用範圍待補齊；不是CT22根因，因該例本就明確更正 |
| B提示：沒有可修補Memory的短更正也通知 | 仍存在，與Owner最新低資訊量先累積政策不一致；CT23已標記，本輪確認未被改掉 | 是待對齊條文；不是CT22原因，該例已有可修補Memory |
| B文字量後備 | dispatcher已有條件；CT22配置未啟用。模型通知沒有另加固定最少字數／回合gate | 不把縮短tick、加低門檻或啟用後備說成修好C |

目前C只有`edits[{path,diff}]`讓模型填；來源、讀取版本等由Runtime提供。`repair.py`處理`applied`、可重試錯誤、stale及不可重試結果。`memory_tools.py`沿DeepAgents官方讀取工具；`request_memory_consolidation`是空參數本地通知，回執不等於背景完成。**本輪沒有新發現schema／錯誤處理壞掉，也沒有因0工具就刪掉舊patch保護。**

## 4. 建議的使用契約（待核准，非已改碼）

| 本輪情況 | 建議動作 |
|---|---|
| 已發布Memory有具體錯誤，正確內容已由員工說明或可靠訪談來源核實 | 讀受影響片段→局部C修補→看回傳；成功後才稱Memory已更新。即使只有一句，也不等B |
| 聊天已說對，但已發布Memory仍舊 | 同上；**聊天中的更正不是持久Memory修補收據** |
| 已發布Memory本來就正確，只有無新增重述 | 不重寫、不因這項內容再通知B |
| 新舊說法意義不清，或兩個案例可能被混為一談 | 先詢問／回查；不能單憑較新就覆寫，也不把真實業務矛盾交給deterministic verifier猜 |
| 沒有已發布目標，或新案例／工作範圍需整理 | 留在已保存的訪談與當前延續context；有足夠未整理進展、到適當段落才B，或走文字量後備；不強行用C建立整套Memory |
| C已修好，但同輪還有其他實質新進展 | C只解決那項更正；其餘資料仍可依正常段落條件通知B |

「局部」不等於只能改一處：正文與導覽若都含錯誤，既有工具可整包修正；保留未被更正的工作細節、案例邊界及引用。讀取版本已變時沿現成stale回饋重讀，不重建並行協調。失敗應如實反映、依既有有界重試處理；**失敗回復政策不是這次0工具的原因，也不因本稿默默改成強制B**。

## 5. 下一個局部候選：把已知反例示範清楚，不再加同一句MUST

CT20§4已保留過「少量正反情境範例」，但CT21／CT22沒有試過。OpenAI明確提到反覆出錯的情況可考慮例子，也警告推理模型可能因此變差 [O3]；Anthropic建議工具說明包含何時用／不用，並把漏選和填錯分開診斷 [A2][A3]。**這些支持一個可否證候選，不保證效果。**

建議下一步選這個窄候選：

1. 維持模型、6工具、schema、patch、Memory架構及reasoning延續。把現有修補使用條件整理成§4，補上「回查發現自身整理錯誤」也可核實修補；這是覆蓋補齊，不宣稱找到CT22根因。
2. 用一對很短、不同於失敗日期答案的**動作情境**示範：聊天已確認「本人覆核、主管核准」，Memory仍寫「本人核准」時，應讀取並修補；若Memory本來就已正確，才不寫。不是在員工訊息塞工具名、不是新增模型必填欄位／隱藏推理記錄，也不直接傳Anthropic的`input_examples`到OpenAI API。
3. 替換相關重複段落，不在所有工具各加長篇規則；展示完整system＋工具對照後才施工。保留既有patch格式例子及來源／案例防錯規則。
4. B只對齊「無Memory的短更正不一律通知」，不加timer、每輪反思Agent、訊息數門檻或新排程。足夠資訊指相對未整理批次有實質新內容，不代表這個工作／Task全部訪談完才可通知；本輪不擅定字數值。

沒有選：強制工具、另一個必經維護模型、取消C等B、換模型；也不直接將C改成Claude專用Memory tool。六工具的數量本身不是目前已知問題 [O3]。

**驗證與停止：**這是新的局部假設，不借CT22已封存額度。若Owner核准，再另確認小額Luna／medium範圍；先驗新更正、聊天已更正但Memory未寫、Memory已寫的重述，另以不同工作條件檢查不只是背日期例子。看真正C呼叫／發布內容及未改細節，不只看答案。含糊說法應詢問，不得誤修。若同類漏選仍出現，候選封存，回報需要更強完成機制或其他選擇的取捨；不繼續逐句加規則，也不偷偷實作被否決方案。局部通過後才恢復長訪談。

## 6. 來源、重現與交接

官網本輪2026-09-08重新讀取；官方SDK為本地已安裝**0.22.0**，不宣稱最新發行或等於Codex全部內部。官網負責核對現行能力，固定本地碼負責核對實際細節。

- [O1 OpenAI Sandbox Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)：live update能力及session／背景分工。
- O2 本機官方`agents/sandbox/memory/prompts.py`、`prompts/memory_read_prompt.md`及`capabilities/memory.py`全文：寫入授權／核實／本輪完成、注入順序與工具依賴。hash依次為`2eb0bf2e2e097a396ca6eba9cbf98c8b0e5e3c72f1cdfc5e7f1ed5194a5f93b0`、`4dd97a62fc02ad75427a4f34d1fbda30d4d8afd99de99d0edafd672f873705d2`、`f9e08b5ef09f6a4c7c74f7475ed53c36ee724a3f615a94fd470353b61b0a35ba`。均位於`experiments/analysis-agent/.venv/Lib/site-packages/`；[官方repo來源入口](https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts.py)用於导航，未聲稱Git SHA等於本地套件。
- [O3 OpenAI函式設計建議](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)：使用條件／工具負擔／情境例子與推理模型警語；不是零失敗保證。
- [A1 Anthropic Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)：how it works、commands、prompting guidance、error handling；自動提示屬專用工具，不能假設Luna自訂tool已取得。
- [A2 Anthropic Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions)、[A3 Troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use#claude-calls-the-wrong-tool)：清楚的WHEN及漏選／錯參數區別；不將Claude的症狀表直接當成本案根因。
- [F1 LangChain寫入Memory](https://docs.langchain.com/oss/python/concepts/memory#writing-memories)：hot path多工取捨、背景批次及應用選擇時機；不用其轉述ChatGPT當OpenAI內部直接證據。

本輪實作核對：`memory_tools.py`、`repair.py`、`consolidation_request.py`及`scheduling.py`全文；`live_memory.py`使用條件及CT22實際請求。基準工作分支HEAD`1d9ee13b`，產品候選仍`b7312d9a`，未promote。

Decision：C優先、B僅同策略內對齊，維持Owner有效裁決。Status：§5是**待核准候選**，不是新的durable implementation decision。Why：先前零工具失敗已排除部分接線／執行問題；尚未試過的短正反情境是有限新差異。Next gate：Owner審核候選，再做完整提示對照；不延伸研究新Memory架構。CT22 FAIL、closed帳本及原證據保留。
