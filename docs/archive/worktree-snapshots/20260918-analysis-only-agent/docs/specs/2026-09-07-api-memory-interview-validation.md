# CT-04：有持久記憶的正常 API 訪談

2026-09-07 · LLM-Q019 · G5/G7 isolated · 小測已結束；CT04-Q01 OPEN

入口：[current decisions](../../../../docs/current-decisions.md)。前置：[CT-03 回查校準](2026-09-07-memory-recall-completion-calibration.md)。只補完整入口驗證，不重選 Memory／框架，不接 JD、Web 或 production。

## 本輪問題與方法

Owner 要求繼續研究、調整、優化至正常訪談。唯一問題：**已校準讀取提示在真 API factory、PostgreSQL Memory head、員工更正及重新開啟時，能否正常銜接？**

最便宜的測法是重用[已生成合成案例](evidence/2026-09-07-b1-attribution-calibration.json)，只重建真實來源／檔案地址，再透過現有 publication API 發布初始 head。不是手工改成預期答案；不重跑原始 B1/B2。

1. 零生成檢查：實際 Saver／Store 與來源引用可保存、關閉資源再開啟；原文沒有移除。已通過，0 次生成。
2. 真 OpenAI Luna／medium：正常回顧 → 明確更正 B 案權限 → 重新開啟後確認。所有新輸入均走 FastAPI submit／服務執行／狀態／訊息入口。
3. 背景 dispatcher 保持原樣；若模型通知則正常執行，同樣計入測試額度。不為測試強迫關閉背景、不另加觸發規則。
4. 本次小額護欄 20 次實際生成請求／US$0.10 預留，包含 SDK 重試及背景。不是產品上限，也不是期望用滿。超出即停並辨別測試停止與產品錯誤，不宣稱失敗等於資料遺失。

**證據界線：**初始 Memory 是先前模型生成的 fixture；原始訪談仍在 A 的 canonical history／近期 Context。不能把本次答對當作「只能靠 Memory 也能回答」；該獨立問題由 CT-03 處理。本次直接記錄實際 tool call、答案、head／修訂、原文數量、重開結果及用量。短訪談未觸發壓縮時，不宣稱原生 compaction 已真測。

## 官方依據與映射

- **Official fact：**[OpenAI tool calling](https://developers.openai.com/api/docs/guides/function-calling#the-tool-calling-flow)要求應用執行工具後把結果交回模型，再回答或继续工具。依需要重複，沒有通用固定步數。本次檢查真實往返，不只檢查回傳字串。
- **Official fact：**[OpenAI reasoning continuity](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)區分可見對話與不透明 reasoning；`all_turns` 需要實際取得先前 output items，設定本身不產生舊推理。本次保留官方 adapter 的完整資料，證據只存 opaque 指紋、不解碼。
- **已研究官方機制：**[CT-03 §2](2026-09-07-memory-recall-completion-calibration.md#2-診斷與直接來源)保存 LangChain 限制、Anthropic 工具工程與 OpenAI progressive-disclosure 來源；不因換驗證入口而重複研究相同原則。
- **Caliburn mapping：**合成前端接案、更正與重啟三情境，以及本次測試額度，是本案驗證方法，不稱為大廠唯一流程。

> 後續：本頁保留CT04當時的OPEN結果；CT05針對B2任務提示的修正與最新驗收狀態只見[增量整併品質校準](2026-09-07-incremental-memory-quality-calibration.md)，不要重跑本頁已關閉的付費帳本。

## 結果／下一 gate

原入口三輪已完成（3＋3＋1 次 A、另 5 次 B，共 12 次／估 US$0.01135661）。C 發布 revision 2；B 補新詳記引用成 revision 3，沒有蓋回旧客服權限；重新開啟後新理解及原生 reasoning 延續。四份詳記已沿引用實際回查原文；重建的 16 則 fixture 訊息逐字不變。

**CT04-Q01／需要修正：**C 將整句 B 案換掉，保留新客服／匯出規則卻省掉未被更正的「主管可查看全部訂單」；B 沿用已發布 C，只補詳記引用，沒有還原這項明確細節。原始對話、舊詳記仍在，不是不可恢復的資料遺失；但目前知識的完整性不足，不能因 chat 答對就略過。

Owner 首次核准小改：優先最小、唯一可定位的 exact edit；需要整句／整段替換時保留未被更正的事實、範圍、例外與引用。先只改 `repair_memory` 工具說明；第二次核准擴到兩條寫入路徑，見下節。不增加 LLM 欄位、Agent、語意 verifier 或新儲存層。

依據：[Anthropic Memory `str_replace`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#str_replace)公開局部精確替換與不唯一時報錯；[prompting guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)允許針對記憶內容／整理品質補指引。框架既有 StateBackend exact edit 已做到機械替換；缺的是模型如何選範圍，不能假稱框架會驗證語意完整性。新增英文指引是本案校準，不是兩家公司逐字標準。

依 TDD／消費者行為驗證：先以已保存真模型寫入結果執行小型情境檢查，實際因主管原有查看權限缺失而 FAIL，再改提示。不是檢查原始碼含有指定文字。後續用相同來源／記憶與同一句更正、新 API document 再試；沒有重播前一輪真回顧，故只驗證修補效果，不稱嚴格同 Context A/B。延續同帳本，仍合計最多 20 次／US$0.10，不重置已用的 12 次。

## 局部復測與 Owner 補充

**第一個 20 次帳本已結束：**復測用了剩餘 8 次，總計 20 次／估 US$0.01617042。模型選擇通知背景整理，沒有呼叫 C；因此不能據此判斷 C 新提示有效。B1 抽取與 B2 發布完成，但 B2 整句替換仍漏掉主管原有查看權限。這是同一內容保留問題出現在另一條寫入路徑，不是新增架構缺口。

Owner 再次核准：C `repair_memory` 與 B2 `edit_file`／`write_file` 共用同一條內容保留指引；另做最多 8 次 Luna／medium、US$0.05 小測。只透過 LangChain `BaseTool.description` 與 Deep Agents `custom_tool_descriptions` 設定說明，不改工具參數、儲存、錯誤處理、排程、模型或產品上限。

**Owner 本輪澄清（有效目的，不限定資料格式）：**這輪未提及，不代表以前分析整理且仍成立的工作不存在。共同、穩定的工作是對所有已掌握訪談、理解與案例的歸納，仍可補充、修訂及重新歸納；不是新案例一律新增工作，也不是永遠凍結舊理解。這不要求每輪把全部歷史塞進 Context，但不能只憑本輪輸入把既有理解改寫成其子集。新資訊真的更正、否定或澄清舊內容時才調整相應結論；語意不清時詢問，不把省略當撤銷。

**Official fact／直接相關來源：**[OpenAI Codex consolidation 公開提示](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md)的 incremental mode 要求從新增／改變來源定位既有知識，更新受影響部分、保留仍受支持的共用內容；只有部分依據失效時，不應整塊刪除混合了有效資訊的段落。它支持上述保留原則，不保證模型每次都能正確做到。此前 Anthropic 的 `str_replace` 支持局部編輯的操作契約，不能單憑該契約聲稱能檢查語意遺漏。

**第二個 8 次帳本已結束：**4 次 C＋4 次 B2，估 US$0.00558755；合計兩帳本 28 次／估 US$0.02175797。C 透過真 API 成功發布修補，這個樣本保留了主管查看全部訂單、A 案細節、驗收分工及既有引用。B2 已輸出的整句編輯仍省略主管查看範圍；在預檢工具之後、下一次模型請求前遇到實驗總請求上限，沒有完成發布。不得把這次停測當成產品自身上限錯誤，也不能假設再呼叫一次就會修正語意。

**測法限制：**為確實測到兩個寫入者且控制費用，第二次小測暫停的只是測試 process 的 scheduler；C 的合成訊息明確要求走即時修補、不通知背景。B2 重用前次真模型 B1 結果，透過官方 `update_state` 注入已完成 B1 checkpoint 再執行真 B2。它是提示消費者測試，不是自然路由或全流程重新抽取測試；第一組正常三輪才保留預設 scheduler。C 的樣本改善不等於長訪談保證，B2／CT04-Q01 仍 OPEN。到此停止付費呼叫，不自動追加。

## 證據與收尾／避免重新討論

- [正常 API 三輪原始證據](evidence/2026-09-07-api-memory-interview-validation.json)：12 次請求、答案、發布 head、詳記與來源回查、opaque reasoning 指紋，以及可重現診斷程式。原始證據不覆寫。
- [保留細節的兩次復測證據](evidence/2026-09-07-memory-edit-retention-calibration.json)：前帳本第13–20次＋新帳本8次；前12次以檔名與 SHA256 引用，不重複複製。保存实际工具參數、結果、初始／修改後正文及測試限制；沒有 credential 或原生隱藏推理全文。
- 零生成接線核對：由同一 model binding 組裝 HTTP payload，在送出網路前攔截；B2 `edit_file`／`write_file` 的說明均包含共用指引。原付費帳本只記工具名稱，故不偽稱有逐字保存當時的說明。重新讀取 B2 head 仍是 revision 1，沒有將本次未完成草稿發布。
- 最新三個 source 變更後完整離線回歸：**547 passed／0 skipped，118.95秒**，包含 PostgreSQL；一項既有 Starlette／AnyIO deprecation warning。這是流程與機械契約安全網，不保證模型語意正確。
- 獨立 reviewer 已核對三個 source 的框架接線、參數與依賴，無新增 Critical／Important 實作問題；既知 B2 語意省略仍列 Important／OPEN。允許保存這次局部校準與未完成證據，不是允許把它標成完整修復或合併 production。
- 不新增「主管查看全部」專用產品規則，也不增加模型審核者／記憶欄位／新資料層來硬過合成案例。情境檢查只在實驗判斷該案例，不注入 production。

**下一個唯一問題：**背景整併如何將既有仍成立的資訊與本次增量一起整理，而不將新資訊中省略的部分誤刪？已排除「這條工具指引未接到」；尚不能斷言是模型能力、提示優先級或提示表述的哪一項。下一步先核對既有 B2 任務提示與官方 incremental-consolidation 指引的落差，提出局部調整後再驗證，不重選 Memory 架構、不假設加步數能修語意。新的付費復測需另列小額範圍，本輪不追加。

**維持未驗收：**長訪談真正觸發 native compaction、跨更多案例的語意可靠度、CT03 原句回查多帶下一段的 minor finding。不把本輪結果稱為整體正常訪談或長期記憶已完成驗收。
