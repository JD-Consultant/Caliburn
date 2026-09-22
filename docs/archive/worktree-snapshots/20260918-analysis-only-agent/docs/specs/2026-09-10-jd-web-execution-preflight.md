# JD Task 4：Web 版本與真瀏覽器施工前核對

**主工作單位採用更新（2026-09-10）：**§1–3 與 §4 均已完成[有限獨立審查](evidence/2026-09-10-jd-web-preflight-review.md)，WP-R01 CLOSED。Next16.3.3／工具修補及隔離 Node22.23.2 已寫入 register／Task4.0–4.6；目前 Task3 沿原 runtime 施工，Task4 尚未安裝／驗新版。下文「候選／未採用／Task2」是補證撰寫當時狀態，效力以本更新及 current register 為準，不改寫歷史測試結果。

- 查閱日：2026-09-10（Asia/Taipei）；topic：JD-R002；狀態：有限 G2 補證，交主線納入施工入口，**不是已實作／安全全認證／IME 驗收**。
- 依據：[current register](../current-decisions.md)、[decision process](../decision-process.md)、[核心 Task 4](../plans/2026-09-10-jd-editor-core-implementation.md#task-4同頁手編完整實際差異與-session-history)、[員工旅程](2026-09-10-jd-employee-journey-design.md)。當前唯一施工單位仍為 Task 2。
- 本輪只核 Next／React／Web 測試工具與 browser 驗證接點；未安裝、改鎖、改 schema／plan、啟服務／DB／模型、commit 或修改 production。

## 1. 採用建議與版本證據

**Caliburn mapping：Task 4 不應再新建 Next 16.2.6；建議隔離 Web 使用 `next`／`eslint-config-next` 16.3.3，保留 React／ReactDOM 19.2.4，Vitest 4.1.11。**這是官方已發布修補所需的有限升級；16.2.6→16.3.3 跨 minor，不能稱同 minor patch，也不藉此重選框架。主線須把有限版本修正寫回 register／Task 4 後施工；本稿不自行授權或修改鎖。

| 項目 | 唯讀現況／官方核對 | 建議與界線 |
|---|---|---|
| Next／eslint-config-next | 原 Task 4 與 worktree `apps/web` 為16.2.6。官方2026-08-25安全公告、兩份GHSA均列16.3.3為16線修補版；官方tag package為MIT、Node >=20.9、React peer含 ^19.0.0 | 隔離W用16.3.3並對齊eslint config；不在本輪改既有production apps/web |
| React／react-dom | worktree root與`experiments/jd-editor` lock為19.2.4／MIT。Next16.3.3 peer容許此版 | 保留原生adapter已測19.2.4；不可把client套件版本等同framework內嵌RSC已修補 |
| Vitest | root lock仍4.1.9；Task1隔離lock的`native/node_modules/vitest`已4.1.11／MIT。GHSA-82fw-gwwq-j7x9影響vitest與mocker <4.1.11 | 新W沿4.1.11，確認mocker等同族resolved版本；不從root複製4.1.9或引入5 prerelease |
| jsdom | root lock28.1.0／MIT；Node需求 ^20.19.0 或 ^22.12.0 或 >=24 | 可保留做元件／DOM模擬；Task1 Node22.12滿足版本宣告，這不構成Node本身安全稽核 |
| Testing Library | root lockReact16.3.2、user-event14.6.4，均MIT；官方React套件peer支持React18／19 | 可沿用已知元件測試接法，不將user-event當OS輸入法 |
| Playwright | 已查root lock、隔離JD lock、Web設定及舊UI probe，未見直接安裝的playwright／playwright-core／@playwright/test或專用設定；舊probe verify用SSR／原生editor，不是Playwright E2E | 若要可重跑CDP驗收，需在隔離測試依賴加入runner；已核官方1.61.0／Apache-2.0／Node>=18，僅作可用候選，不宣稱最新或已安裝。亦可用現有browser工具做視覺／鍵鼠驗收，CDP能力必須看工具實際公開API |

**Official fact：**[Next August security release](https://nextjs.org/blog/august-2026-security-release)修補AVIF影像最佳化底層libheif RCE，及Windows上特定Pages＋App Router且未開Cache Components的RCE。[AVIF GHSA](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4)及[Windows GHSA](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36)列修補16.3.3／15.5.24。16.2.6落在套件影響範圍；本案是否滿足各漏洞可利用前提未做攻擊測試，不能因本機用途宣稱不存在，也不能把App-only直接說成Windows漏洞已可利用。本輪所讀官方來源沒有16.2.x對這兩項的修補版，故不推薦虛構16.2 patch。

**Official fact：**[React July GHSA-wx67-qw84-cm4g](https://github.com/react/react/security/advisories/GHSA-wx67-qw84-cm4g)針對`react-server-dom-webpack/parcel/turbopack`，19.2線修補為19.2.8；不是把`react`／`react-dom` client19.2.4列成相同套件。應升級包含修補的Next並核resolved／內嵌RSC，不用獨立override Next compiled RSC。這次未找到要求純client19.2.4升級的相同公開安全依據；不是保證沒有未知問題。

**Official fact：**[Vitest August GHSA](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9)修補可到達dev-server WebSocket時的redirect-mock任意檔案讀取，4.1.11為stable修補。Task1隔離版已符合，root仍舊不代表Task1沒修。此次不是完整transitive audit；jsdom／Testing Library只核精確lock、授權與相容宣告，未宣稱整棵依賴「無漏洞」。

版本／授權primary sources：[Next16.3.3 package](https://raw.githubusercontent.com/vercel/next.js/v16.3.3/packages/next/package.json)、[React19.2.4 package](https://raw.githubusercontent.com/facebook/react/v19.2.4/packages/react/package.json)、[Vitest4.1.11 package](https://raw.githubusercontent.com/vitest-dev/vitest/v4.1.11/packages/vitest/package.json)、[Testing Library16.3.2 package](https://raw.githubusercontent.com/testing-library/react-testing-library/v16.3.2/package.json)、[jsdom28.1.0 README](https://raw.githubusercontent.com/jsdom/jsdom/28.1.0/README.md)、[Playwright1.61.0 package](https://raw.githubusercontent.com/microsoft/playwright/v1.61.0/packages/playwright-core/package.json)與[LICENSE](https://raw.githubusercontent.com/microsoft/playwright/v1.61.0/LICENSE)。Playwright library免費OSS不等於所有分發browser／第三方組件共用Apache授權；此輪無重分發。

最小版本驗證：隔離W建成後核lock內Next／eslint一致、react／react-dom宣告與resolved套件維持19.2.4並與native套件鎖一致、Vitest與mocker修補線。**App Router使用Next內建React canary，不等於套件鎖的React19.2.4**；另記Next compiled React／RSC識別、browser內實際React runtime及browser.version／channel／headed狀態，不override或強迫內建版本等於19.2.4。依據為[Next官方安裝文件](https://nextjs.org/docs/app/getting-started/installation#manual-installation)及[16.3.3內建React package](https://raw.githubusercontent.com/vercel/next.js/v16.3.3/packages/next/src/compiled/react/package.json)。Plate/native相容性由Task4真DOM、編輯、選取、history及保存重開驗收證明，不能用package.json同版替代。執行計畫既有test／typecheck／lint／build及native regression；記錄Node實際版本與resolved清單，針對新增W依賴作audit並逐项對照官方GHSA。若發現較新已修補風險只補對應有限patch，不更新整倉。

## 2. 真 browser 的可行路徑與不能冒稱的範圍

**Official fact：**Playwright [CDPSession](https://playwright.dev/docs/api/class-cdpsession)可用`context.newCDPSession(page)`及`session.send(...)`調Chromium CDP。CDP [Input](https://chromedevtools.github.io/devtools-protocol/tot/Input/)提供experimental `Input.imeSetComposition`，含候選文字、selectionStart／selectionEnd與可選replacement range；空字串取消composition。此路徑限Chromium，protocol非跨browser穩定保證。

官方Input說明提到`imeCommitComposition`，但同頁沒有該可呼叫方法，**不得照抄成存在的API**。核對[Chromium官方InputHandler](https://raw.githubusercontent.com/chromium/chromium/main/content/browser/devtools/protocol/input_handler.cc)：`ImeSetComposition`送至widget input handler的同名方法；`InsertText`送至`ImeCommitText`。因此候選→更新→`Input.insertText`提交可作原生輸入層composition接線測試。這是從官方source推導的Caliburn測法；應以實際browser事件／內容驗證，不把CDP成功回應當編輯器通過。

| 測法 | 能證明 | 不能證明 |
|---|---|---|
| jsdom／dispatchEvent(new CompositionEvent) | handler與狀態分支 | 原生編輯、composition文字替換、OS IME；不計真IME PASS |
| Playwright fill／keyboard.insertText／type繁中 | 最終Unicode文字輸入 | 候選更新與完整composition生命週期；官方[Keyboard](https://playwright.dev/docs/api/class-keyboard)明列insertText不產生keydown/up/keypress，非US字元type也可能只有input |
| headed Chromium＋CDP composition | browser input handler→DOM composition／beforeinput／input→Plate selection/value／保存接線 | Windows注音或倉頡候選視窗、按鍵轉候選、系統詞庫／重轉換、實體鍵盤、特定OS IME bug |
| 真人在此機器／實際App browser使用Windows繁中IME | OS輸入法、候選選字、取消／提交與實際產品整段互動 | 未測其他OS／IME；不能推廣為所有輸入法全通過 |

既有CUA browser可提供畫面與已公開的鍵鼠操作，但目前列出的工具入口沒有公開raw CDP／OS原生IME控制；不得假設它支援未列API。要走CDP用明確runner；要驗OS候選由真人操作。若只跑headless Chromium，能記引擎證據，但核心Task4現行停止線要求真DOM／人工IME，仍不得將整列勾完成。Playwright1.61.0官方[browsers.json](https://raw.githubusercontent.com/microsoft/playwright/v1.61.0/packages/playwright-core/browsers.json)對應Chromium149.0.7827.55／revision1228；實測須寫實際browser.version及channel，不冒稱等同App內嵌版本。

## 3. 最小驗證材料與退出條件

以下是待執行步驟，全部沿既定固定provider／專用DB，不發付費模型。

1. **記錄環境及基線。** 用active v2 r2，列1基本資料表、8Task、5K／5S；記錄commit、lock、browser版本、headed/headless、Windows與IME種類。留初始exact value、ID／refs、畫面與AX；舊v1三表probe只能作歷史方法參考。
2. **原生composition最小例。** 點入真正Plate contenteditable，唯讀監聽compositionstart/update/end、beforeinput/input之data、inputType、isComposing及selection。經CDP送`imeSetComposition({text:'職',selectionStart:1,selectionEnd:1})`，更新為`職務`與範圍2／2，再`insertText({text:'職務'})`；另跑空字串取消。assert沒有重複字／漏字、選區可繼續輸入；保存與新頁重開exact value一致。不得以直接setValue或dispatchEvent替代輸入層。若實際events不同，保存證據並診斷，不硬編事件數求綠燈。
3. **真selection。** 透過滑鼠或Shift＋方向鍵選同block第二次出現的相同繁中文字；讀DOM與Plate selection，經既定dirty-save→capture→POST runs的actual request驗base與範圍。只改第二處；跨block／選取改變／stale應拒絕且留chat文字。不預造selection ref。
4. **剪貼簿與history。** 在測試context以官方[grantPermissions](https://playwright.dev/docs/api/class-browsercontext#browser-context-grant-permissions)按精確localhost origin授clipboard讀寫；走Ctrl+C／Ctrl+V的browser剪貼路徑，查paste後表格／清單／marks／metadata與新ID，保存重開核對。不要把合成ClipboardEvent當OS clipboard。固定AI operations batch→人工改字→Ctrl+Z一次只退人工、再一次退AI→redo順序與ID正確；查看歷史不可污染stack。跨程式Word／Excel HTML貼上與Windows剪貼簿格式仍列真人未覆蓋。
5. **實際差異。** 用同ID刪／增、空mark、表格span／border、K／S改連線與共享item固定材料，三種renderer都可讀；snapshot無operations時明示高亮限制，兩版各用本版引用者聯集／名稱。畫面／AX＋exact before/after＋actual save/read結果聯合斷言，不只截圖或computeDiff空值。
6. **真人IME小卡。** 在實際App browser用Windows繁中IME打「職務分析」，選不同候選再修正、Escape取消、Enter提交後另一次Enter換段；在清單與表格各一次，接續undo／redo／保存／關頁重開。記IME名稱、操作、畫面、事件與saved value；未執行就寫`OS IME NOT RUN`，保留Task4整列未驗，不以CDP代填。此與後續3名員工完整可用性驗收分開。

**停止研究／下一gate：**已有官方已知修補與可行Chromium原生input驗證路徑，停止廣搜。主線處理Next版本有限修正與W測試依賴後，依Task4執行；若真測顯示profile／history／selection無法達標，保留反例回既有停止線，不自造diff／history引擎。當前沒有執行任何上述browser／IME／保存驗收。

## 4. Node 22 支援與安全修補補核（2026-09-10）

**狀態：有限官方補證／候選，未採用、未安裝、未切換runtime、未重跑Task1或其他測試。**本節僅延伸§1的Node engine核對；先前「22.12.0符合宣告」仍成立，但不能推成「22.12.0已包含現行安全修補」。不改§1–3已review文字，不調整全機Node、Python或其他npm依賴。

**Official fact：Node 22大版仍受支援。**查閱日官方[Release Working Group](https://raw.githubusercontent.com/nodejs/Release/main/README.md)列22.x／Jod為Maintenance LTS，2025-10-21進入維護，預定2027-04-30 EOL；維護期仍提供重大bug與安全修補。日期可由官方調整。[release schedule JSON](https://raw.githubusercontent.com/nodejs/Release/main/schedule.json)為機讀來源。這是22線的維護狀態，並非每個歷史22.x binary都持續就地修補，也非要求此案改24或26。

**Official fact：已有直接反證，22.12.0不能當已修補基線。**官方[2025-01-21安全公告](https://nodejs.org/en/blog/vulnerability/january-2025-security-releases)列Windows `path.join`路徑／磁碟名稱處理漏洞CVE-2025-23084，並連至[22.13.1 security release](https://nodejs.org/en/blog/release/v22.13.1)的修補；該版另修HTTP/2記憶體洩漏、Permission Model與Undici問題。原22.12.0早於此修補。這足以否定「符合jsdom engine便可視為安全更新完整」；未做Caliburn漏洞利用測試，不聲稱每個漏洞在本案都可觸發。

**Caliburn mapping：推薦隔離runtime精確候選Node 22.23.2。**官方[2026-07-29／22.23.2 LTS release](https://nodejs.org/en/blog/release/v22.23.2)明示security release；查閱當下官方[latest-v22.x SHASUMS](https://nodejs.org/download/release/latest-v22.x/SHASUMS256.txt)也指向22.23.2。它保留22大版，跨22.12→22.23 minor，不是22.12同minor patch。官方[July security公告](https://nodejs.org/en/blog/vulnerability/july-2026-security-releases)列22線HTTP/2、HTTPS identity/session、DNS、zlib及permission等修補；例如CVE-2026-58040補HTTPS session重用的hostname驗證、CVE-2026-58042補DNS多A-record造成程序中止。本節不逐項宣稱22.12.0具有所有七月漏洞，因各問題可能有不同引入版本；推薦的是官方目前22線已發布修補組合。

**授權與供應來源：**[v22.23.2 LICENSE](https://raw.githubusercontent.com/nodejs/node/v22.23.2/LICENSE)的Node本體為MIT條款，附帶元件各有列出的授權，不能將整個分發包粗略說成所有檔案只有MIT。導入時由官方22.23.2 release下載對應Windows架構的portable binary／archive，核SHA256及官方簽署SHASUMS；選專案隔離目錄與明確executable path，不替換全機PATH、全機安裝或其他task runtime。本輪只讀官方網頁，未下載binary或檢驗現有binary簽章。

**導入後必要回歸（待主線安排，現在NOT RUN）：**先保存原22.12.0基線與新runtime路徑／`process.version`、architecture、`process.versions`，確認Node worker／npm scripts／Python子程序橋接都實際使用22.23.2，不能只看目前terminal的`node --version`。在同一鎖檔下重跑JD contract生成bytes／check-codegen、native原生七命令與selection／copy／history回歸及build；重跑已存在的Python→Node engine bridge／子程序錯誤與UTF-8序列化測試，若涉及實際保存則沿既有專用PG recovery集合，不新建測試引擎。W建成後跑原Task4 test／typecheck／lint／build與browser smoke；原Task1完成證據保持原runtime日期，不改寫為已在新版通過。任何行為差異保留實況，只診斷Node變動接點，不更新整棵依賴求綠燈。

**停止線／限制：**支援線、舊binary缺修補的官方反證與同22線精確stable候選已清楚，停止擴搜；這不是整機或全依賴安全認證。後續若官方22線再發安全版，再定點核對；此次不延伸Python／所有npm／全機版本管理。
