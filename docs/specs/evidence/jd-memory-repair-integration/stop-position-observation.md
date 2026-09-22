# C 兩個停止位置的原生形狀觀察

2026-09-13；JD-R002／OI-02。修 CA-01／CA-02 之前，先用拋棄式探針讀兩個停止點**實際**的原生狀態，再決定只補哪些投影。App 鎖 LangChain 1.4.0／LangGraph 1.2.11；離線、0 provider、InMemorySaver 與記憶體 SQLite，沒有連真 DB 或模型。

來源 fixture 是既有 `tests/test_memory_repair_session.py::setup_repair`（真 `create_agent`、真 `build_document_graph`、真固定 C 子圖），故障注入與[審核稿 §3](continuation-audit.md) 的兩個反例相同。探針本身是一次性的，不留在測試樹；其結論由 `tests/test_memory_repair_session.py` 的 `stopped()` 與真 PG 案例接手。

## CA-01：停在 App 自己的 binding handler

| 觀察 | 實際值 |
|---|---|
| root `next` / `tasks` | `('consultant',)` / `['consultant']` |
| consultant 子圖 `next` | `('AiToolMiddleware.after_model',)` |
| consultant 子圖 `pending_writes` | 一筆 `__error__` |
| 子圖 `channel_values` | 含 `branch:to:AiToolMiddleware.after_model` 與 `jd_memory_repair_bindings`（值為 `[]`） |
| `observed.repair_bindings` / `repair_checkpoint` | `[]` / `None` |
| `observed.source_config` 的 ns | `consultant:<task id>` |
| model 請求 / C `seed` / publication revision | 1 / 0 / 1（未動） |

判斷依據：停止位置仍是 binding node，代表工具沒有把控制權交回 root，固定 `memory_repair` 節點因此從未執行。這是「C 尚未開始」的原生證據，不是從「binding 不存在」反推。node 名稱由 LangChain 依 middleware 類別命名，App 以 `consultant_tools.BINDING_NODE` 精確比對；名稱不符時保持門閘，不放寬成任意節點。

## CA-02：停在固定 C 子圖自己的 START

| 觀察 | 實際值 |
|---|---|
| root `next` / `tasks` | `('memory_repair',)` / `['memory_repair']` |
| C 子圖 checkpoint `metadata.source` | `input` |
| C 子圖 `channel_values` 鍵 | 只有 `__start__` |
| `__start__` payload 鍵 | `operation_id`、`base`、`source_reference`、`edits` |
| 以該固定 config 再 `get_state` 的 `next` | `('__start__',)` |
| `StateSnapshot.values` | `{'files': {}, 'messages': []}`，**不含**原輸入 |
| `observed.repair_bindings` | 一筆，與 START payload 的 operation／base／source 相同 |
| model 請求 / C `seed` / publication revision | 1 / 0 / 1（未動） |

判斷依據：`channel_values` 只有 `__start__`，代表沒有任何節點寫過狀態通道；這比檢查 `values` 形狀穩定，也是「C 尚未開始」的直接證據。原輸入不在 `values`，所以 `ai_checkpoints._repair_input` 沿用 root 既有的 `checkpointer.get_tuple` 做法讀同一 START 通道，只多投影 `input` 一個欄位，不掃任意 namespace。

## 界線

- 兩段觀察只證明這兩個停止位置的形狀，不證明所有可能的停止組合都安全，也不等於整個 App 已解鎖。
- 這是固定 SDK 回覆的離線觀察，不是自然模型；真 PG 與真新程序證據見[結果稿](../../2026-09-13-jd-memory-repair-app-integration-slice.md)。
- 官方文件支持原生子圖觀察與保留原請求身分，但沒有規定本案的判定表；形狀變更以本機 lock 與反例為準，不以文件網站當下說法覆蓋實測。
