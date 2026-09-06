# Q019 Memory 引用／來源修復計畫

> **For agentic workers:** 使用 superpowers:executing-plans 逐項實作，完成一段回看有效決策。本輪 Owner 已要求修復上一輪審核缺陷，不新增產品語意。

**Goal:** 修 BG-01／BG-02／MR-02，讓已保存 Memory 的引用真能回查，短答更正不漏必要前文。

**Architecture:** A/B/C、五產物、Store／Checkpointer／publication 分工不變。Markdown 語法用成熟 parser；受控地址交既有 artifact／ConversationReader 驗證；C 的來源定位沿既有安全回合 primitives。沒有新模型、來源副本或必填欄位。

**Tech Stack:** 既有 LangChain／LangGraph／Deep Agents；markdown-it-py CommonMark parser＋官方 linkify extra；pytest、SQLite／專用 PostgreSQL 驗證，provider HTTP 全合成。

**Spec:** [上一輪逐項審核](../../../../docs/specs/2026-09-06-analysis-only-context-memory-readiness-audit.md) §5；[已准 Memory 設計](../../../../docs/specs/2026-09-06-analysis-only-agent-memory-design.md) §3–6。

## Preflight／邊界

- Topic `Q019-MEM-REF-REPAIR-01`；2026-09-07；Owner 已授權隔離修復。
- 工作目錄 `S:/caliburn/.worktrees/analysis-only-agent`，起點 `f246f43c`；主 checkout 只更新 current register，不碰其他修改。
- 唯一問題：三項已重現缺陷能否沿已准契約局部修復，而不改 Memory 語意或追加付費分析。
- 不做：UI／JD／production、Skills 內容、完整 request budget、新的 raw-history 搜尋、grep 政策、付費語意測試。它們仍各有 gate，不能說本輪完成了整個產品。
- 不強制每次寫 Memory 必須新引原話；只驗已出現的受控引用。來源位置有效不代表語意正確。
- 不把 OpenAI／Anthropic 的工具錯誤原則宣稱為相同資料庫、相同驗證器或相同 Markdown library。

## 官方依據與實作選擇

1. [OpenAI Function results](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)：工具結果可用文字／JSON／錯誤碼；執行成功或失敗要回模型。不是新增 validation agent 的理由。
2. [Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)：指示性錯誤應交代原因與下一步，維持 call/result 配對。沿 LangChain ToolException／既有 C outcome 實現，不能直接拼 Anthropic wire 到 OpenAI。
3. [既有 Codex producer→consumer 研究](../../../../docs/specs/2026-09-05-memory-summary-routing-and-deep-read-source-review.md) §2–4：Runtime 提供真实位置，模型選擇引用、搜尋並逐層深讀；不猜來源。沿用已查固定 OpenAI source，不重做全套研究。
4. [markdown-it-py token stream](https://markdown-it-py.readthedocs.io/en/latest/using.html#the-token-stream)：CommonMark parse 提供 link attributes／inline children；用此辨識強調與連結，不繼續手刻 Markdown 文法。literal code／文字中的受控地址仍檢查。選 parser 是本案工程映射，不是廠商共用實作聲明。
5. [LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools)：工具參數和 runtime context 分開；沿已存在的 reader 注入，LLM 不填 reader／scope／版本。
6. [官方 linkify extra](https://markdown-it-py.readthedocs.io/en/latest/using.html#linkify)＋[LinkifyIt.match](https://linkify-it-py.readthedocs.io/en/latest/#match-text)：辨識一般文字／code 裡整段外部 URI 的位置，避免把 URL 路徑片段誤認為本地受控地址。不 fetch 網址、不修寫原 Markdown。使用 locked 4.2.0／2.2.0；短小的受控地址辨識及原文範圍驗證仍是已准應用接線。

## Task 1：一致的 Memory 引用驗證（BG-01／BG-02）

**Files:** `experiments/analysis-agent/src/analysis_agent/memory.py`、新 `references.py`、`repair.py`、`service.py`、package dependency/lock；tests `test_memory_read_path.py`、`test_consolidation.py`、`test_live_memory.py`、新 `test_memory_references.py`；相關 fixture／README。

**Interfaces:** `MemoryArtifacts(store, document_id, *, source: ConversationReader | None = None)`。含 raw ref 而沒有 reader 時 fail closed；不以 optional 代表跳過。`controlled_references(text)` 只解析本案兩種受控地址；實際可读性沿 `ConversationReader.read(reference)` 與 backend read。B/C／save／verify_version 共用，不在 C 留另一套 regex。

- [x] RED：用真正 Store、Saver、PublicationStore 測合法強調／連結／裸路徑；損壞前綴、不存在 checkpoint／message、跨文件引用都不得發布。首輪27 failed／17 passed；review 補例另6 failed／2 passed，再補外部URI／中文標點6 failed／8 passed。

```python
record = artifacts.save_extraction(summary='A案例', candidates='核准', slug='A', source_reference=ref)
artifacts.save_memory(knowledge=f'__{record.summary_path}__', guide='A')
# 原缺陷：上行誤拒。另一組：with pytest.raises(ValueError):
artifacts.save_memory(knowledge='[原話](conversation:???)', guide='A')
```

- [x] GREEN：CommonMark tokens 分開文字／連結目的地；只在普通 literal 文字處理句末標點，不能把壞連結修成另一個有效位置；去除重複驗證但不更改保存的 Markdown。引用錯誤指出受控目標、原因與重新讀取／複製地址的下一步。
- [x] 接線：應用 `_context` 傳入同文件 canonical reader；fixture 跟隨實際 composition。`repair._validate` 移除獨立 raw regex，保持既有 Tool result／失敗上限。專用PG另補真正服務重建接線測試。
- [x] 回歸：B2 `validate_memory` 收到錯誤後改正再成功；跳過該工具直接結束也不能繞過最後驗證。C 同樣拒絕且不發布部分內容；合法引用成功且 schema 不增欄位。
- [x] 驗證：`uv run --no-sync pytest -q tests/test_memory_references.py tests/test_memory_read_path.py tests/test_live_memory.py tests/test_consolidation.py tests/test_publication.py`：最終132 passed（22.42s）；較早125項為補review變體前的快照。

Task1 相鄰修正：C 已有失敗 JSON，但 `ToolMessage.status` 原本仍為預設 success；現在同步標記 error，保留原重試計數／wire JSON。已核對目前 Responses adapter 不序列化該 status 欄位，**不能說先前模型看不到失敗或現在多了新重試能力**。不另外增加錯誤處理框架。

## Task 2：短答更正保留問答脈絡（MR-02）

**Files:** `src/analysis_agent/sources.py`、`tests/test_conversation_lifecycle.py`、必要 source regression tests、README、結果紀錄。

**Interfaces:** `ConversationReader.capture_input(message_id)` 的引用格式不變。以 `_groups`／`_turn_status` 確認中間回合安全封閉，`_visible` 找最後真正顧問文字；缺問句時仍保留安全連續的員工輸入，不以 runtime notice 作問題。原文不搬家、不要求 B1 封口本輪。

- [ ] RED：compiled root 前輪 h1「不是主管，是處長」只有 read tool 後 limit；h2「對，剛剛說的是 A 案」啟動 C；assert receipt 回查依序包含 a0 問句、h1、h2，而非只有 h2。

```python
h.replies.append(call('read_file', file_path='/memory/knowledge.md'))
graph = compose_memory(h, max_model_steps=1)
graph.invoke({'messages': [HumanMessage('不是主管，是處長。', id='h1')]}, h.config)
h.replies.append(call('repair_memory', edits=[edit()]))
graph.invoke({'messages': [HumanMessage('對，剛剛說的是A案。', id='h2')]}, h.config)
receipt = h.pub.repair_receipts(after_revision=1, through_revision=2)[0]
assert [s['text'] for s in h.source.read(receipt.repair_sources[0])['segments']] == [
    '是由主管核准嗎？', '不是主管，是處長。', '對，剛剛說的是A案。']
```

- [ ] GREEN：沿現成回合判斷往前定位；不跨 unresolved 回合，不修改對話內容、封口規則或模型 context。
- [ ] 回歸：多個無可見 AI 的安全回合／runtime notice／沒有舊問句／未安全封閉中間回合／現有普通短答。讀取仍有界、可續頁。
- [ ] 驗證：source／extraction／lifecycle／C 測試及全套離線測試，綠燈後 scoped commit。

## Closure gate

- [ ] 獨立 review 看新增測試實際能否捕捉原缺陷；不只看測試數。
- [ ] 更新結果：紅→綠、官方原則／本案接法、未驗品質、原有 parked gaps。
- [ ] 根 register 指向本段結果；確認沒有改 production／額外模型步驟／隱藏語意政策。
- [ ] 全部檢查通過才建立本地 tag；不 merge／push。若新問題需要產品決策，停在該邊界回報。
