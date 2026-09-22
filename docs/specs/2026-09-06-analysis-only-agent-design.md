# Q019：從零建立「只訪談、只分析」的第一版 Agent

> 2026-09-06 · **Owner 已同意繼續；作為隔離開發的 Working Design。不是 production 切換或效果測試通過。**
> 最新授權：[決策入口 §0](../current-decisions.md#0-最新任務llm-q019從零設計只分析的第一版)。本稿是新版設計入口；過往研究保留理由，不再要求讀完整討論長文才能知道本版怎麼做。

## 1. 目標與範圍

員工持續與一位顧問聊天。顧問能理解工作、追問不清楚之處、比較新舊案例與修正理解；長訪談、關頁及重新啟動後仍可找回重要細節。**這版不編輯 JD，也不建立待審變更、核准文件、匯出或完整 JD UI。** 分析方法可參考既有研究，但不 import、包裝或遷移舊系統。

本版驗收的是分析與記憶底座，不宣稱已產出「滿分 JD」。保存完整來源、列舉全部知識可以避免機制性漏讀，不能證明模型的每項語意判斷都正確。

- 本機單一操作者；可以有多份彼此隔離的訪談文件，每份一個聊天室、一份 Memory。
- 員工更正就是發送新訊息；不新增更正原句按鈕，不改寫歷史。
- 不另做 Focus／Gap／工作案例專用資料表。未知、差異及未回答的重要問題寫在相關知識的自然語言內容；尚未整理前由近期對話與原生推理延續。
- 工作理解主要供模型使用；員工可唯讀查看，發現錯誤仍用聊天說明。
- 分析中禁止第二次送出；成功、失敗或取消後解除，不把錯誤變成永久鎖住聊天室。
- 舊資料不搬移；**本輪沒有刪除任何資料，也不因新方案省略 migration 就執行清空。**

## 2. 一眼看懂整體

```text
員工的新訊息
  ↓ 保存於同一訪談
A 主顧問：原生 reasoning 延續＋有界 Context
  ↔ 相關時搜尋／讀 Memory、詳記、原始問答、分析 Skill
  ↔ C：確定舊知識需要修正時，用工具局部修補
  ↓ 回答／追問，保存完整模型回應
  ↓ 有新訪談且符合整理時機
B 背景整理（不阻塞下一輪訪談）
  抽取詳記＋候選資訊 → 保存真實來源引用
  → 對照目前 Memory，按需深讀詳記
  → 補充、去重、修訂知識與小型導覽 → 發布同一文件的新版本
```

A 與 B 是兩種工作，不是每個方塊都開一個 Agent。C 是 A 的工具，沒有第三位修補 Agent。一次訪談 run 可能包含多次模型↔工具往返，**不是保證每回合只付一次 API 費用**。

這保留已研究的 OpenAI 分層理由：對話延續、詳細抽取、長期整併、漸進回查各有用途；不是只借用五個檔名。原始證據及與本案的差異見[單訪談流程 §2–5](2026-09-05-work-understanding-memory-flow-working-design.md)、[引用 producer／consumer](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)。

## 3. 本版推薦：LangGraph 組合；OpenAI 原生 SDK 是實質替代

已納入 Owner「框架難用可改原生 OpenAI SDK 或其他」的補充。比較的是整套分析／記憶生命週期，不以舊程式或舊元件名稱選型。推薦沿官方 LangChain／LangGraph 組合；原生 Agents SDK 與 Sandbox Memory 的具體覆蓋、限制及替換條件見[三方案比較](2026-09-06-analysis-only-agent-design-review.md#2-原生-openai-sdk-也已納入不把框架當前提)。本輪不鎖死技術，更不並行造兩套 Agent。

| 責任 | 本版推薦 | 理由／界線 |
|---|---|---|
| 主顧問與整併 Agent | LangChain `create_agent`，底下 LangGraph | 重用官方模型↔工具循環、state、middleware；不再自寫 loop |
| 原生推理／Compaction | **OpenAI 官方 Responses 直連**作參考接法 | 同一條協定完成不透明推理延續與原生 compaction；不拿一般文字摘要冒充推理保存 |
| 起始模型設定 | 支援所需能力的 GPT-5.6 family；沿用 Owner 測試偏好，先以 Luna／medium 作開發預設 | 可分別配置 A、B1、B2 型號／effort；不是品質或費用已勝出的結論，需帳戶實際可用 |
| 訪談與執行保存 | LangGraph 官方 PostgreSQL Checkpointer | 保存完整 message objects；model view 與原文保存分開 |
| 長期知識與抽取產物 | LangGraph PostgreSQL Store；公開 Deep Agents `StoreBackend`／檔案工具 | Markdown 承接詳細內容、關鍵詞及引用；不用另造 Memory 資料庫引擎 |
| B/C 發布協調 | SQLAlchemy 官方版本計數＋PostgreSQL 短交易 | 小型 head／receipt 只保存發布 metadata；正文仍在 Store，不是第二份語意 Memory |
| 兩階段背景接力 | LangGraph workflow＋持久步驟；B1 原生 structured output，B2 `create_agent` | B1 產生少量欄位，B2 可邊讀邊整理；不重複跑 manager 後再整併一次 |
| Skill 按需讀取 | Deep Agents 公開 Skills／Filesystem 元件 | 方法與資料分離；只先載名稱、用途與位置，不預塞全部方法 |
| 錯誤／上限 | LangChain 官方錯誤與 call-limit middleware；單層 transport retry | 不堆疊多層重試；保存與執行失敗不得偽裝模型成功 |
| 本機介面 | 新 FastAPI＋小型 React／Vite Web，單一 API process＋PostgreSQL | 只做文件清單、訪談、唯讀知識與執行狀態；不接舊 App |

官方能力依據：[Agent](https://docs.langchain.com/oss/python/langchain/agents)、[原生推理](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)、[Compaction](https://developers.openai.com/api/docs/guides/compaction)、[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[Store](https://docs.langchain.com/oss/python/langgraph/stores)、[Backends](https://docs.langchain.com/oss/python/deepagents/backends)。這個**整套組合是本案設計提案，不是聲稱 OpenAI／Anthropic 內部使用這套框架**。

## 4. 三個需要明說的取捨

### 4.1 原生推理是延續能力，不是完整可靠的工作知識

保存 provider 原生 reasoning items，有助於下一輪接續分析；不把它解碼成工作筆記、不顯示私有推理，也不承諾永不重算。背景整理仍讀實際訪談，不會讀到 A 的全部隱藏分析。因此 B 有一定整理成本，並非免費搬運 A 的思考。工作知識仍要保存成可讀、可修訂、可回查的 Memory。[OpenAI 區分 conversation／reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)

### 4.2 第一版先打通一條原生接法，不假裝所有模型可無損互換

模型及參數可配置，但切換 family／provider 可能不能沿用舊 opaque state。第一次交付只承諾經相容性檢查的 OpenAI 路線；Claude 是有明確接入條件的後續 adapter，不在這版同時建第二套 Context 協定。Anthropic 新版 preserved thinking 對歷史 prefix 有自己的限制，不能把同一套動態 prompt 拼接直接套上去。[Anthropic preserved thinking](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking)

LangChain adapter 若無法完整 round-trip 所需 native items，就依[Runtime §3](2026-09-06-analysis-only-agent-runtime-design.md)切原生 SDK，不以 generic summary 假裝滿足。尚未實測，不宣稱兩條路線效果已比較勝出。

### 4.3 先採「小型導覽＋按需搜尋」，不強制每輪自動向量召回

這是相對 Q017「少量自動召回」的**明確調整提案**，不是偷偷漏做：第一版導覽指路，模型用關鍵詞找正文、沿引用深讀。避免同時引入 embedding、索引更新及新召回政策；小型導覽不是全文知識，沒有命中也不等於沒說過。

已有原廠實際路線支持這個形狀；不是說向量較差。若同義改寫、跨案例查找的輕量驗收顯示 keyword 路線不夠，再使用 Store 官方 semantic search 加強；不另換 Memory authority。**不把「多家都有某功能」推論為每個專案都必須採相同細節。** [Codex 查找證據](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)、[Anthropic just-in-time／hybrid 取捨](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[Store semantic search](https://docs.langchain.com/oss/python/langgraph/stores#semantic-search)

## 5. 不是每項都得自訂；真正接合處集中在四處

1. **原文 reader**：把 graph 的已保存訊息，變成模型可按引用、可續讀的問答片段。框架有讀 state 的 API，沒有本案完整 transcript Tool。
2. **Context 接線**：原生 compaction item 的 request-view、Memory 更新通知及 Skill 載入，不能破壞原生訊息序列。
3. **背景生命週期**：何時整理、處理到哪段、失敗如何續作。workflow 自帶保存，不自帶本機排程。
4. **Memory 發布協調**：B 與 C 的修改不能互相覆蓋；未完成的正文／導覽不對外當成功版本。採 Store immutable 產物＋SQLAlchemy 小型版本／回執 metadata；這是本輪新接法提案，不宣稱 Store 自動提供所有交易語意。詳見[Memory §6](2026-09-06-analysis-only-agent-memory-design.md#6-背景與即時修補可以並行但發布不能互相覆蓋)。

這些自訂的必要性、較簡替代及安全界線放在下列兩份子設計，不以自訂名詞掩蓋額外成本。

## 6. 詳細資料只放對應文件

| 要看什麼 | 唯一持有細節的文件 |
|---|---|
| 每輪如何呼叫、保存推理、組 Context、載 Skill、處理錯誤與成本 | [Runtime 設計](2026-09-06-analysis-only-agent-runtime-design.md) |
| 五產物、引用、搜尋、背景觸發、即時修補、寫入協調 | [Memory 設計](2026-09-06-analysis-only-agent-memory-design.md) |
| 本輪補查來源、差異、自我審核、能力覆蓋與最小驗收 | [設計審核](2026-09-06-analysis-only-agent-design-review.md) |

本稿只持有整體選擇；後續變更先改持有細節的子稿，再更新此處差異與 register，不在每個文件末尾另加一套新結論。舊研究供追溯，不批次重寫，也不再讀 Owner 排除的 2026-08-12 產品長稿。

## 7. 開發前的停止線

Owner 已回覆「可以繼續了，有問題提出來討論」。現在進入[第一切片計畫](../plans/2026-09-06-analysis-only-agent-native-continuity-slice.md)，先在隔離 worktree 驗證原生訊息的接線與保存，再加入 B/C 與回查。這不是整體分析效果已通過；production 與舊資料不動。每段以[審核稿驗收](2026-09-06-analysis-only-agent-design-review.md)檢查，不以「元件名稱都有」當作完成。

不做大型 eval 平台，不以廣泛模型競賽延誤產品。必要的小型 round-trip、來源回查、並寫／重啟測試不能省，因為它們驗證的是接線沒有做錯；未測試前不宣稱效果最好、永不遺忘或無限長訪談成本固定。
