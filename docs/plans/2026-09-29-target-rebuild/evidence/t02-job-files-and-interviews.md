# T02 職務檔案與訪談資格：實測及接續紀錄

- 日期：2026-09-29；狀態由[任務表 T02](../tasks.md#t02-職務檔案正式訪談與執行准入)維護。第一切片為建立／讀取／開場保存；第二切片見 §6 輸入／准入，**不是 T02 全部完成**。
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

**第一切片當時未完：**輸入接受／執行准入於 §6 續補；目前仍欠受控正式化、來源區間底層與建立／列表 UI。A 完整成功提交與取消／候選回退仍在 T08；無假完成／任意新增正式訪談 endpoint。正式帳號權限、瀏覽器入口保護與端到端故障仍須 T12／T15／T18，不拿 TestClient 通過當產品交付。

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

1. T02 受控正式化與序號／範圍查詢：原輸入依 execution 精確取回，完成協調才分配員工與答覆的正式序號；測取消後接續仍不佔號、來源資格、K／H／F 與前問。不能新增 UI 任意正式化 API；完整 JD／背景意圖同次生效留 T08 接線。
2. 加入建立／列表 UI，沿 React Router／Query 的既定責任及來源 schema；之後才能補齊 T02 gate。不要重做已成立的建立／接受交易。
3. T08 接入現有 writer／准入 service 時，控制意圖、Graph 恢復、候選與原生基底回退仍須逐項驗；不能把 §6 的終態競爭當完整 A final／取消已驗。

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
