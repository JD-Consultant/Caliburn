# JD clean Plate document profile

**2026-09-10 active語意契約v2：**Owner已同意Task成果／要求平行分組、K／S引用及原生JSONB＋同PG保存方向。[語意契約與有限驗證](evidence/2026-09-10-jd-semantic-contract-closure.md)固定新grammar、模型refs／保存IDs及首次建立；本文件active設計已同步v2。v1及F01／F02的實測紀錄保留其舊範圍，不能代稱新增關係已完成runtime驗收。

前次格式確認及v1無共享引用的診斷見[保存研究](evidence/2026-09-10-jd-semantic-relations-storage-audit.md)；已由v2具體補正，不再等待同一產品決定。尚未完成的原生／DB／DOM／真模型項目仍依六切片逐項驗收。

JD-R002/C03；2026-09-10；**可實作設計附件，待 successor ADR 與整合驗收後施工。**依 [current register](../current-decisions.md)、[決策流程](../decision-process.md)、[接線設計 §2](2026-09-09-jd-editor-app-integration-design.md#2-文件格式業務內容在文件中讀得到)及 [Owner 持續工作稿裁決](2026-09-09-jd-editing-and-review-working-design.md#77-owner-裁決持續工作稿保留差異與更正)。本附件收斂文件表示與原生接點，不重開框架／審閱選擇，不改 Memory、工具契約、保存 authority 或現行 production。

**設計採用：**一份 clean Plate working value；每次成功保存形成不可變 revision，留下實際改動及前後內容。員工在同一工作畫面聊天、看同一份可編 JD，也能在當畫面看實際差異；歷史可展開唯讀，不是第二份可編稿。沒有 pending 群組、逐筆接受／取消或 accepted projection。工作稿保存不代表工作事實或專業品質已獲核准。

本文以 **D（設計選擇）／E（既有實證）／S（固定官方 source）／V（整合須驗）** 區分效力。**後續 F02 已完成：**[官方插件四組實證](evidence/2026-09-10-jd-official-profile-probe.md)第二輪 4／4、15 項斷言通過，首輪子程序缺檔的 1／3 保留；有新的獨立 lock／實裝 source／授權封存。下列原生能力可據此補強，但仍不是全 grammar、DOM／IME、來源或產品驗收。本文初稿只有唯讀設計，新增實驗的完整範圍由 F02 報告負責。

## 1. 固定引擎與官方插件

**D：**active profile採`jd-plate-clean-v2`，對應`format_version:2`及[語意契約v2](evidence/2026-09-10-jd-semantic-contract-closure.md)。v1固定證據保持歷史效力；新Task兩組及K／S引用不是v1已支援功能，不把舊fixture直接冒充v2。套件版本不變，無production migration或相容讀取。完整依賴lock與配置跟識別一起固定，不用npm latest隱性換引擎。

| 用途 | 固定版本／接點 | 證據與邊界 |
|---|---|---|
| 核心／執行環境 | `platejs@53.3.11`；鎖內 `@platejs/core@53.3.11`、`@platejs/slate@53.3.10`、`slate@0.126.2`；Node `22.12.0`；React／React DOM `19.2.4` | E：既有 native、history、F01、UI 的固定環境；核心／Slate／React 為 MIT。repo release `v53.3.12` 不是核心 npm 版號 |
| 原生差異 | `@platejs/diff@53.0.0` 的 `computeDiff` | E：保留兩個失敗；LICENSE 的原衍生碼 Apache-2.0、修改部分 Apache-2.0／MIT 雙授權；不能僅以缺少 package license 欄位判非 OSS |
| 標題／引言／分隔線／格式 | `@platejs/basic-nodes@53.0.0` | S：MIT、正式 npm 版；使用各 `Base*Plugin` 與 `/react` 對應插件；未在既有 F01 安裝／整合 |
| 真正巢狀清單 | `@platejs/list-classic@53.0.0`；headless `BaseListPlugin`，Web `ListPlugin` | S：MIT；原生 list transforms、normalizers 與 React 接點。選 classic 是為真正巢狀結構；不另建 indentation／list engine |
| 表格 | `@platejs/table@53.0.9`；headless `BaseTablePlugin`，Web `TablePlugin` | S：MIT；官方建立／增刪行列／合併／拆格及鍵盤接點。相依 `@platejs/resizable@53.0.0`；E：F02 固定官方增刪一列通過，其餘操作未驗 |
| JD 語意容器 | `jd_section`／`jd_duty`／`jd_task`及v2的`jd_outcomes`／`jd_requirements`／`jd_knowledge`／`jd_skill`，`createSlatePlugin`／對應React plugin | F01只驗前三種；新容器證據見語意契約。維持普通`node.isElement:true` block，不設void／isContainer、不自訂工作內容normalizer |

**D：**保留 core 的 paragraph、history、NodeId 等預設插件；標題使用 `BaseHeadingPlugin`／`HeadingPlugin`，`levels:[1,2,3]`；另接官方 blockquote、horizontal rule、bold、italic、underline、strikethrough 插件。headless 用 `createSlateEditor`，Web 用 `createPlateEditor` 與 React 對應插件，兩端的節點 key、normalization 與 ID 配置一致。React 事件／render 層差異不等於另一套文件 schema。

**S／E：**list-classic／basic-nodes 的 npm gitHead 為 `7b9b204e1e38a20b1f8bec5a900d67c64afbc525`，table 為 `79578fd8ef53237edfc78389594df3ed5c722277`；各 package 版號、MIT 及 peer 範圍於 2026-09-10 核對。F02 的[獨立 lock](evidence/jd-official-profile-probe/package-lock.json)及[48 項授權盤點](evidence/jd-official-profile-probe/license-inventory.json)補齊新組合：40 項實裝附授權，8 項另取固定 gitHead 官方授權，來源分列。實際 headless 四組通過，不等於全部 React／人工功能通過；沒有改 production lock，也不用舊 44 項 inventory 代稱新增插件已核。

**E／V：**F01 的 `ul/li/table/tr/td/th` 是普通 element 註冊；UI 也只有有限 renderer，並非官方 list/table kit。本設計選用官方插件後，不再把這些普通註冊覆蓋同 key。官方網站的 `ListKit`／表格 UI 是可參考的原始碼組裝，不是本案已安裝或可直接 import 的虛構套件；不得宣稱存在 `@platejs/diff` 匯出的 `DiffKit`。人工清單、表格能力由官方插件承擔，本案只接命令、有限樣式與顯示。

## 2. 文件 grammar 與完整 JD

**D：**權威 value 是非空 `Element[]`。以下 `+` 表示至少一個、`*` 可空、`|` 表示擇一；次序有意義，不能為整理格式自行排序。名稱／節數／任務數不固定；[完整 r2](2026-09-09-frontend-engineer-jd-sample.md)是內容驗收樣本，不是每份文件模板。

```text
document   = (body | jd_section)+
body       = p | h1 | h2 | h3 | blockquote | ul | ol | table | hr
jd_section = body+                              # 非 work/knowledge/skills 用途
           | (body | jd_duty | jd_task)+          # section_kind = work
           | (body | jd_knowledge)+              # section_kind = knowledge
           | (body | jd_skill)+                  # section_kind = skills
jd_duty    = (body | jd_task)+
jd_task    = (body | jd_outcomes | jd_requirements)+
             # 至少1 body，恰1 jd_outcomes、恰1 jd_requirements
jd_outcomes = body+
jd_requirements = body+
jd_knowledge = body+
jd_skill    = body+
p/h1/h2/h3 = Text+
blockquote = (p | h1 | h2 | h3 | ul | ol | table | hr)+
ul/ol      = li+
li         = lic (ul | ol)*
lic        = Text+
table      = tr+
tr         = (td | th)+
td/th      = (p | ul | ol)+
hr         = [{ text: '' }]                     # 官方 void 的必要文字 child
```

`section_kind` 採有限用途 `identity | purpose | work | knowledge | skills | conditions | other`；`other` 的實際含義由可讀標題／內文說明。這是 D，F01 只使用其中六種，沒有測 `other`。不要求每種用途都存在，也不把用途相同的 section 合併；缺少資料不以造字填滿。Duty／Task 必須位於工作 section；Task 可以直接屬於工作 section，未分類工作不必虛構 Duty。語意容器不互相任意嵌套，Duty 不含 Duty、Task 不含 Task。

**S／D：**官方 classic list 的內容節點是 `lic`；F01 的 `li→p` 不能原封不動稱為正式 canonical grammar。`normalizeListItem` 會把首個非清單、非 `lic` block 轉成 `lic`，也可能移動不合法 children。正式建稿直接產生 `ul/ol→li→lic`，r2 子清單留在同一 `li` 的 `lic` 之後；不自訂 list normalizer 去保住 probe 舊形狀。不啟用會另寫任務狀態的 `taskList`／checkbox UI；官方父插件即使註冊該型別，App profile 仍拒絕把它當 JD Task。這不影響 JD 工作事實與進度應由既有顧問 state 承擔的邊界。

一般表格仍使用官方cell factory／transforms、th／td及巢狀段落／清單，grid由官方行為處理，不重寫merge引擎。F02的v1三張表實證保留；v2完整樣稿fixture把K／S兩張表的每列明示換成完整item，文字／marks保留，退役外框ID記在[固定映射](evidence/jd-semantic-native-probe/fixture-mapping.json)，現存1張基本資料表。這是新增語意表示的固定fixture調整，不是通用importer，也不宣稱原版面不變。表格編輯及差異仍須按正式插件驗收，不能因樣稿表數減少就刪除表格能力。

**S／D：**已核對 `basic-nodes@53.0.0` npm gitHead 的 [BaseBlockquotePlugin](https://github.com/udecode/plate/blob/7b9b204e1e38a20b1f8bec5a900d67c64afbc525/packages/basic-nodes/src/lib/BaseBlockquotePlugin.ts)：其 `toggle` 使用 `toggleBlock(type,{wrap:true})`，normalizer 將直接 Text／inline 包入 `p`、保留既有 block children；不是只改 p 的 type 並永久留下直接 Text。故本 grammar 使用 block children，並允許本 profile 的一般 body blocks，避免只准 `p` 擋住官方包裹清單／表格。引言命令只作用於 body，不包住整個 JD 語意容器；r2 的引言文字及分隔線完整保留。此為固定 source 核對，尚非新插件組合的執行正證。

Task名稱／敘述及其適用條件在一般body，成果與要求各在Task直屬的一個專屬群組內；可含多段、清單或表格，數量不配對、不互為父子、不合併回敘述。K／S各以完整item保存一次，Task引用該版ID。Task4三種異常處理要求、Task8約定服務月檢限制及未指定正文須全文保留。未知內容留空p或既有Memory，不造事實；固定容器不是必須每次訪談填滿內容。詳[語意契約§2–3](evidence/2026-09-10-jd-semantic-contract-closure.md#2-最小完整文件結構)。

## 3. 空白、未完整與允許欄位

**D：**整份空白用一個帶 ID 的 `p`，其中 `children:[{text:''}]`；不生成假 Task。已建立但尚未完整的容器至少有同樣的合法空 `p`，清單至少有 `li→lic→{text:''}`，空格至少有 `p→{text:''}`。允許只有已知事實的短內容、暫無標題、尚未歸屬的敘述；「不完整」不等於非法 grammar，亦不新增 `completed`／`approved` 欄位。

**E：**F01-D 的合法空 paragraph、無 Duty Task、未歸屬成果經 JSON 序列化／解析到新 editor 相等。`jd_task.children:[]` 則原生補成直接空 Text，沒有自動生成本 grammar 的 paragraph；不能把這種輸入交 normalization 猜修。F01-D 不是檔案／DB 保存測試。

**D：**clean value 僅容許以下有限 props。所有陣列／物件均須普通 JSON 值：不含 `undefined`、NaN、Infinity、BigInt、Date、Map、class、函式、循環或空洞陣列；node property 不存 `null`，省略可選欄位表示未設定。這是 clean 文件限制；原生 operations、`computeDiff` 的比較 metadata 與文件 value 是不同表示，不能因比較結果出現 `undefined` 就推定原生操作需要相同 codec。operations／實際變動材料依[主稿 §5.5](2026-09-09-jd-editor-app-integration-design.md#55-原生操作與比較投影的保存分界)。

| 位置 | 允許 props 與形狀 | 語意／限制 |
|---|---|---|
| 所有 Element | `type:string`（上述白名單）、`id:string`（非空）、`children`（上述 grammar） | 不以任意 `Record<string,unknown>` 放行 metadata |
| 所有 Element 的可選來源 | `source_refs:string[]` | App 發出的同文件來源 handle；不得塞逐字稿、模型判斷或替代 Memory。空陣列可用；內部 handle 格式／解析依既有 source owner 接線 |
| `jd_section` | 必需 `section_kind`（上述有限值） | 用途可供定位，顯示仍有正文；改用途不自動重分類子工作 |
| `jd_task` | 可選`knowledge_ids:string[]`／`skill_ids:string[]`，各有序且不重複 | 只存同版完整K／S項目ID；端點存在、種類及全文件ID唯一由App驗。模型只在set_properties選issued refs；反向清單不保存 |
| Text | `text:string`；可選 `bold/italic/underline/strikethrough:true` | 格式取消後省略 key；無 leaf ID、score、scope、source、approved 等業務 attrs。外部 `false` 或其他值不靜默改寫成相同語意 |
| `table` | 可選 `colSizes:number[]`、`marginLeft:number` | 有限、非負數；尺寸只負責版面，不承載工作事實；初始不自動設定 table width |
| `tr` | 可選 `size:number` | 有限、非負行高 |
| `td/th` | 可選 `colSpan/rowSpan`（正整數）、`size`（有限非負數）、`background:string`、`borders` | `borders` 僅 `top/right/bottom/left`；各邊可有 `size`（有限非負數）、`color:string`、`style:string`，值由有限 UI 選項與安全樣式解析器接受。無任意 DOM attributes |
| `td/th` 的原生 HTML span 表示 | 可選 `attributes:{colspan?:string,rowspan?:string}` | 只接受正整數字串，與 numeric span 同時存在時須相符。保留官方可產生的表示，禁止事件／任意 HTML props |

本表描述**保存稿**。模型 new-element／set_properties 只填 numeric colSpan／rowSpan，不接受 attributes；App／Node 用原生 setNodes／unsetNodes 同步或清除已存在的對應 HTML key，保留另一維，清空後移除 attributes 物件。新增省略 span 有效值 1，明填 1 保留；不是要求自動拆格。精確當批映射、例子及 table 53.0.9 原碼依[TF02 附件 §3](evidence/2026-09-10-jd-model-input-contract-closure.md#3-tf02單一-span-意圖與保存映射)。saved value／人工貼上仍驗本表所有合法表示；不能因縮小模型輸入而丟棄原生保存內容。

上述 table 欄位依固定 `@platejs/utils@53.3.11` 的 `TTableElement/TTableRowElement/TTableCellElement` 與官方 table source；不是宣稱這些欄位都已做 UI／JSON 整合實驗。移除或新增這些有限 props 也屬實際修改，不能僅顯示紅綠文字。

**D：**拒絕額外 `suggestion*`、`diff/diffOperation`、`_id`、選取／history／plugin options、任意 `attributes`、測試的 `score/approved/provenance/obsolete`。不得靠清掉未知必要資料讓驗證通過：回報哪個內容／格式不受本 profile 支援，保留原輸入與舊 revision；如有新必要能力再明確升版。外部貼上先沿官方 parser 產生候選，通過 profile 才納入；不能靜默丟掉有意義內容，也不自行建立通用 importer。

空 Text 的有效 marks 保留；游標 active marks 是 editor session state，不是持久 leaf。兩者不得混為一談，也不能為避開 diff 反例清除空 leaf 格式。

## 4. 身分、移動、拆分、複製與引用

v2另外驗同版Task→K／S關係。NodeId不負責links；App只在明示copy時以該次舊→新ID映射重寫複本內連線。含必需兩組的Task不能單獨unwrap後發布；須同批明示unwrap兩組再unwrap Task。刪／unwrap被引用K／S或其祖先須先解除／改接incoming links。完整候選在批次末驗grammar／links，中間暫態不得當成已保存正文；具體copy／刪除規則以[語意契約§3](evidence/2026-09-10-jd-semantic-contract-closure.md#3-共同編輯與引用邊界)為準。

**D／S：**寫入 editor 的 NodeId 固定 `reuseId:true, initialValueIds:'always'`；其餘沿原生 `idKey:'id'`、`filterText:true`、`filterInline:true`、預設 `idCreator:()=>nanoid(10)`。不採 F01／history probe 每次重置的測試 ID 序列。所有可定位 block（包括行、格、list item／lic）都有 ID；文字位置由當前 tree 的原生 API 解析，模型不計算 path／offset。App 定位同時限定 document、revision、ID，重複或不存在都回錯，不能 first-match。

`initialValueIds:'always'` 是走訪補缺 ID，**不是保證修好重複 ID**；有 ID 的已保存 canonical revision 在建立 editor 前就要驗唯一。只有新建內容允許先缺 ID，交原生補齊後再驗證。從保存載入缺 ID 視為 profile 不符，不當背景修復。`reuseId:true` 可保留尚未被使用的 ID，故不能拿它當跨文件複製隔離；目的文件隔離與複製入口仍是 App 責任。

| 使用者意圖 | D：有限原生接線與身分規則 | E／V |
|---|---|---|
| 改字、改名、移 Task／Duty | 原生 text／setNodes／moveNodes；同一內容保持 ID 與完整 subtree，移動不套入新父的工作條件 | F01-B 固定 Task8 移動保留 ID／全文／引用；沒有 DOM 拖放或任意父條件實測 |
| 普通 Enter／段落 split | 官方 block／list／table 行為；在 Task 內換段落仍是同一 Task，新段由 NodeId 配新 ID | F01-E 普通 p insertBreak 正證，不證官方 list/table 組合或 DOM／IME |
| 明確拆成兩項工作 | 命令須有完整兩項內容與條件配置；延續原工作者保留原 Task ID，新增者新 ID；無延續者則兩者新 ID | 不以 Enter 猜語意，不建 lineage／dependency engine；正式資料流及 UI 尚須驗 |
| 合併工作／取消 Duty 分組 | 明示 survivor 與完整內容後用原生 transforms；unwrap 只取消容器、保留子內容；delete 明示刪除 subtree | F01-C 固定 unwrap 保留標題／兩 Task；不把 source IDs 或相似文字當自動合併判據 |
| 複製／外部貼上 | 複本所有 Element 都取新 ID。App 可在明示「複製」入口移除輸入 IDs，交原生 NodeId 生成；原始 revision 不改 | F01-F 只驗同文件已解析 fragment 的重複 ID 處理；沒驗外部 clipboard／跨文件。不能依賴 reuseId 自動換掉外來唯一 ID |
| 刪除工作 | 原生刪除明示 subtree，保留該 revision 的真實前後內容；不自動連帶刪別处知識／技能 | 不提供任意已接受歷史的一鍵局部回退；更正由新操作形成新 revision |

**D：**source refs 是「這段工作曾參考哪些既有來源」的引用，不是每一句都已被證實。移動保留 refs；同文件複製可保留真實相同依據，但不表示複本已核對。跨文件 ID／refs 不直接取得目的文件 authority，來源無法在目的文件解析即回報，不造新 provenance 內容。人工或 AI 續改後舊引用不自動替新文字背書；增加／刪除引用是 App 驗證後的明示變動，並可看引用前後。既有 source owner 與 correction lineage 不搬進文件。

**E：**H09 以不同 ID 產生流，固定 split／同步／undo／redo 仍相等，支持上述配置；不能外推所有新插件都安全。session undo／redo 只沿原生 history；重開不復活 undo stack。不以 `withoutSaving(setValue)` 保舊 history，同步／批次互斥／保存交易依接線設計，不在本附件另造 history 或 rebase。

## 5. Normalization 與失敗責任

**D：**每次外部／模型候選先驗 JSON 值、欄位、基本 grammar、來源與 ID；對可修改的輸入做獨立 clone，再交同 profile 原生 transforms。在拋棄式候選 editor 內完成原生 normalization，收集其真實 operations；之後驗 canonical grammar／ID／props，再交保存流程。正式 current 只從成功保存的 canonical revision 更新。這是有限 profile 檢查及 App 提交流程，不是自製 normalization、diff 或 rollback 引擎。

原生 normalizer 可改資料，不是無副作用 validator；完整官方 list/table normalizers 啟用後的效果必須納入那次真實改動。App 不以自訂 normalizer 改 Task 的範圍、將任意段落升為 Task、補工作事實或靜默丟棄非法節點。無法通過時回報，不把部分候選當正式稿；live 人編的批次／暫態 grammar 與失敗回復由人工接線驗收，不允許每打一字就用自製重寫規則整理全文。

**E：**F01-A force normalize 只移除 Task4 粗體 label 後多出的空無格式 leaf；原始 JSON 精確相等仍 **FAIL**，其 canonical clean value 檔案→新 editor→再 normalize 全等。這支持保存 canonical value，**不授權任意空 leaf／格式／工作內容被移除**。原報告 5 PASS／1 FAIL 不改判。官方 classic list 與 table 的新 normalization 組合尚未被該結果覆蓋。

保存重開要先比對 format／engine profile，再用新 editor 載入已驗 canonical value。若 normalize 仍造成未預期內容或 ID 變化，視為整合失敗，不背景升版、吞掉差異或默認接受。NodeId 傳入物件上的 `_id` 是暫態 wrapper 材料，不持久化；F01-D 測試 aliasing 修正不等於保存缺陷已被 codec 修好。

## 6. 同一工作畫面的 renderer 責任

**D：**current 只有一份可編 value。聊天與 JD 同畫面，成功寫入後立即更新，該次實際增、刪、改與所需前後內容可在當画面展開；不要求先換到另一頁或另一可編版本才知道 AI 改了什麼。唯讀歷史／比較共用相同 JD／body／格式／來源 renderer 規則，只增加原生 diff 樣式及有限變動說明。

- `jd_*` 容器渲染為可讀章節／工作區塊並正常傳遞 Slate attributes、children；不把整個任務設為不可編 void。標題仍是真實文字，scope／要求仍是真實內文；ID 不需要讓員工手填。
- v2成果／要求群組的固定名稱由type決定；空body可編輯但不補造文字。K／S全文与Task引用在current及同版readonly view使用同一解析；incoming Task清單由該版推導。變更顯示實際前後關係及共享影響，不能只看紅綠字。
- 用官方 list/table React plugins 與其 UI 接點處理人工操作；table DOM 要維持 `table→tbody→tr→td/th`，清單 `ul/ol→li`。不得對每個 row／cell 的 diff 強包一層 `div`。只讀 renderer 不執行會改動比較內容的編輯 normalizer。
- source refs 顯示可讀「依據」與實際來源內容；section 用途、table尺寸／span／背景／border 等本 profile 的有限機器欄位，變動時有可讀前後說明，不靠 JSON 面板代替員工視圖。F01 的 `fixture-source:*` 只是假資料標籤，不能進正式文件。
- 比較值與 clean value 分開；readonly comparison 可使用 `nodeId:false`，不拿它做命令定位或保存為 current。原生 diff 的同 ID 刪／增两份都要顯示，不按業務 ID 去重；React key 不能直接假定等於該業務 ID。
- **保留實際缺口：**leaf `score:1→0` 不在此 clean profile 內，原失敗仍有效；空 Text marks 仍在 profile 內，`computeDiff` 漏標記仍成立。當次及歷次已保存的原生 operation 可提供有限格式前後提示；只剩兩份任意快照時，不捏造缺失 operation，也不宣稱完整高亮已由本附件解決。不修改 `computeDiff` 或建通用比較補丁。

**E：**既有 UI 的完整 r2 前／後／diff 共九張表格、一個子清單、同 ID 刪／增正文及清除 session 重开已被 Node 與瀏覽器觀察；它使用普通 element renderer、不是本正式插件組合。Task3 合成 scope 曾只能在 JSON 看見，故本案不可用紅綠正文替所有必要欄位通過；也不把歷史研究的三欄探針畫面當正式三份稿 UX。

## 7. 有限整合通過條件

以下是施工時一次整合驗收的必要集合。F02 補上 P1／P4／P5 的固定 headless／JSON 正證，沒有完成整列驗收；不以微型案例無限擴張研究。失敗先定位官方接法／profile 契約；如需自製清單、表格、差異、排序或回退引擎才通過，回報具體缺口，不暗中擴建。

| 編號 | 必須肯定的結果 | 已有材料可重用；尚須完成 |
|---|---|---|
| P1 完整内容 | 官方插件下v2完整樣稿、Task4／8條件、基本資料表／子清單、成果／要求組及K／S全文都在，ID／links正確；同畫面current／必要前後可讀 | F01／F02的三表為v1基線；v2固定mapping及F03補原生證據，renderer及真實人工整合仍待Task 1／4 |
| P2 不完整／非法輸入 | 空文件、無 Duty Task、未完整敘述可保存；Task 套 Task、非法 parent、未知 props、無效來源／重複 ID 回明確錯誤，正式稿不受部分寫入污染 | F01-D 只覆蓋部分；不能把 normalization 改形狀稱為拒絕成功 |
| P3 真正人工編輯 | 繁中 IME、選取改字、段落 Enter／Backspace、巢狀清單縮排／取消、表格 cell 編輯及增刪行列、格式切換，本文與獨立工作不丟失；AI 後人改 undo／redo 邊界正確 | 官方接點有 source；既有 headless／唯讀 UI 不是 DOM 驗收。不要求自寫成熟套件已提供的鍵盤引擎 |
| P4 身分／引用 | 移 Task、unwrap、明示 split／copy 保留應保留的全文／引用，生成應新增的 ID；來源與正文差異可讀，跨文件來源不誤接 | F01-B/C/E/F 及 H09 只有固定操作正證；原生新組合與操作後真正 JSON／新 editor 重開須整合驗 |
| P5 持久工作稿／實際改動 | 成功保存 revision 的 canonical JSON 重開相等；current、當次差異、唯讀歷史同构呈現；同 ID 刪增不漏，空格式改動有真實保存材料與可讀提示；兩個原始反例原樣保留 | UI、native、保存實證可重用；DB／Python／工具與 authority 由另外接線及 ADR 承接。未保存的 transient operations 不冒稱歷史記錄 |

完成以上與主線工具／保存／人工接線驗收，才可稱正式 profile 整合通過；本附件已選具體接點，不再留下多框架候選問題。沒有許可新增登入、多租戶、雲端、多人協作或重做顧問 Memory。

## 8. 來源與核對日期

本輪新查只限官方固定版本／原碼；查閱日 **2026-09-10**。下列 npm 是指定版本 endpoint，不是 latest；registry gitHead 與既有 monorepo source commit 分列。官方 source 證明 API／預設行為存在，不等於本案 runtime 已驗。

| 來源 | Publisher／版本／授權 | 支持範圍 |
|---|---|---|
| [basic-nodes npm](https://registry.npmjs.org/@platejs/basic-nodes/53.0.0)、[Heading source](https://github.com/udecode/plate/blob/7b9b204e1e38a20b1f8bec5a900d67c64afbc525/packages/basic-nodes/src/lib/BaseHeadingPlugin.ts)、[HR source](https://github.com/udecode/plate/blob/7b9b204e1e38a20b1f8bec5a900d67c64afbc525/packages/basic-nodes/src/lib/BaseHorizontalRulePlugin.ts) | Plate／53.0.0／MIT；gitHead `7b9b204e…` | 版本、peer、levels、原生標題規則與 hr void |
| [list-classic npm](https://registry.npmjs.org/@platejs/list-classic/53.0.0)、[BaseListPlugin](https://github.com/udecode/plate/blob/7b9b204e1e38a20b1f8bec5a900d67c64afbc525/packages/list-classic/src/lib/BaseListPlugin.ts) | Plate／53.0.0／MIT；gitHead `7b9b204e…` | 原生 nested plugins／transforms；正式 profile 採用接點 |
| [list normalizer](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/list-classic/src/lib/normalizers/normalizeListItem.ts)、[React ListPlugin](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/list-classic/src/react/ListPlugin.tsx)、[官方 ListKit source](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/apps/www/src/registry/components/editor/plugins/list-classic-kit.tsx) | Plate／既有 release source commit `cee7a4ec…`；該 commit package 53.0.0／MIT | `lic` 正規化與 React 組裝；沒有聲稱本輪逐檔比對 npm dist 相同 |
| [table npm](https://registry.npmjs.org/@platejs/table/53.0.9)、[BaseTablePlugin](https://github.com/udecode/plate/blob/79578fd8ef53237edfc78389594df3ed5c722277/packages/table/src/lib/BaseTablePlugin.ts)、[resizable npm](https://registry.npmjs.org/@platejs/resizable/53.0.0) | Plate／table53.0.9、resizable53.0.0／MIT；table gitHead `79578fd8…` | 原生 table factory／transforms、span、選取 state 與相依；未核新安裝全部 transitive LICENSE |
| [React TablePlugin](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/table/src/react/TablePlugin.tsx)、[官方 table renderer](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/apps/www/src/registry/ui/table-node.tsx) | Plate／既有固定 source commit `cee7a4ec…` | React keydown 與官方欄位／UI 接點；未直接照搬其全部 toolbar／額外依賴 |
| [NodeIdPlugin](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/core/src/lib/plugins/node-id/NodeIdPlugin.ts)、[withNodeId](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/core/src/lib/plugins/node-id/withNodeId.ts) | Plate／既有 core53.3.11 source／MIT；本機 fixed source 再讀 | NodeIdPlugin 第15–82、324–442行的設定／補缺 ID；withNodeId 第197–224行的 split ID 條件，非語意身分引擎 |
| [F01 原報告](evidence/2026-09-09-jd-native-content-profile-probe.md)、[engine](evidence/jd-profile-probe/engine.mjs)、[fixture](evidence/jd-profile-probe/fixture.mjs) | 本案／2026-09-09固定實證 | 5／1、普通容器、內容與已知 normalization 邊界 |
| [native 原報告](evidence/2026-09-09-jd-native-editor-probe.md)、[history](evidence/2026-09-09-jd-native-history-and-sync-probe.md)、[UI](evidence/2026-09-09-jd-native-editor-ui-probe.md) | 本案／2026-09-09固定實證及封存 lock／LICENSE | 兩反例、3項原生觀測、H09、真正唯讀 UI；不改判未測範圍 |

欄位型別另唯讀核對既有安裝 `@platejs/utils@53.3.11/dist/index.d.ts` 第253–283行；檔案由 [native lock](evidence/jd-native-probe/package-lock.json) 重現。初稿未新增實驗；後續 F02 的獨立 source／LICENSE／fixtures／results 依其報告封存，舊材料不變。pending／codec 原證據保留為歷史，不列正式依賴。
