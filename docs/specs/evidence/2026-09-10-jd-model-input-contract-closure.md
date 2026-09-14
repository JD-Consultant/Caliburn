# JD 模型輸入減負：TF02／TF03 契約閉合依據

日期：2026-09-10。Topic：JD-R002/C03；屬 Owner 已同意的有限契約補正。責任文件仍是[工具契約](../2026-09-10-jd-app-tool-contract.md)、[正式 profile](../2026-09-10-jd-plate-document-profile.md)與[schema 附件](../2026-09-10-jd-editor-contract-schema.md)。本文固定 TF02／TF03 的依據、選擇與驗收材料；不改變 Plate、單份持續工作稿、來源 owner 或既有保存邊界。

## 1. 已讀證據與效力

| 證據 | 直接證明 | 本案映射與界線 |
|---|---|---|
| [OpenAI function calling：Best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)，本日由官方 docs 工具重新 fetch | 模型不必填 App 已知的參數；能由程式處理的負擔交給程式；透過物件／enum 避免矛盾狀態；用途、參數、結果含義須清楚 | numeric／HTML 重複表示與引用聯集可由程式處理。官方沒有指定 JD span 或引用契約；這是 Caliburn 的工程映射，亦不以工具數量建議宣稱跨廠共識 |
| [Anthropic tool definitions](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions)，沿[先前已 fetch 的官方核對 §2.13](2026-09-09-jd-app-tool-and-review-contracts.md#213-契約定稿前的官方複核參數結果版本與重試) | 工具描述須說明用途、參數與限制 | 支持將「保留引用不等於重新核實」和 unset 邊界写進模型指引；未公開同一 JD 實作 |
| 固定 `@platejs/table@53.0.9`：[官方 npm tarball](https://registry.npmjs.org/@platejs/table/-/table-53.0.9.tgz)、[已封存 registry metadata](jd-official-profile-probe/sources/registry/@platejs__table.json) L29／L94 | `gitHead=79578fd8ef53237edfc78389594df3ed5c722277`，版本 53.0.9，MIT | 採用組合由正式 profile 的 exact lock 固定；不是把所有 Plate 子套件都誤稱 53.3.11，也不是查最新版後擅自升級 |
| [實際官方 npm dist](jd-official-profile-probe/sources/installed/@platejs__table/constants-6xljcM3U.js) L4–10、L38–53 | 新空 cell 不強制存 span；getter 依 `numeric || Number(attributes小寫欄位) || 1` 取值 | 省略兩種表示時有效值是 1。只 unset numeric 並不能保證回到 1；殘留 HTML 值仍可能生效 |
| 同一 [dist](jd-official-profile-probe/sources/installed/@platejs__table/constants-6xljcM3U.js) L1176–1182／L1289–1295 | 官方插欄／插行遇到跨格時，更新 numeric；只有既存對應 HTML key 時一起改成字串，再以 `setNodes` 寫入 | 採相同的有限欄位映射。不能由此宣稱裸 `setNodes({colSpan:n})` 會自動同步 attributes |
| 同一 [dist](jd-official-profile-probe/sources/installed/@platejs__table/constants-6xljcM3U.js) L1331–1377／L1383–1404 | 原生 merge／split 會處理 cell 集合並建立 cell；split 新 cell 明示 numeric span 為 1 | 單一 cell property 的 set／unset 不等於 merge／split，不讓 App 另造表格格線引擎 |
| [正式 profile §4](../2026-09-10-jd-plate-document-profile.md#4-身分移動拆分複製與引用)、[工具契約 §8](../2026-09-10-jd-app-tool-contract.md#8-source-reference-與更正-lineage) | 既有本案要求：移動保留 subtree；unwrap 取消容器、保留子內容；引用只表示曾參考，不替續改文字重新背書 | 引用附著是模型的語意選擇；App 只做同文件／既發 handle／來源窗口等機械檢查，不從正文猜引用 |

官方 dist 與 `.research-tmp` 中原封存副本 SHA256 同為 `ACE1A1A1A785FE2E4D3758C82E63991AEE265D00688571BBB603B35A6D193ABF`；[source manifest](jd-official-profile-probe/sources/installed-source-manifest.json)記錄其為實際安裝 npm dist，無 vendor patch。本輪據這份已保存的精確版本原碼判斷；GitHub／raw 網路補取未成功，不將未取回頁面另算已讀證據。

## 2. 兩個選項與選定責任

| 選項 | 做法 | 取捨 |
|---|---|---|
| **A：採用** | 模型僅填 numeric span；App 同步既存 HTML 表示。`jd_edit` 移除頂層 `source_refs`，只在新節點或明示 `set_properties` 填附著引用，App 機械收集聯集 | 減少重複輸入，保存 shape 不變。文字替換若要新增引用，需同批明示屬性更新；不另外承諾記錄模型所有查閱過的來源 |
| B：保留原輸入、強化描述與一致性檢查 | 模型仍能填兩種 span，以及頂層／節點兩層 sources；另定每層用途 | 可以保留獨立操作依據，但模型仍承擔衍生資料與集合一致性。現有需求沒有要求完整 consulted-source log，不為此保留重複欄位 |

「實際附著哪些引用」仍由模型決定；App 不能把本輪全部已讀來源、自動捕捉的員工輸入或父群組引用撒到所有改動節點。引用聯集是可推導的驗證材料，不是 App 代替模型判斷哪些原話支持某句文字。

## 3. TF02：單一 span 意圖與保存映射

模型 new-element／properties 只接受 `colSpan`、`rowSpan` 正整數，不接受 `attributes`。保存的 `JdSavedElement` 仍可保留既有合法 `attributes.colspan/rowspan` 正整數字串；兩種表示同時存在仍須相等。

App 的固定 Node adapter 在 disposable editor 中依命令順序取得**當時目標 cell**，用原生 `setNodes`／`unsetNodes` 完成以下映射，不能每次從批次最初 base 回填舊 attributes：

- 新節點省略 span：不補造欄位；原生有效跨度為 1。明示 1：保留 numeric 1，並非要求執行 split。
- existing `set:{colSpan:n}`：存 numeric n；若當時已有 `attributes.colspan`，同步為 `String(n)`；沒有該 key 就不另外生成。rowSpan 對稱處理。
- existing `unset:["colSpan"]`：移除 numeric `colSpan` **及**對應 `attributes.colspan`。保留 attributes 中未指定的另一維；若物件因此為空則省略整個 `attributes`。rowSpan 對稱處理。
- 命令未提某維，該維所有既有資料保持不變。不能以 `null`、0 或負數表示預設／清除。
- 這是表示層映射，不自動增刪鄰格、搬內容或猜合併意圖。仍依既有固定 profile／原生操作驗完整 table；若候選不符合 grammar／grid 就整批拒絕、零發布。

三個必要例子如下；只展開 span props，其餘合法 cell 的 type、id、children 及其他 props 均保留。

| 輸入與基底 | 預期保存 span props | 有效值與驗收重點 |
|---|---|---|
| 新 cell 未填 span；另比較新 cell 明示 `colSpan:1` | 前者省略 numeric／attributes；後者保留 `colSpan:1`，不造 attributes | 兩者原生有效 colSpan 均為 1；保存表示未必全值相同，不用清洗把二者強制合一 |
| 基底 `{colSpan:2,rowSpan:2,attributes:{colspan:"2",rowspan:"2"}}`；set `colSpan:1` | `{colSpan:1,rowSpan:2,attributes:{colspan:"1",rowspan:"2"}}` | 對應字串同步，另一維不變；示例只證映射期望，完整表格仍須合法 |
| 同一基底；unset `colSpan` | `{rowSpan:2,attributes:{rowspan:"2"}}` | colSpan 回到有效 1，舊 "2" 不復活；若原 attributes 僅 colspan，整個 attributes 省略 |

必改 definitions：`JdNewElement.properties.attributes` 及其 type 限制中的冗餘 attributes 分支、`JdEditableProperties.properties.attributes`、`JdUnsettableProperty` 的 attributes 成員。`JdResolvedEditCommand` 透過共用 definitions 同步縮小；不要為 Python→Node 再複製第二份模型屬性集合。`JdCellAttributes`、`JdSavedElement`／所有 saved read／manual value 保留。TF01 的 set／unset 衝突檢查須對剩餘可編欄位生效；模型不能透過 attributes 別名繞過。

必改文義：工具契約 §4、profile §3 的「保存表示」與「模型意圖」分界、schema 附件 §2–4／§7、Task 1 的 props adapter 與表格例子。全值／原生 operation 的保存表示沿既有設計，不新增 codec、通用 importer 或自製 table engine。

## 4. TF03：引用只輸入在實際附著位置

`JdEditModelInput` 只含 `commands`。模型在 `insert_content.content` 的 Element metadata，或 `set_properties.set.source_refs` 提供要附著的引用。Python 遞迴收集本批**明示提交**引用的去重聯集，沿既有來源 owner 核對，不要求模型另填一次頂層集合。不同節點若確實要附同一來源，仍各有其 metadata；這是不同附著位置，不能為減少字串而抹掉必要語意。

| command／意圖 | 目前文件中的引用結果 | App 與歷史責任 |
|---|---|---|
| `insert_content` | 各新 Element 只帶模型在該位置明示的 refs；省略就沒有新附著 | 驗已發配來源，配新 ID；不自動繼承父／相鄰／本輪所有來源 |
| `replace_block_content`／`replace_selection` | 外層原有 metadata、refs 保留；只換支持的文字／marks | 保留不代表重新核實。要新增／改掉依據，在**同批**以該 element 的已發配 target 做 `set_properties` |
| `set_properties` | `set.source_refs` 明示替換整個陣列；省略該欄保持原值；`[]` 清空陣列，`unset:["source_refs"]` 移除可選欄位 | 需要保留舊 ref 時，set 陣列中明列舊 ref＋新 ref。引用前後與正文差異一樣可查；TF01 禁止同命令又 set 又 unset |
| `move_content` | 完整 subtree 及各節點 refs 隨原 ID 保留 | 不套用目的父群組的 refs，不重新背書 |
| `unwrap_group` | 子節點、標題正文、各自 ID／refs 保留；明示取消的外層容器及其 own refs 不再存在於 current | 外層 refs 隨 immutable before 保留，歷史可回查；不自動複製為各子節點依據。如確實應附在某個仍存子節點，模型先在同批明示 set_properties，再 unwrap |
| `remove_content` | 明示 subtree（含其 refs）退出 current；其他節點 refs 不變 | 保留 exact before／after、原 operation 與員工 input／message binding；不刪 canonical 原文／Memory，也不連帶清掉其他節點上的同 ref |

新增、文字替換與取消分組的代表模型輸入：

```json
{"commands":[{"type":"insert_content","target_ref":"issued-target","placement":"after","content":[{"type":"p","source_refs":["issued-source"],"children":[{"text":"依已確認的條件執行檢查。"}]}]}]}
```

```json
{"commands":[{"type":"replace_block_content","target_ref":"issued-paragraph","content":[{"text":"僅對約定服務執行每月檢查。"}]},{"type":"set_properties","target_ref":"issued-paragraph","set":{"source_refs":["issued-old-source","issued-new-source"]}}]}
```

```json
{"commands":[{"type":"set_properties","target_ref":"issued-child-task","set":{"source_refs":["issued-child-source","issued-group-source"]}},{"type":"unwrap_group","target_ref":"issued-duty"}]}
```

這些 ref 字串僅作形狀示例；執行驗收必须從實際 read／既有來源入口取得，不能硬寫假 ref 跳過發配檢查。第三例只有在模型判斷群組來源適合該 Task 時使用；App 不推斷此關係。

上述 unwrap 不違反「未指定內容保留」：被明示移除的是 wrapper，標題／子正文與其 own metadata 全值保留，wrapper 原 metadata 保存在 before 歷史。若使用者意圖是保留該群組本身，就不能選 unwrap。不能把取消容器解釋成刪子內容，也不能為「保留引用」把父來源默默改成每個子句的背書。

**union 的語意限制：**它是本批明示附著引用的集合，不是模型查過的一切來源、所有刪除／移動理由或事實證明。繼承保留的舊 refs 不因模型本批未再提交而被清除；既有 owner／scope 規則不變。`jd_read`／`jd_change_read` 的 sources 由實際文件或返回的前後片段推導，不能標成模型完整 consulted-source log。operation 仍由原 employee input／message binding 與 exact before／after 回查，不新增推理記錄或第二份來源庫。

必改 definitions：移除 `JdEditModelInput.required`／`properties` 的頂層 `source_refs`，保留 `JdSourceRefs`、`JdNewElement.source_refs`、`JdEditableProperties.source_refs` 和 saved／read／change-result 引用表示。`JdEditRuntimeRequest` 與 provider `$ref` closure 由 SSOT 機械更新；Node 仍不解析來源 owner。不增一份需要模型填的 runtime union。

必改文義：工具契約 §4.1／§4.2／§8、profile §4、schema 附件的 edit 概述／digest／JSON 正例／embedded subset 不變量，以及 Task 3.1 的固定文字替換例。digest 依 exact validated commands 計算，內嵌 refs 已在 commands 中，不能繼續要求已刪欄位。原「內嵌 refs 必為頂層 refs 子集」改為 App 收集並驗明示 refs；來源語意與發配責任仍保留。

## 5. 必要驗收與本輪未證明事項

schema 層須拒絕新元素 attributes、set attributes、unset attributes 及 edit 頂層 source_refs；正確 numeric 與上述三個 commands 例應通過形狀驗證。保存層原合法 HTML attributes 仍應通過；不是把模型減負誤作保存格式破壞。全 closure 與 provider renderer 由同一 SSOT 重生，先前 frozen schema／placeholder 序列化通過不自動涵蓋本次變更。

接線驗收須包括：三個 span 例的完整合法 table／重開；只有 HTML key 的舊 cell set／unset；兩個連續命令分別改兩維不復活舊值；同一來源附在兩個新節點；文字替換不清 refs；明示替換／清除 refs；移動／unwrap／刪除保留未指定內容與歷史回查；無效来源導致整批零發布。這些是必要有限情境，不要求新增泛化推理／引用／表格引擎。

本文完成官方文件與精確本機原始碼核對、契約映射及驗收規格；沒有執行新的原生 probe、source-owner／DB／Web 接線或自然模型測試。schema／離線反例實際結果由本輪補正主工作另記，不能用本文當作那些實測已通過。
