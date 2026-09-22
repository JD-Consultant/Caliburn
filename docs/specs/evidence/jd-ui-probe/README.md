# JD 完整 r2：Plate 唯讀呈現的有限驗證

2026-09-09；研究暫存，不接 production、不代表框架或審閱政策已採用。

**主線封存註：**此副本位於 `docs/specs/evidence/jd-ui-probe`；實際瀏覽器結果另見 `results/browser-observations.json`，研究 server 已停止。以下是重現命令，不代表背景服務仍在執行。封存不包含 node_modules 或生成的 bundle；安裝、build 後才 verify／serve。重新執行會產生新結果，請另存原證據作比較。

## 範圍

- 只在本目錄建立隔離 package、固定 fixture、保存材料、React 頁面及驗證結果。
- 使用 `platejs@53.3.11`、`@platejs/diff@53.0.0`、React／React DOM `19.2.4`。額外建置依賴固定版本並記錄授權；安裝停用 lifecycle scripts。
- 完整呈現 `docs/specs/2026-09-09-frontend-engineer-jd-sample.md` 的 r2 文字與表格／巢狀清單；fixture 明確手寫，不建立通用 Markdown importer 或產品 schema。
- 真正 React Plate 唯讀前版、後版與原生 `computeDiff` 比較。明列少量節點／leaf renderer 接線；沒有現成的 exported DiffKit。
- 固定正文、marks、表格、element 0／false／object／屬性刪除及同 ID 正文＋屬性雙改案例。原生 diff 原樣保留。
- 已知 leaf `score:1→0`、空文字 `bold→italic` 反例另列乾淨前後及實際捕捉的原生 operations。操作材料只是觀測，不能替換／修補 diff 或製造歷史回退。
- 將乾淨快照與 operation 材料保存為檔案；全新 Node 程序及頁面重開時從保存資料重算 diff。diff 不保存為 current，也不依赖 diff JSON roundtrip（undefined 會遺失）。

## 判準

1. 完整 r2 各項文字均保留；表格與子清單使用相應 HTML 元素，不把它們攤成段落。
2. before／after 與重開的乾淨文件相等；原生比較不污染它們。
3. 同 ID 刪＋增保留兩份正文。有限 props 說明如實呈現前後值，包括 object、false、0 與 undefined 刪除；不新增 diff 演算法。
4. 兩個已知反例仍如實顯示為原生比較缺口；保存的 operations 與實際批次一致，不為全綠修改套件。
5. Node 驗證與實際瀏覽器驗收分列。Node／SSR 通過不能冒充互動瀏覽器已驗收；本子題不使用 CUA，由主線檢查 localhost 頁面。

## 停止條件與未驗界線

若必需通用差異修補、定位或回退引擎才能呈現，停止並保存反例，不擴大。無編輯 toolbar、LLM、MCP、DB、登入、多使用者、任意文件或匯出驗證。有限手寫 renderer 不證明表格／清單可編輯能力、任意 schema 或完整變更高亮保證。

官方接點：固定 commit `cee7a4ec0328718d8cf147094466b597215f5406` 的 [version-history-demo](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/apps/www/src/registry/examples/version-history-demo.tsx)。採用其 leaf diff 呈現接點，將 element diff 色彩直接放在合法節點上，避免以 div 包住 tr／td。npm package 版號獨立於 repo release v53.3.12。

## 實際接線與固定改動

`fixture.mjs` 手寫 r2 的 h1/h2/h3、p、blockquote、table/tr/th/td、ul/li 及分隔線。文中研究連結的文字保留，目的地存在 `materials.source.referenceLink`；本 probe 不實作文件路由。`render.jsx` 只做以下有限接線：

1. 每種 fixture element 經 `createPlatePlugin` 註冊，交 `PlateElement` 輸出對應 HTML；table 補合法 tbody。hr 保留 Slate 的空文字 child，另呈現非編輯分隔線。
2. bold／italic 為 native leaf renderer；diff leaf 用 `PlateLeaf` 呈現 `diffOperation` 色彩與 title。element 的色彩／title 直接加在該節點，不另外包 div。沒有 exported DiffKit，也沒加入 suggestion 套件。
3. 頁面下方把原生 `update` 的 properties／newProperties 轉成可讀文字；保留 undefined 與 object 值。undefined 使用中性「未設定／原生移除值」，不把 oldProperties 尚不存在的值錯標成已移除。原生沒有產出的差異不補算。同 ID 同時改 attrs／正文是刪＋增，其 scope 值仍在原樣 diff／保存材料內，沒有冒充 update 高亮。
4. 頁面重開重新讀 `public/materials.json` 的乾淨 before／after／實際 operation 批次，呼叫未覆寫規則的原生 computeDiff。不保存 diff 為 current，不使用 localStorage、不編輯及不重播 operations。

完整 r2 案例有一批 **7 個**實際原生操作：職務目的追加固定句；任務 1 說明加粗；任務 2 element 的 score 1→0、approved true→false、provenance object 更換與 obsolete 移除；任務 3 同 ID 新增 scope 並追加文字；基本資料協作者儲存格追加文字；任務 4 子清單第一項追加文字。此為刻意製造的研究改動，不是職務分析／JD 品質決策。兩個反例各另有一個實際 `set_node`。

## 執行、檔案與結果

```text
npm ci --ignore-scripts --no-audit --no-fund --cache .npm-cache
node prepare.mjs ../../2026-09-09-frontend-engineer-jd-sample.md
node build.mjs
node verify.mjs
node licenses.mjs
node server.mjs
```

`prepare` 會重新產生本目錄的固定材料；`verify` 是另一個全新 Node 程序，只讀保存的動態材料，重開 headless editor 並重算 diff。`build` 使用 esbuild 的免費原生 binary；初次 sandbox 阻止 spawn（EPERM），重新以獲准的隔離建置執行成功，沒有改用 lifecycle script。上述命令不寫既有 native probe、evidence 或 production。

- `public/materials.json`：乾淨快照、修改時捕捉的 `editor.operations`、批次後值、版本及 r2 source SHA-256。
- `results/ui-node-results.json`：**29 個固定呈現／材料檢查通過，0 個新的驗證失敗；原生 diff 的 2 個已知失敗仍成立。**這不是把原生 diff 改成 29/29 正確，也不是原先 13 案測試的替代分母。
- `results/*-before.html`、`*-after.html`、`*-diff.html`：真正 React Plate 的 SSR 輸出。完整 r2 前後文字符合快照；三欄均有三張合法 table/tbody 與 ul/li 子清單；同 ID 的刪＋增 SSR 均存在。SSR 不足以證明瀏覽器 DOM 或視覺驗收。
- `results/recomputed-native-diff.txt`：以 Node inspect 保留 undefined 的診斷文字，**不是可重開 diff 的正式格式**。實際重開由乾淨快照重算。
- `results/r2-source.md`：比對用的原始樣稿。測試只為本固定原稿移除 Markdown 標記及空白後逐字比對，這是驗證 oracle，不是 importer。

Node v22.12.0 實際執行。server 綁定 `127.0.0.1:4391`；頁面入口 `http://127.0.0.1:4391/`。本子題沒有使用 CUA；主線另驗瀏覽器及清除頁面重開，結果不可由這裡的 Node／SSR 通過推定。

**已確認的呈現限制：未證明所有 Element 欄位在員工視圖可讀。**任務 3 的 scope 只在展開的 JSON／原始操作材料中可見；有紅綠正文不代表全部 metadata 的呈現通過。正式 schema 仍需依必要欄位做有限 renderer 接線及驗收；本輪不因此加通用 metadata diff 或擴大 UI。主線已另外回報實際 DOM、重開及兩反例觀測，會自行保存獨立的 browser 證據。

## 固定依賴及授權（查閱 2026-09-09）

| 實裝套件 | 版本 | 已核對的授權／來源 |
|---|---|---|
| platejs、@platejs/core | 53.3.11 | MIT；官方 npm package 及 LICENSE |
| @platejs/diff | 53.0.0 | package license 欄位空缺；實際 LICENSE：slate-diff 衍生為 Apache-2.0，Plate 修改 Apache-2.0／MIT 雙授權 |
| react、react-dom | 19.2.4 | MIT；官方 npm package |
| esbuild | 0.25.12 | MIT；官方 npm metadata 及 LICENSE.md；僅建置 |
| @esbuild/win32-x64 | 0.25.12 | MIT；官方 package 宣告，binary package 沒另外放 LICENSE；僅建置 |

`results/license-inventory.json` 記錄實際安裝的 **46 項**（44 項宣告 MIT、1 項 Apache-2.0、1 項 diff 另讀實際 LICENSE）、版本及官方 tarball URL；包含鎖定的 transitive dependency。`results/*LICENSE.txt` 保留讀到的正文；不是把全部套件概稱 MIT。官方來源入口：[platejs](https://registry.npmjs.org/platejs/53.3.11)、[diff](https://registry.npmjs.org/@platejs%2fdiff/53.0.0)、[React](https://registry.npmjs.org/react/19.2.4)、[React DOM](https://registry.npmjs.org/react-dom/19.2.4)、[esbuild](https://registry.npmjs.org/esbuild/0.25.12)。沒有付費套件、模型或 Pro 元件。
