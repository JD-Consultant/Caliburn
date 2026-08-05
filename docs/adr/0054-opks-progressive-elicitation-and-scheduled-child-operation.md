# 0054. OPKS 漸進式蒐集：自動排定的 child operation 與可持久的缺口

- 狀態：Proposed
- 日期：2026-08-05
- 依據：[`docs/specs/2026-08-04-opks-progressive-elicitation-research.md`](../specs/2026-08-04-opks-progressive-elicitation-research.md)
- 延續：[0047](0047-model-owned-open-issue-closure.md)（模型自關 open issue）、
  [0048](0048-opks-evidence-axes-and-document-level-competencies.md) 決定 6／14／24–25、
  [0049](0049-opks-derived-axes-evidence-whitelist-and-document-authority.md) 決定 13／14、
  [0052](0052-jd-readiness-assessment-and-official-code-boundaries.md) 決定 1／7／15
- 不翻案：0048–0051 的 OPKS 概念與持久化形狀

## 脈絡

OPKS 生成目前是一次性候選生成器。模型可以輸出 `uncertain`，但 verifier 直接略過
（`opks_verifier.py` 的 `continue`），而 wire 規定 `uncertain` 必須 `target_ordinal=0, text=""`
——**缺口在契約層就沒有形狀**。系統因此不知道資料是否足以產出 O/P/K/S，也無處保存缺什麼。

同時，唯一入口是員工按「產生建議」的按鈕。這讓員工承擔系統流程：他必須自己判斷哪個 Task
已經談夠、何時該按。這與「AI 顧問主動帶領」的產品方向相反。

追問機制本身已經存在（`next_question`、`OpenIssue`、`last_asked_turn_id`），只是 OPKS 沒接上。

三件事因此需要裁決：**誰觸發下一次分析**、**缺口怎麼表示與持久**、**兩次 LLM 呼叫的 durable 語意**。

## 決定

### A. 觸發與編排

1. **不放常駐「產生／重新分析 OPKS」按鈕。** 員工不需要理解 OPKS 階段的存在。
   保留員工手動新增／編輯／刪除 O/P/K/S——那不是 AI 入口。
2. **啟動與否由 application 純函式決定，不交給模型 routing。** 主顧問繼續擁有唯一聊天室
   與唯一 active question；OPKS 是有邊界的 specialist。這是 Anthropic 定義的 predefined
   workflow，不是自治 agent（沿用 0052 決定 1 把 readiness 放在純函式的同一條紀律）。
3. **Pre-gate 只擋明顯過早，不得宣稱資料完整**：Task 在 Current JD、Work Model Task 為 `ACTIVE`、
   有 ≥1 筆仍有效的員工依據、無指向該 Task 的未解邊界／矛盾／證據不足 issue、無未回答 OPKS gap、
   無 pending／deferred OPKS Proposal、無相同 `analysis_input_digest` 的成功 receipt、
   本輪 `next_question` 未指向該 Task。
4. **`purpose_result` 不得列為 pre-gate 硬條件**（0052 決定 15：工作產出可合法缺省；
   meaningful outcome 可隱含於 `action + object`）。
5. **不得以引文數、字數或涵蓋度加強 pre-gate。** 機械條件的誠實極限是「≥1 筆有效 SupportLink」；
   再往上就是 0052 決定 6 禁止的完成百分比換皮。證據太薄時由 specialist 回全 `uncertain`，
   該 digest 的 receipt 使浪費上限為「每個輸入狀態一次呼叫」。
6. **v1 排序為 eligible 集合中 Current JD `display_order` 最小者。** 決定性、reload 一致。
   `immediate_task_ids` 只活在 `TransitionResult`，replay 不保留，因此排序必須從 current state 重算。

### B. 主回合 receipt 固定唯一 child

7. **`CompletedTurnPayload` 新增 `scheduled_opks?`，內含 `task_id` 與 `analysis_input_digest`。**
   child operation ID 由兩者推導（`opks:auto:{task_id}:{digest}`），**不重複持久化**。
8. **一個已提交的員工回合最多綁定一個 child，綁定在 receipt 寫入時凍結。**
   沒有這一條，replay 會重跑 scheduler 並改選下一個 Task，使同一個員工回合付兩次錢。
9. **replay 若發現 scheduled child 尚無 receipt，應嘗試恢復同一個 child**（同 `task_id` ＋ 同 digest），
   涵蓋「主回合 commit 後、child 執行前 crash」。
10. **digest 已漂移則 abandon，不寫任何 receipt。** 漂移代表已有更新的回合，由該回合排定自己的 child。
    **abandon 與 failed 必須分開**——用一次偶發競態永久壓住一個 digest 是錯的。
11. **不引入 queue、background worker、workflow engine 或 retry framework。**

### C. `analysis_input_digest` 的範圍

12. **納入**：Task 語意欄位（`statement`／`action`／`object`／`purpose_result`／`context`／`enablers`）
    與當前有效且實際投影的 employee evidence。
13. **排除 `CurrentJdOpks` items 與 `OpksProposal` 狀態**：納入會造成
    接受 Proposal → 寫入 `OpksItem` → digest 變 → 再分析的 ping-pong。
14. **排除 `rejection_reason`。** `OpksProposalDecisionPayload` 強制 REJECTED 必須帶 reason，
    每次拒絕都必然產生新文字；若進 digest 會形成付費 reject loop。
    拒絕回饋只作為下次分析的 **rejection memory／analysis-control feedback**（0049 決定 13）,
    **既不是 Evidence，也不是分析觸發器**。

### D. 缺口的表示與持久

15. **gap 重用既有 item 形狀，`opks_result_v1` 零 schema 變更**：
    `entity_kind` = 缺口軸、`decision` = `uncertain`、`target_ordinal` = 0、
    **`text` 從強制空字串改為強制非空的缺口摘要**。Task 綁定由 application 補上。
16. **gap 不帶問句。** 問句在提問當下由主顧問生成，使 0048 決定 14（不得把 K/S 問成認領題）
    只住主顧問 prompt 一處。
17. **一個缺口若同時影響多軸，由 specialist 逐軸輸出 `uncertain`；application 不得推導跨軸依賴。**
    0048 決定 5–6 已明定 K/S 與 Task／Indicator 是多對多、不由 Indicator 擁有；
    O/P 掛 Task、K/S/A 掛文件的不對稱源自官方編號結構，不是依賴關係。
18. **item-level 部分發布**：有充分 Evidence 的候選照常提案，同時保留其他 gap。
    **不做同軸一律扣住，也不做整個 Task 扣住**——0048 決定 24 的 `source_refs[]` 非空是
    逐項規則，效力單位是 item，不是軸。
19. **`OpenIssue` 新增三項，全部 application-set，不進 `task_analysis_result_v2`**：
    `subject_task_id`（**不得挪用 `reconciliation_task_id`**）、
    `opks_axis`（**只含 O／P／K／S，不含 Attitude**）、
    `terminal_resolution?`（`{ kind: employee_unknown | not_applicable, source_ref }`
    **合併為單一物件**，避免兩欄位失步）。gap 摘要重用既有 `summary`。
20. **agenda 位置**：Task 邊界矛盾／責任問題 → 一般 open issue → **OPKS gap** → 遺漏掃描。

### E. 無副作用的解決通道

21. **新增與 `work_signals` 平行的第三個頂層陣列 `issue_resolutions[]`**，扁平、每 issue 一筆：
    `{ ordinal, resolution: answered | employee_unknown | not_applicable }`。
    **不把 gap resolution 綁在 `WorkSignal.disposition` 上**，也不把
    `resolves_open_issue_ordinal` 複數化——後者仍掛著該筆 signal 的副作用。
22. **`answered` 必須在同一輪有一筆與該 gap 的 `subject_task_id` 相關、且留下有效員工 Evidence
    的 `WorkSignal`**，否則 digest 不變、OPKS 不會再分析，gap 會被假關閉。
    這是機械可判的跨欄位條件，屬 Task Analysis verifier 的規則集。
23. **`answered` 維持現行語意（移出 `open_issues`）；`employee_unknown`／`not_applicable`
    不移除**，寫入 `terminal_resolution`、退出 agenda，但在 packet 投影成「已問過，勿重問」。
24. **resolution 的 `source_ref` 由 application 蓋，不進 wire。**

### F. Task 離開 Current JD 時的清理

25. **`prune_opks_for_current_jd()` 現行簽章只收／回 `CurrentJdOpks`，碰不到
    `work_model.open_issues`——不得宣稱它已能終結 gap issue。** 實作者須在同一個 authority
    transaction、同一批既有呼叫點（Task delete、accepted withdraw、merge、split）
    擴充該 seam 或加一個相鄰純函式。
26. **merge／split 一律終結 gap，不遷移。** 沿用既有政策「不把舊 refs 猜接到 replacement Task」。

### G. Receipt、失敗與付費邊界

27. **`OpksGenerationPayload` 新增 `analysis_input_digest` 與 `gap_issue_ids[]`；
    `outcome` 由 2 值擴為 `proposed | needs_clarification | no_change | failed`。**
    proposals 與 gaps 可同時存在；**有 gap 即 `needs_clarification`，`proposal_ids` 仍可非空**，
    此一致性由 validator 寫死。
28. **Proposal、OpenIssue 與 receipt 在同一個 `commit_authority_change()` 交易寫入。**
29. **terminal 失敗寫 `failed` receipt**（provider error／invalid output／refused／verifier rejected），
    用以阻止相同 digest 每回合重複付費。**第一版不做 backoff、attempt counter、circuit breaker。**
30. **成本上限**：每個已提交的員工回合最多一筆自動 OPKS call；相同 analysis input 不自動重跑；
    **零隱藏 retry**。
31. **Task Analysis 已提交後不因 OPKS 失敗而回滾**；`/turns` 不得因 child 失敗改回 5xx。
32. **不得宣稱 provider call at-most-once 或 exactly-once。** provider 已回應、Journal commit 前
    崩潰仍可能重打一次（外部呼叫的 at-least-once crash window）。Temporal 只能當概念類比，
    不能宣稱它替本 PostgreSQL＋HTTP 實作提供任何保證。

### H. UI 範圍與禁令

33. **`/turns` 最多執行主顧問＋一個 OPKS specialist**，員工只看到一個「分析中」。
34. **gap 不做側邊聊天、不做問題卡**，只由主顧問在同一聊天室問，一次一題。
35. **不做完成百分比、不宣稱「OPKS 已完整」、不做進度 dashboard。**
    狀態僅呈現「尚未適合分析／尚有待確認資訊／已可提出建議」，措辭受 0052 決定 7 約束。
36. **不引入通用 agent router、tool loop、handoff 或 tracing framework。**

## 後果

### 正面

- 缺口第一次有形狀：`uncertain` 從被丟棄變成可持久、可追問、可終結的產品狀態，且 wire schema 不變。
- 員工不再承擔流程判斷；顧問主動帶領，與產品北極星一致。
- 兩次 LLM 呼叫各自是獨立 durable operation，主回合的成功不被 OPKS 的失敗牽連。
- 付費邊界被 receipt 綁死：同一回合一次、同一輸入一次、失敗一次即停。
- 追問全部走既有的單一 active question 與 agenda，沒有第二套對話狀態機。

### 負面／代價

- 每個員工回合可能多一次 reasoning 呼叫，成本與延遲上升；上限為 1，但不是零。
- `display_order` 排序可能先分析清單上方而非員工剛談到的工作；員工可隨時結束訪談，
  順序**會**影響最終覆蓋。升級為「最近證據排序」需多一次讀與 evidence→turn 映射。
- 偶發 provider 抖動會永久壓住那個確切 digest，直到新 Evidence 使 digest 改變。
- 拒絕回饋不觸發重分析，員工拒絕後必須等下一次自然分析才看到改進。
- 部分發布可能使員工在缺口未解時先接受一部分候選；殘餘錨定風險無本產品資料可量化，
  只靠「主顧問一律問行為、不得讓員工認領 K/S」的既有 invariant 緩解。
- `issue_resolutions[]` 給了模型一個新的出口，可能被當成偷懶關閉。決定 22 只能擋機械前提，
  其餘靠 rubric 與「specialist 下次仍會重提同一 gap」的自我修正，**verifier 擋不住**。
