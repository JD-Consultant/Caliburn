# Q019 第六切片：B2 按需整併與發布 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. 本切片耦合度高，主實作者 inline，完成後獨立 review；不新增平行產品任務。

**Goal:** 使用已保存 B1 產物，透過有界工具回圈整理正文／導覽，耐久發布並在 stale 時重新讀取較新的修補。
**Architecture:** 官方 create_agent + StateBackend 暫存；LangGraph 子圖保存本次工具進度，外層依序保存不可變版本及 publication request，再發布。既有 publication seam 仍是唯一 head／receipt owner。
**Tech Stack:** 沿用隔離 lock：LangChain 1.4.0、LangGraph 1.2.11、DeepAgents 0.7.13、LangChain-OpenAI 1.6.0、SQLAlchemy 2.0.52。
**Spec:** [Q019 Memory §2.3／§6](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md)、[總覽](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design.md)。主 checkout 最新稿有效，worktree 歷史 register 不作新需求。

## Preflight／Global constraints

- Topic LLM-Q019；G7 第六切片。第五切片 HEAD a8f81b82，71 passed／0 skipped。
- 唯一交付 B2。無 JD、UI、C 對員工工具、A 刷新或背景 scheduler；C 競爭以既有 publication API 注入驗證。
- 只改 .worktrees/analysis-only-agent/experiments/analysis-agent 與本段文件。主 checkout 只同步路由／設計狀態／計畫結果，不暫存舊 dirty 文件。
- 不搬資料、不付費 API、不改 provider 接法；synthetic HTTP 測 real LangChain／LangGraph／Store，真 PG 驗恢復。
- 不要求 LLM 填版本、operation ID、游標、來源身份或 Skill ID。
- 不 decode 原生 reasoning、不向 B2 自由開放 raw 來源工具、不接真實檔案或 shell。
- 呼叫者仍須每份文件序列執行 B job；checkpointer 不是 job 排程鎖。
- 寫入驗證只判格式／路徑／引用存在，不判語意正確／全部工作已涵蓋。

## 1. 接法與證據（2026-09-06 核對）

| 接點 | Official fact | 本段 mapping／限制 |
|---|---|---|
| 工具及暫存 | [DeepAgents Backends](https://docs.langchain.com/oss/python/deepagents/backends)：StateBackend 在 graph state 保存檔案；StoreBackend 持久保存；CompositeBackend 路由；允許 backend policy wrapper。 | 只有 /memory/knowledge.md、/memory/guide.md 可寫；/interviews/ 唯讀。StateBackend 是本次 staging，不是第二份 published Memory。 |
| Agent durable steps | [LangGraph subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)：per-invocation 子圖可繼承 parent saver，本次執行可恢復、下次 invocation 不繼承舊對話。 | B2 一次 attempt 是子圖，新的 stale attempt 從新 base seed，舊 model result 不沿用。 |
| 有界執行 | [官方限額 middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)：model/tool limits、thread/run 差別與 error 行為。 | 每 job 成功 model steps 共 8／tool calls 共 12；已完成 attempt 的用量扣到下一 attempt，本次恢復由子圖 counter 持續。HTTP 傳送後尚未保存的重送不保證 exactly-once，不將此額度冒稱供應商計費硬上限。 |
| 格式錯誤回傳 | [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)：ToolException／錯誤回傳及正常工具回圈。 | 提供無參數 validate_memory，檢查當前暫存，錯誤回工具結果；模型可在剩餘額度內修改。最終仍重驗，沒有通過就不發布。 |
| 發布及重做 | Q019 §6、既有第四切片 SQLAlchemy version_id_col／receipt 證據。 | save／prepare／publish 分 durable steps。stale 重載 base 和其修補來源，不改舊 request 的 expected_revision。 |

不重新研究 OpenAI 五產物，沿用 Q019 的引用鏈。以上實作組合是對已同意概念的框架接線，不宣稱 OpenAI 使用相同 Python 類別或 metadata schema。

## 2. 資料流與精確邊界

1. 從同文件 ExtractionWorkflow 的 completed checkpoint 取得 source_reference 與 files；B1 尚 pending 就拒絕啟動 B2。不接受模型拼的產物 manifest。
2. 固定目前 published head；核對本次來源比已處理游標新，同一完成來源回已完成結果／head，不倒退處理。
3. 保存基準 revision、正文／導覽內容、B1 真實地址及候選內容。候選先給全文（總量有界）；詳記僅給地址，按需 grep/read_file。既有正文先 seed 到 staging，不能只靠小導覽重建全文。
4. 本次子圖 seed 使用 StateBackend.upload_files；create_agent 使用官方 FilesystemState 與檔案 tools。只選 ls、grep、read_file、write_file、edit_file；另有不含模型欄位的 validate_memory。沒有通用 filesystem middleware 的 context eviction／summary hooks，保持原生 Responses items。
5. 最終 provider response 必須 completed 且沒有未完成 tool calls；整個 attempt 不得有 incomplete／failed／refusal 或 invalid_tool_calls 被當作成功。download staging、驗兩個檔案／引用／大小；正文導覽成對返回。validate_memory 是提前取得錯誤的工具，不取代最終重新檢查。
6. 結果先 checkpoint，再 save_memory；prepare request 另 checkpoint；最後 publish。Store 或提交結果不明時恢復相應 node，沿用已有 request／operation id。
7. stale 時保留原 B1，從新 head 重新 seed 新 attempt。Runtime 讀取 old base 至新 head 之間 repair receipts，加入其實際有界問答／角色／ref；不提供任意 raw 搜尋。新 cursor 已涵蓋本來源則不回退覆寫。
8. 額度／輸入超界、找不到來源或處理中的游標衝突：停止並保留 job，不能截短冒充完整。修補來源過長不發布覆寫。自動 scheduler／人工取消重排 UI 在本段範圍外。

初始可調工程上限：新候選合計 24,000 字、更正原文合計 12,000 字、模型輸出每步 4,096 tokens。repair receipts 20 筆是目前固定安全上限，不是可調參數；以上均非官方品質或最佳值。完整正文留 staging，不硬塞 prompt；guide 沿第三切片上限 4,000 字。

## Task 1：B2 durable vertical slice（單一可驗證交付）

**Files**
- Create: experiments/analysis-agent/src/analysis_agent/consolidation.py（job／attempt 組合）
- Create: experiments/analysis-agent/src/analysis_agent/consolidation_tools.py（scoped staging／validation）
- Modify: experiments/analysis-agent/src/analysis_agent/memory.py（public scoped text/backend access，A scope 不放寬）
- Create: experiments/analysis-agent/tests/test_consolidation.py
- Create: experiments/analysis-agent/tests/test_postgres_consolidation.py
- Modify: experiments/analysis-agent/README.md
- Create: docs/specs/2026-09-06-analysis-only-agent-consolidation-results.md

**Interfaces**
- Consumes ExtractionWorkflow.graph/config、reader、artifacts；PublicationStore.current/prepare/publish/repair_receipts。
- Produces ConsolidationWorkflow(extraction, publication, model, checkpointer, *, max_model_steps=8, max_tool_calls=12).start()/resume()。
- completed result 保存 source_reference、files、attempt、base_revision、used_model_steps、used_tool_calls、material、request、result；全由 runtime 更新。result 是 publication head 的可序列化資料。
- MemoryArtifacts 新公開方法 read_text(path, version=None)、interview_backend()；固定 doc namespace，不加入另一個來源副本。

- [x] Step 1：先寫端到端失敗測試。只 fake 外部 HTTP，不 fake Agent／Store 行為。

```python
def test_consolidates_saved_candidates_and_can_read_detail(harness):
    h = harness  # tests/test_consolidation.py：真 B1/Store，synthetic HTTP
    h.replies.append(call("read_file", file_path=h.extracted["files"][0]["summary_path"]))
    edits(h)  # 同測試檔提供 write_file -> validate_memory -> final fixture
    workflow = workflow_class()(h.b1, h.pub, h.model, h.saver)
    result = workflow.start()
    assert result["result"]["processed_source"] == h.ref
    assert "/interviews/" in knowledge(h)
    assert h.pub.current().revision == 1
```

- [x] Step 2：執行 .venv/Scripts/python.exe -m pytest tests/test_consolidation.py -q；確認缺少 B2 行為的 RED，不是環境錯誤。
- [x] Step 3：按以下骨架實作公共框架組合（helper 精確職責見資料流，禁止 import framework private helpers）。

```python
builder.add_node("load", self._load)
builder.add_node("consolidate", self._consolidate)
builder.add_node("save", self._save)
builder.add_node("prepare", self._prepare)
builder.add_node("publish", self._publish)
builder.add_edge(START, "load")
builder.add_conditional_edges("load", lambda s: END if s["result"] else "consolidate")
builder.add_edge("consolidate", "save")
builder.add_edge("save", "prepare")
builder.add_edge("prepare", "publish")
builder.add_conditional_edges("publish", lambda s: "load" if s["stale"] else END)
# _consolidate：seed -> 官方 create_agent -> collect，
# checkpointer=None 繼承 parent；每新 attempt 的輸入不含上一 attempt 對話。
```

- [x] Step 4：追加並逐一驗 RED→GREEN：只改 guide/正文的原子發布；詳記唯讀／跨 doc；格式或缺引用工具錯誤可修；incomplete／refusal 不能當成功；B1 pending；新候選／更正來源超限；沒有修改的成功仍前進 cursor。
- [x] Step 5：故障驗證：model 完成後 Store 故障不重呼模型；提交後斷線以同 receipt 恢復；B2 途中 C 發布，舊結果不發布、用新 base＋更正問答重做，B1 不再抽取。
- [x] Step 6：限額及繼承驗證。用官方 counter 在子圖重啟仍阻擋；過期重做只得剩餘額度，不重新給 8／12。讓 persisted count／實際 HTTP 次數不一致時 fail test，不用文字檢查代替行為。
- [x] Step 7：専用 PostgreSQL 重開所有 client／Saver／Store，至少驗工具中斷與已完成模型後的保存恢復；清理只限本次隨機文件。PG skipped 不是 durability pass。
- [x] Step 8：完整 pytest、compileall、uv lock --check、git diff --check；獨立 correctness/security review，必要 finding 有 ID 並修復複核；回寫結果、README、主 register／Memory 狀態。
- [x] Step 9：只暫存上述實際改動，單一 task 本地 commit＋tag q019-memory-consolidation-v1；不 merge／push，保留 worktree 接 C。實際 hash 與保存點核對見[主 register](S:/caliburn/docs/current-decisions.md)。

## 自我審核／退出條件

Memory §2.3 對應步驟1–6；§6 協調對應5–7。數值及固定／可調邊界見上文，方法引用附在接點旁。
start 先作 read-only input preflight，超界不預占 job；執行中限額／不合法最終結果則安全停止。resume 只重試失敗 node，不自動改寫已產生的壞檔案；本段不交付產品 retry/cancel/replan 操作界面，限制必須列入結果。
完成只代表確定性流程與故障恢復成立；synthetic 模型不能證明抽象／去重的真實品質。下一段才 C 對話內修補與 A 受控刷新，再完整使用者流程；不重開五產物命名與來源保存架構。
