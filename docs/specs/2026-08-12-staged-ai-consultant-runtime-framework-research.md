# AI 專業職務分析顧問：framework-first runtime、Context Engine 與記憶研究

- 日期：2026-08-12
- 狀態：Research / Proposed；供 owner、架構討論者與後續實作者評估
- 決策狀態：尚未形成 ADR，未授權 production 實作
- 需求來源：owner 提供的階段表、現行 Job Analysis／OPKS 研究與本 repo 現行程式
- 核心問題：哪些通用 LLM 元件應由主流框架替代；哪些職務分析能力必須保留；如何在正確時機放入正確 context，同時控制成本

> 2026-08-12 後續澄清：owner 已先收斂產品流程、動態 Skills、記憶權威與 Context Engine 的產品層方向；以 [`AI 專業職務分析顧問：產品流程工作研究稿`](2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) 為優先。本文的「stage」一律只表示可回跳的 attention／operation mode；固定 Context lanes／budget、LangGraph／LangChain 組合與欄位名稱都是待 conformance spike／後續 eval 的 framework 候選，不是已核准產品狀態機或實作決策；兩份文件衝突時以前者為準。正式 eval、benchmark、A／B 與量化品質 gate 已裁示延至可用成品完成後；開發期只保留既有工程測試、authority safety、介面 conformance、簡單人工 smoke 與可回溯紀錄。
>
> 2026-08-13 責任分界確認：框架可以取代或包裝通用工程機制，Caliburn 保留產品語意與 authority；「保留」不等於所有底層程式都自行維護。LangGraph 是目前推薦的外層 runtime 候選，但仍須先證明它能忠實承接既有 durable input、Journal、generation／read-set 與 authority transaction，不能把推薦寫成已 Accepted 的框架決策。
>
> **2026-08-13 後續取代警示：**產品工作稿已確認 AI 顧問子系統採隔離 worktree 內的受限 Big-bang、fresh-schema hard cut，並把 iCAP Reference／RAG 納入同一次 final gate；先完成核心顧問、後接 RAG，再一次切換。本文原先的漸進 phase、`Wrap` 既有 runtime、LangGraph 優先順序與「RAG 延後到未來」只能作候選能力與風險研究，**不再是現行遷移順序或實作者 plan**。後續應先依產品工作稿建立 framework-neutral 目標能力與 `Replace／Wrap／Retain` 矩陣，再重寫本研究結論；在此之前不得依本文 §15 直接施工。
>
> **2026-08-14 現行 successor 警示：**上段本身又被後續 owner 裁決取代。現行權威是產品工作稿 §9.12–§9.16、Accepted ADR 0060、Accepted ADR 0061（schema-only）、`docs/design/consultant-runtime.md` 與北極星帳本：主 runtime 已定 LangChain／LangGraph，舊 Work Model／Focus／Progress／Proposal／Current JD lifecycle 已 hard cut，**本次不接 RAG**。本文仍保存市場研究與 Evidence 標準盤點，但凡出現「保留舊 domain tables／SQLAlchemy aggregate」「RAG 納入同次 final gate」或舊元件名稱，皆只作歷史候選，不得據此施工；Tool／Skill loading 尚未因 ADR 0061 獲得變更授權。

## 0. 結論先行

建議採用「framework-first、domain-owned authority」的**目標候選**：

1. LangGraph 1.x 候選管理外層 bounded application run、checkpoint、resume、必要 interrupt 與 failure boundary；採用前須與現有 durable turn 做 conformance。
2. LangChain 管理 model interface、tools、structured output 與 context lifecycle；需要工具迴圈的單一 operation 才使用 bounded agent node。
3. langchain-openrouter 優先取代自寫 OpenRouter HTTP／structured-output plumbing，但必須先通過 Caliburn 的 exact-model、單一 endpoint、零 retry／fallback 與 execution evidence 相容測試。
4. Agent Skills 規格保存已研究驗證的 Task／Duty／OPKS 方法；優先使用唯讀 SkillsMiddleware 做 progressive disclosure，不採整套 Deep Agents。
5. Pydantic、SQLAlchemy 與 PostgreSQL 繼續負責 typed domain model、transaction、constraint 與 persistence；先深化既有框架能力，再增加新 state／event framework。
6. W3C Web Annotation 候選改善 quote anchor；W3C PROV 語彙候選改善 lineage mapping，但不導入第二份 RDF／evidence truth。
7. 可用成品完成後，再評估以 Pydantic Evals 作為 repo-owned eval runner；目前不建立資料集、grader 或 eval release gate。
8. 未來 RAG 以 read-only tool／MCP 形式接入；在 ADR 0057 邊界被新 ADR 翻案前，不得接入 current production。

保留的不是目前每一行自寫程式，而是下列產品行為：

- 工作分析、Task boundary、Duty、5W1H、O/P/K/S 的方法與 rubric；
- Source Layer、Work Model、Proposal、Current JD 的權威分層；
- 逐字 quote、說話者、修正／矛盾、employee approval 與 authority commit seam；
- provider 在 transaction 外，commit 前重鎖並驗 generation／read-set；
- Current JD 只能由員工直接編輯或員工對 Proposal 的決策改變；
- 一份 document 的資料與記憶不得洩漏到另一份 document。

一句話：

> 框架負責通用 runtime；Caliburn 負責「怎麼做專業職務分析、什麼算證據、誰有權改文件」。

圖片中的八個階段應視為「可回跳的工作區與注意力模式」，不是八個 Agent，也不是只能由上往下走一次的 wizard。

## 1. 本研究的邊界與權威

### 1.1 產品範圍不變

本研究不把產品擴張成 SaaS、多租戶、多人協作或帳號系統。owner 新增的「記得別人說過什麼」解讀為：

- 在同一份職務文件內，保存多位說話者或被轉述者的可追溯陳述；
- 不建立登入、member、organization 或 ACL；
- 不跨 document 共用個人記憶；
- 不把「某人說過」自動升格成「已確認工作事實」。

### 1.2 現有研究是 domain 資產

下列能力已研究、落地或有 Accepted ADR 支撐，不應被通用 Agent prompt 覆蓋：

- Task 的 action／object／meaningful outcome、merge／split／identity 判準；
- 每輪高召回吸收新訊號，再選一個最高資訊價值焦點；
- Source Layer、Work Model、Document Layer 三層權威；
- OPKS 以單一 Task 為生成粒度，O/P 綁 Task、K/S 文件層多對多、A 文件層；
- 公版 blind-first，後段只作 challenger；
- quote 必須為合法來源的逐字片段；
- AI 只提候選，員工才有 Current JD authority；
- 資訊不足可留空、uncertain 或 gap，不為填表而虛構。

要保留的是這些行為與測試，不是 context.py、wire.py 或 verifier.py 現有行數。

### 1.3 研究證據優先序

本研究採：

1. repo 現行 code、AGENTS.md、Accepted ADR 與 design 文件；
2. OpenAI、Anthropic、LangChain、Pydantic、Google、Microsoft、AWS 官方文件；
3. W3C 等正式標準；
4. 官方框架文件與原始研究；
5. 其他資料只作候選，不覆蓋前四層。

## 2. 需求不是一般聊天機器人

owner 的階段表至少包含：

1. Reference 搜尋與 ICAP 候選挑選；
2. 工作故事與 Duty／Task 骨架；
3. 待訪談線索與未完成清單；
4. 主要 Duty 深入分析與 Task 補齊；
5. 候選內容的人工作業；
6. 單一 Task 的 5W1H、Output／Performance 分析；
7. K/S 候選的人工作業；
8. 右側正式 JD 的增刪改與完成。

但員工可能隨時：

- 補充新故事或另一項工作；
- 更正頻率、所有權、主管權限或目前／過去狀態；
- 返回先前 Duty／Task；
- 拒絕候選、要求修訂或直接編輯 JD；
- 提到原本不在 agenda 的高價值工作；
- 說不知道、不適用、暫時不談或要求停止。

因此正確形狀是：

~~~text
固定分析責任
  + 可回跳的 bounded application run
  + 每個 focus／operation 有限 model judgment
  + durable Proposal 與獨立 employee decision command
~~~

不是：

- 八頁固定問卷；
- 八個人格化 Agent；
- 一個能任意規劃、任意選工具、任意寫文件的自由 Agent。

## 3. 推薦目標架構

~~~text
Web / API
   │
   ▼
Application command
   ├─ Source acceptance transaction
   └─ durable input_event_id / payload hash / processing status
   │
   ▼
ConsultantRunGraph（LangGraph 候選）
   ├─ 讀 domain authority snapshot
   ├─ 建立 ContextRequest
   ├─ Context Engine 產生 ContextPack + ContextManifest
   ├─ 選擇 direct structured call 或 bounded agent node
   ├─ phase checkpoint / immutable execution artifacts
   ├─ Pydantic parse + deterministic verifier
   ├─ 產生 VerifiedCommitPlan
   ├─ 原子保存 Work Model delta / agenda / Proposal / consultant turn
   ├─ 寫入 idempotent result receipt 後結束本次 run
   └─ 只有 run 內真的需要人工輸入時才 optional interrupt
          │
          ▼
PostgreSQL domain state（唯一業務真相）

員工稍後審核 durable Proposal
   └─ accept / edit / return / reject domain command
          └─ 經既有 authority commit seam 寫入

橫切：
- Analysis Skills
- Model Profiles
- Tool Registry / allowlist
- speaker-attributed memory
- evaluation / OTel
~~~

### 3.1 StateGraph 管執行，不管業務真相

LangGraph checkpoint 若採用，只應保存：

- thread／run／node cursor；
- operation／focus mode 與 pending interrupt；
- domain revision／generation／read-set digest；
- operation／tool call ID；
- model result 或 domain artifact 的穩定 reference；
- 恢復所需的最小 execution metadata。

不得把完整 Current JD、完整 Work Model、Proposal 或 Evidence 複製成第二份 authoritative store。checkpoint 刪除後，Current JD 與 Proposal 的真相仍必須能從 domain tables 判定。

### 3.2 兩種 operation execution mode

每個 OperationProfile 明確選一種：

1. Direct structured operation：
   - 不需要工具探索；
   - 一次模型呼叫即可；
   - 例如單一 Task 的 OPKS 候選、Question Policy + Realizer。
2. Bounded agent operation：
   - 確實需要按需讀取多段 evidence、查 reference 或展開 Skill；
   - tools 有 allowlist；
   - tool／model call budget 有硬上限；
   - 不能取得 authority mutation tool。

不是每個 attention mode／operation 都需要 agent loop。使用框架不代表每個 operation 都要變成 Agent。

### 3.3 Source、execution 與 semantic commit 是三種不同的 durable boundary

2026-08-13 依 owner 確認的白話回合重新審核後，不能再用「整輪原子保存」含糊涵蓋所有 persistence：

1. `input_event` 先獨立 commit，保證 provider、parse 或 verifier 失敗不會吃掉員工原話；
2. run／attempt checkpoint 與 immutable artifact 分階段保存 provider／tool 結果及 verification，避免已付費工作在 crash recovery 時被重做；
3. 只有 deterministic verifier／reducer 產生的 `VerifiedCommitPlan` 能進 domain transaction；Work Model、agenda／progress、Proposal、consultant turn 與 result receipt 同生共死；
4. Proposal decision 是稍後獨立 command，Current JD 不在 consultant semantic commit 中。

這不是 distributed transaction。network I/O 永遠在 PostgreSQL transaction 外；application 以 input／run／attempt identity、checkpoint、CAS generation／read-set 與 idempotent result 把數個短 transaction 串成可恢復 operation。LangGraph 可管理第 2 層的 execution cursor／task result，但預設 checkpointer 不會自動與第 3 層的 Caliburn UoW 共用同一 atomic commit。DBOS datasource 能把 transaction output 與 application mutation 原子記錄，代表它值得作 durability 對照；但 LangGraph＋DBOS 同時接管同一條 run 會形成雙 runtime，預設不採。若 LangGraph vertical 需要大量自寫 exactly-once plumbing，應比較「DBOS 作替代外層 runtime＋selective LangChain」而不是再疊一層。

模型輸出可以有 item-level verifier verdict，但 commit 的單位仍是 coherent CommitPlan。只有完全獨立、未被可見回覆／下一題／其他 finding 引用的 invalid optional item 才能被 drop 並留下 reason；任何 source identity、scope、authority、stale、dependency 或跨 entity invariant 錯誤都 fail closed。現行 `task_analysis.transition` 採整輪 all-or-nothing，可作保守 baseline；沒有 typed dependency contract 前不得擅自改成 partial semantic commit。

現行 code 仍未符合新的 source-first 裁決：`consultation.submit_employee_turn()` 在 employee turn 只存在記憶體時先呼叫 provider，`commit_verified_turn()` 才把 employee turn、consultant turn 與 state 一起寫入；provider 失敗時員工來源不會 durable。這是後續 ADR／plan 要處理的已確認 gap，不在研究稿階段直接修改。

## 4. 為什麼選這組框架

主流性只能支持「這類通用問題已有成熟解法」，不能證明同一模型會因此寫出更好的 JD。目前沒有可信的公開 benchmark 能證明 LangGraph、LangChain 或其他 Agent framework 對專業職務分析有直接品質優勢；品質仍須由 Caliburn 自己的 transcript、Task／OPKS rubric 與真人 pilot 驗證。框架的直接價值是少維護通用 runtime、收斂預設行為、提高可恢復性與可觀測性。

### 4.1 LangGraph：外層 runtime 推薦候選

官方能力符合需求：

- checkpoint 與 thread-scoped state；
- PostgreSQL checkpointer；
- failure recovery 與 resume；
- interrupt 等待 human approval；
- graph／functional API 可包住既有函式；
- node、edge、stop condition 與 state transition 可測。

官方也明確指出 interrupt resume 會從該 node 開頭重跑，interrupt 前副作用必須 idempotent。這與 Caliburn 既有 operation ID、Journal replay、generation/read-set 及 authority seam 高度相容，但「相容」不等於 checkpoint 與 domain transaction 自動原子化。預設 Proposal 路徑應切成兩個各自 durable 的 application command：

~~~text
consultant run:
prepare snapshot
→ provider/tool work
→ verify
→ persist Proposal
→ finish run

later employee decision command:
load durable Proposal
→ validate decision / stale state
→ authority commit or return
~~~

只有同一個 in-flight run 確實需要人工補充才能繼續時，才使用 `interrupt`；不能為了使用 framework HITL，把本來可獨立審核的 durable Proposal 綁在一個長時間懸停的 graph 上。任何 interrupt node 都不能先寫入不可重播副作用。

### 4.2 LangChain：model、tool 與 context lifecycle

LangChain 現行 context engineering 把 model context 分為：

- system prompt；
- messages；
- tools；
- model；
- response format。

並以 middleware 控制 model context、tool context 與 lifecycle context。這正好能讓 OperationProfile 在每次 call：

- 切換 instructions；
- 只暴露本 operation tools；
- 解析 ModelProfile；
- 固定 output strategy；
- 注入 ContextPack；
- 記錄 usage／latency／manifest。

不採用其自動 SummarizationMiddleware 作為業務記憶，因官方文件明說它會用另一次 LLM call 並永久以摘要取代舊 messages。Caliburn 的原話、Evidence 與更正不得被這樣覆蓋。

### 4.3 ChatOpenRouter：優先替代 HTTP plumbing

官方 integration 已支援：

- OpenRouter model slug；
- strict tool calling；
- function_calling 與 json_schema structured output；
- ProviderStrategy；
- reasoning 參數；
- token、reasoning token、cache 與 response metadata；
- provider order、only、allow_fallbacks、require_parameters、data_collection。

但預設與範例不符合 Caliburn：

- 文件範例使用 max_retries=2；
- provider routing 預設可能 fallback；
- structured-output method 有預設選擇；
- response metadata 不一定涵蓋現有 endpoint preflight／pipeline execution evidence。

所以結論是「先 conformance、再替換」，不是直接刪除自寫 adapter。

### 4.4 Agent Skills：保存方法，不把方法塞進長 prompt

Agent Skills 規格與 SkillsMiddleware 採三層 progressive disclosure：

1. 全部 Skill 只載入約百 token 的 name／description；
2. 命中時讀完整 SKILL.md；
3. references／scripts／assets 只在需要時載入。

適合承載：

- Task boundary 與 merge/split；
- Duty grouping；
- 工作故事／5W1H probe families；
- Output／Indicator；
- Knowledge／Skill；
- Reference challenge；
- completion／red-team review。

Production Skills 必須 repo versioned、唯讀、由程式或 owner 更新；模型不可自行修改專業規則。

本研究不建議採整套 Deep Agents。它同時帶入 filesystem、planning、subagents、summarization、memory 等較強預設，會與 current-only domain authority 重疊。第一個 spike 應驗證 SkillsMiddleware 能否獨立組合；若 dependency surface 過大，仍採 Agent Skills 標準，僅自寫最小唯讀 loader。

### 4.5 Pydantic Evals：成品後的評測 runner 候選

Pydantic Evals：

- code-first，dataset／case／evaluator 可放 repo；
- 有 built-in、custom 與 LLM-as-a-judge evaluator；
- 可用 OpenTelemetry span 評 agent trajectory；
- 不依賴 PydanticAI；
- 不強迫使用雲端 Logfire。

它未來可替代通用 eval runner，但不能替代 Caliburn 的 task-specific dataset、工作分析 rubric 或人類專家標註。依 owner 的時間優先裁示，本能力不進第一版成品開發 critical path。

## 5. 候選方案比較

| 方案 | 通用能力覆蓋 | 主要代價 | 判斷 |
|---|---|---|---|
| LangGraph + selective LangChain + ChatOpenRouter + Agent Skills + 現有 Pydantic／SQLAlchemy／PostgreSQL | workflow、resume、必要 HITL、tools、model、context lifecycle、structured output、skills、domain persistence | 需治理 framework defaults；LangGraph checkpoint 與 domain transaction 不是天然同一提交 | **推薦目標候選**；先做最小 conformance vertical，不是已 Accepted 決策 |
| 現有 durable turn／Journal + selective LangChain／Skills | model、tool、context、structured output 與 skills 可減碼；不新增 graph persistence | 跨請求 resume、分支與 in-flight checkpoint 仍自維護 | 保守 baseline；若 LangGraph 沒有淨收益，可採此路徑 |
| PydanticAI + Pydantic Graph | typed model/tool/output 很好，與現有 Pydantic 自然 | graph/durable ecosystem 與本需求貼合度較低；和 LangGraph 全疊會重複 | 次選；若 LangChain model layer conformance 失敗再比較 |
| DBOS + 現有 domain | PostgreSQL-native durable workflow、idempotency 與 transaction integration | 缺少本需求重視的 context／Skills／agent middleware 生態；要改用 DBOS datasource 才能取得共同 transaction | durability 成為主要痛點時再 spike；不作目前預設 runtime |
| Python eventsourcing 全面重建 domain | event store、aggregate replay、snapshot、notification log | 重寫既有 Current State、Journal、repository、migration 與 authority seam；仍不理解員工 authority | 功能完整但目前不划算；除非產品明確改採 event-sourced domain |
| 全面 Deep Agents | skills、memory、planning、subagents、filesystem 一次齊全 | 自治與預設過多；authority、state、summary 與工具面難收斂 | 不採 |
| 多 Agent 對應八階段 | 每個專家 prompt 清楚 | handoff、context 漂移、成本與責任歸因增加 | 除非 eval 證明單一 bounded consultant 不足，否則不採 |
| 全部自寫 | 控制最大 | checkpoint、resume、tools、memory、skills、eval、provider compatibility 都自行維護 | 不再划算 |

## 6. 現有元件 Replace／Wrap／Retain 稽核

以下行數只是目前維護面積，不是可直接刪除承諾。

| 現有責任 | 代表檔案／規模 | 框架候選 | 框架不能取代的殘留 | 結論 |
|---|---|---|---|---|
| OpenRouter HTTP、structured output、reasoning、usage | openrouter.py 301 行；openrouter_evidence.py 373 行 | ChatOpenRouter | exact model、單 endpoint、零 retry/fallback、typed refusal/error、raw execution evidence conformance | Replace 大部分；保留薄 adapter／profile resolver |
| 一次 operation 的 render→call→parse→verify | task operation 94 行；OPKS operation 89 行 | structured model runnable／bounded agent node | operation-specific domain verifier 與 outcome mapping | Replace orchestration，Retain domain callback |
| model-facing wire boilerplate | task wire 475 行 | Pydantic schema + explicit ProviderStrategy／ToolStrategy | ordinal mapping、portable neutral values、domain mapper | Wrap；可望顯著縮小，不保證全刪 |
| prompt 與所有方法規則 | task prompt 118 行及各研究文件 | Agent Skills + dynamic prompt | Task／Duty／OPKS rubric | Replace 載入機制；Retain 內容 |
| context lifecycle | task context 659 行；OPKS context 349 行 | LangChain middleware／ToolRuntime | domain selection、authority、ordinal、token lane policy、manifest | Wrap；框架管生命週期，Caliburn 管選取 |
| durable turn、pause/resume、child orchestration | durable_turn.py 337 行；turn.py 196 行；opks generation 454 行 | LangGraph + Postgres checkpointer；DBOS 作 durability 對照 | operation id、authority snapshot、read-set、Journal、commit seam | 先 Wrap／conformance；只有證明淨減碼且無 durability 退步才 Replace workflow mechanics |
| verifier 形狀與交叉欄位規則 | task verifier 938 行；OPKS verifier 361 行 | Pydantic validators、typed structured output、middleware guard | quote 來源、ordinal、lineage、identity、Current JD／Proposal 不變量 | Wrap；只刪純 shape／boilerplate |
| Work Model transition | transition.py 941 行 | Pydantic model、SQLAlchemy UoW／constraint 可減少局部 plumbing；LangMem 只可產生 typed 候選 | Task identity gate、delta、Proposal、Current JD 禁寫、retirement／supersession | Retain domain reducer；框架只 Wrap 輸入與持久化機制 |
| Evidence／SourceAnchor／SupportLink | core/domain/sources.py 等 | W3C Web Annotation 的 TextQuote／TextPosition Selector + W3C PROV lineage vocabulary | speaker、quote validity、supersession、document scope、employee authority、語意支持 | 升級 anchor 標準與 lineage mapping；Retain domain truth／verifier |
| Current JD／Proposal persistence | PostgreSQL repositories、authority commit | SQLAlchemy transaction／constraint／versioning；Pydantic discriminated union | 跨 entity generation／read-set、before-state stale、員工決策語意 | 深化既有框架；不以 generic JSON Patch、memory store 或 workflow state 取代 |
| generic memory／resume | transcript、Journal 與自組 packet | LangGraph checkpointer/store；LangMem 僅作候選抽取／非權威 recall | 原話、業務記憶、正式 Work Model 與事實狀態 | Wrap；checkpoint／store 只存 execution 或可重建 artifact，不當 truth |
| Skill 發現與按需載入 | 尚未正式元件化 | Agent Skills／SkillsMiddleware | 專業內容與版本核准 | Replace 通用 loader |
| runtime observability | 現有 OTel 與 provider evidence | OpenTelemetry GenAI conventions；未來需要本機 trace UI 時再評估 MLflow | 產品 evidence、quote lineage、員工決策 authority | Wrap；trace_id／span_id 只作 correlation，不作產品真相 |
| eval runner、報表與 trajectory capture | 分散腳本／fixture | Pydantic Evals + OTel | dataset、grader、release gate | 成品後 Replace runner，Retain rubric；目前不進 critical path |
| RAG retrieval/citation | 隔離 bounded context | 未來 MCP／retriever／LlamaIndex 可選 | source authority、employee confirmation、ADR 0057 邊界 | 延後；先不接 production |

### 6.1 刪碼成功的定義

不能以「引入套件後檔案變少」為唯一標準。每個替代都要證明：

1. 既有成功案例不退步；
2. hidden retry／fallback／summary／state copy 沒有出現；
3. failure、refusal、model mismatch 與 stale snapshot 仍可歸因；
4. 開發期既有測試、authority safety、介面 conformance 與人工 smoke 通過；成品後再補品質、成本與延遲 eval；
5. 被框架覆蓋的舊 code 與測試才刪除，不保留雙路徑。

## 7. Context Engine：最大問題的具體設計

### 7.1 Context 不等於 memory，也不等於完整 transcript

需要分開：

| 概念 | 內容 | 真相性 | 是否每次送模型 |
|---|---|---:|---:|
| Domain state | Current JD、Work Model、Proposal、open issue | 高，但各層權威不同 | 否，只投影相關 slice |
| Transcript | 每位說話者原話 | 來源真相 | 否，按需載入 |
| Evidence | 經 quote／speaker／scope 驗證的原子主張 | 可追溯，不等於客觀正確 | 依 operation／target |
| Graph checkpoint | 執行 cursor 與 resume metadata | 只屬 execution | 不直接送 |
| Skill | 方法、rubric、例子 | 程序知識 | 命中才讀 |
| Reference | ICAP／公版／文件候選 | 外部候選 | opt-in、後段 |
| ContextPack | 單次模型 call 的高訊號輸入 | 可丟棄 projection | 是 |
| Summary | 導覽與檢索索引 | 非權威 | 必要時少量 |

### 7.2 ContextRequest

每次模型呼叫前由 application runtime 建立 typed request。以下只示意責任，不是最終 schema：

~~~json
{
  "document_id": "doc",
  "operation": "consultation.decide",
  "focus_refs": ["task:..."],
  "active_skills": ["task-boundary", "output"],
  "objective": "選擇單一最高價值追問",
  "authority_generation": 42,
  "required_source_kinds": ["employee_turn", "direct_edit"],
  "allowed_reference_kinds": [],
  "token_budget": 9000,
  "output_reserve": 1800,
  "freshness": "current",
  "policy_version": "context-policy/1"
}
~~~

模型不能自己決定跨 document、放寬 source policy 或提高 budget。

### 7.3 Context 選取管線

Context Engine 採 hybrid 流程：application deterministic 保證 scope、authority 與必帶核心；retrieval 與受控按需工具補足語意相關資料。

~~~text
1. Scope
   document / operation / focus / target
2. Eligibility
   來源種類、Current/Past、speaker、Proposal 狀態、是否 superseded
3. Authority partition
   Source / Work Model / Proposal / Current JD / Reference 分區
4. Required facts
   operation 必帶的 target、當輪回答、矛盾、未決 gap、最新更正
5. Retrieval
   structured filter → lexical → semantic（各分支都必須經 eval）
6. Rank
   operation/focus relevance、target linkage、recency、contradiction、information value
7. Deduplicate
   不重複送同一份內容；summary 可作導覽，必要原話仍可作 evidence
8. Budget allocation
   先保留 output/schema/tool 與不可省略核心；其餘類別不預設固定比例
9. Render
   結構化 state + 少量逐字 quote + 未載入提示
10. Just-in-time read
   模型只可透過受 scope／budget 控制的唯讀工具補查
11. Manifest
   保存實際載入項目、理由、版本、hash、tokens
~~~

語意搜尋只負責找候選，不能：

- 判斷 quote 是否存在；
- 刪掉意思相近但來自不同人的兩句話；
- 以最高相似度決定事實；
- 靜默跨 document；
- 讓 summary 覆蓋 correction。

### 7.4 Context lanes 與預算順序

以下 lane 是第一輪 eval 候選，不是固定 prompt 版型或配額：

1. Guardrail lane：極短、穩定的產品角色、authority 與本 operation 禁令。
2. Skill lane：相關 Skill metadata；完整方法按需載入。
3. Target lane：目前 Duty／Task／O/P/K/S 與必要 Current JD before。
4. Evidence lane：支持、反證、最新更正與 speaker-attributed quotes。
5. Agenda lane：open gaps、contradictions、ask count、declined／unknown。
6. Proposal lane：相關 pending／rejected／revision history。
7. Recent-turn lane：最近少量自然對話，維持連續性。
8. Reference lane：只有 operation 允許且符合 blind-first／員工選擇規則時載入。

預算優先序：

~~~text
輸出與 schema reserve
> authority / latest correction
> target + blocking contradiction
> direct evidence
> open gaps
> recent dialogue
> optional reference
> historical low-value detail
~~~

當相關來源因預算未載入，pack 應明示「有其他相關來源未載入」，不能讓模型把未載入誤判為不存在。

### 7.5 ContextManifest

每次 operation 保存：

- attention mode／operation／policy／skill／prompt／schema／model profile version；
- domain generation 與 read-set；
- 每個 context item 的 source ID、kind、speaker、target、revision/hash；
- selected reason 與 excluded reason；
- estimated／actual input tokens；
- tool schemas 與 tool results；
- reference 是否由員工主動選擇；
- output、verifier 與 Proposal reference。

Manifest 是可重播與除錯證據，不是第二份內容 store。它保存 reference 與 hash，原文仍在 domain source。

## 8. 記得「別人說過什麼」

### 8.1 說話者記憶模型

每筆原始陳述至少區分：

- document_id；
- turn_id／sequence；
- speaker_kind：employee、manager、colleague、HR、customer、other、unknown、AI；
- speaker_label：使用者可讀名稱或角色，不是登入帳號；
- capture_mode：direct_utterance、employee_reported、artifact_quote、direct_edit；
- reporter：若是轉述，誰做了轉述；
- text 與時間；
- question／episode／Duty／Task links；
- source validity；
- correction／contradiction／superseded_by；
- consent／sensitive-data flag（若日後需要）。

關鍵區別：

> 「主管在系統內直接說 X」與「員工說主管曾說 X」不是同一證據。

後者的逐字 quote 只能證明員工這樣轉述，不能偽裝成主管原話。

### 8.2 三層記憶

1. Immutable utterance：
   - 原始文字與說話者；
   - 永不被摘要覆寫；
   - 修正以新事件與 supersession 表示。
2. Evidence／claim：
   - 從原話抽出的可否定主張；
   - 有 subject、polarity、time_scope、typicality、ownership；
   - 多人衝突時兩邊都保留。
3. Retrieval index／summary：
   - 幫助找到相關原話；
   - 可重建、可丟棄；
   - 不能直接進 Current JD。

### 8.3 衝突與更正

例如：

- 員工：「我負責核准。」
- 主管：「最後是我核准，員工只初審。」

系統應：

1. 保存兩筆不同 speaker 的原話；
2. 建立 authority／ownership contradiction；
3. Context Engine 在會影響 Task 責任邊界時優先載入兩邊；
4. 顧問提出中性澄清；
5. AI 不自行選一邊；
6. 員工對 JD Proposal 的決策仍是本產品文件 authority，但不能把另一人的陳述刪掉。

### 8.4 隔離

namespace 至少為 document_id。第一版：

- 不跨文件記住偏好或工作事實；
- 不建立「這位主管在所有文件都說過什麼」；
- LangGraph long-term Store 不承載 speaker truth；
- 若未來要跨文件個人記憶，必須另開產品／隱私 ADR。

## 9. 各 attention mode／operation 的 Context 配方

| attention mode／operation | Always include | On demand | 預設排除 | 主要輸出 |
|---|---|---|---|---|
| Reference 搜尋 | 使用者搜尋意圖、角色假說摘要、Reference Skill、read-only tools | ICAP／公版 metadata，再取候選全文 | 未確認候選不得混入工作事實 | reference candidates + source refs |
| 工作骨架 | 本輪完整回答、active question、近期必要 turn、未映射訊號、Current Work Model 摘要 | 相關舊故事／更正 | 大量公版、完整 OPKS、無關 transcript | work signals、初步 Duty/Task、gaps |
| 待訪談清單 | open gaps、contradictions、ask count、priority、fatigue、Current JD digest | gap 的逐字來源 | 無關原話、完整 reference | 下一個單一 target／轉題／停止 |
| 主要 Duty 分析 | 選定 Duty、其 Task、支持／反證、unmapped signals | 相關故事、相似 Task、merge/split history | 其他 Duty 全文 | Duty/Task candidate、追問 |
| 候選區審核 | proposal before/after、source pointers、影響範圍 | 相關原話、既有拒絕原因 | 新的自由分析 | accept/edit/return/reject interrupt |
| Task 5W1H／O-P | 單一 Task、有效員工 evidence、story skeleton、既有 O/P、blocking gaps | SOP／artifact、例外事件 | 其他 Task、公版 K/S | O/P candidate 或 uncertain |
| K/S 候選 | 單一 Task + O/P、方法／判斷 evidence、文件層 K/S、支持軸 | 必要 reference taxonomy 只作判準 | 職稱推定、未連 Task 公版清單 | K/S add/reuse/revise/remove/unknown |
| 右側 JD | Current JD、已接受內容、readiness issue、選定編輯目標 | source trace、quality challenge | pending hypothesis 不得混入正式內容 | 員工直接 edit／final review |

這張表是第一版 policy 候選，不是永久固定。是否 load-bearing 必須由 context ablation eval 決定。

## 10. Skill、Tool 與 Agent 的邊界

### 10.1 OperationProfile

每個 operation 具有版本化 contract；可見的 attention mode 只用於說明目前焦點，不要求與 graph node 一一對應：

- operation_id 與可見 attention／UI mode；
- objective；
- entry、completion、return、stop conditions；
- ContextRequest builder；
- Skill names；
- allowed tools；
- execution mode；
- exact ModelProfile；
- generation params；
- max model／tool calls；
- output schema；
- verifier；
- possible next operations／focus transitions。

### 10.2 Tools 三級

1. Read-only：
   - read_state_slice；
   - read_transcript_slice；
   - read_source／artifact；
   - search_reference／read_reference；
   - inspect_current_jd。
2. Candidate-producing：
   - propose_task_change；
   - propose_duty_change；
   - propose_opks_change；
   - report_gap／contradiction；
   - run_quality_check。
3. Authority mutation：
   - 不提供給模型；
   - 只由 employee command 進 authority commit seam。

tool description 只寫一次，schema 自帶權限與輸入限制。每個 operation 只暴露必要工具，避免所有工具永久佔 context。

### 10.3 不採多 Agent 的理由

八階段是注意力切換，不是八個獨立對話所有者。多 Agent 會增加：

- transcript／memory handoff；
- 同一 source 在不同 Agent 間的摘要漂移；
- model call 與 latency；
- 哪個 Agent 對錯誤負責的歸因；
- prompt 與 tool policy 重複。

只有當 eval 證明某個 specialist：

- contract、tool、policy 明顯獨立；
- 以 agent-as-tool 比同模型單一 OperationProfile 顯著提升；
- 成本／延遲可接受；

才拆出，且不得取得 Current JD authority。

## 11. Evidence、quote anchor、verifier 與來源可信度

### 11.1 有框架，但沒有一個框架能完整替代

| 問題 | 現成能力 | 能解決 | 不能解決 |
|---|---|---|---|
| output shape | Pydantic／LangChain structured output | JSON／type／部分欄位組合 | 語意真實性 |
| exact text anchor shape | W3C Web Annotation TextQuoteSelector／TextPositionSelector | `exact`、`prefix`、`suffix`、`start`、`end` 與可互通的文字片段定位 | speaker authority、來源是否未被竄改、引文是否支持 claim |
| citation source chunks | LlamaIndex CitationQueryEngine 等 | 建立可引用 source nodes、控制 chunk granularity | 引文是否真的支持職務判斷 |
| provenance schema | W3C PROV-O | Entity／Activity／Agent、quoted/derived/primary-source 關係詞彙 | Caliburn 的員工 authority 與信任政策 |
| RAG quality eval | Ragas | context precision／recall、faithfulness、tool metrics | production commit gate |
| trajectory eval | Pydantic Evals + OTel | tool／node path、custom evaluator | 業務真相 |
| exact quote verifier | Caliburn deterministic code | turn、speaker、逐字 substring、source scope | entailment與專業合理性 |
| source credibility | Caliburn policy + human | employee／manager／reference／AI 分層 | 無通用框架可替產品裁決 |

結論：

- 可用框架／標準取代 citation transport、anchor shape、retrieval、provenance vocabulary 與 eval plumbing；
- exact quote、speaker attribution、supersession、source authority 與 Current JD gate 必須保留；
- citations 只證明「指到某段」，不證明 claim 被支持；
- source credibility 不應是一個神秘 confidence 0.83，而應拆成 source validity、speaker、capture mode、claim status、task linkage 與 employee decision。

### 11.2 deterministic 與 semantic 分工

程式可判定：

- source／turn／speaker 是否存在；
- quote 是否逐字；
- 是否跨 document；
- source 是否 AI 自己上一輪輸出；
- ordinal／entity／refs 是否合法；
- superseded／past／denied 是否被錯用；
- schema、lineage、state transition、authority generation。

模型／rubric／人類判定：

- 引文是否語意支持 Task／O/P/K/S；
- Task boundary 是否專業合理；
- Indicator 是否可觀察；
- K/S 是否真的由工作行為支持；
- 多人衝突該如何澄清；
- 最終 JD 是否代表員工工作。

### 11.3 2026-08-13 保留核心的 framework 化裁決

Owner 的要求不是「五個核心全部自寫」，而是保留其產品責任。逐項裁決如下：

| 產品責任 | 可直接採用／深化的框架或標準 | Caliburn 必須保留 |
|---|---|---|
| 員工原話、來源、speaker、更正、quote anchor | W3C Web Annotation anchor shape；W3C PROV lineage vocabulary；Pydantic shape validation；PostgreSQL durability | speaker／capture mode 權威、source revision、逐字驗證、correction／supersession、document isolation |
| Work Model、Current JD、Proposal | Pydantic typed models；SQLAlchemy UoW、transaction、constraint、必要時 row-level versioning；PostgreSQL | hypothesis identity／lifecycle、generation／read-set、cross-entity stale、Proposal action 語意、employee authority |
| Task／Duty／OPKS 分析方法 | Agent Skills 規格、SkillsMiddleware、dynamic prompt／tool allowlist | 研究過的方法、rubric、觸發語意、共同 work hypothesis 與跨 Skill 對帳 |
| deterministic verifier、來源可信度 | Pydantic field／model validators、typed output、可組合 validation pipeline | transcript-backed quote、speaker、ordinal、lineage、identity、domain invariant；可信度仍拆成可解釋政策，不採神秘單一分數 |
| 員工核准與 authority commit | LangGraph／其他 runtime 可承接通用 pause／resume 與 payload transport；SQLAlchemy 承接 transaction | durable Proposal、accept／edit／return／reject domain command、stale checks、原子 authority commit |

補充邊界：

- SQLAlchemy `version_id_col` 只能協助 ORM row flush 的 stale detection，不能取代跨 Document／Task／Duty／OPKS／Proposal 的 generation＋read-set；
- LangMem、Pydantic Harness Memory、Mem0 等模型驅動記憶若採用，只能產生可丟棄摘要、非權威 recall 或 typed hypothesis candidate，不能自行 create／update／delete canonical Work Model；
- event-sourcing framework 的 aggregate／snapshot／notification log 比現有 Journal 更完整，但採用代表重寫 persistence model，不因功能較多就自動更好；目前先深化既有 PostgreSQL／SQLAlchemy／Journal；
- framework approval 通常批准的是一次 tool call／run interruption；Caliburn 員工核准的是有來源、before／after、revision 與 domain dependency 的 Proposal，兩者不可混為同一狀態。

quote anchor 的推薦升級形狀是：

```text
source_id + source_revision_hash
+ exact quote + prefix/suffix
+ Unicode code-point start/end + normalization policy
+ speaker/capture mode + document scope
```

Web Annotation 提供的是成熟 selector 模型，不要求 Caliburn 使用 JSON-LD 或 RDF 作內部 truth；可保留 Pydantic／relational domain model，只在命名、驗證與對外 projection 對齊標準。

### 11.4 2026-08-14 現行 Evidence 與 Opus 5 補充裁決

現行 runtime 不再有一個待保留的 `Evidence` 大元件；同目的機制已拆給成熟 primitive：LangGraph Store 保存員工逐字來源與更正，LangChain `Citation` 承接回覆 citation annotation，W3C TextQuote／TextPosition selectors 承接來源位置形狀，PROV vocabulary 承接 quotation／revision／invalidation 語彙，Pydantic 承接 typed validation，LangChain callbacks＋OpenTelemetry 承接 execution evidence，LangGraph command／checkpoint 承接員工審核 durability。Caliburn 只保留 framework 無法判斷的 employee authority、source revision／document scope、exact quote、correction 失效與 Task／Duty／OPKS semantic support。

需特別區分：LangChain `Citation.start_index／end_index` 指向模型回覆，不是來源文字；Anthropic 原生 citations 與 structured outputs 不能同 request 使用；目前 pin 的 `langchain-openrouter==0.2.7` response converter 也未保留 citation annotations。因此第一版核心仍使用 provider-neutral source ID＋W3C-aligned selector＋Pydantic result＋deterministic verifier，native citation 只可在 adapter conformance 通過後作 tool-enabled analysis 段的選配能力。

Task 10 真模型另證明，完整 tools＋大型 strict `ConsultantResult` 綁在同一 request 會撞 grammar complexity；後續結構量測又確認 output schema 自身已有 28 optional／20 union sites，超過 Anthropic 公開的 24／16 合併上限。產品工作稿 §9.16 因此修正先前過早的兩段式結論：先恢復 repo 已以 Opus 5 live smoke 證明的 compact provider wire＋pure mapper，保留單一 bounded agent；只有 compact wire exact conformance 仍失敗，才評估 tool-free finalization。owner 已核准 ADR 0061 的 schema-only 範圍；Skill／Tool 的集合、description、載入與排程維持現況，另行討論。完整裁決與來源見產品工作稿 §9.16 與 Accepted ADR 0061。

## 12. 通用模型接口與可替換模型

### 12.1 ModelProfile

模型不應散落成環境變數與 if/else。每個已核准 profile 至少包含：

- profile_id／version；
- operation／attention-mode allowlist；
- provider adapter；
- exact model slug；
- exact provider／endpoint policy；
- structured-output strategy；
- reasoning effort／mode；
- temperature／top_p（若支援且有需要）；
- max input/output；
- timeout；
- retry policy；
- fallback policy；
- data collection policy；
- prompt cache policy；
- max model/tool calls；
- pricing snapshot reference；
- capability/eval suite version。

OperationProfile 指向 ModelProfile，不直接寫任意 model string。

### 12.2 換模型流程

~~~text
新增候選 ModelProfile
→ capability probe
→ provider/conformance tests
→ 簡單人工 smoke
→ owner 核准
→ 版本化切換
→ 成品後補 fixed replay／branching／pairwise／成本品質 gate
~~~

不能因 framework 宣稱 provider-neutral 就假設模型等價。

### 12.3 ChatOpenRouter conformance gate

替換現有 adapter 前必測：

- request body 的 exact model；
- provider order/only 恰一個；
- allow_fallbacks=false；
- require_parameters=true；
- data_collection=deny（若需求如此）；
- max_retries=0；
- explicit structured-output method + strict；
- reasoning 參數與 reasoning exclusion；
- refusal、200 error envelope、timeout、截斷、invalid schema；
- response model mismatch；
- selected provider／endpoint evidence；
- prompt、completion、reasoning、cache tokens 與 cost；
- unknown additive fields 的 forward compatibility。

任一關鍵 execution evidence 取不到，就保留該部分薄 adapter，不為了「全框架」降低可稽核性。

## 13. 成本控制

### 13.1 成本公式

每份 JD 成本約為：

~~~text
Σ 每次模型呼叫
  (uncached input tokens × input price
   + cached input tokens × cache price
   + output/reasoning tokens × output price)
+ 額外 judge／summary／retrieval model calls
~~~

框架本身不是主要 per-call 成本。LangGraph、LangChain、Pydantic Evals 的 open-source library 不要求每次模型呼叫付 framework 費；真正成本是 call 數、context、model 與 reasoning。

### 13.2 第一版硬控制

- 一個 employee turn 預設最多一次主要 consultant call；
- 遷移期間現行 OPKS child 仍維持最多一個 single-Task child；終局是否在主要顧問同一次 inference 內按需組合 O／P／K／S Skills，依 operation contract 與後續成品 eval 決定，不把現行 child topology 升格成產品流程；
- bounded agent 設 max model calls、max tool calls、max tokens；
- retry=0、fallback=false；
- 不開自動 summary call；
- 不開 background memory extraction；
- Reference 只在員工選擇或後段 coverage challenge 使用；
- 工具 metadata 與 stable Skill prefix 才考慮 prompt cache；
- 每個 operation 有 input/output budget 與超額降級路徑；
- 成品前不為省 token 額外導入未驗證的 cheap-model routing；模型分級與自動 routing 留到正式 eval。

### 13.3 降級順序

context 超預算時：

1. 移除無關 reference；
2. 移除低價值歷史與重複 projection；
3. 以 ID／metadata 保留可按需讀取的來源；
4. 縮短 recent-turn window；
5. 保留 latest corrections、blocking contradictions、target facts 與直接 quotes；
6. 若仍不足，停止並標示 ContextBudgetExceeded，不靜默截掉權威資訊。

### 13.4 成本指標

不要只看「每 call 多少錢」。至少看：

- 每個 confirmed Task 的 calls／tokens／cost；
- 每個 accepted O/P/K/S item 的 cost；
- 每份完成 JD 的平均與 p95 cost；
- 因 invalid output、retry、fallback、tool loop 浪費的比例；
- context duplication rate；
- 未命中 context 造成的重問與人工 edit 成本。

## 14. 成品後的評測與 release gate

本章保留未來評測設計，但不是第一版成品的前置 Phase 或 release blocker。正式 eval 在可用端到端成品完成後啟動；開發期間只收集可回溯資料並維持一般工程安全網，不先建 dataset、grader、A／B、LLM judge 或評測平台。

### 14.1 成品完成後建立 baseline

以可用成品的真實操作形狀凍結：

- 現行代表性 transcript／state fixtures；
- 現行 output、Proposal 與 verifier 結果；
- call、token、latency、cost；
- 已知 failure；
- 人工 Task／OPKS 品質標註。

沒有 baseline，就無法判斷後續模型、context、retrieval 與 prompt 調優是改善還是退化；但不為建立此 baseline 阻塞第一版成品。框架替代期間仍須以既有測試與 conformance 證明機械語意沒有退化。

### 14.2 Context Engine 指標

Deterministic：

- required-context recall；
- irrelevant-context precision；
- latest-correction recall；
- contradiction pair recall；
- quote validity；
- cross-document leakage = 0；
- duplicate context rate；
- manifest completeness；
- input tokens by lane；
- omitted-required-context = 0。

Human／LLM rubric（需人校準）：

- 問題是否 grounded；
- 是否正確記得某人說過的內容；
- 是否把轉述當直接發言；
- 是否受 reference 錨定；
- 是否選到最高資訊價值 gap；
- context 足夠但不過量。

### 14.3 Domain 品質

- Task boundary、ownership、temporality；
- Duty／Task 完整性；
- O/P/K/S grounding；
- 引文 entailment；
- 虛構率與 unsupported item；
- accept/edit/return/reject；
- final JD 修改量與員工代表性評分。

### 14.4 Runtime 與框架品質

- operation／tool／authority violation = 0；
- duplicate resume 不重複 side effect；
- restart 可恢復；
- checkpoint 遺失不破壞 domain truth；
- provider failure 不留下半套 mutation；
- exact model/provider 可證明；
- hidden retry/fallback = 0；
- checkpoint retention 可治理。

### 14.5 三層 eval

1. Fixed replay：
   - extraction、reducer、context、verifier、projection、replay。
2. Branching simulation：
   - 不同問題路徑、短答、更正、多人衝突、拒答、停止與 turn cost。
3. 真人／專家 pilot：
   - 受訪者是否被理解、疲勞、重複；
   - 工作分析 reviewer 對 Task／OPKS／JD 的品質與可追溯性；
   - blinded pairwise 比較。

任何 LLM judge 都要以人工標註校準，不能以單一總分取代逐項 failure。

## 15. 建議遷移順序

### Phase 0：contracts 與可回溯性（不建立正式 eval）

- 凍結 ModelProfile／OperationProfile／ContextManifest 候選 contract；
- 保留既有 unit／integration／contract tests 與 authority invariants；
- 記錄 operation、model、prompt／Skill／tool version、source refs、tokens、latency 與結果 lineage；
- 每個垂直切片只做簡單人工 happy-path／resume／approval smoke。

Gate：既有測試通過、authority 與 document isolation 不退步、紀錄足以在成品後建立 replay；不要求 dataset、人工標註或 grader。

### Phase 1：ChatOpenRouter conformance spike

- 不改 domain workflow；
- 以 ChatOpenRouter 重現現行 Task／OPKS call；
- 比較 request、outcome、usage、provider evidence；
- 明確關閉 retry／fallback。

Gate：現行 adapter 的必要語意全部通過；否則只採部分框架。

### Phase 2：structured output 與 wire 瘦身

- 固定 explicit strategy；
- 把 shape validator 移到 Pydantic／framework；
- 保留 ordinal mapper、domain verifier；
- 只有等價測試通過才刪舊 plumbing。

### Phase 3：最小 LangGraph vertical

選一條：

~~~text
待訪談項目
→ consultant operation
→ durable Proposal / no-op / gap
→ consultant run 結束

稍後獨立 employee decision command
→ accept / edit / return / reject
→ authority commit / return
~~~

這個 vertical 先驗證 checkpoint／resume 是否真的減少 orchestration；不把 Proposal 審核硬改成 interrupt。另選一個「run 內確實需要人工輸入」的窄案例，才測 optional interrupt。

Gate：restart、duplicate resume、stale generation、checkpoint loss、Proposal 在沒有 graph checkpoint 時仍可審核，以及 authority violation 全通過。若 LangGraph 不能比現有 durable turn 明確減少總維護面，保留現有 runtime 並只採 model／Skills／context framework。

這個 Gate 另須包含四個 crash seam：source commit 後、provider result checkpoint 後、verification checkpoint 後、domain commit acknowledgment 前。已保存 provider result 的 recovery 不得再呼叫模型；domain transaction 中任一 write 注入失敗時，Work Model／agenda／Proposal／consultant turn／result receipt 必須全部 rollback；同一 input ID＋同 payload 回既有狀態或結果，同一 ID＋不同 payload 穩定 conflict。

### Phase 4：Analysis Skills 與 Context Engine

- 將 Task／Duty／OPKS 方法拆成少數不重疊 Skills；
- 實作 ContextRequest、lanes、Manifest；
- operation-specific tool allowlist；
- 不啟用自動 summary 或 cross-document memory。

Gate：必帶核心、document scope、最新更正與 Manifest 的 deterministic tests 通過，人工 smoke 可完成主流程；recall／precision、重問率、品質與最佳 token 配置延至成品後評測。

### Phase 5：說話者記憶

- speaker-attributed utterance；
- direct vs reported distinction；
- correction／contradiction；
- document-local retrieval；
- UI 顯示來源，不建立帳號。

Gate：多人陳述案例零誤歸屬、零跨文件洩漏、矛盾不被靜默覆蓋。

### Phase 6：verifier 與 durable code 簡化

- 移除已被 typed output／graph 保證的 boilerplate；
- 保留 quote、lineage、identity、authority；
- 禁止新舊雙 runtime 長期並存。

### Phase 7：Reference／RAG

- 先開新 ADR 翻案或擴充 ADR 0057；
- 以 read-only tool／MCP 接入；
- reference 與 employee evidence 分 lane；
- 先完成 read-only retrieval／citation 與 source boundary；Ragas 等離線 eval 延至可用成品完成後。

Gate：開發期只要求公版不自動升格、來源可追溯與人工 smoke 可用；成本與 coverage challenge 的實證收益成品後再量測。

## 16. 明確不做

- 不把八階段做成八個 Agent。
- 不讓 LLM 自行放寬 operation／focus boundary 或寫 Current JD。
- 不把 LangGraph checkpoint／Store 當第二份 document store。
- 不用 generic vector memory 當工作事實。
- 不用 summary 取代 transcript 或 Evidence。
- 不啟用 hidden retry、fallback、automatic model routing。
- 不同時全面導入 LangGraph、PydanticAI、Deep Agents、LiteLLM。
- 不為框架整潔而刪除 exact model/provider execution evidence。
- 不在新 ADR 前把隔離 RAG bounded context 接入 current API/Web。
- 不以 schema 合規或 citation 存在宣稱內容正確。
- 不因 eval 後置就一次重寫全部流程；仍採可回退的垂直切片與介面 conformance。

## 17. 已收斂與仍需討論

### 17.1 本研究建議視為已收斂

- bounded application run 包有限 model／tool step，不採自由 Agent loop；
- framework-first 替代通用機械碼；
- 「保留產品責任」不等於所有底層程式自寫；先深化 Pydantic／SQLAlchemy／PostgreSQL，再選擇性導入新框架；
- domain authority、Task／Duty／OPKS 方法、source policy 與進度語意保留；
- durable Proposal 與 employee decision command 不依賴 graph interrupt；
- W3C Web Annotation／PROV 可改善 anchor 與 lineage 形狀，但不取代 domain truth；
- operation-specific context，不送完整歷史；
- speaker-attributed、document-local、原話優先；
- Skills progressive disclosure；
- 不採 full Deep Agents 或多 Agent 起步；
- product-first、先做可回退 spike 後擴張；正式 eval 在可用成品後補上。

### 17.2 討論者需裁決

1. ChatOpenRouter conformance 若缺 endpoint execution evidence，是否接受混合薄 adapter。
2. SkillsMiddleware 的 dependency surface 是否可接受；否則是否只採 Agent Skills 標準。
3. LangGraph 最小 vertical 是否比現有 durable turn／Journal 產生可證明的淨減碼；若沒有，是否只採 model／Skills／context framework。UI attention mode 已確認不與 graph node 一一對應。
4. speaker_kind／capture_mode 第一版是否直接進 domain，或先以 artifact/source metadata 形式實驗。
5. Context Engine 第一版只用 relational／lexical，還是同時實驗 semantic retrieval。
6. ModelProfile 由設定檔、資料庫或 versioned Python registry 管理。
7. 哪些現行 verifier 規則可安全下沉到 Pydantic，哪些必須維持獨立純函式。
8. W3C anchor 升級是否與 runtime vertical 同批，或先作獨立 source-contract slice。
9. 成品完成後第一個真人 pilot 的職務樣本、專家 reviewer 與 release threshold。

## 18. 後續 ADR 建議

若 owner 與討論者接受方向，至少需要：

1. Consultant application run、runtime 選型與 LangGraph authority boundary ADR。
2. ModelProfile、provider conformance 與 framework default policy ADR。
3. Context Engine、ContextManifest 與 memory scope ADR。
4. Agent Skills 儲存、版本、唯讀與 activation ADR。
5. Speaker-attributed source、reported speech 與 contradiction ADR。
6. Eval dataset、grader、cost gate 與 model migration ADR。
7. 未來 RAG production boundary ADR。

ADR Accepted 後才寫 docs/plans/；不得直接據本研究全文施工。

## 19. 第一方／官方來源

### Workflow、Agent 與 model

- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
- [Anthropic — Mid-conversation system messages and tool changes](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages)
- [Anthropic — Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [OpenAI — Latest model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI — Agents SDK](https://developers.openai.com/api/docs/guides/agents)
- [OpenAI Agents SDK — Guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- [OpenAI Agents SDK — Human in the loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- [OpenAI — Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- [Google ADK — Workflow agents](https://adk.dev/agents/workflow-agents/)
- [Microsoft Agent Framework — Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/)
- [AWS Prescriptive Guidance — Workflow orchestration agents](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/workflow-orchestration-agents.html)

### LangGraph、LangChain 與 OpenRouter

- [LangGraph — Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph — Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [LangChain — Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — Memory](https://docs.langchain.com/oss/python/concepts/memory)
- [LangChain — Tools](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain — `Citation` content annotation](https://reference.langchain.com/python/langchain-core/messages/content/Citation)
- [LangChain — ChatOpenRouter](https://docs.langchain.com/oss/python/integrations/chat/openrouter)
- [LangGraph — MIT License](https://github.com/langchain-ai/langgraph/blob/main/LICENSE)
- [LangChain — MIT License](https://github.com/langchain-ai/langchain/blob/master/LICENSE)

### Skills、eval 與 provenance

- [Agent Skills — Specification](https://agentskills.io/specification)
- [Deep Agents — Skills](https://docs.langchain.com/oss/python/deepagents/skills)
- [LangMem — Memory conceptual guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [Pydantic — Validators](https://pydantic.dev/docs/validation/latest/concepts/validators/)
- [Pydantic AI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/)
- [Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/)
- [Pydantic AI repository and MIT License](https://github.com/pydantic/pydantic-ai)
- [SQLAlchemy — Configuring a Version Counter](https://docs.sqlalchemy.org/en/20/orm/versioning.html)
- [W3C — Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [W3C — PROV-O](https://www.w3.org/TR/prov-o/)
- [OpenTelemetry — Generative AI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [MLflow — GenAI tracing](https://mlflow.org/docs/latest/genai/tracing/)
- [DBOS — Workflow communication](https://docs.dbos.dev/python/tutorials/workflow-communication)
- [DBOS — Transactions](https://docs.dbos.dev/python/tutorials/transaction-tutorial)
- [DBOS — Workflows and idempotent workflow IDs](https://docs.dbos.dev/python/tutorials/workflow-tutorial)
- [PostgreSQL — Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [AWS Builders' Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- [Python eventsourcing — Applications](https://eventsourcing.readthedocs.io/en/stable/topics/application.html)
- [LlamaIndex — CitationQueryEngine](https://developers.llamaindex.ai/python/framework-api-reference/query_engine/citation/)
- [Ragas — Available metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/)

## 20. 本 repo 依據

- docs/current-job-analysis-analysis-flow.md
- docs/design/task-analysis-engine.md
- docs/specs/2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md
- docs/specs/2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md
- docs/specs/2026-07-30-professional-consultant-minimal-complete-loop-research.md
- docs/specs/2026-07-31-context-engineering-model-facing-contract-research.md
- docs/specs/2026-08-01-opks-design-decisions-research.md
- docs/specs/2026-08-01-opks-raw-llm-generation-grounding.md
- docs/adr/0048-opks-evidence-axes-and-document-level-competencies.md
- docs/adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md
- docs/adr/0050-opks-proposal-minimal-shape.md
- docs/adr/0051-opks-proposal-status-machine-and-stable-entity-id.md
- docs/adr/0054-opks-progressive-elicitation-and-scheduled-child-operation.md
- docs/adr/0057-current-only-runtime-and-data-boundary.md
- docs/adr/0058-current-api-functional-modules-and-dependency-rules.md
- docs/adr/0059-core-shared-kernel-boundary-clarifications.md

## 21. 最終判斷

對 Caliburn 的專業職務說明書顧問，最好的終局不是「所有東西自己寫」，也不是「把產品交給一個功能最多的 Agent framework」。

推薦的目標候選是：

> LangGraph 候選管可恢復的 bounded application run；LangChain/OpenRouter 候選管模型、工具、structured output 與 context lifecycle；Agent Skills 管專業方法的按需載入；Pydantic／SQLAlchemy／PostgreSQL 管 typed domain 與 transaction；W3C Web Annotation／PROV 改善 anchor 與 lineage；成品完成後再由 Pydantic Evals 等候選承接評測 plumbing。Caliburn 保留的是專業分析、來源權威、deterministic domain invariants、進度語意與員工決策，不是保留所有自寫機械碼。

這仍是一個待 conformance 的目標架構，不是已 Accepted 的 framework ADR。若 LangGraph 無法比現有 durable turn／Journal 明確降低總維護面，應保留現有 runtime，只採 model／Skills／context／anchor 等有淨收益的部分；不為「全框架」重寫已正確的 authority。

最大的品質槓桿不是再加一個 Agent，而是 Context Engine：

- 在正確 focus／operation；
- 對正確 Duty／Task；
- 載入最新更正、必要原話、矛盾與 gap；
- 清楚區分誰說的、是直接說還是轉述；
- 不被無關歷史與公版資料稀釋；
- 每次保存可重播的 ContextManifest；
- 以每個 confirmed Task／JD 的品質、tokens、latency 與成本持續評測。

這樣既能保留現有研究過的工作分析與 OPKS 方法，也能把大量通用 runtime 交給主流框架維護。
