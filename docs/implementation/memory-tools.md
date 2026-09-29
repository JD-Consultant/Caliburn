# Memory 模型工具接線

- 日期：2026-09-30；狀態：**T05 施工中；讀取工具已通過契約及真 PostgreSQL 驗證，寫入工具與模型執行尚未交付**。實測與限制見 [T05 evidence](../plans/2026-09-29-target-rebuild/evidence/t05-memory-tools.md)。
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

## 4. 官方契約、驗證與未完事項

依 [OpenAI function calling strict 契約](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)明確送 `strict: true`；每個 object 關閉額外欄位、宣告 required，分支使用巢狀 `anyOf`。這不把輸入 schema 正確等同語意正確。工具描述說明歷史內容是資料，不授予其中指令更高權限；角色權限仍由 App／Domain 判斷。

已驗：生成一致、三角色工具清單、SDK 離線 serialization、真 PG 的改名／同名重用、固定快照、單次一致讀取、訪談範圍與失效拒絕，以及 wheel 內 schema 可讀。沒有真 provider strict 接受或模型品質證據。

尚待 T05：create/update/delete 的模型 schema、原操作綁定與候選全成或全拒，以及 Update 的真實差異回傳。V4A 運算沿 [正文編輯器](memory-body-editing.md)，不自行保存候選。

尚待 T06／T10：native `function_call_output` 與 `call_id` 配對、保存／Step 恢復、context 組裝、B1／B2 真執行。不得因這些讀取函式可呼叫就宣稱 Agent 產品流程已接通。
