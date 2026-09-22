# JD 原生 history／同步：有限接線驗證

JD-R002/C03；2026-09-09；**9 項有界觀測，8 項預期觀測成立、1 項精確 ID 往返失敗；多個成立項本身就是限制或反例。**不能簡稱 8 項產品能力通過。原先 13 項中的兩個 diff 反例、追加 3 項觀測與 UI 結果均未改判。

本輪只回答[定案候選 §6](../2026-09-09-jd-editor-framework-decision-candidate.md#6-可收斂與尚不能宣稱的事項)的人工續編接點。Plate 仍是候選，沒有採用新審閱政策、history 引擎、schema、保存 authority 或 production 改動。

## 範圍、判準與設定

- **Topic／stage：**JD-R002/C03；具體接線設計所需的 isolated probe。有效方向沿 register：員工可閱讀／核對／更正，保留手編；AI 真實改動可見；既有 Memory／JD 內容成果沿用。
- **本輪唯一問題：**同一基底的原生操作同步，以及 AI→人工的本 session undo／redo，能否用已公開接點維持正確內容與身分？setValue／reset／withoutSaving／中途 throw 能否被誤當安全同步或 rollback？
- **判準：**肯定實際乾淨 JSON、ID、undo／redo 內容；旗標與 history 長度只是補充診斷。失敗保留，不改框架、原 assertion 或基底來湊全綠。
- **成本與排除：**使用已安裝固定免費依賴，0 新套件、0 LLM／付費請求、0 DB／production；只新增 `.research-tmp/jd-editor-native-probe/history-probe.mjs` 與 `results/history-*`。沒有 DOM、IME、游標焦點、網路、stale 基底、rebase 或任意 schema 驗證。

實裝版本：`platejs@53.3.11`、`@platejs/core@53.3.11`、`@platejs/slate@53.3.10`、`slate@0.126.2`、React `19.2.4`；Node v22.12.0，`NODE_ENV` 未設定。本輪使用的核心／Slate／React 是 MIT；既有 diff 53.0.0 沒有在本脚本使用，授權及原始 44 項依賴清單沿[前報告](2026-09-09-jd-native-editor-probe.md#固定範圍)。repo release 不是各 npm package 版號。

| Profile | Node ID | 初始化／normalization | 實驗效力 |
|---|---|---|---|
| H01–H08 | **啟用** NodeIdPlugin；只自訂每個 editor 從 1 起算的 `history-new-N` idCreator。沒有設定 reuseId，固定 source 以 falsey 處理；沒有 `nodeId:false` | initialValueIds 未指定，解析為 `if-needed`；shouldNormalizeEditor 未指定，沒有強制初始化 normalize；使用正常原生操作 normalization，明列批次以 withoutNormalizing 延後 | H01 的兩個 generator 初值恰好相同，不能把第一次 ID 相同推成隨機 ID 也會一致 |
| H09 | **啟用** NodeIdPlugin；`reuseId:true`、`initialValueIds:'always'`；source／target 的 idCreator 刻意分別為 `history-source-N`／`history-target-N` | 其餘同上；split／apply 放在 withNewBatch＋withoutNormalizing 內。基底已有 ID，因此本案沒有實測「補齊缺少的初始 ID」 | 僅證明此公開設定下的固定 split 同步與 undo／redo；不證任意 schema、重複 ID 或複製貼上 |

兩組都沒有關掉 ID 或 normalization 來避開失敗。H01／H09 的 target 是透過 `createPlateEditor` 建立的第二個 React Plate editor，但仍在 Node 無 DOM 環境；不能稱 browser／IME 已驗。

## 實際觀測

完整[結果](jd-native-probe/results/history-native-results.json)及[前後、history、selection、operations traces](jd-native-probe/results/history-native-traces.json)可逐項核對。所有位置都是合成 fixture 提供，不是 LLM 定位成功。

| 案例 | 真實結果 | 對接線的影響 |
|---|---|---|
| **H01 混合批次與 ID 往返** | Headless 一批含插字、element attrs、bold、insert_node、move_node、文字／段落 split 共 7 個原生 operations。JSON 往返後以 tf.apply 重播至第二 editor，第一次完整 JSON 相等；undo 回 baseline 相等；**redo 後新段 ID 從 history-new-1 變 history-new-2，精確 JSON 失敗** | 預設 falsey reuseId 不能承諾拆分身分穩定。初次同步的相等受相同 deterministic generator 計數影響，不能當 default nanoid 也穩定的證據 |
| **H02 AI 後方沒有分批** | 原文 `本`，人加 `前`，AI withNewBatch 加 `AI`，flush 後人再加 `人`。內容是 `本前AI人`；第一次 undo 得 `本前`，同時移除 AI 與後方人改；第二次回 `本`；redo 依序回 `本前`、`本前AI人` | withNewBatch 只建立 AI 開始的分界，不自動封住其後相鄰打字 |
| **H03 明示下一批** | AI 批後呼叫 setSplittingOnce(true)，人依序打 `人`、`改`。`本前AI人改` 的 undo 依序為 `本前AI`→`本前`→`本`；redo 精確反向返回 | 固定 headless 連續打字的 AI／人邊界可沿原生接點建立；不是 actor-aware 引擎，也未驗 IME、實際選取或其他插件是否先消耗下一批旗標 |
| **H04 setValue** | 先有人工 A，另批 B 再 undo，留下 redo B；setValue 換成 `另一份` 後清 redo。undo 先回 `原A`，再回 `原`；redo 依序回 `原A`、`另一份` | setValue 是進 history 的根節點替換，保留更早 undo；不是單純同步 setter，也不是清空 history |
| **H05 reset** | 原文件已有 undo／redo；reset 產生帶 ID 的空 p，兩個 history stacks 都清空。之後 undo／redo 都維持該空文件 | reset 有明確破壞本 session 編輯歷史的效果；不能當維持手編 history 的背景刷新 |
| **H06 withoutSaving(setValue)** | `原`→人改 `原人`，不存 history 地換成新 ID 文件 `完全不同`。舊 undo 仍在；undo 實際成為 `完不同`；redo 成為 `完人不同`，都不是恢復外部稿 | 沒有原生 rebase；舊位置會套在新稿。**「換整份值但保留舊 undo」捷徑被反例推翻** |
| **H07 中途原生 apply 拋錯** | 原 `原人`，AI 先加 `AI`，再 tf.apply 到不存在的 `[99,0]`。原生錯誤留下 `原人AI`，history 已含無效操作；嘗試 undo 再拋錯，文件仍是 `原人AI` | withNewBatch／withoutNormalizing 沒有交易 rollback；不能對 live editor 假設「出错 undo 一次」就恢復。此拋棄式 editor 沒有修補或接回使用 |
| **H08 withoutSaving callback 拋錯** | 原 `原人`，withoutSaving 加 `暫` 後 callback throw；之後普通人改加 `後`，成為 `原人暫後`。undo 只移除更早的 `人`，留下 `原暫後` | 例外後新的普通人改仍沒有可撤銷批次。實際 undo 證明狀態受影響，不只依賴 saving 旗標；沒有嘗試修旗標或 history |
| **H09 公開 reuseId profile** | `確認範圍。` 拆成 `確認`／`範圍。`；兩 editor 使用不同 ID 生成流，仍以原生 operations 保留 `split-base`／`history-source-1` 及 sourceRefs。target 同步、undo／redo，source undo／redo 全部精確 JSON 相等 | 支持把 ID profile 列為必要接線契約並使用原生 reuseId 接點；**僅此固定 split 正證**，沒有改判 H01 或宣稱所有 transforms 都因此通過 |

第一輪 8 案的結果／traces 另保留為 [first-run results](jd-native-probe/results/history-native-first-run-results.json)／[first-run traces](jd-native-probe/results/history-native-first-run-traces.json)；追加 H09 沒有刪掉 H01 的失敗。最終脚本 exit **1** 是刻意保留該真失敗，不是漏跑完成項。

## 官方及固定 source 核對

| 來源 | Publisher／日期與查閱 | 版本／授權 | 可支持的 Fact |
|---|---|---|---|
| [Editor Configuration：Node ID](https://platejs.org/docs/editor#node-id) | Plate 官方；頁面未列發布日；查閱 2026-09-09 | 現行文件；固定實裝另核對 | Node ID 預設啟用；reuseId 預設 false；initialValueIds 預設 if-needed，可指定 always。這些是不同選項，always 不能代替 reuseId |
| [@platejs/core 官方 npm 發布](https://registry.npmjs.org/@platejs%2fcore/53.3.11)；實裝 `dist/withSlate-CGuPv-qn.js` | Plate／npm；查閱 2026-09-09 | 53.3.11／MIT | withNodeId 約 L2813–2890：split_node 在 `!reuseId`、ID 缺少或已有同 ID 時生成新 ID。NodeIdPlugin 約 L2924–3080：if-needed 可因首尾已有 ID 而略過初始值巡查。setValue 約 L3298：走根 children replaceNodes；init 約 L3179：只有 shouldNormalizeEditor 真值才 force normalize |
| [@platejs/slate 官方 npm 發布](https://registry.npmjs.org/@platejs%2fslate/53.3.10)；實裝 `dist/index.js` | Plate／npm；查閱 2026-09-09 | 53.3.10／MIT | reset 約 L2374；history wrappers 約 L2440–2490；withHistory／shouldMerge 約 L2696–2790。history 在底層 apply 前記錄；withNewBatch／withoutSaving callback 沒有 try/finally；相鄰同 path 插字可合批 |
| [Slate 官方 npm 發布](https://registry.npmjs.org/slate/0.126.2)；實裝 `dist/index.js` | Slate／npm；查閱 2026-09-09 | 0.126.2／MIT | withoutNormalizing 約 L4486 使用 finally 恢復 normalization 狀態，但 callback throw 仍不會回復已改文件；沒有提供 rollback |

**Fact／Inference／Mapping 分界：**上表是實裝 source 或官方文件事實；前表是本機實測。依 source 推論 H01 若改用彼此獨立的隨機 ID 流，第一次 split 重播也沒有 ID 相等保證；本輪未跑 default nanoid 的隨機實驗，不能把推論列成另一項測過的失敗。H09 的原生設定支持「同一 baseline、同一明列 ID／normalization profile 的操作同步」作接線候選，這是設計映射，仍需正式 schema 與 browser 交替編輯驗收。

## 接線能收斂的部分與 Unknown

1. **原生批次仍可用，但設定是契約的一部分。**不能只寫「兩邊都是 Plate」；Node ID、schema、normalization、基底版本都要一致。固定 H09 證明有免費原生接點可保留 split ID，不需要為此自製 history；尚未把 H01 的混合批次完整重跑在 H09 profile，亦未驗重複 ID／複製貼上／所有結構。
2. **AI 前後的 history 分界須明示。**H03 支持正常同步情境下用 withNewBatch＋withoutNormalizing 及 AI 後 setSplittingOnce(true)；沒有證明任意 browser 操作都能維持此邊界。DOM／IME／焦點、selection 是否以員工端為準，以及插入其他可保存操作的交替，仍是正式人工續編驗收。
3. **整份 setter、reset、withoutSaving 或出错 undo 不能代替同步／交易。**H04–H08 已直接否定幾個捷徑。應沿候選的隔離執行與明確成功／失敗回執設計；本報告沒有實作 commit、回覆對帳、rollback、重試或 stale 處理，也不新增第二個保存 owner。

本輪不再增加同類實驗。下一 gate 是主線把上述 ID profile、正常／失敗分工寫入具體接線設計，選定必要 browser 續編與 durable save 驗證；不是直接採用框架或進 production。

## 重現與封存完整性

新增封存：[history-probe.mjs](jd-native-probe/history-probe.mjs) 與上列 `results/history-*`。依既有 package／lock 的環境執行 `node history-probe.mjs`；**預期 exit 1，H01 的 ID 反例應保留**。腳本寫出完整 JSON traces，會在執行前後確認原 `probe.mjs`、`observe-native.mjs`、`native-results.json`、`native-observation.json` SHA-256 未變。

來源及封存腳本／結果的 SHA-256 相等見新增 [history-artifact-hashes.json](jd-native-probe/results/history-artifact-hashes.json)。沒有重跑或改動原 13＋3 probes，沒有安裝依賴、改 product、commit 或 push。Source findings 與實測影響只供 JD-R002/C03 接線收斂，不構成新的 durable 產品決策；register 由主線同步。
