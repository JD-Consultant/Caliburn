---
title: OPKS 漸進式蒐集——從一次性建議器到會追問的顧問
date: 2026-08-04
status: 待審（三案並列，**B 為建議方案**；owner 已認可 B 的自動觸發成本）
purpose: 裁決 OPKS 生成在證據不足時該怎麼辦，並把建議方案壓到最小可行形狀
---

# OPKS 漸進式蒐集研究

## 0. 這份回答什麼、不回答什麼

**回答**：OPKS 生成發現證據不足時，缺口怎麼表示、誰觸發下一次分析、追問長在哪裡、
成本與失敗邊界在哪。

**不回答**：每個欄位怎麼寫才合格（判準教材已備齊，見
[iCAP 逐欄位標準](2026-07-13-ai-redesign-raw-icap-field-standards.md)、
[國際體系欄位定義](2026-07-13-ai-redesign-raw-intl-competency-standards.md)）；
OPKS 的概念與持久化形狀（已由 ADR [0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)
＋[0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)
＋[0050](../adr/0050-opks-proposal-minimal-shape.md)
＋[0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md) 裁決，本文不翻案）。

**本輪不動任何程式碼。**

---

## 1. 現況：模型說「我不確定」等於沒說

| 事實 | 證據 |
|---|---|
| `uncertain` 被靜默丟棄 | [`opks_verifier.py:237`](../../apps/api/app/job_analysis/application/opks_verifier.py#L237) 直接 `continue` |
| `uncertain` 在契約上**無法**承載任何資訊 | [`opks_prompt.py:24`](../../apps/api/app/job_analysis/llm/opks_prompt.py#L24) 規定 `target_ordinal=0, text=""`；verifier 的 `_payload_is_valid` 對應 `not has_target and not has_text` |
| 沒有「這批證據分析過了嗎」的證明 | `OpksGenerationPayload` 只有 `operation_id / selected_task_id / outcome / proposal_ids`（[`opks_generation.py:228`](../../apps/api/app/job_analysis/application/opks_generation.py#L228)） |
| Journal 只能按 `entry_id` 查 | `JournalRepository` 只有 `get / add / list_conversation_turns`（[`persistence.py:388`](../../apps/api/app/job_analysis/application/persistence.py#L388)） |
| 觸發完全靠員工按鈕 | `POST …/tasks/{task_id}/opks-proposals` 是唯一入口 |

所以現行 OPKS 是**一次性候選生成器**：它知道「有沒有資格分析」（Task ACTIVE、有有效員工依據），
不知道「資料夠不夠」，也沒有地方保存「缺什麼」。

**但追問機制本身已經存在**，只是 OPKS 沒接上：Task Analysis 每輪產出 `next_question`，
`OpenIssue` 可由模型以 `resolves_open_issue_ordinal` 關閉（[`transition.py:261`](../../apps/api/app/job_analysis/application/transition.py#L261)），
`last_asked_turn_id` 兩種 target 都記（ADR [0047](../adr/0047-model-owned-open-issue-closure.md)）。

---

## 2. 2026 權威資料核對

### 2.1 「有沒有問」是大差距，「問得多聰明」是小差距

[Ask or Assume?（arXiv 2603.26233v2, 2026）](https://arxiv.org/html/2603.26233v2) 在 underspecified
SWE-bench 上量到：完全不問 **54.8%** → 校準式追問 61.2–69.4% → 每次都問 **70.4%**。
校準的價值不在準確度（對比「每次都問」只差約 1 個百分點），而在打擾成本
（Claude Sonnet 4.5 平均 3.06 次詢問／題，Kimi K2.6 為 8.71）。

同篇另一個結論直接影響架構：**把「偵測資訊不足」與「執行工作」拆開**，比單一 agent
邊做邊判斷顯著更好（69.40% vs 61.20–61.60%）。

[SAGE-Agent（arXiv 2511.08798）](https://arxiv.org/abs/2511.08798) 同向：覆蓋率 +7–39%
而詢問次數少 1.5–2.7 倍。[ICML 2026 的 Information Gain Reward](https://icml.cc/virtual/2026/poster/66065)
用 Bayesian belief update 選問題，成功率僅 **+3.7%**、平均多 0.3 個互動步驟。

→ **不建 EVPI／資訊增益機器。** 價值集中在「能問、缺口能持久」，不在選題演算法。

### 2.2 大廠怎麼放追問

| | [Anthropic `AskUserQuestion`](https://code.claude.com/docs/en/agent-sdk/user-input)（官方 Agent SDK 文件） | [OpenAI Deep Research clarifier](https://developers.openai.com/cookbook/examples/deep_research_api/introduction_to_deep_research_api)（官方 cookbook） |
|---|---|---|
| 問在哪 | 同一 session 中途暫停，提問卡；不是第二條對話 | 主對話、**開跑之前** |
| 誰問 | 主 agent 自己（**它就是對話擁有者**） | 另一個便宜模型先問，答案改寫成 brief 餵給貴模型 |
| 一次幾題 | **1–4 題，每題 2–4 個選項** | **3–6 題** |
| 判準 | 有多個都成立的做法時才問 | 會改變答案的**結構、深度或方向**才問 |
| 逃生口 | host 須自加「Other」自由輸入；使用者可關卡直接打字（`response` 欄） | 不答走預設 |
| 可恢復 | callback 可無限期 pending，另有 `defer` 讓行程退出、**之後從持久 session 續問** | — |

**適用邊界（本輪修正）**：`AskUserQuestion` 的形狀對映到**主顧問**，不對映到 OPKS。
該先例裡發問的 agent 就是對話擁有者；OPKS 是 specialist，不擁有對話。詳見 §4.4。

[Anthropic 的 agent autonomy 量測](https://www.anthropic.com/research/measuring-agent-autonomy)（2026-02）
另有一句可當設計態度：最複雜的任務上，Claude Code 主動要求澄清的頻率
「more than twice as often as humans choose to interrupt it」——**主動問不是失敗訊號**。

### 2.3 流程該由誰控制：workflow 先於 agent

[Anthropic《Building Effective Agents》](https://www.anthropic.com/engineering/building-effective-agents) 逐字：

> **Workflows** are systems where LLMs and tools are orchestrated through **predefined code paths**.
> **Agents** are systems where LLMs **dynamically direct their own processes and tool usage**.

> we recommend finding the simplest solution possible, and only increasing complexity when needed.
> **This might mean not building agentic systems at all.**

> **Agentic systems often trade latency and cost for better task performance.** … you should consider
> adding complexity **only** when it demonstrably improves outcomes.

[OpenAI《A practical guide to building agents》](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
建議先單一 agent、逐步加 tool；**拆 specialist 的觸發症狀**是「agent 跟不上複雜指令、
持續選錯工具、prompt 裡 if-then-else 多到難以維護」。

→ 「這項工作該不該深挖 OPKS」**不是 ambiguity**，是可由純函式判定的條件，
不該花一次 reasoning=high 推論去回答布林式。這與 ADR [0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md)
決定 1（readiness 是 `app/job_analysis` 的純函式）是同一條紀律。
OPKS 拆成獨立 operation 仍然成立——它有自己的 prompt／schema／verifier（ADR 0049 決定 14）。

### 2.4 「完整」在權威體系裡沒有第三種說法

- [29 CFR §1607.14C(2)](https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XIV/part-1607/subject-group-ECFRe6113332da568d1/section-1607.14)
  要求涵蓋 *critical or important work behaviors*——是**重要性**判準，不是欄位齊全判準。
- 質性研究的[飽和](https://www.sciencedirect.com/science/article/pii/S0277953621008558)（Hennink & Kaiser 2022,
  *Soc Sci Med*）是**操作型停止規則**（再問不再產生新編碼就停），不是完整性宣告。
- iCAP 官方允許操作型任務省略工作產出、態度「視需求納入」（ADR 0052 決定 15–16）。

→ 系統可以誠實說的只有「這批資料再追問已問不出新東西」。**不得宣稱完整**，
也不得用「不完整／不合格／未通過」（ADR 0052 決定 7 措辭禁令）。

### 2.5 durable execution：child operation 的 ID 與失敗語意

[Temporal 官方 child workflow 文件](https://docs.temporal.io/child-workflows)給的是**反向告誡**：

> **There is no reason to use Child Workflows just for code organization.** … When in doubt, use an Activity.

→ OPKS 拆成獨立 durable operation 的正當理由**不是分檔案**，是它必須能獨立失敗與恢復。
這條理由要寫進 ADR，否則就是為拆而拆。

「child ID 由 parent 決定性推導以取得去重」是**實務慣例，非該頁官方條文**（見 §7 查證層級）。
真正官方且可引的是失敗語意：[Azure Durable Task 程式模型](https://docs.azure.cn/en-us/durable-task/common/programming-model-overview)
明示 activity 只保證 **at-least-once**——activity 完成後、結果寫入前失敗會重跑，因此應盡量冪等。
這正是我們的 provider call 位置，**不能宣稱 at-most-once**（§5）。

---

## 3. 三案比對

| | **A：員工按鈕** | **B：application 自動編排（建議）** | **C：模型動態 routing／tool loop** |
|---|---|---|---|
| 誰觸發 | 員工看到提示後自己按 | 員工回合提交後，純函式判定 eligible 即啟動 | 主模型自行決定呼叫 OPKS tool |
| 每回合模型呼叫 | 1（回合）＋按了才 1 | 1（回合）＋最多 1（OPKS child） | ≥2，含 tool loop 與可能的整理回合 |
| 新增機制 | 純函式 eligibility ＋ 缺口持久化 | 同 A ＋ scheduler ＋ ID 政策 | 同 B ＋ tool 定義、handoff、tracing |
| 與現行 durable 語意 | 不動 | 不動（兩筆獨立 operation，順序執行） | 需重新定義 turn 內多次 provider call 的 snapshot／replay |
| 員工負擔 | **需理解 OPKS 階段存在** | 不需要 | 不需要 |
| 權威依據 | 最小複雜度 | Anthropic「predefined code paths」＋OpenAI「契約不同才拆 specialist」 | 兩家都建議**先不要** |
| 成本可預測性 | 最高 | 高（每回合上限 1） | 低 |

**淘汰 C**：目前沒有任何 OpenAI 所列的拆分觸發症狀，且 §2.3 兩家官方都建議先用 workflow。

**建議 B**，理由是產品北極星：真人顧問不會等受訪者按按鈕。A 的 eligibility 判斷與 B **完全相同**
（同一個純函式），差別只在「render 成按鈕」或「直接呼叫」，因此**基座相同、trigger 可翻轉**。
A 保留為 recovery 入口（§4.3）。

---

## 4. B 的最小形狀

### 4.1 gap 表示：重用既有 item，**零 schema 變更**

`opks_result_v1` 目前每個 item 恰好 4 個 property、全部 required、零 union
（`entity_kind` / `decision` / `target_ordinal` / `text`）。gap 不新增物件也不新增 property：

| 欄位 | 值 |
|---|---|
| `entity_kind` | 缺口所在的軸（output／indicator／knowledge／skill） |
| `decision` | `uncertain` |
| `target_ordinal` | `0` |
| `text` | **缺口摘要（非空）** ← 唯一改動：從強制空字串改為強制非空 |

Task 綁定由 application 補上（OPKS 是單 Task operation，不必進 wire）。
這避免再次逼近 [Anthropic strict schema grammar 上限](2026-07-31-anthropic-strict-schema-grammar-limit-research.md)。

**gap 不帶問句。** 理由三條：

1. 問句會在 T0 寫成、T1 才問出口，中間上下文已變——主顧問要嘛照貼（時機語氣不對），
   要嘛重寫（那 T0 寫它就是白花 token）；
2. 既有 `OpenIssue` 本就只帶 `summary` ＋ anchors，問句在提問當下由主顧問生成，機制已驗證可行；
3. Morgeson et al. (2004) 的「不得把 K/S 問成認領題」紀律（ADR 0048 決定 14）因此**只住主顧問 prompt 一處**，
   不會出現第二個寫問題的地方需要同步。

**verifier 只做機械檢查**：`text` 非空、`entity_kind` 合法、`target_ordinal` 必須為 0、
payload 結構互斥。語意品質（是否真的缺、摘要寫得好不好）走 rubric——
ADR 0048 決定 24–25 明文只有三類可進 deterministic verifier，
程度修飾詞與「具備…之能力」句式**降為 linter／rubric，不得整筆拒絕**（反例：「基本工資」）。

### 4.2 `analysis_input_digest`：範圍與排除理由

digest 只涵蓋**實際影響 OPKS 判斷的正規化投影**：

- **納入**：Task 語意欄位 `statement` / `action` / `object` / `purpose_result` / `context` / `enablers`；
  當前有效且實際投影的 employee evidence。
- **排除**：`support_links` 原始結構、`retirement` / `merged_into` / `split_from` /
  `pending_reconciliation`（[`task.py:80-85`](../../apps/api/app/job_analysis/domain/task.py#L80-L85)）；
  內部 ID；未渲染欄位。
- **排除且需理由**：`OpksProposal` 狀態與 `CurrentJdOpks` items。
  它們確實有被投影進 packet，理論上算 input；但一旦納入，
  員工接受 Proposal → 寫入 `OpksItem` → digest 變 → 又 eligible → 再分析，形成
  **accept／re-analyze ping-pong**。代價是員工手改 OPKS、或依 ADR 0049 決定 13 的
  rejection memory 想重試時不會自動觸發——那正是手動 recovery 的用途（§4.3）。

不用 `OpksContextPacket.read_set` 直接當 digest：它含 `OpksProposal`
（[`opks_context.py:90`](../../apps/api/app/job_analysis/application/opks_context.py#L90)），
接受／拒絕提案會改變它。read_set 繼續只做 commit 時的 stale 檢查，兩者職責不同。

### 4.3 operation ID 分流：自動與手動不同政策

`Identifier = NonEmptyText`，[`base.py:20`](../../apps/api/app/job_analysis/domain/base.py#L20)
明文不綁格式，因此可直接把 digest 編進 `entry_id`：

| 路徑 | operation ID | 效果 |
|---|---|---|
| 自動 | `opks:auto:{task_id}:{analysis_input_digest}` | 相同 Task 語意＋相同員工依據**只自動分析一次**；用既有 `journal.get(document_id, operation_id)` 即可判定，不新增查詢 port |
| 手動 recovery | 員工這次請求的 client operation ID | **真的重跑**；同一次請求重送沿用同一 `Idempotency-Key` 不重複付費，員工再次主動按才建立新 ID |

手動必須能真正重跑，否則 recovery 沒有意義：員工拒絕過品質不好的候選、手改過 OPKS、
或想讓 rejection memory 生效時，input digest 依 §4.2 並未改變。
**UI 不得以「這批資料已分析過」拒絕重跑。**

### 4.4 單一 active question：gap 不覆寫，agenda 之後選中

現行每次 Task Analysis commit 都會把 `next_question` 寫成**唯一**的 `active_question`。
若 OPKS child 再送一張可回答的問題卡，會同時存在兩個問題：員工下一句回答哪題？
`question_turn_id` 連哪一題？短答怎麼判讀？

**這不是靠「下一題指向同一 Task 才不觸發」能解的**——即使下一題指向別的 Task，
active question 已經存在。所以：

```
OPKS operation 發現 gap
  → 持久化為待確認缺口（不覆寫 active_question、不新增第二個 consultant question）
  → 主顧問 agenda 在後續回合依既有優先序選中它
  → 選中時才生成問句、成為 consultant turn 與 active question
```

保留單一聊天室與單一 active question，且不需要第三次模型呼叫。

`gaps` 允許 0..N、**一次只問一題**。理由是「一次分析可能發現多個獨立缺口」，
**不是**從 Anthropic 1–4 題或 OpenAI 3–6 題類推——那兩者的 UI 能力不等於本產品該同時問多題。

### 4.5 scheduler：eligible 中 `display_order` 最小者

一輪可能新增／修改多個 Task，而 OPKS 一次只分析一個。`immediate_task_ids` 只活在
`TransitionResult`（[`transition.py:115`](../../apps/api/app/job_analysis/application/transition.py#L115)），
replay 回的是 `CompletedTurnPayload`，**不保留**——所以排序必須從 current state 重算。

**eligibility（純函式）：**

```
eligible(task) = task ∈ Current JD ∧ Work Model Task 為 ACTIVE
               ∧ 有有效員工依據（employee_turn／direct_edit）
               ∧ 無未回答 gap
               ∧ 無 pending/deferred OPKS Proposal
               ∧ 無相同 analysis_input_digest 的 receipt
               ∧ 本輪 next_question 未指向該 Task
```

最後一條是防止打斷故事：repo 既有 prompt 紀律「故事仍有資訊時可深挖」，
且下一題 target 就在剛提交的 transition 結果裡，純函式可判、零成本。

**v1 排序：eligible 集合中取 Current JD `display_order` 最小者。**
決定性、reload 一致、不需新查詢或 focus state、容易向員工解釋。
**誠實代價：可能先分析清單上方，而非員工剛談到的工作**；員工隨時可結束訪談，
所以順序**會**影響最後覆蓋到哪些 Task。
先不做「最近證據排序」（`list_conversation_turns()` 已依 `journal_sequence` 有序，
但需多一次讀＋evidence→turn 映射）；等真實使用證明順序不自然再升級。

### 4.6 自動失敗的成本防線（**待裁決的唯一選項**）

`display_order` scheduler ＋ 「失敗不留痕跡」會組成迴圈：清單第一項 Task 若因內容特性
持續 invalid／refused／provider failure → 沒有 receipt → 每個員工回合又選到它 →
重複付費，且**後面的 Task 永遠拿不到分析機會**（head-of-line blocking）。
這不只在 provider 全面故障時發生，單一 Task 特別容易造成 invalid output 也會。

| | **甲（建議）：留最小 attempt outcome** | 乙：不記 failure，本 session 不再嘗試 |
|---|---|---|
| 機制 | 自動路徑的 terminal failure 寫一筆最小 receipt；相同 digest 不再自動重試 | 記在 process 記憶體 |
| 契約成本 | `OpksGenerationOutcome` 多一個值 | 零 |
| reload 後 | 仍不重試 | **可能重試**（記憶體沒了） |
| head-of-line | 解除 | reload 後復發 |
| 恢復 | 員工用 recovery 明確重跑（§4.3 手動 ID） | 同 |

**傾向甲。** 它不是通用 workflow 狀態機，而是**自動付費功能必須有的成本防線**。

---

## 5. 誠實邊界（必須寫進 ADR）

1. **零隱藏 retry。**
2. **已提交 receipt 的重播不重打 provider**，相同 input 不重複建立 Proposal。
3. **provider 已回應、Journal commit 前崩潰，仍可能重打一次**——外部呼叫的
   at-least-once crash window（§2.5 Azure 官方同一語意）。**不是 at-most-once，不是 exactly-once。**
   Temporal 只能當概念類比，不能宣稱它替本 PostgreSQL＋HTTP 實作提供了任何保證。
   這與 design doc 既有的「兩個同時飛行中的相同 request 尚未合併，不得稱為 exactly-once」是同一條紀律。
4. **Task Analysis 已提交後，不因 OPKS 失敗而回滾。** 兩筆獨立 durable operation，順序執行。
5. **不宣稱完整。** UI 三態為「可提出建議／尚有 N 項待確認／依據不足暫不建議」，
   無百分比，措辭受 ADR 0052 決定 7 約束。

**自動成本政策**（owner 已認可）：每個已提交員工回合最多一筆自動 OPKS call；
只分析 Current JD 中 ACTIVE、有有效員工依據的 Task；相同 analysis input 不自動重跑；
有未回答 gap 或 pending／deferred Proposal 時不跑；OPKS 失敗不回滾 Task Analysis；
自動失敗不得在每個後續回合反覆付費；recovery 是員工明確要求的另一筆 operation。

---

## 6. 被撤回的主張（本輪討論中提出後又收回，留供追溯）

| 主張 | 為什麼撤回 |
|---|---|
| gap 的問句品質可進 deterministic verifier（禁能力句式、禁程度修飾詞、禁選項題） | 違反 ADR 0048 決定 24–25；「基本工資」是真實反例。且 §4.1 之後 gap 不帶問句，規則整組不存在 |
| 決定性 child ID ＋ receipt-first ＝「免費的 at-most-once」 | 錯。那是 Temporal 執行模型下的性質；我們的 provider call 在 commit 之前，是 at-least-once（§5.3） |
| 追問可直接沿用 `AskUserQuestion` 的形狀，由 OPKS 產出問句 | 該先例中發問者即對話擁有者；OPKS 是 specialist，不擁有對話（§2.2、§4.4） |
| gap 只需「一個 schema 欄位＋一種 open issue」 | 低估：還缺 OPKS axis、Task 綁定、unknown／not applicable 終端態（§8） |
| `display_order` 排序無所謂，「一輪對話下來覆蓋率相同」 | 錯。員工可隨時結束訪談，順序會影響最終覆蓋（§4.5） |
| 缺口一律「一次只問一個最高影響的問題」 | 過度限制契約；改為契約允許 0..N、產品政策一次問一題（§4.4） |
| 自動失敗「不寫 receipt、下回合再試」即可 | 與 `display_order` scheduler 組成 head-of-line blocking ＋ 重複付費（§4.6） |

---

## 7. 來源與查證層級

| 來源 | 層級 | 備註 |
|---|---|---|
| ADR 0048／0049、repo 程式與行號 | **一手，已逐項核對** | 2026-08-04 |
| Anthropic《Building Effective Agents》、`AskUserQuestion` 官方文件 | **一手，逐字擷取** | — |
| OpenAI Deep Research cookbook、《A practical guide to building agents》 | 一手（cookbook 逐字；guide 為搜尋層摘要） | guide PDF 未逐頁核對 |
| Temporal child workflow 官方頁 | **一手，逐字**（僅「不得為程式組織而拆」一句） | **「決定性 child ID 去重」該頁未載，屬實務慣例，不得當官方依據** |
| Azure Durable Task 程式模型（at-least-once） | 一手頁面，搜尋層摘要 | 語意與本 repo 現況一致 |
| arXiv 2603.26233v2、2511.08798、ICML 2026 poster | 一手頁面摘要層 | 數值取自論文自述，未複現 |
| 29 CFR §1607.14C(2)、Hennink & Kaiser 2022 | 一手／期刊，搜尋層摘要 | — |
| Hu et al., PACM HCI 8(CSCW1), [10.1145/3637320](https://dblp.org/rec/journals/pacmhci/HuGTMYYX24.html) | **僅摘要層（dl.acm.org 回 403）** | **不得作為 ADR 依據**；本文未用它證成任何規則 |
| Morgeson et al. (2004) *JAP* 89(4) | 經 [2026-08-01 OPKS 裁決研究](2026-08-01-opks-design-decisions-research.md) 轉引 | 已在 ADR 0048 採納 |
| Flanagan (1954) 事件回憶遺失率 | 經 [行為指標原料](2026-08-01-opks-raw-performance-indicators.md) 轉引 | 本文未據以證成規則 |

---

## 8. 仍然缺（ADR 前必須補完）

1. **`OpenIssue` 的三個新增語意**：OPKS axis（缺哪一格）、Task 綁定
   （**不得挪用 `reconciliation_task_id`**，其語意已被 JD 對帳佔走）、
   「不知道／不適用」的持久終端態（目前只有 `ExcludedSignal` 有 `EMPLOYEE_DENIED`，
   `OpenIssue` 無終端態）。
2. **§4.6 甲／乙裁決**，以及甲案下 `OpksGenerationOutcome` 新值的名稱與語意。
3. **gap 摘要的 rubric 判準教材**（什麼叫「缺口寫得夠具體到能生成好問題」）——
   §4.1 已把品質從 verifier 移到 rubric，判準教材尚未寫。
4. **主顧問 agenda 如何把 OPKS gap 與既有 open issue 一起排序**——
   既有優先序是「會改變 Task 邊界的矛盾／責任問題優先」，OPKS gap 插在哪一層未定。

## 9. 下一步

1. owner／討論者審本稿，裁決 §4.6 與 §8；
2. 才寫 ADR（Proposed）；
3. ADR Accepted 後才寫 `docs/plans/`；plan 之後才動碼。
