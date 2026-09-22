# JD 語意關係與保存方式：K／S 引用的定點稽核

2026-09-10；Topic：JD-R001/C06、JD-R002/C01／C03。本文依 Owner 新研究要求，核對完整格式與任務↔知識／技能推薦如何落入現有契約；只新增本附件，不改 SSOT、SQL、migration、runtime、Memory 或 production，不連資料庫、不安裝或呼叫付費模型。

**結論：現行 v1 能保存完整任務及多項產出／要求，尚未實作任務↔K／S 的明確內容引用。**這是新關係需求對既有契約的擴充，不能說先前版本／回執交易全部錯誤。若採用目前格式中的同份 JD 共用 K／S 推薦，優先考慮「同一 immutable revision 內，完整項目只存一份，Task 保存對它的引用；App 驗完整候選關係」。SQL FK 投影及完整關聯式實體另列兩個有條件候選，不以多對多三字直接決定拆表。

標記：**F**＝官方／本機直接證據；**M**＝本案需求映射／推薦；**I**＝由明列契約推得的風險；**V**＝尚待實作驗收；**U**＝公開資料不能確認。

## 1. 本輪基線、版本與效力

已讀：[current register](../../current-decisions.md)、[決策流程](../../decision-process.md)、[完整格式討論稿](../2026-09-10-jd-format-review.md)、[K／S 新關係討論](../2026-09-09-jd-document-relationships-working-research.md#2026-09-10任務與知識技能的明確對應討論)、[正式 Plate profile](../2026-09-10-jd-plate-document-profile.md)、[SSOT](../contracts/jd-editor-v1.schema.json)、[主設計 §5.4](../2026-09-09-jd-editor-app-integration-design.md#54-保存資料的具體約束)、[保存 closure](2026-09-10-jd-storage-contract-closure.md)、[先前關係稽核](2026-09-10-jd-storage-relations-audit.md)及[contract strategy](../../contract-strategy.md)。

截至本輪讀取，register 的完整格式／K／S 明確引用仍為 G3 OPEN 推薦，主體格式為 WORKING，Task 1 暫緩。本文提供後續收斂依據，不將提問或研究授權改稱格式及實作已核准。既有 `revision→receipt→head` 原子發布、單向 FK、immutable terminal receipt、no_change／unknown 恢復策略保留。

**F：**本機 [docker-compose.yml](../../../docker-compose.yml) L8 與[隔離 checkout 同檔](../../../.worktrees/analysis-only-agent/docker-compose.yml) L8 均為 `image: postgres:16`。這只固定 major，沒有固定 minor 或 image digest；本輪未查正在執行的 server，因此實際 patch、image 及 WAL 設定仍 Unknown。官方 [versioning](https://www.postgresql.org/support/versioning/)本日列 16 仍受支援、當期 minor 16.15、預定支援至 2028-11-09；[current JSON 文件](https://www.postgresql.org/docs/current/datatype-json.html)標示 18。研究與可用 SQL 能力仍以 16 為準，不因 current 指向 18 就要求換版。

**F：**實際讀取的候選 SSOT 為 86 defs，SHA256 `CED26A3B625DE891989A63D5F12E4AC884484083D7F677CF10AD8C54E318B973`。現有 201 項契約驗證證明其當時列出的 shape／動作矩陣，不包含本輪新 K／S 關係能力；見[原紀錄](jd-contract-closure/README.md)。

## 2. 實際契約已支持什麼、缺在哪裡

| 項目 | 實際位置與所見 | 判定／必要責任 |
|---|---|---|
| 任務可有多項 O／P | `JdSavedElement` 的 jd_task 分支 L155–157 → `JdSavedBodyElement`；profile §2 的 `jd_task=body+`，body 含段落／清單／表格 | **F：**沒有恰一 O／P 的限制，能保留多項成果、品質／條件及未歸屬正文。**界線：**這些內容尚非有獨立語意型別的 O／P 記錄，程式不能只靠正文標籤可靠列舉它們；目前要求多項可讀內容，並不自動要求 O／P 資料表 |
| K／S 的完整項目身分 | `JdSectionKind` L80–82 有 knowledge／skills；`JdElementType` L84–89 沒有 knowledge-item／skill-item；非 work section 仍只含一般 body | **F／SR01：**只能辨識總覽區段，未定義可引用的完整 K／S 項目。paragraph、table row、cell 雖有 Element ID，並不自動代表「一項含名稱、內涵與用途的專業」 |
| Task→K／S 連線 | `JdSavedElement` L91 起、`JdNewElement` L198 起、`JdEditableProperties` L878 起、`JdUnsettableProperty` L921 起均無 K／S 引用欄位；封閉物件拒絕額外欄位 | **F／SR02：**目前沒有可提交、保存及回讀的語意連線。`source_refs` 是 canonical 訪談依據，不能改作 K／S identity；知識／技能總覽的「對應任務」也不應再存一份手填反向清單 |
| 端點及版本完整性 | `JdDocumentValue` L724–728 為 Element array；`JdReadTarget` L1547 起只含 target_ref／element／access；既有 profile 驗 grammar、ID、來源；三表 FK 指 catalog／revision／operation | **F／SR03：**既有 FK 不會查 JSON 樹中 K／S 端點是否存在、種類正確或屬同版。新 relation 要有完整候選 validator／解析責任；JSON Schema 形狀不能冒稱 referential integrity |
| 拆分／複製／刪除／共用改名 | 既有七 command 与 profile §4 已有 ID／subtree／來源保留規則 | **I：**這些能作基礎，但未定新語意引用的複本 ID 重映射、被引用項刪除、共享改名及歷史解析。原生 move／NodeId 不會自動完成它們 |

**K／S identity 的最小意思：**一個可獨立改名／移動、可能有多段內涵與用途的完整項目，其身分不等於標題字串、畫面 K01 編號、某個 cell ID 或整個 knowledge section ID。同名不同範圍不得自動合併；排版／表格拆列也不能未經語意規則就改項目身分。

### 2.1 實跑的六個只讀 schema 情境

本輪以既有 Node 22.12.0／AJV 8.20.0＋ajv-formats，Draft 2020-12，關閉 coercion／default／removeAdditional，在記憶體驗同一 SSOT；未改 schema 或輸入，沒有 Plate／App／DB 執行。六例均符合下表預期，0 mismatch。

基底：一 work section 中一個 jd_task，含四個 p，分別寫「產出：修正版本」「產出：處理紀錄」「要求：驗證問題」「要求：必要時交接」；另有 knowledge section，內含一個 p「介面契約知識」。所有節點先有不同 ID。

| 僅作這項變動 | `JdDocumentValue` 結果 | 能／不能證明 |
|---|---|---|
| 基底不變 | 通過 | 多 O／P 內容可保存形狀；不證明程式知道哪句是 O／P |
| 刪除 knowledge section | 通過 | 未連線、內容尚在建構的草稿合法；缺關係不應強造引用 |
| task 加 `knowledge_ids:["missing-k"]` | 拒絕 | 現 v1 沒有此欄位，**不是已驗 dangling 引用會被 relation validator 拒絕** |
| knowledge section 放 `type:"jd_knowledge"` 的新完整項目 | 拒絕 | 現 v1 沒有此型別；新名稱僅研究示例，不是可用 API |
| task 增 p「所需知識：K99」，但沒有 K99 項目 | 通過 | 普通文字不會被當成機器關係驗證；不得把看起來有引用的文字當已建立連線 |
| 將 knowledge p 的 ID 改成與某 task p 相同 | 通過 | JSON Schema 本身不保證全樹 ID 唯一；**此責任已在原 profile 明列 App／Node 檢查，不是新发现未設防實作漏洞** |

未連線草稿與 dangling link 是不同情況：前者沒有宣稱存在的端點，應可保存；後者一旦用正式 typed link 聲稱連到某項目，就必須能在該保存版找到唯一且正確種類的目標，不能因「允許不完整」放行懸空引用。

### 2.2 六例檢查的可重現程式

在 repo root，以已安裝 Node 執行以下 JavaScript。以 `.research-tmp/jd-editor-native-probe/package.json` 為 `createRequire` 的明確解析起點，優先使用該 probe 既有依賴，不假定執行檔案旁就有 AJV 8。Node 仍會依原生解析規則向父目錄查找，因此程式輸出實際 `ajvResolvedFrom` 並核對固定 8.20.0，不能把 anchor 當實際安裝位置；本輪此環境解析到 `S:/caliburn/node_modules/ajv/dist/2020.js`，probe 下沒有另一份該檔。缺依賴或版本不同時停止，不自動安裝。程式只讀 current SSOT，在記憶體中複製測試值並把結果寫到 stdout；不修改 schema、輸入或任何檔案，不啟動 editor／模型／DB。重跑時以輸出的 schema hash 與版本識別實際基線，不能在後續改版後仍套用本次結果。

```javascript
const fs = require('node:fs');
const crypto = require('node:crypto');
const probeRequire = require('node:module').createRequire(require('node:path').resolve('.research-tmp/jd-editor-native-probe/package.json'));
const ajvVersion = probeRequire('ajv/package.json').version;
if (ajvVersion !== '8.20.0') throw new Error('Expected existing AJV 8.20.0; found ' + ajvVersion);
const Ajv = probeRequire('ajv/dist/2020').default;
const addFormats = probeRequire('ajv-formats');
const path = 'docs/specs/contracts/jd-editor-v1.schema.json';
const bytes = fs.readFileSync(path);
const schema = JSON.parse(bytes);
const ajv = new Ajv({strict:false,allErrors:true,coerceTypes:false,useDefaults:false,removeAdditional:false});
addFormats(ajv);
ajv.addSchema(schema);
const valid = ajv.getSchema(schema.$id + '#/$defs/JdDocumentValue');
const p = (id,text) => ({type:'p',id,children:[{text}]});
const base = [{type:'jd_section',id:'work',section_kind:'work',children:[{type:'jd_task',id:'task-1',children:[p('p-1','產出：修正版本'),p('p-2','產出：處理紀錄'),p('p-3','要求：驗證問題'),p('p-4','要求：必要時交接')]}]},{type:'jd_section',id:'knowledge',section_kind:'knowledge',children:[p('k-body','介面契約知識')]}];
const rows=[];
function check(name, edit, expected) {const input=structuredClone(base);edit(input);const before=JSON.stringify(input);const accepted=valid(input); rows.push({name,expected,accepted,inputUnchanged:before===JSON.stringify(input),errorKeywords:accepted?[]:[...new Set(valid.errors.map(x=>x.keyword))]});}
check('multiple_outputs_and_requirements',x=>{},true);
check('unlinked_draft_allowed',x=>x.splice(1,1),true);
check('task_knowledge_ids_not_supported',x=>x[0].children[0].knowledge_ids=['missing-k'],false);
check('knowledge_item_type_not_supported',x=>x[1].children=[{type:'jd_knowledge',id:'k-1',children:[p('k-text','介面契約知識')]}],false);
check('textual_K99_is_not_validated_as_relation',x=>x[0].children[0].children.push(p('p-5','所需知識：K99')),true);
check('duplicate_element_ids_not_schema_integrity',x=>x[1].children[0].id='p-1',true);
console.log(JSON.stringify({node:process.version,ajv:ajvVersion,ajvResolvedFrom:probeRequire.resolve('ajv/dist/2020'),schemaSha256:crypto.createHash('sha256').update(bytes).digest('hex'),checks:rows,mismatch:rows.filter(x=>x.expected!==x.accepted||!x.inputUnchanged).length},null,2));
```

## 3. 現行官方資料支持的原則

下列頁面本日均實際 open／fetch 並核對相關段落，不只引用搜尋摘要。滾動文件沒有精確單頁版本／更新日者明列，沒有把來源服務裝入本案。

| 官方來源／狀態 | F：直接支持的事實 | M：本案可採用與不可推出之處 |
|---|---|---|
| [PostgreSQL 16 JSON Types §8.14.2](https://www.postgresql.org/docs/16/datatype-json.html#JSON-DESIGN)；另核 current 18 同節 | JSON 與關聯形式可並用；JSON 宜有可預測形狀；更新會鎖整列，資料單位與可獨立修改性需一起考慮 | 完整 JD revision 作原子發布單位是**本案既有保存／歷史需求的選擇**。局部改一 Task 不必然要求拆表；反過來也不能由「是文件」推得永遠整份 JSON 最佳 |
| [PostgreSQL 16 Constraints §5.4.5](https://www.postgresql.org/docs/16/ddl-constraints.html#DDL-CONSTRAINTS-FK) | 複合 FK 核欄位組對應，雙 FK 的連接表可表達多對多；刪除策略依物件是否獨立而定；CHECK 不適合可靠跨列檢查 | 若採關聯表，FK 必含 document／revision／項目識別，不能只核 UUID 或裸 ID。SQL 外鍵不會因 JSON 字串名叫 ref 就成立；不以觸發跨列查詢的 CHECK 冒充完整性 |
| [PostgreSQL 16 Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html) | 多步交易全成／全敗，未提交中間狀態不供其他交易觀察 | 三個候選均可維持一個 JD 發布交易及原 receipt 策略，不需為新關係另起獨立可寫 current store |
| [Microsoft Azure Cosmos DB data modeling](https://learn.microsoft.com/en-us/azure/cosmos-db/modeling-data#when-to-reference)，頁面 last updated 2026-07-31 | 依存取／變動／增長選 embedding 或 referencing；多對多、共用頻改資料可採 reference；其文件間引用沒有 FK 約束，存在性須另驗 | 支持共用 K／S 內容不重抄及反向關係推導。Cosmos 特定分區／效能／交易能力不直接套成 PostgreSQL 契約，也不支持一律採無 SQL FK |
| [MongoDB Reference Data](https://www.mongodb.com/docs/manual/data-modeling/referencing/)，頁面導覽本日標 8.3 Current，未列單頁更新日 | reference 可免重複內容；複雜多對多、常獨立查詢或重複更新成本高時可考慮引用 | 「有引用」和「把每句正文拆成另一表」不相同；用來比較關係表示，不採 MongoDB 或假定其供應商保證本案 referential integrity |
| [AWS Amazon DocumentDB：Optimize Data Models Based on Query Patterns](https://docs.aws.amazon.com/documentdb/latest/devguide/performance-improvement-tips.html)，current developer guide，未列單頁發布日 | 常一起取用的有限資料可內嵌；大量／低頻取用資料可引用，變動與存取模式影響拆分 | 當前以同份 JD 閱讀／發布、單寫入者為主，支持先驗較薄方案；沒有給本案文件大小／延遲的實測結論，亦不採 AWS 服務 |

**共同層次：**依實際存取、更新、資料範圍、重複成本及一致性需求選關係表示。**不是共同結論：**所有 JD 必須 JSONB、必須 SQL join tables，或各大 AI 廠商都使用相同 DB。**U：**本輪沒有可核實的 OpenAI／ChatGPT／Codex、Anthropic／Claude 內部 JD／職能資料庫 schema；其模型工具文件不能證明私有保存實作，保持 Unknown，不拿品牌當選型理由。

## 4. 最多三個實質候選

所有候選都使用既有 PostgreSQL 16、JD 唯一 owner、immutable revision、同文件 head lock／base 檢查及既有 terminal receipt 協定。K／S 僅在同份 JD 共享，沒有跨文件詞庫、K↔S 第三組圖、RAG、Memory 複製或第二分析系統。

| 候選 | 權威表示／完整性責任 | 優点、代價與選用條件 |
|---|---|---|
| **A：完整 revision JSONB，內含有型別項目與單向 Task refs；優先推薦** | K／S 各完整項目在該版 tree 只出現一次；Task 存目標項目穩定 ID。App 由同一候選全值驗唯一身分、同版端點及正確種類；反向對應由這組連線推導。DB 保證 revision／receipt 發布，不對 JSON 內每條 link 提供 FK | 最貼近同文件完整讀取／差異／單一發布的既有界線；不重抄正文、不加同步 projection。但必須把 relation validator 接入 AI、人編、貼上／複製、匯入、重開的必要邊界；不能稱既有 NodeId 或 schema 已完成 |
| **B：A 的唯一 JSONB＋同交易產生 membership／edge 關聯投影** | JSONB 仍是唯一可編正文與關係來源；從同一 candidate 抽取 `(document,revision,item_id,kind)` 及兩組 Task→K／S edges。投影 FK 核同文件／同版兩端，種類須以有限 typed membership／欄位約束固定。投影不得被獨立修改 | 適用於確定要讓 SQL 約束阻擋錯端點、或有實測支持的關係查詢。代價是每版附加列／索引、同交易完整提取與一致性核對。**FK 只保證投影內存在性；投影漏掉 link／宣稱不存在的 tree item 仍須 App 比對完整集合**，不可宣稱投影自然等於正文 |
| **C：按 revision 正規化語意項目／關係，Plate value 為確定性閱讀與編輯投影** | Task、K／S、關係有 SQL authority；完整敘述仍可作各項 rich-text JSONB，不必拆每句。所有項目與關係同 revision 保存，整份快照由唯一 mapper 生成；不允许 SQL 正文與一份獨立可寫 Plate value 各自決定事實 | 適用於已需要大量獨立實體查詢／更新、跨用途投影而 A／B 不足時。当前須改動更多編輯／投影／差異／保存契約，容易產生雙權威或遺漏排版；不能只為「多對多通常有關聯表」就採用。原 receipt 原子性可保留，但內容來源的改變須另做 successor 設計與驗收 |

**M：推薦 A 的理由是目前已知工作負載與權威界線，不是 JSON 比 relational 先進。**Task 的局部編輯意圖，仍在整份 JD 版本中原子發布；共享項目改名及引用集合一起進同一快照，歷史直接帶該版定義。現階段沒有「跨多份 JD 即時查技能統計」「多個 writer 獨立更新 K／S」等採 C 的已核需求。若需要關係投影的 SQL 約束／直接查詢，或完整候選關係檢查的成本／查詢效果實測不符，可評估 B；其 FK 只約束投影端點，App 仍須核對投影與正文的完整項目及連線集合。若要求繞過 App 的任意 SQL 寫入也全面阻擋 JSON 內部失效引用，A 與此處 B 皆不足，須另評 DB 一致性機制或 C 的關聯式 authority，不能把投影 FK 說成充分保證。本輪不新增 trigger，也不先建三路。

## 5. A 的具體身分、範圍及編輯語意

以下保留研究提出時的具體推薦。Owner後續同意A方向，已由[語意契約v2](2026-09-10-jd-semantic-contract-closure.md)固定群組／項目、refs與IDs分工及先建後連流程；v1仍不支持這些shape。原有實測界線不因v2設計而改判。

### 5.1 最少而完整的資料關係

- 完整 K／S 項目須有明確語意邊界，例如普通 block 容器 `jd_knowledge`／`jd_skill`，內含可讀 body 與既有 NodeId。實際型別名稱、允許位置與 renderer 由 successor profile 固定；不能只把任意 p／td 當項目，或讓 title 與說明分成互無身分的 cell 後仍冒稱完整引用。
- Task→knowledge、Task→skill 是兩組 `0..*` 的有序、不重複目標引用；各 K／S 可被 `0..*` Tasks 使用。沒有連線可表示尚未釐清／未使用，不自動刪項目或生成假的知識／技能。反向清單從 Task links 與當版 Task 次序計算，模型不再填第二份。
- saved link 只須保存該 JD 內的穩定目標 ID；document／revision 由所屬 immutable revision 提供，App 不讓模型逐條重填。**解析一條 link 的完整語境是 `(document_id, revision_id, target_item_id)`**。只有 ID 相同、目標在另一份文件或另一版存在，都不足以成立。
- 已保存歷史永遠用同版 K／S 定義；不能拿 r5 Task 的 link 解析到 current r9 的改名／改義內容。current 編輯取得新 base 後全候選重驗；同一項目 ID 跨版延續不等於引用「永遠 latest」。
- K／S 名稱與內涵只在本版定義保存一份；任務旁可讀名稱由 App renderer 解析，避免另存需要同步更新的拷貝。關係特有的適用限制先保留於相關任務的完整正文，不為本題新增通用 scope object／繼承引擎。
- `source_refs` 維持原始訪談回查，其作用、發配與 owner 不變。Task→K／S 的適用關係不是證據引用，不能把兩種 ref 混入同一陣列。

### 5.2 操作後果必須明確

| 意圖 | 建議的有限規則 | 必須保留／驗證 |
|---|---|---|
| 共用 K／S 改名／改正文 | 同一項目保留 ID，形成新 revision；所有 current 引用者依新定義呈現。若只是其中一任務需要不同含義，模型明示新建項目並重新連那一部分 | 顯示受影響 Task 清單；舊版仍讀原名／原文。App 不從名稱相同推論可合併，也不能判斷新內涵仍適用所有工作 |
| Task 或 K／S 移動／重新排版 | 完整項目保留 ID，links 不因流水號／父位置改變而改動 | 普通表格增刪／拆格不能未經 item 規則就切碎語意項目。正文與引用仍都可回查 |
| 明確拆 Task | 延續者可保留原 Task ID，新者新 ID；模型決定各自 O／P、條件及 K／S 適用連線 | App 只驗分配後結構及端點，不將原 links 自動撒給所有新 Task；普通 Enter 仍不是拆工作 |
| 明確拆 K／S | 模型決定哪份保留原身分，其他新 ID，並明示需要改接的 Task 子集 | 原有 Task 不能悄悄跟到錯誤的新含義；未指定既有內容及舊版不變 |
| 同文件只複製 Task | 全部複本 Element 新 ID；如使用者意圖確為複製原工作，可保留指向原共享 K／S 的連線 | 共享定義不重抄；內容變成另一工作時仍需模型核對適用性 |
| 同文件複製包含 Task 與 K／S 的整組內容 | App 以同次新 ID 映射重寫複本內部連線；指向未複製的同文件項目仍保留原連線，外部既有 Tasks 不轉向複本 | 原生 NodeId 只配 ID 不等於完成連線重映射；所有新端點須在完整候選中存在 |
| 跨文件複製 | 不能直接保留外文件 IDs／links；須明示連到目的文件既有項目，或連同必要定義一起複製後映新 ID | 無法解出目的端點時保留候選並拒絕發布，不默默丟 link、拷貝全詞庫或查全域同名匹配 |
| 解除一 Task 的引用 | 只改該 Task 的連線 | K／S 定義與其他使用者不變；反向清單即時從同版 links 推導 |
| 刪除 Task／unwrap Task 容器 | 刪 Task 時其 outgoing links 隨任務退出 current；unwrap 使其不再是語意 Task，需明示呈現其正文仍保留 | 不連帶刪共享 K／S；unwrap 不把 task links 隱性轉到段落或兄弟工作，原關係留在 immutable before |
| 刪除仍被引用的 K／S | 預設拒絕並提供同版受影響 Tasks；同一原子批次明示解除／替換全部相關引用後才可刪定義 | 不級聯刪 Task、正文或原始來源。人工刪除操作也通過同一 relation boundary，不能靠只在 AI 工具檢查 |

原有 `remove_content`／`unwrap_group` 能刪掉包含很多子內容的容器，因此「是否移除某個被引用 K／S」必須檢查**實際整批最終候選**及明示修改範圍，不能只看 top-level command target 的 type。驗證器可先建本版有限 item map，再遍歷兩組 links；這是確定性完整性檢查，不是判斷工作適用性的模型或通用圖引擎。

### 5.3 模型、App、原生與 DB 的分工

| 責任者 | 應做 | 不應轉嫁／誤稱 |
|---|---|---|
| LLM／員工 | 判斷真實工作與 K／S 的適用關係、完整內容、拆分後分配及共享修改範圍；使用 App 已發配可讀目標 | 不填 document／revision／保存 ID、反向引用聯集、SQL、FK 或重複名稱拷貝；不因必填關係造事實 |
| App | 發配 `(document,current base,item)` 能力引用；解析模型選擇；維護正反向呈現；檢查全候選端點／kind／scope、複本映射及刪除影響 | 不用名稱模糊配對，不猜 relation 語意，不把「存在」標為「適用已核實」 |
| Plate／NodeId | 原生文字／結構編輯、配新 Element ID、維持指定身分與完整 value；Node adapter 執行有限 relation 映射／後檢 | 原生框架不自動理解 K／S 及工作拆分；現有普通節點測試不證明新關係保存 |
| PostgreSQL／JD store | 沿既有 head／revision／receipt 發布完整經驗證候選，保存其關係與定義同版一致；A 的 link 完整性依 App，B／C 才再有明列 SQL FK | JSONB 存得下、schema 形狀通過或 transaction 成功，均不能代稱 K／S 端點已驗或語意正確 |

**首建的實際接點缺口：**現有 new-element 不讓模型填 ID，target handles 又由已保存 `jd_read` 發配；因此「同一批創建新 K／S，立刻連到同批新 Task」不能靠模型猜 native 新 ID。最薄可行順序是先保存新完整項目→讀取已發配 item refs→再設定連線，且未連線中間草稿本來合法；若成品要求這兩步也必須一次原子完成，須另定有限的 batch-local 接點並驗證，不能偷偷加模型 temporary ID／第四 Agent。本研究不將此尚未定義接點說成現七 command 已支持。

## 6. 受影響契約與有限後續驗收

採 A 前須在唯一 SSOT／profile 同步：`JdElementType`、`JdSavedElement`／`JdNewElement` 的型別分支及 K／S 完整項目 child grammar、section 可包含項目的範圍、saved links、模型可選的 issued refs、`JdEditableProperties`／`JdUnsettableProperty`、`JdSetPropertiesCommand` 的適用種類與衝突規則、`JdResolvedEditCommand` 的內部映射、read result 的完整項目／必要引用資料及失敗提示。模型 ref 與 saved item ID 的作用不同，不得只因都是 string 就共用錯誤解析規則。

新的 shape 要跟格式／profile 版本一起明示；既有 v1 grammar 不支持的資料不能默默塞進 `other`／source_refs 或清除後過測。人工完整 value、native adapter、差異 renderer 及完整快照回讀也要採同一新契約。跨語言形狀仍依 contract strategy 的 JSON Schema SSOT 生成，Python internal port／mapper 沿既有方式；不手寫第二份 Web relation schema，也不為純內部遍歷新建泛用 package。

| 有限驗收 | 必要可观察結果 |
|---|---|
| 三 Task、两 K、两 S、零與多連線 | 多對多、單項定義、反向呈現一致；沒有連線的有效草稿可存；多 O／P、未知與任務特有條件全文保留 |
| 缺失／錯型別／重複／外文件／外版本端點 | typed link 外形合法仍拒絕，不能 fallback 到 current／同名／第一個 ID；本批零發布 |
| 同 ID 跨 revision 改名 | r1 仍顯示 r1 定義；r2 引用者顯示 r2 定義；完整歷史不用讀 latest K／S |
| 共享改名、只一 Task 改適用範圍 | 全部受影響 Task 可查；局部差異需分項或明示 relink，不悄悄改其他工作條件 |
| Task／K／S 拆分、複製、移動、unwrap、刪除 | 新 ID 與內外連線映射符合 §5；不能遺失未指定正文、引用或歷史；刪定義不刪 Task |
| AI／人編／貼上／新程序重開 | 同一 relation invariant 生效，既有 refs 發配與 scope 不繞過；source_refs 與內容 links 分開回查 |
| base 競爭、候選失敗及 commit 回覆遺失 | 原 receipt-first／head lock／immutable result 協定不變；正文、定義與連線同版全成或全敗，不增加第二可寫關係 store |
| A 的成本與 B 的升級條件 | 用完整樣稿及有代表性的較長文件記 bytes、items／edges、驗證／讀取／差異成本；沒有量測前不宣稱 A 必快或 B 必需。若採 B，故意漏投影／錯造 membership 也應被完整集合比對拒絕，不能只驗 FK 正常例 |

本輪已完成來源 fetch、只讀配置／契約診斷及六例 schema 檢查。沒有執行新的 Plate relation、DB FK／交易、Web 編輯或自然模型測試。下一步由主研究整合產品格式與此有限關係設計，再同步 successor 契約／驗收；本文本身不是 migration／施工核准，也不推翻先前已限定的保存證據。

## 7. JSON、關聯與三表：現行公開證據能支持到哪裡

2026-09-10 Owner續問：以LLM與人共同編輯的App來說，JSON或關聯是哪個主流？`jd_head`／`jd_revision`／`jd_operation`是否大廠最新共識？本節是定點補證，不重新選框架或自動批准§4的資料候選。

**結論：不能把這三張表、每次完整JD快照，或JSONB內部引用稱為大廠統一實作。**能佐證的是現行仍使用的可靠性原則與具體框架能力。JSON與關聯並非單一層次的二選一；本案採同PostgreSQL中，關聯欄位管理文件／版本／操作，JSONB保存完整編輯內容，是針對已知需求的工程映射。本文沒有市場佔有率調查，也沒有證據宣稱「AI時代已全面改成JSON」或關聯模型被淘汰。

### 7.1 先分清四個問題

| 層次 | 應回答的問題 | 不可直接推論 |
|---|---|---|
| 文件與編輯模型 | 哪些是任務、成果、要求及K／S？如何排序、保留文字與身分？ | 輸出JSON不等於有SQL表，也不等於內部引用已驗證 |
| 傳輸與模型工具 | App給模型何種可讀狀態、接受何種操作、回傳何種結果？ | API用JSON不證明後端保存JSONB；模型不需直接看或改SQL |
| 持久保存與關係 | 內容放JSONB、獨立block rows或其他原生狀態？哪些約束在App／DB？ | 關聯DB可包含JSON／binary；文件有結構不表示每個節點必拆表 |
| 版本及同時修改 | 用快照、差量或兩者？舊基底拒絕還是協作合併？ | 有版本不等於每次按鍵永久完整快照；兩種作者不等於必須兩個並行副本 |

### 7.2 新近產品與現行框架的直接證據

以下頁面均於2026-09-10實際讀取；未標單頁修訂日的滾動文件不虛構日期，較早文章明列為沿革。

| 來源／日期或狀態 | 官方公開的事實 | 能與不能支持的本案判讀 |
|---|---|---|
| [OpenAI Codex App Server API overview](https://learn.chatgpt.com/docs/app-server#api-overview)，現行滾動文件 | `thread/metadata/update`明示SQLite-backed metadata；thread history另有log／rollout檔案及resume／fork／archive接點 | 是公開的metadata與檔案歷史並用實例，不是ChatGPT Canvas或JD正文的DB schema。頁面部分API另標experimental／deprecated，不一概当穩定採用接點 |
| [OpenAI產品changelog](https://learn.chatgpt.com/docs/changelog)，2026-08-20條目 | Sites可編輯／保存版本、由owner控制恢復；共享Codex thread則是固定歷史快照 | 支持區分工作中內容與可回看版本；Sites內應用自己的資料庫不能當成儲存Sites定義／歷史的內部DB證據。本案不因此引入分享或權限 |
| [Claude Cowork Artifacts](https://support.claude.com/en/articles/14729249-use-artifacts-in-claude-cowork)，頁面顯示本週更新；適用2026-08-19起建立的新系統 | 更新保存新版本，可比較先前版與目前版或恢復 | 是近期AI產物版本行為的直接證據，沒有公開JSON／SQL或完整／差量快照。此系統有方案與設定限制，只作產品參照，不列免費採用依賴，也不概括旧live artifacts |
| [Claude Code checkpointing](https://code.claude.com/docs/en/checkpointing)，現行滾動文件 | 隨對話保存受追蹤檔案快照，能恢復code／conversation；Bash與外部直接修改不在相同追蹤範圍，另有清理界線 | 可學習恢復與追蹤範圍要明示；不是所有人／AI修改都已自動永久保存，更不揭露Claude雲端Artifacts資料表 |
| [Google Docs batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate)，2026-07-07更新；[Drive changes／revisions](https://developers.google.com/workspace/drive/api/guides/change-overview)，2026-07-22更新 | Docs批次驗證及原子套用；`requiredRevisionId`過時拒絕，`targetRevisionId`可整合近期協作者修改；編輯器revision可能合併、API不一定列出全部變更 | 支持版本基底、明確衝突政策及歷史能力；不支持每按鍵永久完整快照。Drive `headRevisionId`僅適用blob，不能拿來證明Docs獨立head表 |
| [AWS REL04-BP04](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_prevent_interaction_failure_idempotent.html)，現行滾動指引；其仍連結的[Builders’ Library重試設計](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)為較早有效原則 | 以同次操作token辨識重試並返回原結果；token紀錄與變更需一致／原子；可用DB或cache等，明列清理舊token／TTL | 支持保存結果與避免重複副作用，不指定三表或永久保存每次attempt。較早但仍在現行官方指引引用的可靠性原則，不因不是2026新發明便判淘汰 |
| [Notion AI架構](https://www.notion.com/blog/speed-structure-and-smarts-the-notion-ai-way)，2025-05-29 | AI使用帶metadata及關係的block結構 | 支持給AI有意義的結構與關係；未揭露JSONB欄位或三表，也不表示採圖形DB |
| [Notion離線工程](https://www.notion.com/blog/how-we-made-notion-available-offline)，2025-12-11 | SQLite持久層；離線可用性用`offline_page`／`offline_action`兩表；可離線頁遷入新的CRDT模型，版本更新通知沿既有快照系統 | 是資料表、引用追蹤及協作模型並用的近期實例。這兩表只管理離線可用性，不能當JD內容表照抄；也不能由此推2026伺服器完整schema |
| [Notion Developer Platform](https://www.notion.com/blog/introducing-developer-platform)，2026-05-13發布時的能力／狀態 | 人與agent使用同一工作面與介面；強調可信共用內容、確定性工具及操作可見性 | 支持AI操作既有App能力，而非因接AI就另建一份正文。文章未公布內部保存表；Workers發布時為public beta，外部agent為候補／private beta，不採其商業服務或推定今日狀態 |
| [Plate Next.js保存示例](https://platejs.org/docs/installation/next)、[Slate保存指南](https://docs.slatejs.org/walkthroughs/06-saving-to-a-database)，現行滾動文件 | 原生value可序列化保存及重載；Slate示例用localStorage展示App保存接點，其他序列化有取捨 | 支持沿原生文件表示，未給JD版本／交易／引用維護完整方案；亦未替本案固定插件組合做驗收 |
| [Hocuspocus Database](https://tiptap.dev/docs/hocuspocus/server/extensions/database)，現行3.x文件 | Yjs狀態保存為binary，載入應取原先保存的狀態；從普通JSON反覆新建Y.Doc會產生新歷史並可能重複內容，可接不同資料庫 | 直接反證所有共編App只存普通JSON便足夠。此限制屬Yjs協作模型，不是Plate非協作value一律不能保存JSON；不因此引入多人／付費功能 |
| [PostgreSQL 16 JSON §8.14.2](https://www.postgresql.org/docs/16/datatype-json.html#JSON-DESIGN)，本案major對應現行受支援文件 | JSON與關聯模型可並用；應有可預測結構，考慮資料單位與整row更新鎖 | 支持混合表示的能力及取捨，沒有替本案選整份JD原子單位。16不是最新major，沿實際版本查契約，不以年份宣稱所有DB應升版 |

**沿革而非2026完整實作：**Notion的[2021 block模型](https://www.notion.com/blog/data-model-behind-notion)公開JSON傳輸、record操作／交易與背景歷史快照；[2023 Postgres擴充](https://www.notion.com/blog/the-great-re-shard)公開工作區內容存於Postgres叢集。兩文支持曾有成熟先例，但前者JSON傳輸不證JSONB存放，後者也不能直接證2026全部底層不變。2025離線文已有新CRDT模型，不能照舊文推定現行衝突處理。

### 7.3 三張表的依據與不可擴張的結論

| 本案設計 | 有證據的效果／工程原則 | 仍屬本案映射 |
|---|---|---|
| `jd_head` | App能辨認目前基底、過時修改不得盲目覆蓋 | 是否獨立head表、放catalog欄位或用框架目前版接點，不是廠商共同規定 |
| `jd_revision` | 保存可回看的前後狀態，能恢復及比較實際內容 | 每次成功且有變更的發布保存完整不可變JD、線性parent、具體保留粒度，是本案設計；不是每個按鍵或每輪AI都產版 |
| `jd_operation` | 執行與回覆分開；相同意圖可對帳，避免回覆遺失導致重複副作用 | 獨立回執表、終局狀態及保留範圍，是本案設計。工具call ID本身不保證外部寫入去重；本表也不保存每個未綁定失敗或所有模型思考 |

OpenAI的[apply-patch harness](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness)要求App執行操作並回傳成功／失敗；**Atomicity段明示由App決定全成全敗或逐檔結果**。這是模型工具邊界的直接證據，不能說OpenAI要求每個App都採本案原子批次，更不能由工具結果推出必須有`jd_operation`表。

Google的版本檢查與Claude的版本回看，支持head／revision所服務的效果；AWS的token與原結果支援operation的可靠性目的。**三者的具體表結構仍由本案選擇。**目前保存契約已把`no_change`限定為不產新版本，`busy`／`unknown`／`operation_conflict`不另寫終局回執，並非逐attempt無差別留存。現候選沒有自動清理revision／receipt；這是本案目前保留政策，不是AWS建議永久保留。若要設定期限，須一併界定可恢復／對帳範圍及已過期操作的處理，不能只刪token後仍承諾永久去重；本輪不默改清理政策。

**本案不是以operation重播還原正文的event sourcing。**目前讀取head指向的完整revision；operation供結果與同次意圖對帳。快照、操作回執與事件溯源不可只憑表名混稱；操作紀錄也不代替底層資料庫WAL。

### 7.4 對現方案的判斷與驗證邊界

仍推薦以原生結構內容＋同PG關聯管理＋完整revision作本版驗證候選。理由是同一份JD為主要閱讀／發布單位、要查實際差異與重開、前景AI與人工互斥，以及不要求離線並行副本自動合併；**不是宣稱JSONB比關聯較新，也不是三表天然最佳**。JSONB內K／S連結驗證責任仍見§4–6，不因大廠使用結構資料便算完成。

若日後要同時手改與AI改、離線多副本、跨文件獨立K／S管理，或量測證明整份快照／候選驗證成本不合需求，才依具體觸發重評CRDT、分塊保存或關聯化；這些新需求不能偷偷塞入本版。先前已列的實際保存失敗、回覆遺失、舊版目標、重開及引用變更情境仍須驗證，文件與shape檢查不能代替實作證據。

本節三路定點來源研究已整合；OpenAI／Anthropic及Google／AWS兩路獨立只讀審查無實質finding。本文、保存契約、主設計及register新增路由的103個本地連結／錨點核對0失敗，限定檔案`git diff --check`通過。此次只有研究／文檔補註，未新增程式測試、schema、資料表、套件或模型實驗。
