# 一般訪談提問與未解資訊最小契約（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q013`
- 階段：`G3 — Owner Decision complete`
- 狀態：**WORKING；Product Owner 已核准方案 B**
- 本輪唯一問題：一般訪談回合要用什麼最小輸出契約，才能自然提問、保存影響後續 JD 的未解資訊，又不讓模型填寫另一套容易失敗的 clarification schema？
- 父決策：`LLM-Q012` 已核准第一版沒有員工輸入型 unfinished workflow；所有訪談問題皆為 normal assistant completion。
- production authority：現行 code 與 Accepted ADR 0060 仍有效；本文件不授權施工。

## 1. 先固定產品效果，不先固定舊欄位

第一版必須做到：

1. 顧問可在正常回覆中自然提出一個目前最值得回答的問題；沒有必要時不必硬問。
2. 回覆完成後聊天室保持可輸入；員工可以回答、補充別件工作、離開後再回來。
3. 員工下一則訊息啟動新的 bounded invocation，而不是恢復一個等待中的舊 run。
4. 尚未回答但會影響後續分析的未知、矛盾或重要缺口，不因長對話或 compaction 永久遺失。
5. 問題文字只有一個 canonical 表示，避免聊天回覆與獨立問題欄位不一致。
6. 問題本身不鎖 JD、不建立 pending execution，也不要求模型填 UI routing、版本、ID 或 lifecycle metadata。

本題只決定「一般提問」的契約。理解更新、JD 變更與其他 machine effects 最終應使用 Tool 還是 structured response，另開後續決策；不能偷渡進本題。

## 2. 最新官方能力與共同邊界

### 2.1 OpenAI

OpenAI Responses API 的正常介面是讓模型產生 text／JSON output；conversation 會將既有 items 放入下一次 request，完成後的 input／output 也會加入該 conversation。自訂程式動作另由 function／custom tools 承接。API 的文字格式預設就是 `text`，不是每次對話都必須先定義一個問題 schema。

OpenAI 最新 model guidance 也把 plain conversational formatting 當一般對話預設；只有需要自動驗證或產品 UI 的穩定 artifact 時才使用 Structured Outputs，內部系統／business workflow 則使用 Tool calling。這支持「對人說的話」與「給機器執行的資料」分離。

來源：

- [OpenAI Responses API — create response、conversation、text 與 tools](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [OpenAI latest model guidance — plain conversation、Structured Outputs 與 Tool calling](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)

### 2.2 Anthropic

Anthropic Messages API 的 normal multi-turn 介面，是輸入 user／assistant messages 後產生下一則 assistant message；`end_turn` 代表模型自然完成本輪，應直接使用這則回覆。只有 `tool_use` 才要求應用執行 Tool 並把 `tool_result` 回傳。Anthropic 另提供 structured outputs，但用途是讓 downstream 程式取得可驗證 JSON，不是一般提問的必備包裝。

來源：

- [Anthropic Messages API — normal multi-turn 與 assistant message](https://platform.claude.com/docs/en/api/messages/create)
- [Anthropic stop reasons — `end_turn` 與 `tool_use` 的處理分界](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons)
- [Anthropic structured outputs — 需要 schema-compliant JSON 時使用](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

### 2.3 LangChain／LangGraph

LangChain 用 `AIMessage` 表示 provider-neutral 的模型訊息，內容可包含文字與 Tool calls。Agent loop 在模型不再呼叫 Tool 時，以 final output 結束；`response_format=None` 表示不要求 structured response。只有 downstream 確實需要可預測資料時，才提供 schema，並由 ProviderStrategy／ToolStrategy 承接。

來源：

- [LangChain Messages — `AIMessage`、文字與 Tool calls](https://docs.langchain.com/oss/python/langchain/messages)
- [LangChain Agents — message state 與 agent loop](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain Structured Output — `response_format=None` 與 schema 策略](https://docs.langchain.com/oss/python/langchain/structured-output)

### 2.4 能與不能宣稱的共識

可宣稱的共同邊界：

- 正常的人機對話以 user／assistant message 表達；
- Tool call 用於要由程式執行、驗證或取得結果的動作；
- structured output 用於 downstream 需要穩定、機器可讀資料的情境；
- 長期未解資訊是否另存 Memory，是應用的記憶政策，不應與「畫面是否顯示問題卡」混成同一生命週期。

不能宣稱：

- 廠商共同規定每輪只能問一題；
- 廠商共同規定未知一定要存成 Caliburn Semantic Memory；
- 廠商共同禁止問題卡或選項；
- 廠商共同採用本文件的方案名稱。

「每輪最多一個主要問題」與「重要未解資訊進既有 Semantic Memory」都是依 Caliburn 長訪談目的作出的產品推論。

## 3. 與既有 Memory 契約的接點

目前已核准的 framework-independent Memory contract 已經規定：

- 未知與未解衝突是合法的目前知識；
- 模型只撰寫既有的 `title／topic＋rich self-contained content`；
- 不新增 `status`、`kind`、`conflict_type`、`confidence`、quote offset、版本或時間等模型欄位；
- 可獨立理解的待釐清內容，可以是同一形狀的 focused Memory；否則留在相關主題 Memory 內；
- visible reminder 若存在，只是可重建 projection，不是第二份 authority。

因此本題沒有理由再建立 `PendingQuestion`、`GapQuestion`、`ClarificationState` 或其他新資料形狀。若某個問題只是當下自然追問，conversation 已完整保存；只有其背後的未知／矛盾會影響未來 JD 且必須跨長訪談保留時，才透過既有 Memory 更新流程保存「尚未確定的工作理解」，而不是保存 UI 問句本身。

依據：

- [Framework-independent Memory contract](./2026-09-01-framework-independent-memory-contract.md) §3.2、§3.4
- [相似案例、細節與 consolidation reconciliation](./2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md)

## 4. 現行 code diagnosis（只作 migration inventory）

現行 branch 同時存在兩份問題表示：

1. 對員工顯示的 `visible_reply`；
2. 另一個 `question` union，要求模型選 `none／next／required_clarification`，並視種類填 `answer_target`、`reason`、`current_understanding`、`choices`、`affected_work_ids`、`affected_branch`、`basis_ordinal` 等欄位。

Web 又同時顯示 canonical chat message 與由 `next_question` 建出的「目前問題」卡。這會造成：

- 同一句問題可在兩處不同步；
- 純文字訪談被迫承擔 UI／routing schema；
- optional／union 欄位增加 provider strict-schema 與模型填錯面；
- `required_clarification` 還額外建立 state、API、interrupt 與鎖定行為，但 `LLM-Q012` 已判定第一版沒有這種 unfinished workflow。

相關位置：

- `apps/api/app/consultant/model_output.py`
- `apps/api/app/consultant/results.py`
- `apps/api/app/consultant/context.py`
- `apps/api/app/consultant/state.py`
- `apps/api/app/consultant/graph.py`
- `apps/api/app/api/routes/consultant.py`
- `apps/web/src/features/consultant/ConsultantConversation.tsx`
- `apps/web/src/features/consultant/consultantWorkspaceModel.ts`

這些名稱不是目標設計；只用來確保未來受控替換沒有漏掉舊生命週期。

## 5. 三個候選方案

| 方案 | 一般問題如何輸出 | 未解資訊如何保存 | 優點 | 主要風險 |
|---|---|---|---|---|
| A．只有 assistant message | 問題只寫在自然語言回覆 | 只靠 canonical conversation | 最小、最自然、沒有重複 schema | 長對話經 compaction 或有界召回後，重要未解歧義可能不容易重新取得 |
| **B．assistant message＋既有 Semantic Memory（建議）** | 問題只寫在自然語言回覆 | conversation 保存實際對話；只有影響未來 JD 的未知／矛盾，以既有 content-only Memory 更新保存 | 不新增問題型別；可跨長訪談保留真正重要的未解資訊；符合已核准 Memory 邊界 | 仍須後續驗證 Memory prompt 能區分「普通追問」和「必須長期保留的未知」 |
| C．結構化問題 envelope＋Memory | 額外輸出問題文字、選項、原因、相關 ID 等 | 同 B | UI 可直接做卡片與選項 | 問題文字重複；schema 與 retry 面增大；第一版沒有證據需要這些 machine-readable 欄位 |

## 6. 建議方案 B 的精確契約

若 Owner 核准方案 B，G4 target contract 是：

1. **唯一對話表示**：顧問對員工說的完整內容只存在 canonical assistant message。若問題必要，它自然寫在訊息末段；不再另外輸出 `question.text`。
2. **正常結束**：模型完成回覆後，本輪即完成。員工下一則文字是新的 user message／bounded invocation。
3. **Prompt policy，不是 schema**：指示顧問在確實需要員工資料時提出一個清楚、聚焦的主要問題；不需要時不硬問。這不要求模型回報 `kind`、`reason`、`answer_target` 或 UI metadata。
4. **未解資訊的持久化條件**：只有未知、矛盾或缺漏會影響未來 JD，且不能安全只留在近期 conversation 時，才交給既有 Semantic Memory extraction／consolidation 流程，以自然語言工作理解保存。
5. **不保存 UI 問句副本**：Memory 保存的是「目前知道什麼、哪裡仍不確定、為何不能下結論」，不是把 assistant 的問題文字再抄一次。
6. **沒有新 lifecycle**：不建立 pending question ID、answer API、resume token、affected branch、stale state 或聊天室鎖定。
7. **Machine effects 另題處理**：本題不決定 understanding／JD changes 最後透過 Tool 還是 structured output；無論哪種，對人說的問題都不應成為同一大型 machine schema 的 UI 子物件。

概念流程：

```text
員工訊息
  → 新 bounded invocation 讀取必要 conversation／Memory
  → 模型可使用既有 Tool／Memory 能力
  → 必要的未解工作資訊寫入或修訂既有 Semantic Memory
  → 產生一則 canonical assistant message（可自然包含一個主要問題）
  → 本輪完成；聊天室保持可輸入
  → 員工下一則訊息開啟下一輪
```

## 7. 未來受控替換範圍

方案獲核准後仍不能直接施工。後續順序應是：

1. successor ADR 只取代 ADR 0060 的 required-clarification／interrupt 部分，不順便改變其他 authority；
2. 另定 machine effects 的最小 contract，避免誤把整個 agent output 架構偷定在本題；
3. 寫一個垂直切片 plan，移除第一版訪談的專用 question union、interrupt state、answer API 與問題卡 projection；
4. 驗證一般問題只出現一次、聊天室不鎖、員工改談別題仍可分析、重要未解歧義可由既有 Memory 找回；
5. 只有 G5 驗證通過才考慮 production merge。

## 8. 驗收情境（現在只定效果）

1. 顧問問「這項工作是每週固定執行，還是有案件才處理？」；員工可立即回答，也可先補充另一項工作。
2. 員工未回答上一題並關閉頁面；重開後沒有 pending run，但相關未知若會影響 JD，仍可由 Memory 找回。
3. 顧問回覆中沒有問題時，不產生空 question object 或 sentinel 欄位。
4. 顧問發現前後說法衝突時，先保存未解工作理解並自然詢問；不得自行選最近一句為真，也不得亂改相依 JD。
5. 員工下一則回答必須進正常 analysis，而不是只清除 blocker 後結束。
6. 同一個問題不能同時以聊天文字和另一張不同內容的問題卡出現。

## 9. Parking lot

以下不阻塞 `LLM-Q013`：

- 問題卡、quick replies 或自由文字選項的 UI；
- machine effects 採 Tool calls 或 structured response；
- Memory extraction／consolidation 的正式 prompt 與模型選擇；
- provider 版本、retry 數字、成本 characterization；
- production migration、舊資料、merge、push。

## 10. Product Owner 裁決

Product Owner 於 2026-09-04 明確回覆「同意」，核准 **方案 B：canonical assistant message＋既有 content-only Semantic Memory**：

- 一般訪談問題只存在 canonical assistant message；
- 只有會影響未來 JD 的未解工作資訊，才透過既有 content-only Semantic Memory 保存；
- 第一版不建立專用 question schema、pending question state 或 answer／resume lifecycle；
- 問題卡與快捷選項若日後需要，只是 UI presentation，不得倒逼模型填另一套權威資料。

這項 Working Decision 約束後續設計，但本文件本身仍不取代 Accepted ADR 0060，也不授權修改 production。

下一個 gate：另開單一題，決定理解／Memory／JD 候選變更等 **machine effects** 應如何使用 framework-native Tool calling 或 structured output；收斂後才開 successor ADR，精確取代 ADR 0060 的 required-clarification 部分。

## 11. Closure

```text
Decision:
  採方案 B。對人的問題只有 canonical assistant message；跨回合要保留的是影響 JD 的未解工作資訊，並沿用既有 content-only Semantic Memory。
Status:
  G3 complete；Product Owner 已核准。尚未改變 production authority。
Why:
  OpenAI、Anthropic 與 LangChain 的正常對話 primitive 都是 assistant message；Tool／structured output 用於程式動作或 machine-readable artifact。方案 B 同時避免問題文字重複與重要未知在長訪談中遺失。
Supersedes for first-version interview:
  專用 next-question／required-clarification schema 與 pending execution 方向；實際 code／ADR 仍待 successor ADR 與 implementation gate 才能替換。
Next gate:
  machine-effects 最小契約；不在本題偷定 Tool、structured response、Memory write 或 JD edit schema。
```
