# JD 跨輪修改通知與引用：官方依據及本案接法

2026-09-10 查閱；JD-R002/C03；定點研究及接線推薦。效力依 [current register](../current-decisions.md)。本輪釐清前次新增需求的依據，不把原核心 schema／固定模型測試當成這項能力已通過。

## 1. 結論與證據界線

「App 將更新送進模型真正收到的 context，並提供讀取工具」已有 OpenAI、Anthropic 與既有框架的官方接點。Claude 的特定共同編輯流程也直接公開了人工改動後告知模型的行為。因此不用另造 agent loop、通知傳輸協定或 Memory 系統。

**沒有證據支持所有產品都會自動偵測、傳送每次外部修改的完整 diff，或使用同一通知格式。** OpenAI 現行 Codex prompting 指南反而提醒手改／撤回後要告知 Codex。上一輪所說的「每輪主動通知、短內容直接附上、長內容按需讀」是本案效果要求與推薦，不應回溯包裝成已定案的跨廠共同規格。以下分開 Official fact、共同原則、Caliburn mapping 及 Unknown。

## 2. 官方事實與容易誤用的細節

| 依據 | 已確認的內容 | 不能延伸的結論 |
|---|---|---|
| [OpenAI Agents SDK：Context management](https://openai.github.io/openai-agents-python/context/) | 本機 `context` 物件只供程式使用，不自動送模型；可透過 instructions、input、工具結果把資料交給模型 | 把資料放進 runtime context／DB，並不等於 LLM 已知道 |
| [Codex：Prompting](https://learn.chatgpt.com/docs/prompting#cli-workflow-run-vite-then-iterate-with-small-prompts) | 官方 CLI 迭代工作流建議使用者在手改或撤回後告知 Codex，避免後續覆寫 | 不能宣稱 Codex 所有表面都自動知道手改，亦不能由此推定所有表面都沒有自動通知 |
| [Codex 公開跨輪注入測試](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/app-server/tests/suite/v2/thread_inject_items.rs#L512-L641) | 在第一輪完成後注入 model-visible item，測試斷言第二輪 `/responses` request 有該內容；另有 `turn/start.additionalContext` 的請求測試 | 本輪只讀官方測試碼、未執行；`additionalContext` 明標 experimental，不採作本案新依賴，也不能代表封閉 UI 自動注入手改 diff |
| [Claude Code：VS Code review changes](https://code.claude.com/docs/en/vs-code) | **Manual mode、接受前手編 proposed diff** 時，Claude 會被告知內容改過，避免仍假定等於原提案 | 這是限定產品流程；文件未揭露該通知全文、分段演算法，也不是任意外部手編均有相同保證 |
| [Claude Code hooks：Add context for Claude](https://code.claude.com/docs/en/hooks#add-context-for-claude) | `hookSpecificOutput.additionalContext` 進入模型 context；`UserPromptSubmit` 時與當輪 prompt 一起出現，下一次模型請求可讀；文件稱包成 system reminder，並非畫面上的一般聊天訊息 | reminder 名稱不是 API `role=system` 的證明；可插入 context 也不代表 hook 自動替 App 產生 diff |
| 同上 hooks | 單一值超過 **10,000 字元**時，Claude Code 保存完整文字，送路徑與短預覽。恢復舊 session 會重播已保存的注入文字，歷史時間／版本可能過時；SessionStart 可刷新 | 10,000 是此產品接點的字元政策，不是跨廠 token 標準，不能直接當成本案繁中門檻。歷史通知不能當目前版本 |
| [Claude Code hooks：UserPromptSubmit](https://code.claude.com/docs/en/hooks#userpromptsubmit) | 某些 command／HTTP／MCP hook timeout 會丟棄附加 context 而繼續 prompt；Agent SDK callback timeout 的處理不同 | 「已配置 hook」不證明每次必要通知均送達。App 仍須處理取文／組裝失敗，不能靜默假報未改 |
| [Anthropic：Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 公開少量先載入＋識別／工具按需取得的混合策略；保留相關資訊並控制 context 大小 | 不保證任何固定短／長分界最適合 JD，亦未指定 JD 的版本／差異格式 |
| [LangChain：Context engineering／Messages](https://docs.langchain.com/oss/python/langchain/context-engineering#messages) | 官方檔案 context 範例用 `wrap_model_call`、`request.override(messages=...)`；只改當次模型請求，可不改保存的 conversation state | 必須在实际 provider request 驗證資料存在；只在 middleware 內建立變數不算送達 |

以上網頁為查閱當日現行文件；未公布該項最低版本者不猜版本。Anthropic context engineering 為 2025-09-29 發布、當日仍現行的官方原則文，不把出版較早等同已淘汰；具体機制以現行 hooks／SDK 文件優先。商業產品作研究參照，不採其付費插件。LangChain 本案 lock 為 1.4.0、core 1.6.2，DeepAgents 0.7.13；使用既有開源依賴，不新增產品套件。官方服務文件是功能契約，不當作程式碼授權。

**共同原則（跨來源歸納）：**應用程式負責讓模型取得所需的現況；按需要提供詳細資料；分清原始輸入、環境資料及工具結果；可回查的版本與目前內容不能混用。**跨廠未一致：**通知的角色、欄位名稱、大小門檻、偵測時機、模型已看過多少的追蹤，以及何時要求人工介入。

公開原始碼／版本明細分存 [OpenAI 證據](evidence/2026-09-10-jd-context-openai.md)及 [Anthropic 證據](evidence/2026-09-10-jd-context-anthropic.md)。Codex 固定 commit `c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68`（2026-09-09 UTC，Apache-2.0），其 experimental additional-context 會區分 application／untrusted、採不同 message role；每值的 1,000 是以 bytes 近似的 token 預算。Claude Code 當日參照 v2.1.266、公開 Python Agent SDK v0.2.152（MIT，bundled CLI 2.1.259）；不能因此推定 SDK 已含較後 CLI 修正。兩種大小政策與受信任程度處理並不相同。

另外三個細節保留作防踩坑依據：[Claude Edit](https://code.claude.com/docs/en/tools-reference#edit-tool-behavior) v2.1.208 起，部分讀後改變情況只要現況精確唯一匹配仍可執行，結果告知另有變更；不能稱所有大廠一律拒絕過期讀取。[SDK approve-with-changes](https://code.claude.com/docs/en/agent-sdk/user-input#respond-to-tool-requests)可修改執行參數，但官方明示模型不會因此被告知改過。[FileChanged hook](https://code.claude.com/docs/en/hooks#filechanged)的終端通知及 Codex `fs/changed` client event，也不能當成模型已收到內容的證明。**本案同版檢查是結構化 JD 的已選取捨，不依這些特定文字工具自動放寬。**

## 3. 本案如何沿官方接點接線

以下是推薦的 Caliburn mapping，不是兩家供應商共同指定的 JD schema。

1. **來源是 App 已保存的文件。** 員工 dirty 先保存；App 在原有 run admission 取得目前 JD 版本及明確比較基準。讀的是唯一 JD revisions／actual changes，不從聊天內容猜員工有沒有改過，也不另外寫一份變更 Memory。
2. **模型請求中加入明標來源的文件狀態資料。** 沿現有 LangChain `wrap_model_call`／`request.override` 接入 model-view；用普通訊息內容區分「App 提供的文件資料」與原始員工問句，文件文字按資料處理。固定行為規則留在顧問指引；不因文件中出現命令句就把它提升成 developer instruction。這份 model-view 不寫進原始訪談，來源回查及 Memory extraction 不把它當員工原話；不偽造沒有配對 tool call 的 ToolMessage。
3. **最少告知什麼。** 明確前後版本、比較範圍、有哪些人工／AI 保存事件、可取得實際前後內容的引用，以及內容是否只提供了一部分。能由已保存 actual changes／確切前後可靠定位時，提供受影響任務／段落；人工 full-value 保存的 `affected_element_ids` 可為空，此時明示定位限制與版本對、提供可續讀的完整差異，不為通知而補造語意 diff。只剩格式變更、先改再改回、連續多次保存，都不能由「最後作者」或淨文字差異錯判為從未手改。通知可辨識事件，詳細內容仍由既有差異讀取處理，不建立逐字 ownership 引擎。
4. **文字怎麼給。** 少量相關更動可附實際前後內容；較多內容提供明確識別與有界預覽，使用現有 `jd_read`／`jd_change_read` 取完整版本或差異。完整資料保留在現有 revisions，不仿造 Claude 另寫一套檔案備份。省略／續頁必須明示，不把生成摘要當完整證據。短／長預算屬本案待固定驗收參數，不能照抄 10,000 字元。
5. **「通知過」不等於「讀完、理解或同意」。** 版本／區間只表示曾向模型提供哪些文件狀態及資料。純訪談可能未完整讀 JD，`jd_edit` 的結果可能包含新版本，分頁也可能只讀一部分；不能只記最後一個 `jd_read` 版本，便稱整份文件都已讀。前版資訊缺失時明示未知並重新提供 current，不能自動報無改動。
6. **重新開啟與失敗。** 重試可以重新提供同一份唯讀通知；不得因此重做 JD 寫入。通知組裝或讀保存狀態失敗時回報實際失敗，不讓它悄悄變成「沒有修改」。恢复的歷史通知標其固定版本；本輪仍需取得現況。context 縮減後必要現況也由同一入口提供，不能僅仰賴模型記住壓縮前的片段。

這條路需要有限的 App 接線，框架不會自行認識本案的 JD 資料庫及 revision。現有 [runtime.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/runtime.py) 已以 `request.override(messages=server_compaction_view(...))` 建立當次請求投影；[memory_tools.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory_tools.py) 已用同類 middleware 提供版本固定的 Memory guide。**沿用的是正式接點與責任邊界，不是把新通知寫進 Memory guide 或改 Memory 流程。** 新 JD context 必須在 compaction view 之後保持可見；串接順序與 checkpoint 的有限版本狀態要由 Task 3／5 驗證。

當前已核對官方機制與 installed source，尚未證明新 JD context 的实际 request、保存、重開與自然模型效果。這些屬施工驗收；不再為同一問題重做廣泛框架比較。Task 3 接線前仍须把比較基準、通知資料覆蓋範圍、呈現預算與恢復分支定成可驗證契約，必要公開 wire 變更沿唯一 SSOT。

## 4. JD 是否要引用 Memory

**推薦保留可追查依據，使用 Memory 協助理解，最終依據能回到原始訪談。** 正文仍以員工易讀的 JD 為主，不要求每句插入腳註或員工手填引用。

| 用途 | 適合使用什麼 | 效力 |
|---|---|---|
| AI 理解目前工作、找到細節 | 版本固定的 current understanding／Memory guide／knowledge／訪談詳記 | 幫助轉寫及查找；是可修訂理解，不取代原始問答 |
| 追查「這項任務為什麼這樣寫」 | 有意義 JD block 的 `source_refs`，回查確切訪談 window | 說明形成依據；引用存在不等於每個字都已被來源支持 |
| 追查「誰把這句改掉」 | JD immutable revisions／actual changes／origin | 是修改歷史，不偽裝成訪談證據 |
| 檢查更正及矛盾 | 既有 Memory 的較新更正與原始問答 | 舊引用不會因仍可開啟就自動取得較新事實的效力 |

現有 [Memory](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory.py) 的讀取 view 帶 document／version；同一 `/memory/knowledge.md` 邏輯路徑內容可隨版改變。**目前沒有把裸 Memory path 定成 JD 永久來源引用。** 若往後有需要記錄「AI 當時參考哪一版 Memory」，須帶確切版及範圍並沿原 owner 解析；這是另外的過程依據，不能用來取代原話，也不能宣稱本次已建立該 locator。

[sources.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/sources.py) 的 `conversation:` handle 已綁同文件、checkpoint、起訖 message，驗實際 Saver snapshot；Memory 詳記可導回保存的 source／context windows。沿[工具契約 §8](2026-09-10-jd-app-tool-contract.md#8-source-reference-與更正-lineage)重用這條來源路徑；模型用 App 真正發出的引用，不算行號、不造 source ID、不複製一份原話到 JD 表。

人工新增的 JD 內容本身有人工變更歷史，但若尚未在訪談說過，不能偽造訪談引用。修改後仍保留的舊 reference 只能作回查線索，不自動替新句背書；未有依據的內容可以明示未知／待釐清，不為了看起來引用完整而硬掛最近一輪聊天。這也是本案已定「保存不等於核准」的延伸。

### 引用是否要直接用供應商 Citations API

[Anthropic Citations](https://platform.claude.com/docs/en/build-with-claude/citations) 能對請求提供的 document blocks 回傳精確來源位置；plain text、PDF、自訂 blocks 的定位形式不同。它是來源呈現能力，**不會自動理解本案 Memory 的版本、JD block 或更正 lineage**。現行文件還明示 citations 與 `output_config.format` 的 structured outputs 不相容；不能把該限制擴大成所有 tool use 皆不相容。

本版沿既有 JD `source_refs` 及來源 owner 完成追查即可，不需為此切 provider、另做 RAG、建立引用 Agent，或把供應商輸出 annotations 當 JD 資料庫的永久身分。是否在畫面上展開依據、如何呈現是既有單畫面體驗範圍，並不啟動已 PARKED 的真人交付功能。

## 5. 施工驗收與停止研究條件

已回答：哪些官方機制可送入模型、哪些通知只有 UI、短／長內容的官方先例、恢復會過時的風險、本地框架接點、Memory 與原始來源的不同效力。剩餘不能靠更多產品介紹證明，依 [Task 3／5／6](../plans/2026-09-10-jd-editor-core-implementation.md)驗：

- 實際 provider request 含本輪文件狀態；canonical 員工問句不變，Memory extraction 不收到偽造問答。
- 多次手改、純訪談、分頁、AI 編輯後再手改、先改再改回、另文件、保存失敗、關頁重開與 compaction 的比較範圍正確。
- 需要續改時先讀 current，過期目標按既有規則拒絕；可查完整差異，不因通知重送重複寫入。
- 來源回到實際原話／較新更正；人工內容不捏造引用、舊引用不假稱重新核實。

固定請求驗收只能證明接線與資料保留；模型是否讀對、理解更正、保存無關有效工作，仍屬後續有範圍與預算的真模型驗收。本輪未改程式／DB／Memory，未安裝套件或呼叫付費模型。

**研究稿核對紀錄：**獨立只讀審查確認未把通知等同全文已讀、未更改 Memory authority、未假稱 Memory-version locator 已建立，也未誇稱跨廠共同規格；一項 P2 已修正：人工全值保存若沒有可靠 affected IDs，明示限制並提供確切版本對與完整差異回讀，不新增語意定位引擎。既有 36 份文件的 456 個本地連結／80 個 anchor 核對及新增三份研究稿的 9 個本地檔案連結均無錯誤；這是文檔檢查，未重跑原有模型／編輯器實驗。
