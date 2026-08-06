# 0055. 未解的 OPKS 缺口不再阻擋再分析

- 狀態：Proposed
- 日期：2026-08-06
- 依據：[`docs/specs/2026-08-06-opks-gap-reanalysis-blocking-research.md`](../specs/2026-08-06-opks-gap-reanalysis-blocking-research.md)、
  [Opus 5 與 Luna-Pro 兩次 live smoke](../experiments/2026-08-06-opks-progressive-elicitation-live-smoke/README.md)
- 修正：[0054](0054-opks-progressive-elicitation-and-scheduled-child-operation.md) 決定 3 的**一條** pre-gate 條件。
  **0054 其餘決策全部不變**，特別是決定 20（specialist 不解決 issue）、決定 22–24（缺口的三條出路）、
  決定 29（四種終端 receipt）、決定 31（每個輸入狀態一次呼叫）。
- 不翻案：0044 / 0047 / 0048–0052 的任何裁決

## 脈絡

0054 決定 3 的 pre-gate 對「同一個 Task 要不要再分析」有**兩條**獨立條件：
**(a)** 無相同 `analysis_input_digest` 的終端 receipt，**(b)** 無 active 的 OPKS gap。

2026-08-06 的 live smoke（Opus 5，生產模型）顯示 (b) 讓 0054 的核心價值主張不會發生。
單一 Task、一句依據，Opus 只提得出 1 條候選、開了 **4 個缺口**。員工在第 3 回合講出做法，
那句話已成為 SupportLink、`analysis_input_digest` 已改變、主顧問也正確地用
`issue_resolutions.answered` 收掉它命中的那一個——**但 specialist 永遠看不到那句話**，
因為另外 3 個缺口還 active。要 4 個全部關掉才會有第二次分析。
**模型越誠實（缺口開得越細），再分析被鎖得越久。**

逐情況拆開 (b)：digest 未變時它是**多餘**的（(a) 已經擋住）；digest 已變且新證據正是缺口的
答案時它是**有害**的；只有在「digest 因與缺口無關的原因變動」時它才有用。

三處文檔顯示 (b) 從一開始就沒有屬於自己的理由：

- 決定 3 的自述目的是「**只擋明顯過早**」。缺口未解 ＋ 員工剛給新依據不是明顯過早。
- 成本上限不是 (b) 給的。決定 5 與研究稿 §4.1 都把「每個輸入狀態一次呼叫」歸給 (a)。
- 唯一與封鎖有關的理由（研究稿 §4.7「與 pre-gate 是同一條規則的兩端」）是為決定 3 的**另一條**
  ——「無指向該 Task 的未解邊界／矛盾／責任 issue」——寫的。那條的前提是「工作本身還沒確定」；
  OPKS 缺口的前提相反：**工作早就確定，分析也跑過了，只是某幾軸缺依據。**

決定 29 已經替**失敗路徑**解除 head-of-line blocking；(b) 在**成功路徑**上重新製造了它，
而且更嚴重——失敗那條至少停在一次呼叫，缺口這條把後續分析全部鎖死。

放寬 (b) 之後必須回答「新分析跑完了，舊缺口怎麼辦」。缺口的 ID 是 `{operation_id}-gap{index}`，
**每次分析都不同，跨分析沒有穩定 identity**，所以任何「新舊配對」只能靠文字——那是 0044 與
0051 決定 8 兩度否決的路；而「新的取代舊的」還會讓模型漏講的那一項在**沒有人回答、也沒有人
問過**的情況下靜默消失。

## 決定

1. **移除 pre-gate 的「無 active 的 OPKS gap」。** 決定 3 其餘七條不變。
   `analysis_input_digest` 的終端 receipt（(a)）單獨守門：輸入沒變就不重跑，輸入變了就分析。
2. **「無指向該 Task 的未解邊界／矛盾／責任 issue」保留。** 那條的理由（工作站穩了才分析細節）
   成立且與缺口無關。實作上 `_issue_blocks()` 只認 `reconciliation_task_id`，不再認 `subject_task_id`。
3. **一個 Task 已有 active 缺口時，該次分析的 `uncertain` 不落地；proposals 照常提交。**
   缺口只在「該 Task 目前沒有任何 active 缺口」的那次分析建立。
4. **不做新舊缺口配對，不做取代，不用文字相似度**（0044、0051 決定 8）。
   跨分析沒有穩定 identity，application 不猜——比照 `supersedes_support_ordinals[]` 立下的判準：
   模型無法明確指認時，application 不得自行推測。
5. **specialist 仍不得刪除或解決缺口**（0054 決定 20 不變）。缺口維持既有三條出路：
   員工回答（`answered`，移除）、員工說不知道／不適用（寫 `terminal_resolution`，轉記憶）、
   Task 離開 Current JD（移除，決定 26）。
6. **被抑制的 `uncertain` 不進 receipt。** outcome 照實記 `proposed`／`no_change`——
   receipt 記錄的是狀態變更，這次確實沒有新增缺口。**不加 `suppressed_gap_count`**：
   多一個只為診斷存在的欄位，換不到任何決策。
7. **不做 backoff、節流、新狀態、新欄位、新的 agenda 機制。**
8. **不做「讓 specialist 明確指認舊缺口不再成立」**（需要動 `opks_result_v1`、需要給 specialist
   ordinal 與解 issue 的權力，推翻決定 15 與決定 20）。它是決定 4 那條先例的正解，
   但**要有測量才做**：判準是「新證據讓某個舊缺口不再成立、主顧問卻仍照著問一次」的實際頻率。
   沒有那個數字之前不動契約。

## 後果

### 正面

- 0054 的價值主張（員工回答 → 自動重新分析）在生產模型下真的會發生；員工的答案會變成候選。
- **少一條規則，不是多一條。** 付費邊界仍只有一個定義（每個輸入狀態一次呼叫）。
- 缺口不會累積、不會靜默消失、`last_asked_turn_id` 不會遺失——這三件事在決定 3 之下
  **沒有機會發生**，不是被額外機制解決的。
- 誠實的模型不再被懲罰：開四個缺口與開一個缺口，再分析的時機一樣。

### 負面／代價

- **每次新增有效員工依據都可能多一次 specialist 呼叫**，即使那次依據與任何缺口無關。
  上限仍是決定 31 的「每個輸入狀態一次」，但一次訪談的總呼叫數會上升；實際金額未量測
  （Opus 單次 specialist 呼叫本次量到 US$0.024）。
- 新證據掀出的**全新**缺口要等現有缺口清光才會浮現。第一版接受：主顧問手上本來就還有題目要問。
- 新證據讓某個舊缺口實質不再成立時，主顧問仍會照著問一次；員工要重覆一次答案。
  決定 8 已寫下要不要修的判準。
- 抑制掉的 `uncertain` 不留任何痕跡：診斷時只能從 raw capture 看，看不出「模型當時還說缺什麼」。
