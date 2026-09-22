# LLM machine effects responsibility Working Design

- 狀態：**WORKING；G4 設計中，未獲 production 授權**
- Topic：`LLM-Q014`
- 目的：逐項把第一版 LLM 輸出分配到 canonical assistant message、framework-native Tool、deterministic projection 或窄 structured artifact，避免再次建立一份巨大的混合輸出 schema。
- Production authority：現行 code、`AGENTS.md` 與 Accepted ADR 0060；本文尚不能改 production。

## 1. 閱讀與決策規則

1. 一次只處理一個有爭議的 machine-effect 邊界。
2. 每項先列官方事實，再列 Caliburn mapping；不得把產品選擇冒充跨廠共同架構。
3. Tool 名稱、參數、批次粒度、模型呼叫數、背景部署與 migration 留到父層責任通過後再定。
4. 已由 Memory 決策收斂的產品效果不重開；只有新官方事實、代表性失敗或 Owner 改變需求才重開。

## 2. G4.1 — Semantic Memory 寫入責任與時機

### 2.1 本輪唯一問題

Semantic Memory mutation 應由主顧問在目前 agent loop 直接呼叫 Memory Tool、由回合後的 Memory Manager 背景產生，或由同一套 Manager 依目前動作的資料依賴選擇同步／背景排程？

### 2.2 官方事實

| 來源 | 公開機制 | 可直接支持的結論 |
|---|---|---|
| [OpenAI Codex Memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories) | 合格且已閒置的歷史聊天在背景轉成記憶；公開設定分開 extraction model 與 consolidation model。 | 背景抽取／彙整是成熟路徑；Codex 不要求每個主回合即時寫入 Memory。 |
| [Anthropic Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) | Claude 在工作途中以 Memory Tool 讀、建、改、刪記憶檔；應用程式執行實際檔案操作。 | 主 agent 的 hot-path Tool 寫入也是成熟路徑；模型請求操作、應用控制執行與安全。 |
| [Anthropic Tool-use contract](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works) | Client Tool 每次都需要 model → application → tool result → model 的 agent loop。 | hot-path 寫入有額外 round trip／延遲；Memory 不應埋在 prose 裡由應用自行猜。 |
| [Google Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories) | 可從 session 產生 Memory；event ingestion 可與生成解耦並預設背景處理。 | Managed Memory 的背景 formation 也是現行路徑。 |
| [AWS AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-saving-and-retrieving-insights.html) | conversation event 先保存，long-term extraction／consolidation 非同步在背景執行。 | 原始對話保存與長期 Memory 形成可分離。 |
| [LangChain Memory overview](https://docs.langchain.com/oss/python/concepts/memory) | 正式列出 hot path 與 background 兩種寫入模式；前者即時但增加延遲與主 agent 負擔，後者不增加主回合延遲但結果較晚可用。 | Framework 不替產品固定唯一時機；必須依資料依賴與產品延遲要求選擇。 |
| [LangMem](https://langchain-ai.github.io/langmem/) | 同時提供 `create_manage_memory_tool` 與 background memory manager；兩者都能使用 LangGraph Store。 | 兩種排程可用成熟 primitive 承接，不必自行發明第二套 storage／CRUD framework。 |

### 2.3 跨廠共同點與非共同點

**共同點：**

- canonical conversation／event 先由應用或 conversation runtime 保存；
- Semantic Memory 是從對話形成的另一層可持久、可更新資料；
- 實際持久化與 scope／權限由應用或受控 framework 執行，不能靠自然語言回覆暗示已寫入；
- Memory formation 可以沒有產出，合法 no-op 不是錯誤。

**不是共同點：**

- 是否每一回合都在 hot path 更新；
- 是否由主顧問自己決定 CRUD，或由另一個 extraction／consolidation manager 處理；
- 是否使用背景 worker、閒置觸發或固定排程。

因此「always hot path」「always background」都不能冒充大廠共識。

### 2.4 三個可行方案

#### A. 主顧問一律直接呼叫 Memory Tool

流程：員工訊息保存 → 主顧問判斷內容 → 呼叫 Memory Tool → Runtime／Store 寫入 → 主顧問繼續回答或編輯 JD。

- 優點：新理解立即可用；單一 agent loop；Anthropic Memory Tool 與 LangMem hot path 有現成 primitive。
- 缺點：多數實質訪談回合都增加 Tool round trip；主顧問同時負責訪談、Memory 整理與 JD 判斷，官方文件明示可能增加延遲並降低其他任務品質。

#### B. 一律由回合後 Manager 背景處理

流程：員工訊息保存 → 主顧問完成回覆 → Memory Manager 背景抽取／整併 → Store 發布。

- 優點：主回合延遲低、職責清楚；符合 Codex、Google、AWS 的公開背景 formation 路徑。
- 缺點：本輪新理解尚未發布；若同輪直接依它建立 JD 變更，會出現 Memory 與 JD 的因果不一致；還需要背景續跑與失敗恢復。

#### C. 同一套 Manager，依資料依賴同步或背景（建議）

流程：員工訊息先保存；一般訪談可完成回覆並讓同一套 Manager 背景整理；若接下來要依本輪新資訊產生 JD 變更或做全量完整性檢查，Runtime 先等待同一套 Manager 成功發布，再允許依賴動作。

- 優點：保留即時正確性，又不要求每個普通回合承受同步 Memory 成本；沿用一套 extraction／consolidation 規則，不建立兩個語意 writer。
- 缺點：比單一路徑多一個排程邊界；Runtime 必須知道哪些動作依賴最新 Memory，且背景失敗不能靜默。

### 2.5 建議的 Q014 responsibility mapping

本段是 **Caliburn mapping**，不是廠商共同內部架構：

| 產物／動作 | 責任位置 |
|---|---|
| 員工訊息與顧問回覆 | LangGraph thread／Checkpointer 的 canonical messages；顧問回覆是唯一 human-facing message。 |
| Memory extraction／consolidation 判斷 | 一套專用 Memory Manager；同步與背景只改排程，不改語意規則。 |
| Memory mutation 候選 | Manager 的窄 machine-readable artifact；不塞回主顧問 final response 的巨大 schema。 |
| scope、namespace、ID、version、timestamp、權限、retry | Runtime 從可信 context 注入／管理；模型不得填。 |
| 實際 Store CRUD | LangGraph Store／Runtime 執行並回傳明確 success、no-op 或 error。 |
| JD 變更 | 另一組 JD workspace Tools；若依賴尚未發布的新 Memory，Runtime 在該動作前建立 hard gate。 |
| 對員工說明 | 主顧問在 canonical assistant message 中自然說明；不得以 prose 假裝 Memory 或 JD 已寫入。 |

這項 mapping 與 [`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md) §6 的既有 dependency-aware Working Baseline 一致；本輪新資料沒有提供足以重開它的相反證據。Q014 只補上：**背景 Manager 的窄 mutation artifact 是 structured-output 例外；主顧問自身仍採 Tool-first＋plain final message。**

### 2.6 尚未決定

- Manager 是否直接採 LangMem `create_memory_store_manager`、其 core manager 或包成 LangChain Tool；
- 背景工作以何種 trigger／worker／LangGraph task 執行；
- 哪些 JD Tools 構成 hard gate；
- Tool／artifact 的精確 schema、一次處理幾筆、模型與 reasoning effort；
- retry、timeout、token／cost budget 與 observability 欄位；
- 是否先做同步-only 的最小施工切片，再以實測決定是否啟用背景排程。

上述項目不能由本段偷定，也不授權 spike 或 production 施工。

### 2.7 Owner gate

待確認：是否接受方案 C 與 §2.5 的責任分配，作為 `LLM-Q014` 的第一個 G4 section？接受後才繼續盤點下一個 machine effect；若不接受，再只重開本題，不連帶翻案其他 Memory 決策。
