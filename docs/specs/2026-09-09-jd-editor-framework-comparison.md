# JD 編輯框架：原生能力、細節差距與選型證據

**2026-09-09 後續限制：**Owner 已限定免費開源並要求執行研究計畫。下方 F 表中的付費 Tiptap Toolkit／Tracked Changes、CKEditor premium 僅保留為比較沿革，原優先排序不再有效；最新採用候選與原始碼證據依[免費開源能力與缺口研究](2026-09-09-jd-oss-editor-capabilities-and-gaps.md)。Owner 另容許重議「人改 pending 仍 pending」，不可再以該條單獨淘汰開源方案。

JD-R002/C03；查閱日 **2026-09-09**。這是 G2 證據／比較，不是套件採用、購買或施工授權。結論在[整體入口](2026-09-09-ai-document-app-composition-research.md)，建議流程在[可執行方案](2026-09-09-jd-ai-editing-executable-proposal.md)。既有文件產品證據保留於 [E01–E20](2026-09-09-jd-document-model-official-evidence.md)；agent 往返及錯誤見 [R01–R10](2026-09-09-jd-ai-app-runtime-official-evidence.md)。不重開職務內容或 Memory。

**閱讀方式：**Fact 是來源明文；Mapping 是針對 C01／C02 的選擇；Unknown 不是沒有功能，而是目前證據不足，不能當作已覆蓋。官方範例不等於完整成品；latest 文件也不等於任何舊安裝版本可用。

## F01 Tiptap 的兩種接法不能混拼

來源：[AI Toolkit overview](https://tiptap.dev/docs/ai/ai-toolkit/overview)、[Client tools](https://tiptap.dev/docs/ai/ai-toolkit/client/agents/tools)、[Workflows](https://tiptap.dev/docs/ai/ai-toolkit/client/api-reference/workflows)。主線直接查閱正文。

- **Fact：**目前 overview 仍列 Client Toolkit 為 embedded client 選擇；其他路徑可用 cloud／on-premise。總產品標 Paid add-on／Beta，不因它列在 Other Options 就推論已淘汰。框架無關不等於各部署路徑契約相同。
- **Agent 路徑：**原生 `tiptapRead`、`tiptapEdit`、`tiptapReadSelection`；comments 另選。模型使用套件的工具 definitions，browser toolkit 執行。
- **Workflow 路徑：**`createTiptapEditWorkflow` 提供 prompt／JSON schema，模型返回操作；`tiptapEditWorkflow` 接 readResult 作 stale-read detection。其操作是 replace／insertBefore／insertAfter，target 為 read 產生的六字元 hash 或 doc，content 為 HTML，回傳逐操作結果。
- **界線：**上述 object schema 屬 workflow；agent hooks 的公開例子是 tuple。不能混成一份「官方通用 schema」。hash 是讀取定位 token，不是 JD 永久身分，不能自行存成 task_id。
- **Mapping：**主顧問優先 agent tool 路徑，不額外加一個必跑的 workflow 模型。workflow 留作特定整段整理的備選；不直接沿範例替換全文。

## F02 Tiptap 執行結果與部分失敗

來源：[Execute tools](https://tiptap.dev/docs/ai/ai-toolkit/client/api-reference/execute-tool)、[Edit hooks](https://tiptap.dev/docs/ai/ai-toolkit/client/advanced-guides/tiptap-edit-hooks)、[Review options](https://tiptap.dev/docs/ai/ai-toolkit/client/api-reference/review-options)。主線直接查閱正文。

- **Fact：**`executeTool` 回傳 output、hasError、unknownTool、docChanged；activeSelection 可隨 transaction 映射。`streamTool` 可在生成結束前套用內容。
- **Fact：**experimental beforeOperation 可查看目前 transaction 的 doc、解析後範圍及插入／刪除 fragment，選擇接受、拒絕或調整；拒絕一項會記 error、跳過該項，再繼續後續操作。**所以批次不是已證明的 all-or-nothing。**
- **Fact：**review mode 有 disabled、review、preview、trackedChanges；後者需另裝擴充。runtime 可帶作者資料；diff utility 的細分方式可配置，不能只看綠紅色就判定保存／核准成立。
- **Mapping：**第一接線先不串流套用文件；仍可串流聊天及進度。完整工具結果送回模型；hasError 與 docChanged 同時為真時，要先重讀目前內容再修，不能盲目重送整批。這降低中途狀態，不代表已解決跨操作原子性。

## F03 Tiptap：人改 AI 待審內容不是範例自然就會做到

來源：[Tracked Changes integration](https://tiptap.dev/docs/ai/ai-toolkit/client/agents/review-changes/tracked-changes)、[Advanced usage](https://tiptap.dev/docs/tracked-changes/usage/advanced-usage)、[Tracked Changes changelog／0.10.2](https://tiptap.dev/docs/resources/changelog/pro-extension-tracked-changes)。主線與獨立研究皆核對。

- **Fact：**整合頁仍明標 Alpha／Experimental，且 Tracked Changes 另售。Toolkit 暫時建議 decorations 與文件內持久 tracked changes 不同，見 E10–E15。
- **Fact：**AI 套用時範例要求 tracking disabled，由 reviewOptions 建議模式產生修訂；但 changelog 明說：disabled 時在 pending mark 內打字，插入的是 untracked 文字，原 mark 被切開。
- **Fact：**跨作者 inline 巢狀修訂：接受外層會留下內層 pending；拒絕外層則一起移除內層。block-level nesting 未支援。自動相鄰分組不是語意相依分組。
- **結論：**直接複製官方 demo，不能宣稱已符合 C02「人改後仍待審、接受整組最新版」。需要區分 AI 執行期間、人工編輯期間及是否落在既有待審範圍；具體 tracking／group 接點須驗證，不能一句 enabled=true 就宣稱解完。

## F04 CKEditor：持久審閱有直接契約，新 AI patch 路徑另有風險

來源：[Track Changes](https://ckeditor.com/docs/ckeditor5/latest/features/collaboration/track-changes/track-changes.html)、[Integration](https://ckeditor.com/docs/ckeditor5/latest/features/collaboration/track-changes/track-changes-integration.html)、[Adapter](https://ckeditor.com/docs/ckeditor5/latest/api/module_track-changes_trackchanges-TrackChangesAdapter.html)、[TrackChangesEditing](https://ckeditor.com/docs/ckeditor5/latest/api/module_track-changes_trackchangesediting-TrackChangesEditing.html)。獨立研究核對原生 API；主線核對官方搜尋及相關文件，不聲稱每份繼承 API 全文逐行閱讀。

- **Fact：**standalone Track Changes 不要求多人協作；文件 markers、suggestions metadata、作者資料有保存／回載方法及 adapter。跨作者切開建議有 originalSuggestionId lineage，但不等於我們的整組審核。
- **Fact：**multi-range insertion／deletion 有現成 API；insertion 的 range 需含單一 element、不可為 text range、不可與其他 suggestion 相交。不能從此推論任意跨位置的插入＋刪除＋屬性修改皆可當一組。
- **Fact：**自訂功能需要[追蹤修訂整合](https://ckeditor.com/docs/ckeditor5/latest/features/collaboration/track-changes/track-changes-custom-features.html)，不是自訂 editor command 自動有完整 reject 行為。

新路徑另核對：[DocumentCompare API](https://ckeditor.com/docs/ckeditor5/latest/api/module_ai_aisdk_documentcompare-DocumentCompare.html)、[Patch](https://ckeditor.com/docs/ckeditor5/latest/api/module_ai_aisdk_documentcompare-DocumentComparePatch.html)、[Snapshot](https://ckeditor.com/docs/ckeditor5/latest/api/module_ai_aisdk_documentsnapshot-DocumentCompareSnapshot.html)、[Error codes](https://ckeditor.com/docs/ckeditor5/latest/support/error-codes.html#documentcompare-apply-failed)。API 直接開頁失敗後，主線讀到官方搜尋回傳的相關完整方法段落，不由第三方補猜。

- **Fact：**makeSnapshot 產生含 data-id 的 HTML；外部處理後由 diffSnapshot 計算 granular patch，applyPatch 可轉成 tracked suggestions。快照可序列化；套用仍限原 editing session，資料可保存不表示 patch 可跨重開套用。
- **Fact：**套用先在副本驗證，但另有 apply-failed，明示可能部分套用。process 的 overwriteOnError 可退回全文覆寫；本案不建議開啟。
- **版本／界線：**[v48.5.0 release](https://github.com/ckeditor/ckeditor5/releases/tag/v48.5.0)新增此路徑，不能把既有 Track Changes 的成熟度移植到新 DocumentCompare。也不要誤把文件中「atomic changes」解讀成整批交易必定原子。
- **Mapping：**是「模型交回處理內容、框架算 patch」的有力替代，不要求模型算行號。但要保留 data-id、驗證結構及 pending 行為，並非無限制生成 HTML 就可靠。完整 CKEditor AI Chat 也不直接取代我們已可延續的訪談；[其 Chat history 限制](https://ckeditor.com/docs/ckeditor5/latest/features/ai/ckeditor-ai-chat.html)需分開看。

## F05 Plate：可擴充底座，不等於完整持久 AI 審核

來源：[Suggestion](https://platejs.org/docs/suggestion)、[AI](https://platejs.org/docs/ai)、[rejectSuggestion 原始碼](https://github.com/udecode/plate/blob/main/packages/suggestion/src/lib/transforms/rejectSuggestion.ts)、[Suggestion changelog](https://github.com/udecode/plate/blob/main/packages/suggestion/CHANGELOG.md)。由獨立研究讀取；本輪主線採其具體契約比較，不主張每條 API 均已本機測試。

- **Fact：**Suggestion 有文件內 text marks／block suggestions 及 ID／作者／類型；rejectSuggestion 可按 ID 處理，並非只有畫面 diff。
- **Fact：**AI applyAISuggestions 對 chatNodes 做 diff、產生 transient suggestions；withAIBatch 是 undo batch。這些不是完整 durable review group 的證據。
- **Unknown：**未找到足以證明 AI pending 保存重開、跨作者修改及 C02 相依群組全鏈路已原生包辦的契約。歷史 experimental 聲明不能當今日永遠不成熟，也不能無證據當已解除。
- **Mapping：**適合需要更多源碼可控性的團隊；本案若目標是降低審核自建責任，不優先選。授權需按實際安裝套件／所用付費範例核對，不把網站可見當全部免費。

## 方案比較與停止條件

| 候選 | 本案價值 | 決定性風險 | 研究建議 |
|---|---|---|---|
| Tiptap Client AI Toolkit＋Tracked Changes | 原生讀／改／結果及多 agent SDK 接點最貼近；embedded 避免先選外部文件服務 | 付費、Beta／Alpha、人工待審重寫、部分失敗、跨位置分組未證明 | **優先驗證**，不是已選 production |
| CKEditor Track Changes＋DocumentCompare／自訂 agent 接線 | 持久 review adapter 契約清楚，外部生成→內建 diff 路徑可減少模型操作負擔 | 新 compare 路徑；工具循環另接；相依群組與部分失敗仍需驗證 | 第一候選未過，作實質對照 |
| Plate Suggestion＋AI／自訂接線 | 可改底層、彈性高 | 持久 AI 審核與產品群組需要更多整合責任 | 前兩者不適用且接受自訂成本時再選 |

此排序是 **Mapping**：按工具適配、審核正確、維護與授權綜合判斷，不是知名度排名或官方共識排名。沒有任一套已由公開資料證明全覆蓋 C02，也不因此立刻自寫新引擎。

研究到此可交付選型建議；下一步只驗證能否滿足具體必需情境。若失敗，帶著「哪個行為缺、框架哪個接點不足、替代成本」討論。不能無限搜新框架，也不能以 deadline 為由靜默把人改即接受、整輪一起審或只支援單句改寫當成原需求。
