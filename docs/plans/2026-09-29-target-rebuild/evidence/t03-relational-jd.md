# T03 關聯式 JD：施工證據

- 日期：2026-09-29；任務狀態以[任務表](../tasks.md#t03-關聯式-jd-與人工編輯垂直切片)為準。接續 T02 提交 `20e8ecad`，只做新目標，不改根正式入口。
- 已交付 profile 人工 API、不可變正式修訂與原命令結果（`52b55951`），以及下方 §4 的基本資料人工 UI。**T03 整體未完成**；尚無職責／任務集合、候選、來源或 AI 可用聲明。§1–2 保留第一切片當時的驗證範圍。
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
