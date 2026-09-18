# JD-R002/C03：Anthropic 的人工變更感知與模型 context 證據

查核日：2026-09-10。狀態：**G2 有界官方補證，不是接線實作或新決策**。

## 本輪邊界

- Topic ID：JD-R002/C03。
- Current stage：跨輪人工變更感知補充；runtime 接点須在 Task 3 接線前閉合。
- Binding decisions：同一份持續 JD 工作稿；Owner 要求顧問在下一輪知道員工手改過的內容；既有 Memory／原文分工不重做。
- Only blocking question：主動送入模型的人工變更資訊是否有 Anthropic 官方先例／契約，能證明到哪一層？
- Already reviewed evidence：current register 最新 C03 條目、decision process；本稿以下官方文件與公開 SDK source。
- Out of scope：production／DB／Memory／主契約／施工計畫修改、安裝、付費模型、非官方或洩漏／反編譯 Claude Code 實作。

## 可以成立的結論

**主動讓模型知道人工變更有官方產品先例，也有公開 context 注入接點。**但「Claude Code 必定在每一輪、自動提供所有外部手改的完整 diff」仍未由本輪來源證明。以下刻意分開模型可見性、UI 呈現與底層檔案比對。

| 證據 | 官方直接支持的範圍 | 不能推出的結論 |
|---|---|---|
| [Claude Code／VS Code：Review changes](https://code.claude.com/docs/en/vs-code#review-changes)，2026-09-10 現行頁 | Manual 模式下，使用者在接受前直接修改 proposed diff，Claude 會被告知修改，避免假定檔案仍是原提案。 | 不是任意編輯器、任意外部檔案、跨輪完整 diff 的通用承諾；未公開此接點的精確 API message role。 |
| [Claude Code hooks：Add context for Claude](https://code.claude.com/docs/en/hooks#add-context-for-claude)及 [UserPromptSubmit](https://code.claude.com/docs/en/hooks#userpromptsubmit)，2026-09-10 現行頁 | `UserPromptSubmit` 在模型處理使用者輸入前執行；`additionalContext` 隨該 prompt 進入 conversation，包成 system reminder，下一個 model request 可讀，並非 UI chat message。 | 有 hook 不代表已替每個 App 計算文件變更；system reminder 名稱不證明 API `role=system`。 |
| [Tools reference：Edit tool behavior](https://code.claude.com/docs/en/tools-reference#edit-tool-behavior)，v2.1.208 起的規則 | 檔案在讀後改變，若目標文字仍精確且無歧義、允許免提示讀取，Edit 可繼續；**工具結果會註明另有變更**，使 Claude 在依賴周邊內容的後續編輯前重讀。其他失配情況須重讀。 | 這是工具執行與結果回饋，不能單獨滿足尚未呼叫工具的下一輪訪談開始前通知。也不能沿用「任何讀後變更一律拒寫」的舊敘述。 |
| [VS Code：Reference files and folders](https://code.claude.com/docs/en/vs-code#reference-files-and-folders) | 編輯器選取文字可自動供 Claude 看見，使用者可切換隱藏；`@` 可提供路徑、行號或檔案內容。 | 選取 context 不等於前後版本差異，也不表示所有開啟文件全文都進模型。 |
| [JetBrains IDEs](https://code.claude.com/docs/en/jetbrains#features) | 現行選取或 tab 會分享給 Claude Code，`Read` deny rules 可阻止相應檔案分享。 | 僅證明該 IDE 整合的分享範圍；不能外推成通用 diff 注入。 |

### 特別需要排除的兩個誤讀

1. [FileChanged hook](https://code.claude.com/docs/en/hooks#filechanged) 能偵測指定磁碟檔案被工具、腳本或外部程序改變；但其 `systemMessage` 是互動終端短通知，文件明說不進 SDK message stream。**檔案變更事件存在，不等於模型已獲知。**
2. [Agent SDK 的 Approve with changes](https://code.claude.com/docs/en/agent-sdk/user-input#respond-to-tool-requests) 明說，修改工具 input 後允許執行，Claude 看得到結果，但不會因此被告知 input 曾遭修改。**修改執行參數與告知修改來源是兩件事。**這與 VS Code diff 手改通知屬不同接點，不能混用。

## 公開 source 能追到哪裡

本輪官方 releases 頁可見 Claude Code [v2.1.266](https://github.com/anthropics/claude-code/releases/tag/v2.1.266)（2026-09-08；commit `347b38e4a733d95b2f00690a4ca58ac1544f8a1c`）。這是查核版本參照，不表示所有現行 docs 功能首次出現在該版。

Python Agent SDK 官方可見版為 [v0.2.152](https://github.com/anthropics/claude-agent-sdk-python/releases/tag/v0.2.152)（2026-09-02；commit `a8b1e285f97f8dbcb7b10226d74ba0d551b493f4`），release 記載 bundled Claude CLI 為 **2.1.259**；不能當成已包含 2.1.260／261 修正。

固定該 SDK commit 的公開鏈：

1. [`types.py`／UserPromptSubmitHookSpecificOutput](https://github.com/anthropics/claude-agent-sdk-python/blob/a8b1e285f97f8dbcb7b10226d74ba0d551b493f4/src/claude_agent_sdk/types.py)：明列 `hookEventName` 與 `additionalContext`。
2. [`_internal/query.py`／hook_callback](https://github.com/anthropics/claude-agent-sdk-python/blob/a8b1e285f97f8dbcb7b10226d74ba0d551b493f4/src/claude_agent_sdk/_internal/query.py)：等待註冊 callback、轉換 Python 欄位名，再把 output 包成 `control_response` 寫向 transport。
3. [`subprocess_cli.py`／SubprocessCLITransport.write](https://github.com/anthropics/claude-agent-sdk-python/blob/a8b1e285f97f8dbcb7b10226d74ba0d551b493f4/src/claude_agent_sdk/_internal/transport/subprocess_cli.py)：transport 把資料送入 Claude CLI stdin。

因此 source 證實的不只是裝飾 UI：App 的 hook output 確實送入執行器；之後如何組成模型請求，由 hooks 官方契約支持。**未查 Claude Code 閉源內部的 message builder／一般外部文件差異演算法，不聲稱 source 已追到 provider wire。**[Agent SDK hooks 文件](https://code.claude.com/docs/en/agent-sdk/hooks)也把 `UserPromptSubmit` 列為 Python／TypeScript 都可用的 prompt context 接點。

## 版本差異、長內容與恢復

- [v2.1.89（2026-04-01）](https://github.com/anthropics/claude-code/releases/tag/v2.1.89) 記載 Bash 對 formatter／linter 修改已讀檔案新增警示；這支持防止 stale edit 的產品目的，未說每次外部手改都自動全文同步。
- [v2.1.208（2026-07-14）](https://github.com/anthropics/claude-code/releases/tag/v2.1.208) 記載目標文字仍唯一時，不再因讀後改變直接令 Edit 失敗，對應現行 tools reference。
- [v2.1.260（2026-09-03）](https://github.com/anthropics/claude-code/releases/tag/v2.1.260) 修正 rewind 遺留檔案讀取追蹤、造成錯誤未改提示及外部修改後全文重注入。這證明產品存在外部變更／重注入相關流程；release 沒給正常觸發、範圍與完整性契約。同版也修正 skill／slash command 遺失 IDE 選取 context。
- [v2.1.261（2026-09-04）](https://github.com/anthropics/claude-code/releases/tag/v2.1.261) 修正 resume 時遺失並行 tool calls 周邊 hook output/context、使恢復請求不同。可見保存與恢復也必須驗，而非只驗 callback 回傳成功。
- [現行 hooks 文件](https://code.claude.com/docs/en/hooks#add-context-for-claude)將超過 **10,000 字元**的單筆 context 存檔，給模型路徑與短預覽；resume 重播歷史注入，不重跑過去 hook，時間／版本等可能過期。v2.1.89 曾記載 **50K**，不得拿舊門檻當現行承諾。
- [Anthropic context engineering（2025-09-29）](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)支持少量高訊號 context，加上路徑等輕量識別供工具按需深讀；Claude Code 採預先 context 與按需探索混合方式。這支持有限摘要＋可回查內容的分工，**不是本案 revision／diff 格式的官方規範**。

## Caliburn mapping 與剩餘 unknown

**Mapping：**在顧問下一輪開始前，由 App 從唯一 JD owner 比較上次已供模型看到的基準與本次已保存版本，把事實性的文件狀態／人工改動及可查來源送入模型；小差異可直接帶入，長差異先帶足以識別影響的摘要與版本化回查位置。這是本案落地設計，得到上述產品先例及 context 接點支持，不能稱為照抄 Anthropic 的內部實作。

尚須由本案接線／驗收閉合：基準在成功、取消、失敗、重開、compaction 後如何恢復；模型實際收到哪些版本／範圍；長差異未全載時如何避免假裝完整知悉；工具回查取得同一版本；空白新稿、未知基準與未保存候選的明確語意。單純 UI 顯示變更、工具能讀最新版或回傳注入欄位，不等於此驗收已完成。

本輪 finding：**官方依據足夠支持主動 context 的方向；全面自動外部 diff 的 Claude Code 內部契約仍 unknown，無須再擴大搜尋才能做本案有限設計。**下個 gate 是將本案模型可見輸入與恢復情境納入既有 Task 3 接線驗證。未改 register／主設計／契約／plan，未執行 runtime 或模型實驗。
