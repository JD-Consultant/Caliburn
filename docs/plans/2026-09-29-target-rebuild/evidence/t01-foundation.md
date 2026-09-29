# T01 工具鏈與最小契約：實測及接續紀錄

- 記錄日：2026-09-29；任務狀態只由[任務表 T01](../tasks.md#t01-工具鏈契約生成與可測邊界)判定。
- 範圍：本次 Goal 整理前已進行的 T01 工作。本次整理沒有重跑產品測試、發送真模型或宣告 T01 通過。
- 工作位置：`S:\caliburn`；分支 `target-rebuild`，起點 `7e47c133`。既有規劃文件與新骨架尚有未提交差異；接續先核 dirty，不清除、不把他人變更一併提交。

## 1. 已有產物與實際觀察

| 項目 | 已觀察結果 | 未完成／不能推導 |
|---|---|---|
| Python 環境 | 隔離 uv 0.12.20、CPython 3.14.7；`apps/api/uv.lock` 與依賴安裝完成 | 不等於所有套件組合相容；完整 lint／typecheck／乾淨重建待驗 |
| Web 環境 | Node 24.19.0、pnpm 12.5.1；`@caliburn/frontend` 安裝完成 | TypeScript 7.0.2 超出 typescript-eslint 8.71.0 的 `<6.1.0` peer 範圍；須先解決，不忽略警告 |
| 最小契約 | health JSON Schema 產 Python／TS；FastAPI health 與靜態前端骨架已建立 | health 只表示程序存活，不能當成 DB／模型／訪談可用 |
| Import 反例 | 原空實作有 8 個禁止依賴測例失敗；加入小型 AST 檢查後，這組反例已通過 | 非動態 import 或全產品依賴安全的證明 |
| 後端最近測試 | contracts＋unit：**15 passed、1 failed** | 額外欄位 payload 被 schema 接受；這是有效 Red，不得刪除該測例 |
| PostgreSQL | Docker Desktop GUI 啟動但 engine pipe 不可用；已從官方 Windows 下載入口取得 EDB PostgreSQL 18.6 binary zip | 尚未驗包／解壓／建立隔離 cluster，沒有真 PG／saver 通過證據 |
| OpenAI／LangGraph | 核過已安裝 SDK 原碼及 saver 介面 | 尚未做 fake SDK 原生 items round trip、真 PG saver 或遠端 API 測試；未讀取憑證 |

SDK 3.20.0 使用 `httpx2`；fake transport 須依該 SDK 的真實型別接線，不能直接假定開發測試用的 `httpx==0.28.1` client 可交給它。已核到 `httpx2.MockTransport`，但測試尚未完成。官方 saver 的 `setup()` 與新程序 round trip 仍須實跑。

## 2. 可接續的環境與命令

下列是本機已使用位置，不是交付給一般使用者的固定安裝路徑；暫存目錄可能不存在，接續須先核實。

| 用途 | 路徑 |
|---|---|
| uv | `S:\caliburn\.research-tmp\bin\uv.exe` |
| `UV_CACHE_DIR` | `S:\caliburn\.research-tmp\uv-cache` |
| `UV_PYTHON_INSTALL_DIR` | `S:\caliburn\.research-tmp\python` |
| `UV_PROJECT_ENVIRONMENT` | `S:\caliburn\.research-tmp\target-rebuild-api-venv` |
| Python | `S:\caliburn\.research-tmp\target-rebuild-api-venv\Scripts\python.exe` |
| Node | `C:\Users\chenb\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe` |
| pnpm | `S:\caliburn\.research-tmp\pnpm-12.5.1\package\bin\pnpm.mjs` |
| pnpm store | `S:\caliburn\.research-tmp\pnpm-store` |
| PG binary zip | `S:\caliburn\.research-tmp\postgresql-18.6-binaries.zip` |

PATH 的原 Node 22.12 不滿足所選工具；使用前先確認 Node 24 路徑。套件精確清單以 manifest／lock 為準，不在此維護另一份。

最近已執行（工作目錄 repo root）：

```powershell
& 'S:\caliburn\.research-tmp\target-rebuild-api-venv\Scripts\python.exe' apps/api/scripts/generate_contracts.py
& 'S:\caliburn\.research-tmp\target-rebuild-api-venv\Scripts\python.exe' -m pytest apps/api/tests/contracts apps/api/tests/unit -q -o cache_dir=S:/caliburn/.research-tmp/target-pytest-cache
```

生成初次因 sandbox 暫存目錄 ACL 失敗，經工具權限流程重跑成功；此環境錯誤不計 TDD Red。後續 pytest 的 schema 額外欄位失敗才是有效行為反例。沒有因此取得繞過安全限制的長期授權。

PG 來源：[PostgreSQL Windows](https://www.postgresql.org/download/windows/) → [EDB binaries](https://www.enterprisedb.com/download-postgresql-binaries)。下載完成不代表 binary 已驗證或 DB 已啟動；不用 SQLite 替代，也不讀舊 `.env` 連既有 DB。

## 3. 下一個可執行步驟

1. 修 health 唯一 schema 的額外欄位約束，重新生成 Python／TS，再驗原失敗測例；不手改生成 DTO。
2. 研究並鎖受支援的 TS／lint 組合。已找到 TS 6.0.3、typescript-eslint 8.70.1 作候選，尚未套用或通過；核 registry／peer 後再選。pnpm 曾自動加入 release-age exceptions，應隨相容組合處理，不以永久繞過檢查解決。
3. 完成前後端格式、lint、typecheck、unit、build、`codegen:check`；補 SDK fake transport 原生項目往返。
4. 先確認 Docker engine 是否已可用；仍不可用可完成官方 binary 的隔離 PG 測試環境。不要反覆重啟或停止不明使用者程序；只用新建測試資料，驗官方 saver／新程序恢復。
5. 補實際啟動／生成命令與新路徑 README，驗乾淨安裝，再依 T01 gate 記證據、審查及完整本地提交。T01 未通過前不勾完成、不切換根 production 入口。

本次沒有等待 Owner 決策的已知阻塞；以上是可繼續解決的工程工作。Goal 分層整理不重置這些進度，也不把舊環境或付費證據全部重新執行。
