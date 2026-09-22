# R01 原生待審建議：首次結果與能力邊界

研究日期／存取日期：2026-09-09。執行：2026-09-09T14:36:40.941Z。JD-R002/C03；僅隔離研究，不選型或採用產品審閱政策。

## 已實測

**四組 2 PASS／2 FAIL，沒有執行錯誤。** `results/2026-09-09T14-36-40-805Z/review-results.json` 保留首次全部 assertion 與差異；`review-traces.json`／`review-traces.inspect.txt` 保留每階段完整 before／after／selection／原生 suggestion data／onChange operations。原 probe 與首次結果未為消除失敗而修改。

| 組別 | 固定操作與實際結果 | 結論可支持的範圍 |
|---|---|---|
| R01-1 PASS，5/5 | 原生將月檢限制句替換成「所有專案都按月檢查。」；另處插入故障說明。兩者確有不同 pending ID。JSON 寫檔後建全新 editor，全部 pending JSON 相等；拒絕月檢 ID 恢復原始乾淨月檢節點，故障全文及 pending metadata 完全相等，交付段不變，只剩故障 ID 待審。 | 普通文字替換與獨立段落新增，在此固定 profile 可保存後只取消其中一項。這是目前有效需求的直接正證，非已接受歷史回退。 |
| R01-2 PASS，4/4 | 從同一份 pending JSON 建另一個全新 editor；接受月檢 ID 得到完整當前月檢新文且清除該組修訂，故障節點全文與 pending metadata 完全相等，交付段不變。 | 當下只有一次替換的獨立組，可接受目前新文並保留別組待審。不能延伸為任意續改最新版皆可結算。 |
| R01-3 FAIL，3/6 | 原生 `ai→human→ai` 依序替換待審新文；月檢 ID 從 1 個變成 2 個再變成 3 個。JSON 重開完整保留這條原生 metadata。只 accept 原始月檢 ID，未得到乾淨最新版；只 reject 原始 ID，也未回到只有組前內容。兩條分支均保留故障整個 pending 節點。 | **原始 ID 不是此跨作者續改鏈的完整結算入口。** 多 ID 本身只是表示法觀察；實際能力缺口是無法用原始 ID 一次接受最新版／完整取消此續改鏈。不可因此泛稱所有原生 pending 都失敗。 |
| R01-4 FAIL，2/3 | 原始正文 bold=true。原生 removeMark('bold') 留下 update `properties` 自有 key `bold:undefined`。保留 undefined 的記憶體副本→全新 editor→reject 能恢復 bold；同內容標準 JSON 寫檔→全新 editor，properties 變成 `{}`，reject 後正文在但 bold 未恢復。 | **「標準 JSON 可無損保存待審移除 mark 的必要資訊」在此例不成立。** 這是已實測反例，不只是 source 推測；不能以普通文字 round-trip 的 PASS 宣稱全部 pending 格式均可保存取消。 |

Node `22.12.0`；`platejs`／core `53.3.11`、`@platejs/slate` `53.3.10`、suggestion `53.2.3`、diff `53.0.0`、slate `0.126.2`、React／React DOM `19.2.4`。Node ID profile 為 `{reuseId:true,initialValueIds:'always'}`；native normalization 預設開啟，只有 SuggestionPlugin 內部自行包裝 withoutNormalizing。採 `createSlateEditor`＋`BaseSuggestionPlugin`、`isSuggesting:true`，沒有手寫 suggestion metadata、AI helpers 或低階 apply 偽裝追蹤。

替換用明確固定 fixture 內的原生 `api.nodes`／`api.range` 定位唯一文字 leaf，再 `tf.select`／`tf.insertText`；新增用 `tf.insertNodes`。結算以原生資料讀出的 ID／key 呼叫 `acceptSuggestion`／`rejectSuggestion`，置於公開 `api.suggestion.withoutSuggestions`。只有此 headless 接點經本輪實測，不代表 DOM／IME 或 React UI 已驗。

## R01-3 的原始資料如何解讀

初次 AI 月檢 ID 為 `ZGXJMoVuecTRW9aHmyE5d`；人工續編新增 `5IE5qwahRmkLHapfW5AEX`；再次 AI 續編新增 `m3B3MrQpdikPTtR3cTYVP`。這些 ID 是實際 native 輸出，未指定或複製來強制共組。

最後的月檢節點包含原文、初次 AI 文字、人工文字與最新 AI 文字，附上各自新增／刪除的 pending 標記。只 accept 原始 ID 後，原文刪除，但初次 AI 文字上的初次 insert＋人工 remove、人工文字上的人工 insert＋再次 AI remove，以及最新 AI insert 均仍留在節點內。只 reject 原始 ID 後，原文恢復，後面這些續改文字及 pending 標記也仍在。精確物件由 traces 保留；本輪沒有把所有 leaf 文字直接串起來冒充員工所見正文，也未測 UI 如何呈現各層。

這是**分作者＋只結算原始 ID**的有限測法。未驗同作者續編、依序結算所有 ID、任意跨位置相依群組或正式產品的待審政策；Owner 容許再比較「人工續改是否仍待審」，這項失敗不能替 Owner 選擇政策或自動淘汰框架。若要要求同一產品建議跨作者長期續改仍可整組接受／取消，現有正證不足。

## 唯讀來源核對：確定原因與公開接點

Publisher 為 Plate／udecode。官方固定 source commit `cee7a4ec0328718d8cf147094466b597215f5406`；所有下列來源存取日均為 2026-09-09。套件授權為 MIT；套件 `53.2.3` 不等於 monorepo release `53.3.12`。主線另已核對同日 npm metadata 與 fixed source 55 檔比較；本稿直接證據是本次 lock／實装 package／dist／挑選 source 的保留檔與 hash，不把主線比較冒稱本腳本完成。

| 官方一手來源／版本 | Read/code evidence；與真正實測的關係 |
|---|---|
| [BaseSuggestionPlugin.ts](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/BaseSuggestionPlugin.ts)；固定 commit、MIT | options 定義只有 currentUserId／isSuggesting；公開查詢可讀 nodeId／dataList。React [SuggestionPlugin.tsx](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/react/SuggestionPlugin.tsx) 為 toPlatePlugin(BaseSuggestionPlugin)，仍有 experimental 註解。本次只跑基底 headless，沒有把註解當成新的已測失敗。 |
| [findSuggestionProps.ts](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/queries/findSuggestionProps.ts)；固定 commit、MIT | 新 ID／時間是預設；第 100 行起，同 type 且當前作者相同才沿用鄰接 active suggestion 的 ID。這支持 R3 拆 ID 的解釋；不是任意產品群組合併機制。 |
| [getSuggestionId.ts](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/utils/getSuggestionId.ts)、[acceptSuggestion.ts](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/acceptSuggestion.ts)、[rejectSuggestion.ts](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/rejectSuggestion.ts)；固定 commit、MIT | 最後一個 suggestion key 是 active key；insert/remove 分支按 active data 的單一 ID 匹配，update 分支另查 dataList。支持 R3 中較早 ID 不能順便結算後續 active 層的解釋。 |
| [removeMarkSuggestion.ts](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/removeMarkSuggestion.ts)、[官方 test](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/removeMarkSuggestion.spec.tsx)；固定 commit、MIT | source 第 45–46 行記 `properties:{[key]:undefined}`，官方 test 明確預期此形狀；reject 第 190 行依 properties 的 Object.keys 還原 mark=true。實裝 dist 亦為 `void 0`，再加本輪 memory／JSON 對照，才把 R4 記成真正失敗。 |
| [setSuggestionNodes.ts](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/setSuggestionNodes.ts)、[getSuggestionProps.ts](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/getSuggestionProps.ts)；固定 commit、MIT | **確有公開接點接受指定 ID**：前者的 suggestionId 會建立固定 type:'remove' 的標記，並 setNodes 到範圍；後者的 id 只生成標記物件。兩者不是「接下來整次一般續編沿用此 ID」的設定，不能把存在 id 參數直接宣稱 R3 已被原生覆蓋。本輪未呼叫這些 helper 改造共組。 |
| 實装 `@platejs/suggestion@53.2.3` 的 `dist/index.d.ts`、`dist/index.js` 與 `dist/src-CMqLOrDd.js`；npm lock 中固定 tarball／integrity、MIT | 一般 insertTextSuggestion(editor,text)、deleteSuggestion(editor,range,{reverse})、insertFragmentSuggestion 沒有既有 ID 參數；acceptSuggestion／rejectSuggestion 各收單一 TResolvedSuggestion／suggestionId。未在此固定 package exports／types／source／tests 找到多 ID 結算入口。只讀核對未增加 runtime case。 |

`SuggestionEditorProps.activeSuggestionId` 仍可在 type 與歷史 changelog 看見，但現行 BaseSuggestionConfig 未列此 option，一般 transforms 也未讀它；不能用這個殘留型別宣稱已具備固定群組接點。將多個單 ID accept／reject 逐個呼叫，並自行推導哪些 ID 是同一產品建議，會增加本輪未證的分組與順序責任；本稿沒有實作或推薦這種通用補層。

## 授權、封存與決策界線

`results/dependency-inventory.json` 保留實装 45 個套件名稱、版本、license 宣告與 lock tarball URL。43 個為 MIT、1 個 Apache-2.0；`@platejs/diff` package metadata 未列 license，已讀其封存 LICENSE：slate-diff 衍生部分 Apache-2.0，Plate 修改部分另提供 MIT／Apache-2.0 雙授權。這些皆免費 OSS；本 probe 未取得或使用付費產品。

`source/official-fixed/`、`source/installed-suggestion/`、`source/licenses/` 是只讀原檔副本。`results/source-manifest.json` 記 23 個選定檔的來源及 SHA-256，副本 hash 全相等；編譯 chunk 直接涵蓋上述型別以外的實際行為。首次 `run-hashes.json` 分別綁定原 probe script、package-lock、results、traces；JSON traces 對 undefined 的消失本身是測量內容，所以必須一併保存 inspect 診斷檔。

**Mapping：**R01-1／2 使「未確認的獨立文字建議可取消／接受、不傷別處且能重開」有真正原生正證。R01-3 限制了跨作者持續 pending 的整組結算宣稱；R01-4 限制了含移除 mark 的 pending JSON 持久化宣稱。它們不回答整個框架選型，也不意味員工必須逐筆接受、不准審閱，或應改用永久 pending。

**Unknown／不擴做：**DOM／IME、員工所見刪增與層級的可讀性、表格／巢狀結構、block attrs、相依組策略、批次結算順序、不同作者政策、跨版本、正式 DB 與真 LLM 尚未經本輪驗證。沒有自製 codec、diff、群組索引、歷史／回退引擎，沒有為修反例而增加測試或變更套件。

## R01-F：已知三個成員及結算順序的公平對照（獨立 follow-up）

此段於新實驗執行前記下範圍。原 R01 四組及 2 PASS／2 FAIL 不改；R3 只結算最早 ID，不能單憑這個條件與其他框架的整段範圍結算比較優劣。

沿用已保存的 `results/2026-09-09T14-36-40-805Z/ai-human-ai-pending-value.json`，不再產生新編輯。三個月檢 ID 固定明列為初次 AI `ZGXJMoVuecTRW9aHmyE5d`、人工 `5IE5qwahRmkLHapfW5AEX`、再次 AI `m3B3MrQpdikPTtR3cTYVP`；沒有通用成員發現、分組或相依圖。只以原生 accept／reject 逐一執行四種組合：接受正序、接受反序、拒絕正序、拒絕反序。

每組從相同保存 JSON 另寫獨立輸入副本，再建立全新 editor；保留各 ID 結算後的完整 JSON、原生 dataList 與 operations。接受應得乾淨最新版；拒絕應得乾淨原文；月檢不應殘留 pending，故障整個 pending 節點及交付段應完全不變。最後值再 JSON 重開檢查。文字觀察使用原生 `SkipSuggestionDeletes` 的目前文字投影，另留所有原始文字；**這不代表 React／DOM 可見性已驗**。

只新增 `review-order-followup.mjs` 與新的結果目錄，沿用既有固定 Node／依賴；不安裝、不修改原 script／fixtures／results，不寫 metadata、不用 before-image 恢復、不修 vendor 或造 review engine。即使全失敗也保留首次結果。此對照僅能回答「成員及順序已知時，原生單 ID primitives 能否組合」，不能證明 App 如何正確取得成員、選擇順序或處理任意相依編輯。

### R01-F 首次實測結果

2026-09-09T14:53:39.269Z，**3 PASS／1 FAIL，0 執行錯誤；48 個判斷中 45 個通過**。首次執行 exit code 為 1，失敗材料未改／未重跑。結果目錄為 `results/order-followup-2026-09-09T14-53-39-183Z/`；仍使用 Node 22.12.0、相同固定套件與 Node ID profile。

| 組別 | 明列順序 | 實測結果 |
|---|---|---|
| R01-F1，12/12 PASS | accept：初次 AI → 人工 → 再次 AI | 得到只有最新版文字的乾淨月檢節點；月檢 metadata 消失。故障整個 pending 節點與交付段完全不變；結算後 JSON→新 editor 相等。 |
| R01-F2，12/12 PASS | accept：再次 AI → 人工 → 初次 AI | 同樣得到乾淨最新版；組外 pending、交付段及最終重開皆通過。 |
| R01-F3，9/12 FAIL | reject：初次 AI → 人工 → 再次 AI | 原文、初次 AI 文、人工文全部留下，沒有回到乾淨原文。原生目前文字投影也包含三段，JSON 重開保留同一失敗內容。故障 pending 與交付段仍完整保留。 |
| R01-F4，12/12 PASS | reject：再次 AI → 人工 → 初次 AI | 得到只有原文的乾淨月檢節點；月檢 metadata 消失。故障 pending 與交付段不變；最終 JSON 重開相等。 |

R01-F3 的完整原生文字投影為「僅有月檢約定的專案按月檢查。所有專案都按月檢查。僅有月檢約定的專案按月檢查，並記錄結果。」；預期只有第一句。此結果不是採用 before-image 寫回、改同作者或重新編輯而得。

**額外的讀值限制，不能被 PASS 計數掩蓋：**R01-F3 的 `api.suggestion.nodes` 回報月檢 ID 清單為空，因此該查詢的單項判斷通過；但 `R01-F3-final-value.json` 仍保有初次 AI 與人工兩個 `suggestion_<id>` insert key，只是 `suggestion:true` 已被清掉。原生 nodes source 以 `n[type]` 過濾；[SkipSuggestionDeletes](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/utils/SkipSuggestionDeletes.ts) 也會直接回傳沒有 suggestion flag 的文字，所以殘存文字进入目前投影。完整節點相等判斷與文字判斷仍正確將此組判為 FAIL。**不能以查詢為空推論所有 metadata 已結清**；原 assertion、原始物件與其判斷結果均保留，未在失敗後改腳本湊分數。

**公平比較修正：**R01-3 的原結論限於「只用最早 ID 不能完成整條續改」。R01-F 新增了「已知完整三個成員時，原生單 ID 結算可以組合，且拒絕反序在此固定例成功」的正證，因此不能單憑 R3 推論其他框架的已知範圍方案比較優。正序拒絕的反例也保留，不能把成功的反序稱為所有相依建議的普遍算法。App 的成員邊界、順序決定、跨位置及組外相依仍未知；R01-4 移除粗體的 JSON 反例亦未受此對照影響。

新檔 `review-order-followup.mjs` 在既有 probe 目錄直接以 `node review-order-followup.mjs` 執行。它需要原 R3 保存檔與既有依賴，另讀同層 fixed source 以保存本次使用的 SkipSuggestionDeletes 原檔；沒有變更任何既有 source。新結果目錄含每組輸入／最終 value 的 JSON 與 inspect、所有步驟與 operations 的 `review-order-traces.json`／`.inspect.txt`、`review-order-results.json`、新增原生 helper source 副本與 `run-hashes.json`。封存時原 R3 input 路徑須保留；`run-hashes.json` 記新腳本、來源 input、lock、結果、traces 及實裝 implementation chunk hash，並確認原 R01 script／lock／results／traces 的四個 hash 均未改變。新增檔完整雜湊清單另列 `followup-artifact-hashes.json`。
