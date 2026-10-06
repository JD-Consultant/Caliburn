# 長訪談、記憶與 Context 演進材料

回到[演進總覽](README.md)。本頁追查長訪談中的入料、限定條件、更正、來源回讀與實際寫入。B1／B2／C、詳記、case、turn 依各時期原文解釋；10 月接續另列於後段。

## 從對話歷史，到持久工作理解

### 2026-05-20：先以對話歷史與 Graph 狀態延續

最初 JobIntel 的訪談節點取最近 20 則訊息，任務萃取則讀保存的訊息；STAR／5W2H／指標等另有 Graph 狀態。它與後來的背景記憶整理不同：當時還沒有「原話、工作情境、工作理解」三層。

**引用：**[初始 Graph §2](../../history.md#source-f6099bd5a1a81730042d)、[初始架構的 graph_state](../../history.md#source-403e401b5f084bb191fc)。程式原件為 `9bbfe51b9c2130335065e495f102e84f1e2f6b11:backend/app/graph/nodes/interview.py` 與同提交的 `task_extraction.py`。這只能證明窗口／取料方式，不能推定當時已實測資訊因 20 則窗口而遺失。

### 2026-07-20：短答不能脫離前問解釋

「是」「每週」「主管」單獨看沒有完整指涉，過去頻率也可能被誤當現在。當時因此研究 QuestionFrame 與 contextual evidence，保留顧問問題和員工回答的關係。這是後來原話前後文問題的早期材料，不必等到有 Memory 才出現。

**引用：**[短答及專業分析研究](../../history.md#source-41f73d8f9e737418f7ea)、[ADR0037](../../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)。這是當時的產品決策，沒有因此要求新架構保留同名結構。

### 2026-08-12 至 08-13：保存得到，不代表 State 不會膨脹

在合成長來源測試中，25 → 50 輪時，完整來源累積於 State 的 PostgreSQL 保存量約由 1.20 MB 增到 3.94 MB（3.281 倍）；Store-first 約 2 倍，Delta 方案也約 2 倍。研究據此區分原始來源與執行工作態；Delta 雖有容量改善，但當時仍是 beta 且重建整份 journal，因此不採作唯一來源權威。

**引用：**[產品流程研究 §9.7.2、§9.8](../../history.md#source-20bcac8af4c10acef7f5)。這測的是保存／序列化負擔，不是模型 input tokens，也不是長訪談語意品質通過。

### 2026-08-27 至 08-29：不只累積對話，試作可修訂的工作理解

研究開始把跨輪延續、工作理解與來源回查分開，並用 LangMem 做領域語意記憶試驗。最初 subject＋detail 結構會在頻率改變後留下過時標題，因此改成 kind＋body 再測。16 輪合成訪談、六批整理中，更正、未知及一次性事件大致保留，但仍有輕微記錄重疊。

**引用：**[跨輪延續研究](../../research/agent-systems/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md)、[LangMem 試驗與限制](../../history.md#source-ebaa81dee5721a6f1001)。此試驗不含正式來源 anchor、完整 checkpoint rollback、程序崩潰或 production 採用，不能寫成整套 Memory 已完成。

### 2026-09-01 至 09-04：分開保存、路由與原話回讀，先被基礎接線擋住

設計進一步區分 canonical 原話、語意工作理解與查找導覽。但隔離 spike 先遇 Windows event loop／Psycopg 不相容；修正後，DB／Store／embedding 可以跑，第一個 chat 請求又因路由與參數組合無可用 endpoint 而失敗，六項語意品質檢查仍是 NOT_EVALUATED。

**引用：**[路由與 canonical 研究](../../history.md#source-e56a1c076f474bdb39da) §7、[原 spike 結果](../../experiments/historical/20260918-memory-routing-spike/experiments/2026-09-03-memory-routing-canonical-read/report.md)。這是基礎設施／provider 相容性失敗，不能說模型記憶品質已被證明不好或已修好。

## 分層分析試驗：有工具、有資料，仍可能做錯

### 2026-09-05 至 09-06：借鑑分層 Memory，拆開讀取、整理與即時修補

當時形成 A 顧問、B1 訪談詳記／候選、B2 工作理解／guide，以及 C 即時修補的設計，並用有限真 API／PG 試驗檢查寫入。後續 readiness audit 又找到 Markdown 引用判定、B2 原話引用驗證與無正常回覆時的前景資訊風險；不能用一筆 CAS 成功就說完整產品已可用。

**引用：**[analysis-only 設計](../../history.md#source-7c28c9e58ce7f8268b9f)、[live 結果](../../history.md#source-d35d0f7eca5627081212)、[接續 readiness audit](../../history.md#source-48b4568da315ba701c14)。這裡的 B1 詳記還不是後來可跨批修訂的工作情境。

### 2026-09-07：長文編輯失敗，不一定是 Memory 分層錯誤

正常訪談試驗先因 token-count API 404 被擋，之後才完成有限前景回合；長訪談又讓 B2 耗盡工具步數。trace 顯示模型把讀取回傳的行號／tab 一起抄入 `old_string`，多次精確替換失敗。接著研究原生 patch helper，但 wrapper 又錯拒合法的結尾標記，須分開修接線。

**引用：**[正常訪談結果](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-07-native-context-normal-interview-results.md)、[CT09 長訪談](../../history.md#source-b97b3bf78ac49cdc4cc7)、[CT11 patch 試驗](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-07-official-memory-patch-trial-results.md)。wrapper 的本地 replay 通過不等於完整 B2 真模型發布已通過。

### 2026-09-08 CT28／32／33：口頭記得更正，卻沒有真的寫入

同樣的「每月 10 日改為 5 日」，短 context 對照會讀取並修補；帶舊延續的情境卻可能零工具、口頭說 5 日，實際 Memory 仍是 10 日。再拆 visible／opaque 因素，追到舊 compaction 的生成請求及當時 optional 修補規則。

追查確認，**目前要求修補的規則與導覽已送到模型**，不能再猜是漏注入；但加密內容不可讀，有限對照也不足以證明 compaction 的唯一因果或普遍失敗率。

**引用：**[CT28 原對照](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-08-ct28-live-repair-context-contrast.md)、[CT32 因素拆分](../../history.md#source-e27b12969cabd656ac6a)、[CT33 來源追查與未解界線](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-08-ct33-compaction-provenance-and-recovery-review.md)。不能據此寫成「刪掉歷史就解決」。

### 2026-09-08 CT37／38：原文都在，部分回答仍被過度概括

顧問一次問兩種情境，員工只回答其中一種沒有做過；B1 卻把另一種未回答情境也變成「沒有經驗」，B2 又沿用。核對實際 request，完整八則訊息都在，原提示也已有相關規則，因此不是單純 context 遺失或規則沒寫。

隨後比較 prompt 與 reasoning effort：只升 high 仍有失敗；候選 prompt＋high 的局部產物較好，再接原 B2 medium 測兩批增量，主要更正與未知能保留。但有措辭瑕疵，也不是隨機重複實驗／錯誤率統計。

**引用：**[CT37 定位第一個錯誤產物](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-08-ct37-partial-answer-memory-fidelity-review.md)、[prompt／effort 對照](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-08-ct37-prompt-effort-comparison-results.md)、[CT38 增量結果](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-08-ct38-high-extraction-medium-consolidation-results.md)。原文件連有 Codex／OpenAI／Anthropic 的研究依據，不必另寫一份來源清單。

### 2026-09-09 CT42：整場執行完成，仍有舊未知與回查問題

固定版本的 11 輪合成訪談，前景背景都完成，22 則 canonical 訊息重開後一致，也經過原生 compaction。但員工已核實的核准者，仍在 Memory 另一處寫成未知；回查原句需要診斷用的較高額度，還有長引用抄錯與早期詳記未直接引用問題。

**引用：**[CT42 結果／不通過項](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-09-ct42-long-interview-results.md)、[逐字稿](../../experiments/historical/20260918-analysis-only-agent/evidence/2026-09-09-ct42-transcript.md)。資料能找回、資訊語意一致、回查成本合格是不同判準；局部 high replay 不能抹掉原失敗。

### 2026-09-09 CT43 至 CT48：修回查後，又暴露編輯與引用保留

CT43 改善詳記到原話的讀取路由；下一次 CT45 固定長訪談仍在 B2 長 patch／UUID 錯誤與額度耗盡處失敗，也出現引用存在但支撐內容不符。CT46 只提高 effort 到 xhigh 仍失敗，接著才沿官方 helper 核對 hunk 必須按原文順序、短全文重寫與局部 patch 的工具選擇。

CT47／48 的候選在局部重播完成並保留重要舊引用，但還有標籤過寬等 minor；原 CT45 的錯誤資料沒有被假裝修復。CT47 成功僅用七步，不能因測試上限設為 16 就說「加上限是成功原因」。

**引用：**[CT43](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-09-ct43-read-routing-results.md)、[CT45](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-09-ct45-fixed-long-interview-results.md)、[CT46–48 原碼核對、比較與限制](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-09-ct46-48-edit-routing-and-budget-results.md)。這段有「反例 → 官方契約 → 局部改法 → 回歸 → 仍未解項」的連續材料。

### 2026-09-09 CT49：固定代表情境通過，仍不是全部品質過關

再以固定新版跑 11 輪前端接案訪談，核對案例、頻率更正、未知變已知、深讀原話與重開保存。原結果標為代表情境 PASS、有 minor；不是零工具錯誤，也沒有測背景自動重試。

空近期 context 的 reader 找回細節，但用 15 模型／14 工具的獨立診斷額度，不能冒稱產品 A 當時的 12／11 上限已通過同一題。guide 舊地址、措辭與無依據代詞亦保留為限制。

**引用：**[CT49 範圍、證據與 minor](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-09-ct49-fixed-long-interview-results.md)、[逐輪問答](../../experiments/historical/20260918-analysis-only-agent/evidence/2026-09-09-ct49-transcript.md)。此時還不含 JD，也不是百輪或所有職位的成功率。

## 不是只調 Prompt，產品分層和工具也再改

### 2026-09-15 起：HTTP 200 不能證明原生壓縮有執行

OpenRouter inline compaction smoke 的 input 超過指定 threshold，卻沒有回傳 compaction item。客戶端 fixture 可往返，不代表此 provider／route／模型組合已完成「壓縮 → 保存 → 下次接續」。當時如實標 UNVERIFIED，再研究 request-only 的延續摘要。

**引用：**[服務端 smoke](../../experiments/legacy-evidence/2026-09-15-openrouter-inline-compaction-live-smoke.md)、[9/16 延續壓縮設計及後續修訂](../../history.md#source-49fa82b26188aad2b075)。這只是當時組合的結果，不是 OpenRouter 永久不支援的主張；更不是原始訪談可刪除的授權。

### 2026-09-16 至 09-18：固定窗口詳記，不等於完整工作案例

即使詳記能保存，案例仍可能跨批次被補充、更正；因此原「B1 訪談窗口詳記＋B2 knowledge／guide」改為 **B1 維護完整工作案例，B2 維護跨案例工作理解，各有導覽與來源關係**。這是分析單位的改變，不只是換名。

當時還有 C repair，又發現 C 修改並解除舊關係後，下一批若只看 B1 的新變化，可能漏掉 B2 應重評的影響。後續從既有 receipts 和新舊 bindings 接回影響範圍，留下離線反例與回歸；沒有因此完成自然長訪談品質驗收。

**引用：**[分層重設計 §0–§3、§6.1](../../history.md#source-9540bc676045d402f2e8)、[背景流程 §2.4 的接力修正](../../history.md#source-581fea9d87762ea5c453)。原件保留多次 successor；C 與 B2 回交等依當時流程解讀，不能由此推定現行產品接線。

### 2026-09-23：反覆摘要的主要負擔，竟是工具格式與近期回傳

自然 JD 撰寫試驗未完成後，沿 checkpoint 拆算實際 context：**17／17 次摘要後仍高於當時 16K trigger**。主要負擔是近期 JD 讀取與固定工具 schema，不是摘要太長；一頁讀取 31,329 字元中，重複定位 refs 約占 86%，文字 value 只有 320 字元。

離線測無損表格投影有減量，但仍過 trigger；把摘要換成一個字元的證偽下界仍不能跨過門檻。因此「再把摘要寫短」不夠，須同時考慮工具表示、近期保留範圍、壓縮收益與安全容量。這些測量只解釋反覆觸發，**不證明顧問未收尾的唯一語意根因**。

同一紀錄也試 tool search：服務端可回工具搜尋項目，但目前 adapter 的往返遺漏特定 item，顯示支援宣告、HTTP 成功與完整 App 接續能力仍不同。

**引用：**[自然試驗與停機後診斷](../../experiments/legacy-evidence/2026-09-23-gpt6-cw-natural-trial.md) 的「JD 撰寫回合的 context 膨脹」「重複 JD 引用」「工具定義按需載入」三節。token 分項是離線估算，不能當精確帳單；表格投影與一字元摘要皆不是已採用產品方案。

### 2026-09-24 之後：重新分工並自行管理 Context，再接受新驗證

新目標退役 C，重新釐清原始訪談、工作情境、工作理解與 JD；採 LangGraph＋OpenAI direct Responses，App 負責組裝 context、原生項目接續、導覽／按需工具、壓縮與安全點。Memory 版本、候選工作面、diff 與 JD 核對也經多次修訂，不能拿最早討論稿當最後契約。

**引用：**[reasoning／工具結果／state 研究](../../research/agent-systems/2026-09-26-reasoning-tool-results-and-state-boundary-research.md)、[context 設計沿革](../../specs/2026-09-26-consultant-context-and-state-design.md)、[目標架構地圖](../../target-architecture-map.md)、[T01–T18 計畫](../../history.md#source-ee8cbce8eb3c303d1765)。最新實驗再遇到的早期依據漏選、Prompt 比較、長旅程中斷與續跑，接[近期案例索引](../research-casebook.md)及其原始證據；不是到此便全面解決。

## 9月底重建前的六個轉折

以下補上前節沒有展開的版本、權責與操作演化。9/24–9/28 是文件記載的討論／事件日期，許多文件於9/29才一起提交；不能用 Git 初次收錄日推算每個方案實際存在多久，也不能把同日多輪討論說成三套均已上線。

### 2026-09-24：先限制 C 與背景競爭，再決定退役 C

**反例：**背景只拿到較早固定訪談，新的第17輪更正若先由 C 發布，舊背景即使因 CAS 衝突重做，也不會憑空取得不在原輸入範圍內的更正。寫入版本安全與分析資料充分是兩件事。

**演化：**當時先提出背景期間禁止 C，再收斂為新目標退役 C；不可變原話及 A 的工作接續承接新資訊，B1／B2 在適當時機整理。候選不作 JD 正式 Memory 來源，背景尚未發布時 A 仍可依原話工作。

**引用／界線：**`7e47c133:docs/current-decisions.md` 中兩條「2026-09-24 MEM-L001／JD-R002」決定，及[分層設計沿革](../../history.md#source-9540bc676045d402f2e8)。這是當時的需求反例與已確認目標，不是本輪重現第17輪事故，也不表示9/24程式已移除 C。

### 2026-09-25：整批返工可以完成，卻把另一個正確案例弄丟

**發現：**零付費固定回覆反例先建立案例甲、乙；B2 只要求修甲，下一次 B1 產出甲′卻未重建乙。結果 `completed`、案例只剩一筆、處理來源進度已前進，乙不在正式 manifest。

**定位：**當時 `_prepare_case_rework` 清空兩層 stage、換 attempt，只帶指定問題；下一次從正式 base 重建，未把其他尚未發布候選視為保留義務。這不是 SQL 原子提交失敗，也不是原始訪談遭刪除，而是「重做的候選集合」與「完成的涵蓋承諾」脫節。

**後續取捨／限制：**原研究比較重建、保留候選及差異對帳，後來又澄清不是讓 B2 主動判錯並要求全批重做，而是限定其分析中的資訊缺口。此測試證明舊流程**允許**靜默漏案，不證明真模型每次都漏，也不要求一則訪談必須對應一個情境。候選操作能力仍須另外設計，不能只把所有舊稿複製回去。

**引用：**[能力與生命週期研究「多案例返工的隔離反例」及其後續澄清](../../research/agent-systems/2026-09-25-agent-capabilities-and-lifecycle-patterns-research.md)；原碼 `7681963d:packages/consultant-memory/src/caliburn_memory/background_workflow.py::_prepare_case_rework`。原研究 Git 路徑為 `a0994d1d:docs/specs/2026-09-25-agent-capabilities-and-lifecycle-patterns-research.md`，不是把新架構問題套在現行程式上。

### 2026-09-26 至 09-27：不把分工做成每批固定雙向互審

**問題／收斂：**上游情境改動後，下游要分析影響；但程式找既有引用，不能找到所有尚未連結的新情境。另一方面，讓 B1／B2 每批互審全部內容，增加重讀與迴圈，沒有 eval 證明值得。

當時收斂稿讓 B1 維護情境且不讀理解，B2 專注理解，不主動審核整個 B1；程式處理身分／範圍／操作有效性，語意由分析角色負責。**當時文件仍保留資訊缺口的例外交回**，這不同於早期「案例錯誤→全批重建」，也不同於固定雙向審核。不能因為都叫 B1／B2，就把三者寫成同一機制。

**引用／界線：**[分責、影響範圍與讀寫權限的歷史稿](../../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)的 PROD-G2-006／007；原件 `1bf5f1b3:docs/specs/2026-09-25-b1-b2-information-gap-lifecycle.md`。這是設計取捨，沒有證據顯示固定互審曾完整實作再撤下。是否仍保留例外交回須查相應時期的實作／決策，本報告不以舊稿重新決定現行流程。

### 2026-09-28：引用核對也曾做過減法

**討論順序：**先比較 B2 完成階段後由 App 改綁，再討論逐條 `confirm_reference_alignment`，最後改為 **候選關係綁物件身分、正式發布才固定修訂**。工作面上同一物件持續編輯，不要求 B2 為每次換版刪舊引用再加新引用。

**留下與移除：**B2 仍要看上游變更並完成理解分析；去掉的是逐條版本格式確認，不是去掉語意工作。JD 的來源核對則保留，因其可能分段、跨回合處理。`read_ref` 作為所有 Memory 操作必填值亦曾是候選，不能把它寫成已採用後全面改回。

**引用／界線：**[Memory更新契約 §10討論沿革](../../specs/2026-09-27-memory-object-update-tool-contract.md)、[Memory讀取契約 §4](../../specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[JD來源契約 §4](../../specs/2026-09-29-jd-model-tool-contract-review.md)。前兩份原件於 `df4221a5` 收錄；同日方案次序由文內 successor 說明辨認，沒有三個獨立已驗版本可比較。

### 2026-09-28 至 09-29：分清可編輯工作面、交接快照與正式 Memory

**問題：**只說「版本固定」會讓人誤以為 B1／B2 修改後仍只能讀舊 map；只說「永遠最新」又會破壞 A 與 JD 當時依據。這兩種使用者需要不同的讀取邊界。

**設計收斂：**一批整理使用一份邏輯候選，B1／B2 的 map／read 隨已成立操作更新，權限各自限定。改名不改身分；刪情境會解除候選綁定，理解物件本身保留。開始前與 B1 完成後快照供恢復／diff 使用，不是第二份可寫資料。完成後發布不可變 Memory 快照，同一物件在本版只選一個修訂；A 固定一版使用，歷史 JD 來源不被後續編輯覆寫。

**引用／界線：**[生命週期「候選操作、快照與三個安全點」](../../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[Memory操作契約的刪除及關係規則](../../specs/2026-09-27-memory-object-update-tool-contract.md)。這裡記錄的是重建前契約如何變清楚，不表示該時候 SQL、checkpoint 或原子發布已驗。後來施工與測試沿[T04候選／快照](../../history.md#source-378c7f9480def66d4cde)及[T10背景整理](../../history.md#source-378c7f9480def66d4cde)找，不能用圖或一次發布成功替代各項驗收。

### 2026-09-28 至 09-29：從執行 Turn 改成有效訊息序列來界定取材

**問題／收斂：**問答、模型執行回合及單則發話不等同；短答需要前問，員工也會主動補充。於是分開完整訊息的來源身分與固定訪談序號，按需工具可選個別訊息或區間，保留順序、說話者與原文，不另造 LLM 維護的主題分組。

當時新規則只讓成功完成的員工輸入／完整答覆取得正式序號，取消輸入與中間訊息不成為共享來源；App 開場另為第1則。Memory 的**啟動時點**與**資料截止點**分開：X Turn 成功後啟動，但上界取其最後員工輸入，不取其後顧問答覆或延後啟動時的最大序號。Runtime 固定並驗證範圍，模型只選需要讀的訊息。

**引用／界線：**[原話讀取、來源資格與固定上界](../../specs/2026-09-27-memory-read-and-source-navigation-contract.md) §2–3。序號38／39／40是設計示意，不是真實長旅程結果；尚未完成與正式原話的保存也不能混為一談。後來的容量、來源工具與長訪談實驗接[T16](../../history.md#source-6d2d7ab4abfedbf8416e)及[T17](../../history.md#source-98d840caa9eed7fb2840)，結果層級各自看原件。

## 2026-10-04 至 10-05：從保存得到，進一步比較選讀與使用

正式重建後，測試分開觀察壓縮後發布、資訊找回、增量維護與顧問取用。它們使用不同材料及接線，不合併成一個 Memory 成功率。

| 問題與轉折 | 結果及界線 | 原件 |
|---|---|---|
| 10／2 未完成的 B 壓後發布如何補證 | 調低門檻的兩組真模型整合對照完成四批發布與固定來源回讀；不代替正式容量邊界或自然長旅程 | [壓縮發布](../../experiments/product-validation/data/memory-compaction-publish-2026-10-04/README.md) |
| 理解已足夠，是否仍要讀到底 | 固定同一 Memory 的共同完成三對保留 33／33 指定核心事實，讀取 23→3、累計 input 少 56.23%；全稿欄位一致性仍有反例 | [充分性停止](../../experiments/product-validation/data/memory-reading-policy-2026-10-04/results.md) |
| 少一層或換摘要，是否就更好 | 單集合先導維護較省，卻漏讀另一理解的分工且下一題格式失敗；三層／單層摘要先導品質未顯示三層較優，三層累計 input 為 3.31 倍 | [單集合](../../experiments/product-validation/data/memory-structure-incremental-2026-10-05/results.md)、[單層摘要](../../experiments/product-validation/data/memory-summary-capacity-2026-10-05/results.md) |
| 自足單元與回答限定是否足以解決漏項 | 自足單元少讀卻未保持品質等價；固定 Memory 的範圍指引仍有讀後漏分工及責任推論；另一次取用指引未減總讀取且細節退步，均未據此切換產品 | [自足單元](../../experiments/product-validation/data/memory-coherent-units-2026-10-05/results.md)、[回答範圍](../../experiments/product-validation/data/jd-scope-preservation-2026-10-05/results.md)、[未採用指引](../../experiments/product-validation/data/memory-summary-capacity-2026-10-05/reading-policy-update.md) |
| 分層成果能否承接更正並局部更新 | 三批整理及四對顧問作答觀察到選讀一項理解、保留未變物件與局部修訂；跨案舊期限副本及已讀分工省略仍需修正 | [分層增量](../../experiments/product-validation/data/memory-layered-value-2026-10-05/results.md)、[局部修訂配對](../../experiments/product-validation/data/memory-local-preservation-2026-10-05/results.md) |
| 換窗後能否接續現行工作及歷史查證 | 兩批三組各八段完成，Memory 的累計 input 相對完整原話分別少 21.0% 與多 7.32%；原話均放得下，沒有超容量勝出結論 | [中後期修訂](../../experiments/product-validation/data/context-reset-comparison-2026-10-05/results.md)、[早期找回](../../experiments/product-validation/data/early-interview-recall-2026-10-05/results.md) |

後續[五對唯讀取用比較](../../experiments/product-validation/data/early-interview-recall-2026-10-05/reading-probe-01/README.md)分開測導覽說明與回答細節：缺導覽時少讀一份情境 map，細節候選補回確認者；已有導覽時兩邊都未重讀。每題只有一對，沒有把兩種候選合併，也未改正式 Prompt／工具或驗 JD 保存。

[研究收斂](../../research/agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md#9-收斂採用既有分層改善內容組織與選讀)保留原話→情境→理解，單集合替代暫不推進。改進重心是各層的內容用途、局部自足性、撤換舊說法及足夠時停止。其後只將兩句跨案數值副本維護規則加入正式 B2，A 候選未採用；角色／工具／完成契約檢查不能代替正式提示組合的真模型效果。採用範圍見[執行紀錄](../../experiments/product-validation/data/memory-local-preservation-2026-10-05/execution-notes.md#後續採用2026-10-05)。

現行輪前與輪中仍使用原生 compaction；輪前 App 文字摘要的目標尚未實作，依[摘要契約](../../specs/2026-10-04-context-summary-and-compaction-design.md)查閱。上述換窗比較不能冒充新摘要政策或容量驗收。

## 可以連著讀的問題鏈

- **短答與過度概括：**7/20 的前問關係 → CT37 實際入料核對 → CT38 prompt／effort 對照 → CT42／49 長訪談。
- **能保存與能使用不同：**早期 Graph 歷史 → State 大小比較 → routing spike → CT42 回查效率 → 新目標引用／按需讀取。
- **工具會影響分析效果：**行號污染 old_string → patch wrapper／hunk 順序 → 引用保留 → 9/23 重複 refs 與 schema 膨脹。
- **分層本身也在迭代：**固定窗口詳記 → 跨批案例 → 理解與來源影響 → 新目標 Snapshot／工作面；每次都要區分設計決定與已有的實測。
- **操作有效不等於分析完整：**C與背景的取材反例 → 多案例返工漏案 → 分責與候選接續 → B2看變更、JD按需核對；不靠多加審核者解決所有問題。

這些只是方便回讀的素材路線，不先判定哪條一定要放團隊專題正文。所有原失敗、未驗項目與外送資料限制仍以各原件為準。
