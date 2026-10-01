# Task4 implementation freeze report — 2026-09-10

Task4 的隔離 API／同頁 Web 工程已完成並凍結，交 root 做一次完整 review；未 commit、tag、push 或切 production。這不是完整員工成品驗收：Windows 真人 IME 未執行，Task5 生命週期、P5 完整管理 UI 與 Task6 Skill／自然案例仍未完成。

工作樹 `S:/caliburn/.worktrees/analysis-only-agent`，branch `codex/analysis-only-agent`，base `80e29b4a98363f10cffeaf332802adb6f6e29329`。精確 source/test/generated 清單為同目錄 `task-4-source-files.json`（69 檔），root 已建立不可變 snapshot；之後只新增報告／證據，source 無再改動。完整自身交付清單 `task-4-files.json` 排除 root-owned register／review／schema-performance evidence／.gitattributes 等與不相關 dirty docs。README 原 11 行 recall hunk 保留，由 root baseline 排除。production package-lock、apps/api/uv.lock、job-analysis-contract 沒有 diff。

## 實作結果與 authority

同頁只有一份可編輯 Plate JD，旁邊是聊天；唯讀同 renderer 顯示 exact before／after、官方 computeDiff、歷史與逐字來源。六章、基本資料表、Task 的成果與要求、共享 K/S 全文及引用均可讀；section enum 改為繁中名稱。metadata、空 leaf marks、source、span、links-only 差異不以空文字差異冒稱無修改。

API 延用原 Catalog／PostgreSQL／JdService、AnalysisService 與三個原 factory tools。新增 create key、metadata/version/archive seam、read-only run-by-request、canonical source 與 JD routes；新 read/source guard 仍使用原實例與 owner 路徑。API DTO 由單一 active SSOT 加實際 Pydantic API，透過既有官方生成器產生。Web 不另建 wire schema 或 semantic validator。

create 的 key/digest/catalog/初版/head 原子保存，重放同鍵回同文件；普通 dirty 只在頁面 buffer，JD 與未送 chat 有離頁提示。已送 manual/run payload 才進非 authority recovery cache：cache 寫失敗不 POST、unknown 不換鍵、重開只 lookup／同鍵核回覆；confirmed stale candidate 保留唯讀而不覆蓋 current。頁面恢復先 revalidate，讀取失敗鎖住寫入。封存 metadata API 與內部列表接點已備，完整管理 UI 留 P5。

## 4.0 runtime 與依賴

重用 root 已驗簽的官方 Windows x64 ZIP，抽取前重核 SHA256 `1177b4137ba5adaa56354ae40f1080c7450e8ae09cecb47da459d1c52ac99f97`。portable binary 放 plan `task4-runtime/node-v22.23.2-win-x64/`（ignored），不安裝全域、不改全機 PATH。原簽署／授權材料由 root 保存，不混成已執行證據。

先在原 lock 完成 check-codegen、native 68 tests／build、Python→Node test_jd_engine 8 tests；原 Task1–3 的 Node22.12.0 歷史結果不改寫。最初 sandbox 子程序 EPERM，使用獲准 scoped 執行後通過；原鎖這組結果在執行紀錄，沒有另造當時未保存的 raw log。

所有新版 Python tests 經 plan `task4-run.py` 啟動：只從 docker-compose db service 的結構化設定取 credential，建立專用 `q019_jd_app_20260910` URL，設定 PYTHONUTF8/PYTHONPATH 並僅給子程序 PATH 加 portable Node。沒有 .env、DSN 輸出、drop/reset；既有 Memory PG guard `q019_agent_test` 不動。新建 API／JdEngine 的 `self.node` 與同 binary 的 process.execPath/version/versions 記於 `task4-browser-server.json`，實際 v22.23.2；JdEngine bridge Popen 使用此捕捉的 executable，沒有另加 bridge 版本診斷。

Next／eslint-config-next 16.3.3，declared + resolved React/react-dom 19.2.4，Vitest／mocker 4.1.11，Playwright 1.61.0；isolated npm install --ignore-scripts。Next compiled React/react-dom 與 browser React.version 實際是 `19.3.0-canary-cbb046ab-20260731`，不是 19.2.4；compiled RSC webpack/turbopack 記錄該 canary peer/build identity，沒有憑空補 package version。436 個新增／改變 lock entries（含 optional 平台套件）的 resolved/integrity/license 與已安裝授權檔 hash 在 Web license-inventory.json，沒有缺 license declaration；含 MIT、Apache、BSD、ISC、MPL、LGPL、CC 等免費 OSS，不宣稱全 MIT。npm-audit.json 為 0 vulnerabilities。Next 自動產生 Web AGENTS.md／CLAUDE.md，保留於清單；已讀固定版本附帶文件。

## 最終工程驗證

完整命令、cwd、Node、exit code 與 elapsed 保存在 `task4-final-verification.json`；所有 8 組 exit 0：codegen check、contract 27、native 68（9 files）、Web 18（7 files）、typecheck、lint、Next build、API／受影響 owner 41。共 154 tests。API 組包含 test_jd_api、test_api、test_jd_engine、test_jd_tools、test_jd_sources、test_jd_fix1、test_jd_fix2。最後新增的 browser structure-final script 單檔 lint 也 exit 0。沒有為安心重跑無新影響的已過 browser 群。

contract uv 警告繼承的 A VIRTUAL_ENV 不符 C：uv 忽略它而使用 contract 專案環境；不是測錯環境。API 有既有 Starlette anyio BlockingPortal alias DeprecationWarning。git diff --check 通過，只有換行提示。

## 真 browser 與首敗

使用 Playwright 的既有 installed `chrome` channel，headed Chrome **153.0.8010.37**，避免不必要的 browser 下載；沒有驗 Playwright bundled Chromium149。first-browser 留全 network／AX／畫面：只有 3001/8091、1 editable、8 tasks、1 table、0 page errors。後續 scenario network 多為 8091 過濾，不能僅憑這些子集證明全網路無外連。fixture 明確 fixed httpx transport、dummy constant key，無 live fallback；真 create_app／AnalysisService／router／PostgresSaver／Store／三工具，實際 model request body 留 JSONL，零付費呼叫。資料是工程固定案例，不是自然專業品質證据。

| 情境 | 實際證據／結果 |
|---|---|
| input | keyboard 選第二次「工作」（anchor4/focus2）；先保存同 candidate，再 actual POST 帶同 saved base／range；真 jd_read→replace_selection；saved value 為「工作第二處修正」，Human 原話「請改選取」不變。AI batch 加相鄰手改，兩次 undo／redo 分別正確；native Ctrl-C/V 產新 IDs；保存重載 exact IDs/value。 |
| composition | CDP imeSetComposition→insertText 的 compositionstart/update/beforeinput/input/end、提交「職務」與取消「取消」均記錄。**Windows 真人 OS IME NOT RUN**（原生 app 控制不可用）；CDP 不等於 OS 候選操作。 |
| recovery | create commit lost reply 後同鍵同 ID；manual commit lost reply 後同 payload receipt；confirmed stale 經兩次 reload 保留唯讀 candidate；run lost reply 重開只有 lookup GET、不 POST/resume，one Human／one run；純聊天 head 不變。 |
| selection negatives | native cross-block/stale base 409 不寫來源，chat 保留；missing selection 當地拒絕、無 POST。明確「請AI改這段」與「改為純聊天」分開，失效 selection 不靜默轉聊天。 |
| navigation | 真 beforeunload reload 提示取消仍保留普通 dirty；未送 chat 的 App 保存不離頁、不發 chat POST；manual POST 後立即關頁，重開同 exact receipt。 |
| final full r2 | 採用 schema 後完整 6章／1表／8Task／5K／5S，table insert/delete + nested list Enter，保存／重開 exact 結構、來源可讀，0 page errors。ready 1795.55ms、保存 confirmed UI 2071.51ms、reopen ready 1504.21ms；manual HTTP response headers 815.97ms、save後 current 559.30ms、changes 256.89ms、source 17.48ms。 |

selection 首敗 actual request 缺 range，已保留 attempts 1–4。最小修正是從真正 editor.selection 捕捉、明確 intent、同 candidate 保存期間封鎖輸入但不切 readOnly（避免 DOM selection 被解除），保存前後核同 range/base。沒有字串重找、另造 locator 或 range restore。因果界線：不能稱 Plate callback 沒有 selection；固定 @platejs/core53.3.11 `dist/react/index.js:1457–1463` 實際提供 `{editor, selection}`。slate-react0.126.4 `dist/index.js:3170–3228` 的 throttled DOM selection 與 readOnly/nonselectable deselect 支持接合診斷，未把每個時序因素獨立隔離。官方 @platejs/slate53.3.10 `dist/index.js` setSplittingOnce／withNewBatch（約2457／2469）提供歷史接點。

fixture/script 首敗另列，不混為產品：selection attempt3 太早按鍵選到第一次文字；provider 一度取最後 app_jd_context notice 當 Human，已排除；attempt4 r.url 字串誤呼叫導致 harness 停止。recovery strict alert 同時命中 Next announcer，改 scoped main；另一次 route.abort/unroute race 已等待完成再移除 handler。recovery-attempt2 是舊結果重複檔，未當第二次證據、未收入 durable raw。API early RED 包括 create422、CORS403、新 route404，及 response serialization 注入 null 破壞 clean value，後者以 exclude_unset 修正；Next src .js export／Plate renderer override、cache/purechat/readUnavailable、linked source callback 等以有限 RED/GREEN 修正。

## 完整稿性能反證與採用修正

原 schema full r2 read/save 曾超過 5s／30s 測試等待，兩次首敗留 raw；放寬等待只供診斷，不是產品規格。profile：mapper38.909s，其中 jsonschema38.842s，DB .033s、Pydantic .0066s、dump .0047s、FastAPI .0036s、JSON .0008s，94.6M calls；無 profile 的原 HTTP read12.79s。沒有 skip App semantic validation 或換 validator。

candidate1 雖語言測試相同，官方 codegen union 變寬／缺分支，拒絕。candidate2 僅因式分解同 SSOT 的 conditional child refinements；root 窄 review Spec PASS／quality APPROVED 後才採用。active SHA256 `893fdb43fe2696846e74f15f2b5e12ed97a00f5ff1a5bc667c11ce734d7430fc`。438+92 對照及生成型別等價證據、逐 wrapper required type／Text 排除論證、原 schema/hash/diff、官方語義／review 已由 root 保存在 `schema-performance/`，不重複搬移。單段 validator 原3.8138s→.08918s 與上表實際 App/UI 數值分開。替換後重建持 cache 的 API worker580，再跑受影響 final suite + 完整 r2 browser。

## 驗收界線

4.0–4.5 工程項已實作；4.6 自動化／真 browser 已執行，真人 IME 未過、review/commit 由 root 接手。

| Journey | 本輪狀態 |
|---|---|
| J01/J02 | create/list/error 與 key/transaction/API 負例、真 lost reply recovery 已驗。 |
| J03/J04/J05 | 本輪 dirty/cache/run lookup 範圍已驗；普通未送 dirty 不宣稱 crash recovery。 |
| J06 | 完整 cancel/unknown/worker 停止終局留 Task5；不能標全 PASS。 |
| J07 | session 隔離及 revalidate guard 已實作／測試；未把完整 A-running/B/bfcache 真 browser 競態整列標 PASS。 |
| J08 | metadata/archive admission 與內部 archived catalog seam 已備；完整管理 UI、B1/B2/C 背景旅程留後續，非全 PASS。 |
| J09 | 完整 DOM、selection/copy/paste/history、CDP composition 已驗；真人 OS IME NOT RUN，整列 PARTIAL。 |
| J10/J11 | 共用 K/S／舊定義／metadata-only exact material 有 component tests 與共用唯讀 renderer；未宣稱每個排列皆真 browser 重走。 |
| J12 | 本輪 create/chat/edit/save/history/source/reopen 子旅程已驗；更名封存恢復與完整正常生命週期留 P5/Task5，PARTIAL。 |

## 自有程序與交接

讀取實際 Win32 process tree 留 `task4-owned-processes.json`。Next launcher PID **24248** → server **25744**，console helper12956；127.0.0.1:3001。API scoped launcher **2836** → Python26424 → uv23424 → venv Python3736 → worker **580**，console helper28852；127.0.0.1:8091。均由本輪 hidden Start-Process 啟動。換 bootstrap 前仍應核 commandline／parent，PID 可被 OS 重用；不要依 port 猜 kill。先前本輪 API31924/31832 已停止，不是目前 worker。browser scenario 已關閉自己的 browser，不留下另一本輪長駐 browser helper。

目前固定案例 URL：http://127.0.0.1:3001/workspace/3c2812d5-31e0-471a-b874-be7bb7ac468b 。資料庫保留，不清理。durable 自身證據 `docs/specs/evidence/jd-editor-task4/web-app/`；Node 原始驗簽與 schema-performance 為 root-owned 鄰接目錄。raw archive 的 launcher/verify 複本保留原相對位置語義，執行仍從 plan 原件；不宣稱搬到 evidence 後可直接執行。
