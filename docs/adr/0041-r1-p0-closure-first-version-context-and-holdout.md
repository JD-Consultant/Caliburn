# 0041. R1-P0 結案、第一版 Context 表示與 R1 holdout

- 狀態：**Accepted**（owner 於 2026-07-27 裁定不為 P0 支付 trial 成本，改以外部權威證據結論收斂；
  **同日第二位審查者條件式核准，六項條件已修畢**——見文末「2026-07-27 第二次審查修訂」）
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

1. R1-P0 **結案為「不執行」**：第一版不投入 trial 成本，不以真 provider 跑原四 arm。
   這是**第一版的成本裁定，不是永久禁令**——owner 的裁定是「不為此支付成本」，
   不是「永遠不得驗證」，兩者不得混寫。要重啟須另升 experiment revision 並經 owner 核准。
2. **結案理由是 YAGNI 與外部證據，不是實驗結果。** 零個 trial 曾被執行。
   任何文件**不得**把本結案寫成「實驗顯示 Hybrid 與 Raw 持平」或「Evidence 架構已被驗證／否決」——
   那會違反 P0 README §1.1 對事後重新解釋的禁令，也是虛構結果。
3. 六個 frozen cases、`rubric.md`、`assemble_context.py` 與其測試**保留為可重用實驗資產**，
   不刪除；它們可供後續 extraction fidelity 或 Context 實驗改寫使用，但須另升 revision。
4. P0 原本要問的問題（額外提供一份**人工整理的字面 claim table** 是否加值）在**第一版**依 YAGNI 擱置：
   **目前沒有足夠證據支持其成本，因此暫不實作**。**這不等於問題已被回答。**
   若日後 extraction fidelity 或 Task 邊界失敗且可歸因到 Context 表示，仍應重開實驗。
   P0 對 typed Work Model 的射程限定（README §3.2）仍然成立：
   本結案**不涵蓋** typed Work Model 的價值判斷。

### 2. 第一版 Context 表示

5. 第一版採**三層 Hybrid**，作為**安全預設**，不宣稱已由本產品實證：

   | 層 | 回答的問題 | 權威地位 |
   |---|---|---|
   | Source Layer | 員工實際說了／做了什麼 | 唯一逐字真相，永遠保留，不被摘要取代 |
   | Current Work Model | 目前對這份工作的理解是什麼 | 可操作現況與索引，**不冒充逐字來源** |
   | Operation-specific Context Packet | 這一次模型要看什麼 | 每次 operation 組裝，非持久資產 |

6. **第一版不建 literal-claim layer**：不為餵模型而額外維護一份人工／自動的逐字 claim table。
   理由是成本未被證據支持（決定 4），不是它已被否證。
   Current Work Model 之所以存在，是因為員工必須能檢視與修改現況、且 reload 要讀得到它
   （ADR 0040 決定 18），**不是因為它被證明能改善模型的 Task 判斷**。這兩個理由不得混寫。
7. 沿用證據審查 §11 的分層：

   | 決定 | 項目 |
   |---|---|
   | 現在採用 | lossless transcript、可修改 Current Work Model、operation-specific Context Packet、source linkage、recent window、insufficient／unknown 出口 |
   | 有失敗證據再加 | BM25／embedding、reranker、compaction、週期性 challenger、較完整 retrieval planner |
   | 延後 | GraphRAG、圖資料庫、多 Agent memory、全域 community summaries |
   | 拒絕 | summary-only、Evidence-only、embedding-only、每回合永遠 full-history-only |

8. **表格中的 `recent window` 是長對話下的機制，不是第一版的起手式。** 啟用時機分兩段：

   | 情境 | 送進 Context Packet 的內容 |
   |---|---|
   | 短對話／完整 transcript 放得下（**第一版預設**） | 完整 transcript ＋ 最小 Current Work Model |
   | 對話變長，或 eval 顯示 full context 開始退化 | recent full turns ＋ 按 operation 選取的原句 ＋ Current Work Model |

   **Source Layer 永遠完整保存**，縮減的只是每次送給模型的 Context Packet。
   不以任意固定 token 數當永久架構常數（證據審查 §1 建議 1–2）。
9. Current Work Model 的每個重要判斷必須能回到 `turn_id`。此要求由 ADR 0040 決定 25 的
   deterministic verifier（source span 存在、ID／跨欄位引用合法）承擔，不另建機制。

### 3. R1 效力不變

10. **ADR 0040 的六 arm 快篩、最強模型天花板、exit gate 與「持平選簡單者」一律不變。**
    本 ADR 決定的是第一版**建什麼**；R1 要驗的是 harness 是否承重、schema 重量、單／雙階段是否值得——
    不同問題，外部研究沒有回答。
11. **不得以「Context 表示已有研究結論」為由縮減或跳過 R1 的任何 arm。**
    被引用的 OpenAI Evaluation Best Practices 與 Anthropic Demystifying Evals 本身都要求 eval 必須
    task-specific；用它們來取代自建 eval 是誤用。
12. **沒有任何一個 arm 能單獨歸因到 typed Work Model。** A1 vs A6 差的是整個 minimal／full harness
    bundle（ADR 0040 決定 6 已明文禁止把它描述成「只差 typed Work Model」）；A2 vs A6 差的是
    **兩階段拆分整體**（含把 typed 中間結果具現化＋多一次呼叫），兩個變因綁在一起。
    因此只能說 R1 會測「兩階段拆分是否值得」與「harness 是否承重」，
    **不得寫成 R1 會獨立驗證 typed Work Model 的價值**。

### 4. R1 快篩案例：八案全數為 development set，真 holdout 延到擴充階段

13. **八案不切 holdout，全部作 development screening。**
    `TI-R1-01`–`TI-R1-08` 的 `輸入核心`、`預期`（含建議的 Task 句子）與 `Critical failure` 已完整公開在
    [R1 深入研究](../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md) §11，
    而該文件是 ADR 0040 決定 1 指定的四份 authority 之一、**寫 prompt 的人被要求必讀**。
    答案已曝光的案例事後標記為 holdout 不會產生 unseen generalization 證據。
14. 尤其**不得抽走 `TI-R1-02`**：它是八案中唯一的**正向**案例（工具相關工作**可以**成為 Task）。
    抽走會使迭代組只剩排除型案例，把 prompt 推向「看到工具就不建 Task」的單邊最佳化，
    而其失敗只反映我們自己造出的覆蓋缺口，不是過度擬合證據。
    capability eval 須同時包含「應發生」與「不應發生」的行為。
15. 八案期間的實際防線是**凍結期望**：`預期` 與 `Critical failure` 在迭代期間**不得為了配合模型輸出而改寫**。
    要改須升 case revision 並記錄理由。`TI-R1-02`／`TI-R1-07` 另標為 **locked regression cases**
    （凍結行為錨點、防退步），**不得宣稱它們證明 unseen generalization**。
16. **真正的 holdout 延到 ADR 0040 決定 11 的 20–30 案擴充階段**，且必須同時滿足：

    - **新建、未曝光**：不得取自任何已發布的 spec／ADR／roadmap；其輸入與期望
      **不得寫進任何 authority 文件**，只存在於封存的 case 檔（否則本次的失敗模式會原樣重演）；
    - **正反平衡**：同時含「應形成 Task」與「不應形成 Task」的案例；
    - 由**未參與該輪 prompt 迭代**的來源產出；
    - 開封前不得檢視輸出、不得據以改 prompt。

17. holdout 的裁決效力（適用第 16 條的真 holdout）：

    - 出現 critical failure → **不得宣稱該候選通過**；候選標為 `inconclusive` 或淘汰；
    - **只開封一次**；開封後若再改 prompt／context／schema，該 holdout 即失效，須新建一組；
    - 迭代組通過而 holdout 失敗＝過度擬合證據，必須寫入報告，不得以「案例太少」帶過。

## 後果

### 正面

- P0 的狀態明確結案，下一位實作者不會以為還有實驗待跑，也不會誤引為已驗證結果。
- 第一版 Context 有明文預設，填補 0040 決定 2 讓 0038 失效後留下的空白。
- 省下 P0 真 provider 的 trial 成本與時間，而其唯一未決問題（literal-claim layer）本來就落在
  P0 事前登記的預期結果上，以 YAGNI 收斂不損失資訊。
- 過度擬合防線寫在正確的階段：八案期間靠凍結期望，真 holdout 留到有足夠案例可正反平衡時才建立，
  且明文禁止把它的輸入與期望寫進 authority 文件——這正是本次差點犯下的錯。

### 負面與成本

- 三層 Hybrid 是**未經本產品驗證的預設**。若 R1 的 Task 邊界失敗且可歸因到 Context 表示，
  必須重開實驗，屆時成本比現在跑 P0 更高（已有實作綁定）。
- **八案階段沒有任何 unseen 證據**。快篩通過只代表「沒有明顯錯誤設計」，這與 ADR 0040 決定 11
  「不得宣稱勝出」一致，但也意味著過度擬合要到 20–30 案擴充才會被抓到。
- 20–30 案階段必須額外產出一組不寫進任何文件的封存案例，是新增的工程與紀律負擔。

### 風險與未決

- **literal-claim layer 與 typed Work Model 的價值在第一版沒有本產品實證**，只有外部證據與 YAGNI。
  這是接受的缺口，**不是已結論**；要取得實證得靠後續 extraction fidelity 實驗
  （模型自己產生型別欄位、錯誤可歸因到模型）。R1 的 A2 vs A6 只能測兩階段拆分整體是否值得，
  **不能單獨歸因到 typed Work Model**（決定 12）。
- 證據審查大量引用 2024–2026 的外部論文與大廠工程文章，其任務（QA、程式、長文件、個人化記憶）
  都不是職務訪談。轉移的是失敗模式，不是成效；**不得在後續文件中把這些來源寫成本產品的效能依據**。
- 本 ADR 未規定 Current Work Model 的具體欄位與持久化形狀，那由第一條 production vertical 的
  plan 與 `docs/design/professional-consultant-engine.md` 決定。

## 2026-07-27 第二次審查修訂

初稿當日經第二位審查者條件式核准，六項條件已修畢（比照 ADR 0040 的同日修訂處理方式）：

| # | 指出的問題 | 處置 |
|---|---|---|
| 1 | 初稿的「不重啟、不升 revision」把 owner 的**成本裁定**寫成永久禁令 | 決定 1 改為第一版成本裁定，保留升 revision 重啟路徑 |
| 2 | `TI-R1-02`／`07` 的輸入與期望早已公開在必讀 authority spec，事後標 holdout 無效 | **撤銷 holdout 設計**；決定 13 改為八案全數 development set |
| 3 | 抽走唯一正向案例會讓迭代組單邊失衡，其失敗只反映自造的覆蓋缺口 | 決定 14 明文禁止抽走 `TI-R1-02`；改以決定 15 的凍結期望＋locked regression cases 替代 |
| 4 | 初稿的 holdout 失敗「不是自動否決」等於沒有裁決效力 | 決定 17 給出真 holdout 的硬效力（不得宣稱通過／`inconclusive` 或淘汰／只開封一次） |
| 5 | 初稿把 typed Work Model 的驗證掛在 A2 vs A6，與 ADR 0040 的 arm 定義不符 | 新增決定 12 並修正風險段：沒有任何 arm 能單獨歸因 |
| 6 | 決定 7 表格的 `recent window` 易被讀成第一版就截斷 transcript | 新增決定 8 的兩段啟用時機；Source Layer 永遠完整保存 |

第 2、3 項的教訓已回寫進決定 16：真 holdout 的輸入與期望**不得寫進任何 authority 文件**。
