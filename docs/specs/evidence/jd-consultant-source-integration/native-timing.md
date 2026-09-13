# 原生模型請求前的來源保存時序

2026-09-13；OI-01／02 有界離線探針。沿[接線核對](memory-seams.md)，只回答：真正 LangChain model request middleware 執行時，是否已有可固定回查的本輪原話。沒有修改產品 src／tests，沒有 DB、服務、SDK 傳輸或 provider 呼叫。

## 結果

**首跑直接 PASS，exit 0，外層命令耗時 7.246 秒。沒有觀察到首敗，不虛構 RED。**原始 metadata-only 輸出為 [jd-source-timing-first.jsonl](../../../../.research-tmp/jd-source-timing-first.jsonl)；可重跑附件為 [jd-source-timing-probe.py](../../../../.research-tmp/jd-source-timing-probe.py)。重新執行會產生不同原生 checkpoint／task IDs，不要求和本次 ID 相同。

| 觀察位置 | 真正保存的訊息種類 | root next／task | 固定來源 |
|---|---|---|---|
| 第一次 `wrap_model_call`、尚未呼叫 model handler | `human` | `consultant`／`consultant` | 本輪 Human 已存在，id＝run_id，全文及 metadata 與原輸入完全相同；source 為 child checkpoint。 |
| 真正 ToolNode 呼叫合成工具的 body | `human, ai` | `consultant`／`consultant` | source 已前進；用首次 root＋source config 回讀，仍精確等於首次 Human-only snapshot。 |
| 第二次 `wrap_model_call` | `human, ai, tool` | `consultant`／`consultant` | 原 ToolMessage 已保存；首次固定來源仍相等，未隨 child latest 前進。 |
| 原生 Agent loop 返回後 | `human, ai, tool, ai` | 空／空 | 最新 source 回到 root；首次 child 固定來源仍可回查。這不是 App run receipt 收尾證明。 |

四次 `AiRunCheckpoints.observe` 都取得唯一且原樣的本輪 Human，當下再以 `observe_at(document, run, dataset, root_config, source_config=...)` 回讀都相等；後三次另回读首次固定位置，沒有混入後續 AI／tool 內容。模型實際請求 2 次、工具 1 次，全部為本機合成，無額外 Agent loop。

本次實際形狀（僅來源位置，不含原話）：

```json
{
  "first_root": {
    "thread_id": "8414af1e-7695-40ec-b4bc-c1a867ec75a8",
    "checkpoint_ns": "",
    "checkpoint_id": "1f1af3f9-c357-6298-8000-e7eb2b65530e"
  },
  "first_source": {
    "thread_id": "8414af1e-7695-40ec-b4bc-c1a867ec75a8",
    "checkpoint_ns": "consultant:a2c07a8c-992a-d70a-efc3-a41bf7baa7e2",
    "checkpoint_id": "1f1af3f9-c360-6f24-8000-ea4d696a68b9"
  },
  "source_at_tool": "1f1af3f9-c38c-65cc-8001-e072535580a5",
  "source_at_second_model": "1f1af3f9-c3ac-631d-8002-0974873f34f2",
  "root_after_native_loop": "1f1af3f9-c3d0-6a33-8001-720aa92642ff"
}
```

## 方法與可重跑命令

依現有 `test_consultant_context.py` 的 `FixedModel`／`setup`，用官方 `create_agent`、`ConsultantState`／`ConsultantContext` 與 `JdNoticeMiddleware`，另加僅觀察的 request middleware；root 使用產品 `build_document_graph`＋原生 `InMemorySaver`。V2 `new_run_record` 產生原 Human。第一個合成 AIMessage 呼叫一個真正註冊的工具，第二個合成 AIMessage 正常結束；middleware 與工具皆調用產品 `AiRunCheckpoints`。

實際套件：LangChain **1.4.0**、langchain-core **1.6.3**、LangGraph **1.2.11**、checkpoint **4.2.0**。呼叫 `graph.invoke(..., durability="sync")`，未使用 `SyntheticRuntime` 繞過 request middleware，亦未自造 checkpoint decoder。`tracing_context(enabled=False)` 禁止遠端 tracing；輸出僅種類、布林判準、scope／checkpoint IDs，不記錄問答正文。

```powershell
# cwd: S:/caliburn；只跑離線探針，無資料庫或金鑰設定。
$env:PYTHONUTF8='1'
& 'experiments/jd-relational-app/.venv/Scripts/python.exe' '.research-tmp/jd-source-timing-probe.py'
```

## 對最小 source owner 的影響

本次支持在**模型 request middleware、原 input 已同步保存後**，沿 `AiRunCheckpoints.observe` 發配當輪來源位置，再讓 source reader 使用同一固定 root＋source config。只需要新的來源投影與契約接合；沒有證據需要為來源另加 root 保存 node、原話表或在 active child 中更新 root。

必須保持 `source_config`，不能只留 root checkpoint：本次三個 loop 位置的 root 相同、child source 不同。既有 `observe_at` 已提供精確讀取接點；此時產生的「當輪輸入來源」也不等於完整回合已閉合或所有 Memory 已更新。

限制：這只驗**同步正常流程＋InMemorySaver**的原生時序、逐字保留及固定回查，未驗 PG、async、故障、取消、重啟、更多前文範圍或 source tool／basis_refs 完整縱向流程；也沒有啟用 `AiToolMiddleware` 的 JD SQL 寫入。這些不能由本次 PASS 推定完成，後續只在實際 source 接合測必要正反例。
