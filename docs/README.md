# Caliburn 文檔索引

本目錄是 repo 的文檔權威。現行產品是本機 Web Job Analysis；current-only 硬切後，只有現行 code、ADR 0057、current design 與 runbook 可指導 current 產品的新施工。repo 另外保留一組與 current 完全隔離的 RAG bounded context（`pdf-to-json`／`ocs-indexer`／`embedder`／`ocs-contract`／`indexer-contract`），設計見 [`design/rag-pipeline.md`](design/rag-pipeline.md)；它們有自己可獨立驗證的 runtime 與 schema，只是不屬於 current API/Web。已刪除的舊訪談／`job_authoring` 內容則保留在歷史研究與 ADR 中供追溯，不代表仍有 runtime 或 schema。

## 先讀

- [產品核心目標](product-notes.md) — 一個 JD App；人與 LLM 共用 relational JD 業務邏輯，framework 經 OpenRouter 使用 Luna。第一版只要求看／撤回當輪 LLM 的 JD 變更；既有完整歷史可保留但不再擴張，對話或 Memory 不隨 JD 撤回。

- [`../AGENTS.md`](../AGENTS.md) — agent 工作紀律與 current-only 邊界。
- [`current-decisions.md`](current-decisions.md) — **目前有效／未決／暫停事項的唯一閱讀入口**；先看這裡，再決定需不需要打開長研究稿。
- [`decision-process.md`](decision-process.md) — 從產品目的、研究、Owner 決策、design／spike、ADR、施工到驗收的 gate、停止與翻案規則。
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — 現行 monorepo 與 API／Web 邊界。
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — 安裝、開發、測試與提交。
- [`runbook.md`](runbook.md) — PostgreSQL、API、Web 起停與 fresh DB。
- [`product-notes.md`](product-notes.md) — 產品範圍與 UX 優先級。

> 下方是文檔目錄，不是施工授權清單。若標題中的 `latest`／`final`／`approved`、文件內狀態或聊天內容互相衝突，以 [`current-decisions.md`](current-decisions.md) 指定的 current authority 與 stage 為準；它本身也不能越過 Accepted ADR 或現行 code。

## JD 核心知識與成品研究

[完整工作分析與高品質 JD 入口](specs/2026-09-09-job-analysis-and-jd-content-research.md#2-文檔各負責什麼)提供本組的閱讀地圖：分析／訪談方法、欄位語意、客製化深度、國際方法與實際雇主證據、完整樣稿及雙向審查。**這組是新產品如何理解工作、寫出 JD 的核心知識依據，不是可跳過的聊天附錄；也不是目前程式已如此實作的宣告。**

先看register的狀態，再依入口的「完整閱讀順序」閱讀相關正文。內容規則、來源、樣稿與審查各有負責文件；不把全部內容複製進總索引或某個大計畫。進入prompt、編輯／資料設計或施工前，按入口說明引用適用規則及待決事項，不從歷史程式反推新內容。

## 現行設計與決策

- [`plans/2026-09-10-jd-product-delivery.md`](plans/2026-09-10-jd-product-delivery.md) — **從現有成果到本機可用成品的執行總計畫**：Owner已要求實作；核心由原六切片Task1開始，完整旅程／品質驗收／正式採用並行。只在目前電腦App內使用，封存／恢復保留資料；各階段完成狀態依register及計畫，不以設計或離線驗證代稱產品完成。
- [`specs/2026-09-17-managed-app-background-callback-design.md`](specs/2026-09-17-managed-app-background-callback-design.md) — **JD-R002／MEM-L001 managed App 接線 G7 離線窄切片完成**：共用 A graph 無建構期 document reader；每次 invocation 注入兩文件隔離、每個 employee input 只讀一次的 availability provider。App-owned `BackgroundCoordinator` map 僅作 process-local single-flight，startup 在 Runtime ready 後才按 catalog＋durable state 恢復；一般 turn settle wake、shutdown drain 與 manual／no-key 無 coordinator 邊界保持。[§7 fresh evidence](specs/2026-09-17-managed-app-background-callback-design.md#7-g7-驗收與實際證據)另保存 Task 3 T3-R1 已關閉的 synthetic UI helper composition seam 及「未啟動 DB／lifespan／listener／瀏覽器」限制。最終受影響集合 **128 passed／2 skipped／1 warning**，最終完整 App **3,016 passed／320 skipped／5 warnings**，compileall 成功；零 provider／正式 key／付費／schema／migration。仍未完成 layered C、自然模型／付費、完整瀏覽器 App 旅程、production authority，以及多 process 拓撲下才需要的原子 admission claim；唯一下一 gate 是獨立 layered C bundle repair。
- [`superpowers/plans/2026-09-17-managed-app-background-callback.md`](superpowers/plans/2026-09-17-managed-app-background-callback.md) — **已完成的 managed App callback 窄 G7 施工計畫**：Tasks 1–4 依序固定 per-run availability、App-owned coordinator、ready 後背景恢復及完整離線證據；實際命令、首次環境失敗與最終結果見上方設計。本計畫沒有進入 C、provider smoke、完整瀏覽器 UI、schema 或 production 切換。
- [`specs/2026-09-16-consultant-interview-working-state-design.md`](specs/2026-09-16-consultant-interview-working-state-design.md) — **JD-R002／CTX-W001 主顧問訪談工作面 G4 候選**：從滿分 JD、完整工作分析與官方長任務設計反推最小欄位，讓 A 在第一輪尚無 Memory、一次問不完或尚未 compaction 時保存 Focus 與待追查事項。Stored state 與 Tool patch 分離，新增只必填三個核心語意欄位；它不是第二套 Memory、Agenda、固定問卷或 B1／B2 來源，待 Owner 複核後才進窄 G7。
- [`specs/2026-09-16-openrouter-continuation-compaction-design.md`](specs/2026-09-16-openrouter-continuation-compaction-design.md) — **JD-R002／CTX-C001 App-side 離線接線已完成**：維持單一 OpenRouter／Luna，以非破壞式 continuity summary 縮小 A／B1／B2 request；canonical 原文、Memory／JD authority 不變，不切 direct OpenAI、不等待原生 compaction item。正式 role factory 與 managed callback successors 亦已完成；下一 gate 統一依本頁 managed App 條目，不沿舊 H4 中途順序。
- [`specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md`](specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md) — **JD-R002／MEM-L001 最新 Memory 產品語意與 G7 狀態**：B1 維護完整且可修正的案例／任務／事件與案例 guide，B2 維護穩定工作理解與理解 guide；兩層採同一 publication。Bundle、完整回合引用與兩層按需查找、B1／B2 staged Agent graphs、package 外層有界 rework／共同 publication／stale recovery、App dispatcher／正式資源、compaction、role factory 與 managed callback 均已完成各自離線切片；唯一下一 gate 是 layered C bundle repair，provider／自然模型、完整瀏覽器 App 旅程與 production authority 其後分開驗證。
- [`specs/2026-09-17-model-runtime-parameter-ownership-review.md`](specs/2026-09-17-model-runtime-parameter-ownership-review.md) — **MEM-L001 模型／Runtime 權責收斂**：撤回把全域 `turn_sequence` 當必要產品欄位的過早結論；改採 Runtime-issued、attempt-scoped `evidence_key` 與明示 ordered blocks。模型只做案例／理解／證據的語意選擇；signed reference、canonical order、offset、版本、ID 配置與完成 outcome 由 Runtime 管理並 fail closed。
- [`plans/2026-09-17-interview-evidence-citations.md`](plans/2026-09-17-interview-evidence-citations.md) — **MEM-L001 已完成的引用前置切片**：沿用現有 `source`，由 conversation owner 證明 canonical order；B1 只選 Runtime 已提供／已讀的短 `evidence_key`，Runtime 完成 reference 解析、排序與 revise／split／merge 分配，B2 保持同序按需回查且不再讓模型填 signed reference／offset。該片本身不接 publication；後續 package 背景 workflow 已完成，現況依上方 MEM-L001 規格。
- [`specs/2026-09-17-layered-memory-background-workflow-design.md`](specs/2026-09-17-layered-memory-background-workflow-design.md) — **MEM-L001 完整背景 workflow 與 App 離線 successor 鏈**：deterministic B1→B2 chain、有界 rework、同步 request checkpoint、attempt identity、來源游標單調性及既有 CAS／receipt 已完成；後續亦完成 dispatcher／真 PG 新程序合成恢復、compaction、正式 role factory 與 managed callback 各自切片，不新增第三個 LLM orchestrator。仍未完成 layered C、自然模型／付費、完整瀏覽器 App 旅程與 production authority。
- [`plans/2026-09-16-b1-case-maintainer.md`](plans/2026-09-16-b1-case-maintainer.md) — **B1 第一施工切片與下一接點**：記錄可沿用的來源／checkpoint／patch 能力、Runtime-owned stage 與工具契約、read-before-write、離線反例及明確未做範圍。

- [`specs/2026-09-12-jd-relational-editing-requirements.md`](specs/2026-09-12-jd-relational-editing-requirements.md) — **JD-R002/C01／C03 最新 Owner 方向**：關聯式資料與 duty／task／成果／要求／K/S 項目管理取代完整 Plate JSONB 作後續 current-authority 前提；格式不重議。
- [`specs/evidence/2026-09-12-jd-relational-editor-evidence.md`](specs/evidence/2026-09-12-jd-relational-editor-evidence.md) — **官方證據層**：OpenAI、Anthropic、PostgreSQL、Plate、iCAP、Microsoft／Notion 與本地新舊實作的事實／推論／本案映射／unknown。
- [`specs/2026-09-12-jd-relational-editor-design.md`](specs/2026-09-12-jd-relational-editor-design.md) — **G4 整體設計**：同頁結構化管理畫面、六章關係、relational current＋derived history、Plate leaf role、差異／來源／匯出及 D01 OPEN。
- [`specs/2026-09-12-jd-relational-schema-and-write-contract.md`](specs/2026-09-12-jd-relational-schema-and-write-contract.md) — **資料庫層**：13 張 JD scope 表、欄位／PK／FK／delete actions／indexes、文件 head、immutable snapshot、operation receipt 與同交易流程。
- [`specs/2026-09-12-jd-relational-agent-tool-contract.md`](specs/2026-09-12-jd-relational-agent-tool-contract.md) — **App／AI 契約層**：七個小型 strict 業務工具、App-issued refs、人工變更通知、真實結果、來源與重試邊界。
- [`specs/evidence/2026-09-12-jd-relational-editor-review-brief.md`](specs/evidence/2026-09-12-jd-relational-editor-review-brief.md) — **第三方審查入口**：固定閱讀順序、審查題、已知 OPEN、自審結果與 finding 格式。
- [`adr/0075-relational-jd-authority-and-structured-editor.md`](adr/0075-relational-jd-authority-and-structured-editor.md) — **Proposed successor**：若通過，取代 0073 的完整 Plate JSONB current authority；目前等待外部 review 與 duty-delete D01，未授權建表或 production 切換。

- [`specs/2026-09-09-jd-oss-editor-capabilities-and-gaps.md`](specs/2026-09-09-jd-oss-editor-capabilities-and-gaps.md) — **JD-R002/C03 當前入口**：S1／S2 研究已交付；§6.2 的訪談主導、AI 主寫、多文件與真人後續核對方向已同意，續收斂完整情境與 App 能力。先前付費候選及逐批 pending 優先排序不作採用決定，最新狀態依 register。
- [`specs/2026-09-09-jd-editor-framework-decision-candidate.md`](specs/2026-09-09-jd-editor-framework-decision-candidate.md) — **歷史 Plate 文件底座候選**：沿用 Memory／JD 基線、非每輪改稿；選型理由、原生證據及反例保留。2026-09-12 的 relational current 方向已取代整份 Plate authority；是否在單一文字欄位使用 Plate 依 0075 的 leaf spike。
- [`specs/2026-09-09-jd-editing-and-review-working-design.md`](specs/2026-09-09-jd-editing-and-review-working-design.md#77-owner-裁決持續工作稿保留差異與更正) — **持續工作稿已同意（WORKING）**：保留完整差異、聊天／手改更正；個別待審接受／取消不列本版功能，停止分組／結算研究。舊選項與證據保留，未完成事項依 register。
- [`specs/2026-09-09-jd-editor-app-integration-design.md`](specs/2026-09-09-jd-editor-app-integration-design.md) — 文件／工具／唯一 JD 交易候選，含 Plate／Deep Agents 分工及保存結果契約；[待審比較](specs/evidence/2026-09-09-jd-native-pending-review-comparison.md)、[現成 codec 四項實證](specs/evidence/2026-09-09-jd-native-pending-codec-probe.md)、F01／P01 各自保留限制。完整審閱與 production authority 未採用，下一題依 register。
- [`specs/2026-09-10-jd-plate-document-profile.md`](specs/2026-09-10-jd-plate-document-profile.md) — clean 文件、官方清單／表格插件、ID／JSON／normalization 與同畫面 renderer；[F02](specs/evidence/2026-09-10-jd-official-profile-probe.md)第二輪四組通過，首輪失敗保留，仍未驗 DOM／IME／完整 profile。
- [`specs/2026-09-10-jd-app-tool-contract.md`](specs/2026-09-10-jd-app-tool-contract.md) — 三個 JD 工具的已讀引用、來源接點、真實結果及中斷恢復語意；保持同一既有顧問，不另建 Agent／Memory。
- [`specs/2026-09-10-jd-editor-contract-schema.md`](specs/2026-09-10-jd-editor-contract-schema.md) — 核心契約總審完成；文件、模型參數、App／Node、人工保存／選取的單一 schema，85 defs 限定離線通過。本機驗證、SDK 傳遞與真 provider 接受分列；[官方複核](specs/evidence/2026-09-09-jd-app-tool-and-review-contracts.md#213-契約定稿前的官方複核參數結果版本與重試)不把本案 mapping 稱為共識。
- [`plans/2026-09-10-jd-editor-core-implementation.md`](plans/2026-09-10-jd-editor-core-implementation.md) — 六個核心隔離施工切片：文件／保存／工具／同畫面／恢復／專業方法；未執行，production 的 Memory authority 正式化另有明確依賴。
- [`specs/2026-09-10-jd-export-and-consultant-handoff.md`](specs/2026-09-10-jd-export-and-consultant-handoff.md) — **PARKED**：Owner 表示真人交付核對先不做；保留 HTML／DOCX＋原始問答研究，移出本版核心施工與驗收。
- [`adr/0073-plate-jd-app-working-document-and-revision-authority.md`](adr/0073-plate-jd-app-working-document-and-revision-authority.md) — **歷史 Proposed；active candidate 已由 0075 取代**：保留完整 Plate JSONB、版本／receipt、單 writer 及故障實證；不得再由此直接推進 adoption。
- [`specs/2026-09-09-jd-app-native-capability-crosswalk.md`](specs/2026-09-09-jd-app-native-capability-crosswalk.md) — 依已同意主體驗映射完整流程、失敗與必要原生能力；OpenAI Codex／ChatGPT、Anthropic Claude 必查，現行／沿革分列。候選與下一單位依上方定案候選，不另設競爭中的討論 gate。

- [`specs/2026-09-09-llm-app-tool-use-and-document-editing-common-practices.md`](specs/2026-09-09-llm-app-tool-use-and-document-editing-common-practices.md) — **JD-R002/C03 共同基礎 G3／WORKING**：Owner 已同意 LLM 使用 App 與編輯文件的共同分工；近期進度沿既有方案 §0.1，當前候選與下一步統一依上方免費開源研究，不沿舊付費驗證排序。

- [`design/consultant-runtime.md`](design/consultant-runtime.md) — LangChain／LangGraph durable consultant、context、Skills、文件審核／authority、API、Web 與 export 的端到端真相。
- [`adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`](adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) — **Accepted** framework replacement、單一 durable authority、Big-bang 與延後 RAG 的決策。
- [`adr/0066-persistent-ai-jd-working-draft-and-semantic-review.md`](adr/0066-persistent-ai-jd-working-draft-and-semantic-review.md) — **Accepted** 一份 JD 一個持久、非權威工作草稿，以及 derived semantic review 與員工 authority。
- [`adr/0067-deep-agents-store-backed-jd-working-draft.md`](adr/0067-deep-agents-store-backed-jd-working-draft.md) — **Accepted** 以 Deep Agents `StoreBackend`／LangGraph Store 保存 active workspace；Saver 仍負責對話與核准 authority。
- [`adr/0068-framework-run-budgets-replace-lookup-wave-cap.md`](adr/0068-framework-run-budgets-replace-lookup-wave-cap.md) — **Accepted** 以 LangChain model／Tool budgets 與既有 token／cost／elapsed guards 取代自寫 lookup-wave 上限。
- [`adr/0069-shared-current-jd-working-copy-and-semantic-approval.md`](adr/0069-shared-current-jd-working-copy-and-semantic-approval.md) — **Accepted** 共用「目前 JD」工作副本、只讀核准基線與 derived semantic review。
- [`adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md`](adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md) — **Proposed；owner 已核准施工，待 implementation gate 後 Accepted** 三欄顧問工作區、AI after-state 編輯仍待審、OPKS 未定位分流、ownership lifecycle 與 Web framework 方案 A。
- [`adr/0071-revisable-work-understanding-context-and-review-provenance.md`](adr/0071-revisable-work-understanding-context-and-review-provenance.md) — **Proposed；待整體重寫或 successor，不可直接施工**。產品目的仍可參考，但 Case／Pattern／Unresolved、checkpoint authority、revision／CAS／lineage 等較早形狀已由 2026-09-02 Memory 重驗降回候選；任何 production authority 變更仍須明確取代 Accepted ADR 0060。
- [`adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md`](adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md) — **Proposed；deferred candidate**。只有代表性長訪談證明官方 Store recall 不足才重開；目前不授權 Qdrant、Voyage、outbox 或另一套 Memory authority 施工，也不接 Reference RAG。
- [`specs/2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md`](specs/2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md) — OpenAI／Anthropic／Microsoft／Google／LangChain 官方做法、方案比較與現行產品邊界。
- [`specs/2026-08-25-shared-current-jd-working-copy-and-semantic-approval-research.md`](specs/2026-08-25-shared-current-jd-working-copy-and-semantic-approval-research.md) — **Proposed** 共用「目前 JD」工作副本、只讀核准基線、語意審核、direct edit 與必要澄清的最新官方研究及建議方案。
- [`specs/2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md`](specs/2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md) — **owner 已複核並授權施工** 顧問工作區完整 UI／authority 設計、官方來源、framework mapping 與驗收情境。
- [`specs/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md`](specs/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md) — **產品原則已由 Proposed ADR 0071 收斂；§15.21 的三種 Work Understanding 責任、runtime-owned metadata 與 `WorkUnderstanding／WorkEpisode／OpenIssue` 暫名已獲 Owner 可翻案的暫時同意，§15.21.17 已區分 conversation compaction、framework memory 機制與 Caliburn domain 語意；紀錄邊界與精確 Tool branches 仍待複審** 跨輪對話、未回答問題、工作理解／待釐清／目前訪談重點、目前 JD／pending review 與最小充分 Context 邊界。
- [`specs/2026-08-30-agent-memory-landscape-and-decision-working-research.md`](specs/2026-08-30-agent-memory-landscape-and-decision-working-research.md) — **Working research；尚未選方案或授權施工** 先獨立比較 OpenAI、Anthropic、Google、AWS、Microsoft 與主流 Memory 框架的最新流程，再由共同基線與分歧逐項討論最佳方案；不預套 Caliburn 舊元件或實作。
- [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) — **Working contract；產品效果基線**。以 M1～M11 固定長訪談 Memory 必須達成的效果，並把模型語意、Runtime authority 與 framework mechanism 分開。
- [`specs/2026-09-04-decision-register-and-llm-baseline-reconciliation.md`](specs/2026-09-04-decision-register-and-llm-baseline-reconciliation.md) — **最新 reconciliation 入口**。消除跨 worktree 的 `MEM-Q005` ID 衝突，將 Memory read spike 以 `FAIL_UNPROVEN` 結束且不再重跑，帶回已核准的 LLM／Agent Working Baseline，並指定 `LLM-Q014` 為下一個唯一 gate。
- [`specs/2026-09-04-llm-machine-effects-and-sibling-results-working-design.md`](specs/2026-09-04-llm-machine-effects-and-sibling-results-working-design.md) — **LLM-Q014 G4.1／G4.2 已核准；G4.3 待討論**。固定單一 `create_agent` 根 loop，主顧問直接使用 LangMem Memory Tool 與 JD editing Tools；不固定先跑或巢狀使用 `create_memory_manager`；Tool result 採 framework-native success／error 並依真正恢復者分流。
- [`specs/2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md`](specs/2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md) — **G4.3b focused evidence；不授權施工**。拆解 OpenAI Codex 的兩階段 Memory 生成、`memory_summary.md → MEMORY.md → rollout summary → raw rollout` 讀取路徑、文字搜尋實作、成本界線及 Caliburn 不可直接照抄的限制。
- [`specs/2026-09-05-openai-conversation-context-and-memory-system-map.md`](specs/2026-09-05-openai-conversation-context-and-memory-system-map.md) — **G4.3b OpenAI 系統地圖；不授權施工**。分清 Conversation／Session、Compaction、Project／workspace、Codex／Sandbox Memory、Prompt Caching、Background Response，並整理每輪 Context 的自動注入、應用提供與按需讀取邊界。
- [`specs/2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md`](specs/2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md) — **Framework 官方事實圖；不授權施工**。還原 latest LangChain／LangGraph／Deep Agents／LangMem 的真實流程、primitive、recipe 與已知相容性風險。
- [`specs/2026-09-05-openai-memory-flow-to-latest-framework-functional-crosswalk.md`](specs/2026-09-05-openai-memory-flow-to-latest-framework-functional-crosswalk.md) — **歷史 G3；組合偏好已由 Q017 接續，不授權施工**。保留 OpenAI A／B／C 的責任級比對。
- [`specs/2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md`](specs/2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md) — **G2 detailed crosswalk；已複核修正；不授權施工**。保留逐 artifact 詳解；後續先讀下列審核結論。
- [`specs/2026-09-05-generic-memory-flow-framework-crosswalk-audit.md`](specs/2026-09-05-generic-memory-flow-framework-crosswalk-audit.md) — **Q017 審核沿革；最新主要組合方向已暫時同意**。保存 F01–F07、OpenAI 背景補查證據及前輪接合發現。
- [`specs/2026-09-05-openai-shaped-memory-framework-composition-research.md`](specs/2026-09-05-openai-shaped-memory-framework-composition-research.md) — **Q017 G3 Owner 暫時同意，未授權施工**。create_agent＋LangGraph＋獨立 filesystem／StoreBackend 為主要候選；LangMem 紀錄工具備選；保存 A／B／C 整體接力。
- [`specs/2026-09-05-memory-background-live-repair-coordination-research.md`](specs/2026-09-05-memory-background-live-repair-coordination-research.md) — **Q018 目前待審入口**。核對 OpenAI 實際 writer／failure 機制與框架邊界；比較修改週期序列化與 precondition 並寫，策略尚未核准。
- [`specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md) — **最新官方重驗入口**。核對 OpenAI、Anthropic、Google、AWS、LangGraph 與 Pydantic Harness 的完整列舉、版本、CAS、冪等與 provenance，校正哪些是共同效果、哪些只是條件式治理能力。
- [`specs/2026-09-02-memory-versioning-concurrency-and-replay-research.md`](specs/2026-09-02-memory-versioning-concurrency-and-replay-research.md) — **治理機制比較；以最新重驗校正後解讀**。保存各家 revision、CAS、idempotency、transaction 與 replay 的實際公開差異；custom adapter／receipt／manifest 只在對應風險出現時才重開。
- [`specs/2026-09-02-memory-foundation-vertical-slice-design.md`](specs/2026-09-02-memory-foundation-vertical-slice-design.md) — **PAUSED 歷史候選，不可施工**。其 Checkpointer-as-Semantic-Memory 前提已被 `MEM-Q001` 的 Checkpointer canonical conversation＋Store Semantic Memory 分工取代。
- [`specs/2026-09-02-memory-framework-selection-revalidation.md`](specs/2026-09-02-memory-framework-selection-revalidation.md) — **PAUSED 歷史複核**。框架比較可供追溯，但 substrate 結論不得越過 `current-decisions.md` 的 `MEM-Q001～Q006`。
- [`specs/2026-08-28-llm-authored-field-contract-audit.md`](specs/2026-08-28-llm-authored-field-contract-audit.md) — **Owner 已接受的目前欄位契約基線**：普通 assistant text、atomic tagged Tools、runtime-injected metadata、framework receipts 與 bounded repair；取代 flat all-required wire／固定巨型輸出表單。
- [`specs/2026-08-23-luna-structured-tools-and-context-official-audit.md`](specs/2026-08-23-luna-structured-tools-and-context-official-audit.md) — Luna／OpenRouter／LangChain／Deep Agents 官方文件重審、strict schema 實測與未提交 workaround 裁決。
- [`specs/2026-08-22-persistent-store-backed-jd-working-draft-completion.md`](specs/2026-08-22-persistent-store-backed-jd-working-draft-completion.md) — 持久工作草稿升級的產品對照、framework mapping、live evidence、Final Gate 與已知界線。
- [`plans/2026-08-22-persistent-store-backed-jd-working-draft-plan.md`](plans/2026-08-22-persistent-store-backed-jd-working-draft-plan.md) — 現行持久草稿逐 task 驗證、hard-cut、browser／live gate 與 traceability 計畫。
- [`superpowers/plans/2026-08-28-consultant-work-understanding-and-workspace-implementation.md`](superpowers/plans/2026-08-28-consultant-work-understanding-and-workspace-implementation.md) — **目前不可執行、待依欄位契約全面重寫** 的歷史逐 task 計畫；不可從其中舊 `ConsultantModelOutput`／flat wire snippets 反推需求。
- [`specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`](specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md) — 每個功能切片回看產品大方向與 framework 覆蓋的證據。
- [`contract-strategy.md`](contract-strategy.md) — 現行 `job-analysis-contract` 的契約規範。
- [`adr/README.md`](adr/README.md) — ADR 索引；0057 記錄 current-only hard cut。
- [`design/rag-pipeline.md`](design/rag-pipeline.md) — PDF → OCS contract → indexer → embedder/Qdrant 的 RAG 供應鏈；保留但與 current API/Web 完全隔離的獨立 bounded context，非 current 產品 runtime。

## 文檔分層

| 問題 | 位置 |
|---|---|
| 現行跨 app 流程、請求與不變量 | `docs/design/` |
| 單一 app 的 codemap／內部規則 | `apps/*/README.md`、`AGENTS.md` |
| 為什麼採這個決策 | `docs/adr/` |
| 研究、診斷、來源與選項 | `docs/specs/` |
| 可重現操作與故障排除 | `docs/runbook.md`、`CONTRIBUTING.md` |
| 實驗與 live evidence | `docs/experiments/` |
| 已淘汰的歷史材料 | `docs/archive/`、被標成 superseded／retired 的 ADR、spec、plan |

跨 app 文檔要把 UI 動作對到真實 endpoint 或純函式，寫出欄位真名、不變量與「已退役、不要呼叫」的路徑。動到該 seam 的 code，就在同一 commit 更新文檔。

## 歷史材料使用規則

被 ADR 0060 取代的 0058–0059 模組切割、`docs/design/task-analysis-engine.md` 的 Git 歷史、`docs/adr/0001`–`0056`、舊 interview／vNext research、舊 plans 與 archive 都是決策歷史。閱讀它們是為了理解取捨，不是恢復實作的授權。若要改變 current／RAG 邊界或 authority，必須另開研究與 successor ADR。
