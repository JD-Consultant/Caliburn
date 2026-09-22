# CT35：工具錯誤恢復核對——沿用框架迴圈

2026-09-08 · LLM-Q019／Q019-MEM-CADENCE-01／CT15-R07 · **最新G3 WORKING：沿用其他工具的框架錯誤回饋；額外結束攔截PARKED。G8仍OPEN，不代表漏存已修好。**

**最新Owner方向：**「我們其他tool不是也會錯誤重試，就用框架一樣的機制」。本輪核對後，Memory修補已使用官方Agent／ToolMessage錯誤回饋路徑，沒有漏接此機制。依此不新增§3的Memory專用final攔截／一次續做規則；具體接線對照見§5。§1–4保留為上一輪候選沿革，不是施工指令。

## 1. 本輪唯一問題與既有邊界

Owner在理解[CT34結果](2026-09-08-ct34-first-correction-and-recovery-results.md)後要求「那你想辦法優化吧」。按最近上下文，本轮處理**已用repair工具、結果可重試、模型卻直接final**；不撤銷[CT30§9](2026-09-08-ct30-missed-memory-write-official-controls.md#9-owner先不追修即時漏存釐清重試的實際意思)先放下零工具漏存的決定，也不恢復額外語意檢查模型。

Preflight已回讀root current register、decision-process、CT30完整沿革與CT34結果。現行接點是`MemorySession`的工具回執／after_model、`create_agent`與`TurnOutcome`；最近問答、reasoning／compaction、B排程、Memory分層及patch介面均不重開。這是既有流程的bounded設計討論，不先寫施工計畫。

## 2. 官方查核：重送工具，與讓模型修正後續做，不是同一件事

| 來源（2026-09-08實際開啟小節） | Official fact | 本案判斷／限制 |
|---|---|---|
| [LangChain Tool error](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-error) | 把exception轉為模型可見錯誤，不會自動重試；官方例子要求模型修正input再試 | 現有工具已送回錯誤。單加此元件不能解決收到錯誤後選final |
| [LangChain Tool retry](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-retry) | 重送拋exception的工具，支援退避及retry_on；主要用於暫時性故障 | 本案是回傳Command／error ToolMessage的invalid_edit，且原參數多句號；直接掛重送不會替模型改參數。不能改成exception後盲目重送來假裝修復 |
| [Codex Stop](https://learn.chatgpt.com/docs/hooks#stop) | hook可回reason要求原任務續做 | 支持在準備結束時回饋；不證明Codex預設為Memory做本案檢查 |
| [Claude Stop decision control](https://code.claude.com/docs/en/hooks#stop-decision-control) | 支持阻止結束／additionalContext續做，以及防無限循環 | 不需要採用另一個prompt-hook模型才可回饋；本案只查機器已知失敗 |
| [LangChain agent jumps及順序](https://docs.langchain.com/oss/python/langchain/middleware/custom#agent-jumps) | after_model可回到model／before_model；after hooks反向執行 | 可沿框架原迴圈與額度接續，不另寫while-loop；掛接仍需顧及現有validation／limit順序 |

本機唯讀查得LangChain **1.4.0**、LangGraph **1.2.11**；不是因沒有新版ToolError可用。未升級依賴。官方證據支持錯誤回饋與有限續做的接點；**下面的精確觸發條件和一次介入上限是本案候選，不冒稱跨廠共同預設。**

## 3. 歷史候選（依最新方向PARKED，不施工）

1. 原流程照常：工具失敗先回饋模型；模型若自然讀取、修正、重試，就不介入。
2. 只在準備final、這輪最新repair結果仍是`invalid_edit`或`stale`且`retryable=true`、沒有後續成功修補、尚未介入過時，經官方after_model接點給**一次額外的續做機會**。本輪判斷依真實回執及來源範圍，不比對回答中的「已更正」字串，也不做語意推測。
3. 回饋明說「上次修改未写入」，附既有錯誤／重讀位置，請原顧問確認後改參數再試；若已發現不該修改或需問員工，允許停下寫入並正常說明／提問。不是命令無論如何都必須改成功。
4. 不增加修補失敗總額度，不清零模型／工具計數；每個員工輸入最多一次這種額外介入。成功、no_memory、不可重試、已達上限、取消／API錯誤、沒有嘗試修補，都不由此接點強制續做。
5. 若仍未修成，保留未完成事實與已保存對話，按既有背景機制後續整理；不能把通知B當作Memory已更新，也不能宣稱本設計保證背景一定修好。不自動重寫或放寬patch匹配。

**成本：**不設額外判斷LLM。正常回合不因本機檢查多出模型請求；觸發時原顧問續做仍會計入Context／推理／輸出費用，後續讀取及修補也可能有多次往返，不能說最多只多一個請求或零成本。

**整體接線限制：**續做留在同一員工輸入／checkpoint脈絡；機器回饋不冒充新HumanMessage或source。現有`service.messages()`會呈現有文字的AI回應，故在最後答覆正式放行前，需明確區分被續做取代的候選回應與真正交付的回應；原生內容／reasoning／工具鏈仍保留可追溯，不靜默刪原始訪談，也不先顯示「完成」再暗中補寫。具體欄位接法需在核准後依官方message／middleware契約驗證，不在此猜用runtime_notice冒充模型回應來源。

## 4. 歷史候選的驗證與停止條件（未執行）

核准後先用現有官方Agent＋synthetic provider測：第一次失敗→final→續做→正確patch；自然重試不多介入；成功／無工具／無Memory不觸發；兩次失敗與模型／工具上限正常終止；跨重開不重複介入；員工問答及來源不被機器回饋污染、對外僅交付最終答覆。主要受影響為`live_memory.py`、必要的訊息顯示接點及對應測試，不改Memory儲存與patch工具。

真實語意效果只能另以Luna／medium局部測試驗證，不預先稱修好；舊付費帳本已關閉，不重用。本輪無新增測試或付費請求、無產品程式改動；只核對文件、程式接點與已知證據。

**Closure／唯一下一gate：**Owner確認「已失敗卻提前結束時，允許原顧問一次有限續做」的局部行為，才能施工。這與已停放的逐輪語意完成檢查不同；若Owner不接受額外續做，回到背景延後整理，不重新遊說逐輪檢查Agent。

## 5. Owner改採共用框架機制：實際接線核對與結論

本輪依decision-process回讀register、CT34結果與本稿；問題只限「是否漏接其他工具既有的錯誤恢復」，不擴大到Memory架構、prompt重寫或另一個檢查Agent。

| 目前接點 | 實際如何把錯誤交回模型 | 不應誤認為什麼 |
|---|---|---|
| [原始訪談回查](../../experiments/analysis-agent/src/analysis_agent/memory_tools.py) `read_conversation` | `ToolException`＋官方BaseTool的`handle_tool_error=True`，轉成error ToolMessage | 不會自動替模型改引用／重選工具 |
| [背景編輯與驗證工具](../../experiments/analysis-agent/src/analysis_agent/consolidation_tools.py) `apply_memory_patch`／`validate_memory` | 同樣由ToolException＋handle_tool_error回饋；框架Agent接著呼叫模型 | 不是框架無限重送同一個錯誤patch |
| [即時修補](../../experiments/analysis-agent/src/analysis_agent/live_memory.py) `repair_memory` | `Command(update=...)`攜带error ToolMessage、read_paths及失敗計數，交回同一官方Agent；schema错误亦接ToolNode結果 | Command同時更新runtime狀態，不等於另寫了Agent重試迴圈；不能為統一外觀而刪掉狀態更新 |
| [共同Agent入口](../../experiments/analysis-agent/src/analysis_agent/runtime.py) | `create_agent`處理model→tool→model，沿既有模型／工具額度 | 框架安排模型讀取結果，不保證模型必然再次呼叫工具 |

另外核對[conversation.py](../../experiments/analysis-agent/src/analysis_agent/conversation.py)的JSON編碼錯誤橋接，以及[背景最終驗證](../../experiments/analysis-agent/src/analysis_agent/consolidation_feedback.py)：前者補ToolNode無法接收未解析參數的回饋，後者是背景產物驗證後的自訂hook，**不是所有工具自带的重試保證**。此次不改兩者，也不將背景私有驗證hook直接搬到員工對話。

官方依据仍見§2兩個LangChain來源，2026-09-08再次開啟核對。`ToolErrorMiddleware`／`handle_tool_error`解決「錯誤交回模型」，`ToolRetryMiddleware`解決「失敗呼叫重送」；填錯patch需要模型修參數，不靠重送原參數。現在C已回傳error ToolMessage，因此無需為這個已知錯誤再疊ToolError或ToolRetry。原模型SDK的暫時性HTTP重試也不因本題更動。

**既有證據：**[CT32](2026-09-08-ct32-context-factor-isolation.md)有失敗後重讀、修正成功；[CT34](2026-09-08-ct34-first-correction-and-recovery-results.md)則收到錯誤後直接final。共同接線可支援修正重試，但兩份結果不能被改寫成保證成功或單純漏裝middleware。CT34的口頭「已更正」也不能推論它明確宣稱資料庫已保存。

**Decision／closure：**沿用共同框架錯誤回饋與原模型修正迴圈；§3額外final攔截PARKED，不再為此另問一次核准。無工具漏存仍依CT30§9停放。背景後續整理是既有策略，不將尚未整理的更正視為已持久化。本輪只更新研究與閱讀路由，未改產品碼／prompt／依賴，未做付費生成或重跑測試。下一步回到既有訪談驗收，不再開本候選施工計畫；只有新證據指出共同接線缺漏或Owner重開需求，才重新研究具體修復。
