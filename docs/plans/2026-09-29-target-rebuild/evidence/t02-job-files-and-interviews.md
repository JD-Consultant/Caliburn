# T02 職務檔案與訪談資格：實測及接續紀錄

- 日期：2026-09-29；狀態由[任務表 T02](../tasks.md#t02-職務檔案正式訪談與執行准入)維護。第一切片為建立／讀取／開場保存；第二切片見 §6 輸入／准入，第三切片見 §7 正式化／來源查詢，第四切片見 §8 檔案 UI，第五切片見 §9 列表改名與 T02 完成。這不是完整 AI 產品已完成。
- 分支 `target-rebuild`，接續 `b1b8a17e`；本切片程式、契約與文件共同提交，SHA 從 Git 歷史取得。不改根 production 入口。
- 真實 PostgreSQL 18.6；全部合成資料、隨機 `t02_<uuid>` namespace；每次只清理該次新建 schema。未讀 `.env`、未呼叫真模型、無外送費用。

## 1. 已成立與尚未成立

| 已驗效果 | 證據 |
|---|---|
| 建立檔案與 App 開場正式序號 1 同次保存 | `test_create_and_resend_keeps_one_file_and_one_formal_opening`；中途注入失敗後，三張表均無半套結果 |
| 重送／併發不重建 | 4 個並行請求執行緒、8 次同命令，只產生一份檔案／一則開場；同命令不同內容 409 |
| 原建立結果與目前 metadata 不混用 | 修改目前名稱後，同命令仍返回原建立結果，GET 返回目前名稱 |
| 同名與隔離 | 同名檔案 UUID 與開場來源不同；跨檔案正式來源複合 FK 拒絕；不存在檔案 404 |
| 原文不等於正式資格 | 插入尚無正式資格的合成員工原文後，公開歷史仍只有開場第 1 則；原文／正式身分 UPDATE、DELETE 拒絕 |
| 遷移可重現 | CLI `upgrade head` 兩次＋`check`；metadata／約束名稱對照；空／錯版 schema 啟動拒絕且不自動建表 |
| 生成與靜態邊界 | Python／TS schema 往返、Ruff、mypy、既有 import 邊界、TS 型別／格式及 codegen:check |

**第一切片當時未完：**輸入接受／執行准入於 §6 續補，受控正式化／來源區間底層於 §7 續補，建立／列表／改名 UI 於 §8–9 續補。A 完整成功提交與取消／候選回退仍在 T08；無假完成／任意新增正式訪談 endpoint。正式帳號權限、瀏覽器入口保護與端到端故障仍須 T12／T15／T18，不拿 TestClient 通過當產品交付。

## 2. 實作與研究取捨

- 資料關係、交易與責任在[訪談保存接線](../../../implementation/interview-storage.md)，不在此維護第二份 schema。
- 採 SQLAlchemy **2.1.1**、Alembic **1.20.0**；核當前官方 stable 文件、PyPI Python／Windows 支援與 MIT license，與既有 psycopg 3.3.6 一起驗。僅增加 Alembic、SQLAlchemy 及必要 greenlet／Mako 相依，精確版本在 `uv.lock`。
- 每次 workflow 獨立 session，短交易由 workflow 管理，feature 不 commit；不建 BaseRepository／通用 UnitOfWork。建立重送用原 owner 內的不可變建立資料，沒有第二套通用收據服務。
- 開場為 App 保存的引導文字，依工作分析指南先了解工作全貌；不是員工事實或模型回答。
- 原始文字及正式資格分表，讓已保存但未正式採用的輸入不混入正式歷史；原文不需要複製兩份。資格的實際提升仍待完成協調接線。

## 3. Red、問題與修正

1. 先建立真 PG 行為測試：`POST /api/job-files` 實際 404／預期 201；接入 workflow／routes 後通過。不是把缺依賴或 fixture 失敗當作 Red。
2. schema 比較發現 Alembic 把自己的版本表列作 `remove_table`：migration 固定 search path，版本表沿 default schema，並校驗 `current_schema()`；CLI 與 metadata 比較後通過。
3. 額外查 PG constraint catalog 發現 CHECK 名稱重複加前綴。依 Alembic 官方 `op.f()` 標示已完成名稱；所有宣告約束名稱均存在。不能只靠 autogenerate 推論全部 DDL 相同。
4. 新版 SQLAlchemy 2.1 警告 `Result.tuples()` 已棄用：改用 typed Row 解構，不忽略警告。
5. 生成器的單檔輸出不接受外部 root ref；原生 external-ref-mapping 以 fragment 名解析，空 fragment 亦失敗。改將該 feature 的共用 JobFile 定義留在同一 schema 的 `$defs`，而非手抄 DTO 或自行寫 resolver。生成器加 strict local refs／禁止 Python 端遠端 ref，四份 schema 可重現生成。
6. Windows sandbox 對 codegen 臨時目錄、隔離 headless Chrome 出現拒絕／EPERM；經工具授權後執行同一命令成功。沒有改使用者瀏覽器、放寬產品權限或刪除舊資料。
7. NUL 名稱原本通過 DTO 後在 PG text adapter 失敗；先新增 HTTP 邊界反例，再修 schema／領域驗證並再生 DTO，現在回 422 且無半套資料。engine／migration 設定 `hide_parameters=True`，避免 SQLAlchemy 例外列出原始參數；完整診斷／安全 gate 仍不由這個設定代替。

上述均為本機具體反例與有界修正，沒有重訂產品語意。官方來源與取捨見責任文件 §5。

## 4. 驗證命令與結果

沿 [T01 環境路徑](t01-foundation.md#2-可接續的環境與命令)，本機 PG 為專用 loopback `55439`／`caliburn_t01_test`；不把此測試連線寫成產品預設。

在 `apps/api`，Python 為 `.venv-target/Scripts/python.exe`，先明確設定合成 `CALIBURN_TEST_DATABASE_URL`：

```powershell
python -m pytest -q -p no:cacheprovider
python -m ruff check . --no-cache
python -m ruff format --check . --no-cache
python -m mypy --cache-dir S:/caliburn/.research-tmp/mypy-t02
python scripts/generate_contracts.py --check
```

- **60 passed**：含 **26 項真 PostgreSQL 測例**（其中 1 項是 T01 官方 saver 跨程序回歸），其餘單元／契約測試。沒有 skip 冒充通過，無警告。
- Ruff／格式（41 檔）通過，mypy（29 source files）通過；生成再生檢查通過。
- `pnpm --filter @caliburn/frontend typecheck`、`format:check` 通過；前端只新增生成 DTO，未新增 UI，不把此項說成瀏覽器旅程通過。
- 新 schema 圖以 Mermaid 11.17.2＋Playwright 1.62.1 隔離 headless Chrome 實際渲染、檢視：3 個表、2 條關係及 PK／FK／UK 標示可讀，無裁切。圖只是本切片，不冒充完整產品資料圖。
- 文件檢查：9 份受影響文件、105 個本機連結與對應錨點／fences／行尾空白通過；Git diff 空白檢查通過。

測試只刪除自己本次建立的隨機測試 namespace；這些合成暫存不可恢復、不需要保留。未刪 DB／cluster／使用者資料。

## 5. 下一個可執行切片

1. T02 已於 §9 完成；下一切片 **T03 關聯式 JD 人工編輯**。先完整讀 JD 欄位指南／工具能力覆蓋、資料接線及驗證矩陣；沿既有檔案 scope、短交易與准入服務，不重做已成立底層，不在 UI 暴露尚無 runner 的輸入入口。
2. T08 使用 §7 的正式化參與介面與當前 writer／准入，接完整 JD／背景意圖的同次完成，並固定 K／H／F；只有全體效果成立才提交。禁止另開 HTTP 任意正式化 endpoint。
3. 控制意圖、Graph 恢復、候選與原生基底回退仍須 T06／T08／T12 驗；不能把 §6／§7 的資料交易競爭當完整 A final／取消已驗。

## 6. 第二切片：輸入接受與持久執行准入（2026-09-29）

接續 `e3889e28`；只改新目標。先核有效契約的原文／正式來源分離、取消不佔號、同檔案 A 與 Memory 分別准入；研究當前 PostgreSQL 18 列鎖、Read Committed 與 partial unique index。具體 schema／責任／限制維護在[保存接線 §6–7](../../../implementation/interview-storage.md#6-輸入接受重送與新提交)，未新增套件、佇列或 Graph 進度副本。

**TDD：**先以 POST 輸入保存的行為測試取得 404（預期 202）；不是環境錯誤。接入生成 DTO、接受 workflow、原文／提交關係及准入後通過，再補競爭、取消與恢復反例。正式歷史仍只有原已成立來源。

| 實際驗證 | 覆蓋與限制 |
|---|---|
| 接受重送 | 4 執行緒／8 次同命令只一份 input／execution，原文含空白換行不改寫；不同文字重用命令拒絕 |
| 同檔／跨檔競爭 | 不同輸入競爭只一個 A 被接受；持有甲檔列鎖時乙檔仍可接受。A 與 Memory 可各一個，不用全 App mutex |
| 取消資格與重試輸入 | 終止 A 資格後，新命令可接受相同文字；重送舊命令仍只回原接受結果、不復活舊執行；兩份原文均不取得正式序號 |
| 保存失敗 | 原文與接受關係已 flush 後注入失敗，准入／輸入／關係一起回滾；可重送同命令 |
| 實例重建 | 新 App instance 依同 DB 承接相同接受結果；不是 process kill／provider 故障測試 |
| writer fencing | 競爭領取只有一個 writer；明確 CAS 取代後舊 writer 的資格及實際同交易資料寫入拒絕；領取重送可回原 writer |
| 終態 | 完成／取消競爭只有一個勝者；active／paused 占准入，terminal 不可復活；Memory 不能 paused／cancelled。未接正式答覆／JD，不能稱整輪完成原子驗收 |
| 真資料約束 | input 關係不可改寫／刪除；跨檔案來源與 execution 的複合 FK 精確拒絕，不以 UNIQUE 或不存在 ID 的失敗冒充 scope 驗證 |

**回歸：94 passed，含 54 項真 PG 測例，無 skip／警告。**原 60 項保留，增加 28 PG／6 契約測例。Ruff／格式（50 檔）、mypy（37 source files）、生成檢查與前端型別／格式檢查通過；TS 新增兩份生成型別，不表示 UI 已驗收。以 Mermaid 11.17.2＋Playwright 1.62.1 隔離 headless Chrome 渲染並檢視五表／五條關係圖，標示可讀、無裁切；9 份文件／109 個本機連結與錨點檢查通過。

本切片有資格層 pause／resume／finish，但沒有對外控制 API 或 background runner。`writer_id` 是防遲到寫入的條件，不是存活偵測：不能因逾時就偷換 writer、不能自動重跑 Memory、不能把 terminal 復活作重試。後續 supervisor／控制接線沿原框架設計實作，既有待驗項不削減。

未讀 `.env`、未送模型請求、費用 0。專用 PG 只供合成測試；測例清理各自 schema，不刪 cluster／DB／正式資料。所有程式與文檔一同本地提交，不 push。

## 7. 第三切片：正式交流與有界原話查詢（2026-09-29）

接續 `a630f957`，先完整核對來源契約的正式資格、序號、K／H／F、前問與整筆拒絕，再核資料交易、程式組織與寫法。研究 PostgreSQL sequence 的 abort 行為、SQLAlchemy 2.1 的交易參與；採既有檔案列鎖＋短交易，不增加分散式號碼服務、通用完成引擎或套件。詳細規則及來源只維護在[保存接線 §8–9](../../../implementation/interview-storage.md#8-正式答覆與序號參與完成交易不自成完成-api)。

**兩個 Red：**先建立正式化參與位置，測原話與答覆完成後的歷史，實際 `[1]`／預期 `[1,2,3]`；再測 B 的 F=6 卻請求讀到顧問答覆 7，原查詢未拒絕。實作後兩者轉綠，不把 import／環境故障當行為失敗。

| 已驗效果 | 證據及限制 |
|---|---|
| 正式化保存 | 完整員工原文與正式答覆各取得固定序號；保留原 source ID、不複製原輸入，開場仍為 1 |
| 完成重送 | 4 執行緒／8 次同工作完成只一組來源；更晚訪談已成立仍回原 pair，不拿最新答覆代替；不同答覆拒絕 |
| 回滾不佔號 | 答覆／序號已 flush、終態已設後注入失敗，整次回滾；原輸入保留、執行仍 active，合法重試仍分配 2／3 |
| 資格與競爭 | paused、cancelled、failed、過期 writer、錯檔及 Memory 拒絕正式化；取消與完成競爭不留半組來源 |
| 引用保存 | 答覆—提交關係不可改寫／刪除，複合 FK 拒絕跨檔案 execution；歷史正文循既有不可變來源保存 |
| 單則／多則／範圍 | 保留角色、原文、全檔序號；選 `(7,2,5,2)` 得 `(2,5,7)`，範圍 `(2,5)` 得全部 2–5，不自動加前問 |
| 全拒而非漏回 | 空集合、非整數、零／負數、倒置、混入超界、不存在或錯範圍，一律拋 typed error，不交回部分原文 |
| 固定界線 | A 的 H=7／B 的 F=6，在新訪談到 9 後仍固定；B 不取得顧問回覆 7；未完成原文只可透過 App 私有原提交查詢取得 |
| 近期與前問 | 首次含 App 開場；K+1 後完整讀、需要時補一則並標 `context_sequences`；空近期仍可有前問，補語境不改涵蓋 |

回歸 **134 passed，含 94 項真 PG，無 skip／警告**；新增 40 項皆為真 PG 測例。Ruff／格式（54 檔）及 mypy（38 source files）通過；含 migration 空 schema 升級／重跑／metadata check 的原測例仍通過。無 HTTP schema／前端改動，不因此重跑 provider 或宣稱 UI／AI 可用。

資料圖以 Mermaid 11.17.2＋Playwright 1.62.1 隔離 headless Chrome 實際渲染及檢視；六表、七條關係皆可讀，改為橫向配置避免連線遮住表格，無裁切。9 份相關文件、112 個本機連結／錨點及 fences／行尾空白檢查通過；Git diff 空白檢查通過。圖與文件只表示本切片已實作的底層，不提前宣告 T02 UI 或 T08 完成。

目前只有內部 `record_formal_interview` 參與介面，不 commit、不單獨完成整輪；合成 harness 的終態提交不能替代 T08 的 JD／來源／背景意圖完整協調。模型工具 wire、容量不足策略及固定基準注入仍依原任務驗收。本次未讀 `.env`、沒有付費模型請求；專用 PG 的測例只清理自己建立的合成 namespace，正式資料未動。

## 8. 第四切片：建立、選取與正式開場 UI（2026-09-29）

接續 `f51d6ccf`；以既有建立／清單／正式歷史 API 為唯一後端，不增設假模型或任意正式化入口。研究與實現責任見[介面 §1.1](../../../implementation/interface-and-delivery.md#11-t02-已落地的讀寫邊界)，使用方式見[frontend README](../../../../apps/web/README.md)。

**Red → Green：**先測空清單應有建立入口，原施工頁找不到「職務檔案」heading；新增路由、Query、受控表單與正式歷史回讀後轉綠。再補不明結果重送、格式驗證、同名／晚到回應隔離等反例。瀏覽器另發現初始焦點在 Dialog paper 而非名稱欄，核對 MUI 9.4 的 FocusTrap 與 StrictMode effect lifecycle 後，改在框架 transition `onEntered` 定位 input；不刪測例、不關閉 StrictMode／焦點陷阱。

| 驗證層級 | 已成立效果／限制 |
|---|---|
| Vitest＋Testing Library，12 項 | 空清單、GET 失敗／重讀、非法 schema 拒絕、建立後開場／真出處、同名檔案切換與遲到結果、404 不漏 debug、原話 HTML 字串不執行；建立命令先保留／不明結果重開仍同 ID、確認後新命令、送出期間不重送／Escape 不關閉、空白及儲存失敗不送、明確拒絕與無法採用結果分開 |
| 真 PG＋Playwright Test，3 項 | 真建立／同名選取／reload、Dialog 鍵盤焦點及 Escape 恢復、390px 無整頁水平溢出；POST 真提交後故意丟回應，reload 後原命令回 200 且同名合成檔案只一份；離線列表有重讀入口而非假空白 |
| 靜態與建置 | TypeScript strict、typed ESLint、Prettier、Vite build；不以 build 成功代替旅程 |
| 視覺 | 實際檢視 desktop 1280px 清單及 mobile 390px 正式開場截圖，標籤、按鈕、角色／序號及換行可讀；不是全裝置或可及性完整認證 |

新增直接依賴：React Router 8.4.0、TanStack Query 5.104.0、MUI Core 9.4.0、Emotion 11.14.x、Ajv 8.20.0／formats 3.0.1、user-event 14.6.7（MIT），Playwright Test 1.63.0（Apache-2.0）。registry peer metadata 與 strict peer 安裝通過；精確版本仍以 lock 為準。沒有另加全域 store、form engine 或 UI 付費套件，舊產品 importer 未變。

實際沿 Node 24.19.0／pnpm 12.5.1，命令見 frontend README。PG 為原專用 `caliburn_t01_test`，本輪另建 `t02_ui_20260929_1816` namespace；API／Web 僅綁 loopback 8100／5173，未用舊 `.env`／正式資料。瀏覽器為 Playwright 1.63.0 對應 **Chrome for Testing 153.0.8010.12（revision 1243）**，不是拿舊 browser revision 冒充相容。

環境／工程修正紀錄：

- sandbox 的 Vite／Vitest 子程序 EPERM 經工具權限審查重跑；不是行為 Red。
- MUI 9 移除 Stack system props／`disableEscapeKeyDown`，依目前 API 改 `sx`／受控關閉，不套用舊教學。
- Node 24 執行 E2E 時要求 JSON import attributes；同一 schema import 加 `with { type: 'json' }`，不複製第二套 test schema。
- Playwright 內建 Node 下載器逾時；curl 對同一官方 CDN 跟隨到 Google storage 成功，下載到 `.research-tmp`，核對 server MD5（只作傳輸完整性、不宣稱簽章）、binary 版本後，以明確 executable path 跑隔離 headless。沒有改個人瀏覽器或偷降 Playwright 版本。
- 專用 PG 初次啟動漏帶測試埠，診斷 log／PID 後停止該自有 cluster，再明配 `-p 55439 -h 127.0.0.1`；未對 5432 的其他 DB 發命令。

**仍待後續 gate：**列表改名先補 T02；A 訪談／JD 尚未接線。首個 bundle 約 692 KB（gzip 212 KB）有 Vite 500 KB 警告，未調高警告門檻掩蓋；T15 衡量 route／validator 分割與嚴格 CSP，Ajv runtime compile 不能當嚴格 CSP 已通過。T15／T18 的 Host／Origin／CSRF、正式交付與資料安全仍待完成。此輪不呼叫 OpenAI、不讀金鑰、費用 0，不把三項 UI 測試宣稱完整產品或模型品質驗收。

最後回歸：12 項 Vitest、3 項真 PG 瀏覽器旅程再次通過；strict peer／frozen lock 離線安裝、型別、lint、格式、build、原 schema 再生檢查通過。4 份受影響文件、65 個本機連結／錨點、fences 與 Git 空白檢查通過。新增 sequence diagram 以 Mermaid 11.17.2 實際渲染並檢視；首次註記過長已換行修正，最終四個參與者／兩條結果分支可讀無裁切。檢查後精確停止自有前後端與 PG；只清除本次 namespace 的 8 筆合成檔案及其測試關聯，這些臨時測資未備份不可回復；未刪 cluster／DB／既有資料。

## 9. 第五切片：列表改名與 T02 完成（2026-09-29）

接續 `598daff2`，補 T02 最後的列表改名需求；只修改顯示名稱，同名仍合法，不改檔案身分、員工姓名或訪談。先查產品責任，再研究 Google AIP-154 的新鮮度檢查與 PostgreSQL 短列鎖；採明確名稱修訂及原操作結果，不引入通用收據／版本平台。契約、資料圖、選型理由與官方來源集中在[保存接線 §10](../../../implementation/interview-storage.md#10-列表改名名稱新鮮度與原操作結果)，UI 接線在[介面 §1.1](../../../implementation/interface-and-delivery.md#11-t02-已落地的讀寫邊界)。

**Red → Green：**後端先驗改名應成功，實際 endpoint 404／預期 200；前端先補三個改名行為測例，原畫面沒有改名入口。接入唯一 JSON Schema／生成 DTO、原 owner 的 service／workflow、短交易、migration 0004 及表單後轉綠。沙箱 cache／子程序權限錯誤另行處理，不當作 TDD 行為證據。

| 驗證層級 | 已成立效果／限制 |
|---|---|
| 23 項新增真 PG 測例 | label-only、同名隔離、建立重送仍回原名、改回同字仍拒舊基準、同值命令不增修訂、同命令異 payload 拒絕、同基準兩命令只有一個成功、8 次並行重送只有一份結果、非法輸入／錯 scope、修改與結果一起回滾、原結果不可改及 counter 不可任意倒轉 |
| 原結果與最新狀態 | 原改名後已有第二次改名，重送第一個命令只回原結果，不覆蓋第二個名稱；UI 再讀目前 metadata，不把原回傳當最新版 |
| 15 項前端測試 | 原 12 項保留；新增 label-only payload／refresh、未知結果 remount 後原命令不變、409 需明確重讀而非自動換基準 |
| 5 項真瀏覽器旅程 | 原 3 項保留；新增窄螢幕改名／同 URL／姓名與開場不變，以及真 POST 已提交後 abort 回應、另一命令改名、reload 重送仍不覆蓋後來名稱 |
| 視覺與操作 | 390px 清單／Dialog 實際截圖、焦點與水平溢出檢查；窄螢幕隱藏建立時間、操作直排，避免姓名逐字擠壓。不是完整可及性／全部裝置認證 |

回歸使用 §4 的同一後端命令與明確合成測試 DSN：**158 passed，含 117 項真 PG、41 項單元／契約，無 skip／警告**；Ruff／格式（56 檔）、mypy（39 source files）、codegen 再生檢查通過。前端 `test` **15 passed**，`typecheck`、`lint`、`format:check`、`build` 通過；Playwright `test:e2e` **5 passed**。沿 §8 的 Node 24.19.0／pnpm 12.5.1／Playwright 1.63.0／Chromium 153.0.8010.12，沒有新增依賴或修改 lock。

工程問題及修正：

- MUI 9 的 Stack 版型使用 `sx`，未停用型別檢查；窄螢幕視覺檢查發現欄位過擠，調整後重跑五項旅程。
- 重跑 E2E 的合成同名資料讓文字 locator 匹配多筆；改以本測例剛建立的檔案 URL 精確定位，不用 `.first()` 掩蓋歧義，也不為通過測試強迫名稱唯一。
- 七表的單一 ER 圖連線被表格遮擋；拆為「原文／正式來源」與「准入／改名」兩個視圖，共用表仍為同一 owner。Mermaid 11.17.2 實際渲染兩圖並逐張檢視，關係標示可讀、無裁切。
- Windows `psql -c` 的中文字元編碼使清理前查詢失敗；改用明確 UTF-8 的 Python／psycopg 核對測資，不改資料編碼或放寬刪除範圍。

本次 UI 專用 namespace 為 `t02_rename_20260929_1846`；完成後核對 18 筆均由本次測例建立，再精確停止自有 API／Vite，刪除該 namespace 及合成關聯，最後停止同一專用 PG cluster。這些測資未備份、不可恢復；cluster、DB、使用者資料及舊產品均未刪除。未讀 `.env`、未呼叫模型，費用 0。

文件終檢：11 份責任／入口文件、130 個本機連結及錨點、fences／行尾空白通過；Git diff 空白檢查通過。程式審查核對 owner、原結果與目前狀態分離、唯一 schema／再生、錯誤映射與不隱含重試，未另建平行保存系統。

**T02 範圍完成，不能擴張解讀：**尚未接完整顧問執行、JD 或背景 Memory；A 完成交易及回退在 T08。bundle 約 696 KB（gzip 213 KB）的原 500 KB 警告仍留給 T15，沒有調高門檻；CSP／入口安全／正式交付仍依原 gate。下一切片為 T03，不以底層／檔案 UI 通過宣稱完整 AI 產品可用。
