# 0051. OPKS Proposal 的自有狀態機與穩定 entity ID

- 狀態：Accepted
- 日期：2026-08-01
- 修正：[0050](0050-opks-proposal-minimal-shape.md) 的兩處契約不自洽（`status` 沿用與 `target_id` 選填）。
  **0050 其餘決策全部不變**，0048／0049 的裁決亦不變。
- 審查：外部審查者第五輪（2026-08-01）

## 脈絡

0050 寫「`status` 沿用既有 `ProposalStatus` 值域與轉移表」，但只列了 `rejection_reason` 一個 payload。
對照 `domain/proposal.py` 後確認這不自洽：Task Proposal 的狀態各自依賴專有 payload——
`edited_jd_after`、`stale_reason`、`revision_resolution`、`excluded_member_task_ids`、
`excluded_child_refs`、`caused_by_decision_id`。少了它們，`OpksProposal` 回答不出
「員工到底改了什麼」「stale 的原因要呈現什麼」，**而第一個問題正是 0050 決定 5
（只有真的改了 `after` 才鑄 direct-edit 來源）賴以成立的依據**。

第二處：0050 只在 `revise`／`remove` 要求 `target_id`，`add` 沒有 identity。
後果是 add 候選在被接受前沒有可跨回合指涉的 ID，兩筆競爭的 add 無從判斷衝突與 stale，
被拒候選只能靠文字相似度辨認——**正好走回 [0044](0044-partial-jd-task-reconciliation-and-human-confirmation.md)
已否決的那條路**。

Task v1 早就處理過同一題：`application/transition.py` 的 `_add()` 在**候選建立當下**
就配發 `task_id = f"{operation_id}-t{index}"`，不等接受，且**由 operation_id 推導而非隨機**，
因此重播冪等。

## 決定

### A. OPKS 自有的六態狀態機

1. ```
   OpksProposalStatus = pending | deferred | accepted | edited | rejected | stale

   pending  → deferred | accepted | edited | rejected | stale
   deferred → accepted | edited | rejected | stale
   accepted / edited / rejected / stale = terminal
   ```

2. **不支援 `revision_requested`。** 它在 Task 側服務 merge／split 的結構修訂
   （排除成員、排除子項），OPKS 沒有等價需求。

3. **0048 的 `unknown` 映射為 `deferred`，不新增第七種狀態。**
   「員工看不懂或現在答不出來」與「稍後再決定」在領域上是同一件事。

### B. 三個狀態專屬 payload

4. - `edited_after?` —— **只有 `edited` 必填**，且**必須不同於模型原始 `after`**。
     這條不變量是 0050 決定 5 的執行機制：application 只在此欄存在且相異時才鑄 direct-edit 來源。
   - `stale_reason?` —— **只有 `stale` 必填**，且必須是**可直接呈現給員工**的文字。
   - `rejection_reason?` —— 只屬於 `rejected`。

5. 三者皆比照 Task Proposal 既有寫法，以 model validator 鎖「payload 只屬於它的狀態」。

### C. 所有 action 都必須有穩定 `entity_id`

6. `target_id?` 改為**必填的 `entity_id`**：

   ```
   add:     entity_id = application 在 Proposal 建立時配發的新 ID
            before = null,  after = 候選內容
   revise:  entity_id = 既有 ID；before / after 皆有值
   remove:  entity_id = 既有 ID；before 有值，after = null
   ```

7. **ID 由 operation 推導而非隨機**，比照 Task 的 `{operation_id}-t{index}`，
   使同一 operation 重播產生相同 ID（與既有 Journal 冪等機制一致）。

8. **衝突與 stale 一律以 `entity_id` 判定**，不用文字相似度。

9. 員工拒絕 `add` 時留下未使用的 ID，**不回收**，也不因此新增 revision system。

## 依據

兩處皆以現行程式碼查證：`ProposalStatus` 的七態與其專有 payload 見 `domain/proposal.py`；
候選建立即配發 ID 見 `application/transition.py` 的 `_add()`。

本 ADR **仍不建立通用 Proposal framework**——它只讓 0050 那個獨立薄型別**自洽**。
兩種提案的 target、stale 語意與 lineage 本來就不同，共用抽象仍是過早。

## 後果

正面：

- 0050 決定 5 的 direct-edit 防線有了可執行的依據（`edited_after` 存在且相異）。
- add 從建立當下就有 identity，拒絕記憶（0049 決定 13）與衝突判定都不必回頭猜文字。
- 少一個狀態（無 `revision_requested`），OPKS 的決策 UI 比 Task 側簡單。

負面／風險：

- 兩套狀態機並存，`ProposalStatus` 與 `OpksProposalStatus` 名稱相近易誤用；
  以型別分離與命名前綴防範，不共用 enum。
- 被拒絕的 `add` 留下未使用 ID。可接受：ID 空間無壓力，回收才會製造 ABA 問題。
- `entity_id` 由模型指定 `revise`／`remove` 的目標時仍可能錯指（0050 已記此風險），
  本 ADR 不改變該邊界：application 只驗 ID 合法性，語意由員工在 Proposal 把關。
