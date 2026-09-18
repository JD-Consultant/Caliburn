# 0050. OPKS Proposal 的最小形狀：獨立、薄、每項一筆

- 狀態：Accepted
- 日期：2026-08-01
- 補充：[0049](0049-opks-derived-axes-evidence-whitelist-and-document-authority.md) 決定 8、11、13。
  0048／0049 的裁決全部不變，本 ADR 只補「OPKS 提案怎麼持久化」這一個未定義處。
- 審查：外部審查者 closure review（2026-08-01，第四輪）

## 脈絡

0049 決定 11 要求 OPKS 全部經 Proposal gate、決定 13 以 rejected Proposal 承載拒絕記憶。
查證現行 `app/job_analysis/domain/proposal.py` 後確認：**現有 Proposal 完全是 Task 專用**，
無法承載 OPKS。

- `ProposalAction` 只有 `add`／`revise`／`withdraw`／`merge`／`split`；
- `TaskTarget.task_id`、`MergeTarget`／`SplitTarget` 全部以 `TaskId` 定義；
- stale 與衝突以 `affected_task_ids` 計算；
- `validate_edited_jd_after()` 操作的是 `JdEntry`（`task_id -> content`）。

因此「`REJECTED` 已存在」只證明**狀態機語意可借鏡**，不證明 OPKS 已有可持久化的提案。
不先定死形狀就寫 plan，施工者必須臨場決定四件事：擴充既有 Task Proposal 或另建、
一次生成的 O/P/K/S 是一包還是每項一筆、edit／stale 怎麼表達、authority snapshot 怎麼取。

## 決定

1. **建獨立、薄的 `OpksProposal`。** 不把 OPKS 塞進現有 `ProposalTarget`，
   **也不抽通用 Proposal framework**——只重用權威原則，不重用型別。

   ```
   OpksProposal
   ├─ proposal_id
   ├─ operation_id            同一次模型 operation 產生的數筆共用，供 UI 分組
   ├─ entity_kind: output | indicator | knowledge | skill | attitude
   ├─ action: add | revise | remove
   ├─ target_id?              revise／remove 必填
   ├─ before?                 revise／remove 必填
   ├─ after                   remove 以外必填
   ├─ task_refs[] / indicator_refs[]
   ├─ evidence_links[]        非空（0048 決定 3、0049 決定 5–9）
   ├─ status                  沿用既有 ProposalStatus 值域與轉移表
   ├─ rejection_reason?
   └─ authority snapshot      沿用 Task Proposal 既有的 authority generation／CAS，不另發明
   ```

2. **粒度：第一版每個項目一筆 Proposal。** 同一次模型 operation 可建立數筆，
   由 `operation_id` 關聯、UI 同區呈現，但**第一版不做批次核准框架**。

   理由：每條 K/S 可獨立 `confirm`／`edit`／`reject`／`unknown`；一條錯誤不會迫使整包作廢；
   拒絕記憶有明確 identity（0049 決定 13 才成立）；不污染 Task 的 merge／split lineage。

   > **域粒度不等於 UI 粒度。** 一個 Task 的 OPKS 生成可能產出十餘筆提案；
   > 那是 UI 的分組與呈現問題，不是把它們在領域層綁成一包的理由。

3. **stale 規則**（對應 Task 側的 `affected_task_ids`）：`OpksProposal` 在下列任一情況轉 `stale` ——
   - `revise`／`remove` 的 `target_id` 已不存在；
   - 任一 `task_refs` 指向的 Task 已退休或不存在；
   - 另一筆觸及同一 `target_id` 的提案先被接受。

4. **`entity_kind` 決定 refs 的合法性**：`output`／`indicator` 必須有恰好一個 `task_refs`
   （官方 `O1.1.1`／`P1.1.1` 是任務層編號）；`knowledge`／`skill` 的 `task_refs` 可多筆、
   `indicator_refs` 選填；`attitude` 兩者皆可為空（文件層，0048 決定 5）。

5. **綁定 0049 決定 8 的 direct-edit 來源鑄造**：**只有員工實際修改了 `after` 文字時**，
   application 才可建立對應的 employee-authored edit source。
   **單純 accept／reject 不得偽造 direct-edit source**——否則就是 0049 決定 6 禁止的那條後門。

## 依據

現行 Proposal 的每一項 Task 耦合都在程式碼中查證（見〈脈絡〉）。
選擇獨立薄型別而非通用框架，與 repo 既有紀律一致：0049 已拒絕為 OPKS 建平行 Work Model shadow，
同理不為兩種提案抽共用抽象——**兩者的 target、stale 規則與 lineage 語意本來就不同**。

## 後果

正面：

- 施工者不必臨場決定形狀；plan 可以直接切 task。
- Task Proposal 一行不改，既有 merge／split lineage 與 `affected_task_ids` 不受影響。
- 每項一筆讓 0049 決定 13 的拒絕記憶真正可用（有 identity 才記得住拒絕了什麼）。

負面／風險：

- 兩套 Proposal 型別共存，`ProposalStatus` 與轉移表被兩者共用。若日後第三種提案出現，
  才考慮抽象化——**現在抽是過早**。
- 一次生成十餘筆提案，員工點擊次數高。第一版接受；若真實使用顯示過於繁瑣，
  再設計批次核准，屆時另開 ADR。
- `operation_id` 只作分組，不承載交易語意；不得用它做批次 accept 的隱含通道。
