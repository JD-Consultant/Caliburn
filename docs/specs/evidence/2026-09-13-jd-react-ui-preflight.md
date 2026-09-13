# JD 六章管理畫面：React／MUI 精確接線前置

- 查閱日：2026-09-13；Topic：JD-R002／RS-3。
- 狀態：有界官方文件、公開套件資料與必要發行版原碼核對；**未安裝、未改 package／lock、未建置、未做真瀏覽器或模型驗證**。這是可安裝驗證的候選組合，不是完整 UI 已通過。
- 依據：[目前決策](../../current-decisions.md)、[框架選型](../2026-09-13-jd-app-stack-selection.md)、[完整管理旅程](../2026-09-13-jd-complete-app-journey-design.md)。保留六章、一般文字與換行、完整任務整組建立、共用 K/S、AI 直接保存及既有後端權責，不因元件增加必填或改成文章編輯器。

## 1. 可採版本組合與證據

**沿已選 Next App Router／React／TypeScript，先驗 MUI Material UI 免費 Core＋Emotion。**以下皆非 alpha／beta／RC 套件版本；Next 內部 React 執行通道與實際建置相容性另列，不能寫成所有內部依賴皆穩定通道。

| 項目 | 精確候選 | 官方事實與來源 |
|---|---|---|
| Node.js | **現有 24.19.0；本輪採用** | [官方發行頁](https://nodejs.org/en/about/previous-releases)列 24.21.0 為 Latest LTS，26.8.2 是 Current。本輪主代理已核現有 Node 24.19.0／npm 10.9.0，符合 Next `>=20.9.0` 與其他 peer；沿現有受支援 24.x runtime，不為本切片升級 bundled Node。Node 20 已 EOL，不用最低門檻代替受支援版本。 |
| Next.js | **16.3.5** | [公開 registry manifest](https://registry.npmjs.org/next/latest)：MIT、Node `>=20.9.0`、React／DOM peer 包含 `^19.0.0`；[官方支援政策](https://nextjs.org/support-policy)的 16.x 為 Active LTS。安裝時鎖精確值，不持續追 `latest`。 |
| React／react-dom | **19.3.0／19.3.0** | [React registry](https://registry.npmjs.org/react/latest)、[DOM 發行版本](https://www.npmjs.com/package/react-dom?activeTab=versions)為正式發布，MIT；兩者成對。 |
| TypeScript | **7.0.2** | [registry manifest](https://registry.npmjs.org/typescript/latest)：latest、Apache-2.0、Node `>=16.20.0`；不可只用舊文檔的 TypeScript 最低版本推定完整相容。 |
| `@mui/material` | **9.4.0** | [官方安裝頁](https://mui.com/material-ui/getting-started/installation/)及[固定 tag manifest](https://raw.githubusercontent.com/mui/material-ui/v9.4.0/packages/mui-material/package.json)：MIT；React／DOM／React types 支援 19.x，Emotion react `^11.5.0`、styled `^11.3.0`，Node `>=14`。 |
| `@mui/material-nextjs` | **9.4.0** | [固定 tag manifest](https://raw.githubusercontent.com/mui/material-ui/v9.4.0/packages/mui-material-nextjs/package.json)：MIT；Next peer 包含 `^16.0.0`、React 19.x；Emotion cache `^11.11.0`、react `^11.11.4`。 |
| Emotion react／cache／styled | **11.14.0／11.14.0／11.14.1** | MUI 上述 adapter tag 的直接開發組合列 react／cache 11.14.0；[Emotion react manifest](https://raw.githubusercontent.com/emotion-js/emotion/main/packages/react/package.json)與[styled 發行頁](https://www.npmjs.com/package/%40emotion/styled)相符、MIT；React peer `>=16.8.0`。這些精確值落在 MUI 的 peer 範圍內，仍須核實安裝解析。 |
| `@types/react`／`@types/react-dom` | **19.3.0／19.3.0** | [React types 發行表](https://www.npmjs.com/package/%40types/react?activeTab=versions)、[DOM types 發行表](https://www.npmjs.com/package/%40types/react-dom?activeTab=versions)均有正式 19.3.0；[DOM types 原碼](https://raw.githubusercontent.com/DefinitelyTyped/DefinitelyTyped/master/types/react-dom/package.json)peer 是 `@types/react ^19.3.0`。MUI types peer 接受 19.x；MIT。 |
| `@types/node` | **24.13.4** | 主代理於本輪以指定 Node 24.19.0／npm 10.9.0 查官方 registry，確認 24.x 最新已發布 patch 為 24.13.4 並採用。[DefinitelyTyped v24 原碼](https://raw.githubusercontent.com/DefinitelyTyped/DefinitelyTyped/master/types/node/v24/package.json)的 `24.13.9999` 是來源占位，不能當 npm 發布版；此處以實際 registry 結果補齊。 |
| Ajv／ajv-formats | **8.20.0／3.0.1** | [Ajv 正式版本表](https://www.npmjs.com/package/ajv?activeTab=versions)、[formats 正式版本表](https://www.npmjs.com/package/ajv-formats?activeTab=versions)：兩者 MIT；[formats 固定 tag manifest](https://raw.githubusercontent.com/ajv-validator/ajv-formats/v3.0.1/package.json)支援 Ajv `^8.0.0`。 |

本輪 shell 的公開 registry 請求被環境拒絕；部分 scoped registry／npm 頁面也無法由瀏覽工具取得，因此改以官方發行 tag 和可讀發行頁交叉核對。未輸出或讀取私人 npm 設定，未用 `--legacy-peer-deps` 掩蓋相依問題。完整轉依賴、Windows SWC／TypeScript native binary 與 lock integrity 由下一步實際安裝記錄核定。

## 2. Next／MUI 與型別接線

使用 `@mui/material-nextjs/v16-appRouter` 的 `AppRouterCacheProvider`。官方文件示例仍寫 v15，但[9.4.0 的 v16 入口](https://raw.githubusercontent.com/mui/material-ui/v9.4.0/packages/mui-material-nextjs/src/v16-appRouter/index.ts)確實存在，並重用官方 v13 adapter；這不等於安裝舊 Next。在 root layout 的 body 內承接 ThemeProvider 與互動子樹，讓串流 SSR 的 Emotion CSS 正確收集到 head；所需 cache 套件已列在上表。[官方 Next 接合](https://mui.com/material-ui/integrations/nextjs/)

表單、組字狀態、DOM ref 與事件放 Client Component；Server Component 不另作 JD 寫入 authority。Next 16 的 MUI `component={Link}` 若跨 Client 邊界，沿官方的 client wrapper；使用 `useSearchParams` 的子樹以 Suspense 承接。使用既有本機 Next 程序路線，不用建置時未知的文件 UUID 強做 static export。字型採本機字型堆疊，不照範例增加 Google Fonts 請求。

TypeScript 7 已改變 compiler API，這是本次唯一需追 Next 原碼的相依缺口。[Next 16.3.5 config](https://raw.githubusercontent.com/vercel/next.js/v16.3.5/packages/next/src/server/config-shared.ts)的 `experimental.useTypeScriptCli` 預設為 true；[CLI 接點](https://raw.githubusercontent.com/vercel/next.js/v16.3.5/packages/next/src/lib/typescript/runTypeScriptCli.ts)明確處理 TypeScript 7 的入口。**可先驗 7.0.2，不必預先降版；也不宣稱 experimental 名稱已成永久穩定 API。**保持預設 CLI 路徑，不關閉 build 型別檢查來製造通過。App Router 仍有 Next 內含的 React canary 執行層，外部 React 套件正式發布與此是兩件事。[Next 安裝責任](https://nextjs.org/docs/app/getting-started/installation)

非 JSX 的純資料／保存協調測試可用 Node 原生 `node:test`；原生 TypeScript stripping 不代替 `tsc`，也不承接 TSX 渲染。React 元件、hydration、焦點及 IME 以真瀏覽器驗證。[Node TypeScript 文件](https://nodejs.org/api/typescript.html)

## 3. 免費元件、文字與精確選區

所需表單／列表／展開／確認／狀態可由 Material UI Core 的 TextField、List、Card、Checkbox、Autocomplete、Accordion、Dialog、Alert、Snackbar 等組合；不依賴 Data Grid Pro／Premium、AI 商業功能、付費模板或雲端服務。[MUI 授權頁](https://mui.com/legal/)明分 MIT Core 與商業 X。MUI 實作 Google 的 Material Design，不是 Google 自家 React 框架；本稿沒有新增「所有大廠都用」的部署宣稱。

官方 TextField 的 `multiline` 會渲染 textarea；用 `inputRef` 取得實際輸入節點，`slotProps.htmlInput` 放原生元素參數與事件，不把包裝元件當 textarea。保留明確 label、helperText、id，文字無需 rich text tree。[TextField API](https://mui.com/material-ui/api/text-field/)

React 支援 `onCompositionStart`／`onCompositionUpdate`／`onCompositionEnd`、`onSelect` 與原生事件入口；controlled textarea 必須在 onChange 同步更新顯示值。**本案接合：**顯示值即時更新，自動保存另行排程；組字尚未結束時不把候選文字或 Enter 誤當完成操作，組字結束後再依最後顯示值安排保存；晚到回覆不能覆蓋較新的本地輸入。不能因為支援事件 props 就宣稱繁中 IME 已驗收。[React 共用事件](https://react.dev/reference/react-dom/components/common)、[controlled textarea](https://react.dev/reference/react-dom/components/textarea)

選區以該 textarea 的 value、selectionStart／selectionEnd／selectionDirection 取得，不從重複文字內容搜尋位置。HTML 的文字選區以字串 code units 計算；emoji、換行及跨語言索引必須在 App 的既有選區契約邊界核清，不能直接把 DOM offset 當 Python 字元位置。瀏覽器觀察值不是可寫 authority；送模型仍是 App-issued `selection_ref`，本前置不新增 issuer 或通用定位規則。[HTML 文字選區規範](https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#textFieldSelection)

## 4. 既有 JSON Schema 的瀏覽器驗證

使用 `Ajv2020`（`ajv/dist/2020.js`）與 `addFormats` 載入既有 draft 2020-12 schema；預設 Ajv export 是 draft-07，不能拿同一個 instance 混用不相容 draft。[Ajv 官方 JSON Schema 說明](https://ajv.js.org/json-schema.html#draft-2020-12-breaking)

只將 repo 已有 schema 及固定外部 `$id`／`$ref` 關係註冊給 Ajv，不從 HTTP response 取得或遠端下載 schema，不手寫另一份 DTO 或自製 validator。驗證時保留原資料：`coerceTypes: false`、`useDefaults: false`、`removeAdditional: false`；無效回應不得顯示成已保存。型別檢查與 runtime schema 驗證各守其責任，瀏覽器不重算 domain invariant。[Ajv 修改資料選項](https://ajv.js.org/guide/modifying-data.html)

先在純 Node 測試實際 compile 所需 SSOT 根與跨檔 refs。若日後採禁止動態程式碼的 CSP，可沿 Ajv 官方 standalone 產生驗證函式；不是先加入自製 schema generator。[Ajv standalone](https://ajv.js.org/standalone.html)

## 5. 固定的有限驗證及停止條件

| 驗證 | 必須看見的結果；目前均未在本稿執行 |
|---|---|
| 安裝與 build | 以已補定的 Node 24 types patch 建立精確 lock、無 peer 強制跳過；TypeScript 7 CLI＋Next production build 通過，v16 adapter 可 import，沒有外部字型必要請求。 |
| SSOT response | 真正八份 schema 的所需 root／refs 可編譯；合法回應通過，錯 bool（0／1）、缺欄／多欄、錯 dataset／非法結果組合按既有契約拒絕，不自動修資料。 |
| 新文件與刷新 | 執行時建立的文件可開、重新載入與直接貼網址可到同文件；SSR／hydration 無錯誤，MUI 樣式／label／焦點保持。 |
| 真繁中 IME | Windows 繁中輸入法輸入與選字、Enter 確認、換行、取消組字、貼上 emoji；組字候選不發布、最終文字不漏，不能以 dispatch 合成 composition 事件冒稱實際 IME。 |
| 保存中續打 | 延遲與倒序回覆時仍保留本地新字；穩定 row key／元件位置不令 textarea 重掛、跳 caret、失去選區。保存狀態以既有結果／查回為準。 |
| 精確選區 | `修正🙂\n同字／同字` 只選第二段同字；正反向選取、跨行、emoji 邊界與重繪後位置可核對，不以搜尋首個同字替代。 |
| 管理操作 | 完整新增任務＋多成果／要求＋共用 K/S 只按既定整組操作完成；一般欄位保存、排序／刪除與未知結果恢復走同一後端，六章內容不因元件遺漏。 |

套件能力、peer 與版本已足以進入這組有限驗證，停止品牌比較。若失敗，先以具體 build／事件／選區反例定位接合；只有候選無法承接既定效果才重開元件選型。AI 回合、來源 owner、實際選區 issuer、完整真人驗收仍按各責任切片，不由本份 UI 前置代稱完成。
