# 0038. Interview AI vNext：Context Engine、專業顧問工作流與文件共編權威

- 狀態：Accepted（owner 於 2026-07-22 核准）
- 日期：2026-07-22
- 範圍：R5 後的第一個產品垂直切片、Context Engine、LLM operation 邊界、訪談／文件共編流程、公版參考使用
- 前置決策：[`0034`](0034-interview-ai-vnext-greenfield-evidence-workflow.md)、
  [`0035`](0035-interview-vnext-openrouter-first-provider-boundary.md)、
  [`0036`](0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md)、
  [`0037`](0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)
- 研究：[`../specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md`](../specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)

## 脈絡

成品不是通用聊天機器人，也不是讓模型自行操作整份文件的 autonomous agent。使用者是對職務分析不熟悉的員工：
他與 AI 專業顧問持續對話，同時看到自己的職務說明書逐步形成；員工可直接編輯，AI 對文件的任何語意新增、修改、
刪除、合併或重分類都只能先形成可理解的提案，再由員工接受、修改後採用或拒絕。

R5-BC 已把 employee turn 轉成可追溯、可更正的 Evidence，但尚未提供下一題選擇、episode coding、canonical document
revision、AI proposal、共編 UI 或最終 JD。若下一步只做一個大型「顧問 prompt」，讓模型同時解讀回答、選下一題、查公版、
寫文件並維護聊天記憶，會重新引入下列問題：

1. 無法知道錯誤發生在理解、提問、職務分析還是寫作；
2. provider 對話歷史、editor state 與 domain truth 混在一起；
3. 員工直接編輯後，舊模型輸出可能覆蓋新內容；
4. 公版候選容易被誤當成員工實際工作；
5. 長 context 會增加成本、延遲與注意力污染；
6. 無法對單一能力做可重複 eval 或安全回復。

本 ADR 固化產品級 LLM 流程與 Context Engine 邊界，避免實作者再從 prompt 或 UI 猜架構。它不要求一次完成所有 JD
欄位，也不授權 production route、paid live、SaaS、多人共編或新微服務。

## 目前主流性檢查（2026-07-22）

本決策採用的是目前官方仍明確支持的 architecture pattern，不是因模型能力變強而淘汰的舊式 chaining：

- OpenAI 目前把 Responses API 定位為「應用程式自行控制 model interactions、state 與 orchestration」的路徑；Agents SDK
  適合由 SDK 接管 recurrent agent loop。vNext 的 domain state、CAS、Capture 與人工決策都需要 application control，因此
  own loop／own `LlmPort` 仍是合適選擇。
- OpenAI Structured Outputs 提供 schema adherence，但官方仍提醒 structured output 可能有內容錯誤；typed output 後保留
  local semantic verifier、domain reducer 與 human review 是必要的，不是重複工作。
- Anthropic 仍區分 predefined code path 的 workflow 與由模型動態控制流程的 agent，並建議先用最簡單、可組合方案；固定、
  可評估的職務訪談適合 workflow。prompt chaining 加 programmatic gate 也仍是官方列出的 production pattern。
- Anthropic 2025 Context Engineering 與 Google Cloud 2026 Context Engineering 都把重點放在每輪策展 system rules、state、
  history、external data 與 retrieval，而非只調 prompt 或無限制增加 context。operation-specific packet、bounded digest 與
  reference retrieval符合此方向。
- OpenAI 與 Anthropic 2026 eval 指引都要求保存 end-to-end trace／transcript、environment outcome、repeatable dataset 與
  graders。既有 Capture、artifact closure、trial 與 human review 應保留，但 eval 規模必須由產品風險與實際 failure mode
  決定，不能取代交付產品。
- Anthropic 2026 trustworthy-agent 指引強調 human control、透明度與在不確定時交還決策。AI 文件修改採 proposal，並以
  task bundle 降低逐項 approval fatigue，符合該方向。
- OpenRouter 目前仍正式文件化 `/api/v1/chat/completions`、strict structured output與router metadata；同時提供標為
  `beta.responses`的Responses介面。現行已live驗證的Chat adapter不是legacy text completion，也未過時；不得只因介面名稱
  較新就放棄既有conformance證據。Responses要等exact routing／metadata／schema／error matrix重新驗證後才能成為新adapter。

因此：**不採 multi-agent、LangGraph 類通用 graph runtime 或 provider-owned memory 作產品權威，不代表架構落後。**
對目前明確、可分解、具有正式文件副作用的工作，application-owned deterministic workflow 是較新的可靠 AI application
實務之一。日後只有 eval 證明動態規劃、工具迴圈或多 specialist 能帶來可衡量收益，才另開 ADR 增加複雜度。

## 決定

### 1. 一個 conversation owner，固定 application workflow

員工只面對一個 AI 專業顧問。內部可有多個 versioned model operation，但不是多個互相 handoff 的角色或 agent。

```text
employee message
  -> append transcript
  -> ContextEngine.build_turn_interpret()
  -> turn.interpret
  -> local verify + Evidence/receipt commit
  -> Agenda/Sufficiency
       -> [conditional] episode.code -> document proposals
  -> ContextEngine.build_question_select()
  -> question.select -> visible acknowledgement + one next question
```

application 決定何時執行哪個 operation、哪些資料可進 context、哪個結果可寫入 state。模型只能在 operation contract 內
做語意判斷，不得自行建立無界迴圈、任意選工具或直接 mutation domain state。

### 2. Operation catalog 與寫入權限固定如下

| operation | 主要輸入 | 輸出 | 不得做的事 |
|---|---|---|---|
| `turn.interpret/2.x` | current employee turn、eligible QuestionFrame、必要前文 | literal observations、answer bindings、dialogue/episode signals | 不查公版、不選下一題、不寫 JD |
| `question.select/1.x` | committed Evidence、active episode、candidate gaps、JobStateDigest、近期對話 | acknowledgement、selected gap、one question、QuestionFrame proposal | 不建立 employee fact、不修改文件 |
| `episode.code/1.x` | active episode Evidence、accepted job digest、必要公版片段 | task/output/indicator candidates、support refs、remaining gaps | 不直接接受候選、不選下一題 |
| `job.consolidate/1.x` | accepted tasks/outputs、既有 duties | duty grouping、dedupe/conflict proposals | 不把單一 task 換句話當 duty、不直接合併 |
| `requirements.draft/1.x` | accepted task graph、相關 reference K/S | document-local K/S proposals、task linkage、reference outcome | 不宣稱員工具備 K/S、不創造官方 code |
| `job.compose/1.x` | accepted canonical Job Model | purpose、summary、export wording proposals | 不補新的工作事實 |

`reference.retrieve` 是 application／adapter 能力，不是有自由寫入權的 agent。`authoring.apply`、proposal decision、revision、
completion gate 與 export 是 application commands，不是模型 operation。

不得建立一個同時包辦 interpretation、question、document proposal 的 `consultant.advance` 大型 operation。不同 operation
可使用同一 Provider／同一模型；分離是為 context、schema、eval、retry 與 failure attribution，不是為了追求多 Agent。

### 3. 每一輪的 exact orchestration

#### 3.1 一般 employee turn

1. transcript append 先提交；provider 失敗不能讓員工訊息消失；
2. Context Engine 從 committed state 建 `TurnInterpretContext`；
3. executor 呼叫 `turn.interpret`；
4. schema、QuestionFrame、quote/support、policy、domain 與 state CAS gates依 ADR 0037執行；
5. 成功時同一 transition保存 Evidence（可為空）、receipt與 frame lifecycle；
6. Agenda/Sufficiency 從新 state產生少量 candidate gaps；
7. Context Engine 建 `QuestionSelectContext`；
8. `question.select`輸出簡短 acknowledgement與單一自然問題；
9. application驗證 selected gap與 frame，保存 consultant turn + QuestionFrame後回 UI。

一般回合預期兩次 provider call。這是以較小、可驗證工作換取品質的有意 trade-off，不先用大 prompt壓成一次。

#### 3.2 Episode 可關閉或產生實質新內容

在步驟 6 後，若 deterministic policy判斷 active episode已足以形成文件候選：

1. 先執行 `episode.code`；
2. local grounding/linkage gate通過後建立 pending document proposal；
3. 再執行 `question.select`，讓下一題知道 episode已關閉或已有待審提案。

此類回合預期三次 provider call，但不會每輪發生。第一版採序列流程，避免為少量 latency 預先加入 parallel merge、race、
background reconciliation。取得真實 latency 後，只有彼此獨立且可證明不改語意時才平行化。

#### 3.3 文件直接編輯與 proposal decision

員工直接編輯、接受、修改後採用、拒絕都不需要 provider call：

1. command以目前 draft revision/hash作 optimistic precondition；
2. 成功後建立新 canonical revision／decision；
3. 重建 deterministic `JobStateDigest`；
4. 對舊 proposal與 active QuestionFrame做 stale檢查；
5. 下一次模型 call只讀最新 committed revision。

### 4. Context Engine 是 application service，不是模型記憶

Context Engine 的責任是針對 operation 建立 versioned、typed、bounded Context Packet。它不做 domain mutation、不產生
employee facts、不決定 accepted document，也不以自由文字 summary取代 Evidence。

共同流程固定為：

```text
load committed state
  -> select operation-required sources
  -> apply lifecycle/eligibility filters
  -> project domain IDs to operation-local ordinals
  -> enforce section priority/token budget
  -> canonicalize + hash
  -> persist context artifact
  -> provider projection
```

每個 builder 獨立，例如：

```text
build_turn_interpret()
build_question_select()
build_episode_code()
build_job_consolidate()
build_requirements_draft()
build_job_compose()
```

不得以一個 `build_everything_context()` 將完整 transcript、完整 editor JSON、全部 Evidence、全部公版與全部 pending proposal
交給每個 operation。

### 5. Context 分層與 authority

Context 依用途分四層；這是 selection priority，不是四個新服務：

| 層 | 內容 | authority／限制 |
|---|---|---|
| L0 current turn | current message、immediate consultant question、QuestionFrame | 必要；不得被摘要 |
| L1 active episode | 目前工作相關 Evidence、correction lineage、unresolved contradiction | Evidence是事實權威；只取 active/relevant |
| L2 job state | deterministic JobStateDigest、active proposals摘要、accepted entities | canonical Authoring Core是文件權威 |
| L3 references | 少量結構化公版片段與 exact source metadata | 只能作候選／coverage，不是 employee truth |

system instructions、operation definition與 portable schema是 persistent contract；state/digest是 semi-persistent application
state；current message、active evidence與retrieval result是 transient context。provider conversation object、
`previous_response_id`或 prompt cache 可以作 transport／效能能力，但不得成為唯一 domain state或 recovery authority。

### 6. Context budget 與長對話策略

1. required section缺失時 fail closed，不讓模型自行補；
2. current turn與eligible frame永不因 token budget被截斷；
3. active episode優先於舊 episode；accepted JobStateDigest優先於自由聊天歷史；
4. correction target與contradiction優先於一般 coverage；
5. reference片段在業務事實後加入，超預算先刪 reference，不刪 employee support；
6. 不把「模型曾經說過」當 truth；
7. 長期可加入 episode digest，但 digest只作導航，任何 document claim仍須回到 Evidence／accepted revision；
8. 不啟用 provider auto-truncation丟棄最舊內容後繼續提交 domain mutation；超預算要可觀測地重建 context或失敗。

Context Packet／request artifact 必須記錄 schema/operation/prompt/policy版本、state revision/hash與所選 source refs，沿用現有
Capture primitive；不另建第二套 tracing service。

### 7. `JobStateDigest` 是 deterministic projection

`JobStateDigest` 從 canonical Authoring Core建立，不由 LLM自由摘要。最小內容：

- job title／purpose（若有）；
- accepted duties、tasks、outputs、indicators與K/S的精簡文字及local ordinal；
- task-output-indicator-requirement linkage；
- active episode與已覆蓋工作區域；
- unresolved contradictions／high-value gaps；
- pending/stale proposal數量與被影響entity；
- draft revision/hash；
- selected reference standards的code/name/version與coverage，不含整份公版。

`turn.interpret`不讀 JobStateDigest。`question.select`讀 bounded digest；`episode.code`只讀 active episode所需子集；
`job.consolidate`與`requirements.draft`讀 accepted graph投影。員工直接編輯後立即重建 digest，不能等待下一次 LLM summary。

### 8. Agenda／Sufficiency 是輕量決策狀態，不是欄位問卷

Agenda 追蹤：active episode、covered work、unresolved contradiction、candidate gaps、declined/dont-know history、question
budget與finish intent。application先產少量 eligible gaps，`question.select`只能從中選一個或回傳 close／finish action；模型
不得憑空建立會直接綁短答的隱藏 target。

gap priority預設為：

1. correction／contradiction；
2. task action/object/purpose；
3. output或observable success standard；
4. exception、dependency與responsibility boundary；
5. broaden work coverage；
6. close episode／offer finish。

不是每個task都必須補齊frequency、tool、output、standard、exception等所有slot。每個episode只追1–2個高價值缺口；重複
無新Evidence、不知道、拒答、低資訊增益、疲勞或budget到達時就close。員工可隨時finish，系統只提示缺口，不以完整度
gate強迫繼續。

### 9. Canonical Authoring Core 與 AI proposal

現有 editor不是domain authority。R5後先建立最小、UI-independent Authoring Core，至少支援：

- 單一 JobModel與單一active draft；
- stable document entity identity；
- immutable/optimistic draft revision；
- employee direct edit command；
- AI add/replace/remove/merge proposal（第一版可只做add/replace）；
- employee accept/edit-then-accept/reject decision；
- proposal support refs、base revision/hash與stale status；
- deterministic JobStateDigest。

現有 editor只作thin adapter candidate。若不能無損呈現entity linkage、proposal diff、revision與provenance，就建立簡化的
chat + document workspace，不為沉沒成本改壞core。

所有會改文件的 AI輸出都是proposal；聊天acknowledgement、下一題、缺口說明不是document proposal。員工direct edit立即
成為draft truth。AI不得在背景套用proposal、自動rebase過時proposal或覆蓋員工剛修改的文字。

### 10. Proposal呈現與review負擔

提案以task為中心形成可部分接受的bundle，不為每個atom跳一個彈窗：

```text
task proposal
  + outputs
  + behavior indicators
  + linked K/S
  + why/source
```

外部文案使用：

- 符合我的工作；
- 選擇部分採用；
- 修改後採用；
- 不符合；
- 為什麼這樣建議。

第一版先讓 task + output可用，再加入indicator、duty與K/S。proposal只在episode close、實質新Evidence或員工主動要求
整理時產生，不在每個turn造成文件閃動。拒絕task時，依附output/indicator/K/S標示失效；第一版不自動重新連結。

### 11. 公版資料與職能基準metadata

公版是專業參考、coverage checker與export mapping，不是employee fact。使用順序固定為：

```text
confirmed employee task
  -> structured/hybrid reference retrieval
  -> usable | partial | no_match
  -> clarification or labeled proposal
  -> employee decision
```

前期先聽員工工作；`turn.interpret`永遠不看公版。`episode.code`只在已有employee support時取少量相關task/output/indicator，
`requirements.draft`依accepted task取K/S；`question.select`只有在application明確提供reference-backed coverage gap時才能使用，
且不得把reference claim包裝成員工已說過。

公版authority保存 exact metadata：scheme、official code、name、category path、issuing authority、version/published date、
source URI/hash。LLM不得生成或修正官方code。客製JD與公版以many-to-many mapping連結，標示primary/supplemental及
usable/partial/no_match；custom task/K/S合法且使用document-local identity。公司內部職務代碼、系統JobModel ID與官方
職能基準code是不同欄位。

retrieval index只是可重建adapter。第一版可沿用現有Qdrant/vector資料；若繁中benchmark顯示不足，再加入結構化filter、
BM25/hybrid與reranker，不預先重建另一個knowledge platform。

### 12. Provider、cache與state

- OpenRouter仍是第一個production candidate；direct OpenAI保留reference／未來adapter，遵守ADR 0035/0036；
- OpenRouter Chat Completions仍是已驗證主線；`beta.responses`只列為後續獨立adapter候選，不在原adapter內用compatibility
  branch混合兩種wire protocol；
- `LlmPort`與operation contract是provider-neutral；capability差異由binding／adapter／conformance處理；
- application DB是transcript、Evidence、draft、proposal、decision、operation與Capture authority；
- provider conversation state可作可替換transport optimization，但第一版維持stateless explicit request artifacts；
- 允許provider prompt caching／stable-prefix caching降低成本；cache hit/miss只是execution evidence，不影響semantic truth；
- 不做semantic response cache重用employee turn結果；相同文字在不同QuestionFrame／revision下語意可能不同；
- 不因模型context window變大就傳整份歷史。大context是容量，不是相關性或grounding保證。

### 13. Failure、concurrency與recovery

- provider/schema/conformance失敗：保留transcript與typed operation failure，不建立Evidence／document proposal；
- valid zero-Evidence interpretation：保留receipt並繼續由Agenda處理；
- state/draft在call期間前進：舊結果`state_context_stale`，不自動rebase；
- employee edit使proposal base revision過時：proposal標stale，重新產生或由員工明確review；
- recovery從persisted artifacts/checkpoints繼續，provider-completed後不重打provider；
- reference缺失／no_match：不算provider failure，允許custom candidate；
- incomplete/refusal/timeout：不得解析partial JSON成成功；
- UI可顯示安全的retry／rephrase，但不能偽造顧問已理解。

### 14. R5-D範圍收斂

R5-D要做，但它是短小correctness audit，不是下一輪架構重構或使用者功能。R5-BC已完成frequency/current、mixed、CAS、
recovery與minimum Capture的大部分行為；R5-D只盤點並補齊：

1. exact bundle corruption matrix；
2. re-export byte identity；
3. existing 12-case mechanical/reference gate；
4. no-network + real PostgreSQL final gates；
5. status/README handoff。

R5-D不得新增產品domain、LLM operation、migration、provider behavior或大規模case expansion。它可與scripted Authoring Core
prototype準備並行，但production OpenRouter user route前必須完成。若R5-D要求再次hard-cut Turn Interpreter，立即停線另行
review。

詳細施工、root contract、corruption matrix、byte-identity gate與停線條件見
[`../plans/2026-07-22-interview-vnext-v3-5a-r5-d-bounded-correctness-closure-plan.md`](../plans/2026-07-22-interview-vnext-v3-5a-r5-d-bounded-correctness-closure-plan.md)。

### 15. 產品交付順序

1. **R5-D bounded closure**：只補完整性gate；
2. **最小Authoring Core**：task entity、revision、direct edit、一組scripted AI task/output proposal、三種employee decision、
   stale、JobStateDigest；
3. **Context Engine + `question.select`**：先形成自然、不中斷的真實訪談；
4. **production OpenRouter composition**：沿用已驗證adapter，不另寫簡化production adapter；
5. **`episode.code` task/output vertical**：第一個真正AI文件提案成品；
6. **針對此vertical slice做true-live與真人review**；
7. **duty/indicator/K/S/reference mapping**；
8. **completion assessment與deterministic exports**。

不先做SaaS、tenant、company catalog、多人權限、CRDT、general agent framework、multi-agent、fine-tuning、長期vector memory或
SKILL.md runtime。這些只有在產品數據證明需要時再設計。

## 第一版已確認的產品決策

1. 使用者與唯一人工決策者是員工；沒有另一位顧問負責終審。
2. 第一版只處理一名員工、一次session、一份當下職務與單一active draft。
3. AI所有文件語意變更都是proposal；employee direct edit立即成為draft truth。
4. task/output先做；indicator、duty、K/S依序加入，不要求第一版一次完成全部欄位。
5. AI proposal採task-centered bundle且可部分接受，不為每個欄位逐一打斷員工。
6. 員工可隨時finish；系統提示缺口但不強迫完成欄位問卷。
7. K/S是document-local requirement，不是員工能力評分；必須連到task，可來自公版或custom inference。
8. 公版`no_match`是正常outcome；官方code/name/category/authority/version只能來自source record。
9. canonical Authoring Core與UI分離；現有editor可包裝或替換。
10. first product是modular monolith，不先設計company/SaaS/multitenancy。

尚未成為第一版hard requirement、可後續裁決：既有JD匯入格式、多個export模板、跨session個人偏好、公司內部job code管理、
多人共編、reference自動升版、語音訪談與跨語言輸出。

## 被否決的選項

### 一個大型顧問prompt完成所有工作

無法隔離錯誤、驗證grounding、可靠retry或控制文件副作用；也會迫使每輪送出不相關資料。

### Provider conversation memory是產品真相

供應商綁定、recovery、版本與資料保留語意都不符合canonical domain authority需求。可以作transport能力，不能取代DB。

### 每輪傳完整transcript與完整JD

長context容量不等於注意力品質；會增加成本、context rot與舊內容干擾。採operation-specific packet與deterministic digest。

### 自由multi-agent或orchestrator-workers

目前subtasks可預先定義、write authority嚴格且評估標準清楚。動態delegation增加trace、latency、cost與責任歸因，沒有已知
產品收益。

### 每輪都產生文件patch

會造成flicker、approval fatigue與半成品污染。只在episode close／實質新資訊／員工要求時提案。

### 公版task/K/S直接寫入文件

公版只是candidate。沒有employee Evidence或employee decision就不能成為此職位truth。

### 用自由文字LLM summary作長期記憶

summary可能遺漏否認、時間與provenance。JobStateDigest必須由accepted state確定性投影；模型summary最多作導航。

## 後果與取捨

- 一般turn有兩次call，episode close可能三次，latency/cost高於one-shot；換得可驗證、可重試、可評估與較高語意品質；
- Context Engine與Authoring Core需要正式契約，但避免每個operation重複拼prompt或依賴UI JSON；
- strict stale會偶爾要求重跑operation，但不會把舊結果套進員工新文件；
- employee approval確保authority，task bundle與低頻proposal降低rubber-stamp疲勞；
- public reference保留專業覆蓋能力，但不會把公版工作偽造成員工事實；
- operation分離不表示永遠不能合併call；若真實eval證明可在不破壞gates下顯著降低latency，另做versioned ablation；
- 直接API／own loop讓一人團隊較易debug；未來若出現大量動態tool loop或specialist handoff，再評估Agents SDK／framework。

## Supersession

- 擴充ADR 0034的一個adaptive conversation owner與Evidence-first workflow；
- 保留ADR 0035 OpenRouter-first及ADR 0036 provider-neutral runtime；
- 依ADR 0037的QuestionFrame、Evidence.v3、strict CAS與employee authority建構後續產品；
- 取代將`_pending`視為canonical proposal store的舊設計；舊editor pending只能是UI projection；
- 取代「先完成全部R6再做共編」的交付順序：先做scripted最小Authoring vertical，再以真產品loop建立針對性live eval；
- 不否定episode與agenda概念，但它們是application workflow state，不是自由agent planner。

## 來源

- OpenAI, [Agents SDK：Responses API vs. Agents SDK](https://developers.openai.com/api/docs/guides/agents)
- OpenAI, [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- OpenAI, [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- OpenAI, [Evaluate agent workflows](https://developers.openai.com/api/docs/guides/agent-evals)
- Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Anthropic, [Trustworthy agents in practice](https://www.anthropic.com/research/trustworthy-agents)
- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Anthropic, [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- Google Cloud, [What is AI context engineering?](https://cloud.google.com/discover/ai-context-engineering)
- OpenRouter, [API Reference](https://openrouter.ai/docs/api_reference/overview)
- OpenRouter, [Create a response (`beta.responses`)](https://openrouter.ai/docs/api/api-reference/responses/create-responses)
- OpenRouter, [Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata)
