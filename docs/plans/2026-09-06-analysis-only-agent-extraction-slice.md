# Q019 第五切片：B1 訪談抽取與可恢復交接

> For agentic workers: 使用 executing-plans；單一緊密相依 seam 由主代理執行，TDD＋獨立 code review。Owner「OK」接續已核准 Q019 Memory §2.2，不是重新選架構。只准隔離開發。

**Goal:** 已完成訪談的每個新範圍都能送入 B1，生成三個簡單字串，耐久保存後交付詳記／候選真實地址；失敗不假裝完成。
**Architecture:** ConversationReader 在工作開始前驗證／分段，再把refs交LangGraph；ChatOpenAI原生with_structured_output；StateGraph extract → save，checkpoint 保存抽取結果後才寫 StoreBackend。B1 不取得 publication writer。
**Tech Stack:** 沿用已鎖定 LC1.4.0／LG1.2.11／LC OpenAI1.6.0／OpenAI3.8.0／Deep Agents0.7.13，無新依賴。
**Status:** 本切片完成；71 passed／0 skipped；獨立review兩項已修復複核關閉。[結果／限制／官方引用](../specs/2026-09-06-analysis-only-agent-extraction-results.md)。只做本地保存，不merge/push。
**Spec:** [Memory §2.2](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md)、[整體](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design.md)、[Runtime](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-runtime-design.md)、[審核 F07/F12](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design-review.md)。

## Global constraints / preflight

- Topic LLM-Q019；第四切片135587bb已完成。本輪只 B1，不實作 B2/C/排程/UI/JD/Skill。
- 已回讀 main register、decision-process、四份最新Q019文檔；不讀排除的2026-08-12長稿。
- 沿用隔離 worktree codex/analysis-only-agent；不讀產品.env、不付費、不merge/push。
- 原始問答保留在canonical checkpoint；B1不讀opaque reasoning，不把AI問題當員工陳述。
- 模型僅填 rollout_summary／raw_memory／rollout_slug；身份、引用、版本、完成範圍由runtime產生。
- empty raw_memory正常成功；refusal／incomplete／schema錯誤／Store失敗不當空成功。
- 本切片同步、每份文件同時一個B工作由caller負責；不宣稱已做跨process job admission。
- 實作技能分類：既有核准架構的下一垂直切片；來源分段、抽取checkpoint、保存有順序依賴，不拆成平行施工。獨立review於完成後進行。

## 官方核對與本案映射

1. [LangChain models](https://docs.langchain.com/oss/python/langchain/models#structured-output)：單次抽取可直接用模型，with_structured_output(method="json_schema", include_raw=True) 同時返回parsed及原始AIMessage。不用建無工具Agent loop。
2. [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：strict管格式，不保證語意正確；拒答和不完整輸出必須辨識。沿用Luna／medium測試字串，不因文件例子換模型。
3. [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[Graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api)：節點間checkpoint、sync durability、失敗後input=None恢復。外部呼叫成功但checkpoint未成功仍可能重跑，不宣稱API exactly-once。
4. [Deep Agents backend](https://docs.langchain.com/oss/python/deepagents/backends)：沿用前切片公開StoreBackend.write/download確認；不另造對話資料庫。
5. 分段大小、prompt、來源路由、B1工作識別是已核准目的的應用接線，不宣稱大廠內部同一schema。OpenAI五產物理由已研究，不重做。

## Task 1：從完整來源到耐久抽取產物

**Files**
- Modify sources.py：extraction_windows 與共用文字投影；原read行為維持。
- Modify memory.py：save_extraction可記可選context_reference header，明確不是新內容。
- Create extraction.py：三欄Pydantic、抽取instructions、原生binding、StateGraph及文件固定的B1入口。
- Create tests/test_extraction.py、tests/test_postgres_extraction.py。
- README／結果／本plan／main register 更新。

### Interfaces and data flow

ConversationReader.extraction_windows(reference, max_chars=6000, context_chars=1500)：
- 同一固定完成checkpoint，取得Human開始、AI正常完成結束的回合；每個新回合恰好進一個source_reference。graph next為空不代表provider輸出完整，末尾Responses status必須明確completed；incomplete或缺狀態不可猜完成。
- 完整回合裝入有界視窗；可有前一完整回合作context_reference，放不下就不帶，不截半句假稱完整。
- prefix只供消歧，input明確分新內容／舊脈絡。未知指涉保留未知。
- 單一回合過大、範圍切半回合、未完成／不存在／跨文件來源，在呼叫模型前ValueError；不漏中段後標成功。
- char bound 是保守的可見文字工程限额，不是精確token帳單；schema／JSON角色包裝另有小量開銷。max_output_tokens用獨立抽取配置。

ExtractionOutput：三個必填str，extra=forbid；欄位用自然語言說明，不要求ID/quote offset/Skill。

ExtractionWorkflow(reader, artifacts, model, checkpointer, max_chars=6000, context_chars=1500, max_output_tokens=4096, max_windows=16)：
- start(reference)：固定文件背景路由，graph初始state只保存ref／視窗refs／position／輸出地址；不得覆寫pending工作。
- resume()：input=None，sync；如果graph已完成只返回已存結果，沒有新模型呼叫。
- start在建工作checkpoint前規劃／驗範圍與視窗數，錯誤範圍不鎖住下一次合法工作；extract節點用reader讀可見role/text頁直到EOF，組instructions＋context/source JSON data，with_structured_output(include_raw=True)。max_output_tokens在此方法kwargs傳入內部model binding，不是在外層RunnableMap.bind；實際wire測試驗參數有送出。工程初值16視窗（可配1–100），超過直接拒絕本批，不默默少處理；不是大廠共同數值。
- extract完成checkpoint含三欄及raw AIMessage（含usage，非A私有思考）；拒答、incomplete或parse失敗明確報錯，不交付產物。無自訂模型重試loop。
- save節點只使用已checkpoint成功結果，runtime header加入來源；成功累積ExtractionFiles及source_reference，position+1；清目前暫存結果，再跑下一視窗或END。
- 恢復路由同文件獨立於員工聊天室；將來由B整體工作呼叫，不是第二聊天室。
- B1完成代表詳記候選可交B2，不推進publication的已整併游標。B2失敗可沿用B1地址。
- 最近完成的同source重送可回原結果。已開始／完成其他範圍後，舊範圍或與前次重疊的輸入明確拒絕，不默默重呼模型；依同canonical snapshot中的message順序驗證，不比較UUID大小／時間、不新增另一份歷史結果索引。找不到前次終點也停止。本切片不提供「強制重抽」API，將來若確有需要另定顯式修復工作；不能冒充已有任意歷史結果快取。這是串行B1的入場規則，不是B2發布游標。
- Store成功但checkpoint失敗可留未引用artifact；不對A發布、不覆寫、無GC。本段不增加分散式交易。

### TDD steps

- [x] 寫test_extraction.py缺功能紅燈；真Graph／InMemorySaver／Store，僅HTTP是假。
```python
def test_saved_model_result_survives_store_failure():
    workflow = ExtractionWorkflow(reader, failing_artifacts, model, saver)
    with pytest.raises(RuntimeError):
        workflow.start(ref)
    restored = ExtractionWorkflow(reader, artifacts, model, saver)
    result = restored.resume()
    assert len(result["files"]) == 1
    assert len(sent_requests) == 1
```
測試fixture明確建Human→assistant已完成兩案例；HTTP payload驗原生json_schema只三欄、沒有工具／A reasoning，模型結果實際存進Store header可回查。
- [x] 最小實作：StateGraph checkpoint把extract與save隔開；沿用官方binding，不patch converter。
```python
structured = model.with_structured_output(
    ExtractionOutput, method="json_schema", strict=True, include_raw=True,
    max_output_tokens=4096,
)
builder.add_edge(START, "extract")
builder.add_edge("extract", "save")
builder.add_conditional_edges("save", lambda s: "extract" if s["position"] < len(s["windows"]) else END)
graph = builder.compile(checkpointer=checkpointer)
```
- [x] 測試成功詳記／空候選、完整分段無中間遺失、前文只標context、問答歸屬、scope、未完成／太大停止、同ref重送與pending拒絕覆寫。
- [x] 測試refusal／incomplete／錯schema不寫artifact；Store失敗resume不重呼模型；第一視窗成功第二視窗失敗不丟第一份／不重跑第一模型；原文無修改。
- [x] 真PG重新建立Saver/Store/Graph後resume pending save，驗模型結果耐久、原文可回查、未產生可發布Memory版本／B1無publication writer；只清專用測試document/workflow資料。
- [x] 全套、compileall、lock check、diff check；獨立review針對本slice與已核准完整流程，finding先重現再修。
- [x] 結果／來源／限制寫回；本地commit/tag保存点詳見main register，不接production。

## Self-review and stop line

- 實測修正接點：外層bind未將上限傳入內部model，改官方with_structured_output kwargs；save前才驗格式會重試同一壞結果，改Pydantic validator先驗共用artifact格式；range先進prepare checkpoint會把超量拒絕變pending，改run外read-only preflight，成功refs才checkpoint。以上各自先有失敗再有通過，沒有改五產物或B1/B2責任。
- 獨立review兩項：B1-R01來源回覆incomplete但graph已END，新增2個反例先失敗再修；B1-R02 X→Y→X／重疊來源重送，新增3個反例先失敗再修，採明確拒絕舊範圍而非另造全歷史結果倉庫。限定複核另記結果稿。

- §2.2輸入/三產物/保存/恢復本段覆蓋；§2.1排程、B2整併、C修補不假稱已交付。
- 原native continuity、原文回查與publication不改權責。
- 代表性案例合併/摘要品質未用真模型驗證，合成結果只驗管線/格式/來源。
- 有關原始來源過大或選取邊界的新需求，先回Owner，不偷偷截短或換成另一套摘要。
