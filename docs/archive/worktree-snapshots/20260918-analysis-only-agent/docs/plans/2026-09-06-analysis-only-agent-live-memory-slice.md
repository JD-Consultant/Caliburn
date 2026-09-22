# Q019 第七切片：C 即時修補與 A 受控刷新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。單一緊密耦合切片，由主實作者 inline；完成後獨立 review。Owner 已同意 Q019 設計及接續此段，不重開概念選型。

**Goal:** 主顧問用小型 edits 修補已有 Memory，提交成功或 stale 後同時切換讀取版本與可見回覆；中斷恢復不能重複發布。
**Architecture:** 官方 tool／Command／middleware＋無模型的 per-invocation 子圖，重用 StateBackend edits 與既有 publication seam。保存完整原文，不新增對話庫或第三位 Agent。
**Tech Stack:** 沿隔離 lock；LangChain1.4.0、LangGraph1.2.11、DeepAgents0.7.13、ChatOpenAI1.6.0、SQLAlchemy2.0.52。
**Spec:** [Memory §3–6](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md)；[Runtime §2–6](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-runtime-design.md)。

## Preflight／約束

- LLM-Q019／G7 第七切片；基準7bb01e39。隔離worktree既有，baseline84 passed／12 PG skipped；上一切片全套96 passed。PG須本輪再跑，skipped不算恢復通過。
- 唯一交付C＋A刷新。無JD／UI／scheduler／新provider／付費API／正式Skill搬遷；不讀產品.env，不搬或刪舊資料。
- 看主checkout最新四稿與register，不以worktree歷史register或被排除長文猜需求。
- 原生reasoning仍opaque；固定run初始prefix、不改歷史，工具結果明示更新。無獨立分析筆記。
- 一份文件一個A run；parallel_tool_calls=False，不在這段做並行工具排程。
- 模型只填edits（path、old_text、new_text），不填版本／operation／來源ID／Skill。只有已有兩檔可改，C不初始化無Memory的文件。
- 已讀內容與語意衝突由模型判斷，歧義先問員工；程式只做精確套用及格式／來源範圍檢查。
- C不推進B游標。Runtime自動保留本輪更正问答引用供B stale重做；不把它說成逐句語意證明。

## 框架接點與本案映射

| 接點 | 2026-09-06核對的官方事實 | 本段接法 |
|---|---|---|
| ToolRuntime／Command | [Tools](https://docs.langchain.com/oss/python/langchain/tools)：runtime注入不在模型schema；Command可連同ToolMessage更新state。 | 同一update更新memory_read_head及對模型的成功／stale回覆。 |
| 動態讀取 | [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)及安裝版ToolCallRequest.override：可用state替換本次實際tool。 | 每次按已checkpoint的head重綁官方read tools，不從global最新head偷換。 |
| Backend差異 | [Backends migration](https://docs.langchain.com/oss/python/deepagents/backends)：舊runtime factory／ctx.state已淘汰，不應把mutable state當Store namespace。 | 每次取得固定MemoryVersion的readonly backend；不使用deprecated factory或private helper。 |
| 精確編輯 | 同上StateBackend.edit：不存在／多重命中回error；state寫入由backend處理。 | per-invocation FilesystemState先seed兩檔，逐步edit；全部成功才驗證保存。 |
| 保存與重啟 | [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)、[Durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)：工具可呼叫繼承Saver的子圖。 | C是無LLM的seed→edit→validate→save→prepare→publish；request耐久後才提交，失敗恢復同request。 |

這是沿已核准Q019的framework composition，不宣稱各大廠使用相同類別、資料表或錯誤碼。OpenAI五產物／live-repair概念已研究，不重做廣泛搜尋。

## 正常及錯誤資料流

1. A before_agent以最新HumanMessage識別新訪談輸入，讀一次head／導覽並checkpoint；同輸入恢復不重新綁head。scope由runtime固定文件。
2. 本輪可回查來源從已持久化canonical snapshot建立，範圍包含最近可見顧問問句及當前員工輸入。不把未完成run冒稱B1完整視窗；B1 capture規則不放寬。
3. 起始prompt提供固定導覽與真實本輪source ref；A可選擇在修補內容引用。machine receipt自動記來源，不要求每次整理附新quote。
4. A的ls/grep/read_file用middleware依memory_read_head重綁官方工具；沒有head時可看詳記，正文明確不存在，不建立假Memory。read_conversation沿既有reader。
5. repair_memory(edits)只接受已有正文／導覽的非空精確old_text。初始工程界線：最多8 edits、old＋new合計12,000字，非大廠統一最佳值。
6. C以A已看版本seed，逐項由官方StateBackend.edit套用，任一失敗整包不發布；保存／準備／發布分durable節點。不把DB錯誤回給模型猜成功。
7. 正常成功回新版本、導覽、已套用new_text及原文引用，Command更新read head。stale回當前head／導覽及需重讀路徑，Command切換，模型可重讀後再提一次；不自動重新套同edits。
8. 每個A輸入最多兩次可修正C失敗（初次＋一次重試）；下一次新輸入重置，關閉重開不重置。存取故障／提交不明保留pending，不當一般內容錯誤，不放寬retry budget。
9. B再次發布不暗中改A固定head；下次新訪談讀新head，下一次C仍驗expected base。已成功C提交後A後續失敗不假裝回滾。
10. 結果分status／錯誤位置／下一步；不回長表單、不要求拒絕原因。不開新memory語意驗證器。

## Task 1：C與主顧問同run接線

**Files**
- Create: experiments/analysis-agent/src/analysis_agent/repair.py（無模型修補子圖／小型schema）
- Create: experiments/analysis-agent/src/analysis_agent/live_memory.py（MemorySession middleware與repair tool／Command）
- Modify: experiments/analysis-agent/src/analysis_agent/memory_tools.py（抽出可重用官方read工具組裝）
- Modify: experiments/analysis-agent/src/analysis_agent/memory.py（無head readonly view，不寫假檔）
- Modify: experiments/analysis-agent/src/analysis_agent/sources.py（in-run已保存輸入引用）
- Create: experiments/analysis-agent/tests/test_live_memory.py
- Create: experiments/analysis-agent/tests/test_postgres_live_memory.py
- Modify: experiments/analysis-agent/README.md
- Create: docs/specs/2026-09-06-analysis-only-agent-live-memory-results.md
- 主checkout只同步plan/results、register、Memory／Runtime狀態，不stage歷史dirty文檔。

**Interfaces**
- MemorySession(publication, source)：AgentMiddleware，自帶tools。state_schema擴充AgentState；調用build_agent(..., middleware=[session], tools=session.tools)。
- RepairWorkflow(artifacts,publication,source).graph：FilesystemState子圖；input為runtime-selected base、source_reference及已validated edits。output含outcome及head。
- ConversationReader.capture_input(message_id)：只讀canonical最新snapshot，必須是最新HumanMessage；返回實際問句／輸入範圍，不要求run已final。

- [x] Step 1：先寫真框架HTTP合成測試，缺功能RED。
```python
def test_repair_refreshes_reads_without_rewriting_initial_guide(h):
    session = MemorySession(h.publication, h.source)
    h.invoke(session, [h.read(), h.repair("主管", "處長"), h.read(), h.final()])
    assert h.knowledge() == "例外由處長核准。"
    assert "處長" in h.last_tool_result()
    assert h.publication.current().processed_source == h.initial_source
```
- [x] Step 2：.venv/Scripts/python.exe -m pytest tests/test_live_memory.py -q --tb=short；核對RED原因是缺接線。
- [x] Step 3：實作state初始化及公開read-tool override。
```python
def wrap_tool_call(self, request, handler):
    tools = self.read_tools(request.state["memory_read_head"])
    replacement = tools.get(request.tool_call["name"])
    return handler(request.override(tool=replacement)) if replacement else handler(request)
```
- [x] Step 4：實作C子圖，逐節點seed／edit／validate／save／prepare／publish，工具回Command。
```python
return Command(update={
    "memory_read_head": result["head"],
    "messages": [ToolMessage(content=json.dumps(result), tool_call_id=runtime.tool_call_id)]
})
```
- [x] Step 5：逐一RED→GREEN：雙檔原子變更、批中一項錯誤不發布、missing/ambiguous path/oldtext、stale新head重讀重提一次、無Memory、跨文件、大小上限、原文問答可回查、未要求模型ID、沒有平行tool side effects。
- [x] Step 6：同run／新run／重啟head一致性；C不前進B游標；published receipt包含實際本輪source，B2能讀；完整native items持續可用。
- [x] Step 7：專用PG重建所有clients，注入保存前／prepare後／提交後回覆丟失，驗證同request只發布一次，無第二模型。
- [x] Step 8：全套pytest（PG不可跳過）、compileall、lock check、diff check，獨立review並有限複核。結果記清官方／mapping／實測／未測。
- [ ] Step 9：只stage此段檔案，本地commit＋tag q019-live-memory-v1，worktree保留，不merge／push。

## 退出與後續

本段只證明C發布／A刷新／恢復接線，不證明自然模型語意判斷必然正確。未決配置／錯誤應由精確測試或官方API釐清；產品範圍或模型數量若需改則先回Owner。後續才應用排程／錯誤重排入口／只分析Web整合及小額真模型測試，不新開無限memory選型討論。
