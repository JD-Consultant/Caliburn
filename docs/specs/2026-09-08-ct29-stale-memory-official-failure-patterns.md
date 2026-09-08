# CT29：官方如何處理過時 Memory 與「以為已完成」

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **G2補證完成；漏存根因仍Unknown、G8 OPEN。本輪只研究與記錄，未改產品／提示／工具，未呼叫付費模型。**

## 1. 決策題與既有證據

承接[CT28結果與完整證據](2026-09-08-ct28-live-repair-context-contrast.md)，本輪只回答：OpenAI／Anthropic是否公開處理過相近失敗，以及本案還缺哪個診斷？不重開Memory分層、B段落通知＋字量後備、低資訊量先累積、C即時修補等已核准方向。不讀已排除的2026-08-12大長稿，不以舊production架構約束隔離實驗。

**Observed：**CT28失敗A2首請求的當前guide已含「每月10日前」與正文／詳記地址；可見歷史又有AI確認「每月5日前」的回答。本輪再次更正時，A2回答5日但0工具、Memory仍10日。同提示／工具的A1短context能自然讀取、修補。可以排除「10日完全沒有傳入該次請求」，**不能宣稱模型確實注意到、理解為待修補，也不能從opaque推測它如何思考**。日期出現在導覽關鍵詞，不等於完整正文已讀取。

既有CT25早已要求聊天確認不能代替保存，並非本輪才找到這個漏項。完整提示及歷史防錯目的見[CT25§7](2026-09-08-ct25-gpt-prompt-stack-and-live-repair-candidate.md#7-核准接線按錯誤類型整理不逐個bug堆句子)；原CT28證據SHA256仍為`6718b012c0d56ce7b82a7f7ce5bd8920c5b8b799ec44df588aabdff256210d6f`。

## 2. 官方事實：相近問題、實際處理與限制

| 來源 | Official fact：公開到哪裡 | 對本案的意義／不能推論之處 |
|---|---|---|
| [O1 Sandbox Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)＋[O2官方SDK提示](https://github.com/openai/openai-agents-python/blob/v0.22.0/src/agents/sandbox/memory/prompts.py) | Session訊息與持久Memory分開；run起點給小型導覽、按需讀Memory。啟用live updates時，提示要求發現與已核實現況衝突便同輪修補，真正寫入後才完成答覆，不等另一個要求 | 官方確實預期Memory會過時，也把寫入納入完成條件；不是只有一句「以最新對話為準」。但這是模型指令與工具能力，不是自動保證每個更正均被模型選中 |
| [O3官方Memory讀取提示](https://github.com/openai/openai-agents-python/blob/v0.22.0/src/agents/sandbox/memory/prompts/memory_read_prompt.md) | 先從導覽抽關鍵詞，搜尋正文；正文有引用且需要時才開少量詳記。依漂移風險、核實成本判斷是否驗證；沒有核實時不能把Memory當已確認現況 | 這是相關內容的漸進查閱，不是每輪讀完整Memory，也不是要求每次都查原文。導覽有舊日期可提供線索，但不能視為已執行正文查閱 |
| [O4 GPT-5.6提示指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)／[目前模型指南](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6) | 目標、假設與優先順序穩定時可保留reasoning；先前推理已不相關時有current-turn選項。提示指南也警告過時推理可能延續過時方向；應逐組調整提示、保留真正的防錯限制 | 支持檢查延續context，不支持由CT28直接認定all_turns壞掉。此推理選項不等於刪掉全部對話，也不能假定會清除compaction中的資訊 |
| [A1 Anthropic Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance) | 使用官方Memory tool時，API會加入先查看Memory與記錄進展的system指令。模型提出檔案操作，由應用執行，回傳成功或錯誤；工具本身提供持續編輯能力 | 不是模型「口頭知道」就自動存。這組API注入規則不能因自訂工具也叫Memory就視為存在；目前Luna流程不會自動繼承Claude的原生tool行為。它也不保證所有該做的更新都被呼叫 |
| [A2 Anthropic長任務失敗研究](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | 公開觀察到：後續Agent看見部分進展便過早認定完成；也有未真正驗證就標完成。其coding實驗以進展紀錄、可核對成果和驗證改善，明說仍有未解問題 | 與「有過正確回答，所以以為已保存」是**相近風險的類比**，不是本案同一根因或官方重現月報更正漏存。不因此引入其initializer／feature表／Git或新增Agent |

**共同概念：**可延續的對話不等於持久資料已更新；查目前資料、執行寫入、接收真實結果，是不同責任。**不同細節：**Anthropic原生Memory tool自帶先查看指令；OpenAI按任務相關性漸進讀取。不能說兩家規定完全相同的強制流程，更不能把任何一家的提示視為成功率保證。

新鮮度：A2是2025-11-26的已發生失敗案例，僅用於其觀察，不稱為最新模型效果。[A3 Anthropic 2026-07-24 context engineering](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)則說明新一代模型仍需管理互相矛盾、重複的context與工具指令。其Claude Code數據不外推Luna；與O4共同支持避免無限堆疊提示，不支持刪除本案已有BUG防線。

## 3. 與現有實作對照：不要把已做事項當新修法

| 核對點 | 本案現況 | 結論 |
|---|---|---|
| 告知當前Memory及查閱地址 | A2首請求已給revision3導覽，包含10日與正文地址 | 不是該舊值完全漏傳；尚未證明資料呈現已足夠讓模型正確選動作 |
| 更正與持久保存分清 | `MEMORY_ACTION_GUIDANCE`已寫聊天確認不是保存證據，且有正反例 | 再添加同義提醒不是有新依據的修復 |
| 先讀受影響文字，核實後修補 | system與`repair_memory`描述已有；含糊先詢問／回查，新句不一定更正確 | 規則已接到，A2未遵行；不替換成每轮強制寫入 |
| 工具回饋及恢復 | `status=applied`才確認發布；失敗不發布、可重讀重試。CT28 A1實際走過失敗→重讀→成功 | patch恢復能走通；A2是零工具，沒有進入patch執行器，不以放寬匹配解釋漏選 |
| 延續中的完成狀態判斷 | 舊可見回答說5日，當前guide仍10日；與opaque一起存在 | **Inference候選**：舊回答／延續使模型把更正當成已完成。還可能有其他context或隨機因素，不能直接定因 |

框架接點沿用[CT27§6](2026-09-08-ct27-live-repair-no-call-evidence-review.md#6-owner同意a追問sandbox介面差異與是否學習)與[CT28§1](2026-09-08-ct28-live-repair-context-contrast.md#1-本輪邊界與依據)：LangChain可在模型呼叫邊界提供有界context；LangGraph工具結果可更新run狀態。它們沒有因此保證模型一定選修補。本輪不改介面、資料authority或provider。

## 4. 收斂與下一步：研究不冒充修好

**Finding：**兩家有過時Memory、長任務過早判定完成等相近問題的公開處理，但沒有找到「目前Luna A2這份context為何零工具」的官方直接判定。這個Unknown不能靠再收集相同prompt建議消除，停止廣泛搜尋。

**建議：**沿已同意的context診斷方向，下一小測先隔離舊可見答覆的影響，保持初始Memory／提示／工具／模型及有效的原生延續契約一致。若還需區分reasoning，再以官方支援的選項另作單變因對照；不能手改opaque、破壞工具配對，也不能把current_turn當作清掉全部壓縮歷史。具體可行接線、比較組與新費用護欄須在執行前寫清楚；本輪不執行。即使某組成功，也不直接將實驗的裁切視窗採為產品方案。

**不採為當前修法：**繼續同義prompt重述、提高步數修零工具、強制每輪修補、以B代做C、直接停用reasoning、因A1標點錯誤就換patch介面。沒有證據支持它們能解決本次漏存，部分還會推翻已核准成本與流程。

**Closure：**本輪G2補證完成，G8 OPEN；下一唯一gate為context進一步隔離的診斷設定，不重問Memory整體設計。只有新的直接官方契約或實驗證據才重開具體方案；原CT26／CT28失敗與closed帳本保留。未新增付費生成、DB操作或src/tests修改，亦未宣稱已穩定正常訪談。

## 5. 重查定位

- O1–O4、A1–A3於2026-09-08查閱；OpenAI先由官方Docs搜尋／fetch，再對照本地官方SDK。O4的web入口可能導向模型總覽，提示全文以官方Docs同網址fetch為準；沒有將不同頁面的模型數據混為Luna訪談結果。
- O2本地`experiments/analysis-agent/.venv/Lib/site-packages/agents/sandbox/memory/prompts.py`，`MEMORY_LIVE_UPDATE_INSTRUCTIONS`；SHA256 `2eb0bf2e2e097a396ca6eba9cbf98c8b0e5e3c72f1cdfc5e7f1ed5194a5f93b0`。
- O3同目錄`prompts/memory_read_prompt.md`，完整讀取；SHA256 `4dd97a62fc02ad75427a4f34d1fbda30d4d8afd99de99d0edafd672f873705d2`。SDK **0.22.0只是本輪可重現版本，不宣稱最新發行**；SDK公開實作也不等於Codex所有未公開內部機制。
- 本地核對：`experiments/analysis-agent/src/analysis_agent/live_memory.py`的`MEMORY_ACTION_GUIDANCE`、`MEMORY_REPAIR_DESCRIPTION`；CT25／CT27／CT28完整閱讀。資料與舊失敗仍由CT28證據檔負責，不複製整份trace或新增第二份產品決策。

## 6. Owner核准診斷方向；補充工具防錯研究原則

Owner同意§4的下一步，並要求先找大廠對相近問題的實際解法，包含底層介面，不能只堆提示；以行號易算錯與Patch為例。這是**研究／診斷方向核准，不是已選產品修法**。沿同一topic記錄，不另開重複研究題；付費對照尚未執行。

2026-09-08補查以下直接依據，範圍是驗證研究原則，不重做已研究的patch applier：

- **Official fact — 格式負擔確實被指出：**[Anthropic Building effective agents，Appendix 2](https://www.anthropic.com/engineering/building-effective-agents#appendix-2-prompt-engineering-your-tools)說明傳統diff表頭需預先計算變更行數，JSON包程式碼需額外跳脫，建議減少這類負擔、從模型使用角度設計工具。該文2024-12-19發表，現有工具生態已變，**只引用其觀察，不把整篇當最新框架選型依據**。
- **Official fact — OpenAI實際介面：**[Codex Apply patch範例](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide#apply_patch)示範原生Responses與freeform／grammar兩種接法；以`@@`及周圍文字提供上下文，沒有要求傳統hunk起始行／行數表頭。[目前Apply Patch文件](https://developers.openai.com/api/docs/guides/tools-apply-patch)要求應用真正套用diff、按call_id回傳成功／失敗，並提供SDK `apply_diff`／`applyDiff`；Invalid Context可回饋模型重讀修正。引用的是工具契約，不由範例模型名推論本案provider相容或模型效果。
- **Official fact — 不同公司仍有不同選擇：**[Anthropic目前Text editor工具](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool#str_replace)以old_str／new_str精確替換，包含空白／縮排；另有依行號insert，讀取也可顯示行號。不能宣稱兩家均淘汰行號、精確匹配已過時、所有Patch都免算行號，或Patch原本就是為LLM發明。

**本案採用的研究準則：**先定位失敗層（沒取得資料／沒選動作／參數填錯／實際執行失敗），再查同類官方解法的模型輸入、工具參數、定位方式、結果與恢復，最後對照框架現成能力及本案差異。有合適成熟能力優先用；無公開證據就標Unknown，不假定大廠一定已公開解決完全相同BUG。這是依Owner要求與官方資料收斂的檢查方式，不宣稱為兩家相同的內部流程。

**本段為沿革，最新進度見[CT30漏存執行控制](2026-09-08-ct30-missed-memory-write-official-controls.md)：**Owner隨後澄清Patch只是例子，要求直接研究漏存解法。新補Codex／Claude完成檢查續做、工具選擇控制與LangChain接點；均未授權產品新增強制工具／檢查。原context隔離保留，下一gate改為審官方機制的局部比較候選，不以換Patch修零工具。
