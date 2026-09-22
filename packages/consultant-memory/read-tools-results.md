# Memory 原生只讀工具採用結果

查閱與驗證：2026-09-13，基準 `81a1ca76`。提供 `caliburn_memory.read_tools.readonly_file_tools(backend: BackendProtocol) -> list[BaseTool]`，供 App 對固定 Memory reader 建立 `ls`、`read_file`、`grep`。

## 採用與限制

- 提取原 checkout `033540cef870d1f92baa5c69133a799231c46d48` 的 `analysis_agent/memory_tools.py` 中 `READONLY_TOOL_DESCRIPTIONS`／`readonly_file_tools`；只移除本輪沒有採用的 Skill 檔案宣稱，註解改為 provider 無關。没有採用舊來源、SkillAssets、runner、provider 或寫入工具。
- 以已安裝 MIT [Deep Agents 0.7.13 的官方原碼](https://github.com/langchain-ai/deepagents/blob/deepagents%3D%3D0.7.13/libs/deepagents/deepagents/middleware/filesystem.py)核對：public `tools` allowlist 實際只建立三個工具，schema、sync／async backend 呼叫、行號、分頁及 `ToolMessage` 錯誤均由原生實作提供。`4000` token 設定同時供原生文字分頁使用；沒有另外實作讀取分頁器。
- 只回傳工具實例，沒有向 agent 註冊 `FilesystemMiddleware`，因此本接點沒有自動 offload 或對話 scrubbing hooks。官方 constructor 會配置 glob executor 物件，但此 allowlist 不建立 glob 工具、不提交 glob 工作；沒有操作其私有生命週期。
- 官方 0.7 已移除 backend factory。實際傳入 lambda 的離線探針回 `TypeError: backend must be an initialized backend instance. Backend factories were removed in deepagents 0.7; pass StateBackend(), CompositeBackend(...), or another BackendProtocol instance instead.` 不把舊 factory 介面加回本套件。
- App 如需在當輪挑選固定 reader，可沿已安裝 LangGraph 1.2.11 的 `ToolCallRequest.override(tool=...)` 替換原生工具實例；`_ToolCallRequestOverrides` 明列 `tool`，ToolNode 執行使用該實例並保留 runtime 注入。這是 App 接點，本 factory 本身不決定目前版或保存任何第二份狀態。已對三個工具驗證此路徑。

## 實測

環境為新 JD App 正式 editable 依賴及其鎖定的 Python 3.12、Deep Agents 0.7.13、LangChain 1.4.0／core 1.6.3、LangGraph 1.2.11，沒有使用舊 worktree 環境。

| 範圍 | 實際結果 |
|---|---|
| 實作前首敗 | 1 collection error／9.08s：`ModuleNotFoundError: caliburn_memory.read_tools` |
| 初始 native 工具驗證 | 10 PASS／6.21s |
| 原核心44＋工具11（加入 factory 拒絕反例） | 55 PASS／5.30s |
| 最後工具14（另加3個原生 override 接點） | 14 PASS／6.49s；未重跑無關44案 |

14案涵蓋：實際原生 schema 與 allowlist、移除 factory 的版本界線、三工具 `override` 保留真 graph state／Store／config、offset 行號與原 Human 不變、缺檔／不合法路徑 error status 與 call ID、writer 不可 dispatch、固定 reader 不追後來版本、literal grep／可見檔案、跨文件拒絕、完整長繁中原生續頁／不新增 Store 檔案，以及原生非同步讀取。

可重跑（工作目錄 `experiments/jd-relational-app`）：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest ../../packages/consultant-memory/tests/test_read_tools.py -q -p no:cacheprovider
```

原始首敗及最後輸出保留於 `.research-tmp/jd-memory-read-tools-first.txt`、`jd-memory-read-tools-package-final.txt`、`jd-memory-read-tools-override-final.txt`；factory 探針為 `jd-memory-read-tools-factory-probe.txt`。本輪使用真原生 ToolNode／InMemoryStore，沒有 provider、DB、服務或自然模型；不能代稱 App 完整 Memory 訪談已通過。

## MR-R01／P2：參數驗證錯誤不得回傳整包輸入

另一位審查者以原生 `read_file(offset="PRIVATE_INPUT_MARKER")` 發現，ToolNode 預設驗證錯誤會在 `ToolMessage` 帶入完整 kwargs。本包先加入 `ls` 非文字 path、`grep` 非文字 pattern、`read_file` 非整數 offset 三個反例，首跑 **3 FAIL／4.24s**，均在錯誤內容發現合成 marker；原始輸出 `.research-tmp/jd-memory-read-validation-first.txt`。

修正只使用已安裝 LangChain core 1.6.3 的 public `BaseTool.handle_validation_error` 字串設定。三個 factory 產物都回固定 `invalid_input` 提示，由原生 BaseTool 處理 Pydantic 錯誤，保留 `ToolMessage.status="error"`、工具名稱及原 call ID；沒有自製 validator、改 schema 或文字讀取格式。App 的 canonical 與當輪 replacement 均沿同一 factory。其他正常結果及 backend 錯誤維持原生行為；上文「保留原生錯誤」的例外限此安全驗證提示。

最後工具全組 **17 PASS／4.38s**，含三個反例與既有 native／override／分頁／scope／async 案例；未重跑無關 Memory 核心。輸出 `.research-tmp/jd-memory-read-validation-final.txt`，零 provider／DB。修正已交原審查者窄複核。
