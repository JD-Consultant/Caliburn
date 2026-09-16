# JD-R002／MEM-L001：分層工作案例與工作理解 Memory 對齊

- 日期：2026-09-16
- Stage：**G7 分段施工；Owner 已確認產品語意與共同版本方向，Bundle authority foundation 已完成離線驗證**
- 取代：Q019 在 Caliburn 採用的「B1 固定訪談窗口詳記＋B2 只維護 knowledge／guide」產品映射
- 不取代：canonical 原始訪談、已校準主顧問 Prompt／Skills、背景通知語意、JD relational writer、既有 Saver／Store／CAS／receipt 證據及 `CTX-C001` 的非破壞式 compaction 原則

## 0. 本輪決策界線

```text
Topic ID: JD-R002／MEM-L001
Current stage: G7 segmented implementation
Binding product goal: 完整理解個別工作案例／任務／事件，再歸納穩定共同工作，最後產生客製化 JD
This turn's decision: B1、B2 的分層責任、各自 guide、共同 publication、C 即時更正語意，以及第一版 bundle／reference／tool authority 契約
Still open after second G7 slice: B2、C 與完整背景 job／dispatcher／A read path 依 §14 分段接線；B1 compaction 與正式 App 組裝仍待後續切片
Out of scope: 本輪不改 production authority、不呼叫模型、不修改正式資料、不做 provider／JD schema 選型
```

這次不是重新發明第二套工作理解 Memory，而是修正先前將「訪談窗口詳記」誤當成足以承接完整案例現況的產品映射。舊 Q019 程式與測試仍可作來源固定、checkpoint、不可變 artifact、stale、CAS 與 receipt 的工程證據；不能再用它們宣稱案例層產品效果已完成。

## 1. 產品資料鏈

```text
canonical 原始訪談
    ↕ 精確來源引用、必要時回查原話
完整工作案例／任務／事件層
    ↕ 歸納、驗證、更正、深入細節
穩定工作理解層
    ↓ 作為主要分析基礎，必要時向下回查
current JD
```

大括號內的前三層由 LLM 與 Runtime 管理，使用者不直接編輯。JD 是人與 LLM 共用相同業務邏輯編輯的正式工作稿。JD 撤回不倒退原始訪談、案例、工作理解或 Memory publication。

「完整」是工作相關資訊可保存、可找回及可更正的效果，不是每次把所有原話送給模型。原話保存所有實際往返；案例層保存工作目的、行動、角色與責任、條件、頻率、判斷、結果、例外、差異、更正與未確認事項；工作理解層保存跨案例可成立的穩定任務、責任、流程、交接、條件與能力。無關寒暄不必複製到案例層。

## 2. 兩個背景 Agent 採相同工作形狀、管理不同層級

| 角色 | 管理權責 | 主要輸入 | 正式產物 |
|---|---|---|---|
| A 主顧問 Agent | 訪談、釐清、按需回查、JD 工具與背景通知 | 對話、兩層 guide、相關案例／理解、current JD | 顧問回答、JD 操作、背景整理通知、必要的 C 修補要求 |
| B1 案例整理 Agent | 目前有效的完整工作案例／任務／事件 | 新 canonical 訪談範圍、案例 guide、相關目前案例、必要原話 | 修訂後案例內容、案例 guide、來源與本批變更資訊 |
| B2 工作理解 Agent | 從案例歸納的穩定共同工作理解 | B1 staged 案例變更、理解 guide、目前工作理解、相關案例與必要原話 | 修訂後工作理解、理解 guide、案例引用 |
| C 即時修補工具／無模型子圖 | 當輪已明確核實的案例或工作理解錯誤 | A 基於最新 publication 提出的受控修改、當輪原話 | 一次完整、原子、可對帳的 repair publication |
| Continuation compaction | 各 Agent 自己的 request-only 對話延續 | 實際準備送出的舊訊息與已完成工具 wave | 非權威 continuity summary；不進案例、理解或 JD basis |

B1 與 B2 都遵循：

```text
讀最新基準 → 看小型 guide → 找相關內容 → 按需深讀 → 比較新舊
→ staged 最小修改 → 驗證 → 版本條件保存
```

兩者的差異不是「一個只抽取、一個才會整理」，而是 B1 維護個別工作實況，B2 維護跨案例的穩定理解。

## 3. B1：持續維護完整案例層

B1 必須先讀案例小型 guide，辨認本批資料是在新增案例、補充既有案例、更正舊理解、描述工作後來變化，或仍無法確認。它按需讀取相關目前案例；需要精確證據才沿受控引用讀 canonical 原話。不能只因新來源提到相似名稱就建立重複案例，也不能把 A 案條件套到 B／C。

案例 guide 是 map，不是案例全文或證據。至少要能用名稱／別名、辨識詞、目前狀態、未確認事項及穩定案例身分找到對應內容。案例文件是目前有效內容；同一案例的後續補充與更正更新該內容，而不是把每個訪談窗口都當成另一份「目前案例」。

現有固定 source window、`NEW_SOURCE`／`CONTEXT_ONLY`、結構化抽取、checkpoint、拒答／截斷／格式處理與 runtime source reference 可以保留作 B1 的來源準備或候選步驟；普通 B1 的完成條件不再只是多存一對 `rollout_summary/raw_memory`，而是相關案例與案例 guide 已更新，或明確判定 no-op。

## 4. B2：由目前案例維護穩定工作理解

B2 以 B1 已 staged 的目前案例變更為主要增量入口，先讀理解 guide 與相關既有理解，再按需深入其他案例；仍不足時才沿案例引用讀原始訪談。它更新共同任務、責任、流程、交接、條件、能力、例外及未知，不把新案例重新摘要成覆蓋全部舊理解的正文，也不把多個相似案例的差異過早消除。

理解 guide 是工作理解的 map；工作理解必須引用支持它的案例身分與該 publication 中解析到的精確 artifact。若某項只在 CASE-A 成立，保留為案例差異或例外，不得擴成 A／B／C 的共同規則。

案例與工作理解是多對多關係：一個工作理解可以由多個案例支持，一個案例也可以影響多個工作理解。B1 staged 案例改變後，B2 的影響判斷不能只做「找出目前引用該案例的理解並換掉版本號」；它至少要同時處理：

1. 透過精確引用找出直接依賴該案例的既有工作理解；
2. 透過理解 guide、案例主題與必要的相關案例比較，判斷是否出現先前不存在的新穩定工作任務；
3. 對受影響範圍決定維持內容但重新驗證引用、修訂、拆分、合併、新增，或因支持不足而降級／移除；
4. 保留只在個別案例成立的條件與例外，不因其他案例相似就擴成共同規則。

B2 判定案例變更不影響工作理解時可以做**語意 no-op**：工作理解正文 artifact 可以重用，但 B2 仍須實際讀取新版相關案例、完成影響判斷，並讓新 publication 的精確引用／驗證基準對應新版案例。`no-op` 不表示 B2 未執行，也不允許舊理解未經重驗就把案例 artifact ID 機械改成新版。反過來，即使沒有任何既有理解引用本批案例，B2 仍可能建立新的工作理解；反向引用掃描只是影響入口，不是完整分析。

## 5. 一個共同的文件級 Memory publication

目前採用的 WORKING 方向是：B1 與 B2 不各自建立公開 version stream。每份文件只有一個正式 Memory head；一個 publication revision 選出一組可一致解析的 artifacts：

```text
Memory publication vN
├─ case guide
├─ current case artifacts
├─ work-understanding guide
├─ current work-understanding artifacts
└─ references／manifest
```

這裡的 `manifest` 是**邏輯上的版本內容清單**：它記錄「vN 這一版實際選用了哪些案例、理解、guide 與引用 artifact」。它可以由現有 publication record／head 所保存的 artifact references 承擔，不表示第一版一定要另建一張名為 manifest 的資料表或一份新檔案。用途是避免案例已是 v13、工作理解卻仍混用 v12 之類的半套發布；一次 CAS 成功後，整組引用才一起成為新的正式版本。

案例與理解具有跨版本不變的語意身分；每次內容保存產生不可變 artifact／digest。跨層引用在邏輯上同時包含：

- **穩定語意身分**，例如 `CASE-A`，供 guide、影響查找與目前內容導覽；
- **publication 解析出的精確 artifact**，例如 `CASE-A@r4`，記錄這一版工作理解實際依據的案例內容。

具體欄位與儲存位置見 §11；不要求把版本字串重複寫進工作理解正文。新版 publication 在邏輯上只替換有變動的 artifact，未變內容可以重用；但案例 artifact 改變時，B2 必須先依新版重新評估。若工作理解語意不變，可以重用其正文 artifact 並更新本 publication 的精確依據／驗證資料；若支持內容、範圍、條件或例外改變，就建立修訂後的工作理解 artifact。現在查找由穩定身分解析到該 publication 選定的內容；歷史重現則使用該歷史 publication 選定的精確 artifact 與原始來源 reference。

因此，current publication 不得留下無法解析的 dangling reference，也不得讓工作理解繼續以已被更正為錯誤的舊案例 revision 作為目前依據。案例合併、拆分或移除時，B2 必須先重新評估依賴它的理解並更新、改接有效案例或標示支持不足，完成後才能一起發布。真正的工作隨時間改變不是垃圾回收：若歷史差異對理解使用者工作仍有意義，應由案例／理解的時間語意表達，不能因「不再目前適用」就直接當成無引用垃圾。

第一版不實作 GC（garbage collection）：新版不再引用的舊 immutable artifact 暫時留在 Store，不立即物理刪除。這不是宣稱引用能讓誤刪永遠不可能，而是第一版尚未建立並驗證 reference-aware GC，因此先不加入自動物理刪除這條高風險路徑。正常讀取只跟隨目前 publication head，舊 artifact 不會自動進入模型 context，也不是要新增使用者可見的 Memory／JD 歷史功能。

截至 2026-09-16，OpenAI Codex 公開的 Memory 實作同樣具有分層導覽、supporting rollout references 與增量整理；它會在輸入淘汰時由 workspace diff 找出上層引用，只移除唯一由已刪輸入支持的 Memory，混合來源則保留仍有支持的部分，最後再修正上層摘要。它同時以全域整理鎖、成功 baseline、使用／新鮮度選擇與 retention prune 管理清理。這支持「引用感知整理」的方向，但 Codex 將 Memory 定位為輔助 recall，且公開實作沒有本產品 B1／B2 整組 publication 契約，因此不能直接把它的使用頻率淘汰規則套到完整工作案例。官方來源：[Codex consolidation template](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)、[Codex memories README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)、[Codex Memories 使用說明](https://learn.chatgpt.com/docs/customization/memories)。

日後只有出現可量測的儲存壓力，才另外設計 reference-aware GC：以仍有效的 publication、目前跨層引用及尚未結束的受控工作為 roots，沿引用確認可達內容，只回收超過保留界線且不可達的內部 revision，並在刪除前再次原子確認。canonical 原始訪談、目前 publication、仍被引用的證據，以及產品仍需保留的工作時間差異，不在可隨意清除的範圍。

普通背景流程為：

```text
正式 head v12
    ↓
B1 以 v12 建立 staged 案例更新，不先公開
    ↓
B2 讀 v12 理解＋B1 staged 案例，完成更新或 no-op
    ↓
驗證兩層、guide、引用與來源
    ↓
CAS：目前 head 仍為 v12 才一次發布完整 v13
```

B1 已完成但 B2 尚未完成／失敗時，A 繼續讀上一個完整 publication；B1 結果保留在原 durable job／staging，不得冒充已發布案例。這避免 A 在「案例已改、理解仍舊」的中間狀態產生 JD。

## 6. C：緊急更正與發布

使用者明確指出目前理解錯誤時，原話先保存並取得同文件不可變來源 reference。A 準備修補前必須確認最新 head；若與本回合目前讀取基準不同，先按需讀取新版受影響內容並重新評估，不能只替舊 patch 換版號。

C 直接使用同一個 Memory publication stream，不等待 B1／B2：

1. 從明確最新版本建立 staging。
2. 案例錯誤先修改受影響案例；名稱／別名／路由改變才修改案例 guide。
3. 若更正影響共同任務、責任或例外，同一次操作也修改工作理解；路由改變才修改理解 guide。
4. 每項修改引用當輪更正原話；不改其他無關案例，不改 canonical 對話。
5. 驗證案例、理解、guide、來源與跨層引用後，另存有變動 artifacts，重用未變內容。
6. 以本次實際依據的 `expected_revision` 做原子 CAS，成功才發布下一個完整版本並保存 receipt。
7. 成功後，本回合目前讀取基準更新為 C 實際產生的版本；後來背景再發布新版不會偷偷推進本回合。

若尚無 Memory publication，C 不從空白猜出第一版；保留本輪原話並讓已通知的 B1／B2 建立。若 CAS stale，這次任何 staged 修改都不生效；A 取得最新 head、按需重讀並重新決定。若提交結果不明，只以原 operation／receipt 對帳，不配置新 operation 重送。Memory 不隨 JD 撤回；錯誤的 repair 以後續新版本更正，不原地改寫歷史。

## 7. 並行與恢復

新的 B1 會讀目前案例，因此背景依據 v12 完成後若 C 先發布 v13，不能再沿舊規則只重跑 B2：

```text
B1／B2 依 v12 完成候選
    ↓
C 先發布 v13
    ↓
背景 CAS(v12) 被拒絕
    ↓
基於 v13 重新執行受影響的 B1 案例判斷
    ↓
B2 再基於新的 B1 結果與 v13 理解重整
```

不能把舊 B1 或 B2 結果改標新版後發布。相同 base 上的中斷可沿 durable checkpoint 續作；真正 stale 才建立新的語意 attempt，並沿既有有界步數／時間限制，不能無限重試或最後強制覆蓋。

## 8. Compaction 邊界

`CTX-C001` 的 runtime 判斷維持有效：是否 compaction 依套用既有摘要後、真正準備送出的完整 request 計算；只壓縮安全完成的舊訊息／工具 wave，保留當前輸入、未完成工具配對與固定任務原文。continuity summary 不是來源，不能寫入案例、理解或 JD basis。

原 `CTX-C001` 只需處理 A／B2，因當時 B1 是單次 structured extraction。B1 現改為可能多步讀寫的案例 Agent，G4 必須把 B1 納入相同非破壞式 context 原則；是否實際達門檻才執行，不因角色新增而每輪固定摘要。

主顧問在第一輪尚無 publication、背景尚未整理或一次無法問完所有線索時的 Focus／待追查事項，由 [CTX-W001 訪談 Working State](2026-09-16-consultant-interview-working-state-design.md)承接。它只是 A checkpoint 中的發布前工作面，不是第三層 Memory：B1／B2 不得把 item 文字當員工來源，仍從 canonical source 建立案例與理解；publication 完成後，A 必須按需讀相關新版再移除、保留或改寫 item，不能只因版本前進就自動宣告已解決。這補足「Memory 不會每回合更新」的恢復缺口，不改 B1／B2／C 的 authority 與單一 publication head。

## 9. 已知衝突與處理要求

| 衝突 | 現況 | 後續要求 |
|---|---|---|
| B1 責任 | `extraction.py` 只讀固定窗口並保存詳記／候選 | 保留可用來源接縫，重新設計為能讀案例 guide／相關目前案例並 staged 更新的 B1 Agent |
| Memory bundle | `MemoryArtifacts.save_memory()` 只保存 `knowledge.md`／`guide.md` | G4 定義同一 version 如何選出案例 guide、案例、理解 guide、理解與 references；不先假定一定新增 relational Case table |
| C 修改範圍 | `PATHS` 只允許兩個既有 Memory 檔 | 受控擴充到本次允許的案例與兩層 guide／理解；仍禁止任意路徑及跨文件修改 |
| 背景發布 | H4 舊流程把 B1 artifact 交 B2，由 B2 發布兩檔 Memory | 改為一個 durable B job 內 B1 staged → B2 staged → 一次完整 publication；舊 R1／R2 結果只作底層證據 |
| stale 重整 | 舊 B1 不讀 Memory，C 插入後通常只需 B2 重整 | 新 B1 依賴目前案例；stale 後 B1、B2 都要基於新 head 重新評估 |
| compaction | 現設計只有 A／B2 | 新 B1 多步 agent 納入同一 request-only 原則與受影響測試 |
| 跨層引用更新 | 現行 `knowledge.md`／`guide.md` 未表達多對多案例依賴、穩定身分與精確 artifact 的雙層引用 | G4 固定 reference contract 與影響查找；案例改變後 B2 必須重新分析既有理解與可能的新理解，禁止只換 artifact ID |
| 歷史 artifact 成長 | 現行 Store 無一般 GC | 第一版保留不再由 current head 選用的舊 immutable artifact，不新增自動 GC，也不讓正常回查掃描它們；長期只有出現可量測儲存壓力才重開 reference-aware 回收設計，canonical 原始訪談、有效 publication、仍被引用的證據與產品需保留的時間差異不得隨意刪除 |

上述衝突是已知設計／程式差距，不是授權實作者直接自行選 schema、改 Prompt 或宣稱舊測試已覆蓋。遇到會改產品效果、資料權責、引用可重現性或失敗語意的選擇，先提出具體衝突與最小方案。

## 10. G4 必須固定的代表性驗收

1. A／B／C 三個相似案例保留各自流程、責任、條件與例外；共同理解只歸納有足夠支持的穩定工作。
2. 後續補充 CASE-A 時更新同一案例，不新增重複的「目前案例」；CASE-B／C 不受污染。
3. 明確更正同時修正受影響案例與共同理解，兩層在同一 publication 可解析；原話與歷史版本仍可追查。
4. 工作真的隨時間改變時，目前內容依 §11.3 清楚區分先前與目前適用範圍，不能把歷史改寫成當時從未成立，也不能用 GC 代替語意修訂。
5. 一個工作理解由 CASE-A／B／C 共同支持，其中 CASE-B 改變時，B2 會重新分析整個受影響理解；依新內容可以維持、修訂、拆分或降低適用範圍，不能只替引用換版。
6. 新案例揭露新的穩定工作任務時，即使沒有任何既有工作理解反向引用它，B2 仍會建立新理解並更新 guide。
7. B1 更新案例而 B2 判定共同理解語意不變時，可以重用理解正文 artifact，但新 publication 必須保存已依新版案例重新驗證的精確引用／基準，且 current publication 沒有 dangling 或已失效引用。
8. 案例合併、拆分或移除時，所有受影響的目前工作理解先更新、改接有效支持或標示支持不足，再一起發布；不可留下只由淘汰案例支持的目前結論。
9. C 與背景競爭時先成功者成立；舊背景重跑 B1／B2，不能覆蓋更正或只換版本。
10. A 從兩層 guide 起步，按需讀理解、案例及原話；不全量重送，不把 compaction summary 當證據。
11. 另一文件的案例、guide、版本、來源或 staged job 不可讀取、引用或發布。

## 11. G4 第一版資料與引用契約

### 11.1 一個不可變 bundle，不新增另一套 Memory authority

第一版沿用現有 `MemoryVersion`／Store version 的邊界：每次候選保存產生一個不可變、文件 scoped 的完整 Memory bundle；`q019_document_memory_head` 仍只以一次 CAS 選出其中一個 bundle。這不是要求每次把全部 Memory 送給模型，模型讀取仍從小型 guide 起步、按需開啟個別內容。

第一版 Store 內部路徑固定為：

```text
/memory/manifest.json                       # Runtime 結構資料，不放入一般模型 context
/memory/cases/guide.md                      # B1 小型導覽
/memory/cases/items/{case_id}.md            # 一個目前案例一檔
/memory/understanding/guide.md              # B2 小型導覽
/memory/understanding/items/{understanding_id}.md
```

案例與工作理解正文使用 Markdown，而不是固定十幾欄的表格。它們須達成[完整工作分析指南](2026-09-09-complete-work-analysis-guide.md)與[資訊取捨研究](2026-09-07-work-case-and-understanding-information-selection.md)的效果，但不把分析面向誤作每筆必填 schema。`manifest.json` 則是 Runtime 產生與驗證的結構資料，不由模型直接編輯，也不是第三層 Memory、摘要或使用者可見歷史。

第一版可以把未變檔案以相同 bytes 複製進新 Store version；相同內容的 digest 不變，邏輯上仍是同一 artifact。是否做實體去重不是產品效果，也不列為第一切片前置。正常讀取只跟隨 head 指定的 bundle，不掃描舊 version。

### 11.2 穩定身分、精確 artifact 與 manifest 最小內容

`case_id`／`understanding_id` 是 Runtime 產生、在同一文件內穩定且不可由模型自訂的 opaque ID。名稱、標題、工具名與員工說法都可能改變，不能作主鍵。Runtime 也擁有路徑、bundle version、digest、文件 scope 與發布 revision。

manifest 至少保存：

```text
schema_version
document_id
base_publication_revision
base_memory_version_id
case_guide: path + digest
cases: case_id -> path + digest + canonical source references
understanding_guide: path + digest
understandings: understanding_id -> path + digest
understanding_case_bindings:
  understanding_id -> [{case_id, case_digest}]
supersessions:
  retired stable ID -> [current stable IDs]
```

`case_digest` 是候選 bundle 內實際選中的案例內容 digest。這使「UNDERSTANDING-X 引用 CASE-A」同時具有穩定身分與精確依據，不需要把 `CASE-A@r4` 字串複製進正文。head 的 publication revision 由 CAS 成功時配置；候選 manifest 只記自己依據的 `base_publication_revision` 與精確 `base_memory_version_id`，不能預先猜下一版號。發布交易必須同時確認目前 head 的 revision 與 MemoryVersion 都是這個 base，避免拿同版號下另一個未發布／錯誤 bundle 作為語意依據。

建立非首版候選時，Runtime 還必須持有該 base head 指定的精確 `MemoryVersion`，用它核對哪些穩定身分仍存在、哪些本批退出 current set；不能只拿一個版本數字從空白重建 bundle。每個退出 current set 的 ID 都要有 supersession／retirement 紀錄，且不能替仍屬 current 的 ID 偽造淘汰；若沒有後繼項目，replacement 清單可以為空。

案例正文需要保存足以回查的來源語意；正式 canonical source reference 由工具參數交 Runtime 驗證後寫入 manifest。工作理解只能引用候選 bundle 中存在的 `case_id`，Runtime 將它解析並固定成該 bundle 的 `case_digest`。guide 可以顯示穩定 ID、名稱／別名、辨識詞、目前狀態與未確認事項作導覽，但 manifest 才是路徑、digest 與跨層關聯的結構 authority。模型按需讀取一筆案例或理解時，Runtime 的 read 結果須連同該筆已驗證的 source references／case bindings 回傳；不是把整份 manifest 塞進每次 context，也不能只回正文而藏掉回查入口。

### 11.3 身分生命週期

- 同一真實案例的補充、更正或目前狀態變化：保留 `case_id`，建立新內容 artifact，並保留來源與時間語意。
- 新的獨立案例／事件／任務情境：建立新 `case_id`；不能只因名稱相似就覆蓋舊案例。
- 重複案例合併：選定一個目前身分，其他身分標為被取代；B2 先重整所有依賴，current manifest 不再把被取代身分當目前案例。
- 一個錯誤混合的案例拆分：建立能各自代表真實情境的新身分，舊身分退出 current set；B2 先重新判斷理解與引用。
- 工作隨時間真正改變：不得用刪除或 GC 假裝舊情況從未成立。正文清楚區分先前與目前適用範圍；是否仍屬同一案例依實際工作情境判斷，不用檔名或固定時間門檻自動決定。
- 工作理解同樣以語意責任為身分。措辭修正保留 ID；責任實際拆分／合併時以明確操作建立、保留或取代身分，不讓 Runtime 只憑文字相似度猜測。

## 12. G4 Agent 工具責任與正常資料流

### 12.1 工具傳達語意操作，不讓模型管理儲存細節

B1／B2 的模型輸入只包含 Runtime 已選定的 document scope、base revision、guide、相關內容及可用來源／案例 ID。模型可以提出下列效果，但不填 `document_id`、版本號、digest、實體路徑、時間戳或 operation ID：

| Agent | 允許的語意效果 | Runtime 責任 |
|---|---|---|
| B1 | create／revise／supersede 案例；必要時修訂案例 guide；明確 no-op | 配置／驗證 ID，限制可改範圍，驗證 canonical source，建立 staged artifacts 與變更集 |
| B2 | create／revise／supersede 工作理解；選擇支持案例；必要時修訂理解 guide；語意 no-op | 解析 case IDs 到候選 digests，建立多對多 bindings，驗證所有依賴與 guide 路由 |
| C | 對最新 head 的既有目標做受控 revise；必要時同次修改案例與理解 | 套用 scope、最新版本檢查、來源驗證、完整 bundle 驗證、CAS 與 receipt |

精確函式名稱可以在施工切片依現有框架公開 API 決定；上述輸入／輸出權責不可改。單純狀態變更不要求模型重填整份物件，未提及的既有項目保持不變；remove／supersede 也不能與 upsert 用互相矛盾的欄位同時表達。

### 12.2 一次背景工作的完整流程

```text
Runtime 固定 document_id、source range、base head／revision
    ↓
載入 base manifest 與 case guide
    ↓
B1 按需讀相關案例／原話，產生 staged case changes＋case guide
    ↓
Runtime 建立候選 case set 與 B1 change set
    ↓
B2 讀 understanding guide、直接依賴、相關鄰域與 staged cases
    ↓
B2 重新驗證／修訂／拆分／合併／新增／supersede，或明確 semantic no-op
    ↓
Runtime 產生 understanding bindings 與完整 candidate manifest
    ↓
純程式驗證 bundle、來源、guide、跨層引用、document scope、processed source
    ↓
以 base revision 一次 CAS 發布；成功才前進 source cursor
```

「相關鄰域」由 guide、直接 bindings、本批案例主題／辨識詞及 B2 的按需讀取共同形成；它不是 Runtime 以關鍵詞直接決定工作理解。即使沒有既有反向 binding，B2 仍須判斷新案例是否揭露新工作理解。

### 12.3 發布前必須全部成立

1. manifest 中每個 path／digest 都與實際 immutable bytes 相符，且只屬本文件。
2. 兩份 guide 引用的目前 ID 都存在；current item 也有可導覽入口，不留下孤兒內容。
3. 每個案例的 canonical source reference 可由現有 SourceReader 驗證；continuity summary／Working State 不得成為來源。
4. 每個工作理解的支持案例都存在於同一 candidate bundle，binding digest 與候選案例 bytes 相符。
5. 本批改變、合併、拆分或退出 current set 的案例，都有 B2 的受影響處理結果；不能只更新 B1 就發布。
6. B2 semantic no-op 仍留下對新版案例的精確 binding；若沒讀取並判斷新版相關內容，不能宣稱 no-op。
7. source cursor 只涵蓋本次已成功處理的 canonical 範圍；C repair 不前進背景 cursor。
8. 任何一項失敗，整個候選不得成為 head。

## 13. 錯誤、恢復、成本與明確不做事項

| 情況 | 第一版行為 |
|---|---|
| 模型輸出／工具參數可修正錯誤 | 保留同一 base 與 checkpoint，在既有有界步數內回報具體錯誤供 Agent 修正；不部分發布 |
| B1 完成、B2 失敗或取消 | 保留 durable job／staging 供同 base 恢復；A 繼續讀舊 head，source cursor 不前進 |
| CAS stale | 舊候選完整拒絕；取得新 head，重新執行受影響 B1 與 B2 語意判斷，不能只換版本／digest |
| 提交結果不明 | 使用同一 operation ID 與 request digest 查 receipt／重送同一請求；不建立另一個可能重複的 operation |
| artifact／source 暫時不可讀 | 不發布；保存可診斷錯誤，不把缺資料當空白或 no-op |
| 達到重試／時間／成本上限 | 任務進入既有 blocked／failed 狀態，保留上一個正式 head；不強制覆蓋 |

模型成本只來自真正需要的 B1／B2 工作；manifest 組裝、digest、scope、引用完整性與 CAS 都是純程式責任，不新增判斷模型。B1／B2 的 compaction 仍只在實際 request 超過門檻時執行，不固定每次多叫一次摘要模型。

第一版明確不做：文件封存、使用者可見 Memory history、自動 GC、實體去重最佳化、另一套 relational Case authority、讓 Web 重算引用不變量、以 embedding／RAG 取代 guide、讓 continuity summary 或 Working State 變成證據、以及因本設計重做已校準 Prompt／Skills／JD relational writer。

## 14. 最小施工順序

為避免又同時重做 Agent、Prompt、背景排程與 UI，施工拆成下列可獨立驗證的窄切片：

1. **Bundle authority foundation（已完成）：**已擴充 Memory bundle／manifest 的資料型別、保存、讀取、驗證及 publication；synthetic fixtures 已驗證 stable IDs、來源、digest、跨層 bindings、supersession、文件隔離、精確 bundle base、完整 CAS、receipt、tamper、stale 與舊 receipt digest 相容。舊兩檔 Memory 保持相容；零模型、零 Prompt、零 dispatcher、零 UI。`consultant-memory` 全套 162 項測試及 compileall 通過。
2. **B1 case maintainer（前兩片已完成）：**沿現有來源固定／checkpoint／錯誤處理，接上案例 guide、相關案例讀取與受控語意操作；已離線測新增、補充、更正、重複、拆分／合併候選、no-op、多窗口、完成界線、transport resume、步數額度及 incomplete／refusal。
3. **B2 understanding maintainer＋完整背景 job：**接 staged case change set、多對多影響查找、新理解發現與一次發布；驗證 B1 成功而 B2 失敗不外露、semantic no-op 與 stale 後 B1／B2 重整。
4. **C repair：**把現有兩檔 patch 限制改成穩定目標 ID 的受控修訂，驗證同次案例／理解更正、來源、CAS、receipt 及本回合基準推進。
5. **Dispatcher／A read path／compaction／App journey：**最後接回既有通知與背景恢復，讓 A 從兩層 guide 按需回查；補 B1 的 request-only compaction 與完整 App 驗收。未受影響的 H4／CTX-C001 證據直接沿用。

第一切片不得先改 B1／B2 Prompt 或正式 dispatcher，也不得把舊 `knowledge.md` 自動解讀成已符合新案例／理解 schema。專案目前沒有舊正式使用者資料搬移需求，因此只保留明確的不相容錯誤；不做猜測式 migration。

## 15. Closure

- **Decision：**B1 成為目前案例／任務／事件層的整理 Agent 並擁有小型 guide；B2 以目前案例維護穩定工作理解及其 guide。兩者暫採同一文件級 Memory publication，B1 staged 後由 B2 完成或 no-op，再一次發布。C 可在明確更正時直接原子發布同一完整版本。
- **Status：**G7 分段施工；bundle authority foundation、B1 staged state／語意工具及固定 source window Agent graph 已完成。B2／C、B1→B2 共同發布與正式 App 接線尚未切換，不是完整產品已完成或 production authority 已切換。
- **Why：**產品需要記住完整個別工作實況與可修訂的穩定共同理解，並透過分層引用產出貼合員工的 JD；歷史窗口詳記＋單一正文不能充分表達「目前完整案例」。
- **Sources：**Owner 2026-09-16 對話裁決；[Codex Memories](https://learn.chatgpt.com/docs/customization/memories)、[Codex consolidation template](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)與[Codex memories README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)只支持分層、引用與引用感知整理的官方事實，不替本產品決定 publication schema；既有 Q019／重抽／publication／H4 實作證據只作可沿用工程基礎。
- **Affected：**`current-decisions.md`、`packages/consultant-memory` 的 bundle／Memory／publication／reference 基礎、B1 Prompt／Agent graph、產品核心目標、Q019 Memory、H4 舊 B1／B2 計畫與 `CTX-C001` 的 B1 適用範圍；前兩片沒有改 dispatcher、B2／C、UI、provider credential 或正式入口。
- **Reopen：**Owner 改變案例完整度／更正效果；G4 發現共同 publication 無法在現有 Store／Saver 契約下可靠完成；或代表性測試證明兩層一致性／回查成本不能同時成立。
- **Next gate：**B1 前兩片已完成；下一個獨立工作單位先固定 B2 understanding maintainer 的 staged state／語意工具與多對多影響分析，再接 B1→B2→完整 bundle publication。不在同一單位接 dispatcher、C、compaction、UI 或真模型；第一版沿用「舊 immutable artifact 暫留、不做 GC」。
