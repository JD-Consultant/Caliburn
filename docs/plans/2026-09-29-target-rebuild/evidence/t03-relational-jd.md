# T03 關聯式 JD：施工證據

- 日期：2026-09-29；任務狀態以[任務表](../tasks.md#t03-關聯式-jd-與人工編輯垂直切片)為準。接續 T02 提交 `20e8ecad`，只做新目標，不改根正式入口。
- 已交付 profile 人工 API、不可變正式修訂與原命令結果（`52b55951`）、§4 基本資料人工 UI（`32e3ea5e`）、§5 職責集合後端（`f8aca13f`）、§6 任務／成果／要求後端（`129f60f1`）、§7 職責／任務人工 UI 與同版組合讀取（`cb6e8e9f`），以及 §8 共用知識／技能與任務關係後端。**T03 整體未完成**；知識／技能 UI、其餘集合、候選、來源及 AI 尚未交付。§1–2 保留第一切片當時的驗證範圍。
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

## 8. 第六切片：共用知識／技能與任務關係後端（2026-09-29）

### 8.1 範圍、研究與 Red

依 JD 指南的 K／S 區分、工具覆蓋 §2.1／4.1 與資料接線，只延伸同一 JD owner，不新增保存／收據服務。先核 PostgreSQL 複合關係約束及 SQLAlchemy association object 的官方機制；選用理由與明確資料圖維護於 [JD 保存 §2.4](../../../implementation/jd-storage.md#24-共用知識技能與任務使用關係)及 §5，非另創通用能力管理平台。

先寫「一筆共用定義供兩任務使用，刪除須先解除」及「原命令結果不等於目前定義」兩個 HTTP／真 PG 反例，實作前 **2 failed**（端點 404，0.51 秒）。接線後兩項轉綠，再擴充契約、純規則、競爭、保存與故障案例。

本切片交付：

- 知識／技能定義的建立、部分更新、刪除、各類概覽排序；名稱／敘述至少一者有內容，允許只有敘述，不強迫編造標題。
- 任務連結／解除、每任務各類關係排序；正文只存一份。反向用途從同一組關係投影，無第二套反向列表。
- 修改定義保留關係；刪任務只解除新稿關係、保留定義；刪職責讓任務未歸屬且保留關係；仍被使用的能力禁止刪除。
- `0008` 固定內容／選用／關係、同檔案同修訂複合 FK、不可變及採用後禁止追加。未變正文重用；排序／關係不重建正文；改回舊字仍有新修訂。
- 人工 HTTP 沿原檔案鎖、准入、CAS、command 與正式結果；原命令在後續改名、刪除或 A 准入後仍回原結果，不復活已刪內容。

### 8.2 已執行驗證

| 層級 | 實測範圍 |
|---|---|
| 新切片 | **43 passed**：18 項 HTTP／真 PG、2 項保存約束、18 項 schema／DTO／adapter、5 項純規則 |
| 後端全套 | **312 passed**、無 skip／警告；213 項真 PG、99 項單元／契約。含既有 schema 升級／metadata 一致性及人工 JD、訪談、准入回歸 |
| 靜態與生成 | Ruff lint／格式（99 檔）、mypy strict（72 source files）、完整 codegen 比對通過 |
| 前端 | 新增兩份生成契約；typecheck、ESLint、Prettier 與既有 **37 項測試**通過；沒有新增畫面或宣稱新的瀏覽器驗收 |

反例包括：八次同命令、四個並行工作重送只產生一份定義；同基底兩個新命令只一方成功；同命令不同意圖／跨類操作拒絕；跨檔案／跨 kind／不存在目標拒絕；非法末態及重複欄位全拒；內容與關係兩種提交前故障都回退所有行、head、原操作，原命令可再送；讀正文後另一請求提交關係仍只回同一固定修訂；原有其他 JD 集合改動保留關係。

同名／同文字不當成同身分；no-op 留原操作但不增修訂，改回舊字則產生新內容修訂。DB 層另直接驗禁止歷史 UPDATE／DELETE、已採用選用／關係禁止追加、關係兩端不能只存在於另一檔案或舊 JD 修訂。這些不宣稱管理員任意 SQL 皆符合業務，也不能代替 T12 的程序強殺／COMMIT 確認遺失 gate。

代表執行命令沿 backend README，使用既有 `.venv-target`：`pytest -q -p no:cacheprovider`，完整 312 項；新增範圍可指定 `test_jd_capabilities.py`、`test_jd_capability_storage.py`、`test_jd_capability_contracts.py`、`test_jd_capability_values.py`。格式交 Ruff，不手改生成檔；schema 仍唯一來源。

### 8.3 審查與未完界線

- 原本為檢查任務身分而讀所有任務正文及明細；審查後改從固定選用只取 ID，移除無用途的全文讀取，不增加 cache／索引服務。
- 生成器對 nullable 文字／create anyOf 的包裝留在 transport 轉型；領域仍用明確 dataclass／enum，不把 generated DTO 或動態字典傳入 service。批次 payload 的推導型別問題以清楚的具名 typed list 修正，沒有 suppression。
- 延用同一 workflow 交易及原操作查詢，不抽 BaseRepository／萬用 CRUD；這是本次 [程式撰寫規範](../../../implementation/coding-standard.md)的實際審查，不因 API 綠燈略過可讀性。
- 保存頁五張 Mermaid 圖均重新渲染；新增 K／S 關係圖實際檢視無裁切／遮擋。圖文明確此為人工正式保存，不冒充 A 候選。八份入口／責任／證據文件的 156 個本機連結及錨點、fences、行尾與 Git diff 檢查通過。

沿 §2 的獨立 PG18.6 測試環境，每測例用自身隨機 schema 並由 fixture 清理，不改原產品 DB；未讀秘密、未呼叫模型，費用 0。沒有新增依賴，沒有啟動新的 App／UI 服務。

**下一步：**知識／技能與關係人工 UI，須使用同版組合查詢，不能拼接 `/work` 與 `/capabilities` 的獨立 latest；再補協作／共通條件及候選。來源／工具跨項目原子能力仍在 T07，Turn 共同正式化在 T08，T03／Goal 均未完成。

## 9. 第七切片：共用知識／技能與任務關係人工 UI（2026-09-29）

### 9.1 範圍與方法

接續 `536ea774`，重用 §8 後端及 §7 UI 的單一命令／固定基底／重讀機制。先核 JD 指南、工具覆蓋的共享 K／S 規則，再核 MUI Select、React／Query 與 Pydantic 官方契約；研究及取捨分別維護在[介面 §1.4](../../../implementation/interface-and-delivery.md#14-t03-共用知識技能及任務關係的人工編輯)及[保存 §5](../../../implementation/jd-storage.md#5-研究依據與本案取捨)。未新增依賴、表、保存 owner、表單框架或搜尋平台。

交付共用定義的增修刪、概覽排序、反向用途；任務的選用／解除及各類關係排序。改共用定義不改關係；刪任務不刪定義；使用中須先解除才能刪定義。改動仍是人工正式編輯，不是 Agent 候選工具。

同版 `/jd/work` 擴充既有 definition／link schema，先固定一次 head，再讀所有相關集合；不由 UI 拼接多個 latest。各元件只處理自身表單或呈現，命令提交及恢復沿同一 hook，沒有為 K／S 另建一份 pending owner。

### 9.2 Red、問題與修正

- 先加同版集合測例，原 `/work` 缺 `capabilities`，**1 failed／1 passed**；前三項 UI 測例因新增／關係控制尚未存在而失敗。補機制後再驗非空集合、並行更新及真畫面，不把空集合轉綠當成功。
- 非空資料實測發現 Python 生成契約的 Enum class 不同，預設 `model_dump()` 跨契約重組會被 Pydantic 拒絕；完整後端當時 **311 passed／1 failed**，兩個瀏覽器旅程也因 GET 500 失敗。核對官方序列化後，在 transport 使用 `mode="json"` 交接 wire 值；沒有改生成檔、放寬型別或略過驗證。
- 修正後瀏覽器的業務步驟成功，但 console gate 發現缺少 `/favicon.ico`。trace 確認不是 API 失敗；補明確的本機 SVG icon，保留原錯誤斷言、不忽略所有 404。完整瀏覽器再驗轉綠。
- 審查移除測例中缺元素時退回整個 document 的容錯；同名物件按穩定 ID 明確驗證，不用「第一個碰巧匹配」當 identity。

### 9.3 已執行驗證

| 層級 | 結果與範圍 |
|---|---|
| 後端全套 | **312 passed**，78.32 秒、無 skip／警告；213 項真 PG、99 項單元／契約。原同版測例擴充為另一請求刪職責、改共用名稱、解除關係後，本 GET 仍保留全部原修訂，下次 GET 才讀新稿 |
| 前端 | **44 passed**，7 個檔；新增 7 項涵蓋描述單獨建立、名稱更新、用途／刪除保護、連結解除、兩類原命令 remount、同名身分、兩種排序與空白／no-op 拒絕 |
| 真 PG 瀏覽器 | **14 passed**，29.3 秒；12 個既有旅程及 2 個新共享編輯旅程，未開自動 retry |
| 靜態／生成／建置 | Ruff lint／格式（99 檔）、mypy（72 source files）、完整生成比對；前端 TypeScript、ESLint、Prettier 及正式 build 通過 |

新瀏覽器旅程透過真 HTTP／PG 驗證：兩任務共用知識、任務另用技能、定義改名反映各用途、概覽排序不改任務關係排序、reload 不丟資料、解除後才可刪、刪任務保留剩餘定義。另一旅程在真提交後丟 HTTP 回應，其他命令先改名；reload 用相同原命令確認，畫面及 DB 仍保留後來新名稱，沒有第二份定義或舊結果覆蓋。

桌面共享定義與 390px 編輯 Dialog 截圖實際檢視，焦點、固定底部儲存入口及文字可讀，沒有水平溢出；正常旅程無 pageerror／console error。保存頁五張 Mermaid 圖以既有 Mermaid 11.17.2／Chromium 流程全部渲染，更新的同版讀取時序圖已視覺檢查，集合／關係及固定修訂方向清楚。

命令沿 App README：後端 `pytest -q -p no:cacheprovider`、Ruff、mypy、`scripts/generate_contracts.py --check`；前端 `test`、`typecheck`、`lint`、`format:check`、`build`、`test:e2e`。新瀏覽器可單跑 `jd-capabilities.spec.ts`，不是以 mock／200 替代效果。

### 9.4 邊界與接續

沿 §2 的 Python／Node／PG 工具鏈；真瀏覽器用獨立合成 namespace `t03_capability_ui_20260929_2210`、loopback API／Vite，未讀秘密、未呼叫模型，費用 0，舊 DB 與入口不動。測試資料保留供診斷，不刪 schema。

前端正式 bundle 742.04 kB（gzip 223.25 kB），仍有既有 >500 kB 提示；不調高閥值掩蓋，整體效能／CSP 與 Ajv 評估依 T15。此為功能切片，不宣稱完整產品安全、長訪談或模型品質通過。

八份入口／責任／證據文件的 165 個本機連結及錨點、fences、行尾與 Git diff 檢查通過。

**下一步：**沿 T03 補協作者／共通條件，再補候選；來源／模型工具在 T07、Turn 共同完成在 T08、程序強殺與提交確認遺失全鏈在 T12。T03 及 Goal 仍未完成，不切換 production。

## 10. 第八切片：協作對象與共通條件後端（2026-09-29）

### 10.1 範圍與研究

接續 `2bf929e6`，完成兩個集合的正式人工讀寫、排序、固定修訂／歷史與原操作恢復；**未接這兩個集合的 UI、模型工具、候選或來源**。沿 JD 指南與工具能力覆蓋的既定欄位／分類，重用同一檔案鎖、准入、短交易、head、operation 及不可變選用，不建立另一套 CRUD 平台。

先查 PostgreSQL 當前 constraints 與 SQLAlchemy 2.1 constraints 官方契約，採既有 text＋具名 CHECK、複合 FK／UNIQUE，沒有為五種類別另增 enum type 管理或框架。責任、研究及增量圖維護在 [JD 保存 §2.5](../../../implementation/jd-storage.md#25-協作對象與全職務共通條件)及該頁 §5，不以單一廠商文件宣稱整份 schema 是業界共識。

協作對象允許只知道合作範圍、不猜名稱；共通條件不新增 title，不自動套用成任務要求。明確更正條件分類保留身分、固定正文新修訂並移到目的分類最後；分類內排序不影響另一分類。這是有界欄位編輯及身分保留，不增加通用動態分類產品。

### 10.2 Red、修正與審查

- 最初兩項真 PG 反例均因端點不存在回 404 失敗；新增 schema、domain、保存／workflow、transport 與 0009 migration 後，兩項與五項 migration 測例全通過。
- 擴充歷史測例時，一處改寫舊測例誤把 profile 的 `job_title` 寫成 `job_name`，**34 passed／1 failed**。核對唯一 schema，修測例回真正 profile 欄位；沒有放寬 API、忽略 422 或移除歷史斷言。
- 完整靜態審查處理格式與長字串，保留 strict 型別及明確錯誤；生成 Python／TS 只從 schema 生成。未修改既有模型工具形狀，未引入額外依賴。
- 新集合接入共用 `insert_revision`，測試改 profile／職責／任務／能力後兩集合仍在，反向修改兩集合也保留其他內容；未改正文只重用固定內容鍵，不完整重存 JD。

### 10.3 已執行驗證

| 層級 | 實測結果 |
|---|---|
| 後端全套 | **381 passed**，103.86 秒，無 skip／警告；258 項真 PG、123 項單元／契約 |
| 新增 PostgreSQL | **45 項**：CRUD、兩類排序、分類更正、同身分改回舊文字、no-op、歷史讀回、空白／錯值全拒、跨檔案、活躍／暫停 A、並行重送／競爭與提交前例外全退 |
| 新增單元／契約 | **24 項**：domain 不靠 HTTP 才拒絕空白、分類 no-op／修訂、重複 change 拒絕、JSON Schema／Pydantic round trip、未知欄位拒絕、內部內容修訂不外露 |
| 既有前端回歸 | **44 passed**，7 檔；本切片未改畫面，沒有冒稱新 UI 已驗收 |
| 靜態／生成 | Ruff lint／format（115 檔）、mypy（85 source files）、全契約生成比對；前端 TypeScript、ESLint、Prettier 通過 |

DB 測例直接驗證：固定正文／選用不能 UPDATE／DELETE；目前、初始及過去已採用修訂不能再追加選用；不同檔案正文／修訂不能接在一起，同版同身分及位置不能重複。回應遺失以原命令回原固定結果，不用最新內容冒充；同時重送只產生一次新增效果。這些不取代 T12 的程序強殺／COMMIT 確認遺失全鏈 gate。

命令沿 backend README：`pytest -q -p no:cacheprovider`、Ruff、mypy、`scripts/generate_contracts.py --check`；前端 `test`、`typecheck`、`lint`、`format:check`。單跑新範圍用 `test_jd_collaborators_conditions.py`、兩個 storage tests、兩個 contracts tests 與 `test_jd_collaborator_condition_values.py`。完整 migration 同樣驗 fresh schema、upgrade 重跑、metadata 與具名約束對照。

保存頁六張 Mermaid 圖均用既有 Mermaid 11.17.2／Chromium 流程渲染；新增固定正文重用圖實際檢視，關係清楚、無文字裁切。八份相關文件的 177 個本機連結／錨點、fences 與 Git diff 檢查通過。

### 10.4 環境、限制與下一步

沿 §2 PG18.6／Python 工具鏈，每測例只建立並清理其自有隨機 schema；沒有讀取／遷移原產品資料、載入秘密或呼叫模型，provider 費用 0。沒有啟動新 API／Vite 服務；本輪未重跑瀏覽器旅程或 provider gate，之前的瀏覽器證據仍屬 §9。

`/jd/work` 尚只含既有集合，下一切片須把協作／條件一併放在同版組合查詢，再接人工 UI 與相應真 PG 瀏覽器。之後續做候選，T07 接來源／模型工具，T08 接共同正式完成；**T03 和 Goal 仍未完成，正式入口不切換**。
