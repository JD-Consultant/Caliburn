# Task4 同一 SSOT 因式分解候選 — 待窄 review

2026-09-10。僅 scratch 候選；active SSOT、generated DTO、使用中 API 尚未換版。採用候選為 `task4-schema-candidate2/candidate.schema.json`，不是第一候選。沒有新增依賴、validator、關鍵字實作或 engine。

## 觀測反證與責任

完整 r2 browser current 約 148KB，直接 HTTP 一次 12.79s；瀏覽器開頁 StrictMode 兩次讀取並行時約25s。完整稿保存已執行官方表格增刪列／nested-list Enter，但保存確認首次超出30s測試等待，首敗 `task4-structure-attempt2.json` 保留。較長等待只用來取得實際時序，並不構成效能修正或新產品規格。原 schema 實際後續 response 約22s manual-save、14s current、10s changes；來源回查與結構保存最終有成功回覆，與效能 gate 分開。

`task4-read-profile.json`／`.txt`：cProfile 下 mapper38.909s，JSON Schema JdReadSuccess38.842s，DB0.033s，Pydantic0.0066s，dump0.0047s，FastAPI DTO0.0036s，JSON序列化0.0008s；current read 不呼叫 native。94.6M函式呼叫集中在 recursive properties/items/allOf/oneOf，reference lookup僅3.16s。主要成本不是DB／React／Node，而是同一 saved descendant 在 common children 與 narrower child wrapper 反覆完整遞迴驗證。

## 官方語義與有限變換

[JSON Schema combining](https://json-schema.org/understanding-json-schema/reference/combining) 明定 allOf 為各分支皆真、oneOf 為恰一分支真，並直接說明共同條件可因式分解、遞迴組合可能使成本倍增。这里保留 oneOf，沒有改 anyOf。[官方 structuring／JSON Pointer](https://json-schema.org/understanding-json-schema/structuring#json-pointer) 允許 `$ref` 指向文件中合法 subschema；`/allOf/1` 指向同一 SSOT 中原有的第二個 conjunct，不是另一份 runtime schema。[jsonschema4.26.0 官方 validate API](https://python-jsonschema.readthedocs.io/en/stable/validate/) 仍是相同 `Draft202012Validator`／`validate`／`is_valid`；無 keyword override 或 memoizing validator。

設 E=`JdSavedElement`、T=`JdText`。common children 原本而且候選仍完整要求每項 `oneOf(T,E)`，**不是先假設每個 child 都是 E**。T required text 且 additionalProperties:false，不許 type；E required type/id/children 且 additionalProperties:false。所有本次抽取的 shallow type conjunct 均 required type（BodyElement 間接引用 `JdSavedElementOfBodyType` 同樣 required type）。因此 `(T xor E) AND required-type predicate` 排除 T，才可省去同 child 再次 E 驗證。unknown type、欠 id、欠 children、非法 descendant／metadata 等仍在 common E 失敗。

候選2只改 `JdSavedElement.allOf` 下15個既有 narrower child 引用。一般 wrapper 改指既有 `/allOf/1`。Task／Knowledge／Skills 三個 child oneOf **僅在此已受common children約束的context** 提出共同 E，改為由原各 wrapper `/allOf/1` 組成的 oneOf。其 standalone defs 完全不變，沒有在獨立驗 wrapper 時放寬。

| 父型別／位置 | common部分仍保證 | 剩餘 type／position grammar |
|---|---|---|
| p/h1/h2/h3/lic | 非空array；T或E完整驗證 | 原 items JdText 不變（marks/text/額外欄位照舊） |
| hr | 非空array、child完整 | 原 JdEmptyText、min=max1 不變 |
| ul/ol | 每 child完整T或E | ListItem shallow required type=li，排除T |
| li 第一項 | child完整T或E | prefixItems ListContent shallow required type=lic；minItems1不變 |
| li 後續 | child完整T或E | items List shallow required type∈ul/ol |
| table | child完整T或E | TableRow shallow required type=tr |
| tr | child完整T或E | TableCell shallow required type∈td/th |
| td/th | child完整T或E | CellChild shallow required type∈p/ul/ol |
| blockquote | child完整T或E | BlockquoteChild shallow required type∈p/h1/h2/h3/ul/ol/table/hr |
| jd_task items | child完整T或E | oneOf BodyType／required type=jd_outcomes／required type=jd_requirements；三分支type集合不交疊 |
| jd_task 數量 | 原array約束仍在 | minItems3；outcomes/requirements各contains恰1不變；body contains改用原BodyType required type，仍至少1 |
| jd_duty | child完整T或E | DutyChild required type∈BodyType或jd_task |
| jd_section work | child完整T或E | WorkSectionChild required type∈BodyType或jd_duty/jd_task |
| jd_section knowledge | child完整T或E | oneOf BodyType／KnowledgeItem required type=jd_knowledge |
| jd_section skills | child完整T或E | oneOf BodyType／SkillItem required type=jd_skill |
| jd_section 其他kind | child完整T或E | BodyType required type；原section_kind required與enum不變 |
| jd_outcomes/requirements/knowledge/skill | child完整T或E | BodyType required type；原minItems1不變 |

BodyType仍是p/h1/h2/h3/blockquote/ul/ol/table/hr。共同 E 的所有 required、additionalProperties、id、source_refs、section_kind、table/row/cell欄位、K/S ids及type-specific欄位placement均原樣。原 JdNewElement完全未改；native grammar／ID／K/S關係檢查及 App source owner 全未改。

## 兩輪結果，首敗不改判

候選1改寫了三個 standalone oneOf wrapper。438個語言對照皆相等，r2由3.814s降至0.091s；但 datamodel-codegen0.71.0 對這種 allOf+oneOf 因式式產生過寬且缺分支的 Python union。**候選1不採用。**其 schema/diff/DTO差異完整保留在 `task4-schema-candidate/`。第一個scratch TS alias helper另有反斜線誤植造成duplicate alias，屬驗收腳本錯誤；第二腳本與原 codegen options一致修正，與Pydantic生成反證分欄。

候選2：438個原／新schema結果全等；保留三個完整fixtures、190 saved elements、逐parent malformed descendants、未知type、required/additionalProperties/metadata、兩Task groups數量、各standalone wrapper正反例。第二輪old結果沿用同hash第一輪原schema既有結果，沒有重跑同組。另補92個old/new實跑：合法純Text誤放每個結構父型別與各wrapper、unknown type、task body／list prefix不能是純Text、required缺欄及原forbidden score fixture；全符合預期。見 `equivalence-results.json` 和 `supplement-results.json`。

無profiler完整r2 JdDocumentValue：原schema3.8138109s；候選2 0.0891823s。此為同一Python runtime／同fixtures／同official validator的schema計時，**不是更新後browser/HTTP保存效能聲稱**。採用後仍需重建API（validator有lru_cache）、跑HTTP/profile/native受影響回歸與完整稿browser驗收。

## 生成型別獨立核對

現有 codegen wrapper source 固定active路徑，候選採同已安裝 json-schema-to-typescript15.0.4 compile及datamodel-codegen0.71.0，逐項相同options，輸出僅scratch。`task4-candidate-codegen2.mjs`／`codegen-invocation.json` 記實際呼叫。沒有更換active入口或手改DTO。

候選2生成TS與active逐byte相同；actual API export生成TS逐byte相同；Python只差datamodel-codegen來源basename註解，所有程式碼逐byte相同（`py.diff`僅1行）。candidate DTO實際匯入路徑記於 `actual-dto-import.txt`／`supplement-results.json`，確實在candidate2/src下，非editable舊包。完整r2經該DTO roundtrip exact value通過。**語言對照PASS與生成等價PASS分開證明。**

原schema SHA256：`f8a8a5841945b959e578ac2462a5d111b428f0ed2b3e6d80a5768cbc3a695311`。

候選2 SHA256：`893fdb43fe2696846e74f15f2b5e12ed97a00f5ff1a5bc667c11ce734d7430fc`。

範圍限制：此有限corpus不是無限JSON語言的形式證明；上面依官方語義與逐wrapper required-type implication 才是等價推導，corpus是反例檢查。原本schema以外的cross-reference／source authority invariant不由本變換重算。候選待root窄review通過才可落入active SSOT並生成正式產物。
