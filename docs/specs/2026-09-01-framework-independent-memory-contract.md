# Caliburn 框架選擇前 Memory 現行契約

- 日期：2026-09-01
- 狀態：**Memory 討論的現行主入口；Working Contract，可經新證據與 Owner 討論翻案**
- 範圍：只整理選擇 Memory／Agent framework 前已收斂的產品效果與行為契約
- 非目標：不選框架、不定 schema、不寫施工方法，也不重述完整供應商研究

> **閱讀規則**：後續 Memory 框架比較先以本文為準。需要判斷本文的由來、精確證據、候選取捨或歷史翻案時，再回讀文末連結的研究文檔。若本文與較早研究段落衝突，以本文記錄的現行結論為準；若要改變本文結論，必須先列出新證據、影響與取捨並與 Owner 討論，不得靜默翻案。

> **2026-09-02 重驗校正**：最新官方資料確認 exact-scope 列舉／分頁與可重試副作用不重複是必要效果；但 immutable revision、per-record CAS、operation-receipt table、持久 inventory manifest 與「缺少 lineage 就拒絕」不是跨家共同第一版機制。本文以下已按 [`2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](./2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md) 校正；這不否定其成熟價值，只把它們改回有觸發條件的治理強化。

> **2026-09-02 底層機制校正**：功能共識不等於各家使用相同資料庫、鎖、cursor 或 retry loop。single writer、deterministic key、checkpoint worklist 與 LangGraph offset inventory 目前都只是候選映射，尚未獲准進施工計畫；逐項官方 primitive、成熟框架覆蓋與未決選擇見 [`Memory 實作機制與成熟框架共識稽核`](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md)。

> **2026-09-02 最新切片候選校正**：[`Memory Foundation 最小垂直切片設計`](./2026-09-02-memory-foundation-vertical-slice-design.md) 已否決先前把完整 Semantic Memory collection 放進 Checkpointer 的候選，並重寫為 Store-first：Checkpointer 只承接 thread／run state，每份 JD 隔離的 PostgreSQL Store 承接完整來源與目前 Semantic Memory，再用極小對照實驗比較 LangMem core 與 Store manager。這是待 Owner 複核的 Caliburn 映射，不是跨廠商共同底層，也尚未授權 production 改造；本文 M1～M11 效果不因此改變。

> **2026-09-03 責任分層 reconciliation**：上段 2026-09-02 Store-first 切片候選已由 [`MEM-Q001`](../current-decisions.md) 的 Working Decision 取代。現行目標設計是：LangGraph Checkpointer 保存每份 JD 的完整員工↔顧問 conversation 與 graph／run／interrupt state；PostgreSQL Store 保存可修訂 Semantic Memory collection；每輪模型 Context 從兩者非破壞性地有界組裝，不另建重複的 employee-source 文字 leaf。這項 Working Decision 尚未越過 ADR 0060 授權 production 施工；本文 M1～M11 的產品效果契約不變。完整證據與方案比較見 [`2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](./2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md)。

## 1. 唯一目的

Caliburn 的目的不是製作 Memory 系統，而是透過長期員工訪談，產出準確、完整、不重複、抽象層級合理、可持續修訂且由員工核准的高品質職務說明書（JD）。

Memory 的價值只有一個：讓 LLM 在長訪談後，仍能取得形成與檢查該份 JD 所需的完整、目前有效且細節足夠的員工工作資訊。

來源：[高品質 JD 能力研究 §1、§5](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)

## 2. 框架選擇前已收斂的完整形狀

```text
完整、可回查的訪談來源
        ＋
同一 JD 範圍內多筆聚焦、詳細、自足且可修訂的 Semantic Memory
        ＋
一份很小、可由目前有效 Memory 重建的導覽
        ＋
日常少量自動召回，模型需要時再搜尋／讀取
        ＋
製作、重大重整或全面檢查 JD 時，確實列舉全部目前有效 Memory
```

這五項是目前的**框架無關行為契約**，不是五套資料庫，也不預先指定 Markdown、JSON、檔案、向量資料庫、graph 或任何 framework class。

來源：[Memory mapping §9.39～§9.40](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md)、[通用 Memory 研究 §6、§9、§13](./2026-08-30-agent-memory-landscape-and-decision-working-research.md)

## 3. 五個部分各自負責什麼

### 3.1 完整訪談來源

- 員工訊息先耐久保存，能在關閉後繼續訪談。
- 原始來源用於查錯、解析更正與指涉、核實細節，以及在整理後 Memory 可能失真時回查。
- 原始來源不等於每輪都要注入的 Context，也不等於已整理的目前工作知識。
- 不要求 LLM 為每筆 Memory 手填 quote、source UUID、版本或時間。

### 3.2 聚焦、詳細、可修訂的 Semantic Memory

- 同一份 JD 可有多筆 Memory；一筆表達一個可獨立取回與修訂的連貫工作主題，而不是一則訊息、一個零碎 fact 或一個 JD 欄位。
- 這裡的「同一份 JD」只表示同一名員工、同一段職務訪談的隔離 scope；Memory 不是從 JD 欄位產生，也不必綁定 Duty、Task 或 OPKS。
- 在已知時，內容應保留會影響 JD 判斷的行動、對象、目的／成果、條件／情境、頻率／例外、協作與責任邊界。
- 不知道的內容維持不知道，不能為了填滿欄位而猜。
- 新資訊可能是新增主題、補充、明確更正、不同案例、未解衝突或 no-op；不能把所有差異都當成覆蓋更新。
- 明確更正後，正常召回使用新的目前有效內容；舊說法至少可透過完整來源回查；若所選 substrate 提供 revision history，也可由該歷史回查。
- 未解衝突與重要未知可以是合法的目前知識，不能只依最近、語氣或 confidence 自動選邊。
- 一次案例不能自動升格成長期 Task；案例如何一般化、合併或拆分由 LLM＋職務分析 Skill 判斷。

這些是語意保存政策，不是正式 schema。

> **反覆修正語意（2026-09-01；Owner 已確認，2026-09-02 校正實作邊界）**：每份 JD scope 具有一組彼此隔離、可持續修訂的 Semantic Memory。新員工訊息先進入耐久 conversation，再與少量可能相關的目前有效 Memory 比較：同一工作主題的新細節或明確更正修訂既有目前內容；可獨立搜尋與修訂的新工作主題建立新 Memory；重複或無關內容可以 no-op；條件／時點／案例不同或尚未釐清的矛盾不得被誤當覆蓋。正常召回只使用目前有效內容，舊說法至少可由 conversation 回查。是否另外保存 immutable revision history 由 substrate 能力與實際 audit／recovery 需求決定；它不是模型欄位，也不是第一切片的跨家共同硬要求。是否屬同一筆 Memory 以「能否獨立搜尋、理解與修訂」判斷，不依 Duty／Task／OPKS 分類。

> **詳細設計進度（2026-09-01；2026-09-02 校正）**：Owner 已確認 A+ 作「單筆 Semantic Memory 的邏輯表徵」目前基線：可信 Store／Runtime metadata 與模型撰寫的 `title／topic＋rich self-contained content` 分離。A+ 不是完整 Memory 架構；物理 schema 與目前有效內容的持久映射仍待 framework 接線驗證，unknown／conflict 則由本節下方的產品語意規則補足。CAS 只在出現重疊 writer／lost update 時重開，inventory snapshot 只在全量盤點期間必須接受並行 mutation 時重開，不能從「仍待比較」誤讀成第一版必做。完整問題、限制與官方依據見 [Memory mapping §9.48](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md) 與[最小切片重驗](./2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)。

> **Admission 詳細設計進度（2026-09-01）**：Owner 已確認採「職務目的導向 admission＋成熟 extraction／consolidation＋完整原始來源保底」，不採 generic `useful／noteworthy` 預設，也不把全部 transcript 複製成 Semantic Memory。
>
> - 所有可用的員工來源訊息先留在完整 conversation；來源資格、哪些語意值得進 Memory、以及安全／保留政策是三個不同責任。
> - 只要員工提供的資訊可能改變現在或未來的 JD 分析，就應形成或修訂 Memory；出現頻率不能當門檻，年度一次、例外事件、核准責任、風險與工作邊界同樣不可漏。
> - 行動、對象、目的／成果、輸入輸出、頻率、情境、例外、工具／方法、判斷、協作／交接與責任邊界，在有提供且會影響 JD 時都屬候選；未知、未解衝突與明確更正也不能因尚非肯定 fact 而丟失。
> - 員工訊息與可信結構事件才是職務事實來源；助理訊息只協助解析上下文，未經員工支持的模型建議不能升格成工作事實。
> - 寒暄、純 UI／流程控制、沒有新增語意的重複、只屬當輪推理的中間文字與未獲員工支持的模型推測，可以合法 no-op。
> - Runtime 至少要能辨識每則可處理來源已成功形成／修訂 Memory、合法 no-op 或處理失敗；這是可觀察性與重試依據，不是要求模型填 source ID、狀態或 receipt。
> - 成熟 framework 可以負責 extraction、CRUD、去重與 consolidation，但不能用其 generic default 取代上述職務 admission policy，也不能自行宣稱已完整保存員工全部工作。

直接官方依據：[OpenAI Codex Memories](https://learn.chatgpt.com/docs/customization/memories) 將 Memory 定位為 useful recall layer 而非唯一權威；[Google Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories) 以 custom topics／instructions／few-shot 控制哪些資訊持久化；[AWS AgentCore Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html) 提供 managed、prompt override 與 self-managed 三層；[Anthropic Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) 允許應用限定只記錄指定 topic，並要求應用掌握 write validation。

> **未知／矛盾詳細設計進度（2026-09-01；現行 Working Baseline）**：回查先前對話後，當時已暫定以自然語言聚焦 Memory 保存跨回合未解問題，且不為每筆 Memory 增加 `known／unknown／conflict／confidence` 等模型欄位；較早研究則只裁決「未解不得冒充事實」，並曾保留自然語言 Memory 或 typed runtime state 兩種候選。本輪 Owner 再次同意沿用 content-only 作現行基線。這不是不可翻案的跨廠商定律；若後續框架研究或代表性驗證顯示無法可靠保留、召回或完整盤點，必須帶證據回來討論，實作者不得自行加欄位或專用型別。
>
> - 模型仍只撰寫既有的 `title／topic＋rich self-contained content`；不得為此新增或要求模型填寫 `status`、`kind`、`conflict_type`、`confidence`、quote offset、版本或時間。
> - 不知道就直接在內容中寫明「尚未確認」；遇到互斥說法則同時保留兩邊及尚未確認之處，不能由 recency、語氣或 confidence 自動選邊。
> - 若待釐清內容本身可獨立理解與取回，可以建立另一筆同樣 `title／topic＋content` 形狀的聚焦 Memory；這不是新的 Gap／Conflict 型別、資料表或第二份權威。若未知只屬某個連貫工作主題的一部分，也可留在該 Memory 內容內，不必把整筆 Memory 標成某種狀態。
> - 明確更正才更新目前有效內容；條件、時點或案例不同則保留各自適用範圍；真的尚未分辨才維持未解。舊說法至少留在完整 conversation；若 substrate 提供 revision history，也可由該歷史回查。正常召回只使用目前版本。
> - 若日後要顯示或提醒待釐清事項，只能由目前有效 Memory 重建導覽；導覽不是新事實來源。是否必須當下詢問員工屬 workflow 判斷，也不應變成另一套長期真相。
> - Framework 可以提供 extraction、版本、current head、CAS 與 consolidation 機制，但 generic consolidation 不得自行刪除或覆蓋尚未釐清的說法。

直接官方依據：[Google Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories) 的 managed consolidation 可能因新資訊矛盾而刪除既有 Memory，證明不能直接把 generic 衝突策略當成產品真相；[AWS AgentCore semantic-memory prompt](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html) 要求保留模糊指涉而非猜測；[Anthropic Managed Agent Memory](https://platform.claude.com/docs/en/managed-agents/memory) 提供 latest version、不可變 revision 與 optimistic concurrency，但不替應用判定哪個說法為真；[OpenAI Codex Memories](https://learn.chatgpt.com/docs/customization/memories) 公開定位為 recall layer，未公開足以讓本產品委託未解衝突判定的規則。

#### 3.2.1 目前有效內容、可選歷史與移除生命週期

> **詳細設計進度（2026-09-02 重驗校正）**：一筆邏輯 Memory 在正常使用時只有一份目前有效內容。正常讀取不得把已更正／已退出的舊內容混回 Context。Anthropic 與 Google 證明 immutable revision 是成熟的 audit／recovery 能力，但 Google 允許停用、AWS／LangGraph Store／OpenAI 公開契約也未共同要求同一機制；因此 framework-independent contract 不再規定「每次修訂必有不可變 revision」。

- 日常搜尋、按需讀取與 exact-scope 全量盤點只處理目前有效內容；若保存歷史，歷史不得與目前內容一起進入一般 Context。
- 同一工作主題的新細節或明確更正更新目前有效內容；舊說法至少由完整 conversation 保留，若 substrate 有 revision history 則可再用於診斷與復原。
- 條件、時點或案例不同時，應補充目前內容或建立可獨立搜尋／修訂的新 Memory，不得只因表面差異移除舊內容。
- 未解矛盾維持為合法的目前內容，不能依 recency、語氣或 confidence 自動刪除其中一邊。
- 員工明確確認「不是自己的工作」、既有內容確定歸屬錯誤，或多筆內容已確認合併時，相關內容應退出目前有效集合；完整 conversation 仍保留，revision history 則依所選 substrate／保留政策處理。
- 拆分時建立新的有效 Memories，原 head 退出有效集合；合併時建立或修訂合併後的有效 Memory，被取代的 heads 退出有效集合。這些是一般 Memory lifecycle，不需要模型輸出 `split／merge` 專用內容型別。
- 更新或移除不得在實際存在多 writer 時 silent last-write-wins。第一切片可明確採 per-JD serial writer＋可重放冪等寫入；只有允許並行 writer、出現 lost update，或 audit 要求提高時，才把 Runtime／Store 的版本或內容前置條件升格成硬要求。
- 物理上使用 framework 原生 delete／tombstone、archive namespace 或其他等價機制，留到框架接線階段依能力選擇；產品契約只要求「不再進入有效集合，但來源與可用歷史不消失」。

直接官方依據：[Anthropic Managed Agent Memory](https://platform.claude.com/docs/en/managed-agents/memory) 讓每次修改形成不可變版本，並提供可選 `content_sha256` precondition；[Google Memory Revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions) 將目前 consolidated Memory 與 revisions 分離、提供 rollback，也明示 revisions 可停用；[AWS ListMemoryRecords](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListMemoryRecords.html) 與 [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 提供不同的 persistence／listing primitive，沒有相同 revision／CAS 保證。OpenAI 公開資料只足以確認 extraction／consolidation 分層，未公開 application Semantic Memory 的 current-head／revision 內部實作。

版本、並行與重放的跨家機制差異，以及何時才需要 per-record CAS／operation receipt，見 [`2026-09-02-memory-versioning-concurrency-and-replay-research.md`](./2026-09-02-memory-versioning-concurrency-and-replay-research.md) 與[最小切片重驗](./2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)。共同硬效果是 replay 不重複；CAS、receipt、immutable history 與 `scope generation` 都依實際觸發條件選用。

### 3.3 小型可重建導覽

- 只提供目前有哪些工作主題、簡短描述，以及可繼續搜尋／讀取的入口。
- 不能保存只存在於導覽、詳細 Memory 找不到的工作事實。
- 必須能由目前有效 Memory 重建，因此不是第二份工作真相。
- 導覽落後或重建失敗時，系統必須能繞過它直接讀取 Memory。
- 全面盤點永遠直接列舉 Memory，不能拿導覽當完整性證明。

### 3.4 日常有界召回與按需深入

一般訪談回合只提供：

1. 穩定的顧問規則與本輪需要的 Skill；
2. 本輪訊息與足以理解指涉的近期對話；
3. 小型導覽；
4. 少量相關 Memory；
5. 必要時由模型繼續搜尋／讀取 Memory；
6. 只有查錯、更正指涉或核實原話時才回查訪談來源。

不得用每輪重送全部 transcript、全部 Memory 或完整 JD 來換取表面上的記憶能力。

> **詳細設計進度（2026-09-01）**：Owner 已確認採三種互補讀取模式，而不是把其中一種誤用於所有情境：
>
> 1. **一般訪談採自動、有界的混合召回。**Runtime 先鎖定目前 JD scope 與 current heads，再以本輪訊息和必要近期脈絡，取回少量相關 Memory。候選可結合 semantic relevance、文字／專有名詞命中與可信 filter；不能只依單次向量 top-k，也不能預設每輪載入全部 Memory。
> 2. **資料可能不足時由模型按需 `search／read`。**搜尋先回傳有界候選與簡短內容，模型只讀取選中的完整 Memory；模糊指涉、可能衝突／重複、較廣的比較或現有候選不足時，都可以繼續查找。這是日常自動召回的補充，不是要求模型每輪先做完整搜尋。
> 3. **製作、重大重整或全面檢查 JD 時改走 exact-scope 全量列舉。**Runtime 分頁走完全部目前有效 Memory，不能讓 semantic score、top-k、小型導覽或模型自行判斷「已看夠」刪減盤點集合。
>
> 「少量相關 Memory」只是日常訪談的第一批更新候選，用來控制成本與雜訊；它不是完整性邊界。若候選不足，模型可以繼續搜尋；需要保證整份 JD 涵蓋全部已保存工作時，必須改用上述 exact-scope 全量列舉。
>
> 這裡的「混合召回」是根據公開 retrieval 能力與跨家共同方向形成的 Caliburn 設計結論；它**不是**對 Codex 或 Claude 消費型產品內部 ranking 演算法的宣稱。OpenAI 公開 Retrieval 支援 semantic／text hybrid ranking、filter、threshold 與 query rewrite；Anthropic Memory Tool 公開 just-in-time directory／file read；Google Memory Bank 與 AWS AgentCore Memory 都把相似度搜尋和 list／retrieve-all／pagination 分開。LangChain 也明示 collection 雖可提高 downstream recall，卻可能讓 comprehensive context 與跨記憶關係變得困難，因此相關 top-k 不能代替全量盤點。

直接官方依據：

- [OpenAI — Retrieval：query rewrite、filter、ranking 與 semantic／text hybrid search](https://developers.openai.com/api/docs/guides/retrieval)
- [Anthropic — Memory Tool：just-in-time context retrieval 與按需 `view`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Google — Memory Bank：同一 scope 的 similarity search 或 retrieve all](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [AWS — Retrieve memory records：semantic top-k、分數與 pagination](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-retrieve-records.html)
- [AWS — List memory records：不經 semantic search 列舉 namespace 內容](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-list-memory-records.html)
- [LangChain — Memory overview：長 Context 成本／干擾與 collection 的 comprehensive-context 限制](https://docs.langchain.com/oss/python/concepts/memory)

### 3.5 可驗證的全量盤點

在製作完整 JD、重大重整、判斷涵蓋率或匯出前品質檢查時，Runtime 必須：

- 在受信任的單一 JD scope 中列舉全部目前有效 Memory；
- 走完所有分頁或批次；
- 維持本次處理 worklist／完成狀態，能證明每個列出的項目恰好進入處理；這可以存在既有 workflow checkpoint，不預設新的持久 manifest entity；
- 明確處理盤點期間的 mutation：第一切片採同 scope serial writer／暫停 mutation 或遇變更重啟；只有真的允許並行 writer 時才需要 snapshot／generation／revision manifest；
- 讓 LLM＋JD quality Skill 對全部 Memory 與目前 JD 判斷 covered／partial／missing／conflict，以及 duplicate／overlap／boundary。

Semantic top-k、最近項目、小型導覽或模型聲稱「都看過了」都不能代替全量盤點。Runtime 只保證資料完整送達與批次走完，不保證 LLM 的專業判斷必然正確；JD 變更仍由員工審核。

全量盤點也只能證明「全部已發布的 current Memory 都被處理」，不能倒推每則訪談的重要資訊一定已被正確整理進 Memory。因此來源事件的 Memory processing 必須可觀察：至少能知道處理成功、合法 no-op 或失敗，並能在失敗後重試；語意 admission 是否正確則仍需職務分析政策、代表性資料與員工審核，而不能由 framework 自行宣稱。

## 4. M1～M11 覆蓋檢查

| 能力 | 現行契約如何承接 |
| --- | --- |
| M1 長期連續性 | 耐久訪談來源＋可修訂 Semantic Memory＋跨關閉恢復 |
| M2 細節保真 | 聚焦但 rich、自足的 Memory；整理不能不可逆丟失重要細節；來源可回查 |
| M3 廣度完整性 | 職務資訊 admission policy＋來源處理狀態＋多筆 Memory＋全量盤點；不是只保存高頻內容 |
| M4 可修訂目前理解 | add／supplement／correct／different case／conflict／no-op 與 current head lifecycle |
| M5 未知與衝突不壓平 | 未知、未解衝突可合法保留；不依 recency／confidence 自動選邊 |
| M6 語意關係不丟失 | 一筆 Memory 保存連貫工作脈絡，不拆成無關 fact bag；第一版不因此預設 graph |
| M7 案例與穩定工作雙層可用 | 來源保留具體案例；Memory 保存會影響後續判斷的細節與目前理解 |
| M8 日常召回有界 | 小型導覽＋少量自動召回＋按需 search／read |
| M9 可驗證完整盤點 | exact-scope list-all／pagination＋可信處理 worklist／完成狀態；並行 mutation 的 snapshot 強化依實際需求觸發 |
| M10 原始來源回查 | Durable conversation／events 可搜尋與讀取；平常不全量注入 |
| M11 單一 JD 隔離 | scope／namespace／identity 由可信 Runtime 決定，模型不能選擇安全範圍 |

M1～M11 的中立定義見：[高品質 JD 能力研究 §5.2](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)。成熟能力與產品需求的逐項 mapping 見：[Memory mapping §9.2～§9.7、§9.22～§9.40](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md)。

## 5. Memory 不負責什麼

Memory 只負責保存、修訂、搜尋、讀取與完整列舉工作資訊。它不能自行：

- 判斷一段內容應成為 Duty、Task、工作細節、完成標準或 K／S；
- 決定案例如何抽象、合併、拆分或去重；
- 判斷現在是否應修改 JD；
- 撰寫或發布正式 JD；
- 把每筆 Memory 一對一映射成 JD 欄位；
- 把新 Memory 自動套用到 JD；
- 取代員工核准。

正確責任如下：

| 層 | 責任 |
| --- | --- |
| Memory | 保存、修訂、搜尋、讀取與完整列舉工作資訊 |
| LLM＋職務分析 Skill | 理解、訪談、判斷、比較、抽象、去重及決定是否提出 JD 變更 |
| Tool／Runtime | 執行受限操作、驗證、管理 scope／ID 與 framework 已啟用的可信版本／並行條件、回傳 typed result／error |
| 員工 | 接受、修改後接受或拒絕 AI 變更；核准後才成為正式 JD |

「具體工作案例 → 目前工作理解 → JD」只是顧問認知關係，不代表三份持久文件、三個 store、三個固定 stage 或三次模型呼叫。

來源：[高品質 JD 能力研究 §5.3～§5.5](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)、[Memory mapping §9.32～§9.35](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md)

## 6. 更新與發布時序

框架必須能承接下列行為，但本文不固定 node 數或模型呼叫次數：

```text
員工訊息先耐久保存
        ↓
目前 Memory + 相關 conversation + 本輪訊息 + 目前 JD
        ↓
形成本輪已驗證的語意理解
        ├─ Semantic Memory mutation
        └─ optional JD 待審變更
```

- 這仍是 dependency-aware hybrid，但依賴必須按**實際讀取關係**判斷，不是把所有 durable effects 一律串在 Memory publication 後。
- 同一 run 由同一組輸入與同一份已驗證理解形成的 Memory mutation 與 JD 待審變更是並列 effects；JD 依賴語意內容，不依賴該內容先寫入 Store。
- Memory 因格式、暫時性基礎設施或 Store 寫入問題失敗，不刪除、不阻擋、也不自行標 stale 已通過自身驗證的 JD 待審變更。只有重新分析後的理解或 JD base state 實質改變，相關候選才重驗／stale。
- 真正需要重新讀取已發布 new head 的下一個獨立步驟仍須等待；最終全面製作／檢查也必須先處理全部有效來源與 Memory，才能宣稱完整涵蓋。
- 員工明確更正時，原始訊息一定先耐久保存，但「更正」這個事件名稱本身不構成一律同步的跨家規則：本輪後續實質判斷若依賴修訂後的持久 Memory，才必須等待發布；若本輪只需依目前訊息與近期對話正常回應，Memory Manager 可以背景更新。
- Memory 更新不會自行修改 JD。
- 員工直接修改 JD 也不會自動改寫 Memory；後續若 LLM 發現文件與工作資訊衝突，透過正常訪談釐清。

> **2026-09-04 `MEM-Q005` reconciliation（Owner 已核准）**：本節先前把「提出或修改 JD」整類視為 Memory publication hard gate，混淆了「JD 使用哪份語意內容」與「同一份語意內容是否已成功持久化」。OpenAI Codex Memory 可背景更新且可能延後／略過；Anthropic 則明確把 dependent／independent Tool 的排序交給 application。這些官方事實不支持 Memory 技術性持久化失敗必須一併丟棄由相同 Context 形成的 JD 候選。完整事實、Caliburn mapping、失敗矩陣與重開條件見 [`2026-09-04-memory-persistence-and-jd-effect-reconciliation.md`](./2026-09-04-memory-persistence-and-jd-effect-reconciliation.md)。

> **跨家更新時序與 writer 複核（2026-09-01；2026-09-04 依 `MEM-Q005` 校正）**：官方公開機制不支持「一律由主 agent 在 hot path 寫入」或「一律交給背景 worker」任何一個極端作為跨家共識。OpenAI Codex 對合適的歷史對話採背景 extraction／consolidation；Anthropic 讓同一 agent 可在工作途中用 Memory Tool 即時讀寫；Google Memory Bank 同時提供 blocking 與 background generation；AWS AgentCore 將 long-term extraction／consolidation 放在背景；LangChain／LangMem 則把 hot path 與 background 都列為正式模式。因此共同原則是：**只有下一個動作必須讀取新發布 Memory 結果時才等待；同一 Context／理解形成的並列 effect 不因 Memory 尚未持久化而自動失效。**其餘抽取、去重與重整可以延後或背景化。
>
> **2026-09-05 supersession：**下列「固定由單一 Memory Manager 作語意 writer」與其後「第一版只由主顧問 direct Tool 寫入、不加入背景 manager」都已是歷史候選。Product Owner 已在 [`LLM-Q014` G4.3b-4a](./2026-09-04-llm-machine-effects-and-sibling-results-working-design.md#13-g43b-4a-三路-memory-生命週期product-owner-已核准) 核准三條互補責任：每輪即時讀取／Context、背景 extraction＋consolidation，以及只針對已明確過時 Memory 的窄幅 live repair。它們可以共用相同的職務領域保存政策，但不是固定每輪先跑的同一個步驟；scope、ID、revision、排程與持久化仍由 Runtime／Store 負責。exact manager、Tool、模型與排程 wiring 留待後續 gate。
>
> ~~語意 writer 暫定只有**一套 Memory Manager**：它使用同一組 admission、extraction 與 consolidation 規則，分析 conversation 與候選 current Memories，產生 add／update／remove／no-op；同步與背景只是這套 Manager 的兩種排程方式，不得另寫兩套會產生不同語意的 writer。主顧問可以指出「後續判斷是否立即依賴最新 Memory」並請求處理，但不直接管理 scope、ID、revision 或持久化；Runtime／Store 驗證並發布 mutation。這不要求常駐第二個 agent，也尚未決定 Manager 使用哪個模型、framework class 或實體部署方式。~~
>
> **排程權責（2026-09-01；2026-09-04 依 `MEM-Q005` 校正）**：Memory Manager／LLM 只判斷語意上的 add／update／remove／no-op 與內容；Application／Runtime 根據下一個動作是否真的需要**重新讀取新發布 Memory**，決定同步等待或排入背景。不得要求模型另外填寫 `needs_sync`、時序、重試或基礎設施狀態。Runtime 不得只因 JD 是 durable effect 就虛構 hard dependency；JD 與 Memory 若來自同一份已驗證理解，必須分別回報與保存各自結果。

#### 6.1 Hard gate 動作映射

> **詳細設計進度（2026-09-01；Owner 暫時同意的 Working Baseline）**：跨家可直接支持的判準只有「目前動作是否需要使用這次 Memory generation 的結果」；各家不會替 Caliburn 定義哪些產品動作屬於 JD hard gate。下表是把該共同判準映射到本產品的暫定決策，不能冒充供應商原生規則。

| 動作 | 暫定時序 | 理由 |
| --- | --- | --- |
| 一般訪談回答 | 可背景 | 本輪訊息與必要近期對話仍在目前 Context，不需先等待持久 Memory 發布 |
| 提出澄清問題 | 可背景 | 問題可由目前訊息、既有 current Memory 與近期對話形成 |
| 提出或修改 JD 變更 | 可與 Memory mutation 形成並列 effect；分別驗證 | JD 使用的是同一 run 的語意內容，不必等待該內容先寫入 Store；Memory 技術失敗不丟棄有效候選 |
| 全面檢查 JD 或宣稱完整涵蓋 | 同步等待相關 pending Memory，並對穩定 current-head 集合全量盤點 | 完整性宣稱不能忽略仍在處理的有效來源 |
| 結束本輪、休息或關閉應用 | 不阻塞 | 原始來源先耐久保存；Memory 工作必須可在背景續跑或下次恢復 |
| 去重、重整與導覽更新 | 背景 | 不影響目前語意正確性的維護工作不應增加互動延遲 |

只有兩類情況需要 publication barrier：第一，下一個步驟確實要重新讀取新 Memory head；第二，全面盤點或完整涵蓋宣稱需要確認所有有效來源均已成功形成 Memory 或合法 no-op。JD 待審變更若與 Memory mutation 來自同一份已驗證理解，不屬第一類。是否屬「相關 pending」及盤點期間採 serial writer、遇變更重啟或 snapshot，留待實際 writer 模式決定；不得預設一定要 snapshot，也不得靠模型聲稱「應該完成了」。

直接官方依據：[OpenAI Codex Memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)、[OpenAI Tools](https://developers.openai.com/api/docs/guides/tools)、[Anthropic Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)、[Anthropic Tool-use contract](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)、[Anthropic Parallel Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)、[Google Memory Bank Generate Memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)、[AWS AgentCore Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)、[AWS CreateEvent](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_CreateEvent.html)、[LangChain Memory overview](https://docs.langchain.com/oss/python/concepts/memory)、[LangMem conceptual guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)。這些資料共同支持可修訂 Memory、同步／背景兩種時序、真正相依的 Tool sequencing，以及模型語意選擇與應用執行責任分離；**它們沒有規定 Memory 技術性持久化失敗必須丟棄同一 Context 形成的 JD 候選。**該部分是 Owner 核准的 Caliburn mapping，不冒充廠商原生規則。

## 7. 模型與 Runtime 的輸入責任

模型只應提供語意內容與有限 mutation intent，例如新增、修訂、移除或 no-op，以及本輪已取得的短期 reference。

模型不應填：

- canonical ID；
- JD scope／namespace／principal；
- revision／version／timestamp；
- source event ID；
- embedding／TTL；
- actor／digest／處理狀態；
- 實際載入過的 Skill ID 或 receipt；
- retry、權限與並行控制資料。

上述資訊由 Runtime／Storage 從可信 Context 產生。Tool 結果必須可區分成功、合法 no-op、輸入錯誤、找不到或已過期，以及可重試失敗；失敗不能偽裝成成功，也不能要求模型猜測系統 ID。

來源：[Memory mapping §9.40.1、§9.40.4～§9.40.7](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md)、[通用 Memory 研究 §13.15](./2026-08-30-agent-memory-landscape-and-decision-working-research.md)

### 7.1 通用 production 治理基線

無論採哪個框架，都必須保留下列跨家共同責任分離：

- **保存資格、整理、召回與 Context 注入是不同步驟。**資料存在不代表必須成為 Semantic Memory，也不代表每輪都要送入模型。
- **使用既有 Memory 與由本輪來源學習是不同操作。**產品第一版不一定需要公開兩個 UI 開關，但 Runtime 不能把「讀取」偷換成「同意永久寫入」。
- **空結果合法。**本輪沒有值得持久保存的內容、查無相關 Memory 或不需修改既有 Memory，都不是錯誤。
- **Persistence eligibility 先於 durable write。**允許保存與值得保存是兩個判斷；安全與產品邊界不能只依 extraction model 決定。
- **Memory 是低權限資料。**員工內容、來源、整理後 Memory 與搜尋結果都只能當資料，不得覆蓋 system policy、權限或工具規則。
- **發布與使用狀態可觀察。**處理中／成功／失敗、重試、召回原因、token、延遲與錯誤不能成為無法診斷的黑盒；若 substrate 啟用版本／revision，再一併記錄，而不是為了觀測先自建版本平台。

來源：[通用 Memory 研究 §6 的 B1～B14、§9](./2026-08-30-agent-memory-landscape-and-decision-working-research.md)

## 8. 選框架時不可妥協的門檻

後續框架比較必須以「能否完整承接本文」為主，不以既有程式、套件知名度或少寫幾行 code 為主。最低門檻是：

1. 本機、自架並能使用 PostgreSQL，不強迫導入雲端 control plane 或第二個預設基礎服務；
2. Provider／model 可替換；
3. Durable conversation 與關閉後 resume；
4. Durable、可修訂的 Semantic Memory；
5. Bounded recall、按需 search／read，以及原始來源回查；
6. Exact-scope list-all／pagination，並能證明全部頁面與列出的目前 Memory 都已進入處理；
7. Trusted per-JD isolation，模型不能自行決定 scope；
8. 重放不得重複副作用；若系統實際允許多 writer，必須再提供 stale／並行保護，不能靜默 lost update；
9. Typed tool 與 failure contract；
10. 能接入員工審核且待審內容可跨關閉保存；
11. 來源處理、Memory 發布、召回、失敗、成本與延遲可觀察；
12. 有可維護的正式版本政策。

完整候選比較留在：[Memory mapping §9.41～§9.46](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md)。本文本身不預先採用任何候選；其下游 Owner 已核准的 Working Research 選型另見 [`2026-09-02-memory-framework-selection-revalidation.md`](./2026-09-02-memory-framework-selection-revalidation.md)，該選型不得反向降低本文契約。

## 9. 已排除的提前假設

在沒有代表性資料證明必要前，不得預設：

- 每輪注入全部對話、全部 Memory 或完整 JD；
- 一份巨大且持續整份重寫的 profile；
- 每個工作案例一筆固定 entity 或獨立 case store；
- 每筆 Memory 永久連結一個 JD 欄位；
- Knowledge Graph、episodic engine、RAG 或跨 JD Memory；
- `Work Understanding`、`Work Model`、`Focus`、`Gap` 等名稱必須成為資料層；
- 固定兩次模型呼叫、固定 stage 或多 Agent；
- Semantic top-k 可以代表全部資料；
- Managed Memory 的預設摘要、衝突合併或淘汰政策自然符合職務分析需求。

## 10. 尚未決定，留給框架比較與後續設計

以下尚未成為契約，不得由實作者自行補成既定需求：

1. A+ 已確認單筆 Memory 的邏輯表徵；正式物理表徵仍未決定是 Markdown、JSON document、file、record 或其他形狀；
2. 一筆 Memory 的最大粒度、拆分／合併規則與長度門檻；
3. 導覽是即時計算、持久化 projection，或先不持久化；
4. 三模式召回已確認；仍未決定的是一般回合的候選筆數、token／tool-call budget、分數門檻、排序融合、query rewrite，以及 embedding／lexical index 的具體實作；
5. Admission 的產品語意已確認；仍未決定的是正式 Prompt／topic／few-shot、案例細節提升門檻、一次案例何時併入既有主題，以及 extraction 漏失的量測與修復方式；
6. 未知／衝突的現行 Working Baseline 是只以既有 `title／topic＋content` 表達，不新增模型欄位或專用型別；仍可在新證據證明效果不足時經 Owner 討論翻案。尚未決定的是正式 Prompt／few-shot，以及是否、何時把它們投影到可重建導覽供提醒或查看；
7. 已核准即時讀取、背景 extraction＋consolidation、窄幅 live repair 三條互補責任；尚未決定的是共用保存政策如何落入 manager／Tool、各自採用的 framework／model、部署形狀，以及 background trigger／debounce 與 live-repair 門檻；
8. exact inventory 是必要效果，但底層尚未裁決；官方非語意 listing＋exact namespace equality＋同 scope serial writer＋checkpoint worklist＋pinned-backend 測試只是候選映射。它沒有 opaque cursor／snapshot 保證，須先與 managed pager、可信單批上限及最小 keyset／catalog 路徑比較並經 Owner 同意；
9. replay 不重複是必要效果，但底層尚未裁決；serial writer＋LangGraph task＋Runtime deterministic key／既有結果查核與 Pydantic Harness 原生 CAS＋idempotency 都是正式候選，不能先把任何一個寫成共同底層；
10. 真正的成本、延遲、召回率與 record 成長門檻。

這些問題可以影響框架優劣，但不得反向降低第 2～8 節的必要效果。

## 11. 後續討論順序

1. 以第 8 節硬門檻淘汰明顯不合格的框架組合；
2. 比較合格候選對第 10 節未決事項能提供多少成熟能力；
3. 優先比較最終 JD 效果、可靠性與功能，再比較成本、延遲與複雜度；
4. 對框架未覆蓋但契約必要的部分，只允許最薄、可驗證的產品 policy／adapter；
5. 形成推薦後再與 Owner 討論；未核准前不開 ADR、不寫 schema、不施工。

## 12. 研究來源與回讀路徑

### 12.1 產品成果與中立能力

- [`2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md`](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)
  - §1：唯一產品目標
  - §5.2：M1～M11
  - §5.3～§5.5：Memory、LLM、Skill、Tool、Runtime 與 JD 的責任邊界
  - §7：Prompt／Skill／Memory／Tool 的分工

### 12.2 跨 OpenAI、Anthropic、Google、AWS 與框架的通用研究

- [`2026-08-30-agent-memory-landscape-and-decision-working-research.md`](./2026-08-30-agent-memory-landscape-and-decision-working-research.md)
  - §5：各家實際公開作法
  - §6：B1～B14 共同基線與可選能力
  - §7～§9：更新、召回、版本與完整通用流程
  - §13：資料表徵、Prompt、Tool、Runtime 責任與限制的深入核對

### 12.3 Caliburn Memory 能力 mapping 與候選比較

- [`2026-08-30-caliburn-memory-requirements-mapping-working-research.md`](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md)
  - §9.2～§9.7：M1～M11 對成熟能力的 mapping
  - §9.9～§9.23：admission、衝突、關係與全量盤點
  - §9.32～§9.40：現行表徵主候選、Context、Tool、更新與失敗契約
  - §9.41：框架候選比較；不是本文的預設答案

### 12.4 使用原則

- 本文回答「框架必須完成什麼」。
- `perfect-jd` 文檔回答「為什麼高品質 JD 需要這些能力」。
- `agent-memory-landscape` 文檔回答「各家實際公開做了什麼、共同點與差異是什麼」。
- `caliburn-memory-requirements-mapping` 文檔保存完整分析、候選與翻案歷史。
- 後續若發現本文缺漏或與來源衝突，先回讀相應段落並與 Owner 討論，再更新本文。
