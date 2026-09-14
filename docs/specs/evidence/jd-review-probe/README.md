# R01：尚未確認建議的原生取消／接受與重開

JD-R002/C03；2026-09-09。此為有界研究，不採用框架／審閱政策，不改 production、Memory、原 native／UI／P01 probe。

## 固定問題與停止條件

只驗「尚未確認建議可取消，不傷別處」；不是任意已接受歷史回退。不使用 LLM、AI helpers、自製 diff／codec／review／rollback。若一般 SuggestionPlugin 原生 API 無法維持所需範圍，記 FAIL／unsupported，不造共組 metadata 或修引擎。

判準用真正的前後 JSON／正文／原生修訂 ID；重開必須 JSON.stringify→檔案→JSON.parse→全新 editor。記憶體控制組使用 structuredClone 保留 undefined；原始 inspect 診斷文字另存，不能當 codec 回灌。保留首次失敗，不能以改 assertion 或抹除 metadata 湊全綠。

## 固定依賴與授權

- `platejs@53.3.11`（MIT）、`@platejs/suggestion@53.2.3`（MIT）。不要把 monorepo release v53.3.12 當套件版號。
- React／React DOM `19.2.4`（MIT）滿足 suggestion 官方 peer `>=18`；platejs peer `>=53.0.3`。
- `@platejs/diff@53.0.0` 固定 suggestion 所需依賴；package LICENSE 的 Apache-2.0 衍生／修改部分雙授權分開記錄。本 probe 不直接呼叫 diff 或 AI helper。
- 新目錄隔離 package／lock；安裝使用 `--ignore-scripts --no-audit --no-fund`，不改任何既有安裝環境。實裝版本／授權清單及 lock/hash 另存 results。
- 官方固定 source：`cee7a4ec0328718d8cf147094466b597215f5406` 的 `packages/suggestion`；先讀既有 evidence §7–9 與 source/tests，實装後再核對 dist／types。來源與 SHA-256 保留；本輪不廣搜。

## 原生接點

`createSlateEditor`＋`BaseSuggestionPlugin`（React SuggestionPlugin 的原生基底）；公開配置 `isSuggesting:true`、`currentUserId`。Node ID 啟用，固定 `reuseId:true`、`initialValueIds:'always'`。普通段落 fixture，沒有關閉 normalization 或編輯器 ID 來避錯。

用 `tf.select` 明確選取，再走一般 `tf.insertText` 完成 old→new 替換；另處 `tf.insertNodes` 加故障說明。Suggestion wrapper 依目前 selection 工作，不把低階 apply 或手寫 suggestion metadata 偽裝成原生追蹤。用公開 `api.suggestion.dataList/nodeId/nodes` 讀原生 ID；`acceptSuggestion`／`rejectSuggestion` 以該 ID 結算，包在官方 `api.suggestion.withoutSuggestions` 內。

四組固定操作：

1. **R01-1／取消獨立組。**月檢原文「僅有月檢約定的專案按月檢查。」改為「所有專案都按月檢查。」；另新增「記錄故障處理結果與未解事項。」。兩處均 pending。保存重開後 reject 月檢；要求原月檢恢復，故障正文及 pending 身分完整保留。
2. **R01-2／接受目前版本。**相同 pending fixture 保存重開後 accept 月檢；要求接受當前新文，該組標記結清，故障正文及 pending 保留。
3. **R01-3／AI→人工→AI。**在第 1 組月檢的目前新文依序原生替換，切 currentUserId 為 `ai`→`human`→`ai`。人改「僅有月檢約定的專案按月檢查，並記錄結果。」；再 AI 改「僅有月檢約定的專案按月檢查，記錄結果並追蹤未解事項。」。不直接改 metadata、不強造共組。記每階段 ID／正文；重開後分別 accept／reject 原始月檢 ID，觀察能否結算同一待審組最新版並保留別組。原生若拆成多 ID，明列範圍與限制。
4. **R01-4／取消粗體與 JSON。**原本 bold=true 的固定正文，全選後原生 removeMark('bold')，保持 pending。對照記憶體新 editor 與標準 JSON 重開後 reject；要求恢復原粗體。觀察 undefined payload 是否在 JSON 消失；不加 codec。

## 未驗範圍

無 DOM／IME、UI 可讀性、多使用者協作、任意相依群組、表格／巢狀結構、block attrs、正式 DB、重送／交易、真模型或跨版本移植驗收。固定 actor ID 只是 plugin attribution 情境，不是新增產品角色或權限。

## 首次實際結果與重現

2026-09-09 14:36:40 UTC、Node `22.12.0`：**2 組 PASS、2 組 FAIL、0 組執行錯誤**；18 個判斷中 14 個通過、4 個失敗。首次結果固定保留於 `results/2026-09-09T14-36-40-805Z/`，詳讀 `RESULTS.md`。R01-1／2 證實此固定文字替換與獨立段落可保存後個別結算；R01-3 跨作者續編不能以原始 ID 結算整條續改；R01-4 標準 JSON 重開後無法拒絕移除粗體以恢復原格式。未修套件、改判準或重跑湊全綠。

重現環境只需本目錄的 `package.json`、`package-lock.json`、`review-probe.mjs`，無 DB、模型或其他 probe runtime 依賴。在新的隔離目錄使用相同 Node，執行：

```text
npm ci --ignore-scripts --no-audit --no-fund
node review-probe.mjs
```

腳本以 UTC 時間另建結果目錄，保留之前結果；只要原失敗仍在，預期 exit code 為 1。IDs／createdAt／執行時間由原生產生，跨次執行不要求其位元相同；判斷依當次真實原生 ID 與內容。

`capture-source.mjs` 是本輪來源封存輔助程式，不是 runtime probe 的前置步驟；它讀取同層 `../jd-oss/plate/packages/suggestion` 的既有官方固定 source。若只重現行為，毋須重跑它。封存應保留 `README.md`、`RESULTS.md`、兩個 `.mjs`、package／lock、`source/`、`results/`；不封存 `node_modules/` 與 `.npm-cache/`。原始 traces 的 `.inspect.txt` 保留 undefined 診斷，JSON 檔保留實際可保存形狀，兩者都應留下。

實裝 45 個套件的版本／license 宣告在 `results/dependency-inventory.json`：43 個 MIT、1 個 Apache-2.0、1 個 `@platejs/diff` 另讀 package LICENSE（上文已區分）。`results/source-manifest.json` 記 23 個官方 source／test 與實裝 dist 檔的原檔／副本 SHA-256；包括 `dist/index.js` 真正引用的 `dist/src-CMqLOrDd.js` 實作，不只入口重匯出檔。來源副本 hash 全相等；這不等於將 TypeScript source 和編譯 JS 宣稱為相同檔案。首次 run 的 script／lock／results／traces hash 另存於該 run 的 `run-hashes.json`。
