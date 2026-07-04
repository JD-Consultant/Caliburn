---
title: 編輯器 × 知識包 — 端到端設計
audience: agent-primary(也給人)
scope: apps/web 著作 UI + apps/api knowledge/document 端點
updated: 2026-07-04
---

# 編輯器 × 知識包 — 端到端設計(職能基準著作面)

> **主讀者 = coding agent。** 目的:不看 code 也能改對這條線——不亂發明端點、不把退役路徑救回來、
> 不誤動刻意設計。**living:動到這條線的碼,同一個 commit 更新本檔**(fossilization 是頭號壞味道;
> 見 [`../specs/2026-07-03-agent-facing-docs-research.md`](../specs/2026-07-03-agent-facing-docs-research.md))。
> 範圍:`apps/web` 著作 UI + `apps/api` 的 `knowledge` / `document` 端點。權威決策在 ADR 0021(見 §8)。

## 1. 一句話

**選職類**抓一份「**知識包**」(occupation_details + 12 池 + source_tasks);web **所有選單**都從這包讀;
使用者勾選/填寫 → **純函式改文件** → **autosave PATCH** 存草稿。沒有任何 curation 專用端點。

## 2. 角色與資料模型

**知識包 `KnowledgePack`**([types/index.ts](../../apps/web/src/types/index.ts);欄位名照 indexer-contract):

| 部位 | 形狀 | 用途 |
|---|---|---|
| `occupation_details[]` | `{ocs_code, ocs_name, job_description, ocs_level}`(**保序**=優先序) | 表頭主基準選單 |
| `pools.{units,tasks,knowledge,skills,outputs,indicators,attitudes,prerequisites,supplements}` | `Record<key, {srcs}>` | 各選單池;**key=去重鍵**(見下) |
| `pools.{job_categories,occupations,industries}` | `Record<分類碼, {name, srcs}>` | 表頭三類(顯真實碼) |
| `source_tasks` | `Record<URN, {…, o_refs,p_refs,k_refs,s_refs, competency_level}>` | 任務→自己的官方 O/P/K/S 配套 |
| `meta.partial` | `bool` | 部分 code 的 indexer 掛(降級旗標,ADR 0018) |

**池去重鍵**:K/S/O/units/tasks/attitudes = **name**;P(indicators)/notes = **text**;三類池 = **國家分類碼**。

**來源三分**(最容易搞混,務必分清):

| 角色 | 是什麼 | 存哪 | 生命週期 |
|---|---|---|---|
| `srcs` | 池列/選項的**全部來源**(`SourceRef[]`) | 線材(pack)+ 選單顯示 | 不落文件 |
| `_ref` | 使用者**選中的那一個**來源(= own-first 重排後 `srcs[0]`) | 文件項的 `_ref` 欄 | **export 剝除** |
| URN | 任務**身分座標** `ocs:{code}:T:{task_code}` | source_tasks 的 key、tasks 池 srcs 指標 | **現組不落庫**([urn.ts](../../apps/web/src/lib/urn.ts)) |

`_` 前綴一律 **UI-only、finalize/export 後端剝除**:`_ref` `_refs`(合併列多來源聯集,provenance 取首個)、
`_levelSrc`(帶官方級別的來源,B4;任務級 + 表頭級 `ocs_profile._levelSrc`)、`_notes`(工作筆記 D28)、
`_id`/`_uid`/`_tid`(dnd 穩定鍵)、**`notes._prerequisites`/`_supplements`(NoteItem 影子列=notes 唯一真相,
契約欄 string[] 由 renumber 導出;來源 n 碼由 api build_pack 蓋在池 srcs.code)**。

**每列三件套**(spec 2026-07-04 §1):UUID 列身分(`_id` 系,永不變)+ 位置顯示碼(`code`,renumber 重編)
+ 官方綁定(`_ref`=URN 成分,勾選當下凍結)。單值欄(級別/基準代碼)只有官方綁定。

## 3. 端到端資料流(runtime 場景)

```
① 選職類  OccupationPicker → useSetOccupations
          └ PUT /occupations {ocs_codes}      ← 唯一同步點
            server: 設 selected_ocs_codes + 用 knowledge.occupation(codes[0]) 刷表頭名 + upsert draft
          └ onSuccess: invalidate ["document",id] + invalidate&prefetch ["knowledge",id]

② 抓知識包  useKnowledge(id, hasOccupations) → GET /knowledge          (staleTime 24h, persist)
          server: 對每個 code 並行抓 indexer 三資源(occupation / occupation_tasks / competencies)
                  → knowledge_pack.build_pack(照優先序 append) → 12 池 + source_tasks + meta.partial
                  單 code 掛→略過+partial=true;全掛→502

③ 各選單讀池  (pack.ts 純函式層,唯一 pack 讀取點)
   表頭主基準   DocHeader     primaryBasisOptions(pack)          → setPrimaryBasis
   表頭三類     DocHeader     codedPoolOptions(pack.pools[kind]) → setCategory
   NOTE 前提/補充 DocNotes    valuePoolOptions(pack.pools[field])→ setNoteItems(影子列)
   態度 A       AttitudeBlock valuePoolOptions(pack.pools.attitudes) → setAttitudes
   選職責 ▾     UnitPickerMenu unitRows(pack)                    → addFromPool / deleteUnit
   選任務 ▾     TaskPickerMenu taskRows(pack)+ownTaskKeys        → addTasksToUnit / deleteTask
   填格 O/P/K/S CellFillerPanel valuePoolOptions + ownTaskRefs(預勾) → setOp / setKS

④ 勾選/填寫  onChange/onSave(nextDoc) → page.persist → useAutosaveDocument.commit(next)
          └ setQueryData(["document",id]) 即時反映 + debounce 500ms
          └ PATCH /document?expect_version&expect_revision   (樂觀鎖 opt-in)
             409 → 不回滾本地編輯 → ConflictDialog(載入最新版 / 以我覆蓋)

⑤ 收尾   匯出 GET /document/export(組乾淨 OCS JSON,剝 _ 欄,不寫庫)
        產生正式版本 POST /document:finalize(assemble + 驗 schema,失敗 422)
```

**純函式改文件**都在 [ocsDoc.ts](../../apps/web/src/lib/ocsDoc.ts):`renumber()` 是**唯一重編點**
(職責 `T#`、任務 `T#.#`、任務範圍 O/P、態度 `A##`、notes `n#`、A4 文件級 K/S),冪等;
結構變動與 `setOp`/`setKS`/`setAttitudes`/`setNoteItems` 收尾都走它——「漏重編」類 bug 結構上不可能。

## 4. UI 動作 → 請求對照

| 動作 | 元件 | 純函式(ocsDoc) | 網路 |
|---|---|---|---|
| 搜/勾/套用職類 | OccupationPicker | — | **`PUT /occupations`** → prefetch `GET /knowledge` |
| 選職責 ▾ 勾/取消 | UnitPickerMenu | addFromPool / deleteUnit | `PATCH /document`(autosave) |
| 選任務 ▾ 勾/取消 | TaskPickerMenu | addTasksToUnit / deleteTask | `PATCH /document` |
| 點空格填 O/P/K/S | CellFillerPanel | setOp / setKS | `PATCH /document` |
| 改主基準/三類 | DocHeader | setPrimaryBasis / setCategory | `PATCH /document` |
| 改 NOTE / 態度 / 級別 | DocNotes / AttitudeBlock / TaskRow | setNoteItems / setAttitudes / setTaskLevel | `PATCH /document` |
| 匯出 JSON | 工具列 | — | `GET /document/export` |
| 產生正式版本 | 工具列 | — | `POST /document:finalize` |

> **關鍵**:選職責/選任務/填格/改表頭 **一律不打自己的端點**——全部漏斗進**同一條 autosave `PATCH`**
> (與 LLM 共編同一條寫入路徑)。唯一會主動打網路的著作動作是**選職類**(換同步點)。

## 5. 端點 reference

前綴 `/api/v1`;router `/job-profiles`([documents.py](../../apps/api/app/api/routes/documents.py))。

| Method Path | 用途 | 降級/錯誤 |
|---|---|---|
| `PUT …/occupations` | 設 selected_ocs_codes(序=優先) + 刷表頭 + 建/更新 draft | indexer 掛→表頭名留空(不退回 job_title) |
| `GET …/knowledge` | 知識包(選職類後一次抓齊);**含 `similarity`**(態度/任務兩池的相似比對結果,ADR 0022,api 原樣搬運 indexer `items:match`) | 單 code 掛→partial;**全掛→502**(critical);match 掛→`similarity` 缺該 kind + `meta.similarity: ok\|partial\|unavailable`(enrichment) |
| `GET …/document` | 最新 draft/final;無→空殼(status none, v0) | — |
| `PATCH …/document` | 存整份 draft(loose,不 strict 驗) | 帶雙 token 且不符→**409**(ADR 0015) |
| `POST …/document:finalize` | 組裝+驗 schema→正式版本 | schema 錯→**422** |
| `GET …/document/export` | 唯讀匯出乾淨 OCS JSON | 無文件→400 |
| `GET /occupations?q=` | 職類目錄搜尋(根層,ADR 0019) | — |

## 6. 不變量(code 裡讀不出的規則)

1. **選職類 = 唯一 knowledge 同步點**。只有 `useSetOccupations` 會 invalidate+prefetch `["knowledge",id]`;
   其餘一切從這一包讀,不各自打 indexer。
2. **單一寫入路徑**:所有 curation(選職責/任務/填格/表頭)= 前端純函式改 doc + autosave `PATCH`;
   **沒有 curation 專用端點**(刻意,與 LLM 共編一致)。
3. **來源三分**:`srcs`(全來源,線材)/ `_ref`(使用者選的那個,export 剝除)/ URN(身分,現組不落庫)。§2。
4. **池序 = append 序**(職位優先序);**選單不排序、不搜尋**;無碼選項顯序號 `1. 2. 3.`(三類池例外顯真分類碼)。
5. **A4 K/S 文件級去重**:碼以 **name 為 key 全文件共用**(首現給號、同名共碼);O/P 任務範圍、A 全域。
   `renumberDocKS` 在每次 K/S 內容或結構變動時跑。
6. **預勾/自動勾選統一規則**(spec 2026-07-04 §4):「開誰的選單 → 給全池、預勾它自己的官方配套、
   其餘可勾=借用」。**任務層**(OPKS 格/任務級別)defaults=該任務 own refs;**表頭層**(三類/基準級別/
   態度/notes)defaults=**主基準來源**,主基準空白/自訂→不套。一律**首開且欄位空**才自動套(一次為限),
   之後**以使用者動過的為準(文件是真相)**;「自動勾選」鈕一律在**選單頂列**。
7. **取消勾選=移除**,但**有內容/含任務/在他職責 → 鎖定**(只能在表格刪;防誤刪已填資料)。
8. **降級**(ADR 0018):部分 code 掛→`meta.partial=true`(前端提示部分暫缺);全掛→502(沒 knowledge 選不了)。
9. **樂觀鎖 opt-in**(ADR 0015):web 一律帶 `expect_version+expect_revision`;409 **不回滾本地編輯**(使用者的字留著)→ ConflictDialog。
10. **改名=斷鏈變自訂**(spec 2026-07-04 §5):職責/任務改名即清官方綁定(`_refs`/`source`/
    `provenance`/`_levelSrc`)→ 列標「自訂」、選單取消勾選;職責改名**不**影響底下任務身分。
    TaskPickerMenu 的 own 任務以 `unit._refs` 的 `(ocs_code, ocu_code)` 身分對位,**不比名字**。
11. **級別「值==官方值即官方」**(spec §9 決策 6):選中值等於官方級別→寫 `_levelSrc`,不等→清;
    不區分使用者選的還是自動帶的。基準代碼**再點已選項=整組清空**(code+兩名一起)。
12. **相似比對分群 = render-only 顯示變換**(ADR 0022):選擇邏輯(`primaryDefaults`/首開自動套/
    勾選判定/寫入身分)**永遠跑在平選項上,一行不改**;`groupedValueOptions`/`taskRowsWithSimilar`
    只在 render 前折疊顯示列。**把分群搬進選擇邏輯 = 違規**。收合列**就是代表成員本人**
    (群無可選身分,文件永遠只出現成員真身);任務灰區對**純顯示徽章**(不自動勾、不合併、不擋)。
    兩個湧現不變量:(A) 來源不相交才比 ⇒ 一群內每基準最多一條 ⇒ 自動勾選不可能勾雙;
    (B) survivorship 主基準優先 ⇒ 主基準成員在群內必為代表 ⇒ 自動套勾到的就是主基準身分。

## 7. 已退役 / 別做(anti-patterns)

- **別叫這四個端點**(P3 已刪,web 已無對應 client):`…/document/task-candidates`、`…/document:buildTasks`、
  `…/header-meta`、`…/task-catalogs`。任務入文件只走 `addFromPool`/`addTasksToUnit` + `PATCH`。
- **別為 curation 新開端點**——見不變量 2(單一寫入路徑)。
- **別在選單排序/搜尋池**——append 序是刻意的(不變量 4)。
- **別把 `_` 前綴欄當契約欄**——UI-only,finalize/export 剝除(§2)。
- **`/ai/*` server 端點還在**(訪談引擎 ADR 0020),但 **web 目前零呼叫**;別以為 AI 預勾/自訂助手在跑
  ——P3 UI 修訂已拿掉,等引擎回歸(ADR 0020)。

## 8. 指路(不複製內容,連過去)

- **ADR**:[0021 知識包](../adr/0021-knowledge-pack-single-sync-point.md)(權威)、
  [0018 降級](../adr/0018-indexer-dependency-degradation-policy.md)、
  [0015 樂觀鎖](../adr/0015-document-save-optimistic-concurrency.md)、
  [0019 命名](../adr/0019-api-naming-alignment.md)、[0011 生成型別](../adr/0011-web-ocs-types-generated.md)。
- **spec**:[editor-provenance-knowledge-pack-decisions](../specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md)(逐項決策:三分/A4/B4/預勾/借用)、
  [editor-field-identity-unification](../specs/2026-07-04-editor-field-identity-unification-spec.md)(全欄位身分表/n 碼/改名斷鏈/自動勾選)。
- **契約 schema**:`packages/ocs-contract`(OCS 文件單一真相,生 TS)。
- **README**:[apps/web](../../apps/web/README.md)、[apps/api](../../apps/api/README.md)。
