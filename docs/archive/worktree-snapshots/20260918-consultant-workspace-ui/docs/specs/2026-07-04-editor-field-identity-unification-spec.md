# 2026-07-04 編輯器全欄位身分統一 + 自動勾選規則(spec)

> 狀態:spec(與維護者逐點討論拍板,決策紀錄見 §9)。實作 plan =
> [`docs/plans/2026-07-04-editor-field-identity.md`](../plans/2026-07-04-editor-field-identity.md)(12 task 已全數落地)。
> 相關深文檔:`docs/design/editor-knowledge-pack.md`(§2 三分法)、`apps/web/docs/data-layer.md`、
> `apps/api/docs/knowledge-pack-assembly.md`。實作落地後**同 commit 更新**上述 living 文檔。

## 0. 動機(這輪要解的問題)

1. **bug:說明與補充事項勾選填入全標「自訂」**——notes 契約欄是 `string[]`,攤成裸列丟失
   `_id/_src/_ref`,`FieldCombobox` 的 `statusOf` 一律判 custom、勾選判定(`_src==="official"`)
   永遠不成立 → 選單打不了勾、可重複加。
2. **TaskPickerMenu 以職責名判定「自己的官方任務」**——改過名=全借用,名字不是身分。
3. 各欄位的身分/來源/自動帶入規則**不統一**:有的有 `_id`/`_ref`(OPKS/態度/類別)、有的沒有
   (notes)、有的來源會殘留(任務級別換值不清 `_levelSrc`)、自動勾選鈕位置與觸發規則不一。
4. UX 缺口:職能基準代碼選了不能取消;所屬類別/基準級別/態度/notes 沒有自動勾選。

## 1. 核心模型:每列三件套(全站唯一心智模型)

| 件 | 欄位 | 值 | 回答什麼 | 何時變 |
|---|---|---|---|---|
| **列身分** | `_id` / `_uid`(職責)/ `_tid`(任務) | UUID,生成後不變 | 「這還是不是同一列」(dnd/編輯不跟丟) | 永不 |
| **顯示碼** | `code` | 位置碼(`T1.1`/`O1.1.1`/`K01`/`A01`/`n1`) | 「現在排在哪」(官方表格編號語意) | 結構/內容變動→`renumber()` 重編 |
| **官方綁定** | `_ref`(列項)/ `provenance`+`_refs`(任務/職責)/ `_levelSrc`(級別) | 來源成分 `{ocs_code, code, …}` | 「是不是官方、來自哪份基準的哪一項」 | 勾選當下凍結;改內容→清 |

- `_id`/`_uid`/`_tid` **同概念同格式**(UUID),僅欄名歷史差異;不改名(舊 draft 遷移不值得)。
- **官方唯一 ID = URN** `ocs:{ocs_code}:{型別}:{官方碼}`(基準代碼全域唯一且版本化不可變,
  「在來源文件裡的位置碼」因此穩定)。`_ref` 存 URN 的**拆解成分**,要當鍵時現組
  (三分法,同 `editor-knowledge-pack.md` §2)。型別代號 `T/O/P/K/S/A/N` 為 web 內部慣例,
  **不動 indexer** 的 urn scheme(那邊只有任務)。
- 單值欄(基準級別/任務級別/職能基準代碼)**沒有列身分**,只有官方綁定。
- **官方值必有來源**(B4):凡標 official 的值,`_ref`/`_levelSrc`/`ocs_code` 必可回答出處。

## 2. 全欄位身分表(權威;新增/修改以粗體標示)

| 欄位 | 契約形狀 | 列身分 | 顯示碼 | 官方綁定 | 改內容→ |
|---|---|---|---|---|---|
| 職能基準代碼+名稱 | scalar | — | — | `ocs_code` 本身 | **再點已選項=整組清空**(code+職類名+職業名) |
| 基準級別 | int\|null | — | — | **新增 `ocs_profile._levelSrc`** | 換值≠官方 → **清** |
| 所屬類別三類 | {name,code}[] | `_id` ✓ | 國家分類碼(真碼,不重編) | `_ref` ✓ | 編輯→custom+清 `_ref` ✓ |
| 工作描述 | string | — | — | 不綁(**素材庫**:選單只 append 純文字) | — |
| 職責 | ocu_code/name | `_uid` ✓ | `T{u}`(重編) | `source`+`_refs` | **改名→清 `source`/`_refs`→標「自訂」** |
| 任務 | task_codes | `_tid` ✓ | `T{u}.{t}`(重編) | `provenance`+`_refs` | **改名→清 `provenance`/`_refs`/`_levelSrc`→標「自訂」** |
| 任務級別 | int\|null | — | — | `_levelSrc` ✓ | 換值≠官方 → **清**(⚠ 現況不清,修) |
| O/P | CodeName[]/Indicator[] | `_id` ✓ | `O{u}.{t}.{n}`(重編) | `_ref` ✓ | 編輯→custom+清 ✓ |
| K/S | CodeName[] | `_id` ✓ | `K01`(A4 文件級共碼,重編) | `_ref` ✓ | ✓ |
| 態度 A | CodeName[] | `_id` ✓ | `A01`(重編) | `_ref` ✓ | ✓ |
| **notes 兩欄** | string[] | **`_id`(影子欄,§3)** | **`n{i}`(重編)** | **`_ref`(code=來源文件 n 碼,§3)** | **編輯→custom+清 `_ref`** |

「標『自訂』」判定 = 無官方綁定(職責:無 `_refs` 且 `source.ocs_code` 空;任務:`taskUrns()` 為空)。
手動新增的職責/任務本來就無來源 → 同樣標自訂(語意正確)。

## 3. notes 設計(bug 修法)

**存放——影子欄(維護者拍板,取代 derive-on-read 提案)**:

- draft 的 `notes._prerequisites` / `notes._supplements` 存物件列
  `{ code, text, _id, _src, _ref }`,是**唯一真相**;契約欄 `notes.prerequisites/supplements: string[]`
  由 setter **同步導出**(單一寫入點 `ocsDoc.ts`,兩欄不會漂)。
- finalize/export 的 `_strip_underscore` 自動剝 `_` 欄 → 契約乾淨,**後端 ocs_doc 零改動**。
- 為何不 derive-on-read:官方性會跟著當前知識包浮動(重選職類後官方帶入項「變自訂」),
  違反「文件是真相、來源必標」;`_ref` 落庫把 provenance 凍結在勾選當下,與全站一致。

**官方 n 碼——api `build_pack` 補位置碼**:

- 現況 notes 池 `srcs[].code = null`(來源文件對 notes 沒編碼)。
- `build_pack` 組 `prerequisites`/`supplements` 池時,照**該來源文件清單順序**蓋
  `src.code = "n{i}"`(1-based;同文去重列的 code 取該來源首現位置)。
  `PackSrc.code` 欄位既有,**契約/indexer 零改動**;加 api pytest。
- 效果:web `officialMatch` 自動走「有碼比碼」分支(`_ref{ocs_code, code:"n1"}`),
  notes 判定與 OPKS 同一條路,無特例。
- 我們文件端的顯示碼 `n1,n2…` 由 `renumber()` 重編(prefix `n`,影子列),與 `_ref.code` 無關
  (顯示=我們的位置、身分=來源的位置,同 OPKS)。

**舊 draft 遷移**:`notes._*` 缺失時,首次 render(有 pack)由 `string[]` 重建影子列——
文字對池命中 → `official`+`_ref`;對不到/無 pack → `custom`。下次 commit 隨 PATCH 落庫。

## 4. 自動勾選統一規則(維護者拍板)

- **觸發**:首次打開該選單**且該欄位為空** → 自動套;之後以使用者為準。
  選單內都有「自動勾選」鈕可隨時重套(**鈕一律放選單頂列**,從外部按鈕列移入)。
- **來源規則(表頭層欄位)**:defaults = **主基準**(`ocs_profile.ocs_code` 選定的職能基準)
  來源的官方值;主基準**空白或自訂**(不在 `pack.occupation_details`)→ **不套**。
  適用:所屬類別三類、基準級別、態度、notes 兩欄。
- **任務層欄位維持任務規則**:OPKS 四格/任務級別的 defaults = 該任務自己的官方配套
  (`source_tasks` own refs),粒度不同,**不改**成主基準。
- 已套用過、使用者清空 → 不再自動套(首開一次為限,與現行 CellFiller/TaskPicker 一致)。

## 5. 改名斷鏈(維護者拍板:與 OPKS 規則一致)

- `renameUnit` / `renameTask` 內容變更即斷鏈:清官方綁定(§2 表)→ 列標「自訂」、
  對應選單(UnitPicker/TaskPicker)**取消勾選**(可重新勾官方,會另起一列)。
- 改回原名**不**自動重新連結(與 OPKS 一致;要官方就從選單重勾)。
- 職責改名**不影響**底下已選任務(任務身分在任務自己身上);任務改名只斷**該任務**的
  own-refs 自動帶入/官方級別,已填格子內容保留。

## 6. TaskPickerMenu 身分判定(取代名字對位)

- `SourceRef` 型別新增 `ocu_code?: string`;`packSrcToRef` 帶上 → `addFromPool` 存進
  `unit._refs` 的來源就含 `ocu_code`(`_` 欄,契約安全)。
- 「自己的官方任務」= `unit._refs` 的 `(ocs_code, ocu_code)` 對回 units 池列,
  不再比 `ocu_name`。改過名的職責(§5 已清 `_refs`)→ 無 own(全借用),行為由身分導出。

## 7. UI 改動點清單

| 元件 | 改動 |
|---|---|
| `FieldCombobox` | 「自動勾選」鈕移入選單頂列;新增首開自動套(defaults 給定且 value 空);list 列顯示碼照常 |
| `DocNotes` | 影子列接入(value=物件列);選單勾選/取消走有碼比對;自動勾選+首開套主基準 notes |
| `AttitudeBlock` | defaults=主基準來源態度;自動勾選入選單+首開套 |
| `DocHeader` 三類 | `CategoryPicker` 加自動勾選(defaults=srcs 含主基準碼)+首開套(該類空時) |
| `DocHeader` 基準級別 | 首開且空→帶主基準級別+`_levelSrc`;選 1–6 時值==官方→寫 `_levelSrc`,≠→清;選單加自動勾選 |
| `DocHeader` 基準代碼 | `OfficialMenu` 支援再點已選=清空;`clearPrimaryBasis`(清 code+兩名) |
| `DocHeader` 工作描述 | 不動(素材庫) |
| `JobDocTable` | 職責/任務名旁「自訂」tag(無官方綁定時);任務級別選單加自動勾選鈕 |
| `TaskPickerMenu` | §6 身分判定 |
| `ocsDoc.ts` | `renameUnit`/`renameTask` 斷鏈;`clearPrimaryBasis`;notes setters 改影子列+導出;`setTaskLevel`/`setOcsLevel` 清 `_levelSrc`;`renumber()` 加 notes 影子列 `n` 碼 |
| `pack.ts` | `primaryDefaults(pool, primaryCode)` 純函式(表頭層 defaults);`packSrcToRef` 帶 `ocu_code` |
| api `knowledge_pack.py` | notes 池 srcs 蓋 `n{i}`(§3) |

## 8. 驗證

- **vitest(`src/lib`)**:改名斷鏈(職責/任務)、notes setters(影子列↔string[] 同步、
  `n` 碼重編、遷移重建)、`clearPrimaryBasis`、`setTaskLevel`/`setOcsLevel` 清 `_levelSrc`、
  `primaryDefaults`、`packSrcToRef` 帶 `ocu_code`。
- **api pytest**:`build_pack` notes n 碼(順序、去重列取首現、跨基準)。
- `tsc --noEmit` + `eslint`;手測腳本:勾 notes→打勾+不標自訂→改字→變自訂→選單取消勾選;
  改任務名→tag+選單取消勾;拖 notes 順序→顯示碼重編、`_ref` 不變;基準代碼再點=清空。

## 9. 決策紀錄(維護者逐點拍板)

1. notes 綁身分採**影子欄落庫**(否決 derive-on-read/index-對齊 meta/改契約)。
2. notes 官方碼 = **來源文件位置 n 碼**,存 `_ref.code`;我們文件另有顯示碼(重編)。
3. **改名=丟身分變自訂、選單取消勾選**(與 OPKS 一致;不採「保留身分+僅標籤」)。
4. 基準代碼再點已選項 = **整組清空**。
5. 自動勾選:**首開選單且欄位空**;來源=主基準;主基準空白/自訂不填;鈕移入選單。
6. level 不區分「使用者選的 vs 自動帶的」——**值等於官方值即官方**(寫 `_levelSrc`)。
7. 每欄位統一設計 ID(用不用其次);`_id/_uid/_tid` 同概念不改名;官方唯一 ID=URN 成分存 `_ref`。
