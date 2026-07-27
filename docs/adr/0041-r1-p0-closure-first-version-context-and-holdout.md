# 0041. R1-P0 結案、第一版 Context 表示與 R1 holdout

- 狀態：**Accepted**（owner 於 2026-07-27 裁定不為 P0 支付 trial 成本，改以外部權威證據結論收斂）
- 日期：2026-07-27
- 範圍：R1-P0 實驗的處置、第一版 Context 表示的預設架構、R1 快篩案例的 holdout 規則
- 補充：[0040](0040-professional-consultant-engine-and-r1-validation-contract.md)
  （六 arm、exit gate、模型策略一律不變；本 ADR 只補 0040 未規定的 Context 表示預設與案例 holdout）
- 權威文件：
  [Context 表示外部權威證據審查](../specs/2026-07-26-professional-consultant-context-representation-external-evidence-review.md)、
  [R1 Task Discovery 深入研究](../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md) §10.6
- 實驗資產：[R1-P0 Context Representation Screening](../experiments/2026-07-26-r1-p0-context-representation/README.md)

## 脈絡

ADR 0040 決定 2 讓 0038 的 Context Engine 邊界全面失效，但沒有規定第一版該用什麼取代它。
同時 R1-P0 實驗在 cases／rubric／assembler 凍結後停擺：原訂把 Codex subagent 當受測 API 的做法
被 owner 否決，六個案例一個 trial 都沒跑。

owner 裁定不為 P0 另付真 provider 的 trial 成本，改以外部權威證據直接收斂。該審查的結論是三層 Hybrid，
且其 §10 自述「外部研究不能取代本產品 A/B，只能提供安全預設與待測風險」。

若不記錄，會出現三種誤用：把 P0 的未執行寫成「實驗顯示持平」；把研究結論當成 R1 已經不必跑；
以及讓 P0 停在「Deferred」狀態，使下一位實作者以為它還要執行。

另外，R1 深入研究 §10.6 已把「八個案例很容易被 Prompt 過度擬合」列為反方六，但 ADR 0040 的
案例規則沒有對應的防護。

## 決定

### 1. R1-P0 結案

1. R1-P0 **結案為「不執行」**，不重啟、不升 revision、不改用真 provider 跑原四 arm。
2. **結案理由是 YAGNI 與外部證據，不是實驗結果。** 零個 trial 曾被執行。
   任何文件**不得**把本結案寫成「實驗顯示 Hybrid 與 Raw 持平」或「Evidence 架構已被驗證／否決」——
   那會違反 P0 README §1.1 對事後重新解釋的禁令，也是虛構結果。
3. 六個 frozen cases、`rubric.md`、`assemble_context.py` 與其測試**保留為可重用實驗資產**，
   不刪除；它們可供後續 extraction fidelity 或 Context 實驗改寫使用，但須另升 revision。
4. P0 原本要問的問題（額外提供一份**人工整理的字面 claim table** 是否加值）**由 §2.3 直接以 YAGNI 回答**，
   不再需要實證。P0 對 typed Work Model 的射程限定（README §3.2）仍然成立：
   本結案**不涵蓋** typed Work Model 的價值判斷。

### 2. 第一版 Context 表示

5. 第一版採**三層 Hybrid**，作為**安全預設**，不宣稱已由本產品實證：

   | 層 | 回答的問題 | 權威地位 |
   |---|---|---|
   | Source Layer | 員工實際說了／做了什麼 | 唯一逐字真相，永遠保留，不被摘要取代 |
   | Current Work Model | 目前對這份工作的理解是什麼 | 可操作現況與索引，**不冒充逐字來源** |
   | Operation-specific Context Packet | 這一次模型要看什麼 | 每次 operation 組裝，非持久資產 |

6. **不建 literal-claim layer**：不為餵模型而額外維護一份人工／自動的逐字 claim table。
   Current Work Model 之所以存在，是因為員工必須能檢視與修改現況、且 reload 要讀得到它
   （ADR 0040 決定 18），**不是因為它被證明能改善模型的 Task 判斷**。這兩個理由不得混寫。
7. 沿用證據審查 §11 的分層：

   | 決定 | 項目 |
   |---|---|
   | 現在採用 | lossless transcript、可修改 Current Work Model、operation-specific Context Packet、source linkage、recent window、insufficient／unknown 出口 |
   | 有失敗證據再加 | BM25／embedding、reranker、compaction、週期性 challenger、較完整 retrieval planner |
   | 延後 | GraphRAG、圖資料庫、多 Agent memory、全域 community summaries |
   | 拒絕 | summary-only、Evidence-only、embedding-only、每回合永遠 full-history-only |

8. Current Work Model 的每個重要判斷必須能回到 `turn_id`。此要求由 ADR 0040 決定 25 的
   deterministic verifier（source span 存在、ID／跨欄位引用合法）承擔，不另建機制。

### 3. R1 效力不變

9. **ADR 0040 的六 arm 快篩、最強模型天花板、exit gate 與「持平選簡單者」一律不變。**
   本 ADR 決定的是第一版**建什麼**；R1 要驗的是 harness 是否承重、schema 重量、單／雙階段是否值得——
   不同問題，外部研究沒有回答。
10. **不得以「Context 表示已有研究結論」為由縮減或跳過 R1 的任何 arm。**
    被引用的 OpenAI Evaluation Best Practices 與 Anthropic Demystifying Evals 本身都要求 eval 必須
    task-specific；用它們來取代自建 eval 是誤用。

### 4. R1 快篩案例 holdout

11. R1 的 8 個快篩案例（roadmap §8.5）在**第一次 prompt 迭代之前**切分為：

    案例 ID 見 [R1 深入研究](../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md) §11。

    | 組 | 案例 | 用途 |
    |---|---|---|
    | 迭代組（6） | `TI-R1-01` 工具名稱不是 Task、`TI-R1-03` 一故事多工作、`TI-R1-04` 多故事一 Task、`TI-R1-05` 過去工作、`TI-R1-06` 他人工作／交接、`TI-R1-08` 更正先前說法 | prompt／context／schema 迭代期間可見 |
    | **Holdout（2）** | **`TI-R1-02` 工具操作有獨立 outcome 因此可成 Task、`TI-R1-07` 一次性支援** | 封存，迭代期間**不得檢視輸出、不得據以改 prompt** |

12. 選這兩案的理由：迭代組仍完整覆蓋工具、拆分、合併、時間、他人責任、更正六類風險；
    而 `TI-R1-02` 是八案中**唯一的正向案例**（工具相關工作**可以**成為 Task），最容易被過度擬合成
    「看到工具就排除」的 prompt；`TI-R1-07` 與 `TI-R1-06` 同屬「不得升格為穩定責任」，抽走不損失類別覆蓋。
    **holdout 必須在迭代開始前指定**；事後挑選等於沒有 holdout。
13. 開封規則：holdout **只在 shortlist 之前開封一次**。開封後若再修改 prompt／context／schema，
    該次 holdout 結果即**作廢**，須另行構造新案例才能重新取得 holdout 效力。
14. holdout 的失敗不是自動否決，但必須寫入 R1 報告；**迭代組通過而 holdout 失敗，即視為過度擬合證據**，
    不得以「案例太少」帶過。

## 後果

### 正面

- P0 的狀態明確結案，下一位實作者不會以為還有實驗待跑，也不會誤引為已驗證結果。
- 第一版 Context 有明文預設，填補 0040 決定 2 讓 0038 失效後留下的空白。
- 省下 P0 真 provider 的 trial 成本與時間，而其唯一未決問題（literal-claim layer）本來就落在
  P0 事前登記的預期結果上，以 YAGNI 收斂不損失資訊。
- holdout 讓 R1 的「快篩通過」不再能單靠對八案調 prompt 取得。

### 負面與成本

- 三層 Hybrid 是**未經本產品驗證的預設**。若 R1 的 Task 邊界失敗且可歸因到 Context 表示，
  必須重開實驗，屆時成本比現在跑 P0 更高（已有實作綁定）。
- 迭代組只剩 6 案，迭代期間的訊號更弱。
- holdout 只能用一次，用掉之後 R1 後續階段沒有同等強度的過度擬合防線。

### 風險與未決

- **literal-claim layer 與 typed Work Model 的價值在本產品內永遠沒有實證**，只有外部證據與 YAGNI。
  這是接受的缺口；typed Work Model 的問題仍屬 ADR 0040 的 A2 vs A6 與後續 extraction fidelity 實驗。
- 證據審查大量引用 2024–2026 的外部論文與大廠工程文章，其任務（QA、程式、長文件、個人化記憶）
  都不是職務訪談。轉移的是失敗模式，不是成效；**不得在後續文件中把這些來源寫成本產品的效能依據**。
- 本 ADR 未規定 Current Work Model 的具體欄位與持久化形狀，那由第一條 production vertical 的
  plan 與 `docs/design/professional-consultant-engine.md` 決定。
