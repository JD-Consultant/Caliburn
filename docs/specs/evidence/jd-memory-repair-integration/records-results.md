# C 原 call／結果純契約

日期：2026-09-13；施工基準 `8403d7e2`。本輪只建立 App 層的原訊息、修補輸入與結果驗證；不執行 C、讀取 Store／來源、發布 Memory 或處理宿主恢復。

## 實作與責任

- [memory_repair_records.py](../../../../experiments/jd-relational-app/src/jd_relational/memory_repair_records.py) 提供 `parse_repair_input`、`make_repair_binding`、`decode_repair_bindings`、`verify_repair_binding_message`、`make_repair_message` 與 `validate_repair_message`。
- `RepairBinding` 是 frozen、strict Pydantic 模型，可用 `model_dump(mode="json")` 保存。包含原 run scope／message／call／operation／args digest／base／source；operation 由 App 配發。即使原 args 不符合編輯 schema，仍能保留原 call digest，讓後續原生驗證回覆配對這次失敗。
- 模型輸入只有頂層 `edits`，每項沿核心 `MemoryEdit` 的 `path`／`diff`，1–8 項、合計 12000 字元與兩條既有路徑；不新增 patch matcher。
- 模型可見 content 只投影 status／detail／guide／read_paths／retryable；`ToolMessage.artifact` 保存原 outcome（排除 changes）與原 PublishRequest，外加格式、operation 及 input digest。成功 status 僅限 applied。原生工具 call ID、name、status、content 和 artifact 必須相符。
- applied 必有原 request，核 operation／doc／base／source／kind、原 memory、base+1、背景 cursor 不被 C 改寫；current head 同文件且不低於 applied，同一發布 revision 不得有不同內容身分。current 較高時保留晚 B 與原 applied 的差別。
- stale 可在 prepare 前不帶 request，或 CAS 後保留原 prepared request；`not_executed` 只代表尚未 prepare。未知來源／Store／SQL 失敗沒有可修結果代碼；取消後已開始的 C 由整合層等實際完成再依原結果收尾，這層不推定未發布。
- invalid_edit／stale／no_memory 的 retryable 依既定兩次限額投影；不保存第二份 read head／計數。原生配對訊息如何推導本輪讀版／次數，由本輪 App session 接合負責。

## 官方依據與實測

[LangChain Messages：Tool message／artifact](https://docs.langchain.com/oss/python/langchain/messages#tool-message) 明示 artifact 是可供程式使用而不送給模型的附加資料；tool_call_id 配對原 AI tool call。查閱日 2026-09-13，實際使用 LangChain 1.4.0／langchain-core 1.6.3、LangGraph 1.2.11、langchain-anthropic 1.7.2，皆固定安裝版。框架不替本案驗證 publication receipt；本模組也不把 artifact 自稱為資料庫發布證明。

[test_memory_repair_records.py](../../../../experiments/jd-relational-app/tests/test_memory_repair_records.py) 使用真正 AIMessage／ToolMessage、JsonPlusSerializer，及已安裝 Anthropic adapter `_format_messages` 的離線轉換。後者僅測試使用私有 seam，未修改 adapter、未建 client 或連 provider；升版時須重驗此 wire 限制。

| 證據 | 結果 |
|---|---|
| 先寫反例，模組尚不存在 | **1 collection error／7.18s**，ModuleNotFoundError；保留首敗，沒有把尚未執行的斷言記為失敗驗證。 |
| 第一批原 call／artifact／request／scope／錯配反例 | **83 PASS／13.04s**。 |
| 補真正 adapter artifact 排除、原生序列化、prepare 後 stale、持久 request 嚴格形狀等 | **91 PASS／5.40s**；未跑 DB／模型／舊 runtime。 |
| 最後固定 error code 型別防錯後窄跑 | **91 PASS／11.57s**，同組重跑，不與上一列相加。 |

首敗與第一次通過有既有 pytest cache 權限警告；最後窄跑僅停用 pytest cache provider，不改產品或依賴。原始輸出保留於 `.research-tmp/jd-memory-repair-records-first.txt`、`jd-memory-repair-records-first-implementation.txt`、`jd-memory-repair-records-final.txt`、`jd-memory-repair-records-final-safe.txt`。

可重跑（`experiments/jd-relational-app`，新 App 鎖定環境）：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_memory_repair_records.py -q -p no:cacheprovider
```

本結果不等於完整 Agent／Memory C 接線通過；原 after_model 保存、真正 C 子圖執行、同輪讀版與次數推導、取消／查回仍由本輪整合及獨立審查驗收。無新表、provider 呼叫、程式碼外傳或 production 變更。
