# 工作理解 Memory：單一訪談的流程、資料與引用

> 2026-09-05 · `LLM-Q017` · **G4 流程／效果已獲 Owner 暫時同意；實現方式可等價調整，不是施工計畫**。
> 已確認：每份 JD 一個持續訪談 thread；只整理該文件的 Memory，保留即時修補。
> Owner 確認導覽／工作理解承接工作性質，訪談詳記／候選保留案例素材，原始對話可再回查；這些名稱作 Working 用語，不是正式 schema。資料流沿用已准 A／B／C 與既有 OpenAI 研究；技術接法依 §0.1 細化，寫入協調仍待討論。

## 0. 用途與閱讀順序

本元件讓顧問 LLM 在長訪談後仍能找回員工工作、案例細節、條件差異、更正與未明資訊，形成可持續修訂的工作理解。**Memory 提供知識；是否及如何編輯 JD 由顧問 LLM 判斷，不由 Memory 自動操控。** 原始案例不必逐件變成 JD Task，工作理解也不預先綁定 Duty／Task／OPKS 結構。

先讀本文確認「資料是什麼、誰產生、如何接力與找回」；只有需要證據才沿引用深入：

- 官方全貌：[OpenAI 系統圖 §5.6–5.7](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[artifact 詳表 §4](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md)。
- 引用 producer／consumer：[摘要路由 source review §2–4](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)。
- 兩階段、保存與直接交接：[B 流程 §3.4–3.5](2026-09-05-memory-background-cycle-flow-review.md)。
- 本文通過後才回到[框架組合提案](2026-09-05-memory-framework-end-to-end-composition-proposal.md)；不重選已研究的通用 Memory 原理。

快速檢查是否漏掉已討論細節，讀本文 **§7 覆蓋索引**；五個 artifact／單一導覽／按需停止的最新審核見 **§8**。不是只讀本文就代替所有固定 source。接點沿革在[抽取產物 §8](2026-09-05-memory-extraction-artifact-framework-handoff-review.md#8-引用接力的框架覆蓋核對)，底層查證與②研究建議只放[原生 backend 審閱](2026-09-05-memory-artifact-native-backend-design-review.md)，不在本文複製框架選型表。

**權限／狀態：**[current register](../current-decisions.md)仍是決策入口。本文整合閱讀，不改 production、Accepted ADR 或原始官方證據；新提案未經 Owner 同意不當成已准規格。舊產品長稿不作本輪輸入。

### 0.1 Owner 澄清：流程效果必須達成，實現方式不鎖死

**[2026-09-05 Owner 決策，非新增官方事實]** 本輪兩次補充確認：優先學習已研究的 OpenAI 流程、分工及其理由；同時依框架自己的生態、資料流與公開底層元件／API 實現。Owner 沒有要求照抄檔名、資料格式或函式，亦非核准所有尚未完成的技術契約。

- **必須達成：**已討論的 A／B／C、抽取與保存、整併與更新導覽、搜尋及逐層深讀。引用、關鍵詞等不是裝飾欄位：必須實際支援找到相關理解、沿引用讀訪談詳記，必要時回查原始問答；不能因換表示而省略用途或遺失必要細節。
- **可以調整：**引用以 path、record ID、metadata 或其他可定位表示保存，關鍵詞如何保存／供搜尋使用，以及採哪個官方 reader／backend 接點；依功能、效果、成本與維護性研究選擇，不要求 Owner 逐一指定格式或 SDK 參數。這些例子不是預先選定 schema。
- **研究順序：**先回讀既有 OpenAI 證據理解用途，再追框架輸入、處理、保存及回傳。高階元件不完全吻合時，先查已研究的底層元件、公開 API 與擴充接點；不能只按名稱配對，也不能未查就另造整套機制。聲稱替代接法更好，仍需提出依據與取捨，不把本案映射稱為各家共同底層。
- **何時再討論：**效果等價、範圍內的接法可繼續細化並記錄理由；若會改動已同意流程／目的、降低效果、明顯增加成本或複雜度，或涉及尚未裁決的權責／協調問題，先提出討論。保留可翻案性，但不得擅自翻案；production／實作授權不因此擴張。

**既有研究指路：**用途與引用鏈見[摘要路由研究 §2–4](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)；框架底層見[原文 reader §6](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)、[StoreBackend 接法 §1–4](2026-09-05-memory-artifact-native-backend-design-review.md)。本次只記 Owner 邊界澄清，不重做官方研究；後續以能否完整走通資料接力審查，不以名稱／表示完全一致作通過條件。

## 1. 先校正舊圖與單 thread 的意思

**[Owner 本輪澄清]** 一份 JD 的同一個訪談 thread 持續累積內容。背景從這份訪談抽取，再對照這份文件既有 Memory 整併；**不做跨員工、跨 JD、跨 conversation thread 整併**。同一訪談前後談到相似工作，仍需去重、補充及修訂，不能因只有一個 thread 就省掉 consolidation。

我們稱為「**單一訪談抽取 → 同一份工作理解持續整併**」，不使用容易暗示多 thread 的「跨 rollout 整併」。一次背景整理可以處理該訪談的一段已保存範圍；既有 Q014 已准方向是新範圍加必要舊脈絡，不是每輪重讀整個無限成長 thread。精確切段、觸發與重跑方式仍待定，不從名稱偷決定。

**[官方與 mapping 邊界]** Codex 的 rollout 是其具體執行紀錄單位；不能將 Caliburn 每則訊息、每次模型 API request 或每個抽取片段都叫成新的 Codex rollout。背景工作的技術執行紀錄也不等於另開員工聊天室。參考[既有原文／Session 邊界](2026-09-05-openai-conversation-context-and-memory-system-map.md)。

舊圖的「C 未來讀取」放回已准 **A 的按需讀取**；本文 **C 專指即時修補**，避免同一字母兩種意思。A 的即時 Context 含有界對話／compaction 延續、小型導覽及既定少量相關召回，按需再深讀；不是只讀最近對話。

## 2. 命名與資料責任（Working 用語，尚非檔名／資料表）

| 本案建議名稱 | 研究中的對應 | 保存什麼、給誰用 | 不代表什麼 |
|---|---|---|---|
| **訪談原始紀錄** | Conversation／raw rollout 的來源責任 | 實際員工↔AI 問答；需要時含相關 Tool call/result、執行脈絡。供抽取與精確回查 | 不把 compaction 文字當原始紀錄；也不把所有技術事件無條件送給抽取模型 |
| **對話延續摘要** | Compaction continuation | 幫主顧問在 Context 變長後接續對話 | 不是工作理解，不是下列訪談詳記，不取代原始紀錄 |
| **訪談詳記** | `rollout_summary` | 本次整理範圍談了什麼、案例／條件／更正／未明資訊及結論脈絡；供 A／B 深讀 | 是模型整理的詳細摘要，不是逐字稿，也不保證無損 |
| **工作資訊候選** | `raw_memory` | 從同份訪談辨識出值得拿去與既有理解比對的資訊；交給整併模型 | `raw` 不是原始對話；候選不等於已成立的 current Memory |
| **整理短標籤** | `rollout_slug` | 抽取模型給摘要的可讀短名稱；Runtime 可用於命名／顯示 | 不是第三份知識正文，不是唯一身份，也不是導覽本身；是否獨立成欄位仍未定 |
| **訪談整理結果** | Phase 1 產物的集合稱呼 | 上面「詳記＋候選」、若採用的短標籤，及 Runtime 附上的來源定位 | 是結果封裝，不是再建一份同內容知識或第三個 Agent |
| **工作理解** | `MEMORY.md` 的 durable Memory 責任 | 按主題整理、可搜尋、可修訂的工作知識；保留重要細節、適用條件及相關詳記引用 | 不是固定 JD 任務清單，不是每案例各建一筆，也不是模型私有推理過程 |
| **工作理解導覽** | `memory_summary.md` 的 routing 責任 | 少量主題、用途與能搜到正文的關鍵詞；幫主顧問找路 | 不再複製整份工作理解，不獨立判定事實 |

**五個概念均已納入設計；不等於五個功能均已實作驗證。** `rollout_slug` 在 Codex 是抽取模型產生的短標籤，Runtime 用於組成可讀檔名；本案保留命名用途，**還未決定需要獨立欄位**。不能因沒有一張 slug 資料表就判定漏功能，也不能讓模型靠 slug 自創唯一身份。Codex 資料分工與實際 header 見 [storage source](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/storage.rs)。

**「工作理解導覽」就是 `memory_summary.md` 的對應，不是它之外再加一份導航 Memory。** 可調整的是表示，不是多加一層：B 隨正文維護這份小型入口，A 讀取／注入其內容；不是每次模型呼叫再生成一次。它與 Compaction 的對話延續摘要、B 補查用的詳記目錄都不同；後者是查找既存產物的能力，不是另一份語意導覽。Codex 導覽也可含少量 profile／通用提示；本案學其高密度入口與可搜尋線索責任，不宣稱逐欄照抄。詳見[系統圖 §5.8](2026-09-05-openai-conversation-context-and-memory-system-map.md#58-第四個細部邊界三份-read-artifact-各自存什麼何時停止深入)。

**[Owner 已確認]**「穩定任務」指逐漸形成、仍可修訂的工作性質／工作模式理解，**不是先建立固定 JD Task**。Owner 以「依客戶需求開發前端網站」說明：此工作性質可進導覽與工作理解，各網站案例的特殊細節由訪談詳記／工作資訊候選承接，必要時再回查原始對話。

### 2.1 同一內容在不同層的樣子

以下是 Owner 確認的概念之示例，**不是實際員工資料或固定欄位模板**：

| 層 | 網站開發例子 | 用途 |
|---|---|---|
| 工作理解導覽 | 「客製前端開發」及能搜尋到正文的線索 | 知道有這類工作、往哪裡找；不是複製整篇正文 |
| 工作理解 | 依客戶需求開發前端網站；已知的責任範圍、常見做法、條件與相關詳記引用 | 理解這份工作的性質，不把每個網站一律變成獨立 JD Task |
| 訪談詳記／工作資訊候選 | A、B 網站各自的需求、限制、處理經過及新發現；候選著重哪些資訊值得整併，詳記保留當時脈絡 | 提供整併素材及往後案例深查；兩種產物不必逐字重複 |
| 訪談原始紀錄 | 實際問答與更正 | 需要精確原句或核實整理是否正確時回讀 |

**解讀邊界：**這是內容重心，不是互斥分類。會影響整體工作理解的案例差異、例外與重要細節，也可寫入工作理解正文；正文不是只能留一句抽象結論。候選的主要讀者仍是 B 整併，A 的正常深查鏈**不必經過候選庫**，而是由正文直接連到詳記。既有 producer／consumer 依據見[摘要路由 §2–4](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)。

**能力目標而非效果證明：**所有工作及必要細節應保持可找回，模型可按需深入，不必每次全放 prompt；不把「每輪一定知道所有細節」或「保存原文就一定能找回」當成已成立的實作保證。後續接法須維持正文線索→相關詳記→原始問答的可用路徑，不因去重而刪掉案例辨識線索。

## 3. 完整接力：不只是原文丟進模型

### A. 主顧問對話與按需讀取

```text
同一訪談的新訊息保存
  → 組裝本輪 Context（固定規則、有界對話／延續、導覽、少量相關召回）
  → 主顧問判斷是否需要更多資料
      ├─ 已足夠：回答／處理本輪工作，不啟動額外 Memory 深查
      └─ 需要既有工作知識：依導覽線索搜尋工作理解正文
          ├─ 命中內容已足夠：停止深查
          └─ 仍缺當時脈絡：沿正文引用選讀相關訪談詳記
              ├─ 已足夠：停止深查
              └─ 仍需精確內容：沿來源定位讀原始問答

各步的新資料回到主顧問，由模型決定繼續／停止；符合 C 條件時才即時修補。
```

查到足夠即可停止，不必每輪走完所有層。Codex read prompt 的「1～2 份摘要」是快速 lookup 指引，不是本案硬性最多只能讀兩份；沒有命中也不等於員工沒說過。原始問答需保留 AI 問句的必要脈絡，不能把「對」「不是」等回答孤立讀取。[讀取政策與限制](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#3-讀取端每次多讀一層都有明確依據)

**搜尋與讀取分開：**一般先搜尋正文定位知識；之後是沿已提供的詳記引用／原文位置選讀，可在選中內容內繼續查找，不是再依序搜尋整個詳記庫及全部原文。`raw_memory` 不是這條 A 讀取鏈的必經站。已有明確來源引用或本輪 Context 已足夠時，不為湊齊流程重新跑每一站；日常 lookup 也不能代替最後全面檢查所需的全部有效 Memory 處理能力。

**官方邊界：**本輪重新取得的 [Sandbox Memory 官方頁](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)明示 run 開始注入導覽、相關才查正文、需要更多細節才開 rollout summaries。更深 raw rollout 的讀法及 quick-pass 指引沿用[已研究的 Codex 固定 read prompt](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#3-讀取端每次多讀一層都有明確依據)，不混稱每個 OpenAI 產品都有相同注入時機或工具 schema。

**證據歸屬：**圖中的「少量自動相關召回」來自已准 Q014／Q017 的組合方向，**不是上述 Codex read prompt 已證實每輪必跑的額外搜尋**。確切召回方法／頻率仍待 Context 接線；不把檔案搜尋或小型導覽冒稱已自動完成此步，也不由本輪取消既有決策。

### B1. 背景抽取：產生訪談詳記與工作資訊候選

| 輸入 | 責任與證據 |
|---|---|
| 抽取 instructions | 定義如何辨識有用資訊、保留細節與不確定性、不把 AI 建議當員工事實；這部分會換成職務訪談用途的 prompt |
| 選定範圍的原始問答與必要結果 | 不是只有員工單句；Codex 固定 input template 使用經篩選、render 的 rollout conversation，並非全套 JSONL 技術事件原封搬入 |
| 來源定位／執行脈絡 | Codex input 有真實 `rollout_path`、`rollout_cwd`；本案是同一訪談的可信範圍／定位，不照抄 cwd 為產品必填欄位 |
| 必要的較早對話背景 | 本案既有單一長訪談範圍消歧方向；**不是宣稱 Codex template 原生有相同 segment 機制**。需要時才能解讀本段指涉；精確窗口尚未決定 |

**[官方事實]** Codex Stage 1 是抽取指示＋rollout context＋filtered conversation，產生三個字串 `rollout_summary`／`rollout_slug`／`raw_memory`。其 system prompt 容許 summary 詳細保留脈絡及簡短 evidence，並區別使用者明述、模型推論與未採納建議。不能由此宣稱框架已自動產生每句原文的精準 message 引用。[完整 input template](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/stage_one_input.md)、[system prompt 的 output／summary 規則](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/stage_one_system.md#L221-L283)

**[本案接力]** 一份抽取結果同時含詳記及候選；Runtime 附上可回到本次原始問答的定位，保存供後續讀取。不是叫模型再用一個 Tool 重填同一份資料。沒有新的可用工作資訊時可以不新增理解，不強迫每次湊一筆。此階段不直接修改工作理解或 JD；目前工作理解主要由下一階段讀取，不為了「完整」而無條件把整份 Memory 也塞入抽取 prompt。

### B2. 背景整併：同一份工作理解持續更新

```text
本次選用的工作資訊候選＋其詳記／來源位置
  ＋同一文件現有工作理解／導覽
  ＋哪些整理輸入已處理、哪些是本次新增或更新的執行資訊
  ＋整併 instructions
    → 背景整理模型按需讀正文與相關訪談詳記
    → 去重、補充、修訂；確有獨立用途才另立主題
    → 在相關知識旁保留真實的詳記引用與查找線索
    → 配合正文變化維護小型導覽
    → 依實際寫入結果記錄完成／無需修改／未完成
```

「已處理哪些輸入」是 Runtime 的執行資料，不是模型要填的工作理解欄位。不是將每次 `raw_memory` 原樣串接成越來越長的正文；也不是每次全部重寫。Codex Phase 2 有既有 workspace、候選集合、selection／diff 與可讀 summaries；本案沿用責任，**不把其跨 thread 選取、Git baseline、lock 或檔名當成已核准實作**。[完整既有研究 §5.7](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[固定 consolidation prompt](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md)

已准邊界保留：B2 可以補查詳記，**不直接開原始訪談**；B1 才讀原始問答，A 也能按需深查。這是目前選用的 Codex 背景權限形狀，不宣稱所有 OpenAI 產品一律禁止背景讀原文。若詳記不足，不能捏造內容；是否補做抽取、如何重排，留生命週期設計討論。[B summary-only 的直接證據](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#4-背景-b-的補查不同不能把-a-原封套過去)

**保存≠延後：**B1 結果保存成功後可把手上的同份結果直接交給 B2，不必為交接再讀 DB，也不必等下一次排程。保存讓以後 A／B 仍可開詳記／重用抽取。兩階段不是固定兩次 API；B2 的工具往返可能增加 requests，存檔本身不呼叫模型。保存失敗不可發假引用；恢復策略未定。[B §3.4–3.5](2026-09-05-memory-background-cycle-flow-review.md)

### C. 主顧問當輪即時修補

當 A 已讀到某段工作理解、確認本輪資訊使它明確過時，而且後續要使用修正版，可透過 Tool 局部修改，確認實際結果再繼續。**C 不是重新執行整套 B，也不是第三個 Agent。** 不清楚／只是疑似矛盾時先與員工釐清，不是以最新一句自動蓋掉前文。

同一訪談仍會進後續 B；B 應對照當時最新理解，避免把已修補內容改回舊版。C 發生時未必已有本輪訪談詳記，**不可為了引用鏈捏造不存在的 summary**：同輪依據可先由 Runtime 定位實際對話；B 產生詳記後再依內容維護相關引用。確切定位保存／補接方式及 B/C 同時修改，仍待 Q017 接法／Q018 審閱，不先新增強制引用 schema。[C 已准邊界](../current-decisions.md)、[協調題](2026-09-05-memory-background-live-repair-coordination-research.md)

## 4. 引用怎麼建立、放哪裡、怎麼沿著找

```text
工作理解導覽 ──主題／可搜尋詞──→ 工作理解正文
工作理解某個主題 ──相關詳記引用──→ 一份或多份訪談詳記
訪談詳記 ──Runtime 來源定位──→ 同一訪談的原始問答範圍

工作資訊候選 ──Runtime 關聯──→ 同批詳記＋相同原始問答範圍
```

| 關聯 | 誰負責 | 正確界線 |
|---|---|---|
| 抽取產物來自哪段訪談 | Runtime 掌握實際輸入位置；保存時附上可讀定位 | Codex 以 thread／時間／rollout_path 等 header 定位原文；不等於已內建逐句 quote offsets |
| 哪段工作理解由哪些詳記支援 | 整併模型判斷相關性，選用 Runtime 已提供的真實地址 | 可以多對多；不是靠標題一樣就自動關聯，也不是模型發明 ID |
| 導覽如何指向正文 | 整理模型保留主題、用途與正文可搜尋詞 | 正常不必再複製每份詳記／原文引用；導覽不是另一次完整知識保存 |
| 真的讀到什麼 | 工具依定位讀取並回傳內容，模型再判斷是否足夠 | 有引用不等於語意必然正確；找不到來源不能假裝已讀到 |

**直接回答：**Extraction 產物可以帶原文的短片段，但可回查原始對話的基本連結主要由 Runtime 補上的來源資訊承接。`MEMORY.md` 的相關段落保留 `rollout_summary_files`；不是要求把 `raw_memory` 全部複製進正文，也不是每段必須串「正文→候選→詳記→原文」四跳。`raw_memory` 主要服務整併；未來讀取通常是正文直接到詳記。`memory_summary.md` 主要指路，不必另建全套來源鏈。[storage producer](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/storage.rs#L44-L135)、[正文 task-local refs／guide 規則與讀取證據](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#2-先看寫入端相關摘要不是等查詢時才臨時配對)

**保存的邏輯位置：**原始問答仍在 canonical conversation；詳記／候選是持久可讀的抽取產物，來源定位跟著該產物；工作理解是 current Memory 正文，詳記引用放在相關知識旁；小型導覽另外維護。**這是責任位置，不代表五張新表或五份對話副本。** Record、Markdown、同一 Store 的表示及 reader 形式留下一層選；不因命名就決定多存一份。

## 5. 套到職務訪談時，哪些不只是換名字

- **已確認的範圍差異：**單一訪談、同一文件 Memory；不照抄 Codex 跨 chats 的抽取資格與整併 scope。
- **用途／prompt 差異：**Codex 主要保存可重用的工作經驗／使用者偏好；這裡保存員工工作知識與必要細節。「一次性案例沒有通用新知」不等於它的細節可以永久丟失。
- **細節保留：**原始訪談耐久保留，重要案例能沿查找線索及來源定位找回；不能只因有原文存著就聲稱一定找得到。摘要抽取、正文整併都可能漏訊息；既有完整性要求保留，不能由此文宣稱效果已驗證。
- **不是每個案例都建任務：**A、B 兩個網站案例可支持同一「按需求開發前端」理解，差異留正文或詳記；後續 C 案例帶來例外時再修訂適用條件。LLM 最後如何萃取 JD 是下一個功能，不在此增加案例／模式專用表。
- **保留策略未照抄：**OpenAI 公開實作有輸入截斷、保留集合及 prune；本案沒有因此同意刪除員工歷史或切斷必要詳記引用。物理儲存與保留政策必須一起審，不能稱只換 prompt 就保證一切等價。

以上是必要 mapping／取捨，不冒充所有大廠的統一實作。具體 Codex source 與 Sandbox SDK 是不同公開表面，不能拼成同一產品的精確內部規格。

## 6. 本輪收斂與下一步

**2026-09-06 接續：**Context 候選接法與來源集中於 [Compaction 審閱 §9](2026-09-05-conversation-compaction-framework-gap-review.md#9-非破壞性延續兩條既有候選的接線取捨)。Owner 提醒「函式只回摘要／近期訊息，不代表底層沒有保存原對話」；該節已按 caller→state→reducer→Saver 分清既有對話保存、延續摘要與額外歷史檔。推薦順序尚待審閱，未選定引擎／未測試，不另增加 Memory 層。

**最新查證接續見同稿 §9.7／[Context 接線子稿 §5](2026-09-06-context-window-retention-and-budget-wiring-review.md#5-owner-澄清可組合元件以及先摘要再給模型)：**Owner 優先可組合的公開元件；先說明摘要時點與 Agent／Tool／Skill／Memory 如何接合，不以套件名稱二選一。`CC-F13` 多工具切點、完整 request 預算及 §9.6 保存／retry 證據仍有效，尚未選型；「先摘要再給模型」不等於切段及保存已驗證。不翻案 A/B/C 或原文 owner，未測試不宣稱功能通過。

- **已有效：**單 thread／同文件隔離、A 按需讀取、B 抽取與整併、C 即時修補、引用回查目的；不要求跨 rollout 功能。
- **Owner 本輪確認：**§2.1 的內容分層與工作理解語意成為可翻案的 Working Decision；不再重問是否指固定 JD Task，不把此次同意擴張成 schema／所有未決接法已准。
- **目前接法與下一個 gate：**[原生 backend 審閱](2026-09-05-memory-artifact-native-backend-design-review.md)推薦②；[原文回查契約 §7](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#7-原文回查契約來源定位與有界讀取)已形成「Runtime 選定 checkpoint＋實際訊息範圍、模型沿引用有界續讀、讀取失敗不冒充無資料」設計基線。依 §0.1 可繼續細化等價接法，不要求 Owner 再選唯一格式；①／③仍保留替代條件。**接續只收斂 Context／Compaction 如何保留這條原文回查路徑。**
- **仍需收斂／驗證：**原文讀取契約尚未實測；背景何時取得已封口的來源、C 依據補接、保存失敗與 B/C 協調仍未決；不能憑流程圖直接施工。
- **研究停止線：**流程及引用已有本文所列研究，不再重做 OpenAI 全套。下一輪只查所選框架能否保存／傳回這些資料；有明確證據缺口才補原廠來源。
- **本文變更範圍：**只更新研究與路由；不改程式、不跑付費模型、不建立新 schema、Agent、背景工作、ADR 或 implementation plan。

### 本輪來源核對紀錄

先回讀 Q017／B／引用路由及 OpenAI 系統圖、artifact 相關章節；未重做跨家研究。僅補核對 Stage 1 input／system prompt 的輸入與引用責任，並重新取得 [Codex Memory 公開說明](https://learn.chatgpt.com/docs/customization/memories)及 [Sandbox Memory 公開頁](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)。

另發現舊 artifact 稿「公開頁沒有 `phase_two_selection.json`／沒有逐檔 layout」與本輪取得的 **Sandbox 頁面**不一致：現頁列出該檔與 `<rollout-id>` 路徑。已定向校正原研究；**Codex 固定快照的 DB selection 機制不因此改變**，也不替本案新增此檔。頁面何時改變未考證，不推測原因。

## 7. OpenAI 流程細節覆蓋索引

**2026-09-05 接續審核：**Owner 同意引用校正，要求檢查已討論的 OpenAI 細節是否寫到。此次回讀既有系統圖全文、B 流程、引用路由、Q018、框架原文／產物接力，定向核對 artifact §1.1 及已留存 Codex storage／consolidation／read-path source；**未重新宣稱查驗最新 HEAD，未執行模型或框架測試**。下表的「已記錄」不是實作完成或效果已保證。

| 已討論的細節 | 記錄／證據入口 | 本案尚待決定的接線，不是漏研究 |
|---|---|---|
| Conversation、SDK Session、sandbox session、raw rollout 不同責任；訊息／工具事件與持久性 | [系統圖 §3、§5.4–5.5](2026-09-05-openai-conversation-context-and-memory-system-map.md) | 原文 reader、選段與 retention；不依名詞另存副本 |
| Compaction 延續 Context，不等於逐字來源、詳記或 Memory | [系統圖 §4、§7](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[框架三種替換 §1–3](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md) | 選定摘要引擎、配置與原始問答可回查路徑 |
| 抽取輸入不只是最新員工一句：instructions、filtered conversation、可信來源／執行脈絡 | 本文 B1；[Stage 1 input](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/stage_one_input.md) | 單一長訪談的具體範圍與必要舊脈絡 |
| `rollout_summary`、`raw_memory`、`rollout_slug` 的內容、用途、產生者不同 | [系統圖 §5.6](2026-09-05-openai-conversation-context-and-memory-system-map.md)、本文 §2 | 輸出 schema；slug 是否需要獨立欄位 |
| 保存摘要供未來 A／B 深讀，候選供整併重用；可直接交接、不額外叫存檔模型 | [B §3.4–3.5](2026-09-05-memory-background-cycle-flow-review.md) | 產物表示／reader；保存失敗如何續作 |
| 整併的輸入包含候選、既有 Memory、選取／差異資訊及 instructions；可 no-op | [系統圖 §5.7](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[B §3.2](2026-09-05-memory-background-cycle-flow-review.md) | 本案增量範圍、已處理狀態與觸發方式 |
| B 整理途中能補查詳記，不直接讀 raw；不把條件不同一律當重複 | [引用路由 §4](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#4-背景-b-的補查不同不能把-a-原封套過去) | 摘要 inventory／read 接點；不足時的恢復政策 |
| Runtime 先給真實位置；模型在相關知識旁選擇詳記引用及可搜尋詞 | [引用路由 §2](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)、本文 §4 | 引用的物理表示與 reader；不是逐句 quote／ID 填寫表 |
| 正文整理後維護小型導覽；保留能搜到的詞，不抹掉案例辨識線索 | [系統圖 §5.7–5.8](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[引用路由 §2.3](2026-09-05-memory-summary-routing-and-deep-read-source-review.md) | guide 載入時機；框架快取不等於自動刷新 |
| A：導覽→查正文→相關詳記→必要時原文；足夠就停，不固定讀遍所有層 | [引用路由 §3](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#3-讀取端每次多讀一層都有明確依據) | 讀取界限／成本；不憑空新增 A 全摘要庫搜尋政策 |
| 框架原文定位、模型可見引用、長內容續讀與不可讀錯誤 | [原文回查契約 §7](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#7-原文回查契約來源定位與有界讀取) | 已有 API 證據與設計基線，非 OpenAI 原封 schema；待 Compaction／retention 接線及後續機制驗證 |
| C：同輪局部修補，並非重跑 B／第三 Agent；後續 B 仍整理同一訪談 | 本文 C；[Sandbox Memory live update](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)；[Q018 §2](2026-09-05-memory-background-live-repair-coordination-research.md) | C 同輪來源定位、B/C 寫入協調；SDK liveUpdate 不等於 CLI Phase 2 claim |
| 兩階段≠固定兩次 API；normal no-op、失敗、部分完成不同；不盲抄 prune | [B §3.4、§4–5](2026-09-05-memory-background-cycle-flow-review.md)、[Q018](2026-09-05-memory-background-live-repair-coordination-research.md) | budgets、retry、executor、保留／恢復契約 |

**審核結論：**上述已討論的 A／B／C、產物與引用責任均有既有記錄；不是還缺一套 OpenAI 原理。此次補的是閱讀索引、證據歸屬及殘留文字校正：

- `FLOW-F01`：系統圖 §5.4 尚稱 SDK 未公開候選逐檔命名，與 artifact §1.1 已核對資料衝突；同步修正，仍區分 SDK 與 CLI。
- `FLOW-F02`：產物比較表還標①「建議」、組合提案 closure 仍以③為下一 gate；依既有撤回決定清除有效推薦歧義，不另作選型。
- `FLOW-F03`：A 的自動召回是本案已准組合，不是 Codex 已證實的必經步驟；補上歸屬。最終全 Memory 檢查則是 [MEM-D003](../current-decisions.md) 的能力目標，不冒稱 quick pass 可保證全涵蓋。

保存／讀取接法的比較沿革留在[產物接力 §8](2026-09-05-memory-extraction-artifact-framework-handoff-review.md#8-引用接力的框架覆蓋核對)，最新來源讀取基線見[原文契約 §7](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#7-原文回查契約來源定位與有界讀取)。後續依 §6 推進 Context／Compaction、B 生命週期與 Q018。**有新證據或具體效果缺口才重開原理；接法尚待驗證，不等於需要重問已同意的目的或唯一格式。**

## 8. 五個產物與按需深入的定向審核

**2026-09-05／Q017 G4，非新選型。** Owner 同意前輪原文回查方向，再要求查清 `raw_memory`、`rollout_summary`、`rollout_slug`、`MEMORY.md`、`memory_summary.md` 及導覽是否重複。本輪全文回讀本文、決策入口／流程、摘要路由、原生 backend 及全流程提案，核對 artifact §1–4、系統圖 §5.6–5.8；重用既有 Codex 固定 source 研究，未重新抓 HEAD。新取得的官方 [Sandbox Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)與 [Codex local memories](https://learn.chatgpt.com/docs/customization/memories)分別支持分層讀取／兩階段，以及背景生成與本地記憶分工；不以產品介紹頁代替 slug、header 或 raw fallback 的既有 source 證據。

| Finding／程度 | 位置、影響與依據 | 處理／狀態 |
|---|---|---|
| FLOW-F04／P2 | §2.1「不必繞過候選庫」可能反讀成 A 應經候選，與 §4 及 Codex read-path 責任相反 | 改成「不必經過候選庫，正文直接連詳記」；文字已修正 |
| FLOW-F05／non-blocking | §2 將 slug 放表外，且未直說導覽是 `memory_summary.md` 的同一對應，易被誤判漏產物或新增層 | slug 入表並標明非知識正文／非身份；導覽同一性寫清楚。是否獨立 slug 欄位仍未定，不是假裝已實作 |
| FLOW-F06／P2 | 較早 artifact §3.1 的直線箭頭及省略中間摘要的舊 read shape，可能變成「每輪固定讀完」或漏掉詳記橋接 | 本文 A 改為可停止分支；artifact 示意及 register 舊路由加最新適用邊界。依據為摘要路由 §3，不新增全庫搜尋 |
| FLOW-F07／non-blocking | 「有工具／五個名稱都在」不足以證明生成、保存、載入與引用都接好 | 下列未完成責任明列；未做框架或模型測試，不宣稱功能已驗收 |

**仍未完成，不是本輪新增需求：**①最新導覽載入、既定少量自動召回、Compaction 及原文保留的 Context 接線；②B 輸入範圍／觸發、產物部分保存與恢復；③C 同輪來源補接、B/C 正文與導覽協調。`read_file`／Store 可承接讀寫，不能自行形成這些流程。具體限制與公開 API 已在[backend §3–5](2026-09-05-memory-artifact-native-backend-design-review.md)及[來源契約 §7](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#7-原文回查契約來源定位與有界讀取)分層記錄。

**Closure：**五個概念及用途均已記錄，未發現本範圍漏掉整個 artifact 責任；找到上述文字／路由歧義並校正。沒有新增第二份導覽、候選必讀、固定全深讀或每輪 guide 生成。接續仍是 Context／Compaction，再 B 生命週期、Q018，最後實作計畫；有新官方證據或具體效果缺口才重開。只改研究／指路，不改 production、執行 spike／付費模型或宣稱驗證完成。
