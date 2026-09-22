# JD 前景 AI 回合與具名工具：RS-4 局部接合

日期：2026-09-13。Topic：JD-R002／`experiments/jd-relational-app`。**本程序 AI 回合與工具局部接合通過，獨立窄複核 PASS。**本文記錄工具、原生 checkpoint、共用 writer 及固定 SDK／真 PG 接合，沒有宣稱整體 RS-4／App 或自然顧問已完成。ADR0075 仍為 Proposed，ADR0060 production authority 不變。

## 1. 本次效果與目前狀態

固定串流回覆已經能透過真正前景 owner 讀取目前 JD、一次新增含多筆成果與要求的任務，結束後接受同 owner 的人工更正，再開始新 AI 回合讀取人工通知及目前內容、續改任務。純訪談也能完成而不增加 JD revision。SQL 已提交但確認回覆遺失時，本程序沿原 operation 查回 committed receipt，補原 call 的真實結果，不重新執行命令或續叫模型。

這些效果有四個真 PostgreSQL／原生 PostgresSaver／實際 Agent 與 SDK 接合案例。SDK 全由程序內 `httpx2.MockTransport` 回固定合成 SSE，**10 次 SDK 請求、0 provider**。它們驗接合與保存事實，不驗模型自行選擇工具、自然職務分析品質或真人使用。

本輪補齊的 coordinator 邊界：

| 項目 | 最後實作與驗證 |
|---|---|
| 開始回合的同步讀取錯誤 | `start` 的未知錯誤映固定 checkpoint_unavailable；原始 driver marker 不出現在公開錯誤。 |
| close 與同步讀取交錯 | 原請求查回由同 owner 的 inspect_foreground_start／同文件 slot 與短期 start token 包住；close 必須排空，重入也看見 token。此 token 不授予 SQL 寫入權。 |
| caller 不再等待 handle | 原生 Future callback 由 App 自動收尾一次；wait 只等待完成 Event，不持鎖做 DB。失敗保留原 handle，明示 recover 只查原結果／補閉合，不重播。callback 另等待 owner 自身 settled，避免「Future 已 done、較早 callback 尚未結束」的真競爭。 |
| 初始輸入保存失敗 | 固定原生 START input 可保留原 Human／舊對話並閉合；所有 put 均失敗只有在原本 idle、前後固定位置與內容未變、無工具／SQL 且真 Future 停止時回 input_saved=false。不能只憑 run_not_found 解鎖。 |
| coordinator 唯一性 | 同 owner 原子 claim 一個 coordinator；不同實例不能共用原生 foreground handle 卻各持不同 attempt／codec。重開用新 owner；同實例重送取原 handle。 |
| 最終受影響組／全組／生成 | §6 分別記全組、最後窄組與真 PG，沒有把重疊數字相加。 |

## 2. 官方依據與本案取捨

本次沿已選組合，**沒有新增或升級依賴**。適用 LangChain 1.4.0、langchain-core 1.6.3、LangGraph 1.2.11、checkpoint 4.2.0、PG Saver 3.1.2、langchain-anthropic 1.7.2、Anthropic SDK 1.5.0 與 Python 3.12.13；框架套件的 MIT／Python PSF 授權、既有 adapter 精確相容證據沿[前次結果](2026-09-13-jd-consultant-context-slice.md#2-官方依據版本與本案映射)及[版本附件](evidence/jd-relational-context/adapter-versions.json)。商業模型服務與本機套件授權分開，本輪沒有模型費用。

三份本轮前置各保存其研究範圍、原碼位置與限制：

1. [前景 owner 前置](evidence/jd-relational-ai-runtime/ownership-preflight.md)：同文件 gate、真 Future、取消及程序內／跨宿主證據。
2. [原生 admission checkpoint 核實](evidence/jd-relational-ai-runtime/admission_checkpoint_notes.md)：`after_model`、`sync`、ToolNode 次序及五個合成探針。
3. [具名工具前置](evidence/jd-relational-ai-runtime/tool-preflight.md)：generated schema、ToolRuntime 注入、原生 validation／callback 限制與固定錯誤出口。

以下官方來源均沿上述 2026-09-13 查閱證據，不另作同層品牌比較。

| 官方事實 | 本案實際映射與限制 |
|---|---|
| [AWS 安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)以 caller request identity 辨識原意圖，保留可重複取得的原結果，將識別與變更的持久化一起處理。 | 模型 call ID 負責對話配對；App 另配 operation UUID，保存 request digest／原 base。JD mutation 與永久 receipt 沿既有共同 SQL 交易；未知先查原 identity，不能換 key 重做。Saver 與 JD SQL 仍是兩個交易，沒有跨兩者原子性宣稱。 |
| [AWS hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)支持不同輸入共用業務規則、隔離外部服務，也有額外抽象成本。 | 人工與 AI 同用 domain、intents、JdStorage、receipt 投影；模型與 Web 不各寫一份業務 invariant。新增有限工具／模型／checkpoint 接點，不新增通用 Agent loop 或第二套 repository。AWS 沒有指定十三表、工具名稱或此處 binding 格式。 |
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#how-it-works)及[Anthropic tool result](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)均要求結果對應原呼叫。 | 原生 AIMessage／ToolMessage 保留 call identity，Anthropic mapper 使用原 `tool_use_id`；OpenAI 既有外殼使用 `call_id`。本輪真 Agent／SDK 接合只有 Anthropic，沒有新增 OpenAI runtime 或真 provider 驗收。call 配對不授予 DB 寫入權。 |
| [LangChain middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)與[工具](https://docs.langchain.com/oss/python/langchain/tools)提供獨立 `after_model` 節點、StructuredTool、JSON Schema 和隱藏 ToolRuntime 注入。 | 使用原生節點與工具分派，generated DTO 產出模型 schema，參數仍由共同 parser 驗證。不靠 callable 類型提示再造一份近似契約，也不自己寫 ToolNode／重試迴圈。 |
| [LangGraph checkpoint](https://docs.langchain.com/oss/python/langgraph/checkpointers)的 sync 在下一步前保存；replay 可能重執行後續模型與外部呼叫。 | 實際入口明示 `durability="sync"`，讓 binding 先進原生 checkpoint 再進工具 SQL；恢復只觀察固定 root／child 與原 receipt，不 invoke／resume 未完成 graph。 |
| [Python Future](https://docs.python.org/3.12/library/concurrent.futures.html)的 timeout 不停止 running callable；同 pool 的相依等待可死鎖。 | Agent 與 SQL 使用分開且有界的原生 pool，共用同一文件 owner。取消是 Event；真正 Future／SQL／持久閉合完成前保留 gate。跨程序死亡另需 OS 證據。 |
| [LangSmith selective tracing](https://docs.langchain.com/langsmith/trace-with-langchain#trace-selectively)允許以 tracing_context(enabled=False) 覆蓋環境的自動 tracing。 | run 的實際 graph invocation 關閉自動外部 trace；原生本機 Saver 仍保存原始對話。此設定不宣稱能阻止任意新增的自訂 callback，App 不注入該類外送 sink。 |

共同原則是原呼叫／結果配對、明確執行與保存責任、未知不盲目重做。文件 slot、七欄 operation identity、十二欄 AI binding、結果文案及停止條件是本案設計，不稱作大廠共同指定格式。

## 3. LLM 與 App 各自負責什麼

| 責任 | LLM | App／原生元件 |
|---|---|---|
| 訪談與正文 | 依已知工作選擇讀取或修改，填既定業務欄位；可以只訪談、不改稿。 | 保留原始 HumanMessage、完整 AIMessage 與原生內容塊，不用通知或補寫訊息替代原話。 |
| 工具參數 | 只填 generated input 的具名欄位、內容與已取得的 opaque refs。 | 十個工具由既有 generated DTO 的 `model_json_schema(mode="validation")` 產生；App scope／runtime／DSN／authority 不在模型 schema。共同 parser 仍負責實際驗參數。 |
| 版本與操作身分 | 不填 document／dataset／run／operation UUID、revision、digest、row ID／FK／position。 | 宿主注入 scope、真正 foreground permit、read/change/history ports、codec；App 配新項目與 operation 身分。 |
| 寫入基準 | 必須先取得本輪實際 `jd_read` 結果，按工作所需讀取頁面。 | 成功 current、current item／section 的真 ToolMessage 綁 exact B；核 message／call ID、content digest、用途與 scope。通知 `jd_model_view` 不是已讀 JD 的證明；history／change 不能升為可寫基準。 |
| 完整操作與保存 | 新任务和多成果／要求一次傳完整命令；相依更正沿原具名效果。 | 共用 command_context、bind_edit、domain 與 SQL 交易核最終候選；不把完整任务拆成逐欄半存。read 的分頁、has_more、cursor 與 oversized_unit 保留，不偷偷补完整正文或混入新 head。 |
| 來源與選區 | 只能使用真正接點交付的引用，不能自造來源／offset。 | 本輪沒有 source owner 或 selection issuer；非空來源／選區要求安全拒絕。空 `basis_refs` 是無新增來源，不是宣稱内容已有原話證據。 |
| 保存結果 | 讀取真實結果再決定後續；不得自行宣告 committed。 | confirmed receipt 才投影原結果；已 bound 而結果未知停止 graph，原 identity 查回。共同結果契約不接受模型自填 App 保存欄位。 |

原生 `ToolRuntime` 在 function signature 隱藏注入。使用 JSON Schema dict 是為避開已觀察的「closed DTO class 連 runtime 一起驗證」衝突，不是放棄 strict validation。已知無效參數在 `after_model`／wrapper 共同 parser 接點攔下，避免 ToolNode 預設錯誤把原 kwargs 回送，並阻止該無效工具進入 `on_tool_start`。一般有效工具的 canonical 參數仍屬原對話紀錄；不能把「錯誤文案安全」誤稱任意 callback 都安全。

實際 SDK 請求已核 `strict=true`、禁止平行工具，以及模型呼叫所在官方 tracing context 為 disabled。App 另外拒絕一個 AIMessage 帶多於一個 tool call，沒有把 provider 設定當權限保證。此處不新增通用 scrubber 或任意外部 trace sink。

程式落點：[tools](../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py)、[coordinator](../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py)、[AI checkpoint](../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py)、[共同 owner](../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py)、[既有保存](../../experiments/jd-relational-app/src/jd_relational/storage/service.py)。

## 4. 已接合的保存與本程序恢復路徑

1. 本機前景 owner 在同文件 slot 准入原 run，自己持有真正 Agent Future；純訪談也佔用同一 gate。root／child 共用原生 channels，graph input 保存原 HumanMessage 與 run descriptor，不建立新 run 表、第二份聊天或 JD 草稿表。
2. 模型完整回覆經原生 model node 保存，`after_model` 核唯一 call、scope、既有 call digest 與本輪 read binding。mutation 只以 exact B 的歷史材料組 command_context／BoundEdit，不在寫入時讀新 head 假裝模型已看過。
3. native state 只追加恢復所需 binding：原 operation identity、dataset／run、AIMessage ID／call ID 及 canonical input digest。完整 command 已在原 AIMessage；含 callable 的 BoundEdit／context 留在本 run 記憶體 cache。遺失 cache 不重新讀來源、重綁或產生新 operation。
4. `after_model` 的 **sync checkpoint 成功後**才進原生 tools node。工具比對原 binding 與 cached BoundEdit，owner 再核同 run permit／真正 SQL Future／執行 context，交共同 JdStorage。四案中的正常旅程亦在 SQL 入口從真 PG Saver 觀察並比對已保存 identity。
5. confirmed ordinary result 用既有投影及 transport 驗證，成為原 call 的 native ToolMessage；不把整個 provider 外殼再塞進 content。已確認的正文保存，不因較晚 checkpoint／cleanup 錯誤改稱 save_failed。
6. mutation 未綁定時缺本輪 current read／混入不可寫歷史引用，回共同 `invalid_input`、unchanged／unconfirmed、三 refs=null、`reread_current`；這是本輪只擴充該 unbound 變體的 next_action，不捏造 stale receipt。source／selection 未接回固定不可用結果。
7. 已綁定而結果未知時，固定 pending 例外停止 graph，保留原 binding，不再叫模型。真正 run／SQL Future 結束後，coordinator 用共用 decoder 核原 AIMessage／call／參數 digest，先查原 receipt；必要時沿 owner 的 failure-only recovery。恢復不需要 live BoundEdit，也不執行原 command。
8. 已保存的 ToolMessage 與原 receipt 核對；尚未配對的原 call 補真實 committed／失敗／未執行結果，固定 root 閉合並 exact readback 後才解除 gate。當下 codec 的確定性 token 讓同 key／dataset 投影可核原內容；**跨 key rotation 的結果核對未在本輪驗收**。

回合結束由 App 自動收尾，與呼叫者是否仍等待分開。`wait(timeout)` 只觀察完成，不以 timeout 中斷工作或重新執行；自動閉合未確認時保留 gate，`recover()` 是顯式對帳。關閉只對仍未結束的前景工作要求停止，不能把已成功完成的回合改標 cancelled。初始 Saver 的特殊狀態與明示單次閉合依[原生 START 探針](evidence/jd-relational-ai-runtime/initial-checkpoint-probe.md)，不以清 tasks 或 graph resume 冒充恢復。

本程序 owner 的實際 Future／attempt token 是寫入資格；空 Future、timeout、外部 bool、tool call ID 或 graph 字串 status 都不是停止證明。原生 checkpoint adapter 的 close 只管固定保存位置，caller 仍必須先完成 Future／receipt／完整 call-result 配對。這些接線由[工具與 checkpoint 獨立審查](evidence/jd-relational-ai-runtime/tool-checkpoint-review.md)列明，不能單憑 adapter PASS 宣稱整個 coordinator 已通過。

## 5. 首敗與審查處理

| 證據 | 首敗／修正與目前界線 |
|---|---|
| [原生 admission 探針](evidence/jd-relational-ai-runtime/admission_checkpoint_notes.md#五個可重現結果) | 五個合成探針含 async 反例：預設 async 可讓工具先於 binding 保存，故正式入口必須 sync。初兩個接法錯誤是 probe command key／namespace 用法，修正後取得證據；不是產品 SQL 測試。 |
| [owner OR-R01](evidence/jd-relational-ai-runtime/ownership-review.md) | 發現已 done recovery 捕捉的 context 在同一 pool thread 重用仍可能過門閘。manual／AI × done／下一 recovery 四紅例後，綁 exact attempt token 並要求本次原生 Future 仍 running。作者受影響回歸 **92 PASS／0.80s**；另由獨立 reviewer 重跑四反例 PASS。 |
| 工具單測 | 新模組未建立先有 collection error；初實作 **7 FAIL／7 PASS**，主要為測資沿用舊 CreateTask 外形，修成正式 container_ref／after_ref 等後 14 PASS。後續恢復測試曾把已完成後的舊 AIMessage 當作 pending 最新訊息，修測資後 35 PASS；加 current item／section 後 **37 PASS／1.71s**。沒有為過測放寬 schema。 |
| 本輪真 PG 接合 | 首跑 **2 FAIL／2.66s**，是固定回覆測資錯用 `owner_item_ref`，generated ContainerRecord 實為 `owner_ref`，MockTransport 內 KeyError 被 SDK 包成 connection error；只修測資。修後 **2 PASS／2.89s**，再加純訪談／取消及 tracing 核對後 **4 PASS／3.42s**。 |
| [coordinator 獨立審查](evidence/jd-relational-ai-runtime/coordinator-review.md) | 前置錯誤、start/close、無 observer 三個紅例 **3 FAIL → PASS**。後續抓到 callback 註冊競爭，再有 **1 FAIL → PASS**；修為明確等待 owner callback 完成。25 個 coordinator 測試含上述、六個初始保存故障、新舊回覆區分及原子唯一 claim。 |
| 初始 START 保存 | helper 原本拒絕只有 input checkpoint 的已保存原話，四紅例後新增固定 Saver tuple 讀取，**52 PASS**。另有八個 native 初始情境與一個清 task 反例；coordinator 六例再核 actual owner 關閉與 input_saved 真值。 |

## 6. 分層驗收紀錄

以下是各自執行的紀錄，**彼此有重疊，不能加總成獨立案例總數**。研究探針、原生記憶體測試與真 PG 證據也不互相代替。

| 層級與來源 | 實際結果與可證範圍 |
|---|---|
| 原生接法研究 | [admission 五探針](evidence/jd-relational-ai-runtime/admission_checkpoint_notes.md)及[工具 schema／validation probe](evidence/jd-relational-ai-runtime/tool-preflight.md#3-原生框架的三個實際限制)。InMemorySaver／固定回覆／合成 SQL 邊界；不是資料庫或 provider。 |
| 共同 owner 修正回歸 | [ownership review](evidence/jd-relational-ai-runtime/ownership-review.md)：92 PASS，含真 Future／thread 與合成 storage/checkpoint、人工／目錄／startup 回歸；無真 PG／OS host。 |
| 原生工具單測 | [test_consultant_tools.py](../../experiments/jd-relational-app/tests/test_consultant_tools.py)：37 PASS。generated 十工具 schema、無 App 參數、先 checkpoint 再模擬 writer、非法參數／錯 scope／history 不可寫、錯 message digest／缺 cache、unknown 停模型、confirmed 不降級、current item／section。真 create_agent／InMemorySaver，history／owner 為合成 ports。 |
| 工具與 checkpoint 獨立窄審 | [review](evidence/jd-relational-ai-runtime/tool-checkpoint-review.md)：兩測試檔 **71 PASS／2.03s**，範圍無未解 P1／P2；caller preconditions 及 coordinator 明示排除。這包含前列工具單測，不再加總。 |
| 真 PG／Saver／SDK 接合 | [test_ai_runtime_postgres.py](../../experiments/jd-relational-app/tests/test_ai_runtime_postgres.py)：**4 PASS／3.42s**，10 次真 SDK 請求全部 MockTransport，0 provider；細節如下。 |
| 最終 coordinator 與受影響組 | 最後程式的 **253 PASS／4.04s**：coordinator25、AI checkpoint52、tools37、context17、model30、foreground／manual／catalog／startup92。另重跑真 PG **14 PASS／6.43s**（本輪4、既有manual8、context2），與其他列重疊。 |
| coordinator 獨立複核 | [最終 review](evidence/jd-relational-ai-runtime/coordinator-review.md) PASS，無未解 P1／P2；先前四檔126 PASS、最後25 coordinator PASS分別記錄不加總。CR-R01／02、callback註冊競爭與OR-R01均保留首敗與修後證據；兩個新增 start-token gate 探針也拒絕重入寫入。 |
| 全組與生成檢查 | 最後 callback／唯一 claim 窄修前全組 **1766 PASS／197 PG SKIP／1第三方棄用警告**；上述最後253窄組包含新4例及全部受影響元件，不冒稱是全組重跑。生成 Python／TS 一致，專案 tsc --noEmit 通過；未改 UI，不重跑無關 Web build 或自然模型。 |

四個 PG 案例使用明示 opt-in 的 PostgreSQL **18.6**、localhost:55436 專用合成 DB，以及既有 `jd_runtime_test` 原生 PostgresSaver schema。沒有 setup、drop、刪合成資料或讀真設定／provider key；fixture 不使用 FakeAuthority 證明 AI 准入。

| 真 PG 案例 | 固定 SDK 請求與實際斷言 |
|---|---|
| AI 初稿 → 同 owner 人工更正 → AI 續編 | 6 次。`jd_read → jd_create_task → final`，手改 task description，再 `jd_read → jd_set_text → final`；不是已實跑所有十個工具。兩個成果、一個要求保存；人工範圍、原其他欄位與 detail IDs 保留。兩次 AI SQL 前真 Saver 已有 exact binding；head 1→2→3→4、三個 operation；第二輪 notice 指向原 manual operation，完整 HumanMessage／AIMessage／model-view 配對保持。 |
| SQL COMMIT 確認回覆遺失 | 2 次。只在真正 storage.execute 期間注入「先 do_commit 再失去 ACK」；fault marker 必命中。恢復後原 receipt 仍 committed，原 call 得 success ToolMessage；1 execute、1 task、head2／1 operation，沒有第三次模型回覆。run 以 failed 如實結束，不把已提交的 JD 改稱保存失敗。 |
| 純訪談與只讀重開 | 1 次。没有工具寫入，仍 head1／0 operation，完整對話及 terminal run 保存；關 connection 後新 Saver／graph 只讀相同資料，沒有新模型請求。 |
| 取消與真正 Future | 1 次。合成 response 在已進入原生串流後用 Event 阻塞。要求取消與 wait timeout 後仍 running／blocked，metadata 新寫拒絕、close=false；釋放真正串流後才保存 cancelled root。沒有假的 AI 完整回覆或新 model-view，仍 head1／0 operation。 |

所有上述 SDK 請求均在 `receive` 核對十工具的 strict=true、`disable_parallel_tool_use=true`，以及 `get_tracing_context()['enabled'] is False`。測試的 HTTP transport 不開 socket；並非連 Anthropic 取得免費或付費回覆。

重現工具單測：於 `experiments/jd-relational-app` 使用既有 uv lock，設定 `PYTHONUTF8=1`，執行 `uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_consultant_tools.py -q -p no:cacheprovider`。真 PG 接合另明示 `JD_RELATIONAL_TEST_DB=1`，以同命令執行 `tests/test_ai_runtime_postgres.py`；資料庫與 Saver schema 未明示初始化時不由測試自動建立。

## 7. 未完成界線與下一個最小工作

下一單位先完成新宿主面對原 AI pending 的安全恢復，再接聊天 HTTP 的原請求查回／狀態／取消，沿原計畫接真正相依能力，不重開框架選擇或改欄位政策：

- **來源／Memory／選區：**現 factory 保留十個契約形狀；`jd_replace_selection` 尚無 selection issuer，非空 basis 尚無真正原話／Memory source resolver。已驗安全拒絕，沒有宣稱實際選文編輯或來源追溯完成。原生 Saver／Store／原話仍沿既定單一權威，不建立替代 Memory 或假 handle。
- **foreign-host AI restart：**本輪證明同程序的真 run／SQL Future 與原 receipt 收尾；新宿主沒有舊 local Future 不等於前程序已停。既有 Windows host／manual startup 成果不能代證 AI child 恢復；未知 AI pending 仍需保持阻擋，另接真正 OS proof 與原 native checkpoint，不能 replay。
- **HTTP／聊天 Web：**沒有 AI chat HTTP、Web 串流／取消／重連與日常 host 組合的本輪完整驗收；既有人工管理畫面不能代稱已接 AI 顧問。
- **故障與完整旅程：**尚未以本輪真 PG 案例覆蓋每個工具、部分成功後第二項取消、所有 Saver admission／tool-result ACK 故障與跨程序恢復。無 caller 自動閉合與初始 Saver 故障有真 Future／InMemory 原生案例，未代稱新程序／PG全面故障驗收。sync 入口的證據不推成整套 async 工具取消保證。
- **自然顧問與產品：**10 次回覆均由測试程式指定工具／參數，不驗自然選工具、工作完整性、反覆更正、壓縮後回查、Memory 採用、整輪 JD 撤回或真人品質。自然模型仍須另有可審資料、呼叫數與費用授權；Excel／原話匯出延後有效，整體 G4／G6 不因局部 PASS 改判。

本稿不變更六章欄位、純文字換行、全手動 CRUD、AI 直存、共享 K/S 多對多或既定保存語意。
