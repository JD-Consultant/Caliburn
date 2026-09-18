# JD App 工具契約：Plate 持續工作稿

2026-09-10；JD-R002/C03；**G4 可評審設計候選，不是 production authority 或施工計畫**。本稿只定義既有主顧問使用 `jd_read`、`jd_edit`、`jd_change_read` 的責任、結果與恢復語意。Owner 已選 Plate 免費核心＋持續工作稿：AI 與人編輯同一份已保存最新版，完整變更可查，沒有個別 pending accept／reject、長期 suggestion chain 或 accepted projection。

有效產品決策依 [current decision register](../current-decisions.md)，流程 gate 依 [decision process](../decision-process.md)。跨 Python／JavaScript／Web 的 wire shape 見[JSON Schema 附件](2026-09-10-jd-editor-contract-schema.md)，依 [contract strategy](../contract-strategy.md)使用單一 SSOT 與生成型別；本稿負責語意和驗收，不另造手寫 transport contract。文件保存資料模型與交易實體由同期 storage ownership 設計承接，本稿不重複定表。provider 參數與 App 完整文件驗證的能力差異依[官方複核 §2.13](evidence/2026-09-09-jd-app-tool-and-review-contracts.md#213-契約定稿前的官方複核參數結果版本與重試)，不能以 JSON Schema 格式相同就宣稱兩家 strict 相容。

**現行設計為 v2：**唯一 active schema 是 [jd-editor-v2.schema.json](contracts/jd-editor-v2.schema.json)，105 defs，固定 `format_version:2`／`jd-plate-clean-v2`。Task 的兩個平行群組、同 JD 共享 K／S、首次建立與刪除規則集中於[語意契約 v2](evidence/2026-09-10-jd-semantic-contract-closure.md)；v1 schema／封存是歷史證據，不生成新契約、不做 migration 或雙寫。

## 1. 已決邊界

2026-09-10 補正：[責任稽核](2026-09-10-jd-responsibility-and-evidence-audit.md)的 TF／ER 缺口由本文 §4.3／§6、同一 SSOT 與正式模型說明承接；[模型參數依據](evidence/2026-09-10-jd-model-input-contract-closure.md)、[錯誤與恢復依據](evidence/2026-09-10-jd-error-recovery-contract-closure.md)記選擇理由。新的離線驗證另存，不將旧 placeholder 序列化或格式通過當成自然模型已能正確操作。

1. 主顧問仍是現行 LangChain `create_agent` loop；工具以既有 `BaseTool` 注入，不新增 Agent、Memory、Store 或 MCP 依賴。
2. App 是唯一執行者。模型提出有限操作，不能自填 document、revision、operation ID、engine profile、Slate path、中文字元 offset 或保存結果。
3. Plate 只計算及驗證候選 value／operations；Node 不讀資料庫、Memory 或 canonical conversation，也不裁定工作事實真假。
4. `jd_edit` 一次呼叫是一個同基底、按序執行、整批發布的文件改動。disposable editor 中可能發生中途操作，正式文件只能全部發布或完全不發布，不提供 durable partial commit。
5. 工作稿 revision 保存後立即成為下一次人／AI 編輯的 current。保存不等於員工看過、專業品質通過或 AI 自評正確。
6. 歷史 revision 與差異在同一 JD 工作畫面唯讀展開；不是第二份可編輯 JD，也不會把 current head 切到舊版。

## 2. App 注入上下文與已發配引用

跨輪員工手改的主動模型通知依[定點研究 §3](2026-09-10-jd-context-change-and-source-research.md#3-本案如何沿官方接點接線)；runtime context 可供工具讀取，不自動等於模型已看到。沿官方 model-view 接點供給當輪文件狀態，保留原始問句；通知與可查完整差異分工，不能將通知版本冒称整份已讀，也不因此對模型參數開放 document／offset 等 App 責任。此補充未改 wire schema，實際 delivery／compaction／resume 仍須 Task 3／5 驗收。

每次工具執行前，App／runtime 供給下列權威上下文，模型看得到需要理解的部分，但不把它們作為可自由填寫的工具參數：

| App 注入資料 | 契約 |
|---|---|
| document scope | 綁目前單一 JD；必須與 conversation／Memory 的 document scope 相同 |
| current input／run | 綁已成功保存的員工輸入、目前 run 及該次 AI message |
| base | 綁 `jd_read` 所讀的已保存 revision 與其完整 value；不能只帶版本號再套另一份稿 |
| operation | 綁目前 AI message 的 tool call 與穩定 JD operation；模型不能建立或更換 |
| engine profile | 綁正式 Plate profile／format version；模型不能降級 normalization、ID 或格式限制來讓操作通過 |
| actor | AI 工具寫入固定為 AI；人工保存走同一 App 寫入邊界，但不偽裝成 tool call |
| current UI selection | 只有員工在目前已保存基底上的真實選取可發配；未選取時不憑空建立局部 range |

App 只發配本案需要的五種引用：

| 引用 | 綁定內容與可用範圍 |
|---|---|
| revision reference | 同文件的一個 immutable saved revision；不帶 reference 的 current read 可發出明標為目前寫入基底的 revision／targets，只有在該 revision 提交時仍是 head 才可寫；明示 history read 發出的 revision 一律只讀，即使它碰巧仍等於 head 也不靜默升格 |
| target reference | 一次 `jd_read` 返回的實際 block，綁 document、revision、block ID 與必要基底內容；不等於 Slate path |
| selection reference | App 捕捉的同一支持正文 block 內 range，另綁 document／revision／block；不接受模型自算 offset |
| change reference | 一次已知文件操作的 base、result、origin、actual changes 與保存結果；不把任意版本比較冒充單次 AI 修改 |
| source reference | 由既有 conversation／Memory read 或已保存本輪 input 上下文發出的 canonical handle；JD App 轉交並呼叫既有 owner 驗 scope／window，不要求先存在於 JD。只定位可回查依據，不代表語意已自動證實 |

引用的 wire encoding 是 App 私有細節。本契約不要求通用 token store、模糊搜尋或簽章引擎；實作可由既有 read 結果發出可回查 handle，再以文件、revision 與實際物件核對。模型只能回傳 App 已發配的引用。任意編造、跨文件、過期、已刪除或不屬於目前 scope 的引用都不執行。

JD 的 target／selection 由 `jd_read` 發出；來源 handle 可來自上述既有來源入口，兩者不混成必須先寫進 JD 才能使用的循環。單憑一個字串可以解析，不等於該次 run 已取得 current target；App 必須用實際讀取結果及其 revision／讀取種類核對，不能藉猜 ID 繞過 read 前置條件。具體 handle encoding 不新增通用 token 系統。

### 2.1 首次畫面選取如何進入工具

Browser 以 Plate 的真實 selection／原生 range 接點捕捉範圍，透過既有 `POST /documents/{document_id}/runs` 的可選 `jd_selection` 欄位送出；其 shape 引用同一 SSOT 的 `JdSelectionCaptureClientInput`，只有 `base_revision_ref` 與原生 `range`。這是 App→App 資料，模型參數不出現 path／offset。一般訪談不带此欄位，原始員工問句仍原樣保存，不把 range 改寫成員工陳述或 Memory。

UI 先完成 dirty 保存並確認，再捕捉已保存基底上的有效選取。API 在 run admission 核對同文件、current head、合法原生 range 及其完整 fragment；僅單一 `p/h1/h2/h3/lic` 文字容器可進入本版精確替換。前景 writer gate 取得後，經驗證的選取 context 隨當次 run checkpoint 保存，`jd_read({})` 從該 context 返回實際選取內容及首次 `selection_ref`。之後 `jd_edit` 仍須使用實際 read 發出的 reference；不预造引用，也不另建 token 發配服務或第四個模型工具。

若保存／normalization 使原選取無法核對，或 admission 時基底已過期，拒絕該次帶選取的執行並保留聊天輸入供重選；不猜字串位置、不以合法 offset 代替基底內容驗證。恢復 run 時仍綁原 revision，不把 selection context 套到新 head。實作測試從 browser capture 經 admission／current read 取得引用，再驗重複繁中文字只改該處，不能直接製造 fixture selection_ref 跳過入口。

Python 取得原生選取的具體接點為固定 Node 唯讀 entry `read-selection`：`JdPlateReadSelectionRequest` 帶 profile、已保存完整 value 與 App 捕捉的 range；Node 以同一 profile 載入，核對單一支持文字容器，呼叫 `editor.api.fragment(range)`，回 `JdPlateReadSelectionResult` 的 target ID／range／fragment 或既有格式的失敗。載入若改變已保存 canonical value，拒絕該基底，不默默以 normalization 後的位置繼續。這和 `transform`／`validate-value` 共用正式 profile；不透過假修改取得 fragment，不另建定位引擎，也不增加第四個模型工具。回傳 fragment 是讀取投影，不是新的保存稿。

## 3. `jd_read`

### 3.1 輸入與讀取模式

- 不帶 reference：讀目前文件的已保存 head。
- revision reference：明示讀該同文件歷史 revision，結果及其新發出的 references 都標為 read-only；不能成為 `jd_edit` 基底。要取得寫入能力必須重新作不帶 reference 的 current read，由 App 發出 current-base references，不能因版本號相同而靜默升格。
- target／selection reference：讀其固定 revision 中的完整支持 block 或選取範圍，連同必要附近上下文。
- 讀取超過單次有界輸出時，App 返回綁同一 revision 的唯讀 continuation handle；它只是該 revision read 的下一頁，不是第六種可寫 reference。續 current read 的結果仍可發相同基底的 current-base targets，續 history 則仍唯讀；不讓續頁把歷史升格或換成新 head。模型不得自行改 offset。

UI 選取是目前同一工作畫面的額外讀取入口。沒有選取時，局部改寫的最小安全範圍是模型已讀的完整正文 block；相同文字出現多次時不取第一個命中。

**可直接改寫的文字容器固定為 `p | h1 | h2 | h3 | lic`。** `lic` 是官方 classic list 的內容節點，即使不在文件 grammar 的 `body` union 中仍可定位文字；不把整個 `li` 當文字容器，也不尋找不存在的 `li→p`。表格儲存格定位其內的 `p` 或清單中的 `lic`。`jd_read` 對上述容器發出 target，真實選取若在單一容器內才可發 selection；原生 range／fragment 接點不改。

### 3.2 返回

Task 3 已納模型通知設計 §6.2 的既有欄位語意：whole-document current／history read 的 `change_refs` 只回建立該 revision 的 committed change，初始版為空；同版續頁保留相同 reference。用 `jd_change_read` 讀該事件，再讀其 `before_revision_ref` 可向前回查至明示基準。no_change 不在建立事件鏈；取得導航引用不等於已讀正文。三工具形狀不變，模型說明仍只取 SSOT。

返回至少包含：讀取種類（current／history／selection）、saved revision reference、實際內容、支持 block 的 target references、可用 selection reference、內容所帶 source references、可查 change references、是否尚有 continuation。current/history/selection 是同一文件的不同讀取投影，不是三套文件或互斥產品頁；只有 current read 發出的 current-base revision／targets 具候選寫入能力，且提交時仍須通過 head／base 檢查。

Task 的 read target 必含 `knowledge_refs`／`skill_refs`；K／S item 必含由 App 推導的 `used_by_task_refs`，皆可空。這些仍是既有 target reference，由完整該 revision 計算，不能只看當頁或另存反向集合。發配不代表已讀正文；改共享內涵前讀完整 item 及受影響 Tasks，替換 links 前讀完整原集合及新端點。可沿已發配 `target_ref` 讀其全文，history 衍生 refs 全為唯讀；saved IDs 不當工具 refs。

App 可以返回人工／AI 的 change origin，供顧問判斷內容如何形成；`origin=manual` 只證明人改過文件，不自動表示那次修改是明確的工作事實更正。

## 4. `jd_edit`

### 4.1 模型可提供的內容

模型只提供：

1. 一批有意義、數量有界的 commands；
2. 每項 command 使用的已發配 target／selection／插入位置 reference；
3. 必要的新文字、支持的內容節點或允許的 properties；
4. 模型實際讀過、要附著於特定內容的 source references（可為零），只在新節點或明示 `set_properties` 填寫；不另填頂層集合，也不能虛構「已驗證」狀態。

第一版支持的 command 集合固定為既有候選：`insert_content`、`replace_block_content`、`replace_selection`、`set_properties`、`move_content`、`unwrap_group`、`remove_content`。拆分／合併工作必須用這些有限命令明示內容如何分配及哪個身分延續；原生 `splitNodes` 不代表 App 已理解 Task 語意。任意物件 patch、任意程式、外部檔案路徑、模糊字串定位與未列出的 element／property 都拒絕。

**空稿第一筆寫入：**正式空稿已有帶 ID 的空 `p`。current `jd_read` 發它的 target，並明示合法 root sibling 的 before／after 插入位置；不用另造可寫 root ref。模型可在同批 `insert_content` 建已理解的內容，再 `remove_content` 移除仍未改動的空 placeholder。App 以該 target 的同基底原生位置執行，整批 normalize／驗 grammar 後才發布；不因空稿自動生成整份 JD 或假 Task。

所有模型新增 Element **不得帶 ID 或 K／S links**；App clone 新內容後由固定 NodeId 產生，再驗唯一。新 Task 至少一個 body，恰有一個 `jd_outcomes` 及一個 `jd_requirements` 直屬群組，各可用空 p 保留未知內容；K／S 為相應章節直屬完整 item。既有目標改名／換文字保留外層 ID，移動帶完整既有 subtree；新複本不沿用舊 ID。`replace_block_content`／`replace_selection` 的對象限上列五種文字容器，替換其文字與支持 marks，不藉改標題換整個 Task。source refs 由 Python 交既有 owner 驗證，來源有效性與格式／ID 檢查各負其責。

首次建立或模型複製：先 `insert_content` 建內容並確認保存，再 `jd_read({})` 讀新基底及相關內容，最後用 `set_properties` 連結。兩次編輯各自原子；未連結草稿合法，第二步失敗不撤銷第一步。unknown 先對帳，不重新 insert、不沿用前版 refs 或自造 temporary IDs。完整流程及共享影響見[語意契約 §4](evidence/2026-09-10-jd-semantic-contract-closure.md#4-模型參數及app分工)。

### 4.2 預檢、運算與發布

1. Runtime 先確認 canonical 員工輸入已保存，並把 AI message／tool call 與 JD operation 綁定到 checkpoint。
2. App 解析所有引用，要求同 document、同一 current saved base；歷史 revision reference 不可寫。
3. Python 向既有來源 owner 核對 source reference 的文件歸屬、精確保存窗口與可讀性；Node 只接已核對的引用表示。
4. Node 以正式 profile 建立 disposable Plate editor，按 command 順序執行原生 transforms。任何一步失敗即丟棄候選。
5. Node 驗整批最終候選的 value、ID、支持類型／props、K／S 端點及 normalization 結果，返回原生 actual operations／affected content；不能只回模型想做的摘要。中間暫態可缺群組，最終存留的 Task 必須完整。已知候選 grammar／relation 違規映為 `invalid_input`，不冒充引擎故障。命令的修改範圍由有限原生 adapter 約束，未指定內容與工作語意保留以實際前後內容及驗收核對；不宣稱 Node 自動判斷所有工作條件是否等義，也不為此建立通用語意比對引擎。
6. App 在唯一保存邊界重查 operation digest、base value／revision 與 current head，原子提交新的工作稿 revision、change／receipt 與 head。no-change 保存可對帳結果，但不造文件 revision。
7. Tool result 只依保存層可證明的結果回傳。模型最後一句失敗不回滾已提交內容，模型說「已更新」也不能取代 receipt。

一批內多個 references 若來自不同 revision，即使各自曾有效也整批拒絕。模型／provider 意外給出平行寫入時不平行發布；維持現行單工具序列化與同基底規則。

### 4.3 單一輸入意圖與機械映射

`JdEditModelInput` 只含 `commands`；文件 ID、基底、operation、digest 仍由 App 提供。`set_properties` 的同一欄位不能同時出現在 set／unset；SSOT 的有限共用 constraint 與 App 預檢都拒絕，不靠執行順序裁決。

僅 Task 可設定 `knowledge_refs`／`skill_refs`；set 替換整個有序、不重複集合，`[]` 清空，unset 移除，省略保留。App 驗已發配、同文件／current base／access 及端點種類，再把 set 值與 unset 欄名都映為保存的 `knowledge_ids`／`skill_ids`。模型與 resolved properties／unset／constraint 在同一 SSOT 分開，Node 不接 opaque semantic refs；來源 `source_refs` 保持原 owner 與用途。

取消 Task 須同批明示 unwrap 兩個專屬群組，再 unwrap Task，保留 body 與順序；單獨 unwrap Task 不自動攤平。仍保留 Task 時移除必需群組，須同批明示同類替代組。刪／unwrap K／S 或其祖先須核全部剩餘引用，必要時同批明示解除／改接；不級聯刪工作或靜默斷線。完整操作後果由[語意契約 §3](evidence/2026-09-10-jd-semantic-contract-closure.md#3-共同編輯與引用邊界)維護。

模型只填 numeric `colSpan/rowSpan`，不能填或 unset `attributes`。保存稿仍保留原生合法 HTML span 表示；Node adapter 取得命令當下 cell，用原生 setNodes／unsetNodes 同步已存在的對應 HTML key，unset 同時清除該 key，空 attributes 物件移除，另一維保留。新增省略 span 的原生有效值為 1，明填 1 保留 numeric 1；不自動合併／拆分鄰格。完整規則與官方原碼見[模型參數附件 §3](evidence/2026-09-10-jd-model-input-contract-closure.md#3-tf02單一-span-意圖與保存映射)。

来源只在實際附著位置輸入；App 遞迴收集本批明示的新節點及 `set.source_refs` 聯集，交既有來源 owner 驗證。該聯集不是模型所有曾查閱或用來判斷刪除的來源清單。它不覆蓋全文來源，不清掉本批沒有重填的舊 refs，不建立新的查閱紀錄庫。

- 新增只附著各節點明示的 refs，不自動繼承本輪／父節點全部來源。
- 文字替換與移動保留既有 refs，保留不代表重新核實；需換依據時在同批明示 `set_properties`。set.source_refs 替換完整陣列，`[]` 清空，unset 移除欄位；省略維持原值。
- unwrap 保留子內容、標題、ID 與各自 refs；已明示移除的外層 refs 留在歷史，不自動背書每個 child。必要時先在同批明示附給適合的既發配子目標。
- 刪除只讓該 subtree 退出 current；其前版及來源仍可查，不刪原始問答／Memory或其他內容的相同來源。

三工具正式模型說明以 SSOT 各 `*ModelInput.description` 為唯一原文，factory 與 provider model-view 同用；各 command description 解釋適用目標、位置、來源與限制。這不增加另一套 prompt config，也不保證模型自然使用效果，須由 Task 3／後續模型驗收證明。

## 5. `jd_change_read`

此工具只有兩種讀法：

1. 使用 App 已發配的 change reference，讀一次實際操作的 exact base／result、origin、actual changes、保存結果及可展開 source references；
2. 使用兩個 App 已發配、同文件的 revision references，讀明示前版與後版的實際差異；結果必須標為版本比較，不稱為單次 AI 修改。

資料較長時，App 發出的 `continuation_ref` 只能續讀上述同一 change 或同一 before／after pair；後續頁不換基底、不取得寫入能力。完整前後內容可分頁讀完，不只供應 `affected_element_ids` 指到的片段。

返回的比較以完整 immutable before／after 為必要輸入，原生 operations 不是人工保存或任意兩版比較的前置條件。使用同 profile renderer 在原畫面唯讀展開確切前後內容與支持的格式／屬性；有已保存且 JSON-safe 的原生 operations 時，才加精細變動提示。`computeDiff` 有已知漏空格式／屬性的反例，不能依它算出的 affected blocks 作唯一可查範圍。沒有可靠高亮時保留完整前後可讀，不捏造受影響範圍或補造操作。LLM 自述「我只改了 X」不是證據。刪除內容只在比較中，不混回 current；本工具無寫入、還原、核准或切換 head 的效力。

人工full-value保存的`native_operations=null`、`affected_element_ids=[]`表示沒有可靠baseline定位材料，不能當「沒有變更」。是否有保存變更以committed／前後revision與完整快照判定；candidate normalization只從人工候選起算，不轉稱baseline→manual的操作或範圍。人工committed即使無定位仍計入跨輪事件；AI transform已捕捉的真操作則須回報其可支持的受影響內容，不能回未變的全文件。

## 6. 結果與錯誤契約

結果帶 `status`、已存在的 operation／change reference（若有）、base revision、result revision（若有）、`document_effect`、`receipt_durability`、App 產生的 `actual_changes`（若有）、有界 error detail 與下一個允許動作。`document_effect` 只取 `unchanged`／`committed`／`unknown`；`receipt_durability` 只表示 terminal receipt 是否為 `confirmed`／`unconfirmed`，兩者不得合併。schema／參數預檢若發生在 operation binding 前，沒有 `operation_ref`，但仍可確定 `document_effect=unchanged`、`receipt_durability=unconfirmed`。這些是語意欄位；正式名稱由跨語言 JSON Schema 定稿。

| status | `document_effect` | receipt 條件 | ToolMessage／下一步 |
|---|---|---|---|
| `committed` | `committed` | `confirmed`；新 revision、head 與 receipt 已原子保存 | success；依 actual changes 續談，不重送 |
| `no_change` | `unchanged` | `confirmed`；已對帳本次操作但沒有新文件 revision | success；不得宣稱改了不存在的內容 |
| `invalid_input` | `unchanged` | binding 前為 `unconfirmed`、無 operation ref；binding 後若形成 terminal receipt 則為 `confirmed` | error；在有界工具額度內修正新 call |
| `unsupported_content` | `unchanged` | 已有 operation 時保存 immutable terminal receipt；否則 `unconfirmed` | error；改用支持操作或保留原文，不刪資料求過測 |
| `target_missing` | `unchanged` | 已有 operation 時保存 immutable terminal receipt | error；重讀 current 後以新 call 規劃 |
| `stale_base` | `unchanged` | 已有 operation 時保存 immutable terminal receipt | error；重讀 current，不盲重播舊位置／command |
| `engine_failed` | `unchanged` | 已有 operation 時保存 immutable terminal receipt；disposable editor 的部分操作不算文件效果 | error；丟棄候選，回失敗 command index／原因；不稱 Plate rollback |
| `save_failed` | `unchanged` | 保存層已確認 transaction 未發布；terminal receipt 是否另行持久確認須據實填寫 | error；由 runtime 處理基礎設施恢復，不叫模型改文字修 DB |
| `outcome_unknown` | `unknown` | `unconfirmed`；commit／receipt 結果尚不能證明 | error／run uncertain；先以同一 operation 對帳，禁止模型重送 |
| `operation_conflict` | `unchanged`（僅指本次衝突 payload 未生效，不判定原操作效果） | 原 receipt 已確認才為 `confirmed`；僅有 binding 且原操作仍未閉合則 `unconfirmed`。原綁定／結果保持原樣 | error；返回已有的原結果 reference，尚未閉合則由 runtime 對帳；拒絕同鍵不同 payload |
| `busy` | `unchanged` | admission 前未發配 operation 時為 `unconfirmed` | error；等既有保存／對帳完成，不吞人工輸入 |

`save_failed` 只能在 rollback／未提交已被權威保存層確認時使用；已知文件未變，不等於 failure receipt 已保存，兩欄須各自據實回報。operation 已發配後產生且成功保存的 terminal failure 也是 immutable result，同 digest 重播必須返回它。commit 嘗試後斷線、receipt 查詢失敗或程序中斷，且無法確定是否已提交時，才是 `outcome_unknown`；不能將已證明未發布的錯誤改報未知。由於正式文件發布是整批 transaction，本契約不提供 `partial_committed`；被丟棄的 disposable editor 中途變化均不算文件效果。原生執行故障是 `engine_failed`，已知候選結構／關係違規是 `invalid_input`，兩者皆為 `document_effect=unchanged`。

錯誤是否可由模型修正與是否可安全重試分開：參數／過期引用可在重讀後形成**新的** call；unknown 只可對帳原 operation。連續無效 JSON、重複無進展或超過工具／模型額度沿既有 runtime 有界停止，不新增修補 Agent。

v2 的錯 kind、重複 link、非 Task 設 links、非法群組及仍被引用的刪除屬 `invalid_input`；有界 error code／message 指明原因，再按既有動作矩陣修正。受影響 Tasks 沿 `jd_read` 查，不把稍後變動的 current 投影塞進 immutable receipt；若原保存基底已有失效關係則停止並交 App 處理。細則見[語意契約 §5](evidence/2026-09-10-jd-semantic-contract-closure.md#5-錯誤及保存契約)。

### 6.1 狀態與下一步的封閉關係

**優先規則：**operation 已綁定但 receipt 未確認時，`next_action=reconcile_operation`。即使文件效果已知 unchanged，也先閉合原 operation，不能讓模型新建替代操作。這不把已知未變改報 unknown。busy 一律發生於 binding 前、operation_ref 為 null；operation_conflict 必帶原 operation，confirmed 時停止該衝突輸入，unconfirmed 時先對帳原操作。

已閉合或尚未 binding 的結果才使用下表。保存的 next_action 是該終局結果的處置類別，不因後來額度／取消而改寫 immutable receipt；當下是否仍可繼續由 runtime 另行限制。

| status | 允許 next_action | 誰處理 |
|---|---|---|
| committed／no_change | continue | 模型據真實結果續談；no_change 不聲稱改稿 |
| invalid_input／unsupported_content | correct_arguments 或 stop | 模型在額度內改合法輸入；不可修時停止 |
| target_missing／stale_base | reread_current 或 stop | 模型重讀再規劃；不硬套舊位置 |
| engine_failed／save_failed／已確認的 operation_conflict | stop | App 處理程序／保存／原操作；不請模型改文字修故障 |
| busy | wait 或 stop | App 保留輸入並等待既有工作閉合；不是模型循環工具 |
| outcome_unknown | reconcile_operation | App 核同一操作；只讀、保留恢復入口 |

人工保存共用結果格式，但不要求員工修 JSON；App 映射為可理解的保存錯誤並保留候選。wait／stop／reconcile_operation 不增加模型工具。所有 confirmed receipt 必須有 operation；確定失敗的 result／change refs 為 null，只有 conflict projection 可引用原結果而不冒稱本次改動；unknown 不推測 result／change refs。no_change 的 before／after 均為 base、affected IDs 為空、native_operations 為 null，不發布候選中淨零的暫時操作。

### 6.2 唯讀失敗與有限執行策略

`jd_read`／`jd_change_read` 共用 `JdReadFailure`：invalid_input→correct_arguments 或 stop；target_missing→reread_current 或 stop；busy→wait 或 stop；unsupported_content／新增 read_failed→stop。read_failed 表示 DB、解碼或唯讀引擎等執行失敗，不代表文件不存在；它不建立 operation。Node 的內部 `ok:false` 仍是內部結果，由 App 映射到這個工具出口，不將 Node 回覆直接當已保存或模型可讀成功。

v2 沿用既有執行策略：各明示 Node 執行、SQL 發布交易、必要失敗回執記錄及 receipt 查詢均最多一次 attempt，零自動重播；provider HTTP 沿既有 SDK，沒有外層整個 Agent／ToolNode retry。明確恢復／重開觸發新一輪對帳，查不到仍保留原 operation，不能推定未執行。控制預算沿[唯一 ER03 策略](evidence/2026-09-10-jd-error-recovery-contract-closure.md)：Node 30 秒及停止／回收 5＋5 秒、單個 SQL 階段總 30 秒，沿既有 connect 5／statement 10／lock 5 秒並依剩餘時間收斂；這是本案可配置起始值，不是大廠規定。取消／超時仍須確認程序停止及交易結果；到期不等於 rollback 已完成。

保存確認的查詢額度耗盡時，UI 結束無限 spinner、明示仍待確認並可恢復／重試確認，保留只讀和原輸入；有未閉合 operation 時不開新 writer。已確認失敗、writer 停止且必要回執閉合後，依既有流程恢復手編。背景 Memory 不延長 JD gate。

## 7. Tool call、operation 與重播

### 7.1 現行 runtime 可直接沿用

隔離版已有以下正式接點：

- [`runtime.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/runtime.py) 以 `create_agent` 注入 tools／middleware／checkpointer；不需換主 Agent。
- [`conversation.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py) 在 ToolNode 前保存完成的 model response，限制每次 model response 至多一個 tool call；無效 JSON 以相同 tool call ID 回 error ToolMessage，兩次後停止；root 以 `input=None`、`durability="sync"` 接續既有 checkpoint。
- [`service.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/service.py) 已有 document→thread scope、run admission、停止邊界及 uncertain／interrupted 狀態。
- [`live_memory.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py) 證明 middleware 可在 tool 執行前把 document、input、AI message 與 tool call 綁成 checkpointed operation identity；[`publication.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/publication.py) 證明 request digest、expected revision、receipt-first、CAS 與 uncertain reconcile 的限定模式。

這些只證明機制可沿用，不表示 JD tool／document storage 已存在。Memory 的 state 欄位、publication rows、source cursor 或 repair allow-list 不能照抄成 JD schema。

### 7.2 JD 必須新增的 App 接線

1. `jd_edit` 的 AI message 完成且 tool call identity 有效後，JD middleware 在 ToolNode 前建立並 checkpoint 一個穩定 binding：目前 document、已保存 employee input、AI message、tool call、operation。operation 不由模型提供，也不能只用 `tool_call_id` 當全域去重鍵。
2. 綁定後的 exact request 形成 digest；document、base、commands、source refs 與 engine profile 任一改變，都不得沿用同一 operation。
3. 同 operation 重播先向 JD storage 查 receipt。digest 相同且已有任何 immutable terminal result（成功、no-change 或確定失敗）時返回原結果，不再執行；digest 不同返回 `operation_conflict`，保留原 receipt／結果且不以新 payload 覆寫。
4. 程序在 commit 後、ToolMessage 前中斷時，checkpointed binding 仍存在。恢復流程先以同 operation 查 receipt，找到後用原 tool call ID 形成對應結果，再讓既有 Agent loop 接續。
5. 查不到 receipt 不等於沒執行。只有 storage ownership 契約能證明原 transaction 未提交或允許以**同 operation、同 digest**受控重試時才可重入；否則 run 保持 uncertain，不能配置新 operation 或叫模型重寫。
6. `input=None` 只表示接續既有 checkpoint；它本身不授權任意 JD write replay。現行 `resumable_repair` 只涵蓋已知 Memory C workflow；JD 必須有自己的 binding／receipt reconcile 條件，不能加入泛用「所有未知工具重跑」白名單。
7. 停止或關閉時，只對**已發配 JD operation 且結果尚未閉合**的 `jd_edit` 逐一處理：先停止並確認 worker 已不再執行該工具；再以 checkpointed binding 的同一 operation 唯讀查 JD receipt；只在缺少匹配結果時，依真實 terminal／known-none 結果補上使用原 `tool_call_id` 的 ToolMessage，已有匹配 ToolMessage 不重複。所有這類 operation 閉合並完成 turn closure 後才解除 JD writer gate。若仍是 unknown，就保留 run uncertain 及 writer gate，不可補造失敗 ToolMessage、重新寫稿或先解鎖。沒有 JD operation 的純訪談 turn 沿既有流程結束，不等待不存在的 receipt。

現行 [`conversation.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py) 的關閉分支只會對「確認尚未開始」、純 Memory notification、已辨識 read，以及 `repair_memory` 作特殊處理；其他未配對 write 會丟 `PublicationUncertain`。因此它**不會自然涵蓋 `jd_edit`**。正式接線須以 factory-bound JD tool identity 及 checkpointed binding 加入上述 JD reconcile 分支；不能只比對一個可被替換的工具名稱，也不能把所有未知工具一律當 JD write。

Composition root 必須保留三個 JD 工具名稱，注入唯一 factory-built instances，發現 middleware／caller 提供同名替代就 fail closed。關閉 turn 時，只有這兩個已綁定的 `jd_read`／`jd_change_read` 可按 read-only 結果遺失處理；這表示丟棄未收到的讀取結果，不表示內容不存在。`jd_edit` 必須走前述 receipt reconcile，不能套 read 規則。

read 工具沒有文件寫入副作用，但其歷史／target references 仍固定到已讀 revision。恢復後 current head 已變時，舊讀取結果可以作歷史資料，不能偷偷升格成新寫入基底。

## 8. Source reference 與更正 lineage

JD 不建立第二份來源庫。現行 [`sources.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/sources.py) 的 `conversation:` reference 已綁 document、checkpoint、first／last message，並以實際 Saver snapshot 驗文件歸屬、checkpoint 與完整 range；歷史 extraction window 另要求 completed／safely closed turns，同 run 則可由 runtime `capture_input` 發出已保存的最新員工輸入範圍。後者不必等本輪 final 或背景 Memory publication，符合 MEM-Q005 的同 run 邊界。[`memory_tools.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory_tools.py) 已能把 interview summary path 解到其保存的 source／context window。JD App 應直接透過這些 owner 解析既有 read result 發出的 reference，不另寫通用來源定位器，也不複製逐字內容到 JD。

保存前的機械檢查只能證明：引用存在、屬同文件、指向確切已保存可見問答範圍，且未把 ToolMessage、opaque reasoning 或 runtime notice 當員工原話。它**不能**證明該來源語意支持每個 JD 句子，也不能只靠 reference 判斷後來的更正是否已取代舊說法。

current understanding、歷史詳記及更正 lineage 仍由既有 Memory／conversation owner 管。主顧問依目前理解、必要原文與新更正決定是否改稿；明確矛盾不足時追問。人工或 AI 改了帶引用的 JD block 後，原 reference 可以保留供回查，但 App 不自動把它標為「重新核實」。change origin、source existence 與專業／事實驗收是三件事。

引用用途的釐清見[研究 §4](2026-09-10-jd-context-change-and-source-research.md#4-jd-是否要引用-memory)：Memory 是版本化理解與查找入口，裸 `/memory/knowledge.md` 不作 JD 永久原始證據；既有訪談詳記沿 owner 解回確切 conversation window。`Memory version＋path` 作獨立 durable locator 尚未定義，不冒稱已有。人工新文字若沒有訪談來源，保留人工修改證據，不偽造訪談引用；正文不要求每句腳註，也不為此新增 citation Agent、RAG 或 provider 依賴。

## 9. 有限驗收

正式施工前的設計 review 及其後整合驗收只需覆蓋下列固定契約，不再重跑 pending／codec 群組實驗：

1. **Current／history／selection：**同一畫面 current 可編，歷史唯讀展開；selection ref 只來自 App 真實選取。歷史／跨文件／編造 ref 寫入均零影響。
2. **完整 r2 編輯：**用明列內容對應的新 v2 fixture 驗正式 profile，不把封存 v1 原值當 v2。有限 command 保留 Task4／8 的適用條件、格式、ID、來源引用及未指定內容，並核兩個必需群組、共享 K／S、兩階段首建及刪除影響；normalization 產生的實際改動完整回報。當次有限結果見語意契約，不代稱全部正式接線通過。
3. **原子發布：**多 command 第 N 步失敗時正式文件、head 與 change 均不變；成功時 revision、head、receipt、actual changes 同成同敗；no-change 無新 revision。
4. **過期與人工競爭：**模型讀後人工先保存，原 `jd_edit` 回 stale，不能覆蓋；run admission 前先完成並確認人工 dirty buffer 保存，再取得同文件 JD writer gate。AI 執行期間 API 也拒絕人工保存；停止／失敗後只對已發配且未閉合的 JD operations 依同 operation 對帳，只補缺失的匹配 ToolMessage，關閉 turn 後才解鎖。無 JD operation 的純訪談不等 receipt；背景 Memory 不寫 JD，不能持有或延長這個 gate。
5. **來源：**有效同文件來源可展開；同 run 已保存 current input 可用，歷史窗口仍須 completed／safely closed。跨文件、缺失 checkpoint、不符合該 reference 類型 closure 規則，或把工具輸出當原話均拒絕。人工修改不造成假的 reverified 狀態。
6. **回覆遺失：**commit 後中斷且無 ToolMessage，新程序由 checkpointed binding＋同 operation receipt 找回 committed 結果，不再次插入；同 operation 不同 digest 拒絕。
7. **錯誤與停止：**invalid JSON 不執行；target／schema 錯誤可由同模型在額度內重讀修正；save unknown 先對帳並停止模型重送；所有結果與 UI 的已保存狀態一致。
8. **端到端語意：**用未參與調整的新職位，驗證理解足夠才改稿、員工指出錯誤後 AI 讀最新版修正、完整變更可查、獨立內容未誤動、相依內容一致及來源可回查。工具成功不代替 JD 專業內容驗收。

## 10. 施工驗收與正式化邊界

- [App 接線設計 §5.4](2026-09-09-jd-editor-app-integration-design.md#54-保存資料的具體約束)已固定 JD head／revision／operation／change 的有限保存約束；[Proposed ADR 0073](../adr/0073-plate-jd-app-working-document-and-revision-authority.md)已指定 JD App 為唯一文件 owner 與舊 JD authority 的取代範圍。仍須完成正式 schema review、接受 ADR 與 implementation gate；不再把 durable owner 當成空白選項。
- v1 核心總審保留歷史效力；本次[語意契約 v2](evidence/2026-09-10-jd-semantic-contract-closure.md)同步[正式 Plate profile](2026-09-10-jd-plate-document-profile.md)、[JSON Schema](2026-09-10-jd-editor-contract-schema.md)與[六切片計畫](../plans/2026-09-10-jd-editor-core-implementation.md)，完成有限閉合後恢復 Task 1。[整體評審包](2026-09-09-jd-editor-app-integration-design.md#91-整體接線評審包)的核心產品取捨已同意、真人交付 PARKED；不重問或重選框架。
- Owner 採用持續工作稿不會自行改寫既有 production authority；Proposed ADR 0073 已明列 0060／0064／0066／0067／0069 的 JD 專屬取代範圍，production 須在其 Accepted 並通過 implementation gate 後才可切換；隔離施工依六切片及 register 已同意範圍。
- S5 核心設計／隔離施工交接已完成，效力限可驗證設計與計畫。本稿沒有證明 DOM／IME、完整 Agent binding、真 provider 接受、真模型 JD 品質或 production 整合已通過。

## 11. 證據與效力

- [語意契約 v2](evidence/2026-09-10-jd-semantic-contract-closure.md)：新 grammar、同版 K／S、模型／App 映射、首建及有限驗證的唯一詳細入口；舊 v1 證據不改。
- [JD App 接線設計](2026-09-09-jd-editor-app-integration-design.md)：三工具、Plate headless、結果梯、single-writer 與保存候選。
- [App／工具／審閱官方證據](evidence/2026-09-09-jd-app-tool-and-review-contracts.md)：OpenAI／Anthropic call-result 關聯、Google revision／atomic batch、失敗與 unknown 邊界，以及既有 runtime 對照。
- [審閱生命週期裁決](2026-09-09-jd-editing-and-review-working-design.md#77-owner-裁決持續工作稿保留差異與更正)：B 路線、被取代的 pending 操作要求與仍保留效果。
- 隔離 runtime source：[`runtime.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/runtime.py)、[`conversation.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py)、[`service.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/service.py)、[`live_memory.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py)、[`sources.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/sources.py)、[`publication.py`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/publication.py)。這些證明可重用機制與責任界線，不是 JD 已實作證據。
