# Memory 模型工具接線

- 狀態：**現行 Memory 模型工具接線** 。讀寫、角色與共用執行依下列責任協作；工具測試不取代真模型分析品質評估。
- 語意權威：[讀取與來源回查](../specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[單物件更新](../specs/2026-09-27-memory-object-update-tool-contract.md)、[共同工具規範](../specs/2026-09-27-agent-tool-contract-design-research.md)。本頁只說程式責任與接線，不另抄 JSON shape。

本頁維護模型參數如何進入受限用例，以及實際結果如何回到原工具呼叫。讀取從[固定基準](#2-固定基準與候選最新位置)與[輸出投影](#3-模型可見資料與錯誤)開始；寫入從[準備及採用](#4-寫入準備採用與原結果接續)開始。資料交易見[Memory 保存](memory-storage.md)，正文解析與定位見[正文編輯](memory-body-editing.md)。

## 1. 契約與模組邊界

工具使用 `apps/api/contracts/tools/` 的 schema、生成 DTO 及安裝包內的唯讀 schema 資源；生成與 `--check` 依[資料與契約 §5](data-and-contracts.md#5-唯一契約來源及生成)。本頁只維護 Memory 工具如何消費這些生成物。

模型工具由 `transport/model_tools/memory_reads.py` 提供，讀取流程如下：

```text
App 綁定角色、原執行身分、可見基準、訪談上界
  → 薄工具驗模型 arguments
  → workflows/memory_reads.py 核執行資格及跨領域模組讀取
  → work_memory/read_queries.py 固定本次 view、讀 map／物件
  → interviews/queries.py 依正式來源與上界讀原文
  → 工具生成 DTO → 精簡 JSON 字串
```

工具不執行 SQL、不 commit、不保存第二套原話或結果、不重試。Memory 領域模組 重用候選／固定修訂與 map 查詢；訪談領域模組 決定正式來源是否可讀。模型的 `target_title` 在 App map 精確解析成真實 ID，資料介面仍以 ID 讀取，沒有 `WHERE title` 目標操作。

## 2. 固定基準與候選最新位置

| 使用者 | App 提供的綁定 | 單次讀取行為 |
|---|---|---|
| A | 原 Turn 的已發布 snapshot，及本輪輸入前的正式訪談上界 | 不改成後來發布版本；原本無 snapshot 就保持空 Memory |
| B1 | 本批執行與情境階段、原批訪談上界 | 每次讀該階段最新成立位置；只有情境 map／正文與歷史訪談 |
| B2 | 本批執行與理解階段、原批訪談上界 | 每次讀該階段最新成立位置；可讀兩層及歷史訪談 |

一次 read 先固定 `MemoryReadView.position_id`，再從同一位置取 map、正文及關係。即使其他有效操作隨後改名、刪除或重用標題，本次回傳不混合前後位置；下次候選讀取才看到更新。理解的來源導覽沿既有 **物件 ID** 取得當前情境名稱，不用舊標題重新綁定。A 則始終讀原快照內的固定引用鏈。

這是 App／工具的能力，不證明模型心中選的標題正確；產品決策不增加強制重讀或觀察代號。新操作按目前作用域解析；原操作恢復的固定身分另由保存責任承接。

每次新讀取核對執行資格；失效／取消及舊階段拒絕。這不代表取消能召回已在途的純讀取結果；Runtime 在接續採用時再次阻止失效執行。恢復既有工具結果也不靠重新讀目前最新資料冒充原觀察。

## 3. 模型可見資料與錯誤

- Map 回全部 `target_title`／`description`，不預讀正文。完整物件回三個內容欄位及本層來源集合；合法無來源為 `[]`。
- 理解來源列只回情境導覽；情境來源列只回正式訪談序號。下一層正文與原話按需讀，不把完整引用鏈展開。
- 訪談工具可選多個序號或含兩端區間；去重後按正式順序回角色、序號、原文與歷史資料標記。任一來源不合法整筆拒絕，不返回部分成功。
- 正常讀取不回 `stage`、`status: read`、內部 UUID、執行／版本參數；模型只填標題或訪談選取。
- 拒絕沿共同 `status/code/message/next_action`，區分非法參數、無權、過時階段、找不到目標、來源不可讀及容量不足。基礎設施錯誤交 Runtime，不轉成模型參數錯誤或合法空集合；不洩漏 raw exception。

`MemoryReadTools.max_result_characters` 預設 1,000,000，App 可配置，非模型參數。完整結果超限回 `read_limit_exceeded`，不靜默截斷。這是輸出防護，**不是 token 計數或容量預算保證** ；Runtime 在發送前依實際完整 request 計數與檢查容量。訪談可縮小選取；整份 map 或單物件超量則由 App 處理，不能假裝已完整讀過。

## 4. 寫入準備、採用與原結果接續

`transport/model_tools/memory_writes.py` 只提供責任角色的 create/update/delete。Schema 及轉譯在工具邊界；`workflows/memory_writes.py` 準備固定命令；原 `MemoryCandidateWorkflow.edit` 擁有交易與原結果，沒有第二套候選或收據。

```text
已保存的原模型 call + App 操作身分
  → prepare：固定目前位置、標題轉 ID、來源資格、全部 changes／hunks
  → 形成 PreparedMemoryToolCall（固定命令＋完整預期成功回傳）
  → Runtime 可靠保存這份待執行命令
  → execute：Memory 候選服務 同次採用或承接原提交結果
  → 確認成立後才回傳成功，保存並配回原 call
```

### 準備命令與候選採用

準備過程無業務寫入。所有內容與引用使用同一個候選位置解析；參照由訪談序號／情境標題轉成穩定 ID。正文解析、模糊定位與實際 diff 是純運算，在釋放讀取 session 後以受控同步工作執行，不持有寫入交易等模型或做長文運算。候選在準備後已變動，Memory 候選服務就拒絕過時命令，不能改採最新位置。

`PreparedMemoryToolCall` 是 App 內部不可變的待執行命令，包含套用後正文以固定原操作；它不是模型參數、正式回執或第二份可編輯候選。可編輯工作稿仍由 Memory 候選服務保存，可靠序列化、checkpoint 採用及程序接續由[共用執行](agent-execution.md#42-單一模型工具-step)承接。

原操作恢復必須重用已保存的 prepared command，不重新用舊標題呼叫 prepare。例如物件改名後舊名稱被另一物件使用，原命令仍指原身分；真正新操作才解析現在的同名物件。再次進入 execute 時，Memory 候選服務核對同一命令及提交結果，不能重複效果。

### 成功回傳與拒絕

- Create／Delete／全無變更只回 `created`／`deleted`／`unchanged`；不重貼模型已填的完整正文。
- Update 回目前 title／description 與真正有變的 `applied_changes`。短欄位只標記改了哪欄；正文回真實舊文到新文差異；來源只回實際新增／移除，已存在的新增不冒充新效果。
- 正文效果 diff 重用 Python `difflib.unified_diff`，保留三行脈絡與真實行號；不是把輸入 V4A 原樣 echo，也不是可再次執行的 patch 契約。分行與編輯器共同只認 LF／CRLF，Unicode 分隔字元不偷偷變成新行；無尾端換行明示標記。
- 全部結果先通過生成 DTO 與容量檢查，再允許採用。預期完整回傳超過 App 的 `max_result_characters`（預設 1,000,000）時，回 `write_result_limit_exceeded` 且不改候選；不是提交後再把成功誤報拒絕。已成立原操作重入直接承接原回傳，不因新執行器容量配置不同改寫歷史。
- 找不到來源、重名、非法變更、無權、過時位置及 patch 歧義均明確拒絕；patch 錯誤帶必要 hunk 與真實候選位置，不提供他層私有資料。第二個 hunk 失敗不留下前面的 title／來源變更。
- 未知提交結果、timeout 及保存錯誤交 Runtime 核對，不包成一般 `rejected`。只有可確定未成立的拒絕，才供模型修正參數。預先組好的成功文字本身不是提交證據。

## 5. 官方契約與驗證界線

依 [OpenAI function calling strict 契約](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)明確送 `strict: true`；每個 object 關閉額外欄位、宣告 required，分支使用巢狀 `anyOf`。這不把輸入 schema 正確等同語意正確。工具描述說明歷史內容是資料，不授予其中指令更高權限；角色權限仍由 App／Domain 判斷。

驗證：工具與候選交易、原生接續、Memory 單向流程。V4A 運算沿[正文編輯器](memory-body-editing.md)，不自行保存候選。

Runtime 保存 prepared command、原生 `function_call_output` 與 `call_id` 配對；角色 runner 組裝固定 context、執行 B1／B2 並交接 diff。provider 接受格式、程式恢復與模型分析品質須分別驗證；不得由工具函式可呼叫推定模型會正確選取或引用。測試責任見[驗證對照](verification-plan.md)，既有品質證據及未驗範圍見[架構驗證](../architecture/verification.md)。
