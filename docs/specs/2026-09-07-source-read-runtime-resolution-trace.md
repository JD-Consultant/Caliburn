# CT13-A3：來源回查的官方底層與框架接線核對

2026-09-07 · LLM-Q019 · **Owner 已同意 CT13 局部方案；本子題先完成底層查證，尚未變更工具。**

## 1. 唯一問題與效力

Owner 補充：不能只引用「已知參數讓程式處理」就發明底層；必須查清大廠實際如何保存、定位與讀回來源，才修改做法。本篇只處理這個前置條件，不重開 ABC／框架、JD、UI、provider 或其他 CT13 品質問題。

入口：[current decisions](../../../../docs/current-decisions.md) → [CT13 修法研究 A3](2026-09-07-ct12-quality-and-retrieval-remedy-research.md#a3-讓程式代取已知原文地址保留現有工具儲存隔離) → 本篇。既有 [OpenAI progressive disclosure](../../../../docs/specs/2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md) 與 [摘要路由 producer／consumer](../../../../docs/specs/2026-09-05-memory-summary-routing-and-deep-read-source-review.md)已完整重讀；本輪只補查現行來源與我們實際接線，沒有重新廣泛研究全部 Memory。

## 2. OpenAI 實際做法：路徑由程式寫入，模型沿路徑查

2026-09-07 查得 `openai/codex` 當時 main 為 **`db0568dbbb853ce2c377a27a94b5546d4a4d2ec3`**；下列鏈接固定在該版本。完整讀取 `storage.rs`、`read_path.md`，並追 `phase1.rs` 的 `job::run → sample` 原文載入段。前兩個檔案的 blob 與 09-05 研究相同，沒有因另查一天就宣稱新算法。這是公開實作快照，不是永遠不變的 API 契約。

| 接力 | 原始碼中的實際動作 | 證據 |
|---|---|---|
| 原文 → 抽取 | `job::run` 取已 claim thread 的 `rollout_path`；`sample` 用 `RolloutRecorder::load_rollout_items` 載入，經 serializer 選取 response items 後才構造模型輸入。不是模型猜檔名，也不代表把所有執行事件原樣塞進 prompt | [phase1.rs，job／sample](https://github.com/openai/codex/blob/db0568dbbb853ce2c377a27a94b5546d4a4d2ec3/codex-rs/memories/write/src/phase1.rs#L224-L315) |
| 候選 → 整併輸入 | `rebuild_raw_memories_file` 從保存的 `Stage1Output` 寫 thread、時間、cwd、原文路徑、詳記檔名，再接上模型產生的候選內容 | [storage.rs，L44–77](https://github.com/openai/codex/blob/db0568dbbb853ce2c377a27a94b5546d4a4d2ec3/codex-rs/memories/write/src/storage.rs#L44-L77) |
| 詳記 → 原文地址 | `write_rollout_summary_for_thread` 在摘要正文前加入 runtime 持有的 `thread_id`、`updated_at`、`rollout_path`、cwd 等 metadata，最後寫入 Markdown。slug 是模型提供的可讀線索，完整檔名由程式組成 | [storage.rs，header／filename](https://github.com/openai/codex/blob/db0568dbbb853ce2c377a27a94b5546d4a4d2ec3/codex-rs/memories/write/src/storage.rs#L110-L237) |
| Memory → 詳記 → 原文 | read prompt 要模型搜尋 Memory、選讀少量相關詳記，仍需精確證據時才沿 `rollout_path` 搜原始 JSONL；優先用路徑／檔名線索或 session identity，避免無差別全文掃描 | [read_path.md，布局與 quick pass](https://github.com/openai/codex/blob/db0568dbbb853ce2c377a27a94b5546d4a4d2ec3/codex-rs/ext/memories/templates/memories/read_path.md#L19-L53) |

**必須修正措辭：**這條 Codex 公開 read path 不是「模型完全不傳地址」，也沒有在上述 producer／consumer 證據中出現一個自動把 summary path 換成原文的專用函式。模型仍會選擇、引用和傳遞它看到的路徑。OpenAI [Function calling：已知參數交給程式](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)支持減少不必要的參數搬運，但不能用這條建議反推 Codex 的實作必然是 CT13 所提工具。

不沿用 read prompt 排版上的歧義：`.md` 詳記和 `rollout_path` 指向的 JSONL 是兩種資料；由寫入程式確認，不把詳記誤稱 append-only JSONL。亦不從此證明 Claude、ChatGPT 或所有產品採相同內部 schema。

## 3. Anthropic 與框架實際承諾的範圍

- **Anthropic 官方契約：**Memory tool 由客戶端執行。模型要求讀 `/memories/...`；應用 handler 將該 prefix 對應到自身目錄或資料庫 key，再回 `tool_result`。應用需驗證路徑邊界。因此「模型看邏輯地址，程式處理實體位置」有直接依據；**沒有據此證明它內建摘要→原始對話關聯查詢**。[How it works／Implement handler](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#how-it-works)、[路徑限制](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#path-traversal-protection)
- **LangChain 官方契約：**工具可以使用不暴露給模型的 `ToolRuntime`，由 `ToolNode` 注入 state／config／store。官方範例從 `runtime.context.user_id` 查已知資料，而非讓模型填 user ID。但應用仍須提供查哪份資料的函式。[Tools：Access context](https://docs.langchain.com/oss/python/langchain/tools#access-context)
- **DeepAgents 官方契約：**`CompositeBackend` 按 prefix 路由、保留可見地址；`StoreBackend` 以 namespace＋key 存取。官方允許用 `BackendProtocol` 連其他儲存；這是可選擴充點，不代表本案必須再建一個 backend。[Backends：routing／custom backend](https://docs.langchain.com/oss/python/deepagents/backends#custom-backends)
- **LangGraph 官方契約：**`graph.get_state` 帶 `thread_id`＋指定 `checkpoint_id` 可取當時 snapshot；底下 `.get_tuple` 有指定 ID 的精確路徑，不應以最新版本替代缺失版本。[Get state](https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state)、[get_tuple 契約](https://docs.langchain.com/oss/python/langgraph/checkpointers#get_tuple--aget_tuple)

以上是各自公開的責任，**不能合併命名為「各家都有同一個摘要回查工具」**。沒有找到原生承接本案 header、來源視窗與可見問答投影的現成單一工具；接線部分要明示為應用實作。

## 4. 本案底層實際怎麼走

已核對 lock 與安裝原碼：LangChain 1.4.0／langchain-core 1.6.2、LangGraph 1.2.11／prebuilt 1.1.0、Postgres checkpointer 3.1.2、DeepAgents 0.7.13。此為本次核對版本，不宣稱永久最新。沒有為這次查證升級依賴。

```text
詳記保存時（已有）
已保存、可抽取的訪談 snapshot
  → ConversationReader.extraction_windows 劃定實際訊息範圍
  → 產生 source reference 及可選 context reference
  → 模型抽取完成後交 MemoryArtifacts.save_extraction
  → 用 StoreBackend 保存詳記
  → 程式寫入 Source 及 Context-only header

C 即時修補（另一條已有來源路徑）
ConversationReader.capture_input
  → 為本輪已存員工輸入及前置問答產生直接來源 reference
  → 不要求先產生詳記

回查接線（前段待做；後段已存在）
模型選已找到的詳記地址
  → 程式在目前文件 namespace 讀該詳記的固定 metadata
  → 取該份資料已保存的原文 reference，而非語意猜測
  → ConversationReader.read
  → graph.get_state(thread_id, checkpoint_id)
  → 官方 PostgresSaver.get_tuple 精確查指定 snapshot
  → 從 messages 取保存的 first…last 範圍
  → 回傳有界的員工／AI 可見問答，保留 role 與續頁位置
```

具體可回看位置：

| 責任 | 目前程式／實際核對 |
|---|---|
| 保存真正定位、分頁與問答投影 | [sources.py](../../experiments/analysis-agent/src/analysis_agent/sources.py)：`_reference`／`_snapshot`／`_range`／`read` |
| 保存地址關聯、讀原始 artifact bytes | [memory.py](../../experiments/analysis-agent/src/analysis_agent/memory.py)：`save_extraction`／`read_text`／`extraction_window`。`read_text` 用公開 `download_files`，不解析模型看到的行號裝飾 |
| 既有模型入口與錯誤回饋 | [memory_tools.py](../../experiments/analysis-agent/src/analysis_agent/memory_tools.py)：`read_conversation`，使用 `ToolRuntime` 及 `ToolException`，不是另造一套工具錯誤通道 |
| 框架 Store lookup | 已安裝 `deepagents/backends/store.py` 的 `read`／`download_files` 都以 `store.get(namespace, file_path)` 取 item，後者回未加顯示行號的 bytes |
| 框架 snapshot lookup | 已安裝 `langgraph/pregel/main.py:get_state` 呼叫 saver；`langgraph/checkpoint/postgres/__init__.py:get_tuple` 在有 checkpoint ID 時使用 thread＋namespace＋checkpoint 的等值查詢。沒有 ID 才走 latest，兩者不可混用 |
| 框架隱藏參數 | 已安裝 `langgraph/prebuilt/tool_node.py:_inject_tool_args` 注入 runtime，還會剔除 caller 偽填的 injected arguments；本案只使用公開 `@tool`／`ToolRuntime`，不呼叫該私有函式 |

因此這不是向量搜尋、模型再查一次意思、解析 assistant 上一次回答、或讓程式猜「最後讀過哪份」；是沿**保存時已建立的明確關聯**取資料。文件隔離由 runtime 決定，模型的 path 只在該 namespace 解析，不是任意本機檔案路徑。

## 5. CT13 A3 需要補精確的兩個邊界

### 5.1 不要拿重抽入口充當純回查

`extraction_window(summary_path)` 目前在解析 header 之後，還要求配對的 `candidates.md` 存在。這是重抽流程的既有前置檢查，不是「讀原始對話一定需要候選檔」的框架契約。

**設計修正建議：**共用同一段固定 metadata 解析，但把「重抽需要配對候選」檢查留在重抽入口。回查只需已保存的詳記定位與實際可讀原文。不得為了回查而刪除重抽檢查、放寬任意 Markdown、從正文搜尋看似 `Source:` 的字串，或補造遺失的關聯。這是局部責任拆分，不換原文儲存。

### 5.2 本段原文與前置問答脈絡都要仍可找到

現有詳記有 `source_reference` 與可選 `context_reference`：後者可能保存員工本段回答所對應的先前 AI 問題。若新工具只代取 source，會少了一條原本可用的深查入口。這不是已證實 CT12 request 59 的根因，而是新介面必須防止的退化。

後續工具契約需讓模型用**同一已知詳記地址**選擇本段／已保存的前置脈絡，不再要求抄兩個長碼；回傳清楚標示二者，沿各自保存的 reference 分頁，不能把前置脈絡冒充本批新資訊。`context_reference=None` 要如實回沒有另外保存的前置範圍，不猜一個「附近的」對話。是否要多讀由需要決定，不強制每次把兩段全放進 context。

尚未有詳記的 C 即時修補仍可用既有直接來源 reference，這條路徑不能切斷。減少 B 詳記回查的長碼搬運，不代表這輪解決所有 C 引用編輯或所有識別碼問題。

## 6. 取捨、驗證與停止條件

| 選項 | 判斷 |
|---|---|
| 維持模型抄完整 source reference | 現況能用、會回錯及修正；CT12 已發生抄錯。不是禁止 ID，但沒移除已見負擔 |
| **沿既有詳記地址，由同一工具代取來源 metadata** | 建議；符合官方明確定位／已知參數內部處理及框架公開接線。需§5的小型接線，**不是 Codex 原碼逐行複製**；不增加 LLM 呼叫、資料表或原文副本 |
| 新建全面虛擬原文 filesystem／短碼映射服務 | 框架有擴充點，但本題無需為單一已存在關聯擴大 read／grep／ls／索引契約，不採用 |

2026-09-07 用既有測試離線重跑：`tests/test_memory_read_path.py`＋`tests/test_summary_reextraction.py`，**34 passed，8.56s，exit 0**。真框架＋mock provider；確認現有指定舊版本、中文／emoji 分頁、文件隔離、原文／推理分離及重抽來源保留等行為。**沒有新增工具實作，故不是新摘要地址入口已通過，更不是訪談品質已修好。**未呼叫真模型、未存取 API key，US$0。

施工計畫需補的新驗證：摘要地址和原 direct reference 讀到相同範圍；只有前置問題才能解讀的回答；缺候選但原文有效的純讀／重抽差異；缺檔／無固定 header／跨文件／錯誤 checkpoint 不猜測；C 無詳記仍可讀；工具 runtime 不出現在模型 schema。現有 snapshot reader 可能先載入整個 checkpoint 再限量回傳，不能把回傳分頁宣稱為 DB 分頁或已降低整體延遲。

**Closure：**A 的方向已獲 Owner 同意；A3 底層證據已足以進入局部計畫，§5修正明列、不偷稱官方內建。本輪僅文檔與既有離線驗證；未改產品、prompt、Skill、參數、Memory 或上限，未 merge／push。CT13 A1／A2／A4 不因本題而取消或視為已完成。下一步依已核准 CT13 分段修復；若框架接線無法保留上述來源與錯誤邊界，才回來討論，不重開整套 Memory 研究。
