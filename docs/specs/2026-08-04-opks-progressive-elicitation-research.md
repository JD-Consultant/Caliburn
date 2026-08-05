---
title: OPKS 漸進式蒐集——從一次性建議器到會追問的顧問
date: 2026-08-04（2026-08-05 依討論收斂改寫）
status: 已收斂，待開 Proposed ADR
purpose: 裁決 OPKS 生成在證據不足時該怎麼辦，並把方案壓到最小可實作形狀
---

# OPKS 漸進式蒐集研究

## 0. 這份回答什麼、不回答什麼

**回答**：OPKS 生成發現證據不足時，缺口怎麼表示、誰觸發下一次分析、追問長在哪裡、
成本與失敗邊界在哪、durable 語意怎麼接。

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
| `uncertain` 在契約上**無法**承載任何資訊 | [`opks_prompt.py:24`](../../apps/api/app/job_analysis/llm/opks_prompt.py#L24) 規定 `target_ordinal=0, text=""` |
| 沒有「這批證據分析過了嗎」的證明 | `OpksGenerationPayload` 只有 `operation_id / selected_task_id / outcome / proposal_ids` |
| Journal 只能按 `entry_id` 查 | `JournalRepository` 只有 `get / add / list_conversation_turns` |
| 觸發完全靠員工按鈕 | `POST …/tasks/{task_id}/opks-proposals`；Web 入口在 [`OpksEditor.tsx:260`](../../apps/web/src/components/workspace/OpksEditor.tsx#L260) |

所以現行 OPKS 是**一次性候選生成器**：它知道「有沒有資格分析」，不知道「資料夠不夠」，
也沒有地方保存「缺什麼」。

**追問機制本身已存在**，只是 OPKS 沒接上：Task Analysis 每輪產出 `next_question`，
`OpenIssue` 可由模型關閉（[`transition.py:261`](../../apps/api/app/job_analysis/application/transition.py#L261)），
`last_asked_turn_id` 兩種 target 都記（ADR [0047](../adr/0047-model-owned-open-issue-closure.md)）。

---

## 2. 2026 權威資料核對

### 2.1 「有沒有問」是大差距，「問得多聰明」是小差距

[Ask or Assume?（arXiv 2603.26233v2）](https://arxiv.org/html/2603.26233v2) 在 underspecified
SWE-bench 上：完全不問 **54.8%** → 校準式追問 61.2–69.4% → 每次都問 **70.4%**。
校準的價值不在準確度，而在打擾成本（Claude Sonnet 4.5 平均 3.06 次詢問／題，Kimi K2.6 為 8.71）。
同篇另一結論：**把「偵測資訊不足」與「執行工作」拆開**顯著更好（69.40% vs 61.20–61.60%）。

[SAGE-Agent（arXiv 2511.08798）](https://arxiv.org/abs/2511.08798) 同向：覆蓋率 +7–39%
而詢問次數少 1.5–2.7 倍。[ICML 2026 Information Gain Reward](https://icml.cc/virtual/2026/poster/66065)
成功率僅 **+3.7%**。

→ **不建 EVPI／資訊增益機器。** 價值在「能問、缺口能持久」，不在選題演算法。

### 2.2 流程該由誰控制：workflow 先於 agent

[Anthropic《Building Effective Agents》](https://www.anthropic.com/engineering/building-effective-agents) 逐字：

> **Workflows** are systems where LLMs and tools are orchestrated through **predefined code paths**.
> **Agents** are systems where LLMs **dynamically direct their own processes and tool usage**.

> we recommend finding the simplest solution possible, and only increasing complexity when needed.
> **This might mean not building agentic systems at all.**

> **Agentic systems often trade latency and cost for better task performance.** … you should consider
> adding complexity **only** when it demonstrably improves outcomes.

[OpenAI《A practical guide to building agents》](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
的 manager pattern 讓主 agent 保有對話責任、specialist 做有邊界的工作；
**拆 specialist 的觸發症狀**是「agent 跟不上複雜指令、持續選錯工具、prompt 裡 if-then-else 過多」。

→ OPKS 拆成獨立 operation 成立（自己的 prompt／schema／verifier，ADR 0049 決定 14），
但**啟動與否由 application 純函式決定，不交給模型 routing**。這與 ADR
[0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md) 決定 1 是同一條紀律。

### 2.3 pending request 必須持久且可恢復

[Microsoft Agent Framework HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
（doc date 2026-07-16）把待答請求做成 `request_id` 鍵控的 typed `request_data`，並明文：

> When a checkpoint is created, **pending requests are also saved as part of the checkpoint state**.
> When you restore from a checkpoint, any pending requests will be **re-emitted**…

其範例是**收集 N 筆 pending request、由外部逐一回應**——與「0..N gap 持久化、agenda 一次問一題」同形。
**此處只借 durability 形狀，不引入其框架，也不用它證明任何 OPKS 領域語意。**

### 2.4 「完整」在權威體系裡沒有第三種說法

- [29 CFR §1607.14C(2)](https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XIV/part-1607/subject-group-ECFRe6113332da568d1/section-1607.14)
  要求涵蓋 *critical or important work behaviors*——**重要性**判準，不是欄位齊全判準。
- [飽和](https://www.sciencedirect.com/science/article/pii/S0277953621008558)（Hennink & Kaiser 2022）
  是**操作型停止規則**，不是完整性宣告。
- iCAP 官方允許操作型任務省略工作產出、態度「視需求納入」（ADR 0052 決定 15–16）。

→ 系統只能誠實說「這批資料再追問已問不出新東西」。**不得宣稱完整**，
也不得用「不完整／不合格／未通過」（ADR 0052 決定 7）。

### 2.5 durable execution：child operation 的定位

[Temporal 官方 child workflow 文件](https://docs.temporal.io/child-workflows)給的是**反向告誡**：

> **There is no reason to use Child Workflows just for code organization.** … When in doubt, use an Activity.

→ OPKS 拆成獨立 durable operation 的正當理由**不是分檔案**，是它必須能獨立失敗與恢復。

失敗語意引官方可核實者：[Azure Durable Task 程式模型](https://docs.azure.cn/en-us/durable-task/common/programming-model-overview)
明示 activity 只保證 **at-least-once**——完成後、結果寫入前失敗會重跑。
這正是我們 provider call 的位置（§5）。

---

## 3. 三案比對

| | A：員工按鈕 | **B：application 自動編排（採用）** | C：模型動態 routing／tool loop |
|---|---|---|---|
| 誰觸發 | 員工看到提示後自己按 | 主回合提交後，純函式判定 eligible 即排定 | 主模型自行決定呼叫 OPKS tool |
| 每回合模型呼叫 | 1（回合）＋按了才 1 | 1（回合）＋最多 1（OPKS child） | ≥2，含 tool loop |
| 員工負擔 | **需理解 OPKS 階段存在** | 不需要 | 不需要 |
| 與現行 durable 語意 | 不動 | 兩筆獨立 operation，順序執行 | 需重定義 turn 內多次 provider call 的 snapshot／replay |
| 權威依據 | 最小複雜度 | Anthropic「predefined code paths」＋OpenAI manager/specialist | 兩家都建議**先不要** |

**淘汰 C**：無任何 OpenAI 所列的拆分觸發症狀。
**淘汰 A**：產品裁決——真人顧問不會等受訪者按按鈕；常駐「產生／重新分析」按鈕讓員工承擔系統流程。
**採 B。**

---

## 4. 採用方案的最小形狀

### 4.1 Pre-gate（純函式，只擋明顯過早）

```
Task ∈ Current JD
∧ Work Model Task 為 ACTIVE          （TaskState 是推導狀態、三值互斥，
                                       已排除 PENDING_RECONCILIATION／RETIRED）
∧ 有 ≥1 筆仍有效的員工依據（employee_turn／direct_edit）
∧ 無指向此 Task 的未解 Task 邊界／矛盾／證據不足 issue
∧ 無未回答的 OPKS gap
∧ 無 pending／deferred OPKS Proposal
∧ 無相同 analysis_input_digest 的成功 receipt
∧ 本輪 next_question 未指向該 Task
```

**`purpose_result` 不得為硬條件。** ADR 0052 決定 15 明文工作產出可合法缺省；
meaningful outcome 可合理隱含於 `action + object`。

**pre-gate 不宣稱資料完整。** `TaskFields` 的 `statement`／`action`／`object` 都是 `NonEmptyText`，
所以 Work Model Task 在型別上不可能只有名稱；真正稀薄的是**證據**。
機械條件能誠實走到的極限就是「≥1 筆有效 SupportLink」——再往上（數引文、算長度、算涵蓋度）
就是 completeness 分數換皮，禁止。

**因此接受一次浪費**：證據太薄時 specialist 回全 `uncertain`，那個結果本身就是判斷；
該 digest 的 receipt 會擋住重跑，**浪費上限是「每個輸入狀態一次呼叫」**，不累積。
最後一條（next_question 未指向該 Task）是天然延後器——主顧問通常還在深挖剛出現的 Task。

### 4.2 `analysis_input_digest`

只涵蓋**實際影響 OPKS 判斷的正規化投影**：

- **納入**：Task 語意欄位 `statement` / `action` / `object` / `purpose_result` / `context` / `enablers`；
  當前有效且實際投影的 employee evidence。
- **排除**：`support_links` 原始結構、`retirement` / `merged_into` / `split_from` /
  `pending_reconciliation`；內部 ID；未渲染欄位。
- **排除且需理由**：`CurrentJdOpks` items 與 `OpksProposal` 狀態。納入會造成
  接受 Proposal → 寫入 `OpksItem` → digest 變 → 再分析的 **accept／re-analyze ping-pong**。
- **排除且需理由**：`rejection_reason`。`OpksProposalDecisionPayload` 的 validator
  **強制 REJECTED 必須帶 reason**，所以每次拒絕都必然產生新文字；若進 digest，
  每次拒絕都會觸發一次付費重分析，形成 **reject loop**。
  拒絕回饋只作為下次分析的 **rejection memory／analysis-control feedback**（ADR 0049 決定 13），
  **不是 Evidence，也不是分析觸發器**。沒有東西永久遺失——訪談繼續產生新證據時自然生效。

不用 `OpksContextPacket.read_set` 當 digest：它含 `OpksProposal`
（[`opks_context.py:90`](../../apps/api/app/job_analysis/application/opks_context.py#L90)）。
read_set 繼續只做 commit 時的 stale 檢查，兩者職責不同。

### 4.3 主回合 receipt 固定唯一 child

`CompletedTurnPayload` 目前只有 `operation_id` / `employee_turn` / `consultant_turn`，
是 **Journal payload，不是 LLM wire**——加欄位對 provider schema 零影響。

```
CompletedTurnPayload
└─ scheduled_opks?
   ├─ task_id                  ← 唯一不可推導的決策
   └─ analysis_input_digest    ← 偵測漂移用
   （child operation ID 由兩者推導，不重複持久化）
```

**不變量：一個已提交的員工回合最多綁定一個 child，且該綁定在 receipt 寫入時就凍結。**
沒有這一條，replay 會重跑 scheduler：第一次選 T1 並成功、重送同一回合時 scheduler 看到
T1 已分析而改選 T2，**同一個員工回合付兩次錢**。

**replay 行為：**

- scheduled child **已有 receipt** → 直接返回，不打 provider。
- scheduled child **尚無 receipt** → **嘗試恢復同一個 child**（同一 `task_id` ＋ 同一 digest）。
  這涵蓋「主回合 commit 後、child 執行前 crash」。
- 恢復時 digest **已漂移** → **abandon**，不寫 failed receipt。漂移代表已有更新的回合，
  由該回合排定自己的 child。

不需要 queue、background worker 或 workflow engine。

**scheduler 在交易內的成本**：durable turn 的 state 已載入 `current_opks` 與 `opks_proposals`
（[`durable_turn.py:71-72`](../../apps/api/app/job_analysis/application/durable_turn.py#L71-L72)），
open issues 在 work_model 內，所以 eligibility 不必額外讀。只有 receipt 檢查要 `journal.get`；
依 `display_order` 逐一評估、第一個通過就停，典型只花 1 次讀。

### 4.4 排序與 operation ID

**v1 排序：eligible 集合中取 Current JD `display_order` 最小者。**
決定性、reload 一致、不需新查詢或 focus state、容易向員工解釋。
`immediate_task_ids` 只活在 `TransitionResult`
（[`transition.py:115`](../../apps/api/app/job_analysis/application/transition.py#L115)），
replay 回的是 `CompletedTurnPayload`，**不保留**——所以排序必須從 current state 重算。

**誠實代價：可能先分析清單上方，而非員工剛談到的工作。** 員工可隨時結束訪談，
所以順序**會**影響最後覆蓋到哪些 Task。先不做「最近證據排序」
（`list_conversation_turns()` 已依 `journal_sequence` 有序，但需多一次讀＋evidence→turn 映射）。

**operation ID**：`opks:auto:{task_id}:{analysis_input_digest}`。
`Identifier = NonEmptyText`（[`base.py:20`](../../apps/api/app/job_analysis/domain/base.py#L20)）
明文不綁格式。既有 `journal.get(document_id, operation_id)` 即可判定「這批輸入分析過了嗎」，
不新增查詢 port。**沒有手動 recovery 入口**——常駐按鈕已移除（§4.12）。

### 4.5 gap 表示：重用既有 item，**零 schema 變更**

`opks_result_v1` 每個 item 恰好 4 個 property、全部 required、零 union。gap 不新增物件也不新增 property：

| 欄位 | 值 |
|---|---|
| `entity_kind` | 缺口所在的軸（output／indicator／knowledge／skill） |
| `decision` | `uncertain` |
| `target_ordinal` | `0` |
| `text` | **缺口摘要（非空）** ← 唯一改動：從強制空字串改為強制非空 |

Task 綁定由 application 補上（單 Task operation，不必進 wire）。

**gap 不帶問句。** 問句會在 T0 寫成、T1 才問出口，中間上下文已變；既有 `OpenIssue` 本就只帶
`summary` ＋ anchors，問句在提問當下由主顧問生成。這也讓「不得把 K/S 問成認領題」的紀律
（ADR 0048 決定 14）**只住主顧問 prompt 一處**。

**verifier 只做機械檢查**：`text` 非空、`entity_kind` 合法、`target_ordinal` 必須為 0、結構互斥。
語意品質走 rubric——ADR 0048 決定 24–25 明文只有三類可進 deterministic verifier，
程度修飾詞與「具備…之能力」句式**降為 linter／rubric，不得整筆拒絕**（反例：「基本工資」）。

**一個缺口若同時影響多軸，由 specialist 逐軸輸出 `uncertain`；application 不得推導跨軸依賴。**
ADR 0048 決定 6 明文「一條 K/S 不由單一 Indicator 擁有，與 Task／Indicator 是多對多 references」；
決定 5 說明 O/P 掛 Task、K/S/A 掛文件的不對稱來自官方編號結構（指引表單 F3-3 p73），不是依賴關係。

### 4.6 部分發布：item-level

**有充分 Evidence 的候選照常提案，同時保留其他 gap。** 不做同軸一律扣住，也不做整個 Task 扣住。

依據：ADR 0048 決定 24 把 **`source_refs[]` 非空**列為 deterministic verifier 三規則之一——
**每一條候選的效力由它自己的來源建立**，不由所屬軸的完整度建立。「軸」在本系統中不是效力單位、
不是所有權單位、不是驗證單位；選它當扣留單位是範疇錯誤。

而且 specialist 是逐項發布的：若缺口真的讓整軸站不住，它本來就不會發出該軸候選。
任何 application 端的軸級扣留規則，只會在 specialist 判定某些候選有依據時**覆寫它的判斷**。

**殘餘風險（無本產品資料）**：員工讀完部分候選後，回答缺口題時可能被錨定。
[MELBA 2026](https://www.melba-journal.org/papers/2026:007.html) 在病理學情境量到 7% automation bias rate，
但那是「人評估 AI 建議」，不是「人看完建議後回答下一題」——**只能當輔證，不是本產品情境的直接實驗**。
既有 invariant（主顧問一律問行為、不得讓員工認領 K/S）已堵住主要通道。

### 4.7 gap 的持久形狀

`OpenIssue` 新增三項，**全部 application-set，不進 `task_analysis_result_v2`**：

```
subject_task_id: TaskId | None            ← 不挪用 reconciliation_task_id（語意已被 JD 對帳佔走）
opks_axis: <O／P／K／S 四值> | None         ← 不含 Attitude；OpksEntityKind 含 A，需另立四值 domain enum
terminal_resolution: { kind: employee_unknown | not_applicable, source_ref } | None
```

`summary` 直接當 gap summary，不新增欄位。
**終端資料合併成一個物件**，避免 `resolution` 與 `source_ref` 兩個欄位失步。

模型只需在 packet 的 rendering 讀到這些，並用既有 ordinal 關閉；不需要能產生它們。

**只有兩種需要終端記憶：**

| resolution | 行為 |
|---|---|
| `answered` | **維持現行語意：移出 `open_issues`**。若 specialist 下次仍判定缺，會重新提出 |
| `employee_unknown`／`not_applicable` | **不移除**，寫入 `terminal_resolution`；退出 agenda，但在 packet 投影成「已問過，勿重問」 |

**agenda 位置**：「Task 邊界矛盾／責任問題 → 一般 open issue → **OPKS gap** → 遺漏掃描」。
這與 pre-gate 的「無指向此 Task 的未解 issue」是同一條規則的兩端，不需要新機制。

### 4.8 `issue_resolutions[]`：無副作用地一次解多個 gap

現行 `resolves_open_issue_ordinal` 與 `disposition`（必填）、`task_change`、`exclude`、`open_issue`
同層（[`result.py:117`](../../apps/api/app/job_analysis/llm/result.py#L117)），
**要關 issue 就得鑄一個帶處置的工作訊號**。把它複數化並不解決問題——一筆 signal 解三個 gap，
仍掛著那一筆的副作用。

**改成與 `work_signals` 平行的第三個頂層陣列，扁平、每 issue 一筆：**

```
task_analysis_result_v2
├─ work_signals[]        （不動）
├─ next_question         （不動）
└─ issue_resolutions[]   ← 新增
   ├─ ordinal: int
   └─ resolution: answered | employee_unknown | not_applicable
```

一個答案同時解 P、K、S 三個 gap ＝ 輸出三筆 resolution，
**每一筆都沒有 disposition、沒有 task_change、沒有 support**——結構上不可能產生工作副作用。

**`answered` 的機械前提（可寫進 Task Analysis verifier）**：同一輪必須有一筆與該 gap 的
`subject_task_id` 相關、且留下有效員工 Evidence 的 `WorkSignal`。否則 digest 不變、
OPKS 不會再分析，gap 會被**假關閉**。這是跨欄位但完全機械可判的條件，屬於既有
Task Analysis verifier 的規則集（與 ADR 0048 決定 24 限制 OPKS verifier 的範圍不衝突）。

**SourceRef 由 application 蓋，不進 wire**：resolution 發生在某個確定的員工回合，
application 直接用當前 turn 的 SourceRef。

**契約成本（已量測）**：`task_analysis_result_v2` 目前 **2 個頂層 property、0 個 `anyOf`、
0 個 `$defs`、4,668 bytes**（已完全 inline，[2026-07-31 grammar 研究](2026-07-31-anthropic-strict-schema-grammar-limit-research.md)
當時的 17-union 問題已解決）。新增的是零 union、兩個純量欄位的物件陣列，
離官方 union 上限 16 有全部空間。**仍應在實作前重量一次**（官方 grammar size 上限未公開）。

### 4.9 Task 離開 Current JD 時的 gap 清理

**現有函式做不到，這點必須誠實。** `prune_opks_for_current_jd()`
（[`opks_authoring.py:72`](../../apps/api/app/job_analysis/application/opks_authoring.py#L72)）
的簽章只收 `CurrentJdOpks` ＋ `current_jd`、只回 `CurrentJdOpks`，**碰不到 `work_model.open_issues`**。

實作者需在**同一個 authority transaction、同一批既有呼叫點**（Task delete、accepted withdraw、
merge、split）擴充該 seam 或加一個相鄰純函式。**不得宣稱現有函式已能做。**

**merge／split 一律終結，不遷移。** 沿用既有政策「系統不會把舊 refs 猜接到 replacement Task」，
gap 不另立規則。新 Task 若仍缺同一件事，下次分析會自己重新提出。

### 4.10 Receipt 補齊

```
OpksGenerationPayload
├─ operation_id
├─ selected_task_id
├─ analysis_input_digest                                        ← 新增
├─ proposal_ids[]
├─ gap_issue_ids[]                                              ← 新增
└─ outcome: proposed | needs_clarification | no_change | failed  ← 由 2 值擴到 4
```

**proposals 與 gaps 可同時存在**（item-level 部分發布）。outcome 以「本次有無 gap」為準：
有 gap 即 `needs_clarification`，`proposal_ids` 仍可非空。這要在 validator 寫死，
否則兩個欄位會各說各話。

Proposal、OpenIssue 與 receipt **同一個 `commit_authority_change()` 交易**寫入。

### 4.11 失敗與 abandon 必須分開

- **`failed` receipt**：只由 terminal 失敗寫入（provider error／invalid output／refused／verifier rejected）。
  作用是阻止相同 digest 每回合重複付費，解除 head-of-line blocking。
- **abandon**：digest 漂移（§4.3）**不寫任何 receipt**。用一次偶發競態永久壓住一個 digest 是錯的。

**第一版不做 backoff、attempt counter、circuit breaker。**

**誠實代價**：偶發 provider 抖動會**永久**壓住那個確切 digest，直到出現新 Evidence 使 digest 改變。
只在「該 Task 之後再也沒被提到」時才真的損失。

### 4.12 API 與 Web 端到端

```
POST …/turns  (Idempotency-Key)
 1. prepare_turn（讀完關交易）
 2. 交易外：主顧問 LLM ①
 3. commit_verified_turn：Work Model / Proposal / next_question
    ＋ scheduler 在同一交易凍結 scheduled_opks（0 或 1 個）
    ── 到此員工回答已安全落地 ──
 4. 若有 scheduled_opks：
    a. prepare → digest 比對；漂移則 abandon
    b. 交易外：OPKS LLM ②
    c. verifier（機械檢查）
    d. commit：OpksProposal[] ＋ OpenIssue(gap)[] ＋ receipt 同交易
 5. 回 200 ＋ 最新 ConsultationView
```

**步驟 4 全程失敗都不得影響步驟 3 的 200。** 已成功的員工回答不可被顯示成整輪失敗（不得轉 503）。

**Web：**

- **移除**「產生建議／重新分析」按鈕與對應 mutation（[`OpksEditor.tsx:260`](../../apps/web/src/components/workspace/OpksEditor.tsx#L260)）。
- **保留**員工手動新增／編輯／刪除 O/P/K/S（那不是 AI 入口）。
- `/turns` 的「分析中」涵蓋 ①＋可能的 ②，員工只看到一個等待。
- OPKS Proposal 沿用現有聊天室下方呈現。
- gap **不做側邊聊天、不做問題卡**，只由主顧問在同一聊天室問，一次一題。
- 無百分比、無「OPKS 已完整」、無進度 dashboard。

---

## 5. 誠實邊界（必須寫進 ADR）

1. **零隱藏 retry。**
2. **已提交 receipt 的重播不重打 provider**，相同 input 不重複建立 Proposal。
3. **provider 已回應、Journal commit 前崩潰，仍可能重打一次**——外部呼叫的 at-least-once
   crash window。**不是 at-most-once，不是 exactly-once。** Temporal 只能當概念類比，
   不能宣稱它替本 PostgreSQL＋HTTP 實作提供任何保證。
4. **Task Analysis 已提交後，不因 OPKS 失敗而回滾。** 兩筆獨立 durable operation。
5. **不宣稱完整。** UI 只呈現「尚未適合分析／尚有待確認資訊／已可提出建議」，措辭受 ADR 0052 決定 7 約束。
6. **一個員工回合最多一筆自動 OPKS call**，由 §4.3 的 receipt 綁定保證。

---

## 6. 被撤回的主張（討論過程中提出後又收回）

| 主張 | 為什麼撤回 |
|---|---|
| gap 的問句品質可進 deterministic verifier | 違反 ADR 0048 決定 24–25；「基本工資」是真實反例。§4.5 後 gap 不帶問句，規則整組不存在 |
| 決定性 child ID ＋ receipt-first ＝「免費的 at-most-once」 | 錯。那是 Temporal 執行模型下的性質；我們的 provider call 在 commit 之前 |
| 追問可沿用 `AskUserQuestion` 形狀、由 OPKS 產出問句 | 該先例中發問者即對話擁有者；OPKS 是 specialist，不擁有對話 |
| gap 只需「一個 schema 欄位＋一種 open issue」 | 低估：還缺 axis、Task 綁定、終端態，以及無副作用的 resolution 通道 |
| **「缺 P → 扣住 K/S」的跨軸依賴表** | **錯。ADR 0048 決定 6 明文 K/S 與 Task／Indicator 是多對多、不由 Indicator 擁有。從 `indicator_refs` 型別反推產品語意是錯誤方法** |
| **`purpose_result` 非空可當 pre-gate 硬條件** | **錯。ADR 0052 決定 15 明文工作產出可合法缺省；把 O\*NET 的 meaningful outcome 從「task 定義要件」誤搬成「欄位必填」** |
| **`prune_opks_for_current_jd()` 已能終結 gap issue** | **錯。其簽章只收／回 `CurrentJdOpks`，碰不到 work model open issues（§4.9）** |
| **rejection_reason 內容進 digest** | **錯。REJECTED 強制帶 reason，所以每次拒絕必然改變 digest，形成付費 reject loop（§4.2）** |
| **child 未執行時「靠下一回合自癒」即可** | 不足。replay 應嘗試恢復同一 child，只有 digest 漂移才 abandon（§4.3） |
| 引用 HDSR 2026 支持「早期 AI 建議強烈影響後續表現」 | **無法核實**（`hdsr.mitpress.mit.edu` 回 403）。讀不到就不引 |
| `display_order` 排序無所謂，「一輪對話下來覆蓋率相同」 | 錯。員工可隨時結束訪談，順序會影響最終覆蓋 |
| 缺口一律「一次只問一個最高影響的問題」寫進契約 | 過度限制；改為契約允許 0..N、產品政策一次問一題 |

---

## 7. 來源與查證層級

| 來源 | 層級 | 備註 |
|---|---|---|
| ADR 0047–0052、repo 程式與行號 | **一手，已逐項核對** | 2026-08-04／05 |
| Anthropic《Building Effective Agents》 | **一手，逐字擷取** | — |
| Microsoft Agent Framework HITL | **一手，逐字擷取**（doc date 2026-07-16） | 只借 durability 形狀 |
| OpenAI《A practical guide to building agents》 | 一手 PDF，搜尋層摘要 | 未逐頁核對 |
| Temporal child workflow 官方頁 | **一手，逐字**（僅「不得為程式組織而拆」一句） | **「決定性 child ID 去重」該頁未載，屬實務慣例，不得當官方依據** |
| Azure Durable Task 程式模型（at-least-once） | 一手頁面，搜尋層摘要 | — |
| arXiv 2603.26233v2、2511.08798、ICML 2026 poster | 一手頁面摘要層 | 數值取自論文自述，未複現 |
| 29 CFR §1607.14C(2)、Hennink & Kaiser 2022 | 一手／期刊，搜尋層摘要 | — |
| MELBA 2026（automation bias） | 搜尋層摘要 | **僅輔證，非本產品情境的直接實驗** |
| ~~HDSR 8.2 (2026)~~ | **已撤回（403，無法核實）** | 全文未據以證成任何規則 |
| Morgeson et al. (2004) *JAP* 89(4) | 經 [2026-08-01 OPKS 裁決研究](2026-08-01-opks-design-decisions-research.md) 轉引 | 已在 ADR 0048 採納 |

**資料使用邊界**：O/P/K/S 語意與 evidence 規則只由 iCAP／O\*NET／repo OPKS 研究稿決定；
大廠文件只支撐 orchestration、clarification、durability 與 HITL，
**不得用來證明任何 OPKS 領域依賴**。

---

## 8. 交給實作者決定（本文不裁決）

1. 型別與 schema version 的精確命名（含 O/P/K/S 四值 domain enum 的名稱）。
2. digest 的 canonical serialization 細節。
3. helper 放在哪個 application module。
4. 失敗時的簡短 UI 文案。
5. migration、測試切法與 commit 順序。

## 9. 仍缺真人資料

- 員工實際多常回「不知道／不適用」。
- provider terminal failure 的實際頻率（目前只有 live smoke 少數樣本，
  不足以支持任何 retry 策略——這也是不做 retry 的另一個理由）。
- scheduled child 因 digest 漂移被 abandon 的比例。
- 部分發布是否導致員工過早接受、或答題被錨定。

## 10. 下一步

1. 依本稿開一份精簡的 **Proposed ADR**；
2. ADR 核准（Accepted）後才寫 `docs/plans/` bite-size plan；
3. plan 之後才動碼。
