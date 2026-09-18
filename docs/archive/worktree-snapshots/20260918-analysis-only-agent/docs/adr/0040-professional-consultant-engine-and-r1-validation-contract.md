# 0040. 專業顧問引擎 greenfield 與 R1 驗證契約

- 狀態：**Accepted**（owner 於 2026-07-26 核准；第二位審查者同日條件式核准，條件已修畢）
- 日期：2026-07-26
- 範圍：專業職務分析顧問引擎的權威來源、R1 驗證方法、模型策略、狀態與歷史邊界、
  Structured Output 契約、K/S/A 支持度、公版匯出措辭
- **Supersedes**：[0038](0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)
  （**完整取代，非局部**）
- 部分修正：
  [0034](0034-interview-ai-vnext-greenfield-evidence-workflow.md)（greenfield 原則保留，
  operation catalog 與 state 形狀不再沿用）、[0039](0039-local-multi-document-canonical-public-form-workspace.md)
  （本機多文件與公版版型決策保留，儲存語意改由本 ADR 的 Current State + Journal 邊界決定）
- 權威文件：
  [顧問流程最終反方審查](../specs/2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)、
  [LLM 程式架構紅隊審查](../specs/2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md)、
  [實現路線圖](../specs/2026-07-25-professional-consultant-architecture-realization-roadmap.md)、
  [R1 Task Discovery 深入研究](../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)
- 複審與修訂：
  [R1 紅隊複審與修訂裁決](../specs/2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md)

## 脈絡

Owner 已裁定：2026-07-25 的三份權威文件加上 R1 深入研究是現行方向，**其餘 AI 層文件視為過時，重作**。
但 ADR 索引仍指向 0038 為「後續產品切片 authority」，其 operation catalog（`turn.interpret`／`question.select`／
`episode.code`／`job.consolidate`／`requirements.draft`／`job.compose`）與新架構的
（`turn.understand`／`work.reconcile`／`consultation.decide`／`job.analyze`／`document.propose`／
`public.challenge`／`quality.challenge`）名稱與切法皆不同。若不記錄翻案，下一位實作者會照 0038 施工。

同時，對四份權威文件的外部複審（見上列修訂裁決）以 *make the strongest case that this is wrong* 方式，
用 2026 年大廠工程文件、法規與同行審查文獻找出九項需要修訂的地方。其中最嚴重的是：
**原 R1 計畫以固定便宜模型的結果裁決架構**，這會混淆「模型能力不足」與「架構設計錯誤」，
並使 harness 永久 over-fit 到弱模型。

本 ADR 固定翻案關係與這九項修訂，避免它們散落在 spec 裡被後續實作忽略。

## 決定

### 1. 權威來源與翻案關係

1. 專業顧問引擎採 greenfield 實作，權威為上列四份 2026-07-25／26 文件。
2. **ADR 0038 全面失效，不是局部取代**：其 operation catalog、Context Engine 邊界、
   Agenda／Sufficiency、JobStateDigest 與 Authoring Core 流程一律**不再是 authority**，**不得據以開新工**。
   **只有被上列新文件重新寫明的觀念才繼續有效**；不得以「0038 沒說不行」為由沿用其任何規定。
3. `apps/api/app/interview_vnext/` 與 `apps/api/app/interview/` 既有實作**不作為新引擎的前提**。
   語料重用邊界：

   - **可重用**：原始 transcript、案例意圖、語意陷阱設計、`adjudication.md` 的裁決理由 ——
     且僅作為「**待依新 Task rubric 重新審查的候選依據**」，不是現成答案。
   - **不可重用**：舊 `gold.json`、舊 schema、舊 operation 名稱、Evidence 模型、loader、prompt、
     Context Builder、grader 實作與名稱、suite hash。
   - **所有 expected output 必須依新 Task rubric 重新裁決。**
   - `apps/api/evals/golden/JD-golden-001/` **不得直接當作新 gold**：其 `reference.md` 自述為
     agent 依樣張起草、以權威來源自審，未經正式 SME 審查，因此只能作 **candidate exemplar**，
     須重新審查後才可作為品質尺。
4. 舊路徑的正式退役時點與禁令，於第一條 production vertical 落地時寫入
   `docs/design/professional-consultant-engine.md`。在此之前不得因「新引擎存在」而擴建舊路徑。

### 2. 模型策略（修訂 R1 原設計）

5. R1 先以**最強可用模型**建立品質天花板，再往下換便宜模型，而非固定便宜模型先驗架構。
6. R1 的實驗矩陣**固定為 6 個 arm，baseline 是其中之一，不另計**：

   | # | Arm | 模型 | schema | 架構 | harness |
   |---|---|---|---|---|---|
   | A1 | **minimal-harness baseline**（W2 對照組） | 最強 | 輕 | 一次呼叫 | **minimal**（只給 Task rubric） |
   | A2 | 候選 | 最強 | 輕 | 兩階段 | full |
   | A3 | 候選 | 最強 | 重 | 兩階段 | full |
   | A4 | 候選 | 便宜 | 輕 | 兩階段 | full |
   | A5 | 候選 | 便宜 | 重 | 兩階段 | full |
   | A6 | 候選 | 最強 | 輕 | **一次呼叫** | full |

   **A6 的模型與 schema 固定為「最強 + 輕」，不是「A2–A5 勝出配置」**，否則 A1 vs A6 會同時改動
   模型、schema 與 harness，無法歸因。三個比較各自只打開一個變因：

   | 比較 | 唯一差異 | 回答的問題 |
   |---|---|---|
   | A1 vs A6 | harness bundle（minimal ↔ full） | harness 是否承重 |
   | A2–A5 內部 | 模型 × schema（架構固定兩階段） | 容量與 schema 重量的交互作用 |
   | A2 vs A6 | 架構（兩階段 ↔ 一次呼叫） | 拆解是否值得 |

   **不得把 A1 vs A6 的差異描述成「只差 typed Work Model」** —— 差的是整個 minimal/full harness bundle
   （typed Work Model、context policy、verifier 等一起換），過度指定因果即為誤述。

   「A2–A5 勝出配置下的一次呼叫／兩階段複驗」**移到 shortlist 或 shipping model gate**，不放進快篩矩陣。

   快篩階段規模：**48 個 case-arm trial observations**（6 arms × 8 cases × 1 trial）。
   對應的**生成器模型呼叫為 80 次**：單階段 arm（A1、A6）2 × 8 = 16 次，
   兩階段 arm（A2–A5）4 × 8 × 2 = 64 次。**LLM grader 呼叫另計。**
7. **兩階段拆分降級為待實驗假說**，不再視為已確定架構；**兩者持平時選較簡單者（一次呼叫）**。
8. shipping 模型定案時必須重跑一次一次呼叫／兩階段對照；換模型時重審 harness，
   拆掉不再承重的 scaffolding。

### 3. R1 驗證契約

9. exit gate：**無 critical regression，且 Task 邊界品質必須有預先定義的實質改善**。
   **若只是持平，選較簡單的 baseline／較少呼叫的架構。**
   可診斷性不得單獨替較複雜的架構取得通行證。
10. 判準必須在跑實驗**之前**寫定：哪些是 deterministic check、哪些是人工 rubric、
    「實質改善」的具體門檻是什麼。
11. 案例與 trial 分三階段，**不是每個 configuration 都跑 pass³**：

    | 階段 | 規模 | 用途 |
    |---|---|---|
    | 快速篩選 | 8 cases × 6 configurations × 1 trial | 只淘汰明顯錯誤設計，**不得宣稱勝出** |
    | 候選縮小 | shortlist 後擴至 20–30 cases | 形成可討論的品質判斷 |
    | Gate | 僅 shortlisted 架構的 critical subset 跑 pass³ | 決定是否進 R2 |

12. R1 **不做正式 power analysis**；但同一 session 衍生案例共用 `case_family_id`，
    統計時整組算一個單位，不得把重複呼叫當獨立樣本。
13. 案例 metadata 必含 `source_type` 與 `case_family_id`。`source_type` 依**案例實際來源**標記，
    不是依信心程度：

    | 值 | 適用 |
    |---|---|
    | `constructed_edge` | 人工構造的案例（**構造案例一律標此值，不得標成 human_manual_test**） |
    | `human_manual_test` | 確實有人操作產生，但是否描述真實工作未知 |
    | `real_employee_interview` | 能證明受訪者在描述本人真實工作 |

    **不設預設值，依實際來源分類**。由舊 session 衍生時：**原樣使用人類操作逐字稿＝`human_manual_test`；
    改寫或合成成新案例＝`constructed_edge`**，兩者皆可另留 `source_session_ref`。
    `human_manual_test` 不得在缺乏證據時升級為 `real_employee_interview`。

### 4. 評審者三層

14. **Job Analysis Quality Rubric** 為單一權威判準資產（Task 邊界、支持度、禁止錯誤、完成條件）。
15. **R1 Eval Grader**：開發期、盲測、可回 `Unknown`、不讀產生器 rationale、按維度分開評分。
16. **R7 Product Challenger**：執行期，讀 Evidence／Current Work Model／JD，不讀產生器自我辯護，
    只輸出 blocker／疑點／追問；不得宣布完成，不得修改正式文件。
17. 三者共用 rubric 資產，**不共用 prompt、範例與輸出目的**。

### 5. 狀態、歷史與重播邊界

18. **Current Work Model／Current JD 是唯一現況真相**；reload 直接讀取，不 replay。
19. 允許 **append-only Consultation Journal**（回合、員工決策、直接編輯），與現況修改**同一 transaction** 寫入；
    **Journal 不被要求足以重建 Current State**。
20. 第一版不做以事件為唯一真相、靠 replay 重建 Current State 的完整 Event Sourcing。
21. prompt／context／model 的比較重播由 **runtime 之外的 eval capture artifacts** 負責，保存三層：
    source/state snapshot、context packet + operation input、trial evidence。
22. 三層由**單一 Trial Manifest** 管理（一次 trial 一份、寫入後不可變），各層以 reference 關聯；
    `resolved_model`／`resolved_provider+endpoint` **必須取自回應，不得由請求推斷**。

### 6. Structured Output 契約

23. 在 OpenRouter-first（ADR 0035）前提下，**provider 端的 schema 保證不可攜**（含 key ordering）：
    支援度 per endpoint、enforcement 因 provider 而異、strict mode 可能限制可用的 JSON Schema 特性。
24. 採 **portable schema subset**：object／array／基本型別、required、nullable union、enum、
    `additionalProperties: false`、基本巢狀。
25. 其餘一律由 **deterministic verifier** 負責：quote 非空與最小長度、至少一個 source anchor、
    陣列語意去重、數值範圍、source span 存在、ID／跨欄位引用合法、correction target 存在、
    Task 不得因 schema 必填被迫產生、actor／time／ownership 語意規則。
26. 執行要求：固定 exact model slug 與 endpoint、`require_parameters: true`、禁 fallback、
    R1 live preflight 實送 portable schema、local verifier 永遠存在。
27. **JSON Schema 容量上限不是架構常數**，由 resolved endpoint 決定；核心規格不寫死全域
    property／nesting 上限，以 live preflight 實測為準（文件為預期值）。
28. 不把「rationale 欄位排在 schema 最前」當成提升推理品質的方法。需要「先推理後格式化」時依序採用：
    具原生 reasoning 能力的模型 → 減輕 schema → 避免 forced function calling → 最後才拆兩次呼叫。

### 7. K/S/A 與 Indicator 支持度

29. K／S／A 與 Indicator 數值門檻一律帶支持度：`behavior_grounded`／`employee_confirmed`／
    `reference_candidate`／`unsupported`。
30. `unsupported` 不得進正式 JD；`reference_candidate` 只能作候選；`employee_confirmed` 可進但保留標記。
31. 系統必須區分「員工會什麼」與「這份工作要求什麼」；**員工按接受不得被記錄成已有行為證據**。
32. Attitude 一併適用（最缺行為證據、最易膨脹）。

### 8. 公版匯出措辭

33. 匯出標示為「採 iCAP 職能基準欄位版型的客製職務說明書，不代表勞動部認證或官方職能基準」。
34. **不得自行產生看起來像官方認證的職能基準代碼**。

## 後果

### 正面

- ADR 索引不再指向已被取代的 operation catalog，實作者不會照 0038 施工。
- R1 的實驗能分辨「模型不夠強」「schema 太重」「拆解有沒有幫助」「顧問工作切錯」四種失敗，
  而非把它們混成一句「架構不好」。
- exit gate 失去逃生門，路線圖 §21 的停損條件恢復效力。
- Journal／Eval Capture 分離後，R3／R5 的恢復類 gate 有明確歸屬，且不必付 Event Sourcing 的複雜度。
- Structured Output 的責任邊界明確，不會在換 provider 時靜默失去保證。
- K/S/A 支持度直接對應職務分析文獻中最強的已知偏誤來源。

### 負面與成本

- R1 首輪成本提高：多一組強模型與 schema 變體（估計仍在個位數美元量級，因案例僅 8 個）。
- 兩階段拆分變成待驗假說，R1 的實作要能同時跑一次呼叫與兩階段兩種路徑。
- Trial Manifest 與三層 capture 是額外工程，雖然形狀最小，仍需在 R1 就建立。
- 支持度四級會讓 R4 的資料模型多一個維度，且 UI 之後要能呈現「這是確認的還是有證據的」。

### 風險與未決

- **Owner 於 2026-07-26 裁定：沒有真人員工訪談資料，不進行 DB 語料盤點。**
  因此 **R1 僅使用非真實員工資料**，來源可為 `constructed_edge` 或 `human_manual_test`
  （後者限於舊 session 逐字稿恰好可用時）；`real_employee_interview` 保留定義但**目前無此類資料**。
  「沒有真實員工訪談」不等於「全部案例都是人工構造」，兩者不得混寫。
- 直接後果：**C-08（K/S/A 自述膨脹）在 R1–R7 無法用真實在職者資料驗證**，只能靠 rubric 與
  deterministic verifier 擋住；真正的驗證必須留到 R9 真實試用。這是已知且被接受的缺口，
  不得因為 R1 通過就宣稱膨脹問題已解決。
- 既有舊 session（`eb2af457` 25 回合／`6f807f1e` 22 回合 persona 扮演／`53dcde00` 未確認）
  僅在其逐字稿恰好可用時作為素材：**原樣使用＝`human_manual_test`；改寫或合成成新案例＝`constructed_edge`**
  （皆可留 `source_session_ref`）。兩者**都不得**當成真實在職者分布或升級為 `real_employee_interview`。
- 現行 repo 同時存在 `app/interview`（production）與 `app/interview_vnext`（隔離）兩套舊路徑；
  本 ADR 只宣告它們不是新引擎的前提，**未指定退役時點**，該時點由第一條 production vertical 落地時決定。
