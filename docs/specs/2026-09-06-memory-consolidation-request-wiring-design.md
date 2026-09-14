# Q019：主顧問如何通知背景整理

> 2026-09-06 · `Q019-MEM-CADENCE-01` 接線子稿 · **Owner 已核准通知／結果政策，准隔離施工；不是已驗收或 production 授權。**
> Owner「同意那開始吧」核准 §5.1–5.2：通知不等背景完成，成功正常發布，可修復錯誤背景有界處理，未恢復問題於下一次正常 run 放入 Context，不例行喚醒主模型。先做[Task4a 通知切片](../../.worktrees/analysis-only-agent/docs/plans/2026-09-06-memory-consolidation-notification-slice.md)，完整 worker／結果 Context 在後續接線驗證，不能提前宣稱完成。工具契約是應用映射，不宣稱 OpenAI／Anthropic 原生具備同名功能。字數門檻與真模型成本效果尚未定案。

## 1. 閱讀路由與本輪邊界

- 狀態入口：[current decisions](../current-decisions.md)；遵守 [decision process](../decision-process.md)。
- 為什麼選這個節奏、各家差異：[整理時機研究](2026-09-06-memory-generation-cadence-and-continuity-review.md)。不在本稿重複整套 Memory 研究。
- 內容／來源／B1／B2／C：[Memory 設計](2026-09-06-analysis-only-agent-memory-design.md)；服務與恢復：[應用接線設計](2026-09-06-analysis-only-agent-application-wiring-design.md)；施工路由：[接線計畫 Task4](../plans/2026-09-06-analysis-only-agent-application-wiring.md#task-4背景喚醒與重啟重排)。
- **本輪唯一問題：**通知工具不等待背景整理時，後續成功／失敗如何處理及何時讓主顧問知道？通知保存與空參數方向不重開。
- 不做：JD 編輯、每輪整理判斷 Agent、topic 資料表、第二份 Memory、另一個 idle timer、付費模型測試。Task3 的既有隔離 API 授權不變。

## 2. 官方契約與選項

下列於 2026-09-06 查核。官方只證明 primitive 的行為，不替本案選定最佳排程或保證成本。

| 方案 | 官方能力 | 本案取捨 |
|---|---|---|
| **按需工具＋工具結果 metadata（建議）** | LangChain `ToolMessage.artifact` 可存供程式使用、但不送入模型的額外資料；`@tool` 的 `content_and_artifact` 可回傳內容及 artifact。 | 主顧問只選擇是否呼叫；訊號跟工具結果走既有對話保存。一般會有模型接續步驟，需計入成本。 |
| 按需工具＋`Command` 更新 state | 官方工具可回傳 `Command(update=...)`；parent／subgraph 以共享 state keys 傳遞資料。 | 也能實現，但需定義及傳遞額外狀態；目前單一通知可先用既有訊息承載，不因為有 Command 就多建旗標。 |
| 最終回答附小型 Structured Output | `ProviderStrategy` 可用原生結構化輸出；同時使用 tools 時，模型須支援兩者並用；`ToolStrategy` 行為不同。 | 可避免專用通知工具造成的接續步驟，但要設計回答／串流解析及適用模型契約。兩個簡單欄位不是必然過大或不可靠；若工具成本不值得，可回來比較。 |

來源：[LangChain messages：artifact](https://docs.langchain.com/oss/python/langchain/messages#tool-message)、[tool decorator API](https://reference.langchain.com/python/langchain-core/tools/convert/tool)、[工具更新 state](https://docs.langchain.com/oss/python/langchain/tools#update-state)、[Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)、[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)。API reference 的網頁擷取本次遇到 content-type 限制，因此另核對已安裝框架原始碼，不把擷取失敗當成 API 不存在。

OpenAI 公開的 function-calling loop 是模型提出工具呼叫、應用執行並交回結果，再由模型接續；不是零成本的隱形通知。[OpenAI：Function calling](https://developers.openai.com/api/docs/guides/function-calling#how-it-works)

不採 `return_direct=True`：它會結束 Agent 並把工具結果直接作為最終輸出，這裡的技術收據不能取代顧問回答。也不把 headless tool 誤當成不用模型接續的通知元件。[LangChain：Return directly](https://docs.langchain.com/oss/python/langchain/tools#return-directly-from-a-tool)、[Headless tools](https://docs.langchain.com/oss/python/langchain/tools#headless-tools)

## 3. 建議契約：只通知，不整理

工具暫名 `request_memory_consolidation()`；模型可見參數為空物件 `{}`。

| 資料 | 由誰產生／用途 |
|---|---|
| 是否呼叫 | 主顧問依正在訪談的脈絡判斷；不是固定每輪都呼叫。 |
| 工具 `content` | 程式固定短收據，例如「收到整理請求；系統會在本輪安全結束後評估排程。背景尚未執行，記憶尚未更新；請繼續完成本輪答覆。」 |
| 工具 `artifact` | 程式固定標記，例如 `{"kind":"memory_consolidation_requested"}`，供 dispatcher 辨識；不是 LLM 額外填的欄位。 |
| 文件範圍、tool call ID、回合及來源邊界 | 由既有 Runtime／框架訊息與安全封閉紀錄取得，模型不填 topic ID、版本、時間、來源 ID 或 job ID。 |

**工具本身不寫 Memory、不建立外部作業、不呼叫另一個模型。** 它只回傳上述結果；正常工具執行與 checkpointer 負責保存訊息。後續 dispatcher 才處理 admission、啟動或恢復 B。artifact 是技術 metadata，不是第六種 Memory 產物，也不是另一份工作理解。

Prompt 只需說明用途與邊界：累積一段值得整理的新進展時可提出要求；可仍有未答問題，不要求主題完全分析完。不要每輪例行呼叫，也不要為了呼叫工具重寫詳記、候選或理由。是否「值得」仍需後續真訪談校準，不以 Prompt 字句保證品質。

**施工細節核對（2026-09-06）：**已安裝 LangChain Core 的 `BaseTool._to_args_and_kwargs` 對無欄位 StructuredTool 直接使用空參數；多餘輸入不會進函式，空 Pydantic schema 的 `extra=forbid` 也不能在這條捷徑上提供驗證。此純通知沿用框架行為，不為禁止無效多餘欄位而新增 Runtime guard 或隱藏假參數；判定成功依實際保存的 artifact／呼叫配對，不再另要求原始 args 必須恰為空而漏掉框架已成功的通知。模型可見 schema 仍無需填任何欄位，scope 仍由 Runtime 取得。這是實測的框架接法，不是額外模型資料政策。[官方 source](https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/tools/base.py) 與 lock 中實際版本相互核對；精確版本及回歸留在切片結果，不推論未來所有版本相同。

## 4. 正常接力與原文範圍

1. 員工訊息先依既有方式保存；主顧問使用近期問答、可用 reasoning 與按需 Memory 訪談。
2. 主顧問判斷有整理價值，按需呼叫工具；框架保存呼叫與成功結果。模型看到短收據後完成原本答覆，不等待 B 完成。
3. Runtime 確認本輪已安全封閉，再從 canonical conversation 讀取**已保存、與已知工具呼叫配對、成功且具有指定 artifact** 的通知。不能解析員工文字或顧問回答中的「換個話題」來代替訊號。
4. Dispatcher 判斷是否有未處理來源、既有 B 是否要恢復及並行限制，再排入 B。回合安全結束不等於顧問成功回答；沿用既有失敗來源規則。
5. B 仍循既有流程抽取詳記／候選、整併理解及導覽。只有成功發布才前推已處理來源游標，不以「已通知」假裝已保存 Memory。

框架支持以 checkpoint 保存 graph state，以及 parent／subgraph 共享 messages；這是上述接法的底層依據。**本應用的 artifact 穿越子圖、PG round-trip 與重啟還原仍須離線驗證，不能從 API 存在直接宣稱已通過。**[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)

通知只影響「何時整理」，不把範圍裁成某個主題。B1 仍處理上次游標後的可抽取原始問答，包含途中 A／B 交錯的線索及必要前置問句。同一主題可以分段，之後也可以補充或更正；原生 reasoning 不交 B1 解碼。

**文字量後備：**沿安全來源範圍計算上次成功處理後新增的可見訪談文字，不計整份歷史、重複前置 Context、隱藏 reasoning、工具收據或技術事件。用來源實際的人／AI 訪談內容，不以目前 request 的壓縮視窗代替原文；門檻只是負載訊號，不是品質判準。單位／數值仍待配置；舊 6,000 字不是已核准初值。

## 5. 失敗、恢復與不重複做

- **已有 B：**不啟動第二個整併者。多個通知合併為既有待處理來源範圍的整理需求；B 執行中新增的訪談留給下一批，不改掉執行中的來源快照。
- **恢復判定：**用 canonical 訊息順序、通知所在回合的封閉邊界及成功 publication cursor 比較。不要以 UUID 字面大小推先後，也不只保留一個可能提前清掉的布林值。若 B1 有界批次尚未涵蓋通知要求的封閉範圍，不能因部分發布就消掉後半段要求。
- **重啟：**先沿既有 B checkpoint／receipt 恢復，再處理尚未涵蓋的有效通知及文字量觸發；不另外建立一張 durable notification／outbox 表。保存通知後、喚醒前程序停止，仍可由 canonical 資料找回。
- **沒訊號也沒達門檻就關頁：**保留原文與未處理範圍，下次恢復沿相同兩條件評估；不偷偷加另一個 idle timer，也不宣稱短段落已進理解。這是目前策略的限制，若驗收證明累積太慢再討論補齊條件。
- **工具沒成功保存結果：**不視為已提交整理要求；原始問答仍保存。明確安全收尾後可繼續訪談，後續訊號／文字量仍可涵蓋這段，不能編造成功 receipt。

### 5.1 通知回覆與背景結果是兩次不同的交接

**釐清而非翻案：**§3 工具一直只回覆收到整理要求，不執行 B1／B2；主模型只等這個本機交接，不等背景模型完成。正式框架工具往返仍須回覆，不能把 call 懸空當成 fire-and-forget。背景後來成功／失敗是另一個作業狀態，不改寫原先的工具收據，也不為同一 call ID 再附一個完成結果。

下列官方頁面於 2026-09-06 重新開啟核對，區分產品與原生 SDK 能力：

| 官方證據 | 實際能力及限制 |
|---|---|
| [Claude Code async hooks](https://code.claude.com/docs/en/hooks#run-hooks-in-the-background)、[執行與限制](https://code.claude.com/docs/en/hooks#how-async-hooks-execute) | `async:true` command hook 背景執行、不阻塞 Claude；輸出在下一個 conversation turn 交回 Context，閒置時通常等下次互動。另有 `asyncRewake` 在 exit code 2 時喚醒 Claude。這是 Claude Code harness 能力，不是所有模型／框架內建；也不證明 Claude Memory 整理本身用這個 hook。async hook 不自動去重，CLI 結束時另有生命週期限制，不能拿它代替既有耐久 B workflow。 |
| [OpenAI Background mode](https://developers.openai.com/api/docs/guides/background)、[Webhooks](https://developers.openai.com/api/docs/guides/webhooks#handling-webhook-requests-on-a-server) | 可先啟動非同步 Response，再查狀態或由 webhook 通知應用；官方要求 webhook endpoint 快速回應，把耗時工作交背景。通知送到應用，不會自動塞進另一個模型請求的 Context。這不是一個參數就讓整個 B1／B2＋本機發布都耐久完成；本案也不為類比而新增公網 webhook。 |
| [LangChain subagents：Async](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents#asynchronous) | 官方明確區分等待子 Agent 的 sync 與啟動背景作業後繼續的 async；展示 start／status／result 模式。它是設計方式，不是把函式寫成 Python `async` 就自動不等結果，也不是強制本案增加三個工具。 |

共同可學的是「交接確認與工作完成分離、背景狀態可觀察」。**成功是否通知、失敗是否喚醒、何時放入 Context 沒有統一規格。** Claude 的普通 async 與 asyncRewake 就是兩種不同取捨。不能將通知稱為無需保存／無需錯誤處理。

### 5.2 建議：背景處理、例外在下一次正常訪談告知

此 Caliburn mapping 已於 2026-09-06 獲 Owner 核准；不新增例行喚醒主模型。

- **通知已交接：**工具回覆短收據後，主顧問完成答覆；B 等安全來源邊界後自行跑。不要同步 `invoke`／等待 B 完成才回覆通知工具。
- **整理成功：**B 正常發布。主顧問下次正常 run 沿既有讀取規則取得當時可用的理解／導覽，不另叫主模型解說「整理完成」，也不灌入完整 B transcript。不能中途把已送出的模型 Context 改掉；同輪原有 Memory 版本協調維持不變。
- **可自動修復的失敗：**沿既有分層處理；暫時網路／限流由 SDK 有界重試，B 模型的工具參數錯誤由 B 自己依回饋修正。不是每次小錯都通知主顧問，也不讓 dispatcher／SDK／模型再疊多層無限 retry。
- **仍未恢復且影響記憶可用性：**保留原文、已成功發布版本與既有 B 的真實失敗狀態。建議在下一次正常主顧問 run 組 Context 時帶一段程式產生的短提示，說清楚「哪段尚未整理／目前記憶可能未含新資訊、原文仍可回查」，不把技術 stack trace 或秘密送進去，不要求員工修 API／資料庫。
- **事件新鮮度：**Context 從當時的 B 狀態／publication 取得；若背景已恢復，不能再投遞舊失敗通知。持續失敗的當前限制可保持可見，但不逐次重試附加一段歷史訊息，亦不假裝只提示過一次後問題就消失。
- **何時知道：**這個建議是下一次正常 run，而非保證背景失敗瞬間打斷當前推理；不偽造員工訊息、不把提醒送成不配對 ToolMessage。若未來真需要即時喚醒，再比較 Claude asyncRewake 類型的事件驅動機制及額外模型預算。

範例短提示（由系統真實狀態產生，不是 LLM 填）：`最近一段訪談尚未成功整理進長期記憶；原始問答仍保存。回答時不要假定記憶已含這段資料，必要時回查。` 配置問題另走應用技術狀態，不自動把訪談變成維運對話。若不是技術失敗，而是 B 分析發現員工敘述有疑義，仍沿內容／待釐清的既有流程，不混成 job error。

**框架接法候選：**B checkpoint／publication 已是背景真實狀態來源；主顧問的 Context middleware 可在正常 run 開始取得狀態，注入精簡程式提示，不另建通知資料庫。官方 `dynamic_prompt`／`wrap_model_call` 支持組裝請求 Context，但不會自動知道本案哪些失敗值得告知；這個小型映射仍由應用負責。[LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)

**未直接採用的選項：**每個背景失敗都喚醒主模型，會增加模型請求、額度及前台排程協調；等待完整 B 結果又失去前台不等待的目的。LangSmith Deployment 另提供[背景 runs](https://docs.langchain.com/langsmith/background-run)，不能說本機 OSS `create_agent` 天生有同一服務。現階段保留既有本機 worker，不因多看到一個名詞就重換架構。

### 5.3 必要接線修正（Task4a 已實作／隔離驗證）

本次讀取隔離程式發現，`close_turn()` 遇到未配對工具呼叫，除了可證實未執行或已知 `repair_memory` 對帳以外，目前會回報 `PublicationUncertain`。**這不是新增工具已發生的 bug，而是加入它之前必須處理的整合缺口。** 若只加工具，不補取消／失敗收尾，可能讓這個純通知被當成未知外部寫入而卡住。

新工具明確沒有外部副作用，因此 worker 確實停止後，若沒有已保存的成功結果，可回傳「整理請求未成功交接」的配對失敗結果並封閉回合；若已有成功結果，保留它。這個例外只適用本工具，不改 `repair_memory` 的真實發布對帳規則，不泛化成所有工具都可假定失敗。

實作定位：[conversation.py：close_turn](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py)、[request-only compaction view](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/context.py)。Task4a已實作通知窄例外並保持C對帳；[結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-06-memory-consolidation-notification-results.md)記錄244項含PG全過、獨立review與scope。此處不代表完整scheduler／背景失敗Context已驗收。

## 6. 成本與最小驗證

新增工具定義會增加少量固定輸入；實際通知通常還需要一次主模型接續。空參數、artifact 不進模型、背景非同步，都不代表零 token。沿既有 model／tool budget 計入，不因新工具偷偷提高上限；不能省下接續步驟卻丟掉顧問回答。若頻率或費用偏高，再比較 §2 小型原生結構化輸出，不先說工具必然最便宜。

Task4 先做假模型＋本機 PG 的少量整合檢查，不另建大型 eval：

- 空參數 schema、固定 metadata；結果經 ToolNode、子圖及 PG 還原後可辨識，metadata 不送入模型，正常問答可完成。
- 成功通知但未喚醒即重啟、重複通知、B 執行中再通知、分批發布：不丟掉未處理段，也不重跑已發布範圍。
- 工具前取消／工具結果未保存／成功結果後中斷：不假報整理成功，不卡住下一輪；C 對帳回歸不退步。
- 無通知且文字量未達門檻不啟動；達門檻仍等安全來源邊界；無新來源不呼叫 B。這只驗接線，不能證明模型善於判斷主題段落。
- §5.2 已准：完整 worker 接線時以可控阻塞的假 B 證明主顧問不等 B 完成；B 成功不額外喚醒模型，終止失敗在下次正常 run 可見，已恢復則不殘留舊錯誤，且不產生假員工訊息／重複工具結果。Task4a 先驗通知本身沒有 B 執行／等待，不能拿它代替完整 worker 驗收。

之後合併進已核准的小額 Luna／medium 訪談驗收與第四步 Prompt 優化，檢查整理頻率、細節回查、短更正、完整訪談總費用及延遲；本輪零付費呼叫。

## 7. 決策結束點

**已決：**段落訊號＋文字量後備為 WORKING 策略；不用閒置 90 秒、固定回合數主觸發或必需的手動按鈕。

**接續狀態：**§5.2 已獲 Owner 核准，實作／驗收分段進行。Task4a通知與安全收尾已保存 `43e2a487`／`q019-consolidation-notification-v1`；Task3／其餘 Task4 尚待接 API、worker、文字量後備及當前失敗 Context。本文不翻案 A／B／C、五產物、來源保存或 authority，也不授權 production。不再重問通知政策或重做整套背景 Memory 研究。

**重開條件：**框架序列化／恢復測試不成立、通知工具妨礙正常答覆或成本不值得、訪談驗收顯示整理過密／過遲，或 Owner 改變觸發需求。來源缺證與效果未知分開記錄，不把本設計稱為各家唯一共識或已證明最佳。
