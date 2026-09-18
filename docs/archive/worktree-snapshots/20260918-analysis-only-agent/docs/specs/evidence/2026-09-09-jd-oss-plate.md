# Plate 免費開源編輯／審核：固定版本原始碼證據

**補證狀態（2026-09-09）：**本稿保留早期 source 診斷；[R01 實證比較](2026-09-09-jd-native-pending-review-comparison.md)已執行兩獨立 pending 取消／接受、跨作者續改及移除粗體 JSON。§7.2 的 undefined 保存疑點已成真實反例；§4 的 active key／順序風險也有有限觀測。下方「未執行」僅指原靜態閱讀時點，不能作最新狀態；尚未測的 UI、結構與任意依賴仍未知。

JD-R002/C03；G2 evidence；查閱日 **2026-09-09**。承接[框架比較](../2026-09-09-jd-editor-framework-comparison.md)、[C02 工作稿](../2026-09-09-jd-editing-and-review-working-design.md)與[決策流程](../../decision-process.md)。本稿只研究免費開源範圍，不是選型、安裝、spike 或施工授權；LLM／Memory 已處理，不重做。不受舊產品架構限制。

**Owner 最新研究補充：**「人改待審內容仍待審 如果不是共識的話也可以改」。因此人工續編政策是本輪可比較、可再裁決的選擇，不能只因候選不符合舊政策便淘汰，也不能說 Owner 已接受 auto-accept。本文只證明 Plate 的分支，**單一家 default 不是跨廠共識**；主線負責更新 register 與提出產品裁決。

## 1. 可以支持的結論

**Mapping：Plate 應留在免費開源候選清單，且證據比「只有畫面 diff、沒有持久修訂底座」強；但尚不能推薦為 C02 全流程現成解。**它有文件內 suggestion、逐 ID 接受／拒絕、相鄰替換合組、block suggestion 與人工續改接點。主要缺口是任意結構操作的追蹤、重疊修訂、AI 再改既有 pending、跨位置語意同組與保存後回退。這些缺口不因放寬人工 pending 政策便全部消失。

**最接近原生的簡化路徑（Mapping，待 Owner）：**一次選定範圍的 AI 改寫，當次檢視並接受／拒絕，再開始該範圍的下一次 AI 修訂。這貼近 AI helpers 的全 transient 結算與 snapshot 差異流程，但會改變「數組長期待審、繼續 AI 修訂」的體驗，不能默認採用。若仍要求完整 C02，應先拿下列少量反例／unknown 決定是否值得驗，不能因此直接自造 review engine。

## 2. 版本、來源與授權邊界

固定原始碼 commit：`cee7a4ec0328718d8cf147094466b597215f5406`，官方 release `v53.3.12`，發佈時間 `2026-09-06T18:47:01Z`；commit 時間 `2026-09-06T18:43:44Z`。**Monorepo release、套件版本與文件 latest 分開記。**

| 來源 ID | Publisher／來源 | Date／版本／查閱日 | 授權／範圍 | URL |
|---|---|---|---|---|
| P01 | Udecode／Plate，官方 GitHub release 與 commit | release 2026-09-06；v53.3.12；access 2026-09-09 | 版本 metadata | [release](https://github.com/udecode/plate/releases/tag/v53.3.12)、[commit](https://github.com/udecode/plate/commit/cee7a4ec0328718d8cf147094466b597215f5406) |
| P02 | Plate npm publisher／npm registry、官方 package manifest | `@platejs/suggestion` **53.2.3**，2026-06-27T22:20:58.203Z；access 2026-09-09 | manifest 宣告 MIT | [registry](https://registry.npmjs.org/@platejs%2fsuggestion/53.2.3)、[manifest](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/package.json) |
| P03 | Plate npm publisher／npm registry、官方 package manifest | `@platejs/ai` **53.3.12**，2026-09-06T18:46:30.675Z；access 2026-09-09 | manifest 宣告 MIT | [registry](https://registry.npmjs.org/@platejs%2fai/53.3.12)、[manifest](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/package.json) |
| P04 | Udecode／Plate，repo／diff LICENSE | 固定 P01 snapshot；個別 LICENSE 編修日未查；access 2026-09-09 | repo MIT；`@platejs/diff` 衍生碼 Apache-2.0，修改部分另有 MIT／Apache-2.0 雙授權說明 | [repo LICENSE](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/LICENSE)、[diff LICENSE](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/diff/LICENSE) |
| P05 | Plate 官方 Suggestion 文件 | latest 頁未標 publication date；固定 repo snapshot 亦核對；access 2026-09-09 | OSS plugin 與付費 Plus 範例分開 | [Suggestion](https://platejs.org/docs/suggestion) |
| P06 | Plate 官方 AI 文件 | latest 頁未標 publication date；固定 repo snapshot 亦核對；access 2026-09-09 | OSS helpers；Plus 另列 | [AI](https://platejs.org/docs/ai) |
| P07 | Plate 官方保存文件 | latest 頁未標 publication date；access 2026-09-09 | 一般 editor JSON 保存示例 | [Controlled value](https://platejs.org/docs/controlled) |
| P08 | Plate suggestion source 與同目錄 tests | 53.2.3，P01 snapshot；access 2026-09-09 | MIT | [source tree](https://github.com/udecode/plate/tree/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib) |
| P09 | Plate AI source 與 tests | 53.3.12，P01 snapshot；access 2026-09-09 | MIT | [AI chat source](https://github.com/udecode/plate/tree/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/react/ai-chat) |
| P10 | Plate core NodeId source 與 tests | P01 snapshot；不把 core 版本冒稱 suggestion 版本；access 2026-09-09 | repo MIT | [NodeId source](https://github.com/udecode/plate/tree/cee7a4ec0328718d8cf147094466b597215f5406/packages/core/src/lib/plugins/node-id) |
| P11 | Plate diff source 與 tests | `@platejs/diff` 53.0.0，P01 snapshot；access 2026-09-09 | 見 P04 的 package LICENSE | [diff source](https://github.com/udecode/plate/tree/cee7a4ec0328718d8cf147094466b597215f5406/packages/diff/src) |
| P12 | Plate suggestion／AI changelog | 固定 P01 snapshot；各 entry 未逐條查發佈日；access 2026-09-09 | repo 文件 | [suggestion changelog](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/CHANGELOG.md)、[AI changelog](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/CHANGELOG.md) |

**Fact：**npm 當日 latest 分別是 suggestion 53.2.3、AI 53.3.12。suggestion 的 npm `gitHead` 是 `f2c187c95fb7e4010e49b2ecb7becc5f22ae8b1b`；AI 的 `gitHead` 是 P01 commit。已以 GitHub tree blob SHA 比對：suggestion 發佈 commit 內 55 個套件檔，在 P01 snapshot 全部相同，沒有把後來未發佈 suggestion code 當成 53.2.3。這是來源檔 hash 核對，**不是套件安裝／build 或執行驗證**。

**Fact：**P05 的 Plus 區另列完整 full-stack suggestion/comment example、浮動討論 UI 等；不能把這些付費範例算入免費交付。一般 suggestion／AI 原始碼與公開 registry components 可讀，不代表付費範例授權相同。P04 顯示核心候選是免費開源，但不可把依賴樹全寫成單一 MIT；本輪沒有完成整份 transitive dependency legal audit，也沒有付費或購買。

**版本修正：**P12 的 45.0.0 entry 曾稱 experimental；這是歷史警示，不能推導成 53.2.3 永久同級，也不能在沒有聲明下宣稱成熟度問題已解除。53.2.3 修復 block removal 遺漏 `userId`；53.0.3 修復 inline void delete/replace；52.3.8 修復 per-suggestion ID lookup。這些是具體維護證據，仍須看所需情境。

## 3. 查核方法與證據強度

- **Fact / source-read：**實際下載、閱讀上述固定 commit 的相關原始碼與測試；下方每項連到固定 code，避免浮動 main。官方網站用來核對公開契約與付費界線。
- **Fact / authored-test：**讀到官方測試的 fixture／assertion，只表示 upstream 有寫這個測試；**本輪沒有安裝依賴、沒有執行 Plate 測試、沒有開 editor、沒有 runtime／spike、沒有模型請求**。
- **Inference：**由 code 的確切分支推導出的效果／風險；若跨函式或 runtime 尚未驗，明列。沒有把推論寫成實測失敗。
- **Mapping：**對 C01／C02 的產品選擇。**Unknown：**本次官方來源不足以證明完整行為；不是斷言套件永遠不能做。

研究下載只在 `.research-tmp/jd-oss/plate/`，包括 GitHub release／commit／tree、npm 版本摘錄與 source。唯一 durable 寫入是本文；沒有改產品程式、依賴或其他人的文件。

## 4. 一般 suggestion：資料、人工續編與接受／拒絕

### 4.1 文件內 metadata 確實存在，還不是完整審核群組模型

**Fact：**文字節點有 `suggestion` 與 `suggestion_<id>`；一個 text node 可有多個 suggestion data。block 存單一 `suggestion` object。plugin 的 dataList 列全部鍵，但一般 `suggestionData`／`getInlineSuggestionData` 取**最後一個 suggestion key**作 active。預設 `isSuggesting=false`、`currentUserId='alice'`；UI／討論資料另由整合提供。[BaseSuggestionPlugin](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/BaseSuggestionPlugin.ts#L52)、[active key 選擇](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/utils/getSuggestionId.ts#L5)

**Mapping：**這比暫時 decorations 更有可保存基礎。`suggestion.id` 是修訂標記 ID，`node.id` 是內容節點身分；兩者不能互當 task ID／semantic dependency group。dataList 可多值也不能推出任意 nested review 的完整契約。

### 4.2 人工修改 pending 的實際分支

| 情境 | source-read／authored-test 看到什麼 | 可以說／不能說 |
|---|---|---|
| tracking 開，同作者在 inline insertion 續打字 | `findSuggestionProps` 於當前／相鄰位置找同類型且同作者 suggestion，重用 id、createdAt；`insertTextSuggestion` 插入該 id 的新文字。官方 fixture 把 `test` 續成 `testtest`，同一 id | **Fact：**有原生「修改既有待審內容」接點。不是所有輸入皆新建審核項 |
| tracking 開，同作者刪自己 pending insertion 的字 | `deleteSuggestion` 找到同作者 insert text，直接 delete 那段，不另外套 remove suggestion；有對應 authored test | **Fact：**編修自己尚未接受的新增文字，會縮短 pending 本身。接受可保留縮短後的字 |
| tracking 開，不同作者在 inline insertion 續字／刪字 | 重用 id 條件含 current user；續字通常新 id；刪另一作者新增文字不走上述直接刪除，轉為 remove metadata | **Inference：**AI 與員工若用不同 author id，不能套用「同作者續打」證據。精確游標邊界、選取替換與多鍵次序仍需驗 |
| 人在非 lineBreak block suggestion 內 insertText／deleteBackward | wrapper 直接呼叫原 transform，保留 block suggestion、不另加 inline leaf；分支沒有 currentUserId 相等判斷 | **Fact：**block insertion 的目前 children 可人工續改，仍有外層 pending。這是可簡化選項，不能外推 deleteForward／跨 block 選取也完全相同 |
| tracking 關，一般文字輸入 | wrapper 直接透傳；官方 test 證一般 unmarked 節點不加標記 | **Unknown：**既有 inline pending 內部、左右邊界與 marks 繼承結果沒有完整真 editor matrix；不能一律叫 auto-accept，也不能一律叫 pending 不變 |
| 人工選取已核准文字後直接替換，tracking 開 | 先用 deletion 建議取得 id，再把新 insert 用同 id；官方 fixture 原 `test` 保留為 remove，新 `1` 為 insert | **Fact：**相鄰替換可作一項；不是整輪所有無關操作綁一項 |

直接來源：[findSuggestionProps L16–126](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/queries/findSuggestionProps.ts#L16)、[insertTextSuggestion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/insertTextSuggestion.ts)、[deleteSuggestion L329–352](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/deleteSuggestion.ts#L329)、[withSuggestion 的 block／輸入分支](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/withSuggestion.ts#L200)。

測試來源：[same-id typing fixture](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/withSuggestion.spec.tsx#L153)、[block backspace fixture](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/withSuggestion.spec.tsx#L237)、[replacement fixture](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/withSuggestion.spec.tsx#L930)、[直接刪 own insertion 的 authored test](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/deleteSuggestion.spec.ts#L77)。最後一份使用 mock editor，不能冒稱完整真 Slate 情境。另 block insertText fixture 雖位於 suggesting 描述下，該 case 未設 `isSuggesting=true`；對啟用模式的主要證據仍是 wrapper 分支，不能只讀 test title 判覆蓋。

**Mapping：**可以向 Owner 比較「當次 AI 輸出先審，再人工自由改」、「原生同作者／block pending 續編」、「保留 AI／人工作者區分且接受多项修訂」等體驗；不能為了湊出同 id 而默默把 AI 與人作者全部偽裝成同一人。

### 4.3 接受的是目前節點；拒絕是處理被標記範圍

**Fact：**`acceptSuggestion` 按指定 id 掃描目前文件，保留 insert 的當前文字／children 並移除標記，移除 remove 文字／block，處理 remove lineBreak 的合併；不是從描述中的舊 `newText` 重放 AI 初稿。`rejectSuggestion` 相反，清除 remove、移除 insert、合併被建議插入的換行；update 另走屬性復原。[acceptSuggestion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/acceptSuggestion.ts)、[rejectSuggestion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/rejectSuggestion.ts)

**authored-test：**insert、remove、update、lineBreak、block 及同 ID 的相鄰 remove＋insert 均有 fixture/assertion。例如同 ID `removed`／`inserted`：accept 後留下 `inserted`；reject 後留下 `removed`。**這個叫「both remove and insert」的 test 是兩個相鄰 text nodes，並非同一節點兩層跨作者修訂。**[accept fixture](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/acceptSuggestion.spec.tsx#L249)、[reject fixture](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/rejectSuggestion.spec.tsx#L255)

**Inference：**對沒有重疊的既有 id，這比回復全文件快照更接近「不抹組外修改」。但移除一個 insert block 會自然移除全部 descendants，沒有 semantic dependency 檢查；若其下新內容被產品判成獨立另一組，框架不會替產品保留它。

**Fact／接線前提：**官方公開 `BlockSuggestion` 元件在接受／拒絕時，使用 `api.suggestion.withoutSuggestions(...)` 包住 acceptSuggestion／rejectSuggestion。這很關鍵：一般 helper 內的 removeNodes 若仍被 suggesting wrapper 攔截，不能直接把「低階函式存在」當成正確 UI 結算；最少整合應沿官方既有接點，而非自行重寫 resolve。[官方 block suggestion UI L35–46](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/apps/www/src/registry/ui/block-suggestion.tsx#L35)

### 4.4 多鍵／嵌套是具體待驗問題

**Fact：**inline insert/remove 的 accept/reject 多處用 active（最後一個）suggestion data 比對 id；update 的部分分支才遍歷 dataList。結算一個 suggestion 也可能清掉公共 `suggestion` boolean，並不一律保留所有其他 key 的可見標記狀態。block 只有一個 suggestion object，`removeNodesSuggestion` 會覆寫它。[active lookup](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/utils/getSuggestionId.ts)、[accept 多鍵分支](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/acceptSuggestion.ts#L47)、[removeNodesSuggestion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/removeNodesSuggestion.ts)

**Inference／最便宜反例：**A 的 insert 文字被 B 加 remove key 後，直接 reject A 可能因 active 是 B 而沒有命中那片文字；先 reject B 也可能清掉共用 boolean，留下 A key 卻失去一般 `nodes()` 匹配。這是 code-path 風險，**沒有執行，所以不是宣告已重現 bug**。只需無 LLM 的真 editor fixture，依 A→B／B→A 順序各 accept/reject，查看文字、所有 key、UI 與下一次命令，就能回答。

## 5. 結構操作、任務新增／拆分／移動與分組

**Fact：`withSuggestion.apply(operation)` 直接呼叫原 apply。**它沒有在低階 operation 層全面追蹤所有 Slate 操作；高階 wrapper 才有下列特例。因此「有 Slate operations＝所有 command 可拒絕」不成立。[withSuggestion L51](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/withSuggestion.ts#L51)

| 操作／C01 情境 | 實際分支 | 研究判定／最低驗法 |
|---|---|---|
| `insertNodes` 加一或多段 | tracking 開時對傳入每個 node 套 block insert metadata，**每個 node 各 `nanoid()`**；slash_input 特例略過 | **Fact：**一個 transform 呼叫多段不自動同組。驗「新 Task＋必要說明兩段」的 ID／接受範圍 |
| `insertFragment` 貼上多段 | 為該次 fragment 使用同 id；直接 text 清掉其他 suggestion keys 再寫目前作者；element 套 block suggestion | **Fact：**與 insertNodes 的分組不同。fragment top-level 處理不是完整嵌套 lineage 保留契約 |
| `insertBreak` 拆段 | 頂層 paragraph 真拆，舊 paragraph 存 `isLineBreak=true` insert suggestion；nested block 或非 paragraph 改插 `\n` text suggestion | **Fact：**nested JD 的 Enter 未必產生新結構節點。不能把換行當成「Task 拆兩項」原生工作流 |
| Backspace 跨 paragraph | 建 remove lineBreak；accept 合併兩段。已 pending insert lineBreak 可直接取消並合併 | **Fact：**有換行審核特例；不是一般 merge 任意結構的歷史回退 |
| `removeNodes` 多段 | matched blocks 共用該次 remove metadata；不直接刪除 | **Fact：**已有共用 deletion ID 接點；對原有 block suggestion 會覆寫，嵌套及後續修改需驗 |
| 直接 `insert_node`／`remove_node` | operation apply passthrough；上述 wrapper 不會因名稱相近自動套用 | **Fact／Mapping：**command 必須走實際有攔截的路徑，不能以任意 operation adapter 直接接 AI |
| 直接 `split_node`／`merge_node`／`move_node` | suggestion 沒有通用攔截；也沒見專用 move suggestion type／來源目的地配對 | **Unknown：**別的 plugin 是否改走 wrapper 視整合而定。拖移 Task 的來源／目的、accept/reject 不可宣稱已包辦 |
| `set_node` 改 paragraph type、Task metadata、層級 | suggestion apply 透傳；高階 addMark/removeMark 只覆蓋特定 text mark 情境 | **Fact：**共用 metadata 可存在 editor value，不代表其變更有可拒絕歷史。先列實際 command 再驗 |

直接來源：[insertBreak／insertNodes](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/withSuggestion.ts#L125)、[insertFragmentSuggestion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/insertFragmentSuggestion.ts)、[lineBreak delete](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/deleteSuggestion.ts#L261)。authored tests：[nested Enter／insert block／multiple block remove](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/withSuggestion.spec.tsx#L1057)、[lineBreak tests](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/insertBreakSuggestion.spec.tsx#L34)。

### 5.1 跨位置同組有低階 ID 接點，沒有語意群組保證

**Fact：**一般 accept/reject 使用 `at:[]` 掃全文件並以 id 篩選；同一 id 可涵蓋多個位置。`diffToSuggestions` 會把相鄰 remove＋insert 的 id 合併；兩段相互分離的替換在官方測試中維持不同 id。它的 options 可覆寫 getInsertProps／getDeleteProps／getUpdateProps，所以有 supplied-ID 的擴充接點。[diffToSuggestions](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/diffToSuggestions.ts)、[兩組分離測試](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/diffToSuggestions.spec.ts#L93)

**Mapping：**「同 ID、全文件找標記」足以讓跨位置分組成為值得驗的候選接點，不能說完全無分組能力；但「Task 移出＋移入」、「一拆二＋必要條件」哪些應同 id，是產品／語意選擇。沒有看到依賴圖、跨群組 rebase、失敗交易回復或 semantic completeness 的原生契約。本輪不為此發明演算法。**Unknown：**動作建立時能否不碰框架私有細節就完整共組、重開仍成立，須具體情境驗證。

## 6. AI helpers：為什麼不能直接當作長期 pending 的續編引擎

### 6.1 實際資料流

**Fact：**`submitAIChat` 根據 block selection／文字 selection 取得當時 nodes，寫入 `chatNodes`；上下文另送目前 `editor.children` 與 selection。`applyAISuggestions(content)` 讀保存的 chatNodes，而非每次重新擷取目前修改後內容。[submitAIChat L65–111](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/react/ai-chat/utils/submitAIChat.ts#L65)

**Fact：**AI Markdown 經 deserialize 後，`withProps` 依**位置 index**帶回原 node properties，再使用新 children；`getDiffNodes` 先清除 rawChatNodes 的 suggestion/comment payload，呼叫 diffToSuggestions，最後遞迴加 transient key。多 block 分支以 `_replaceIds` 找目前節點、replace；單 block 分支插 fragment 並選取 transient text。[AI apply 流程](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/react/ai-chat/utils/applyAISuggestions.ts#L27)

**Inference：**這是「原範圍 snapshot 對新回覆 diff」接法，source 本身沒有 stale-read version check、跨兩份 pending 群組的因果保存或原子交易回復。原屬性在 spread 次序中覆蓋 AI node 屬性，不能把此 Markdown helper 當成任意 JD 結構／metadata patch；UI 是否鎖定人工編輯是另一層，本稿不推測未讀的整合。

### 6.2 AI 再改 pending 的明確風險

**Fact：**`withoutSuggestionAndComments` 對帶 suggestion 或 comment 的 text 直接回傳 `{text: node.text}`，並非只去除一個 active suggestion；block 清掉 suggestion 前綴屬性、递迴處理 children。它也沒有在這步把 remove 文字排除。[清除函式](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/react/ai-chat/utils/applyAISuggestions.ts#L143)

**Inference：**若 A 的 old/remove 與 new/insert 都還在 value，重新提交給此清除路徑時可能把兩者都當成未標記正文比對；舊 pending 的 id、作者與邊界不保留，帶 suggestion 的 bold 等 text 屬性也可能失去。這與「在最新 pending 上繼續編輯而保留原接受／拒絕意義」有實質差距，並非泛泛的 durable unknown。

**authored-test：**官方直接測「strips suggestion and comment payloads」，與 source 一致；但 applyAISuggestions 的 diff、Markdown 解析、replaceNodes／insertFragment 主要被 mock，不能將此測試當成「真实 editor 同時多 pending 已正確」證據。[測試 setup 與 stripping assertion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/react/ai-chat/utils/applyAISuggestions.spec.ts#L1)

**最便宜驗法：**無模型 fixture，先 A→B 保留 old/new marks，人把 B 改 B2，再固定回覆 B3 進 applyAISuggestions；檢查送入 diff 的 baseline、所有 ids、accept/reject 對 A/B2/B3 的精確效果。另放一個與此區域無關的 pending C，確認不被結算。無需先造 lineage。

### 6.3 `acceptAISuggestions` 不是「轉成永久待審」

**Fact：**P06 文案稱 acceptAISuggestions 把 transient 轉 permanent suggestions；然而固定 source 逐個讀取**全文件所有 transient suggestions**，呼叫一般 `acceptSuggestion`，再清全文件 transient key。reject helper 同樣對所有 transient 呼叫 rejectSuggestion。這兩個 helper **沒有指定 group id 參數**。[acceptAISuggestions](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/react/ai-chat/utils/acceptAISuggestions.ts)、[rejectAISuggestions](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/react/ai-chat/utils/rejectAISuggestions.ts)

**Inference／文件衝突裁讀：**實際是結算目前 suggestion，不能據那句文案說有「AI 暫時 preview →持久 pending review」的現成升級命令。應以固定 source 精確行為為基準並在驗證時確認；沒有對文件作者意圖做推測。若自行只清 transient 保留 suggestion，是另條整合選擇，**本輪未採用，也尚未證明後續續編／保存正確**。

**Fact：**`withAIBatch` 只選用 withNewBatch／withMerging，並在最新 undo batch 設 `ai=true`；它不是 semantic review group store，不證明跨位置群組隔離／持久性。`acceptAIChat` 的 chat 模式會呼叫上述 acceptAISuggestions。[withAIBatch](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/lib/transforms/withAIBatch.ts)、[acceptAIChat](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/ai/src/react/ai-chat/transforms/acceptAIChat.ts#L54)

### 6.4 「最新內容」讀取接點也有範圍

**Fact：**`SkipSuggestionDeletes` 對 text 的 active remove 回空字串，但 inline element 直接用 NodeApi.string；block 分支遞迴 children，不檢查 block-level remove metadata。[source](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/utils/SkipSuggestionDeletes.ts)

**Inference：**不能僅因函式名稱就把它當成含 block 刪除、inline 物件、多層 pending 的完整「最新 JD」投影。需要單獨驗「已標刪除的整 Task／link 是否還被讀到」。這不要求重做 Memory，而是 editor 的對外讀取契約。

## 7. 保存、node ID 與屬性回退

### 7.1 JSON 保存有原生路徑；不能省略重開驗證

**Fact：**P07 用 onValueChange 取得完整 editor value，JSON.stringify 存、JSON.parse 初始化；metadata 放在 value，因此一般 id、insert/remove 字串和時間戳有可保存載體。這不是現成 backend adapter，也不代表 plugin options、AI snapshot、undo history 一併保存。

**Fact：**NodeIdPlugin 預設針對 block，inline/text 被濾除；既有插入 id 未碰撞時可沿用，重複 id 會新造；split 預設產新 id。初始化的 `if-needed` 只看首尾 top-level 是否已有 id，`always` 才全樹補缺。這些具體行為和 tests 不等於 JD 任務身分／lineage。[NodeIdPlugin](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/core/src/lib/plugins/node-id/NodeIdPlugin.ts#L15)、[withNodeId](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/core/src/lib/plugins/node-id/withNodeId.ts#L124)、[ID authored tests](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/core/src/lib/plugins/node-id/withNodeId.spec.ts#L193)

**Unknown：**本輪沒有 suggestion 專用的完整 JSON→新 editor→再續編→按組 reject 整合測試證據；HTML／Markdown round-trip 是否保留全部 suggestion keys、任務 metadata 與 transient，也沒有證明。不能拿匯出格式代替權威保存格式。

### 7.2 具體反例假設：移除粗體後 JSON 保存會丟復原標記

**Fact：**人工 `removeMarkSuggestion('bold')` 在 `properties` 中寫 `bold: undefined`；官方 test 直接斷言該物件。reject 的 update 分支遍歷 `Object.keys(properties)`，找 falsy 值再把對應 mark 設 true。[removeMarkSuggestion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/removeMarkSuggestion.ts#L38)、[authored fixture](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/removeMarkSuggestion.spec.tsx#L20)、[reject update](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/rejectSuggestion.ts#L171)

**Inference：**標準 JSON 省略 object 中的 undefined value；保存後 `properties` 可能變 `{}`，重開再 reject 沒有 `bold` key 可復原。這是 source＋JSON 語義推論，**未執行、未定案為已重現缺陷**。最便宜驗法就是一段粗體，移除粗體但不接受，序列化→新 editor→reject，比對是否恢復粗體；無需 LLM，也無需完整 JD UI。

### 7.3 AI diff 的屬性 update 不等於人工 mark suggestion

**Fact：**`diffToSuggestions` 預設 getUpdateProps 忽略 `_properties`，只把 newProperties 當 `suggestionUpdate` 送 getSuggestionProps；後者只根據此值選 type=update，沒有寫入 old/new property payload。diff 的 propsOnlyStrategy 套用新 node properties 後加這些回傳標記。一般 block accept/reject 主要處理 insert/remove，update 復原遍歷 text。[default update callback](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/diffToSuggestions.ts#L19)、[getSuggestionProps](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/getSuggestionProps.ts)、[diff propsOnlyStrategy](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/diff/src/internal/transforms/transformDiffNodes.ts#L56)

**Inference：**不能以人工 addMark/removeMark tests 宣稱 AI 改格式／block metadata 的 reject 也完整。最低驗法：同文字只改 bold、同 children 只改 heading/type 或 JD metadata，先查看產生的 update data，再 accept/reject。這是需要排除的局部風險，不是本稿自行補寫 serializer 或 rollback engine 的授權。

## 8. 可證偽情境清單：現在證到哪、最便宜怎麼補

所有下列「下一驗證」均**未執行，需沿主線 gate 決定是否進 G5**；可先選能改變選型的少數，不必一口氣擴大測試。

| 編號／JD 情境 | 本輪證據狀態 | 最低驗法／觀察 pass 與 stop |
|---|---|---|
| PL-01 人續改 AI 單句 pending | 同作者輸入／刪自己 insert 有 source＋有限 authored tests；異作者／tracking 關完整矩陣 Unknown | 固定同一 old→new，分 AI／human ids 與 tracking 開／關；打字、backspace、選取替換、accept/reject。記錄實際體驗供 Owner 選，不以舊政策自動淘汰 |
| PL-02 新 Task＋必要說明兩段 | insertNodes 每段不同 ID；insertFragment 同批 outer nodes 共 ID，code evidence | 真 editor 各走一次建立路徑，人工改其中一段再結算；範圍若與 Owner 選的審核單位不合，先回報成本／取捨 |
| PL-03 無關 Task1／Task8 同輪改 | diffToSuggestions authored test 證分離替換不同 id；AI helper 結算所有 transient | A、C 兩處各 pending，接受 A 必須能留下 C；若只能 acceptAISuggestions 全結算，不能稱符合無關分開 |
| PL-04 人改 pending，再 AI 改該段 | AI helper 剝舊 metadata 與 snapshot baseline 是 source fact；完整結果未驗 | A→B→人 B2→固定 AI B3；需能說清每一層何時結算／誰負責，不得靜默丟去原基準 |
| PL-05 Task 移到另一職責／一拆二 | generic move/split/merge 無 suggestion 全面攔截；低階 shared id 接點可研究 | 最小 Task＋隨行必要內容＋獨立技能修訂；accept/reject 不能只留移出／移入半邊，也不得刪獨立技能。native 缺口先交 Owner |
| PL-06 同字跨作者 nested／跨位置同組 | 多鍵 active-last 與 block 單 metadata 已讀；完整順序未證 | 兩個 id、四種 resolve 順序；另同 id 跨兩段加組外第三段。比文字、keys 與 UI；不能只看紅綠文字 |
| PL-07 pending 保存重開 | 普通 JSON 路徑存在；undefined mark 回復有反例假設 | 先測去粗體 JSON round-trip；再測 insert/remove/block、node id、transient、組外改動。任一資料丟失先縮窄原因，不自造儲存層 |
| PL-08 最新 JD 讀取 | SkipSuggestionDeletes 對 block remove 未排除的 source evidence | 已刪 Task、inline link、普通刪字各一個；核對對外讀取究竟含什麼。不要重啟 LLM／Memory 研究 |
| PL-09 AI 改文字以外 properties | 預設 diff update payload 不含復原 properties；非實測 | 純 bold、heading/type、metadata 各一例；reject 不回原值就停止該能力承諾，帶回選項 |

## 9. 最少整合路線：既有 agent 只用 SuggestionPlugin 已覆蓋的 transforms

這是 **Mapping／待裁決的候選路線**，不是新 API 設計，也不是已測過的接線。目標是避開 §6 清除既有 pending 的 AI helper，讓既有 agent 對**當時 editor 的目前內容**使用公開原生 transform；不另加模型／Memory／自製 diff 或 review engine。既有 agent 如何取得可讀目前內容、定位 selection、送回實際執行結果，仍有必要整合，其範圍與成本未證，不能因框架有 transforms 便稱零工程量。

| 原生能力／公開接點 | 可承接的 JD 工作 | 必要界線／驗證 |
|---|---|---|
| 開啟 suggestion 後，在明確 selection 使用 `insertText` | 在已存在段落增補完整敘述，或選取局部文字作同 ID remove＋insert 替換 | 這條路不呼叫 withoutSuggestionAndComments，因而不會先把全範圍的舊 metadata 清空；但同／異作者及選取跨多 pending 仍須 PL-01／PL-06。suggesting 分支主要使用 editor.selection，不能假定任何傳入 options 都被完整沿用 |
| `deleteBackward`／`deleteForward`／`deleteFragment` | 局部刪字、縮短既有 task 敘述；同作者 pending insert 可直接修短 | 只承諾已讀 wrapper 的行為；不用 generic `delete`／直接 `remove_text` 冒充相同接點；跨 block 邊界有 lineBreak 特例 |
| `insertNodes`／`insertFragment` | 新增一段 Task、說明或多段新內容，保留 block pending | 兩者 ID 粒度不同。可先比較「一個完整任務用既有單一 block／多段 fragment」的 native 分組效果，不先規定新 schema。nested 插入、必要內容是否一起 resolve 仍須 PL-02 |
| `removeNodes` | 將既有完整 block 標記刪除；一次 matched blocks 可同 deletion id | 若 block 已有 pending，可能覆寫 suggestion；accept/reject 刪 block 會帶走全部 children。因此不能預先說後加的獨立子內容都安全 |
| 展開文字 selection 後 `addMark`／`removeMark` | 對普通正文做粗體等簡單 text formatting suggestion | 原生 match 會跳過已有 insert/remove suggestion 的文字；update 疊加、非 boolean 值與 JSON 重開都未全面證實。可把格式調整放在人工作業，是否直接生效須明講讓 Owner 選 |
| `acceptSuggestion`／`rejectSuggestion`，沿官方 `withoutSuggestions` 包裝 | 依現有 ID 處理目前版本、保留其他不相交標記；不需所有 transient 一起結算 | 顯示所有相關位置、讓員工看清某 ID 範圍是 UI 接線；nested／同 ID跨位置完整性仍須 PL-06，不假定 id 自動等於最小完整語意組 |

**這條路原生可以少做什麼（Inference）：**普通局部增刪不必先把整段 Markdown 全文替換，再自行 diff；一般 suggestion 本身可以保存其 metadata，也不必僅為人工續改便建立另一個 shadow document。**仍不能保證什麼：**先前 pending 被再修訂時的多鍵優先順序、跨組依賴與 JSON 回復；這些是未解風險，不是架構已決定。

**明確保留／調整體驗的範圍（Mapping，需 Owner）：**

- 移動 Task：暫不承諾 AI 直接拖移／`move_node` 可審核回退。可比較由員工在已結算內容上做移動，或先處理既有 pending 再做移動；這會改變操作政策，不能默認採用。若仍要 AI 移出＋移入待審，先驗共組接點，不能只用兩個獨立 add/remove 就宣稱完整。
- Task 拆兩項：頂層 paragraph 的 insertBreak 只保證換行特例；nested Enter 只是插入換行字元，不拿它偽裝 Task split。若需要完整 Task 替換，先驗 native block removal＋fragment insertion 是否能形成正確一組；尚未證明，不先寫配對引擎。
- block property／結構層級／任務 metadata：`set_node` 未全面追蹤。可先只讓 AI 改受支援文字和新增內容，其他由員工在明確操作下直接更改；或不接受此限制而保留候選 OPEN。兩者都要交 Owner。
- 長期 pending 與繼續 AI 修訂：這條 transforms 路線避開 AI helper 的清除問題，但還有多鍵／重疊與保存問題，不能叫完整 durable 已解決。最先驗的是同一段再修改和獨立組不受影響，而非先建大量通用操作。

### 9.1 與官方短期 AI preview lifecycle 的差距

| 面向 | 官方 AI helpers 的形狀 | 只用一般 suggestion transforms 的候選 |
|---|---|---|
| 修訂輸入 | Markdown 完整回覆，對當次 chatNodes snapshot diff | 已有 editor selection 上的原生輸入／刪除；對外工具接線仍需完成 |
| 已有 pending | apply helper 先清除原 suggestion/comment payload | 不先清除整段 metadata，但每個 transform 的巢狀／作者規則仍生效 |
| 結算 | AI helpers 遍歷全文件 transient suggestions | 一般 helper 以指定 suggestion id 結算 |
| 多組長期保存 | 未看到完整升級／重開／再改契約 | 值內有 metadata，可作候選；JSON／多鍵反例仍 OPEN |
| 結構調整 | Markdown 回覆不等於任意 node property patch | 只能承諾已包裝 transforms；move／generic split／block set 不自動可審 |

## 10. 留給主線的產品選擇與停止條件

| 方案（Mapping，未採用） | 可利用的免費原生部分 | 必須明講的取捨／剩餘 Unknown |
|---|---|---|
| A. 範圍式 AI 改寫，當次檢視後結算 | AI Markdown→diff、transient、全次 accept/reject；一般 editor 自由編寫 | 最貼近 AI helper 形狀；不保證可先存數組 pending 再讓 AI 反覆改。人是否能直接修改 preview、何時算接受，由 Owner 選；先驗保存與屬性風險 |
| B. 以一般 SuggestionPlugin 為候選，限制在已確認可追蹤命令 | 文件內 marks／blocks、逐 ID resolve、同作者或 block 續編、供應 ID 接點 | 仍需接既有 agent 工具；不把 applyAISuggestions 當 pending lineage 引擎。哪些結構 command 可用、哪些操作先直接生效，是產品取捨，不能靜默縮規格 |
| C. 暫不採 Plate，保留證據對照其他 OSS | 沒有新 runtime／自建引擎成本 | 若必要 C02 情境在免費候選均有缺口，回 Owner 比較政策／範圍；paid 只作能力參照，不能偷換回付費主案 |

**建議範圍：**可以把 Plate 作為免費 OSS 的實質候選，優先比較 A 的體驗與 B 的有限接線成本；**不能推薦「照官方 AI demo 就能完成全部 C02」**。先用 PL-04／PL-06／PL-07 這類最能區分選項的無模型小情境辨別是否值得前進，具體組合由主線與 Owner 裁決。

**G2 closure：**本稿已把會改變選型的關鍵 source 行為、文件衝突、授權區別、具體反例假設與最便宜驗法寫出；新增廣泛搜尋暫無必要。尚未完成任何 runtime／UI／保存重開驗收，沒有套件採用、安裝、測試執行、模型請求、commit 或 push。若維持完整長期 pending＋再次 AI 修訂＋跨位置依賴組，仍是 OPEN；Owner 可重議人工 pending 政策，不能由研究者代決或直接擴建審核引擎。
