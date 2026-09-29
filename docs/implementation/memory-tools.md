# Memory 模型工具接線

- 日期：2026-09-30；狀態：**T05 讀寫工具元件已通過契約及真 PostgreSQL 驗證；模型執行與 checkpoint 接線仍待 T06／T10**。實測與限制見 [T05 evidence](../plans/2026-09-29-target-rebuild/evidence/t05-memory-tools.md)。
- 語意權威：[讀取與來源回查](../specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[單物件更新](../specs/2026-09-27-memory-object-update-tool-contract.md)、[共同工具規範](../specs/2026-09-27-agent-tool-contract-design-research.md)。本頁只說程式責任與接線，不另抄 JSON shape。

## 1. 契約與模組邊界

`apps/api/contracts/tools/` 是模型輸入／輸出的唯一 schema 來源。既有生成器產 Python DTO、TypeScript 型別，並把原 schema 複製為 Python package resources，供安裝後的工具 definitions 使用；不是再從 Pydantic schema 反推 provider 契約。`--check` 同時檢查型別與資源副本，禁止手改生成檔。

模型工具由 `transport/model_tools/memory_reads.py` 提供，讀取流程如下：

```text
App 綁定角色、原執行身分、可見基準、訪談上界
  → 薄工具驗模型 arguments
  → workflows/memory_reads.py 核執行資格及跨 owner 讀取
  → work_memory/read_queries.py 固定本次 view、讀 map／物件
  → interviews/queries.py 依正式來源與上界讀原文
  → 工具生成 DTO → 精簡 JSON 字串
```

工具不執行 SQL、不 commit、不保存第二套原話或結果、不重試。Memory owner 重用 T04 的候選／固定修訂與 map 查詢；訪談 owner 決定正式來源是否可讀。模型的 `target_title` 在 App map 精確解析成真實 ID，資料介面仍以 ID 讀取，沒有 `WHERE title` 目標操作。

## 2. 固定基準與候選最新位置

| 使用者 | App 提供的綁定 | 單次讀取行為 |
|---|---|---|
| A | 原 Turn 的已發布 snapshot，及本輪輸入前的正式訪談上界 | 不改成後來發布版本；原本無 snapshot 就保持空 Memory |
| B1 | 本批執行與情境階段、原批訪談上界 | 每次讀該階段最新成立位置；只有情境 map／正文與歷史訪談 |
| B2 | 本批執行與理解階段、原批訪談上界 | 每次讀該階段最新成立位置；可讀兩層及歷史訪談 |

一次 read 先固定 `MemoryReadView.position_id`，再從同一位置取 map、正文及關係。即使其他有效操作隨後改名、刪除或重用標題，本次回傳不混合前後位置；下次候選讀取才看到更新。理解的來源導覽沿既有 **物件 ID** 取得當前情境名稱，不用舊標題重新綁定。A 則始終讀原快照內的固定引用鏈。

這是 App／工具的能力，不證明模型心中選的標題正確；Owner 已決定不增加強制重讀或觀察代號。新操作按目前作用域解析；原操作恢復的固定身分另由保存責任承接。

每次新讀取核對執行資格；失效／取消及舊階段拒絕。這不代表取消能召回已在途的純讀取結果；T06 仍須在接續採用時阻止失效執行。恢復既有工具結果也不靠重新讀目前最新資料冒充原觀察。

## 3. 模型可見資料與錯誤

- Map 回全部 `target_title`／`description`，不預讀正文。完整物件回三個內容欄位及本層來源集合；合法無來源為 `[]`。
- 理解來源列只回情境導覽；情境來源列只回正式訪談序號。下一層正文與原話按需讀，不把完整引用鏈展開。
- 訪談工具可選多個序號或含兩端區間；去重後按正式順序回角色、序號、原文與歷史資料標記。任一來源不合法整筆拒絕，不返回部分成功。
- 正常讀取不回 `stage`、`status: read`、內部 UUID、執行／版本參數；模型只填標題或訪談選取。
- 拒絕沿共同 `status/code/message/next_action`，區分非法參數、無權、過時階段、找不到目標、來源不可讀及容量不足。基礎設施錯誤交 Runtime，不轉成模型參數錯誤或合法空集合；不洩漏 raw exception。

`MemoryReadTools.max_result_characters` 初值 1,000,000，App 可配置，非模型參數。完整結果超限回 `read_limit_exceeded`，不靜默截斷。這是輸出防護，**不是 token 計數或容量預算保證**；T06 必須在發送前依實際 context 判斷。訪談可縮小選取；整份 map 或單物件超量則由 App 處理，不能假裝已完整讀過。

## 4. 寫入準備、採用與原結果接續

`transport/model_tools/memory_writes.py` 只提供責任角色的 create/update/delete。Schema 及轉譯在工具邊界；`workflows/memory_writes.py` 準備固定命令；原 `MemoryCandidateWorkflow.edit` 擁有交易與原結果，沒有第二套候選或收據。

```text
已保存的原模型 call + App 操作身分
  → prepare：固定目前位置、標題轉 ID、來源資格、全部 changes／hunks
  → 形成 PreparedMemoryToolCall（固定命令＋完整預期成功回傳）
  → Runtime 可靠保存這份待執行命令【T06 待接】
  → execute：原候選 owner 同次採用或承接原提交結果
  → 確認成立後才回傳成功，配回原 call【配對保存仍待 T06】
```

準備過程無業務寫入。所有內容與引用使用同一個候選位置解析；參照由訪談序號／情境標題轉成穩定 ID。正文解析、模糊定位與實際 diff 是純運算，在釋放讀取 session 後以受控同步工作執行，不持有寫入交易等模型或做長文運算。候選在準備後已變動則原 owner 拒絕過時命令，不能偷偷改採最新位置。

`PreparedMemoryToolCall` 是 **App 內部不可變待執行命令**，不是模型參數、正式回執或另一份可編輯候選。包含套用後正文是為了固定原操作；可編輯工作稿仍由原候選 owner 保存。其可靠序列化與 checkpoint 採用由 T06 承接；目前只驗準備／執行介面，不能當成已有程序重啟恢復。

原操作恢復必須重用已保存的 prepared command，不重新用舊標題呼叫 prepare。例如物件改名後舊名稱被另一物件使用，原命令仍指原身分；真正新操作才解析現在的同名物件。再次進入 execute 可以，但原 owner 核對同一命令及提交結果，不能重複效果。

### 成功回傳與拒絕

- Create／Delete／全無變更只回 `created`／`deleted`／`unchanged`；不重貼模型已填的完整正文。
- Update 回目前 title／description 與真正有變的 `applied_changes`。短欄位只標記改了哪欄；正文回真實舊文到新文差異；來源只回實際新增／移除，已存在的新增不冒充新效果。
- 正文效果 diff 重用 Python `difflib.unified_diff`，保留三行脈絡與真實行號；不是把輸入 V4A 原樣 echo，也不是可再次執行的 patch 契約。分行與編輯器共同只認 LF／CRLF，Unicode 分隔字元不偷偷變成新行；無尾端換行明示標記。
- 全部結果先通過生成 DTO 與容量檢查，再允許採用。預期完整回傳超過 App 的 `max_result_characters`（初值 1,000,000）時，回 `write_result_limit_exceeded` 且不改候選；不是提交後再把成功誤報拒絕。已成立原操作重入直接承接原回傳，不因新執行器容量配置不同改寫歷史。
- 找不到來源、重名、非法變更、無權、過時位置及 patch 歧義均明確拒絕；patch 錯誤帶必要 hunk 與真實候選位置，不提供他層私有資料。第二個 hunk 失敗不留下前面的 title／來源變更。
- 未知提交結果、timeout 及保存錯誤交 Runtime 核對，不包成一般 `rejected`。只有可確定未成立的拒絕，才供模型修正參數。預先組好的成功文字本身不是提交證據。

## 5. 官方契約、驗證與未完事項

依 [OpenAI function calling strict 契約](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)明確送 `strict: true`；每個 object 關閉額外欄位、宣告 required，分支使用巢狀 `anyOf`。這不把輸入 schema 正確等同語意正確。工具描述說明歷史內容是資料，不授予其中指令更高權限；角色權限仍由 App／Domain 判斷。

已驗：讀寫契約生成、角色清單、讀取的 SDK 離線 serialization、真 PG 固定基準／來源及候選操作；多欄共同採用／拒絕、原命令同名重用恢復、提交已成但確認遺失、過時位置、完整回傳容量與長文受控模糊編輯。V4A 運算沿 [正文編輯器](memory-body-editing.md)，不自行保存候選。精確命令與層級見 evidence；沒有真 provider strict 接受或模型品質證據。

尚待 T06／T10：prepared command 的持久序列化、native `function_call_output` 與 `call_id` 配對、保存／Step 恢復、context 組裝、B1／B2 真執行與交接 diff。不得因工具函式可呼叫就宣稱 Agent 產品流程已接通；T16／T17 仍負責 provider 與模型效果驗收。
