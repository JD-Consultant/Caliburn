# T09 正式 JD 來源唯讀 UI bounded 子切片

- 日期：2026-09-30；分支：`target-rebuild`。前端切片已實作並完成下述離線驗證；不宣稱 T09 整體完成或 production 已切換。沒有 commit、付費 API、新代理、Demo 資料修改或啟停 server／browser。
- 上位：[T09](../tasks.md#t09-訪談-ui候選即時預覽與重連)、[介面 §3](../../../implementation/interface-and-delivery.md#3-顯示與來源)、[程式組織](../../../implementation/code-organization.md)、[撰寫規範](../../../implementation/coding-standard.md)、[SDD／TDD](../../../implementation/development-standard.md)。本次 Owner 明確限於正式來源唯讀，不增加核對或改引用命令。
- Canonical HTTP schemas 與生成 TS 由 main 提供；本 worker 只讀並以 Ajv2020／ajv-formats 編譯同一 schema，沒有修改後端、schema、shared/api/generated 或模型 tools。

## 可觀察效果與接線

`JobFilePage` 在 JD 編輯器之後組裝 `SourceViewer`。「正式 JD 來源（唯讀）」預設收合，展開才 GET 列表；每個引用旁顯示後端的目標標籤及 `needs_recheck`。未附引用使用中性提示，不代表內容錯誤或已核對。

選取引用才 GET 固定正文。Memory 只沿回傳 `source_ref` 再讀，opaque 值經 URLSearchParams 編碼後原樣傳送，不解析它或猜版本；可回到直接來源。訪談用原序號、角色及轉義原話呈現，保留換行。只有 Memory 直接引用提供引用鏈差異 GET，說明比較原引用固定版本與「讀取當時最新已發布」Memory。讀來源／差異不更新核對狀態，沒有 POST、核對或改引用按鈕。

| 用途 | query key 與生命週期 |
| --- | --- |
| 正式來源列表 | `['jd-profile', jobFileId, 'formal', 'sources']`；附掛既有正式 JD prefix，獨立 GET 及 schema |
| 固定正文 | `['jd-source-content', jobFileId, revisionId, citationId, sourceRef]`；root 的 sourceRef 為 null |
| 引用鏈差異 | `['jd-source-changes', jobFileId, revisionId, citationId]`；此 endpoint 比較整條 citation，沒有 source_ref 參數 |

現有 `InterviewComposer` 的 A 完成會 invalidate `['jd-profile', jobFileId]`；人工 profile／work 與撤回均 invalidate `['jd-profile', jobFileId, 'formal']`。因此列表會隨既有操作更新，不跨 feature 匯入私有 API，不另建 cache invalidation 平台。元件切換檔案以 key 重設 disclosure；列表重讀時卸載選取區，完成後以 revision／dataUpdatedAt 重建，連同 child／diff 選取一併清除，避免混版。正文不使用 placeholder。所有查詢沿既有 requestJson，傳入 AbortSignal，明確關閉 retry／window-focus refetch；正文及差異再核對回傳 revision／citation 身分。

409 顯示正式 JD 已更新並要求重讀列表；404 在 feature 顯示此來源無法讀取，不沿共用 HTTP 的「檔案不存在」文案，也不當作空列表；503、422、schema 不符與網路錯誤保留明確錯誤。服務私有錯誤 body 不顯示。重讀失敗不顯示舊詳細資料，也不解除待核對。

## 官方研究與唯一新增依賴

查閱當前第一手文件，採現有 MUI Button／Stack、TanStack Query 與 Ajv；沒有自製 Markdown parser、前端來源規則或新平台。

- [TanStack query keys](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys) 要求 cache key 包含查詢變數；[prefix invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation) 支持本案沿現有 formal prefix 刷新列表。資料固定資格仍由後端負責，框架不保證引用正確。
- [MUI Accordion](https://mui.com/material-ui/react-accordion/) 核對 disclosure 與按需卸載機制；本案沿已有 `HistoricalTurnMessages` 的 MUI Button、aria-expanded／aria-controls 及條件掛載 pattern，無須新元件依賴。
- 新增且精確鎖定 **react-markdown 10.1.0，MIT**；官方 [package metadata](https://raw.githubusercontent.com/remarkjs/react-markdown/main/package.json)、[安全與元件選項](https://github.com/remarkjs/react-markdown#security)。React peer `>=18`，與現有 React 19.3.0 相容。官方聲明預設以 React 節點安全呈現，plugin／自訂轉換會影響安全，不能把採用套件等同完整安全 gate。
- `SafeSourceMarkdown` 使用 `skipHtml`，無 raw HTML plugin、無 dangerouslySetInnerHTML；links 轉成沒有 href 的純文字 span，images 只呈現 alt span，不建立 img 或外部請求。保留預設 URL transform、Markdown 標題／段落／強調與 literal fenced diff code。原始訪談不走 Markdown。
- 替代方案：純文字不能滿足可讀 Markdown 標題／diff；自行解析或 HTML parser＋消毒將增加規則維護。本案只加 react-markdown 及其 lock 中的必要相依，不加 syntax highlighter、remark-gfm 或 rehype plugins。退出方式是替換單一 SafeSourceMarkdown 呈現邊界，wire／資料與 query 不受影響。
- 根 `pnpm-lock.yaml` 為唯一 lock authority。最初依錯誤 scope 產生的 `apps/web/pnpm-lock.yaml` 已確認為本 worker 產物並移除；後續 Owner 明確授權根 lock。pnpm script 的自動 workspace 同步曾引入無關 Next peer resolution，已精確清掉。最終 root lock diff **678 additions／0 deletions**，既有版本與 peer resolution 沒有改動。供應鏈 policy 檢查 485 entries 通過；這不是完整漏洞稽核。

## TDD 與驗證證據

測試只替換 fetch 這個外部邊界；實際 React、MUI、Query、Ajv canonical guards 與 Markdown renderer 均執行。fixture 全為合成資料，不操作 Demo DB。

1. 初始 tiny SourceViewer 回傳 null、SafeSourceMarkdown 只回傳轉義文字，兩個測例明確因缺少「正式來源展開按鈕」與「Markdown heading／code」而失敗：**2 failed**。沒有把缺 import 或編譯錯誤當 Red。首次 sandbox Vite spawn EPERM 是環境失敗，使用正常 escalation 後才取得上述行為 Red。
2. 列表／renderer 初步接線後，新增固定鏈導覽、錯誤、reset 與拒收反例：**11 failed／5 passed**，失敗是無來源正文／衝突提示／空列表語意，非 build 問題。
3. 正文、差異與生命週期實作後 **16 passed**；再加既有兩種 invalidation prefix、新 revision、同 source_ref 不同 citation 及 404 文案的回歸例。以 fresh cache（測試 staleTime Infinity）防止 refetch 掩蓋 key 少維度的缺陷。最終專項 **20 tests**，納入下面全套。

PowerShell 環境：

```powershell
$sourceNode = 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
$sourcePnpm = 'S:/caliburn/.research-tmp/pnpm-12.5.1/package/bin/pnpm.mjs'
# S:/caliburn；Node bin 在本程序 PATH
& $sourceNode $sourcePnpm install --filter @caliburn/frontend --frozen-lockfile --strict-peer-dependencies --ignore-scripts
# 以下 cwd = S:/caliburn/apps/web；直接呼叫對應 package scripts 的工具，避免再次觸發 pnpm 自動安裝
& $sourceNode node_modules/vitest/vitest.mjs run
& $sourceNode node_modules/typescript/bin/tsc --noEmit
& $sourceNode node_modules/eslint/bin/eslint.js .
& $sourceNode node_modules/vite/bin/vite.js build
```

- Root frozen install：exit 0，lock up-to-date、不重新解析；首次 `--offline` 因缺供應鏈 metadata 失敗，正常連線保留 policy 後通過。
- 完整 web Vitest：**18 files／115 tests passed**，12:19:24 Asia/Taipei 開始，14.56 秒，exit 0。
- tsc --noEmit、完整 eslint：exit 0。
- Vite production build：exit 0，1342 modules；單一 JS chunk 907.80 kB、gzip 271.11 kB，仍有 >500 kB chunk 警告，沒有調高 warning 門檻或宣稱效能 gate 完成。
- 格式依現有 Prettier；scope 差異與空白檢查通過。測試包含 GET-only、按需載入、root→child→正式訪談、Memory-only diff、needs_recheck 保持、跨檔 reset／晚到 response、新 revision／citation 隔離、409 清除選取、404／503 不是空、非法 private／candidate 欄位拒收、HTML／圖片／各類 URL 無 active DOM。

## 交付與限制

改動範圍：`apps/web/src/features/source-viewer/{SourceViewer,SourceDetails,SafeSourceMarkdown}.tsx`、`source-api.ts`、兩份 component tests；`apps/web/src/app/JobFilePage.tsx`；`apps/web/package.json`；根 `pnpm-lock.yaml`；本 evidence。沒有改 task 狀態或其他 owner 文件。

本 worker 沒有自行執行真 PostgreSQL、真模型、瀏覽器或 Demo 旅程；後端三條 route／PG 測試及接下來真瀏覽器整合由 main 驗收，不將其報告當成本 worker 實測。完整鍵盤／窄螢幕、真瀏覽器 A 完成後更新與跨 tab 操作、較廣安全／效能仍屬 main 的 T09／T12／T15 gate。未新增 Memory 管理、核對／引用編輯、來源候選或任何模型能力。
