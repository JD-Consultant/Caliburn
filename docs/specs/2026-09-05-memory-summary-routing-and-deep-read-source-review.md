# Q017：模型如何找到相關摘要並按需深查

> 2026-09-05 · G4 定向 source review；官方機制已追到 producer／consumer，框架接法仍待審。不是新 Memory 方案、最終 schema 或施工授權。
> 入口：[current decisions](../current-decisions.md)；父題：[抽取產物接力](2026-09-05-memory-extraction-artifact-framework-handoff-review.md)。

## 0. 本輪只補哪個缺口

Owner 問：「讀 Memory 覺得不夠清楚，怎麼知道哪份摘要相關？怎麼一路挖到原文？」

[09-04 progressive-disclosure 研究 §4](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)已研究讀取順序；本輪補齊**寫入時如何建立路由、讀取時誰判斷相關性、誰提供真實地址、框架實際回傳什麼**。不重選 A／B／C，不讀已排除的舊產品長稿。

**結論：**不是模型憑空猜摘要名稱，也不是搜尋工具自動理解全部關係。Codex 在生成 Memory 時就建立可搜尋的主題線索與摘要引用；模型日後先搜尋命中，再沿已提供的引用讀取。**語意相關性由模型判斷；實際來源位置由 Runtime 提供；搜尋／讀取由工具執行。** 選錯主題或漏查仍可能發生。

## 1. 證據範圍與版本

- [OpenAI Sandbox Memory 公開說明](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)：支持 guide → MEMORY → summary 分層與 extraction／consolidation。詳細欄位及路由政策以下列 **Codex 公開實作快照**為據，不推廣為所有 OpenAI 產品或所有廠商的共同 schema。
- 固定 Codex SHA：`574a36ff99f0807a24f5b043f593122bf151908d`。本輪重新下載下列三個 source，並用 GitHub tree 比對研究時最新 main `ddf04ad26789d040f9ef6a96736f76602e35a6cc`（2026-09-05 05:31:48 UTC）；三檔 blob 相同。這是 source 新鮮度查核，**不是已發佈穩定 API 保證**。

| 官方 source | 本輪追到的責任 | 相同 blob SHA |
|---|---|---|
| [storage.rs](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/storage.rs) | 候選、摘要與原始 rollout 的實體連結 | `e3e3395f940e08647d657621aa671a32738a35ee` |
| [consolidation.md](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md) | 整理模型如何建立主題、keywords 與摘要引用 | `0eef7580b5c2694594e2e52c9dade3dbbdcdae5b` |
| [read_path.md](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/ext/memories/templates/memories/read_path.md) | 前台模型何時搜尋、深讀、停止或重新查 | `00639c7e8c7dfc36b49a37c05bd26d2afe726b8e` |

## 2. 先看寫入端：相關摘要不是等查詢時才臨時配對

### 2.1 Runtime 先把真實位置放進抽取產物

`rebuild_raw_memories_file` 將每筆 Stage1Output 的候選內容與 `thread_id`、來源時間、`cwd`、`rollout_path`、`rollout_summary_file` 一起提供給整併模型。`write_rollout_summary_for_thread` 寫出 `.md` 摘要時，也在模型產生的摘要正文前加入 thread／時間／原文位置等 header。因此「這批候選來自哪份摘要；這份摘要的原文在哪」先由 Runtime 建立，不需要 LLM 重新捏造來源 ID／時間／地址。[storage producer，L44–77、L110–135](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/storage.rs#L44-L135)

模型可產生可讀 slug，但檔名還有 Runtime 的 thread／時間／hash 等組成；slug 不等於身份。這證明 Codex 的定位來源，不替尚待審的 framework record／view 方案決定欄位或保留政策。[filename producer](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/storage.rs#L153-L237)

### 2.2 整併模型將既有引用放到適合的 Memory 主題

Codex 的 `MEMORY.md` 不只是無結構長摘要。其 prompt 規定：

- 群組說明主題、適用範圍；群組內有具體 task 描述。這裡 task 是 Codex 工作記憶單位，**不是 Caliburn JD Task**。
- 每個 task 附自己的 `rollout_summary_files` 與可搜尋 `keywords`，不是把所有摘要混列在全文件底部。
- 摘要引用旁保留來源位置、時間、thread 等線索，可補用途／結果提示。
- 一個主題可連數份相關摘要；同一份摘要也可能支援數個主題。不是強制一對一，也不是按相同字眼就自動合併。

這些關聯由**整併模型根據候選與按需深讀的摘要選擇**；Runtime 提供地址，不替它作語意分類。[Memory 內容規則，L203–328](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L203-L328)

### 2.3 小型導覽要保留真的能搜到的線索

`memory_summary.md` 的導覽項目包含主題、keywords 與用途描述。官方 prompt 特別要求 keywords 能直接在 `MEMORY.md` 搜到，保留來源原本具有區別力的用語；合併主題時不要把原有查找線索全部抽象掉。導覽告訴模型「先查什麼」，不是再塞一份完整知識正文。[guide 規則，L568–602](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L568-L602)

**因此文字搜尋有作用，不是因為 grep 懂同義詞，而是寫入端刻意維持可搜尋線索，讀取模型再將本輪問題對應到這些線索。** 這不保證任意改寫都能命中；來源也沒有證明此 read-path 使用隱藏的向量排名器。

### 2.4 2026-09-06 補查：詳記可否更新，不等於原文不可改

Owner 本輪問的是 **rollout summary／訪談詳記本身**，不是 `MEMORY.md`：同一案例在後續訪談被更正，是否會保存兩份不同說法，以及舊詳記如何處理。

**後續深入核對已完成：**見獨立[Q019-MEM-SUMMARY-01 詳記更正 source review](2026-09-06-openai-rollout-summary-correction-source-review.md)。同 thread 重抽替換 Stage1、跨 rollout 整併與可選詳記清理、live update／讀取邊界已分開核實；不代表全部舊詳記自動同步更正。以下保留首次辨識問題的沿革，最新證據與唯一 next gate 以該子稿為準。

- **Official source fact（本輪重新取得上述固定 SHA，非宣称最新 main）**：[`storage.rs`](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/storage.rs) 的 `sync_rollout_summaries_from_memories` 從選定 Stage1Output 同步詳記；`write_rollout_summary_for_thread` 用檔案寫入更新生成內容，`prune_rollout_summaries` 清理不在保留集合的 `.md`。因此詳記不是永久 append-only 的官方保證。這不證明按案例跨所有 rollout 自動修正，也不證明任何後續訊息都立即觸發重抽。
- **Official prompt fact（同一固定 SHA，本輪完整重讀）**：[`stage_one_system.md`](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/stage_one_system.md) 禁止改寫的是 raw rollout；對 summary 則要求保留使用者更正、結論形成脈絡與已確認／推論／未定的區別。這是抽取模型的內容指示，不是 Runtime 自動判定矛盾正解。
- **Caliburn current mapping**：[Q019 Memory §1／§2.2／§3](2026-09-06-analysis-only-agent-memory-design.md) 選擇按訪談視窗保存不可變詳記。因此 A 案例跨兩個抽取視窗時，可以有兩份詳記；不是每個案例只有一份反覆 CRUD 的詳記。同一視窗內已有更正時，模型可在一份詳記交代前後更正，不能把「一輪」等同「一份詳記」。
- **尚未充分定案的讀取邊界**：現稿有「舊詳記不可恢復舊結論」的原則，但不能据此保證模型只打開舊詳記時，必然也看到後續更正。尤其更正僅涉及案例細節、未改一般工作模式時，不得用「正文會整併」迴避詳記回查是否漏掉更正的問題。若需改為重建詳記、補充更正引用或其他接法，先比較並交 Owner 討論，不在本輪自行新增關聯表、狀態欄位或改保留政策。

**Closure：**補齊保存層與語意更正的證據界線；未翻案、未改程式。下一個討論只處理「讀到舊詳記時如何同時取得已知更正」，不是重選整套 Memory。

## 3. 讀取端：每次多讀一層，都有明確依據

```text
本輪問題＋已注入的小型 Memory 導覽
  → 模型挑相關主題與可搜尋詞
  → 搜尋 MEMORY.md，讀命中區段及適用範圍
  → 內容已足夠：直接工作，不必繼續下挖
  → 還缺當時細節：沿該段引用，開少量相關 rollout summary
  → 仍需精確證據：沿 rollout_path 查原始對話／工具紀錄
  → 新讀到的內容成為工具結果，模型再決定下一步
```

**前台 A 的官方 prompt 邊界：**先選與任務相關的 keywords；只有 MEMORY 指向相關摘要／Skill 才開其中最相關的 1–2 份；需要精確命令、錯誤或證據才查 raw rollout。快速查找理想上不超過 4–6 個搜尋步驟，避免全面掃描摘要；不是產品強制上限，也不是固定 API 呼叫數。沒有相關命中就停止這次 Memory lookup、正常繼續；遇到重複錯誤／令人困惑的行為或懷疑先前脈絡有用，可重新查。[read policy，L6–59](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/ext/memories/templates/memories/read_path.md#L6-L59)

「沒有命中」不證明歷史中不存在，不可據此宣稱涵蓋完整；也不能把上述快捷讀法替代日後需要的全量盤點。prompt 不提供保證判對「是否足夠」的 deterministic 函式；模型看內容後判斷，依工具回傳接續。

**示意，不是實際 Codex 輸出或新 schema：**問題問「之前付款回呼為何重複入帳」。導覽提供「付款回呼／重複入帳」線索；搜尋命中一段 Memory，其中已有結論與摘要 A、B 的地址。A 是首次調查，B 是後續修正。模型需要當時驗證細節就開 B；若還要核對原始錯誤字串，B header 的原文位置讓它直接讀該次紀錄，不必遍搜所有對話、也不必猜 message ID。

## 4. 背景 B 的補查不同，不能把 A 原封套過去

B 已拿到帶摘要位置的候選與 current Memory。增量整理先讀輸入變化及既有引用；需要判斷重要、模糊、重複或有衝突的主題時，再開相應摘要。prompt 要求先列實際存在的摘要檔，只使用其中的地址；缺檔不猜路徑。**這個 Codex Phase 2 不讀 raw sessions**，與前台 A 的最後核實層不同。[B 輸入／限制，L119–175](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L119-L175)、[B 按需深讀／引用檢查，L753–880](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L753-L880)

這也補強 [B §3.5 保存用途](2026-09-05-memory-background-cycle-flow-review.md#35-保存中間結果為了後續補查重用不是才能整併)：摘要不只服務當次整併，也服務以後 A／B 的精讀。**不等於所有中間產物一定永久保存，更不等於必須等下一個排程才整併。** Codex storage 有保留集合／prune；其淘汰策略不能直接當成完整細節永久可回查的保證。

## 5. 框架可承接什麼，缺的是什麼

此表沿用 Q017 主要候選，不批准新的儲存或工具 schema。

| 接力 | 已查到的現成能力 | 仍需明確接合的部分 |
|---|---|---|
| 問題→導覽→查找詞 | `create_agent` 模型／工具循環；model middleware 可組裝當次 context | 導覽內容規則、讀取政策、何時載入最新導覽；不是開 MemoryMiddleware 就自動重現 Codex |
| 查詢→命中位置 | FilesystemMiddleware＋StoreBackend 的文字搜尋；backend 的 GrepMatch 有 path／line／text | 寫入內容要有可搜尋線索；文字命中不等於已判定語意相關，也不等於向量搜尋 |
| 命中位置→詳讀 | backend `read(file_path, offset, limit)`；ReadResult 有內容、分頁資訊或 error | 摘要／Memory 的可見地址須能由選定 reader 真正解讀，不能把不可見的 ToolMessage.artifact 當作模型已讀到 |
| 摘要→原始對話 | graph 公開 state／history reader；或 BackendProtocol 的唯讀投影擴充 | 來源定位、仍保留原訊息的 checkpoint、訊息窗口及 rendering；StoreBackend.files 不會自動讀 graph messages |
| 寫入→下次可找回 | Store／StoreBackend 保存；模型依內容規則整理並保留已有引用 | 框架不自動決定哪份摘要支援哪條知識；record＋視圖或其他公開接法仍 OPEN |

來源：[官方 Backends／擴充契約](https://docs.langchain.com/oss/python/deepagents/backends)、[StoreBackend read 與 grep 固定 source](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L366-L611)、[GrepMatch／ReadResult](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/protocol.py#L159-L230)。Context 與同源原文接法細節沿用[框架接力研究](2026-09-05-openai-shaped-memory-framework-composition-research.md)、[原文小元件 §6](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#6-接續核對同源原文如何供-b-抽取與-a-深查)，不在此重寫。

**成本限制：**固定 StoreBackend 的 grep 先分頁取得 namespace items，再做文字匹配；只回少量命中不代表 DB 只讀少量資料。模型端按需深讀可控 token，但大量資料的查詢成本還要在後續規模／backend 接法討論，不能先宣稱零成本或自動索引優化。[grep 實作，L593–611](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L593-L611)

## 6. 本輪防誤讀與修正

| ID／程度 | 位置及問題 | 修正／狀態 |
|---|---|---|
| MR-F01／P2 | artifact 詳表 source list 的 `memories/read/.../read_path.md` 路徑不存在，影響後續可回查性 | 修為本輪核對的 `ext/memories/...` 固定 SHA；已補正 |
| MR-F02／non-blocking | 「模型知道相關摘要」若只寫四步箭頭，會把語意關聯與實體地址混為框架自動功能 | §2–5 補 producer→consumer、模型／Runtime／工具分工；不是新自訂機制核准 |
| MR-F03／non-blocking | read prompt 在 summaries 小節附近談 append-only JSONL，單看排版可能誤讀摘要格式 | storage 實際寫 `.md` 摘要及 `rollout_path` header；JSONL 原始對話與摘要分開，不從一句話推導二者相同 |

官方要求模型檢查引用存在、保留來源與對齊導覽，但**本輪未找到能保證每個語意引用都正確的 Runtime verifier**。不把 prompt 的 MUST 寫成 deterministic 保證；也不因此擅自新增引用驗證器、分類 Agent、向量服務或強制 lineage gate。Q014 lineage、Q018 並行與讀取介面仍按原 gate 討論。

## 7. Closure

- **Finding：**已補齊寫入時建立搜尋線索／摘要引用，到 A／B 讀取時沿引用深挖的公開機制；先前「按需讀摘要」方向成立，但不是工具自己猜相關性。
- **Status：**官方事實核對完成、供 Owner 審核；不是 adapter／schema 核准或 G5 pass。
- **Why／Sources：**Owner 追問缺少實際接力；§1 固定 source、§2–5 附行號與 framework 公開能力，區分官方規則、實作行為和接法建議。
- **Affected：**本子稿、抽取接力入口、09-04 舊研究路由、artifact 詳表錯誤 source link、current register；只改研究文件。
- **Reopen：**上述 source／public API 改變，或後續接法無法保留可搜尋線索、可見且有效的摘要／原文定位時，定向重查；不重新廣泛研究全部 Memory。
- **Next gate：**以本稿已查明的讀取需要審抽取產物 §3.3–3.5 接法，之後串 current Memory／guide 與 A／B／C。來源定位及 record＋唯讀視圖仍未核准；不因本輪理解就自動施工。
