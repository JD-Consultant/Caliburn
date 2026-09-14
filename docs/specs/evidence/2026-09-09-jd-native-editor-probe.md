# JD 原生文件與差異工具：有限能力驗證

JD-R002/C03；2026-09-09；**原生驗證完成：13 項中 11 通過、2 反例；追加原生觀測 3 項通過**。本輪只回答框架選型會受影響的原生能力問題，不採用審閱政策、不接 production、不使用 LLM，不自造定位／差異／審核／回退引擎。

Owner 要求在既有 Memory 與 JD 撰寫研究下深入收斂編輯器。驗證問題：**Plate 原生 headless editor 加 computeDiff，能否保留代表性 JD 內容並暴露文字、屬性及結構改動，作為持續工作稿的核心候選？**這是不依賴逐項待審政策的選型實證，不宣稱完整 App 或 S4／S5 通過。

## 固定範圍

- 核心：`platejs@53.3.11`；差異：`@platejs/diff@53.0.0`；React／React DOM 19.2.4 僅滿足 peer dependency。版本以官方 npm 發布資料核對；monorepo release v53.3.12 不是核心 npm 版號，前次查詢不存在的核心 53.3.12 失敗已識別。
- [已安裝依賴宣告清單](jd-native-probe/results/license-inventory.json)共 44 項：42 項宣告 MIT、1 項 Apache-2.0；diff 未填 package license 欄位，已另外讀取並封存[實際 LICENSE](jd-native-probe/diff-LICENSE.txt)，衍生原碼 Apache-2.0、修改部分 Apache-2.0／MIT 雙授權。本清單只覆蓋固定 probe，尚不是未來 UI 所有擴充的授權核對。
- 隔離位置：`.research-tmp/jd-editor-native-probe`。安裝停用 lifecycle scripts，不改 root／apps package 或 lock，不啟動產品服務、DB 或付費請求。
- 以完整繁中文字段落及巢狀結構作合成 fixture；數值位置由測試程式供給，**不是要求 LLM 算 path／offset**。
- 檢查原生文字修改、重複文字、marks／attrs、移動／拆分與必要 metadata；JSON 寫出再讀回建立全新 editor；比較差異輸出是否遺漏變動。
- 同時記錄原生限制：diff 是否把移動表示成刪＋增、純 metadata 變動、空文字、屬性刪除及多重變動；不為了通過而修套件或忽略業務屬性。

## 判準

Pass：固定操作的預期目前內容及未改內容相符；序列化重開後必要內容保留；代表性差異不漏。框架輸出刪＋增可證明有差異，但不等於理解語意移動。

Stop：原生處理遺失工作內容／metadata，重要改動在差異中無痕，或需要自造通用引擎；記錄反例並回到候選比較。個別案例失敗須限於實際影響，不概括所有功能不可用。

未覆蓋：瀏覽器輸入法／選取／拖曳、視覺差異可讀性、PostgreSQL 保存／斷線／去重、真模型定位與修復、員工 UX、顧問語意品質及相依修訂的選擇性回退。

## 後續呈現驗證的官方接點與限制

2026-09-09 追加 source／types 覆核，**本節尚未執行 UI**。固定版本的[免費 version-history-demo](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/apps/www/src/registry/examples/version-history-demo.tsx)內嵌 DiffPlugin／DiffLeaf，沿 `platejs/react` 的 `render.node`／`render.aboveNodes` 呈現；`@platejs/diff` 沒有直接匯出這套 UI，不應宣稱安裝即有可用 DiffKit。

- **表格：**範例對非 inline element 一律包 `div`；直接套在表格列／儲存格可能形成不合法 HTML。這是 source 推論，需以真正表格／子清單驗證，不能攤成純文字來迴避。合法 renderer 接線是有限整合，仍需明列。
- **屬性刪除：**computeDiff 的 `newProperties` 可用 `undefined` 表示刪除；diff JSON 往返會丟掉該 key，官方範例只迭代新 properties 的說明可能因此漏項。從保存的乾淨前後快照重算比較，不把封存的 diff JSON 當正式可恢復表示；記憶體複製須保留 undefined。
- **屬性值：**object 值須展開成可讀前後值，不以 `[object Object]` 充當差異說明。
- **身分：**實際 Slate React renderer 的 key 由 `ReactEditor.findKey` 取得，不直接等同業務 `element.id`；重複業務 ID 不足以推定 DOM 必然漏項，也不能免驗。應觀察前後兩份正文都存在、comparison 不成為 current 寫入目標。
- **既知反例：**原生 diff 保持原樣，另呈現真實前後值及確實捕捉的當批 operation，標明原生比較的缺口。若重開只有快照而沒有操作紀錄，不得捏造已不存在的 operations。持久捕捉及呈現尚未驗。

下一個有界驗證：完整 r2 的前版／後版／比較三個唯讀 editor；固定正文、格式、表格內容、Element 0／false／object／刪屬性、同 ID 正文＋屬性及兩個反例；保存乾淨版本及所需操作材料後清除 session 重開。Pass 是必要內容與改動仍可讀、無漏段且材料未污染 current；若須自造通用比較引擎才能滿足，停止此路線，用同一失敗情境核對 PM 原生 Step 組合。這不是重跑三套完整實验的授權，也不是已完成證據。

## 人與 AI 的原生 undo 接點：追加 source 核對

只讀固定安裝版 `@platejs/core@53.3.11`、`@platejs/slate@53.3.10` 及 Slate 0.126.2；**以下未跑新實驗**。程式位置是可由封存 lock 重現的 `@platejs/slate/dist/index.js` history／transform 與 `@platejs/core/dist/withSlate-CGuPv-qn.js` setValue 實作，公開 API 型別另核對同套件 `.d.ts`。

- `tf.apply` 能經原生 history 重播 operations；`withNewBatch` 讓同步 callback 的首個可保存操作另起一批，搭配 `withoutNormalizing` 可延後原生 normalization。這些不是版本檢查、保存交易或 rollback。
- `withNewBatch` 沒有封住後方；AI 後相鄰人工打字仍可能依 `shouldMerge` 合併。公開 `tf.setSplittingOnce(true)` 有下一批接點，仍須實測游標／IME 及 actor 交替，不可把已測單 session undo 擴張為 AI→人續編已驗。
- `tf.setValue` 透過 root remove／insert，會進 history、清 redo，**不是清空 undo 的單純同步 setter**。`reset()` 預設清 history；`withoutSaving` 只不記錄新操作，不替既有 undo 重算位置。三者均不能作未驗的「安全同步」捷徑。
- History wrapper 在底層 apply 前記錄操作，部分 wrapper 未用 try/finally 恢復旗標；中途 throw 可能同時留下部分內容及 history。這是 source 可見風險，尚未測到；不能對 live editor 用「再 undo 一次」假定回復完整。

後續 headless→browser 接線只需有限驗三組：同基底／同 plugins 的原生批次 undo／redo 往返；AI 後相鄰人工打字的批次邊界；拋棄式 editor 中途失敗的實際內容／history。headless selection 不自動代表員工游標；操作能 JSON 表示也不代表重開後 undo stack 自動存在。這是共同編輯接線的驗收要求，不另建 history／rebase 引擎，也不把此 source 查閱算入上方 13＋3 測試數。

## 實際執行與可重現材料

執行於 Windows／Node v22.12.0；原腳本在研究暫存區執行。可重現的[package](jd-native-probe/package.json)、[lockfile](jd-native-probe/package-lock.json)、[主 probe](jd-native-probe/probe.mjs)、[原生觀測](jd-native-probe/observe-native.mjs)及結果已封存到本 evidence 目錄；沒有複製 node_modules 或接入 monorepo。

在該封存目錄使用 `npm ci --ignore-scripts --no-audit --no-fund`，再執行 `npm run probe` 與 `node observe-native.mjs`。**主 probe 預期 exit 1**，因兩個真反例保持失敗；不能把這個 exit 改成全綠或稱套件已修復。重新執行會覆寫此目錄的 results，需另存原證據後才比較。觀測 probe exit 0。

| 實際檢查 | 結果與精確界線 |
|---|---|
| 巢狀職責／任務、用途、未知、來源 metadata 初始化 | 通過；合成 fixture 完整保留，不證明任意 schema 或完整 r2 已渲染 |
| 重複繁中句中的單一目標改寫 | 通過；其餘句子及條件不變；位置由固定測試供給，不是 LLM 定位成功 |
| 跨職責 move | 通過；任務 ID／全部 children 保留；diff 表示刪＋增，不是原生語意 move 識別 |
| split | 通過；文字連接與來源保留，新段有新 ID；不是任意業務拆分的身分決策 |
| 當前 session undo／redo | 通過；不證明關頁後保留 undo stack |
| JSON 檔案寫出、讀回、全新 editor | 通過；本文／metadata 相等；未使用 DB、未模擬斷電或網路遺失 |
| 非空文字 marks、新增／刪除 element props、element 的 0／false／object | 通過；update 保存所測前後值 |
| 同 ID 的 attrs 與 children 同時變更 | 通過可見性；刪＋增，headless normalize 後兩邊仍在，但比較值有重複 ID。比較文件不得當 current／寫入目標；React DOM key／實際 renderer 仍須驗證 |
| computeDiff 不修改乾淨前後快照 | 通過；正式文件與比較輸出可分離 |
| Text leaf `score:1→0` | **FAIL**：乾淨文件有 0，但 diff 新值變 undefined，JSON 後呈現空 properties；不是資料保存遺失，不能宣稱任意 leaf metadata 正確比較 |
| 空文字 `bold:true→italic:true` | **FAIL**：比較輸出有新 italic，沒有 diffOperation；完整改動高亮保證不成立 |

原始證據：[逐項結果](jd-native-probe/results/native-results.json)、[乾淨前後與 diff](jd-native-probe/results/native-diffs.json)、[重開的乾淨文件](jd-native-probe/results/clean-document.json)。

## 兩個反例的原生觀測

已讀實際安裝的 `@platejs/diff` dist 並與固定 source 比較：`getProperties` 的 truthy 判斷使 leaf 的 0 變成刪除；`flattenPropsChanges` 在空文字沒有足夠 range 端點時無變動標記。沒有修改套件或降低原 assertion。

追加以 `tf.setNodes` 真正修改兩種輸入，在 `onChange` 內同步複製 `editor.operations`。**兩案都能取得原生 set_node 的舊／新屬性，當前正文仍正確；flush 後 operations 清空。**第三案證明空游標的 addMark 只改當前輸入 marks，尚未改文件 leaf，不能和空 leaf 寫入混為一談。[完整觀測](jd-native-probe/results/native-observation.json)

這支持「原生當批操作資訊可供有限呈現」的候選，**沒有修好跨重開任意兩份 snapshot 的 computeDiff**。是否保存這些原生資訊及如何在人讀得懂的介面呈現，屬必要 App 整合，須列在設計和驗證；不能暗中叫它現成完整版本歷史。

## 選型影響

Plate 核心＋原生 diff 可保留為推薦候選，因所測 JD element 內容、結構與一般文字差異有正證。工作身分／用途／來源等應放可序列化的 element metadata，文字 leaf 保留文字及格式；這是符合其模型的設計候選，不是把丟資料改為允許。

**無條件「全部修改僅靠 computeDiff 都能看見」路線停止。**如選 Plate，必須明示上述限制，驗證原生操作資訊能否補足當次變更呈現；如需要任意兩版完整格式比較或選擇性歷史回退，現有證據仍不足，不能默認以自製引擎補齊。完整 r2、UI 與持久保存／恢復仍未驗。

## 範圍與完整性

只新增研究文件與暫存依賴；`git diff --name-only -- apps packages package.json package-lock.json` 無輸出。0 LLM 生成，未啟動 DB 或產品；前段 metadata 查詢遇到 sandbox 網路／npm cache 限制後，使用核准的官方 npm 唯讀／隔離安裝，停用 lifecycle scripts。

封存 SHA-256：主 probe `EA175EBA8B4F0DF6D3379A769D93043CCA0F5CA28C269413FE4EE13D33AF2393`；lock `5590879C825D449CC6EFBEE87B170DA758E9621E723929C13C84C298C8673DB0`；主結果 `0A69554B22ED13764E7D47093E2B91210A437BD9AE6F3B94622A91C57EA3C06F`。獨立研究者已唯讀對照兩個失敗與安裝版原始碼，確認反例成立；不是完整產品設計審查。
