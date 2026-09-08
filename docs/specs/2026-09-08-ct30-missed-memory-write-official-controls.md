# CT30：漏存不是 Patch 失敗——官方如何控制必要動作與結束

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **G2 官方機制比較完成；修法待審、G8 OPEN。未改產品／prompt，未新增模型請求。**

## 1. 本輪問題與證據邊界

Owner 最新澄清：Patch 只是「參考大廠減少模型錯誤」的例子，要求的是**找能解決漏存的實際做法**，不是補研究原則或重做 Patch 研究。本稿承接 [CT29](2026-09-08-ct29-stale-memory-official-failure-patterns.md)，不重開 Memory 分層、背景整理 B 或即時修補 C 的目的。

[CT28 原始對照](2026-09-08-ct28-live-repair-context-contrast.md)：A2 已收到含「每月10日前」的當前導覽，員工更正為5日；回答5日但0工具，Memory 未變。A1 短 context 能讀取並修補。**Observed：這次失敗在必要動作未執行，不是修補工具拒絕了寫入。**尚不能判定模型為什麼漏選，也不能靠更換 Patch 或提高步數解決零工具。

CT25 已有「聊天確認不代表保存、核實後同輪修補」及正反例。本輪不再把同義提示當成新解方。CT29 的 context 隔離仍是有效診斷候選；最新要求增加的是直接研究官方執行控制，不代表已核准新產品機制。

## 2. 官方提供的實際機制，不只看名稱

| 直接來源 | Official fact | 對本案的限制 |
|---|---|---|
| [O1 OpenAI function calling：Tool choice](https://developers.openai.com/api/docs/guides/function-calling#tool-choice) | `auto` 允許零工具；`required` 要求至少一次工具；亦可指定某個函式 | 保證呼叫不等於保證呼叫修補、參數正確、保存成功或語意正確。尚未讀取目標就強制 patch 可能製造新錯誤 |
| [A-TOOLS Anthropic：Forcing tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#forcing-tool-use) | 同樣提供自動、必須用工具及指定工具；支援程度受模型與 thinking 模式限制 | 不能宣稱所有 provider／reasoning 組合可直接套用；strict schema 也不能取代是否呼叫的決策 |
| [O2 Codex Stop hook](https://learn.chatgpt.com/docs/hooks#stop) | 結束事件可回傳 block 與 reason，Codex 將理由作為新的 continuation prompt，讓原任務繼續；不是撤销整輪 | 是可配置接點，不是預設開啟的 Memory 漏存偵測器。檢查條件與回饋仍要提供 |
| [A-HOOKS Claude Code Stop／prompt hooks](https://code.claude.com/docs/en/hooks#stop) | Stop 可以阻止結束並把理由交回模型；[prompt hook](https://code.claude.com/docs/en/hooks#prompt-based-hooks)可以另呼叫模型判斷完成與否 | 判斷有模型成本及誤判風險；不是不經配置就會查看 Memory。不能把 Claude 的 prompt hook 當成 Codex 已公開相同實作 |
| [F1 LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom#agent-jumps) | `after_model` 可檢查回應，透過允許的 `jump_to: model` 回到框架模型迴圈；`after_agent` 則在迴圈之後 | 可承接回饋續做，沒有現成「員工更正但 Memory 漏存」判斷器。不需要另寫 agent while-loop，也不等於已具備語意驗收 |

**共同能力，不誇大成預設共識：**兩家都公開工具選擇控制，也公開完成前可檢查、未完成可續做的產品接點。這不證明兩家預設用 Stop hook 驗 Memory，更不證明適合每個回合增加檢查。A-HOOKS 的 prompt-based completion check 是有官方範例的選用方法，不是我們發明的模型角色；套用到本案仍是待審 mapping。

## 3. 目前程式缺在哪裡，以及不能省略的判斷

本輪直接核對 `experiments/analysis-agent/src/analysis_agent/live_memory.py`、`runtime.py`：

- 官方 `create_agent` 負責模型／工具迴圈。
- `MemorySession.after_model` 現在處理回應完成狀態、非法／平行 tool calls，以及實際 repair call 的 runtime identity；**沒有針對無工具的最終答覆判斷「是否漏做必要修補」**。
- `repair_memory` 已有真實發布結果、失敗回饋與有限重試；但 A2 沒有進這條路。不能用更好的執行失敗處理代替動作漏選處理。
- 已讀的 OpenAI SDK `MEMORY_LIVE_UPDATE_INSTRUCTIONS` 要求核實後、結束前真正寫入（[固定版本原始碼](https://github.com/openai/openai-agents-python/blob/v0.22.0/src/agents/sandbox/memory/prompts.py)）；它是提示契約，不能宣稱該常數就是自動完成檢查器。版本用於重現，不宣稱最新。

**關鍵邊界：系統知道「沒有寫入」，不等於系統知道「應該寫入」。**

| 可直接檢查的事 | 仍涉及理解的事 |
|---|---|
| 有沒有工具呼叫、回執是否 applied、目前發布版本與內容 | 新訊息是否更正同一案例、舊理解是否真錯、是新工作還是重述、該問清楚還是修補 |

A2 沒有 repair call，也沒有已建立的待修補意圖。不能假設存在這個標記，再聲稱加一個零成本 guard 就解決。也不能把「出現更正字眼」「0工具」「版本沒變」單獨當成漏存證據；普通提問、含糊資訊、Memory 已正確時都可能符合。

## 4. 三個候選與建議，未授權施工

| 選項 | 能解決什麼 | 代價與風險 | 本輪判斷 |
|---|---|---|---|
| 1：沿 CT29 隔離延續 context | 查為何自然選動作失敗，可能找到不加每輪成本的修法 | 診斷不是保存保證，不能反覆追加同義提示當新方案 | 保留，已有 Owner 方向核准 |
| 2：限制／強制工具選擇 | 在指定階段避免模型直接零工具結束 | 呼叫了 read 仍可能不 repair；強制 repair 又需先知道目標及必要性；可能增加無效往返 | 不建議直接套所有訪談回合 |
| 3：完成檢查，不通過則回饋原模型續做 | 直接處理「回答了但必要動作未做」；以 F1 承接續做，不另建主迴圈 | 本案必要性涉及語意。若採 A-HOOKS 的模型判斷方法，會多一次檢查呼叫，加上未通過後的續做；會有漏判／誤擋 | **建議下一個局部比較候選，不是已選產品設計** |

方案3的具體方向是對照本輪對話、實際 Memory 與工具結果，檢查是否有尚未處理的明確不一致；有問題就交回原顧問查閱／修補，意思不清楚則仍可詢問員工。檢查不能自己改 Memory，不能以背景整理代替即時修補，也不能只看模型自稱「已記住」。**這些是本案套用準則，不是冒充官方原封不動的 Memory 漏存方案。**

仍待 G3／G4 的實作細節：檢查啟動範圍、如何選足夠資料、具體訊息接線、一次未通過後的上限與故障處理。A-HOOKS 所提供的 prompt hook 不是免設定／免成本函式；本案也不能用一份只有日期的小測就宣稱長訪談全覆蓋。不得偷偷建立新逐輪大模型驗證 Agent，或把新流程塞進 production。

本地接線另需核對：`MemorySession.before_agent` 以最後員工訊息建立本輪来源，因此不能把機器的續做回饋冒充新員工訪談、再產生錯誤來源引用。O2 的「相當於新 user prompt」描述不能不經轉譯就照貼進本案 canonical 對話；F1 的跳轉能力只覆蓋流程，不自動解決這項產品來源語意。

**最小比較的驗收方向（未執行）：**沿用原 A2，確認不是只答5日而是真正發布修補；另有 Memory 已正確、一般新資訊、含糊更正／不同案例等反例，確認不會亂修或無限阻止結束。保留 reasoning／thinking、背景時機及現有工具；記實際保存、誤擋、往返次數、成本，而非只看回答。任何付費測試先另列小額範圍，不重開 CT28 closed 帳本。

**當時的下一 gate，最新追問見§6：**Owner 審閱是否把方案3納入局部對照。原 context 診斷保留，不把這份研究當成施工同意。研究已找到不同於「多寫提醒」的官方機制；未知的是本案適用性及實際增益，繼續找同義文件無法代替驗證。

## 5. 查閱與紀錄

- O1、O2：2026-09-08 從官方 Docs 定位並讀取對應完整小節；不是根據搜尋摘要下結論。
- A-TOOLS、A-HOOKS、F1：同日讀取官方相關章節，特別核對 forced tool use 相容限制、Stop 與 prompt hook 的不同責任、LangChain after-model 的跳轉位置。引用的是當日公開可配置能力，不聲稱產品預設或實測成效。
- 既有漏存與 context 證據只由 CT28 保存；本稿不複製 transcript、opaque、測試資料或 API 設定。
- 本輪僅修改研究與 register 路由。G8 仍 OPEN；沒有修好／正常長訪談已通過的宣稱。

## 6. Owner追問：應該用工具卻沒用，是不是提示沒說清楚？

本次為同題的唯讀核對，不另開CT31、未改prompt或呼叫付費API。Owner尚未選方案3，不能把前述推薦當核准。

**Observed：**重讀CT28證據第8次實際請求（history組），不是只看程式碼。system確有「核實過時後read＋repair、結束前完成、不需另請求、聊天確認不等於保存」；六個具名工具均在且無重名，repair契約與範例也已送出。當前導覽寫10日，近期員工重述與AI答覆寫5日，本輪再更正為5日；最後只有文字回答。回放的舊AI訊息保有`final_answer` phase，不能在沒有其他證據時歸因於phase遺失。

**Official fact：**[Anthropic troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use#claude-calls-the-wrong-tool)直接列出不呼叫工具，建議查名稱衝突、schema與例子，並把工具說明按「何時用」區分。[OpenAI function定義建議](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)要求system說清何時用／不用；也提醒例子對reasoning model未必有益。這些是排查方向，不代表本案已證實命中某個原因。

[OpenAI工具路由與提示整理指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#tool-routing)要求必要查閱不能因最終答案看似已知而略過，並建議逐組去掉重複、核對矛盾，保留真正限制。**當日取得的頁面標題是GPT-5.6 Sol指南；僅參考一般路由原則，不宣稱是Luna專屬保證或切換模型依據。**

**Inference／待審候選：**現有規則偏向「已判定過時之後怎麼做」。可局部對照更直接的查閱入口：收到曾談工作資訊的更正，或當前導覽與本輪內容不一致時，先查相關的目前Memory；已正確不寫，確認過時再修補，不清楚則查來源或詢問。不是再堆一個MUST，也不要求所有聊天都查／寫或初始化Memory。現有正反例已部分表達這個意思，所以不能聲稱完全漏寫、也不能預先保證改寫有效。

**最新建議／next gate：**先把此入口與現有提示／context的差異交Owner審，再選一個最小變因對照；原context隔離保留。Stop／模型完成檢查仍是未核准備選，不因查到官方接點就優先加上。不以寫了提示當成功，也不因一次失敗斷言prompt無效或必須新增Agent。既有A1成功／A2失敗只支持繼續釐清延續context中的動作選擇，不是穩定性結論。
