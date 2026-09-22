# CT17：短更正的保存路由校準

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **局部校準與複測完成，品質G8仍OPEN。**

結論：新更正可沿B自然保存，但已有更正的重述仍未補存；C同輪修補未實證。不能宣稱全面修好。[去敏完整證據](evidence/2026-09-08-ct17-correction-persistence.json) · [可見逐字稿](evidence/2026-09-08-ct17-correction-persistence.transcript.md)。

## 決策與證據邊界

唯一問題：員工更正具體工作資料，但共同工作模式不變時，不能只在回答採用新值，卻讓目前Memory繼續提供舊值。承接[CT16結果](2026-09-08-ct16-notification-live-results.md)，不重新討論Memory分層。最新授權：「同意，一樣研究大廠它們遇到這種情況會怎麼解決」。

CT16 #16–17均有更正訊息、guide舊日期及可用B/C工具；回答採用5日前，卻沒有任何tool call，正文／導覽仍10日前。這是修改前可觀察失敗，不是API／schema失敗。近期對話可以回答正確，不等於Memory已更新；原始訪談仍可回查。

## 官方事實，以及我們與官方的差異

| 直接來源 | 核對內容 | 適用邊界 |
|---|---|---|
| [OpenAI Sandbox Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs) | 對話與持久記憶不同；live update允許在使用中修復過時Memory，背景生成另走抽取／整併 | 此頁未保證每個模型在每次更正一定成功 |
| [OpenAI SDK live-update提示](https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts.py#L35-L68) | 核實與目前證據衝突的Memory後，將同輪修補視為完成工作的一部分，不等待另一次使用者要求；回覆前寫入 | 本輪GitHub頁抓取失敗，實際逐行核對本機已安裝官方`openai-agents 0.22.0`同模組的`MEMORY_LIVE_UPDATE_INSTRUCTIONS`及`render_memory_read_prompt`；固定SHA沿既有研究，不能冒稱已重新線上驗SHA相等 |
| [Claude Code auto memory](https://code.claude.com/docs/en/memory#auto-memory) | 記錄有未來用途的回饋／更正及專案期限；會在session中用檔案工具讀寫，並非每session都保存 | 不代表Claude使用與OpenAI相同的強制同輪條款，更不代表背景通知門檻一致 |
| [Anthropic工具故障排解](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use#claude-calls-the-wrong-tool) | 工具選擇含糊時，明確區分何時使用，不只描述功能 | 本例無參數通知沒有填值錯誤，不能靠strict schema解決未選工具 |
| [OpenAI GPT-5.6提示指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6) | 清楚成果與完成條件，去除矛盾指令，根據真實失敗局部調整並複測 | 不換Luna／medium；一次通過不等於全面可靠 |

**修改前的程式事實：**`live_memory.py`每次模型呼叫附加「Repair is optional」，通知描述又是「更正若改變既有工作理解」。前者與我們要學的OpenAI live-update完成條件不同；後者可能把具體資料更正誤等同共同模式變更。本輪已依下節移除歧義；**後者仍是待驗原因，不猜模型隱藏思考。**

既有[詳記更正設計§3.4–3.6](../../../../docs/specs/2026-09-06-interview-summary-correction-routing-proposal.md#3-推薦流程原文詳記與目前-memory-各做什麼)已說明：案例更正也值得保留；C不重建所有詳記，B稍後整理新來源。不是本輪新發明此分工。

## 最小修改與驗證

這是已核准的bounded提示修正，不開新ADR／實作計畫：

- 既有C模型指引：核實目前Memory過時後，讀受影響內容，以現有`repair_memory`修正再回覆；不因只改期限／頻率／案例条件、共同模式沒變而略過。相關導覽若也陳述舊值，一併更正。未受更正影響的細節與引用沿原規則保留。
- 既有空參數B通知指引：具體工作資料更正也是實質進展；沒有C成功保留時，於答覆前通知背景。不要求對同一更正先C再B做兩遍，不強迫每輪整理。
- 核實不了就正常詢問；工具失败依原回傳／有界修正，不謊稱保存成功。這是本案既有工具上的映射，並非兩家共用一份提示或能保證語意正確。
- 不改tool schema、tool loop、權威資料、抽取／整併、原始對話、框架、模型、輸出額度及產品預設。若需其他機制，再回Owner。

測法：先用封存CT16验证「回答正確但目前Memory舊值」檢查會失敗，再改提示；離線只驗接線不退步，不測prompt含某句。真測使用CT16最終DB複本接續更正，保存真實API input/output、receipt、正文／guide與原文回查。這是延續情境，不是完全相同歷史的嚴格A/B。不改原CT16，不重新跑完整訪談。

本輪診斷自設最多12次請求／US$0.10保守預留，Luna／medium，包含所有A/B呼叫及SDK重試；沿原實驗8192輸出／12000compaction，產品B1與B2容量預設不改。若受預算或既有容量問題阻擋，記錄停止，不清零續跑。沒有新計費機制。

## 結果與下一gate

修改前封存CT16的檢查確實以「目前Memory仍是10日」失敗；不是grep提示文字。修改後離線回歸：`test_consolidation_request.py / test_scheduling.py / test_api.py / test_live_memory.py / test_extraction.py`共 **89 passed，24.79s**，一項既有Starlette／AnyIO deprecation。這只證明接線不退步。

實際服務入口續談三則，Luna／medium，**11次HTTP200/completed、usage估US$0.01452117**（非帳單保證），未耗盡12次／0.10。沒有手工觸發B、強制tool choice、替換模型、重跑原訪談、重置計數或覆寫產品容量。舊runner顯示`/120`是沿用的列印字樣，真正guard讀取本輪12次；完整helper隨證據保存，不讓字樣誤導結果。

| 情境／请求 | 真實結果 | 界線 |
|---|---|---|
| 已說過的10→5更正再說一次／#1 | 正常回答5日前，0 tool，Memory仍10日、rev3 | **原問題仍可出現**。新版system與guide10均可見；不是完全相同歷史的首次更正A/B，不能推測模型內在原因 |
| 新更正：重新核對行事曆，5也錯、應為7／#2–10 | A真通知＋答覆，B1一呼叫、B2六呼叫／五工具（兩次讀取、兩次patch、一次預檢）自然發布rev4；正文／導覽都7日；無tool error | 走B，不是C同輪修補；提示改善的因果與普遍成功率未由此證明 |
| 已保存後純重述7日／#11 | 0 tool，無新整理，rev4不變 | 是乾淨負例；此時新增175字問答待整理，但沒有新增工作事實，不把它誤判成漏存更正 |

**保存與引用核對（0模型）：**原42則＋新增6則，共48則可見問答全等；5份詳記的source/context引用逐段回查原文全等。正文及導覽各只有一行月報內容變更：日期10→7、加入新詳記引用，其他行全等；該行其餘去重、匯款待確認、工作範圍／責任細節經完整逐字審閱保留。新詳記記錄5→7的更正及整理做法。不代表整份既有Memory本來完全正確：CT15的未知被寫成無經驗與guide標題不一致未動。

第二情境發布瞬間`pending_source=null`；最終175字是第三則純重述，兩個時點不能混用。這次沒有Memory-only模型回查；主顧問有近期對話。背景tick在前一job未完成時的`maximum instances reached`是既有排程防重入訊息，本次job最後完成，不是每兩秒重新生成。

**獨立review：**先查兩處提示diff，再查真實input/output與before/after，無需修正的新增finding；特別保留「第一例失敗、新更正只證明B、未證明C、舊品質問題仍在」四條限制。

**Closure／下一唯一gate：**保留局部提示與正反結果，不把G8關閉。下一步應只診斷「既有更正漏存後，重述仍不修補」及「C沒有被選用」，先沿同一模型請求、目前Memory可見性與官方工具選擇機制確認，再提出局部方案；**不在本輪繼續疊提示、強制每輪整理或新增判斷Agent**。若需要補償排程／額外完成檢查等新機制，先交Owner討論。容量／步數產品選值與其他CT15語意缺口仍分開處理。
