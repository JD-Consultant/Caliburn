# 專業顧問架構 R1 紅隊複審與修訂裁決

> 日期：2026-07-26
> 狀態：**Accepted**（owner 於 2026-07-26 核准；經第二位審查者四輪複審，條件均已修畢）
> 文件性質：對 2026-07-25 三份權威文件（顧問流程／程式架構／實現路線圖）與 R1 深入研究的**外部複審**，
> 以 *make the strongest case that this is wrong* 方式進行，並記錄雙方往返四輪後的裁決
> 複審對象：
> [`顧問流程最終反方審查`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)、
> [`LLM 程式架構紅隊審查`](2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md)、
> [`實現路線圖`](2026-07-25-professional-consultant-architecture-realization-roadmap.md)、
> [`R1 Task Discovery 深入研究`](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)
> 決策記錄：[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)

---

## 1. 這份文件解決什麼

2026-07-25 的三份權威文件回答了「顧問要做什麼」「程式怎麼實現」「依什麼順序交付」。本文件回答第四個問題：

> 這套方法與架構，如果是錯的，會錯在哪裡？用 2026 年的權威證據去打，有哪幾槍打得中？

複審刻意只用三種來源：**法規與官方標準**、**大廠工程文件（Anthropic／OpenAI／Microsoft／OpenRouter 官方）**、
**同行審查文獻**。arXiv preprint 只作輔證並標明證據等級。不採用部落格農場、二手轉述與來路不明整理文。

複審結論：**顧問方法大致站得住，程式架構方向也對，但 R1 的驗證設計有結構性瑕疵** ——
原設計會用便宜模型 + 重 schema 的結果去裁決架構，而 2026 年的權威指引一致建議相反順序。

本文件記錄九項修訂（C-01～C-09）。每一項都在對應的權威文件就地標註，**原文一律保留、標為已否決**，
不刪除，以便追溯當初為什麼那樣想。

---

## 2. 修訂總表

| 編號 | 主題 | 修訂前（已否決） | 修訂後 | 主要依據 |
|---|---|---|---|---|
| C-01 | 模型策略 | 固定便宜模型先驗證架構，失敗才用強模型 spot check | 先用最強模型建品質天花板，再降本；R1 先跑 model × schema ablation | OpenAI Model Selection／Agents Guide；Anthropic Harness Design |
| C-02 | R1 exit gate | 「Task 邊界**或**可診斷性至少一項實質改善」 | 無 critical regression **且** Task 邊界須有**預先定義的實質改善**；**持平時選較簡單者**；可診斷性不得單獨替複雜架構取得通行證 | Anthropic Demystifying Evals |
| C-03 | 案例規模與 trial | 8 案例、日常每案 1 trial | 三階段：8 案 × 6 configs × 1 trial 快速篩選 → shortlist 後擴至 20–30 → 僅 shortlisted 的 critical subset 跑 pass³；`case_family_id` 為聚類單位 | Anthropic Demystifying Evals；Adding Error Bars to Evals |
| C-04 | 評審者 | 產品內 `quality.challenge`（R7）兼作品質保證 | 三層拆分：Rubric 資產／R1 blind grader／R7 product challenger | Anthropic Harness Design |
| C-05 | 狀態與歷史 | 「明確不做 Event Sourcing」（無限定詞） | Current State 為唯一現況真相 + 同交易 append-only Consultation Journal；Journal 不要求可重建 | Martin Fowler；Anthropic Managed Agents |
| C-06 | 重播能力 | 未指定 | 三層 eval capture + 單一 Trial Manifest，runtime 外 | Roadmap §18.4 既有需求；Anthropic Managed Agents |
| C-07 | Structured Output 契約 | schema 保證形狀、程式驗語意（未處理 provider 差異） | portable subset + deterministic verifier 責任表；endpoint-pinning + `require_parameters` + 禁 fallback + live preflight | OpenRouter 官方文件 |
| C-08 | K/S/A 支持度 | 只要求 task linkage 與禁止無來源數字 | 四級支持度（`behavior_grounded`／`employee_confirmed`／`reference_candidate`／`unsupported`），Attitude 與 Indicator 一併適用 | Morgeson et al. (2004) |
| C-09 | 匯出措辭 | 「政府公版格式 projection」 | 明示為採 iCAP 版型的客製 JD，非官方職能基準，不自產基準代碼 | 職能發展及應用推動要點 |

---

## 3. 核心攻擊（八項）：strongest case that this is wrong

### 3.1 C-01｜用便宜模型裁決架構，會把「模型不夠力」誤判成「架構錯」

R1 研究 §10.8／§13.2 已自問過此題，選擇「固定便宜模型先驗證架構」。這與 OpenAI 官方指引相反：

> "build your agent prototype with the most capable model for every task to establish a performance baseline…
> From there, try swapping in smaller models to see if they still achieve acceptable results.
> **This way, you don't prematurely limit the agent's abilities, and you can diagnose where smaller models succeed or fail.**"

理由不是成本，是**歸因能力**。加上 Anthropic 2026-03 的一句：

> "**Every component in a harness encodes an assumption about what the model can't do on its own,
> and those assumptions are worth stress testing.**"

用弱模型校準 harness，會把 scaffolding 永久 over-fit 到該模型；而原路線圖 R0–R9 沒有任何一步是
「換模型後重審 harness、拆掉不再承重的元件」。

輔證（**arXiv preprint，單一作者 Hengxin Fan，2026-06-08，證據等級較低，測試集偏數學**）：
heavy JSON 下 Sonnet 4.6 幾無退化（89.3%→88.7%），Haiku 4.5 −36.2pp、GPT-4o-mini −28.0pp；
forced function calling 最差；延後格式化可回收 80–87%。此證據**只足以要求做 ablation，不足以推論所有
structured output 有害**。

**修訂**：R1 的實驗矩陣固定為 **6 個 arm，baseline 算在其中、不另計**：

| # | Arm | 模型 | schema | 架構 | harness |
|---|---|---|---|---|---|
| A1 | **minimal-harness baseline** | 最強 | 輕 | 一次呼叫 | **minimal**（只給 Task rubric） |
| A2 | 候選 | 最強 | 輕 | 兩階段 | full |
| A3 | 候選 | 最強 | 重 | 兩階段 | full |
| A4 | 候選 | 便宜 | 輕 | 兩階段 | full |
| A5 | 候選 | 便宜 | 重 | 兩階段 | full |
| A6 | 候選 | 最強 | 輕 | **一次呼叫** | full |

**A6 固定在「最強 + 輕」，不是「A2–A5 勝出配置」**：若勝出的是便宜模型或重 schema，A1 vs A6 就同時
改了模型、schema 與 harness，無法歸因。固定後三個比較各只打開一個變因：

| 比較 | 唯一差異 | 回答的問題 |
|---|---|---|
| A1 vs A6 | harness bundle（minimal ↔ full） | §3.1 那句 Anthropic 引文的問題：harness 是否承重 |
| A2–A5 內部 | 模型 × schema（架構固定兩階段） | 容量與 schema 重量的交互作用 |
| A2 vs A6 | 架構（兩階段 ↔ 一次呼叫） | 拆解是否值得 |

**A1 vs A6 的差異不得描述成「只差 typed Work Model」** —— 差的是整個 minimal/full harness bundle
（typed Work Model、context policy、verifier 一起換）。勝出配置下的一次／兩階段複驗移到
shortlist 或 shipping model gate。

快篩規模＝**48 個 case-arm trial observations**（6 × 8 × 1）；對應**生成器模型呼叫 80 次**
（單階段 A1、A6：2 × 8 = 16；兩階段 A2–A5：4 × 8 × 2 = 64），**LLM grader 呼叫另計**。

### 3.2 C-02｜exit gate 有逃生門，使停損條件失效

原 gate：「相較 baseline，在 Task 邊界**或**錯誤可診斷性至少一項實質更好」。
這代表候選架構在 Task 品質沒有改善時，仍可憑「比較好 debug」通過 —— 正好抵銷路線圖 §21
「Task Discovery 不優於簡單 baseline 就停」的效力。

**修訂**：

> 無 critical regression，**且 Task 邊界品質必須有預先定義的實質改善**；
> **若只是持平，選較簡單的 baseline／較少呼叫的架構**。可診斷性不得單獨替較複雜的架構取得通行證。

「不得退步」這個較弱的寫法仍會讓「品質相同、成本與複雜度更高」的兩階段架構過關，因此不採用。
判準必須在跑實驗**之前**寫定：哪些是 deterministic check、哪些是人工 rubric、
「實質改善」的具體門檻是什麼。

### 3.3 C-03｜評測規模與 trial 數低於大廠建議一個量級

Anthropic《Demystifying evals for AI agents》(2026-01-09)：

- **"20-50 simple tasks drawn from real failures is a great start."**
- 變異用 **pass@k / pass^k**；面向使用者、要求一致性者用 **pass^k**。
- LLM judge 要**對齊人類專家**、**每個維度各自一個 judge**、給 **"Unknown" 出口**。

Anthropic《Adding Error Bars to Evals》(arXiv 2411.00640)：報 SEM、用 paired difference、
題目非獨立時要 clustered SE（實測可達 naive 的 3 倍）。

**修訂**：分三階段，**不是每個 configuration 都跑 pass³**：

| 階段 | 規模 | 用途 |
|---|---|---|
| 1. 快速篩選 | 8 cases × 6 configurations × **1 trial** | **只淘汰明顯錯誤設計**，不得宣稱任何架構勝出 |
| 2. 候選縮小 | shortlist 後才擴至 **20–30 cases** | 形成可討論的品質判斷 |
| 3. Gate | 僅 shortlisted 架構的 **critical subset 跑 pass³** | 決定是否進 R2 |

**R1 不做正式 power analysis** —— 該規模下太重。
同一 session 或同一故事家族衍生的案例共用 `case_family_id`，統計時整組算一個單位；
48 個 trial observations 不是 48 個獨立樣本（生成器呼叫 80 次更不是）。

### 3.4 C-04｜自評即自誇，且原設計把品質檢查排到 R7

Anthropic 2026-03 實測：

> "agents tend to respond by confidently praising the work—**even when, to a human observer,
> the quality is obviously mediocre**"

其解法是分離產生器與評審者、把評審者調成 skeptical、每條標準給硬門檻，且校準需數輪。

**修訂**：拆成三層，共用判準但不共用 prompt 與輸出目的：

1. **Job Analysis Quality Rubric**（單一權威判準：Task 邊界、支持度、禁止錯誤、完成條件）；
2. **R1 Eval Grader**（開發期、盲測、可回 Unknown、不看產生器 rationale）；
3. **R7 Product Challenger**（執行期、讀 Evidence／Work Model／JD、不讀產生器自我辯護、
   只輸出 blocker／疑點／追問，不得宣布完成、不得改文件）。

注意：Anthropic 觀察到的是**執行期**行為，因此 R7 必須繼承同樣的懷疑工程（乾淨 context、明確 rubric、
硬門檻），否則它在生產環境就是一台自誇機器。

### 3.5 C-05／C-06｜Event Sourcing 的邊界與重播能力

**複審方原主張「應加入可重建的 append-only log」，經對方引 Fowler 反駁後撤回。** Fowler 原文：

> "The fundamental idea of Event Sourcing is that of ensuring **every change to the state of an application
> is captured in an event object**, and that these event objects are themselves **stored in the sequence
> they were applied for the same lifetime as the application state itself**."

要求「journal 足以完整重建 current state」即等同此定義，只是把 replay 藏在測試裡。
Fowler 另指出 ES 系統本來就常同時保存 current state，因此「我們有 Current State」不能反證「不是 ES」。

同時，原架構紅隊 §16 把「Event Sourcing」列為**無限定詞的禁止項**，而路線圖 §10.5 寫的是
「避免**過早**建立」，兩份權威文件口徑不一致，會讓日後的 journal 設計被誤判為違規。

**修訂（最終邊界）**：

```text
Current Work Model / Current JD
  = 唯一現況真相；reload 直接讀取，不 replay

Consultation Journal
  = append-only：回合、員工決策（accept/edit/reject/defer）、直接編輯
  = 與現況修改同一 transaction 寫入
  = 不要求足以重建 Current State

Eval Capture（runtime 之外）
  = prompt／context／model 的比較重播
  = 不參與 production reload
```

Eval Capture 保存三層，缺任一層都會失去一種比較能力：

| 層 | 內容 | 少了它就測不了 |
|---|---|---|
| Source/state snapshot | 當時的 source 與 state | 新的 Context Builder |
| Context packet + operation input | 實際送進模型的輸入 | 固定輸入下比 prompt／schema／model |
| Trial evidence | request、response、resolved model／endpoint、prompt/schema 版本、cost、latency | 任何事後歸因 |

三層由**單一 Trial Manifest** 統一保存版本來源，各層以 reference 關聯，避免三份副本互相打架：

```text
Trial Manifest（一次 trial 一份，寫入後不可變）
├─ case_id / case_family_id / source_type / source_session_ref?
├─ code_version / operation_name+version
├─ context_builder_version / prompt_version / schema_version
├─ requested_model_slug
├─ resolved_model / resolved_provider+endpoint   ← 必須取自「回應」，不得由請求推斷
├─ provider_config
└─ references → { source_state_snapshot, context_packet+operation_input, request/response+grading }
```

### 3.6 C-07｜Structured Output 的保證在 OpenRouter 下不可攜

OpenRouter 官方文件（複審雙方均已核實）：

> "Support is determined **per endpoint, not just per model**."
> "**Enforcement varies by provider**: some guarantee schema-conforming output, while others
> **translate your schema into their own structured-output format or treat it as a strong hint,
> so exact compliance is not guaranteed on every endpoint.**"
> "Strict modes may also **restrict which JSON Schema features you can use**."

在 ADR 0035 的 OpenRouter-first 前提下，這代表**沒有任何 provider 端 schema 保證是可攜的，
包括 key ordering**。因此 portable subset + deterministic verifier 不是設計品味，是被逼出來的必要條件。

**責任分工**：

| Schema 負責 | Deterministic verifier 負責 |
|---|---|
| object／array／基本型別 | quote 非空與最小有效長度 |
| required | 至少一個 source anchor |
| nullable union（模擬 optional） | 陣列語意去重 |
| enum | 數值範圍（confidence 等） |
| `additionalProperties: false` | source span 真實存在 |
| 基本巢狀結構 | ID／跨欄位引用合法、correction target 存在 |
| | Task 不得因 schema 必填被迫產生 |
| | actor／time／ownership 等語意規則 |

**執行要求**：固定 exact model slug 與 endpoint、`require_parameters: true`、禁 fallback、
R1 live preflight 實際送 portable schema、local verifier 永遠存在。

**key ordering**：OpenAI direct 與 Azure OpenAI 皆有「輸出依 schema key 順序」的保證，可交叉引用；
但 OpenRouter 跨 provider 不繼承，且 R1 **不把欄位順序當成提升推理品質的方法**
（可見 rationale ≠ 內部推理、可能先合理化錯誤結論、增加 token 與 schema 負擔）。
「先推理後格式化」改以下列順序處理：優先用具原生 reasoning 能力的模型 → 減輕 schema →
避免 forced function calling → 前三者無效時才拆兩次呼叫。

### 3.7 C-08｜K/S/A 是自述資料裡最會膨脹的一格

Morgeson, Delaney-Klinger, Mayfield, Ferrara & Campion (2004), *Journal of Applied Psychology*, 89(4), 674–686
的田野實驗發現：在職者對 **ability 陳述的評分膨脹顯著高於 task 陳述**。補充樣本為 36 位回覆主管
（發出 55 份）與 12 位受訓職務分析師（碩／博士層級心理學家），合併 N=48。

正文採限定寫法，不得泛化：

> 在該研究的 clerical supervisor 與 trained job analyst 補充樣本中，未重現 job incumbent 的一致
> ability inflation 模式。

最接近的大廠先例亦支持謹慎：Anthropic Interviewer（1,250 人）自承自述 65% augmentation 對觀測 47%，
且該研究未與人類訪談員直接對照。

**修訂**：K/S/A 與 Indicator 數值門檻一律帶支持度：

| 支持度 | 定義 | 可否進正式 JD |
|---|---|---|
| `behavior_grounded` | 有具體 Task／故事／行為證據 | 可 |
| `employee_confirmed` | 員工明確確認這是**工作要求**，不只是自己會 | 可，但須保留標記 |
| `reference_candidate` | 只來自公版 | 只能作候選 |
| `unsupported` | 模型推測 | 不可 |

Attitude 一併適用（最缺行為證據、最易膨脹）。「員工按接受」不得被偽裝成「已有行為證據」。
系統必須把「員工會什麼」與「這份工作要求什麼」分開；「需要 Java」「主動積極」「每月 99%」都要追問
其 Task、行為、產出或實際判準。

### 3.8 C-09｜公版格式的法律語意

「職能發展及應用推動要點」：

> 職能基準：「為完成**特定職業或職類**工作任務，所應具備之能力組合……」（第 2 點）

第 7 點以「行業」「職業」或「職類」為發展範疇，屬產業／職類層級；第 9 點由中央目的事業主管機關、
受委託機構或民間團體發展。國際對應做法 DACUM 亦為 5–12 位專家工作者 + 引導師的 2 天工作坊。

本產品是**一位員工 + AI** 產出企業內個別職務說明書。因此公版作為 R6 challenger 正確，但匯出必須標示：

> 本文件為客製職務說明書，採 iCAP 職能基準欄位版型，不代表勞動部認證或官方職能基準。

且**不得自行產生看起來像官方認證的職能基準代碼**。

---

## 4. 複審過程中被駁回或撤回的主張

誠實記錄，避免日後重複同一爭論。

| 主張 | 提出方 | 結果 | 原因 |
|---|---|---|---|
| 「路線圖拒絕任何 append-only log」 | 複審方 | **撤回** | §10.5 原文是「避免**過早**建立 event sourcing」，非拒絕 log |
| 「journal 應足以完整重建 current state（測試驗證）」 | 複審方 | **撤回** | 等同 Fowler 的 ES 定義，只是把 replay 藏在測試裡 |
| 「OpenAI 官方頁沒有 key ordering 敘述」 | 複審方 | **撤回** | 擷取工具在該頁三次只取到部分 DOM；「工具沒抓到」≠「文件沒寫」 |
| 「Azure 的 100 properties／5 層是通用上限」 | 複審方 | **撤回** | 為 Azure OpenAI 限制；OpenAI direct 為 5000／10，兩服務不同 |
| 「structured outputs 不支援 parallel function calls」列入 R1 契約 | 複審方 | **移除** | 僅適用於 function calling；R1 走 `response_format`／`json_schema`、無 tools |
| 「三個真人 session 都已驗證」 | 複審方 | **修正** | 僅驗證三個 ID 出現在 repo 文件與其中兩個的回合數；語料存否未驗 |
| 「Morgeson 研究需另設核對人欄位」 | 複審方 | **移除** | git 歷史已記錄加入者，不需另造欄位 |
| 「R7 quality.challenge 應整個搬到 R1」 | 複審方 | **修正** | 兩者是不同元件；正確做法是 R1 另增獨立 grader |
| 「便宜模型優先可驗證架構」 | 原 R1 研究 | **否決** | 見 C-01 |
| 「Event Sourcing 全面禁止」 | 原架構紅隊 §16 | **否決** | 見 C-05 |

---

## 5. 歷史語料記錄（盤點已由 owner 裁定取消）

| Session ID | 出處 | 已知 | 未知 |
|---|---|---|---|
| `eb2af457` | [ADR 0028](../adr/0028-interview-flow-shared-ui-curation.md) | 2026-07-09 真人實測、25 回合深聊 | 逐字稿是否仍在 DB；受訪者是否描述自身真實職務 |
| `6f807f1e` | [ADR 0031](../adr/0031-occupation-suggest-card-refset-source.md) | 新手 persona 真人手測、22 回合鬼打牆 | 同上；**明確為 persona 扮演** |
| `53dcde00` | [task-carrier-routing 研究](2026-07-14-task-carrier-routing-research.md) | 被稱為「一手事故資料／一手逐字稿」 | 是否為獨立第三筆真人 session；逐字稿存否 |

> **【2026-07-26 owner 裁定】沒有真人員工訪談資料，不進行 DB 語料盤點。**
> 上表僅作歷史記錄。**R1 僅使用非真實員工資料**：來源可為 `constructed_edge`，
> 或在舊 session 逐字稿恰好可用時為 `human_manual_test`。
> 「沒有真實員工訪談」**不等於**「全部案例都是人工構造」，兩者不得混寫。
>
> **直接後果（必須寫在成品的誠實邊界裡）**：C-08（K/S/A 自述膨脹）在 R1–R7 **無法用真實在職者資料驗證**，
> 只能靠 rubric 與 deterministic verifier 擋住。真正的驗證留到 R9 真實試用。
> **不得因為 R1 通過就宣稱膨脹問題已解決。**

案例 metadata 規則：

```text
source_type: constructed_edge | human_manual_test | real_employee_interview
case_family_id: 必填（統計聚類單位）
source_session_ref: 選填
```

`source_type` 依**案例實際來源**標記，不是依信心程度：

| 值 | 適用 |
|---|---|
| `constructed_edge` | 人工構造的案例。**構造案例一律標此值**，不得標成 `human_manual_test` |
| `human_manual_test` | 確實有人操作產生，但是否描述真實工作未知（舊 session 逐字稿屬此類） |
| `real_employee_interview` | 能證明受訪者在描述本人真實工作。**目前無此類資料** |

**不設預設值，依實際來源分類。** 由舊 session 衍生時：**原樣使用人類操作逐字稿＝`human_manual_test`；
改寫或合成成新案例＝`constructed_edge`**，兩者皆可另留 `source_session_ref`。
`human_manual_test` 不得在缺乏證據時升級為 `real_employee_interview`。
persona 扮演產生的膨脹模式與真實在職者不同，對 C-08 的驗證尤其不能混用。

既有案例可重用範圍（邊界從嚴）：

- **可重用**：`apps/api/evals/interview_vnext/cases/` 的 12 個 TI 案例（TI-01～TI-12）的 `transcript.jsonl`、
  案例意圖、語意陷阱設計、`adjudication.md` 裁決理由 —— 且僅作為
  **「待依新 Task rubric 重新審查的候選依據」**，不是現成答案。
- **不可重用**：舊 `gold.json`（`turn_eval_gold.v2`，綁舊 Evidence 契約）、舊 schema、舊 operation 名稱、
  Evidence 模型、loader、prompt、Context Builder、grader 實作與名稱、`applicable_graders` 名單、suite hash。
- **所有 expected output 必須依新 Task rubric 重新裁決。**
- `apps/api/evals/golden/JD-golden-001/` **不得直接當作新 gold**：其
  [`reference.md`](../../apps/api/evals/golden/JD-golden-001/reference.md) 自述為 agent 依樣張起草、
  以權威來源自審，**未經正式 SME 審查**，因此只能作 **candidate exemplar**，重新審查後才可作品質尺。
- 12 個 TI 案例的 metadata 為 `constructed_edge`／`pilot_only: true`，因此
  Anthropic 所說的「drawn from real failures」**完全不滿足**，只是語意家族覆蓋。
- 缺口需補：一次性工作、一故事多 Task、多故事同 Task。

---

## 6. 未決事項

1. 兩階段（`turn.understand` → `work.reconcile + decide`）是否優於一次呼叫 —— 降級為待實驗假說，
   由 C-01 的 ablation 裁決；**持平時選一次呼叫**。
2. R1 最終使用的 exact model slug 與 endpoint（實驗前重新取得 catalog snapshot）。
3. 「Task 邊界品質實質改善」的具體門檻 —— 必須在跑實驗**之前**寫定（C-02）。

> 語料盤點已由 owner 於 2026-07-26 裁定不做（無真人資料），不再列為未決事項。

---

## 7. Provider 附錄（帶日期，非架構常數）

> **警告**：以下為特定服務在特定日期的限制，**不得寫成 provider-neutral 契約常數**。
> JSON Schema 的容量與支援關鍵字由 resolved endpoint 決定；R1 核心規格不固定全域 property／nesting 上限，
> 實驗執行時記錄 exact endpoint 的當期限制並以 **live preflight 驗證為準**（文件是預期值，preflight 是實測）。

| 服務 | 查閱日期 | object properties | 巢狀深度 | 備註 |
|---|---|---|---|---|
| OpenAI direct | 2026-07-26 | 5000 | 10 | 有 key ordering 保證 |
| Azure OpenAI | 2026-07-26（文件 `ms.date` 2026-05-13） | 100 | 5 | 有 key ordering 保證；另列一批不支援的 type-specific keyword |
| OpenRouter | 2026-07-26 | 依 resolved endpoint | 依 resolved endpoint | 不保證跨 provider 一致；需 `require_parameters: true` |

---

## 8. 權威來源

### 大廠工程文件

- [OpenAI — A practical guide to building agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/)
- [OpenAI — Model selection](https://developers.openai.com/api/docs/guides/model-selection)
- [OpenAI — Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Anthropic — Harness design for long-running application development（2026-03-24）](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Anthropic — Scaling Managed Agents: Decoupling the brain from the hands（2026-04-08）](https://www.anthropic.com/engineering/managed-agents)
- [Anthropic — Demystifying evals for AI agents（2026-01-09）](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Anthropic — Effective harnesses for long-running agents（2025-11-26）](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Create strong empirical evaluations](https://docs.claude.com/en/docs/test-and-evaluate/develop-tests)
- [Anthropic — Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)
- [Microsoft Learn — Structured outputs with Azure OpenAI](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs)
- [OpenRouter — Structured Outputs](https://openrouter.ai/docs/features/structured-outputs)
- [Cognition — Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents)

### 同行審查與方法學

- [Anthropic — Adding Error Bars to Evals（arXiv 2411.00640）](https://arxiv.org/abs/2411.00640)
- [Morgeson, Delaney-Klinger, Mayfield, Ferrara & Campion (2004), *JAP* 89(4), 674–686](https://www.ncbi.nlm.nih.gov/pubmed/15327353)
- [Morgeson & Campion — A Framework of Potential Sources of Inaccuracy in Job Analysis](http://www.morgeson.com/downloads/morgeson_campion_2012.pdf)
- [Martin Fowler — Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
- [DACUM Handbook / Occupational Analysis（UNEVOC）](https://unevoc.unesco.org/e-forum/DACUM-Brochure.pdf)

### 法規與官方標準

- [勞動部 — 職能發展及應用推動要點](https://laws.mol.gov.tw/FLAW/PrintFLAWDAT0201.aspx?id=FL070293)
- [iCAP 職能發展應用平台 — 指引手冊](https://icap.wda.gov.tw/ap/knowledge_application.php)

### 證據等級較低（僅作輔證）

- [Capacity, Not Format: Rethinking Structured Reasoning Failures（arXiv 2606.09410；單一作者 preprint，
  測試集偏數學，未涵蓋開放式生成）](https://arxiv.org/abs/2606.09410)
