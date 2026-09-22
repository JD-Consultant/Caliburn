# RS-4：原生具名 JD 工具前置

- 查閱：2026-09-13。範圍為目前隔離 relational App；只新增本文件，未改 src、未做 DB／provider 呼叫。
- 路由：[目前有效狀態](../../../current-decisions.md)、[工具責任契約](../../2026-09-12-jd-relational-agent-tool-contract.md)、[前一通知與回覆接點](../2026-09-13-jd-consultant-context-preflight.md)。契約較早的局部狀態行不是本輪完成清單；生成 `ReadPage`／`ChangeReadPage` 現為 format 2。
- 本地實際組合：LangChain 1.4.0、langchain-core 1.6.3、LangGraph 1.2.11、langchain-anthropic 1.7.2；四份已安裝 distribution metadata 均為 MIT。這是既有鎖定穩定版的本輪核對，不是重新挑品牌或宣稱永久最新版。
- 結論：可沿 native `StructuredTool`／`ToolRuntime`／`create_agent`，只補具名 App 接合。generated schema、共同 parser、refs／read、domain、intents、保存 receipt 各維持原權威；工具 callable 不自行授予 writer 權限。

## 1. 模型輸入與 App 注入的邊界

| 具名工具 | 唯一參數來源 | 本輪可直接重用 |
|---|---|---|
| `jd_read` | `generated.reads.ReadInput`：view、target_ref、cursor，三欄 required，nullable 照生成內容 | `parse_read_arguments` → `ReadService.read(document_id,args)` → `read_tool_output` |
| `jd_change_read` | `generated.reads.ChangeReadInput`：change_ref、cursor | `parse_change_arguments` → `ChangeReadService.read(document_id,args)` → `change_tool_output` |
| 八具名 mutation | `transport.MODELS` 的八個 generated input；description 沿 `transport.DESCRIPTIONS` | `model_command` → `command_context` → `bind_edit` → owned writer 的 `JdStorage.execute` → `project_observation`／`tool_output` |

八形狀為 CreateTaskInput、ReviseWorkInput、SetTextInput、InsertItemInput、DeleteItemInput、MoveItemInput、SetTaskCapabilityInput、ReplaceSelectionInput。不要另用 callable type hints 推導一份近似 schema，不改名稱、nullable、required、literal variants、陣列限制或六章欄位。完整任務仍一次保存；相依更正沿 revise_work／move／delete 的既有完整效果，不拆多個 set_text。

App 必須從可信 runtime 注入以下材料，全部不進模型參數：

| 材料 | 來源與用途 |
|---|---|
| dataset／document／AI run | 宿主配置與前景准入；核 native thread_id 等於 document。provider response ID／tool_call_id 不是文件權限。 |
| tool call 身分與 operation UUID | 原生已保存 AIMessage／tool_call_id 加 App run 的穩定綁定；owner 配發／恢復原 operation，不能每次 retry 重新 uuid4。|
| ReadService／ChangeReadService／HistoryReader／ReferenceCodec | 注入同 dataset 的既有服務；codecs 驗同文件、用途、版本。歷史同 head 仍只讀，名稱重複不影響定位。 |
| current-read binding B | 此 run 實際成功取得、`access=current` 的讀取版本觀察。只保存版本／必要觀察身分，不保存第二份正文。不可用 `jd_model_view` 的通知 H 假裝已讀完整 JD。 |
| 來源 resolver | 既有原話／Memory source owner 發配的 opaque source handles 與同文件可讀性；不可合成 `qa:1`，不可把 JD token 重簽成來源。 |
| 選區材料 | 真 selection issuer 提供的固定欄位／版本／UTF-16 範圍／原選文；不是一般 field token。現 `command_context` 明確拒 `selection_ref`，不能自行補 offset。 |
| 新內容 ID | App 的 UUID generator，交 CommandContext；模型不填 row ID／FK／position。 |
| writer／取消／恢復能力 | 本輪前景 owner 驗 run、同文件 gate、原 Future／宿主生存與 stopped proof；`JdStorage` 要求的 `WriterAuthority`，不是 bool 或 ToolRuntime 存在即准入。 |

對照實碼：[transport](../../../../experiments/jd-relational-app/src/jd_relational/transport.py)、[read transport](../../../../experiments/jd-relational-app/src/jd_relational/read_transport.py)、[change transport](../../../../experiments/jd-relational-app/src/jd_relational/change_transport.py)、[read/context binding](../../../../experiments/jd-relational-app/src/jd_relational/reads.py)、[intents](../../../../experiments/jd-relational-app/src/jd_relational/intents.py)、[storage](../../../../experiments/jd-relational-app/src/jd_relational/storage/service.py)。

## 2. 最小工具工廠

**採用建議，不宣稱工具已接入宿主：**工廠由固定表組成具名 `StructuredTool`，`args_schema` 使用 `GeneratedDTO.model_json_schema(mode="validation")` 的 dict，函式以 `runtime: ToolRuntime` 接 App context，再將其餘 arguments 交既有 parser。JSON Schema 模式由原生框架支援；它不負責 runtime validation，故共同 parser 必須保留，不能改成直接執行任意 kwargs。

1. `ToolRuntime.context` 只承接可信 run／既有服務與 owner；callable 先核 thread/document/run，不讓模型指定 provider、DSN、source resolver 或 authority。不要把這些物件序列化到 ToolMessage／receipt。
2. 讀取 callable 回原服務頁面。`has_more`／cursor／oversized_unit 全保留，不在工廠截斷、補全或合併新 head。成功 current 讀可更新 run 的輕量 read binding；history／change 讀不能升格該 binding。
3. 寫入 callable 以已持有 B 讀取 exact historical material，再用原 current refs 組 `command_context`，`bind_edit(operation_id,"ai",run_id,command,context)`。context builder 只接受匹配 B 的 current refs，SQL writer 再驗目前 head。現行 create_task 必填 container_ref／after_ref；早期 parent_duty_ref 外形不適用。refs 驗版與本輪實際讀取觀察各有責任，不能在寫入時自行 `read_current` 並將新 head 當模型已讀的 base。
4. 原生工具函式把固定 call identity 與 BoundEdit 交前景 owner；owner 先完成原操作身分持久綁定／writer 准入，再呼叫既有 `JdStorage.execute`。不要走只接受 manual descriptor 的 ManualRuntime 冒充 AI owner，不讓 callable 自製 FakeAuthority。
5. 回覆只來自 `WriteObservation`。`project_observation` 不讀新 head、不重播，confirmed receipt 不因後續 token／ToolMessage／Saver 回覆失敗而改稱 save_failed。已 bound 而未確認的情況由 owner 查原操作，不能換 key 自動重做。
6. Native `ToolMessage` 的 content 用既有 `read_tool_output`／`change_tool_output`／`tool_output` 驗過的 JSON content，call ID 取 `runtime.tool_call_id`，錯誤設 `status="error"`。不要把整個 Anthropic `tool_result`／OpenAI `function_call_output` 再塞進 ToolMessage content，形成兩層 provider 外殼。

current-read binding 是已交付觀察的版本身分，不是 JD 副本或授权。採 native state／既有 owner run 材料保存時，須和產生它的讀取結果對得上；無 binding、錯 scope、錯版本即安全拒絕。此處不設第二張表／通用 ref registry，也不讓 factory 自動 resume 未完成 graph。

`parallel_tool_calls=False` 只管模型請求，不能取代 App gate。原生 ToolNode 可平行處理多個 call；同文件 mutation 仍由 owner 決定實際准入，不能因多個 tool_use 同時出現就視為 atomic batch。wrapper 不得為了「修好」錯誤多次呼叫 handler。

第一個固定 SSE 旅程只需真正接好 read、完整 create_task、revise_work 與 change_read；其餘已有形狀可沿同工廠，但未實跑不得寫成全部 AI 工具驗收。selection owner 尚無實際能力時不宣稱可用；不得把選區改成整欄來通過。來源尚未接入時 `basis_refs=[]` 是合法無新增來源；非空必須走真正 resolver，未接時拒絕，不 fake readable。這不刪除既定功能或改來源政策。

## 3. 原生框架的三個實際限制

**官方能力：**LangChain 支援 Pydantic 或 JSON Schema 參數，`ToolRuntime` 的 context／config／state／tool_call_id 為隱藏注入；context 與 thread config 是分開輸入。工具可回結構化內容／ToolMessage，middleware 可在工具執行前攔截。依據：[Tools](https://docs.langchain.com/oss/python/langchain/tools)、[Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)。這些是框架接點，不代表廠商規定本案資料表、保存政策或安全文案。

**本地 1.4.0／core 1.6.3／LangGraph 1.2.11 原碼與合成 probe：**

| 情境 | 實際結果／採取措施 |
|---|---|
| closed generated DTO class ＋ `runtime:ToolRuntime` | 原生 `_parse_input` 先將含注入欄的 dict 交 DTO，合法 read 也被 extra=forbid 拒絕。改用 generated JSON Schema dict ＋既有 strict parser，無須製作第二個 injected DTO。 |
| ToolNode 預設 validation error | `ToolInvocationError` 模板含 `tool_kwargs`；預設 handler 回 `e.message`，合成 private marker 確實出現在 ToolMessage。不能只在業務函式內捕 Pydantic error，也不能只在 handler 外層 catch，因預設已轉成訊息。 |
| BaseTool 的 callback 時序 | `on_tool_start` 在參數 validation 前取得原 inputs；安全 error text 不代表 log 安全。保持本機允許清單診斷，不配置原 body／exception 的 verbose/tracing callbacks。model inputs／ToolMessages 的 native checkpoint 是原對話權威，不另 export 為除錯 log。 |
| BaseTool 轉 Anthropic 定義 | 單純 `convert_to_anthropic_tool(tool)` 這次輸出沒有 strict；顯式 strict=True 才帶 true。新 create_agent request 必核，不能引用舊 standalone SDK wire PASS 代稱。 |

嚴格 schema 的最小方式是沿既有 `tool_definition("anthropic",name)`／read/change definition，使用目前 adapter 支援的 `BaseTool.extras["provider_tool_definition"]` 原樣供給；或以官方 bind 的 strict 選項明示並比對最終 SDK request。前者少一次 schema 重寫，採用前須驗實際 request 仍有所有 required／nullable／closed objects，且沒有 runtime。這是目前 pinned adapter 的接合選擇，後续 adapter 升級須重驗，不自行寫 provider schema converter。

本地原碼位置（行號依本次 installed 版本）：

- `langchain_core/tools/base.py:778` `_parse_input`；`:1073` callback；`:1116` validation handler。
- `langgraph/prebuilt/tool_node.py:339` ToolInvocationError、`:383` 預設 handler、`:930` execute、`:1967` 同讀 schema／function annotation 發現注入。
- `langchain/agents/factory.py:1089` 原生 ToolNode 建構；`langchain_anthropic/chat_models.py:2831` converter 與 provider definition override。

純本機 probe 使用原生 StateGraph(MessagesState)→ToolNode→END、generated ReadInput、合成 AIMessage tool call，沒有 ChatModel、DB 或 provider。四次組合結果：class＋valid 是 error；class＋invalid 會回顯 marker；JSON-schema＋valid 正常且 ToolRuntime 已注入；JSON-schema＋invalid 經共同 parser 只得 invalid_input、無 marker。另驗 strict 預設缺省／显式 true。首兩次 probe 接線失敗分別為漏 PYTHONPATH、單獨 invoke ToolNode 缺 graph runtime；補本地 src 路徑並掛 native graph 後完成，不算產品缺陷或驗收 PASS。

## 4. 錯誤出口要保留保存事實

推薦前置 `wrap_tool_call` 核工具固定名稱、scope 與共同 parser，再執行一次 handler；錯誤採工具相符的固定 generated 結果。JSON Schema 模式的 callable 仍防禦性走同 parser；不要把模型注入的 `runtime`／`config` 欄 silently pop 後接納，應在原 args 上按 closed schema 拒絕。

- read／change：`ReadError.code` 對既有 `read_failure`，未知碼映 read_failed。文字取固定表，不能 `str(exception)`／`errors()`／`repr(body)`。
- mutation 未綁定：已知 invalid input 可回 generated UnboundInvalidInput，effect=unchanged、durability=unconfirmed、三個 refs=null；不虛構 operation 或 receipt。本輪 root 已將此唯一分支的 next_action 加入 reread_current，供缺有效 current-read binding／不可寫歷史引用使用；不混成 read_error，也不偽造 stale receipt。可修正一次的規則仍沿契約 §7，wrapper 不自動重試。
- mutation 已綁定：保持原 operation 身分與 WriteObservation；COMMIT 未確認／cleanup 失敗／ToolMessage ACK 遺失不能經通用 catch 改成「沒有保存」。原結果對帳完成前不啟動另一寫入。
- 未知故障／格式或投影錯誤：固定代碼回 owner 停止，診斷只留 allowlist metadata；不把 source 原文、refs、SQL parameters、args、callback exception 或 cause 發给模型／logger。GraphInterrupt／取消與程序停止由 native／owner 處理，不在 generic Exception wrapper 假裝停止。

即使設 `handle_validation_error` 的固定安全文案，也不能解決 callback inputs 先被外傳的問題。此處不新增通用 scrubber；只沿已選本機 logging／tracing 邊界，對新工具接點加 marker 反例。

## 5. 下一個有限驗證

1. **新 wire**：實際 create_agent＋SDK MockTransport 的 tools 等於既有 generated definitions；strict=true、10 個既定型別的參數沒有 App scope／runtime；未接選區的可用清單與實際能力一致。不得只測 factory 自己的 dict。
2. **錯誤與保密**：畸形／多餘欄、錯 ref、假 source、未知工具、非物件 args，未進 writer；ToolMessage 固定結果與原 call_id 配對，marker 不在錯誤／log。native callback 的原 inputs 不被未授權 sink 收集。
3. **真 PG 固定 SSE**：人工建立空白文件；AI read→create_task（多成果／要求，basis 可空）→保存→read/change；人工改文；下一輪 notice＋current read→AI revise_work。檢查 task／其他工作／來源／完整原話保留與原 base/result；AI 寫入須使用真前景 owner，FakeAuthority 僅可準備人工 fixture。
4. **版本交錯**：read B 後人工 H 前進，create 的 container refs 與其他 target refs 都不能偷偷採 H；history 等於 head 也不能成可寫 binding；跨 doc／dataset 在 SQL／source 呼叫前拒絕。
5. **原 operation 恢復**：同原 call replay 只能取原 receipt；同 ID 異意圖 conflict。SQL 已保存後 ToolMessage／checkpoint 回覆失敗，查回仍是原結果，不重新呼叫 provider、不新增 revision。

以上為本輪接線建議與有限前置，不宣稱前景 AI writer、source owner、selection issuer、真模型自然選用、Memory 接合或完整聊天 App 已完成。沿既有 App 保存與 native Saver／Store 分工，不新增正文／原话／Memory 的第二權威。
