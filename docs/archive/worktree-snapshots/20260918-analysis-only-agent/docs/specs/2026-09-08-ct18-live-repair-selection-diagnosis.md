# CT18：即時修補未被選用——唯讀診斷

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **G2診斷完成；局部候選待Owner確認，G8仍OPEN。**

## 本輪入口與邊界

- 承接[CT17封存結果](2026-09-08-ct17-correction-persistence-calibration.md)，Owner「OK」授權繼續定位原因；不是授權新增完成檢查、強制工具或再跑完整訪談。
- 唯一問題：為何已收到更正及過時Memory的主顧問直接回答，沒有選C修補；後續又選B通知而非C？
- 已讀：主repo current register／decision-process、CT17全文與實際請求、CT11既有patch真測、目前A／B通知／C／排程接線、官方來源如下。未重開Memory分層／JD設計，也未讀Owner排除的舊產品流程長文。
- 不改產品碼、prompt、模型、資料或限額；不呼叫付費模型。證據沿[CT17原始去敏紀錄](evidence/2026-09-08-ct17-correction-persistence.json)，不複製成另一份巨型trace。

## 1. 已證實的失敗位置

| 證據 | 實際觀察 | 能／不能下的結論 |
|---|---|---|
| CT17 request #1 | system包含新版C指令、導覽rev3及「每月10日前」；本輪員工明確更正為5日。近期可見問答也已說5日；另有不透明compaction | 不是更正／guide／新版system根本沒送入；不能推測不透明摘要或模型內在想法 |
| 同一request | 6個可用工具名稱互異，包含repair_memory及B通知；HTTP200/completed，只有回答，沒有function_call | **失敗在模型選擇動作前**；本次沒有進入patch、schema修正、CAS或資料庫寫入，自然也沒有工具錯誤可重試 |
| CT17 request #2–10 | 新更正5→7先選B通知，B自然發布rev4；沒有選C | 已證明模型可以選通知、背景可以保存；未證明C自然選擇已修好 |
| 現行LangChain及本案接線 | create_agent未指定強制tool choice；no-tool response走結束。本案TurnOutcome的completed只表示技術回合結束 | 框架沒有收到可執行的C呼叫；completed不是「工作理解已正確保存」的語意認證 |
| scheduling.py／該次text_threshold=None | idle且沒有未處理通知／容量觸發時，不啟動B | 第一次不是「背景整理遺失任務」，而是沒有新整理請求；字數備援、排程政策仍屬別題 |

CT17檔案SHA256仍為`493df5e165f373410db818c8a637dd8e32da1462ba6ec4809e32b15b79ed4ad4`，status仍closed；本輪逐檔比對其中24個產品來源hash全部相同。封存只存工具名稱，不含完整wire工具schema／tool_choice；後兩者由目前同版本接線及離線SDK-wire測試核對，**不冒稱是封存HTTP中逐字記錄的欄位**。

另有[CT11§3](2026-09-07-official-memory-patch-trial-results.md#3-真實測試失敗也保留)的Luna／medium成功C：grep→read→repair→final，但當時有明示修補的合成提示。這能作可用路徑的歷史參考，不能取代自然訪談工具選擇驗收。

## 2. 官方實際責任，不把框架功能猜成語意保證

| 官方來源（本輪重新讀取） | 直接支持的事實 | 不支持的延伸 |
|---|---|---|
| [OpenAI Sandbox Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)及本機官方SDK0.22.0 | Memory和conversation分離；live update需要可寫檔能力。SDK Memory.instructions讀導覽，再render含live-update的指令；該指令把核實過時資料後的同輪修補列為完成條件 | 不能由此說SDK自動判斷每則更正、或保證任何模型必定呼叫工具。所讀capability本身提供指令及能力要求，不是語意判斷器 |
| [OpenAI tool choice](https://developers.openai.com/api/docs/guides/function-calling#tool-choice) | 預設auto可以零次工具；required／指定函式可約束選擇 | required不會判斷哪輪真需修補，也不保證工具成功或內容正確；不是本案應直接每輪啟用的理由 |
| [OpenAI GPT-5.6提示指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6) | 清楚完成條件、先排除互相衝突／重複的規則；保留必要前置動作；用真實trace局部修改及複測 | 不支持再堆多個「必須」、直接提高推理或保證一次prompt修改就修好 |
| [Anthropic工具故障排解](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use#claude-calls-the-wrong-tool) | 工具選錯時釐清何時用各工具；未選工具與參數格式錯誤是不同故障 | 不是本次Luna根因的證明，也不表示strict可以修好零tool |
| [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)及安裝版factory | create_agent負責模型／工具loop；目前標準分支讓沒有tool call的回答結束 | 不自動補出未被模型選擇的Memory副作用；不能把技術重試拿來處理漏選動作 |

SDK細讀範圍：`agents/sandbox/capabilities/memory.py`全文、`memory/prompts.py`全文及`memory/prompts/memory_read_prompt.md`全文；live-update先注入，後面才是讀取判準及導覽。來源程式定位可由[既有固定版官方連結](https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts.py#L35-L68)回看；本輪以本機已安裝版本為逐行證據，未重新聲稱GitHub SHA與套件相等。

本機來源hash：capabilities/memory.py=`f9e08b5ef09f6a4c7c74f7475ed53c36ee724a3f615a94fd470353b61b0a35ba`；memory_read_prompt.md=`4dd97a62fc02ad75427a4f34d1fbda30d4d8afd99de99d0edafd672f873705d2`；LangChain1.4.0 agents/factory.py=`2e1855c669ed50df9795b1f73ca690d7664d0ef58a1c4080d0f6504076ebea97`。factory核對model_node／standard binding與_make_model_to_tools_edge；僅讀取，沒有修改上游程式。

## 3. 尚未證明的原因，以及可測的差異

目前不能宣稱知道模型「為什麼」略過。可直接看到以下指令差異，**對漏選的因果仍是假設**：

1. `memory_tools.py`共享讀取提示允許「資料足夠回答就回答」，沒有在這個停止條件限定「只停止查找」。同份system後方又要求核實過時Memory後先修補。可理解但有優先順序歧義，不等於證明模型被其中一句影響。
2. `consolidation_request.py`說「純重述不需通知」，但沒有在該判準明說「對話中說過、Memory仍過時」不屬已完成的重述。CT17 #1正是對話已有5日、guide仍10日。
3. C的system說修補不能保留更正才走B；B工具描述則說更正「尚未經成功修補保留」就通知，包含尚未嘗試修補。二者的fallback條件不完全相同，#2實際走B，卻沒有C失敗。

這不是context容量不足的證據；也沒有證據支持直接換模型、增加step上限或把這次歸咎於reasoning。零tool第一步結束，加上限不會自行多出修補步驟。

## 4. 下一個局部候選（待確認，未施工）

**建議只整理同一組路由／完成條件，不加新機制：**

- 正常查找仍按需、有界；足夠回答只代表可以停止更多檢索，不代表可以略過已知的必要修補。
- 目前已發布Memory與已核實更正不一致，就沿現有讀取→C小範圍修補；是否重述、是否改變共同工作模式都不是跳過修補的理由。尚有歧義則詢問，不能自動以較新的句子為真。
- B仍處理有實質進展的累積資料；已知過時更正優先C，確實無法經C保存時再依現有B通知作補救。通知收到不等於保存成功。
- 已保存且無新進展的純重述不重做。不要每輪強制寫、不要同一成功更正再做C＋B兩遍。

相較另加完成檢查／forced-tool路由，這個候選不引入固定額外模型輪次、不增加資料結構；但仍依賴模型遵循，所以只能用局部真測判斷效果，不能承諾必定成功。維持原樣則保留已重現的漏存風險。**加語意驗證Agent、字串更正分類器、強制每輪工具或新的排程補償都未選。**

獲准後只測三種代表性情境：漏存後重述、新明確更正、已保存的無新增重述。沿同一版本context／工具／Luna-medium及隔離資料，不用把答案直接寫成「請呼叫repair_memory」的人工提示；保留全部失敗及C／B實際路由。若候選仍失敗，就回報，不繼續無界堆提示或換架構。具體付費範圍與執行另確認；本輪沒有消耗新的模型額度。

## 5. 驗證與closure

本輪僅跑既有離線`test_repair_refreshes_reads_without_rewriting_initial_guide`與參數化`test_new_input_guide_supersedes_historical_c_feedback_on_sdk_wire`：**3 passed，7.91s，程序exit0**。命令為隔離實驗目錄`.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`加上述兩個test node及`--tb=short`。測試用真正框架／SDK、合成provider回應及暫時記憶體儲存；不需要API key、沒有網路模型呼叫，未變更實驗或產品的持久資料庫。這只支持「選了C之後可修補並刷新讀取視圖」，不證明自然模型願意選C。

Finding：失敗層已定位到動作選擇／完成條件；有三處可核對的指令歧義，但具體因果未證實。Status：CT15-R07／G8 OPEN。Affected：只新增此診斷及入口路由，CT17封存與產品碼不變。Next gate：Owner確認§4局部候選後，才做單組路由校準與小額對照；不重研ABC、不重跑完整訪談。Reopen：局部反例或官方契約出現新證據，而非再次讀到歷史OPEN。
