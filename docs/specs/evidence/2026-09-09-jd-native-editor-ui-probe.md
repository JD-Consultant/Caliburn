# 完整 JD 的 Plate 原生比較與重開：有限呈現結果

JD-R002/C03；2026-09-09；**固定 Node／SSR 檢查 29 項通過，瀏覽器呈現與檔案重開已觀察；兩個原生 diff 反例仍成立。**本次只驗證第一候選的呈現接點，不是框架採用、完整編輯器或 S5 設計驗收。

## 結論與實際範圍

Plate 可以在真正 React 唯讀 editor 中呈現完整 r2 的文字、表格、子清單及原生比較；保存乾淨前後快照與當時操作材料後，另一個 Node 程序及瀏覽器重開仍能呈現固定內容。這支持保留第一候選，**不支持「computeDiff 自動完整顯示所有業務欄位變更」**。

新限制已明列：任務 3 同時改正文與 scope 時，原生結果是刪＋增，兩份正文均顯示，但 scope 僅在展開 JSON／材料裡可讀。要讓員工看懂必要欄位，仍需按正式 JD 內容做有限 renderer；不能因正文紅綠已顯示就當所有 metadata 通過。沒有擴大為通用 metadata diff、修訂或回退引擎。

## 固定材料與結果

- 底座仍為 `platejs@53.3.11`、`@platejs/diff@53.0.0`、React／React DOM 19.2.4；新增 esbuild 0.25.12 只作隔離建置。46 項實裝依賴的宣告與例外依[授權清單](jd-ui-probe/results/license-inventory.json)，不混付費功能。
- 完整 r2 手寫為固定 fixture，包含原稿全部敘述、三張表格與子清單；只是測試資料，不是通用 importer 或正式 JD schema。新版刻意添加七個原生操作所產生的合成改動，並非修改已同意樣稿。
- [29 項 Node／SSR 結果](jd-ui-probe/results/ui-node-results.json)包含原稿去 Markdown 標記及空白後逐字比對、前後實際 SSR 文字、初始化、另程序重開與兩個反例仍成立。這些不是 29 個「原生 diff 正確」案例，也不取代原先 13 項中 2 項失敗。
- [瀏覽器觀測](jd-ui-probe/results/browser-observations.json)獨立記錄：三欄共 9 張真表格；diff 的 table→tbody→tr→td 合法；子清單存在；同一 task3 ID 的兩份正文都在，分別為 diff-delete／diff-insert。實際按重開後仍成立，切到反例也可讀到保存的前後值與 operations。沒有觀察到 browser warning／error。
- 兩個反例仍如實展示：文字 leaf 的 `1→0` 被 diff 表成 undefined；空文字格式改動沒有 diffOperation。補列真實前後及確實保存的 operation，只是揭露缺口，沒有修補原生 diff。

瀏覽器曾有定位工具 timeout；重新讀實際 DOM 已確認節點存在，改用已記錄的 DOM 唯讀檢查完成。這是操作工具的限制紀錄，不把它隱藏成產品成功或誤報成編輯器崩潰。最終重新 build 後也已 reload，確認 undefined 說明改成中性的「未設定／原生移除值」。截圖位於 CUA 對話工具紀錄，未另存為圖片檔。

## 原生與有限整合的分界

沿[官方免費 version-history-demo](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/apps/www/src/registry/examples/version-history-demo.tsx)的接點，註冊固定 element／mark 並以 PlateElement／PlateLeaf 呈現原生 diff。為保持合法 HTML，表格使用 tbody，差異色彩放在原節點；沒有把所有 element 包 div。只讀原生 update 欄位呈現 0、false、object 及 undefined，不從快照補算缺失的 diff。

正式比較每次由乾淨快照重算，沒有保存 diff 成 current，也沒有重播 operations。保存材料採研究檔案，**未驗 PostgreSQL 交易、保存失敗、回覆遺失、crash、live editor 同步、人／AI undo、IME、選取、貼上、任意 JD 或真模型品質**。三欄研究畫面也不是已選定的員工 UI。

獨立只讀 review 未發現阻擋此次限定結論的問題；確認未造 diff／history，引述的通過範圍與已知失敗分開。一般業務欄位的可讀性仍是缺口。

## 重現與下一步

[完整材料入口](jd-ui-probe/README.md)含來源、固定依賴、保存材料、SSR HTML 與重現方法；node_modules、瀏覽器 bundle 及生成的 server renderer 沒有封存，依 lock 重建。研究 server 已停止，沒有留下新產品服務。

**下一步是根據已知缺口完成候選的有限整合與接線設計**：必要 JD 欄位如何在正文／變更中可讀、模型如何透過既有 tools 使用原生 editor、操作／保存／回執及人工 undo 的責任。已有原生接點不等於已接線；後續已選的工作稿流程依[候選 §3](../2026-09-09-jd-editor-framework-decision-candidate.md#3-已選的持續工作稿流程)，不能由本 probe 默認完整驗收。此後只驗能推翻具体接線的未知，不再重做三套廣泛比較。
