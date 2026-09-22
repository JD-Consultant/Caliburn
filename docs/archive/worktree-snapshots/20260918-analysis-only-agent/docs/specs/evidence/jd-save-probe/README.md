# P01 固定保存驗證：封存與重現

2026-09-09；[結果、覆核與效力邊界](../2026-09-09-jd-native-save-probe.md)。這是隔離研究腳本，不是 production migration／repository、LLM 工具 schema 或審閱政策。

## 檔案與資料

- `PROTOCOL.md`、`node_bridge.mjs`：固定 stdin／stdout JSON；追加文字、新增段落、空命令。失敗不返回部分候選；Node 沒有 DB 或檔案保存副作用。
- `fixture.json`：完整虛構 r2，保留前次 fixture 的合成 metadata。直接使用此檔即可；`export_fixture.mjs` 只是從前次 UI fixture 重新匯出的沿革工具。
- `save_probe.py`：Python 執行固定 Node 程式，保存 `jd_head`／`jd_revision`／`jd_operation`，並執行有限失敗注入與外部重開檢查。
- `local_connection.py`：讀既有本機指定容器的連線設定，憑證只留程序記憶體，不輸出。固定 `127.0.0.1:55433`／`jd_editor_probe_p01_20260909`。
- `provision.py`：一次性建立隔離 DB；已存在會停止，不是可 import 的連線函式。建立前來源與建立後空 schema 見 `results/provision.json`。
- `results/first-run-save_probe.py` 與 `save-probe-20260909T141142Z.json`：首輪實際原碼及有限結果；未覆寫成後來的斷言。
- `results/save-probe-20260909T142102Z.json` 與同名 `-snapshots.json`：第二輪六組固定情境結果及完整乾淨值／回執；新程序重開、writer commit 後退出均實際執行。初輪不足與效力界線仍依結果報告。
- `results/runtime-inventory.json`：實裝 runtime／Python package 授權 metadata。沒有憑證、員工資料或模型請求。

只保存乾淨 value；原生 operations 是操作記錄，不作為可重播的正式文件。JSON 雜湊使用腳本內固定 UTF-8／sorted-keys 表示，僅用於本驗證的完整值比對。

## 重現路由

在可寫暫存根下還原以下相鄰目錄；不要直接在此 evidence 目錄執行而覆蓋封存结果：

```text
暫存根/
  jd-editor-save-probe/      本目錄的副本
  jd-editor-native-probe/    ../jd-native-probe 的 package.json 與 package-lock.json
```

Node bridge 固定解析 `../jd-editor-native-probe/package.json`。在第二個目錄依鎖檔安裝可重現相同依賴；本輪沿用既有安裝，沒有再下載套件。若只重跑保存驗證，不必重建 UI 或匯出 fixture。

```text
cd <暫存根>/jd-editor-native-probe
npm ci --ignore-scripts --no-audit --no-fund
cd ../jd-editor-save-probe
<Python 3.12.13，已具 psycopg[binary] 3.3.5> save_probe.py run
```

Python 與 Node 都須可從本機啟動；`save_probe.py` 使用固定 Node 檔案，沒有 shell 執行或模型提供的程式碼。本機連線 helper 依既有 `caliburn-q019-postgres` 容器設定工作；執行前須核對為同一明確測試 DB。新環境若尚無該 DB，可先執行一次 `provision.py`；既有 DB 則先核對來源是 P01 建立，不能靠同名就清空或覆蓋。腳本只 `CREATE TABLE IF NOT EXISTS` 及新增本輪 UUID 文件，不使用 DROP／TRUNCATE。沒有自動清理既有證據資料。

每輪結果另存新時間檔；重新執行會新增本輪文件，不能把新結果覆寫為原結果。原始腳本、結果及 fixture 雜湊由封存 manifest 比對。重現不需要真 LLM、訪談資料、Saver／Store tables 或 production runtime。

## 固定版本與免費開源範圍

| 實裝元件 | 版本 | 已核對授權 |
|---|---|---|
| Python | 3.12.13 | PSF-2.0；內含其他元件另依各自 notice |
| psycopg／psycopg-binary | 3.3.5 | LGPL-3.0-only；binary 包含的第三方庫另依其授權 |
| typing-extensions／tzdata | 4.16.0／2026.3 | PSF-2.0／Apache-2.0 |
| Node.js | 22.12.0 | MIT；內含第三方 notice 另列 |
| platejs／@platejs/core | 53.3.11 | MIT |
| @platejs/slate／slate／slate-react | 53.3.10／0.126.2／0.126.4 | MIT |
| React／React DOM | 19.2.4 | MIT |
| PostgreSQL server | 16.14 | PostgreSQL License；未升級既有 server |

查閱日 2026-09-09。Python 實際使用 psycopg `binary` implementation，libpq 客戶端版本為 `180004`；**不是 PostgreSQL server 升到 18**。Node 完整 transitive pin 依[前次 lock](../jd-native-probe/package-lock.json)及[套件授權盤點](../jd-ui-probe/results/license-inventory.json)，不是把全部依賴概稱 MIT。P01 未使用 diff，但前次環境中 `@platejs/diff` 的 Apache-2.0／MIT 實際授權說明仍保留。

固定官方來源：[Python LICENSE](https://github.com/python/cpython/blob/v3.12.13/LICENSE)、[psycopg 3.3.5 metadata](https://github.com/psycopg/psycopg/blob/3.3.5/psycopg/pyproject.toml)、[Node LICENSE](https://github.com/nodejs/node/blob/v22.12.0/LICENSE)、[PostgreSQL License](https://www.postgresql.org/about/licence/)。套件授權與驗證結果不代表付費 editor 功能已納入可採用方案。
