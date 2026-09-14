# JD editor v2 跨語言契約候選

2026-09-10；JD-R002/C03；**可審查的 JSON Schema SSOT 候選，不是 production contract 或施工許可。**Owner 已同意 Plate、持續工作稿、同一畫面、前景 AI 回應期間暫停手改，以及同一 PostgreSQL 內的 JD 文件 authority；真人交付核對與 HTML／DOCX 問答包已 PARKED，不在本契約。

唯一 active 設計 schema 是 [`contracts/jd-editor-v2.schema.json`](contracts/jd-editor-v2.schema.json)，共 105 defs，對應 `format_version:2`／`jd-plate-clean-v2`；[v1 schema](contracts/jd-editor-v1.schema.json)與舊 probe 固定為歷史證據，不再生成新契約，也不安排資料搬移或雙寫。新語意及版本效力由[語意契約 v2](evidence/2026-09-10-jd-semantic-contract-closure.md)集中維護。

本契約依 [contract strategy](../contract-strategy.md)採 JSON Schema Draft 2020-12、封閉物件及 `$defs`；未複製到 `packages/job-analysis-contract`，也未生成或手改 Python／TypeScript DTO。隔離接線依 [六切片計畫](../plans/2026-09-10-jd-editor-core-implementation.md)消費同一經審定 SSOT，本輪語意契約閉合後再恢復 Task 1。production 切換另須 ADR 0073 Accepted、有限 Memory authority 正式化與 implementation gate，才把審定內容移入既有 contract package 的單一 SSOT，再由 codegen 產生兩端型別並跑 schema diff／consumer tests；隔離驗收不代替此 gate。

## 1. 契約表面與消費者

| 層 | 公開 `$defs` | 誰建立／誰驗證 |
|---|---|---|
| clean 文件 | `JdDocumentValue`、`JdSavedElement`、`JdText`、`JdEngineProfile` | App／Node 共同遵守 `jd-plate-clean-v2`；保存層只收成功驗證的完整值 |
| 模型參數 | `JdReadModelInput`、`JdEditModelInput`、`JdChangeReadModelInput` | LangChain tool schema 提供給模型；只含模型能選擇的 refs、七種有限命令及新內容 |
| runtime 合併請求 | `JdReadRuntimeRequest`、`JdEditRuntimeRequest`、`JdChangeReadRuntimeRequest` | Python runtime 注入 document／run／tool call；`jd_edit` 另注入 input、message、operation、digest、base 與 profile |
| Browser 選取 | `JdSelectionCaptureClientInput` | Browser 從 Plate 真實 selection 送 base revision＋Slate range；API admission 驗同文件／head／單一支持文字 block，再只注入本輪 `JdReadRuntimeRequest` |
| Python→Node | `JdPlateTransformRequest`／`Result`、`JdPlateValidateValueRequest`／`Result`、`JdPlateReadSelectionRequest`／`Result`、`JdResolvedEditCommand` | Python 驗證 scope／來源並把 refs 解成 element ID／原生 range；固定 Node adapter 只做 Plate 運算與原生唯讀 selection fragment |
| 人工保存 | `JdManualSaveClientInput`、`JdManualSaveRequest`、`JdManualSaveResult`、`JdPlateValidateValueRequest`、`JdPlateValidateValueResult` | Browser 只送 request key、base 與完整值；Python 配 document、submission、digest、profile，並走同一 Node profile／JD 保存交易 |
| 結果／回讀 | `JdReadResult`、`JdEditResult`、`JdChangeReadResult`、`JdWriteResult`、`JdActualChanges` | App 依真實 read、Node 結果及 durable receipt 建立；模型不得回填保存狀態 |

這些 definitions 是同一 schema 的不同邊界，不是多份 contract。`JdEditRuntimeRequest` 是 App 已把模型呼叫與 durable identity 綁定後的請求；`JdPlateTransformRequest` 是更窄的本機 Node IPC，不帶 document、Memory、operation 或資料庫權限。`JdManualSaveClientInput` 是唯一 browser manual-save input；內部 `JdManualSaveRequest` 不可直接信任客戶端提供的 document、digest、profile 或 submission identity。

## 2. clean document 與 profile 分工

`JdDocumentValue` 是非空 root array，root 只允許一般 body 或 `jd_section`。原有文字、classic list、表格及 `hr` grammar 沿正式 profile。v2 的 Task 至少有一個 body，並恰有一個 `jd_outcomes`、一個 `jd_requirements` 直屬群組；各組以 body 承載多項內容，未知可保留空 p。`jd_knowledge`／`jd_skill` 是完整項目，只能直屬相應 knowledge／skills section；不把任意段落或 cell ID 當作項目。完整 grammar 與合法位置見[語意契約 §2](evidence/2026-09-10-jd-semantic-contract-closure.md#2-最小完整文件結構)。

Schema 同時封閉 profile 的有限 props；僅 Task 可保存有序、不重複的 `knowledge_ids`／`skill_ids`，省略或空陣列均無連線。App／Node 另驗所有 Element ID 全文件唯一、同文件同 revision 的 K／S 端點及種類、numeric 與 HTML span 值一致、table 合法 grid、source ref 的 owner／scope／window、current target 是否仍屬 head，以及 normalization 後重開是否穩定。shape 通過不等於引用完整；反向集合由同版 outgoing links 推導，不存第二份可編關係，也不另建 domain normalizer。

`JdNewElement` 與保存節點分開；任何層都**不接受 ID 或 K／S links**。Python clone 合法新內容後，固定 NodeId profile 配 ID，再以 `JdDocumentValue` 驗完整候選。既有節點改字／移動保留 ID；模型複製以 new-element shape 重新配 ID，不能聲稱這次 insert 已保留原 Task links。首次建立及模型複製均先保存內容、重讀新基底，再以 `set_properties` 連結；不使用 temporary IDs。

## 3. 三個模型工具

### `jd_read`

`JdReadModelInput` 精確四選一或空物件：`{}` 讀 current；單一 `revision_ref`、`target_ref`、`selection_ref` 或 `continuation_ref` 讀固定範圍。模型不能傳 document、revision number、Slate path 或 offset。current result 的 target 可標 `current_base`；明示歷史 read 一律 `read_only`，即使指到當下 head 也不升格。

`JdReadResult` 成功時返回 `revision_ref`、有界 `fragment`、每個內容與 `target_ref` 的對應、可選 selection、source／change refs 與 continuation。continuation handle 本身不能寫；續頁結果保持原 read 的 `read_kind`／`revision_ref`／`access`，所以 current read 的續頁仍可對新讀到的 block 發同一基底的 `current_base` targets，而 history 等唯讀 read 的續頁仍全為 `read_only`。`p/h1/h2/h3/lic` 均可成文字 target；table cell 內定位 p 或 lic。失敗返回封閉的 error result，沒有 operation receipt。

`JdReadTarget` 對 Task 必帶 `knowledge_refs`／`skill_refs`，對 K／S 必帶 `used_by_task_refs`，皆可空；其他 type 不带這些欄位。App 從完整該 revision 推導，不能只查當頁。衍生 refs 可再按 `target_ref` 讀完整項目，但發配不等於模型已讀正文；改共享內涵前須讀受影響 Tasks，替換 links 前須讀完整原集合及新端點。history 的全部衍生 refs 仍唯讀，saved fragment 的 IDs 不能當作工具 refs。

### `jd_edit`

`JdEditModelInput` 只有 `commands`。來源只在新節點或 `set_properties.set.source_refs` 的實際附著位置填寫，App 收集本批明示引用聯集驗證，不要求頂層重複清單；該聯集不是完整 consulted-source log。未選固定 `maxItems`：非空由 schema 保證，批次／工具總額沿 runtime 有界配置，不能由模型提高。七種命令如下：

| `type` | 模型提供 | Python→Node 解析 |
|---|---|---|
| `insert_content` | `target_ref`、before／after／prepend_child／append_child、無 ID／K／S links 的 new elements | `target_id`、相同 placement、新 elements |
| `replace_block_content` | 文字 target ref、非空 Text array | `target_id`；只准 p/h1/h2/h3/lic |
| `replace_selection` | selection ref、Text array（可空，表示刪除 selection） | App 綁定的 `target_id`＋Slate range；模型不見 path／offset |
| `set_properties` | target ref、有限且互不重疊的 `set`／`unset`；Task links 使用 `knowledge_refs`／`skill_refs` | target ID；App 驗種類／scope，把 set 值及 unset 欄名映為 `knowledge_ids`／`skill_ids`；numeric span 沿既有映射 |
| `move_content` | target／destination refs、placement | 兩個 element IDs；Node 在當批依 ID 重取位置 |
| `unwrap_group` | group target ref | group element ID；保留 children |
| `remove_content` | target ref | element ID；刪除範圍以真實結果回報 |

空稿仍是帶 ID 的空 p。current read 發出該 p 的 target；第一批可在 root sibling 插入已理解內容並同批移除未改 placeholder，不增加 root-ref 類型或假 Task。所有 refs 必須同 document／current base；source refs 可由既有 conversation／Memory read 或已保存本輪 input 發出，不要求先寫進 JD。Python 呼叫既有 source owner 驗證，Node 不讀 Memory。

v2 將模型 properties／unset 與 `JdResolvedEditableProperties`／`JdResolvedUnsettableProperty` 分開；`JdPropertyUpdateConstraint` 與 `JdResolvedPropertyUpdateConstraint` 分別按 refs／IDs 欄名拒絕 set／unset 交集。Task links 的 set 替換整組，`[]` 清空，unset 移除欄位，省略保留；App 仍核同一不變量。模型仍不接受 attributes；numeric span、來源保留及移除依[工具 §4.3](2026-09-10-jd-app-tool-contract.md#43-單一輸入意圖與機械映射)，不新增通用屬性引擎或來源庫。

每次首次建立的兩階段均各自原子；第一步成功後的未連結稿合法，第二步失敗不撤銷第一步，unknown 必先對帳再續作。移除必需群組、取消 Task、刪／unwrap 被引用 K／S，須符合整批最終候選規則，不自動攤平或解除關係；精確順序及失敗出口統一見[語意契約 §3–5](evidence/2026-09-10-jd-semantic-contract-closure.md#3-共同編輯與引用邊界)。

正式 tool description 固定取各 `*ModelInput.description`，command／參數说明也保存在同一 SSOT。Task 3 factory 與 model-view 不能另寫不一致版本；正式說明有傳到 SDK 不等於自然模型操作已驗證。

### `jd_change_read`

`JdChangeReadModelInput` 接受一個 `change_ref`、明示的同文件 `before_revision_ref`＋`after_revision_ref`，或 App 前一頁發出的 `continuation_ref`。continuation 永遠綁原 change 或同一 before／after pair，只能讀下一頁，不能換版本。`JdChangeReadResult` 以 immutable snapshots 的有界 before／after fragments 為真相，並可逐頁讀完；只有實際保存且 JSON-safe 的 native operations 才作額外提示。人工保存可沒有 native operations。沒有可靠高亮時返回完整前後與 `presentation_limitations`，不捏造 affected blocks，也不取得還原、核准或切換 head 能力。

## 4. runtime、Node 與人工保存

`JdEditRuntimeContext` 的 document／run／employee input／assistant message／tool call／operation／base／profile 都由 runtime 注入。`request_digest` 由 Python 對 schema 驗證後的 document、exact base、commands（包含明示附著的 refs）與 profile 計算；不再要求獨立頂層來源集合，模型與 Node 都不能配置 digest。`tool_call_id` 只作訊息配對，`operation_ref` 才是 document-scoped durable identity，兩者連同 message/input binding 在 ToolNode 前 checkpoint。

`JdPlateTransformRequest` 只帶 fixed profile、完整 `base_value` 與 `JdResolvedEditCommand[]`；K／S 已解析為 IDs，Node 不接 opaque semantic target refs。Node success 才可帶 canonical `value`、JSON-safe native operations、affected IDs 與 `changed`；failure 只帶 error，不回傳候選 value／operations，避免把拋棄式中途狀態當 durable partial result。Node result從未代表已保存；Python 仍須在 JD transaction 重查同 operation digest、base value／revision 及 head。

Browser 選取不是第四個模型工具。UI 有 dirty 內容時先完成同一人工保存，再由 Plate 真實 selection 建立 `JdSelectionCaptureClientInput`。API admission 核對 base 仍是同文件 head 後，把已驗 canonical value、profile 與 range 送固定 Node `JdPlateReadSelectionRequest`；Node 載入同一 value，以原生 range／fragment API 驗 selection 落在單一 `p | h1 | h2 | h3 | lic` 並回 `target_id`、range 與 fragment。若載入 normalization 改了 canonical value、range 無效或跨支持 block，就回既有 failure，不能偷換 base，也不寫 value／DB。成功後 App 才把 browser input 作為可選 `jd_selection` 注入本輪 `JdReadRuntimeRequest` 並隨 run checkpoint；`jd_read({})` 由這份已驗 context 回 selection 內容並發配 `selection_ref`，之後模型才可用 `replace_selection`。沒有 selection 時沿原 current read。模型三個 input 都不接受 Slate path／offset，provider parameters 不因這個 browser-only seam 增欄。

人工保存分兩層：

1. Browser 以 `crypto.randomUUID()` 產生 `JdManualSaveClientInput.request_key`，連同 base revision ref 與完整新 value 送出；同次 timeout／unknown 重送保留同 key 與 exact payload。這是 client request identity，不是員工手填，也不需要先向 server 預約。
2. Python 從 route scope 建立 `document_ref`，把 `(document, request_key)` 綁成 `submission_ref`，以 server 驗證後的固定 JSON 重算 `request_digest`，注入 profile／origin，再形成 `JdManualSaveRequest`。不同 payload 使用同 key 返回 conflict，不能覆寫。
3. 完整 value 走 `JdPlateValidateValueRequest`／`Result`；它使用同一固定 editor、normalization 與 clean-value 驗證，不偽裝成空 `jd_edit`，也不繞過 commands 的 `minItems:1`。

## 5. 保存結果與恢復

`JdWriteResult` 是 AI 與人工保存共用的結果 envelope。人工結果中的 `operation_ref` 代表 server 綁定的 submission identity；AI 則代表 checkpointed JD operation。結果把 `document_effect=unchanged|committed|unknown` 與 `receipt_durability=confirmed|unconfirmed` 分開，避免「文件已知未改，但 failure receipt 尚未保存」被誤報成 unknown。

- `committed` 必須有 operation、base、result revision、change、actual changes，且 effect=`committed`、receipt=`confirmed`。
- `no_change` 必須有相同可對帳資料，result revision 指已檢查的 base，不造新內容版。
- `outcome_unknown` 必須有原 operation，effect=`unknown`、receipt=`unconfirmed`，唯一下一步是 `reconcile_operation`。
- 其餘確定錯誤的本次 payload effect=`unchanged`；是否已有 terminal receipt 另據實填。已保存 terminal failure 也是 immutable result。
- 同 operation／submission 搭不同 payload 是 `operation_conflict`，保留原結果；相同 digest 重播返回任何既有 terminal result，不重新執行。

補正後的 `JdWriteResult` 以[工具 §6.1](2026-09-10-jd-app-tool-contract.md#61-狀態與下一步的封閉關係)強制 status×next_action。operation 已綁而 receipt 未確認，優先 `reconcile_operation`，即使 effect 已知 unchanged；confirmed 必有 operation，busy 不配 operation。六種確定 failure／busy 的 result／change refs 為 null，unknown 也不能先聲稱結果版；conflict projection 可指原回執，mapper 須核確實來自同一原操作。no_change 的 native_operations 為 null、affected IDs 為空；base=result=actual before=actual after 的跨值等式由 mapper／交易驗證，不謊稱 schema 能比較 opaque refs。

`JdReadFailure` 新增 read_failed，與 unsupported_content 均只允許 stop；invalid_input／target_missing／busy 的動作各依唯讀矩陣。讀取失敗不配 operation、不當成文件空白。程序／交易／receipt 的單次 attempt、取消、控制預算及恢復責任依[ER03 附件](evidence/2026-09-10-jd-error-recovery-contract-closure.md)；這不是新增 retry 工具。

commit 後遺失 ToolMessage 時，runtime 先停止並確認 writer 已停，再查同 operation receipt，只補缺失且匹配原 `tool_call_id` 的 ToolMessage。已存在結果不重複；沒有已發配 JD operation 的純訪談 turn 不查 receipt。仍 unknown 時不解鎖、不配新 operation、不讓模型重寫。這是 JD 專屬接線；現行隔離 runtime 的一般 cancel／Memory repair 尚未自然涵蓋。

## 6. 代表性 JSON

以下四例各自展示一個契約形狀，並非同一操作的連續輸入與結果。第一例在空稿增加一個工作 section；新節點沒有 ID 或 links，未知成果／要求以空 p 保留兩個必要群組：

```json
{
  "commands": [
    {
      "type": "insert_content",
      "target_ref": "jd-target:empty-p",
      "placement": "after",
      "content": [
        {
          "type": "jd_section",
          "section_kind": "work",
          "children": [
            {
              "type": "jd_task",
              "source_refs": ["conversation:source-window"],
              "children": [
                { "type": "p", "children": [{ "text": "每月核對約定服務的執行情形。" }] },
                {
                  "type": "jd_outcomes",
                  "children": [{ "type": "p", "children": [{ "text": "" }] }]
                },
                {
                  "type": "jd_requirements",
                  "children": [{ "type": "p", "children": [{ "text": "" }] }]
                }
              ]
            }
          ]
        }
      ]
    },
    { "type": "remove_content", "target_ref": "jd-target:empty-p" }
  ]
}
```

保存成功結果：

```json
{
  "status": "committed",
  "operation_ref": "jd-operation:01",
  "base_revision_ref": "jd-revision:01",
  "result_revision_ref": "jd-revision:02",
  "change_ref": "jd-change:01",
  "document_effect": "committed",
  "receipt_durability": "confirmed",
  "actual_changes": {
    "origin": "ai",
    "before_revision_ref": "jd-revision:01",
    "after_revision_ref": "jd-revision:02",
    "native_operations": [
      {
        "type": "insert_node",
        "path": [1],
        "node": { "type": "p", "id": "p-new-01", "children": [{ "text": "新增內容" }] }
      }
    ],
    "affected_element_ids": ["p-new-01"]
  },
  "error": null,
  "next_action": "continue"
}
```

commit 嘗試後無法證明結果：

```json
{
  "status": "outcome_unknown",
  "operation_ref": "jd-operation:01",
  "base_revision_ref": "jd-revision:01",
  "result_revision_ref": null,
  "change_ref": null,
  "document_effect": "unknown",
  "receipt_durability": "unconfirmed",
  "actual_changes": null,
  "error": { "code": "receipt_unavailable", "message": "保存結果仍在確認中", "command_index": null },
  "next_action": "reconcile_operation"
}
```

Browser 人工保存輸入：

```json
{
  "request_key": "123e4567-e89b-42d3-a456-426614174000",
  "base_revision_ref": "jd-revision:02",
  "value": [
    { "type": "p", "id": "p-empty-01", "children": [{ "text": "員工更正後的內容" }] }
  ]
}
```

下列輸入必須拒絕：新 element 帶 `id`；`li` 第一個 child 不是 `lic`；非 work section 含 Duty／Task；未知 props；Text mark 為 `false`；模型傳 document／operation／profile／path／offset；跨文件或歷史 ref 寫入；同 request key／operation 搭不同 payload；Node failure 帶候選 value 或 native operations。

## 7. 有限驗證與未涵蓋範圍

本候選 v2 共 105 defs；語意 grammar、refs／IDs 分流、read 投影及本次有限驗證的實際結果集中於[語意契約 §6–7](evidence/2026-09-10-jd-semantic-contract-closure.md#6-有限工作與通過條件)。定義編譯與固定反例不代表原生、保存或自然模型通過。

v1 補正前 85 defs 的驗證記錄，及補正後 86 defs／property constraint／參數與結果限制的[封存驗證紀錄](evidence/jd-contract-closure/README.md)，均保持原始效力；前者對應[補正前完整快照](evidence/jd-contract-closure/schema-before.json)。它們是歷史契約證據，不把舊 hash 或結果回填 v2。

F02 完整 r2 [`F02-A-canonical-input.json`](evidence/jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/F02-A-canonical-input.json)仍是 v1 的 canonical 內容基線，不能直接冒充有兩個專屬群組的 v2 fixture。新 fixture 須在新證據中明列固定內容對應與呈現變更，不改原封存，也不稱通用 migration；較早 raw fixtures 的舊 list／metadata 仍不能冒充 clean value。

本完整 Draft 2020-12 schema **不直接宣稱等於 provider 的 strict tool parameters**。CT49–51 的隔離 runtime 由 LangChain `create_agent` 接 `BaseTool`，現行顧問未設定 strict，因此一般工具是 `strict=None`，不是已驗的嚴格契約。本地固定版 [`_convert_json_schema_to_openai_function`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/.venv/Lib/site-packages/langchain_core/utils/function_calling.py) 會先 dereference 再移除 `$defs`；[`dereference_refs`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/.venv/Lib/site-packages/langchain_core/utils/json_schema.py) 遇遞迴 ref 會停止展開。故把本候選直接塞進 `BaseTool.args_schema` 再交 converter，可能把遞迴 new-element 分支剪成空約束，`strict=False` 也不修這個序列化問題。

**v2 沿用的固定接法：**factory-built 三個 JD `BaseTool` 仍持由同一 active SSOT 生成的完整 input model，供 ToolNode 與 App validation。JD model-call middleware 只把這三個已驗身分的工具在 model-view 換成 Responses raw function dict：`type:function`、固定 name／description、由同一 SSOT 機械抽取的 object-root `*ModelInput`＋`$ref` closure 作 `parameters`、`strict:false`。固定 LangChain 的 `convert_to_openai_tool` 對已是 Responses function 的 dict 原樣返回，避免上述 BaseTool dereference；ToolNode 仍執行原 factory BaseTool。這個 override 不改其他 Memory tools 的 `strict=None`，也不以名稱相同的替代工具混入。provider output 一律再由 App 對完整 definition 驗證，錯誤回 `invalid_input` 並沿既有有界修正。

這是固定三工具的 provider renderer，不是通用 schema compiler；其抽取結果須由同一 schema 在 codegen／no-diff 檢查中重生，不能手寫第二份權威。`strict:false` 承認 provider 不保證 shape 的代價，也不是跨廠共識或永久偏好。要切 `strict:true`，須先證明由同一 SSOT 產生符合固定 OpenAI／Anthropic subset 的機械 projection，並驗實際 provider wire。

v1 補正前的[零網路 SDK 序列化觀測](evidence/jd-contract-schema/provider-wire-README.md)保留原 schema 與 placeholder description 的有界結論；原始 `$ref` 4／61／4 及 hash 不改。v1 [補正後核對](evidence/jd-contract-closure/README.md)使用 LangChain 1.4.0／core 1.6.2／langchain-openai 1.6.0／OpenAI 3.8.0，捕捉當時 schema 和正式說明。

v2 的[獨立 wire 腳本](evidence/jd-semantic-contract-probe/provider-wire-v2.py)沿同一 SDK 組合，以 MockTransport 捕捉[完整 request](evidence/jd-semantic-contract-probe/provider-wire-v2-captured.json)；[實際結果](evidence/jd-semantic-contract-probe/provider-wire-v2-results.json)確認三工具參數／正式說明與 active SSOT 全等，新的群組、模型 refs／set-unset 限制送達，resolved IDs 未暴露為模型參數。初次探針錯認預期 HTTP 400 的 SDK 包裝例外名，修正 assertion 後通過，沿革保留於結果。這只證明 SDK 序列化；零網路、零工具執行，沒有驗 ReadTarget 實際回覆、真 provider 接受、自然模型品質或 production 接通。

依 2026-09-10 查閱的 [OpenAI strict mode](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)、[OpenAI Structured Outputs subset](https://developers.openai.com/api/docs/guides/structured-outputs)及 [Anthropic strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)，兩家都建議能用時採 strict，但支持的 schema subset 不是完整 Draft 2020-12。完整官方對照與版本效力集中在[既有證據 §2.13](evidence/2026-09-09-jd-app-tool-and-review-contracts.md#213-契約定稿前的官方複核參數結果版本與重試)；本附件不重複推測 provider 內部。

Schema 不替代以下整合驗收：完整 r2＋正式 list/table plugins、source owner 的真實 scope/window、ID 全文件唯一與 cross-field table span、Node normalization／重開、operation binding／receipt 對帳、manual dirty save／AI writer admission、同畫面 renderer 與真模型 JD 品質。history reference 必為 read-only、current target 必綁仍為 head 的 base、同批 refs 同 revision、no-change 的 before＝after、continuation 固定原 read，以及本批明示來源經既有 owner 驗證／未改舊 refs 保留等不變量，均由 App 以實際 owner／保存資料驗證；schema 本身不保證。它沒有 pending／accepted、handoff、HTML、DOCX、export、登入、ACL、RAG 或第二 Agent。

效力仍以 [正式 profile](2026-09-10-jd-plate-document-profile.md)、[工具契約](2026-09-10-jd-app-tool-contract.md)、[App 接線設計 §5–§7](2026-09-09-jd-editor-app-integration-design.md#5-保存選項與可觀察的交易契約)及 [Proposed ADR 0073](../adr/0073-plate-jd-app-working-document-and-revision-authority.md)為準；若 schema 與其語意衝突，先修候選，不以生成型別改寫產品決策。
