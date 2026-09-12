# JD 顧問是否需要 LLM 工作區

- 日期：2026-09-12；Topic：JD-R002；G2 研究與推薦，未採用新子系統。
- 問題：既有 Memory／Context 與可反覆修訂的關聯式 JD 之外，是否還需要模型可使用的工作區？
- 範圍：現行本機單人、持續訪談、完整手動管理；不重新設計 Memory、不改正式 authority、不啟動模型實驗。
- 路由：[目前決策](../current-decisions.md)、[需求](2026-09-12-jd-relational-editing-requirements.md)、[完整業務操作](2026-09-12-jd-business-operations-and-scope-design.md)。

## 1. 判斷與用語

**推薦先以既有受控能力完成第一版，不另建通用 LLM 檔案／執行工作區。**這不是禁止 AI 做準備、試想或整理，而是先把需要的能力對回既有 owner：讀材料、修工作理解、形成修改內容、查實際結果及續談。公開資料支持按任務提供工作環境，不能推出每個 Agent 都必須有另一套 workspace。

仍值得觀察兩種不同缺口：一是跨工具／中斷後遺失尚未完成的修改計畫；二是確實需要跨多次工具反覆編修尚未採用的 JD 方案。前者可能只需短期任務筆記，後者是有版本與採用邊界的 JD 暫存功能，不能用同一個「工作區」名稱混過。兩者目前都沒有本案增益實測。

Owner 本輪「同意」接在未完整草稿的兩種意義說明之後。已知任務可先保存部分內容的要求維持；本輪沒有因此直接核准「無所屬任務的成果／要求獨立保存區」，也沒有把它與模型私有筆記合併為新功能。

| 可能稱為工作區的東西 | 實際用途 | 與其他資料的界線 |
|---|---|---|
| 本輪 Context／模型推理 | 讀到資料後比較、判斷與組織本次操作 | 可用視窗有界；推理不是可任意編輯的永久筆記，也不是員工事實 |
| 可持續工作理解 Memory | 案例、未知、差異、更正及回查線索 | 已有 owner，可反覆修訂；不把模型假設或試寫方案當成已確認工作 |
| 短期任務筆記 | 正在做哪项整理、下一步、尚未完成的核對 | 是模型的執行進度，不是員工工作內容；跨回合保存不代表永久有效 |
| JD 暫存候選 | 多次試改、讀回比較，最後才更新目前稿 | 單次候選已有設計；跨多工具／重開續作的獨立草稿生命週期尚未提供 |
| 檔案／程式執行環境 | 操作大量附件、跑程式、產生任意檔案與預覽 | 是 compute 能力；不自動取代 Memory、DB、保存回執或 JD 業務規則 |

## 2. 官方事實與版本界線

以下均於 **2026-09-12** 實際查閱官方正文；官方現行頁不是本案已驗證版本，方法文章也不是 API 保證。未安裝、升級或呼叫模型。

| 來源 | 官方事實 | 適用狀態／授權與限制 |
|---|---|---|
| O1 [OpenAI Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes) | 適合讀寫檔案、執行命令、處理資料目錄與可恢復的檔案工作；harness 管控制／恢復，sandbox 管執行；Session 歷史、workspace snapshots、Memory 有不同用途 | SDK sandbox **beta**，能力／預設仍可能變；服務文件非採用 OSS 授權。Unix-local 範例面向 macOS／Linux，不能冒稱直接適用本案 Windows |
| O2 [OpenAI 證據審查 Cookbook](https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction) | 在 evolving evidence 案例中，來源、工作過程、Memory 與最終可審產物分開；workspace 讓 Agent 按需讀材料及寫產物 | 官方範例，非普遍規格；它刻意把 Memory 限於工作方法，不可據此否定本案 Memory 保存員工工作理解。示例模型與安裝命令不作本案升級依據 |
| O3 [Codex／ChatGPT Memories](https://learn.chatgpt.com/docs/customization/memories) | 本地 Codex Memory 與 ChatGPT web Memory 是不同儲存／控制；記憶輔助回想，必須遵守的指引另放文件；本地 Memory 可在背景更新 | 現行產品文件，未公開全部內部實作；不可把產品畫面的 workspace 名詞等同某個通用 SDK 保存層 |
| A1 [Claude Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) | 模型請求記憶操作，App 執行；`/memories` 是可映射至資料夾或 DB keys 的前綴，並不要求真實檔案系統 | `memory_20250818`，工具不需 beta header，SDK helpers 仍在 beta namespace；服務文件非新增 OSS 套件。其固定命令不直接取代本案已驗 patch |
| A2 [Anthropic Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 將 context 外可回讀的結構筆記視為 agentic memory；compaction、筆記、子代理依工作特性選擇。Claude Code 的即時檔案搜尋是案例 | 2025-09-29 工程方法；文中 Memory 初始 beta 狀態以現行 A1 更新為準。不是所有顧問必有 shell 的主張 |
| A3 [Anthropic think tool 更新](https://www.anthropic.com/engineering/claude-think-tool) | **2025-12-15** 已加註多數情況推薦 extended thinking，而不是獨立 think 工具 | 原文 2025-03-20、舊 Claude 3.7 benchmark 只作沿革；不能拿早期結果要求現行模型每次先寫思考工具。非 OSS 套件 |
| A4 [Claude code execution](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool) | 提供服務端檔案操作及程式執行，容器可跨請求重用，但有到期時間 | 現行頁列 `code_execution_20260521`、不需 beta header；容器建立後 30 天到期。服務端環境不是本機永久 Memory／JD，未採用此服務 |
| L1 [Deep Agents Backends](https://docs.langchain.com/oss/python/deepagents/backends) | StateBackend 可承接 thread 內中間結果，配置 checkpointer 時跨 turn 保留；StoreBackend／CompositeBackend 可按路徑分開長期資料；具檔案介面不代表具 shell | 本地 lock／installed metadata：**deepagents 0.7.13、MIT、Development Status 4-Beta**；現行指南另有較新／舊版範例與遷移說明，不原樣複製。只是可用原生接點，不代表已為主顧問啟用 |

**跨來源共同原則：**只把必要材料帶入 context；需延續的資訊有可回讀的位置；模型提出操作、App／harness 管執行與效力；按任務需要增加檔案／執行能力。

**沒有證據的主張：**「每個高品質 Agent 必須有一個 workspace 表」、「所有大廠都讓模型先維護第二份稿」、「有 sandbox 就不會漏工作」或「多加筆記一定更準確」。檔名、資料夾、表數及本案採用與否都是映射，不是廠商共識。

## 3. 本案已經有什麼

本節核對隔離原碼／設計，**不把隔離成果當 production 已採用**；正式仍沿 ADR0060／G6。新 relational JD 的 DESIGN CLOSED 是文件反例閉合，不是實作通過。

| 能力 | 本地證據與目前效力 |
|---|---|
| 保存原始問答並精確回查 | [Memory 設計 §1／4](2026-09-06-analysis-only-agent-memory-design.md)：Checkpointer 原始資料與逐層回查，隔離已實作 |
| 保存案例詳記、目前工作理解、導覽及較新更正 | 同稿五產物／B1／B2／C；目前接口沿決策入口。未知也可保留，不能把臨時模型猜想直接變已確認內容 |
| 壓縮後續談 | [runtime 設計](2026-09-06-analysis-only-agent-runtime-design.md)、[隔離 context 原碼](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/context.py)：視窗與 canonical 原文分開；有損壓縮不保證語意完全保留 |
| Memory 私有暫存修訂 | [consolidation_tools.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/consolidation_tools.py)：B2 已用官方 StateBackend／CompositeBackend 與私有 staging，多次讀写後發布；只准 knowledge／guide，並非任意 workspace |
| 主顧問讀方法、改 Memory、操作 JD | [service.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/service.py)的 `_context` 及[方法資產說明](../../.worktrees/analysis-only-agent/experiments/analysis-agent/README.md)：按需只讀 Skill 資產，受控工具；未提供主顧問任意 scratch／shell／sandbox |
| JD 整組更正與真實保存結果 | 舊 Plate 核心已有隔離實證；[新 relational 業務稿 §2／5](2026-09-12-jd-business-operations-and-scope-design.md)規定完整候選、同次保存及反例，尚未施工；不是跨多工具的私有 JD 分支 |

因此不能說本案完全沒有「工作區能力」；B2 已有明確用途的受控暫存。也不能反過來說它已覆蓋主顧問的任何試稿需求。

## 4. 最多三個實質方向

| 方向 | 帶來的效果與代價 | 本輪判斷 |
|---|---|---|
| A．既有 Memory／Context＋完整 JD 操作 | 查找、理解、推敲、整組改稿及回查結果；少一份需同步的資料。仍需驗長訪談與复杂修訂是否會遺失進度 | **推薦作第一版基線**；不宣稱自然品質已足夠 |
| B．按缺口增加有界任務暫存 | 可保留未完成計畫；若需求是多輪 JD 試稿，則另需候選讀取／验证／採用／失效生命週期。兩者不可混稱一個筆記工具就完成 | **有條件候選**；先辨識是哪種失敗，再沿框架原生 state／checkpoint 等接點比較；不是此刻一併採用 |
| C．完整檔案／執行 sandbox | 適合大量檔案處理、程式分析及任意產物；增加執行環境、保存／清理與成本責任 | 本輪用途尚無必要證據，**不推薦現在加入**。固定 Excel 匯出由 App 產生，並不需要模型跑程式 |

目前未見獨立 OS workspace 的必要證據，也不等於只能塞在一個 prompt 中。現有資料與工具可讓顧問按需讀取；免費開源的虛擬檔案接點存在，也不等於應直接換成 Deep Agent 全套預設或新增另一套 compaction。

### 具體工作例子

員工說「我只做技術診斷，客戶承諾是窗口負責」。顧問先核對目前理解、JD 及必要原話，判斷哪些正文／要求／K/S 引用受到影響，再提交完整修訂；如需修 Memory，沿原機制分別處理並查真實結果。這段不需要先建立 `JD-draft.md`。

如果實際要求是「AI 先把整份 JD 重新分組成兩種方案，反覆讀回比較，中斷後還能繼續；確定之前畫面保持原稿」，那是新增 **持久 JD 暫存候選** 的需求。目前沒有提供這項完整生命週期；不能把工具單次 validation 稱模型已看過候選，也不能把模型思考等同可重開的稿件。即使後續採用，仍可在同頁呈現，不必新增使用者頁面；具體效果須再確認。

## 5. 有界驗證與採用門檻

本輪不做付費／自然模型測試，以下接續既有品質驗收，只有可重現缺口才增加 A／B 對照：

1. **長訪談／中斷：**讀取、壓縮及重開後，是否仍能找回待釐清的合約差異、重要低頻工作與最新更正？先區分原文未保存、Memory 抽取／讀取失敗、Context 未供給與操作進度遺失。前三類不能只靠另加筆記掩蓋。
2. **複合更正：**正文＋要求＋K/S 修訂有錯誤回覆後，能否核對結果、修正或停止，保留獨立工作？若是完整業務操作缺口，修工具／App 契約，不把半完成狀態轉成 workspace 成功。
3. **試稿需求：**是否確實需要跨多次工具看回未採用內容、比较替代分組及重開續作？若只有單次形成完整更正，沿目前候選即可；若需要，先定與唯一 current 的採用邊界。
4. **候選污染反例：**臨時推測、兩套替代說法及未完成計畫不得當員工事實、已保存 JD 或原始訪談來源；舊 refs／計畫遇 current 改版須重讀，不照舊執行。
5. **比較結果：**同情境比較漏項、錯改、重複工作、資訊保留、錯誤恢復、延遲與模型用量；暫存需有可讀回與續作證據。單一成功示範或筆記增加不能證明品質提升，重大內容錯誤不能被平均分抵銷。

若 B 有明確增益，再形成有界設計：採用既有框架能承接的 state／checkpoint，明定用途、scope、生命週期、資料上限及失效處理。這些仍待研究，沒有在本稿先寫死路徑、表格、工具數或 SQL schema。若需求真涉及 C，另核本機隔離、生命週期與費用；不直接搬雲端示例。

## 6. 狀態與下一步

本輪成果是官方研究、本地能力盤點、三方向取捨與驗證觸發條件；沒有新增表、workspace 工具、prompt、檔案掛載、模型設定或 Memory 流程。停止廣搜同義 workspace 文章；剩餘差異由具體使用目的或既有自然驗收的可重現缺口回答。

JD 主線仍處理未歸任務的成果／要求草稿、自動保存後撤回、歷史與重開恢復。LLM workspace 的必要性不能代替員工草稿需求，也不因本輪研究而阻擋既有已定能力。採用 B／C 前另記產品取捨與必要設計；此推薦不改 ADR0075 Proposed 或 production0060。

**獨立文件審查：**`jd_command_semantics_review` 核官方論證、版本與能力分界，未發現實質阻擋；其非阻擋措辭建議已採，將「沒有需要」收斂為「目前未見必要證據」。`jd_format_audit` 核本地能力、隔離／新設計效力及草稿語意，PASS。這是研究可交付，不代表功能採用或模型實測通過。
