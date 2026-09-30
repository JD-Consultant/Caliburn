# T10：B1／B2 角色工具 schema 預檢

## 外送 manifest（執行前記錄）

- 記錄時間：2026-09-30 10:56 Asia/Taipei；Owner 本次明確授權適用。
- 範圍：新目標 B1 `work_situation_analyst`、B2 `work_understanding_analyst` 的實際 canonical function definitions；沿 `function_definition` 讀取權威 schema 的生成副本，不由 Pydantic 重建、不造 dummy binding。
- 外送內容僅為工具定義及全合成短訊息：instructions = `Synthetic schema validation only.`；user = `Validate the tool schema.`。不含員工／JD／正式訪談／資料庫內容。
- 模型：`gpt-6-luna`，reasoning effort `medium`；正式 OpenAI Responses input-token count endpoint。
- 上限：每角色一次 count，合計最多 **2 次 HTTP 嘗試**；每次 timeout **30 秒**；**0 generation、0 retry**，禁止 redirect。
- key 僅由 `read_openai_api_key` 讀取 `apps/api/.env`，不顯示、不寫證據；不讀取其他環境或金鑰來源。
- 不宣稱 count 免費；本記錄不是費用帳單，若回傳 input_tokens 也不將其冒充生成 usage／結算金額。
- 屬 [T08 同批 demo manifest](t08-consultant-turn.md#51-真模型背景旅程-manifest執行前) 的兩次預檢，不重設／另加生成預算；沿該批總成本上限。count 費用尚未核實，不把其未知費用記為零。
- 400 或其他失敗先停下記錄，離線研究原因，不盲重試、不擴大本次外送額度。
- 接受條件：兩角色的 count 請求各一次被 API 接受。這僅證明所送 strict tool schema 在 count 路徑可接受，不證明真訪談品質、生成／工具選擇品質，也不是 T10 或全 gates 完成。

## 結果

離線 Red：新增 helper／role 參數前，8 個窄測試依預期失敗。Green：相同窄測加既有路由、權限及 import boundary 共 **31 passed**（1.43s）。Mock HTTP 已驗兩角色 canonical definitions、一次 count、30 秒、400／503 即停止且不按 retry header 重送、輸出不洩露 key。

### 真 API count（2026-09-30 10:59 Asia/Taipei）

| 角色 | 工具數 | API count 接受 | input_tokens | HTTP 嘗試 | generation／retry |
| --- | ---: | --- | ---: | ---: | --- |
| B1 `work_situation_analyst` | 6 | 是，程序 exit 0 | 1,780 | 1 | 0／0 |
| B2 `work_understanding_analyst` | 8 | 是，程序 exit 0 | 2,030 | 1 | 0／0 |

總計 **2 HTTP、0 generation、0 retry**；各 30 秒 timeout 並另有同長度的總等待界線，未逾時、未有 400，沒有 rerun。兩次授權額度已用完。input_tokens 是供應商 count 回值，不是已結算費用；未宣稱 count 免費。

完整 definitions 的 SHA-256（UTF-8 JSON，`ensure_ascii=False, sort_keys=True, separators=(",", ":")`）：

- B1：`a249b15d9323df25bfaf5dc471e5e6a4d0fd81beecf124cf1ea104e5df3cb7d8`
- B2：`96b7aaca8aa3199d0ef45c25bacc7af25d274170cf8924639c2667e3a42bb8bc`

B1 為 `read_work_situation_map`、`read_work_situation`、`read_interview`、`create_work_situation`、`update_work_situation`、`delete_work_situation`。B2 另可讀 `read_work_understanding_map`／`read_work_understanding`，三項 write 則只限 `work_understanding`。沒有新增同義工具、B1 理解讀取權限或 B2 情境寫入權限。

實測命令（cwd `apps/api`；**本次已執行，非待辦，不要自動重跑**）：

```powershell
./.venv-target/Scripts/python.exe -B scripts/probe_consultant_tool_schema.py --role work_situation_analyst --key-file .env
./.venv-target/Scripts/python.exe -B scripts/probe_consultant_tool_schema.py --role work_understanding_analyst --key-file .env
```

### Canonical definitions 接縫

- `workflows/memory_analysis/tools.py`：`memory_analysis_tool_definitions(layer: MemoryLayer)`，無 binding、DB、dummy service 或新 registry。
- `transport/model_tools/memory_reads.py`：`memory_read_names(layer=None)` 與既有 `memory_read_definitions(names=...)`；bound `MemoryReadTools.names` 委派同一權限選擇。
- `transport/model_tools/memory_writes.py`：`memory_write_names(layer)`／`memory_write_definitions(layer)`；bound `MemoryWriteTools` 委派同一名稱及定義。原 descriptions、parameters、strict、路由、錯誤及效果不變。
- 兩角色 runtime 仍組合這兩個實際工具 class；探針只組合其相同 helper。測試逐項比較完整 definitions 與 names，無複製 schema。所有 parameters 沿 `function_definition`；權威／生成 JSON schema 都沒有修改，也未執行 codegen。
- `scripts/probe_consultant_tool_schema.py --role` 預設仍為 `consultant`；本次未執行 A 預檢。

離線驗證命令（cwd `apps/api`）：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_memory_schema_probe.py tests/unit/test_memory_analysis_tools.py tests/unit/test_import_boundaries.py tests/contracts/test_memory_read_tool_dispatch.py -q -p no:cacheprovider --tb=short
```

交付前再驗同組 **31 passed（1.58s）**；五個改動 Python 檔案 Ruff 通過，三個 runtime module 與探針共四個檔案 mypy 通過；未放寬 import boundary 測試。

未判定／未宣稱：真訪談分析品質、真生成工具選擇、全 T10／T16／全部 gates。這些不是 count endpoint 可驗的效果；本次不啟動訪談、不接觸 DB、不發布候選。
