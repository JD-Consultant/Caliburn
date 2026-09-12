# 關聯式 JD：隔離編輯核心

此目錄承接[新版施工計畫](../../docs/plans/2026-09-13-jd-relational-app-implementation.md)的 RS-1 首切片。它驗證完整任務建立、一次相依內容更正，以及員工／模型共用規則；框架選擇可替換，產品效果以既有六章 JD 研究為準。

**目前沒有可開啟的 App 畫面，也沒有寫入資料庫。**`build_candidate` 回傳保存前的關聯資料候選，保留原 revision；不得把它當已保存結果或可反覆提交的 operation。它不讀寫 Memory／訪談、不呼叫模型、不接正式產品或舊實驗模組。

## 結構

- `contracts/jd-work.schema.json`：兩工具輸入的唯一 JSON Schema。
- `src/jd_relational/generated`：標準工具生成 Python DTO／TS 型別，禁止手改。
- `transport.py`：人工與模型轉入同一 command；兩家工具外殼不同。
- `domain.py`：同文件／同 base refs、完整候選、正文／引用／排序／来源規則，沒有 SQL 或 SDK。
- `tests`：合成工作、格式正反例、共同操作流程、真 SDK 的離線請求捕捉。未完整任務不強迫補欄；多成果和多要求不配對。

## 重現

本單位驗證 Python 3.12.13、Node 24.19.0。使用此目錄的 lock；不修改正式 App 依賴。安裝公開套件後，測試可以全程離線且不需要模型金鑰：

```powershell
uv sync --frozen
npm ci --ignore-scripts --no-audit --no-fund
uv run --frozen --offline python scripts/generate_contract.py --check
uv run --frozen --offline pytest -q -p no:cacheprovider
node node_modules/typescript/bin/tsc -p tsconfig.json
```

若工具預設暫存目錄不可寫，將 uv 的 `--cache-dir` 指到可寫位置。`NODE_BINARY` 可指到正確的 Node 執行檔；在本機不要依賴全機舊版 npm wrapper 選中的 Node。產生器只用標準 CLI stdout，`--check` 不寫生成物。

SDK 測試使用 `httpx2.MockTransport`、固定假 key 與 `offline.invalid`，封鎖 sockets 及環境／本地帳號探索；8 個測試 POST 都在程序內攔截。這只證明 SDK 序列化，未證明 provider 接受或模型自然選用。

## 待接責任

`Ref`／`Source` 為 App 注入的合成已驗讀取材料；正式 refs 發配、讀取 DTO、HTTP envelope、operation／未知結果、其他具名 CRUD、資料庫交易、畫面、顧問 runtime 在後續切片。正式保存格式仍以十三表與 immutable revision 設計為準；此 probe 的 dict 不是另一份文件 authority。

依據、來源 digest 精確化、通過界線及首敗／最後結果見[切片設計與結果](../../docs/specs/2026-09-13-jd-relational-command-slice.md)。
