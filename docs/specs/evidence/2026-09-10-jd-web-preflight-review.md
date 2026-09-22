# JD Web preflight 獨立審查

- 日期：2026-09-10（Asia/Taipei）；reviewer：jd_web_preflight_review。
- Topic ID：JD-R002；current stage：隔離 G7／Task 2 施工中，本審查只是 Task 4 有限 G2 補證。
- 已讀：root `docs/current-decisions.md`、`docs/decision-process.md`、`docs/specs/2026-09-10-jd-web-execution-preflight.md`、核心計畫 Task 4。
- 唯一問題：preflight 能否供主線更新 Task 4 的版本與真 browser 驗證計畫。
- 有效邊界：同頁 Plate／active v2／同 PG／既有六切片；React、ReactDOM 套件鎖保留 19.2.4，Vitest 保留 4.1.11；不改 production authority、不提前啟動 Task 4、不把 CDP 當 Windows 真人 IME。

**結論：有限 PASS-with-wording-fix。** 官方修補版本與 CDP 可呼叫接點有直接證據；可直接更新 Task 4 的有限計畫，並同時補正下列 WP-R01。沒有其他會阻止這次計畫更新的 finding。這不是安裝後相容性、安全全認證、真 DOM 或 IME 驗收通過。

## WP-R01：區分依賴套件版本與 App Router 實際 React runtime

- Severity：P2（有限驗收文字修正，不要求重選框架或升級 React client 套件）。
- 位置：preflight §1 第 9／14／22 行的 React 表述與第 28 行「React單份且與native一致」；核心計畫 Task 4.2 第 198 行，以及 Task 4.6 第 232 行的版本／相容性證據要求。行號為本次 root 讀取位置。
- 官方契約：[Next 安裝文件 Manual installation](https://nextjs.org/docs/app/getting-started/installation#manual-installation)明示 App Router 使用內建 React canary，package.json 仍宣告 react/react-dom 供 tooling／生態相容；Pages Router 才使用 package.json 的 React 版本。16.3.3 tag 也保留獨立 [react-builtin package](https://raw.githubusercontent.com/vercel/next.js/v16.3.3/packages/next/src/compiled/react/package.json)。
- 影響：若把 lock 中單份 19.2.4 當成 App Router 實際 runtime 同版，會把 native 測試環境的證據擴大到未測的 Web 環境，或誤判 Next 官方內建副本為必須去除的重複 React。
- 要求：保留 react/react-dom **宣告與 resolved 套件** 19.2.4 且與 native 的套件鎖一致；另外記錄 Next 實際 compiled React／RSC 識別及 browser 內 React runtime 版本、browser.version／channel／headed 狀態。不可獨立 override Next compiled React／RSC，也不可強制其版本字串等於 19.2.4。Plate/native 在 App Router 的相容性由 Task 4 真 DOM／編輯／選取／history／保存重開驗收證明，不能由 package.json 版本相同替代。
- 狀態：OPEN，主線可在納入計畫時直接補文字；補後供窄複核，不需要重新廣搜或重問產品方向。

## 已核實的主要依據與限制

| 主張 | 審查結果 |
|---|---|
| Next 16.2.6 → 16.3.3 | PASS。[2026-08-25 官方公告](https://nextjs.org/blog/august-2026-security-release)、[AVIF advisory](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4)、[Windows advisory](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36)直接列 16.3.3／15.5.24 修補版。16.2.6 落於版本範圍；AVIF 最佳化及 Windows Pages＋App Router／未開 Cache Components 等可利用前提仍須分開。preflight 已保留此前提，沒有把本機 App-only 宣稱已可利用。跨 minor 描述正確；本審查不把 16.3.3 稱最新版本。 |
| eslint-config-next 同升 16.3.3 | PASS，屬版本對齊的 Caliburn mapping，不能說 eslint config 自身修補上述 RCE。[官方 tag package](https://raw.githubusercontent.com/vercel/next.js/v16.3.3/packages/eslint-config-next/package.json)為 16.3.3／MIT，依賴同版 Next ESLint plugin、peer 要求 ESLint >=9。現有 lock 的 ESLint 9.39.4 滿足宣告；仍須執行獨立 lint，不能以 build 代替。 |
| 保留 React／ReactDOM 套件 19.2.4 | PASS，須套用 WP-R01。[Next 16.3.3 package](https://raw.githubusercontent.com/vercel/next.js/v16.3.3/packages/next/package.json)的 peer 包含 ^19.0.0，Node >=20.9。[React July advisory](https://github.com/react/react/security/advisories/GHSA-wx67-qw84-cm4g)列的是 react-server-dom-webpack／parcel／turbopack，19.2 修補線是 19.2.8，沒有把 react/react-dom client 套件列為同一受影響套件。peer 可安裝不等於 App Router／Plate runtime 驗收，也不能由 peer 推論內建 RSC 已修補。實際 compiled 內容留待安裝後核對。 |
| Vitest／mocker 4.1.11 | PASS。[官方 advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9)列 stable 修補 4.1.11；保留既有隔離修補線合理。精確範圍為 >=2.1.0 且 <4.1.11，另有 5 prerelease 範圍。非阻擋補充：未驗證 token 的可達 WebSocket 路徑是 public mockerPlugin／standalone interceptorPlugin；Vitest 自己 browser mode 是 token RPC，不能簡化為所有 localhost Vitest 都可遠端無認證讀檔。 |
| Playwright 1.61.0 候選 | PASS。[官方 package](https://raw.githubusercontent.com/microsoft/playwright/v1.61.0/packages/playwright-core/package.json)為 1.61.0、Apache-2.0、Node >=18；[browsers.json](https://raw.githubusercontent.com/microsoft/playwright/v1.61.0/packages/playwright-core/browsers.json)記 Chromium 149.0.7827.55／revision 1228。這是候選及版本對照，未安裝、未宣稱最新或等於 App browser。 |
| CDP composition 提交路徑 | PASS。[Playwright CDPSession](https://playwright.dev/docs/api/class-cdpsession)公開 newCDPSession／send，[BrowserContext](https://playwright.dev/docs/api/class-browsercontext#browser-context-new-cdp-session)限定 Chromium。CDP [Input](https://chromedevtools.github.io/devtools-protocol/tot/Input/)公開 experimental imeSetComposition／insertText，沒有可呼叫 imeCommitComposition；preflight 明確避開該文件殘留名稱。除了 main，審查另核候選 browser 相同版本的 [Chromium 149.0.7827.55 InputHandler](https://raw.githubusercontent.com/chromium/chromium/149.0.7827.55/content/browser/devtools/protocol/input_handler.cc)：InsertText 呼叫 ImeCommitText，ImeSetComposition 呼叫 widget input handler 的同名接點，支持候選→更新→insertText 的有限測法。仍須 actual DOM events／value／selection／saved value 證明，不能只看 CDP 回應成功。 |
| IME／clipboard 證據分層 | PASS。[Keyboard 官方文件](https://playwright.dev/docs/api/class-keyboard)支持 insertText 及非 US 字元 type 不等同完整按鍵／composition；[grantPermissions](https://playwright.dev/docs/api/class-browsercontext#browser-context-grant-permissions)支持 origin 限定與 clipboard 權限，且提醒 browser／版本差異。CDP 不控制 Windows 注音／倉頡候選視窗、系統詞庫或實體按鍵；headless／jsdom 不能填滿 Task 4 人工 IME 列。preflight 的真人小卡與 OS IME NOT RUN 規則正確。 |

其他有限查核：[jsdom 28.1.0 package](https://raw.githubusercontent.com/jsdom/jsdom/v28.1.0/package.json)的 Node 宣告為 ^20.19.0／^22.12.0／>=24；[Testing Library tag package](https://raw.githubusercontent.com/testing-library/react-testing-library/v16.3.2/package.json)為 MIT 且 peer 支援 React 18／19。這些只是宣告相容，沒有把 jsdom／user-event 當真瀏覽器或 OS 輸入法。

本機唯讀 lock 核對：root 與隔離 checkout 的 root lock 均是 Next／eslint-config-next 16.2.6、React／ReactDOM 19.2.4、Vitest／mocker 4.1.9；隔離 `experiments/jd-editor/package-lock.json` 則在 native 下解析 Vitest／mocker 4.1.11，React／ReactDOM 19.2.4。查到的三份 lock 沒有 Playwright 系列 resolved 條目。首次 PowerShell JSON 讀取遇空 key 限制，改用 AsHashtable 後完成；未改 lock。

## 可直接納入 Task 4 的範圍

1. 4.2 改為 next／eslint-config-next 16.3.3，react／react-dom 宣告与套件 resolved 固定 19.2.4，Vitest／mocker 維持 4.1.11；加入 WP-R01 的 runtime 證據規則，不擴整倉升級。
2. 引用 preflight 的 headed Chromium／CDP 測法及真人 IME 小卡；若選 runner，限定為隔離測試依賴，記實際 browser／channel／headless 狀態。
3. 4.6 保留 test／typecheck／lint／build／native regression 與真 DOM 驗收；分列 CDP engine evidence 和 Windows 真人 IME evidence。尚未真人執行時，不得把 Task 4 整列完成。

Closure：研究證據足夠，停止廣搜；WP-R01 修正後可供 Task 4 使用。下一 gate 仍按主線完成 Task 2 與 Task 3，再到 Task 4 實際安裝／lock／runtime／DOM 驗證。新官方反證、實際 compiled 風險、Plate 真 DOM 失敗或 authority 衝突才重開。此 reviewer 只新增本報告，沒有施工、安裝、啟服務、DB／模型呼叫、提交或外部發布，也没有更新 register／preflight／plan。

## 2026-09-10 WP-R01 窄複核 closure

**目前 verdict：有限 PASS；WP-R01 CLOSED。** 上述 OPEN 與 PASS-with-wording-fix 保留為初次審查沿革，以本次 closure 為最新狀態。

只複讀 root preflight §1 第 28 行、核心計畫 Tech Stack 第 15 行／Task 4.2 第 198 行／Task 4.6 第 232 行，沒有重做官方廣搜或完整 review。文字已分開 react／react-dom 宣告與 resolved 套件 19.2.4、Next compiled React／RSC 識別和 browser 實際 React runtime；明列不 override、不強迫內建版本等於 19.2.4，以及 Plate/native 相容性由真 DOM／編輯／選取／history／保存重開驗收證明，符合 WP-R01 全部要求。

Next／eslint-config-next 16.3.3、Vitest／mocker 4.1.11 與 browser 環境證據已納入計畫；CDP imeSetComposition→insertText 和 Windows 真人 IME 分列，OS 候選未操作仍記 OS IME NOT RUN。沒有把此文字複核擴大成套件安裝、runtime、真 DOM 或真人驗收通過。

可供主線同步 durable evidence／current register；本次僅追加這份 scratch 報告，沒有修改其他檔案。

## 2026-09-10 Node §4 限定 review

**Verdict：有限 PASS，無新增阻擋 finding。** 本輪只核 root preflight §4（第 58–72 行）的新 runtime 主張及其導入驗證範圍，不重做 WP-R01。當前 register 已進 Task 3；Task 3 沿舊 runtime，建議僅在 Task 4 前明確切換隔離環境。可把 Node 22.23.2 納入 Task 4 的有限升級計畫；不能藉本報告稱已安裝、已驗安全或沿用 Task 1 舊測試作新 runtime 通過證據。

| 核對項目 | 官方證據與判斷 |
|---|---|
| 支援狀態 | [Node Release WG](https://raw.githubusercontent.com/nodejs/Release/main/README.md)與[schedule.json](https://raw.githubusercontent.com/nodejs/Release/main/schedule.json)一致：22.x／Jod 為 Maintenance LTS，2025-10-21 起維護，預定 2027-04-30 EOL；maintenance 包含關鍵 bug 與安全修補，日期可調整。支持保留 22 major；不代表 22.12.0 binary 已包含後續修補。 |
| 舊版缺修補的直接反證 | [2025-01-21 安全公告](https://nodejs.org/en/blog/vulnerability/january-2025-security-releases)明列 CVE-2025-23084 為 Windows drive-name／path.join 問題，連往 [22.13.1](https://nodejs.org/en/blog/release/v22.13.1)修補；該 release 明列 Windows normalize 路徑修正、HTTP/2、Permission Model 與 Undici 更新。22.12.0 早於修補，足以否定「符合 engine 宣告即安全修補完整」，不需要假稱已重現 Caliburn 漏洞。 |
| 精確候選 | [22.23.2 release](https://nodejs.org/en/blog/release/v22.23.2)日期為 2026-07-29，標示 LTS 與 security release；本次讀取 [latest-v22.x SHASUMS](https://nodejs.org/download/release/latest-v22.x/SHASUMS256.txt)的 portable Windows archive 名称亦為 22.23.2。[July 安全公告](https://nodejs.org/en/blog/vulnerability/july-2026-security-releases)支持文中的 HTTPS session hostname 驗證、DNS 多 A record 中止等例子。22.12→22.23 是同 major 跨 minor，preflight 分類正確；沒有把所有 July 漏洞都推給 22.12.0。 |
| 授權與取得 | [22.23.2 LICENSE](https://raw.githubusercontent.com/nodejs/node/v22.23.2/LICENSE)支持 Node 本體 MIT、附帶元件分列授權。官方 release 提供 Windows 各架構 binary／archive 與 signed SHASUMS；[官方 README 的 Verifying binaries](https://raw.githubusercontent.com/nodejs/node/v22.23.2/README.md)說明以 release keyring 驗 PGP 簽章後核 SHA256。§4 的隔離下載、校驗、明確 executable 路徑可用；本次只是核文件，沒有下載或檢驗 binary。 |

**必要回歸範圍足夠，屬 Caliburn mapping。** 保留原鎖後先重跑 contract 生成 bytes／check-codegen、native commands／selection／copy／history／build，再跑 Python→Node bridge 的真子程序、錯誤／停止／UTF-8 路徑；涉及保存時沿既有專用 PG recovery 集合。W 建成後依 Task 4 跑 test／typecheck／lint／build 與 browser smoke；WP-R01 的 compiled React／實際 browser runtime 及完整 DOM／IME 停止線繼續有效。這些是本案受 Node 變動影響的驗收接點，不冒稱 Node 官方規定的測試清單。

唯讀接點核對：現行 `experiments/analysis-agent/src/analysis_agent/jd_engine.py` 在建構時以 `shutil.which('node')` 保存 `self.node`，Popen 再使用該路徑；native `tests/bridge.test.ts` 用 `process.execPath` 啟新程序。因此 Task 4 導入需在限定程序／啟動環境中解析新 Node 並重建 API／JdEngine，記錄實際 `self.node`／子程序 `process.execPath`／`process.version`，確認 npm scripts 和 worker 也走新 runtime。僅更改另一個 terminal 的 node 版本不足以證明 Python bridge 已切換。此為 §4 既有「實際執行路徑」要求的具體化，不要求更動全機 PATH、Task 3 進行中的程序或新增版本管理框架。

Closure：§4 可供 Task 4 前隔離 runtime 升級使用，研究可停止；導入時保留旧 runtime 證據並產生新的回歸結果。未切換任何 runtime、未跑測試、未改 React／Plate／Memory／全機 Node，僅追加本報告。主線負責同步正式計畫／register；新官方 22 線安全版或實際回歸失敗才定點重開。
