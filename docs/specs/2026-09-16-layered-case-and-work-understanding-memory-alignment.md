# JD-R002／MEM-L001：分層工作案例與工作理解 Memory 對齊

- 日期：2026-09-16
- Stage：**G7 分段施工；package 完整背景 workflow、App A 分層讀取、App B1／B2 request-only compaction、正式 role factory 及 managed callback 已完成離線驗證；下一 gate 為 layered C**
- 取代：Q019 在 Caliburn 採用的「B1 固定訪談窗口詳記＋B2 只維護 knowledge／guide」產品映射
- 不取代：canonical 原始訪談、已校準主顧問 Prompt／Skills、背景通知語意、JD relational writer、既有 Saver／Store／CAS／receipt 證據及 `CTX-C001` 的非破壞式 compaction 原則

**2026-09-17 Owner 引用精確化：**B1 可按需查閱同文件已安全完成的 canonical 訪談，B2 可按需查閱 candidate 中所有目前案例；required／impact 集合只是最低驗收與優先提示，不是閱讀權限上限。案例來源沿用 source owner 在固定 checkpoint 簽發的 `purpose="source"` 完整訪談交換，不使用模型填寫的文字 offset；一筆 `source` 現已包含該輪使用者回答與最接近的前一則公開顧問問題。相同回合可支持多個案例，一個案例可引用多個回合；案例及工作理解 revise／split／merge／retire 時都必須重新分配仍真正支持目前內容的引用。多筆引用交給 LLM 或人閱讀時，必須由 source owner 依 canonical message order 排列，不能依 reference、UUID 或時間戳推測順序；時間戳第一版不進模型 context。模型只選 Runtime 提供的 attempt-scoped `evidence_key`，不填 signed reference、全域輪次或 offset；正式 artifact 仍保存 signed references。引用施工 Tasks 1–6 已淘汰「凡本次改動就自動附整批 `window`」、補上 bundle owner-order 再驗證、讓 B2 用 case-bound key 按需分頁核對原話，並完成文件與 fresh 回歸收尾；後續 package workflow 已把 B1／B2 串成同一 publication，App dispatcher、真 PostgreSQL 新程序資源組裝與離線接合亦已有證據。精確施工見[引用施工計畫](../plans/2026-09-17-interview-evidence-citations.md)、[完整背景 Workflow 設計](2026-09-17-layered-memory-background-workflow-design.md)與[參數權責審核](2026-09-17-model-runtime-parameter-ownership-review.md)。

**2026-09-17 Owner 舊格式退役：**正式新 App 只支援本文件定義的分層 Memory bundle。舊 `knowledge.md`／`guide.md`、模型填寫 `path＋diff` 的 C 契約及通用檔案讀取路徑不再保留產品相容層；沒有舊正式使用者資料，因此不做猜測式 migration、雙寫或雙格式 adapter。既有 legacy 程式與測試只保留為當時工程證據，並在 layered C 窄切片中有界移除或隔離；下文較早的「相容」敘述均由本決定取代。

**2026-09-17 Owner C 修補邊界：**C 只修訂已讀、可唯一定位，且使用者已在當輪或已核對的 canonical 原話中明確更正的既有案例／工作理解，不建立新案例或新工作理解，也不代做 B1／B2 的拆分、合併或廣泛跨案例分析。互相矛盾但尚未裁決的原話、較新敘述、一般補充或模型推測不等於更正；A 必須先按 canonical 順序核對目前內容與相關完整訪談引用，仍不清楚就詢問並保留未解狀態。案例修訂保存提供明確更正的完整訪談 source reference；工作理解只引用案例 stable ID 與候選 bundle 中的精確 digest，不直接引用原話。真正新內容由 canonical conversation／Working State 暫時承接，再交 B1／B2 建立完整分層引用。這將 OpenAI 公開的「live update 修正 stale Memory／依使用者要求更新」與背景 extraction／consolidation 分工映射到本產品；兩層引用與原子 bundle 仍是 Caliburn 契約，不冒充供應商原生行為。[OpenAI Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)、[OpenAI Codex Memories](https://learn.chatgpt.com/docs/customization/memories)。

## 0. 本輪決策界線

```text
Topic ID: JD-R002／MEM-L001
Current stage: G7 segmented implementation
Binding product goal: 完整理解個別工作案例／任務／事件，再歸納穩定共同工作，最後產生客製化 JD
This turn's decision: B1、B2 的分層責任、各自 guide、共同 publication、C 即時更正語意，以及第一版 bundle／reference／tool authority 契約
Still open after current G7 slices: C bundle repair、provider／自然模型驗證、完整瀏覽器 App journey 與 production authority 切換
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
| C 即時修補工具／無模型子圖 | 當輪已明確核實、可唯一定位且需立即修正的既有案例或工作理解錯誤 | A 已讀最新 publication、相關目前內容與必要原話後提出的受控 revise | 一次完整、原子、可對帳的 repair publication；不建立新案例／理解 |
| Continuation compaction | 各 Agent 自己的 request-only 對話延續 | 實際準備送出的舊訊息與已完成工具 wave | 非權威 continuity summary；不進案例、理解或 JD basis |

B1 與 B2 都遵循：

```text
讀最新基準 → 看小型 guide → 找相關內容 → 按需深讀 → 比較新舊
→ staged 最小修改 → 驗證 → 版本條件保存
```

兩者的差異不是「一個只抽取、一個才會整理」，而是 B1 維護個別工作實況，B2 維護跨案例的穩定理解。

## 3. B1：持續維護完整案例層

B1 必須先讀案例小型 guide，辨認本批資料是在新增案例、補充既有案例、更正舊理解、描述工作後來變化，或仍無法確認。它按需讀取相關目前案例及同文件已安全完成的 canonical 訪談；本次新增範圍是工作觸發與 processed-source 邊界，不是閱讀權限邊界。不能只因新來源提到相似名稱就建立重複案例，也不能把 A 案條件套到 B／C。

案例 guide 是 map，不是案例全文或證據。至少要能用名稱／別名、辨識詞、目前狀態、未確認事項及穩定案例身分找到對應內容。案例文件是目前有效內容；同一案例的後續補充與更正更新該內容，而不是把每個訪談窗口都當成另一份「目前案例」。

主顧問通知背景整理後，Runtime 固定通知範圍內尚未處理的完整 canonical 訪談 batch；這個 batch 才是 B1 的語意整理與來源單位。實際組裝後能在 request 預算內完整提供時直接整批交付，不因固定字數主動切成多個產品單位。只有來源交付或模型限制確實需要時，來源 owner 才可將同一 batch 分頁成一個或多個 `NEW_SOURCE`／`CONTEXT_ONLY` 讀取窗口；所有窗口仍屬同一 Agent attempt 與同一 B1 stage，不各自產生案例、完成結果或 publication。既有 checkpoint、拒答／截斷／格式處理及 runtime source reference 可繼續作底層能力；普通 B1 的完成條件不再只是多存一對 `rollout_summary/raw_memory`，而是整批相關案例與案例 guide 已更新，或明確判定 no-op。

## 4. B2：由目前案例維護穩定工作理解

B2 以 B1 已 staged 的目前案例變更為主要增量入口，先讀理解 guide 與相關既有理解，再按需深入 candidate 中任何目前有效案例；Runtime 推導的 required／directly affected IDs 是最低必讀集合，不是可讀集合上限。仍不足時才沿案例引用讀原始訪談。它更新共同任務、責任、流程、交接、條件、能力、例外及未知，不把新案例重新摘要成覆蓋全部舊理解的正文，也不把多個相似案例的差異過早消除。

理解 guide 是工作理解的 map；工作理解必須引用支持它的案例身分與該 publication 中解析到的精確 artifact。若某項只在 CASE-A 成立，保留為案例差異或例外，不得擴成 A／B／C 的共同規則。

案例與工作理解是多對多關係：一個工作理解可以由多個案例支持，一個案例也可以影響多個工作理解。B1 staged 案例改變後，B2 的影響判斷不能只做「找出目前引用該案例的理解並換掉版本號」；它至少要同時處理：

1. 透過精確引用找出直接依賴該案例的既有工作理解；
2. 透過理解 guide、案例主題與必要的相關案例比較，判斷是否出現先前不存在的新穩定工作任務；
3. 對受影響範圍決定維持內容但重新驗證引用、修訂、拆分、合併、新增，或因支持不足而降級／移除；
4. 保留只在個別案例成立的條件與例外，不因其他案例相似就擴成共同規則。

B2 判定案例變更不影響工作理解時可以做**語意 no-op**：工作理解正文 artifact 可以重用，但 B2 仍須實際讀取新版相關案例、完成影響判斷，並讓新 publication 的精確引用／驗證基準對應新版案例。`no-op` 不表示 B2 未執行，也不允許舊理解未經重驗就把案例 artifact ID 機械改成新版。反過來，即使沒有任何既有理解引用本批案例，B2 仍可能建立新的工作理解；反向引用掃描只是影響入口，不是完整分析。

B2 沿已讀案例的 canonical reference 按需核對原話時，若只是在補足形成共同理解所需的細節，仍由 B2 繼續分析；若原話證明 B1 案例在本人責任、條件、流程、例外、時間範圍、案例切分或關鍵來源上有會改變工作理解的實質錯誤／缺漏，B2 不得直接修改案例，也不得繞過錯誤案例產生看似正確的工作理解。它應以結構化 `case_rework_required` 結束目前 attempt，至少指出受影響 `case_id`、已實際讀取的精確 source reference 與問題理由；這是 Runtime 控制／診斷資料，不是新 Memory 或員工證據。

上層背景工作收到此結果後，不發布目前 B1／B2 staging；它以同一 canonical batch 與 base 建立新的有界 B1 attempt，讓 B1 自行重讀原話並修正案例，再建立新的 B2 attempt。舊 B2 已做的修改只留作執行紀錄，不能直接搬到新 attempt 或換版本重送。第一版每個背景工作最多自動退回 B1 一次；再次發現實質 B1 問題時進入可診斷的 blocked／failed 狀態，保留上一個正式 head，不無限循環。

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

C 是例外性的 live repair，不是每輪寫 Memory 的正常路徑。只有下列條件全部成立才能准入：

1. A 已從本回合目前基準按需讀取受影響的既有案例／工作理解，並沿其引用依 canonical 順序讀取足以判斷的完整訪談交換；guide 或較新的單句不能代替深讀。
2. 使用者已在當輪或已核對的 canonical 原話中明確說清楚目前哪個既有內容錯誤、正確內容及適用範圍；若歷史原話彼此仍衝突，不能由模型自行判斷哪句才是更正。目標 stable ID 必須唯一。
3. 當輪後續推理或 JD 操作確實需要修正版，且受影響範圍可以有界、完整處理；不能只修案例卻留下已知錯誤的直接依賴理解。
4. 這不是一般新增資訊、真正的新案例／新工作理解、案例拆分／合併，或需要廣泛比較才能判斷的變化。

只出現新舊衝突、使用者補充另一個條件、較新一句話或模型覺得舊內容可疑時，A 不得呼叫 C，也不得依 recency／語氣／confidence 選邊。它先保存原話，核對相關引用並向使用者確認「哪個內容錯誤、是否只是不同案例／條件、是否為後來的工作變化」；未解部分留在 Working State，必要時交 B1／B2 反覆整理。工作真的隨時間改變時，修訂目前適用內容但保留先前適用語意，不把歷史改寫成從未成立。

准入後，若明確更正來自當輪，該輪原話先保存並取得同文件不可變來源 reference；若來自既有 canonical 原話，沿用 source owner 已驗證的 reference。A 準備修補前必須確認最新 head；若與本回合目前讀取基準不同，先按需讀取新版受影響內容及必要引用並重新評估，不能只替舊修改換版號。

C 直接使用同一個 Memory publication stream，不等待 B1／B2：

1. 從明確最新版本建立 staging。
2. 只 revise 已讀且可唯一定位的 existing stable IDs。案例錯誤先修訂受影響案例；名稱／別名／路由改變才修改案例 guide。案例的 source reference 集合納入提供明確更正的 reference，保留仍支持目前內容的舊引用，只移除已不再支持目前內容的引用。
3. 若更正明確影響既有共同任務、責任或例外，而且所有直接受影響的既有理解都能完整判斷，同一次操作處理它們：正文已不正確就 revise；正文仍正確則明確 revalidate 並刷新修訂後案例 digest，不製造假正文變更。路由改變才修改理解 guide。工作理解只綁定同一候選 bundle 中的 `case_id＋case_digest`，不能越層把當輪原話保存成理解引用。若既有案例不足以支持理解處理，或影響過廣／不明，就不做部分 C publication，改交 B1／B2。
4. 不建立新案例／新工作理解，不自行 split／merge／supersede，也不改其他無關內容或 canonical 對話。真正新內容即使當輪可供 A 理解或編輯 JD，仍由 canonical conversation／Working State 保存，之後由 B1 建案例、B2 建立或修訂理解。
5. 驗證案例、理解、guide、來源與跨層引用後，另存有變動 artifacts，重用未變內容。
6. 以本次實際依據的 `expected_revision` 做原子 CAS，成功才發布下一個完整版本並保存 receipt。
7. 成功後，本回合目前讀取基準更新為 C 實際產生的版本；A 只按需重讀受影響內容與 guide 確認一次，結果正確就停止修補。後來背景再發布新版不會偷偷推進本回合。

若尚無 Memory publication、沒有唯一的既有目標，或只是發現真正遺漏的新工作，C 不從空白猜出第一版，也不為了立即保存而擴張成 B1／B2。保留本輪原話與必要 Working State，讓已通知的 B1／B2 建立；當輪 JD 若已有明確原話依據，仍沿 JD 自己的業務與來源規則處理，不以 Memory 先寫成功作前置。若 CAS stale，這次任何 staged 修改都不生效；A 取得最新 head、按需重讀並重新決定。若提交結果不明，只以原 operation／receipt 對帳，不配置新 operation 重送。Memory 不隨 JD 撤回；錯誤的 repair 以後續新版本更正，不原地改寫歷史。

### 6.1 C repair 對後續背景 B2 的影響接力

C 當次 publication 必須已滿足 §6 的完整一致性；以下接力不能拿來允許 C 只修案例、留下已知錯誤理解，或把本應交背景的廣泛重整拆成「先部分修、以後再說」。它處理的是另一個增量缺口：C 已安全修好目前 bundle 後，下一次正常背景工作仍要能看到這次上游改變，避免 B1 因案例目前已正確而回 `no_op`，使 B2 只看本次 B1 change set 而漏掉 repair 前的依賴。

第一版不新增 `pending`／`held` Memory、持久 watermark、queue、事件表或第二套 dependency registry。現有 publication receipt 與 immutable bundle lineage 已足以提供 durable delta：

1. 背景工作固定 base head 後，以最近一次成功 `kind="consolidation"` 的 **result revision** 作為先前 B1→B2 已完成邊界；若沒有則從 revision 0 起算。
2. Runtime 讀取該邊界之後、固定 base revision 以前（含）的 repair receipts。每筆 receipt result bundle 的 manifest 已保存精確 `base_publication_revision＋base_memory_version_id`，因此可比較修補前、修補後兩份正式內容，不依模型重述或目前 guide 猜測。
3. repair impact 至少包含：digest 改變的目前案例；這些案例在舊 manifest 與新 manifest 中直接綁定的工作理解；正文 digest 或完整 case-binding set 被 C 改變的既有理解。**舊 binding 必須參與**，否則 C 解除 `CASE-C → UNDERSTANDING-U` 後，下一輪會因目前圖上已沒有該邊而找不到 U。
4. Runtime 將 repair impact 與本次 B1 semantic changes 推導出的 impact 取聯集，作為 B2 的最低必讀案例與最低必處理理解。這仍只是必讀下限，不縮小 B2 從 case guide 按需讀取任何目前案例的既有權限。
5. B1 `no_op` 不會清除 repair impact。B2 必須實際讀取這些目前案例，並 revise／revalidate／split／merge／retire 受影響理解，或在讀取後作符合既有完成契約的語意處理；不能只把舊結果換成新版 digest。
6. 完整 B1→B2 候選成功 CAS 後，其 consolidation receipt result revision 自然成為後續新邊界。若工作 blocked、失敗或因 stale 未發布，沒有新的成功 consolidation receipt，原 repair receipts 仍會在基於新版重做時被選中。

案例不需要為了通過檢查而強制綁到某個工作理解。若修訂後的案例目前只代表個別差異、尚不足以形成穩定共同工作，它仍是 current case，並由現有 case guide「每個目前案例恰有一個路由」的不變量保留可發現性；後續新案例進入時，B2 仍從完整 case guide 與相關鄰域按需比較。整份工作的全面涵蓋沿 §10 與完整工作分析指南的語意檢查，不新增 exact coverage ID、第二個 verifier 或每案 `held` schema。

這個做法映射成熟系統的共同工程原則，但精確欄位仍是 Caliburn 既有契約：Google Bazel Skyframe 會從舊依賴圖失效 reverse dependencies，重算值不變時再 change-prune；Google Spanner change streams 將資料變更與 change record 原子保存並由 consumer checkpoint；OpenAI／Anthropic 則分開持久 Memory 與 active context，採 immutable version／條件更新及按需讀取。它們沒有公開本產品 B1／B2／C schema，因此不冒稱 repair impact ID 是廠商標準，也不採完整 Event Sourcing。[Bazel Skyframe](https://bazel.build/versions/8.5.0/reference/skyframe)、[Google Spanner change streams](https://docs.cloud.google.com/spanner/docs/change-streams)、[OpenAI Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)、[Anthropic Managed Agent Memory](https://platform.claude.com/docs/en/managed-agents/memory)、[Microsoft Event Sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)

**2026-09-18 實作結果：**上述接力已在 package 完成，不新增持久欄位或 Agent。Runtime 用既有 consolidation／repair receipts 與 immutable manifests 推導 impact，B2 stage 只沿用原 required-ID gate；同 attempt 不可換集合，stale 則由既有 outer workflow 以新 base 重算。A/B/C→U 反例已覆蓋「C 修訂 C、解除 C→U、下一批 B1 no-op、B2 仍讀 C 並處理 U」；package 全套 **276 passed**、相鄰 App 指定回歸 **15 passed**、兩側 compileall 成功。這只完成背景接力，§6 的 layered C 寫入工具仍是下一個獨立 gate。

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

`CTX-C001` 的 runtime 判斷維持有效：是否 compaction 依套用既有摘要後、真正準備送出的完整 request 計算；只壓縮安全完成的舊互動，保留當前輸入與未完成工具配對。對 B1 而言，正常的一個完整 canonical 訪談 batch 若可在一次 request 內交付並完成，就不固定執行 compaction。只有實際使用多個來源窗口且後續 request 達門檻時，Runtime 才可將已完整交給 B1、對應模型／工具 wave 已安全完成且 checkpoint 已推進的**舊窗口**納入 continuity compaction；尚未完整處理的最新窗口絕對不得摘要、截斷、替換或當成可丟棄訊息。這項資格沿既有 `window_position`／graph 完成邊界判定，不新增模型填寫的 `processed` 欄位，也不以「是否已被某案例引用」作唯一判準。canonical 訪談、signed references 與 evidence registry 始終完整保留；summary 只作後續工作 Context，不能冒充員工原話、寫入案例／理解／JD basis。B1 若需要精確細節，仍沿既有按需來源讀取回查原文。若目前未處理來源本身超限，只能改用仍完整交付原話的受控來源窗口或較小後續排程，不能先壓縮它來通過預算。

原 `CTX-C001` 只需處理 A／B2，因當時 B1 是單次 structured extraction。B1 現改為可能多步讀寫的案例 Agent；2026-09-17 的 App 接線已把 B1 納入相同非破壞式 request-only 原則。正常單一完整 batch 不壓縮；分窗時只有已處理舊窗口可能在門檻達成後壓縮，最新未處理來源保持逐字。B2 固定每個 attempt 的第一個 task message，同 attempt 恢復摘要狀態，新的 stale attempt 從空狀態開始。fresh 離線證據為 App 指定套件 **52 passed、0 skipped**、package 指定套件 **50 passed、0 skipped**，兩側 `compileall` 均成功；這些測試沒有完整覆蓋 publication／JD byte-for-byte unchanged，也不是 provider 或自然模型品質驗證。

主顧問在第一輪尚無 publication、背景尚未整理或一次無法問完所有線索時的 Focus／待追查事項，由 [CTX-W001 訪談 Working State](2026-09-16-consultant-interview-working-state-design.md)承接。它只是 A checkpoint 中的發布前工作面，不是第三層 Memory：B1／B2 不得把 item 文字當員工來源，仍從 canonical source 建立案例與理解；publication 完成後，A 必須按需讀相關新版再移除、保留或改寫 item，不能只因版本前進就自動宣告已解決。這補足「Memory 不會每回合更新」的恢復缺口，不改 B1／B2／C 的 authority 與單一 publication head。

## 9. 既有衝突與有效處理

| 衝突 | 原差距 | 有效決定或完成狀態 |
|---|---|---|
| B1 責任 | 舊 `extraction.py` 只讀固定窗口並保存詳記／候選 | 已保留可用來源接縫，並完成以通知固定的完整 batch 為語意單位、B1 讀案例 guide／相關目前案例後 staged 更新；是否分頁只作必要的來源交付細節 |
| Memory bundle | 舊 `MemoryArtifacts.save_memory()` 只保存 `knowledge.md`／`guide.md` | 分層 bundle authority 已完成：同一 revision 選出案例 guide、案例、理解 guide、理解與 references；正式新 App 的舊兩檔格式已退役，不新增雙格式 adapter |
| C 修改範圍 | legacy `PATHS` 只允許兩個既有 Memory 檔，舊 guidance 又允許為真正新主題增加 section | 產品語意已固定、程式尚待實作：layered C 只處理已讀且可唯一定位的 existing stable IDs；案例引用原話、理解引用案例 digest。新主題交 B1／B2，仍禁止任意路徑、跨文件修改及 routine hot-path 寫入 |
| 背景發布 | H4 舊流程把 B1 artifact 交 B2，由 B2 發布兩檔 Memory | 已完成一個 durable B job 內 B1 staged → B2 staged → 一次完整 publication；舊 R1／R2 結果只作底層證據 |
| stale 重整 | 舊 B1 不讀 Memory，C 插入後通常只需 B2 重整 | 已完成的新 B1 依賴目前案例；stale 後 B1、B2 都基於新 head 重新評估 |
| compaction | 早期只有 request-only middleware，正式角色組裝與 App callback 尚未接上 | A／B1／B2 role factory 與 managed callback 均已完成離線切片；仍待 provider／自然模型與完整瀏覽器 App journey。summary 始終只是非權威 Context |
| 跨層引用更新 | 舊 `knowledge.md`／`guide.md` 未表達多對多案例依賴、穩定身分與精確 artifact 的雙層引用 | reference contract、影響查找與 B2 更新已完成；案例改變後必須重新分析既有理解與可能的新理解，禁止只換 artifact ID |
| 歷史 artifact 成長 | 現行 Store 無一般 GC | 第一版保留不再由 current head 選用的舊 immutable artifact，不新增自動 GC，也不讓正常回查掃描它們；長期只有出現可量測儲存壓力才重開 reference-aware 回收設計，canonical 原始訪談、有效 publication、仍被引用的證據與產品需保留的時間差異不得隨意刪除 |

表中已完成項目保留為差距與處理結果的追溯，不代表需要重做。尚未完成的 C 也不是授權實作者直接自行選 schema、改 Prompt 或宣稱舊測試已覆蓋；遇到會改產品效果、資料權責、引用可重現性或失敗語意的選擇，先提出具體衝突與最小方案。

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
12. B2 沿案例引用核對原話後若發現會影響工作理解的 B1 實質錯誤，會以精確案例／來源回報退回 B1；B2 不直接改案例，該次候選不發布，B1 修正後以新 B2 attempt 重新分析，且自動退回有明確上限。
13. 同一完整訪談回合可以被多個案例引用；同一案例可引用分散於多輪訪談的多個回合。案例 revise／split／merge 後，每個 current 案例仍保有真正支持其目前內容的 references，且沒有把整批來源無差別複製給所有案例。
14. 員工回答省略主體、使用代名詞或依賴前一個 AI 問題時，案例的完整回合證據集合仍足以讓只看引用的人理解工作情境；不保存模型填寫的文字 offset。
15. B1 能按需讀取未預載的同文件訪談；B2 能按需讀取未列入 required／impact hints 的目前案例。兩者皆從 guide／引用起步，不把全量資料塞進 request。
16. 新舊敘述衝突但員工沒有明確指出哪項錯誤時，A 會讀取相關目前內容與 canonical-ordered 引用並詢問；C 不發布、舊內容不因較早就被抹除，Working State 保留未解範圍。
17. 員工在當輪或既有 canonical 原話中明確更正一個既有案例，且更正影響可完整辨認的既有工作理解時，C 在同一 bundle 修訂案例並 revise／revalidate 理解：案例保存提供更正的 source，理解綁定修訂後案例 digest；正文仍正確時沒有假正文變更，也沒有 raw-source 越層引用或無關變更。
18. 員工明確補充真正遺漏的新工作而目前沒有唯一既有目標時，C 不建立新案例／理解；原話與 Working State 可供當輪續談，B1／B2 後續建立完整分層引用，A 不會為了立即寫 Memory 而重複呼叫 C。
19. C 已成功修訂 CASE-C 並解除其對 UNDERSTANDING-U 的舊 binding；下一次正常背景工作即使 B1 對 C 為 no-op，Runtime 仍從 repair receipt 的舊／新 manifest 將 C 與 U 納入 B2 最低 impact。U 若仍由 CASE-A／B 支持可 revalidate 並保留正文；C 仍留在 case guide，若之後與新案例形成另一穩定模式可由 B2 建立或修訂理解，不以解除舊 binding 靜默刪除案例。

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

案例正文需要保存足以回查的來源語意；正式 canonical source reference 由工具參數交 Runtime 驗證後寫入 manifest。持久引用單位沿用來源 owner 在固定 checkpoint 簽發的 `purpose="source"` **完整訪談交換**：以該輪使用者回答為中心，如存在，包含它前面最接近且未跨過另一個使用者輸入的公開 AI 問題／上下文；不是整份 conversation ID、AI-only token、模型自行切出的文字區段或 character offset。`processed_source` 可以表示本次連續待整理範圍，但不能因此自動成為其中每個案例的來源；B1 只能從 Runtime 已提供或已讀的完整交換 references 選擇。相同 reference 可由多個案例共用，一個案例可持有多個跨批次 reference。工作理解只能引用候選 bundle 中存在的 `case_id`，Runtime 將它解析並固定成該 bundle 的 `case_digest`。guide 可以顯示穩定 ID、名稱／別名、辨識詞、目前狀態與未確認事項作導覽，但 manifest 才是路徑、digest 與跨層關聯的結構 authority。模型按需讀取一筆案例或理解時，Runtime 的 read 結果須連同該筆已驗證的 source references／case bindings 回傳；不是把整份 manifest 塞進每次 context，也不能只回正文而藏掉回查入口。

來源 owner 的讀取結果可以用 offset 分頁傳輸完整交換文字，但 offset 只是 Runtime paging cursor，不得成為案例的持久 citation。既有 `context_reference` 可幫助當次理解；若其中較早問答確實支持案例，應選入該較早使用者輪次所屬的既有 `source` 完整交換，不能把 context-only token 升格為 evidence，也不另造 AI-only citation。

現有一筆 `source` 已處理常見的「顧問完整提問、員工簡答」，但一筆交換仍不一定足以讓人理解完整案例；主體、補充或更正可能散落在更早交換。因此一個案例的 `source_references` 是按 canonical 時序排列的**完整交換證據集合**：可以包含一個或多個 references；需要前題、代名詞指向、補充或更正才能理解時，B1 應把必要的相關交換一併引用。畫面展開引用時依序顯示 role 與全文，效果要求是不了解案例正文的人只看引用，也能理解案例的工作情境、細節與修正脈絡。

source owner 為同一文件 canonical conversation 中安全完成的使用者輪次提供 ordered source records，順序來自 conversation message order；settled failed／cancelled 回合的員工原話仍可列入，遇第一個 unsettled gap 即停止，不能跳到後面。Runtime 將本 attempt 已提供／已讀的 records 配置短 `evidence_key` 並把對照保存在 checkpoint；模型只能選既有 key，Runtime 解析成 reference、驗證 lineage 並按 owner order 保存。key 不代表輪次或時間，也不持久寫入案例；reference／UUID／時間戳都不能拿來推測順序，第一版不把時間戳送進模型 context。若底層使用 ordinal，它只是 owner 私有推導值，不是產品欄位。

Runtime 可驗證 reference 由 owner 簽發、固定位置、同文件、完整回合、已提供／已讀、無重複且按 canonical 順序保存；它不能只靠關鍵詞或字數證明語意已完整。是否足以獨立理解由 B1 規則、B2 沿引用反查及包含省略主體／跨輪補充／後續更正的自然訪談驗收共同保護。

### 11.3 身分生命週期

- 同一真實案例的補充、更正或目前狀態變化：保留 `case_id`，建立新內容 artifact，並保留來源與時間語意。
- 新的獨立案例／事件／任務情境：建立新 `case_id`；不能只因名稱相似就覆蓋舊案例。
- 重複案例合併：選定一個目前身分，其他身分標為被取代；B2 先重整所有依賴，current manifest 不再把被取代身分當目前案例。
- 一個錯誤混合的案例拆分：建立能各自代表真實情境的新身分，舊身分退出 current set；B2 先重新判斷理解與引用。
- 工作隨時間真正改變：不得用刪除或 GC 假裝舊情況從未成立。正文清楚區分先前與目前適用範圍；是否仍屬同一案例依實際工作情境判斷，不用檔名或固定時間門檻自動決定。
- 工作理解同樣以語意責任為身分。措辭修正保留 ID；責任實際拆分／合併時以明確操作建立、保留或取代身分，不讓 Runtime 只憑文字相似度猜測。

## 12. G4 Agent 工具責任與正常資料流

### 12.1 工具傳達語意操作，不讓模型管理儲存細節

B1／B2 的模型輸入只包含 Runtime 已選定的 document scope、base revision、guide、相關內容及可用 evidence／案例 ID。模型可以提出下列效果，但不填 `document_id`、版本號、digest、實體路徑、時間戳、operation ID、signed source reference、offset／cursor 或可由 stage 計算的完成 outcome：

| Agent | 允許的語意效果 | Runtime 責任 |
|---|---|---|
| B1 | create／revise／supersede 案例；為新內容選擇已提供／已讀的完整回合來源；必要時修訂案例 guide；明確 no-op | 配置／驗證 ID，提供訪談導覽與回合 reference，限制可改範圍，驗證 canonical source 及 split／merge 後來源分配，建立 staged artifacts 與變更集 |
| B2 | create／revise／supersede 工作理解；選擇支持案例；必要時修訂理解 guide；語意 no-op；沿已讀案例引用核對原話後要求 B1 rework | 解析 case IDs 到候選 digests，限制 source read scope，建立多對多 bindings，驗證所有依賴與 guide 路由；rework 時終止本次可發布候選 |
| C | 對最新 head 中已讀、唯一且明確被更正的既有目標做受控 revise；必要且影響可完整判斷時，同次修改既有案例，並 revise 或 revalidate 直接受影響的既有理解；不 create／split／merge／supersede | 執行准入、scope 與 latest-head 檢查，提供合法 stable IDs／evidence keys，解析案例 source 與理解 case bindings，驗證完整 bundle、CAS 與 receipt；衝突未明、新主題或廣泛影響時拒絕 C |

精確函式名稱可以在施工切片依現有框架公開 API 決定；上述輸入／輸出權責不可改。模型需要決定的是語意目標、正文／diff、route 文字及證據／支持關係；Runtime 提供 attempt-scoped keys，解析正式 ID/reference 並維護版本、排序、分頁與保存。單純狀態變更不要求模型重填整份物件，未提及的既有項目保持不變；remove／supersede 也不能與 upsert 用互相矛盾的欄位同時表達。完整參數矩陣見[模型／Runtime 參數權責審核](2026-09-17-model-runtime-parameter-ownership-review.md)。

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
B2 必要時沿已讀案例引用核對 canonical 原話
    ├─ 案例可用：重新驗證／修訂／拆分／合併／新增／supersede，或明確 semantic no-op
    └─ 案例有實質錯誤：case_rework_required；不發布，Runtime 有界重跑 B1，再建立新 B2 attempt
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
9. C 候選沒有新 stable ID、split／merge／supersession，所有修改目標都已在 latest head、已由 A 讀取且可唯一定位；案例引用由 source owner 驗證並 canonicalize，工作理解只綁定 candidate 中的案例 digest。
10. C 修改既有案例時，所有已知直接依賴理解不是已於同次候選完成語意處理，就是經讀取證明不受影響；影響不明或無法完整處理時整次拒絕，不發布半套分層結果。

## 13. 錯誤、恢復、成本與明確不做事項

| 情況 | 第一版行為 |
|---|---|
| 模型輸出／工具參數可修正錯誤 | 保留同一 base 與 checkpoint，在既有有界步數內回報具體錯誤供 Agent 修正；不部分發布 |
| B1 完成、B2 失敗或取消 | 保留 durable job／staging 供同 base 恢復；A 繼續讀舊 head，source cursor 不前進 |
| B2 從原話發現 B1 實質錯誤 | 以已讀 `case_id`／source reference 保存 `case_rework_required`，本次候選不可發布；Runtime 最多自動退回 B1 一次，再次發生則 blocked／failed |
| CAS stale | 舊候選完整拒絕；取得新 head，重新執行受影響 B1 與 B2 語意判斷，不能只換版本／digest |
| 提交結果不明 | 使用同一 operation ID 與 request digest 查 receipt／重送同一請求；不建立另一個可能重複的 operation |
| artifact／source 暫時不可讀 | 不發布；保存可診斷錯誤，不把缺資料當空白或 no-op |
| 達到重試／時間／成本上限 | 任務進入既有 blocked／failed 狀態，保留上一個正式 head；不強制覆蓋 |
| C 發現衝突但更正目標／正確內容／適用範圍不明 | 不修改 Memory；保留原話與 Working State，由 A 詢問或交 B1／B2。不得依較新敘述、模型 confidence 或工具方便性自動覆寫 |
| C 請求其實是新案例／新理解或廣泛重整 | 明確拒絕 C，保留 canonical source，走 B1／B2；不自動把 repair 升級成背景 Agent 或建立第二套寫入路徑 |

模型成本只來自真正需要的 B1／B2 工作；manifest 組裝、digest、scope、引用完整性與 CAS 都是純程式責任，不新增判斷模型。B1／B2 的 compaction 仍只在實際 request 超過門檻時執行，不固定每次多叫一次摘要模型。

第一版明確不做：文件封存、使用者可見 Memory history、自動 GC、實體去重最佳化、另一套 relational Case authority、讓 Web 重算引用不變量、以 embedding／RAG 取代 guide、讓 continuity summary 或 Working State 變成證據、以及因本設計重做已校準 Prompt／Skills／JD relational writer。

## 14. 最小施工順序

為避免又同時重做 Agent、Prompt、背景排程與 UI，施工拆成下列可獨立驗證的窄切片：

1. **Bundle authority foundation（已完成）：**已擴充 Memory bundle／manifest 的資料型別、保存、讀取、驗證及 publication；synthetic fixtures 已驗證 stable IDs、來源、digest、跨層 bindings、supersession、文件隔離、精確 bundle base、完整 CAS、receipt、tamper、stale 與當時舊 receipt digest 的歷史相容。當時亦驗過舊兩檔 Memory 相容，但該產品要求已由 2026-09-17 Owner 決定取代，不再是新 App 的回歸門檻；零模型、零 Prompt、零 dispatcher、零 UI。`consultant-memory` 全套 162 項測試及 compileall 通過。
2. **B1 case maintainer（前兩片已完成）：**沿現有來源固定／checkpoint／錯誤處理，接上案例 guide、相關案例讀取與受控語意操作；已離線測新增、補充、更正、重複、拆分／合併候選、no-op、單 batch 的一個或多個來源交付窗口、完成界線、transport resume、步數額度及 incomplete／refusal。多窗口是底層能力證據，不是正常產品流程的固定要求。
3. **B2 understanding staged maintainer（第一片已完成）：**已固定 completed B1 candidate 與 exact base，從 case change set＋既有 bindings 推導必讀 cases／直接受影響 understandings；十個窄工具提供 read、create、revise、revalidate、split、merge、retire、route 及 finish。Runtime 驗證 read-before-write、目前 supports、穩定 ID、guide、supersession、semantic no-op 與 binding refresh；後續另加入 case-scoped source-read evidence 與不可發布 rework terminal。本片零模型、零 publication。
4. **B2 Agent graph／Prompt／durable attempt（已完成）：**已用適用 B2 的工作分析方法與 attempt-scoped context，讓模型以 staged tools 完成新理解發現與多對多重整；初始 request 不預載案例、理解或原話正文。B2 沿已讀案例的 owner-ordered evidence keys 按需分頁核對原話，key 綁定 case/source，cursor 及正式 `(case_id, source_reference)` 已讀證據由 checkpoint 保存；發現實質 B1 問題時只提交 key＋理由，由 Runtime 產生不可發布的 `case_rework_required`。同一 completed B1 輸入冪等，新 B1 輸入清除舊訊息；transport resume、零參數完成、模型／工具上限及 incomplete／refusal 防護已離線驗證。本片不自動重跑 B1、不發布。
5. **案例引用精確化＋完整背景 job／共同 publication（package 已完成）：**B1 已從「整批來源自動附到每個改動案例」改為 Runtime 驗證的完整回合引用選擇與 split／merge 分配；bundle 也會由固定歷史上界重新證明 lineage 與 owner order。`BackgroundMemoryWorkflow` 已串 B1 staged → B2 staged → candidate bundle → 一次 publication，消費 `case_rework_required` 並最多自動退回 B1 一次；已離線驗證 B1 成功而 B2 transport failure 的父層 resume、semantic no-op、正式／candidate-only case rework、stale 後 B1／B2 重做、來源已涵蓋短路、retry 上限與同 operation receipt。這仍是 package 切片，不是 dispatcher 或真 PG 新程序旅程。
6. **C repair：**以 stable-ID 的分層受控處理取代正式 App 內舊兩檔 `path＋diff` 契約：案例 revise；直接依賴理解在正文錯誤時 revise、仍正確時 revalidate 並刷新 case digest。先固定並測試「已讀 latest 既有目標＋明確更正＋當輪依賴＋有界完整影響」准入；衝突未明、新主題、create／split／merge／supersede 與廣泛重整 fail closed。驗證案例 source、理解 case-digest binding、同次既有案例／理解處理、latest-head 刷新、完整 bundle CAS、receipt、本回合基準推進及成功後一次核讀。施工同時有界移除或隔離 App 的 legacy C 暴露面；不得新增雙格式 adapter。完成前，分層 head 呼叫舊 `repair_memory` 只回固定 unsupported 結果且不進 legacy workflow；這不算 layered C 已實作。
7. **A 分層 read path（已完成）：**每個 A 回合固定當時的 publication head，只把案例 guide 與工作理解 guide 放進初始 Context；`read_case` 回目前案例與 owner-ordered canonical source references，`read_work_understanding` 回目前理解與精確 `case_id＋case_digest` bindings，需要原話再沿既有 `read_conversation` 回查。工具全程讀同一回合基準，背景後續發布不會偷偷換版；沒有預載完整案例、理解、manifest 或原始訪談。分層 head 的通用 `ls／grep／read_file` fail closed，不能繞過 typed read；正式新 App 不再提供舊兩檔讀取路徑。
8. **Dispatcher／compaction／role factory／managed callback（離線接線已完成，完整 App 旅程未完成）：**App 已接回 dispatcher／背景恢復並組裝正式 Saver／Store／publication resource，也已用精確注入的 B1／B2 role model 與各自 output reserve 建立 request-only middleware；真 PostgreSQL 新程序接合與 B1／B2 attempt lifecycle 已有離線證據。正式 OpenRouter／Luna role factory 已用單一 credential／shared clients 建立 A／B1／B2，managed App callback 亦已組裝 document-scoped coordinator、前景 settle wake、startup recovery 及 bounded shutdown。provider／自然模型及完整瀏覽器 App journey 仍未完成，不得把局部接線稱為完整產品驗收。

第一切片不得先改 B1／B2 Prompt 或正式 dispatcher，也不得把舊 `knowledge.md` 自動解讀成已符合新案例／理解 schema。專案目前沒有舊正式使用者資料搬移需求；舊格式正式退役，遇到時只回明確 unsupported，不做猜測式 migration、雙寫或相容 adapter。

## 15. Closure

- **Decision：**B1 成為目前案例／任務／事件層的整理 Agent並擁有小型 guide；B2 以目前案例維護穩定工作理解及其 guide。兩者暫採同一文件級 Memory publication，B1 staged 後由 B2 完成或 no-op，再一次發布。B2 沿案例引用核對原話發現 B1 實質錯誤時只回報 `case_rework_required`，由 Runtime 有界重跑 B1→B2，不讓 B2 越權改案例。C 只在已讀 latest 既有目標、使用者明確更正、當輪需要且影響可完整判斷時，原子處理既有案例／理解：案例 revise；理解正文錯誤時 revise、仍正確時 revalidate。衝突未明或真正新內容交由詢問、Working State 與 B1／B2，不由 C 建立新項目。
- **Status：**G7 package 分段施工已完成共同 publication 與 C repair→B2 impact 接力：bundle authority、完整回合 citation／owner order、B1／B2 staged state 與 durable attempts、B2→B1 一次有界 rework、完整 bundle、CAS／receipt、covered／stale recovery 均已有離線契約證據；來源 owner 可用一個或多個窗口交付同一範圍，但產品不要求固定切窗。App A 也已能從固定 publication 的兩層 guide 起步，按需讀案例／理解及其已驗證回查入口，同輪不追隨背景新 head。App dispatcher／真 PostgreSQL 新程序資源接合、B1／B2 request-only compaction 的注入與 attempt lifecycle、正式 OpenRouter／Luna role factory 及 managed App callback 已通過各自指定離線回歸；summary 仍只是非權威 Context，canonical source、signed references、Memory／JD／evidence 語意不變。Layered C bundle repair 工具本身、provider／自然模型、完整瀏覽器 App journey 與 production authority 切換仍未完成；目前證據也沒有完整覆蓋 publication／JD byte-for-byte unchanged。
- **Why：**產品需要記住完整個別工作實況與可修訂的穩定共同理解，並透過分層引用產出貼合員工的 JD；歷史窗口詳記＋單一正文不能充分表達「目前完整案例」。
- **Sources：**Owner 2026-09-16～17 對話裁決；[OpenAI Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)明示 live update 可修正 stale Memory／依使用者要求更新，run 結束後另做 extraction／consolidation；[Codex Memories](https://learn.chatgpt.com/docs/customization/memories)、[Codex consolidation template](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)與[Codex memories README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)只支持背景分層、引用與引用感知整理的官方事實，不替本產品決定 C 准入、publication schema 或兩層 citation；Anthropic prompt chaining／evaluator-optimizer、Microsoft AutoGen reflection、AWS dependency rerun 與 Google data lineage 共同支持「保留階段權責、結構化回饋、沿依賴回到真正出錯的上游並有界停止」方向，精確契約仍是 Caliburn 映射；既有 Q019／重抽／publication／H4 實作證據只作可沿用工程基礎。
- **Affected：**`current-decisions.md`、本分層 Memory 規格、Working State 文字、`packages/consultant-memory` 責任 README，以及後續 layered C 工具／測試計畫；B1／B2 Prompt 與 Agent graph、App A typed reads、dispatcher／背景資源、compaction、role factory、managed callback、UI、provider credential owner、已校準 Prompt／Skills、JD 語意及 production authority 不因本次文件對齊改動。
- **Reopen：**Owner 改變案例完整度／更正效果；G4 發現共同 publication 無法在現有 Store／Saver 契約下可靠完成；或代表性測試證明兩層一致性／回查成本不能同時成立。
- **Next gate：**managed App callback 已完成；下一片依本文件的窄准入與分層引用契約實作 layered C bundle repair，再做 provider／自然模型及完整瀏覽器 App journey 驗證；production authority 另循正式採用程序。第一版沿用「舊 immutable artifact 暫留、不做 GC」。
