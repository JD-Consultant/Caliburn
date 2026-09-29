# T03 關聯式 JD：施工證據

- 日期：2026-09-29；任務狀態以[任務表](../tasks.md#t03-關聯式-jd-與人工編輯垂直切片)為準。接續 T02 提交 `20e8ecad`，只做新目標，不改根正式入口。
- 已交付 profile 人工 API、不可變正式修訂與原命令結果（`52b55951`）、§4 基本資料人工 UI（`32e3ea5e`），以及 §5 職責集合後端。**T03 整體未完成**；職責 UI／任務集合、候選、來源及 AI 尚未交付。§1–2 保留第一切片當時的驗證範圍。
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
