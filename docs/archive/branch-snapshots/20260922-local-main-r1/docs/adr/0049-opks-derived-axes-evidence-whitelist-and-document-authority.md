# 0049. OPKS 修正：兩軸改為投影、Evidence 來源白名單、文件層 identity 與權威流程

- 狀態：Accepted
- 日期：2026-08-01
- 修正：[0048](0048-opks-evidence-axes-and-document-level-competencies.md) 決定 1–4、20、22、23，
  並補齊其未定義處。**0048 的概念裁決全部維持**，本 ADR 只改實作形狀與措辭。
- 審查：外部審查者施工前對照（2026-08-01，第三輪）

## 脈絡

0048 已 Accepted，但寫 plan 前對照 `app/job_analysis` 現行 contracts，發現三處若不先收掉，
施工者會被迫臨場發明語意。三處都已在程式碼中查證。

## 決定

### A. 兩軸不持久化，改由 refs 推導（修正 0048 決定 1–4 的實作形狀）

1. 持久化的只有：

   ```
   Competency
   ├─ task_refs[]
   ├─ indicator_refs[]
   └─ evidence_links[]   非空（型別層不變量，0048 決定 3 不變）
   ```

2. `task_linkage` 與 `evidence_origin` **改為推導屬性，不存成欄位**：
   - `task_linkage` = `task_refs`／`indicator_refs` 非空 → `linked`，否則 `unlinked`
   - `evidence_origins` = 由 `evidence_links` 的來源型別推導，**可同時包含多種來源**

3. 理由：兩者同時持久化會製造第二份真相，讓
   `task_linkage=linked` 但 `task_refs=[]`、或 `evidence_origin=reference` 但來源是 `employee_turn`
   這類矛盾**變成可表示**——正是 0048 要消除的東西。單一 `evidence_origin` enum 另外表達不了
   「同時有員工與公版來源」的 mixed origin。

4. 先例在 repo 內：`Task.state` 是由 `retirement`／`pending_reconciliation` 推導的 `@property`，
   docstring 明寫「推導狀態，不存成欄位」。本決定同構。

### B. Evidence 來源白名單（補 0048 未定義處）

5. 第一版 `evidence_links` **只允許** `SourceKind.EMPLOYEE_TURN` 與 `SourceKind.DIRECT_EDIT`。

6. **`proposal_decision` 不得作為 Evidence。** 它可能只是員工按了接受；若它算證據，
   等於把 0048 決定 4 剛移除的 `employee_confirmed` 從後門放回來，並直接違反
   [0040](0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 31。

7. 模型從 Task 推導 K/S 時，**繼承該 Task 的有效員工來源**（`Task.effective_support_links`）；
   員工手動新增時，以該次 `direct_edit` 為來源。

8. 若 `edited` Proposal 的員工新文字要作 Evidence，由 **application 另鑄一筆 direct-edit 類來源**。
   現行 `Proposal.edited_jd_after` 已把員工文字與模型文字分開保存，具備鑄造條件。
   **不得**讓所有 proposal decision 一概變成證據。

9. `reference` 型別的來源等**公版 Reference Challenger 真正施工時**再新增，
   **不現在預建假的資料入口**。在那之前 `evidence_origins` 實際上只會是 `employee`。

### C. 文件層 K/S 的 identity 與權威流程（補 0048 未定義處）

10. 去重不得用文字相似度自動猜（[0044](0044-partial-jd-task-reconciliation-and-human-confirmation.md)
    已否決該手段），也不得每次都新增——否則文件層正規化只是名義上的。第一版：

    ```
    Context 提供既有 K/S 的 ordinal
      → 模型輸出 reuse_existing(target_ordinal) ／ add_new(fields + evidence) ／ uncertain
      → application 驗 ordinal 合法性
      → 員工透過 Proposal 決定
    ```

11. **OPKS 不建平行的 Work Model shadow。** 真相住哪裡：
    - 已接受的 O/P/K/S/A：**只住 Current JD**
    - AI 新建／修改：先住 **Proposal**
    - 員工直接編輯：立即更新 Current JD 並產生 direct-edit Source
    - **Pending Proposal 不是 Current JD 事實**

12. 這比「Work Model 一份 OPKS、Current JD 又一份、再做 reconciliation」少一層，
    且有兩個附帶好處：員工直接編輯 OPKS **不需要 reconciliation**（沒有 shadow 要對齊）；
    OPKS 全部經 Proposal gate，而它正是最易虛構的一格，多一道人為關卡是對的。

13. **被拒絕的 K/S 用既有機制記憶，不新增結構**：`ProposalStatus.REJECTED` 是終端狀態且持久化，
    另有 `rejection_reason`。生成時把**近期被拒絕的 K/S 提案**帶入 context，避免反覆重提。
    這回答了「沒有 Work Model 就沒有拒絕記憶」的疑慮——記憶住在 Proposal，不需要 shadow。

14. **OPKS 是獨立 operation，有自己的 wire schema**，不是 `task_analysis_result_v2` 的擴充。
    理由有二：0048 決定 10 的單次輸出總量限制；以及避免與既有 `disposition`／relation↔change
    耦合機制混在同一份 schema——那組耦合已經產生過 ordinal base 與規則可見性的缺陷。

### D. 既有 hint 欄位退役（補 0048 未定義處）

15. `Task.deliverable_hint` 與 `Task.success_criterion_hint` **在 OPKS 上線時退役**。
    查證現況：`llm/wire.py` 已不再向模型索取這兩個欄位，production 沒有任何寫入路徑；
    唯一消費者是 `application/context.py` 的 packet 渲染。它們與正式 O/P 語意重疊，
    留著必然成為兩份真相。退役成本因此僅限移除欄位與其渲染。

### E. 三項措辭修正

16. **修正 0048 決定 20／22 的相互矛盾。** 數值與外部指涉改為三檔並明確標示可查核性：
    - 具名法規／SOP／規章／明確約定，或員工逐字說出的數值 → 可寫，**標為可查核**
    - 員工逐字只說「依公司程序」→ **忠實保留，標為未具名、不得宣稱已查核**；重要時才追問
    - 模型自行補「依公司規定」「於適當時間內」→ **禁止**

17. **修正 0048 決定 23 的過度外推。** 正確表述為：
    > **本輪檢查的四個體系文件中，職務描述層未發現數值門檻。**

    樣本限定：香港為官方資料庫**全量 1,351 筆**；澳洲**僅 2 個單元**；新加坡**僅 1 個 framework**
    （全國共 38 個產業別）；OPM 為特定文件。**不得外推成整個國家體系皆無。**

18. **修正 0048 決定 11 的理由。** 「官方理由只有跨系統互通」過度絕對——taxonomy 亦官方用於
    人才媒合、學習路徑與分析。**不綁 taxonomy 的結論不變**，但充分理由改為：
    本機單文件、繁體中文缺乏、**證據保真**（綁定會把員工真實知識壓成清單最近詞，破壞可追溯性），
    且目前沒有跨文件分析需求。

## 依據

B1／B2／B3 三項均以現行程式碼查證：`SourceKind` 確實只有三個值且無 `reference`；
`ProposalStatus` 的 `REJECTED`／`EDITED` 為終端狀態且 `edited_jd_after` 已分離員工文字；
兩個 hint 欄位確實無 production 寫入路徑。

## 後果

正面：

- 矛盾狀態（linked 但無 refs、origin 與來源型別不符）**在型別層無法表示**，
  不再依賴 verifier 事後抓。
- mixed origin 自然可表示，公版 Challenger 上線時不需再改契約形狀。
- 少一層 OPKS shadow 與其 reconciliation，且拒絕記憶沿用既有 Proposal 儲存，不新增結構。

負面／風險：

- 每次讀取都要計算推導屬性；資料量小，可接受。
- OPKS 全部經 Proposal gate 會增加員工點擊次數。第一版接受；若真實使用顯示過於繁瑣，
  再考慮比照 Task 的 identity gate，屆時另開 ADR。
- `reuse_existing` 的 ordinal 由模型指定，錯指會把兩條不同知識合併。application 只能驗 ordinal
  合法性，**語意正確性靠員工在 Proposal 上把關**——這是第一版刻意接受的邊界。
- 退役兩個 hint 欄位會動到既有 packet 渲染與其測試；屬 move-only 等級，但仍是既有行為變更。
