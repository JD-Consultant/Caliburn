# Q019 Runtime：訪談、原生推理、Context 與失敗恢復

> 2026-09-06 · **Owner 同意進入隔離開發的 Working Design；原生延續／PG恢復／Memory工具／C受控刷新已完成隔離測試，第七切片review無阻塞；尚未做付費測試或UI／應用入口整合。**
> 最新接線、120 passed／0 skipped證據與未做範圍見[第七切片結果](2026-09-06-analysis-only-agent-live-memory-results.md)；以下生命週期含仍待實作的應用能力，不可把設計全算成已交付。
> 父稿：[完整方案](2026-09-06-analysis-only-agent-design.md)。本稿只持有 A 的接線；Memory 寫入由[Memory 稿](2026-09-06-analysis-only-agent-memory-design.md)持有。

## 1. 選型與責任

推薦 `LangChain create_agent → ChatOpenAI(use_responses_api=True) → OpenAI Responses`；compiled graph 使用 LangGraph PostgreSQL Saver。這不是要保留舊 Caliburn 元件，是重新使用官方 loop、middleware、持久步驟及檔案 backend。

普通 OpenAI Agents SDK 是完整可用的替代，不是被排除；三方案與未選理由見[審核稿 §2](2026-09-06-analysis-only-agent-design-review.md)。**不並行維護兩套主 Agent。** OpenAI 直連指 provider endpoint，不表示同時運行另一個 Agents SDK Runner。

| 層 | 官方元件承接 | 我們提供的部分 |
|---|---|---|
| Agent loop | `create_agent` 的 model／tools 循環 | 顧問 instructions、工具許可、上限 |
| Provider | `ChatOpenAI` Responses adapter | 型號、reasoning、context_management、金鑰與能力檢查 |
| 持久訪談 | PostgreSQL Checkpointer，完整 messages | document→thread 路由、UI 投影、原文 reader |
| 每次 request | model middleware／`request.override` | 有界視圖、固定本輪的 Memory 導覽、預算 |
| 分析方法 | Deep Agents 公開 Skills／Filesystem middleware | 檔案內容與目錄；只讀，不開任意電腦操作 |
| Tools | 官方 filesystem primitives、LangChain tools／ToolMessage | 隔離範圍、來源 reader、C 發布接點 |
| 可觀察性 | LangChain callbacks／官方使用量 metadata | 本機 run log、UI 錯誤與 token／cache 分項 |

依據：[Agent](https://docs.langchain.com/oss/python/langchain/agents)、[OpenAI adapter](https://docs.langchain.com/oss/python/integrations/chat/openai)、[middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[Skills](https://docs.langchain.com/oss/python/deepagents/skills)。公開元件存在不等於這個版本組合已驗證；施工時鎖定一組當時最新、相容的穩定版本，禁止引用 private helper。

## 2. 一輪的完整生命週期

1. Web 送出文字。Runtime 決定文件範圍、訊息識別與 run 識別；LLM 不填。每份文件同時只允許一個 A run，Web 顯示忙碌且禁止再次送出。
2. 新訊息先進 canonical messages 的 durable checkpoint，才呼叫模型。重試引用已保存的同一則輸入，不把同一員工訊息 append 第二次。這不提供改寫歷史的產品操作。
3. 讀一次目前已發布 Memory head；本輪初始導覽與 read tools 綁定這一版本。新問題的相關資料不足時，模型可搜尋正文、讀詳記與原文。只有 C 成功或 stale 的明確工具結果可以受控切換 read head；背景發布不暗中替換本輪版本，見 Memory §6。
4. 每次真正呼叫模型前，middleware 從 canonical messages 建立 **request view**，處理原生 compaction 的有效起點，加入固定規則、導覽與本輪可用工具。不是只在員工按送出時算一次預算。
5. 模型可以直接回答／追問，或使用工具。工具結果回同一 Agent loop；不另啟「是否分析」「是否使用記憶」的分類模型。
6. 保存完整 assistant／reasoning／tool items；只有對員工的正常回覆投影到聊天介面。不把 opaque reasoning 顯示成可讀思考，不要求另產一份長分析表單。
7. 完成的訪談範圍成為 B 可處理來源。A 完成、錯誤或取消都有 terminal UI 狀態；B 未完成不鎖住下一輪聊天。

LangGraph durability 是保存與恢復的機制，不是對外部副作用的 exactly-once 保證；本案以官方 durable steps 保存模型結果，以 Memory 發布回執辨識已完成的工具效果。[Durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)

## 3. 原生 reasoning／thinking：必須保留什麼

**Official fact：**OpenAI 最新公開 GPT-5.6 family 支援跨回合 `reasoning.context="all_turns"`；實際可延續仍取決於先前相容 response items 是否提供。這不等於可讀、可編輯的長期工作知識。不同 family／provider 不保證互通。[原生延續說明](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)

**本版配置提案：**直連 OpenAI，先以帳戶可用的 Luna／medium 為開發基線；A／B1／B2 分別配置，不做本輪中途自動切 provider。採 `store=False` 的完整 item 延續，避免同時混用本地全歷史與 `previous_response_id` 再送一遍。實際模型字串由部署配置及帳戶能力確認，不把 Codex UI 別名當成一定有效的 API model ID。

v1 A 設 `parallel_tool_calls=False`，使讀取→C→結果的先後明確，避免同一批仍在讀舊版又發布新版。這是可調接線取捨，可能增加部分讀取往返；先不寫平行讀／寫排程器。參數支援及實際行為納入 provider 最小相容檢查。[ChatOpenAI tool calling](https://docs.langchain.com/oss/python/integrations/chat/openai)

保存／重送必須包含：

- 原始員工與 assistant items，而不是只取 `.text`。
- opaque／encrypted reasoning、必要的 signature／metadata、assistant phase。
- function call 與匹配 result，及原生 compaction item。
- 工具返回之後繼續時所需的完整有效順序；不能任意抽掉推理區塊或重排 tool pair。

LangChain 官方 adapter 已有 Responses reasoning／compaction 的表示與轉換。但本輪查閱的 source，其 `response_metadata` 並沒有保證暴露 response 頂層所有 reasoning 設定。**不能只看到輸出正常，就宣稱 effective all_turns 已驗證。** 開發初段以最小兩輪原生 SDK 對照及 adapter round-trip 檢查；不 patch private converter、不讓 LLM 填「我有保留推理」來驗證。[adapter 文件](https://docs.langchain.com/oss/python/integrations/chat/openai)、[本輪核對 source](https://github.com/langchain-ai/langchain/blob/master/libs/partners/openai/langchain_openai/chat_models/base.py)（動態分支，實作時須另鎖版本）

若這個最小相容檢查不成立，**停止此 adapter 接法，改用 OpenAI Agents SDK／原生 Responses，不用文字摘要假裝達成 reasoning。** 這是明確替換條件，不是預先建兩個 runtime。

## 4. Context 與 Compaction，不是刪原文

### 4.1 每次 request 的內容

```text
精簡固定規則＋本輪固定的小型 Memory 導覽
原生 compaction 後仍有效的 conversation／reasoning items
尚未被 compact 的近期原始訊息（含本輪輸入、工具呼叫／結果）
需要才取得：Memory 正文 → 詳記 → 原始問答；分析 Skill
```

首次尚無 Memory 時沒有假導覽。知識剛更新而下一輪開始時，讀新 head；不要把導覽每輪 append 成一則員工對話。初始導覽在一個 run 內固定；C 成功／stale 工具結果會明確附上新版導覽與後續有效 head，取代舊導覽的現況效力，但不改寫歷史 prefix。read tools 與 C base 隨該結果一起切到新版，不能新導覽卻仍查舊檔案。沒有這個受控刷新事件時，本輪始終讀固定版本。

### 4.2 採原生 compaction，非通用文字 summarizer

配置 OpenAI `context_management` 的 compaction threshold。它處理的是送入模型的延續視窗，不是本機訪談資料庫的保留政策。完整 output（包括 compaction）照常保存；下一次 request view 依官方規則從有效 compaction item 延續。**只有視圖可以移除其前面的舊項目，canonical messages 不做 RemoveAll、不清除歷史。**[官方 server-side／standalone 區別](https://developers.openai.com/api/docs/guides/compaction)

**2026-09-06 實作狀態核對：**[provider.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/provider.py) 已接受可選 `compact_threshold`，預設 `None` 時不送此 compaction 配置；32,000 是參數 round-trip 的測試數值，不是正式預設。應用入口尚未接上，不能寫成目前已按某個固定 token 數自動壓縮。啟用後依官方 server-side 契約，由服務端在渲染後 context token 跨過配置門檻時觸發，不按訪談回合數／閒置時間，也不用每回合額外呼叫獨立摘要模型。模型、工具結果與規則等完整 request 預算仍須預留餘裕；精確啟用值在應用配置／真模型小額驗收核對。官方 Compaction 頁本日再次核對；本地原文保存及 [context.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/context.py) 的非破壞視圖是本案已驗證接線，不把模型有損壓縮說成無損長期 Memory。

切點以 provider 原生 item 契約為準，不能把「一個 LangChain AIMessage」假定成「一個 Responses item」：同一 message 可能包含多個 content blocks。須保留有效 compaction 及其後全部必要 items／metadata，不自行剪掉 tool pair。若公開 adapter 無法安全表示此視圖，這屬 §3 的原生 SDK 替換條件。

不在同一條路徑疊 LangChain Summarization、LangMem summary、Deep Agents generic summary 三套壓縮。一般文字摘要無法自行解讀 encrypted reasoning。未啟用原生 compaction 的模型不能默認得到相同效果。

Compaction 仍可能耗 token、改變可直接看見的細節。B 不靠它做完整抽取；回查工具不把它當原句。過長**單次輸入**已超模型限制時，單靠閾值不能救回：UI 明確請分段，未送出文字留在輸入框，不偷偷截掉中段。

### 4.3 預算與快取

官方 token counter／provider usage 為基礎；計算包含規則、工具 schema、導覽、items、工具結果及輸出／reasoning 餘裕。中文估算須留安全空間，估算不是帳單。參數依所選型號上限定，不寫死全模型相同數字。[預算證據與限制](2026-09-06-context-window-retention-and-budget-wiring-review.md#2-完整-request-預算現成-api-做得到什麼)

固定 instructions／工具／Skill metadata 順序；導覽只隨 Memory 更新改變，減少 prefix 變動。先用 provider 自動 prompt caching，不自行維護一套回答快取。cache hit 降低部分重複輸入費用，不代表輸入不占 context，不免除新的推理／輸出費。[OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)

## 5. 給模型什麼，哪些不是模型填的

### 主顧問 instructions 的內容範圍

- 用訪談了解實際工作、情境、差異、限制與未釐清處；不要把一個網站案例直接當成固定工作職責。
- 不確定或新舊說法矛盾時詢問，不能按時間新舊自動判定哪句正確。
- 當前對話與已驗證工具結果優先；Memory 是可修訂知識，歷史詳記是當時記錄，不保證是現況。
- 相關才讀 Memory；結果不足改詞、沿引用深讀，不能「沒搜到」就斷言員工沒說過。
- 已清楚的錯誤可 C 修補；存失敗就如實說，不宣稱已記住。
- 本版只訪談分析，不提供 JD 操作工具、不產 JD changeset；不要把全部內部分析長文輸出給員工。

方法內容依既有分析研究萃取成少量 Skill：**工作範圍與案例訪談、案例比較與工作模式、依需要深入的分析準則**。Task／Duty／OPKS 的分析方法可參考，不在 v1 變成必填表單或固定訪談階段。正式 Skill 文字在施工時依這些邊界整理，不虛構「既有 Skill 已搬好」。

### 工具面

| 模型能力 | 輸入形狀／返回 | 框架／自訂界線 |
|---|---|---|
| 目錄、文字搜尋、讀檔 | 官方 `ls`／`glob`／`grep`／`read_file` 形狀；頁面有界，可續讀 | 重用 filesystem primitives；本輪 namespace 與實際路徑由 runtime 限定 |
| 精確原始問答回查 | 已取得的來源引用＋續讀位置；返回實際 role／文字／下一頁 | 自訂薄 reader，底下官方 checkpoint state API；沒有另存一套員工原話 |
| C 局部修補 | `edits` 中每項為既有路徑、old_text、new_text | 重用 backend edit 語意，包成一次發布；不讓多次獨立 put 直接改 live Memory |
| 載分析 Skill | 讀官方 Skills metadata 指向的檔案 | 官方 progressive disclosure；不填 skill_ids、沒讀過的方法不能假裝已知 |

`read_file` 不是任意讀使用者電腦；路徑僅在當前文件的虛擬 backend 和只讀 Skill 目錄。Agent 不獲得 shell／全磁碟／網路發信。原文中的指令視為資料，不提升權限。工具名稱是實作介面，可跟隨官方 API；上述不是強迫 SDK 另發明同義工具。

Runtime 自行處理 scope、版本、時間、來源定位、工具使用紀錄。模型負責文字與引用選擇；不得填 UUID、中文字元 quote offset、已用 Skill ID、執行回執或成本數字。引用只能使用讀取結果已提供的位置。

## 6. 錯誤、停止與重新開啟

> **應用接線狀態：**Task1已保存`3118e8a1`；Task2已保存`e1a3cbf0`／`q019-safe-turn-closure-v1`，最終209項含PG全過，獨立審核R01關閉。[Task1結果](2026-09-06-analysis-only-agent-conversation-lifecycle-results.md)與[Task2結果](2026-09-06-analysis-only-agent-safe-turn-closure-results.md)保存證據。Checkpoint A完成先回報，不接API／UI；以下仍含未實作產品目標，不代表已提供實際worker取消、排程或總金額保證。

| 情境 | A／UI 行為 | 保存／後續 |
|---|---|---|
| 參數或不存在路徑 | ToolMessage 說明哪個輸入有問題、可採的下一步 | 有界修正，不整輪重送員工訊息 |
| 短暫網路／限流 | 一層 transport retry，依 provider backoff | 不疊三套 retry；使用量記錄實際嘗試 |
| 錯誤金鑰、無權模型、不相容 schema | 直接顯示配置錯誤 | 不反覆請模型修復，解除聊天忙碌 |
| 工具／model step 用盡 | 終止本輪並說明未完成 | 不限制整個 thread 一生能呼叫的次數 |
| C 寫入結果不確定 | 先查發布回執，不直接再改一次 | 沒確認成功不說已更新 |
| 使用者關頁 | 後端既有 run 可繼續，重開查狀態 | 不因 UI 斷線重啟第二個 run |
| 程式重啟 | 重載已保存 checkpoint；未完成 run 顯示中斷 | 依最後安全步驟恢復或讓使用者繼續，不能顯示永遠分析中 |
| 取消 | 停止未完成模型工作並結束 busy | 已成功的 Memory 修補不假裝回滾；告知實際狀態 |

使用官方 `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`／Tool error middleware，但注意它們的 error／end／continue 模式不同；必須按選定版本做短測，不能在未配對工具結果時直接截斷 messages。工具錯誤回給模型不等於官方會無限自動修好。[官方 middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)

**可調工程初值，非大廠共識：**A 每 run 最多 6 個 model steps、8 次工具呼叫；單一可修正錯誤最多再修 1 次；transport 最多 2 次 retry。需要更多的場景以 log 討論調整，不默默擴成無界迴圈。B 另有獨立限額，不消耗 A 的 thread-lifetime 額度。正式付費 smoke 前仍需設定總金額上限，本輪未呼叫模型。

**同日應用接線校準：**前述6／8是歷史初值，新隔離 conversation factory 暫採9 model／8 tools，可容納已測深讀、一次必要修正與最終回答；完整邊界與結果見[本段結果](2026-09-06-analysis-only-agent-conversation-lifecycle-results.md)。不是各家固定數字／真模型品質結論。手動恢復一次的新提案已撤回，與「參數錯誤再修一次」不同。SDK／模型修參數／checkpoint resume 的來源集中在[失敗處理核對](2026-09-06-analysis-only-agent-failure-recovery-review.md)，不疊乘重試。

## 7. 儲存與觀察的誠實界線

標準 Checkpointer 可能重複保存增長的 message channel，長訪談資料庫成本不是常數。新版 DeltaChannel 可改善，但本輪查到的是 beta，且相關 private reducer 不宜當 drop-in；**v1 不以私有／beta 接法交換「無限長零代價」承諾**。[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)

保留 canonical conversation 的政策與 request compaction 完全分開；v1 不啟用刪除舊來源的 TTL／pruning。read tool 回給模型有界，不代表底層 get_state 只從 DB 讀那幾行。代表性長訪談若顯示 snapshot I/O 不可接受，重開原文 substrate，原生 SDK SQLAlchemySession 是實質替代，不先自寫另一份 append-only 訪談 store。

本機 log 保存 model／參數、input／output／cached tokens、耗時、tool 次數、Memory 版本與錯誤；不記錄金鑰，不嘗試解密 reasoning。完整訪談不默認送外部 tracing SaaS；開發者要看內容才顯式啟用。這是最小診斷，不建大型 eval／觀測平台。
