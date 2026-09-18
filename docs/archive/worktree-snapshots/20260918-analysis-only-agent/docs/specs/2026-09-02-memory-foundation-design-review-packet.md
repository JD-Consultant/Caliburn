# Memory Foundation 最小切片 Design Review Packet

- 日期：2026-09-02
- 狀態：**Approve for isolated spike；Product Owner 已明確核准，短跨輪 Memory smoke 增補的 affected-section re-review 已通過**
- 被審文件：[`Memory Foundation 最小垂直切片設計（Store-first 重寫）`](./2026-09-02-memory-foundation-vertical-slice-design.md)
- 被審基準 SHA-256：`FC0BFDD02C4201388BD2F7FC4E4877928BF82B53C67D0952D205AACAB553E55C`
- 被審基準行數：565
- 工作分支：`refactor/current-only-architecture`
- 審核目的：決定這份設計是否足以授權**隔離的 Memory foundation spike**；不是核准 production authority、ADR、JD、UI、RAG 或完整 Memory 實作

> **本文件只是審核入口，不是第二份規格。**所有產品契約、技術設計與停止線仍以被審文件及其上位研究為準。Review Packet 只列出審核順序、責任、關鍵主張、意見台帳與核准條件；不得在此偷偷新增產品需求或實作機制。

> **Baseline 規則**：開始或恢復審核前先核對 SHA-256。若不一致，舊 review 只能作歷史意見；作者必須列出變更摘要、更新本 packet，並重新要求受影響章節的審核。這對應 GitHub 在重大變更後 re-request review／讓舊 approval 失效的做法。

PowerShell 核對方式：

```powershell
Get-FileHash -LiteralPath 'docs\specs\2026-09-02-memory-foundation-vertical-slice-design.md' -Algorithm SHA256
```

## 0. 這次審核最後只能有三種結果

1. **Approve for isolated spike**：只核准依文件 Stage 0～3 寫 spike plan、執行隔離測試並產生報告。
2. **Request changes**：存在必須先修正或補證據的 Blocker；不得進 spike plan。
3. **Comment only**：只有非阻擋建議，或審核者尚未完成指定範圍；不能當成核准。

即使本輪 Approve，也**不代表**：

- 接受新的 production authority；
- 接受 LangMem core 或 Store manager 任一候選；
- 接受 successor ADR；
- 接受完整 Memory、Memory→JD、UI 或 RAG 實作；
- 宣稱已能製作滿分 JD。

## 1. 採用的成熟審核方法

本 packet 綜合下列公開做法，但不把任何一家流程原封不動搬進 Caliburn：

1. **先審目的與整體設計，再審細節**：Google 將整體 design、功能、複雜度、過度設計與測試列為 reviewer 的核心責任；Microsoft 也建議 first design pass 後再看錯誤處理、功能與測試。
2. **重大設計必須記錄替代方案、風險與 feasibility spike**：Microsoft Engineering Fundamentals 要求 major component design review 留下文件與 alternatives，未知技術可先做 spike 降低風險。
3. **意見必須可追蹤並有正式 verdict**：GitHub review 使用逐行 comments、Approve／Request changes、resolved conversations；重大修改後 re-request review。
4. **先定義成功，再量測，再依錯誤改善**：OpenAI 的公開 eval 方法是 Specify → Measure → Improve；測試需反映實際工作與高代價 edge cases，而不是只看 demo。
5. **只有實證改善才增加複雜度**：Anthropic 建議從簡單、透明、可測的 agent 設計開始，只有較複雜做法明顯改善結果才採用。

這次不建立完整 eval 平台。上述方法只落成：明確成功條件、deterministic contract tests、極小 semantic smoke、錯誤分析與人工核准。

### 1.1 本輪實際討論與審核流程

本輪不採「想到什麼就聊什麼」，也不把 checklist 打勾當成證據。依下列順序進行；前一 Gate 未通過，不得跳到後一階段：

1. **Baseline lock**：核對被審文件 SHA-256、行數、上位文件與明確排除文件；版本改變就讓受影響的舊結論失效。
2. **Product pass**：Owner 先確認產品目的、必要效果、成本／範圍與停止線，不先討論函式或檔案配置。
3. **Evidence／contract pass**：獨立 reviewer 逐項重開最新官方來源與 pinned framework API，區分官方事實、Caliburn mapping 與尚待實驗的未知。
4. **Adversarial／failure pass**：另一個獨立 pass 從 crash、resume、重放、半完成、跨 scope、細節遺失、低信任資料與過度設計反推失敗案例。
5. **Findings convergence**：每項意見必須有 ID、等級、位置、證據、要求與狀態；只把無法由官方 contract／deterministic test 回答、且會改變產品效果、成本或範圍的真正決策題交給 Owner。
6. **Plan traceability review**：全部 Gates 通過後才寫 isolated spike plan；每個 task 必須能追到「M1～M11 能力 → framework primitive → 測試 → Go／stop」，找不到效果依據的工作不得加入。
7. **Staged execution**：Stage 0 contract canary → Stage 1 deterministic failure／replay → Stage 2 極小 Luna smoke → Stage 3 實驗報告；任何 stop condition 成立即停止，不在同一 task 臨時發明補丁。
8. **Report review and decision**：報告必須同時列成功、失敗、成本、未證明能力與候選淘汰原因；再次獨立 review 後，Owner 才決定 successor ADR，不因已投入時間而保留較差方案。

討論細節的分界：

- **必須討論**：會改變 Memory 效果、資料 authority、員工隔離、可靠性、成本、模型呼叫、framework／retrieval dependency 或產品範圍的選擇。
- **應由證據回答**：API signature、預設值、failure semantics、是否需要 index、replay 邊界、listing contract 等可由官方文件或 canary／fault injection 判定的問題。
- **不在設計審核消耗時間**：函式命名、檔案排版、無行為差異的 wrapper 與尚未出現的未來需求；這些不能拿來延後真正風險，也不能偷渡進第一切片。

## 2. 審核者與責任

| 角色 | 必看 Gate | 不能只做什麼 |
| --- | --- | --- |
| Product Owner | G1、G6、最終 verdict | 不能只說「方向看起來可以」；要確認產品目的、範圍與停止線 |
| 獨立技術／證據 reviewer | G2、G3、G4 | 不能相信作者摘要；需重新開官方來源並核對被審章節 |
| Adversarial／failure reviewer | G5、G6、G7 | 不能只走 happy path；需找無法證明、重放、半完成與過度設計風險 |

同一人可以兼任後兩個角色，但必須分成兩次 pass：先核證據與 framework contract，再重新從 failure／minimality 角度閱讀，避免因已接受方案而降低反證力度。

Owner 是唯一最終核准者；技術 reviewer 不可代替 Owner 改產品目的，Owner 也不以產品偏好代替 framework contract 證據。

## 3. 建議閱讀順序

不要從第 1 行一路讀到最後才開始留言。依下列順序可以先抓住目的，再查最危險主張：

1. **產品與決策摘要**：被審文件 §0～§2。
2. **authority／資料邊界**：§3。
3. **真正要驗證的未知**：§4～§5。
4. **成本受限的驗證方式**：§6～§8。
5. **是否誠實覆蓋產品能力**：§9～§12。
6. **逐項打開來源，不只讀作者摘要**：§13～§14。
7. 最後回看 [`Framework-independent Memory Contract`](./2026-09-01-framework-independent-memory-contract.md) 的 M1～M11，確認切片沒有反向降低上位效果。

## 4. 七個 Review Gates

### G1：產品目的與必要效果

必須逐條確認：

- 一名員工、一份 JD、一個長期訪談 thread、一組私有 Memory；不跨 JD 共用。
- Memory 的目的只是讓顧問在長訪談後仍能取得完整工作範圍與重要細節。
- Memory 不決定 Duty／Task／工作細節／完成標準／K／S，也不決定或操作 JD。
- 原始來源與整理後 Semantic Memory 都保留，彼此不取代。
- 補充不破壞舊細節；明確更正才取代；不同條件／案例與未解衝突不被壓平。
- 日常 Context 可以有界；只有 JD 完成前的全面檢查不能漏掉任何目前有效 Memory。
- 員工核准 JD 的既有產品原則沒有被本切片繞過。

**Blocker**：任一項在設計中消失、被 framework default 取代，或被轉成不必要的新產品目的。

### G2：官方事實、產品映射、未決問題分離

對被審文件 §2 與 §13 的每個重要主張，標記：

- `F`：官方文件直接支持的 framework／vendor fact；
- `M`：Caliburn 為產品需求作出的 mapping；
- `U`：仍需 spike 才能回答的 unknown。

最低要求：

- `F` 必須能在第一手官方來源找到，不依部落格、搜尋摘要或作者記憶。
- `M` 必須說明為何服務 M1～M11，不能冒充「OpenAI／Anthropic 都這樣做」。
- `U` 必須有能推翻候選的測試與 stop condition，不能讓實作者偷選。

**Blocker**：把 mapping 寫成 vendor fact、來源不支持摘要、或尚未證明卻寫成 production 保證。

### G3：framework 責任與 authority 邊界

核對：

- Checkpointer 只承接 thread／run state、interrupt／resume 與短暫結果。
- 每份 JD 隔離的 PostgreSQL Store 承接完整來源與目前 Semantic Memory。
- source leaf 只由可信 conversation intake 新增；semantic writer 不能改掉員工原話。
- scope／namespace／canonical identity／時間／retry／權限由可信 Runtime／framework 管理，不由模型填。
- LangMem 只作 extraction／consolidation 候選，不因此取得 JD authority。
- 現行 Accepted ADR 0060 在 successor ADR Accepted 前仍有效；spike 不寫 production authority。

**Blocker**：出現第二套 Memory authority、雙寫、模型可選 JD scope，或 spike 直接接 production。

### G4：Memory 語意與資料最小性

核對 `topic＋rich self-contained content` 是否足以測：

- 新工作主題；
- 同主題補充且不遺失未重述細節；
- 明確更正；
- 不同條件／案例；
- 未知與未解衝突；
- 無新職務資訊的 no-op；
- 助理推測不得升格成員工工作事實。
- 訪談／Memory 中形似指令的文字仍被視為低信任資料，不能改變 scope、policy 或 Runtime metadata。

同時確認沒有先要求模型填 canonical ID、source UUID、quote offset、status、confidence、Skill ID、version、timestamp 或 retry metadata。

**Blocker**：測試資料無法辨識 destructive rewrite／案例誤一般化，或為了方便程式先加入尚無效果證據的 schema。

### G5：持久化、完整盤點與 replay

核對：

- 真 PostgreSQL Store 的 persistence、restart、same-key overwrite、delete 與 per-JD isolation 都有 deterministic contract test。
- 完整盤點不使用 semantic top-k 或 offset pagination。isolated spike 只在 pinned backend、exact leaf、無同 scope 並行 mutation 的條件下，以單批 `configured_spike_cap＋1` 驗證明示 cap：`0..cap` 必須與 expected key set 完全相等，取得 `cap＋1` 則回 typed overflow、停止 final audit，且不得把部分結果標成完整。若 production 需要超過 cap，必須改用具 stable server cursor／token 與明確 completion signal 的成熟 substrate，否則停止／重選。
- 測試會把實際 key set 與 expected key set 比較，而不是只看筆數。
- Store 同 key overwrite 與 end-to-end semantic operation replay 被明確分開。
- replay 測試真的使用 PostgreSQL Checkpointer、PostgreSQL Store 與最小 LangGraph durable task，不以 Store-only 測試冒充 workflow replay。
- mutation 前、mutation 後但 task 未完成、task 完成後 retry 三個 crash window 都有測試。
- 多筆 mutation 沒有在證據不足時被宣稱 atomic。

**Blocker**：測試只能證明 happy path、把 offset listing 說成 snapshot cursor，或把 Store upsert 說成整條 LLM workflow 冪等。

### G6：最小性、成本與範圍

確認第一切片沒有：

- production graph／authority／JD／UI／export 改造；
- RAG、Qdrant、embedding、reranker 或外部 corpus；
- 跨 JD Memory；
- knowledge graph、case store、第二份工作理解或第二 runtime；
- 預建 CAS、revision、receipt、manifest、outbox 或自訂 repository；
- 為了保留 Store manager 候選而偷接 embedding、semantic index 或額外 retrieval model；
- 無界 retry、固定第二個模型或 multi-agent；
- 完整 eval 平台。

真模型上限仍是 `gpt-5.6-luna` medium、每個通過 Stage 0／1 的候選最多兩次主要 call、全部候選合計最多四次，以及最多一次 framework 文件化 repair。

**Blocker**：新增複雜度沒有對應已觀察 failure，或 spike 成本／範圍已大到等同 production 實作。

### G7：可證偽性與完成判準

逐項確認：

- 每個 Go 條件都有對應測試或可檢查 artifact。
- 每個 Stop 條件真的會停止，而不是實作者可在同 task 自由補機制。
- Stage 0～3 有清楚順序；前一階段失敗不能跳到真模型或 production。
- M1～M11 表格清楚區分「本切片能證明」與「仍不能證明」。
- 最終報告必須包含失敗案例、framework contract、成本與替代候選，而不是只有綠燈摘要。

**Blocker**：測試無法讓候選失敗、成功標準只看 demo、或報告不足以支持下一個 Owner 決策。

## 5. 必須獨立核對的八個高風險主張

| ID | 主張 | 被審位置 | 審核方式與通過條件 |
| --- | --- | --- | --- |
| H1 | Store 比 Checkpointer 適合完整長期 Semantic Memory | §0、§3.1、§14 | 重新讀 LangGraph Persistence；確認是官方責任分層＋Caliburn lifecycle mapping，不是「Store 只能跨 thread」的誤讀 |
| H2 | 同一 PostgreSQL Store 可用不同 leaf 隔離 source／Semantic Memory | §2.2、§3.2 | 標記為 Caliburn mapping；Stage 1 必須證明同 key、相鄰 leaf、相鄰 JD 不污染 |
| H3 | isolated spike 的單批 `configured_spike_cap＋1` 可在明示 cap 內 fail closed；不能外推成 production 無界盤點 | §4.2 | contract test 必須同時證明 `0..cap` 的 exact key set、`cap＋1` typed overflow 與 no partial-as-complete；若 production 需要超過 cap，只能採 stable server cursor／token substrate，否則停止／重選，不得恢復 `asearch＋offset` |
| H4 | `topic＋content` 是足夠薄的 model-facing 形狀 | §3.3～§3.4 | 確認文件明示它不是 vendor common schema；用代表 fixture 判斷是否保存細節而非靠欄位數量 |
| H5 | LangMem core／Store manager 是值得比較的兩個正式介面 | §4.3、Stage 0／2 | 重讀 LangMem concepts／API；先核 signature、side effects、`query_limit` 與 retrieval dependency。C2 若需要未核准 index／embedding 就淘汰，不為了湊比較擴張範圍；合格者才用相同 fixture 比較 |
| H6 | same-key overwrite 不足以證明 end-to-end replay | §5.1～§5.2 | 重讀 LangGraph Functional API；必須用真 PostgreSQL Checkpointer／Store＋最小 durable task 執行三個 crash window，並比較實際 current collection |
| H7 | 第一切片不預建 CAS／receipt／manifest | §2.3、§5、§11 | 確認目前 single-writer／quiescent 邊界足以測 foundation；若實驗失敗才帶證據重開成熟 primitive 比較 |
| H8 | 本切片只部分覆蓋 M1～M11 | §9～§12 | 對照上位 contract；不能把 persistence smoke 說成完整 long-term Memory 或滿分 JD 證據 |

## 6. Review comment 格式

每一項意見都使用下列格式，不能只寫「怪怪的」「我不同意」或留在聊天室：

```text
ID：DR-MEM-001
位置：被審文件 §／行號
等級：Blocker／Important／Suggestion
類型：產品契約／官方證據／framework／語意／failure／成本範圍
發現：具體哪個主張有問題
為什麼：會造成什麼錯誤或無法證明什麼
依據：官方來源、上位契約或可重現案例
要求：要修改什麼，或要由哪個測試回答
狀態：Open／Addressed／Rejected-with-rationale／Deferred-with-link
```

等級定義：

- **Blocker**：會偏離產品目的、錯用 authority、錯引官方事實、無法可靠驗證或可能讓 production 方向做錯。
- **Important**：不一定否決方向，但容易讓兩名實作者做出不同系統，或讓報告得出錯誤結論。
- **Suggestion**：可讀性、命名或不影響判斷的改善。

`Deferred-with-link` 不能用來略過 Blocker。超出本切片但真實存在的問題才可延後，且必須連到明確後續項目；不能在本文偷偷擴張範圍。

## 7. Review findings ledger

第一輪獨立 review 審查的是舊基準 `A279223525EE019E277DA9032241A963C485C1422FEA2A27EE763758E6175DCD`，兩位 reviewer 都給 `Request changes`。作者已逐項對照官方 source、pinned repo dependency 與 PostgreSQL 文件驗證；不是直接照單全收。其後的修正曾由原 reviewer re-review；exact-inventory 大廠共識重驗與 Owner 裁決形成基準 `C16087BD813F5E742260F9670FAB74A3C8B2C9F35ACA9601BDF93176CFD48654`，DR-MEM-F01 也已由 Sagan 重新核對並通過。Owner 隨後指出原 Stage 2 把補充／更正／衝突塞進同一 call，不能直接證明跨輪記得、重啟後續接及衝突釐清。第一次增補基準 `1E55E6E306E09FF12C5525A145D2314C57FD693F1BF949BF54F381CF53C79A52` 經 Erdos review 後又發現 provider-call 上限、intermediate oracle、no-op 證據邊界與 unknown 全稱表述四項問題；基準 `DD2FEA9566DFE33503C6F1F3C578913F8101B2372D7C567739BFFD9D942470C3` 修正後，Erdos 的第一次 affected-section re-review 確認 R1／R2／R4 通過，但抓到 §0 與 §4.3 仍殘留自然語言 no-op 能力宣稱。現在基準 `FC0BFDD02C4201388BD2F7FC4E4877928BF82B53C67D0952D205AACAB553E55C` 已把兩處限縮為 deterministic `no_change` apply wiring；Erdos 第二次窄範圍 re-review 確認 O01／R1～R4 全數通過、沒有剩餘 finding。其他不受影響項目保留原 review 證據。

| ID | 等級 | 位置 | 摘要 | 狀態 | 處理證據 |
| --- | --- | --- | --- | --- | --- |
| DR-MEM-T01 | Important | §4.3、Stage 0 | C1 delete 會回 `RemoveDoc`；C2 Store value 有 `kind＋content` envelope，delete 不在 `final_puts`，空 return 不能當 no-op；未鎖精確 artifact | Addressed；re-review passed | 增加 C1／C2 input／return／Store before-after contract matrix、artifact hash／source revision 與淘汰條件 |
| DR-MEM-F01 | Blocker | §4.2、M9、Go | PostgreSQL Store 只按非唯一 `updated_at DESC` 排序，offset pagination 即使 quiescent 也不能保證無漏／無重 | **Addressed；Owner 已裁決；re-review passed** | 原 offset Go 路徑已撤回；官方重驗顯示跨家共識是 bounded page＋server cursor/token＋completion signal。Owner 正式核准 spike 以 cap＋1 overflow fail closed 驗證明示邊界；不得外推為 production 無界解法。Sagan 的最終 re-review 確認 G5／H3 已無 offset 回流路徑 |
| DR-MEM-F02 | Blocker | §5.2、Stage 1 | fake boundary 未限制，可能用測試專用 ID／apply path 冒充候選真實 replay | Addressed；re-review passed | fake 只取代 provider semantic output；必須走 candidate public API、真 Store／Checkpointer；三個 injection point 明列 |
| DR-MEM-F03 | Blocker | §3.2、§4.1、Stage 1 | source 宣稱 append-only，但 Store same-key `put` 是 upsert，原測試未防同 key 不同 payload 覆寫原話 | Addressed；re-review passed | 加入 same key＋same payload no-op、different payload typed failure、correction new key、semantic delete 不碰 source |
| DR-MEM-F04 | Important | §5.2～§5.3 | 多筆 partial commit 的收斂 oracle、順序與 retry 邊界未定；第一次修正後仍缺 terminal run completion | Addressed；re-review passed | 固定 initial／intended final state、兩種 partial order、預定 attempt budget、一次明確 resume；Store final state、durable task result 與 entrypoint terminal completion 必須一致 |
| DR-MEM-F05 | Important | §3.2、Stage 1 | 只測 namespace happy path，不足以證明可信 catalog 與 child／sibling scope 不會被候選寫入 | Addressed；re-review passed | 加 document→thread／leaf binding 與 unknown／mismatch／child／foreign 在 Store 前 fail closed |
| DR-MEM-F06 | Important | §7.2、Stage 1、Go／stop | 低信任安全只靠真模型 smoke，無 deterministic authority gate；第一次修正後未把語意越權列成 Stop | Addressed；re-review passed | forged effect 在 mutation 前拒絕；指令型內容若造成無員工語意依據的 mutation 或改 scope／policy／metadata，候選立即停止 |
| DR-MEM-F07 | Important | M3 | 原文把一批來源的 per-source applied／no-op／failure 說得比切片可證明的多 | Addressed；re-review passed | 誠實降級 M3 為 source append＋operation outcome wiring；不為第一切片新增 receipt table |
| DR-MEM-O01 | Important | Stage 2、§7、M1／M2／M5、Go／stop | 原真模型 smoke 將補充／更正／衝突放在同一 call，無法直接證明後續回合未重述細節仍保留、重啟後可續接，以及衝突經員工釐清後只收斂應改部分 | **Addressed；affected-section re-review passed** | 維持每候選最多兩次 Luna provider invocation 總數；先經 public seam deterministic seed 詳細 Memory，call 1 補充＋未解衝突＋independent unknown，重建全部 client 後 cold read，call 2 只釐清衝突；以四份 canonical snapshot 驗證中間與最終狀態 |
| DR-MEM-O01-R1 | Critical | Stage 2、Owner call cap | 原文在兩次「主要 call」之外另允許一次 repair，實際可能變三次 Luna invocation | **Addressed；re-review passed** | 上限改成每候選兩次 provider invocation 總數，含 repair／retry；需要第三次立即失敗停止，repair 若耗掉第二次也代表跨輪案例未完成 |
| DR-MEM-O01-R2 | Important | Stage 2、§7、Go／stop | 只驗最終狀態可能掩蓋 call 1 暫時重複／遺失，client 重建也可能偷帶舊 Python 物件 | **Addressed；re-review passed** | 強制保存 seed 後、call 1 後、fresh-client cold read、call 2 後四份 public-seam snapshot；call 1 後即須正確，cold read 必須完全相等，禁止注入舊物件／list／cache |
| DR-MEM-O01-R3 | Important | §0、§4.3、Stage 1、Stage 2、§7 | deterministic fake `no_change` 只能證明 apply wiring，不能證明模型理解寒暄／無新資訊；第一次修正後 §0／§4.3 仍有殘留宣稱 | **Addressed；re-review passed** | 移除自然語言 no-op semantic case及前言／候選清單的殘留宣稱；只保留 deterministic typed-outcome wiring，模型 no-op 辨識列為本切片未證明 |
| DR-MEM-O01-R4 | Minor | §7、M5、Go | fixture 只有 conflict，原文卻對一般 unknown／衝突作全稱保證 | **Addressed；re-review passed** | call 1 加 independent unknown、call 2 不回答它；M5／Go 限定指定 fixture，明列其他未知／衝突形狀未證明 |

## 8. 作者自審紀錄

作者在送審前已完成以下機械與一致性檢查；這些不能取代獨立審核：

- 逐份完整回讀 [`滿分 JD 所需 LLM／Memory 能力`](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)、[`各家 Agent Memory landscape`](./2026-08-30-agent-memory-landscape-and-decision-working-research.md)、[`Caliburn Memory requirements mapping`](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md) 與 [`Framework-independent Memory Contract`](./2026-09-01-framework-independent-memory-contract.md)；
- 逐份完整回讀 [`框架選擇複核`](./2026-09-02-memory-framework-selection-revalidation.md)、[`實作機制與框架共識稽核`](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md)、[`完整列舉／版本／來源最小切片重驗`](./2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)、[`版本／並行／重播研究`](./2026-09-02-memory-versioning-concurrency-and-replay-research.md) 與 [`LangMem 既有小實驗`](./2026-08-29-langmem-domain-semantic-memory-spike-experiment.md)；
- 完整回讀被審設計與本 Review Packet，並核對 Accepted ADR 0060 目前 production authority；
- 重新開啟 OpenAI Codex Memories與公開 collection cursor API、Anthropic Memory Tool／Managed Memory／List memories、LangGraph Persistence／Stores／Functional API、LangMem Memory API，以及 Google／AWS Memory list 官方資料；
- 明確排除較舊且 Owner 指定不可用於本輪的 `2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`，沒有讓舊產品流程倒灌；
- 修正三份上位研究中仍指向舊 Checkpointer candidate 的過時交叉敘述；
- 相對 Markdown 連結存在；
- 無 trailing whitespace；
- repo 鎖定版本與文件 Stage 0 所列版本一致；
- 明確排除舊產品流程文檔、production 改造、RAG 與完整 eval。

### 8.1 本次作者深度自審發現

作者意見不寫進 §7 的「獨立 reviewer ledger」，避免把自審冒充獨立核准；但實際發現與修正仍完整留痕：

| ID | 等級 | 發現 | 處理 | 狀態 |
| --- | --- | --- | --- | --- |
| DR-MEM-A01 | Important | Stage 1 原本只明寫真 Store，卻宣稱能驗證「Store 已寫、durable task 未完成」的 crash window；兩名實作者可能做出 Store-only 測試 | 明定使用真 PostgreSQL Checkpointer／Store＋最小 LangGraph durable task，候選由 deterministic fake／stub 驅動 | Addressed |
| DR-MEM-A02 | Blocker | Store manager 官方是 bounded relevant-candidate retrieval，範例配置 semantic index；原文可能讓實作者為保留 C2 偷接 embedding，違反第一切片範圍 | 增加 Stage 0 retrieval contract canary；需要未核准 index／embedding／query model 即淘汰 C2，C1 可單獨繼續 | Addressed |
| DR-MEM-A03 | Important | 上位共識把持久 Memory 視為低信任資料，但 fixture 沒直接驗證指令型內容不會越權 | 在同一語意 fixture 加入指令型低信任資料，不增加 model call；通過條件明定不得改 scope、policy、metadata 或越權 mutation | Addressed |
| DR-MEM-A04 | Important | C2 可在 Stage 0 淘汰，但 M8 與實驗報告原本仍無條件寫成會觀察 Store manager，可能形成不存在的綠燈證據 | M8 與 Stage 3 改為只陳述合格候選；淘汰原因本身必須進報告，不能宣稱已測未執行的召回行為 | Addressed |

作者自審結論：**可送 independent review；尚不能 Approve for spike。**

### 8.2 Product Owner 方向確認（2026-09-02）

Owner 已確認下列產品／範圍方向；這完成 G1 與 G6 的 Owner 意圖確認，但不取代 G2～G5／G7 的獨立技術與 failure review：

1. 同意 PostgreSQL Store 保存每份 JD 的長期 source／Semantic Memory；Checkpointer 只負責 thread／run 執行狀態。
2. 對第一切片是否接 embedding／RAG 沒有產品硬性要求。依「沒有必要效果就不增加複雜度」原則，本設計仍採**預設不接**；若後續實證顯示它是必要條件，必須帶成本與效果證據另行討論，不能從「可接」推導成「現在就接」。
3. 接受 C2 在 contract canary 不合格時只繼續 C1，不強求湊成兩候選比較。
4. 同意本輪所有 gate 通過後也只授權 isolated spike；不得因此直接改 production。
5. exact inventory 只在 JD 完成前的低頻全面檢查使用；日常建立／修改 JD 仍採 bounded recall／按需 read，不會每回合載入全部 Memory。Owner 在看完共識研究後正式同意 isolated spike 使用 `configured_spike_cap＋1`、overflow fail closed，並明示它不是大廠 cursor 共識、不是 cap 以上的 production 保證。
6. 第一切片必須以極小短跨輪案例驗證「補充不丟舊細節、重啟後仍能續接、未解衝突不自動選邊、員工釐清後只修正衝突部分」；每候選硬性限制兩次 Luna provider invocation 總數（含 repair／retry），也不把它宣稱為數月長訪談 eval。

Owner 已於上述短跨輪要求說明後明確回覆 `Approve for isolated spike`。該要求改變受審基準後，Erdos 已依 Baseline 規則完成受影響段落的兩輪窄範圍 re-review；最終基準通過且無剩餘 finding，因此可依 §10 寫 Stage 0～3 spike plan，不需 Owner 重複核准同一版本。

## 9. Definition of Reviewed

只有全部成立才算本輪審核完成：

1. 被審 SHA-256 與 packet 一致，或已因新版本重新要求審核。
2. G1～G7 都有具名 reviewer 完成，不是只打勾無說明。
3. H1～H8 均已重開官方來源或由明確 Caliburn test／mapping 支持。
4. 所有 Blocker 已 Addressed，且原 reviewer 或 Owner 確認處理有效。
5. Important 已修正，或有不影響本切片判斷的具體理由。
6. 所有 review conversations 都已解析；口頭結論已回寫文件。
7. 重大修改後受影響的舊 approval 已失效並完成 re-review。
8. Owner 明確寫下 `Approve for isolated spike`。

## 10. 核准後仍有第二道 Gate

本 packet 核准後的正確順序是：

```text
Approve for isolated spike
  → 只寫 Stage 0～3 的 spike implementation plan
  → isolated worktree 執行 deterministic contracts＋極小 Luna smoke
  → 產生包含失敗與成本的實驗報告
  → 對報告再做一次獨立 review
  → Owner 才決定是否寫 successor ADR
  → ADR Accepted 後才寫 production implementation plan
```

Spike 結果若推翻設計，回來修正文檔與重新審核；不能因為已投入開發時間就保留較差方案。

## 11. 官方審核方法來源

- [Google Engineering Practices — What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
- [Google Engineering Practices — The Standard of Code Review](https://google.github.io/eng-practices/review/reviewer/standard.html)
- [Microsoft Engineering Fundamentals — Design Reviews Checklist](https://microsoft.github.io/code-with-engineering-playbook/engineering-fundamentals-checklist/)
- [Microsoft Engineering Fundamentals — Reviewer Guidance](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/reviewer-guidance/)
- [GitHub Docs — About pull request reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews)
- [OpenAI — How evals drive the next chapter in AI for businesses](https://openai.com/index/evals-drive-next-chapter-of-ai/)
- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

## 12. 待填最終 verdict

- Product Owner：`Approve for isolated spike；包含 exact-inventory cap＋1 fail-closed fallback 與短跨輪 Memory smoke 增補`
- 獨立技術／證據 reviewer：`Hypatia — DR-MEM-T01 修正版 re-review passed`
- Adversarial／failure reviewer：`Bohr — DR-MEM-F02～F07 修正版 re-review passed；Sagan — DR-MEM-F01 新共識／fallback 修正版 re-review passed；Erdos — DR-MEM-O01／R1～R4 affected-section re-review passed`
- 未解 Blocker：`無`
- 本輪結果：`Approve for isolated spike`
