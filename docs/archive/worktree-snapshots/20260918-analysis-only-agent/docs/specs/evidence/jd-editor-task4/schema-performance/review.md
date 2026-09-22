# Task 4 candidate 2 schema 有限獨立審查

2026-09-10；reviewer：jd_task4_review；Topic JD-R002/C03，隔離 G7／Task 4。

**Spec PASS；quality APPROVED，可採用 candidate 2 到隔離 Task 4。沒有阻擋 finding。**此 verdict 只涵蓋指定 schema 因式分解候選與生成等價；不代表 Task 4 全部實作、更新後 HTTP／browser 效能或 production 採用通過。

## 審查範圍與材料

沿 `task-4-schema-review-brief.md`，讀取 `task4-schema-factorization-candidate.md`、`task4-schema-candidate2/review-normalized.diff`、候選被引用的完整 definitions／common children、438 個 `equivalence-results.json` 與 92 個 `supplement-results.json` 的既有結果、生成 helper／invocation／actual import 及 TS/API/Python diff。另核對現有 contract codegen options，未讀 Task 4 施工中的 Web/API implementation。沒有重跑 corpus、套件安裝、模型或 DB 呼叫。

實際重核 SHA256：before `f8a8a5841945b959e578ac2462a5d111b428f0ed2b3e6d80a5768cbc3a695311`；candidate `893fdb43fe2696846e74f15f2b5e12ed97a00f5ff1a5bc667c11ce734d7430fc`，與 root 凍結值一致。root 已另核 before 為 active byte-exact，且移除唯一定義 JdSavedElement 後整份 JSON 相同。有限 diff 顯示只改該定義 conditional child grammar 的 15 處引用位置；未改 standalone wrappers、new element、工具 input 或其他 wire defs。

## 邏輯與邊界

官方 `allOf` 是所有 subschema 同時成立，`oneOf` 是恰一分支成立；官方亦提供共同條件提取示例並提醒遞迴組合成本。這次定點複核來源支持所用布林規則，不把它冒稱為官方已證明 Caliburn schema。[JSON Schema combining](https://json-schema.org/understanding-json-schema/reference/combining)

令 T 為 JdText、E 為完整 JdSavedElement、P 為被抽取的 type conjunct。common children **仍是 oneOf(T,E)**，並非只含 Element。逐個核實：T 是 object、required text、additionalProperties:false，因此不允許 type；每個 P 都是 object 且 required type，BodyElement 的第二 conjunct 經 JdSavedElementOfBodyType 間接具相同條件。故在 common children 已成立的 context，P 為真必然排除 T、保留完整 E。舊式 `oneOf(T,E) ∧ (E ∧ P)` 與候選 `oneOf(T,E) ∧ P` 在該位置相等。

這個推導可按有限 JSON tree 的 descendant 深度歸納：leaf 規則未改；下一層 common child 仍遞迴驗完整 E，conditional 只省略同 child 的重複 E，不省略下一層自身的 grammar。沒有改成空 schema、停止遞迴或倚賴「properties:type 即存在 type」的錯誤前提。未知 type、欠 id/children、非法後代、額外欄位／marks／source_refs／K/S metadata 仍由 common E 及未變的 placement 規則拒絕。

| 改動位置 | 審查結論 |
|---|---|
| ul/ol、li prefix／items、table、tr、td/th、blockquote | 原各完整 wrapper 恰是 allOf(E,P)；候選 `/allOf/1` 指向原 P，required type 與 type 集合逐項吻合。li 首 lic、後續 ul/ol，表格與引言位置不放寬；prefix/minItems 未變。 |
| jd_duty、work section、一般 section、outcomes/requirements/knowledge/skill body | 同樣只省重複 E；允許 type 集合沿原 conjunct，section_kind 與其他欄位規則未變。 |
| jd_task items、knowledge section、skills section | standalone oneOf defs 保留。context 內 oneOf 各分支抽去共同 E，仍保留 oneOf；BodyType 與相應專屬 type 不交疊，恰一分支語義保持。 |
| jd_task contains body | 所有 children 先通過 common E/T 且 items 的 shallow oneOf 排除 T，因此在 contains 中 E∧BodyType 可改為 BodyType；至少一 body、恰一成果／要求、minItems3 未改。 |
| p/h1/h2/h3/lic、hr | 原 Text／EmptyText 及 hr min=max1 不變；空 leaf marks 不因本次變換遺失。 |
| standalone wrappers | 均保留完整 E＋type 或原完整 oneOf，單獨驗證仍驗所有後代；candidate 1 的生成問題沒有帶入。 |

JSON Pointer 的各 `/allOf/1` 均落於實際 subschema；BodyElement 該位置為合法 `$ref` schema。候選只有既有 root `$id`，未引入 nested base URI、dynamic ref 或 unevaluated* 對 annotation 的依賴。引用同一 wrapper 的 conjunct 可維護，但其 array 位置、required type 與 common children 保證是後續修改時必須一併核對的前提；現有設計／候選報告已明列，無需另造 grammar。[JSON Schema structuring](https://json-schema.org/understanding-json-schema/structuring)

## 生成與證據

- 核對生成 helper 與 contract 現有 options 相同：固定 json-schema-to-typescript compile／alias 補出規則、datamodel-codegen 參數及換行處理；所有候選產物在 scratch，沒有手改 wire。
- candidate TypeScript 與 active TypeScript SHA256 均為 `6376d46cb72b80f4e5e277604269e1dd0153772565191a22f5bbf1033c9ad626`，逐 byte 相同。`api.diff` 為空，API export 等價依據是候選 helper 所呼叫的實際 export 結果；本 reviewer 未讀其正在施工的 API implementation。
- `py.diff` 僅 `filename: jd-editor-v2.schema.json → candidate.schema.json` 註解；實際比對去除此差別後全文相等。candidate DTO import 紀錄確在 `task4-schema-candidate2/src/jd_editor_contract/models.py`，helper 將該路徑放在 PYTHONPATH 首位；補充結果記完整 r2 DTO roundtrip exact。沒有把「codegen exit 0」單獨當成生成語義證明。
- 對既有結果作唯讀統計：438 原／候選判定與 expected 零不一致；補充 92 個亦零不一致，特別含純 Text 錯放結構位置、各 wrapper、task body／list prefix、缺 required、unknown type／非法 score。438 組 old 結果沿同 hash 第一輪保存，未假稱第二輪重跑；兩份結果集只作有限反例檢查，不代替上述結構推導，也不稱全部情境 formal proof。
- 3.8138109 秒與 0.0891823 秒是報告同 runtime／同 fixture、不帶 profiler 的單段 schema 計時；before 計時沿已保存同 hash 結果。不能外推 p95、整體 HTTP／保存／browser 延遲。cProfile 38.842 秒與未 profile 12.79 秒不作前後性能比較。
- 候選 1 的 438 對照通過但 Python union 過寬／缺分支，仍保持「不採用」；其生成反證與早先驗收 helper 首敗不改判。

## Closure 與下一 gate

此有限範圍無需補新的反例或重跑 corpus，可停止 schema 候選研究。採用後仍須 active SSOT 生成／check-codegen、官方 AJV/native 與受影響 API/Web 回歸，並重建持有 cached validator 的 API 後驗完整 r2 HTTP、表格／子清單保存及重開；這些是既有 Task 4 接線驗收，**本次未執行、不代為勾選**。App 的 ID／K/S 關係／source authority invariant 不被本變換替代。

只新增本審查報告，無 code／git／production 修改、零付費。root 負責同步 durable evidence／register 與採用候選。Task 4 full implementation review 仍待最後 freeze；Task 5／6 與 OS IME NOT RUN 等原邊界不變。
