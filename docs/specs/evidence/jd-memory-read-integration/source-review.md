# Memory 唯讀工具與原話接合：獨立窄審

日期：2026-09-13。範圍為 [package read_tools](../../../../packages/consultant-memory/src/caliburn_memory/read_tools.py)、[App memory_read_tools](../../../../experiments/jd-relational-app/src/jd_relational/memory_read_tools.py)、[memory_context](../../../../experiments/jd-relational-app/src/jd_relational/memory_context.py) 的固定 session／tool override，以及 [AiToolMiddleware](../../../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py) 的實際邊界。沒有修改以上產品或作者測試；不將自己的 [checkpoint 實作](checkpoint-results.md) 算作獨審。

## 結論與必要修正

**結論：限定範圍 PASS。MR-R01／P2 已由原作者修正，並經本審查者窄複核 CLOSED；沒有其他可重現的 P1／P2。**

MR-R01 原缺口：原生檔案工具驗證失敗仍回傳整份 kwargs。

具體位置：`read_tools.py:56–68` 直接回原生工具，沒有設定固定 `handle_validation_error`；`memory_context.py:165–168` 每次選用相同工廠的 replacement。`consultant_tools.py:430–435` 只遮例外；原生 ToolNode 已轉成 error ToolMessage 的回覆會直接返回。

零 provider 的原生 StateGraph／ToolNode 反例：用已保存合成 Memory 建 `readonly_file_tools(artifacts.reader(version))`，發出 `read_file` 原 call id `original-call`，參數 `{"file_path":"/memory/knowledge.md","offset":"PRIVATE_INPUT_MARKER"}`。結果 status 為 `error`、name／call id 正確，但內容為：

```text
Error invoking tool 'read_file' with kwargs {'file_path': '/memory/knowledge.md', 'offset': 'PRIVATE_INPUT_MARKER'} with error:
 offset: Input should be a valid integer, unable to parse string as an integer
 Please fix the error and try again.
```

`assert 'PRIVATE_INPUT_MARKER' not in message.content` 首次 **FAIL，exit 1／7.95 秒**。這是固定合成 marker，不含秘密。已檢查安裝版 LangGraph `ToolInvocationError`／預設 handler：其格式確實包含原 call kwargs；不是猜測框架行為。

原作者已採最小修正：同一 package factory 對三個原生工具設定固定 `handle_validation_error`；canonical 工具與 session replacement 一起受益，保留原生 schema、執行函式、格式與分頁。以原生工具的 public 接點補三種壞輸入＋固定 call id／error status 反例，不新增 validator、middleware hook 或工具執行迴圈。

本審查者讀過修正後，獨立執行新增 validation 三例：**3 PASS／6.18 秒，14 deselected**；再原樣執行上面的 `read_file` marker probe，**PASS，exit 0**，回覆固定 `invalid_input` 且不含 marker，原 name／call id／error status 均保留。作者另記的首 3 FAIL 與 package 最終 17 PASS 在 [package 結果](../../../../packages/consultant-memory/read-tools-results.md)，不算作本審查者重跑或相加。

## 已核對的責任與證据

- **固定讀取 scope：** App 的 `memory_session` 核對 context 的 dataset／document／run、native thread、實際 Store identity、state 的原 Memory view 及 stop Event，才給 session backend。官方 `request.override(tool=...)` 只換成本輪固定 backend 的原生工具；不接受模型傳 backend、scope 或版本。schema-only backend 的讀取一律拒絕。
- **原話及角色：** `read_conversation` 的模型 schema 只包含 reference／offset／part；ToolRuntime 由原生 ToolNode 注入。直接引用沿已簽來源 owner；summary 路徑先驗 UUID 形狀，再由採用核心的 `source_window` 讀固定 metadata，沒有重造來源或來源表。assistant 段明示為上下文，沒有改成員工確認。
- **完整續頁：** 每頁最多 3000 Unicode 字元，offset 是固定 excerpt 的全段位置，另保留 message id／role／原訊息內 text_offset。跨訊息、CRLF、繁中、emoji／combining character 的三頁重組與原文相同；end offset 回空頁，越界／bool／非整數回固定輸入錯誤。offset 不傳给 source owner 作新定位，沒有選新版。
- **錯誤歸因：** App 原話工具的 invalid input／invalid ref／指定 summary 缺失回固定 ToolException；不回輸入 marker。未知 ValueError、Store I/O 及 source unavailable 會停止 graph，經共同邊界成固定 `ai_tool_unavailable`，不說成模型參數錯誤。既有核心沒有 typed artifact error，App 僅適配三個已核字串；未知錯誤保留為基礎服務故障，沒有吞錯 fallback。
- **純唯讀：** package 僅交出三個原生工具；沒有安裝 FilesystemMiddleware 的 offload／scrubbing／model hooks，也沒有寫入工具或 host filesystem。長繁中原生分頁重組完整，無 artifact 寫入；來源工具沒有 JD operation、Memory publish 或模型讀取基準更新。

獨立執行：新 App 鎖定環境，`uv run --offline --frozen --no-sync ... pytest -c pyproject.toml ../../packages/consultant-memory/tests/test_read_tools.py tests/test_memory_read_tools.py tests/test_consultant_memory_context.py -q -p no:cacheprovider`，**54 PASS／9.12 秒，exit 0**。這 54 案為原生框架與合成記憶體／SQLite 測試；不抵銷 MR-R01 的新反例，也不代稱真 PG、真模型、完整背景 Memory 工作流程或日常 AI 已啟用。無 provider／DB 初始化／產品碼修改。
