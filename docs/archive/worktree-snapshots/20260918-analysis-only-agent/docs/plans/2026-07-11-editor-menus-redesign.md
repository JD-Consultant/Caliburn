# 編輯器選單重設計實作計畫(ADR 0029;spec 2026-07-11)

> 依 [研究紀錄](../specs/2026-07-11-editor-menus-redesign-research.md) +
> [ADR 0029](../adr/0029-editor-menus-three-types-decoupling.md)。設計已由維護者七層逐點鎖定,
> **不要重開設計討論**;規格有疑義先讀 spec §3/§4/§5,仍不明才問。
> 慣例:一 task 一 commit、TDD、green-before==green-after、**不 push**;
> branch=`research/llm-interview-integration`;動手前 `pwd`+`git branch --show-current`
> (Bash cwd 會落到別的 checkout);api dev server reload 已關(改後端要手動重啟);
> DB 測 `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn`;CJK 用 `PYTHONUTF8=1`。
> 測試:web=`npm run test`+`npx tsc --noEmit`+`npm run lint`;api=`uv run pytest`。

## 全局不變量(每 task 隱含)

- **選單=純工具**:不自動寫(首開自動寫全面退場)、無自訂入口、無 AI 標記、一律獨立視窗(Modal 家族)。
- **改字不斷根**:改名保留來源(`_ref`/provenance);選單勾選判定按**身分**,不按 `_src`。
- **AI 元件不重設計只保綠**:CurationDialog、`interview:curation`/precheck、D7 reviewMap 徽章、
  InterviewPanel——編譯過、測試綠即可,行為與視覺不動(AI 層之後另輪重設計)。
- 素材庫欄(工作描述/說明欄)無勾選狀態;控制欄格內不可能出現非官方值。

## T1 後端脫鉤:`PUT /occupations` 停寫表頭

- **研**:`apps/api/app/api/routes/documents.py:128-176`——現況 set_occupations 會把 codes[0]
  的名稱寫進 draft 的 `ocs_profile`(表頭)。脫鉤後參考集合只住 profile(選了哪些 codes),
  文件表頭唯一寫入口=前端職類視窗。
- **檔**:documents.py 移除 header 回寫(128-133 那段 helper 與呼叫);確認 `GET /job-profiles/{id}`
  回傳已含所選 occupation codes(前端 gate 要用;沒有就補欄位)。既有測試中「set 完表頭跟著變」
  的斷言改為「表頭不變」(characterization 隨行為更新)。
- **測**:pytest——set_occupations 後 `ocs_profile` 原值不動;`/knowledge` 照常出包。
- **驗**:api 綠。**commit**:`feat(api): 參考與文件身分脫鉤(PUT occupations停寫表頭;ADR 0029)`

## T2 前端脫鉤:〔選職能基準參考〕改名+去順序;主基準=表頭所選

- **研**:`OccupationPicker.tsx`(標題「選擇職類(順序＝優先度)」、順序 Badge);
  `UnitPickerMenu.tsx:27` 是前端唯一拿 `occupation_details[0]` 當主基準的地方
  (DocHeader/AttitudeBlock/DocNotes 已吃 `doc.ocs_profile.ocs_code`);
  `page.tsx` 的 `hasOccupations = !!doc?.ocs_profile?.ocs_code` gate 選單與 `useKnowledge`。
- **檔**:OccupationPicker——標題/按鈕文案改「選職能基準參考」、拆順序 Badge 與「順序=優先度」
  語義;page.tsx——頂欄按鈕文案改、gate 改「有參考」(profile 的 codes,T1 曝的欄位);
  UnitPickerMenu primary 改 `doc.ocs_profile.ocs_code`(未選→「選同職能基準」鈕 disabled,
  非官方身分同樣 disabled,比照 `isOfficialBasis` 現有判準)。
- **測**:vitest(pack/curation 測不壞)+tsc+lint;手驗:清參考→選單 disabled;
  只選參考不動表頭→文件全空、選單有料。
- **驗**:綠。**commit**:`feat(web): 選職能基準參考(無序不寫文件)+主基準=表頭所選(ADR 0029)`

## T3 職類視窗:升獨立窗+基準名稱唯讀

- **研**:`DocHeader.tsx:174-221`——職能基準代碼列 OfficialMenu(單選、代碼+名稱綁定、
  再點=清空)+非官方時名稱開 FieldText 自由填。spec §3:控制單選、不可自訂。
- **檔**:OfficialMenu 觸發改開 Modal 家族獨立窗(選項=已選參考,樣式同選職責窗:序號+來源行);
  拆名稱 FieldText 自由填(職類/職業列一律唯讀顯示);「再點同項=清空」保留。
- **測**:tsc+lint;手驗:表頭只能從參考中單選;清空後名稱空、不可打字。
- **驗**:綠。**commit**:`feat(web): 職類視窗獨立窗+基準名稱唯讀(控制單選;ADR 0029)`

## T4 控制選單:三分類+兩處級別

- **研**:DocHeader `CategoryPicker`(Popover+「＋加自訂列」+自訂列 FieldText+首開自動套);
  基準級別 OfficialMenu(首開 levelAuto 自動帶);JobDocTable TaskRow 級別 OfficialMenu。
- **檔**:三分類——Popover→Modal、拆「＋」鈕與自訂列編輯(文件裡既存 custom 列照顯示,
  只是選單不再能新建)、首開自動套退場、「自動勾選」→「**選同職能基準**」;
  基準級別/任務級別——升 Modal、首開自動帶退場(levelAuto ref 拆)。
- **測**:vitest+tsc+lint;手驗:開窗不寫入;三分類格無法輸入自由文字。
- **驗**:綠。**commit**:`feat(web): 控制選單純選+獨立窗+選同職能基準(三分類/級別;ADR 0029)`

## T5 素材庫:工作描述+說明與補充事項

- **研**:工作描述 OfficialMenu 點=附加段落(行為已對,只差窗化);`DocNotes.tsx` 現況是
  FieldCombobox 多選盒(customMode footer+autoApplyOnFirstOpen)——spec §3 要改素材庫。
- **檔**:工作描述選單→Modal(插入行為不變);DocNotes 兩欄(prerequisites/supplements)——
  選單改素材庫窗(點=插入一列,無勾選狀態),表格列就地自由編輯(改字/刪列/加列),
  拆 footer 自訂與首開自動;影子列資料形(`notes._<field>`)不動。
- **測**:vitest(notes 資料形 round-trip)+tsc+lint。
- **驗**:綠。**commit**:`feat(web): 素材庫選單(工作描述/說明欄=點即插入;ADR 0029)`

## T6 參考選單:改名不斷根+原名副行+搜尋框+選同X

- **研**:spec §2/§4——改名保留來源(甲案全層統一);現況 FieldCombobox 編輯 commit 會
  `_ref: undefined`(斷根)且勾選判定 `_src==="official"`——**兩者都要改**。
  UnitPickerMenu/TaskPickerMenu 的「自動勾選」與 TaskPickerMenu 首開自動套(applied ref)。
- **檔**:
  - FieldCombobox 系(O/P/K/S/A):編輯改字→`_src:"custom"` 但**保留 `_ref`**;勾選判定改按
    `_ref` 身分對位;拆 `customMode` footer 與 `autoApplyOnFirstOpen`;加列內改名(hover 鉛筆,
    僅已勾列)與原名副行(細字「原名:○○」,樣式同來源行;判定=文件筆名≠池列官方名且身分同);
    「自動勾選」→「**選同工作任務**」(A 窗=**選同職能基準**);窗頂加 CommandInput 搜尋框。
  - UnitPickerMenu/TaskPickerMenu:列內改名+原名副行(職責/任務的身分對位沿用現有
    `_refs`/URN 機制);「自動勾選」→「選同職能基準」/「選同主要職責」;
    TaskPickerMenu 首開自動套退場;窗頂搜尋框。
- **測**:vitest——改名後:勾選仍 ✓、副行出原名、`_ref` 仍在;未勾列無改名入口;
  tsc+lint。
- **驗**:綠。**commit**:`feat(web): 參考選單改名不斷根+原名副行+搜尋框+選同X(ADR 0029)`

## T7 選主責入表底+全域選工作任務窗

- **研**:spec §6。來源職責解析:任務多來源(srcs 多筆)→取與主基準同 `ocs_code` 的優先
  (同 TaskPickerMenu `pickOf` 慣例);來源職責不在文件→先加(空職責)再掛任務。
- **檔**:
  - page.tsx:UnitPickerMenu 從頂欄移除;JobDocTable 底部與〔＋新增職責〕並排渲染。
  - 新 `GlobalTaskPickerMenu`(頂欄原選職責位):任務大池全列(同任務窗列樣式),每列副行
    「將掛入:○○職責」;勾=解析職責(在→掛入;不在→自動加再掛);取消勾規則同任務窗
    (空任務可移、有內容/他職責鎖定);「選同職能基準」=主基準全部職責+官方任務整組帶入。
  - `lib/ocsDoc.ts`(或 lib/pack.ts)加純函式:`resolveHomeUnit(row, doc, pack, primary)` 與
    整組帶入的組裝,vitest 先行。
- **測**:vitest(解析:多來源取主基準優先/職責缺→建職責+掛/已在他職責→鎖定);tsc+lint。
- **驗**:綠。**commit**:`feat(web): 選主責入表底+全域選任務窗(自動掛來源職責;ADR 0029)`

## T8 版式:任務卡內 OPLKS 全展開;CellFillerPanel 退役

- **研**:spec §7 sketch。三層同構:職責卡⊃任務卡⊃OPLKS 區;▾ 在左欄標籤旁;
  列序 O→P→L→K→S;hover 才出編輯工具;靜止=乾淨官方文件。
- **檔**:JobDocTable `TaskRow`——四顆 Cell 按鈕退役,改 OPLKS 展開區:左標籤
  (工作產出(O)▾/行為指標(P)▾/職能級別(L)▾/職能內涵(K)▾/職能內涵(S)▾,▾ 開 T6 的格選單窗)、
  右側內容全列(每項一行:碼+文字,就地編輯、hover ×刪、格底＋自訂加列即建 custom 項);
  級別列=值+▾(T4 的窗)。CellFillerPanel 與 page.tsx 的 `target`/`CellTarget` 開板流拆除。
  A 區塊/DocNotes 位置不動、接新窗。D7 reviewMap 徽章掛到新格區對應列(最小適配保綠)。
  視覺:碼等寬淡色、任務列字重稍高、職責列淡底、逐層縮排。
- **測**:vitest(既有 ocsDoc 增刪改測不壞)+tsc+lint;手驗長文件捲動與 hover 工具。
- **驗**:綠。**commit**:`feat(web): 任務卡OPLKS全展開+CellFillerPanel退役(ADR 0029)`

## T9 位置碼:顯示+匯出自動連號

- **研**:spec §7——表格顯示的 T/O/P/K/S 碼=**位置碼**(第 1 職責=T1、其第 3 任務=T1.3、
  其產出=O1.3.1…),拖拉自動重編;身分靠來源(URN),原官方碼在來源行。
  匯出=成品所見即所得,採位置碼(內部存檔的原碼與來源不動;若維護者要匯出保留原官方碼,另議)。
- **檔**:lib 加 `displayCode` 純函式(層級+索引→碼),vitest 先行;JobDocTable/OPLKS 區/
  匯出組裝改用;文件內 `ocu_code`/`task_codes`/項目 code 存值不動(只是不再當顯示源)。
- **測**:vitest(重排後連號、跨職責搬移重編、custom 與官方一視同仁);tsc+lint。
- **驗**:綠。**commit**:`feat(web): 位置碼自動連號(顯示+匯出;身分靠來源;ADR 0029)`

## T10 文檔同步+全綠+tag

- **檔**:`docs/design/` 受影響段落(interview-engine.md 的共用 UI/選單段——註明選單三型與
  AI 載體待重設計);研究紀錄補「驗收紀錄」節(照 §16 慣例:哪些綠、跑了什麼);
  ADR 0029 索引已入(README)。
- **驗**:`npx turbo test` 全綠 → tag `editor-menus-v1`。
- **commit**:`docs(design): 編輯器選單重設計文檔同步(ADR 0029)`

## 驗收(整體)

1. 〔選職能基準參考〕只換選單內容,文件不動;表頭由職類視窗單選帶入,換選=視角重算。
2. 任何選單打開**不寫入**;批次帶入只有「選同X」三鈕;職類視窗未選→選同鈕全暗。
3. 參考選單列內改名:✓ 不掉、出「原名:」副行、來源身分還在;控制欄選不出非官方值;
   素材庫點=插入。
4. 任務卡內 O→P→L→K→S 全展開、標籤旁 ▾ 開窗、位置碼連號、hover 才見編輯工具;
   「點此填」與 CellFillerPanel 不存在。
5. AI 訪談既有流程照跑(元件未重設計但全綠)。
