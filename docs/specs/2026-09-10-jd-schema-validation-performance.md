# JD 完整稿的契約檢查效能補核

2026-09-10；JD-R002/C03，隔離Task4。**候選2經獨立Spec PASS／quality APPROVED，採用於隔離Task4；活動接線回歸尚未完成。** production仍依ADR0060；本項不改文件authority、格式版本或既有模型／Memory政策。首輪候選及未採用時的文字在原始證據保留。

## 觀測與限制

真瀏覽器使用完整r2時，本機current讀取觀測約12.79秒／148KB，部分結構修改保存超過30秒驗收等待；短稿可走通。30秒是該次測試等待，不是新產品SLO，也不能只延長等待就宣稱效果成立。

[原始分段資料](evidence/jd-editor-task4/schema-performance/task4-read-profile.json)及[cProfile](evidence/jd-editor-task4/schema-performance/task4-read-profile.txt)將熱點定位為重複遞迴的JSON Schema檢查：mapper38.91秒，其中`JdReadSuccess`檢查38.842秒；DB0.033、Pydantic0.0066、dump0.0047、FastAPI DTO0.0036、JSON0.0008秒，這次read不啟native。cProfile增加執行成本，不能將38.91秒與未profile的12.79秒當同一條件比較。

本案診斷：`JdSavedElement`通用children已完整驗`oneOf(JdText,JdSavedElement)`，各父type的conditional grammar再經完整wrapper重複檢查同一子樹，造成遞迴倍增。不是DB、JSON傳輸或registry查找的主要瓶頸。

## 官方事實與本案映射

查閱日2026-09-10；沿既定Draft2020-12、jsonschema4.26.0／AJV8.20.0及固定生成器，不新增依賴。JSON Schema官方說明`allOf`為所有分支皆滿足、`oneOf`為恰一分支；提醒遞迴組合可能使處理時間倍增，並示範將共同條件提出的等價寫法。這支持以同一契約整理重複條件，**不直接證明本案任意改寫都等價**。[官方組合語義](https://json-schema.org/understanding-json-schema/reference/combining)

官方允許用JSON Pointer識別子schema，`$ref`依該schema語義套用。本案候選在已具完整child檢查的特定context引用現存wrapper的type conjunct；必須核對指向、required與排他條件，不能把只有限制某property誤當成該property必定存在。[官方模組／引用語義](https://json-schema.org/understanding-json-schema/structuring)

尤其通用children可接受Text，並非所有child已是Element。每個shallow type conjunct必須保留排除Text／缺type的條件；父子位置、長度、marks、source_refs與K/S metadata仍按原grammar，App的ID／關係／來源檢查仍由原owner負責。獨立使用的完整wrapper也須保持。

## 候選與下一gate

- **候選1：不採用。**438個固定old/new判定相同，單段完整r2未profile檢查由3.814秒降至0.091秒；但將3個standalone union wrapper共同條件提出後，固定datamodel-codegen0.71.0生成更寬且缺分支的union。Schema判定等價不代表生成型別等價，首候選及反證須保留。
- **候選2：有限review通過，採用。**standalone wrappers保留，只在通用child已檢查的conditional grammar context整理重複檢查。438個對照及92個補充反例一致，單段0.089秒；TypeScript與API export逐byte相同，Python僅輸入檔名註解不同，實際candidate DTO import／完整r2往返已核。root另核採用前活動SSOT與before逐byte相同，除`JdSavedElement`外整份JSON完全相同。這些是候選單段結果，尚不是App整體延遲驗收。

[候選報告及逐父子推導](evidence/jd-editor-task4/schema-performance/task4-schema-factorization-candidate.md)、[有限候選2差異](evidence/jd-editor-task4/schema-performance/task4-schema-candidate2/review-normalized.diff)與[37檔原始證據manifest](evidence/jd-editor-task4/schema-performance/manifest.json)保留兩轮候選、生成差異與反例，未覆蓋首敗。候選2 SHA256為`893fdb43fe2696846e74f15f2b5e12ed97a00f5ff1a5bc667c11ce734d7430fc`；before為`f8a8a5841945b959e578ac2462a5d111b428f0ed2b3e6d80a5768cbc3a695311`。有限corpus不等於所有JSON的形式證明，採用仍須獨立核對條件交集與生成效力。

[獨立窄review](evidence/jd-editor-task4/schema-performance/review.md)確認逐父型別、Text排除、contains與oneOf的條件交集以及生成結果，無阻擋finding；本題停止候選研究。原實作者把核准候選寫回同一活動SSOT，官方重新生成、重建有validator cache的API，再做受影響contract/native/API/Web驗收。完整r2 HTTP、表格／子清單保存與重開須在實際App回驗。Task4最後仍有完整凍結實作審查；不造custom validator、不放寬資料grammar、不換framework、不混用活動與scratch schema。後續調整wrapper的allOf次序／required type或common children時，須一併核對本次推導前提。

原profile兩檔SHA256：JSON `2d524ce7c871e73e4f6a8db048283ee11130a4c89238874990d0f9d1c027b92e`；TXT `24d78369099740c0b08df70b39cda76ea44f5d794fc1210c96c9f2b32b13f46c`。候選raw與有限review結果在完成時併入Task4正式證據；當前不得將候選數字改寫成成品通過。
