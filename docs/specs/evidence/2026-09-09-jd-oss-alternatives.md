# JD 免費開源編輯器底座與修訂層：Lexical／Tiptap／ProseMirror 原始碼核對

**補證狀態（2026-09-09）：**[T02 有限實證與公平比較](2026-09-09-jd-native-pending-review-comparison.md)已安裝固定 1.0.79：獨立文字取消與單組續改結算通過，所測 link attrs 取消及 AttrStep 各有反例。JSON 重開能力須按實測判斷，不用 HTML metadata 問題推定 JSON 也丟失；App groupId／range 與作者合併限制明列。下方未安裝／未執行是原 source 研究時點；T01、Lexical 沒有新增 probe。

查閱日：**2026-09-09**。主題 **JD-R002/C03，G2 官方／作者原始碼證據**。本檔只回答兩條替代路線能否減少自建文件修訂引擎的責任；不選套件、不核准施工、不新增產品政策。

## 0. 本輪邊界與結論

- **Binding decisions：**C01 的可辨識結構＋完整敘述、AI 與人接續同份最新 JD、AI 改動可辨識且人能續編／接受／退回。只考慮免費開源可採用組合；付費功能只能參考。綠地研究，不以舊產品或架構限制方案；不重做既有 LLM／Memory。
- **政策更新：**Owner 最新表示「人改待審內容仍待審 如果不是共識的話也可以改」。因此人工續改的待審歸屬是可以研究後再議的政策，**不是本輪硬性淘汰條件**；也不代表 Owner 已同意人工一改即接受。
- **本輪唯一問題：**Lexical 或 Tiptap／ProseMirror 是否已有可提出完整候選的免費、開源、維護中修訂層？若沒有，缺口能否具體指認，留待共同決定？
- **已讀前置：**[current register](../../current-decisions.md)頂部、[decision process](../../decision-process.md) G2–G5 與 closure、[F01–F05](../2026-09-09-jd-editor-framework-comparison.md)。register 中原付費推薦及較強待審政策需由主線統一更新，本分工不修改 register。
- **完成方式：**官方文件、公開作者倉庫、公開 release／npm 中繼資料、原始碼與既有測試的靜態閱讀。下載只進 `.research-tmp/jd-oss/alternatives/`；未安裝依賴、未執行套件／測試、未呼叫模型、未做 runtime spike。

**研究結論（Caliburn mapping）：**兩條路都有可靠的免費編輯底座，但本輪沒有找到足以直接列為「成熟完整 JD 待審方案」的 Lexical 修訂層。Tiptap／ProseMirror 確有真正開源第三方修訂套件，並非只能買付費功能；其中 `sungkhum/tiptap-track-changes` 可列**有限備選／缺口對照**，但程式寫入追蹤、保存重開、語意群組與任意區塊操作仍有明確缺口。`davefowler/prosemirror-suggestion-mode` 的作者仍標 WIP，另有實際定位及 HTML metadata 問題，不能用其測試數量或 API 名稱升格為成熟候選。**不是「沒有滿足全條件的套件，所以立即自造引擎」的結論。**

標記：**Fact** 是官方／作者直接公開契約或程式路徑；**Inference** 是由程式推得但未實跑；**Mapping** 是本產品取捨；**Unknown** 是此證據不能回答。

## 1. 版本、授權及來源凍結

日期為 UTC 發佈／commit 日期；「主線 package version」與「正式 release」刻意分開。

| 元件 | 本輪核對版本／來源 | 授權、維護證據與限制 |
|---|---|---|
| Lexical | 正式 [v0.50.0](https://github.com/facebook/lexical/releases/tag/v0.50.0)，2026-09-02；另讀主線 [`e0e53e14`](https://github.com/facebook/lexical/commit/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc)，2026-09-09，package 仍寫 0.50.0 | [MIT LICENSE](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/LICENSE)；官方主線持續更新。下文主線新 API／tests 不冒稱全部已在 0.50.0 tag 驗過 |
| Tiptap core | 正式 [v3.31.3](https://github.com/ueberdosis/tiptap/releases/tag/v3.31.3)，2026-09-04；主線 [`7ab690e5`](https://github.com/ueberdosis/tiptap/commit/7ab690e5056fe999988552822c4fc1b1064bf094) package 是 3.30.3 | [MIT LICENSE](https://github.com/ueberdosis/tiptap/blob/7ab690e5056fe999988552822c4fc1b1064bf094/LICENSE.md)。`CommandManager` 與 HTML attribute parser 另直接讀 v3.31.3 tag，關鍵路徑相同；不混入付費 Toolkit／Tracked Changes |
| prosemirror-transform | npm **1.12.1**，2026-09-02，gitHead `43af0b20`；讀[公開發佈原始碼包](https://registry.npmjs.org/prosemirror-transform/-/prosemirror-transform-1.12.1.tgz)內 `src/step.ts`、`src/transform.ts`、LICENSE | MIT。官方 repository 已指向 [code.haverbeke.berlin](https://code.haverbeke.berlin/prosemirror/prosemirror-transform)；不是因 GitHub 封存而停止發佈 |
| prosemirror-changeset | npm **2.4.2**，2026-08-21，gitHead `ba47a84d`；讀[公開發佈原始碼包](https://registry.npmjs.org/prosemirror-changeset/-/prosemirror-changeset-2.4.2.tgz)內 `src/changeset.ts`、`src/diff.ts`、tests、LICENSE | MIT；[官方新位置](https://code.haverbeke.berlin/prosemirror/prosemirror-changeset)。不是完整修訂插件 |
| prosemirror-state | npm **1.4.4**，2025-10-23，gitHead `d6fdcd19`；讀[公開發佈原始碼包](https://registry.npmjs.org/prosemirror-state/-/prosemirror-state-1.4.4.tgz) | MIT；舊 npm repository metadata 仍指 GitHub；[倉庫 README](https://github.com/ProseMirror/prosemirror-state)已指向新站。不能只依單一 metadata 判斷 canonical location |
| sungkhum/tiptap-track-changes | [package 0.2.1](https://github.com/sungkhum/tiptap-track-changes/blob/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/package.json)；主線 [`753eef71`](https://github.com/sungkhum/tiptap-track-changes/commit/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22)，2026-05-07，修正 view mode 唯讀 | 有 [MIT LICENSE](https://github.com/sungkhum/tiptap-track-changes/blob/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/LICENSE)，Tiptap 2／3 peer range、Vitest、prepublish build＋test。非官方維護；不能由近期一次修正推得長期維護承諾 |
| davefowler/prosemirror-suggestion-mode | [package 1.0.79](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/package.json)；主線 [`e61b70c3`](https://github.com/davefowler/prosemirror-suggestion-mode/commit/e61b70c3cd313979778677bb448b13c0a78cfa20)，2025-03-31 | README／package 宣告 MIT；本次主線 archive **沒有獨立 LICENSE 檔**，GitHub API license 為 null。這是授權材料完整性的缺口，非逕行斷言不可用。README 仍 [WIP／known issues](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/README.md)。repo pushed_at 是 2026-08-20，但不能冒稱主線 implementation 更新於該日 |
| chenyuncai/tiptap-track-change-extension | [package 1.0.3](https://github.com/chenyuncai/tiptap-track-change-extension/blob/3e1f93e2754bbfcb0843208a1ba44298871a7246/package.json)；主線 [`3e1f93e2`](https://github.com/chenyuncai/tiptap-track-change-extension/commit/3e1f93e2754bbfcb0843208a1ba44298871a7246)，2023-08-30 | [MIT LICENSE](https://github.com/chenyuncai/tiptap-track-change-extension/blob/3e1f93e2754bbfcb0843208a1ba44298871a7246/LICENSE)；Tiptap 2 beta peer range；package 無 test script，下載樹未見測試。只保留沿革／實作參考，不列維護中成熟候選 |

**來源限制：**ProseMirror 的 GitHub repositories 於 2026-04-01 封存並在 README 指向新站；[現行官方範例](https://prosemirror.net/examples/track/)也把完整 source 連到新站。新站頁面與 API 本輪皆回 403，不能宣稱已逐行讀其最新主線。已改讀發布者的最新 npm source tarball；transform／changeset 的發佈日期晚於搬家，直接排除「封存＝淘汰」誤判。舊 GitHub snapshot 只用於可點閱歷史 code／tests 對照，不當最新維護位置。

## 2. Lexical：強底座，未找到現成完整修訂層

### L01 同一最新文件與保存接點

**Fact：**EditorState 是不可變快照；改動在 `editor.update` 內進行。`getEditorState`／`parseEditorState`／`setEditorState` 支援 JSON 保存與讀回。DOM 不是內容 authority；非同步 commit 尚未完成就保存可能讀到舊狀態，官方提供 discrete update。這解決編輯器內容接點，沒有自帶產品的 pending／accepted 語意。[Editor State](https://lexical.dev/docs/concepts/editor-state)

**Fact：**NodeState 可把自訂 metadata 放在任何 node／root，參與 JSON、history 與 reconciliation；預設 JSON 位於 `$`，可宣告 flat。不同 NodeState 的 TextNode 不會自動合併。官方 source tests 有 export→import 對等與 copy 行為斷言。[NodeState](https://lexical.dev/docs/concepts/node-state)、[LexicalNodeState tests](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/packages/lexical/src/__tests__/unit/LexicalNodeState.test.ts)

**Mapping：**可承載 JD 的 section／task 身分、來源或審閱資料；「能放 metadata」不等於已實作建議生成、人工續編歸屬、拒絕重放與語意分組。只保存 JSON 也不等於完整審閱 session 已跨重開恢復。

### L02 NodeKey 不能當 JD 永久身分；split 也不是免費身分策略

**Fact：**NodeKey 不序列化，JSON／HTML 讀回會產生新 key；key 只在所屬 EditorState 有意義，不應自訂覆寫。[Key Management](https://lexical.dev/docs/concepts/key-management)

**Fact：**主線 `splitText` 第一段通常保留原 TextNode，其餘段產生新 TextNode，並把原 NodeState clone 到新片段。NodeState 的 `resetOnCopyNode` 只聲明針對 `$copyNode`；測試也分別驗 reset／preserve。[splitText source](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/packages/lexical/src/nodes/LexicalTextNode.ts#L989)、[NodeState source](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/packages/lexical/src/LexicalNodeState.ts#L271)

**Inference：**若將唯一內容 ID 直接放在可拆的 text NodeState，clone metadata 可能讓多片段帶相同 ID；「metadata 有保存」不能推成 split／copy／move 的永久身分與 lineage 均已解決。適當的 JD block node／ID 策略須另定。區塊搬移可用 node-tree API，但「被移動的內容與審閱群組共同拒絕」仍 **Unknown**。

### L03 Undo 與失敗恢復有底層支持，沒有 review 結果契約

**Fact：**`@lexical/history` 有 undo／redo stack，包含 EditorState；[history source](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/packages/lexical-history/src/index.ts)及 [history tests](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/packages/lexical-history/src/__tests__/unit/LexicalHistory.test.tsx)提供一般編輯安全網。更新錯誤路徑呼叫 `onError`，並有恢復 current EditorState 至 DOM 的程式碼。[LexicalUpdates](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/packages/lexical/src/LexicalUpdates.ts#L1241)

**Unknown：**這些不是多次 AI 操作、資料庫保存、外部工具與 review status 的共同 all-or-nothing 承諾；history grouping 不是員工可理解的語意審核群組。尚未發現已測的「AI 待審→人工修改→拒絕→保存重開→再 undo」完整免費層。

### L04 查到的同名功能與來源都不足以當修訂產品

**Fact：**官方 feature request [#8754](https://github.com/facebook/lexical/issues/8754)於 2026-06-26 提議 suggestion-mode comments，查閱時仍 Open。它是使用者 feature request，**不是官方承諾，單憑 issue 也不能證明任何第三方都不存在**。

**Fact：**主線搜尋碰到 `ReviewExtension`，但 source 是 0–5 星等、author slot、testimonial prose 的自訂節點示範；不是 accept／reject 修訂功能。[ReviewNode](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/packages/lexical-playground/src/plugins/ReviewExtension/ReviewNode.tsx)、[ReviewNode tests](https://github.com/facebook/lexical/blob/e0e53e14e29c17a3adfd0ec4d8e3b31ba08771dc/packages/lexical-playground/__tests__/unit/ReviewNode.test.ts)

**研究範圍結論：**在官方 packages／playground／docs 與針對 Lexical track-changes／suggestion-mode 的公開倉庫搜尋中，沒有找到同時具備可辨識作者、接受／拒絕、持久修訂 metadata、維護版本及完整測試的現成免費層。網路 discussion 中「自己建 suggestion layer」的回覆不是採用證據；本案不依它推薦另一套平行 operation store。**Lexical 列底座，不列完整修訂候選；外部成熟層的存在性保留 Unknown。**

## 3. Tiptap／ProseMirror：哪些是免費底層契約

### P01 `Suggestion` 名稱不能當 Track Changes

**Fact：**Tiptap 開源 `@tiptap/suggestion` 提供 trigger character、query、items、選單與插入 command 等接點，對應 mention／autocomplete，不是持久修訂及 accept／reject。[官方 Suggestion utility](https://tiptap.dev/docs/editor/api/utilities/suggestion)、[package source](https://github.com/ueberdosis/tiptap/tree/7ab690e5056fe999988552822c4fc1b1064bf094/packages/suggestion/src)

**Mapping：**免費 core、免費 Suggestion 和另售 Tracked Changes 必須拆開；F01–F03 的付費能力不能移植成 OSS 既有能力。

### P02 Transaction／Step／Mapping 能做定位與失敗判斷，沒有自動產品原子性

**Fact：**Step 代表單一文件變更，通常只適用於建立時的文件；有 `apply`、`invert`、`map`、`toJSON`／`fromJSON`。`map` 可回 null，`StepResult` 明分 transformed doc 與 failure。Transform 累積 steps、各 step 前文件及 mapping；`step` 失敗丟錯，`maybeStep` 跳過失敗 step，並不清空已成功 steps。已直接讀 **1.12.1** source；[官方介面](https://prosemirror.net/docs/ref/#transform.Step)、[新版 source package](https://registry.npmjs.org/prosemirror-transform/-/prosemirror-transform-1.12.1.tgz)、[可點閱舊版同路徑](https://github.com/ProseMirror/prosemirror-transform/blob/662b7a937bafde19b7e2a83241dbc8888e257c89/src/transform.ts#L46)

**Fact：**Tiptap **v3.31.3** 的 chain `run()` 先依 dispatch 條件提交 transaction，才回傳各 callback 是否全為 true；不以 callbacks 全成功作 dispatch gate。[CommandManager](https://github.com/ueberdosis/tiptap/blob/v3.31.3/packages/core/src/CommandManager.ts#L64)

**Inference：**某 command 回 false，不足以證明整批沒有改文；App 必須讀真實結果、定義何時不 dispatch／何時報部分成功。底座允許組裝單次交易，不等於 AI 批次或語意群組天然 all-or-nothing。映射後位置仍須對目前內容／身分檢查；mapping 不理解哪一項 JD 工作責任應屬同一審閱群組。

### P03 免費 UniqueID 有用，但不是完整身分／修訂分組

**Fact：**開源 `@tiptap/extension-unique-id` 提供可序列化 node attribute、缺 ID 補值、changed ranges 內重複 ID 處理、paste 清除舊 ID 再產生、依 drag 來源／copy 行為決定是否重建等程式路徑。[UniqueID source](https://github.com/ueberdosis/tiptap/blob/7ab690e5056fe999988552822c4fc1b1064bf094/packages/extension-unique-id/src/unique-id.ts)、[tests](https://github.com/ueberdosis/tiptap/tree/7ab690e5056fe999988552822c4fc1b1064bf094/packages/extension-unique-id)

**Mapping：**比自行把位置／HTML hash 當永久 ID 更有現成接點。它仍沒有定義「一任務拆兩任務」「移動但責任不變」「合併後舊 ID lineage」的 JD 語意，也沒有證明與任一第三方修訂 plugin 組合後，copy／split／reject 都保持正確。這些屬 **Unknown**，不能只單測 UniqueID 就驗收審閱整體。

### P04 `prosemirror-changeset` 是差異集合，不是待審引擎

**Fact：**2.4.2 將 step maps 濃縮成相對起始文件與目前文件的插入／刪除 spans，可帶 metadata；有 startDoc、Change JSON 與重建方法。逐次加入與一次加入可能因 diff 簡化得出不同範圍。預設 encoder 比字元及 node type，忽略 marks／attributes；`addSteps` 從 map 取得替換範圍，無變更 map 時回原集合。[新版 source／tests](https://registry.npmjs.org/prosemirror-changeset/-/prosemirror-changeset-2.4.2.tgz)、[可點閱舊版同契約](https://github.com/ProseMirror/prosemirror-changeset/blob/3e1c6668116383b5bd344f3d543b7e2691c15458/src/changeset.ts)

**Inference：**它能支援差異顯示，但預設不是完整格式／metadata 追蹤；自行換 token encoder 也不能直接假定補齊只有 mark／attribute 改變時的空 map。沒有內建 accept／reject 狀態、人工續改政策、review UI 或相依群組。保存 `Change` 也不是保存整個 review session。

### P05 官方 track example 是 commit／revert 範例

**Fact：**[現行官方範例](https://prosemirror.net/examples/track/)記錄 commits、未 commit 的 inverse steps／maps 與 blameMap；revert 前要求先 commit 尚未提交的內容。revert 把舊 inverse steps 映射到現在，null 會跳過，`maybeStep` 僅把成功結果接入 remap。

**Inference：**這展示映射及回退機制，不能等同「AI pending、人工任意續改、接受最新版、拒絕完整相依群組」。範例的 plugin state 沒顯示保存／重開實作，也沒把每個失敗 step 轉成面向員工的審核結果。ProseMirror `EditorState.toJSON`／`fromJSON` 可選 pluginFields，但 plugin 必須自己提供序列化方法；一般 state JSON 不會自動帶上任意 plugin history。[state source](https://github.com/ProseMirror/prosemirror-state/blob/ffad5d9450a0b93438be53a801deee1a223a81bf/src/state.ts#L207)

## 4. 真正第三方免費修訂層

### T01 sungkhum/tiptap-track-changes 0.2.1

它有實際 schema、commands、plugin 與測試，不能一概說「OSS 沒有 Track Changes」；但本案也不能把它當已驗證完整成品。

| 檢查項 | 已有原始碼／測試證據 | JD 的差距與證據等級 |
|---|---|---|
| 待審資料與接受／退回 | insertion／deletion／formatChange marks；changeId、author、timestamp；替換用同一 changeId 的刪＋增；commands 掃描該 ID 各位置處理 | **Fact：**有持久文件內資料形狀，不只有 decoration。**Unknown：**跨操作語意相依群組與拒絕衝突 |
| 人工續編 | suggest mode 攔文字輸入、Backspace／Delete／Enter／paste；純插入可重用同作者相鄰 insertion mark；刪自己的 insertion 有直接刪掉路徑，刪別人的內容有 deletion mark | **Fact：**有人機續編接點。**Unknown：**AI 作者與員工作者重疊修改後，如何接受／退回整體最新版；不以「人改仍待審」政策作硬淘汰 |
| AI 程式寫入 | appendTransaction 的文字 safety net 限 `uiEvent`／`composition`，明確略過 programmatic changes；格式 AddMark／RemoveMark 另處理 | **Fact：缺口。**不能只開 suggest mode，就宣稱 `setContent`／程式 insert／replace 會形成完整可拒絕 AI 修訂。尚需可驗證接線，不能先承諾微小補丁即可 |
| Undo／redo | `undo-redo.test.ts` 有 undo insertion／deletion、redo、undo accept 恢復 marks；history transactions 跳過重標記 | **Fact：**有真實斷言。名為 undo-after-reject 的案例只確認 `can().undo()`，未檢查恢復內容；不是完整 reject undo 保證。以上均為讀測試，沒有本輪通過結果 |
| JSON 保存／重開 | marks attrs 及 block `dataTracked` 位於 ProseMirror doc，底座 JSON 可承載 | **Inference：**JSON 能保留資料形狀。**Unknown：**未找到 destroy→新 editor 讀回→續編→accept/reject 等完整鏈測試；mode、author、onStatusChange 是 runtime storage/options，不能由 doc JSON 自動推得持久 |
| HTML 保存／重開 | insertion／deletion `renderHTML` 輸出 `data-change-id`／`data-author-id`／`data-author-name`；`addAttributes` 沒定義對應 parseHTML；timestamp 不輸出 | **Inference：具體差距。**Tiptap v3.31.3 預設 parser 讀 `getAttribute(item.name)`，會找 changeId 而非 data-change-id；不能宣稱 HTML 往返保持 ID／作者／時間。block dataTracked 有單獨 JSON parse，不能替 inline marks 補證 |
| 區塊 split／join／type | Enter 用 `paragraphInserted`；刪段落邊界用 `boundaryDeleted`；`trackSetNode` 保存 originalType／attrs，可 accept／reject | **Fact：**涵蓋部分結構操作。**Unknown：**任意拖移、nested list／table、自訂 JD block、split 與後續人工／AI 修改重疊的完整回退 |
| CJK／輸入法 | 有複雜文字測試；輸入中 composing 跳過 handler，事後 safety net 補 insertion；grapheme utilities 處理刪字 | **Fact：**測試有關注此面向。測法主要是 jsdom 直接呼叫 handlers；**Unknown：**繁中 OS 輸入法實際組字、composition 刪改及 undo 的瀏覽器行為 |
| 部分失敗／結果 | 個別接受／退回 command 回 boolean；單一 ID 沒找到時也可回 true；join 用 canJoin 條件；status callback 並非逐 step 結果集合 | **Unknown：**沒有可證明完整批次 all-or-nothing／部分失敗報告與恢復的契約。不能拿回 true 當全組業務成功 |

上述直接來源：[extension／block attributes](https://github.com/sungkhum/tiptap-track-changes/blob/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/src/extension.ts)、[plugin／programmatic guard](https://github.com/sungkhum/tiptap-track-changes/blob/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/src/suggest-mode-plugin.ts#L716)、[commands](https://github.com/sungkhum/tiptap-track-changes/blob/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/src/commands.ts)、[insertion mark](https://github.com/sungkhum/tiptap-track-changes/blob/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/src/marks/insertion.ts)、[Tiptap HTML parser](https://github.com/ueberdosis/tiptap/blob/v3.31.3/packages/core/src/helpers/injectExtensionAttributesToParseRule.ts)、[undo tests](https://github.com/sungkhum/tiptap-track-changes/blob/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/tests/undo-redo.test.ts)、[multi-author tests](https://github.com/sungkhum/tiptap-track-changes/blob/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/tests/multi-author.test.ts)、[完整 tests 樹](https://github.com/sungkhum/tiptap-track-changes/tree/753eef717f7ffaed0cb0e451ecb8b93f5ddaca22/tests)。

**測試閱讀陷阱：**multi-author 中「author 2 can delete author 1s text」案例從普通 `Hello world` 開始，沒有先建立 author 1 insertion；它證明 author attribution 的刪除，**不是跨作者 nested pending→review 證據**。不可只由 test name 摘要為能力已證實。

**Mapping：**可當有限開源備選，若主線較完整候選有缺口，可對照它的文字與段落實作。尚不推薦用它接完整 JD，再把 programmatic tracking／保存／群組無限補進自製層。HTML 不是必選保存格式；指出 HTML 問題也不能反過來斷言 JSON 完全不可用。

### T02 davefowler/prosemirror-suggestion-mode 1.0.79

**Fact：**有 insertion／deletion marks、username＋自訂 data、plugin metadata 切換 suggestion mode、依範圍接受／退回、`createApplySuggestionCommand` 文字建議接點。plugin 攔 transaction steps，包含 ReplaceStep／ReplaceAroundStep／AddMark／RemoveMark，與 T01 的 UI-only safety net 不同。內層既有 suggestion 有沿用 mark／略過再包裝路徑。[plugin](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/src/plugin.ts)、[schema](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/src/schema.ts)

但以下差距會改變是否採用，不是一般「整合再說」：

1. **定位會取第一匹配（Fact）：**applySuggestion 的 dry run 要求剛好一個匹配；真正 dispatch 路徑若多匹配則警告後仍採第一筆。重複句子的 JD 不能把 dry-run 契約誤認為執行時拒絕歧義。[applySuggestion.ts](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/src/applySuggestion.ts#L128)
2. **HTML metadata 未保存（Fact／Inference）：**schema 的 DOM 只輸出 suggestion 標記與 class，沒有輸出／讀回 username 或 data；HTML round-trip 的作者／自訂資料無由恢復。JSON 形狀則能帶 attrs；完整重開後審核仍 Unknown。[schema](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/src/schema.ts)
3. **接受／退回靠 range，非穩定審核 ID（Fact）：**processSuggestionsInRange 掃 range 的 marks 再映射位置；沒有原生 cross-location semantic group ID，雖然自訂 data 可承載 App 資料。刪空 node 的處理還留 TODO。[acceptReject](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/src/acceptReject.ts)
4. **結構與 tests 要分開看（Fact）：**plugin 對 open blocks 有補 pilcrow／零寬字元的路徑。`disabled-openblocks.ts` 不符合 [Jest testMatch](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/jest.config.mjs)，其中跨 list 測試仍註解。不能因檔案存在就說已在標準測試中驗證。[disabled-openblocks](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/test/prosemirror/disabled-openblocks.ts)
5. **有測試不等於 JD 成品（Fact）：**tests 包含 undo、paste、格式、ReplaceAround、多 step；HTML serialization test 只確認 span 標記與文字，沒有往返 username／data。全部本輪未執行。[schema integration tests](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/test/integration/schema.integration.test.ts)、[steps tests](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/test/integration/suggestions.steps.test.ts)
6. **維護／授權材料（Fact）：**作者仍標 WIP；主線 commit 停在 2025-03-31；MIT 宣告缺獨立 LICENSE。本輪不替作者補授權文本，也不由 pushed_at／星數推成熟度。

**Mapping：**研究備查，不列完整成熟候選。即使 Owner 改成「人工修改即可接受」，定位歧義、HTML metadata、區塊與穩定審核單位缺口仍存在，不能把政策放寬當全問題消失。任意 block move／ID lineage、部分失敗後重新審核與跨重開 undo 仍 **Unknown**。

### T03 chenyuncai/tiptap-track-change-extension

[README](https://github.com/chenyuncai/tiptap-track-change-extension/blob/3e1f93e2754bbfcb0843208a1ba44298871a7246/README.md)與[單檔 source](https://github.com/chenyuncai/tiptap-track-change-extension/blob/3e1f93e2754bbfcb0843208a1ba44298871a7246/src/index.ts)顯示有 acceptChange／rejectChange 及作者欄位。但 2023 主線、Tiptap beta peer range、未見測試與目前維護證據，不足以符合本輪要求。停止在來源排除，不做安裝／修補以湊第三候選。

## 5. 能力矩陣：現成層與底座不可混算

「局部」代表 source 已有行為、產品組合未驗證；「Unknown」不等於不存在。

| JD 所需效果 | Lexical OSS | Tiptap／ProseMirror OSS 底座 | ＋T01 sungkhum | ＋T02 davefowler |
|---|---|---|---|---|
| 同份結構文件供人直接改 | 有 | 有 | 沿底座 | 沿底座 |
| 可保存 metadata／文件身分接點 | NodeState；NodeKey 不持久 | schema attrs；免費 UniqueID | changeId 與 author；不等同 JD ID | username／data；無專用 review ID |
| AI 改動形成可接受／退回修訂 | 未找到現成層 | 未附原生審核層 | 程式文字改動不自動追蹤 | 有文字工具／step interception；歧義取第一筆 |
| 人改待審內容 | 無現成 review 政策 | 無現成 review 政策 | 局部續編，跨作者／整組政策 Unknown | 既有 mark 內續編，完整政策 Unknown |
| 接受／退回單位 | 需別的修訂層 | Step／changeset 不是產品單位 | changeId；語意相依群組 Unknown | range；語意相依群組 Unknown |
| Undo／redo | 一般編輯已有 | 一般編輯已有 | 局部 review tests | 局部 review tests |
| JSON 保存 pending 資料形狀 | 可承載，無現成 pending | 可承載；plugin state 要自行接 | 文內 attrs 可承載；完整重開 Unknown | 文內 attrs 可承載；完整重開 Unknown |
| HTML 完整修訂 metadata 往返 | 需自訂節點／import export | 依 schema／extensions | 靜態來源顯示 inline metadata 缺口 | source 明確不輸出 author／data |
| block split／type／move＋reject | 基礎 node API，review Unknown | structure transforms，review Unknown | split／boundary／type 局部；move Unknown | ReplaceAround／open-block 路徑；完整回退 Unknown |
| 批次部分失敗與恢復 | 底座 error path；無 agent 結果契約 | StepResult／mapping 接點；chain false 非全批回滾 | 未有完整結果／恢復契約 | 未有完整結果／恢復契約 |
| 本輪成熟完整候選資格 | **底座** | **底座** | **有限備選，不列成熟完整方案** | **WIP 研究備查** |

## 6. 停止條件、可討論方案與下一 gate

**廣搜到此停止。**決定性主張已有直接 source 或 Unknown；新發現的同類小插件沒有降低已識別責任。不為湊數擴大到多年未維護的 contenteditable 引擎，也不把一般 diff／comment／autocomplete 加總成完整審核能力。

對主線提供三個邊界清楚的處置，這些是 **Mapping，尚未由 Owner 決定**：

1. **優先核對其他已有免費完整修訂層的候選。**由平行研究比較其 source 覆蓋；本檔的 Lexical／PM 保持底座，T01 保持有限對照。若已有更完整層，不再做這兩條路的無差別 spike。
2. **若需要保留 Tiptap，先列出願意接受的缺口及測試範圍。**T01 可先只驗 JSON 持久、AI 程式寫入與人工續編的最小全鏈，而非先承諾補齊任意 Word 功能；但此次研究沒有授權安裝或試做。
3. **若 OSS 皆缺產品必需能力，再共同決定取捨。**可調整人工續改待審政策或選擇明確有限的接線成本；不得默認 auto-accept、全文回覆覆蓋或永久自建修訂引擎。

若主線後續取得 isolated spike 授權，能改變本輪判斷的最少情境是：

- 固定完整 JD、有重複句子與多區塊；AI 插入／刪除／改字／改 node metadata 各能辨識，員工可續編。
- 接受／退回一項不誤動無關內容；對重疊／移動／拆分要有可說明結果，含 Owner 最後選定的人工待審政策。
- 保存→完全新 editor→重新讀回→續編→接受／退回；比對 content IDs、pending IDs、作者、改前／改後文字及結果。
- 有效操作＋失敗操作在同批，結果如實顯示哪些已改，拒絕或重試不重複套用；不把 boolean 當整批成功。
- 實際繁中輸入法組字與 undo／redo；jsdom handler 斷言不能取代這項驗收。

**停止／回報門檻：**需複製大量內部 step 邏輯、引入另一份平行文件／workflow store、無法保留身分及待審資料、拒絕誤刪人工內容、失敗被默認當接受，或套件實際授權／版本與證據不符時，帶源碼與失敗情境回到 Owner 討論；不靜默補成新引擎。

## 7. Closure

- **Finding：**Lexical 與 PM 的免費底座能力充分；找到兩套真實第三方修訂層，且定位、序列化、程式寫入、區塊及維護責任均有可指認差距。沒有已證實成熟完整候選。
- **Status：**G2 證據交付；套件與產品政策仍 OPEN。這不是「OSS 不可能」或「必須買付費」的裁決。
- **Sources：**上方凍結版本、官方文件、作者 source／tests；ProseMirror 新站 403 已由新版 npm source 補足可核對範圍。
- **Affected artifact：**只新增本檔；暫存 source 不作產品依賴。
- **Reopen trigger：**已維護免費修訂層的新 release／原始碼、官方反證、Owner 改需求，或核准 bounded spike 的真實結果。
- **Next gate：**主線合併 OSS 比較、寫回 current register，呈現缺口與可接受取捨，再決定候選；本檔不授權 G5／production。

**驗證聲明：只有靜態 source／tests／metadata 閱讀；沒有本輪測試通過數、瀏覽器演練、模型效果或產品整合驗收。**
