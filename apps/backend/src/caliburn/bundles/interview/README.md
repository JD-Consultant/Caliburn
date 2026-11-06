# 訪談 Bundle

提供正式原話保存、既有訪談 Context、來源說明與 `read_interview`。資料與題答規則由[訪談模組](../../modules/interview/README.md)管理；模型使用持久 `message_N`，由[共同定位模組](../../modules/model_references/README.md)映射到正式 UUID。

## 啟用

```json
{
  "module": "caliburn.bundles.interview",
  "plugins": ["interview", "interview_context", "interview_source_prompt", "interview_read", "interview_navigation"],
  "config": {"max_output_characters": 24000}
}
```

`plugins` 是唯一啟停入口；省略選取全部，空清單全部停用，順序沿 factory 宣告，未知名稱啟動拒絕。

| Plugin | 責任 | 必要服務 |
|---|---|---|
| `interview` | 保存輪首輸入與輪末 final，取消時撤回 | `INTERVIEW_UOW_FACTORY`、`MODEL_REFERENCES` |
| `interview_context` | 獨立預載既有原話 | `INTERVIEW_QUERIES`、`MODEL_REFERENCES` |
| `interview_source_prompt` | 原話、發話者與題答語意，不含完整顧問策略 | 無 |
| `interview_read` | `read_interview` 工具 | `INTERVIEW_QUERIES`、`MODEL_REFERENCES` |
| `interview_navigation` | 輪首提供可讀來源首末 ref | `INTERVIEW_QUERIES`、`MODEL_REFERENCES` |

服務鍵由 [services.py](services.py)定義，Host 綁入共用持久定位服務。`max_output_characters` 控制讀取結果容量；config 不接受能力啟停旗標。

改變執行組合或已保存格式時，更新 Agent 的 `resume_version`，避免未完成輪次沿不同契約接續。停用模型工具仍可透過模組查讀原話，不移除資料或取消收尾能力。

## 一輪的資料

同時啟用上述插件時：Core 初始化本輪輸入 → `interview` 保存員工原文並提供 ref → `interview_context`／`interview_navigation` 準備既有材料及導覽 → 模型與工具循環 → `interview` 保存最終顧問發話。未選的能力不執行；來源 Prompt 只提供解讀指令，不讀資料庫，也不授予讀取資格。

預載排除本輪：原輸入與中途題答已在原生往返，不再從資料庫重貼。員工輸入保存後只追加 `employee_input_reference` 標識及 ref；[提問 Bundle](../human_questions/README.md)在答案保存後交付問題及答案 ref。同輪 `read_interview` 可讀這些已保存訊息，不受輪首資料清單限制。

來源以 user-role 資料注入，保留原文、發話者、正式順序與明確題答關係。預載標記為 `source=interview`，成功工具結果標記為 `data_kind=interview`；兩者及本輪原話使用同一持久訊息定位。`ref` 定位訊息，`reply_to` 指原題；短碼數字不代表順序或版本，正文中的短碼文字不會自動改寫。一般聊天不推定回答前一則，略過不表示同意，未選入答案也不表示尚未回答。

本輪輸入已保存後即可供本輪顧問查讀或支持自己的 JD 候選，不必為取得來源資格而重讀已充分可見的原文。是否直接支持 JD 文字仍須由顧問判斷，引用格式沿 JD 工具契約；其他分析工作的完成資格不由此 Prompt 決定。資料內容不是新增指令，顧問推測也不是員工已確認事實。完整來源說明由 [source_prompt.py](source_prompt.py) 維護。

未指定範圍時，獨立 Context 預載全部有效既有訪談，不任意裁切。Workspace 建立用例在同一筆交易保存 App 開場，Host 接上 Interview 的 `stage_opening`。中途說明與 reasoning 留在執行紀錄，只有本輪 final 顧問發話保存為正式訪談。

## 唯一讀取工具

[read_tool.py](read_tool.py) 的 `create_read_interview_tool` 擁有唯一 schema／描述與選取入口，接受選配的 async reader 及完整結果字元容量。模型參數只有 `query`：明列 `refs`，或 `start_ref`／`end_ref` 區間；不接受 Workspace、UUID、版本或分析權限。

| `query.kind` | 模型填寫的其餘欄位 |
|---|---|
| `messages` | 非空 `refs` 陣列，使用材料提供的 `message_N` |
| `range` | `start_ref`、`end_ref`，兩端都須在可讀集合內 |

成功回 `data_kind=interview` 與 `messages`；每則含 `ref`、`speaker`、`kind`、完整 `text`、可空 `reply_to`。它不回 Workspace／Turn／UUID 或分析版本，也不以導覽代替正文。投影與容量判斷見 [read_output.py](read_output.py)。

明列訊息去重後按 owner 正式順序回傳。區間包含兩端，依 Interview 的正式順序選取有效可讀集合；取消項不回傳，不能以 alias 數字比較或列舉。任何明列來源或端點失效都整次拒絕。只讀答案不自動補原題正文，`reply_to` 仍提供原題 ref。

完整 JSON 結果超過 `max_output_characters` 時拒絕，提供可執行的兩段查讀參數；明列選取不擴成區間，單則超量由應用調整容量。此限制計算字元數，不是 token 預算。

拒絕固定回 `status=rejected`、`code`、`message`、`next_action`，不附部分正文：

| `code` | 模型或應用的下一步 |
|---|---|
| `invalid_arguments` | 依欄位路徑修正形狀、ref 格式或反向區間。 |
| `source_not_available` | 預設 reader 的來源不存在／撤回，或 mapping 未知／跨 Workspace；改用有效材料提供的 ref，不洩漏其他 Workspace 狀態。 |
| `scope_not_allowed` | 自訂 reader 的固定範圍／資格失效，或已知 ref 不在其集合；不能改讀剩餘來源或自行擴權。 |
| `read_limit_exceeded` | 沿提供的縮小查讀參數拆讀；單則超量交應用調整，不截斷原話。 |

DB 或資料損壞仍沿 Runtime 失敗，不冒充空集合或模型參數錯誤。

獨立使用時另選 `interview_navigation` 提供[導覽](discovery.py)：即使不預載正文，模型仍取得有效首末 ref；空集合兩端為 null。窗口配置改由下述 adapter 提供導覽。此範圍是可讀資料提示，不是模型能修改的權限。

## Context 與 Memory 接點

[context.py](context.py)提供普通函式，無須啟用自動預載：

| 函式 | 用途 |
|---|---|
| `load_interview_context` | 查可信 Workspace 的有效原話，再選明示來源 |
| `select_interview_context` | 沿正式順序選取，必要時補原題並標 supporting_question |
| `project_interview_context(messages, refs=...)` | 純投影為模型來源，不暴露 Workspace／Turn／UUID |
| `insert_interview_context` | 在明示位置插入，保留其他原生 items 與順序 |
| `message_refs` | 批次呼叫唯一持久 mapping，只轉明定訊息 UUID 欄位 |

`message_ids=None` 全選既有來源，空 tuple 不預載；明示 ID 不存在、撤回、跨 Workspace 或包含保留原生往返的本輪時拒絕。補題只供語境，不擴張主要選取。查詢失敗不當成空訪談。

使用通用 Context 窗口時，另載入 `caliburn.bundles.interview.window` 並選 `interview_window`。此 adapter 透過公開 `WINDOW_CONTRIBUTIONS` 提供 [window.py](window.py) 的兩個 callback：`prepare_interview_window` 在重建時預載已完成輪次與 App 原話，`prepare_interview_input` 補本輪來源 ref 及導覽。通用窗口從 `turn_input` 重建本輪 input，所以 metadata 接在 `WindowContribution.prepare_input`，適用首次、換窗與同窗續接。callback 保留原生 items，只追加 metadata，不再保存或重貼原文。

以下組合都另選 Context 的 `window`，並排除原 Bundle 的 `interview_context`／`interview_navigation`，避免重複投影：

| 窗口用途 | 原 Bundle 選取 | adapter config |
|---|---|---|
| 完整訪談 | `interview`、`interview_source_prompt`、`interview_read` | `{}`，三種投影預設開啟 |
| 不預載歷史 | 同上 | `{"preload": false}` |
| 只保存本輪 | `interview` | `{"preload": false, "include_navigation": false}` |
| 只讀既有來源 | `interview_source_prompt`、`interview_read` | `{"preload": false, "include_input_reference": false}` |

adapter 三個參數控制同一窗口貢獻的投影內容；Plugin 啟停仍只用 `plugins`。輸入 ref 要求已選 `interview`，本輪員工原話若未保存或失效即明確失敗。提供任一投影需要 `INTERVIEW_QUERIES`／`MODEL_REFERENCES`，預載另需 `COMPLETED_TURNS`。兩種輸入 metadata 都關閉時不提供 `prepare_input`；通用 Context 只允許一個 input owner。未選窗口 consumer 時，adapter 本身不執行回呼。

Memory 組合排除原 Bundle 的 `interview_context`／`interview_navigation` 及此 adapter，改用 Memory 的窗口貢獻；若 Memory 已提供共用 `read_interview`，也排除此處 `interview_read`，同一 Graph 只註冊一次。A 使用預設有效來源 reader，並在最終 request 組裝後重用 `discover_interview_sources`。B 提供受限 reader，先驗整個固定分析窗口及資格，再交有序來源；任何固定來源失效都拒絕，不改讀 latest、不靜默縮小。Memory 仍擁有分析權限與固定版本，Interview 不 import Memory。

壓縮後沿原請求續步，不重跑預載。明確換窗才重新選取與投影；同一窗口的組裝順序由 Context owner 明示管理，Core 不認識訪談或 Memory。模型正文中的短碼文字不自動替換。

## 保存、恢復與取消

UoW／查詢按操作開啟短交易，不跨模型或人工等待持有 Session；async 接點把同步 DB 操作交 worker。最終材料保存於原生 request，不另建 Context 表或 State map。

同輪恢復沿已保存 request。輸入保存成功但 mapping 失敗時，沿原 Workspace／Turn 查回同一輸入 UUID；問答使用原生 task 已保存結果。業務提交、mapping 與 Checkpoint 不同交易，保留既有稀有重跑限制，不宣稱 exactly-once。

[取消回呼](cancellation.py)依 Agent 核對的 Workspace／Turn 撤回本輪正式原話與題答。Agent 必須先收束在途寫入；本方法成功不等於整個 Agent 取消完成。Host 在停用工具後仍須保留未結清輪次所需的撤回回呼與 UoW，下一輪查讀排除撤回資料，持久短碼不回收。
