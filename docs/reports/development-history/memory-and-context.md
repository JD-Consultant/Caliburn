# 長訪談、記憶與 Context 演進材料

回到[演進總覽](README.md)。這條線關心：對話變長後，資訊是否真的送達、能否保留限定條件與更正、能否找回來源，以及模型是否真的完成寫入。下列 B1／B2／C、詳記、case、turn 的意思依各時期原文，不等同現在的工具契約。

## 從對話歷史，到持久工作理解

### 2026-05-20：先以對話歷史與 Graph 狀態延續

最初 JobIntel 的訪談節點取最近 20 則訊息，任務萃取則讀保存的訊息；STAR／5W2H／指標等另有 Graph 狀態。它與後來的背景記憶整理不同：當時還沒有「原話、工作情境、工作理解」三層。

**引用：**[初始 Graph §2](../../archive/early-projects/2026-05-20-jobintel-graph-pipeline.md)、[初始架構的 graph_state](../../archive/early-projects/2026-05-20-jobintel-architecture.md)。程式原件為 `9bbfe51b9c2130335065e495f102e84f1e2f6b11:backend/app/graph/nodes/interview.py` 與同提交的 `task_extraction.py`。這只能證明窗口／取料方式，不能推定當時已實測資訊因 20 則窗口而遺失。

### 2026-07-20：短答不能脫離前問解釋

「是」「每週」「主管」單獨看沒有完整指涉，過去頻率也可能被誤當現在。當時因此研究 QuestionFrame 與 contextual evidence，保留顧問問題和員工回答的關係。這是後來原話前後文問題的早期材料，不必等到有 Memory 才出現。

**引用：**[短答及專業分析研究](../../specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)、[ADR0037](../../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)。這是當時的產品決策，沒有因此要求新架構保留同名結構。

### 2026-08-12 至 08-13：保存得到，不代表 State 不會膨脹

在合成長來源測試中，25 → 50 輪時，完整來源累積於 State 的 PostgreSQL 保存量約由 1.20 MB 增到 3.94 MB（3.281 倍）；Store-first 約 2 倍，Delta 方案也約 2 倍。研究據此區分原始來源與執行工作態；Delta 雖有容量改善，但當時仍是 beta 且重建整份 journal，因此不採作唯一來源權威。

**引用：**[產品流程研究 §9.7.2、§9.8](../../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md)。這測的是保存／序列化負擔，不是模型 input tokens，也不是長訪談語意品質通過。

### 2026-08-27 至 08-29：不只累積對話，試作可修訂的工作理解

研究開始把跨輪延續、工作理解與來源回查分開，並用 LangMem 做領域語意記憶試驗。最初 subject＋detail 結構會在頻率改變後留下過時標題，因此改成 kind＋body 再測。16 輪合成訪談、六批整理中，更正、未知及一次性事件大致保留，但仍有輕微記錄重疊。

**引用：**[跨輪延續研究](../../specs/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md)、[LangMem 試驗與限制](../../specs/2026-08-29-langmem-domain-semantic-memory-spike-experiment.md)。此試驗不含正式來源 anchor、完整 checkpoint rollback、程序崩潰或 production 採用，不能寫成整套 Memory 已完成。

### 2026-09-01 至 09-04：分開保存、路由與原話回讀，先被基礎接線擋住

設計進一步區分 canonical 原話、語意工作理解與查找導覽。但隔離 spike 先遇 Windows event loop／Psycopg 不相容；修正後，DB／Store／embedding 可以跑，第一個 chat 請求又因路由與參數組合無可用 endpoint 而失敗，六項語意品質檢查仍是 NOT_EVALUATED。

**引用：**[路由與 canonical 研究](../../specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) §7、[原 spike 結果](../../experiments/historical/20260918-memory-routing-spike/experiments/2026-09-03-memory-routing-canonical-read/report.md)。這是基礎設施／provider 相容性失敗，不能說模型記憶品質已被證明不好或已修好。

## 分層分析試驗：有工具、有資料，仍可能做錯

### 2026-09-05 至 09-06：借鑑分層 Memory，拆開讀取、整理與即時修補

當時形成 A 顧問、B1 訪談詳記／候選、B2 工作理解／guide，以及 C 即時修補的設計，並用有限真 API／PG 試驗檢查寫入。後續 readiness audit 又找到 Markdown 引用判定、B2 原話引用驗證與無正常回覆時的前景資訊風險；不能用一筆 CAS 成功就說完整產品已可用。

**引用：**[analysis-only 設計](../../specs/2026-09-06-analysis-only-agent-memory-design.md)、[live 結果](../../specs/2026-09-06-analysis-only-agent-live-memory-results.md)、[接續 readiness audit](../../specs/2026-09-06-analysis-only-context-memory-readiness-audit.md)。這裡的 B1 詳記還不是後來可跨批修訂的工作情境。

### 2026-09-07：長文編輯失敗，不一定是 Memory 分層錯誤

正常訪談試驗先因 token-count API 404 被擋，之後才完成有限前景回合；長訪談又讓 B2 耗盡工具步數。trace 顯示模型把讀取回傳的行號／tab 一起抄入 `old_string`，多次精確替換失敗。接著研究原生 patch helper，但 wrapper 又錯拒合法的結尾標記，須分開修接線。

**引用：**[正常訪談結果](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-07-native-context-normal-interview-results.md)、[CT09 長訪談](../../archive/worktree-snapshots/20260918-analysis-only-agent/docs/specs/2026-09-07-long-interview-acceptance.md)、[CT11 patch 試驗](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-07-official-memory-patch-trial-results.md)。wrapper 的本地 replay 通過不等於完整 B2 真模型發布已通過。

### 2026-09-08 CT28／32／33：口頭記得更正，卻沒有真的寫入

同樣的「每月 10 日改為 5 日」，短 context 對照會讀取並修補；帶舊延續的情境卻可能零工具、口頭說 5 日，實際 Memory 仍是 10 日。再拆 visible／opaque 因素，追到舊 compaction 的生成請求及當時 optional 修補規則。

重要的是，追查確認**目前要求修補的規則與導覽真的已送到模型**，不能再猜是漏注入；但加密內容不可讀，有限對照也不足以證明 compaction 的唯一因果或普遍失敗率。

**引用：**[CT28 原對照](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-08-ct28-live-repair-context-contrast.md)、[CT32 因素拆分](../../archive/worktree-snapshots/20260918-analysis-only-agent/docs/specs/2026-09-08-ct32-context-factor-isolation.md)、[CT33 來源追查與未解界線](../../experiments/historical/20260918-analysis-only-agent/reports/2026-09-08-ct33-compaction-provenance-and-recovery-review.md)。不能據此寫成「刪掉歷史就解決」。

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

**引用：**[服務端 smoke](../../experiments/legacy-evidence/2026-09-15-openrouter-inline-compaction-live-smoke.md)、[9/16 延續壓縮設計及後續修訂](../../specs/2026-09-16-openrouter-continuation-compaction-design.md)。這只是當時組合的結果，不是 OpenRouter 永久不支援的主張；更不是原始訪談可刪除的授權。

### 2026-09-16 至 09-18：固定窗口詳記，不等於完整工作案例

即使詳記能保存，案例仍可能跨批次被補充、更正；因此原「B1 訪談窗口詳記＋B2 knowledge／guide」改為 **B1 維護完整工作案例，B2 維護跨案例工作理解，各有導覽與來源關係**。這是分析單位的改變，不只是換名。

當時還有 C repair，又發現 C 修改並解除舊關係後，下一批若只看 B1 的新變化，可能漏掉 B2 應重評的影響。後續從既有 receipts 和新舊 bindings 接回影響範圍，留下離線反例與回歸；沒有因此完成自然長訪談品質驗收。

**引用：**[分層重設計 §0–§3、§6.1](../../specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)、[背景流程 §2.4 的接力修正](../../specs/2026-09-17-layered-memory-background-workflow-design.md)。原件保留多次 successor；C 與 B2 回交等是歷史做法，不能帶入目前新目標。

### 2026-09-23：反覆摘要的主要負擔，竟是工具格式與近期回傳

自然 JD 撰寫試驗未完成後，沿 checkpoint 拆算實際 context：**17／17 次摘要後仍高於當時 16K trigger**。主要負擔是近期 JD 讀取與固定工具 schema，不是摘要太長；一頁讀取 31,329 字元中，重複定位 refs 約占 86%，文字 value 只有 320 字元。

離線測無損表格投影有減量，但仍過 trigger；把摘要換成一個字元的證偽下界仍不能跨過門檻。因此「再把摘要寫短」不夠，須同時考慮工具表示、近期保留範圍、壓縮收益與安全容量。這些測量只解釋反覆觸發，**不證明顧問未收尾的唯一語意根因**。

同一紀錄也試 tool search：服務端可回工具搜尋項目，但目前 adapter 的往返遺漏特定 item，顯示支援宣告、HTTP 成功與完整 App 接續能力仍不同。

**引用：**[自然試驗與停機後診斷](../../experiments/legacy-evidence/2026-09-23-gpt6-cw-natural-trial.md) 的「JD 撰寫回合的 context 膨脹」「重複 JD 引用」「工具定義按需載入」三節。token 分項是離線估算，不能當精確帳單；表格投影與一字元摘要皆不是已採用產品方案。

### 2026-09-24 之後：重新分工並自行管理 Context，再接受新驗證

新目標退役 C，重新釐清原始訪談、工作情境、工作理解與 JD；採 LangGraph＋OpenAI direct Responses，App 負責組裝 context、原生項目接續、導覽／按需工具、壓縮與安全點。Memory 版本、候選工作面、diff 與 JD 核對也經多次修訂，不能拿最早討論稿當最後契約。

**引用：**[reasoning／工具結果／state 研究](../../research/agent-systems/2026-09-26-reasoning-tool-results-and-state-boundary-research.md)、[context 設計沿革](../../specs/2026-09-26-consultant-context-and-state-design.md)、[目標架構地圖](../../target-architecture-map.md)、[T01–T18 計畫](../../plans/2026-09-29-target-rebuild/README.md)。最新實驗再遇到的早期依據漏選、Prompt 比較、長旅程中斷與續跑，接[近期案例索引](../research-casebook.md)及其原始證據；不是到此便全面解決。

## 可以連著讀的問題鏈

- **短答與過度概括：**7/20 的前問關係 → CT37 實際入料核對 → CT38 prompt／effort 對照 → CT42／49 長訪談。
- **能保存與能使用不同：**早期 Graph 歷史 → State 大小比較 → routing spike → CT42 回查效率 → 新目標引用／按需讀取。
- **工具會影響分析效果：**行號污染 old_string → patch wrapper／hunk 順序 → 引用保留 → 9/23 重複 refs 與 schema 膨脹。
- **分層本身也在迭代：**固定窗口詳記 → 跨批案例 → 理解與來源影響 → 新目標 Snapshot／工作面；每次都要區分設計決定與已有的實測。

這些只是方便回讀的素材路線，不先判定哪條一定要放推甄正文。所有原失敗、未驗項目與外送資料限制仍以各原件為準。
