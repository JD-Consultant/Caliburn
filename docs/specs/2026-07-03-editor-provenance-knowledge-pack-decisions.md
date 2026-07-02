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

**形狀**(web 直讀零轉換;每個官方項後端已帶 `srcs: SourceRef[]`):

```
{ occupations: [主基準選項],
  header_pools: {job_categories/occupations/industries/attitudes: [{code,name,srcs}]},
  note_pools:   {prerequisites/supplements: [{text,srcs}]},
  task_tree:    [職類→職責→任務,各帶 SourceRef],
  catalogs:     {"ocs:{code}:T:{task_code}": {knowledge/skills/outputs/indicators:[{code,name,srcs}], level}},
  meta: {partial: bool} }
```

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
- 前情:`2026-06-30-api-review-findings.md`(F1–F8 方法)· `2026-06-30-web-data-layer-optimization-research.md`
  (D-1 系列)· web-opt phase2b plan(實體/值物件身分原則)· ADR 0016/0018/0019/0020
