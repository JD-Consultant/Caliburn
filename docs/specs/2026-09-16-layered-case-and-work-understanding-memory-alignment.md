# JD-R002／MEM-L001：分層工作案例與工作理解 Memory 對齊

- 日期：2026-09-16
- Stage：**G3 WORKING；Owner 已確認產品語意與暫定共同版本方向，下一步是 G4 可驗證設計**
- 取代：Q019 在 Caliburn 採用的「B1 固定訪談窗口詳記＋B2 只維護 knowledge／guide」產品映射
- 不取代：canonical 原始訪談、已校準主顧問 Prompt／Skills、背景通知語意、JD relational writer、既有 Saver／Store／CAS／receipt 證據及 `CTX-C001` 的非破壞式 compaction 原則

## 0. 本輪決策界線

```text
Topic ID: JD-R002／MEM-L001
Current stage: G3 WORKING
Binding product goal: 完整理解個別工作案例／任務／事件，再歸納穩定共同工作，最後產生客製化 JD
This turn's decision: B1、B2 的分層責任、各自 guide、共同 publication 與 C 即時更正語意
Still open for G4: artifact/path/schema、工具契約、既有程式遷移切片；第一版保留舊 immutable artifacts、不做 GC，長期保存上限不是目前施工阻塞
Out of scope: 本輪不改程式、不呼叫模型、不修改正式資料、不做 provider／Prompt／JD schema 選型
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

理解 guide 是工作理解的 map；工作理解必須引用支持它的案例身分與精確 artifact。若某項只在 CASE-A 成立，保留為案例差異或例外，不得擴成 A／B／C 的共同規則。B2 判定案例變更不影響工作理解時可以 no-op，但這個判斷仍屬同一背景工作的已完成步驟。

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

案例與理解具有跨版本不變的語意身分；每次內容保存產生不可變 artifact／digest。新版 publication 只替換有變動的 artifact，未變內容可以重用。現在查找可由穩定身分解析到該 publication 選定的內容；歷史重現則使用精確 artifact 身分與原始來源 reference。

第一版不實作 GC（garbage collection）：新版不再引用的舊 immutable artifact 暫時留在 Store，不立即物理刪除。正常讀取只跟隨目前 publication head，因此舊 artifact 不會自動進入模型 context，也不是要新增使用者可見的 Memory／JD 歷史功能。日後只有出現可量測的儲存壓力，才另外設計「哪些未被任何有效 publication／引用使用的內部 artifact 可以安全回收」；canonical 原始訪談與仍被引用的證據不在可隨意清除的範圍。

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
| 歷史 artifact 成長 | 現行 Store 無一般 GC | 第一版保留不再由 current head 選用的舊 immutable artifact，不新增 GC，也不讓正常回查掃描它們；長期只有出現可量測儲存壓力才重開安全回收設計，canonical 原始訪談與仍被引用的證據不得隨意刪除 |

上述衝突是已知設計／程式差距，不是授權實作者直接自行選 schema、改 Prompt 或宣稱舊測試已覆蓋。遇到會改產品效果、資料權責、引用可重現性或失敗語意的選擇，先提出具體衝突與最小方案。

## 10. G4 必須固定的代表性驗收

1. A／B／C 三個相似案例保留各自流程、責任、條件與例外；共同理解只歸納有足夠支持的穩定工作。
2. 後續補充 CASE-A 時更新同一案例，不新增重複的「目前案例」；CASE-B／C 不受污染。
3. 明確更正同時修正受影響案例與共同理解，兩層在同一 publication 可解析；原話與歷史版本仍可追查。
4. 工作真的隨時間改變時，目前內容更新，但不能把歷史改寫成當時從未成立；精確呈現方式仍待 G4 固定。
5. B1 更新案例而 B2 判定共同理解不變時，可以重用理解 artifact，最後仍只發布一個完整新版。
6. C 與背景競爭時先成功者成立；舊背景重跑 B1／B2，不能覆蓋更正或只換版本。
7. A 從兩層 guide 起步，按需讀理解、案例及原話；不全量重送，不把 compaction summary 當證據。
8. 另一文件的案例、guide、版本、來源或 staged job 不可讀取、引用或發布。

## 11. Closure

- **Decision：**B1 成為目前案例／任務／事件層的整理 Agent 並擁有小型 guide；B2 以目前案例維護穩定工作理解及其 guide。兩者暫採同一文件級 Memory publication，B1 staged 後由 B2 完成或 no-op，再一次發布。C 可在明確更正時直接原子發布同一完整版本。
- **Status：**G3 WORKING；不是程式已完成或 production authority 已切換。
- **Why：**產品需要記住完整個別工作實況與可修訂的穩定共同理解，並透過分層引用產出貼合員工的 JD；歷史窗口詳記＋單一正文不能充分表達「目前完整案例」。
- **Sources：**Owner 2026-09-16 對話裁決；既有 Q019／重抽／publication／H4 實作證據只作可沿用工程基礎。
- **Affected：**`current-decisions.md`、產品核心目標、Q019 Memory、H4 舊 B1／B2 計畫、`CTX-C001` 的 B1 適用範圍；程式尚未修改。
- **Reopen：**Owner 改變案例完整度／更正效果；G4 發現共同 publication 無法在現有 Store／Saver 契約下可靠完成；或代表性測試證明兩層一致性／回查成本不能同時成立。
- **Next gate：**先做現有 artifact／publication／C／dispatcher 的差距表與最小 G4 設計；裁決尚未回答的案例身分與時間變化表達，再另寫施工切片。第一版沿用「舊 immutable artifact 暫留、不做 GC」，不把長期回收設計列為接線前置。遇到衝突先回報，不沿 H4 舊步驟直接開工。
