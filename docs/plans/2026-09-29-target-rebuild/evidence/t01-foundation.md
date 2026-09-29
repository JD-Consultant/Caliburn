# T01 工具鏈與最小契約：實測及接續紀錄

- 記錄日：2026-09-29；任務狀態只由[任務表 T01](../tasks.md#t01-工具鏈契約生成與可測邊界)判定。
- 範圍：T01 基礎機制驗證；§1 保留早期失敗，§3 為修正後證據。沒有真模型請求或產品品質通過宣告。
- 工作位置：`S:\caliburn`；分支 `target-rebuild`，起點 `7e47c133`；規劃提交 `ddae1cfd`。本輪基礎程式與本紀錄共同提交，實際 SHA 可由本檔 Git 歷史取得。

## 1. 早期產物與觀察（歷史，不代表目前仍失敗）

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
| `UV_PROJECT_ENVIRONMENT` | `S:\caliburn\apps\api\.venv-target`（本輪從無環境重新安裝；舊 spike venv 不再使用） |
| Python | `S:\caliburn\apps\api\.venv-target\Scripts\python.exe` |
| Node | `C:\Users\chenb\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe` |
| pnpm | `S:\caliburn\.research-tmp\pnpm-12.5.1\package\bin\pnpm.mjs` |
| pnpm store | `S:\caliburn\.research-tmp\pnpm-store` |
| PG binary zip | `S:\caliburn\.research-tmp\postgresql-18.6-binaries.zip` |

PATH 的原 Node 22.12 不滿足所選工具；使用前先確認 Node 24 路徑。套件精確清單以 manifest／lock 為準，不在此維護另一份。

早期已執行（工作目錄 repo root；保留原失敗的重現路徑）：

```powershell
& 'S:\caliburn\.research-tmp\target-rebuild-api-venv\Scripts\python.exe' apps/api/scripts/generate_contracts.py
& 'S:\caliburn\.research-tmp\target-rebuild-api-venv\Scripts\python.exe' -m pytest apps/api/tests/contracts apps/api/tests/unit -q -o cache_dir=S:/caliburn/.research-tmp/target-pytest-cache
```

生成初次因 sandbox 暫存目錄 ACL 失敗，經工具權限流程重跑成功；此環境錯誤不計 TDD Red。後續 pytest 的 schema 額外欄位失敗才是有效行為反例。沒有因此取得繞過安全限制的長期授權。

PG 來源：[PostgreSQL Windows](https://www.postgresql.org/download/windows/) → [EDB binaries](https://www.enterprisedb.com/download-postgresql-binaries)。下載完成本身不代表 binary 已驗證或 DB 已啟動；後續實際驗證見 §3。不用 SQLite 替代，也不讀舊 `.env` 連既有 DB。

## 3. 修正後實測（2026-09-29）

| 檢查／命令 | 實際結果與限制 |
|---|---|
| 唯一 health schema | 加 `additionalProperties: false`，兩端重新生成，原非法 payload 測例轉綠；不手改 DTO |
| Python 乾淨安裝 | 新建 `.venv-target`；`uv sync --project apps/api --locked --offline` 安裝 80 packages。使用已有下載 cache，但沒有複製舊 venv／site-packages |
| Web 乾淨安裝 | 新建 `.research-tmp/t01-clean-web`，只複製 manifest／lock／新 source／設定；`pnpm install --filter @caliburn/frontend --frozen-lockfile --strict-peer-dependencies --offline --store-dir …` 安裝 243 packages；沒有複製 `node_modules`／`.next`／秘密 |
| 後端測試 | 新 venv：`python -m pytest apps/api/tests -q`，明配隔離 PG，**20 passed**；含真 SDK MockTransport、serializer 及獨立程序 PG probe，沒有 skip。另有 sandbox pytest cache ACL warning，不影響測例結果 |
| Python 靜態／生成 | `ruff check apps/api`、`ruff format --check apps/api`（15 檔）、`mypy --config-file apps/api/pyproject.toml apps/api/src/caliburn`（8 source files）、`python apps/api/scripts/generate_contracts.py --check` 全通過 |
| 後端封裝 | `uv build --project apps/api --offline --out-dir .research-tmp/t01-dist` 產 sdist 及 wheel；不代表正式部署或完整產品已交付 |
| 前端 | 原工作樹 `format:check`／`typecheck` 通過；乾淨安裝 `test` **1 passed**、`build`、`lint` 全通過。build 含 `tsc --noEmit`，Vite 16 modules |
| 實際啟停 | 新 Uvicorn 用 `--factory --loop asyncio:SelectorEventLoop` 在 loopback 58101 啟動；`GET /api/health` 得 `{"status":"ok"}`。Vite loopback 58102 的文件及轉譯 entry 都 HTTP 200；兩個自有程序均已停止 |
| 根產品隔離 | 根 `package.json` 與現行 production 入口未改；workspace 只加入新前端。沒有讀 `.env`、外送原話／金鑰、付費模型、刪除舊 DB 或 volume |

完整一般操作命令見 [backend README](../../../../apps/api/README.md)及 [frontend README](../../../../apps/web/README.md)，此處不另維護第二份 runbook。sandbox 對 Vite 子程序的 `EPERM`、codegen 暫存目錄 ACL 屬環境失敗，經工具權限審查重跑通過；沒有算成有效 Red，也沒有修改產品避開安全限制。

### PostgreSQL／原生接續證據的精確範圍

解壓官方入口取得的 EDB PostgreSQL 18.6，`postgres --version` 確認版本。Windows executable 的 Authenticode 狀態為 `NotSigned`，未取得另行 publisher checksum，**不宣稱已驗簽**。建新 cluster `.research-tmp/postgresql-t01-data`，只綁 `127.0.0.1:55439`、全合成 `caliburn_t01_test`；測試環境 local trust，不作部署認證範本，不停用 fsync。

`test_graph_postgres.py` 在隨機 schema 內執行官方 `AsyncPostgresSaver.setup()`：第一程序完成模型 node 後，`sync` 保存三種原生 items 並在工具觀察前中斷；第二個全新程序取回相同 items／下一節點，追加配對工具結果，**沒有重新執行模型 node**，另一 thread 讀不到。測試只清除自己新建 schema；驗證後確認 cluster PID／data directory 再正常停止，保留 cluster 檔案。這不是 crash-injection、業務效果 exactly-once、取消或 COMMIT 結果不明的驗收；後者留 T06／T12。

SDK 測例以 `httpx2.MockTransport` 攔截 `openai.invalid`，保留 `model_dump(mode="json")` 的完整 items，包括 synthetic encrypted content、`phase`、未知 metadata 及 `call_id`。下一請求保留原生歷史，`store=false`／`all_turns`，無 `previous_response_id`；完整 compact window 的保留 items 也通過 serializer round trip。**沒有真正推論／壓縮，也未驗遠端帳戶接受性**。

### 研究後修正，而非掩蓋失敗

- [typescript-eslint 支援矩陣](https://typescript-eslint.io/users/dependency-versions/)及套件 registry peer metadata：TS 7 超出範圍，改鎖 TS 6.0.3／typescript-eslint 8.70.1；移除自動加出的 release-age exceptions，strict peer 安裝成立。
- [OpenAI stateless reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-without-stored-responses)：用完整原生 items 接續，依鎖定 SDK 3.20.0 的 httpx2 transport 寫測例；未將它轉成 LangChain Messages。
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：使用官方 PG saver，不另寫保存引擎。
- [Psycopg Windows async 限制](https://www.psycopg.org/psycopg3/docs/advanced/async.html)及已裝 3.3.6 的實際錯誤：Proactor 不支援。改用 [Python loop factory](https://docs.python.org/3.14/library/asyncio-runner.html)，不用棄用 policy；Uvicorn 0.54.0 安裝原碼與啟動實測確認可用 import-string factory。
- [Playwright Windows 子程序](https://playwright.dev/python/docs/library#incompatible-with-selectoreventloop-of-asyncio-on-windows)需要 Proactor；T13 的接縫已記入[交付設計](../../../implementation/interface-and-delivery.md#4-pdf-與程序)，尚未提前實作 renderer。
- Web lint 起初誤掃舊 ignored `.next`，造成大量生成物錯誤；只排除生成物，不刪舊目錄。SDK fixture 一度缺 `cache_write_tokens`，修正合成 fixture，不把它當產品 bug。

### 套件授權與版本

此表記本輪 installed package metadata 的授權，不是正式散布審查。完整精確相依以 `uv.lock`／`pnpm-lock.yaml` 為準；工具鏈 CPython 3.14.7、uv 0.12.20、Node 24.19.0、pnpm 12.5.1。

| 本輪主要依賴 | metadata license |
|---|---|
| FastAPI 0.141.1、Pydantic 2.13.5、LangGraph 1.2.12、checkpoint-postgres 3.1.2 | MIT |
| OpenAI 3.20.0、TypeScript 6.0.3 | Apache-2.0 |
| Uvicorn 0.54.0、httpx2 2.13.1 | BSD-3-Clause |
| psycopg／psycopg-binary 3.3.6 | LGPL-3.0-only；T18 交付需保留其及 bundled native dependencies 所需 license／notices，不把它們一概記成 MIT |
| React／React DOM 19.3.0、Vite 8.3.1、Vitest 5.0.2、ESLint 10.11.0、typescript-eslint 8.70.1 | MIT |
| datamodel-code-generator 0.83.0、json-schema-to-typescript 16.0.0、Ruff 0.16.9、mypy 2.3.1、Prettier 3.9.9 | MIT |

## 4. 接續，不重做 T01

T01 gate 的基礎機制已成立；其覆蓋不升格為 V／E／JDT 全產品通過。下一個具備前置條件的任務是 T02：先讀產品、正式訪談資格與資料交易契約，研究 SQLAlchemy／Alembic 的現行接法，再以重送／隔離／取消不佔序號／執行准入反例開發。T06 也已具備前置條件，仍需自己的執行契約及測例，不能直接把本 probe 當 runtime。

已有相容組合與離線測例可直接重用；不因 Goal 縮短重新下載、廣搜或開付費測試。T01 沒有需 Owner 重新裁決的產品語意阻塞。

提交前文件檢查：15 份相關文件、129 個本機連結、25 個錨點、fences／行尾空白通過；新 lock 的既有 workspace importers 與 HEAD 完全相同。`git diff --check` 通過，沒有更改 Mermaid 圖形或重做渲染。
