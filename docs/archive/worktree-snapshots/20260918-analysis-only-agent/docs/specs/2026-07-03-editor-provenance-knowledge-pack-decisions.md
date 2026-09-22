# 決策紀錄:來源標記原則 + 知識包架構 + 編輯器 review findings 處置

- **日期**:2026-07-03
- **類型**:findings + 決策(與維護者逐項討論拍板);落實各開 plan,架構項另開 ADR
- **範圍**:web/api/ocs-indexer 全面 code review 的發現、來源標記原則、knowledge 抓取架構
- **總則(維護者)**:**不用過度設計**——只做「沒有它就是錯」的部分;優化類一行記縫,不進 plan。

---

## §1 原則(維護者拍板,約束所有後續設計)

1. **所有資料必標來源**:官方值 → 帶來源(實作統一 `SourceRef`/`_ref`);非官方 → 標「自訂」(無來源)。
   底層機制不拘,能統一就統一。
2. **例外:工作描述、NOTE(建議條件/補充)** → **素材庫模式**:選單列官方候選(選單內必為官方,
   引用行顯示來源),**點一下直接添加成文字**;存下後就是使用者的話——純文字、不存來源、不標 badge、
   無勾選狀態。防呆(同文字不重複加)**先不做**。
3. **三層職責**:indexer =「只給資料」;api =「資料處理」(聚合/投影/標來源都在後端);
   web = 只讀 + 編輯文件。
4. **選職類 = 唯一 knowledge 同步點**:PUT occupations 後一次抓齊,之後 web 對 indexer 資料
   零請求(特殊功能除外:目錄搜尋、findSimilar/dedup、`/ai/*`)。

## §2 身分/顯示/來源 三分(既有 2b 原則的完整化)

| 概念 | 是什麼 | 存嗎 |
|---|---|---|
| 身分 | `provenance`(任務)/ `_ref`(項目)= 來源座標 {ocs_code, code, task_code…} | ✅ 存,永不重編 |
| 顯示 | 文件位置碼(T1.1/O1.1.1/K01,按位置重編)| ✅ 存(文件內容) |
| 鍵/引用 | URN `ocs:{code}:T:{task_code}`(座標的字串形態,indexer `api/urn.py` 格式) | ❌ 不存,用時現組 |

- **選單顯示(W1)**:官方候選選單**不顯示 OCS-local 碼**(A01/K01/O1.1.1/T1.1)——改序號
  `1. 2. 3.`(依當前清單位置現算,純顯示屬性,不入資料);來源資訊由引用行(SourceLine)承載。
  選進文件後照常顯示文件位置碼,表格/匯出不動。
  依據:NN/g 啟發式 #2「系統應說使用者的語言,而非系統導向詞彙」;OCS-local 碼即系統詞彙,
  對使用者無意義(維護者:「有引用所以知道來源」)。NN/g 下拉選單專文未針對代碼顯示(誠實記)。
  範圍:FieldCombobox 候選清單(K/S/O/P/A/notes)+ 選任務面板(T1/T1.1→序號);
  **DocHeader 類別選單除外**(職類別/行業別代碼是真實國家分類碼,會寫進表格代碼欄,有意義)。

## §3 表頭互動規則(維護者拍板)

- **職能基準代碼 + 名稱(職類/職業)**:單選;選官方 → 代碼+兩名稱綁定帶入、**三格鎖編輯**;
  要自訂唯一路徑 = **✕ 清空**或**選單再點已選項取消**(toggle-off)→ 三格空白 → 手打。
  不能加列。(現況缺:✕、toggle-off、清空後代碼可手打。)
- **基準級別 / 任務級別**:**只能選單、不可手打**(數字範圍 1–6 選單已全列;手打路徑僅屬
  基準代碼/名稱);單選;**再點已選值 = 取消**(回 null);選中值命中官方 → **存 SourceRef**
  (`_levelSrc` 型,`_` 前綴 export 剝);選非官方數字 = 自訂值,無來源。
- 敘事欄(工作描述)與 NOTE:§1.2 素材庫模式。

## §4 Review findings 處置(2026-07-03 拍板)

| # | 發現 | 處置 |
|---|---|---|
| A1 | per-task catalog 快取鍵=位置碼,結構性編輯後錯位(顯示別的任務的候選;違反 2b「位置不當身分」) | **修:鍵改 URN**(api 批次回應鍵 + web 快取鍵 + PERSIST_BUSTER bump)。先行做,pack 原生鍵沿用 |
| A2 | `ai.py::_task_candidates` grounding-id 跨職類撞號 | 已知,併未來重寫(維護者先前拍板) |
| A3 | NOTE 勾選判定壞(string[] round-trip 丟 `_src` → 勾不亮、重點重複加、全列標自訂) | **廢除勾選語意**,改 §1.2 素材庫模式(修法即設計) |
| A4 | 編輯器 K/S 編號 per-task(`renumberCoded("K")`),違反 ocs-schema「**文件層級去重**:name 為 key、同名共碼、所有任務引用同一代碼」——同碼不同物/同物不同碼,匯出不合官方格式 | **修:K/S 改文件層級重編**(name→碼對照表,首現給號、同名共碼;O/P 維持任務範圍、A 維持全域)。代碼共用、身分(`_ref`)各自 |
| A5 | `header_meta._merge_pairs` 全池用 code 優先 key——**態度的碼是文件自編(A01…),跨職類必撞**:X 的 A01 與 Y 的 A01(不同名)被錯誤合併、來源張冠李戴 | **修:per-pool 去重 key 明文化**(§5.1 key 表);態度改 name key |
| B3 | `InterruptHandlers.tsx` 無頁面掛載 | 保留(ADR 0020:候選材料,訪談引擎立項時重評) |
| B4 | `_levelSrc` 無人寫入 | **翻案:接線**(來源必標原則)——選官方級別時寫入 |
| B5 | ocsDoc 7 個死 export(updateCategory/addCategory/addNote/updateNote/deleteNote/moveUnit/moveTask) | 刪 |
| B6 | 4 個未用 shadcn ui 元件 | 留(備料,不進 bundle) |
| — | OfficialMenu「已改」hint 死 prop(無呼叫端) | 刪(已改=轉自訂,無此狀態) |
| C7 | indexer `PAYLOAD_INDEXES` 4/9 是 v3 欄位(v4 payload 無此鍵,空索引+誤導) | 對齊 v4 + 加「索引欄位 ⊆ payload model」drift 測試 |
| C8 | api `get_knowledge` 每請求新建 httpx client | **(a)** lifespan 單例掛 `app.state`,shutdown aclose |
| C9 | `list_job_profiles` N+1 | 記錄,MVP 不動 |
| C10 | user store 用 `e.message.startsWith("404")` | 改 `instanceof ApiError && status===404` |
| C11 | dashboard 後端掛時無限骨架屏 | **先不用**(維護者拍板) |
| C12 | web 無 test gate(tsc+lint 而已) | 記錄(文檔已如實寫) |

## §5 知識包(knowledge pack)——最小設計

**端點**:`GET /job-profiles/{id}/knowledge`(per-profile;聯集=處理,住後端)。
**indexer 零改動**(api 用既有 3 個 GET/code 自己拼:occupation / tasks / competencies)。

**組裝**(api):對每個 selected code **並行** `asyncio.gather(return_exceptions=True)`
(⚠ 現有 header-meta/task-candidates 是循序 for-await,pack 不得複製);單 code 失敗 → 略過 +
`meta.partial=true`(ADR 0018 原封沿用);**全部失敗** → 5xx(critical,沒有 knowledge 走不下去)。

**形狀(定稿;命名全照 packages 既有名,不發明)**——統一機制「append + 同 key 併列 + srcs 累積」:

```
GET /job-profiles/{id}/knowledge
{ occupation_details: [OccupationDetail 原樣,per 職位],      ← 合併前:表頭層(契約型別名)
  pools: {                        ← 合併後:每型別一桶,項目 byId;id = 該池的去重 key
    units:  {name: {srcs}},  tasks: {name: {srcs: [任務URN…]}},
    knowledge/skills/outputs: {name: {srcs}},  indicators: {text: {srcs}},
    attitudes: {name: {srcs}},  job_categories/occupations/industries: {code: {name, srcs}},
    prerequisites/supplements: {text: {srcs}} },
  source_tasks: {                 ← 合併前:任務層原料,鍵=任務 URN(byId)
    "ocs:{code}:T:{t}": {ocs_code, ocs_name, ocu_code, ocu_name, task_code, task_name,
                         competency_level, o_refs/p_refs/k_refs/s_refs: [池 key…]} },
  meta: {partial: bool} }
```

- **建池順序=append 順序,零計算**:照職位優先序處理(A 全部→B…);同 key → 併入既有列
  (位置不動、srcs+1),新 key → append。顯示=桶序原樣,**無搜尋、無排序**。
- **合併列只出現一次**,位置=首次 append 處;跨來源關係看引用行(來源:A、B)。
- 引用(refs)一律存**池 key**,禁用陣列索引(Redux「引用存 ID」;位置≠身分,A1 教訓)。
- 名字**不做正規化**(維護者:先不用做)——key=原始名精確比對;「問題解決能力【T1.1】」與
  「問題解決能力」是兩列,帶註記者為特例文件,後議。
- `srcs` 欄位名照 indexer-contract 借:`{ocs_code, ocs_name, ocu_code?, ocu_name?,
  task_code?, task_name?, code?, competency_level?}`(CitableItem+SourceRef 聯集,零新名)。

**§5.1 per-pool 去重 key 表**(A5 的修法本體;2026-07-03 二修:職責/任務也進池):

| 池 | key | 預勾(預設) |
|---|---|---|
| 職能基準代碼/名稱 | 不去重(A、B 兩選項) | 預選主基準(順序 1) |
| 基準級別 | 值域 1–6 全列,官方值標引用 | 預選主基準的值 |
| 工作描述 / notes | 素材庫(notes 以 text 去重) | 不預勾(點了即加) |
| 職類別/職業別/行業別 | **code**(國家分類碼,同碼=真同物) | 預勾主基準帶的 |
| **職責** | **name**(合併=聯集語意,見下) | 預勾含主基準來源的職責列 |
| **任務** | **name**(同上) | 預勾已勾職責底下全部任務(含聯集) |
| knowledge / skills | **name**(ocs-schema 官方規則) | 開格時預勾該任務官方配套(聯集) |
| attitudes | **name**(值語意;code key 跨職類必撞=A5) | 預勾主基準帶的 |
| **O(outputs)/ P(indicators)** | **O=name、P=text**(2026-07-03 三修:統一去重,維護者 OK) | 預勾該任務本身的(聯集) |

**合併實體的聯集語意(維護者拍板)**——同一條規則遞迴到底:
- 職責同名合併 → 一列、srcs=A+B;勾它 → 任務清單 = 兩來源職責任務**聯集**,各標來源、全預勾。
- 任務同名合併 → 一列、srcs=A+B;選它 → O/P/K/S 預勾 = 兩來源配套**聯集**,各標來源;
  進文件後 **provenance 可多筆**(引用行顯示雙來源)。
- 聯集不了的單值(如兩來源級別不同)→ **照優先序預選主基準的值**,另一值在選單標引用可換。
- 同名假合併風險:實驗證明跨職類罕見(524 對最高 0.823、無全同名),且全程可拆可改、來源可見;
  「像但不同名」歸未來 `items:match`,不在此層。

**預勾統一規則**:預設=主基準(順序 1)的官方集合;單值欄=預選其值;初次/按「**自動勾選**」
按鈕時套用(既有「帶官方」改名——選單裡本就全是官方,語義重複),之後以使用者動過的為準
(文件是真相)。

**選擇流程(定稿:遞迴選單模式,維護者拍板)**——每層同一句話:
「**開誰的選單,就給全池、預勾它自己的、其餘隨你勾(借用,`_ref` 照記)**」:

```
職責選單 = 職責大池(預勾含主基準來源的職責列)→ 勾中職責進文件
每個職責 → 開它的任務選單 = 任務大池(全部,不過濾不分組;
    預勾=該職責官方帶的任務,職責為合併列→兩來源職責的任務聯集;
    已在文件(任何職責下)的任務標「已加入」不可再勾——沿現行規則)
每個任務 → 開它的 O/P/K/S/L 五個選單 = 各自大池
    (預勾=該任務的 o/p/k/s_refs 聯集——合併任務背後有幾筆 source_tasks 就聯幾筆;
     L=級別 1–6,衝突取順序 1 的值)
```

> **2026-07-03 UI 修訂(維護者,P3 驗收回饋)**:選任務大 modal 拆掉,改**表格中心**——
> 工具列「選職責 ▾」下拉(勾=空職責入表格;再點取消=移除空職責;含任務鎖定,表格刪)
> → 每職責列「選任務 ▾」開任務大池(選單語意照舊:全池、預勾自己的、借用;空職責首開
> 自動帶官方任務;取消勾選=移除空任務,有內容鎖定)。AI 預勾(extract-tasks)與 CIT 自訂
> 助手(structure-task)**先拿掉**,等訪談引擎(ADR 0020)回歸;server `/ai/*` 端點保留。

**選單顯示(W1 定稿)**:全部**序號 `1. 2. 3.`**+名稱+**引用行(每列必有)**(維護者撤銷
K/S 標文件碼 `[K02]` 的提案;A4 同名沿用文件碼照常在背後發生,不上選單)。類別選單例外顯示
真實分類碼。**無搜尋、無排序**(桶序原樣)。

**srcs / `_ref` / URN 三者(同一種資訊的三個崗位)**:
- `srcs`:**池列上的完整來源清單**(wire,pack 內;欄位名照 indexer-contract)。
- `_ref`:使用者選用後**抄進文件那一筆**(web UI 欄位,`_` 前綴,export 剝;非 packages 契約)。
- URN:**身分座標的字串格式**(`ocs:{code}:T:{t}` / `:U:{u}`,indexer scheme)——當
  `source_tasks` 的鍵與任務池 srcs 的指標;池的鍵不是它(池 key=name/text/code)。

**LLM 連接(核心)**:池項 srcs 為 machine-resolvable(URN)→ 未來訪談 agent 提議值時直接附
引用、UI 渲染引用行、人可驗——同一套來源軌道,人用選單、LLM 用 citation
(vendor 標準形:Anthropic Citations「文件進、引用出」)。

**web**:單一 query `["knowledge", profileId]`,persisted、staleTime 長;PUT occupations 成功後
**背景 prefetch**(不鎖 UI);重選職類 invalidate。既有 header-meta/task-candidates/task-catalogs
三個 web query 分階段退役(server 端三端點過渡期留給 agent,最終收斂)。

**抓取策略研究依據**(一次抓 vs 分段,2026-07-03):
- TanStack Query 官方:「知道或預期資料將被需要 → 提前抓填快取」;waterfall 是頭號效能問題。
- Next.js 官方(16.2,2026-03):循序僅限「後者依賴前者結果」;無依賴 → eager 並行。
- Google web.dev:critical 資源 eager,lazy 只給畫面外非關鍵。
- 實測:908 份來源 JSON 平均 27KB、p50 24KB、p99 74KB → 選 2–5 職類 gzip 後約 10–50KB。
- 判定式:**確定會用 + 有界 + 小 + 不可變 → 一次抓**(= 精準範圍 prefetch;非「全目錄載入」)。
  現況分段抓 = 權威點名的 waterfall 反模式。
- in-repo 前例:ADR 0016(批次+seed → 開格 0 等待)= 同模式的局部版。

**刻意不做(未來縫,一行記)**:gzip/ETag/immutable 等 HTTP 加固、server 端 per-code 快取、
indexer `view=FULL`、missing-codes 清單/重試機制。pack 內部 per-code 組裝即未來拆分縫。
理由(維護者):**目前全本地部署、只有 LLM API 走雲端**——網路不是問題域;設計預算投向
LLM 核心(去重工具、訪談/共編),那裡的深度不算過度設計。

**資料流三決策(2026-07-03 拍板)**:
1. **寫入路徑收斂**:職責/任務選用改走**前端文件編輯 + autosave PATCH**(單一寫入路徑,
   與共編/LLM 模型一致——LLM 也是改文件);`document:buildTasks` 端點於 web 切換完成後退役。
2. **抓包時機**:PUT occupations 成功 → web 背景 GET `/knowledge`(mutation 回應保持薄)。
3. **過渡**:pack 端點先上,web **逐面切換**(五選單→職責/任務選單→表頭),每面切完刪對應
   舊 query;三個舊投影端點(header-meta/task-candidates/task-catalogs)等全切完再退。

## §6 落地順序(各自 plan,bite-size,green-before==green-after)

1. **Plan A1**:URN 快取鍵(api 回應鍵 + web 鍵 + buster bump)——止血錯資料 bug,pack 前置。
2. **ADR + Plan pack**:知識包(§5)+ web 資料層收斂 + 來源標記補洞(級別 `_levelSrc` 接線)。
3. **Plan UX**:§2 選單序號化 + §3 表頭互動(✕/toggle-off/手打)+ §1.2 素材庫模式(A3 一併解決)。
4. **Plan cleanup**:B5 死 export、「已改」死 prop、C7 索引對齊、C8a 單例、C10。

## §7 來源

- NN/g Heuristic #2: Match Between the System and the Real World(nngroup.com;公認 UX 權威)
- NN/g Drop-Down Menus 指南(誠實記:未針對代碼顯示給規範)
- TanStack Query 官方 Prefetching guide(庫官方)· Next.js 官方 Fetching Data(框架官方,16.2)
- Google web.dev Lazy Loading(大廠指引)
- **pack v2 正規化研究(2026-07-03 第二輪)**:
  - Redux 官方 Normalizing State Shape(每型別一張表、byId、**引用存 ID**、陣列僅表排序)
  - JSON:API 規範 Compound Documents(included 單一 canonical 物件 MUST NOT 重複;引用=type+id)
  - W3C PROV Overview(來源標記的標準地基:entity–derivation–source,「評估品質與可信度」;
    僅取原則,不採本體結構)
  - Anthropic Citations 官方文檔(LLM grounding vendor 標準形:文件進、引用出+精確位置)
  - 反方誠實記:TkDodo(React Query 維護者)— client 正規化快取常過度;本案正規化在**回應形狀**
    (不可變一包),非可變實體快取,不衝突
- 前情:`2026-06-30-api-review-findings.md`(F1–F8 方法)· `2026-06-30-web-data-layer-optimization-research.md`
  (D-1 系列)· web-opt phase2b plan(實體/值物件身分原則)· ADR 0016/0018/0019/0020
