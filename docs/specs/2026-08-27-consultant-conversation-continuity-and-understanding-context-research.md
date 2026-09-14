# AI 顧問對話連續性、工作理解與 Context 邊界研究

- 日期：2026-08-27；2026-08-29 依最新 JD 欄位裁決與 Claude／Codex／主流記憶框架研究完成第六輪重審
- 狀態：產品原則、拒絕記憶決策、§15.4「不固定 continuation」成本原則、§15.6 compaction 邊界、§15.11–§15.12「具體案例 → 穩定工作模式 → JD」shape、§15.13「不另建可寫 WorkScope」、§15.14「質性 coverage／無假百分比」、§15.15「案例→模式最小關係／局部更正傳播」、§15.16「無 anchor 訊息的漸進式 Context recall」、§15.17「直接角色陳述／事件案例分流的歸納門檻」、§15.19「不另建 model-owned 訪談 Agenda」與 §15.20「模型只填語意、atomic tagged Tool、framework receipt」已形成目前基線；§15.21 的三種 Work Understanding 責任邊界、metadata ownership，以及 `WorkUnderstanding／WorkEpisode／OpenIssue` 暫定內部名稱已獲 Owner 可翻案的暫時同意；§16 已依 Codex 真實兩階段 memory pipeline、Claude index＋JIT memory 與 LangMem core manager 重開「是否以成熟框架替代自製 reconcile」的裁決，結論是現在做窄相容性／效果 spike、通過前不改 production authority；ADR 0071 仍為 Proposed
- 範圍：跨輪對話連續性、未回答問題、工作理解、一般待釐清、「需要你的確認」、Focus、目前 JD／待審差異，以及每輪最小充分 Context
- 不在本輪：RAG／Reference、正式 LLM eval、A／能力級別、自動核准、多 Agent、完整 prompt／chain-of-thought 保存
- 上位產品方向：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md)
- 相關 UI／authority：[`2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md`](2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md)

> **閱讀規則**：本研究的最新目前基線是 §15.6、§15.11–§15.21、§16 與 Proposed ADR 0071；§15.4 只保留「不固定增加 model continuation」的成本原則，當中的 final structured batch、`no_change` dummy output 與雙出口 contract 已由 §15.20 取代。§15.6「只壓縮暫時 Context、不壓縮工作理解」、§15.11–§15.12「有界完整語意紀錄＋具體案例／穩定工作模式／待釐清或矛盾」、§15.13「穩定工作模式承接語意、OrientationIndex 承接導航」、§15.14「待補充／目前足夠的質性 coverage」、§15.15「只保存 `supported_by`／`about` 的 exact-revision 關係、先重看直接依賴再按語意擴大」、§15.16「小型導航目錄＋明確 anchor 預載＋同一主顧問按需讀取」、§15.17「不數案例、依直接角色陳述或事件案例分流」，以及 §15.19「Pattern／Unresolved／Focus／coverage 導航，不另建 Agenda writer」已於 2026-08-28 由 Owner 暫定接受。第一版不得先把固定案例數、`confidence score`、embedding、固定 router model、第二份可寫索引、全量記憶注入、混合 role／lifecycle status、JD-like facets 或另一個 Planning store／task list 當成施工規格。這些結論都不是永久鎖定：後續權威研究、固定 transcript、成本／品質證據或實作發現可重開並由本文新節或 successor ADR 取代。§16 已明確取代 §13.3、§14.7.2、§14.9.2、§15.21.7 與 §15.21.10 中「沒有真實失敗前不做 LangMem canary」的舊限制：目前巨型複合輸出、已知 structured-output 修復成本與 Owner 的 framework-first 目標，已足以支持一個窄 spike；但不等於已核准 production 導入。在目前基線被明確取代前，不得施工 §14.8.3 的「一句原子 claim＋facets」舊候選，也不得依 §14.3／§14.7 的舊候選建立另一個可寫 `WorkScope`。較早段落用來保留診斷脈絡；若 `Evidence`、`Gap`、`Proposal`、`Work Model`、`Current JD`、`Focus`、`Agenda` 或 `InterviewWorkItem` 等舊名稱與最新裁決衝突，只能把它們當歷史實作名詞，不得據此重建舊 writer／schema。

> **欄位契約補正（2026-08-29）**：§15.18 只保留 internal 三種語意責任；其 flat all-required provider wire，以及 §15.4 以 final structured root 回 `UnderstandingEffectBatch／no_change` 的舊出口，都已由 §15.20、§15.21.15～§15.21.16 與 [`2026-08-28-llm-authored-field-contract-audit.md`](2026-08-28-llm-authored-field-contract-audit.md) 取代。施工不得再使用固定 `ConsultantModelOutput`、dummy sentinel、model-authored source handle／occurrence／Skill receipt，或要求每輪提交空 effect 證明「有分析」。

> **第五輪研究提醒（2026-08-29）**：最新核心 JD 已明確排除 A／能力級別，且 §15.21 發現舊名 `Pattern` 可能不足以涵蓋穩定的角色定位、回報關係、責任邊界與工作條件。Owner 已暫時同意「目前成立的完整理解／具體工作事件／跨輪未解問題」三種責任、runtime-owned metadata，以及 `WorkUnderstanding／WorkEpisode／OpenIssue` 暫定內部名稱；精確 branches 仍待複審。完成複審前不得先改 ADR、production schema 或 Tool contract，也不得讓舊 Case／Pattern 名稱反過來限制產品語意。

> **討論與文件衝突規則（2026-08-29 Owner 確認）**：本研究中的「同意」一律是可翻案的暫時收斂，不代表後續不得依更完整需求、最新權威資料、成本／效果或實作證據修正。發現文件、ADR、計畫、code 或較早討論與目前方向衝突時，不得自動採「日期較新者勝」、不得因舊實作已存在就保留，也不得靜默改寫 Accepted／Proposed 決策。應先列出兩邊各自要解決的問題、當時脈絡、官方依據、產品效果、成本、遷移與風險，與 Owner 討論後才標示保留／修訂／取代。未完成裁決前，衝突內容不得進入施工規格。

### 最新決策速查（2026-08-29）

| 產品問題 | 已確認規則 | 官方 primitive／可轉移限制 |
| --- | --- | --- |
| 員工原話與更正 | 原話 immutable；「剛才說錯」是普通新訊息；source over inference，但不採 latest-wins | [OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) 支持應用重建對話狀態；它不替 Caliburn 判定哪句工作事實有效 |
| 工作理解 | source-linked、可修訂 collection；包含成立、待釐清、矛盾、已修訂與未定位線索；不是 JD 或聊天摘要 | [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 支持 collection/profile primitive；內容分類是 Caliburn policy |
| 員工直接改 JD | 立即走文件 authority，但只作下一輪 delta／signal；不自動變成 employee source 或工作理解 | revision／digest 是通用 optimistic concurrency；「不是工作來源」是產品裁決 |
| AI 待審 JD | 引用 1～N 筆工作理解＋短理由；正式 JD 不保存理由；員工編輯綠色內容後仍待審 | [VS Code Review](https://code.visualstudio.com/docs/agents/run/review-code-edits) 支持在同一工作面檢視／修改 diff；最新 Agent Host 並沒有 Caliburn 所需的 pending authority，因此只參考 UI 機制 |
| Accept／Reject | Accept 才提升 approved；Reject 整組回退、不填理由；留最小 fingerprint，只有無新資訊的同案才不重提 | [LangChain HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) 提供 approve/edit/reject primitive；semantic group 與拒絕防重提是 Caliburn policy |
| 待釐清與 Focus | 待釐清是工作理解狀態；Focus 是可恢復 runtime bookmark，不是事實 | [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 承接 checkpoint；不替產品定義問題優先順序 |
| 訪談導航 | Pattern＋Unresolved＋Focus＋derived coverage；不另建 Agenda／Plan writer | [Pydantic Planning](https://pydantic.dev/docs/ai/harness/planning/) 的最新版能力完整，但定位為 long agentic execution plan；本案沒有未被既有四者承接的獨特責任 |
| 需要你的確認 | blocking ambiguity 才在 safe boundary durable interrupt；一題、2～4 選項或自由輸入、回答後重新分析 | [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) 承接 pause/resume；[Claude User Input](https://code.claude.com/docs/en/agent-sdk/user-input) 只支持 UI 形狀 |
| 每輪 Context | 本輪訊息＋最短近期雙向對話＋相關理解／Focus＋workspace orientation＋compact pending provenance；其餘按需 | [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 支持最小高訊號、structured notes 與 just-in-time retrieval |
| 無 ID／Focus 的召回 | 小型 Pattern／待釐清／未定位導航目錄常駐；明確 refs 由 middleware 預載；其餘由同一主顧問按需 `grep／read`，找不到就不猜 | Claude Code／Codex 的 progressive disclosure 支持機制；它們不替產品判斷哪筆工作理解相關 |
| Skill 與驗證 | 模型不自報 `skill_ids`；framework receipt 記錄實際載入，deterministic verifier 驗來源、quote、revision 與 domain invariant | [LangChain Structured Output](https://docs.langchain.com/oss/python/langchain/structured-output) 只保證 schema shape，不保證職務內容正確 |
| Domain Semantic Memory 底層 | 唯一 canonical collection 暫留 LangGraph checkpoint；現在以 LangMem core `create_memory_manager` 做窄 spike，驗證能否替代自製 LLM reconcile；不採 Store manager／agent 直寫 memory | [LangMem core API](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/) 可由 caller 控制 storage／removal；pre-1.0 與現行 adapter 相容風險仍須先驗證 |

## 0. 白話結論

LLM 不會因為「上一輪曾經想過或問過」就永久記得。每次模型請求本質上只看當次送入的 Context；產品可以傳入對話歷史、延續 provider conversation，或從自己的 durable state 重建必要內容，但三者都不是模型腦中天然存在的永久記憶。

Caliburn 不採「每輪重播上一輪完整 prompt」。推薦做法是：

1. 員工原話與顧問可見回覆完整持久保存，供歷史與按需查詢；
2. 把已成立、待釐清、矛盾與已修訂的**工作理解**保存成有來源的 durable semantic state；
3. 上一輪詢問但尚未回答的事項，以「仍未解決的工作理解問題」保存，而不是只躲在上一輪 prompt 文字裡；
4. 每輪只帶入本輪員工原話、理解指涉所需的最短近期雙向對話、相關工作理解、目前 Focus、少量待審索引與工作區讀取入口；
5. 完整舊對話、目前 JD、核准基線、待審 Diff、來源與 Skills 依需要讀取，不一次塞滿；
6. 對話摘要、provider conversation state、prompt cache 與 context-selection receipt 都不是工作事實或文件 authority。

每輪的概念順序是「吸收員工新訊息並更新工作理解 → 依最新理解檢查目前 JD／待審內容 → 回答員工當輪直接提出的問題 → 必要時再提出一個主要追問」。這是同一個顧問 product run 的語意責任，不代表固定四次模型呼叫或兩階段 pipeline。依 §15.20 最新欄位契約，只有工作理解確有新增／修訂／退役時才呼叫 atomic Tool；沒有語意變化就正常回覆，不填空 effect／`no_change` 表單。只有本輪 canonical Tool result 真的會改變後續 JD 操作或問題判斷時，才 continuation。

因此，若 AI 問「這項異常最後由誰核准？」而員工下一句先補充別件工作，AI 應先吸收那份新資料，但原問題仍維持待釐清；它不會因為員工沒有立刻回答而自動消失，也不必每輪逐字重播原始 prompt 才記得。

## 1. 「看得到上一輪 prompt」的正確意思

### 1.1 模型本身沒有跨請求記憶

[OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) 明確說明，單次生成請求本身是 stateless；多輪互動要由應用程式重新提供歷史，或使用 Responses／Conversations 的 state 機制。[OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) 也區分當次 `instructions` 與 conversation items；即使使用 `previous_response_id`，先前輸入仍計入後續 input tokens。

這代表「模型記得」其實可能是四種不同機制：

| 機制 | 能做什麼 | 不能當成什麼 |
| --- | --- | --- |
| 近期 message history | 理解「剛才」「那件事」、自然承接問答 | 永久工作知識、可靠長期記憶 |
| LangGraph checkpoint | 保存 thread 的訊息、目前工作、未解事項與恢復位置 | 自動選出每輪應傳入的最佳 Context |
| LangGraph Store／目前 workspace | 保存原話、工作區與跨 run 仍需讀取的資料 | 每輪全部自動進模型注意力 |
| provider conversation／compaction | 便利延續與壓縮長對話 | Caliburn 唯一 authority、零成本記憶、永不遺漏的重要語意 |

Prompt cache 也不是記憶。它只對相同或相近的 prompt prefix 降低重複計算成本／延遲；產品仍必須決定當輪要送什麼，cache 不會替產品保存「這個問題尚未回答」。

### 1.2 Caliburn 不保存上一輪完整 prompt 作為產品狀態

完整 prompt 混合了當時的 system instructions、選到的 Context、Tool／Skill 目錄、暫時診斷與員工訊息。把它永久當成下一輪輸入會造成：

- 同一工作理解、目前 JD 與待審差異重複出現；
- 已過時的推論或舊 workspace 狀態繼續干擾；
- 訪談越久 token、延遲與成本越高；
- prompt 版本與模型更換後，舊文字反而限制新的 Context policy；
- 很難分清哪些是員工事實、AI 暫時推論與執行期提示。

所以保存的是**來源、語意狀態與執行 receipt**，不是把完整 prompt 複製成第二份記憶。若需重播與診斷，receipt 保存 prompt／policy／Skill／Tool version、選取 refs、hash、tokens 與原因；原始內容仍由既有 Store／checkpoint 取得。

## 2. 下一輪模型應取得的 Context

採「目前狀態＋最近變化＋按需展開」，不採「完整歷史＋完整 Diff」。

### 2.1 每輪必帶或優先帶入

1. 穩定且 versioned 的顧問規則、authority 邊界與本輪目標；
2. 本輪員工完整原話；current source identity 由 runtime 預先綁定，不要求模型看見或回填 raw handle；
3. 理解代名詞、否定、更正與「剛才」所需的最短近期**員工＋顧問雙向對話**；
4. 目前 Focus 指向的工作理解／待釐清事項，以及相關的已成立、矛盾或已修訂理解；
5. 仍未回答且可能影響本輪判斷的普通待釐清；
6. 若存在，只帶「需要你的確認」的問題、影響範圍與阻塞狀態；
7. 目前 JD／workspace 的精簡 orientation、validation 狀態，以及待審變更的數量、affected stable IDs／paths 與 AI-pending provenance；
8. 自上次成功分析後，與本輪相關的員工 JD delta、Accept／Reject 結果；JD delta 不是 employee source，Accept 只需最小 receipt，Reject 只提供不含理由的防重提 fingerprint；
9. 可用 Skills 的短 catalog；完整 Skill 正文仍按需載入。

### 2.2 只在需要時讀取

- 較早的逐字對話與員工來源；
- 完整目前 JD 或特定 Duty／Task／OPKS resource；
- 核准基線；
- 某組待審變更的完整 before／after／理由／dependency；
- 完整 Skill 方法；
- 更正與來源 lineage。

### 2.3 不應每輪重複傳入

- 上一輪完整 system／developer prompt；
- 完整 conversation transcript；
- 完整核准 JD 與完整 working JD 各一份；
- 沒有變動且與本輪無關的全部 AI 待審 Diff；
- 已消耗且沒有新資訊價值的 Tool outputs；
- 每個 Task 的「缺 O／P／K／S」欄位清單；
- chain-of-thought 或 provider 內部 reasoning。

[Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 建議把 Context 當成有限注意力資源，以最小高訊號集合、compaction、structured note-taking 與 just-in-time 讀取維持長流程；[Claude Code context window](https://code.claude.com/docs/en/context-window) 也顯示長 session 會壓縮歷史，再重新注入 durable instructions／memory 與最近相關檔案，而不是永久保留所有原始 token。這些來源支持上述形狀，但不直接決定 Caliburn 的職務分析欄位。

## 3. 員工沒有回答上一題時怎麼記得

上一輪問題有三種不同東西，不能混在一起：

1. **顧問當時說的原句**：留在 conversation history，供自然銜接；
2. **它為何需要問**：保存成有來源的 unresolved work-understanding item，例如「目前不清楚異常處理的最終核准責任」；
3. **現在是否先處理它**：由 Focus／routing 決定，可保持、停放或日後回來。

不是每句問號都要升格成 durable state。只有仍會影響工作理解、JD 或後續訪談，而且目前仍可由員工回答的**語意未知／矛盾**才進工作理解；寒暄、說明性反問、已被後文自然回答的問句與模型措辭不建立另一份 question queue。問題原句留在對話歷史，工作理解保存的是可重新措辭的意義，例如「異常案件最終核准者仍未知」。

若員工回答別題：

- 本輪提供的新資訊仍要正常吸收，不能因「答非所問」而丟掉；
- 原 unresolved item 不會自動標成 resolved；
- 若它不阻塞現在的安全分析，可留在一般待釐清，顧問稍後自然回問；
- 若它是只有員工能決定、而且缺少答案會使受影響分支無法安全繼續的重大歧義，才成為 required clarification，阻塞該分支；
- required clarification 不阻止員工離開頁面；進入等待前可先 durable commit 本輪已完成且不受歧義影響的安全結果，進入等待後則不再背景執行模型，直到員工回答。

範例：

```text
AI：加班名單最後是你核准，還是主管核准？
員工：另外我每月也會做新人勞動法教育。

本輪結果：
- 新增／修訂「新人勞動法教育」的工作理解；
- 「加班名單最終核准者」仍是待釐清；
- 若不影響教育訓練的分析，可先處理新線索；
- 日後自然回問，不假裝上一題已回答。
```

這種設計比「重播上一輪 prompt」穩定，因為問題即使經過 context compaction、模型更換或頁面關閉，仍以產品語意存在；顧問原句則可依需要重新措辭。

## 4. 工作理解、待釐清、欄位完整度與 Focus

### 4.1 工作理解是有來源的詳細目前認知

工作理解不是 JD 草稿，也不是一段濃縮聊天摘要。它保存 AI 對員工實際工作的詳細、可修訂理解，包括：

- 目前成立的工作事實與邊界；
- 尚未說清楚但具實際語意的問題；
- 前後衝突；
- 後來修正或被取代的理解；
- 仍未定位、但確實由員工敘述得到的工作線索。

它可以支援 Task／Duty／OPKS Skills 分析，但本體不必長成 Task／Duty／OPKS schema。JD 是 Skills 依工作理解與方法產生的目前成果；員工直接編輯 JD 也不直接改工作理解。若 JD 新內容和理解不一致，下一輪顧問比較後再詢問或以新員工來源修訂理解。

### 4.2 「缺 O／P／K／S」不是自動待釐清

Owner 已確認：員工可見的「待釐清」只顯示**具體、可回答且會影響工作理解或 JD 的問題**。單純欄位為空只是 Skill／deterministic projection 可使用的內部分析訊號，不能直接升格成 durable Gap。

| 情況 | 處理方式 |
| --- | --- |
| Task 沒有 O 欄位，但該工作未必有獨立產出 | 只作內部完整度訊號；不顯示問題 |
| 已知成果存在，但不知道成果是什麼 | 轉成工作理解待釐清：「這項工作完成後通常留下什麼成果或紀錄？」 |
| K／S 尚未分析，且目前訪談不需要 | 不建立待釐清；相關 Skill 日後按需處理 |
| 員工已提到一項知識／技能，但不清楚支援哪項工作 | 保存來源化的未定位工作線索；只有需要員工回答時才顯示白話問題 |
| 員工前後對責任或完成標準說法衝突 | 保存工作理解矛盾；若無法安全自行消解，再提出「需要你的確認」 |

既有 OPKS 研究也已收斂：不是每個 Task 都必須機械式填滿 O／P／K／S，O／P／K／S 應依工作與證據按需深化。U.S. OPM 的 [Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 要求系統性蒐集工作內容、情境、要求並建立 Task－competency linkage，但沒有要求所有 Task 填滿同一組欄位。

### 4.3 Focus 是 runtime attention bookmark

Owner 已確認：Focus 不放進工作理解本體。

- 它是 LangGraph thread state 中指向某項工作理解、待釐清問題或訪談範圍的 runtime bookmark；
- 它可跨關頁與恢復存在；
- 它沒有自己的來源依據，因為它不是工作事實；
- 員工不能直接編輯 Focus，但可以用自然對話改變訪談方向；
- Focus 不必綁定 Task／Duty／OPKS ID；
- Focus 改變不會改寫工作理解，也不會自動建立／解決待釐清。

## 5. 目前 JD 與尚未審核的 AI 差異

AI 與員工持續看到並編輯同一份最新 working copy；核准基線仍是匯出 authority。下一輪模型不需要另外收到一份「完整尚未處理 AI 差異」，因為那些 after-state 已存在目前 workspace。

但只看最新內容仍不夠：模型需要精簡 provenance，知道哪些範圍是 AI pending、哪些已由員工核准或直接編輯。故每輪提供 compact review index；完整 Diff 只在本輪新資訊影響該範圍、員工拒絕／修改造成需重算，或模型真的需要比較時按需讀取。

- 未變且與新資訊無關的 pending：不重新分析、不重建；
- 新資訊影響 pending：讀該 group 的 review details，在目前 workspace 上修訂並更新說明；
- 員工接受：目前值與核准基線一致，只留 idempotency／crash recovery 所需的最小 command receipt；AI 理由不進核准 JD，也不製造工作理解；
- 員工拒絕：整組還原 baseline，不要求理由；保留 `semantic change＋相關工作理解版本＋boundary` 的最小 fingerprint，只有三者都沒有實質變化時抑制原樣重提。員工若另在聊天說明，該訊息才是 employee source 並可修訂工作理解。

## 6. Framework mapping

[LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 與 [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 把 thread-scoped checkpoint 與跨 thread Store 分開：checkpoint 適合對話連續性、human-in-the-loop、恢復與目前 graph state；Store 適合 application-defined facts／knowledge。Caliburn 沿用這套成熟分工，但不建立同目的第二套元件：

| 產品目的 | 成熟機制 | Caliburn 最薄政策 |
| --- | --- | --- |
| 跨輪對話、未解問題、Focus、run resume | LangGraph typed state＋Postgres checkpointer | 哪些語意算 unresolved、何時 resolved／retired／required |
| 員工逐字來源與目前 JD workspace | LangGraph Store／Deep Agents StoreBackend | document scope、source authority、workspace validation |
| 每輪最小充分 Context | LangChain middleware＋read tools | 必帶下限、選取理由、budget、authority labels |
| 長歷史縮減 | message window／compaction／non-authoritative summary | 不得取代來源、工作理解、required clarification 或目前 workspace |
| 待審差異 | approved ↔ workspace derived semantic review | compact provenance、atomic group、employee authority |
| 欄位完整度 | Skills＋deterministic projection | 只有實際語意問題才升格為員工可見待釐清 |

不新增 `PromptMemory`、`PendingQuestionStore`、第二個 Gap database、provider conversation authority 或 RAG。工作理解與 unresolved semantic items 使用同一份 LangGraph semantic state；Focus 只是指向其中項目的 runtime state。

## 7. 現行 code 稽核與差距

2026-08-27 核對現行 code：

- `run_service.py` 每個員工 run 建立 bounded inner agent，初始只傳入本輪 `HumanMessage`；
- inner LangChain agent 沒有另外綁定跨 run checkpointer，因此上一輪完整 model prompt／Tool loop 不會自動進下一輪；
- `context.py` 每次 inference 會從產品 snapshot／Store 重建 authority floor，帶入目前訪談工作、可修訂理解、Gap、最近兩則顧問結果、待審數量與 `/approved`、`/review`、`/workspace` 讀取入口；
- 這已避免每輪塞入完整 workspace 與完整 Diff，是正確基礎；
- 但目前只帶最近顧問結果，尚未形成 token-bounded 的近期**員工＋顧問雙向**對話；
- 若一個普通未回答問題只存在舊 `next_question` 文字、沒有轉成 durable unresolved semantic item，超出近期窗口後仍可能被遺忘；
- global orientation 目前以 approved document 為主，還未完整反映 latest current workspace＋pending provenance；
- durable `GapItem` 與工作理解分開，仍可能把欄位缺失與真正語意未知混成兩套 authority。

因此現行系統不是「完全沒記憶」，但也不能宣稱模型會看到上一輪完整 prompt。後續施工應補的是**雙向近期對話＋durable unresolved understanding＋current-workspace orientation**，不是接上 provider conversation 後把完整歷史全部重播。

## 8. 來源、直接支持與可轉移限制

| 第一手來源 | 直接支持 | 不能據此宣稱 |
| --- | --- | --- |
| [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) | 單次請求 stateless；歷史必須由 messages、previous response 或 conversation state 提供；長歷史受 context／token 限制 | OpenAI 沒有定義 Caliburn 的工作理解、待釐清或 Focus schema |
| [OpenAI — Responses create](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) | conversation items、instructions、context management、prompt caching 是不同機制 | prompt cache 不等於工作記憶；OpenRouter／LangChain 也不必採相同 wire |
| [OpenAI Codex — Memories](https://learn.chatgpt.com/docs/customization/memories) | durable summaries、memory entries 與 supporting evidence 可和當輪工作 Context 分離並按需回看 | Codex 的 coding memory UI 不等於 Caliburn 的職務理解 schema，也不直接決定員工應看到哪些欄位 |
| [Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 最小高訊號 Context、compaction、structured note-taking、just-in-time retrieval | coding／research agent 經驗不能直接證明繁中職務訪談品質 |
| [Claude Code — Context window](https://code.claude.com/docs/en/context-window) | 長 session 會 summary／compaction，durable instructions／memory 重新注入，最近相關檔案按需恢復 | 不代表 Caliburn 應保存 CLAUDE.md、檔案歷史或 coding harness |
| [LangGraph — Memory](https://docs.langchain.com/oss/python/concepts/memory) | thread history／checkpoint 與 semantic long-term memory 分工；完整長歷史會增加干擾、延遲與成本 | framework 不知道什麼是職務事實或哪個問題值得再問 |
| [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | checkpointer 承接 thread continuity／HITL／resume，Store 承接 application-defined durable data | 保存 state 不等於每輪都應把 state 全部傳給模型 |
| [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | 只有流程確實需要外部輸入時才 durable pause／resume；適合「需要你的確認」與核准 | 一般待釐清不應全部變成 interrupt，也不會自動更新職務語意 |
| [Microsoft Agent Framework — Storage](https://learn.microsoft.com/en-us/agent-framework/concepts/agents/conversations/storage) | conversation history、service-managed state 與 typed session state 是不同持久機制；應選定清楚 owner 並限制送回模型的歷史 | 不支持同一對話再加第二個可寫 memory owner，也沒有定義 Caliburn 的工作理解欄位 |
| [U.S. OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) | Job analysis 應蒐集工作內容、情境、要求並建立 Task／competency linkage | OPM 沒有規定 LLM memory、OPKS completeness UI 或 Focus runtime |

外部資料共同支持「持久狀態與當輪 Context 分離、長歷史精簡、關鍵語意另行保存、細節按需取回」。把上一輪未回答問題保存為 source-linked unresolved work-understanding item、把 Focus 保持為 runtime bookmark、把欄位缺失留作內部 Skill signal，是 Caliburn 依專業職務分析流程與員工 authority 作出的產品裁決，不宣稱已有外部 benchmark 證明它是唯一最佳作法。

## 9. 後續施工前的驗收情境

1. AI 問一個普通問題，員工連續兩輪回答其他工作；原問題仍在一般待釐清，但不妨礙新資料被吸收。
2. 相同情境跨頁面關閉、process restart 或 conversation compaction 後，原問題仍可由 durable semantic state 恢復，不依賴逐字 prompt。
3. 員工說「剛才那件事其實是主管決定」時，最短近期雙向對話足以解讀；若仍有兩個可能指涉且無法安全繼續，顧問提出一個「需要你的確認」，不由 application classifier 猜。
4. Task 單純沒有 O／P／K／S 時，工作地圖不自動出現四個待釐清；只有真正未知且可回答的工作問題才顯示。
5. AI pending workspace 未變且與本輪無關時，不重讀完整 Diff；模型仍知道哪些範圍未核准。
6. 新員工來源影響一組 pending 時，只讀並修訂相關 review group；無關 pending 保留。
7. Focus 能跨關頁恢復，員工用自然對話改道後可變更，但它沒有 Evidence、不是員工可編輯的工作事實。
8. context-selection receipt 能說明本輪帶了哪些 refs／versions 與為何省略其他內容，但不複製完整原話或 prompt。

## 10. 已確認的 successor 邊界

已確認：

- 員工可見的待釐清只顯示具體、可回答、會影響工作理解或 JD 的問題；缺 O／P／K／S 只作內部訊號，除非轉成真正問題；
- Focus 不進工作理解本體，是可恢復、無 Evidence、不可由員工直接編輯的 runtime attention bookmark；
- 完整來源、工作理解、目前 JD／workspace、核准基線與待審狀態是不同 authority／projection，不以對話摘要互相取代；
- 上一輪仍未回答、而且仍具產品意義的事項要更新到工作理解，再由工作理解整理出要問員工或要回答員工的問題；原顧問問句只留在 conversation history；
- 不保存或重播上一輪完整 prompt，不建立獨立 `PendingQuestion` authority；員工提供新訊息時先正常吸收，不因沒有照上一題回答而丟資料；
- 產品對 blocking clarification 的名稱使用「需要你的確認」；每一題必須引用 1～N 筆相關工作理解，不要求 Task、Duty、branch、quote 或 Skill ID；
- 即使衝突只在員工當前回合才第一次出現，也先在同一顧問結果建立一筆「矛盾／待釐清」工作理解，再以同輪 local handle 引用；application 在同一 deterministic transition 中把 handle 解析為 stable ID，因此不需要允許 0 筆理解引用。

以下原待複核項目已由 owner 於 2026-08-28 確認並寫入 ADR 0071：

- 跨輪 Context 固定採「本輪原話＋最短近期雙向對話＋相關工作理解／unresolved＋Focus＋current workspace orientation＋compact review provenance＋按需細節」；
- 現行獨立 `GapItem` 如何遷入同一工作理解 collection，以及舊 checkpoint 的 hard-cut／migration 邊界；
- 沒有可引用員工原句的資料缺口，不要求為了湊來源而附 quote、Skill 或 method／coverage 標籤；只保存「目前不知道什麼、為何值得釐清」及必要的相關理解 reference；
- ordinary follow-up 與 underlying unresolved item 的 stable reference，以及 required clarification 回答後必須重回一般顧問分析、確實修訂工作理解的 transition；
- 「需要你的確認」採本輪 safe-boundary pause 的具體 state／command／generated-contract 名稱；第一版固定一次只顯示一題最高優先、真正 blocking 的確認；
- 等待「需要你的確認」期間，以確認卡取代一般 composer，中央 JD 暫時唯讀；仍可閱讀、展開與查看差異，但不能直接編輯、Undo 或接受／拒絕。員工回答並完成下一輪 analysis 後解鎖，避免 required input 尚未解決時又產生新的 authority delta。
- review lifecycle 只保留 pending／accept／reject／stale 語意；Reject 不要求理由但保留最小防重提 fingerprint，相關理解或邊界實質改變後可再提出；
- 員工直接修改 JD 不鑄 source／quote；它是下一輪 delta signal，只有員工在一般聊天確認後才改工作理解；
- 待審 JD 只引用 1～N 筆工作理解與短理由；核准後理由消失，實際 Skill 使用由 execution receipt 而非模型 `skill_ids` 證明。

## 11. 第二輪紅隊複核：工作理解如何產生回覆與問題

### 11.1 目標流程

```text
員工本輪訊息／直接 JD 編輯摘要
  → 同一顧問 run 吸收新事實、更正、矛盾與未知
  → 更新 source-linked 工作理解
  → 以最新工作理解檢查目前 JD 與相關待審範圍
  → 形成員工可見回答與可能的 AI 文件編輯
  → 若仍有最高價值未知，再提出一個主要追問
  → 若缺少只能由員工裁決且當下不能安全繼續的資訊，才建立「需要你的確認」 interrupt
```

這個順序表示 JD 必須使用本輪形成的語意理解，不表示該理解必須先成功持久化成 Semantic Memory。**一次員工可見的產品 run 不等於只能有一次 model call**；同一 Context 與同一份已驗證理解可以形成 Memory mutation、JD changes、reply 與 optional follow-up 等並列 effects，各自驗證。只有後續步驟真的需要重新讀取已發布的 Memory head，才等待該 Tool result。Owner 於 2026-09-04 以 [`MEM-Q005`](../current-decisions.md) 取代本段原本過度寬泛的 canonical-understanding hard gate；完整依據與失敗行為見 [`2026-09-04-memory-persistence-and-jd-effect-reconciliation.md`](./2026-09-04-memory-persistence-and-jd-effect-reconciliation.md)。模型 call 數與 framework steps 仍不固定，也不建立 `should_edit_jd` 預分類。

員工當輪若在問問題，顧問不能只顧著產生下一題：能回答時先回答；答案需要關鍵事實但目前沒有時，清楚說明限制；只有無法安全繼續時才進「需要你的確認」。普通追問最多保留一個主要問題，其他未知留在工作理解，避免把訪談變成問卷清單。

員工直接編輯 JD 的 delta 是下一輪必讀的**變更訊號**，不是自動成立的工作來源，也不直接改工作理解。若它只是在改文件表達，理解可不變；若它新增工作事實或和目前理解衝突，顧問在一般聊天中詢問，員工回答才形成新的 source 並修訂理解。員工詢問 UI／流程或一般說明時，顧問正常回答，但不把這種產品問題污染進工作理解；只有與員工實際工作有關、仍未解決的語意才進 collection。

### 11.1.1 員工來源優先不等於「最新訊息覆蓋舊訊息」

員工原話是工作事實的最高來源，意思是 AI 推論、摘要、工作理解或 JD 都不能凌駕員工證據；但員工訊息彼此之間不採 last-write-wins。較新的說法可能是明確更正，也可能是不小心說錯、描述另一個期間／情境，或只是 AI 先前理解錯誤。

顧問依下列順序處理：

1. 若新舊說法其實可同時成立，例如例行與例外、不同期間或不同責任範圍，修訂成帶條件的多筆理解，不製造假衝突。
2. 若員工在一般對話中明確表示「剛才說錯了，是……才對」，以這份新 employee source 修訂目前理解；舊原話仍保持 immutable，舊 understanding version 標成已被取代，不改寫 source lineage。
3. 若兩種說法不能同時成立但無法判斷哪個正確，不依時間、模型信心或 JD 現況自動選邊；保存 `contradicted／unresolved` 理解，停止受影響的 JD 推導，安全的其他分支仍可繼續。
4. 能稍後自然追問時留在一般待釐清；不回答就只能猜且會改壞理解或 JD 時，才投影成一題「需要你的確認」。員工回答後以新 source 修訂理解，再恢復相依分析。

因此「員工原話優先」的精確含義是 **source over inference**，不是 **newest source wins**。application 不建立自動 correction classifier，也不替 LLM 判斷哪句員工原話應失效。

### 11.2 工作理解內的語意狀態

| 語意狀態 | 保存內容 | 來源要求 | 對員工的投影 |
| --- | --- | --- | --- |
| 目前成立 | 對實際工作已成立的細緻理解 | 必須連到員工 source；需要時有 exact quote／lineage | 主要供 LLM 長期 Context 與 JD 分析；可選的進階唯讀檢視 |
| 待釐清 | 具體、可回答、會影響理解或 JD 的未知 | 有直接相關原話才連來源；純資料缺口可沒有 source／quote，也不強制附 Skill 或 method／coverage 標籤 | 一般待釐清；可由 routing 選成下一題 |
| 矛盾 | 兩個目前無法同時成立的理解 | 連到相衝突員工來源；若由 JD direct edit 觸發，只把 edit delta 當衝突訊號，待員工對話確認後才成為工作來源 | 可延後；不能安全繼續時升為「需要你的確認」 |
| 已修訂／被取代 | 新理解與被取代理解的關係 | 保留新舊來源與 revision lineage | 預設不打擾員工，進階查看可追溯 |
| 未定位線索 | 有來源但還不適合變成 Duty／Task／OPKS 的工作內容 | 必須連到來源 | 背景保留；需要時再深化 |

`缺 O／P／K／S`、coverage score 或 validator warning 不是上述語意狀態。它們先是 deterministic／Skill signal；只有能改寫成真正需要員工回答的工作問題時，才新增或修訂一筆待釐清理解。

#### 員工可見的漸進揭露

- 工作理解首先是給 LLM 使用的 durable semantic state，不是第一版必做的員工主畫面。員工主要看目前 JD、AI 差異、目前訪談重點、訪談概況、待釐清與「需要你的確認」。
- 只有在不增加第二份 authority、不影響核心交付、且可以從同一份 server state 廉價投影時，才可增加「AI 目前的理解」進階唯讀檢視。它預設收合，不是新的編輯器、審核流程或 acceptance gate。
- 若後續加入檢視，可依「目前理解／待釐清／有不同說法／已更新」分組；未定位線索與來源 lineage 仍預設按需或進階查看。員工只用一般聊天補充或更正，不直接改寫工作理解。
- 訪談概況是從工作理解狀態、內部 coverage／depth、目前 JD 與待審變更 deterministic 推導的投影，不另存進度 authority，也不顯示模型自評的假精準百分比。
- Focus 的產品名稱是「目前訪談重點」；它只指向當下優先理解的問題或範圍，不等於某個 Task，也不是工作理解本體。

### 11.3 問題不是第二份 authority

- 一般追問是 unresolved／contradicted understanding 的**當輪措辭投影**；同一未知可以依情境換句話問。
- 模型結果應以 stable understanding reference 指出「這題在解哪個未知」，不能只留自由文字 `answer_target`。
- 顧問訊息保存實際問句；理解 item 保存問題意義。為避免重複，可在訊息 metadata 留該 reference，不另建可寫 question queue。
- 員工沒有回答時，understanding 狀態不變；員工回答其他內容時，新內容仍正常進入分析。
- 員工的訊息若實際解決較早的未知，即使不是回答上一句，顧問也可根據來源把它標為已解決。
- 「需要你的確認」是 runtime interrupt／UI projection，不是另一份職務知識。員工回答後要回到一般顧問 run，先更新工作理解，再解除受影響分支。

### 11.4 現行實作的具體落差

1. `UnderstandingItem`、`GapItem`、`NextQuestion` 目前是三套分離 shape；這與「待釐清是工作理解的一種狀態」不一致。
2. `NextQuestion.answer_target` 是自由文字，沒有穩定連到 underlying understanding；問題超出近期 Context 後可能只剩訊息文字。
3. `context.py` 目前偏向最近顧問結果，尚不是 token-bounded 的員工＋顧問雙向近期對話；「剛才／那件事」的指涉仍可能缺上下文。
4. required clarification 已能 durable interrupt，但回答後必須明確經過工作理解更新，不能只清掉 interrupt 就算完成。
5. 現行 `AnalysisBasis` 對所有分析效果同時要求 employee source 與 Skill，對「已知事實」尚可理解，對回覆、追問、Focus、進度與「因尚未提供資料而產生的未知」則過度約束；應只讓已成立工作主張使用 factual evidence，執行時載入過哪些 Skills 留在 tracing／receipt，不升格為每筆產品語意的必填來源。
6. 舊研究採「同一 model call 同時更新理解、問題、JD 與回覆」是成本優先假設，尚無繁中職務訪談證據證明它能穩定維持「先更新理解、再依理解改 JD」的因果。OpenAI／Anthropic／LangGraph 的官方模式反而要求：只要中間結果會改變下一個模型判斷，就應讓下一步取得該結果。Owner 已裁決採有界 Tool-feedback loop；窄幅真模型 proof 只驗證正確性、calls、tokens、latency 與停止上限，不再把較少 calls 本身當成效果較好，也不重開一個固定一 call／兩 stage 的產品二選一。

上述 1、2、4、5 會改動 Accepted ADR 0060 所定的 semantic-state 邊界，不能直接在實作中偷換。應另開 successor ADR，明確說明取代範圍、fresh-state／checkpoint 策略與 generated contract 影響。

### 11.5 成熟框架與 Caliburn 薄政策

不需要再引入一套 memory framework：

- LangGraph typed state＋Postgres Saver 已能承接 thread 內 durable understanding、routing reference、interrupt 與 resume；
- LangGraph Store 已能承接逐字來源與 lineage；
- LangChain middleware 已能在每次 model call 選取近期訊息與相關 state；
- Structured Output 能保證結果符合 schema；deterministic verifier 仍須檢查 source、stable ref、revision、authority 與文件 invariant；
- provider conversation／prompt cache 可作 transport／成本優化，但不能成為產品記憶或權威。

[LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 也把「在 hot path 更新 memory」與背景更新列為取捨：hot path 可讓同一互動立刻使用更新後記憶，但增加 latency 與單次 multitasking；背景更新不阻塞回答，卻可能在下一輪前仍 stale。Caliburn 下一輪必須依最新工作理解分析 JD，因此第一版選 hot path，是產品一致性與成本的裁決，不冒充所有大廠的唯一做法。

[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 支持把 model effect 約束成 schema，但 schema adherence 不等於內容正確；[OpenAI 最新模型指引](https://developers.openai.com/api/docs/guides/latest-model) 建議 prompt 精簡、同一規則只陳述一次，並明確規定何種重要歧義需要提問；[Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 則支持最小高訊號 Context、structured notes、compaction 與按需讀取。這些做法共同支持本設計的 framework shape，沒有任何一份外部文件直接發明或驗證 Caliburn 的工作理解 schema。

### 11.6 已排除的過度設計／過時路線

- 不以完整 prompt replay 模擬記憶；先前 tokens 仍有成本，舊推論也會污染新狀態。
- 不新增 `PendingQuestionStore`、第二個 Gap database、Mem0／LangMem／provider conversation authority。
- 不為每一個缺欄位建立員工待辦，也不把所有問題變成 blocking form／interrupt。
- 不保存 chain-of-thought；只保存來源、結論、未解語意、決策與必要 execution receipt。
- 不預設多 Agent，也不為了看起來 agentic 而增加自由迴圈；但若工作理解的驗證結果會改變 JD 判斷，允許在同一個 LangGraph product run 內使用兩個有明確邊界的 model stage。Anthropic 也提醒 long-running harness 的 scaffolding 會累積成本與過時假設，應在模型能力提升時持續刪除不再必要的機制。[Anthropic — Harness design for long-running applications](https://www.anthropic.com/engineering/harness-design-long-running-apps)

### 11.7 下一份 ADR 必須裁決的最小集合

1. 工作理解 collection 是成立事實、待釐清、矛盾、修訂與未定位線索的單一 semantic owner；一般待釐清由它投影，不保留獨立可寫 Gap authority。
2. ordinary follow-up 必須 reference underlying understanding item；實際問句留 conversation history。
3. 純資料缺口可沒有 employee source／quote，也不強制保存 method／coverage provenance；任何已成立工作事實仍必須有員工來源，Skill 使用情況只留在 execution tracing／receipt。
   Owner 於 2026-08-28 再確認：移除 provider／workspace Evidence 中由 LLM 逐筆填寫的 `skill_ids`。實際載入的 Skills 由 framework receipt 自動記錄；verifier 驗證 allowlist、實際載入 receipt、員工來源、quote 與 domain invariant。若特定文件操作有明確方法前提，由 application 依操作種類與 receipt 做 deterministic 檢查，不接受模型自報作證明。
4. required clarification 必須引用 1～N 筆 underlying understanding；本輪才發現的衝突先建立同輪 understanding effect 再引用。回答後重回正常 analysis transition；interrupt 自身不是理解。
5. 對員工仍是一個顧問 product run；內部 model stage 數量尚待 §14 的窄幅比較裁決。不得再用 `run` 同時指產品回合與 provider call。
6. fresh-root 產品不維護第二套舊 Gap／question compatibility writer；若既有開發 checkpoint 不相容，依 hard-cut runbook 重建。

## 12. 「需要你的確認」的引用與 durable pause 邊界

### 12.1 為什麼當前回合的新衝突也不需要 0 筆引用

「需要你的確認」不是一個漂浮的表單，而是某筆工作理解目前無法安全判定時的 UI／runtime projection。因此它的語意 target 永遠存在：

| 觸發情況 | 同一顧問結果先做什麼 | 確認卡引用什麼 |
| --- | --- | --- |
| 員工本輪說法與既有理解衝突 | 修訂既有理解為 `contradicted`，保留本輪 source | 該既有理解的 stable ID |
| 員工同一則訊息內有兩種互斥解讀 | 新增一筆 unresolved／contradicted understanding，連到本輪 source | 同輪 local handle；落盤時解析成 stable ID |
| 目前根本沒有足夠資料 | 新增一筆描述「不知道什麼、為何會影響分析」的 unresolved understanding | 該同輪 local handle；這筆理解可沒有 employee source，但確認卡仍不是 0 reference |
| 員工直接改 JD，與目前理解不一致 | 先把 JD delta 保存為衝突訊號，建立待確認理解；不把 edit 自動當員工工作事實 | 該理解 reference；員工回答後才形成新 source |
| UI 使用、匯出或一般產品問題 | 正常回答，不寫入工作理解 | 不建立「需要你的確認」 |

需要分開兩種 reference：

- **工作理解 reference**：說明這個確認正在解決哪個語意問題；「需要你的確認」固定 1～N 筆。
- **來源 reference**：保存在工作理解本身，用來追溯員工說過什麼；純資料缺口可以沒有來源，員工本輪說法造成的衝突則應連本輪 source。

確認卡不再重複填 quote、Skill ID、Task、Duty 或 branch。問題與選項是顧問對相關理解的當輪措辭，不是新的 factual evidence；員工送出的答案才成為新的 immutable employee source。

同樣的 provenance 原則適用於 AI 的語意 JD 編輯：待審變更以 1～N 筆工作理解說明「根據哪些目前理解作出這項改動」，另由模型填一段簡短的人類可讀原因；員工接受後不把這段理由永久塞進核准 JD。員工直接修改 JD 是 authority edit，不必在編輯當下捏造工作理解 reference，下一輪再由顧問比對 JD delta 與工作理解。

### 12.2 選單何時出現

不採兩個極端：

- **不在單次模型生成／Tool loop 的半途中直接開 UI**：那時工作理解、同輪 local handle 與可安全保留的結果可能尚未 durable commit，resume 也容易重跑 interrupt 前的 side effect。
- **不等整場訪談或所有分析結束才詢問**：相依理解與 JD 可能已在錯誤假設上繼續展開。

建議採「**本輪分析的安全停點**」：

```text
員工訊息
  → 本輪模型分析
  → 吸收所有可安全成立的工作理解與無關結果
  → 對衝突／未知建立 understanding effect
  → 不產生依賴該歧義的 JD 變更
  → deterministic transition 驗證、解析 local handle 並 durable commit
  → 專用 wait_for_required_input node 呼叫 LangGraph interrupt
  → UI 顯示「需要你的確認」
  → 員工選擇或自行輸入；答案保存為一般員工訊息／source
  → resume 後啟動下一次模型推理，更新工作理解並完成相依分析
```

所以它既不是「分析到一半讓同一個模型暫停思考」，也不是「本輪所有事情都做完才隨口問下一題」；它是**目前這次模型回合結束、產品狀態已安全保存，但同一個語意工作尚在等待員工輸入**。員工可以關閉頁面，下次回來仍看到同一題。回答後必須有一次新的模型推理，因為模型要讀取新的人類資訊；這個額外呼叫只在真正 blocking 的歧義出現時發生。

[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) 明確說明 interrupt 會透過 checkpointer 保存狀態並等待 `Command(resume=...)`，且 resume 時 node 會從頭執行，因此 interrupt 前的 side effect 必須 idempotent；把等待拆成沒有前置副作用的專用 node，正是為了遵守這個 framework 邊界。[OpenAI 最新模型指引](https://developers.openai.com/api/docs/guides/latest-model) 也建議明確規定何種重要歧義應提問，以及哪些動作需要核准；它支持「重大歧義才問」的 policy，但沒有替 Caliburn 定義工作理解 schema。

### 12.3 普通問題與「需要你的確認」的界線

一般聊天問題只是在提高完整度；員工可以先回答別的事，顧問仍能安全繼續。只有同時符合下列條件，才進入「需要你的確認」：

1. 存在至少兩個會導致不同工作理解／JD 的實質解讀，或已有直接衝突；
2. 猜錯會實質改變工作理解或文件，而不只是少一個可選細節；
3. 近期雙向對話、目前工作理解與按需舊來源查找後仍無法解決；
4. 只有員工能裁決；
5. 未取得答案前，相依分析不能安全繼續。

白話判斷：**可以先標成不知道、仍安全繼續，就是一般待釐清；不回答就只能猜，而且猜錯會改壞理解或 JD，才是「需要你的確認」。** 缺 O／P／K／S、普通下一題、AI 差異接受／拒絕、執行錯誤與產品 UI 問題都不自動升級。

### 12.4 第一版 UI contract

- 員工看到的名稱固定為「需要你的確認」；`required_input`／`interrupt` 只作內部 contract／framework 名稱。
- 問題必須清楚寫出「為什麼現在需要確認」，並引用 1～N 筆工作理解；不顯示內部 ID 給員工。
- 有真正互斥且容易理解的答案時提供 2～4 個選項與簡短說明；永遠允許「其他／自行輸入」。若沒有誠實的離散選項，只顯示必填自由文字，不為了做表單硬湊選項。
- 選項只是表達輔助，不是 authority；無論點選或自行輸入，最後都轉成一則員工答案 source，再交給正常顧問分析。
- 確認尚未回答時，聊天輸入區改顯示這張卡；它不是失敗或分析完成狀態，也不提供「稍後處理」。員工可關閉頁面稍後回來，但要回答後才能繼續相依分析。
- 第一版一次只顯示一題最高優先、真正 blocking 的確認；其他未知留在工作理解，回答並完成下一輪分析後再依最新理解決定是否仍需下一題，避免多題互相依賴或提前過時。
- 等待期間中央 JD 暫時唯讀，保留閱讀／展開／查看差異；確認卡是唯一寫入入口。回答完成並結束下一輪 analysis 後再解鎖，與「running 時同文件單一 writer」規則一致。

[Claude Agent SDK 的 user input 文件](https://code.claude.com/docs/en/agent-sdk/user-input) 把一般 conversational turn 與 `AskUserQuestion` 分開，後者用於多個有效方向需由人決定，支援 2～4 個選項及自由輸入。這支持本 UI 的互動形狀，但 Caliburn 不照搬 Claude 的 schema：Task／Duty／branch／Skill 不是通用必填欄位，真正的 semantic target 是工作理解。[LangChain Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) 也提供 `respond` 類型的人類回覆 primitive；Caliburn 已由 LangGraph interrupt 承接 durable wait，不再新增第二套 approval／question framework。

### 12.5 Context 與成本限制

回答後的新模型回合不重播上一輪完整 prompt。它讀取本輪答案、最短近期雙向對話、被引用的工作理解、必要的 current-workspace orientation，以及按需舊來源。OpenAI 的 [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) 說明每次請求仍需由應用提供 conversation／previous response 等狀態；[Anthropic 的 context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 與 [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 都支持最小高訊號 context、structured notes／semantic memory 與按需 retrieval，而不是無限制重播整段歷史。

這些官方資料支持 durable pause、結構化詢問與最小 Context 的工程 primitive；「每題必須指向工作理解」「哪些歧義才阻塞」仍是 Caliburn 依員工 authority 與職務分析語意作出的產品決策，不宣稱是外部框架自帶答案。

## 13. 2026-08-28 技術新鮮度與框架替代稽核

### 13.1 後端版本

| 套件 | repo pin | 2026-08-28 最新 stable | 判斷 |
| --- | ---: | ---: | --- |
| LangGraph | 1.2.11 | 1.2.11 | 已在最新 stable；保留 typed state、interrupt、Saver／Store |
| `langgraph-checkpoint-postgres` | 3.1.2 | 3.1.2 | 已在最新 stable；不自寫 checkpointer |
| FastAPI | 0.141.1 | 0.141.1 | 已在最新 stable |
| Pydantic | 2.13.4 | 2.13.4 | 已在最新 stable；繼續作 application／wire validation |
| LangChain | 1.3.15 | 1.3.17 | 落後兩個 patch；先過 Deep Agents／middleware／structured-output canary 再升級 |
| Deep Agents | 0.7.5 | 0.7.9 | 落後四個 patch；先 characterise StoreBackend／filesystem verbs／summarization 相容性 |
| `langchain-openrouter` | 0.2.7 | 0.2.8 | 落後一個 patch；先驗 model binding、usage／cache receipt 與 strict structured output |

版本來源直接使用各專案 PyPI release metadata：[LangChain](https://pypi.org/project/langchain/) · [LangGraph](https://pypi.org/project/langgraph/) · [Postgres Checkpointer](https://pypi.org/project/langgraph-checkpoint-postgres/) · [Deep Agents](https://pypi.org/project/deepagents/) · [LangChain OpenRouter](https://pypi.org/project/langchain-openrouter/) · [FastAPI](https://pypi.org/project/fastapi/) · [Pydantic](https://pypi.org/project/pydantic/)。

結論不是「看到 patch 就直接更新」。LangChain 1.3.5 曾因第一方 Deep Agents summarization 相容性回歸而被撤回；這正好說明 agent stack 必須以鎖版＋compatibility canary 升級，而不是把 latest 當品質證明。[LangChain PyPI release history](https://pypi.org/project/langchain/#history)

### 13.2 Web primitives

現行 Next 16／React 19／Tailwind 4／TanStack Query 5／Base UI 已是現代 stack。Base UI 官方在 2026-08-04 發布 1.7.0，包含 bundle、performance、accessibility 與 ScrollArea 修正；repo range 仍是 `^1.4.1`、lock 實際為 1.6.0，應在 UI Task 的 compatibility gate 升到 1.7.x。[Base UI Releases](https://base-ui.com/react/overview/releases)

大型 nested JD 的 dirty state、validation 與 autosave 使用 TanStack Form v1；server cache／mutation serialization 使用既有 TanStack Query；三欄拖曳寬度使用 shadcn Resizable／`react-resizable-panels`。這些框架只承接 form、cache、focus、popover、scroll 與 panel primitives；Duty／Task／OPKS ownership、semantic diff、atomic review 與 authority 仍由 server 投影，Web 不重算。[TanStack Form](https://tanstack.com/form/latest/docs/framework/react/guides/basic-concepts) · [TanStack Query Mutation Scopes](https://tanstack.com/query/latest/docs/framework/react/guides/mutations#mutation-scopes) · [shadcn Resizable](https://ui.shadcn.com/docs/components/base/resizable)

### 13.3 是否還缺成熟框架

本輪已找到與「工作理解 collection 增修刪」目的相近的 [LangMem](https://langchain-ai.github.io/langmem/)／[Trustcall](https://github.com/hinthornw/trustcall)，但查到相近能力不等於已證明適合成為 production authority：

- LangMem 提供 stateless／Store-backed memory manager、Pydantic schema，以及 create／update／delete memory Tool；官方也把它定位成 LangGraph Store 的長期記憶工具。[LangMem memory API](https://langchain-ai.github.io/langmem/reference/memory/) · [LangMem tools API](https://langchain-ai.github.io/langmem/reference/tools/)
- Trustcall 用 JSON Patch 修訂既有結構化物件，目標是降低整份 JSON 重寫造成的遺失與 token 成本；LangMem 目前也直接依賴 Trustcall。[Trustcall repository](https://github.com/hinthornw/trustcall) · [LangMem `pyproject.toml`](https://github.com/langchain-ai/langmem/blob/main/pyproject.toml)
- 截至 2026-08-28，LangMem 最新 PyPI 版本仍是 `0.0.30`、PyPI 列一位 maintainer、GitHub Releases 沒有正式 release；Trustcall 最新 PyPI 版本仍是 `0.0.39`。這些是成熟度風險訊號，不代表功能錯誤，也不足以單獨判定可用或不可用。[LangMem PyPI](https://pypi.org/project/langmem/) · [LangMem GitHub Releases](https://github.com/langchain-ai/langmem/releases) · [Trustcall PyPI](https://pypi.org/project/trustcall/)
- LangMem 的通用 memory Tool 會直接對 `BaseStore` 做單筆 create／update／delete；它沒有直接替 Caliburn 證明 employee source／exact quote、understanding version lineage、同批原子提交、JD review basis 或「不增加固定第二次模型呼叫」。因此不能只換名稱就宣布完整替代。

後續完整機制稽核已在 [§14.9](#149-可推翻的框架機制稽核2026-08-28) 更新這項早期建議：目前沒有真實產品缺口足以支持額外 LangMem／Trustcall canary，因此本切片正式不引入。production 使用 LangGraph checkpoint／Tool loop、Pydantic typed effects 與最薄的 Caliburn domain reducer；只有可重現 transcript 顯示 reconcile 品質、成本或維護性失敗時，才由 successor ADR 以該案例重開候選比較。這仍是 framework-first：通用 persistence、Tool 與 typed state 交給框架，沒有成熟 primitive 能決定的 source／revision／lineage／authority 才留在 domain policy。

除這項受限候選外，目前沒有找到需要再引入的新 workflow、proposal、document 或 Evidence owner：

- LangGraph Saver／Store 已覆蓋 durable state、memory、interrupt／resume 與 recovery；
- Deep Agents StoreBackend／filesystem middleware 已覆蓋共用 JD workspace 與低階編輯；
- LangChain middleware／Structured Output 已覆蓋 Context selection hook 與 typed effects；
- Base UI、TanStack Form／Query、Resizable Panels 已覆蓋通用 Web interaction。

仍需由產品定義的不是「因為沒找框架」，而是框架無法知道的產品語意：工作理解狀態、Task／Duty／OPKS Skills、來源資格與 quote resolution、JD invariant、semantic grouping、拒絕防重提 fingerprint、員工 authority transaction 與產品 copy。框架若能承接其中的資料修訂／持久化／Tool 機制就應替代該機制，但不能連產品語意一起偷換；也不得只因名稱相似就同時保留兩套 owner。

## 14. 四項施工前缺口的補充研究（2026-08-28）

本節只把外部資料能支持的工程模式，轉譯成 Caliburn 的候選設計；外部來源沒有替本產品定義工作理解 schema、訪談完成門檻或 JD 審核政策。以下必須區分：

- **來源直接支持**：框架能力、API／review 的版本保護模式、職務分析應涵蓋的內容、進度元件適用條件；
- **Caliburn 待裁決**：要用幾個 model stage、什麼算「目前足夠」、哪個理解變更使哪組待審內容失效。

### 14.1 一個產品 run 是否應固定只呼叫模型一次

官方資料不支持「calls 越少就一定越主流或效果越好」：

- [OpenAI GPT-5.6 Model guidance](https://developers.openai.com/api/docs/guides/latest-model) 把 Programmatic Tool Calling 限定在**中間步驟不需要新的模型判斷**的 bounded processing；若每個結果可能改變下一個模型決定、動作需要核准，應使用 direct tool feedback。它也要求以代表性工作比較成功率、完整性、Evidence、tokens、latency 與 cost，只有品質門檻仍通過時，較少 calls 才算改進。
- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 把 Tool calling 定義成模型選擇 Tool、application 執行、把 `function_call_output` 回傳模型、再由模型產生 final response 或更多 Tool call 的多步對話；預設由模型決定零、一或多個 Tool。這支持「一個產品 run、動態但有界的內部 model steps」，不支持把 call 數寫成產品 invariant。
- [Anthropic Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) 把 prompt chaining 定義為「下一個 LLM call 處理上一個輸出」，適合能清楚拆成可驗證子工作的任務；代價是 latency，收益是每一步較簡單、通常較準確。
- [LangGraph Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents) 提供同一個 graph run 內的 prompt-chain 範式；[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api#edges) 另提供 conditional edge／`Command`，可依 validated current state 動態結束或進入文件工作；[LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 則明說 hot-path memory 能讓更新立即供後續互動使用，但會增加 latency 與模型 multitasking 風險。
- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 與 [OPM Job Analysis Methodology](https://piv.opm.gov/policy-data-oversight/hiring-information/competitive-hiring/deo_handbook.pdf#page=229) 要求先蒐集、記錄、分析工作的 content／context／requirements，再依資料與 SME input 列出 Task、連結 competencies。它們定義了可用 JD 內容必須有何種工作支持，但沒有定義「每則訪談訊息後都應改文件」或單一完成分數。

因此要比較的是三個真實選項，而不是「一次 run／兩次 run」二選一：

| 選項 | 形狀 | 優點 | 主要限制 |
| --- | --- | --- | --- |
| A. 單一 compound model call | 同一 Structured Output 同時給 understanding effects 與 JD edits | 最低 provider round-trip；Context 只組一次 | schema 能驗欄位，不能證明 JD 真正依 validated post-understanding state 推導 |
| B. 同一 product run 的固定兩 stage chain | stage 1 產生 understanding plan → deterministic gate／post-state → stage 2 只讀驗證後狀態做 JD／reply | 因果邊界清楚、可分別 debug；完全由 LangGraph 原生 node／checkpoint 承接 | 多一次 model step；需以較小第二階段 Context、prompt cache 與恢復避免成本接近倍增 |
| C. 有界自適應 consultant loop | 顧問按需提交 understanding effect；若 JD 依賴本輪新理解，application 先驗證／提交並回傳 canonical revision，模型收到 Tool result 後才讀 JD／編輯；若只依賴既有 validated understanding，則可直接使用 JD Tool | 保留「同輪新理解先驗證」因果，又不把每回合綁死成兩 call；不需要 `should_edit_jd` 預分類 | 必須以 Tool precondition、最大文件 pass／repair 次數限制迴圈，否則會變成開放式 agent |
| D. 開放式 model↔tool loop | 模型可自由反覆呼叫理解／JD tools直到自認完成 | 最靈活、最接近通用 coding agent | calls、延遲與修復路徑不固定；本產品目的較窄，第一版容易增加成本與除錯面 |

**已確認、不因拓撲改變的產品 invariant**：每個與員工實際工作有關的回合都必須重新理解／校正 Work Understanding；「每次處理」不等於每次都建立新 version，資訊沒有實質改變時可以是 no-op。JD 不得繞過已驗證理解直接從本輪原話產生，也不得因單一欄位看似缺漏就自動改文件。

**Owner 於 2026-08-28 裁決採 C，並移除獨立的 `should_edit_jd`／「是否值得進行 JD 分析」分類**。是否需要改 JD 只有在顧問比較 validated Work Understanding、目前 JD 與相關 pending workspace 後才知道；預先再分類一次會重複同一語意判斷，也可能在尚未讀取 JD 時漏判。讀取／比較 JD 本身不需要 publication gate；模型實際產生 JD Tool call 才表示要操作文件，沒有 Tool call 就是 no-op。真正保留的門檻只有：

1. **同輪理解因果門檻**：任何引用本輪新建／修訂理解的 JD Tool call，必須發生在 application 驗證並提交該理解、回傳 canonical stable ID／revision 之後；若本輪沒有新工作事實，且文件工作只引用既有 validated understanding，則不強迫額外 understanding round-trip。
2. **待審發布門檻**：具體 bounded JD change 必須通過理解 basis、blocking ambiguity、dependency closure、schema、read-set 與 document invariant，才可成為員工可見的待審變更。
3. **整體訪談充分性**：只服務進度與訪談規劃，不是每筆文件變更的前置 gate。

這裡的 deterministic validation 只證明 source／quote、schema、stable reference、revision 與 domain invariant 有效；它不把模型理解變成不可推翻的客觀真理。工作理解仍可由後續員工對話修訂。

**目前工作裁決（2026-08-28，可由新證據推翻）**：採局部充分性，不採整份職務／整個工作範圍完成後才開始寫 JD。只要某一個 source-linked 工作理解已足以形成一項具體、可獨立或可原子成組審核的文件變更，且該局部沒有 blocking ambiguity，就可分析並發布這一局部的待審 JD；同一工作範圍的其他未知繼續留在待釐清。阻塞只封鎖受影響 group，不連帶封鎖無關範圍。後續新理解可修訂尚未核准的 workspace，也可再提出已核准 JD 的新變更。若窄幅真模型／browser transcript 顯示此做法造成大量無意義 churn、review fatigue 或頻繁 stale，應重新比較延後或批次發布，而不是把本裁決視為永久規則。

因此正式方向是：對員工仍是一個 product run、同一位顧問、不是多 Agent；模型依當輪需要動態結束、提出普通追問／required input、提交工作理解 Tool，或在取得必要的 canonical understanding 後按需載入 JD Skill／slice 並編輯 workspace。它是**有界 Tool loop，不是固定 Stage 1／Stage 2 pipeline**。同輪新理解會影響文件決定時，外部驗證結果必須回到模型，因此至少有一次 Tool round-trip；沒有這條依賴的回合不因產品 invariant 被強迫成兩次 model call。verifier repair 仍設小上限。

施工前仍只做很窄的 Luna Max proof，不建正式 eval 平台：至少覆蓋「無新理解／無文件影響」、「同輪新理解產生局部 JD 變更」、「更正理解使既有 pending 失效」三種固定情境，觀察理解正確性、JD 因果一致性、deterministic rejection、總 tokens、latency、calls 與停止上限。這是在校準 C 的實作，不是再以單一 happy path 重選架構；若結果出現大量無效文件 pass、成本失控或漏改，再用證據重開。

### 14.2 同輪因果驗證是否真的需要

[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 保證輸出符合指定 JSON Schema，不保證主張為真，也不保證欄位 B 是在欄位 A 經 application 驗證後才推導。現行 `u1／u2` local ref 只能提供 **referential integrity**：JD basis 指到本輪確實存在的理解 effect；它不是 **semantic causality** 的證明。

若採選項 A，application 最多能檢查：

1. local ref 存在且可轉成 stable ID；
2. source／quote、狀態、JD invariant 與 read-set 都有效；
3. JD reason 引用了至少一筆理解。

它不能 deterministic 判斷模型是否真的「先修訂理解再分析 JD」。因此若這條因果是產品硬需求，單 call 的 same-result verifier 不足。

在已裁決的 C 中，LangGraph 的 Tool／`Command` state update 直接建立該因果：[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api#command) 支援 Tool 更新 state 並動態 route，[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 會在 graph step 保存 checkpoint，[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api) 則要求離散 task 可 checkpoint、可恢復且 side effect idempotent。依賴同輪理解的流程是：

```text
model step
  → call understanding Tool
  → application deterministic 驗證並原子提交 understanding
  → Tool result 回傳 canonical understanding ID／revision
  → 同一 product run 的 model continuation 按需讀 JD／Skill
  → no-op、詢問，或呼叫 JD edit Tool
  → application deterministic 驗證 JD edits／review basis
  → 原子發布待審 semantic group
```

Tool result 與 graph state 可由 LangGraph checkpoint 保存，crash 後從 understanding 已提交的安全邊界續跑文件 reconciliation，不必重做成功的理解步驟；不得在 model call 期間長開資料庫 transaction。若文件工作失敗，canonical Work Understanding 與 JD 是否同時可見，仍有兩種產品選擇：

- **原子 publication**：understanding Tool 只保存 validated plan，最後才一起發布理解與 JD；一致性最強。
- **分段 publication**：先發布理解，JD 失敗時只顯示文件整理失敗；恢復與重用較直接。

外部框架支持兩種 durability 形狀，沒有替 Caliburn 決定可見性。**Owner 於 2026-08-28 裁決採分段 publication**：Work Understanding 通過 deterministic gate 後即原子更新；後續文件 Tool 讀取這份真正的 current understanding。文件工作成功才原子發布待審 JD diff；若失敗，Work Understanding 保留、JD 不留下半套變更，UI 解鎖並誠實顯示「理解已更新，文件整理失敗」，只重試文件 reconciliation。required input 同樣先保存安全理解再 interrupt。每個 Tool／transition 內仍 fail closed；「分段」不等於容許半筆理解或半組 JD action。

### 14.3 訪談進度以什麼為單位、何時叫「目前足夠」

權威職務分析資料能定義**應觀察什麼**，不能替單一產品給出固定完成百分比：

- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 將 job analysis 定義為系統性理解 Tasks、所需 competencies 及兩者連結；其現行頁面仍連到六步 checklist 與 DEOH。
- [OPM Job Analysis FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/what-is-a-job-analysis/) 要求收集、記錄、分析工作 content、context、requirements，並建立 tasks 與 KSAs／competencies 的清楚關係。
- [EEOC Uniform Guidelines Q&A，問題 77](https://www.eeoc.gov/es/node/130157) 明確指出不必描述所有 Task，但應涵蓋所有重要 work behaviors、相對重要性／難度、可觀察 work products 以及相關 Tasks。這支持「代表性重要工作覆蓋」，不支持以已找到 Task 數量當完整度。
- [O*NET Content Model](https://www.onetcenter.org/content.html) 把 Tasks、work activities、work context、knowledge 與 skills 放在分層內容模型中，支持跨 JD 欄位的工作範圍視角。

大型設計系統同樣反對對不確定流程顯示假精確進度：[Apple HIG](https://developer.apple.com/design/human-interface-guidelines/progress-indicators) 只在 duration／總量可知時使用 determinate progress；[IBM Carbon Progress indicator](https://carbondesignsystem.com/components/progress-indicator/usage/) 明確說步驟可任意順序或會隨條件變動時不要用線性 progress indicator；[GOV.UK Complete multiple tasks](https://design-system.service.gov.uk/patterns/complete-multiple-tasks/) 建議狀態種類從最少開始，且 task list 是使用者要完成的 actions，不是拿來展示答案。

**後續研究修正（以 §15.11–§15.13 為準）**：本節較早把「可修訂工作範圍＋原子 collection」寫成已核准，現已被後續討論取代。Owner 暫定接受的是一份含具體案例、穩定工作模式與待釐清／矛盾的完整語意 collection，並由這份 collection 投影導航與進度；第一版不另建 stable、可寫的 `WorkScope`。未定位線索仍可留在待釐清／未歸屬投影，不能為 UI 強塞到 Duty／Task／OPKS。

仍已排除以百分比、已找到 Task 數、對話回合數或 Duty／OPKS 完成數宣稱訪談完成。全域只應呈現可解釋的離散狀態；員工仍可停止、關頁、繼續訪談或依既有規則匯出，新重要工作出現時 coverage 可重開。§15.14 已收斂第一版 rubric：只用「待補充／目前足夠」兩個常態 label，其他 Focus、一般待釐清、required input、未定位與待審數分開呈現；這是 Caliburn 產品決策，外部標準只提供應觀察的工作面向，不替產品定義完成門檻。

### 14.4 待審內容如何判斷理解 basis 已失效

成熟系統共同採用「審核／修改綁定精確基線，而不是把舊決定套到新內容」：

- [RFC 9110 `If-Match`](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) 要求 state-changing request 的 entity tag 必須匹配 current representation，否則不得執行，用來避免 lost update。
- [Google Cloud IAM etag guidance](https://docs.cloud.google.com/iam/docs/allow-policies#using_etags_in_a_policy) 在 read-modify-write 時攜帶 exact etag；版本不符回 conflict，重新讀取後再解決業務衝突。
- [Kubernetes API concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/#updates-to-existing-resources) 用 `resourceVersion` 拒絕 stale update，client 必須處理 409／重試。
- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) 把 approval 綁在當時 diff state；reviewable diff 改變時可撤銷 stale approval。GitHub review comment API 也把 comment 綁定 `commit_id／original_commit_id`，後續修改可能讓它變 outdated。
- [VS Code Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits) 讓使用者逐項 Keep／Undo AI edits；審核的是目前實際 edit，而不是一段脫離版本的 AI 理由。

因此第一版不需要 embedding、文字相似度或全文件 invalidation。每個可獨立審核的 atomic group 保存：

1. exact current／approved document baseline digest 與 semantic path read-set；
2. 1～N 筆 `(understanding_id, version_id)`；
3. group digest、dependency closure 與建立 revision。

Accept／Reject 前由 server 重讀：目標 path、dependency 或任何**被引用的**理解 version 不符，就 fail closed 並把該 group 標 stale；不相關理解更新不影響它。員工改綠色 after-state 時重算 group digest，但狀態仍是 pending，舊 accept command 失效。理解 revision 應只在其 meaning／status／relations／source basis 實質改變時建立，因此第一版採 exact version 即可，不再發明「語意差不多就沿用」的 fuzzy rebase。

stale 不代表內容永遠錯，只代表舊審核基線已不存在：舊 group 不可接受，下一次顧問 run 依最新理解 revalidate、supersede 或撤回；approved JD 完全不動。這個依賴範圍規則比「工作理解任何地方一變，全文件待審都失效」更接近 ETag／diff review 的精確基線原則，也符合成本與員工體驗。

### 14.5 對目前 Proposed ADR／計畫的直接影響

Owner 已裁決 runtime 拓撲；下列影響必須同步進 ADR／計畫，其他仍未完成的產品細節不因此自動獲准施工：

1. ADR 0071 §9 與 implementation plan 必須拆清楚 `product run／model step／tool call`；不能再推論成固定單 call 或固定兩 stage。
2. 不建立 `should_edit_jd`／「是否值得分析 JD」state。讀取與比較不是 authority action；實際 JD Tool call 是操作決定。若它引用同輪理解，basis 必須是 understanding Tool 已提交並回傳的 stable ID／revision；只引用既有 canonical understanding 時不強迫額外 round-trip。
3. 現行 `WorkUnderstandingItem` 沒有可表示案例／模式／待釐清之間的 typed 關係；Task 7 的五個 flat counts 不能取代由這些關係重建的 orientation／coverage projection。
4. `understanding_basis_digest` 必須落在每個 atomic review group，並有 exact version mismatch 的 stale transition／409 測試；不能只當 workspace manifest 的全域 metadata。
5. 正式施工前只需三個固定情境的窄 Luna Max proof，不建立正式 eval 平台；但也不能用單一 happy-path smoke 宣稱有界 Tool loop 的品質、成本與停止行為都已驗證。

### 14.6 「已驗證工作理解」的邊界與失敗責任

Owner 於 2026-08-28 確認：工作理解通過機器驗證後，可以自動成為 **AI 目前的理解**；它不是員工核准事實，也不是不可推翻的客觀真理。只有真正無法由現有來源、近期對話與目前理解安全判定的工作語意，才詢問員工。技術錯誤不得包裝成訪談問題丟給員工。

這項裁決需要先拆開外部資料能保證的事情：

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 能約束輸出符合 JSON Schema，提供可靠的型別與 refusal 處理，但官方明確提醒 structured output 內容仍可能出錯；若模型被要求對不相容輸入硬填 schema，甚至可能為了滿足欄位而捏造內容。schema adherence 不是工作事實驗證。
- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 的標準迴圈是模型提出 Tool call、application 執行、把 Tool result 回給模型，再由模型決定 final response 或下一個 Tool；官方也建議把 application 已知的參數由程式補入，不要讓模型重填。這支持「deterministic gate 後給同一顧問一次受限修復」，不支持另開一個自由 agent。
- [LangGraph Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph) 把錯誤責任明確分成 transient error 由系統 retry、LLM-recoverable error 回到模型、user-fixable error 才 `interrupt()`、unexpected error 交開發者。這正是本產品需要的 failure routing；不必自行建立第二套 orchestration framework。
- [Anthropic Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) 建議 Tool 只回高訊號資料、錯誤訊息要具體且可修復，並以嚴格資料模型與 poka-yoke 讓錯誤參數難以產生；[Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) 則提醒 agentic complexity 會交換 latency／cost，應從最簡單可組合流程開始。
- [OPM Job Analysis](https://www.opm.gov/agency-services/talent-management-services/assessment-and-evaluation/hiring-assessments/) 把 job analysis 定義成以 occupational information、subject-matter expertise 與嚴謹方法識別工作 Tasks／competencies。Application 可以驗證來源與結構，卻不能取代實際從事工作的員工判定語意真相。

因此第一版採四層責任，而不是一個名稱含糊的 `verifier`：

| 層 | 能證明什麼 | 不能證明什麼 | Owner |
| --- | --- | --- | --- |
| Provider／schema gate | strict wire 可解析、required／enum／型別／`additionalProperties` 合法 | 員工是否真的這樣工作、quote 是否支持推論 | LangChain structured output＋Pydantic |
| Deterministic application gate | runtime source 存在、quote 是 immutable source 中唯一可定位的 exact text、stable reference／revision／lineage／狀態轉換與 domain invariant 合法 | 哪個互斥說法才是真、員工話語的真正意圖 | Caliburn application |
| Semantic reconciliation | 根據本輪訊息、最短近期對話、current understanding 與按需舊來源，判斷成立、待釐清、矛盾、修訂或 no-op | 在來源仍歧義時自行宣告真相 | 同一位顧問模型 |
| Employee authority | 裁決只有員工知道的 blocking ambiguity；Accept／Reject AI 的 JD 變更 | 修正 JSON、quote offset、stale revision 或 provider timeout | 員工 |

本文後續若寫 `validated Work Understanding`，精確含義固定為：**已通過 schema、來源、引用、版本與 domain invariant 的 current AI interpretation**。它沒有 `employee_confirmed=true` 的隱含意義；後續 employee turn 仍可建立新版本、標示矛盾或取代舊理解。

#### 14.6.1 Deterministic gate 要驗什麼

1. model wire 先由 strict schema／Pydantic 解析；未知欄位、非法 enum、錯誤 shape 不進 domain transition；
2. current turn 的 source identity 由 runtime 注入、不進模型 schema；模型只選逐字 `quote`，只有低頻舊來源 recall 才從已讀取結果選 model-safe handle；stable source UUID、understanding UUID、version、revision、digest 與 quote start／end 都由 application 指派或解析；
3. quote 不 trim、不 Unicode normalize、不 fuzzy match；application 要求唯一匹配，若同一句在 source 出現多次就回 typed diagnostic 要模型擴大 quote，不要求 occurrence ordinal；
4. Case 必須有 employee source；Pattern 必須有 direct source 或 `supported_by` Case；純資料缺口的 Unresolved 可沒有 source，因為「尚未知道」本來就沒有原話；
5. REVISE／RETIRE target、semantic references、source basis 與 lineage 必須存在且仍是 current；expected revision 由 application 從當次 runtime state 注入／驗證，不讓模型重填；
6. 同一 Tool call 的 effects 在一個 transaction 內全數通過才 commit，不能留下半筆理解；若模型誤呼叫但沒有實質 effect，executor 可回 `no_change` receipt，但它是 application 產生的結果，不是每輪要求模型提交的欄位；
7. deterministic gate 不用第二個模型判斷 quote 是否「語意上支持」理解，也不做模型自評信心分數。這類判斷由同一顧問整理；互斥且不能安全判定時建立／修訂 Unresolved，必要時詢問員工。

#### 14.6.2 失敗分流與成本上限

| Failure class | 例子 | 第一版處理 | 不得做的事 |
| --- | --- | --- | --- |
| `transient` | rate limit、timeout、暫時網路／provider 5xx | LangGraph node `RetryPolicy` 做小上限 exponential backoff；與語意 repair budget 分開 | 顯示「需要你的確認」或要求員工重填 |
| `provider_output` | refusal、incomplete response、strict parse failure | adapter 產生 typed failure；若有可操作 schema diagnostic，併入本 stage 唯一一次 model repair | 無限重送完整 Context |
| `repairable_tool_error` | quote 不存在、source handle／local ref 錯、非法狀態轉換、stale revision、相同 rejected change 未改 basis 又重提 | 回最多五筆短、具體、帶 code／path／expected rule 的 Tool diagnostic；同一 authority stage 整個 product run 最多一次 validation-driven model continuation | 問員工技術問題、回巨大 raw schema／traceback、靜默改變模型語意 |
| `semantic_ambiguity` | 員工兩種說法互斥、代名詞有多個實質解讀、缺少只有員工知道的責任邊界 | 能安全繼續就保存一般待釐清；不回答就只能猜且會改壞理解／JD，才建立 source-linked understanding 並進「需要你的確認」 | 把普通 OPKS coverage 缺口或 verifier error 升級成 blocking interrupt |
| `unexpected` | invariant bug、資料損壞、未知例外 | transaction rollback；保留先前已提交的安全 state，JD 不留半套；run terminal、UI 解鎖、員工可重新傳訊息，技術細節只留 trace／log | 吞錯、假裝成功、把 traceback 顯示成訪談問題 |

「最多一次 model repair」指本 authority stage 因 validator rejection 觸發的額外模型 continuation；正常的 understanding Tool result → JD reconciliation 不算錯誤 repair。第二次仍失敗就終止該 stage，不提交這次無效 effects，也不再讓模型自我循環。transport retry 由 framework policy 另計，不能藉此重置 model repair budget。

required input 也不是 deterministic validator 的一種錯誤回傳。validator 只說規則哪裡不成立；模型根據職務語意決定是否能改正、保存未知或提出 required input。這保留清楚責任：程式不假裝理解工作，模型不負責 UUID／offset，員工不替系統除錯。

#### 14.6.3 對 ADR／施工計畫的約束

1. ADR 與 code comment 必須定義 `validated` 的有限語意，避免實作者把 current understanding 誤做成員工已核准 knowledge base；
2. understanding Tool result 可有 `committed／no_change／repairable_error` 的 typed shape；`no_change` 只處理已發生的空操作，不構成每輪呼叫 Tool 的要求；terminal／unexpected failure 走 graph error path，不偽裝 Tool 成功；
3. application 已知的 source UUID、stable ID、version、revision、digest 與 quote offset 不出現在 model-authored contract；
4. Task 2 必須先以測試證明錯誤分流、一次 repair 上限、transaction rollback 與「deterministic error 永不 interrupt 員工」，再接 JD Tool；
5. 第一版不加 critic model、semantic guardrail model、confidence threshold、fuzzy quote matcher或第二套 validation framework。若日後真 transcript 顯示同一顧問無法可靠辨識語意支持，再以實際失敗情境重開，而不是現在預先增加成本。

### 14.7 工作理解 collection、工作範圍與 generic memory 候選

> **歷史候選，已由 §15.11–§15.13 取代**：本節保留當時為何需要 collection 與導航的診斷，但「另有 stable identity 的可寫工作範圍」不是目前可施工結論。Owner 已暫定接受由穩定工作模式承載語意，工作範圍／進度只作可重建 projection。

Owner 於 2026-08-28 核准以下**概念層**方向；coverage rubric 後續已由 §15.14 收斂，精確 record boundary 與關聯／修訂規則仍需下一輪逐項討論，不得由實作者自行補完。

#### 14.7.1 為什麼不是一份大摘要，也不是平面自由文字清單

[LangGraph Memory overview](https://docs.langchain.com/oss/python/concepts/memory) 區分兩種 semantic memory 形狀：單一 profile 容易讀取，但隨內容增長，更新整份文件較容易遺失既有資訊；collection 可獨立新增、修訂與淘汰細項，召回較高，但需要明確的關聯與 retrieval policy。[Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 同樣建議維護 structured notes、按需載入最小高訊號 Context，而不是每輪重播全部歷史。

Caliburn 的工作理解同時需要表示多件工作、尚未定位線索、矛盾、後續更正及來源 lineage，因此採 collection；但只用平面 `kind + text` 又無法回答「這是哪一塊實際工作、目前談到哪裡」。正式概念形狀是：

```text
可修訂工作範圍（stable identity；不是 JD Duty／Task）
  ├─ 1..N 原子工作理解
  ├─ 0..N 待釐清／矛盾理解
  └─ derived coverage projection（精確 rubric 待定）

未定位理解
  └─ 在資訊足夠前不強迫歸入任何工作範圍
```

「工作範圍」只代表員工實際工作的一塊，服務理解整理、Context selection、訪談導航與進度投影。它不等於 Duty，不要求先有 Task，也不阻止 O／P／K／S 線索先出現。工作範圍可改名、重組或被取代，而 employee source 與已核准 JD 的 identity 不因此被改寫。

[OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 與 [OPM FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/what-is-a-job-analysis/) 要求系統性收集、記錄與分析工作 content、context、requirements，以及 Tasks 與 competencies 的關係；[O*NET Content Model](https://www.onetcenter.org/content.html) 則把 Tasks、work activities、work context、knowledge、skills 與 abilities分成相關但不同的 domain。這些來源支持「多面向理解＋關聯」，不支持把訪談內部記憶直接塑形成單一路徑的 Duty → Task → OPKS。

#### 14.7.2 框架替代範圍

本次不是保留舊元件名稱後只把資料庫換成框架。目標是：成熟框架若能完成同一目的，就替代理解 collection 的通用機制；Caliburn 只留下職務語意與 authority 規則。

| 能力 | 優先候選 | 裁決 |
| --- | --- | --- |
| durable thread state、safe resume、history | [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | production 使用；不自建 workflow database |
| typed semantic collection | LangGraph typed state＋Pydantic | production 基線；Work Understanding 由 thread checkpoint 擁有，不搬到 Store、不得雙寫 |
| 既有記憶的新增、修訂、淘汰 | [LangMem memory manager](https://langchain-ai.github.io/langmem/reference/memory/) | 本輪不採用；只有真實 reconcile 失敗案例才由 successor 重開比較 |
| patch 既有複雜 schema、避免整份重寫 | [Trustcall](https://github.com/hinthornw/trustcall) | 本輪不採用；不為框架覆蓋率增加 JSON Patch／第二 model layer |
| source／quote、職務 facets、scope 語意、版本失效與 JD basis | 無通用框架可直接定義 | Caliburn domain policy＋deterministic gate |

#### 14.7.3 若真實缺口觸發 successor，候選必須通過的門檻

本輪不執行 canary。未來只有可重現 transcript 證明現行 reconcile 在品質、成本或維護性上失敗，才可另開 successor；比較只能用該固定失敗案例與現行主模型 adapter，不能先把整個產品改成 LangMem 後再看結果。候選至少必須證明：

1. 可用自訂 Pydantic schema 表達 1..N 筆既有理解，並區分 insert／update／retire，不靠整份 profile 重寫；
2. 能先取得 proposed effects，或以可攔截 adapter 保證 deterministic gate 通過前不直接發布 production memory；
3. 能保留 application 指派的 stable ID、版本 lineage、source／quote basis，不讓模型重算 UUID／offset；
4. 同批任一 effect 失敗時可以零寫入，或交由 Caliburn transaction 一次提交；不能因多個 generic Tool call 留下半套理解；
5. 不建立第二個固定 memory-model call。若只能用額外 manager call，必須以固定 transcript 比較理解品質、tokens、latency 與 call 數，證明效果收益值得成本後才重開；
6. API 與依賴版本必須與 repo 鎖定的 LangChain／LangGraph 相容，並有 characterization test 防止 pre-1.0 行為漂移。

任一核心條件不成立，就記錄 exact gap 並停止引入；不為了宣稱「有用框架」而包多層 adapter 模擬缺失能力。現行 production 使用 LangGraph＋Pydantic，Caliburn 只實作一個可測、原子、版本化的薄 reducer。若未來候選全部成立，successor ADR 必須明確寫出被替代的舊機制並保持單一 owner，不能兩套並存。

#### 14.7.4 下一輪未決問題

1. 原子理解需要哪些最小 typed facets，避免重新變成自由文字 `kind`？
2. 一筆理解只能有一個主要工作範圍，還是能關聯多個範圍？
3. 工作範圍改名、合併、拆分、淘汰時，哪個 identity／lineage 必須保留？
4. Coverage 的三個面向與離散狀態，哪些由 deterministic projection 得出、哪些需要模型語意判斷？

Work Understanding owner 已在 §14.9 收斂為 LangGraph thread checkpoint；Store 只保存 immutable sources、current JD workspace 與按需大物件。這不再是未決問題。

#### 14.7.5 Claude／Codex 可借用的機制與不能照抄的邊界

Owner 補充要求把 Claude／Codex 納入研究。兩者是 coding／general work agent，不是職務分析產品；本節只採官方可驗證的機制，不能把 filesystem、Git 或 coding memory 名稱直接移植成 Caliburn domain。

| 官方做法 | 可學習的原則 | Caliburn 不照抄的部分 |
| --- | --- | --- |
| [Codex Memories](https://learn.chatgpt.com/docs/customization/memories) 明確要求強制團隊規則放 `AGENTS.md`／checked-in docs，memory 只是 helpful recall；本機 memory 另存 summaries、durable entries、recent inputs 與 supporting evidence，並在 chat idle 後背景整理 | 區分不可省略的產品規則與模型生成、可修訂的記憶；記憶可以保留摘要、細項與 supporting evidence，不必把完整對話塞回每輪 | 工作理解不是 Codex 個人偏好 memory；Caliburn 仍需 source／quote、版本與職務狀態，且 hot-path 新理解必須可供同輪 JD 使用，不能照搬只在背景更新 |
| [Claude Code Memory](https://code.claude.com/docs/en/memory) 把 `CLAUDE.md`（人寫的規則）與 auto memory（模型累積的 learnings／patterns）分開；只常駐 `MEMORY.md` 前 200 行或 25KB，詳細 topic files 按需讀取 | 以精簡索引／orientation 常駐 Context，詳細工作範圍、來源與舊 lineage 按需載入；員工不直接編輯模型的工作理解，只用對話修正 | `MEMORY.md` 是 markdown recall，不提供 typed collection、transaction、來源資格或 JD review basis；不可拿檔案長度門檻當本產品 schema |
| [Codex Code Review](https://learn.chatgpt.com/docs/code-review) 的 review pane 反映 repository 真實狀態，包含 Codex、使用者及其他未提交變更，並可切換 unstaged／staged／commit／branch／last-turn diff | 「同一份目前工作區＋審核投影」比另建 AI 專用文件更清楚；審核應綁實際 current diff／baseline，而不是只看 AI 自述理由 | JD 不是 Git repository；Accept／Reject、dependency closure 與 approved baseline 必須由 typed authority commands 實作，不能把 staged／commit 名稱搬進 UI |
| [Claude Code Checkpointing](https://code.claude.com/docs/en/checkpointing) 在每個 user prompt 建 checkpoint，可分別恢復 code／conversation，但只追蹤 Claude edit tools 的檔案變更，且官方明說不能取代 Git | AI 編輯應有可復原的工具 receipt／checkpoint；短期 Undo 與長期核准 authority 是兩個不同層次 | 員工直接編輯與其他 application command 也必須被 Caliburn authority 看見，不能沿用「只追蹤模型 Edit Tool」的限制 |
| [Codex Long-running work](https://learn.chatgpt.com/docs/long-running-work) 建議同一相關工作留在同一 chat，以 outcome／constraints／verification 維持連續性；獨立工作才分 chat／worktree | 同一份 JD 的多輪訪談維持一個 durable product thread；Focus／未決問題／下一步需可跨關頁恢復 | 本產品不是 long-running autonomous goal；員工隨時可停止，沒有「不傳訊息也要繼續跑」的隱含行為 |
| [Claude Context Window](https://code.claude.com/docs/en/context-window) 顯示 rules／memory／Skills 有不同載入生命週期，compaction 後根規則與 auto memory 重新注入，path-scoped rules／詳細內容按觸發重載 | Skill 按需載入、穩定規則與可修訂工作理解分層、compaction 後由 durable state 重建最小 Context | 不採 Claude 的固定 per-skill token cap 或 subagent 策略；Caliburn 仍以一位顧問與實際 token／品質證據校準 |

因此 Claude／Codex 進一步支持目前方向：**規則、可修訂理解、原始來源、目前工作區、審核差異與短期執行狀態必須分層，但在產品上保持一個一致工作面**。它們的 memory 可以被檢視，但不是主要操作面；這也不構成 Caliburn 第一版必須建「AI 目前理解」UI 的證據。它們沒有回答「工作理解有哪些 facets」「工作範圍如何關聯」或「何時足夠」；下一輪仍要以 OPM／O*NET 職務分析來源及本產品需求定義，而不是從 coding agent UI 反推。

### 14.8 原子工作理解應承載什麼（第一輪候選；完整語意與 WorkScope 已由 §15.11–§15.13 重開）

本節只收斂「每筆理解應表達哪些語意」；不把未確認欄位寫成實作契約。外部來源能限制錯誤方向，但沒有任何官方 framework 直接提供 Caliburn 的完整 schema。

#### 14.8.1 權威來源共同支持的分層

| 來源 | 可直接支持的事實 | 不能越界推成 |
| --- | --- | --- |
| [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)／[OPM FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/what-is-a-job-analysis/) | 職務分析要系統性收集、記錄與分析工作 **content、context、requirements**，並建立 Tasks 與 competencies／KSAs 的關係 | OPM 沒有定義 AI memory schema，也沒有說每則訪談只能屬於一個責任區域 |
| [O*NET Content Model](https://www.onetcenter.org/content.html)／[O*NET 31.0 Content Model Reference](https://www.onetcenter.org/dictionary/31.0/csv/content_model_reference.html) | Tasks、work activities、work context、knowledge、skills 等是相關但不同的 domain；工作活動另有 general／intermediate／detailed 層次 | 不能把 O*NET occupation taxonomy 直接當單一員工的工作理解或 Current JD |
| [O*NET Task Statement Components](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf) | Task statement 可拆成 action、object、purpose/result、enabler、context；一項敘述可能同時含多個成分 | 這是 Task 撰寫分析，不代表所有 partial clue 都必須先湊成完整 Task |
| [LangChain Memory Overview](https://docs.langchain.com/oss/python/concepts/memory) | semantic memory 可採單一 profile 或持續增修的 document collection；大型 profile 更新容易出錯，collection 通常提高下游 recall | framework 不知道哪些職務 claim 應合併、拆分、成立或淘汰 |
| [W3C PROV-O](https://www.w3.org/TR/prov-o/) | `wasDerivedFrom`、`wasQuotedFrom`、`wasRevisionOf`、invalidation 是成熟的 provenance 概念 | 第一版不需要導入 RDF／ontology；只借用來源、修訂、失效必須可區分的語意 |
| [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)／[Claude Code Memory](https://code.claude.com/docs/en/memory)／[Codex Memories](https://learn.chatgpt.com/docs/customization/memories) | 長流程以 structured notes／durable memory 保存高訊號理解，Context 只帶精簡 orientation 與當下相關細節 | 不能用 markdown note、auto-memory 產生時機或 coding-agent 目錄直接決定產品 authority |

repo 既有職務分析研究另已確立：初期先盤點目的、週期、責任區域、例行、例外與交接；Task 只有在 action／object／meaningful outcome／responsibility 足夠清楚時才成立；Duty 是後續可重組的正式分組，不應拿來當早期理解盒子。這與上述官方分層一致。

#### 14.8.2 因此先排除四種形狀

1. **一份持續整段重寫的巨大「員工摘要」**：容易在更新時遺失既有細節，也難以單筆修訂／淘汰；不採。
2. **每筆只能選一個互斥 `kind`**：一個真實 claim 常同時含行為、條件與責任邊界，強迫單選會丟關係或複製內容；不採舊 `kind + text`。
3. **預先做成 Duty → Task → OPKS 欄位圖**：partial clue 與未定位線索會被迫過早分類，與已確認產品流程衝突；不採。
4. **第一版建立完整 knowledge graph／RDF ontology**：provenance 概念有用，但現在導入通用圖譜會增加查詢、遷移與 UI 成本，沒有證據能提升本產品效果；不採。

#### 14.8.3 待確認的最小候選

> **2026-08-28 更新**：Owner 強調工作理解必須長期保留完整細節，且 Task／Duty／OPKS 只在後續 JD 分析才形成。後續複核發現，下面「一句 claim＋facets」雖容易修訂，卻可能切斷條件、行動、順序、責任與結果的完整關係；因此本候選已被 §15.11 重開，尚不得施工。

第一輪研究曾支持以下**候選**，它不是 production contract：

```text
WorkUnderstandingCollection
  ├─ WorkScope[]                 # 穩定、可修訂的工作範圍；不是 Duty
  │    ├─ stable identity + revision
  │    ├─ label／summary／lifecycle
  │    ├─ 0..N member claim IDs # 關聯可跨範圍；不複製 claim
  │    └─ predecessor scope IDs # 只在 merge／split lineage 使用
  └─ UnderstandingClaim[]        # 可獨立修訂的一項意思

UnderstandingClaim
  ├─ stable identity + revision
  ├─ 一句可獨立判真／修訂的 claim
  ├─ 1..N semantic facets
  │    activity                  # 做什麼／處理什麼
  │    outcome                   # 產出、維持狀態或避免後果
  │    context                   # 觸發、頻率、條件、工具、互動情境
  │    responsibility_boundary   # 負責、決定、核准、交接邊界
  │    capability_signal         # 尚未升格成正式 OPKS 的執行條件線索
  ├─ established／unresolved／contradicted／superseded
  └─ 0..N source／quote references
       # 已成立 factual claim 至少一筆；「尚不知道什麼」可為 0
```

多 facet 不是把一句話塞成大摘要，而是保留同一原子關係。例如「重大修法時立即通知主管」是一項可獨立修訂的 claim，同時具有 `context + activity + responsibility_boundary`；若拆成三筆，反而會失去「什麼條件下做什麼、通知誰」的關係。

Scope membership 放在關聯／`WorkScope.member_claim_ids`，不算 claim 內容。這是目前建議而非既定規則：沒有任何 scope 包含的 claim 就是尚未定位；多個 scope 可共同引用同一筆交接／跨範圍事實。改分類只增加 scope revision，不誤報「員工工作事實改變」。UI、Context retrieval 與 progress projection 必須把跨範圍 item 標成 shared，不得重複計成多份證據。若固定真實 transcript 顯示多範圍造成高 churn 或模型誤連，才退回「一個主要 scope＋可選 related scopes」，不是先複製 item。

這個候選刻意**不含** Duty／Task／OPKS ID、`skill_id`、LLM confidence、完成百分比或員工可編輯欄位。JD linkage 在後續分析 effect；實際載入 Skill 在 execution receipt；progress 是 collection 的 projection；confidence 不能取代 source、矛盾與明示狀態。

#### 14.8.4 下一個 Owner 決策點

先只確認兩件事，再討論 lineage 與 progress：

1. 原子 item 是否採「一句可獨立修訂的 claim＋可多選 facets」，而不是互斥 `kind` 或固定 Task 欄位？
2. Scope membership 是否允許同一 claim 被 `0..N` 個 WorkScope 引用；或第一版應限制成「0..1 個主要 scope」？

確認後才把精確 Pydantic schema 回填 ADR／實作計畫；未確認前不得施工。LangMem／Trustcall 不在本輪施工路徑，只有後續真實失敗證據才能由 successor 重開。

#### 14.8.5 Codex／Claude 對 current state、checkpoint 與 lineage 的補充研究

Owner 要求再查 Codex／Claude，避免只從一般資料模型推論。官方資料的共同形狀如下：

| 官方機制 | 實際行為 | 對 Caliburn 的限制／啟示 |
| --- | --- | --- |
| [Codex Code Review](https://learn.chatgpt.com/docs/code-review) | review pane 反映 **Git repository 的實際目前狀態**，包含 Codex、使用者與其他未提交變更；可看 unstaged／staged／commit／branch／last-turn diff，並按整體、檔案或 hunk stage／revert | 審核投影不能只看「AI 上一輪做了什麼」；Current workspace 才是現在狀態。Caliburn 借用 granular review，不搬 Git staged／commit 名稱 |
| [Codex Memories](https://learn.chatgpt.com/docs/customization/memories) | 必須遵守的規則留在 `AGENTS.md`／checked-in docs；memory 只是 helpful recall，而且可能在 chat idle 後才背景更新 | Work Understanding 是 hot-path product state，不可降級成可能延遲的 Codex auto-memory；但可學習規則、目前理解與細節來源分層 |
| [OpenAI Conversation State](https://developers.openai.com/api/docs/guides/conversation-state) | `previous_response_id` 串成模型對話 lineage，Conversation 保存 items；Context 增長後要 compaction | provider conversation lineage 不能替代 domain revision。Caliburn 要從 checkpoint／Store 重建必要 Context，而不是把 response chain 當 Work Understanding authority |
| [Claude Checkpointing](https://code.claude.com/docs/en/checkpointing) | 每個 user prompt 建 session checkpoint；可單獨恢復 code、conversation 或兩者，但只追蹤 Claude edit tools，官方明說不是永久 version control | runtime Undo／恢復與長期語意 lineage 是兩層；員工直接編輯也必須由 Caliburn current state 看見，不能套用「只追蹤 AI edit」限制 |
| [Claude Sessions](https://code.claude.com/docs/en/sessions)／[How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) | resume 延續同一 session，fork 複製歷史後取得新 session identity；Claude 會讀目前 branch files，而 conversation history 可持續 | 目前 workspace 與 conversation 可以各自演進；需要新 identity 的真正分叉，不能假裝是原 entity 的 rename |
| [Claude Memory](https://code.claude.com/docs/en/memory) | 精簡 `MEMORY.md` index 常駐、topic details 按需讀取，並標示修改時間 | WorkScope 可作低成本 orientation，Claim／source details 按需載入；`modified` 只能提示新鮮度，不能取代 semantic revision／source lineage |

這些 coding agents 都沒有直接提供「工作範圍 merge／split」domain schema，但共同否定兩種做法：不能把 conversation／checkpoint 當永久語意真相，也不能只看 AI last-turn diff 而忽略員工造成的目前狀態。

因此研究後的推薦收斂為：

1. LangGraph checkpoint 保存可恢復的**目前 collection 與 runtime history**；不另建 Event Store。
2. Claim 內容與 Scope membership 分離：移動／重新分組只改 scope revision，claim identity／revision／source 不變。
3. Scope rename 保留 identity、增加 revision；merge／split 建立新 identity，記最小 predecessor lineage，舊 scope 進 `superseded`。
4. 待審 JD 只綁它實際讀過的 claim／scope revision；無關 scope 改名或未讀 claim 不使整份 review stale。
5. 來源 Store、conversation、runtime checkpoint、目前工作理解與待審 JD basis 各有不同用途，不互相假裝替代。

這仍是待 Owner 核准的資料語意；Codex／Claude 只提高方案的可信度，沒有把 coding 行為升格成職務分析標準。

### 14.9 可推翻的框架機制稽核（2026-08-28）

Owner 再次確認：本文討論過的方案、現行 code、Accepted ADR 的技術選型與已完成的 framework mapping 都只是可檢驗候選；若新資料顯示有更好的產品效果，可以另開 successor ADR 推翻。不能因為已經寫完就保留，也不能因為某個套件的功能名稱相似就採用。比較順序固定為：

1. 能否更準確、穩定地形成並修訂工作理解；
2. 能否讓所有 JD 變更保持可審核、可拒絕、可恢復，且不繞過員工 authority；
3. 能否在多輪訪談中可靠記住相關內容，又只載入必要 Context；
4. 失敗、重跑與跨關頁恢復是否一致；
5. 模型 calls／tokens／latency、產品複雜度與維護成本。

「已採用」「同一家族」或「較少程式碼」都不能單獨勝出。

本節強制把兩條證據鏈分開，後續 ADR、計畫與 review 不得混用：

- **產品方法證據**：Claude／Codex 等成熟產品只用來研究 agent loop、共同工作面、實際 diff 審核、Tool feedback、checkpoint／Undo、Context 分層與按需載入等方法。它們是 coding agent，因此只能證明一種可借鑑的互動／執行形狀，不能替 Caliburn 定義 Work Understanding、Duty／Task／OPKS、來源資格或員工 authority。
- **框架能力證據**：LangGraph、Deep Agents、Pydantic AI／Harness、DBOS 等官方文件用來判斷 persistence、transaction、VFS、interrupt、structured output、Tool 與 recovery 的實際能力和限制。框架名稱不自帶產品方法；只有能承接已確認目的且整體效果／可靠性／成本最佳的 primitive 才採用。

因此不得從「參考 Codex／Claude」推導必須選某家公司或 coding framework，也不得從「已選 LangGraph」反推產品必須長成 graph／checkpoint UI。正確順序是：先從產品研究確定要達成的行為，再獨立比較哪組框架 primitive 最適合實現；若沒有成熟 primitive，才留下最薄的 Caliburn domain policy。

#### 14.9.1 先更正一個已過時的 Pydantic AI 前提

[ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) 當時檢查的 Pydantic AI Harness Planning 0.13.0 缺少本產品所需的 stable identity、subtask dependency 與 durable store。最新版官方 [Pydantic AI Harness Planning](https://pydantic.dev/docs/ai/harness/planning/) 已經不同：

- granular operation 使用 stable task ID；
- 可選 subtasks、dependency、cycle rejection 與 `blocked`；
- 內建 in-memory、SQLite、PostgreSQL 與 Redis store；
- 可跨 runs 共用 plan、發出 events，並以 cache-safe tail reminder 讓每次 model request 取得最新 plan。

所以「Planning 沒有 stable ID／dependency／persistence」**已不是有效淘汰理由**。Accepted ADR 不能事後改寫，但任何 successor 都不得再引用這項舊事實。

這不等於應立刻把 runtime 換成 Pydantic AI。Planning 實際提供的是模型擁有的工作清單：`content／active_form／pending|in_progress|completed|cancelled`，開啟 subtasks 後再加 `blocked／parent／depends_on`。它很接近本產品的**訪談 agenda／下一步工作**，卻不是 employee source、工作理解、矛盾、來源 lineage、Current JD 或 review authority。它現在是應正式評估的 agenda 候選，不是 Work Understanding 的同義詞。

同一輪也核對了其他最新版 Harness 能力：

| Harness／Pydantic 機制 | 官方實際行為 | 對 Caliburn 的判斷 |
| --- | --- | --- |
| [Memory](https://pydantic.dev/docs/ai/harness/memory/) | 模型可寫的 Markdown notebook；有 bounded injection、search、optimistic concurrency 與 idempotency | 官方明說沒有 source citation／verified provenance，CAS 只防 lost update、不證明內容為真；不能作 Work Understanding authority |
| [Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/) | append-only run events、continuable message snapshots、tool-effect ledger 與 run lineage | 官方明說不是完整 graph-state checkpoint，不恢復 capability state、workspace snapshot、graph node、retry counter，也不自動去重 side effect；不能直接替代本產品 durable semantic state |
| [FileSystem](https://pydantic.dev/docs/ai/harness/filesystem/) | root-scoped 本機檔案 read／write／edit／list／search，含 path containment、protected patterns、hash CAS | 安全 Tool 很完整，但 storage 固定為 host filesystem，沒有 application-defined PostgreSQL backend；直接採用會把目前 JD 搬離本機 Web 產品的單一 database authority，或要求自寫 mirror，不優於現有 Store-backed VFS |
| [Deferred Tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/) | Tool 可 inline resolve，或結束 run 後由 UI 收集 approve／deny／external result，再以 message history 開新 run | 適合高風險 Tool approval／外部結果；Caliburn 的 JD review 是多筆、可跨輪的 semantic diff，不應被降成逐 Tool call approval，但 required input 的 pause/resume 形狀可借用 |
| [DBOS durability](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/) | model／MCP 可成 durable steps；DBOS workflow／queue 可恢復，datasource transaction 可把 application mutation 與 step outcome 原子記錄 | 是完整的替代 runtime 候選；但一般 function tools 不會自動包成 durable step，workflow 必須 deterministic，business authority 也要搬到 datasource aggregate 才取得真正 transaction 優勢 |

Pydantic AI V2＋Harness＋DBOS 因此不是「不成熟玩具」，而是可信的**整套替代架構**；但它不是可把 Memory 或 Planning 單顆塞進現行 LangGraph state 的免費升級。若採用，應讓 DBOS 成為唯一 durable runtime、重寫單一 PostgreSQL authority，並移除 LangGraph checkpointer／Store ownership，而不是三套疊加。

#### 14.9.2 逐項目的成熟機制比較

| 產品目的 | LangChain／LangGraph 現行機制 | 最新 Pydantic 候選 | 其他成熟候選 | 研究裁決 |
| --- | --- | --- | --- | --- |
| thread-scoped current Work Understanding、required input、Focus 與恢復 | typed State＋Postgres checkpointer；checkpoint 是 super-step snapshot，`update_state` 建新 checkpoint，interrupt 可跨關頁 resume | Pydantic Graph 需另配 durable engine；Harness StepPersistence 明確不是 graph checkpoint；DBOS 需把 semantic state 另建 datasource aggregate | Letta 自帶 stateful agent server；Mem0／Graphiti 偏跨 session retrieval | **LangGraph checkpoint 目前最貼合**；Work Understanding 留在 thread checkpoint，不搬 Store |
| immutable employee source 與按需逐字引用 | application-scoped Postgres Store namespace，state 只存 refs | Harness Memory 沒 provenance；需另建 custom store／schema | [Graphiti](https://help.getzep.com/graphiti/getting-started/overview) 有 episode provenance／temporal fact invalidation，但需 graph DB、embedding 與 ingestion LLM | **維持 Store source owner**；Graphiti 留給未來真的接 RAG／跨文件 temporal retrieval 時重評 |
| Work Understanding insert／revise／supersede | provider-native／Tool structured effects＋Pydantic＋checkpoint reducer | Harness Memory 是 Markdown；Planning 是 task list；都不承載 factual provenance | LangMem core manager／Trustcall、Mem0、Graphiti | **不用 LangMem／Trustcall 作預設 canary**：官方行為已顯示會增加 memory model call或 JSON-patch layer，仍不提供 source／revision／batch transaction／JD basis；先用現有主顧問產生 typed effects＋薄 reducer。只有真實 transcript 顯示 reconcile 品質失敗時才重開固定案例比較 |
| 訪談 agenda／返回點／目前工作 | typed checkpoint `interview_work`／Focus bookmark，語意由 Caliburn schema 定義 | 最新 Harness Planning 已有 stable ID、dependency、blocked、Postgres store、events 與 cache-safe reminder | Microsoft Agent Framework Harness／workflow planning | **Pydantic Planning 成為正式替代候選**；但需先確認 agenda 是否真的需要獨立可寫 state。若 agenda 可完全由 Work Understanding／未決問題投影，就不再建立第二個 plan owner |
| AI 與員工共用目前 JD workspace | Deep Agents `StoreBackend` 在 PostgreSQL Store 提供 VFS，review 由 approved ↔ current derived | Harness FileSystem 的 CAS／sandbox 很好，但只操作 host filesystem | Git／Codex／Claude workspace 是產品類比，不是 Web JD store | **現行 Store-backed VFS 較合適**；不為換框架建立 filesystem mirror |
| employee Accept／Reject 與 semantic review | current workspace＋approved baseline＋derived atomic group；application command 決策 | Deferred Tool approval 是逐 call 且 client-submitted approval 不是 server authorization boundary | coding review UI／Camunda user task 可供 UX 與 lifecycle 參考 | **保留文件層 derived review**；不能用 generic HITL Tool approval直接代替 |
| durable execution 與跨 Store／Saver failure | LangGraph checkpoint＋idempotent task；Store／Saver 不是單一 ACID transaction，以 approved-first receipt／recovery 收斂 | DBOS datasource 可提供更強的 same-transaction outcome tracking；但要整套搬 authority 並包 function Tool I/O | Temporal／Restate 亦可，但對本機單操作者更重 | **DBOS 是唯一值得整套翻案的主要技術理由**，不是局部套件；只有現行 recovery seam 在產品情境造成錯誤、不可維護或多 worker 需求時才重開 vertical conformance |
| Skills、Tool 按需載入、Context／cache | LangChain middleware、Deep Agents Skills、dynamic prompt、VFS 按需 read；已在 current stack 實作 | Harness Skills、Tool Search、Compaction、Planning reminder 的能力更模組化，且對 prompt cache 有明確設計 | Claude／Codex 也採 progressive disclosure | **Pydantic 目前在 capability ergonomics 上更強**，但這一項不足以抵消 durable state＋DB VFS 的整套遷移；可借其 cache-safe tail reminder 原則改善現行 Context |

其他 memory framework 也沒有直接勝出：

- [Graphiti](https://help.getzep.com/graphiti/getting-started/overview) 能建立具時間與來源的 knowledge graph、保留 episode provenance 並失效舊 fact，功能很完整；但 current 產品只有單一員工、單一文件 thread，且已明確暫不接 RAG。現在加入 Neo4j／FalkorDB／Neptune、embedding 與 ingestion model，成本大於產品效果。
- [Mem0](https://docs.mem0.ai/platform/features/graph-memory) 最新路線偏 retrieval memory；新 graph algorithm 採 single-pass ADD-only extraction，而不是 application-controlled current revision／atomic JD basis。它可以記住偏好或長期 facts，不能直接成為本產品可修訂工作理解的 authority。
- Letta 的 persistent memory blocks／stateful-agent server適合 agent 自我維護 free-text memory；它會再引入一個長期 state owner，也沒有本產品的 source、revision 與 employee document review seam。

這些結論不是「框架都不行，所以自己寫」。框架已接手 model loop、typed state、checkpoint、Store、VFS、interrupt、Skills、structured output 與 provider binding；Caliburn 只留下成熟框架無法替產品決定的最小語意：一筆理解何時成立／修訂／矛盾、它引用哪個 immutable employee source、哪些理解版本真的支撐某組 JD change，以及員工何時取得 authority。

#### 14.9.3 一次產品 run 內，Work Understanding 與 JD 的最佳時序

> **已被後續裁決取代**：本節「每個工作 turn 固定先呼叫 understanding Tool」是較早推薦。Owner 已接受 §15.4 與 §15.20 的成本感知版本：只有 canonical Tool result 會影響本輪後續 JD 決定才 continuation；普通理解更新與可見文字不固定增加 model call。

現行 code 有一個需修正的因果邊界：[run service](../../apps/api/app/consultant/run_service.py) 先讓 LangChain／Deep Agents agent 在同一 loop 直接編輯 Store-backed `/workspace`，agent final structured output 才交回理解／Gap／Focus effects；[interview reducer](../../apps/api/app/consultant/interview.py) 之後才把 verified understanding 寫進 checkpoint。這表示同輪 JD edit 可能早於它所依賴的新理解取得 canonical stable ID／revision。若新 review 必須引用 exact Work Understanding revision，不能只在事後補 metadata 假裝因果成立。

四個方案比較如下：

| 方案 | 優點 | 真實缺點 | 裁決 |
| --- | --- | --- | --- |
| 一次 final structured output 同時交 understanding＋JD | call 最少、transaction shape 表面簡單 | 模型看不到 deterministic understanding result；任一引用錯誤使整包失敗；又會退回龐大 wire schema，失去已驗證的持久 VFS 編輯能力 | 淘汰 |
| 每回合固定兩個獨立模型 calls：理解器 → JD writer | 邊界清楚、第二個模型只讀 canonical understanding | 即使不需改 JD 也可能付第二次成本；兩位／兩次模型容易出現語氣與判斷漂移；重新引入固定 pipeline | 不作預設 |
| 同一顧問的 bounded Tool-feedback loop：先提交 understanding effects，收到 canonical receipt 後才按需開放 JD mutation | 保持一位顧問與同一 Context；只有真的需要才進文件 Tool；deterministic result 可修復；符合 OpenAI／LangChain 的 model → Tool result → continuation 標準迴圈 | 有新理解時至少多一個 model step；Tool／checkpoint 必須冪等，並限制 repair／iteration | **目前推薦** |
| 整套改成 Pydantic AI＋DBOS＋新 relational authority | 可讓 understanding transaction 與 workflow outcome 原子記錄；Pydantic capabilities／cache ergonomics 更完整 | 要重寫整個 durable state、workspace backend、review command 與 API；FileSystem／Memory 仍不能直接承接 DB workspace／provenance，function Tool durability仍需 glue | 保留為 successor 候選，不在沒有產品硬缺口時直接重寫 |

本節當時推薦「每個工作 turn 固定呼叫 understanding Tool」；該細節已被 §15.20 取代，不再保留一組容易被誤抄的歷史施工步驟。仍有效的只有三條架構理由：employee turn 先 immutable 保存、同輪新理解若要支撐 JD 必須先取得 canonical Tool result，以及整個流程是一個有界 product run 而非固定兩個 Agent。

最新流程見 §15.21.11：模型只在確有 semantic changes 時呼叫 Work Understanding atomic Tool；沒有變更就正常回覆，不發 `no_change` Tool call。Tool 成功後，只有後續 JD／required-input 判斷需要 canonical result 才 continuation。模型成本以實際 requests／tokens／cache usage 記錄，不把 step 數寫成產品 invariant。

#### 14.9.4 本輪暫定裁決與必須回填的文件

在「不保護既有 code」的前提下，本輪仍推薦 **LangChain／LangGraph＋Deep Agents Store-backed VFS**，理由不是已完成，而是它目前唯一同時滿足：

- thread-scoped typed semantic checkpoint／interrupt／history；
- PostgreSQL-backed、AI 與員工共用的 current JD VFS；
- immutable source Store 與按需 Context；
- 已實測的 restart、direct edit、review、export 與 recovery seam。

Pydantic AI V2＋Harness＋DBOS 已升格為真正的整套 challenger；若後續窄實作證明現行 Store／Saver recovery 或 bounded Tool-feedback loop造成資料錯誤、顯著成本、無法支援多 worker，應直接做同一情境的替代 vertical，而不是繼續替 LangGraph 補膠水。反之，不能只因 Pydantic 新增 30+ capabilities 就重寫已通過的產品行為。

若 Owner 接受本節，後續文件應作四項修正：

1. Proposed ADR 0071 不再把「保留 ADR 0060 runtime」寫成不可推翻前提，改成「本輪依最新機制重驗後仍採用，硬缺口可由 successor 翻案」。
2. Work Understanding owner 收斂為 **LangGraph thread checkpoint**；Store 只保存 immutable sources、current JD workspace與其他 application-defined大物件，避免同一理解雙寫。
3. 移除實作計畫中預設必做的 LangMem／Trustcall canary；改成有真實 reconcile 品質缺口才啟動的 evidence-triggered successor。
4. 施工計畫把現行「agent 先可寫 JD、final 後才提交理解」改成上述 understanding Tool receipt → gated JD mutation；並以成本／failure test 驗證，而不是固定兩次模型 call。

## 15. 長訪談記憶與 Context 實作研究（2026-08-28）

本節回答一個較精確的問題：Caliburn 要如何像 Claude／Codex 在長工作中保持連貫，又不把整段訪談反覆塞回模型？本節先記錄官方證據、現行 code 審查與推薦形狀；若與 §14.9 已寫方案不同，以「待 Owner 確認的新發現」標示，不悄悄改成實作規格。

### 15.1 主流官方作法真正共同的地方

| 官方來源 | 實際機制 | 對 Caliburn 的直接啟示 |
| --- | --- | --- |
| [OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) | `previous_response_id`／Conversation 可保存對話 lineage，但官方明說 chain 內先前 input tokens 仍計費；context window 也同時包含 input、output 與 reasoning | provider conversation 可優化單一 model loop，不是免費長期記憶，也不可作工作理解 authority |
| [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction) | 對長對話產生 compaction item，平衡品質、成本與延遲 | 是 model-context transport，不能取代 source-linked 理解；壓縮後仍要由 durable product state 重建不可遺失的事實 |
| [OpenAI Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | 重用穩定 prefix；動態交互放後面，以 `prompt_cache_key`／breakpoint 控制 | 只降低重複 input 成本，不會幫模型記住未傳入的內容；穩定規則／Tool schema 在前，本輪理解／delta 在後 |
| [OpenAI Codex agent harness](https://developers.openai.com/blog/codex-as-a-platform) | harness 管理 conversation state、Context、Tool loop、進度、失敗與核准；host application 保留自己的介面、資料與 system of record | 先研究成熟產品行為，再讓 Caliburn 定義職務語意與 authority；不可從既有 code 或 framework 名稱倒推產品流程 |
| [OpenAI Codex Memories](https://learn.chatgpt.com/docs/customization/memories) | 把 summaries、durable entries、recent inputs 與 supporting evidence 存成 generated recall state，且可能在閒置後背景更新 | 可借用「精簡索引＋詳細依據」形狀；但本輪會支撐 JD 的工作理解不能只靠延後的 generic background memory |
| [Claude Code context window](https://code.claude.com/docs/en/context-window) | 長 session 會 compaction；root rules、auto memory 與部分 Skills 重新注入，細節按觸發重讀 | 壓縮不可是唯一記憶；穩定規則、可修訂理解、Skills 與原始來源要有不同生命週期 |
| [Claude Code memory](https://code.claude.com/docs/en/memory) | 人寫的 `CLAUDE.md` 與模型生成的 auto memory 分開；常駐只讀精簡 index，詳細 topic 按需讀取 | 常駐 Context 只要 orientation；不可把全部 claims／sources／Skills 每輪全載入 |
| [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 對每次 inference 重新挑最小高訊號 Context；混合精簡前置資訊、just-in-time retrieval、Tool-result clearing、compaction 與 structured notes | Work Understanding 是 structured note；Context 是當下投影。兩者不可合併成一份大 prompt |
| [LangChain Memory](https://docs.langchain.com/oss/python/concepts/memory) | short-term thread state 與 long-term semantic memory 分開；semantic memory 可用 profile 或 collection；可 hot-path 或 background 更新 | 本產品必須在本輪 JD 使用前看到新理解，因此核心 Work Understanding 要 hot-path；collection 比整份 profile 安全 |
| [LangChain Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) | 區分「本次 model 看到的 transient context」與「寫回 state 的 persistent context」 | Context selector 可每次動態裁切，卻不應修改 Work Understanding authority |
| [AWS AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) | short-term 保存 turn-by-turn interactions；long-term 擷取 facts、preferences 與 summaries，並明確將 immediate context 與 persistent knowledge 分離 | 這是大廠對「對話 ≠ 持久知識」的第三方佐證；但云端 generic extraction 不符合本機產品與來源／版本／JD 因果要求 |

這些來源沒有證明某個框架的 `Memory` 類名稱就等於 Caliburn 的工作理解。它們真正一致的是四層分工：

1. **原始對話／來源**：不被摘要覆寫，需要時可重讀。
2. **可修訂的 semantic memory**：持續整理「目前怎麼理解員工工作」。
3. **單次 model Context**：從前兩者中只選本次最相關的內容。
4. **外部工作成果**：Caliburn 的 current JD workspace 與 employee review authority；它由理解推導，但不是同一份 memory。

### 15.2 三個可行形狀的比較

| 方案 | 優點 | 核心問題 | 結論 |
| --- | --- | --- | --- |
| A. 一直串 provider conversation，快滿就 compaction | 代碼最少，provider 可保留 tool／reasoning lineage | 先前 tokens 仍可計費；壓縮可遺失後來才發現重要的細節；provider lock-in；無 source／revision／JD basis | 不作產品記憶；只允許 adapter 在一個 product run 內優化 continuation |
| B. 採用 generic memory service／background extractor（AgentCore、LangMem、auto memory 類） | 能省 generic memory infrastructure，也可自動擷取重點 | 背景更新對同輪 JD 太晚；常為 free text／profile／retrieval memory；不提供本產品的 source／lineage／batch atomicity／review basis | 不作 Work Understanding authority；未來有跨文件個人化或 RAG 再重評 |
| C. LangGraph typed collection／checkpoint＋Store sources＋每輪最小 Context＋按需 VFS | 新理解可同輪使用；provider 可換；source／revision／review 因果可檢查；框架已接手 persistence／recovery／VFS／context middleware | 仍需很薄的 Caliburn domain reducer；Context selection 與調和規則必須測試 | **推薦** |

方案 C 不是「因為現在已經用 LangGraph」，而是它在不新增第二 state owner 的情況下，已直接提供 typed state、checkpoint history、Store、interrupt、Tool loop、middleware 與 PostgreSQL persistence。LangGraph 的 [`Command`](https://docs.langchain.com/oss/python/langgraph/use-graph-api#combine-control-flow-and-state-updates-with-command) 可在同一步原子表達 state update 與後續 goto；官方 Tool 文件也明確說明，Tool 回傳 `Command` 後，更新的 state 會提供給同一 run 的後續步驟。[LangChain Tools：Return a Command](https://docs.langchain.com/oss/python/langchain/tools#return-a-command) 因此「先提交 canonical understanding，再依該結果編輯 JD」不需要 Caliburn 自製第二套 orchestration。Caliburn 只留框架無法知道的事：什麼是一項工作理解、何時修訂／矛盾、來自哪個 employee source，以及它是否真的支撐某組 JD diff。

### 15.3 第一版單一 owner 分工

| 資料 | 唯一 owner | 是否每輪傳給模型 | 用途 |
| --- | --- | --- | --- |
| employee turns 逐字原文 | LangGraph Store | 本輪完整傳；近期最少 pair 傳；更舊按需讀 | 不可改寫的 source |
| consultant visible replies | LangGraph checkpoint 的產品對話投影 | 只帶解讀「剛才／這個」所需的最近回覆 | 人類對話連貫，不是工作事實 |
| Work Understanding collection | LangGraph thread checkpoint | 常駐只帶 orientation／Focus／open items；詳細 claims 按相關性挑選或 VFS 讀取 | LLM 長訪談記憶，可修訂而非員工核准真理 |
| Focus／run receipt／required input | LangGraph thread checkpoint | 只帶當下狀態 | 執行返回點、單一 writer 與 safe pause |
| current JD workspace | LangGraph Store／Deep Agents `StoreBackend` | 只帶結構 orientation／自上輪的 delta；詳細 resource 按需讀 | 員工與 AI 共用的最新工作狀態 |
| approved baseline／review receipts | checkpoint＋Store-derived review | 只帶待審數、相關 group／basis 簡表；詳細 diff 按需讀 | Accept／Reject／stale／recovery |
| conversation summary | 不是 authority | 只在有實際 context pressure 時可用 | 低優先級的對話連貫補助，不可支撐 JD |

同一份 JD 的訪談維持同一 `thread_id`，但**每個 product turn 開始新的 provider lineage**，由 checkpoint／Store 重建 Context；不以 `previous_response_id` 串完整多週訪談。同一 product run 內的 Tool loop 依然保留 model messages／Tool results／provider reasoning，因為它們是當下一個因果鏈。這個邊界同時保留 model swap／provider swap／更正與 stale detection。

### 15.4 成本感知的 hot-path：成本原則保留，舊雙出口 contract 已由 §15.20 取代

§14.9.3 當時寫「每個工作相關 turn 都先強制呼叫 understanding Tool」。深入對照成本與官方 Tool guidance 後，這不應成為第一版的無條件規則。[OpenAI GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model) 建議：當 intermediate result 會改變模型下一個決定時用 direct Tool loop；同時要比較總 tokens、latency、cost 與結果品質，不能只因為 steps 更少就認定更好。§15.20 後續又移除 fixed final structured root，因此本節只保留下列最新三條路徑：

#### 路徑 A：本輪沒有工作理解變化

1. 一次主要 model loop 吸收 current employee turn、最小近期對話、相關 Work Understanding 與 JD delta。
2. 模型正常回答／追問，不呼叫 Work Understanding Tool，也不填 `no_change`／空 effects。
3. application 依 run completion 自行記錄本輪已完成；模型不填 processed-source receipt。

#### 路徑 B：本輪有工作理解變化，但 canonical result 不影響後續決策

1. 同一顧問呼叫 atomic Work Understanding Tool；model-facing fields 只有 semantic body、必要 quote／relation 與既有 target handle。
2. Tool 由 Pydantic／deterministic gate 驗 source、quote、runtime read-set、lineage 與 domain invariant，整批成功才以 LangGraph checkpoint transition 更新。
3. 同一 provider response 若已含可用的暫存回覆，adapter 在 Tool 成功後可結束 product run；是否可安全省略 continuation 必須以正式 provider smoke 驗證，不寫成跨 provider 保證。

#### 路徑 C：本輪 canonical result 會立即支撐 JD 或 required-input 判斷

1. 先走路徑 B 的 atomic Tool，取得 framework/application 產生的 canonical handles／revisions receipt。
2. Tool result 回到同一主顧問後才 continuation，按需讀 JD／Skill／舊 source並操作 workspace。
3. final response 不重複提交已成功的 understanding changes。

Owner 於 2026-08-28 確認的核心成本原則仍成立：是否 continuation 取決於中間結果是否改變下一步，不固定兩次 model call；但舊的「Tool 或 final structured batch 二選一」已由 §15.20 推翻。現在只有普通 assistant text 與確有變更時的 atomic Tool，不再有第二個 model-authored understanding 出口。

#### 15.4.1 依 §15.20 更新後的分流與失敗規則

1. 不建立額外 router model、`should_edit_jd` classifier 或固定 Stage 1／Stage 2。LLM 在同一 product run 中依工作語意決定是否需要理解／文件操作。
2. 本輪沒有 semantic change 時不呼叫 understanding Tool；application 不要求模型用 `no_change` 自證已思考。
3. 本輪有 create／revise／retire 時只能走 atomic Tool；current source identity、IDs、revision、時間與 receipt 都由 runtime／application 管理。
4. JD 若引用本輪新 canonical understanding，編輯前必須已有成功 receipt；第一版不允許模型自編 local refs 支撐 JD。
5. 可修復 Tool error 整批零寫入，只回精簡 diagnostic 給同一顧問修正一次。若 understanding 已安全提交而後續 JD 編輯失敗，保留理解、回復本輪不完整 JD edit、終止 run 並解鎖 UI；下一輪可依已保存理解繼續，不強迫員工只能重試。

這是對 Claude／Codex harness 行為的產品化轉用，不是照抄 coding schema：共同點是 durable working state、受限 Tool loop、可恢復工作面與 host-owned approval／system of record；Caliburn 額外定義工作理解、來源、JD basis 與員工 authority。[OpenAI Codex agent harness](https://developers.openai.com/blog/codex-as-a-platform) · [Claude Code — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)

### 15.5 每次 inference 的 Context 分層

#### L0：穩定、可 cache 的 prefix

- 單一專業顧問角色、authority／approval／error ownership 邊界；
- 精簡 Tool descriptions 與當前可用 Skills catalog；
- 只寫一次的輸出規則與停止條件。

L0 不包含 document ID、turn ID、Work Understanding 或 JD，避免每輪破壞 prompt prefix。

#### L1：每次必備的 dynamic orientation

- current employee turn 全文與 source handle；
- 最近 1～2 組完整 employee ↔ consultant pair（不是只帶 AI 回覆）；
- derived OrientationIndex：current stable patterns 的名稱／一行說明、open／conflict 計數、最近修訂與未定位數；不另帶可寫 `WorkScope`；
- 目前 Focus、blocking required input／普通 open items；
- current workspace generation、待審數、自上次成功 run 後的 employee JD delta。

#### L2：每次依相關性選的詳細內容

- Focus 所指 pattern／case／unresolved item 及其 current relations；
- 本輪訊號／JD delta／pending review 實際引用的 understanding revisions；
- 本輪更正或代名詞所需的近期 source basis。

選擇順序先用 deterministic refs（Focus、pending basis、changed paths、open relations、recency），不在第一版引入 embedding／RAG／LLM reranker。

#### L3：just-in-time 按需讀取

- 完整 Work Understanding record／relation／revision history／source quote；
- 舊 employee turns；
- 詳細 current／approved／review JD resources；
- 完整 Task／Duty／O／P／K／S Skill body。

第一版直接重用 Deep Agents VFS 的 `read_file／grep／glob`，將 Work Understanding 投影成唯讀 orientation index／pattern／case／unresolved resources；不為每種資料各寫一個 retrieval Tool，也不增加第二個 memory database。Deep Agents 官方 backend 已提供 State／Store／Composite／custom VFS 路由，而 permissions 可把該路徑限制為 read-only，因此這裡只需要 projection adapter，不需自製檔案工具或記憶框架。[Deep Agents Backends](https://docs.langchain.com/oss/python/deepagents/backends) · [Deep Agents Permissions](https://docs.langchain.com/oss/python/deepagents/permissions)

### 15.6 摘要、compaction 與 Tool-result clearing 的正確邊界

現行 `PolicyBoundSummarizationMiddleware` 在單一 product run 的 agent messages 達 16k tokens 時呼叫同一個模型產生摘要；LangChain 官方文件明確說 `SummarizationMiddleware` 會用**額外 LLM call**、永久以摘要替換舊 messages。同時，現行 `ContextEditingMiddleware` 能在 model call 前 transient 清掉舊 Tool outputs，不改 product state。[LangChain prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)

本 repo 的 agent 每個 employee turn 都新建、不把內部 Tool trace 當跨 turn 記憶；員工原文另在 Store，工作理解另在 checkpoint。Owner 已確認 **compaction 只處理送入模型的暫時 Context，不得改寫任何 durable product state**：

| 對象 | 是否允許有損 compaction | 規則 |
| --- | --- | --- |
| employee turns 逐字原文 | 否 | Store 完整保留；舊對話只可在當輪 model input 中摘要，需核對時仍按需讀原文 |
| Work Understanding collection／revision／source basis | **否** | 完整保存案例、模式、例外、矛盾與修訂 lineage；不得以一段摘要覆寫或任意合併語意自足 records |
| current JD、approved baseline、pending review | 否 | 都是產品工作狀態／authority，不屬於模型對話壓縮範圍 |
| 每輪 Work Understanding orientation／index | 可縮短，但不是 compaction 本體 | 它只是 derived Context projection；相關完整 claims 進 L2，其餘可由 L3 按需讀取 |
| 單一 product run 的舊 Tool outputs／重複中間訊息 | 是 | 第一線以 framework `ContextEditingMiddleware／ClearToolUsesEdit` 清除，保留最近 2～3 個仍有用結果 |
| 送入模型的較舊 conversation context | 是 | 只為語用連貫；摘要不可成為 employee source、工作理解或 JD basis |
| provider conversation／opaque compaction item | 是，且僅限 adapter optimization | 只在單一 run 接近 context budget 時使用，不進 domain contract，也不承擔跨輪記憶 |

具體第一版規則如下：

1. 工具回短、typed、可操作 diagnostic；大資源分段讀，先避免製造不必要 Context。
2. 優先清除已消耗的 Tool outputs，再考慮摘要或 provider compaction。
3. 預設移除現行 16k `SummarizationMiddleware`；不為每個正常訪談回合固定多付一次摘要 model call。只有固定真實情境證明「單一 product run 在清除 Tool results 後仍超 budget」才重開。
4. 跨輪每次從 durable source、完整 Work Understanding、workspace 與 review state 重建最小充分 Context；不沿用 opaque compaction item 作多週產品記憶。
5. 若未來仍需要較舊對話摘要，只能是可重建、`authority=none` 的 Context projection；原始 conversation 與詳細工作理解不因此刪除或改寫。

[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction) 明確把 compaction 定義為以較少 tokens 延續長對話的 model-context transport，且 server-side compaction item 是 opaque、不可供人閱讀；因此不能作產品權威。[Claude Code — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) 也說明 context 將滿時先清舊 Tool output，再摘要對話，而且早期細節可能遺失；[Claude Code Memory](https://code.claude.com/docs/en/memory) 另以精簡 index 常駐、詳細 topic 按需讀取。這些來源共同支持「壓縮暫時對話、完整保存持久細節」，而不是壓縮 Work Understanding 本體。

### 15.7 目標 Context 流程（白話）

```text
員工新訊息
  → Store 先保存不可改寫原文
  → Context selector 帶入：本輪＋最近對話＋相關工作理解＋JD delta
  → 同一位顧問整理／修訂 Work Understanding
      ├─ 不需立即改 JD：final effect batch 一次提交
      └─ 需立即改 JD：Tool 先提交理解 → 回 canonical receipt → 繼續編輯
  → 必要時按需讀 Skill／舊原文／JD 細節
  → current JD workspace 出現 AI diff
  → 員工稍後 Accept／Reject／直接編輯
  → 下一輪從 durable state 重建最小 Context，不回放整段 prompt
```

員工說「我剛才說錯了」時沒有特別 correction workflow。本輪原文＋最近完整 pair＋相關理解已經在 Context；模型能安全判定就修訂理解，不能判定才從 `/sources`／`/understanding` 按需讀或詢問。這正是長訪談「記得」的具體實現：不依賴模型隱形記憶，也不要求員工點選舊原話。

### 15.8 現行 code 的保留、替換與刪除

| 現行機制 | 處理 | 理由 |
| --- | --- | --- |
| LangGraph PostgreSQL checkpointer／Store | 保留 | 成熟 framework 已承接 durable state、history、resume 與 application Store |
| Deep Agents Store-backed VFS／Skills | 保留 | 符合 just-in-time retrieval／progressive disclosure 與同一 current workspace |
| `ConsultantContextMiddleware` 與 receipts／token budget | 保留框架骨架、重寫選擇政策 | 現在只帶最近 AI 回覆、混入 Duty／Task orientation，且使用 run 開始的 stale snapshot |
| `UnderstandingItem(kind + text)` | hard cut | 無案例／模式／待釐清 typed role 與 relation／revision 語意，難以安全長期修訂 |
| `GapItem` | hard cut | 未知／矛盾是 Work Understanding 狀態，不應有第二 writer |
| `UnderstandingCalibration`／confirm／later | hard cut | 員工只用一般對話修正理解，不直接管理 AI memory |
| `InterviewWorkItem` 當 Focus／Progress authority | hard cut，不包成 `WorkScope` compatibility layer | 穩定工作模式承接語意；Orientation／Progress 由 collection 重建；Focus 只保留 checkpoint bookmark |
| current `PolicyBoundSummarizationMiddleware` | 第一版預設移除，待 Owner 確認 | 一個 turn 內的額外摘要 call 不應與 typed Work Understanding 重複解決長期記憶 |
| `ContextEditingMiddleware／ClearToolUsesEdit` | 保留並改為第一線 | 官方成熟 primitive；清理舊 Tool output 不需額外模型 call |
| provider conversation／compaction／prompt caching | adapter-optional | 只作單一 run 品質／成本優化，不進 domain contract |

現行 `ConsultantContextMiddleware` 每次 inference 都從 run 開始的 `runtime_context.snapshot` 重建 prompt。新 understanding Tool 若中途 commit，middleware 必須取得最新 snapshot，或由 Tool 原子更新 runtime context；不可繼續把舊 understanding 放回後續 model call。同樣，最後 semantic commit 要使用 Tool 後的新 expected revision，不可使用 run 開始 revision。

### 15.9 第一版不做的事

1. 不接 RAG／embedding／Graphiti／Mem0／AgentCore service。
2. 不建多 Agent／獨立 memory model／critic model／每輪背景 extractor。
3. 不把 Work Understanding 存成 Markdown notebook／一份大摘要，也不讓員工直接編輯。
4. 不因為可用就常駐全部 Skills／Tools／sources／JD／pending diff。
5. 不在沒有真實失敗證據前把 LangGraph 與 Pydantic AI／DBOS 疊在一起。
6. 不把可選「AI 目前理解」UI 當內部 schema 設計目標；核心完成後只能從同一 state 唯讀投影。

### 15.10 施工前 Owner 裁決狀態

1. **已確認並由 §15.20 補正（2026-08-29）**：只有確有新增／修訂／退役才呼叫 understanding Tool；只有 canonical result 會影響本輪後續 JD／required-input 判斷才 continuation。沒有變化不呼叫 Tool、不填空 effect／`no_change`；具體 invariant 見 §15.4.1。
2. **已確認（2026-08-28）**：第一版預設移除 16k `SummarizationMiddleware`，改用 Tool-result clearing／最小 Context／bounded reads／hard budget；只有真實單輪超限失敗才重開 provider compaction。Work Understanding、employee sources、JD 與 review state 永不作有損 compaction。
3. **目前基線（2026-08-28，可推翻）**：不採 §14.8.3 的「一句 claim＋facets」；採 §15.11–§15.12 的有界完整語意紀錄，並在同一 collection 內區分具體案例、穩定工作模式、待釐清／矛盾。後續若證據顯示這仍造成遺失、重複、過度一般化或成本過高，必須重開比較。

### 15.11 完整語意工作理解：分析原料，不預先寫成 JD（目前基線，可推翻）

Owner 最新澄清有兩個不可退讓的效果：

1. 工作理解是 LLM 在長訪談中記得員工工作細節的 durable current understanding，不能因切細、摘要或 compaction 丟失條件、順序、例外、責任與結果關係；
2. Task、Duty、O、P、K、S 都是後續 JD Skills 讀取工作理解後才形成的分析結果，不能預先變成工作理解 schema 或分類欄位。

#### 15.11.1 權威資料限制了兩個極端

- [OPM Job Analysis](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/what-is-a-job-analysis/) 把工作分析定義為收集、記錄與分析工作的 content、context、requirements；OPM 引用的 Uniform Guidelines 更要求工作行為、相關 Tasks 與 work products 應被完整描述，並記錄 KSA 與工作行為的關係。[OPM：job-analysis documentation](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/when-conducting-a-job-analysis-do-i-have-to-collect-ratings-eg-importance-required-at-entry-from-the-subject-matter-experts-sme-for-the-tasks-and-competencies/)
- [O*NET Task Statement Components](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf) 顯示正式 Task 可包含 action、object、purpose/result、enabler 與 context；過度複雜才考慮拆成多個 Task。這支持保留關係完整性，但它是**後續 Task 寫作規則**，不能反推每段訪談立即就是 Task。
- [O*NET Content Model](https://www.onetcenter.org/content.html) 分開 Tasks、不同粒度 Work Activities、Work Context、Knowledge 與 Skills，並以 linkages 表達關係；這反對把尚未分析的工作理解先塞進 Duty → Task → OPKS 階層。
- [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 指出單一大型 profile 更新容易出錯；collection 較不易遺失個別資訊、下游 recall 較高，但純小文件 collection 也可能失去完整 context 與項目間關係。這正好否決「一篇大摘要」與「大量孤立一句 facts」兩個極端。
- [OpenAI Context Engineering for Personalization](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization/) 採 structured state＋unstructured contextual notes，並只注入 relevant slices；官方也明說 memory shape 必須由 use case 決定。對 Caliburn 的可轉用結論是：機器需要的 identity／revision／status／source 採 typed envelope，人類工作情境保留為完整語意內容。
- [Claude Code Memory](https://code.claude.com/docs/en/memory) 與 [Codex Memories](https://learn.chatgpt.com/docs/customization/memories) 都把精簡 index／summary 與詳細 topic／supporting evidence 分開；它們支持「索引可短、詳細內容不能因此消失」，但不替 Caliburn 定義職務欄位。

repo 既有專業研究也已經裁決：Story／Event／Work Unit／Task 不是一對一；一個故事可含多項工作，多個故事也可共同支持同一工作，故事只提供深度與分析原料，不能直接成為正式 Task。因此工作理解若預先切成 Task-like claim，會重演已被紅隊否決的過早分類。

#### 15.11.2 三種形狀比較

| 形狀 | 優點 | 主要風險 | 裁決 |
| --- | --- | --- | --- |
| A. 一份持續整段重寫的完整工作摘要／profile | 關係與全貌集中 | 內容變長後更新容易遺漏舊細節；局部更正會重寫整份；Context 成本高 | 不採 |
| B. 一句一筆的原子 facts／claims | 容易新增、修訂、失效與檢索 | 可能把「條件 → 行動 → 判斷 → 交接 → 結果」切散；模型拿到部分 facts 時會誤解完整工作 | 不採 |
| C. 多筆**有界、語意自足的工作理解紀錄** | 每筆保留完整關係，又能獨立版本化、按需載入與跨來源更新 | 需要定義何時同筆、何時拆筆；仍需薄的 domain gate | **推薦，待 Owner 確認** |

#### 15.11.3 推薦形狀：語意自足，不要求只有一句

第一版內部概念先稱 `WorkUnderstandingRecord`，名稱仍可調整：

```text
WorkUnderstandingRecord
  ├─ stable identity + revision
  ├─ status: current／unresolved／contradicted／superseded
  ├─ content: 一至數句、可獨立理解與修訂的完整工作語意
  ├─ minimal typed relations    # supported_by／about；不另建 WorkScope owner
  ├─ 0..N source／quote refs    # 已成立事實至少一筆；純未知可為 0
  └─ revision／supersession lineage
```

`content` 是唯一語意主體，不再把 activity、outcome、context、responsibility 等值重抄成第二份欄位。若 Context selection／coverage 需要 facets、keywords 或一行 orientation，它們只能是從同一 collection 可重建的 projection，不是工作理解 authority，也不得反向覆寫 `content`。紀錄邊界依「能否獨立修訂且仍保持原意」判斷，而不是依句號、動詞數量或 JD 欄位：

- 條件、行動、責任與結果若彼此依賴，就留在同一筆；
- 其中一部分改變而不影響另一部分的意思，才拆成不同紀錄；
- 一段員工回答可以建立 0..N 筆紀錄；多段回答可以補充或修訂同一筆；
- 一筆紀錄不是 Task，也不因含工具、成果或能力線索就預先標成 O／P／K／S；
- 未知、矛盾與例外保存成完整、可理解的語意，不以空欄或 `missing_k` 代替。

例如員工說：「重大修法時，我會先評估對制度的影響並通知主管；主管決定是否修制度，通過後我再更新教育訓練教材。」工作理解不能拆成互不相干的「評估影響」「通知主管」「更新教材」三個孤立詞條；至少要保留觸發條件、決策權在主管、員工後續責任與順序。若後續確認「教材由別人更新」，只修訂相應理解，舊 revision 仍保留，不重寫整份員工工作摘要。

#### 15.11.4 JD 分析只讀工作理解，再形成正式結構

```text
員工訊息／更正／JD delta
  → 更新有來源的 WorkUnderstandingRecord collection
  → Context 只載入相關完整 records；必要時按需讀原話
  → 依本輪 Focus／線索按需載入 Task／Duty／O／P／K／S Skills
  → 各 Skill 從完整 records 分析候選，任一種資訊都可以先出現
  → 聯合檢查 Task 邊界、Duty 分組與 O／P／K／S 關係並反覆修訂
  → 形成可審核 JD diff
```

因此工作理解 schema 不含 Task／Duty／O／P／K／S ID，也移除 `capability_signal` 這種提前朝 K／S 分類的 facet。員工主動提到工具、知識、成果或標準時仍完整記住；只是到 JD Skills 執行時才判斷它究竟是工具、步驟、Task、O、P、K、S，或不應進 JD。這不是固定「Task 穩定 → 再分析 OPKS」的 pipeline：資訊可任意先出現，Skills 按需加入，後續發現可雙向修正 Task／Duty／OPKS。這保留產品大方向，也避免 JD 分類反向污染長期理解。

#### 15.11.5 Owner 確認與後續精化

Owner 於 2026-08-28 暫定接受方案 C：工作理解採「多筆有界、語意自足的紀錄」，每筆可一至數句並保留完整條件／行動／責任／結果關係；工作理解本體不預先拆成 facets 或 Task／Duty／OPKS 欄位，後者全留到按需 JD Skills 才分析。§15.12 再把這個 envelope 精化為案例、工作模式與待釐清／矛盾三種語意角色。這是目前討論基線，不是不可推翻的永久 schema；production schema／實作計畫仍要等剩餘邊界收斂後才更新。

### 15.12 具體工作案例、穩定工作模式與 JD 抽象層（目前基線，可推翻）

Owner 進一步澄清：工作理解不只要「記得完整語意」，還要承接顧問逐步理解工作的分析成果。員工起初可能只說「我有做網站」「我會處理申訴」；顧問必須保留已知細節、指出仍不清楚的條件／責任／判斷／結果，取得補充後再從整體理解發現衝突、例外與反覆出現的工作模式。訪談完成時，工作理解應比 JD 更詳細；JD 是從中形成的**角色層級、可長期適用且仍清楚的專業抽象**，不是把每一個客戶、案件或專案各寫成一條 Task。

這有一部分像「顧問的工作底稿」，但**不是模型私有 chain-of-thought**。產品不保存 token-by-token 推理、隱藏草稿或完整內在思考；只保存可檢查的目前結論、具體案例、尚未知事項、矛盾、短而可追溯的歸納關係與修訂 lineage。

#### 15.12.1 最新官方資料直接支持「案例不是正式 Task」

- [OPM Assessment and Selection](https://piv.opm.gov/policy-data-oversight/assessment-and-selection/) 把 critical incidents 定義成描述重要職務功能的具體有效／無效行為**例子**，同頁另把 Tasks、roles、responsibilities、resources、context 與 competencies 列為 job analysis 的分析結果。可轉用邊界是：具體事件是深挖與驗證工作內容的原料，不能因為被訪談者講了一個事件，就直接宣告它是一條穩定 Task。
- O*NET 於 2025 年發布的 [Identification of Emerging Tasks: Revised Approach](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf) 先收集 incumbents／occupational experts 的 write-in statements，再由分析師區分 non-task、既有 Task 的 duplicate／overlap 與新內容；有重疊的多筆敘述會先找共通與差異，再抽取 action、object、purpose/result、enabler、context 來形成新 Task 或修訂既有 Task。官方明定目標是「足夠廣，能涵蓋敘述中的一般活動；又足夠具體，能準確描述所含行為」，並排除只適用單一職位、過度狹窄的敘述。這是本輪最直接的權威佐證。
- [O*NET 2026 Web and Digital Interface Designers](https://www.onetonline.org/link/details/15-1255.00) 的正式 Task 也是「Design, build, or maintain Web sites」「Conduct user research to determine design requirements」這類角色層級工作，而不是把某位任職者做過的網站 A、網站 B 各列一條。
- [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 區分 semantic memory（目前事實／概念）與 episodic memory（經驗／事件）。這支持在 Context 與檢索時區分「發生過的具體案例」和「目前歸納出的工作模式」，但不要求 Caliburn 建兩個資料庫或兩個 writer；兩者仍屬同一份工作理解 authority。
- repo 既有 [`2026-07-25 professional consultant red-team`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md) 已確認 Story／Event／Work Unit／Task 不是一對一：故事提供深度，跨故事整併才判斷 add／edit／merge／split／no-op／clarify。本節是把該專業原則落到長訪談記憶形狀，不是另創一套 Task-first pipeline。

外部資料沒有替 Caliburn 規定欄位名稱或保證 LLM 能自動做對所有歸納；以下 shape 是把 OPM／O*NET 的工作分析方法、LangGraph 的成熟 memory primitive 與本產品單一員工 authority 結合後的產品推論。

#### 15.12.2 三種作法比較

| 作法 | 效果 | 主要問題 | 裁決 |
| --- | --- | --- | --- |
| 只保存具體案例 | 細節與原話脈絡完整 | 每輪都要重新跨案例歸納；成本高，且可能今天分成兩項、明天又合成一項 | 不採 |
| 只保存歸納後工作模式 | Context 短、容易直接寫 JD | 容易丟失案例差異、例外與更正依據，也無法判斷是否過度概括 | 不採 |
| 同一工作理解內保留「具體案例＋目前工作模式＋待釐清／矛盾」並建立最小關聯 | 同時保留細節與穩定理解；JD 不需從聊天重做全部分析 | 要定義何時可一般化，以及更正案例時哪些模式要重看 | **推薦，待 Owner 確認** |

「三種語意角色」不等於三個 Store。第一版仍是一份 LangGraph semantic-state collection、同一 writer 與同一 revision boundary；可用一個共同 typed envelope 承載三種內容：

```text
Work Understanding collection
  ├─ 具體工作案例：某次實際發生了什麼、條件、順序、參與者、判斷、結果與例外
  ├─ 目前工作模式：跨案例或由員工直接說明後成立的穩定責任／流程／變化範圍
  └─ 待釐清／矛盾：少了什麼、哪些說法不能同時成立、下一步需要問什麼
```

三者共用 stable identity、revision、status、source linkage 與 supersession lineage；只增加最小 `supported_by／about` 關係，讓「目前工作模式」可以指回支持它的案例或員工直接陳述，讓「待釐清／矛盾」可以指向受影響的理解。它們仍然不含 Duty／Task／O／P／K／S 欄位。

#### 15.12.3 何時可以從案例歸納成工作模式

不能因為員工剛好做過兩次，就自動假定那是永久責任。至少有一種支持才可建立目前工作模式：

1. 員工直接說明這是反覆、週期性或角色固定承擔的工作；
2. 多個案例呈現相同 action／object／purpose 或責任邊界，且沒有相反證據；
3. 顧問對典型性、範圍或例外追問後，員工確認這個一般化描述。

若只有具體案例而無法判定一般性，就保留案例並建立白話待釐清，例如：「這兩個網站是固定維護對象，還是你會依不同顧客案件持續開發新網站？」不能自行把兩個網站概括成接案型前端開發，也不能直接產生兩條網站 Task。

#### 15.12.4 網站例子的正確流向

```text
員工原話
  「去年替 A 客戶做購物網站；最近又替 B 客戶做企業形象網站。」

具體工作案例（詳細保留）
  A 案：需求來源、前端範圍、技術、協作、測試、交付、例外……
  B 案：需求來源、前端範圍、技術、協作、測試、交付、例外……

顧問待釐清
  「這是固定維護兩個網站，還是會持續依不同顧客需求承接網站開發？」

員工確認後的目前工作模式
  「依不同顧客需求釐清前端規格，實作、測試並交付網頁介面；專案內容不同，但責任流程相近。」

JD Skill 形成的角色層級 Task 候選
  「依顧客需求開發及測試前端網頁介面。」
```

JD 不是普通壓縮摘要，而是有方法與目的的 abstraction／synthesis：盡量涵蓋穩定工作，保留必要 action、object、purpose／result 與角色邊界，移除客戶名稱、單次專案細節與不具代表性的偶發資訊。若那些網站其實就是固定維護標的，工作模式與 JD 就應反映固定維護責任；不能為了寫得通用而改變員工真實工作。

#### 15.12.5 Context 與成本邊界

- durable authority 保存完整案例、工作模式與待釐清內容，不作有損摘要；
- 每輪 Context 預設帶目前相關的工作模式、待釐清索引與本輪涉及的完整案例；其餘案例可由 `/understanding`／`/sources` 按需讀取；
- JD Skills 以目前工作模式為主要導航，但要能讀支持案例與例外以驗證是否過度概括；不能只看一行模式就直接改 JD；
- 新來源修訂案例時，系統只標記其支持的工作模式需要重看，不要求每輪重算全部工作理解；
- Focus 只指向當下要理解的案例、模式或問題，仍不是 Task，也不進工作理解本體。

這沿用 Claude／Codex 類長工作產品的可轉移概念：持久保存可檢查工作狀態與詳細資料，模型每輪取得高訊號目前狀態及按需細節；不保存上一輪完整 hidden reasoning，也不要求每輪重播整份歷史。

#### 15.12.6 Owner 暫定確認與可推翻條件

Owner 於 2026-08-28 暫定接受：工作理解仍採 §15.11 的多筆語意自足紀錄，但明確包含同一 collection 內的三種語意角色——**具體工作案例、目前歸納的穩定工作模式、待釐清／矛盾**；JD Skills 再從這份比 JD 詳細的工作理解形成角色層級 Duty／Task／OPKS，而不是把每個案例直接變成 Task。

本裁決可由後續證據推翻，尤其是：固定長訪談顯示案例與模式大量重複或頻繁失效、模型無法可靠維持兩者關係、Context 成本失控，或更成熟框架能以更好的效果完整替代同目的機制。§15.13 已完成「穩定工作模式」與既有 `WorkScope` 的去留研究並獲 Owner 暫定接受；production schema 仍須等 coverage 與其餘 record boundary 收斂後才施工。

### 15.13 `WorkScope` 去留：語意由工作模式承接，導航由 projection 承接（目前基線，可推翻）

#### 15.13.1 先區分「工作語意」與「找到工作語意的索引」

現行 production state 同時有 `InterviewWorkItem` 與 `UnderstandingItem`：前者保存 title、status、priority、reason、missing／next step 與 current focus，後者保存理解文字、source、revision 與 `work_ids`；`ConsultantContextMiddleware` 又先投影 work items，再把理解掛到第一個 `work_id`。因此現況不是單純多一個 UI label，而是兩個都由模型修訂、都在描述「員工正在做哪一塊工作」的 semantic layers。若把它們原樣改名成 `WorkScope` 與 Work Understanding，重複 writer、改名／合併 churn、失效規則與 Context 成本都會保留。

外部框架沒有要求為導航另建一個 domain object：

- [LangChain Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory) 的 Store 以 namespace、key、filter 與 search 組織 JSON documents；這證明成熟框架已有「分組與找資料」primitive，不代表每個 namespace 都要升格成另一份 LLM 可寫的業務真相。Caliburn 依 ADR 0060／0071 仍由 checkpoint 擁有 semantic state，本節只借用索引／查詢概念，不搬 authority。
- [Claude Code memory](https://code.claude.com/docs/en/memory) 把簡短 `MEMORY.md` 當索引，詳細內容放 topic files 按需載入；索引可重建、服務 orientation，詳細記憶才承載內容。這比「索引本身也是一套有 lineage 的工作知識」更貼近本產品需求。
- [Codex memories](https://learn.chatgpt.com/docs/customization/memories) 也區分 summaries、durable entries、recent inputs 與 supporting evidence。可轉移原則是分層選取 Context，不是替同一語意建立兩個可寫 owner。

#### 15.13.2 O*NET 有工作活動階層，但不能直接推導 Caliburn 必須有 WorkScope

[現行 O*NET Content Model](https://www.onetcenter.org/content.html) 的 Work Activities 確實分成 generalized、intermediate 與 detailed work activities，並以大量 DWA–Task linkages 連到 occupation-specific Tasks。這說明多粒度活動層在**跨職業比較、資料維護與 taxonomy reuse**有價值；不代表單一員工訪談必須持久保存相同層數。

較早但仍解釋現行 hierarchy 形成方法的 [O*NET DWA methodology report](https://www.onetcenter.org/dl_files/DWA_2014.pdf) 說明 Task 先聚成 DWA，再聚成 IWA，且方法上的核心挑戰是每層都要有獨特內容、不能複製相鄰層。Caliburn 已有「具體案例 → 穩定工作模式 → JD Duty／Task」三個目的不同的語意階段；若 `WorkScope` 只是把穩定工作模式再換一個較寬名稱，便沒有達到 O*NET 所要求的獨特用途，反而容易與後續 Duty 再次重複。

#### 15.13.3 三種方案比較

| 方案 | 效果 | 成本／風險 | 裁決 |
| --- | --- | --- | --- |
| A. 保留獨立、可寫、stable `WorkScope` | 有固定大分類，可直接顯示 scope progress | 模型要同步 scope 與 pattern；改名、merge、split、membership、lineage、stale 都要另做；與 Pattern／Duty 意義容易重疊 | 不推薦 |
| B. 完全只顯示所有工作理解紀錄 | schema 最少，沒有重複 owner | 大量案例與未知會讓 Context／UI 缺少 orientation；進度難掃描 | 不採 |
| C. 穩定工作模式是 durable semantic hub；由 collection 關係即時計算 Orientation／Coverage index | 保留導航、Focus、Context selection 與進度，又只有一份語意真相 | projection 要有明確且可重建的排序／狀態規則；模式過多時可能需要日後再分組 | **Owner 暫定接受** |

#### 15.13.4 推薦形狀

```text
Work Understanding（唯一可修訂 semantic authority）
  ├─ stable work patterns
  ├─ concrete work cases ──supported_by／about──> pattern(s)
  └─ unresolved／contradicted ──about──> pattern／case；也可尚未定位

OrientationIndex（每次由 current collection 重建；不是 authority）
  ├─ 每個 current stable pattern 一張工作範圍卡
  ├─ 相關案例、待釐清／矛盾與最近變更摘要
  ├─ 尚未定位區
  └─ derived coverage／next-focus hints（無假百分比）

Focus（checkpoint runtime bookmark）
  └─ 指向理解 ID、待釐清 ID 或一次查詢選擇；不指向另一個 scope owner
```

第一版不另做 LLM clustering、scope merge／split Tool、scope lineage 或第二套 status。工作模式本身的一行 title 可直接成為 UI／prompt orientation label；案例與未知依 typed relations 掛載，沒有安全關聯就進「尚未定位」。Context middleware 只常駐這份小型 index，再按本輪訊息、Focus 與關係載入完整 records／sources。進度同樣是 projection：顯示哪些穩定工作模式已有足夠理解、哪些仍有一般待釐清或矛盾，不宣稱固定百分比，也不把缺 O／P／K／S 直接當員工進度。

這不是「自己再寫一套記憶框架」：LangGraph checkpoint／typed reducers 承接 durable state 與 revision，Pydantic 承接 shape validation，Context middleware 承接每輪 projection／selection；Caliburn 只保留職務語意的 record／relation／coverage 規則。現行 `InterviewWorkItem` 的 semantic writer 應在後續 hard cut 被移除，而不是包成 compatibility `WorkScope`。

#### 15.13.5 何時才重開真正的 WorkScope

只有固定長訪談顯示以下任一缺口，才以 successor research／ADR 重開更高層工作範圍：

1. 單一員工穩定工作模式數量長期過多，使 orientation／Context selection 明顯失效；
2. 多個模式確實共享一個不等同 Duty、且會跨 JD 改寫仍保持穩定的工作語意；
3. 真實使用證明額外層能顯著提高召回、訪談方向或進度理解，而不是只改善命名；
4. 新層能定義與 Pattern、Duty 不重複的 invariant、writer、revision 與可測 acceptance。

在此之前，若只是 UI 想把幾張模式卡折疊在一起，只能做可重建的 view group／filter，不建立 stable semantic identity。下一個待討論問題因此變成：如何為 pattern／case／unresolved 定義足以驅動 Context 與員工可理解進度的最小 coverage projection，而不重新發明 Scope。

Owner 於 2026-08-28 暫定接受方案 C；這只確認第一版不建立獨立可寫 `WorkScope`，不代表 record boundary 已定稿。coverage 與第一版 UI 語意後續由 §15.14 收斂；若 §15.13.5 的真實缺口出現，仍可由 successor 研究推翻。

### 15.14 訪談 coverage 與進度：顯示可解釋狀態，不製造完成百分比（目前基線，可推翻）

#### 15.14.1 必須分開三種「進度」

目前討論容易把三件不同的事混成一條進度列：

1. **本輪系統執行狀態**：模型是否仍在分析、是否等待員工回答或是否發生技術錯誤；這是幾秒到幾分鐘的 transient operation status。
2. **訪談理解 coverage**：目前辨識了哪些穩定工作模式、哪些仍有重大未知／矛盾、哪個是目前訪談重點；它可反覆重開，沒有固定總量。
3. **JD 工作面狀態**：目前有多少待審變更、員工是否已審核、是否選擇匯出；這不是「對員工工作理解了多少」。

第一項可用 loading／busy indicator；第二項用質性、可解釋的 overview；第三項沿用 current workspace／pending review 的真實計數。不得因「已有三個 Task」或「已接受五個變更」就宣稱訪談完成。

#### 15.14.2 職務分析來源支持哪些 coverage 面向，也明確不支持什麼

- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 與 [OPM FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/what-is-a-job-analysis/) 要求系統性收集、記錄與分析工作 content、context、requirements，以及 Tasks 與 competencies／KSAs 的關係。這支持廣度、工作情境與能力連結，不提供固定訪談百分比。
- [OPM Assessment and Selection](https://www.opm.gov/policy-data-oversight/assessment-and-selection/) 進一步要求辨識 duties、roles／responsibilities、resources 與 context，並由具近期直接經驗的 SMEs 提供資訊；importance 應與成功工作表現連結。它也把 critical incidents 當理解重要功能的案例，而不是完整工作清單。
- [EEOC Uniform Guidelines Q&A 77](https://www.eeoc.gov/laws/guidance/questions-and-answers-clarify-and-provide-common-interpretation-uniform-guidelines) 明確說不必描述所有 Task，但要描述所有重要 work behaviors、相對重要性／難度、可觀察 work products 與相關 Tasks。這直接支持「重要行為代表性覆蓋」，反對以 Task 數或欄位填滿率作完成度。
- 最新 [O*NET 31.0 Task Ratings](https://www.onetcenter.org/dictionary/31.0/csv/task_ratings.html) 仍分開 relevance、importance 與 frequency；[O*NET 現行資料蒐集](https://www.onetcenter.org/dataCollection.html) 也同時使用 incumbents、occupational experts、分析者及多種資料來源。可轉用結論是高頻不等於高重要，低頻高影響工作不能因出現次數少而漏掉；但 O*NET 是跨多人、跨職業資料庫，不能把其群體量表直接當單一員工的訪談分數。
- [OPM 對 critical task 的官方回答](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/when-conducting-a-job-analysis-how-do-i-determine-which-tasks-and-competencies-are-considered-important-or-critical/) 明說 cut-off 取決於採用的 job-analysis method。這表示 Caliburn 可以定義產品 rubric，但必須誠實標成產品決策，不能聲稱外部標準給了通用門檻。

因此第一版的專業 coverage challenge 應保留為 Skill／顧問判斷面向，而不是資料表必填 facets：

- 是否只被一個精彩案例主導，還是已掃描例行、週期性與例外工作；
- 是否同時看高頻例行與低頻高影響工作，並區分 relevance／importance／frequency；
- 是否理解實際 action、object／服務對象、責任與決策邊界、交接、結果、情境、變化與重要例外；
- 是否仍有會實質改變工作模式或 JD 的未知／矛盾；
- 需要形成 JD 時，Task 與適用的 O／P／K／S 是否有合理關係，而不是為填滿欄位捏造內容。

這些是顧問要檢查的問題，不是每個 pattern 必須填滿的 schema 欄位；某些工作本來就沒有獨立 Output、量化 Indicator 或固定週期。

#### 15.14.3 大型設計系統共同否定假百分比與線性 wizard

- [Apple HIG Progress indicators](https://developer.apple.com/design/human-interface-guidelines/progress-indicators) 只在 duration／總量明確時使用 determinate progress，並要求數字準確，否則會讓使用者覺得受騙。
- [Microsoft WinUI Progress controls](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/progress-controls) 同樣把 determinate percentage 限定在可預測終點的 operation；若只是背景狀態，文字可能比 progress control 更合適。
- [IBM Carbon Progress indicator](https://carbondesignsystem.com/components/progress-indicator/usage/) 與 [USWDS Step indicator](https://designsystem.digital.gov/components/step-indicator/) 都把 step indicator 限定在三步以上、順序與總步數已知的線性流程；USWDS 明確說條件式或可任意順序流程應換別的呈現。
- [GOV.UK Complete multiple tasks](https://design-system.service.gov.uk/patterns/complete-multiple-tasks/) 建議狀態先從最少種類開始，只有 user research 證明需要時才增加；狀態應短、可理解並優先突出仍需行動的項目。

Caliburn 的訪談會因新線索增加工作模式、因更正重開舊理解，也允許員工任意離開／返回，顯然不是固定線性流程。因此「第 3／8 階段」「63% 完成」與整體 progress bar 都不成立。本輪 LLM 分析時仍可顯示 indeterminate busy state，但那只代表系統正在工作，不代表訪談完成度。

#### 15.14.4 Claude／Codex 可轉用的是「持久狀態地圖」，不是 coding task 百分比

- [Anthropic long-running agent harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) 發現只靠 conversation／compaction 容易讓後續 agent 猜測現況或過早宣告完成，因此以可持久、可檢查的 progress artifact 留下已做與剩餘工作。
- [Claude Code task list](https://code.claude.com/docs/en/interactive-mode#task-list) 使用 pending／in progress／complete 的少量狀態並跨 compaction 保存；[Claude context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 則主張每輪從持續演化的資料中選取高效用 Context。
- [OpenAI Harness engineering](https://openai.com/index/harness-engineering/) 的直接經驗是「給 agent 一張 map，而不是千頁說明書」，並指出可機械檢查 coverage、freshness、ownership 與 cross-links 的分散知識比單一巨大手冊更可靠；[OpenAI Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/) 也把長 conversation 的 compaction 定位成 Context 管理，不是產品完成狀態。

可轉用結論是：每輪讓顧問看到短小 OrientationIndex、目前 Focus 與具體 open items；員工也看到同一事實的精簡 projection。coding agent 的 task list 不能直接拿來定義職務分析完成，也不需要引入另一個 planner／task framework。

#### 15.14.5 三種產品方案

| 方案 | 優點 | 主要問題 | 裁決 |
| --- | --- | --- | --- |
| A. 整體百分比／固定階段 | 一眼可見，看起來最像進度 | 分母未知、訪談非線性；新線索與更正會倒退，容易誤導 | 不採 |
| B. 只顯示「訪談中／已完成」 | 最簡單 | 員工仍不知道談了什麼、缺什麼；模型也缺少可恢復 orientation | 不採 |
| C. 由 current understanding 投影每個工作模式的質性 coverage，加上全域具體未決與待審計數 | 可解釋、可重開、能同時服務員工與 Context selection；沒有第二 semantic owner | 「目前足夠」含語意判斷，必須綁定精確 understanding basis，不能由程式假裝全自動證明 | **Owner 暫定接受** |

#### 15.14.6 推薦的第一版畫面與語意

```text
訪談概況
  目前重點：釐清重大修法時的決策與交接
  已辨識 5 個穩定工作模式
  2 項一般待釐清 · 0 項需要你的確認 · 3 組待審變更

工作模式
  法令變動追蹤與影響評估      待補充
    還不清楚重大影響由誰決定，以及後續交接方式

  內部法令諮詢                目前足夠
    已足以形成一版可審核描述；之後有新資料仍可重開

尚未定位
  1 筆新線索：員工另外提到「每季整理一份報表」
```

第一版只需要兩個常態 coverage label：

- **待補充**：已有 stable pattern，但仍有會影響理解或 JD 的重要未知／矛盾；卡片顯示一條最有價值的具體原因。
- **目前足夠**：依目前來源，已足以解釋這塊工作並形成或檢查一項有用的 JD 描述，且沒有影響它的 blocking ambiguity；不是永久完成，後續可重開。

「需要你的確認」仍是獨立 blocking interrupt，不變成第三種一般進度；「目前訪談重點」是 Focus 標記，不變成 coverage status；未定位線索放獨立區，不假裝已知其所屬工作模式。已核准 JD 是否完整反映某個 pattern，第一版也不另做 per-pattern status：核准後按既定方向不永久保留 AI 理由／來源關聯，強行宣稱「已反映」會需要另一套 provenance 或額外模型判斷。員工直接看 Current JD 與全域待審數即可。

#### 15.14.7 如何產生，而不建立第二份 truth 或多一次固定 model call

「待補充／目前足夠」包含專業語意，deterministic code 無法只靠 records 數量證明。推薦採混合 projection：

1. 同一主顧問在更新工作理解、選擇下一個 Focus 或評估是否要整理 JD 時，**按需要**輸出 pattern-level sufficiency recommendation 與 1～N 筆 basis understanding IDs；不是每個 model step 固定重算全部 pattern，也不另開 progress agent。
2. application 只驗證 basis revision、references、status 與 hard contradiction／required-input invariant；模型不可輸出百分比，application 也不把「沒有 unresolved」誤當充分。
3. 通過後可把 projection cache 存在同一 LangGraph checkpoint，附 `basis_digest／generated_at_revision`；任何相關理解 revision 改變就視為 stale，下一個相關 run 重建。cache 可刪除重算，不能反向覆寫 Work Understanding。
4. deterministic 部分直接從 authority 投影：pattern 數、unresolved／contradicted 數、required input、Focus、未定位線索與 pending review 數；員工可見原因只能引用 current understanding，不由 UI 猜。
5. Context middleware 常駐 compact overview；只有本輪 Focus、待補充原因及受影響 pattern 的完整 records 進詳細 Context。這沿用 §15.13 OrientationIndex，不建立 `CoverageItem` writer 或另一個 database。

整體「目前資料已足夠整理一版 JD」只能是可推翻的顧問建議：重要工作廣度已有合理掃描、current patterns 大多目前足夠、沒有會實質改寫文件的 blocking unknown／contradiction，且待審內容可由員工處理。員工仍可繼續談、關頁、匯出或日後重開；系統不增加 finish 按鈕、完成鎖或自動終止。

#### 15.14.8 重開門檻與下一個決策點

若固定真實長訪談顯示兩種 label 太粗、員工無法理解「待補充」的差異，再依 user research 增加一個有明確行動差異的狀態；不得先加入 `尚待辨識／已有線索／了解中／需重看／完成` 五六種近義標籤。若模型頻繁錯判「目前足夠」，先檢查 coverage Skill、basis selection 與具體理由，不立即加 critic model或評分百分比。

Owner 於 2026-08-28 暫定接受方案 C：第一版只顯示「待補充／目前足夠」兩個常態 coverage label，另列 Focus、一般待釐清、需要你的確認、未定位線索與待審數；所有狀態都由同一 Work Understanding／runtime／workspace 投影，不建立新 authority。這仍可由真實 transcript／user research 重開。

下一題研究長訪談的 Context recall：新訊息沒有 stable ID、也不在目前 Focus 時，如何找回相關 Case／Pattern／待釐清而不把全部內容每輪重傳。在此之前不得由 implementation 自行加入 embedding／RAG、額外 router model 或全量 context。

### 15.15 案例→模式關係與更正傳播：最小 typed dependency，不做通用知識圖譜（目前基線，可推翻）

#### 15.15.1 現行缺口不是「沒有版本」，而是「不知道誰依賴哪個版本」

現行 `UnderstandingItem` 已有 stable `understanding_id`、`version_id`、`supersedes_version_id`、`source_ids` 與歷史版本；`_apply_understanding_changes()` 也會以 ADD／REVISE／RETIRE 產生新版本，不原地覆寫。然而 `kind`、`text` 與 `work_ids` 都不足以表示：

- 哪個穩定工作模式是由哪些具體案例歸納；
- 哪個待釐清／矛盾正在影響哪些案例或模式；
- 某個案例的新版本出現後，哪些模式的 basis 已經不是它分析時讀到的版本；
- 哪些 coverage／待審 JD 需要重建，哪些完全無關。

因此若只沿用現行 shape，application 只能每輪把大量理解重新交給模型猜關係，或粗暴使整份工作理解 stale。前者增加成本並會因 Context selection 不同而漂移；後者會讓一個小更正重開整場訪談。

普通對話更正也不能靠 `EmployeeSource.validity` 或 `source_supersessions` 取代這個關係。依 §2／ADR 0071，員工說「剛才說錯」只是新增 immutable employee turn；舊原話仍是歷史事實，而新訊息可能是取代、補充條件、修正範圍或另一時期的例外。真正被修訂的是**目前工作理解**，不是由 application 在來源層猜「舊訊息已失效」。

#### 15.15.2 權威資料支持「版本＋實際依賴＋精確前置條件」，不支持任意級聯刪除

- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) 是 2013 年的穩定 Recommendation，年代較早但 revision／derivation 語意至今仍是正式 provenance 標準。它把 revision 定義為保留原內容的 derivation，並強調只有舊 entity **實際影響**新 entity 才是 derivation；「同一次處理曾經讀到」本身不夠。它也允許應用選擇最合適的關係粒度，沒有要求建立完整 ontology。
- 同一標準把 invalidation 定義成 entity 的毀壞、停止或到期，之後不再可用；[PROV Constraints](https://www.w3.org/TR/prov-constraints/) 又要求 derivation 的新 entity 晚於原 entity。這表示員工更正案例後，舊案例版本可以留作 revision history，但不能把「可能要重看」誤寫成「所有下游內容已被證明錯誤／刪除」。
- [RFC 9110 `If-Match`](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) 用 current entity tag 防止對過期 representation 的 lost update；最新 [Kubernetes `resourceVersion`](https://kubernetes.io/docs/reference/kubernetes-api/definitions/object-meta-v1-meta/#ObjectMeta) 同樣把 opaque exact version 用於 optimistic concurrency、change detection 與 watch。可轉用原則是：關係不能只記 stable ID，還要記「分析時依賴的 exact version」，才能 deterministic 判斷是否過期。
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 已承接 thread checkpoint、history、resume 與 reducer；[LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 明說 document collection 較不容易遺失資訊，但 update／delete 很難，且單筆 schema 不一定能捕捉 records 之間的關係。框架提供儲存與執行 primitive，不會替 Caliburn 定義「案例支持模式」的職務語意。
- [Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents) 把 append-only session log 與每輪實際送進模型的 Context 分開，允許之後按位置重讀原始事件；[OpenAI Harness engineering](https://openai.com/index/harness-engineering/) 則強調讓 agent 取得可檢查、具 ownership／cross-links 的知識地圖，而不是依一份巨大摘要。兩者都支持「原始歷史可恢復＋目前狀態有明確索引」，不支持用 compaction 或模型隱形記憶取代 durable dependency。
- 最新 [O*NET Emerging Tasks revised approach](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf) 先保留 incumbents 的具體 write-ins，再依與既有／其他 statements 的重疊、差異及 action／object／purpose／enabler／context 核心元素決定修訂既有 Task、建立新 Task或保留 stand-alone statement 供後續 SME review。這支持「具體案例可支持較一般模式，但沒有足夠重疊時不得強迫歸納」。

這些資料共同支持一個窄結論：保留可版本化的小型 records，明寫真正使用的依賴，並以 exact version 偵測需要重看；它們沒有替 Caliburn 規定 record 名稱或自動語意判斷。

#### 15.15.3 三種方案比較

| 方案 | 優點 | 主要問題 | 裁決 |
| --- | --- | --- | --- |
| A. 不保存關係，每輪由模型從內容重猜 | schema 最少 | 需要反覆載入大量 records；更正影響範圍不可驗證，長訪談容易漏掉或全重算 | 不採 |
| B. 建立任意 node／edge knowledge graph，再做遞迴 invalidation | 表達力最高 | 要定義 edge ontology、cycle、transitive semantics、graph query、級聯與同步；「相關」很容易被誤當「已失效」，第一版明顯過度設計 | 不採 |
| C. 單一 collection 內保留兩種 active typed relation＋exact revision，其他只作 lifecycle lineage | 可精準找 direct dependents、保留完整細節、成本可控；可由 LangGraph checkpoint／Pydantic 承接 | 模型仍須判斷語意是否真的改變，但只處理有界範圍 | **Owner 暫定接受** |

#### 15.15.4 推薦的最小關係面

第一版只讓三種 record 承擔下列關係，不開放任意 edge：

```text
具體案例 Case
  └─ 直接引用 1..N 筆 employee sources／必要 quote anchors

穩定工作模式 Pattern
  ├─ 可直接引用 employee source（員工明說「這是我固定會做的工作」）
  └─ supported_by: 0..N 個 CaseRef(record_id + expected_version_id)
     ※ direct source 與 supported_by 至少要有一種；dependency closure 最終必須抵達 employee source

待釐清／矛盾 Unresolved
  └─ about: 0..N 個 UnderstandingRef(record_id + expected_version_id)
     ※ 未定位線索或純缺口可為 0；若已知影響對象就必須連結，不能只在文字中暗示

共同 lifecycle
  ├─ stable record_id + current version_id
  ├─ supersedes_version_id：同一語意主體的修正／補充
  └─ derived_from_version_ids：只有 record 邊界真的 split／merge 時使用的歷史 lineage
```

`supported_by` 只允許 Pattern → Case，不允許 Pattern → Pattern 的任意推論鏈；`about` 只允許 Unresolved → Case／Pattern，不建立 Unresolved → Unresolved 的問題網。這使 current graph 天然有界，reverse index 可直接由 collection 重建，不需要 graph database、embedding、RAG 或另一個 Store。

`derived_from_version_ids` 不是第三種 active semantic dependency，也不驅動日常 Context；它只回答「這筆新 identity 是由哪些舊 records 重整而來」。同一主題只是內容修正就維持 stable ID 並建立新 version；只有下列情況才改 record boundary：

- 一筆內容包含兩個可以獨立修訂而不改變彼此原意的工作，才 split 成兩個新／既有 stable IDs；
- 兩筆其實是同一個可獨立修訂的工作語意，才 merge／retire 重複 identity；
- 一個新案例、另一個時期／條件的獨立例外，或另一個持續責任，本來就應是新 stable ID。

split／merge 不需要專門的模型 Tool。模型仍輸出一個原子 effect batch 的 create／revise／retire＋typed refs；application 對候選最終 collection 驗證 identity、exact versions、type direction、source closure、self-reference、duplicate refs 與 lifecycle 後才一次提交。這沿用目前「低階編輯 primitive 組成高階語意變更」的大方向。

#### 15.15.5 員工更正一個案例時的白話流程

```text
目前：
  Case C1 v1 ─┐
              ├─ supports → Pattern P1 v1「依客戶需求開發前端網站」
  Case C2 v1 ─┘

員工新訊息：
  「A 案我剛才說錯了，我只做需求確認，實作是外包。」

同一 product run：
  1. 新 employee turn 永久保存；舊 turn 不刪除、不由 application 宣告無效。
  2. 顧問把 C1 修訂成 C1 v2，保留 v1→v2 lineage 與新舊來源依據。
  3. deterministic reverse index 發現 P1 v1 仍 pin 在 C1 v1，因此只把 P1 與相關 unresolved／coverage／pending JD 列入受影響集合。
  4. 顧問依 C1 v2、C2 v1 與 P1 v1 決定：
     - 意義仍成立：建立內容可相同的 P1 v2，改 pin 最新 support；
     - 意義要改：建立修訂後 P1 v2；
     - 已無足夠支持或出現互斥：保留／建立待釐清，Pattern 暫不供 JD 編輯使用；
     - record boundary 改變：以同一 batch create／retire 並留下 derived-from lineage。
  5. 完全未引用 C1 v1 的其他 Pattern 不重算、不重開。
```

若模型同輪沒有安全完成第 4 步，application 也不能自動改寫 Pattern 內容。它只從 exact-version mismatch 投影 `needs_reconciliation`：該 Pattern 的 coverage 回到「待補充」，下一次相關 Context 必載入它，且新的 JD edit 不得以過期 Pattern revision 作 basis。這不是永久 status／第二 writer，也不是宣告 Pattern 已錯；Pattern 一旦 revise／rebase，投影便自然消失。

相同規則向下游延伸：coverage cache 只因自己引用的 Pattern／Case revision 改變而 stale；待審 JD 只因自己引用的 understanding revision 改變而 stale。不得用整份 collection revision 讓所有項目一起失效。

#### 15.15.6 Context、成本與框架分工

- OrientationIndex 常駐 stable ID、current version、role、短標題、coverage 與 unresolved 計數；不常駐完整歷史。
- 本輪更正優先載入近期對話、被修訂 Case、直接依賴它的 Pattern／Unresolved，以及判斷所需的 supporting Cases；其餘由 `/understanding`／`/sources` 按需讀取。
- `supported_by/about` reverse index、exact-version mismatch、source closure 與候選 batch validation 都是 deterministic code；不增加固定第二模型、critic、embedding 或圖資料庫查詢。
- LangGraph Saver／checkpoint 負責 durable state、history、resume 與原子 transition；Pydantic 負責 typed schema；Context middleware 負責 projection／selection。Caliburn 只保留 Case／Pattern／Unresolved 的 domain relation 與 verifier，沒有成熟 framework 可以替產品決定「這兩個案例是否代表同一種穩定工作」。
- 若真實 transcript 顯示模型頻繁 over-insert／over-update，才用固定失敗案例重開 LangMem／Trustcall 或其他 collection editor 評估；不能為了 API 相似先加入第二 writer。

#### 15.15.7 Owner 對齊與下一題

Owner 於 2026-08-28 暫定接受方案 C：**active 關係只保留 `supported_by` 與 `about`，每個 record ref 同時 pin stable ID 與 exact version；同一 identity 用 revision chain，只有 split／merge 才保留 `derived_from` lifecycle lineage。員工更正先把直接依賴的 Pattern／Unresolved 列為最小候選影響範圍，再由顧問依新訊息的實際語意決定是否擴大；不得全域 invalidation，也不得由 application 自動改寫語意。**

這仍可由真實 transcript 推翻，尤其是 direct dependency 頻繁漏掉跨案例影響、relation 維護成本高於節省的 Context，或成熟框架能完整替代同目的機制。下一題不再擴張 relation graph，而是研究**初次 recall**：當新訊息沒有任何 ID／Focus anchor 時，如何低成本找到可能相關的工作理解。

### 15.16 沒有 ID／Focus 的新訊息如何找回相關工作理解（目前基線，可推翻）

#### 15.16.1 這是 recall 問題，不是 persistence 問題

§15.11–§15.15 已回答工作理解保存什麼、如何版本化，以及已知 Case 更正後哪些 Pattern 是直接依賴者；但尚未完整回答一個更早的步驟：員工只說「那個月報其實是主管做的」或「剛才那個網站我是做需求，不是實作」，訊息沒有 stable ID，也可能不在目前 Focus，顧問如何先找出可能相關的 Case／Pattern？

若把所有歷史、所有 records 與所有來源每輪全傳，recall 可能提高但成本與注意力污染一起增加；若只靠 exact ID／Focus，長訪談會漏掉跨題更正。這個缺口不能由 §15.15 的 dependency graph 倒推解決，因為必須先辨識員工正在談哪個 record，才知道從哪條 relation 開始。

#### 15.16.2 最新官方資料支持「少量前置導航＋同一 agent 即時探索」

- [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 把目標定為每次 inference 使用最小的高訊號 Context，並明確描述 hybrid 策略：少量資料 upfront 取得速度，再由 agent 以 identifier、file path、stored query 與工具 just-in-time 探索；Claude Code 是 root instructions upfront、`glob／grep` 即時讀取的實例。官方同時建議先做最簡單可行方案，而不是預先建立複雜索引。
- 最新 [Claude Code Memory](https://code.claude.com/docs/en/memory) 讓精簡 `MEMORY.md` index 常駐，詳細 topic files 不在啟動時載入，模型需要時才以標準檔案工具讀取。這支持「可掃描目錄＋詳細 records 按需載入」，但不代表 Caliburn 應把工作理解改存 Markdown。
- OpenAI 於 2026-08-19 發布的 [Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform) 把 reusable harness 定義成維護 Context、檢查相關資訊、呼叫 Tools、跨 turn 推進、呈現進度與請求人類核准；同時明確保留 host application 的 editor／records／approval flow、可見資料與 system-of-record 邊界。這支持「沿用成熟 agent loop＋由 Caliburn 定義 Work Understanding」，不支持把 Codex 的 coding state 名稱照搬成職務語意。
- 最新 [Codex Skills](https://learn.chatgpt.com/docs/build-skills) 本身採 progressive disclosure：啟動時只有名稱與 description，選中後才讀完整 `SKILL.md`；初始 Skills catalog 還有明確 Context budget。這是「小型可匹配目錄＋命中後載入全文」的直接產品實例，可類比 Work Understanding recall，但 Skill description 是人工定義的能力入口，不能直接證明自動語意配對永遠正確。
- 最新 [Codex Memories](https://learn.chatgpt.com/docs/customization/memories) 把 required guidance 留在 `AGENTS.md`／checked-in docs，把 summaries、durable entries、recent inputs 與 supporting evidence 放在另一個 generated recall layer；背景 memory 會等 chat idle 後才更新，也可能為節省額度略過。這再次證明 generic memory 適合幫助 recall，不適合承擔 Caliburn「本輪就要支撐 JD」的 hot-path Work Understanding authority。
- [Codex `AGENTS.md`](https://learn.chatgpt.com/docs/agent-configuration/agents-md) 由 root 到目前目錄分層載入、預設有總 byte budget，並建議把特殊規則放在最接近適用範圍的位置。這支持 scoped Context 而非無條件全量注入；它是 instruction discovery 機制，不是 Case／Pattern search 演算法。
- 最新 [OpenAI GPT-5.6 Model Guidance](https://developers.openai.com/api/docs/guides/latest-model) 建議優先採成熟 hosted tools／Agents SDK，內部 business workflow 才使用 custom function tools；大型 Tool catalog 用 tool search 延後載入 definitions。這是 progressive disclosure 的佐證，但 **tool search 搜尋的是 Tool schema，不是工作理解資料**，不能誤當 memory retrieval。
- 同一份 GPT-5.6 指引的 OpenAI internal coding-agent runs 顯示，精簡重複 instructions／Tool descriptions 的組態在該樣本同時改善分數並大幅降低 tokens／成本；官方也要求把數字只當方向、回到代表性工作驗證。這支持先減少常駐 Context，不足以單獨決定本產品的 record 數量或 token 門檻。
- OpenAI [Compaction](https://developers.openai.com/api/docs/guides/compaction) 能在長互動中以 opaque compaction item 帶回先前關鍵 state、平衡品質／成本／延遲；它不提供可供產品檢查的 Case／Pattern／source revision。Caliburn 可把它留作 provider adapter 的長 Tool-loop transport，但不能拿它取代 hot-path typed Work Understanding 或員工來源。
- OpenAI [Vector Store Search](https://developers.openai.com/api/reference/python/resources/vector_stores/methods/search) 與 [LangGraph Store semantic search](https://docs.langchain.com/oss/python/langgraph/persistence#semantic-search) 都已提供成熟的 semantic search、filter 與 top-k primitive；它們證明方案可行，但需要 embedding／索引生命週期。Caliburn 的工作理解目前由 thread checkpoint 擁有，第一版若直接加入 Store semantic index，必須額外定義 derived index 重建、revision 刪除、local data／provider 與 RAG 邊界，不能只因框架有 API 就假設零成本。
- [LangChain Context Engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) 將錯誤 Context 列為 agent 失敗的主要來源，並以 middleware 動態選 messages／tools／response format；[Deep Agents Context Engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering) 與 [Backends](https://docs.langchain.com/oss/python/deepagents/backends) 已提供大內容落到 VFS、由模型用 `read_file／grep／glob` 分段取回的成熟 primitive。框架可承接 selector 與讀取機制，不會替產品決定「月報」對應哪項工作模式。

#### 15.16.3 三種方案比較

| 方案 | 效果 | 成本／風險 | 裁決 |
| --- | --- | --- | --- |
| A. 每輪載入所有 Case／Pattern／Unresolved／來源 | 小資料時 recall 最直接 | 長訪談線性增長，會擠壓本輪訊息、Skill、JD 與輸出；高 token 不等於高注意力 | 不採 |
| B. 每輪先跑 router／embedding retrieval，再把 top-k 交給主顧問 | 大規模資料可提高模糊語意搜尋 | 固定多一個模型或索引路徑；top-k 可能漏關鍵項；checkpoint→index 的 revision／刪除一致性與 RAG 邊界尚未有真實失敗驅動 | 保留為證據觸發的升級，不作第一版 |
| C. 完整但精簡的導航目錄＋deterministic anchors＋同一主顧問按需 `grep/read` | 同一個懂上下文的顧問可先以語意看目錄，再讀精確 record／source；無固定額外模型與第二 owner | 仍須明定目錄內容、讀取 budget 與「找不到時不猜」；超大目錄未來可能需 semantic search | **Owner 暫定接受** |

#### 15.16.4 方案 C 的具體 Context 行為

1. 每輪 L1 先帶本輪員工原文、最近必要對話、Focus、required input／open 計數、JD delta，以及 **current Pattern 與 active Unresolved 的精簡目錄**。每個目錄項只含 stable ID、current revision、短標題、一行完整語意、coverage／relation 計數；不含完整案例、來源或歷史。
2. 尚未歸到 Pattern 的 current Case／線索必須在「未定位」目錄有短 handle；不能因沒有分組就在導航中消失。已歸組 Case 不常駐 L1，而由各 Pattern 的唯讀 topic resource 列出 ID、revision 與短標題。
3. middleware deterministic 預載明確 anchors 的完整 L2：Focus、required input `about` refs、pending JD basis、員工直接編輯的 JD delta basis、最近修訂 record 與 §15.15 direct dependents。這些不需要模型猜。
4. 沒有 anchor 時，**主顧問本身**先用本輪語意對精簡目錄判斷；可能相關就以現有 Deep Agents `grep／read_file` 讀 pattern topic、Case、Unresolved 或 source。這是同一 agent loop 的按需 Tool continuation，不增加固定 router／critic／memory model。
5. 根目錄若超過明定 L1 token budget，不得靜默截斷後假裝沒有其他理解；L1 改帶 counts、當前／近期／未定位／active unresolved 與可搜尋入口，顧問在宣告「新工作」或改寫既有 Pattern 前至少做一次 bounded index search。具體 token 門檻由 implementation 的 provider budget 測量，不在 domain schema 硬編 Claude 的 200 行／25KB。
6. 若仍無安全 match，不能把最相近結果硬接上：可建立未定位 Case／線索、保留一般待釐清，或只有在後續無法安全分析時進「需要你的確認」。這與一般顧問面對模糊指稱的行為一致。
7. 任何 revise／retire effect 仍須引用工具實際讀到的 exact current revision，通過 optimistic read-set；目錄命中只決定「值得讀哪裡」，不能直接成為更新 basis。

#### 15.16.5 為何暫不啟用 semantic search

這不是判定 embedding／RAG 過時或不好，而是遵守目前「先完成核心、RAG 後談」與成本約束。當下 collection 是單一員工／單一 JD 的 typed records，已具 Pattern 目錄、關係、Focus、recent source 與 VFS；先使用成熟的 middleware＋VFS progressive disclosure，能直接覆蓋大多數精確與語用 recall。

只有出現下列可重現證據才重開方案 B：完整導航常態超出 Context budget、固定長訪談反覆漏找語意相關舊 Case、同義表達讓 bounded `grep/read` 無法恢復，或 Tool continuation 的成本／延遲高於 semantic index。屆時優先評估 LangGraph Store 現成 semantic search 作**可由 checkpoint 重建的 derived index**，而不是新增權威；仍須與本專案延後的 RAG／本機資料政策一起決策。

#### 15.16.6 Owner 對齊與下一題

Owner 於 2026-08-28 暫定接受方案 C：**小型 navigation catalog 常駐、明確 refs deterministic 預載、沒有 refs 時由同一主顧問用現有 VFS 按需找；找不到就保留未定位／追問，不猜。第一版不固定增加 router model、embedding 或第二 Store index。**

這不是永久排除 semantic search；只有真實長訪談出現可重現的 recall／budget／latency 失敗，才以可重建 derived index 形式重開。下一題回到工作理解的職務語意核心：**具體 Case 何時足以形成或修訂穩定 Pattern，如何避免太早泛化，也不要求同一工作一定先累積多個案例。**

### 15.17 具體 Case 何時可形成穩定 Pattern（目前基線，可推翻）

#### 15.17.1 先分清員工說的是「角色常態」還是「某次事件」

同一則 employee turn 可能直接表達角色常態，也可能只描述一次經驗：

- 「我每個月負責彙整部門月報」已直接聲明目前角色、責任與週期；
- 「上週主管請我幫忙整理一次月報」只證明一個具體事件，不足以宣稱這是員工的穩定責任；
- 「去年替 A 客戶做購物網站，最近又替 B 客戶做形象網站」提供兩個案例，但仍未回答這是持續接案型職責，還是恰好做過兩個專案。

因此不能把「一則訊息」等同「一個 Case」，也不能把「一則訊息」一律直接升成 Pattern。模型需要保留員工實際表達的語意層級：直接角色陳述可成為目前 Pattern 的來源；一次事件先成為 Case；不確定它是否代表常態時建立相關 Unresolved，而不是猜。

#### 15.17.2 權威資料支持判斷式門檻，不支持固定案例數

- [OPM Assessment and Selection](https://piv.opm.gov/policy-data-oversight/assessment-and-selection/) 把直接、最新的職務經驗者視為 SME，要求工作分析辨識 Tasks、roles、responsibilities、resources、context 與 competencies；critical incidents 則只是描述重要工作行為的具體**例子**。這支持區分「目前角色陳述」與「事件案例」，沒有要求單一職務必須先收集固定數量事件才能形成理解。
- [OPM Job Analysis FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/when-conducting-a-job-analysis-do-i-have-to-collect-ratings-eg-importance-required-at-entry-from-the-subject-matter-experts-sme-for-the-tasks-and-competencies/) 明確說方法取決於 incumbents／supervisors 數量、既有資訊新舊與職務是否改變；無論是否收 rating，都要有支持 Task／KSA 重要性的證據。這否定把某一份群體研究的固定樣本門檻硬套到單一員工客製 JD。
- O*NET 2025 [Identification of Emerging Tasks: Revised Approach](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf) 在建立**整個 occupation 共通**的新 Task 時，要求兩筆 overlapping write-ins，並由分析師覆核 NLP 的 duplicate／overlap 判斷；但同份方法也保留沒有 overlap、仍寫得清楚的 stand-alone statement 供後續 SME review。其「兩筆」是 occupation publication policy，不是 LLM memory 的普遍真理，也不能推導員工明確說「這是我每月固定工作」仍必須再舉第二例。
- 同份 O*NET 方法要求建立 Task 時比較既有內容、找 write-ins 的共通與差異，抽取 action、object、purpose/result、enabler、context，做到「足夠廣以涵蓋一般活動、又足夠具體以描述行為」，並避免把不相關活動塞成 double-barreled Task。這直接支持 Pattern 對既有 Pattern 先做 duplicate／overlap／new 判斷，但 Pattern 本身仍不是正式 Task。
- O*NET 的 [Task Analysis](https://www.onetcenter.org/dl_files/TaskAnalysis.pdf) 明確不建議只用頻率決定是否保留 Task，因為低頻工作仍可能非常重要。因此年度稽核、重大事件處理等，只要員工明確說是角色責任，不應因只有一個案例或一年一次就被排除。
- [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 區分 semantic facts／concepts 與 episodic experiences，並說 collection 在 recall 上有優勢但模型可能 over-insert 或 over-update。它提供保存／修訂 primitive，沒有提供「兩個案例才算 Pattern」的 domain gate；Caliburn 必須用職務分析規則約束同一 collection 的 Case／Pattern effects。
- 最新 [OpenAI Model Guidance](https://developers.openai.com/api/docs/guides/latest-model) 要求提供 domain context、hard constraints、approval boundaries，並明定重要歧義何時應提問；[Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform) 則把 Context、Tool、approval 與 system-of-record 留給 host application。這支持讓主顧問先讀現有理解、必要時追問、再提交 typed effect，不支持用 coding harness 發明職務歸納門檻。
- [Codex Long-running work](https://learn.chatgpt.com/docs/long-running-work)、[Codex Memories](https://learn.chatgpt.com/docs/customization/memories)、[Claude Code Memory](https://code.claude.com/docs/en/memory) 與 [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 共同支持同一長工作保持持久狀態、把詳細內容按需讀回並從更正更新記憶；它們沒有判定某次員工事件是否代表角色常態。可轉移的是記憶／Context 機制，不是職務語意。

#### 15.17.3 三種方案

| 方案 | 優點 | 問題 | 裁決 |
| --- | --- | --- | --- |
| A. 每一則明確工作敘述都直接建立 Pattern | 立即可供 JD 分析，流程最短 | 臨時支援、特殊事件與他人工作容易被永久一般化；Pattern 膨脹 | 不採 |
| B. 固定累積兩個以上案例或要求一次專門確認才建立 Pattern | 保守、容易寫 deterministic count | 把 occupation-level O*NET publication 門檻誤套到單一員工；明確月例行／年度關鍵工作也被無謂延遲；訪談問卷化 | 不採 |
| C. 依員工陳述的語意層級與支持來源判斷，無固定案例數 | 直接角色陳述可立即成為可修訂 Pattern；事件不會被過早泛化；低頻高重要工作不漏掉 | 仍需主模型做 typicality／ownership／scope 的語意判斷，需有清楚例子與 deterministic 邊界 | **Owner 暫定接受** |

#### 15.17.4 方案 C 的白話規則

1. **員工直接說明角色常態**：只要目前時間範圍、本人責任與工作語意足夠清楚，一則來源就可以新增或修訂 Pattern；不要求再湊第二個案例。Pattern 仍是 AI 可修訂的目前理解，不等於員工核准 JD；細節不足時 coverage 顯示「待補充」。
2. **員工描述一次事件**：先保存 Case。它可以成為既有 Pattern 的支持案例；若要建立新的 Pattern，至少還要有員工對一般性／角色責任的直接說明、多個一致案例且無反證，或針對典型性追問後的確認。
3. **一般性不明**：保留 Case＋具體 Unresolved，例如「這是固定責任、週期性工作，還是臨時支援？」；若不影響當下安全分析，留作一般待釐清，不強迫 interrupt。
4. **低頻不等於偶發**：員工明確負責年度申報、災害應變或重大稽核時，可直接形成 Pattern；是否進 JD 由重要性、責任與結果判斷，不用頻率門檻。
5. **先比既有 Pattern**：新內容若完全被既有 Pattern 涵蓋，只新增／修訂支持 Case 或細節；若有新 nuance 就修訂 Pattern；只有語意邊界真的不同才新增 Pattern。相似度只可找候選，最終由主顧問讀完整內容判斷。
6. **Pattern 與 JD gate 分開**：成立 Pattern 只代表目前工作理解已足以表達一項角色工作；要不要立刻修改 JD，仍由 Task／Duty／OPKS Skills 比較 validated Pattern、支持案例、目前 JD 與 pending workspace。不得把每個 Pattern 機械變成一條 Task。

第一版不新增 `provisional_pattern`、`confidence score`、`case_count_threshold` 或另一個 classifier model。既有 revision、`待補充／目前足夠` coverage、Unresolved、source／quote 與 `supported_by` 已能表達「目前成立但仍可補充／推翻」。模型提出 Case／Pattern typed effects；application 只驗 source、quote、record type、exact revision、relation 與 transaction invariant，不能用程式碼假裝驗證 typicality。若同輪新 Pattern 會支撐 JD edit，仍沿用 §15.4 的 understanding Tool receipt，再由同一 product run 繼續；不固定多一次模型呼叫。

#### 15.17.5 例子

| 員工說法 | 工作理解處理 | 是否能立即形成 Pattern |
| --- | --- | --- |
| 「我每月負責彙整部門月報，交主管確認」 | 直接保存角色常態；細節不足可另留待釐清 | 可以 |
| 「上週主管臨時請我幫忙整理月報」 | 保存 Case；不要假定固定責任 | 不可以 |
| 「去年做 A 網站，最近做 B 網站」 | 保存兩個 Case；詢問固定標的或持續接案 | 尚不可以 |
| 「我們有客戶就由我負責前端需求、實作與測試；A、B 是最近兩案」 | 建／修訂接案型前端 Pattern，A／B 作支持案例 | 可以 |
| 「每年一次由我主責年度勞檢資料彙整」 | 保存低頻但固定的 Pattern | 可以 |
| 「有時會幫同事處理申訴」 | ownership／責任邊界不明，保存 Case／Unresolved | 尚不可以 |

#### 15.17.6 Owner 對齊與下一題

Owner 於 2026-08-28 暫定接受方案 C：**不數案例，而是區分直接角色陳述與事件案例。明確、目前、屬於本人角色的常態陳述可由一則來源形成可修訂 Pattern；一次事件先保留為 Case，只有已有一般性支持才歸納；低頻工作不因頻率被排除；成立 Pattern 也不等於立即生成 Task。**

這項基線仍可由固定 transcript 推翻，尤其是直接角色陳述經常被誤讀為常態、Case 長期無法被歸納，或 Pattern churn／漏掉低頻高重要責任。下一題須從最新研究稿找真正仍未收斂的核心邊界，不由實作者自行把舊 schema 補回來。

### 15.18 三種工作理解角色的最小 production shape（internal shape 沿用；provider wire 已由 §15.20 取代）

> 本節保留 15.18.1–15.18.4 的 internal domain 診斷與三種語意角色；15.18.5–15.18.7 的 flat provider-wire 裁決是歷史脈絡，不再是施工規格。

#### 15.18.1 文件稽核發現：產品語意已收斂，施工 schema 尚未同步

§15.11–§15.17 與 ADR 0071 已收斂為同一份 Work Understanding collection 內的 Case／Pattern／Unresolved，但現行實作計畫仍保留已撤回的 `WorkScope＋atomic item＋facets` 與 `kind＋text` 草稿。ADR acceptance gate 又寫成「後續精確 schema 已取代」，造成表面上已定稿、實際施工仍 blocked 的矛盾。

真正尚未定義的不是新的產品概念，而是三個窄邊界：

1. 語意角色與 lifecycle 是否混在同一個 `status`；
2. 三種角色哪些 relation 合法，哪些欄位不得出現；
3. 內部 domain schema 與 provider strict wire 是否必須長得完全一樣。

這些若不先裁決，實作者很可能重新引入 `CURRENT／UNRESOLVED／CONTRADICTED／UNLOCATED` 混合 enum、自由文字 `kind`，或為了「精確」把工作理解拆回 JD-like facets。

#### 15.18.2 最新框架／大廠資料能決定什麼，不能決定什麼

- [Pydantic discriminated unions](https://pydantic.dev/docs/validation/latest/concepts/unions/) 官方推薦以 discriminator 明確選擇 variant，因為比 untagged union 更可預測、驗證更有效率，也會產生標準 discriminator schema。這支持 internal domain 採 Case／Pattern／Unresolved tagged variants。
- [OpenAI Model Guidance](https://developers.openai.com/api/docs/guides/latest-model) 建議把精確 output schema、必要 evidence、Tool return fields、錯誤與停止條件寫清楚；Structured Outputs 可保證輸出符合 schema，但不能替產品判斷「這是一則事件還是穩定角色責任」。
- Anthropic 最新 [Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use) 明確指出 JSON Schema 能表達型別、required fields 與 enums，卻不能表達何時使用 optional 參數、哪些組合有意義；正確用法仍需清楚描述與 examples。[Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) 也要求 Tool 邊界清楚、參數無歧義、回傳高訊號 Context，並避免重疊工具。
- [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 支持 collection 以降低整份 profile 更新時的遺失，亦警告 collection 的 update／delete、搜尋與跨紀錄關係較難。框架承接 checkpoint／collection primitive，不會替 Caliburn 定義 role relation。
- [Codex Memories](https://learn.chatgpt.com/docs/customization/memories) 把 summaries、durable entries、recent inputs 與 supporting evidence 分層保存，且明確說 memory 是 recall layer，不是必須遵守規則的唯一 authority。可轉用結論是「目前內容、來源／依據與規則分層」，不是照搬 Codex 的本機檔案 shape。
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) 的 revision／derivation 原則支持 stable identity、版本與實際依賴分離；不支持只因同輪曾讀過就建立任意關係。

因此以下 schema 是把成熟 framework primitive 與本產品已核准語意結合後的 **Caliburn 產品推論**；沒有任何大廠框架可直接提供職務理解的 Case／Pattern／Unresolved 欄位。

#### 15.18.3 三種方案比較

| 方案 | 優點 | 問題 | 裁決 |
| --- | --- | --- | --- |
| A. 一個平面 record：`role＋status＋content＋所有 relations` | wire 最小、程式容易開始 | 合法組合靠散落 if 判斷；`UNRESOLVED` 同時像 role 又像 status；Case 可能錯帶 `about`，Pattern 可能錯帶 Pattern→Pattern | 不採作 internal domain |
| B. 每種角色拆成完整職務 facets | 欄位看似最精確，方便個別查詢 | 把尚未分析內容提前切成 activity／outcome／context 或 Task-like schema；重複 `content`、容易遺失完整關係，並放大 provider schema | 不採 |
| C. **共同 application-owned envelope＋role-discriminated semantic payload；provider wire 另維持扁平** | internal domain 能精確驗證合法組合，語意內容仍完整；wire 不必承擔大型 `anyOf` | 需要一個很薄的 boundary mapper／validator | **Owner 暫定接受** |

#### 15.18.4 推薦 internal domain shape

```text
共同 envelope（application-owned）
  record_id
  version_id
  lifecycle: active／superseded／retired
  supersedes_version_id
  derived_from_version_ids       # 只有真正 split／merge record boundary
  role discriminator
  role payload

Case payload
  content                        # 完整、語意自足的某次工作案例
  source_quote_refs: 1..N

Pattern payload
  content                        # 完整、語意自足的目前穩定工作模式
  source_quote_refs: 0..N        # 員工直接說明常態時可直接支持
  supported_by: 0..N CaseVersionRef
  invariant: direct source 與 supported_by 至少一種成立

Unresolved payload
  content                        # 缺少什麼、歧義或不能安全並存之處
  source_quote_refs: 0..N
  about: 0..N Case／Pattern VersionRef
  invariant: 純資料缺口或尚未定位線索可以兩者皆 0
```

`content` 仍是唯一職務語意主體；不重抄 activity、outcome、context、responsibility facets，也不含 Duty／Task／OPKS 欄位。role 在同一 stable identity 內不可變：Case 之後支持 Pattern，是**保留 Case 並新增／修訂 Pattern**，不是把 Case 的 role 改成 Pattern。若原 record boundary 本身判錯，才用 create／retire 與 `derived_from_version_ids` 重整。

role 與 lifecycle 必須分開：

- `case／pattern／unresolved` 回答「這筆語意是什麼」；
- `active／superseded／retired` 回答「這個版本現在是否仍生效」；
- `current` 是 stable ID 所指的目前 active version，不是另一種 semantic status；
- `contradicted` 由一筆 Unresolved 描述衝突並以 `about` 指向受影響 records，不把被指向內容直接宣告錯誤；
- `unlocated`、`needs_reconciliation`、coverage 與 Orientation 都是可由 current collection 重建的 projection，不寫回 authority；
- Unresolved 回答後，以 retire／supersede 結束，不再增加 `resolved` writer。

#### 15.18.5 provider strict wire 舊候選（已由 §15.20 取代）

內部 Pydantic 可使用 discriminated union；送給模型的 effect Tool 則維持一個扁平、低 `anyOf` 的 operation shape：

```text
operation
record_role
record_id／expected_version_id／local_ref
content
source_basis_ordinal
supported_by_refs[]
about_refs[]
derived_from_refs[]
```

所有陣列皆 required，沒有資料就送空陣列；application 依 `record_role` 轉成 internal variant，驗證 role-specific invariant 後才原子提交。例如 Case 帶 `about_refs`、Pattern 既無 direct source 也無 Case support、或 Unresolved 指向 Unresolved 都會得到精簡 typed diagnostic，讓同一顧問在有限 repair budget 內修正。

這個分層不是自寫第二套 schema：Pydantic domain model 是 authoritative invariant，flat wire 只是 provider compatibility boundary。JSON Schema／Structured Outputs 負責「形狀正確」；Tool description 與少量正反 examples 說明「何時用哪個 role／relation」；application deterministic gate 驗 relation direction、exact revision、source closure 與 lifecycle；典型性與職務語意仍由主顧問依 §15.17 判斷。

#### 15.18.6 成本與避免過度設計

第一版不新增：

- `work_scope_id`、facets、confidence、case count、pattern classifier；
- `contradicted／unlocated／needs_reconciliation` 持久 status；
- generic graph edge、Pattern→Pattern、Unresolved→Unresolved；
- 第二模型、第二 memory manager 或另一個 Store；
- 專用 split／merge Tool。

模型仍以低階 create／revise／retire＋refs 組成原子 batch；LangGraph checkpoint 持久化，Pydantic 驗證，現有 VFS 提供按需 context。這讓新增的 Caliburn code 只剩 role-specific invariant 與 boundary mapper，不重寫框架已提供的持久化／恢復／typed validation。

#### 15.18.7 Owner 對齊與下一題

Owner 當時暫定接受方案 C；其 **internal domain 採共同 envelope＋Case／Pattern／Unresolved variants、語意角色與 lifecycle 分離、`content` 不拆 JD facets** 的部分仍有效。後續欄位稽核發現 flat all-required wire 會把非法 role／operation 組合、空值 sentinel 與 application 已知欄位交給模型，因此 provider-wire 部分已由 §15.20 取代。

本節的 internal shape 已同步 ADR 0071；實作計畫中的 `WorkScope＋atomic item`、混合狀態 enum、舊 `kind＋text` snippets 與 flat effect wire 均視為 blocked 舊稿。provider Tool 必須依 §15.20 重寫；在此之前仍不施工 production code。

### 15.19 是否另建 model-owned 訪談 Agenda（目前基線，可推翻）

#### 15.19.1 為什麼現在必須重新裁決

現行產品語意已能回答四件不同的事：

- Pattern 保存目前成立、可修訂的穩定工作模式；
- Unresolved 保存一般待釐清、矛盾與未定位線索；
- Focus 只保存目前訪談注意力書籤；
- coverage 由 current Pattern basis 投影「待補充／目前足夠」。

舊 runtime／計畫仍出現 `InterviewWorkItem`、Agenda／Todo 或「進行中／完成」工作項目。若再引入框架的 Planning，必須先證明它承接一個上述四者沒有承接的產品目的；不能只因框架功能成熟，就同時保存一份「還要做什麼」清單，讓同一待釐清事項又存在 Unresolved、Focus 與 Plan task 三處。

#### 15.19.2 先更正舊版本事實：最新版 Pydantic Planning 已大幅補強

本專案較早的框架決賽研究曾依 Pydantic AI Harness 0.13.0 實查，判定 Planning 沒有 stable item ID、dependency 與 durable store。這個版本事實現在已過時。最新版官方 [Pydantic AI Harness Planning](https://pydantic.dev/docs/ai/harness/planning/) 已提供：

- model-owned、自我更新的 structured task list；
- stable task ID、`pending／in_progress／completed／cancelled`，可選 `blocked`；
- subtasks、dependencies 與可執行項目查詢；
- SQLite／Postgres／Redis store、跨 run handoff 與 granular events；
- 每次 model request 以 cache-safe tail reminder 注入目前 plan；
- 預設六個 Tool，開啟 subtasks 後再增加三個，亦可 allowlist 縮減。

同一官方頁也明示 Harness 仍在 0.x，minor release 之間可能改 API；persistent reminder 每次 model request 都讀 store，store 失敗會使 run 失敗。這些不是否決理由，但代表採用它會真正新增一個 writer、storage contract、Tool surface 與 failure boundary，不能把它描述成免費 UI projection。

#### 15.19.3 官方資料實際支持的使用情境

- Pydantic 把 Planning 定位為解決 **long agentic run 漂移**：模型有一組明確任務要完成，需要記得進度、依賴與剩餘步驟。範例是重構模組、先規劃再交給另一個 executor，不是探索式員工訪談。
- Anthropic 的 [Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 也把 todo／structured notes 放在「數十分鐘到數小時、具有清楚里程碑」的長期 agent 工作；同文同時警告 Tool 集過大或功能重疊會增加模型選擇歧義，並建議採最小高訊號 Context、just-in-time retrieval 與「do the simplest thing that works」。
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 已能以 checkpointer 保存 thread-scoped graph state、interrupt、conversation continuity 與 fault recovery；state 內容仍由 application 定義。它足以保存 Focus、Work Understanding 與 required input，但不會要求再建 task list。
- [Microsoft Agent Framework HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) 的 request／response primitive 解決「執行到必須外部回答時暫停並恢復」，同樣不等於一般待釐清 Agenda。

因此「成熟框架已有 plan」只能證明方案 A 可實作，不能證明 Caliburn 的探索式訪談需要把未知事項改造成 agent execution tasks。以下適配判斷是根據官方能力與本產品目的形成的 **Caliburn 推論**，不是任一家 vendor 對職務訪談的既定規範。

#### 15.19.4 三種方案

| 方案 | 優點 | 問題 | 判斷 |
| --- | --- | --- | --- |
| A. 採 Pydantic Planning 作可寫訪談 Agenda | stable ID、dependency、store、events、cache-safe reminder 都已有成熟 primitive | 同一未知會同時出現在 Unresolved／plan；Focus 與 `in_progress` 競爭；每次 model step 多一份 plan Context；增加 6～9 Tools、第二 persistence／failure boundary；容易把可改道訪談變成 checklist | 不推薦第一版 |
| B. 從 Work Understanding 派生 plan，再同步回 Planning | UI 可看熟悉的 task list，又保留理解 authority | Planning 的 model-owned writer 優勢被取消；仍要處理雙向同步、ID／status mapping 與 stale，功能上只是較昂貴的 projection | 不採 |
| C. 不建獨立 Agenda；沿用單一語意 authority | Pattern／Unresolved／Focus／coverage 各有單一責任；沒有重複 writer；Context／Tool／維護成本最低；訪談可隨新線索改道 | 沒有一份通用「步驟 1、2、3」清單；需由顧問在每輪從導航目錄選下一個焦點 | **推薦** |

#### 15.19.5 推薦方案 C 的具體產品行為

1. 不新增 `InterviewWorkItem`、`AgendaItem`、`PlanTask` 或另一個 planning store；Pydantic Planning 不進第一版 production dependency。
2. 一般「還需要知道什麼」保存成 Unresolved；已問但尚未回答，也保存 underlying Unresolved，不另存 durable question queue。實際問句仍在 conversation history。
3. `需要你的確認` 仍用 LangGraph interrupt；它只處理不回答就不能安全繼續的 blocking ambiguity，不進 plan status。
4. Focus 只指向目前深入的 Pattern／Unresolved／臨時查詢，不等同 `in_progress`，員工改話題時可直接換。
5. 每輪由同一主顧問讀目前 Focus、小型導航目錄、active Unresolved、coverage 與本輪訊息，選擇繼續、改道、追問或整理 JD；不需要固定 planner node 或第二模型。
6. UI 顯示「目前訪談重點」「待釐清」「待補充／目前足夠」「未定位線索」「需要你的確認」與待審數，不顯示 agent 自己的 todo checklist 或假完成百分比。
7. Pydantic Planning 只在未來出現**不同產品目的**時重開，例如有一段可明確列步驟、長時間自主執行、跨 run 仍需 dependency／completion 的批次工作。若只是訪談中尚未理解的問題，仍不可因此重建 Agenda。

這個方案不是拒絕成熟框架，而是把框架用在其真正相符的機制：LangGraph checkpointer 承接 durable thread state／interrupt／resume；Pydantic 承接 typed variants；Context middleware／VFS 承接按需載入。Pydantic Planning 的能力已確認成熟，但目前沒有獨特產品責任可替換，因此加入反而會重複狀態。

#### 15.19.6 Owner 對齊

Owner 於 2026-08-28 暫定接受方案 C：**不增加獨立訪談 Agenda 或 Pydantic Planning；訪談導航完全由 current Pattern、active Unresolved、Focus 與 derived coverage 組成。** 本節已同步 ADR 0071。這個裁決仍可由真實長訪談證明需要一段具明確步驟、依賴與完成狀態的自主工作後，以 successor ADR 重開；一般待釐清本身不構成重開理由。

### 15.20 LLM 應填欄位與 Tool contract（目前基線，可推翻）

#### 15.20.1 為何重審 §15.18 的 wire

現行 `ConsultantModelOutput` 與 §15.18 flat effect 把四種不同責任混在模型輸出：職務語意、application 已知環境、framework 執行 receipt、員工審核狀態。即使 strict schema 能保證 JSON 形狀，模型仍會被迫抄 ID、猜 Skill、算 occurrence、填空字串／空陣列，再由 mapper 以跨欄位規則拒絕。已發生的中文 quote 位置錯誤與 `enabler_list` 錯置就是這種 ownership 錯配的具體證據。

[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 明確建議不要讓模型填 application 已知參數，並應把非法狀態設計成不可表示；[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 說明 schema adherence 仍不保證語意正確；[Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) 的限制是 Tool／optional／union 規模，而不是禁止所有 nested union；[LangChain Tools／ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools) 可把 runtime context 注入 Tool 且不暴露給模型。因此不能以「零 union」為目標，反而應優先減少模型不該負責的欄位。

完整量測、方案比較與來源見 [`2026-08-28-llm-authored-field-contract-audit.md`](2026-08-28-llm-authored-field-contract-audit.md)。

#### 15.20.2 Owner 已接受的責任分工

1. 員工可見回覆使用普通 assistant text，不再包進固定 structured root。
2. Work Understanding 只有確實新增／修訂／退役時才呼叫小型 atomic Tool；Tool 使用 role／operation-specific tagged variants，不使用 flat all-required dummy wire。
3. 模型只填它才能判斷的 `content`、必要 relation、exact quote 與真正需要員工確認的問題／選項；不填 stable UUID、revision、digest、status、timestamp、run ID、Skill receipt、diff、stale 或審核 decision。
4. current source identity 由 `ToolRuntime` 注入；application 對 exact quote 做唯一匹配。重複時回 typed diagnostic 要模型擴大 quote，不要求 occurrence、Unicode offset、trim、normalize 或 fuzzy match。
5. 實際載入的 Skill、版本、模型、token、context refs 與 Tool execution 只由 framework receipt 記錄；模型不得以 `skill_ids` 或改名欄位自報。
6. JD 維持 VFS／editor Tool；resource 只保存文件語意，不重複 path 已知 handle／kind、Evidence、Skill 或 application 可推導的預設排序。semantic review group 才保存一次短理由與 1～N 筆 Work Understanding basis。
7. 同一 provider response 可同時有 assistant text 與 Tool calls；runtime 先緩衝文字，Tool 成功後若沒有後續 JD 對 canonical result 的依賴即可結束，不固定多一次 model continuation。只有後續決策真的需要 Tool result 時才繼續。
8. 每個 authority stage 最多一次 validation-driven repair；第二次仍失敗就 rollback、解鎖並回可理解錯誤。schema 縮減優先於增加 retry。

#### 15.20.3 最小 Tool surface

- 一個 Work Understanding atomic Tool，內含小型 tagged variants；若實際 provider compile preflight 不支援，再依當輪可用 role 動態曝光 2～4 個更小 Tools。
- 既有 JD read／write／edit／delete VFS 能力；模型以低階操作組成新增、修訂、移動、拆分或合併，不新增每個 domain 動作一支專用 Tool。
- Focus 只有真正改變注意力書籤時才呼叫小型 Tool。
- `需要你的確認` 只有 blocking ambiguity 才呼叫；有選項與自由回答可用兩個合法小 schema，避免靠空陣列表示分支。
- Pattern coverage 只有相關 basis 改變且判斷改變時才提交 recommendation；application 保存可由 current understanding 重建的 basis-bound projection cache。

#### 15.20.4 下一輪與施工 gate

Owner 於 2026-08-28 接受本節並正式推翻 §15.18 的 flat all-required wire。下一輪只剩兩種不同工作：

1. 產品語意仍須審核 Header／Duty／Task／OPKS 哪些欄位真正由模型判斷，尤其 Task `statement` 與 `action／object／purpose_result` 的重疊、可選欄位與一個 Task 多筆 O／P／K／S 的最小寫入形狀；
2. 技術上須讓 authoritative Pydantic type 對實際 OpenRouter endpoint 做 compile／parse／strict-routing preflight，並驗證 tagged Tool 的 branch 數；若失敗，採 role-specific Tool fallback，不退回 dummy wire。

在 JD 領域欄位完成審核、實作計畫按本節重寫並由 Owner 複審前，不得施工 production code。

### 15.21 依最新 JD 與 Claude／Codex 重審 Work Understanding 最小 shape（研究候選，尚未取代 ADR 0071）

> **狀態**：本節只回答「長訪談中，LLM 要怎麼持續保留完整、可修訂的員工工作理解」。Owner 於 2026-08-29 **暫時同意三種責任邊界作為可推翻的研究方向**，但尚未核准名稱、精確 field contract、ADR 0071 改寫或 production 實作。`SemanticUnderstanding／WorkEpisode／OpenIssue` 在下一輪欄位審核完成前不得先寫入 production schema 或 Tool contract。

#### 15.21.1 先固定本輪產品邊界

最新核心 JD 已由 [`2026-08-28-llm-authored-field-contract-audit.md` §18](2026-08-28-llm-authored-field-contract-audit.md#18-caliburn-核心-jd-欄位與下游邊界最新研究owner-逐項可翻案同意) 收斂：第一版核心 JD、Web 編輯器與匯出都**沒有 A／能力級別**。Work Understanding 也不需要預先長成 JD：它是比 JD 更完整的職務知識，保存具體工作、穩定責任、情境、判斷、例外、尚缺資訊與修訂脈絡；JD 只在適當時機從中萃取可讀、可審核的正式文件。

本輪不能被下列舊形狀帶偏：

- 不能為了相容舊 `Work Model／Pattern／Gap` 名稱，先決定資料一定叫什麼；
- 不能把 Duty／Task／O／P／K／S、A 或 JD 欄位當 Work Understanding 必填 facets；
- 不能把 Work Understanding 寫成會持續縮短的一份聊天摘要；
- 不能因 Claude／Codex 是 coding agent，就照搬 `file／branch／todo／build status` 等 coding schema；
- 也不能只因某框架有 Memory，便把 generic recall store 當成職務知識 authority。

#### 15.21.2 Claude 與 Codex 實際怎麼處理相似問題

兩者公開設計雖然面向通用 agent／coding，但共同拆開了四種責任：

| 責任 | Codex 官方做法 | Claude 官方做法 | 可轉用到 Caliburn 的結論 |
| --- | --- | --- | --- |
| 完整歷史 | 同一 thread 的既有 messages／Tool items 會進後續 turn；長到門檻後才做 Responses compaction | Managed Agents 把 session 定義為外置、append-only event log；session 不等於 Claude context window | 員工逐字訊息與事件歷史要耐久、可回查，不能只剩摘要 |
| 持久記憶 | 本機 memories 分成 summaries、durable entries、recent inputs 與 supporting evidence；另有 extraction／consolidation model | Auto memory 以精簡 `MEMORY.md` 作入口，詳細內容拆 topic files，必要時才讀 | 工作理解不能是一個巨型 profile；應有小型導航目錄＋可按需載入的完整紀錄 |
| 當前 Context | Codex 把前序 items append 進 prompt，並刻意保持 prefix 穩定以利 cache；超限時 compact | Claude 建議最小高訊號 Context、progressive disclosure 與 just-in-time retrieval | 每輪只載入目前訊息、必要近期歷史、小索引、明確相關的完整理解，不全量灌入 |
| 壓縮 | Codex `/responses/compact` 產生可延續的 compacted items；官方仍把 durable memory 視為另一層 | Claude 先清舊 Tool results，再視需要摘要；Anthropic 明確警告過度 compaction 會丟失之後才顯得重要的細節 | compaction 只處理傳給模型的舊對話／Tool 噪音，不得改寫或取代完整 Work Understanding |
| 規則／權威 | Codex 官方明示 memory 是 helpful recall layer，必守規則仍放 `AGENTS.md`／checked-in docs | Claude 官方明示 CLAUDE.md／auto memory 是 Context，不是強制設定；強制行為交給 Hook／client | LLM 記得什麼與系統允許寫什麼必須分離；來源、版本、合法關係與 JD 核准由 application gate |

直接依據：

- [OpenAI — Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)：每個新訊息會帶入先前 conversation items；Codex 保持舊 prompt prefix 以利用 cache，超過門檻才用 Responses compaction 取代 transport Context。
- [OpenAI — Codex Memories](https://learn.chatgpt.com/docs/customization/memories)：memory 是可選 recall layer，不是唯一 authority；本機 memory 由摘要、durable entries、recent inputs 與 supporting evidence 組成，並區分 extraction 與 consolidation。
- [OpenAI — Long-running work](https://learn.chatgpt.com/docs/long-running-work)：相關工作保持在同一 chat，允許後續訊息持續補充／修改限制；長工作另保存清楚 outcome、constraints 與 review criteria。
- [Anthropic — Claude Code Memory](https://code.claude.com/docs/en/memory)：每個 session 都是新 context；`MEMORY.md` 只作精簡索引，詳細 topic files 按需讀；memory 是 Context，不是 enforcement。
- [Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)：目標是最小而足夠的高訊號 Context；Claude Code 以小型預載資訊＋`glob／grep／read` 即時探索；compaction、structured notes 與 Tool-result clearing 各有不同責任。
- [Anthropic — Managed Agents](https://www.anthropic.com/engineering/managed-agents)：session 是 context window 外的 durable event log，可重讀任意切片；harness 決定當輪如何轉換／選取 Context，避免不可逆摘要成為唯一歷史。

這些資料沒有提供「職務理解」現成 schema；以下是把共同機制與本產品職務分析目的結合後的 **Caliburn 推論**，不是宣稱 Claude／Codex 內部也使用同名物件。

也不能直接照搬兩者的 generic auto-memory lifecycle。Codex 官方說明會跳過仍 active／短暫的 session，等待 chat idle 後才背景產生 memory，額度接近門檻時也可能略過；Claude auto memory 則是可被模型讀取的 Context，不是強制 truth。這適合「未來可能有用的回想」，不適合作為 Caliburn 同輪 JD 分析所依賴的工作理解。Caliburn 應借用「原始歷史可回查、持久記憶分題、索引小而細節按需讀」的架構，但工作理解若要支撐本輪 JD change，仍須在同一 product run 經來源與 revision gate 提交。

#### 15.21.3 三個候選形狀

| 方案 | 優點 | 主要失敗模式 | 本輪判斷 |
| --- | --- | --- | --- |
| A. 一份持續覆寫的完整工作 profile | 全貌集中、第一次最容易實作 | profile 越大越容易整份改寫漏細節、來源粒度粗、局部更正造成無關內容 churn；LangChain 官方也警告大型 profile 更新會愈來愈 error-prone | 不採第一版 |
| B. 每句拆成原子 claim／triple graph | 來源與依賴最精細，局部 invalidation 容易 | 把完整工作流程切碎，模型必須填大量 relation／facet；Context 重組昂貴，容易失去整體語意，形成過度設計的知識圖譜 | 不採第一版 |
| C. **按工作主題保存的完整語意 collection，另保留具體事件與待釐清事項** | 每筆仍可自足地表達完整工作；局部修訂不必重寫整份 profile；比原子 claim 更能保留因果與情境；可用小索引按需讀取 | 需要處理 insert／update／retire、重疊與查找；若切分錯仍可能碎裂 | **推薦研究候選** |

[LangGraph／LangChain Memory](https://docs.langchain.com/oss/python/concepts/memory) 提供直接佐證：單一 profile 隨成長會變得難更新；document collection 的單筆範圍較窄、比較不容易遺失資訊，通常有較高 recall，但 update／delete／search 與跨紀錄全貌需要額外處理。這與 Claude 的「精簡 index＋詳細 topic files」及 Codex 的「durable entries＋supporting evidence」方向一致。

#### 15.21.4 方案 C 的最小語意角色

舊 `Pattern` 名稱可能太窄：回報關係、責任邊界、授權範圍、工作條件與角色目的都可能是穩定工作理解，卻不一定自然稱為「模式」。因此本輪只提出三個**可再改名**的角色：

1. **`SemanticUnderstanding`（目前成立的工作理解）**
   - 一個語意自足、可修訂的工作主題或角色事實；
   - 可寫完整流程、責任、判斷、情境、例外、產出與相關人物；不是一句摘要；
   - 必須有直接員工來源，或由具來源的 `WorkEpisode` 支持；
   - 不等於 Duty、Task 或 JD 欄位，也不保證立即編輯 JD。
2. **`WorkEpisode`（具體工作事件／例子）**
   - 員工曾實際做過的一次案例、案件、專案或特殊事件；
   - 必須連到 1～N 段逐字 employee source；
   - 不因發生一次就自動一般化成穩定責任。
3. **`OpenIssue`（尚待理解的問題）**
   - 缺少資訊、語意歧義、衝突或尚不能安全歸納之處；
   - 可引用相關理解／事件；純缺口可以沒有原句，因為「尚未知道」本來沒有 evidence；
   - 它是跨輪保留的未知，不是 agent todo、JD 缺欄清單或一定要立即 interrupt 的問題。

對員工 UI 仍可統一稱「AI 目前的理解／待釐清」，不必暴露這三個技術名稱。`Focus` 仍是 runtime bookmark；coverage／訪談概況仍是 derived projection，不是第四種語意紀錄。

#### 15.21.5 候選 internal shape：少欄位，但每筆內容要完整

```text
application-owned envelope
  understanding_id
  revision_id
  role
  lifecycle: active | superseded | retired
  supersedes_revision_id?
  created_at / updated_at
  payload

SemanticUnderstanding payload
  body                              # 完整、自足、多段文字也可以
  direct_source_refs[]              # 0..N
  supported_by_episode_refs[]       # 0..N；與 direct source 至少一種成立

WorkEpisode payload
  body                              # 完整具體事件，不強迫拆 facets
  source_refs[]                     # 1..N

OpenIssue payload
  body                              # 缺什麼／哪裡衝突／為何不能安全判斷
  source_refs[]                     # 0..N
  related_understanding_refs[]      # 0..N
```

Envelope 的 ID、revision、lifecycle、時間與 expected revision 仍由 application 產生／注入；模型只提交當次 `body`、exact quote 與必要 relation。`body` 可以在語意需要時包含觸發、輸入、動作、判斷、角色、工具、頻率、條件、結果與例外，但這些是分析 Skill 的寫作指引，不是每筆都必填的 provider 欄位。

第一版刻意不加入：

- `title`：小型導航目錄可先用 role＋`body` 首句／截斷預覽，若真實長訪談證明辨識困難再加入；
- Duty／Task／O／P／K／S IDs、A／能力級別、JD display order；
- confidence score、progress percent、coverage 欄、Focus、Skill IDs；
- source UUID、revision、timestamp 等模型已知不了的欄位；
- generic edge、任意 graph、固定拆分／合併 Tool；
- 另一份可寫 `WorkScope` 或第二 memory authority。

一般修正建立新 revision 並 supersede 舊 revision。若兩筆真的需要重切邊界，第一版可建立新 records、retire 舊 records；是否值得保存額外 `derived_from` 只在實際稽核／除錯證據證明有需要時再加入，不能因舊 ADR 已有欄位就自動保留。

#### 15.21.6 Context 組裝：完整保存，不代表每輪全量傳入

推薦的每輪 Context 是：

1. 主顧問指令、當輪允許的 Tools／Skills；
2. 員工本輪訊息與必要的近期對話；
3. 小型 Work Understanding 導航目錄：stable ID、role、目前 revision、短預覽；
4. Focus、active required input、pending JD basis、員工自上輪以來的 JD delta 等明確 refs 所指向的完整 records；
5. 主顧問再按需 `grep／read` 其他完整 records 或原始員工來源；
6. 只有對話／Tool trace 超出預算時才清理或 compact；完整 Work Understanding、員工來源、目前 JD 與 pending review 不 compact。

這不是 RAG：第一版可用 LangGraph checkpoint／Store 與現有 VFS 的 deterministic index、filter、read 完成。只有真實資料量證明目錄過大或 keyword recall 反覆失敗，才重開 semantic index；目前不接 RAG 的 Owner 決定不變。

#### 15.21.7 成熟框架能替代哪些機制

| 問題 | 優先用成熟元件 | Caliburn 仍需負責 |
| --- | --- | --- |
| thread durability、resume、interrupt | LangGraph checkpointer | 哪些 state 具有產品語意、員工核准邊界 |
| immutable conversation／source log、按 scope 查詢 | LangGraph Store／session log pattern | exact quote、source lineage 與本機資料權限 |
| semantic／episodic collection 的 create／update／delete | 先用同一主顧問的 typed effects＋LangGraph Tool loop；只有固定失敗證據才以 LangMem [`create_memory_manager`](https://langchain-ai.github.io/langmem/reference/memory/#create_memory_manager) 做窄 spike | 職務角色 schema、來源必備規則、revision 與原子提交；LangMem 不得成為第二 authority |
| typed variants 與 deterministic validation | Pydantic discriminated models | 職務語意是否正確不能由 schema 假裝證明 |
| 大型 structured object 的局部修補 | Trustcall 只列可選 fallback | 只有固定 transcript 證明整物件更新會漏欄才引入，不作預設依賴 |
| Context trimming／JIT read | LangChain middleware＋VFS／Store query | 小索引內容、明確 refs 預載規則、找不到時不猜 |

成熟框架應替換通用的 durability、Tool loop、validation、retrieval 與 repair 機制；它不能替產品定義「某句是穩定責任還是一次事件」、「什麼理解足以形成 JD」或「員工何時必須核准」。只有真實 transcript 顯示現行 reconcile 在資訊保留、錯誤更新、token、延遲或維護性上失敗時，才做 LangMem 窄 spike；不以少寫幾行 code 作唯一判準。

#### 15.21.8 壓力案例

| 訪談內容／事件 | 候選處理 | 不應發生 |
| --- | --- | --- |
| 「我每月彙整各組月報，交主管確認後發布」 | 一筆 `SemanticUnderstanding`，保存流程、頻率、核准與產出，連到原句 | 立即拆成 Task＋O＋P 或只留「處理月報」摘要 |
| 「上週臨時幫同事整理一次月報」 | `WorkEpisode`；必要時 `OpenIssue` 詢問是否固定責任 | 因一次事件直接變成穩定責任 |
| 「剛才說錯了，最後是處長核准，不是科長」 | 員工更正仍是一則普通新訊息；建立 understanding 新 revision，舊 revision 保留 lineage | 專門要求員工找原句按「更正」；或直接覆寫舊來源 |
| 「有時會幫忙處理申訴」 | 保留事件／目前理解並加 `OpenIssue`：是否本人固定責任、什麼條件下介入 | 強迫綁 Task，或虛構 frequency／ownership |
| 工具、判斷條件、例外很多，但核心 JD 不需要逐項顯示 | 細節全部留在 `SemanticUnderstanding.body`；JD Skill 再萃取 Task、outputs、criteria、K/S | 因 JD 欄位較少就刪掉工作理解細節 |
| 已有待審 JD change 依賴理解 revision 3，後來修成 revision 4 | pending change 的 basis stale，主顧問依最新理解重看／更新／撤回 | 悄悄接受舊 basis，或全域重算所有 JD |
| 員工直接編輯目前 JD | 保存 deterministic JD delta；下輪主顧問比較最新 JD 與工作理解，必要時追問 | 直接用 JD edit 改寫 Work Understanding，或把員工 edit 當 employee quote |

#### 15.21.9 與目前基線的差異及待 Owner 決定

本候選沒有推翻產品方向，只重審名稱與最小資料結構：

- `Case` 的目的保持不變，但 `WorkEpisode` 更直接表達「具體工作事件」；
- `Unresolved` 的目的保持不變，但 `OpenIssue` 更直接表達「跨輪仍待理解的問題」；
- `Pattern` 可能改成較廣的 `SemanticUnderstanding`，避免穩定角色事實被「模式」名稱排除；
- 共同 envelope、source-linked revisions、single authority、JIT Context、pending JD basis 與員工核准 seam 都不變；
- 第一版 JD／Web／export 仍不含 A／能力級別，RAG 仍不接。

Owner 已暫時接受把舊 `Pattern` 的產品語意擴成「目前成立的完整工作理解」，並以三種角色進入下一輪精確 field contract 研究；這不是永久裁決。ADR 0071 仍維持 Proposed，且在精確欄位、operation、Context 與成本邊界複審前仍保留 Case／Pattern／Unresolved 歷史名稱。名稱本身仍可換，真正已暫時對齊的是三種責任：**目前成立的完整知識、具體工作事件、跨輪未解問題**。

#### 15.21.10 追加框架成熟度稽核：相似能力不等於可以直接接管 authority

本輪再核對 LangMem、LangGraph、Deep Agents、AWS AgentCore Memory、Google Memory Bank 與 W3C PROV 後，框架邊界應收斂如下：

| 通用能力 | 第一版裁決 | 原因 |
| --- | --- | --- |
| thread state、resume、interrupt、step checkpoint | **直接使用 LangGraph checkpointer** | 這正是 LangGraph 的成熟責任；Caliburn 已採 PostgreSQL Saver，不應另寫 workflow persistence |
| immutable employee turns／Tool events | **沿用 LangGraph Store／append-only session log pattern** | 原始歷史與萃取後理解必須分層；來源不能被 memory consolidation 覆寫 |
| 小型目錄、`grep／read`、按需載入完整紀錄 | **使用 Deep Agents VFS 與 custom read-only projection** | 與 Claude Code／Anthropic 的 lightweight refs＋JIT read 一致；projection 不成為第二 truth |
| role／operation schema 與 deterministic parsing | **使用 Pydantic discriminated models** | 避免巨型 all-optional schema；application-known ID、revision、時間與 source handle 不交給模型填 |
| generic semantic／episodic extraction 與 consolidation | **LangMem 只保留為 evidence-triggered 候選，不在第一版接管** | API 目的相近，但它會再呼叫 memory model或讓 agent 直接管理 Store，且不提供本產品 source closure、exact revision、同批原子性與 JD review basis |
| 版本、引用、失效的概念模型 | **採最小 provenance 欄位，不導入通用 ontology／graph DB** | W3C PROV 佐證 quotation、revision、invalidation 應分開；Caliburn 只需 source ref、revision lineage 與 lifecycle |

LangMem 的成熟度判讀必須更精確：

- PyPI 最新版是 [`0.0.30`](https://pypi.org/project/langmem/)，2025-10-27 發布；其 main branch dependency 已放寬為 `langgraph>=0.6.0,<2`，因此**版本解析上**可與本 repo 的 LangGraph `1.2.11` 共存。舊版 `0.0.29` 對 LangGraph 1.0 的 incompatibility 不可再當現況。
- 但專案仍是 pre-1.0、PyPI 列一位 maintainer、[GitHub Releases](https://github.com/langchain-ai/langmem/releases) 沒有正式 release；2026-02 仍有「`create_memory_store_manager` 寫入後，`create_search_memory_tool` 在 PostgresStore 找不到」的[未解 issue](https://github.com/langchain-ai/langmem/issues/140)。這些不證明 LangMem 功能不好，但不足以把產品最核心的職務理解 authority 交給它。
- 官方 [`create_memory_manager`](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/) 的確可由 caller 自行控制 storage，並以 typed schema 產生 insert／update／delete；若日後固定 transcript 證明目前主顧問 reconcile 品質差，這是比 `create_memory_store_manager` 更安全的 spike 候選。後者直接搜尋與寫入 BaseStore，會與 checkpoint 單一 semantic owner 衝突。
- 第一版不為了「看起來更 framework-first」固定多跑一次 LangMem extraction model。這會增加 latency／token，又可能在同一回合產生兩個對話理解者。Caliburn 的主模型原本就必須理解員工訊息；最小方案是讓同一主顧問提出 typed understanding operations，成熟框架負責 tool loop、durability、validation、JIT read 與錯誤回傳，application 只保留無框架能替代的來源／revision／authority 規則。

大型雲端產品提供了相同方向但不是適合直接採用的 runtime：

- [AWS AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-memory.html) 明確把 raw messages／Tool calls 的 short-term events 與抽取出的 semantic／summary／episodic long-term records 分開；各 memory strategy 又分 extraction、consolidation、必要時 reflection，並有各自 output schema。這佐證「事件、語意知識、案例不可混成一種萬用記憶」。
- [Google Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories) 也從 Session events 產生可檢索 memories，而不是以 memory 取代 Session 原文。
- 兩者偏向 managed、背景抽取與跨 session semantic retrieval；Caliburn 是本機單一職務、同輪理解可能立刻支撐 JD edit，因此不能照搬其非同步 lifecycle、雲端 authority 或固定 embedding 成本。
- [W3C PROV-O](https://www.w3.org/TR/prov-o/) 分別定義 quotation、revision、primary source 與 invalidation；它支持「員工新更正是新來源、工作理解建立新 revision、舊 revision 不再 active」，但不要求建立 RDF、通用 edge 或 graph database。

#### 15.21.11 每一輪實際如何運作：一個產品 run、必要時多個 model steps

「每次員工送出訊息」仍是一個產品 run，不固定拆成兩個 agent，也不固定呼叫兩次模型。run 內若模型呼叫 Tool，framework 會執行後把 receipt 放回同一 agent loop；是否再進一個 model step 取決於本輪是否還需要 JD 操作或追問。

1. **先保存原文**：員工訊息以 immutable source event 寫入 Store。這一步不靠 LLM，也不改舊原文。
2. **組裝最小充分 Context**：穩定 instructions／Tool schema 放前綴；加入本輪訊息、最短必要近期對話、小型 understanding index、Focus／required input／pending basis／JD delta 明確指向的完整紀錄。其他完整理解與來源由同一主顧問按需 `grep／read`。
3. **主顧問先更新理解**：模型可以提出零到多個 create／revise／retire operation；只填語意內容、必要 relation 與本輪 exact quote，不填 ID、revision、timestamp、lifecycle 或 Skill ID。
4. **application gate**：系統驗 source 真實存在、quote 確實出現在該來源、reference 指向目前 revision、角色／lifecycle transition 合法；全部通過才以一個 checkpoint transition 提交，並回傳 canonical IDs／revisions 的精簡 Tool receipt。
5. **有需要才分析 JD**：若本輪理解已局部足夠、會改變成品 JD，或員工明確要求處理文件，同一主顧問才按需載入相關 Task／Duty／OPKS Skill 與 JD slice，使用剛提交的 canonical understanding revision 編輯 workspace。若還不夠，就只更新理解／OpenIssue 並正常回覆或提問。
6. **員工審核**：AI JD edit 保持 pending diff；員工可改綠色建議，但仍要對完整審核群組接受或拒絕。接受後才進 approved JD；接受後 JD 本體不保留 AI reason／source，完整依據仍在 Work Understanding。
7. **下一輪不靠上輪 prompt 猜狀態**：新 run 從 checkpoint／Store／workspace 重新建立 Context。尚未回答的 OpenIssue、pending JD basis 與員工 JD delta 都是可重建的持久狀態；上輪 chain-of-thought 與長 Tool output 不需要永久重播。

這個流程借用 [OpenAI Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/) 的正常 Tool-feedback 模式：Tool output 追加後再推理，直到回覆；同時保持舊 prompt prefix 穩定以利用 caching。它也符合 [LangChain memory guide](https://docs.langchain.com/oss/python/concepts/memory) 對 hot-path update 的定義：新理解可在同一互動立即使用，但必須控制額外 latency、Tool 複雜度與模型多工負擔。Caliburn 不需要為「更新理解」固定再開 background memory run。

#### 15.21.12 修正、局部失效與重新分析的具體例子

假設員工先說：

> 「我每月底彙整三組月報，整理後交科長核准再發布。」

系統保存 employee source `S1`，主顧問形成一筆目前成立的工作理解 `U1 revision 1`，完整保留頻率、輸入、動作、核准角色與產出。JD Skill 若判斷已足夠，可提出 Task，但待審群組的 basis 指向 `U1@1`。

幾輪後員工普通聊天更正：

> 「我剛才說錯了，最後核准的是處長，不是科長。」

正確處理不是覆寫 `S1`，也不是要求員工點「更正原話」：

1. 新原文保存為 `S9`；
2. 模型讀取 `U1@1`、`S1`、`S9`，辨認這是明確修正；
3. 提出 `revise U1`，application 建立 `U1@2` 並讓 `U1@1` superseded；
4. 尚未核准、且 basis 是 `U1@1` 的 JD group 變 stale，不能直接套用；
5. 已核准 JD 不被程式偷偷改寫，主顧問依 `U1@2` 提出新的待審修正；
6. 無關的其他理解與 JD 不重算。

若員工只說「好像不是科長」而不明確，模型不能用「最新一句一定正確」自動覆蓋；它應保留衝突 `OpenIssue`，必要時用「需要你的確認」追問。這就是 source over inference，而不是 latest source wins。

#### 15.21.13 Context、細節與成本的實際邊界

| 每輪通常直接提供 | 有明確需要才讀 | 不應每輪提供／不作 authority |
| --- | --- | --- |
| 穩定 instructions、當輪 Tools／Skill catalog、本輪訊息、必要近期對話、小型 understanding index、Focus／required-input refs、JD delta 摘要 | 被 refs 指向的完整 understanding revisions、相關 employee sources、相關 JD resources、完整 Skill | 全歷史、全 understanding collection、全部 approved＋current JD、舊 Tool logs、上輪完整 prompt、chain-of-thought、opaque compaction item |

成本控制不是靠刪掉工作理解細節，而是把**保存**與**放進當輪 Context**分開：

- Work Understanding 本體完整保存；index 只作導航，不是摘要 authority。
- Stable prompt prefix 有利 [OpenAI prompt caching](https://openai.com/index/unrolling-the-codex-agent-loop/#performance-considerations)；動態員工內容與 Tool receipt 放後面。
- Tool receipt 只回傳成功／錯誤、canonical handle／revision 與下一步必要資訊，不把整份 state 重複塞回。
- 第一版不接 RAG、不固定 embedding、不固定 router model、不固定 JD Skill、不固定第二 memory model。
- [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 的原則是「最小而足夠的高訊號 Context」與 lightweight refs＋JIT read；不是一律把所有資料預載，也不是只留一份會丟細節的摘要。
- [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction) 的 compacted item 是 opaque transport state，適合縮小長對話，不適合作員工來源或工作理解。因此只允許 compact 舊聊天／Tool transport，不能 compact Work Understanding 本體。

#### 15.21.14 本輪暫定結論與仍可推翻事項

1. Work Understanding 第一版採**主題型完整 collection**，不採單一巨型 profile，也不採每句一個 triple。
2. 三種責任暫定為：目前成立的完整工作知識、具體工作事件、跨輪未解問題；技術名仍可換。為避免 `SemanticUnderstanding` 被誤認為 embedding／semantic search，下一輪 field contract 可比較較白話的 `WorkKnowledge／WorkEpisode／OpenIssue`，但本輪不自行改名。
3. 原始員工來源、工作理解、JD、當輪 Context 是四層不同責任；只有 Work Understanding 是長訪談中給主顧問使用的完整職務知識。
4. 第一版 production 組合仍是 LangGraph checkpointer／Store＋Deep Agents VFS＋Pydantic＋既有 model adapter；不新增 LangMem、Trustcall、AWS／Google cloud memory、graph DB 或 RAG。
5. 「不引入 LangMem」不是拒絕框架，而是避免用成熟度與產品 seam 不合的元件取代已由 LangGraph 承擔的 authority。若固定 transcript 證明 insert／update／retire reconcile 真的失敗，再以同一案例比較 LangMem core manager、Trustcall 與現行薄 reducer，效果／正確性優先於少寫程式。
6. 本節仍未核准精確 fields、Tool branches、每筆切分粒度與 migration；下一步應先把三種角色各自「模型填什麼／application 注入什麼／verifier 驗什麼」寫成可讀契約，再由 Owner 複審，不能直接施工。

#### 15.21.15 精確責任分工第一步：ID、版本與時間不進模型 schema

Owner 追問「模型沒有自行捏造 ID、版本或時間」是否代表模型仍要填這些欄位。答案是**否**；先前這種說法不夠精確，正式更正為：

> 不靠 prompt 要求模型「不要亂填」application metadata；而是從 model-facing schema 移除該欄位，使模型根本沒有填寫入口。需要識別既有目標時，模型只選 application 已提供的 model-safe handle；canonical identity 與 concurrency metadata 仍由 runtime 管理。

官方依據一致：

- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 直接要求「不要讓模型填 application 已經知道的 arguments」，並建議用 enum／object structure 讓非法狀態不可表示；同頁建議 strict mode 與 `additionalProperties: false`。
- [Anthropic How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works) 把 Tool 定義成模型提出 typed request、application 執行並回傳結果的契約；[Strict Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use) 只保證模型輸入符合 schema，不把 application metadata 變成模型責任。
- [LangChain Tools／ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools) 可注入 state、context、store、thread／run／attempt 與 tool-call ID，而且 runtime 參數不會出現在給模型的 Tool schema。
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 的 checkpoint ID、step metadata 與 `created_at` 都是 framework 保存 checkpoint 時產生的執行資料。
- [Pydantic discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions) 建議用 discriminator 讓 variant 更可預測；[`extra='forbid'`](https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.extra) 可拒絕 schema 外欄位，避免模型額外塞入 metadata。
- [RFC 9110 `If-Match`](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) 說明 state-changing operation 應以伺服器可驗證的 current representation token 防止 lost update；在 Caliburn 中，token／revision 由 read Tool 與 `ToolRuntime` read-set 保存，不要求 LLM 抄回。

三種作法比較：

| 方案 | 作法 | 結果 |
| --- | --- | --- |
| A. 模型填 raw UUID／revision／timestamp | schema 暴露所有 metadata，再靠 prompt 與 validator 防亂填 | 欄位多、易 stale、重現既有 retry 問題；淘汰 |
| B. 模型只填 semantic payload，必要時選 runtime 提供的 handle | application 解析 handle、注入 exact revision／source／時間並執行 | **推薦**；符合 OpenAI／Anthropic Tool contract 與 LangChain runtime injection |
| C. 模型只寫自由文字，由 application 猜要改哪筆 | 模型欄位最少，但需要 fuzzy match／parser | 目標不確定、錯誤難回傳、可能改錯紀錄；淘汰 |

候選責任表如下；名稱與最終 branch 數仍待 Owner 複審，不能直接施工：

| 責任面 | 模型可提供 | 不由模型提供 |
| --- | --- | --- |
| 新增工作理解 | 語意角色（或由所選 Tool variant 表示）、完整 `body`、必要 exact quote、必要 relation handle | record ID、revision、lifecycle、時間、source UUID、run／Skill receipt |
| 修訂工作理解 | 從已讀目錄選一個 `target_handle`、完整替代語意、必要 quote／relation handle | canonical target ID、`expected_revision`、supersedes ID、updated time |
| 退役工作理解 | 已讀 `target_handle`；是否需要一行 semantic reason 尚待下一輪比較 | lifecycle transition、retired time、actor、revision |
| Tool 執行 | 無 | provider call ID、thread／run／attempt、實際載入 Skill、status、receipt、token／cost |
| JD 待審變更 | JD 語意內容、群組一次的短理由與 1～N 筆 understanding handles | diff、stable JD IDs、order、digest、stale、pending／accepted／rejected 狀態 |

`target_handle`／relation handle 的邊界要特別清楚：

1. handle 必須先由小型 index 或 read Tool 提供，模型不能自訂格式、不能猜不存在的值；
2. read middleware 同時把 `handle → canonical ID＋exact revision` 記入本 run read-set，但只把 handle 與必要語意顯示給模型；
3. revise／retire 時，application 從 read-set 解析並驗 current revision；模型不回填 revision；
4. stale 就回小型 typed Tool result，要求重讀目標；不能接受模型改一個 revision 數字後重試；
5. 若本輪 Tool 已預先綁定唯一目標，連 `target_handle` 都可從 schema 移除，遵守 OpenAI「已知參數不要交模型填」原則。

因此 verifier 的正確工作不是「判斷模型有沒有捏造 metadata」，而是：

1. provider strict／Pydantic 驗 model-authored semantic shape，並拒絕所有額外欄位；
2. runtime 驗 handle 確實由本輪 Context／read Tool 提供，且 read-set revision 仍 current；
3. application 驗 exact quote、source closure、role／relation direction、lifecycle transition 與 batch atomicity；
4. framework 產生 canonical ID、revision、timestamp、call pairing 與 receipt；
5. Tool result 只回模型下一步需要的 canonical handle／revision label或 typed error，不回灌整份 state。

這一節只收斂 **metadata ownership**，還沒有核准三種語意角色的最後名稱、create／revise／retire 是否共用一個 tagged Tool，以及 retire 是否需要短理由。下一輪應只討論這三個 model-authored semantic 問題，不再把 ID／版本／時間重新放回模型表單。

#### 15.21.16 下一個候選：一個原子能力，不是巨型表單，也不是十幾支相似 Tools

本輪追加核對最新官方 Tool 設計建議：

- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 建議讓 invalid states 不可表示、把 application 已知負擔移出模型，且初始可見 function 數量盡量小（官方提供 `<20` 的 soft suggestion，不是硬上限）。
- [Anthropic Managed Agents — Tools](https://platform.claude.com/docs/en/managed-agents/tools) 建議把密切相關操作合併成較少、較有能力的 Tools，以降低 selection ambiguity；結果只回下一步需要的 high-signal semantic identifiers。這是 2026 Managed Agents 指南，可作設計佐證，但 Caliburn 不因此改用 Anthropic managed runtime。
- [Anthropic Tool Troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use) 指出相似名稱與模糊 description 會造成選錯 Tool／參數，strict 只處理 schema shape。
- [LangChain Agents — Dynamic tools](https://docs.langchain.com/oss/python/langchain/agents#dynamic-tools) 與 [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom#dynamically-selecting-tools) 可依 graph state／runtime context 只曝光當輪相關 Tools，以縮短 prompt 並降低錯誤。
- [Pydantic discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions) 仍適合把 create／revise／retire 的不同必要欄位做成可預測 variants，而不是用一張 all-optional 表單。

三個候選：

| 方案 | 優點 | 問題 | 裁決 |
| --- | --- | --- | --- |
| A. 每個 role × operation × source mode 各一支 Tool | 每支 schema 很小 | 會形成十多支名稱相近 Tools；每輪 tool description 成本與選錯機率增加 | 不採常駐方案 |
| B. 一支 flat Tool，所有欄位都 optional／空陣列 | 表面只有一支 Tool | 合法 shape 仍可形成大量非法語意組合，重現 dummy field／mapper retry | 淘汰 |
| C. 一支 `reconcile_work_understanding` 原子 Tool，`changes[]` 是少量 discriminated variants | 同一回合多筆理解可原子提交；只選一次 domain capability；每個 variant 只含真正需要的欄位 | provider 對 nested union 的實際相容性仍須小型 preflight | **目前推薦研究候選** |

若正式 OpenRouter／Claude endpoint 對方案 C 的 nested union compile／routing 不穩，fallback 是以**同一 authoritative Pydantic domain type**在當輪轉成 2～4 支 role-specific Tools，並由 LangChain middleware 只曝光相關 subset。這只是 provider adapter 的呈現差異；不能維護第二份 schema，也不能退回 giant root output。

目前最小 model-authored 資訊只有：

1. **語意內容 `body`**：create／revise 時提供完整、自足的目前理解；不是 JD 欄位拆解表。
2. **既有目標 `target_handle`**：只有 revise／retire 需要，而且只能選已讀 handle；canonical ID／revision 不在 schema。
3. **direct quote**：只有該 role／source mode 確實需要員工原句支持時提供；current source identity 由 runtime 注入。
4. **relation handles**：只有 Work Knowledge 由既有 Work Episode 支持，或 Open Issue 指向相關理解時才提供；不能讓模型造 local IDs。
5. **role／operation**：優先由 discriminated variant／Tool 名稱表示，不再要求模型重複填多個彼此可能矛盾的 enum。

概念示意（不是最終 JSON Schema）：

```text
reconcile_work_understanding(changes=[
  create_work_episode(body, current_source_quotes),
  create_work_knowledge_from_source(body, current_source_quotes),
  revise_work_knowledge(target_handle, body, support),
  open_issue(body, related_handles, optional_current_source_quotes),
  retire(target_handle),
])
```

這裡的 `optional_current_source_quotes` 表示 Open Issue 的真實 domain cardinality：純缺口沒有 quote，員工說法衝突則有 quote；不是要求模型填假的空值。最終可拆成 gap／conflict variants，或保留一個 0～N list，應以 provider schema preflight 與固定 transcript 的錯誤率決定，不能只追求 branch 數最少。

`retire` 第一版暫不另要求模型填「理由」。OpenAI Apply Patch／Anthropic Text Editor 的 delete operation 也是 target action 與 harness receipt 分離；Caliburn 可由本輪 employee source、相鄰 understanding changes、checkpoint 與 Tool receipt 重建發生背景。若真實除錯證明無短理由就無法理解誤退役，再提出增加；不能現在為可能的 audit 多加一個每次必填欄位。[OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch) · [Anthropic Text Editor Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)

Owner 於 2026-08-29 暫時同意把內部三種角色命名為 `WorkUnderstanding／WorkEpisode／OpenIssue`；這仍是可翻案暫名。採 `WorkUnderstanding` 而不是 `WorkKnowledge`，是為了避免讓人誤認為該內容已由員工核准或不可修訂。名稱會進 Pydantic discriminator、Tool description、trace 與文件，精確 branches 定案時仍須一併複審。

#### 15.21.17 長訪談記憶複審：compaction 不等於工作理解，framework 管機制、Caliburn 定義語意

Owner 追問「這些 ID、版本、時間是否仍要模型填」後，本輪也回頭複審工作理解的最小資料結構，避免只是把舊 `Work Model／Case／Pattern／Gap` 換名後原封不動搬回來。以下仍是**可翻案的暫定候選**，不是 production schema。

最新官方資料的共同方向是：

1. [OpenAI〈Unrolling the Codex agent loop〉](https://openai.com/index/unrolling-the-codex-agent-loop/) 說明 Codex 會在長任務中 compact conversation，換成較小但可延續工作的 input；這是 active context 管理，不是可供產品查詢、逐筆修訂的 domain knowledge base。
2. [OpenAI GPT-5 model guidance](https://developers.openai.com/api/docs/guides/latest-model) 同樣把 compaction 定義為 continuation 用的 opaque items，明確提醒不要解析或依賴其內部格式。因此 Caliburn 不能從 compacted payload 反推職務事實、來源或版本。
3. [Anthropic〈Effective context engineering for AI agents〉](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 將 compaction、structured note-taking／agentic memory 與按需取回分成互補機制：對話與舊 Tool result 可壓縮，重要知識另存持久 notes，再按需讀回。
4. [Claude Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) 也是 client-side contract：模型請求 create／read／update／delete，實際儲存、路徑映射與權限由 application 控制。它佐證「模型提出語意操作、harness 擁有 storage」，但不替職務分析產品定義資料語意。
5. [LangGraph Memory overview](https://docs.langchain.com/oss/python/concepts/memory) 區分 thread-scoped short-term memory 與跨 session long-term memory，也區分 semantic facts、episodic experiences 與 procedural instructions；大型單一 profile 更新容易遺漏，collection 通常較適合逐筆新增／修訂並提高 recall。
6. [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 的 Store item 已由 framework 提供 key、namespace、`created_at`、`updated_at` 與搜尋機制。這直接支持前一節結論：這些欄位沒有理由再交給模型生成。

因此三層責任暫定如下。這裡原先把 Work Understanding 直接指定給 Store；經 §15.21.20 以 OpenAI／Anthropic／LangGraph 官方資料與現行 recovery seam 整體複審後，**第一版 owner 維持 LangGraph typed checkpoint**。三層語意分工仍成立，但不能把「長期知識」直接等同「一定要放 Store」：

| 層 | 保存什麼 | 由誰負責 | 不得混入 |
| --- | --- | --- | --- |
| Conversation／short-term state | 近期訊息、當輪 Tool call/result、短暫執行狀態 | LangGraph checkpoint；長時可 compact／清除低價值 Tool result | 不當成職務事實的唯一保存處 |
| Work Understanding collection | 員工實際工作的完整可修訂理解、具體工作事件、跨輪未解問題及來源關係 | **第一版：LangGraph typed checkpoint＋Caliburn semantic reducer／verifier**；Store 是 evidence-triggered successor 候選 | 不壓成一份會覆寫遺漏細節的大摘要；不拆成 JD 欄位；不在 checkpoint 與 Store 雙寫 |
| Procedural knowledge | Task／Duty／OPKS／JD 分析方法與產品規則 | versioned Skills／developer instructions | 不由每輪模型改寫成個人記憶 |

三種**語意責任**暫定如下；名稱仍待 Owner 複審：

| 暫定內部名 | 真正責任 | 何時使用 | 不代表什麼 |
| --- | --- | --- | --- |
| `WorkUnderstanding` | 對員工實際工作目前成立的、完整且可獨立理解的理解，例如固定責任、工作方式、責任邊界、情境與條件 | 員工直接敘述穩定事實，或具體事件已足以支持較穩定理解時 | 不是員工核准的 JD 欄位，也不是不可修訂的真理 |
| `WorkEpisode` | 一次具體工作事件／案例及其關鍵細節 | 員工以某次事件說明做法，但尚不能安全概括成普遍規律，或案例本身對後續訪談仍重要時 | 不是每句對話都要建立一筆，也不是 Task |
| `OpenIssue` | 目前缺少、含糊、互相衝突或尚待員工回答的實質問題 | 不解決仍可安全前進時持久保留；若不回答就只能猜且會改壞理解／JD，才投影成「需要你的確認」 | 不是固定 OPKS checklist、Task backlog 或技術錯誤 |

第一版模型可填的最小資料維持極少：

1. `body`：完整、自足的目前語意；`OpenIssue` 則是清楚描述未知／衝突與要釐清的問題。
2. `quote`：只有需要以員工原話支持的新增／修訂才提供；本輪 source identity 由 runtime 預先綁定。若引用舊訊息，只能選 read Tool 已回傳的 source handle，不可自行造來源 ID。
3. `target_handle`：只有 revise／retire 既有紀錄時需要，只能選本 run 已讀取的 handle。
4. `related_handles`：只有語意上確實需要連到既有理解／事件／問題時提供；不要求每筆都建圖。
5. operation／role 由 tagged variant 或動態 Tool 名稱表示，不另外重複填 enum。

第一版**不讓模型填**：title、canonical ID、source UUID、revision、timestamp、lifecycle、confidence、coverage score、Skill ID、quote offset、run ID、receipt、JD field mapping。小型 index 若需要短標籤，先由 application 使用 `body` 的安全截斷建立可重建 projection；只有真實 transcript 證明導航品質不足，才評估增加非權威 label，不先多一個必填生成欄位。

也不要求每段員工話同時產生 `WorkEpisode` 與 `WorkKnowledge`：

- 員工直接說明穩定工作規律，可直接建立有 quote 支持的 `WorkUnderstanding`；
- 員工只講一個具體案例且尚不能概括，先建立 `WorkEpisode`；
- 後續足以概括時，新／修訂的 `WorkUnderstanding` 可引用已讀 episode handle，或直接引用支持它的員工原話；
- 同一 atomic call 不為了「先建 episode 再關聯 knowledge」引入模型自造 local ID。真的需要同輪關聯時，應由 application 從共同 source／operation order 產生，或拆成收到 canonical receipt 後的有界 continuation，不能讓模型發明暫時 UUID。

這一節帶來的暫定結論是：成熟 framework 已覆蓋 durability、checkpoint、Store、metadata、Tool execution、按需 retrieval 與 compaction；Caliburn 只保留不可外包的職務分析語意與 deterministic domain validation。`WorkUnderstanding／WorkEpisode／OpenIssue` 已獲可翻案的暫時同意；下一個需要複審的是每一筆紀錄的語意邊界，以及 create／revise／retire 的最小 branches。

#### 15.21.18 紀錄粒度研究：不是整份摘要，也不是一句一筆

本節只研究「一筆 Work Understanding 應多大」，尚未取代 ADR 0071 或施工計畫。官方資料能支持 memory 機制與風險，不能替 Caliburn 決定職務語意邊界：

- [LangGraph Memory overview — Profile／Collection](https://docs.langchain.com/oss/python/concepts/memory) 明確指出：單一 profile 變大後，重寫整份文件容易遺失既有資訊；collection 的 individual memories 範圍較窄，通常較容易新增並提高後續 recall。但 collection 會把難題移到 update／delete、搜尋與完整 Context 組裝，模型也可能 over-insert 或 over-update。
- [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 建議長任務用 structured notes 保存關鍵狀態並按需讀回，而不是讓所有歷史永遠占據 active context；它沒有要求每句輸入都成為一筆 note。
- [Claude Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) 提供 create／read／update／delete 與 just-in-time retrieval 的成熟 primitive，但檔案切分與內容仍由產品／agent 定義。
- [OpenAI〈Unrolling the Codex agent loop〉](https://openai.com/index/unrolling-the-codex-agent-loop/) 顯示長任務靠完整對話、Tool feedback 與 compaction 延續；它沒有把 compacted conversation 當成可逐筆修訂的產品知識。因此 Caliburn 仍需要可定位、可修訂的工作理解 collection。

三個候選：

| 方案 | 優點 | 主要失敗模式 | 暫定裁決 |
| --- | --- | --- | --- |
| A. 每位員工一份巨大「目前理解」profile | 初期讀取簡單、整體脈絡集中 | 長訪談反覆重寫整份；容易漏掉舊細節、diff 太大、局部更正會波及無關內容 | 不推薦 |
| B. 每句話／每個 claim／triple 一筆 | 每筆很小，局部修改容易 | 紀錄爆量、重複、語境破碎、關係圖與召回成本上升；模型必須自行重組完整工作 | 不推薦 |
| C. 一個可獨立理解的工作主題一筆 | 保留完整語境，又能局部新增／修訂／退役；符合 collection 優勢 | 邊界是語意判斷，仍需防 over-insert／over-update | **目前推薦候選** |

「工作主題一筆」的白話判準不是字數，而是：

> 日後主顧問只讀這一筆，不重播原對話，也能完整理解員工在這一塊實際做什麼、在什麼情境下做、負責到哪裡，以及目前仍有哪些限制或邊界；但它仍不是 Task／Duty／OPKS 欄位表。

暫定更新規則：

1. **同一件工作的補充、更正、責任邊界或做法變化**：優先 revise 既有 `WorkUnderstanding`，產生新 revision；不因每輪多一句就新增一筆。
2. **可獨立理解、日後可能單獨形成不同 JD 責任或訪談方向的新工作**：create 新 `WorkUnderstanding`。
3. **只知道一次具體事件，尚不能安全說成常態**：create／revise `WorkEpisode`，不強迫立刻概括成 `WorkUnderstanding`。
4. **缺少、含糊或互相衝突，現在無法安全整合**：create／revise `OpenIssue`；回答後由同一顧問修訂相關理解並 retire／resolve 問題。
5. **同一段訊息同時談多塊工作**：可在一次 atomic Tool call 提交多個 changes；原子性是「整批驗證／提交」，不是把內容硬塞進一筆。

第一版不設定固定 token 數、句數、案例數、embedding clustering threshold 或「一個 Duty／Task 對應一筆」規則。模型在改寫前必須先讀相關 current records，選既有 `target_handle` 或明確 create；application 只能檢查 handle、revision、source、quote 與 transaction，不能用字串相似度替模型自動合併職務語意。

例子：

- 員工先說「我處理客戶退貨」，後續補充「只負責判斷能否退，不負責退款入帳」：這是同一工作主題的責任邊界補充，revise 同一 `WorkUnderstanding`。
- 員工又說「每月也會分析退貨原因並向產品部門提出改善」：若它有不同目的、產出與訪談方向，create 另一筆；不能因都含「退貨」就自動合併。
- 員工只描述「上週遇到一筆海外客戶特殊退貨」但不確定是否常態：先保留 `WorkEpisode`；是否能形成穩定理解由後續訪談決定。

這個方案沿用成熟 framework 的 collection／Store／revision／按需讀取能力，但 record boundary 仍是 Caliburn 顧問 Skill 的專業判斷。Owner 於 2026-08-29 **可翻案地暫時同意**「一個可獨立理解的工作主題一筆」；下一題是 create／revise／retire 需要哪些最小 tagged branches，以及什麼情況必須整批提交。

#### 15.21.19 操作形狀研究：三個基本動作＋原子 changeset，不建立專用 split／merge

本節比較 Work Understanding 如何被模型編輯；仍是待 Owner 複審的研究候選。可轉移的官方做法如下：

- [OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch) 讓模型提出 create／update／delete，application harness 實際套用、記錄成功或錯誤，再以 call ID 回傳結果；模型不直接擁有 filesystem transaction。
- [Claude Text Editor Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool) 同樣採先 view，再 create／`str_replace`／insert，由 client 執行並回 Tool result。
- [Claude Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) 對持久 memory 提供 view／create／`str_replace`／insert／delete／rename，並對不存在、文字不唯一或不匹配回精確錯誤。這支持「模型提出最小編輯意圖、application 驗目標與套用」；不代表 Caliburn 應照搬檔案 path、行號或 raw string patch。
- [Google Agent Platform Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories) 會從對話抽取記憶，對同一 scope 的獨立 memories 做 consolidation，隨時間新增、更新或刪除重複／互補／矛盾內容；每個結果明列 `CREATED／UPDATED／DELETED`。其 [Memory revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions) 又把 current consolidated memory 與 immutable revisions 分開，並支援查看與 rollback。這是目前找到最接近「持續修訂工作理解 collection」的已出貨大廠機制，但仍不是 Caliburn 的職務分析 schema。
- [AWS AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html) 也明確區分保存逐輪 events 的 short-term memory，以及從互動中 extraction／consolidation 後形成的 structured long-term memory records；[Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html) 可用 built-in、override 或 self-managed pipeline。這佐證「原始對話與可持續整併的長期理解分層」不是 Caliburn 自創。
- [LangGraph Persistence／Store](https://docs.langchain.com/oss/python/langgraph/persistence) 以 namespace＋key 保存 JSON memory item，`put` 更新 item，framework 管 key 與 created／updated time。對本案的 topic-sized record，完整替代一筆小 JSON value 比在一份巨大 profile 中做跨欄位 patch 更簡單。

必須分清楚證據強度：

| 設計片段 | 證據層級 | 能否宣稱 Claude／Codex 就是這樣做 |
| --- | --- | --- |
| 模型先讀目前內容，再提出 create／update／delete；host application 執行並回傳精確成敗 | OpenAI／Anthropic 公開且已出貨的 Tool contract | **可以宣稱同一機制家族**，但不能宣稱其資料就是 Work Understanding |
| 從對話抽取長期 memories，對既有 collection 新增／更新／刪除、處理重複或矛盾，保留 revision／rollback | Google Memory Bank 公開產品；AWS 也公開 extraction／consolidation | **可以宣稱是大廠已出貨的相同目的機制**，但不是 Claude／Codex 公開的內部 schema |
| collection 比巨型 profile 較不易在更新時漏失內容，但 update／delete 與 retrieval 會更難 | LangGraph 官方 memory 指南 | **可以作 framework 取捨依據**，不是某家產品唯一最佳解 |
| `WorkUnderstanding／WorkEpisode／OpenIssue` 三種角色與「一個可獨立理解的工作主題一筆」 | Caliburn 依職務訪談目的做的 domain mapping | **不可以**冒稱大廠 schema；這必須由本產品研究與 transcript 驗證 |
| revise 使用 `target_handle＋完整 replacement body` | 受 bounded resource replacement、LangGraph item update 與降低 Tool schema 錯誤啟發的 Caliburn 候選 | **不可以**冒稱 Claude／Codex 做法；Claude／Codex 公開 editor 主要是 patch／replace primitives |
| split／merge 由多個 create／revise／retire 組合，不另設專用 Tool | Caliburn 為減少等價操作與 schema 分支做的候選 | **不可以**冒稱大廠既定規則 |
| 多筆相依變更同批全成或全退 | [RFC 5789 PATCH](https://www.rfc-editor.org/rfc/rfc5789.html) 與 [PostgreSQL transaction](https://www.postgresql.org/docs/current/tutorial-transactions.html) 支持的資料一致性原則 | 是成熟工程標準；**不是** OpenAI／Anthropic 公開保證多個 Tool calls 原子提交 |

因此，本節不是「照抄 Claude／Codex」。準確說法是：**Tool loop、低階編輯、host-owned execution／error feedback 直接沿用 Claude／Codex；可修訂 memory collection 與 revision 另有 Google／AWS／LangGraph 的成熟先例；Caliburn 只自行決定職務領域語意與哪些操作必須綁成同一個業務決策。**

三種候選：

| 方案 | 優點 | 問題 | 暫定裁決 |
| --- | --- | --- | --- |
| A. 每個語意動作都有專用 branch：create／revise／resolve／split／merge／reclassify… | trace 名稱很具體 | branch 與 schema 快速膨脹；同一結果有多條等價路徑，模型更容易選錯 | 不推薦 |
| B. 完全照搬檔案 editor：path＋line／old text＋new text | Claude／Codex 熟悉；局部 diff 很小 | Work Understanding 不是純文字檔；relation、source、revision 與 role invariant 無法只靠文字 patch 表達 | 不直接採用 |
| C. domain editor：`create／revise／retire` 三個基本動作，零到多筆組成一個 atomic changeset | operation 少、非法狀態可由 tagged variants 排除；split／merge／resolve 都能組合表達 | revise 必須先讀目前紀錄；完整 replacement 可能遺漏舊細節，需靠小 record boundary、明確 instruction 與 review diff 降低 | **目前推薦候選** |

推薦候選的白話語意：

1. **create**：建立新的 `WorkUnderstanding`、`WorkEpisode` 或 `OpenIssue`。模型填完整 `body` 與該 variant 真正需要的 quote／relation；ID、版本與時間由 application 產生。
2. **revise**：模型先讀 current record，再用 `target_handle＋完整 replacement body` 建立下一版。不是只送自由文字「補一句」、不是自己填 revision，也不是直接覆寫歷史版本。
3. **retire**：讓既有 current record 不再進導航或後續 JD basis；歷史 revision、來源與 lineage 仍保留。第一版不另要求模型填 retire reason。

不建立專用拓撲操作：

- **拆分理解**＝create 兩筆較清楚的新紀錄＋retire 原紀錄；
- **合併理解**＝create 一筆整合後紀錄＋retire 多筆舊紀錄；
- **解決 OpenIssue**＝create／revise 真正得到的理解＋retire 該 issue；
- **發現問題其實無關**＝只 retire issue；
- **同一工作內容改正**＝revise，不需要 delete＋create，也不改 stable identity。

以上多步驟必須放在**同一 atomic changeset**：全部 source／quote／target／revision／relation 驗證通過才提交；任一失敗就全不寫入，回一個短 typed diagnostic 給同一顧問有界修正。這裡的「原子」是 application transaction，不要求模型填 transaction ID。

為何 revise 暫定送「完整 replacement body」而不是 raw patch：

1. §15.21.18 已限制每筆是有界、可獨立理解的工作主題，不是幾萬字檔案；完整替代的 token 成本可控。
2. 模型不需填行號、offset、JSON Patch path 或同一句出現第幾次，能避開先前 quote offset／複雜 schema 的失敗模式。
3. application 仍保存 old／new revision，能 deterministic 產生 review diff；完整替代不等於破壞歷史。
4. 主要風險是模型在重寫時漏掉未變細節；因此 Tool description 必須要求 preserve unrelated details，且 revise 前必須讀 current body。若固定 transcript 日後證明 omission 仍頻繁，再比較 trained-in text editor／patch adapter，不能現在為大型檔案問題預先複雜化小型 domain record。

這個候選不改變員工權限：Work Understanding 仍由顧問根據員工對話維護、員工唯讀；員工直接編輯的是共同目前 JD。也不建立第二份 memory store：Work Understanding operations 只提交至 checkpoint typed collection；Store 仍只承接 employee source、目前 JD workspace 與其他不同責任的既有資料。

這裡曾發現一項文件衝突：§15.21.17 一度把 Work Understanding collection 指定給 LangGraph Store，但現行 `AGENTS.md`、Accepted ADR 0060、Proposed ADR 0071 與 production code 都把 document-thread scoped Work Understanding 放在 LangGraph checkpoint，Store 只持 employee source／workspace 等 application records。這項衝突現已在 §15.21.20 正式重開比較；第一版結論是**維持 checkpoint 為唯一 Work Understanding owner**，而不是雙寫或立即搬遷。Store 方案保留為有真實容量、查詢或 scope 證據後才能重開的 successor 候選。

目前已收斂的兩點是：

1. 暫時接受「三個基本動作＋完整 replacement revise＋atomic changeset」，並清楚標記其中只有基本編輯 loop 是 Claude／Codex 直接做法，其餘是有大廠相似機制支持的 Caliburn domain adaptation；
2. Work Understanding 第一版由 checkpoint typed collection 單獨擁有；實作不得因看見本節早期 Store 候選就自行新增 Store namespace、雙寫或 migration。

#### 15.21.20 整體 authority 複審：第一版維持 checkpoint，Store 只作有證據才啟動的 successor 候選

本節回到完整產品方向，而不是只看某個 framework 名詞。研究優先序依 Owner 指示調整為：

1. **OpenAI／Codex 與 Anthropic／Claude 官方公開機制**：作為目前最成熟 agent 產品的主要方法證據；
2. **LangGraph／LangChain 官方文件與原始碼**：決定已選 framework primitive 的實際能力與邊界；
3. PostgreSQL／Psycopg 等底層官方文件：判斷 transaction、batch 與 recovery 能否成立；
4. Google／AWS 只作相同目的已有出貨機制的次要交叉佐證，不能凌駕前兩層，也不能單獨決定 Caliburn 架構。

##### A. 官方實際公開了什麼；哪些仍只是 Caliburn 推論

| 來源 | 官方明確公開的事實 | 不得冒稱的內容 |
| --- | --- | --- |
| [OpenAI Codex App Server](https://openai.com/index/unlocking-the-codex-harness/) | durable thread 保存 event history；turn 由 typed items 組成；Tool、diff、approval 都有生命週期，client 可重連並還原一致 timeline | 沒有公開 Codex 內部 domain-memory 資料表，也沒有說 application records 應放 LangGraph Store |
| [OpenAI Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform) | harness 管 agent loop、conversation state、Tool interaction 與 approval；host application 擁有產品 Context、business rules、records、controls 與 system-of-record 邊界 | 不能把 Codex harness 的 thread persistence 當成 Caliburn JD／工作理解 schema |
| [OpenAI Codex Memories](https://learn.chatgpt.com/docs/customization/memories) | local memories 與 chat 分離，包含 summaries、durable entries、recent inputs、supporting evidence；背景 extraction／consolidation，且官方要求必須遵守的規則仍放 `AGENTS.md`／checked-in docs，不可只靠 memory | 這種 idle 後背景 memory 不適合直接照搬成同輪 JD 所依賴的 Work Understanding authority |
| [OpenAI Conversation State](https://developers.openai.com/api/docs/guides/conversation-state)／[Compaction](https://developers.openai.com/api/docs/guides/compaction) | conversation／response chain 能延續 Tool items；compaction 是縮小 active model context 的 opaque continuation state | compacted payload 不是可查詢、可逐筆修訂、可作來源的職務知識 |
| [Claude Code sessions](https://code.claude.com/docs/en/sessions)／[memory](https://code.claude.com/docs/en/memory)／[checkpointing](https://code.claude.com/docs/en/checkpointing) | session transcript、可按需讀取的 topic memory、file-edit checkpoint 是不同層；memory index 精簡，細節檔案 JIT read；code 與 conversation 可分開 rewind | 沒有公開一套可照抄的職務理解 record schema，也不能宣稱 Claude 的 memory 就等於 application system of record |
| [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 使用最小高訊號 Context；compaction、structured notes／memory、JIT retrieval 是互補機制；持久資料不必全部塞進每次 inference | 它沒有要求每種持久知識都必須搬到跨-thread Store |
| [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)／[Memory overview](https://docs.langchain.com/oss/python/concepts/memory) | checkpointer 每個 graph step 保存 thread-scoped state snapshot，支援 resume、HITL、time travel、fault recovery；Store 保存 graph state 外、namespace＋key 的 application-defined records，主要用於跨 thread long-term memory；Store namespace 可自訂，不必是 user scope | 官方分類是預設責任，不會替 Caliburn 判定 Work Understanding 到底是 thread state 或跨-thread memory |

OpenAI 與 Anthropic 公開產品共同支持的是**分層**，不是特定資料庫拓撲：conversation／run history、可按需讀的持久知識、正在編輯的 workspace、application system of record 不應混成一段永遠重播的 prompt。它們沒有公開證據可支持「Work Understanding 必須用 Store」或「必須用 checkpoint」；後者仍須按本產品 scope、原子性、成本與 recovery 判斷。

##### B. 以 Caliburn 真正需求分類 Work Understanding

| 判斷面 | Caliburn 目前事實 | 對 owner 選擇的影響 |
| --- | --- | --- |
| scope | 一份 JD／一場長訪談固定對應一個 `document_id == thread_id`；文件彼此隔離，不跨文件共享員工工作理解 | 符合 LangGraph thread-scoped checkpoint 的主要使用情境；目前沒有 Store 的跨-thread 必要性 |
| lifecycle | 每個 work-related turn 都可能修訂 Work Understanding、OpenIssue、Focus／coverage 與 run receipt | 這些是同一 graph transition 的互相依賴 semantic state；checkpoint 可直接一起提交與 resume |
| 同輪 JD basis | JD 只能依已驗證、已提交的最新工作理解分析；JD 不必每輪改 | 先提交 understanding checkpoint，再於必要時讓同一 product run 繼續 JD Tool loop，邊界比跨 Store／Saver transaction 清楚 |
| Context 成本 | LLM 只取得 navigation index、明確 refs 與按需選中的完整 records；framework state 不會自動全部進 prompt | Work Understanding 在 checkpoint 不等於每次把全部內容計入 tokens；Context selector 才決定模型成本 |
| 資料量 | 原始對話全文在 Store，目前 JD 大型資源在 StoreBackend；checkpoint 只需有界的 topic records／issues／runtime state | checkpoint 會成長但尚無真實長訪談證據顯示已超出容量或延遲預算；現在搬 Store 是預先最佳化 |
| recovery | production 已有 Store source → checkpoint reference → Store committed 的 idempotent reconciliation，且 Saver／Store 使用不同連線 | 若再把 Work Understanding 搬 Store，會新增 Store semantic commit 與 checkpoint run-state 間的恢復 seam；沒有證據前不值得增加 |
| 查詢 | 第一版只在單文件顧問 run 中依 handle／role／lifecycle 選取；不做跨文件分析、任意 SQL 或 RAG | typed collection＋derived in-memory index 已足夠；Store search 尚未帶來必要產品能力 |

特別澄清：**「長訪談會長期保留」不等於 LangGraph 官方定義的「cross-thread long-term memory」。** Work Understanding 可以是長期存在的產品知識，同時仍是單一 document thread 的 typed semantic state。物理位置與產品壽命不是同一個問題。

##### C. 三個 storage 方案重新比較

| 方案 | 效果／可靠性 | 成本與複雜度 | 第一版裁決 |
| --- | --- | --- | --- |
| A. Work Understanding 全文只在 Saver typed checkpoint | 與 OpenIssue、Focus、coverage、run receipt 同步；resume／HITL／fault recovery 原生；同輪可先取得 canonical revision 再決定是否改 JD | 每個 super-step 會保存 state snapshot；長訪談有 storage growth 風險，但 raw source／JD workspace 已外移，且目前無失敗證據 | **採用／維持** |
| B. Work Understanding 全文只在 Store | item CRUD／namespace／JIT read 自然；若未來跨 thread 或資料量很大較合適 | 要新增 semantic command receipt、Store→Saver recovery、migration 與更多 concurrency canary；目前沒有跨-thread需求 | 有真實觸發證據後的 successor 候選 |
| C. Store 放全文、Saver 再放可寫副本 | 表面同時取得兩邊優點 | 形成兩個可寫 authority、stale／repair／刪除一致性問題；違反已確認的 single owner | **禁止**；Saver 只能保存 handle／read-set／receipt 等 runtime reference，不能複製第二份 semantic body |

LangGraph 官方也提醒 checkpoint 預設在每個 super-step 保存 state channel 的完整 value，長 thread 可能增加 storage；`DeltaChannel` 可減少 append-heavy channel 的重複，但目前仍標示 beta。因此本節不是宣稱 Saver 永遠最好，而是判定：**在單文件、單 thread、無跨文件共享且同輪 semantic consistency 很重要的第一版，Saver 的已驗證一致性收益大於尚未證明的 Store 查詢收益。** 不因 beta 優化存在就立即採用，也不先寫自製 pruning。

##### D. 第一版最終 responsibility map

| 持久內容 | 唯一 owner | 模型當輪如何取得 |
| --- | --- | --- |
| 員工原始訊息／更正 lineage／exact quote source | LangGraph Store 的 document source namespace | 本輪原文預載；舊來源只由明確 handle／read Tool 按需載入 |
| `WorkUnderstanding／WorkEpisode／OpenIssue` current collection | **LangGraph Saver typed checkpoint** | 小型導航＋明確 refs 預載＋按需讀完整 record；不把整份 collection 自動塞入 prompt |
| Focus、required input、run／command receipts、理解與 JD basis handles | LangGraph Saver typed checkpoint | 作 runtime routing／resume；只把本輪需要的部分投影給模型 |
| 員工與 AI 共用的目前 JD workspace | Deep Agents `StoreBackend`／LangGraph Store 的獨立 workspace namespace | JD Skill／Tools 按需 read／edit；Web 顯示 current＋derived review diff |
| 核准 JD baseline | 依 Accepted ADR 0060／Proposed ADR 0071 仍由 Saver authority channel | export／review rebase deterministic 讀取；AI 無直接 approved write edge |
| active model Context／compacted conversation | provider／LangChain middleware 的非權威 transport | 可 trimming／compaction；永不取代 employee source、Work Understanding 或 JD |

這是「框架層混合、語意層單一 owner」，不是兩份工作理解：Saver 管一份 thread semantic authority；Store 管不同責任的原始 source 與 workspace。

##### E. 同一 product run 的推薦流程與一致性

1. 員工訊息先以 immutable source 寫 Store；成功後才開始模型工作。
2. Context builder 從 checkpoint 讀目前 Work Understanding index／明確 refs，從 Store 取本輪 employee source；只把最小充分內容送模型。
3. 主顧問提出 Work Understanding create／revise／retire effects；application 驗 handle、current revision、source／quote、relation 與整批 invariant。
4. 一個 checkpoint transition 提交 Work Understanding、OpenIssue／coverage／Focus 調整與 operation receipt，並回 canonical handles／revisions。這一步後工作理解才是本輪可依賴的 authority。
5. 只有顧問判斷最新理解已足以新增／修正 JD 時，同一 **product run** 才繼續 JD Skill／Tool loop；它讀取剛提交的 canonical understanding basis。這可能增加一次 model continuation，但不是開第二場訪談或重播整段歷史。
6. JD workspace edit 若失敗，不回退正確的 Work Understanding；回精確 Tool error 讓同一 run 有界修正，或保留理解、下輪再重建 JD。JD 是工作理解的衍生編輯，不是兩者必須跨 Store／Saver 共同 commit 的單一資料庫 transaction。
7. checkpoint 最後記錄 run completed／failed 與必要 receipt；重開時從 Saver、Store 與 workspace 的 canonical state 重建，不依賴上輪 prompt 或 chain-of-thought。

這個流程符合 [OpenAI agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/) 與 [Anthropic Tool design](https://www.anthropic.com/engineering/writing-tools-for-agents) 的共同做法：模型提出動作，host 執行 deterministic validation／persistence，再用精簡、可行動的 Tool result 讓模型繼續；但 Work Understanding 的 domain transaction 仍是 Caliburn 自己的產品責任。

##### F. 何時才有資格翻成 Store owner

不以猜測或 framework 名稱翻案。至少出現以下一項可重現證據，才重開 successor ADR：

- 真實長訪談的 latest checkpoint bytes、serialization／resume latency 或 PostgreSQL growth 已影響產品；
- 同文件內的 handle／role／lifecycle selection 無法在有界 typed state 中可靠完成；
- 出現跨 thread／跨文件共用工作理解的正式產品需求；
- API／Web 需要不啟動 graph 就做大量 item-level query，且 derived read projection 不足；
- checkpoint retention／migration 造成可重現的恢復或維護問題。

重開時只比較**完整替代**：若 Store 勝出，就把 semantic body 全部遷成 Store sole owner，checkpoint 只留 immutable handles、expected revision、Focus／run receipts；不得雙寫。翻案須開 successor ADR，不修改 Accepted ADR 0060 的歷史文字。

##### G. 本輪結論與文件影響

1. §15.21.17 的「Work Understanding 由 Store 擁有」已撤回為第一版裁決；它只保留為研究過的候選。
2. Accepted ADR 0060 不改；Proposed ADR 0071 的 checkpoint owner、single writer、JIT Context 與 no-RAG 方向目前一致。
3. 不新增 production code、migration、Store namespace、LangMem、embedding 或第二 index；本輪只修正文檔認知。
4. `WorkUnderstanding／WorkEpisode／OpenIssue` 的語意角色、topic-sized records、三個基本操作仍屬可翻案候選；storage 裁決不代表其精確 schema 已核准。
5. OpenAI／Anthropic 是主要方法來源；Google／AWS 仍可留作次要「同目的機制已出貨」佐證，但後續 ADR／實作計畫不得用它們單獨推導架構。

## 16. Domain Semantic Memory 底層重審：Codex、Claude 與 LangMem（2026-08-29）

本節依 Owner 最新說明重開 §13.3、§14.7、§14.9 與 §15.21 對通用 memory framework 的裁決。研究問題不是「舊 `UnderstandingItem` 要不要換名字」，而是：

> Caliburn 要長期、完整、可反覆修訂地理解一位員工實際做什麼，再以這份理解形成 JD；OpenAI／Anthropic 已出貨的 memory 機制與 LangMem 能否取代自製的 LLM reconcile，哪些部分仍必須由 application 保證？

這次允許推翻既有設計，但不把相似名詞當成相同能力，也不因 framework 存在就先讓它接管 production authority。

### 16.1 先固定目的，不固定舊資料結構

本產品所稱 **Domain Semantic Memory**，目前就是前文的「工作理解」大概念；它必須：

1. 完整保存員工實際工作的流程、情境、責任、判斷、例外、協作與產出細節，而不是把對話壓成短摘要；
2. 隨訪談新增、補充、更正、拆開、合併、淘汰與保留未解問題；
3. 能追到員工原始訊息／逐字支持，避免顧問把推測沉澱成事實；
4. 與聊天歷史、active Context、JD、待審 diff、分析 Skill 分層；
5. 讓後續顧問與 JD Skill 按需讀到相關細節，而不是每輪全量注入；
6. 同輪若要依新理解編輯 JD，JD 階段只能讀到已驗證、已提交的最新 memory revision；
7. 員工主要審核 JD，不直接編輯這份內部 memory；若理解錯誤，員工以正常對話更正，系統再修訂 memory。

`WorkUnderstanding／WorkEpisode／OpenIssue`、一個工作主題一筆、三個基本操作等仍是目前候選，不是本節先驗前提。框架若有更好的 collection reconcile，可以替代機制；但「什麼算員工工作事實、一次事件或未知」仍須由職務分析 Skill／產品規則定義。

### 16.2 OpenAI Codex 真正出貨的 memory pipeline

[OpenAI Codex Memories](https://learn.chatgpt.com/docs/customization/memories) 與開源 [`codex-rs/memories/README.md`](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md) 已公開比「存摘要」更完整的兩階段流程：

1. **Phase 1：per-rollout extraction**
   - 從近期、已 idle、符合資格的 rollout 擷取結構化 `raw_memory`、`rollout_summary` 與 slug；
   - 多個 rollout 可平行處理，成功結果先寫入 DB；
   - 失敗會 backoff，不會 hot-loop 重試。
2. **Phase 2：global consolidation**
   - 以單一全域 lease／lock 串行整併；
   - 對 bounded inputs 做 added／retained／removed diff，按使用次數與最近使用／產生時間選取；
   - 以獨立 consolidation agent 更新 `MEMORY.md`、`memory_summary.md`、rollout summaries 與可重用 Skills；
   - 原始 rollout／raw evidence 不被 consolidation 直接改寫，失效內容依 input removal 做局部清理。

Codex 的 [`consolidation.md`](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md) 又把 artifacts 分成：

- `memory_summary.md`：永遠預載的高密度導航；
- `MEMORY.md`：可搜尋、可逐題群組的 durable handbook；
- `rollout_summaries/`：需要更精確證據時才讀的細節；
- raw rollout：不可變 evidence；
- Skills：由反覆成功方法才提升成程序知識。

它的 [`read_path.md`](https://github.com/openai/codex/blob/main/codex-rs/ext/memories/templates/memories/read_path.md) 也明確採 progressive disclosure：先看已注入的 summary，再以關鍵字搜尋 `MEMORY.md`，只打開 1～2 份最相關細節，理想上在 4～6 個查找步驟內停止；沒有相關結果就回到正常工作。官方設定另把 `extract_model` 與 `consolidation_model` 分開，證明 extraction 與 consolidation 可以獨立選模型、限制成本。[OpenAI Codex Memories](https://learn.chatgpt.com/docs/customization/memories)

可直接借用的不是其檔名，而是五個機制：

1. 原始互動、逐次抽取、整體整併與讀取導航分層；
2. extraction 與 consolidation 是不同責任；
3. 以 diff 做增量更新／忘記，不每次重建全部；
4. 小型 index 常駐，完整細節 JIT read；
5. supporting evidence 與 consolidated memory 分開保存。

不能照搬的部分也很清楚：Codex 的 memory 在 session idle 後背景更新，甚至可能因 rate-limit 門檻跳過；它被官方定位為 helpful recall layer，不是必須遵守規則的唯一 authority。Caliburn 的 Domain Semantic Memory 可能在**同一員工回合**立刻成為 JD 分析依據，因此不能等背景 consolidation 才成立，也不能讓 best-effort background job 成為唯一 writer。

### 16.3 Claude 的 index＋topic files、client-owned memory 與安全整併

[Claude Code memory](https://code.claude.com/docs/en/memory) 採另一種已出貨的 progressive-disclosure 實作：

- 每個 project 有 `MEMORY.md` index 與一個主題一檔的詳細 memory；
- 每輪只預載 index 的前 200 行／25KB；詳細 topic files 不預載，由 Claude 在需要時自行讀取；
- index 接近上限時，系統要求把細節移到 topic files、合併或刪除 stale entries；
- memory 是可檢視／修改的 context，不是 policy enforcement。

[Claude Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) 則把 storage／Tool execution 留給 client application：模型只提出 view／create／replace／insert／delete 等意圖，client 驗 path、執行並以 `is_error` 回精確錯誤。官方同時建議把 memory 與 compaction 一起用：compaction 控制 active conversation，memory 保存必須穿越摘要仍存在的資料；兩者不可互相取代。

Anthropic 的 managed memory 另有兩個可轉移的可靠性做法：

- [Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory) 的每次 mutation 都產生 immutable version，並以 `content_sha256` 做 optimistic concurrency；
- [Dreams](https://platform.claude.com/docs/en/managed-agents/dreams) 讀取既有 memory 與多個 sessions，將去重、矛盾／過時修正寫到**分離的 output store**，不直接改 input；結果可檢查、保留或丟棄。

Caliburn 可借用的是：小 index＋主題細節、host-owned Tool 執行、精確錯誤、compaction／memory 分層、consolidation 先寫候選而非直接覆蓋 canonical。不能直接採用 provider-managed storage／Dreams beta，因為本產品要求本機 PostgreSQL authority、可換模型，而且同輪工作理解更新不是非同步知識整理工作。

### 16.4 LangMem 與本需求的實際重疊

[LangMem Core Concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/) 把 semantic memory 分為單一 profile 與 collection。對本產品而言，collection 更接近目的：每筆 memory 是可獨立查找的紀錄；新訊息到來時要與既有 beliefs reconcile，新增、更新、合併或失效內容。官方也直接警告 collection 的品質取決於 over-extraction／under-extraction、更新／刪除與 recall，而不只是「能存 JSON」。

最重要的成熟 primitive 是 [`create_memory_manager`](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)：

- 輸入 conversation／新訊息與 `existing` memories；
- 由一個專門的 memory model 使用平行 Tool calls 判斷 insert／update／delete；
- 支援多個 custom Pydantic schemas；
- 回傳更新後的 `ExtractedMemory` collection 與 `RemoveDoc`；
- core API 不讀寫任何 database，caller 自行決定 removal 是 soft delete、retire、down-weight 或實體刪除；
- storage、revision、transaction 與 domain validation 因此仍可由 Caliburn 掌握。

這與目前自製 `_apply_understanding_changes()`／巨型 `ConsultantModelOutput` 的目的有高度重疊。現行 provider root 同時要求模型填 `visible_reply`、analysis bases、understanding changes、attention changes、gaps、question 與 sufficiency；單一 understanding item 又填 operation、ID、kind、text、impact、work IDs 與 basis ordinal。即使 wire schema 已避免 optional union，這仍把「理解員工、管理 memory、選訪談焦點、判斷缺口、回覆員工」塞入同一 structured-output 決策；它正是 Owner 先前觀察到填欄／重試成本變高的具體原因之一。

若 LangMem core spike 通過，它可替換的是**LLM 對既有 memory collection 的 reconciliation mechanism**，不是只在舊 reducer 外再套一層名稱：

- 新增／修訂／淘汰選擇由 memory manager 的既有框架機制處理；
- main consultant 不再輸出舊 `UnderstandingChange`、`Gap`、`Attention` 全套欄位；
- application 仍把 manager 結果轉成唯一 canonical changeset，驗證後一次寫入 checkpoint；
- OpenIssue／Focus／coverage 是否分成 memory record 或 projection，仍依最新產品語意裁決，不由 LangMem 名稱決定。

### 16.5 為何現在只做 core manager spike，不直接接 Store manager／memory tools

功能相近不代表 production 路徑已成熟。2026-08-29 的直接證據是：

1. [LangMem PyPI](https://pypi.org/project/langmem/) 最新仍為 `0.0.30`（2025-10-27），pre-1.0，PyPI 列一位 maintainer；這是 API／維護風險訊號，不是判定功能無效。
2. [`create_memory_manager`＋`BaseChatModel` issue #106](https://github.com/langchain-ai/langmem/issues/106) 仍為 Open：傳入 pre-instantiated `BaseChatModel` 時可能出現 strict function schema 失敗；本 repo 正使用自訂 `ReceiptChatOpenRouter(ChatOpenRouter)`，所以不是理論風險。
3. [`create_memory_store_manager` 與 memory Tool schema mismatch #138](https://github.com/langchain-ai/langmem/issues/138) 與 [PostgresStore 寫入後 search tool 找不到 #140](https://github.com/langchain-ai/langmem/issues/140) 顯示 direct Store integration／hot＋background 組合仍有未解相容問題。
4. LangMem 官方也承認單次 manager call 同時管理大量 inserts／updates／deletes 可能讓模型多工過重；資訊很多時可改成多步 memory agent，但會增加延遲與成本。[LangMem semantic-memory guide](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)

因此第一候選必須是**無 storage side effect 的 core `create_memory_manager`**，而不是：

- 把 model-facing `create_manage_memory_tool` 直接接上 production Store；
- 讓 LangMem Store manager 成為第二個 Work Understanding writer；
- 為繞過 issue #106 改用 framework 的 provider string，跳過本產品的 OpenRouter adapter、receipt 與可換模型邊界；
- 先把 checkpoint semantic authority 搬到 Store，再用產品測試找問題。

### 16.6 框架／產品責任對照

| 能力 | 推薦 owner／primitive | 可以替代多少自製機制 | 仍不可外包的產品責任 |
| --- | --- | --- | --- |
| 原始員工對話與逐字來源 | LangGraph Store 的 immutable document-source namespace | storage、scope query、durability | 哪段員工話支持哪項職務理解、correction lineage |
| thread resume／HITL／當前 semantic snapshot | LangGraph Postgres checkpointer | persistence、checkpoint、resume、time travel | 哪些 state 是 canonical Domain Semantic Memory |
| semantic collection reconcile | **LangMem core `create_memory_manager`，待 spike** | 既有 collection 的 insert／update／delete／consolidate 決策 | 職務語意 schema、來源 closure、revision、原子提交、合法 relation |
| schema shape | LangMem custom Pydantic schemas＋Pydantic validation | tagged memory variants、解析與基本型別錯誤 | body 是否忠實、工作事實與案例／未知的專業判斷 |
| ID、version、timestamp、lifecycle | application envelope／checkpoint transition | 不讓模型填、可重播 ID 與 lineage | stable identity、expected revision、retire／supersede 規則 |
| 記憶導航 | 從 canonical collection deterministic 重建的 read-only memory map | index、preview、filter、handle resolution | 哪些 refs 必帶、何時需讀原始來源 |
| JIT detail read | Deep Agents／LangGraph Store-style read primitive 或現有 VFS projection | `grep／read`、path containment、Tool errors | memory 本體仍由 checkpoint 單一擁有；projection 不可寫回成第二 truth |
| 對話 context 壓縮 | provider／LangChain compaction | 移除舊 Tool traces、縮短聊天 transport | 不得 compact Domain Semantic Memory、來源、目前 JD 或待審 basis |
| JD 形成與編輯 | 主顧問＋按需 Task／Duty／OPKS／JD Skills＋workspace Tools | Tool loop、structured errors、checkpoint continuation | 專業分析方法、何時足以編輯 JD、員工核准 seam |

這個 mapping 的核心是：**framework 可以替換 reconcile mechanism，但不能讓同一份 memory 同時由 LangMem Store 與 LangGraph checkpoint 寫入。** Core manager 是 pure transformation；canonical state 仍只有一份。

### 16.7 第一候選流程：hot-path memory manager＋已提交理解後的顧問階段

若窄 spike 通過，第一版候選改成：

1. 員工訊息先寫入 immutable source Store。
2. Context builder 提供本輪訊息、最短必要近期對話與可重建 memory map；只預載員工明確引用、目前待審 JD 變更的直接 basis，以及精確 deterministic match 命中的少量 current records。其餘細節由主顧問透過 memory search／read 按需取得，不全量重播對話，也不再把持久 Focus／OpenIssue 當成召回成立的必要條件。
3. LangMem core manager 專心產生 Domain Semantic Memory 的 candidate collection changes；它不回 user-facing reply、不編輯 JD、不寫 database。
4. application 把 manager 結果轉成 app-owned atomic changeset，補 canonical IDs／revision／time，驗 exact quote／source handle、target current revision、relation 與 role invariant；任一錯誤整批不寫，回短 typed diagnostic 做有界修正。
5. 一個 checkpoint transition 寫入驗證後的 canonical Domain Semantic Memory 與必要 runtime refs。此時新理解才可被後續階段依賴。
6. 主顧問讀最新 canonical memory，正常回覆／提問；只有理解已足以影響 JD 時才載入相關 JD Skills／Tools 編輯共同 workspace。
7. 可選的背景 consolidation 日後只能產生**分離候選**，不得直接覆寫 canonical memory；這沿用 Codex Phase 2／Claude Dreams 的 safe-consolidation 形狀。

這個候選會讓多數工作相關回合至少多一個專用 memory model step；它不是免費優化。因此尚不能只因 schema 變小就採用。效果優先，但必須同時量測：理解遺漏／誤改、重複 memory、修正傳播、模型修復次數、input／output tokens、首字延遲與整輪延遲。若效果只小幅提升而成本接近倍增，就不值得。

這也不等於「固定兩個 agent」：仍是一個產品 run 與一條 LangGraph workflow；只是把 memory reconcile 與 user-facing consultant 分成兩個有明確 state boundary 的 model stages。JD 階段仍按需，不固定每輪執行。

### 16.8 Model-facing schema 必須縮到語意，不重建另一個巨型 contract

LangMem spike 的 custom schemas 應以 §15.21 最新語意責任為起點，但只放模型真正知道的內容。暫定原則：

- schema variant 本身表示 `WorkUnderstanding／WorkEpisode／OpenIssue`，不再要求模型重複填 role enum；
- memory manager 的 insert／update／delete 行為表示 operation，不再要求另一個 operation enum；
- 模型填完整 `body`；需要直接支持時填當輪 exact quote，application 驗證為 source substring；
- 只有確有必要時選 runtime 已提供的 related memory handles；不得自行造 UUID；
- 新 ID、revision、timestamp、lifecycle、run ID、Skill ID、confidence、coverage、Focus、JD mapping 與 transaction ID 全由 framework receipt／application 產生；
- `OpenIssue` 由「缺資料」形成時可以沒有 quote；它不能被 dummy quote 或模型猜測填滿。

必須特別驗證 LangMem 如何保留既有 stable ID：對 existing records 的更新要能映回同一 app identity；新 memory 的 library ID 只能當本次 temporary result handle，由 application 換成 canonical ID。`RemoveDoc` 不直接 hard-delete，而先映成 app 的 retire／supersede candidate，保留來源與 revision history。

### 16.9 完整保存與 Context retrieval：memory map 是 projection，不是第二份 Memory

OpenAI 與 Anthropic 的共同設計不是「每輪把所有 memory 塞進 prompt」，而是 **small routing layer → search → relevant details → evidence if needed**。[Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 同樣主張最小高訊號 Context、lightweight identifiers 與 JIT loading。Owner 於 2026-08-30 進一步裁決：召回入口只依本輪 conversation、這份小型 map、明確 direct references／JD basis 與實際 search 結果；不得因舊設計已有 Focus／OpenIssue 就把它們設為必經 routing key。Focus 日後即使因其他產品目的保留，也只能是可選的 runtime hint，不能成為「沒有它就找不到 memory」的前提。

Caliburn 因此需要一份從 canonical collection 隨時可重建的 memory map，例如每筆只含：

```text
handle | role | lifecycle | current revision | body preview | direct relation handles
```

它不是第二份可寫 memory，也不另外做 LLM summary；`body preview` 第一版可 deterministic 截斷。完整 body、來源與歷史 revision 仍只在 canonical records／source Store。若 projection 消失或 schema 更新，可從 canonical collection 重建。

現行 `context.py` 已有 `_orientation()` 與 `_understanding_slice()` 雛形，但還不是正式 long-memory read path：前者把完整 `text` 當 label，後者主要依 challenged／current work／recent revision 選取，舊但語意相關的細節可能沒有明確可讀路徑。後續實作不應把 `max_items` 調大解決，而應 characterise：index 是否能路由到正確 handle、Tool 是否能讀完整 record、無 anchor 的更正是否能經 hybrid search 找到候選。

Owner 於 2026-08-30 取代本節較早的「第一版僅 lexical／structured recall」限制：若採成熟框架實作，Domain Semantic Memory 的 read projection 可使用 **metadata／stable-handle filter＋lexical／BM25＋vector semantic search＋必要時 reranking** 的混合召回。[OpenAI Vector Store Search](https://developers.openai.com/api/reference/python/resources/vector_stores/methods/search) 已出貨自然語言 query、attribute filters、query rewrite、ranking options 與 similarity score；[Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) 明確建議 embeddings 與 BM25 互補、以 rank fusion 合併，資料量增長時再使用可擴充檢索。這些來源證明 hybrid vector RAG 是成熟大廠作法，但**沒有證明 Codex／Claude 的個人或專案 Memory 內部必然使用向量檢索**；因此本產品可採相同 retrieval primitive，不能冒稱照抄其私有 Memory pipeline。

這項裁決只開放「從 canonical Domain Semantic Memory 建立可刪除重建的 semantic read index」，不代表接回 ADR 0057 隔離的 Reference／公版 RAG bounded context，也不建立第二 canonical writer。是否第一版立即啟用向量索引，留給後續依 memory 規模、召回品質、延遲與成本選擇成熟框架；架構不得再禁止它。

### 16.10 窄 spike：先驗證效果與相容，不做正式 eval 或 production migration

> **2026-08-29 實驗結果：** 已完成一次成本封頂的 compatibility／quality probe；現行 adapter 與 Luna medium 相容，固定 synthetic transcript 的細節保留、更正、未知與一次性事件行為通過，但 source／checkpoint rollback／JIT retrieval 尚未驗證。完整證據、成本與限制見 [`2026-08-29-langmem-domain-semantic-memory-spike-experiment.md`](2026-08-29-langmem-domain-semantic-memory-spike-experiment.md)。

這次新研究已構成做 spike 的合理理由：

- 現行 production `ConsultantModelOutput` 仍是多責任複合 schema；
- 專案已實際遇過 structured output／quote／repair 成本；
- Owner 已明確要求優先比較成熟框架能否替代同目的自製元件；
- LangMem core API 的能力與本需求高度重疊，但現行 OpenRouter adapter 相容性未證明。

因此下一步只做**隔離、可丟棄、無 DB migration 的 compatibility／quality spike**。不是正式 eval；固定少量 transcript 即可：

1. **初次完整敘述**：一則中文訊息同時包含兩個可獨立工作主題，應建立正確 collection，不過度拆成一句一筆。
2. **局部補充**：補充同一工作細節，只 revise 目標 memory，未提及細節完整保留。
3. **明確更正**：「最後是處長核准，不是科長」只建立目標新 revision，無關 records 不變，舊 source／revision lineage 仍可追。
4. **事件不可過度一般化**：一次臨時支援先形成 episode／issue，不自動變固定責任。
5. **衝突與未知**：模糊否定不採 latest-wins，保留 OpenIssue／需要確認的候選。
6. **長 collection recall**：至少 8～10 筆 current records，只給 index＋相關 details，仍能找到舊但相關目標、不 duplicate。
7. **現行 adapter**：必須直接使用 `ReceiptChatOpenRouter` 與使用者指定的 `gpt-5.6-luna`／`max` 測試 strict schema、parallel Tool calls、receipt、token 與 retry；不能以 provider string workaround 冒充相容。

比較重點依 Owner 修正為**效果與功能優先**，不是少寫幾行：

- 是否完整保留細節；
- 是否選對 revise／retire target；
- 是否不亂新增／合併；
- correction 是否只傳播到直接依賴；
- source／quote 是否可 deterministic 驗證；
- 一輪需要多少 model steps／repair、tokens 與延遲；
- crash／validation error 後能否不污染 canonical checkpoint。

停止條件：如果 issue #106 在現行 adapter 可重現且無薄、provider-neutral 修法；或 manager 需要 direct Store writer；或 fixed cases 出現未提及細節遺失、錯 target、無法映射 stable ID、成本大增但品質沒有明顯提升，便不導入 production。可以記錄 upstream issue／最小 patch 候選，但不能把整個產品綁到私有 fork。

### 16.11 本輪暫定裁決

1. **產品概念正確且不屬過度設計**：Domain Semantic Memory 是長訪談下維持完整工作理解的必要層；它不是聊天摘要、JD 或 RAG。
2. **OpenAI／Anthropic 的共同成熟形狀**是：immutable history／evidence → extraction／revision → consolidated memory → small index → JIT detail；active context compaction 與 durable memory 分離。
3. **LangMem core manager 是目前找到最直接覆蓋自製 reconcile 的框架元件**；早期「沒有 production failure 前不做 canary」已撤回，現在應做窄 spike。
4. **尚未核准 production 導入**：LangMem pre-1.0、Store integration issues 與 `BaseChatModel` strict-schema issue 都是實際風險；通過 spike 後才可開 successor ADR／更新 ADR 0071 與施工計畫。
5. **canonical owner 暫不改**：第一版仍由 LangGraph typed checkpoint 單獨保存 Domain Semantic Memory。這不妨礙使用 LangMem core，因為 core manager 是 caller-owned storage 的 pure transformation；不得因此新增第二 Store authority。
6. **不採 direct memory Tool／Store manager、不接 RAG、不做 embedding、不把背景 consolidation 當同輪 authority。**
7. **如果 spike 通過**，主顧問舊的 understanding／gap／attention 複合輸出應被真正移除，由專用 memory stage＋framework result 接管，而不是把 LangMem 疊在舊 schema 外面。
8. **如果 spike 不通過**，也不能恢復舊巨型 contract；應依最新 field audit 把自製 fallback 限縮為最小 tagged semantic effects，並保留未來替換 port。

這是可翻案的研究裁決。它修改的是「現在是否值得驗證成熟 memory manager」；尚未翻案 Domain Semantic Memory 的產品目的、immutable source、員工 JD 核准權、同輪先提交理解再依理解編輯 JD、single canonical owner 與 no-RAG 邊界。
