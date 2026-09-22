# JD 語意契約 v2：成果／要求分組與知識技能引用

- 日期：2026-09-10；Topic：JD-R001/C06、JD-R002/C01／C03；階段：G4及有限G5，未接production。
- 有效前提：Owner同意完整格式、Task底下成果及要求平行分組，以及Plate原生內容＋同PG完整JSONB版本。資料候選A的取捨與限制沿[保存研究§4–7](2026-09-10-jd-semantic-relations-storage-audit.md)。名稱暫沿「工作執行要求」，文案微調不影響結構。
- 唯一問題：把已同意的格式與共享關係變成能生成、編輯、驗證、保存的明確契約，避免靠標題文字猜結構或讓模型配ID。
- 官方依據：既有[profile來源](../2026-09-10-jd-plate-document-profile.md#8-來源與核對日期)、[工具責任與證據](../2026-09-10-jd-responsibility-and-evidence-audit.md)；本次再讀Plate普通element插件與Slate normalization，並重用固定版本原生環境驗證。
- 排除：重選編輯器、通用關係／import／rebase引擎、Memory／來源owner變更、多人／離線副本、DB建表、付費模型、真人交付。ADR0073仍Proposed。

## 1. 決定與版本效力

**D（本案設計）：**唯一active設計schema改為[汲取v1後的v2](../contracts/jd-editor-v2.schema.json)，`format_version:2`、`engine_profile:jd-plate-clean-v2`。v1 schema及既有封存固定不改；它們是舊grammar的證據，不能拿來生成新契約。這是尚未接production的設計升版，不是舊資料migration、相容讀取或雙寫。固定原生套件版本不變；語意grammar改變本身就須明示profile版本。

成果／要求及K／S是普通可編輯block，沿Plate `node.isElement:true`；不設void／isContainer、不加入工作內容normalizer。普通文字、清單、表格、selection、ID、history仍由原生插件處理。本案只約束語意容器及引用完整性。[Plate現行插件文件](https://platejs.org/docs/plugin)支持自訂element接點；[Slate normalization](https://docs.slatejs.org/concepts/11-normalizing)說明原生正規化可能改變結構，不能當無副作用驗證器。兩頁查閱2026-09-10；採用版本／免費授權沿profile固定lock，不由滾動網頁推測新版相容性。

## 2. 最小完整文件結構

以下只替換v1的JD語意部分，其餘body／list／table grammar沿正式profile：

```text
jd_task         = (body | jd_outcomes | jd_requirements)+
                  # 至少1 body；恰1 jd_outcomes、恰1 jd_requirements
jd_outcomes     = body+
jd_requirements = body+
jd_knowledge    = body+
jd_skill        = body+
knowledge章節   = (body | jd_knowledge)+
skills章節      = (body | jd_skill)+
```

- Task一般body放名稱、完整任務敘述及其適用條件；成果／要求分別在自己的組內，可以有多段、清單或表格。兩組數量不配對、不互為父子、不因文字重複而自動合併回敘述。
- 每組至少一個合法body；尚不知道成果或要求時用空p承載編輯位置，沒有假成果／要求、完成度或待審狀態。Task敘述也可只有空p。結構完整不表示工作資訊完整。
- 兩組只准Task直屬，不能重複、互相包含、放在Duty或table cell。內容順序照保存值，不另做背景排序；「成果先、要求後」可作建立時的呈現順序，不是自動重排規則。
- 完整K項目只在`section_kind:knowledge`直屬，完整S項目只在`skills`直屬；名稱與內涵均在該item body，可多段／清單／表格，不把表格cell或名稱相同的普通段落猜成共享item。
- 同文件可有多個同用途章節；所有Element ID全文件唯一。沒有引用的K／S可保存，不自動刪除或連到任何Task。
- 每個Task可省略或保存`knowledge_ids:[]`、`skill_ids:[]`；有值時各為有序、不重複的item ID清單。只有Task可带這兩個保存欄位。省略／空陣列均沒有連線；仍沿exact canonical value判斷實際有無變化，不靜默重寫表示。

「工作成果／產出」「工作執行要求」標籤由renderer依type顯示，不讓LLM額外填label／group kind重複欄位。既有body中的有效文字不得因補標籤被刪。新專屬群組的全文及引用也要在同画面readonly差異中可讀。

## 3. 共同編輯與引用邊界

**完整關係語境仍是`(document_id, revision_id, item_id)`。**正文只存該版item ID；document與revision由App保存上下文提供，模型不逐條填。App遍歷完整候選，驗ID唯一、兩組端點存在及種類正確；不能跨JD查同名、回退到latest或把來源refs當K／S引用。

App的反向對應由同版Task outgoing links推導，按文件Task順序呈現，不保存第二組可編關係。歷史讀r1就用r1定義；r2同ID改名不改寫r1。共享item的本文或名稱變更，需呈現before／after及相關Task；引用者的可讀名稱由其所屬版解析，不另外存一份需同步的文字。

| 操作 | 有限規則及失敗邊界 |
|---|---|
| 改字／改共享名稱、移Task或item | 原生文字／set／move保留ID與未指定內容；item仍須在正確章節。模型讀完整item及受影響Task後判斷語意，不由App斷定適用性 |
| 清空成果／要求 | 清除其body內容並保留合法空p及群組；不移除必需容器，不將空內容解讀為沒有這項工作 |
| 刪一成果／要求容器 | 若整批終點仍有Task，須明示同類replacement group；否則拒絕。中間暫態可以缺組，最終候選不可以 |
| 取消Task語意分組 | 同批明示先unwrap兩個群組，再unwrap Task，保留全部body與順序；單獨unwrap Task會把專屬群組放到非法父層，故拒絕而非靜默攤平。Task outgoing links隨語意身分退出current，留在before |
| 刪Task／Duty | 只刪明示subtree及其outgoing links；共享K／S及其他工作不刪。原版可回看 |
| 刪／unwrap K／S或含它的章節 | 檢查整批最終候選。若有Task仍指向被移除item則拒絕；同批明示解除／改接所有受影響links後才可發布。不能只看top-level target漏掉後代 |
| 人工同文件複製Task | 複本所有Element新ID，保留指向原共享item的links。原工作不變，適用性仍由人／顧問判斷 |
| 人工複製含K／S的一組 | 同次copy的舊→新ID映射只重寫複本內端點；指向未複製item的links保留，組外Tasks不轉向複本。NodeId不會自行處理這些引用 |
| 跨文件複製 | 目的App須明示既存item對應或連必要定義一起建立並重映；無法確定就保留候選並拒絕發布，不猜同名、不原樣帶外文件links |
| 模型複製或首建Task | new-element不收links，先建立內容，保存／重讀後再明示關係；不得冒稱一次insert已保留原Task links。若取消發生於兩步之間，已保存的未連結草稿保留 |

人工完整value、貼上／copy、AI候選、重開都通過同一完整性規則。Node在disposable editor完成原生運算後檢查最終候選；Python負責文件／base／issued refs及來源scope，Node不讀DB／Memory。失敗保留人工未存buffer與舊正式revision；手改UI應透過有限動作及可讀錯誤保護必需群組，不能刪資料讓保存過關。DOM鍵盤與貼上驗收仍由原Task 4負責。

## 4. 模型參數及App分工

工具仍只有`jd_read`／`jd_edit`／`jd_change_read`，七個command不增加。

| 邊界 | 形狀／責任 |
|---|---|
| 模型new-element | 只有typed內容與必要來源等既有欄位；任何層不能填ID、K／S refs／IDs或temporary IDs |
| 模型set／unset | Task的`knowledge_refs`／`skill_refs`為App發配的目標refs；set替換整組，[]清空、unset省略、未指定保留。set／unset同欄位拒絕 |
| App解析 | 驗issued、同文件、同current base、可寫access及K／S種類；將set內refs及unset欄名一併映成`knowledge_ids`／`skill_ids` |
| Node輸入 | `JdResolvedEditableProperties`、`JdResolvedUnsettableProperty`、`JdResolvedPropertyUpdateConstraint`只收對應IDs欄名；不能沿用模型properties導致ref漏進JSONB |
| 保存／人工value | `JdSavedElement`只存Task IDs清單；反向清單及opaque目標refs不進正文。來源仍為原`source_refs`且沿既有來源owner |
| 模型read結果 | Task的`JdReadTarget`必有knowledge／skill refs（可空）；K／S target必有`used_by_task_refs`（可空）；其他type不帶這些欄位。App由完整該revision計算，不能只看當頁 |

**首次建立固定流程：**`insert_content`建立已理解的Task／K／S → 確認保存結果 → `jd_read({})`讀新current base及必要分頁／項目 → `set_properties`建立關係。每次保存後重新取得下一批refs，不沿用前一版；第一步成功第二步失敗不撤销已保存內容，重開可從尚未連結的稿續作。結果未知先對帳原operation，不重新insert。這是兩次各自原子的編輯，不承諾跨兩次保存全成全敗。

已發配ref不等於已讀內容。改共享內涵前須讀完整item及其`used_by_task_refs`指向的Task；完整替換link集合前須讀目前完整集合與新端點，保留仍適用者。history與其衍生refs全部readonly；分页不能換base／access，也不能將未讀當不存在。

上述「已知資訊交App」「工具有明確用途／輸入／結果」沿現行[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)及[Anthropic tool definitions](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions)（2026-09-10定點核對）；具體兩階段及refs／IDs欄位仍是本案映射。正式模型description保存在v2 SSOT，factory不得另手寫不同版本。

## 5. 錯誤及保存契約

沿既有[錯誤／重試契約](2026-09-10-jd-error-recovery-contract-closure.md)，不新增工具或持久狀態：

- shape、重複link、錯kind、非Task設定links、set／unset交集、非法group或仍被引用的刪除 → `invalid_input`，error.code說明有限原因（如`invalid_relation_kind`、`referenced_item`、`invalid_jd_structure`），message指出涉及的內容及可讀取的關係位置。保存前零發布；不可冒充`engine_failed`。
- 未發配／外scope refs不得降級成raw ID；已有target缺失／基底過期沿`target_missing`／`stale_base`及重讀。若原base本身已有失效保存關係，視為資料／profile失敗並停止，不要求模型編故事修資料。
- `referenced_item`可先以`jd_read`讀取相關K／S及其incoming refs，再明示修正同批意圖；不在immutable receipt塞稍後會變動的current投影，不為錯誤另造關係查詢工具。
- 原生／保存故障仍走`engine_failed`／`save_failed`；已綁定operation未確認時仍優先對帳。完整文件／定義／links同revision發布，operation回執與head沿同PG短交易，不新增關係store。

新格式只將固定保存profile核值改為2／`jd-plate-clean-v2`，不改三表關係／FK／去重語意。本轮不建DB，也沒有JSONB內部FK的宣稱；完整性仍是已選A的App驗證責任。

## 6. 有限工作與通過條件

1. **同一schema與說明。**v2封閉grammar及邊界，v1 hash不變；全部defs可編譯，Task兩組／K／S合法與反例、model/resolved set／unset互斥、read投影與來源分隔通過。
2. **關係與恢復的契約示範。**固定3 Tasks／2 K／2 S涵蓋零與多連線、錯端點、共享改名、同ID歷史、首建兩階段、copy/delete/unwrap及人工全值；這一層是有限驗證模型，不冒充正式App或DB。
3. **真正原生能力。**沿已裝固定Plate組合驗新容器、原生編輯／ID／move／unwrap及新程序JSON重開；固定內容複製的關係依明列fixture映射設定，不宣稱正式copy／remap已實作。完整r2的固定對應與版面變更明列，不修改原封存、不稱通用migration。
4. **交接與審查。**同步profile、工具、schema說明、保存核值、主設計、Proposed ADR及六切片；獨立review無阻擋，register恢復Task 1。後續Task 1使用v2來源與新fixture，真DOM／SQL／provider／自然模型不列此輪已通過。

若必須重做通用編輯／匹配／排序／回退引擎才能滿足，停在具體缺口回報；有限App語意驗證不因此包裝為原生內建。正式語意validator仍由Task 1接線並重跑相同情境，研究probe不得成為runtime import。

## 7. 執行結果

**2026-09-10有限閉合，下一單位恢復原隔離Task 1。**v2共105 defs，SHA256為`c6cc0f996b7a24b37cdf784a9d46e88cbb1d59f4d68d327e4167f3dfa40fb715`；v1維持`ced26a3b625de891989a63d5f12e4ac884484083d7f677cf10ad8c54e318b973`。正式App、DB及UI尚未實作；不把本表當六切片驗收。

| 證據 | 實際結果 | 效力界線 |
|---|---|---|
| [契約probe](jd-semantic-contract-probe/README.md)／[最終結果](jd-semantic-contract-probe/final-v2-results.json) | 268項、0 mismatch、exit 0：105 defs編譯＋121 shape＋42有限契約模型；主線直接Node重跑一致 | 固定refs／候選模型不是真App發配、两次保存或取消；AJV不轉型、不補值、不刪欄位 |
| [F03原生probe](jd-semantic-native-probe/README.md) | 第二輪4／4組、21項通過，6次不同PID新程序重開全值相等；首輪0／4的clone callback／EPERM harness失敗保留 | 普通原生API及固定copy／明列映射有證據；**原生容許非法group／orphan結果，負例斷言不是正式App已拒絕** |
| [SDK wire](jd-semantic-contract-probe/provider-wire-v2-results.json) | 三工具正式description／parameters全等；新群組及model refs到request，resolved IDs不暴露；0網路、0工具執行 | 沿固定SDK MockTransport，只證序列化；初始過度限定例外名稱的探針assert已修並記錄，未改工具契約，不證真provider接受或自然模型 |
| [整合核對](jd-semantic-schema-build/integrated-results.json)／[重現腳本](jd-semantic-schema-build/check-integrated-evidence.cjs) | 16項、0失敗：F03真實完整值／固定expected與v2 schema相符，非法unwrap／缺組被shape拒絕，三工具capture與目前SSOT再核全等 | orphan故意是shape-valid，關係完整性仍須App；不重跑原生或外部provider |

新完整fixture有190個Element、6章、4 Duty、8 Task及各8個成果／要求組、5 K／5 S、1張基本資料表。原r2文字／marked leaves及8個帶來源節點保留；K／S表格38個外框ID的退役由[固定mapping](jd-semantic-native-probe/fixture-mapping.json)明列。新增links是合成測試配置，非已核實職務事實。Task8-only的[完整expected](jd-semantic-native-probe/task8-move-full-expected.json)是明列oracle，與F03-C先copy再move的實測after分開，不混用基底。

F03-D的三次unwrap保留全部文字／marks及剩餘body ID，但被移除Task wrapper自身的`source_refs`及outgoing links退出current，留在before；原生不下傳。這符合§3及工具原有明示unwrap語意，不能稱來源／關係無損。必要附著由模型在同批明示，不增加來源傳播引擎。

獨立工具／schema review及關係review無阻擋；F03另經只讀review確認未建通用matcher或把負例說成App已處理。兩個schema版本顯示文字殘留已修正；copy措辭依review限為固定內容與明列映射。本輪未修改production程式、套件lock、Memory或資料庫，未安裝或付費呼叫。profile、工具、schema說明、保存核值、主設計、Proposed ADR及六切片已同步；唯一active SSOT是v2，研究builder／probe不得成為runtime依賴。

接下來Task 1完成生成DTO、正式有限grammar／relation validator及原生command adapter，重新驗收本批情境；Task 2–6再做SQL／真工具／DOM／取消與整體閉合。無需重問格式、保存方向或三表選擇；實際自然模型的職務忠實度、完整性、延遲／成本仍另有預算驗收，不以本輪數字代稱滿分。

收尾核對：13份責任文件／新證據說明及register最新路由的280個本地連結／錨點，0失敗；限定變更檔案的`git diff --check`通過。這些是文檔一致性檢查，不追加產品驗收主張。
