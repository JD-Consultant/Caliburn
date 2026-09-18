# 0055. 未解的 OPKS 缺口不再阻擋再分析

- 狀態：**Rejected（暫不採用，2026-08-06 owner 裁決）**
- 日期：2026-08-06
- 依據：[`docs/specs/2026-08-06-opks-gap-reanalysis-blocking-research.md`](../specs/2026-08-06-opks-gap-reanalysis-blocking-research.md)、
  [Opus 5 與 Luna-Pro 兩次 live smoke](../experiments/2026-08-06-opks-progressive-elicitation-live-smoke/README.md)
- 修正：[0054](0054-opks-progressive-elicitation-and-scheduled-child-operation.md) 決定 3 的**一條** pre-gate 條件。
  **0054 其餘決策全部不變**，特別是決定 20（specialist 不解決 issue）、決定 22–24（缺口的三條出路）、
  決定 29（四種終端 receipt）、決定 31（每個輸入狀態一次呼叫）。
- 不翻案：0044 / 0047 / 0048–0052 的任何裁決

## 裁決（為什麼沒有採用）

owner 2026-08-06 裁決**暫不採用**。理由是本 ADR 對嚴重程度的描述**超出證據支持的範圍**。

提案脈絡寫「這條線很可能一次都跑不到第二次分析」，但同一次 Opus run 的資料其實顯示相反的一面：

- 第 2 回合主顧問**主動問了**那個 Task 的缺口；
- 第 3 回合員工回答，主顧問**正確地**用 `issue_resolutions.answered` 關掉其中一個。

也就是**缺口確實會被問、也確實會一個一個關掉**，觀察到的速度約為一回合一個。四個缺口再花
3–4 回合就清完，一場正常長度的訪談跑得完；清完之後 pre-gate 自然放行，第二次分析會正常發生
（那時 digest 已因那些回答改變，沒有對應 receipt）。**整條線是通的。**

該 run 只有 3 回合、單一 Task，把它外推成「功能缺席」是過度推論。**真正的殘餘風險是尾端衰減**
——訪談結束時仍開著缺口的 Task（多半是後期才發現的），其已回答內容產出為零——
而不是全面失效。這個代價目前不足以支付本 ADR 的成本（每次新依據多一次呼叫、重複缺口風險、
K/S 可能碎片化）。

**要重啟需要的證據是缺口關閉率**：一次 10–15 回合、2–3 件工作的實測，看缺口消得比開得快還是慢。
在那個數字出現之前不再討論此案。研究紀錄
[`2026-08-06-opks-gap-reanalysis-blocking-research.md`](../specs/2026-08-06-opks-gap-reanalysis-blocking-research.md)
保留完整分析與兩次 live smoke 依據。

以下**脈絡／決定／後果**維持提案當時原樣，作為當初主張的紀錄，不再修改。

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
3. **該 Task 的 active 缺口比照已終結缺口，以唯讀記憶區進 specialist packet，不配發 ordinal。**
   語意只有一句：「這些缺口已經記錄在案，不要重複提出，只提新的。」
   0054 決定 20 已經為**已終結**缺口下過同一個賭注（進 packet 就是為了不重開），
   本決定只是把同一區多蓋一格，不是新機制。

   **該記憶區只供去重，不是 Evidence。** 缺口文字是 specialist 自己上一次生成的，
   可能含系統名、步驟或能力詞；若不鎖住用途，會形成
   「模型產生 gap → gap 進下次 packet → 模型從 gap 推導候選」的循環推導。因此明訂：
   **不得作為任何 proposal 的語意依據、不得產生或滿足 `SourceRef`、不得視為員工已表達的事實。**
   ADR 0049 的 Evidence 白名單（只收 `employee_turn`／`direct_edit`）在型別層已擋住它成為
   `source_refs[]`，但語意污染是**機械擋不住**的，所以要寫進 packet 的 rendering 與 prompt。
   已終結缺口記憶同樣適用本限制。
4. **本次分析的 `uncertain` 全部落地，不抑制、不配對、不取代、不用文字相似度**
   （0044、0051 決定 8）。缺口跨分析沒有穩定 identity，application 不猜——比照
   `supersedes_support_ordinals[]` 立下的判準：模型無法明確指認時，application 不得自行推測。
   **模型若沒讀懂記憶區而重複提出，後果是一筆看得見的重複缺口**，員工被多問一次，
   主顧問可用同一個答案一次收掉兩筆（0054 決定 22 明文支持一答解多缺口）。
   **這是刻意選擇的失敗方向：寧可錯得看得見，不要錯得沒人知道**（0044、0052）。
5. **specialist 仍不得刪除或解決缺口**（0054 決定 20 不變）。缺口維持既有三條出路：
   員工回答（`answered`，移除）、員工說不知道／不適用（寫 `terminal_resolution`，轉記憶）、
   Task 離開 Current JD（移除，決定 26）。
6. **receipt 照既有規則記**：本次新建立的缺口照常寫入 `gap_issue_ids`，outcome 照決定 28 判定。
   沒有「被抑制的 `uncertain`」這種東西，因此**不加 `suppressed_gap_count`**。
7. **不做 backoff、節流、新狀態、新的 agenda 機制。** 也**不拆** `trigger_digest`／`packet_digest`：
   `compute_analysis_input_digest()` 的簽章只收一個 `Task`，缺口在型別上進不了 digest，
   **自我觸發不可能發生**；缺口記憶同樣不進 `read_set`（0054 既有決定，理由是避免製造與分析
   輸入無關的 abandon 觸發器）。

   replay 時記憶區可能與排定當下不同，但 `analysis_input_digest` 代表的 Task 與 Evidence 狀態
   不變。**記憶區只用於提示既有缺口、降低重複，不保證輸出與首次執行相同，也不保證結果單調改善**
   ——多一則記憶同樣可能讓模型把語意相近但不同的新缺口誤認為已記錄、或改變候選的取捨與順序。
   這是 0054 既有的 replay 取捨（可接受的非決定性），本 ADR 不將缺口記憶加入 `read_set`。

   **局部寫入不可能發生**，因此上述非決定性不會留下半套產物：0054 決定 30 要求 Proposal、
   OpenIssue 與 receipt 同一個 `commit_authority_change()` 交易，而該 seam 的所有寫入
   （含 `work_model` 內的缺口與 journal 內的 receipt）走**單一 `uow.commit()`** 並帶
   `expected_generation` CAS。provider 已回應但 commit 前崩潰時，第一次執行**什麼都沒寫**，
   replay 取得的新輸出就是唯一落地的那一份——不會出現「同一個 `-gap{index}` ID 先後代表兩件事」。
   （provider 可能被重打一次仍是 0054 決定 33 已載明的 at-least-once 窗口，本 ADR 不宣稱改善它。）
8. **不做「specialist 用 ordinal 把 uncertainty 分類成既有／新增，application 只為新增建 issue」。**
   初步量測顯示契約成本不構成主要阻礙（數字見研究稿 §8.7），而且「給 ordinal ≠ 給寫入權」
   ——`opks_result_v1` 沒有任何解決 issue 的欄位，**不會**推翻決定 20。
   拒絕的理由只有一個：**它的失敗方向是錯的**。模型把一個真正的新缺口誤標成既有時，
   application 不建 issue，那一項就**靜默消失**；而決定 4 的方案在同樣誤判下只會多一筆看得見的重複。

   **升級門檻是雙向的，兩條都要成立**：
   **(a)** 決定 4 的重複缺口已造成**可量測**的 agenda／訪談負擔；
   **(b)** ordinal 分類方案在離線 shadow evaluation 中，`new → existing` 的誤判率與缺口召回
   下降**在可接受範圍**。
   **只有 (a) 不足以採用**——用 3% 的靜默遺失換 25% 的可見重複，在本 repo 的優先序下不是划算交易。
   兩個比率的定義與量法見研究稿 §7；**量測一律離線進行，不寫回 domain state，
   也不得把 eval 的語意相似度邏輯搬進 application**（0044／0051 決定 8 的文字相似度禁令不因量測而鬆動）。

## 後果

### 正面

- 0054 的價值主張（員工回答 → 自動重新分析）在生產模型下真的會發生；員工的答案會變成候選。
- **少一條規則，不是多一條。** 付費邊界仍只有一個定義（每個輸入狀態一次呼叫）。
- 舊缺口不會被改寫或刪除，新缺口當場記下——**兩個方向都沒有靜默遺失**。
  `last_asked_turn_id` 也不會遺失，因為缺口物件從頭到尾沒有被換掉。
- 新缺口不必等舊缺口清光；「等一輪之後模型還記不記得」這個賭注不存在。
- 誠實的模型不再被懲罰：開四個缺口與開一個缺口，再分析的時機一樣。
- **provider-facing output schema 零變更**，`opks_result_v1` 不動；改的是 specialist 的
  **input packet**（多一個唯讀記憶區）與其 rendering／prompt。

### 負面／代價

- **每次新增有效員工依據都可能多一次 specialist 呼叫**，即使那次依據與任何缺口無關。
  上限仍是決定 31 的「每個輸入狀態一次」，但一次訪談的總呼叫數會上升；實際金額未量測
  （Opus 單次 specialist 呼叫本次量到 US$0.024）。
- **重複缺口會發生。** 決定 3 靠 specialist 讀懂記憶區才不重提，那是 prompt 遵從，沒有結構保證。
  失敗時員工被同一件事問兩次。**主顧問若辨認得出兩筆被同一個答案命中，可在同回合一併收掉
  （決定 22 允許一答解多缺口）；辨認不出就會留下其中一筆。** 這是打擾，而且 ADR 0047 量過
  過時 issue 會排擠 agenda。重複負擔必須實際量（決定 8 的門檻 (a)）。
- 新證據讓某個舊缺口實質不再成立時，主顧問仍會照著問一次；specialist 沒有退回缺口的權力。
- replay 時 specialist 的記憶區可能與排定當下不同（缺口記憶不進 `read_set`）。
  證據相同、付費邊界不動，但**送出的 packet 不保證逐位元相同**——這是 0054 既有的取捨，
  本 ADR 不改，但在此明記。
