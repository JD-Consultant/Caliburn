# T03 關聯式 JD：施工證據

- 日期：2026-09-29；任務狀態以[任務表](../tasks.md#t03-關聯式-jd-與人工編輯垂直切片)為準。接續 T02 提交 `20e8ecad`，只做新目標，不改根正式入口。
- 已交付 profile 人工 API、不可變正式修訂與原命令結果（`52b55951`）、§4 基本資料人工 UI（`32e3ea5e`）、§5 職責集合後端（`f8aca13f`）、§6 任務／成果／要求後端（`129f60f1`），以及 §7 職責／任務人工 UI 與同版組合讀取。**T03 整體未完成**；K／S 等其餘集合與關係、候選、來源及 AI 尚未交付。§1–2 保留第一切片當時的驗證範圍。
- 保存／研究／資料圖：[JD 保存接線](../../../implementation/jd-storage.md)。欄位與業務權威沿該頁路由，這裡只記實測，不抄第二份 schema。

## 1. 先驗反例與實現

先新增「建立後讀空 JD、局部修改保留其他欄」測試；初次真 PG 得 endpoint 404／預期 200。新增 feature 的純值、service／persistence／queries、HTTP schema 生成與 workflow 後轉綠。新建檔案也在原交易內建立空 JD，不靠第一次 GET 寫資料。

後續補驗證，不以第一個綠燈結案：

| 類別 | 已驗行為 |
|---|---|
| 欄位與局部修改 | 四欄 set／clear，未指定保留；沒有員工姓名／檔案名；空白、NUL、錯型別、錯欄位、重複欄位／多餘 key 拒絕 |
| 整批原子 | 後段非法 change 不留下前段效果；插入新修訂／操作後、commit 前注入例外，revision／head／operation 一起回退，原命令之後可成功 |
| 初始化 | 開場與空 JD 後注入例外不留半套檔案；重送建立不重設已修改 JD；0004 新目標已有檔案升 0005，各有固定空 JD，再升級不重建 |
| 重送／競爭 | 8 次並行重送一個效果；兩命令同基底只有一個成功；同 ID 異 payload 拒絕；過期修訂不覆蓋；後續改稿與 A 已啟動後，舊命令仍回原結果 |
| 資料保留／範圍 | 歷史修訂、原操作、初始基底不可改；跨檔案 head 被 FK 拒絕；同值不增修訂，改走再改回仍新身分；不存在檔案不隱式建立 |
| 人工准入 | 活躍／暫停 A 阻止新人工修改，但可讀、可讀回原命令；另一檔案正常；背景 Memory 不鎖人工 JD |

這是有限真 PG 接線與回歸，不包含程序強殺／COMMIT 回應遺失的全鏈證據（T12），不包含 UI 旅程或 provider。

## 2. 驗證命令與結果

沿用專用 loopback PostgreSQL 18.6，`127.0.0.1:55439/caliburn_t01_test`；測例只建立／清理自己的隨機 namespace。Python 3.14.7、SQLAlchemy 2.1.1、Alembic 1.20.0／psycopg 3.3.6；Node 24.19.0／pnpm 12.5.1 沿 T01 lock，不新增依賴。

在 `apps/api` 的 `.venv-target` 執行；DSN 由 `CALIBURN_TEST_DATABASE_URL` 明確指定，沒有載入 `.env`：

```powershell
python -m pytest -q -p no:cacheprovider
python -m ruff check . --no-cache
python -m ruff format --check . --no-cache
python -m mypy --cache-dir S:/caliburn/.research-tmp/mypy-t03
python scripts/generate_contracts.py --check
```

結果：**196 passed，無 skip／警告；144 項真 PG、52 項單元／契約**。Ruff／格式 67 檔、mypy 48 source files 通過；完整生成比對通過。包含原有 migrations／metadata／同命令／隔離回歸，不只跑新測例。

前端本切片只新增生成 DTO；`typecheck`、`format:check` 通過，未新增或改畫面，不拿 T02 的瀏覽器證據冒充 T03 UI 已完成。

資料關係圖與人工修改時序圖用 Mermaid 11.17.2／Playwright 1.63.0 的隔離 Chromium 153.0.8010.12 實際渲染並逐張檢視，標示可讀、無裁切。6 份受影響入口／責任文件的 95 個本機連結與錨點、fences／行尾空白及 Git diff 檢查通過。schema／生成檔／領域／交易／HTTP 的責任邊界已審，沒有提前提供 A 直接寫正式稿的路徑。

工程問題：單元與整合測試最初同名 `test_jd_profile.py` 造成 pytest 收集衝突；改單元檔為語意更清楚的 `test_jd_profile_values.py`，不刪快取掩蓋、不切換全庫 import 模式。此為測試組織錯誤，不算產品行為 Red。其後全套通過。

未讀金鑰、未呼叫模型、費用 0；沒有舊 schema 相容層、通用 receipt 引擎、另套 validator 或 event sourcing。

## 3. 尚未完成與下一步

1. profile 人工 UI 已在 §4 完成；繼續使用相同生成契約、明確新鮮度與原命令結果模式，不為每類集合另造保存機制。
2. 依 T03 原欄位／能力矩陣，逐步新增職責、未歸屬任務、平行成果／要求、共用 K／S 關係、協作者／共通條件及移動／排序。先寫刪職責不誤刪任務、跨目標／引用與後段失敗反例。
3. 候選與固定正式內容分開；來源、人工 diff 與依據確認由 T07 接，完整 A 成功／取消由 T08 接。不能為沿用這個人工 endpoint 而讓 A 中途直接改正式稿。
4. T03 checkbox 維持未完成；API 通過不代表模型品質、整份 JD 或正式交付完成。

## 4. 第二切片：基本資料人工編輯 UI（2026-09-29）

先補 App 旅程測例，觀察既有畫面找不到「JD 基本資料」而失敗，再接 `features/jd-editor`。正式 query、局部草稿與待確認 command 分開；欄位文意來自 JD 指南，HTTP 型別／runtime guard 仍從原 schema 生成／編譯。研究及具體責任見[介面 §1.2](../../../implementation/interface-and-delivery.md#12-t03-基本資料編輯的讀取基底與恢復)。沒有新增 package、第二套 validator、通用 form／receipt 引擎。

**前端 24 項測試通過**（含新增的 App 入口與 8 個 profile 情境）：只傳變動欄位、明確 clear、原結果後 GET 最新、remount 沿原命令、衝突不偷換基底、背景 GET 不覆蓋已開啟草稿、非法／離線讀取不當空稿、空白／未修改／storage 失敗不 POST、在途雙點與 Escape。其他 App 測例補有效空 profile fixture，不讓非本題的 schema 錯誤混入成功場景。

**真 PostgreSQL 瀏覽器 8 項全部通過**，5 個原 T02＋3 個新 T03 旅程，未開啟測試自動 retry：

| 旅程 | 實際檢查 |
|---|---|
| 四欄人工編輯 | 設定四欄、reload 取回、局部清空其餘保留；姓名與開場不變；焦點／Escape、390px 窄螢幕、後端 GET 一致 |
| 表單競爭／准入 | 開表單後另一 API 修改，舊基底提交 409；明確重讀才用新稿；A 已准入時新人工修改被拒，正式內容不變。不是 A runner 或暫停 UI 驗收 |
| 真提交回應遺失 | Playwright `route.fetch()` 讓原 POST 真實提交，再 abort 丟回應；另一次 API 改稿後 reload，以原 command／base／payload 重送取原結果；畫面 GET 目前稿，兩次送出的命令完全相同，較新正式內容不被覆蓋 |

使用既有隔離 PG 18.6／loopback 55439，獨立新 namespace `t03_profile_ui_20260929_1935`；migration 到 head，API 8100、Vite 5173 均為本次啟動，未載入 `.env`／舊資料。Playwright 1.63.0＋相符 Chromium 153.0.8010.12，隔離 headless context，未使用個人瀏覽器。

```powershell
pnpm --filter @caliburn/frontend typecheck
pnpm --filter @caliburn/frontend lint
pnpm --filter @caliburn/frontend test
pnpm --filter @caliburn/frontend format:check
pnpm --filter @caliburn/frontend build
# 明確提供專用 loopback App 與已核對相符 Chromium 的路徑後：
pnpm --filter @caliburn/frontend test:e2e
```

上述全部通過。build 仍警告單一 JS chunk 703.78 kB（gzip 215.10 kB），未提高警告門檻掩蓋；分割／runtime schema 編譯與 CSP 在 T15 做有量測的取捨。本切片不宣稱效能／安全 gate 已通過。瀏覽器另有既有終端色彩環境警告，沒有產品失敗。

桌面與手機編輯畫面實際擷取並檢視。首次手機圖位於 Dialog 的淡入中途，不拿透明重疊圖當完成證據；改成等待框架焦點就緒並用 Playwright 官方 `screenshot(animations: 'disabled')`，重跑八旅程通過，重拍圖清楚且無裁切。圖檔留於 ignored `apps/web/test-results`，僅含本次合成內容。

本切片只改前端與文件；沿用 §2 的後端真 PG 契約證據，並增加真瀏覽器到同一後端的交互驗證。未呼叫模型，費用 0。其餘 JD 集合、來源核對、候選、A／Memory 生命週期及整體恢復仍按原 task 後續完成。

8 份相關文件、114 個本機連結／錨點、fences 與 diff 檢查通過。驗收後停止已核對身分的自有 API／Vite，清除本次 namespace（18 份檔案，均為合成員工）；未刪 DB／舊資料，合成內容可由測試重建但未留資料備份。

## 5. 第三切片：職責集合、固定正文與排序（2026-09-29）

以「建立職責 → 改 profile → 修職責仍保留身分與其他欄」作先驗反例，原後端缺 `/jd/areas`，GET 回 404。接上同一 JD workflow 的型別化職責命令、固定內容與選用後轉綠；沒有將此改動當成模型工具或完整 JD UI。

| 測試範圍 | 已驗證效果 |
|---|---|
| 建立／局部修訂 | title／scope_text 至少一個有意義；可只填範圍；未列欄位保留、明確 null 清空；重複欄、空白／NUL／錯型別／多餘欄拒絕，非法後段不留前段效果 |
| 固定正文／排序 | 穩定 area 身分、變動正文另有修訂；同值／原位置不增 JD 版；改走再改回是新修訂；排序只重選鍵不複製正文 |
| 刪除／歷史 | 新稿移除選用，歷史正文與排序仍可查；同名重建是新身分；原刪除命令在後續新稿後仍返回原結果 |
| 跨操作一致 | profile 改動保留職責，職責改動保留 profile；同 command 不能改投另一種 JD 動作；新命令不可使用舊基底 |
| 恢復／並行 | 八次並行重送只一個效果；同基底兩個競爭修改只一個成功；A 開始後原結果仍可取回；提交前注入例外使 head、revision、content、selection、operation 一起回退 |
| 資料完整性 | 固定正文／選用禁止更新與刪除，已採用的目前／歷史修訂禁止追加選用；跨檔案內容／修訂 FK、同物件重複選用、位置重複／負值被拒；不存在或外檔案的操作目標不寫入 |
| 人工准入 | 活躍／暫停 A 阻止新的職責修改，讀取與另一檔案仍可用；沿用 executions 與同一檔案列鎖，不另建鎖 |
| 契約與生成 | 六種有效 wire 情境及讀取形狀 round trip；nested 額外欄拒絕；內部內容修訂不出現在人工 view |

完整後端 **230 passed，無 skip／警告：171 項真 PG、59 項單元／契約**，其中本切片新增 27 項真 PG、7 項契約。沿用 §2 明確 DSN／隨機 namespace fixture；每測例清理自有 schema，不改舊資料。包含 migrations／metadata、既有 profile、檔案、訪談／准入及 saver 回歸；沒有用 mock 代替 DB 效果。

同一環境執行 §2 命令：Ruff lint／格式（76 檔）、mypy（55 source files）、完整 codegen 比對全部通過。前端只有新增生成 DTO；`typecheck`、`format:check` 通過，沒有把舊瀏覽器測試當職責 UI 證據。

工程問題與修正：`title` enum 初次生成為 `StrEnum.title`，覆蓋字串方法、被 mypy 正確攔截。依官方 generator `--capitalize-enum-members` 設定修生成來源；JSON wire 值不變，既有兩個 enum 一併重新生成／回歸。動態 dict 展開進 dataclass `replace` 也無法證明只改文字欄，改為明確具名欄位，不用 cast 或 ignore 消除警告。這正是程式撰寫規範的型別／命名審查案例；資料契約不為型別檢查退讓。

JD 關係圖與人工寫入時序圖以同版 Mermaid／Playwright 實際渲染並檢視，無裁切；SQL／Domain／HTTP 分責及 FK／保存順序已審。研究與取捨集中於 [JD 保存 §5](../../../implementation/jd-storage.md#5-研究依據與本案取捨)，不另建研究副本。

8 份相關文件的 123 個本機連結／錨點、fences、行尾及 diff 檢查通過。

**限制：**任務尚不存在，因此「刪職責保留任務為未歸屬」仍待下一切片，不宣稱本次已驗；職責 UI、候選、來源、A 完成及程序強殺恢復仍未交付。本次無模型請求／費用，不開瀏覽器 App，不動 production 入口。T03 不勾完成。

## 6. 第四切片：任務、平行明細與歸屬保存（2026-09-29）

從 §5 完成點接續。先寫「刪職責保留任務與明細」「兩組明細獨立且局部修改保留身分」兩個真 PG 反例，原程式缺 `/jd/tasks`，兩項均因 GET 404 失敗。接上型別化任務變更、三個關聯保存表及原 workflow 後轉綠；不將 Red 當成資料遺失真的已發生。

| 測試範圍 | 已驗效果 |
|---|---|
| 任務與明細 | 建立／局部改字／明確清空／增刪成果要求；兩組獨立、不配對，任務及保留明細 ID 不變；同值不增版本，順序改走再改回仍新修訂 |
| 移動與刪除 | 任務跨職責／未歸屬、鄰項定位與排序；只移動不複製正文；同任務必要內容調整可原子附帶。刪職責把任務追加到未歸屬、保留相對順序及明細；原建立命令仍回當時歸屬，不用目前稿冒充 |
| 局部界線 | 禁跨任務修改明細、禁成果／要求混排；錯檔案、錯群組、錯鄰項拒絕。profile、職責及任務互相保留，不回寫員工姓名／原話 |
| 全成或全拒 | 空白／NUL／錯型別／多餘 key／重複指定／清成無內容拒絕；前段新增明細、後段不存在或移動目的錯誤，不留下部分效果 |
| 恢復與競爭 | 八次並行重送只一份內容／效果；同基底兩新命令一成一拒；同 command 改 payload／基底／動作拒絕。A 啟動後可回原結果、新人工修改仍被擋；提交前注入失敗使內容、明細、選用、head 與操作一起回退 |
| DB 約束 | 固定正文、明細、選用不能改寫／刪除；已選用正文不能事後加明細，已採用 JD 不可追加選用；同檔案／同修訂 FK、穩定身分與位置唯一，未歸屬 null 組也受唯一排序約束 |
| 契約／純規則 | 八種輸入 round trip 同時比對 schema、生成 DTO、Domain 原意 payload；內部內容修訂不出 view。純值直接拒絕非法內容／重複修改；移動原位置不新增修訂、缺群組不默默丟掉任務 |

最後全套 **267 passed，無 skip／警告：191 項真 PG、76 項單元／契約**；相較 §5 新增 20 項真 PG、9 項契約、6 項純任務規則與 2 項分層反例。沿 §2 同一專用 DB／隨機 schema fixture，覆蓋新舊 migration／metadata 及既有用例，沒有重建現行產品資料。

Ruff lint／格式（86 檔）、mypy（62 source files）、完整 codegen 比對全部通過；前端僅增加生成 DTO，`typecheck` 與 `format:check` 通過。未重跑 UI／provider，不能以本輪後端測試宣稱任務 UI 或模型工具已完成。

程式審查：純 task 值與變更計算、service、SQL、workflow、HTTP 分責；不新增 class/interface 工廠或另一套 receipt。原意 payload 明確序列化各動作，不用 `default=str` 隱藏未知型別；格式交 Ruff，沒有加 ignore 迴避型別／命名。任務自身內容／明細採固定小集合，其餘項目正文重用，理由與限制寫在 [JD 保存 §2.2](../../../implementation/jd-storage.md#22-任務內容獨立明細及歸屬)。

資料關係拆為 JD 頭／職責與任務／明細兩張圖，另保留人工寫入時序；同版 Mermaid 11.17.2／Playwright 隔離 Chromium 實際渲染，逐張檢視無裁切與遮擋。研究沿 [JD 保存 §5](../../../implementation/jd-storage.md#5-研究依據與本案取捨)，不另造第二份規格或通用版本引擎。

8 份相關文件的 133 個本機連結／錨點、fences、行尾及 diff 檢查通過。

**未完與接續：**優先補職責／任務的人工 UI 垂直旅程，再補共用 K／S、關係、協作者／共通條件及候選。完整結構工具的跨項目必要內容調整、來源及模型 read_ref 適配仍按 T07 接，不能把這批人工 UUID endpoint 直接給 A。程序強殺／COMMIT 確認遺失的全鏈 gate 仍在 T12。未呼叫模型、費用 0，T03 仍未完成。

## 7. 第五切片：職責／任務人工 UI 與同版讀取（2026-09-29）

接續 `129f60f1`，沿既有關聯式欄位、命令／固定基底及人工准入，不新造資料 owner。研究與接線集中在[介面 §1.3](../../../implementation/interface-and-delivery.md#13-t03-職責與任務的人工編輯)及[同版讀取 §2.3](../../../implementation/jd-storage.md#23-組合畫面使用同一修訂)，不在 evidence 複製 wire 契約。

### 7.1 Red 與新增範圍

`GET /jd/work` 先寫兩個真 PG 反例，原 API 404；前端先寫 editor／任務草稿測試，尚無模組而不能收集。新增讀取投影與 UI 後轉綠。模組缺失只代表尚未實作，不冒稱已驗證資料損失。

組合讀取只固定一次正式 JD 修訂，再以該修訂讀職責、任務及明細。測例在讀完職責後，由另一真請求刪職責並提交；這次仍取得原修訂的完整職責與任務，下一次 GET 才看到任務轉未歸屬。不存在檔案回 404，不回空文件。不新增表、不改 migration、不提升全域 isolation；JSON Schema `$ref` 重用既有項目型別，標準生成器及 Ajv 均驗證同一契約。

UI 的表單、局部明細變更、待確認命令與頁面組裝分責。已開表單保留原基底，背景讀取不覆蓋草稿；成功重讀目前稿而非塞入原命令的舊回傳。profile／集合共同 head 互相失效，重讀中不開啟使用舊 cache 的新表單。

### 7.2 已執行驗證

| 層級 | 結果與範圍 |
|---|---|
| 後端全套 | **269 passed**、無 skip／警告；193 項真 PG、76 項單元／契約。包含原有隔離、CAS、重送、不可變選用及全部 migration 回歸；本切片增加兩項同版讀取反例 |
| 前端 | **37 passed**，6 個測試檔；原 24 項加 10 項集合 UI、1 項明細變更及 2 項焦點規則測例。原 App 入口另補 console error 斷言 |
| 真 PG 瀏覽器 | **12 passed**，8 個既有旅程＋4 個新旅程；Playwright 1.63.0／Chromium 153.0.8010.12，未開自動 retry |
| 靜態／生成 | Ruff lint／格式（89 檔）、mypy（65 source files）、完整 codegen 比對；前端 typecheck、lint、Prettier、build 通過 |

前端反例涵蓋：增修刪職責／任務、只送有變明細、原命令 remount 接續、原目標已消失仍能查結果、post-commit 暫存清理失敗不誤報保存未知、衝突不偷換基底、讀取失敗不當空稿、儲存不可用不發請求、在途雙點／關閉保護，以及背景重讀不覆蓋表單。

四個新瀏覽器旅程使用真正的 HTTP 與 PostgreSQL：

1. 職責／任務／明細 CRUD、排序、跨組移動；刪職責保留任務、成果／要求身分，reload 一致；390px 表單可讀、儲存按鈕可見，未歸屬名稱明確；正常旅程無瀏覽器 console error 或 pageerror。
2. 集合修改後改 profile，再新增集合，兩個方向都刷新共用 JD 基底。
3. 任務在 DB 真提交後攔截並丟棄 HTTP 回應，另一命令再刪任務；reload 重送原命令可確認原結果，但不復活已刪任務，也不把原結果覆蓋目前稿。
4. 表單開啟後其他提交導致 409；A 已准入也拒絕新人工任務，使用者獲得重讀提示而非覆蓋。

### 7.3 審查中修正的實際問題

- 窄螢幕截圖發現未歸屬 select 呈空白、長表單的儲存入口不易看見：使用明確的顯示選項（送出仍為契約的 null），按鈕改放 Dialog 固定底部。修正後重跑旅程並檢視桌面與手機截圖。
- MUI 轉場與快速鍵入的焦點競爭：單用 `autoFocus` 不可靠；無條件 `onEntered` 又會把已移到其他欄位的輸入搶回。以窄 helper 在轉場完成時只設定尚未互動的初始焦點；兩個決定性測例及 profile／work 真瀏覽器通過，不拿 sleep 或移除 StrictMode 掩蓋。
- 最後讀 Vite 紀錄發現兩個 sibling editor 的相同 key 警告。補 App console 斷言後確實 Red；移除重複 key，沿外層檔案 key 重置，完整前端轉綠，再補正常瀏覽器旅程的錯誤檢查。
- 新增的清理失敗測例最初重用已消耗的 mock Response，導致假失敗；改為每次回 clone。這是 fixture 修正，不是產品根因，也不將原失敗列通過。

本輪沒有新增套件／鎖檔。前端建置為 730.93 kB（gzip 221.13 kB），仍有既有 >500 kB chunk 提示；不提高閥值隱藏，整體效能與 Ajv 編譯的安全／容量評估仍由 T15 執行。正常瀏覽器檢查不要求故障注入旅程沒有預期的 HTTP 錯誤。

JD 保存文件的 4 張 Mermaid 圖（職責、任務明細、同版讀取時序、寫入時序）以 Mermaid 11.17.2 實際渲染並逐張檢視，沒有裁切／遮擋。圖說標明目前人工範圍，不將查詢投影畫成第二份儲存。

### 7.4 環境、限制與下一步

沿 §2 工具鏈／DB，瀏覽器使用專用 namespace `t03_work_ui_20260929_2054`，API／Vite 僅 loopback。未讀 `.env`、未呼叫模型，費用 0；測試資料全合成，現行產品 DB 與入口不變。暫態瀏覽器 command 不承諾清除分頁後可恢復，亦不等於正式 JD 的保存權威。

完成後核對 namespace 中 52 份檔案全部為合成員工，保留供本機診斷；未刪 DB 或 schema。只停止核對過命令行的本次 API／Vite，PG 測試服務保留。8 份責任／入口／證據文件共 145 個本機連結與錨點、fences、行尾及 Git diff 檢查通過。

下一個 T03 切片為共用知識／技能及任務關係，再補協作者／共通條件與候選；依原任務邊界接 T07 來源／模型工具及 T08 Turn，不能因人工畫面可用就說 AI 可以改稿。完整程序強殺／提交確認遺失 gate 仍在 T12，**T03 未完成、Goal 未完成**。
