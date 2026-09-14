# Q019：整體執行／錯誤恢復／Context 接線審核

> 2026-09-07 · `Q019-RUNTIME-CONTEXT-COHERENCE-AUDIT-01` · **審核完成，findings OPEN；未授權本輪施工**。
> 程式基準：`codex/analysis-only-agent`，`1d2be04cc5e30a607c5707ece14779a442b74e40`。只分析的隔離底座，不是 production JD 系統。

> **後續狀態：**Owner 已核准並完成四項局部修復／427項總回歸／獨立review；見[修復結果與限制](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-runtime-recovery-repair-results.md)。下列 OPEN／未授權是本次 audit 當時的證據沿革；CT-01／SK-01及一般原文可達性仍未在此修復，不把歷史OPEN誤當成需重新研究。

## 1. 本輪問題與閱讀路由

- **問題：**各切片是否接成同一條可靠流程，使用框架的錯誤／恢復能力；實際模型 Context 是否漏放、多放或互相矛盾？
- **Binding：**每文件隔離；A 原生多輪延續、B1 抽取／B2 整併、C 按需修補；完整原文保留、逐層深讀。不新增 JD、UI、隱藏思考筆記或第二份 Memory。
- **本輪範圍：**讀碼、官方契約查核、合成 HTTP 的離線重現、紀錄。未改程式、未付費呼叫、未動 Docker、未 merge／push。
- **下一個 gate：**先回報整體缺口，再確認修復切片；不直接沿前輪 next-step 開始 Skills／UI。

完整回讀 [總設計](2026-09-06-analysis-only-agent-design.md)、[Runtime](2026-09-06-analysis-only-agent-runtime-design.md)、[Memory](2026-09-06-analysis-only-agent-memory-design.md)、[設計審核](2026-09-06-analysis-only-agent-design-review.md)、[應用接線](2026-09-06-analysis-only-agent-application-wiring-design.md)、[通知／背景結果](2026-09-06-memory-consolidation-request-wiring-design.md)、[失敗恢復政策](2026-09-06-analysis-only-agent-failure-recovery-review.md)、[Context 預算核對](2026-09-06-context-window-retention-and-budget-wiring-review.md)。

沿用 [前輪 readiness audit](2026-09-06-analysis-only-context-memory-readiness-audit.md) 的五產物／工具盤點與已讀 OpenAI 研究；並完整核對 [引用修復結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-memory-reference-repair-results.md)。**BG-01／BG-02／MR-02 維持 CLOSED**；不因本輪其他反例重開。未讀 Owner 排除的舊 August-12 產品流程長稿。

鎖定套件：LangChain 1.4.0、LangGraph 1.2.11、langchain-openai 1.6.0、OpenAI SDK 3.8.0、Deep Agents 0.7.13；另核對安裝版 ToolNode、ToolErrorMiddleware 與 adapter 原始碼。版本號不是品質證明。

## 2. 整體結論：分工未亂掉，但恢復接線未一致

| 責任 | 實際使用 | 審核結論 |
|---|---|---|
| A 與 B2 的模型↔工具循環 | LangChain `create_agent`／LangGraph | 已用框架，不是另造兩個推理循環；但 B2 循環外的驗證沒有修正回路 |
| 暫時 HTTP 失敗 | OpenAI SDK retry | 沒有再包一層通用模型重試，未見相乘式 retry；配置／帳務錯誤不應當成可修參數 |
| 已解析工具參數錯誤 | ToolNode invocation validation、ToolMessage；部分工具 `ToolException` | 已讓框架回傳模型可讀錯誤；這不涵蓋所有 adapter／循環外錯誤 |
| 呼叫次數限制與接續 | 官方 Model／ToolCallLimitMiddleware＋Checkpointer | A 額度按一次員工輸入計，resume 不重置；不是整份訪談一輩子的上限，也不是金額上限 |
| 原文／延續狀態 | Checkpointer canonical conversation＋非破壞 request view | 原文未被 compaction 刪除；不是第二份自製逐字稿 |
| Memory 讀寫／暫存 | Store／Deep Agents filesystem tools／StateBackend | 已用公開 primitive；虛擬路徑與角色權限是應用接線 |
| B／C 同時發布 | 共用 validator、SQLAlchemy head／receipt、CAS | 既有已同意應用接法；驗證失敗不發布，未知發布先對帳，不讓 LLM 猜成功 |
| 背景喚醒與 API 恢復 | APScheduler、官方 graph resume＋應用分類 | 通知不等待 B；但外層恢復分類會擋住框架可恢復的已知只讀失敗（ER-A01） |

**統一不等於所有例外用同一個 catch／retry。** 應統一「誰能修、錯誤回給誰、花多少額度、最後如何退出」：模型可修的參數／格式回模型，暫時故障由限定重試處理，配置／未知寫入結果停住並查證。這是官方公開原則；目前 A/B/C 的具體組合仍是本案設計，不宣稱是 OpenAI／Anthropic 相同內部實作。來源見 §6。

## 3. 已確認 findings

### ER-A01 · P2／OPEN：只讀工具故障後，服務沒有可用恢復出口

- **位置：**[service.py:316](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/service.py:316) 的 `can_resume` 只放行 transport／process interruption／已知 C receipt；[conversation.py:223](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py:223) 把其他未配對工具結果視為未知副作用。
- **重現：**有效 `read_conversation` 呼叫中注入一次 `psycopg.OperationalError`，再恢復來源 reader。服務仍回 `interrupted / runtime_error / can_resume=False`；重開服務仍相同；resume 被拒，stop 及 abandon 都回 `PublicationUncertain`。同一 checkpoint 用公開 `graph.invoke(None, ..., durability='sync')` 可完成。
- **影響：**只是讀取暫時故障，卻可能卡住整份文件不能繼續。資料沒有因此遭到覆寫，但正常產品出口失效。
- **要求／候選：**沿既有公開恢復入口區分「已知只讀、可安全再執行」與「寫入結果未知」。不能把全部 runtime_error 放行，也不必另造恢復引擎。安全收尾與 resume 都要一起驗。

### ER-B01 · P2／OPEN：B2 最終驗證錯誤停在循環外，模型無法修正

- **位置：**[consolidation.py:181](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/consolidation.py:181) 建 Agent；同函式內 `collect` 在 Agent 結束後跑 `staged_texts`／驗證，沒有回 Agent 的邊。
- **正常分支：**模型有先呼叫 `validate_memory`，錯誤可由 ToolException→ToolMessage 回模型修正；共同 validator 與發布防線有效。
- **反例：**模型寫入不存在詳記引用後直接完成、未呼叫驗證工具；最終 collect 拒絕。resume 仍只執行 collect，沒有新增模型請求，也沒有錯誤回饋供模型修正文。
- **影響：**無效資料不發布，但 B 被 blocked，原樣 resume 無法修好。這是前輪引用修復已提過的循環外限制，**不是引用修復回歸**；本輪將其提升為整體恢復缺口。
- **要求／候選：**把模型可修的最終格式／引用錯誤接回同一受額度限制的框架流程；仍保留發布前驗證。不是依賴 Prompt「記得驗證」、重跑全部 B1，或加無限外部 retry。
- **防禦邊界：**合成 malformed tool JSON 也可走到 collect 後卡住；此類違反 provider 正常輸出契約的探針不代表真 API 常見發生率。前述正常 JSON／錯誤引用反例已足以支持 finding。

### ER-B02 · P2／OPEN：B1 格式錯誤重跑時沒有帶回可修正的錯誤

- **位置：**[extraction.py:156](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/extraction.py:156)：`with_structured_output` 後接 Pydantic／應用文字檢查；無模型修正分支。
- **重現：**回傳合法 JSON，三個欄位都有，但詳記一行 2,001 字，觸發已存在的 2,000 字行長限制。實際 adapter／Pydantic 拋 ValidationError，沒有產物。resume 確實再呼叫模型，但兩次 `input` **完全相同**，沒有上一份輸出或具體錯誤。
- **影響：**重跑可能因模型另生成一份而成功，不是「模型已知道哪裡錯再修」。對同型格式錯誤會浪費呼叫；scheduler 的 blocked 也不會自行讓這個回合取得修正資訊。
- **要求／候選：**用官方結構化輸出／graph error-state 的能力接有界修正；先比較現行 native schema 路徑可用的公開接法。不能只因官方 ToolStrategy 會回饋就宣稱現在的 `with_structured_output` 也會；也不因此逕自把 B1 換成更多工具／欄位。
- **成本檢查：**修復設計先檢查應用格式限制是否必要、能否由現成格式處理完成；不要為純排版增加模型呼叫。需要模型修正的錯誤才交回模型。本輪沒有自行取消既有格式邊界。
- **細節：**本反例的完整 Pydantic 錯誤有存進 checkpoint task.error，**不是完全遺失診斷**；缺的是沒有放到後續模型輸入。不同 refusal／incomplete 分支可能只有程式的 generic error，不應全當模型可修。

### AC-01 · P2／OPEN：歷史 C 刷新指示與新一輪導覽的優先權不夠明確

- **位置：**[live_memory.py:79](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py:79) 說 C feedback supersedes initial guide，未限定本輪；[repair.py:129](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/repair.py:129) 的歷史結果說 initial guide remains historical。
- **重現：**第1輪 C 發布 v2，輪間合成發布 v3；第2輪 system 是 v3 導覽，歷史 ToolMessage 仍含 v2 刷新指示，system 導覽沒有 revision 標記。第2輪真正 read_file 正確返回 v3。
- **影響界線：**已證明 Context 有新舊優先權歧義；**不是讀取 head 回退，也沒有證明自然模型一定答錯**。不列資料污染。
- **要求／候選：**明確只允許本輪 C 結果刷新本輪初始視圖，Runtime 提供適量新鮮度標示；不刪歷史，也不要求模型自己填版本，不必改每個 step 的固定 system prefix。

## 4. Context 有什麼／沒有什麼

| 路徑 | 已放且符合目前設計 | 未放／需注意 |
|---|---|---|
| A 主顧問 | 短顧問規則、Memory 讀取政策、本輪小導覽、當前來源 reference；有效 conversation／opaque reasoning／compaction items；6 個工具 schema；實際讀取結果 | **SK-01** 分析 Skills 尚未接入，不能說已具備研究完整的方法。沒有強制全量正文／全部詳記／B候選／B工具對話 |
| A 長對話 | 無 compaction 時完整已有 items；有時從最新 inline compaction 加其後內容；尚未被壓縮收起的最新 Human 不重複加入，保留切點後必要工具 call/result | 不是固定最近 N 則；本輪早段也可能已進 opaque item，不能承諾永久保留所有細節；完整原文仍在，有可用 reference 時可由 reader 回查 |
| A 背景狀況 | B blocked 時下一正常 run 放短提示及真實 target_reference，恢復後可消失 | 不例行另外叫 A、不灌入 B 的全文／錯誤堆疊；通知 artifact 不進模型 wire |
| B1 抽取 | 抽取 Prompt、NEW_SOURCE 可見問答、CONTEXT_ONLY 消歧前文、回合結束狀態 | 不以 A 壓縮摘要取代原文，不提取 A 隱藏推理；模型格式錯誤缺後續回饋（ER-B02） |
| B2 整併 | 整併 Prompt、新候選＋詳記地址、目前小導覽、可讀暫存正文位置；需要時才讀詳記；stale 時相關修補問答 | 舊正文不直接全灌、候選不等於正式知識；最後校驗錯誤缺回圈（ER-B01） |
| C 修補 | 主顧問已讀的內容、精確小批編輯；Runtime 的來源／版本／發布身份；結果回 A | C 不另呼叫模型、不執行整段 B；歷史刷新指示需限定時效（AC-01） |

**CT-01 仍未完成：**目前有 compaction threshold、單次 output limit、timeout、model／tool 次數上限，但未核對「固定規則＋tool schema＋guide＋有效對話／結果＋輸出餘裕」的完整 request 預算。API 也沒有與模型容量對應的輸入長度邊界。這不是已觀察到真 API 超窗；是既定能力未接。應先沿 [官方 counter／adapter 研究](2026-09-06-context-window-retention-and-budget-wiring-review.md) 補全，不再另造摘要 Agent 或靜默截掉員工原話。

**不是每項沒注入都算缺漏：**沒有強制每輪自動向量召回、沒有把全部 Memory 放入 Context，是目前已選策略；同一段來源用於 A 對話與 B1 抽取是不同模型責任，不是同一 request 重複灌入。真正要處理的是 AC-01 的過時指示與 budget／Skills 缺口。

**前輪可達性邊界維持未決：**有詳記／Memory 引用時能逐層找原文；若舊話已被 compaction 收起、又沒有任何 Memory／詳記入口，目前沒有一般 raw-history 搜尋工具。資料保留不等於模型必定找得到。另 `grep` 固定總量上限4與框架「提高 max_count」提示不一致。這兩項沿前輪 MR-03／read-path 邊界處理，不自行新增向量庫或改 Memory 架構。

## 5. 驗證與排除的誤判

主審以真實鎖定 framework／adapter／SDK＋`httpx.MockTransport` 重跑：

```text
uv run --no-sync pytest -q tests/test_extraction.py tests/test_consolidation.py
  tests/test_native_continuity.py tests/test_agent_runtime.py --tb=short
66 passed in 9.78s
```

另用既有測試 harness 的 stdin 探針，沒有修改程式或測試檔：

| 探針／重做入口 | 觀察 |
|---|---|
| ER-A01：`test_service.service_harness`＋記憶體 SQLite／Saver／Store；有效原文引用，reader 暫時 OperationalError | 恢復故障／重開仍不能 resume、stop、abandon；同 checkpoint 公開 graph resume 可 completed。主審與獨立 reviewer 重現 |
| ER-B01：`test_consolidation.harness.__wrapped__()`；write_file 不存在引用、done、不先 validate_memory | 無發布；start／resume 同錯、resume 不增加 model request。malformed JSON 另作防禦探針 |
| ER-B02：`test_extraction.harness.__wrapped__()`；合法三欄 JSON，summary 一行 2,001 字 | ValidationError；resume 的輸入與首次相同；注入第二個有效回覆後成功，證明不是錯誤回饋修復 |
| AC-01：`test_live_memory.h.__wrapped__()`＋真正 `build_conversation`；C v2→輪間合成發布 v3→新輸入 | v3 system 與歷史 v2 刷新指示同時上 wire；實際 read 正確 v3。未執行真正 B 或自然模型判斷 |

排除：B1／B2 輸出上限不尊重部署設定的疑點，實際 wire 尊重配置；`store:false` 未填 `include` 不是已核對版本的 reasoning 遺失 bug；一份 system 逐層添加沒有丟掉原 instructions；最新 Human、六個工具 schema 未重複註冊。歷史技術提示可能保留在 wire，未證明其造成模型錯誤，不另立缺陷。

獨立 reviewer 補充非 object JSON `[]／42` 會在 adapter 建 AIMessage 時失敗，未回 ToolMessage；這是刻意違反 native 正常輸出契約的防禦觀察，**不列重要產品缺陷、不以此要求 private converter patch**，真 API 發生率 unknown。

以上測試證明接線／反例，不證明 Luna 長訪談語意品質、完整率或付費成本。沒有跑新的大型 eval、PG 或真 API；前輪370項是歷史驗證，不能與本輪66項相加當覆蓋率。

## 6. 官方依據與適用範圍

- **OpenAI official fact：**[Function calling — formatting results](https://developers.openai.com/api/docs/guides/function-calling#formatting-results) 允許以 tool output 回傳成功／失敗與錯誤資訊，支持把可處理結果交回模型；沒有承諾 SDK 自動判斷應用錯誤或修復外部資料。
- **Anthropic official fact：**[Handling tool errors](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error) 使用配對 tool_result 與 is_error，提供可理解的錯誤供 Claude 修正。這是可學的循環概念，不直接套 Anthropic wire 到 OpenAI。
- **LangGraph official fact：**[Thinking in LangGraph — handle errors](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph) 區分暫時錯誤、LLM 可恢復錯誤、人需補資料與未知錯誤；模型可恢復的工具／解析錯誤應寫到 state 再回模型。支持 ER-A01／B01／B02 的接線方向，不替本案決定重試數值。
- **LangChain official fact：**[Built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) 的 ToolErrorMiddleware 處理選定執行例外，**不自動重試**；參數驗證由 ToolNode 另處理，ToolRetry 是另一種責任。不能裝一個 middleware 就宣稱涵蓋 adapter、最終 collect、資料庫未知寫入。
- **LangChain official fact：**[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output) 的 ToolStrategy 可回傳 validation feedback 並修正；需核對實際路徑，本案 B1 是 native schema＋Pydantic，不是該 Agent ToolStrategy。
- **OpenAI official fact：**[Server-side compaction](https://developers.openai.com/api/docs/guides/compaction#server-side-compaction) 以 threshold 觸發、回傳 encrypted compaction item；stateless client 可移除最新 compaction 前的 request items。支持目前非破壞視圖，不代表 app 保存的 canonical 原文應刪除，也不是整包請求的獨立預算驗證。

**Inference／本案建議：**保留已接好的 A/B/C 與原生框架，優先修 ER-A01 的恢復出口、B1/B2 可修錯誤的回饋，再收斂 AC-01 與 CT-01／SK-01；不換整套 Memory、不增加一個統籌重試 Agent。細部 patch／額度與測試方案待下一個設計／施工 gate；本輪不默默翻案。
