# 0064. Deep Agents 虛擬 JD 工作區與確定性 Evidence Anchor

- **狀態**：Accepted
- **日期**：2026-08-21
- **Owner 對齊**：owner 於 2026-08-21 確認本版完成本 ADR 與兩項 authority／Evidence 缺口後再 merge
- **研究**：[`2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md`](../specs/2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md)
- **Supersedes**：ADR 0060 決定 2／§4.1 對 Deep Agents 僅使用 Skill `read_file`、不暴露其餘 VFS verbs 的限制；ADR 0061 決定 2–4 的 model-facing required-only／fixed payload slots／model-authored Evidence anchor 表示法（只限 filesystem Tool 與 candidate resource，final output 仍維持 compact typed contract）；ADR 0062 決定 1–2 與決定 4 的 model-facing source Tool／payload 形狀；ADR 0063 決定 2–4、10 與決定 11 的初始五次 model-step ceiling；ADR 0063 Rejected Alternatives 中對「完整 Deep Agents virtual filesystem」的整體否決
- **保留**：ADR 0060 的產品行為、framework replacement、單一 durable authority、Store／Saver 事實分工與 no-RAG；ADR 0061 決定 1、5–6 的 model/application 分層、Pydantic／LangChain transport 與完整產品效果，以及 Evidence 的 employee source／exact quote／Skill 語意；ADR 0062 的 application-controlled scope／limit、來源資格與更正語意、必要澄清、員工 command、no Tool Search；ADR 0063 決定 1、5–10、12，以及決定 11 的有界 budget 原則（不保留初始五次 ceiling），包括 tool→result→repair、candidate／approved 分離、revision＋digest＋action handles final reference、pending dependency、員工 authority與 deterministic projection

## Context

ADR 0063 正確建立 candidate Tool→application 套用→Tool result→模型修正→final publication→員工決策的閉環，也維持「模型不能直接寫核准 JD」。但它為跨 provider strict grammar 採用一個自寫、union-free、required-only `job_document_candidate_edit` mega-form：每筆 change 同時帶所有 payload slots，再由 mapper 要求未使用欄位保持 sentinel／空值。

真模型 smoke 已先後發現 integer sentinel、模型自填 UUID、重複 linkage、`enabler_list` 錯置與 quote offset 不符。逐一補 prompt 可修已見案例，卻沒有移除 agent 必須替大量無關欄位選中性值的根因。現行 `OutputQuoteAnchor` 也把 `start／end` 字元定位交給模型，application 最後才用 exact slice 拒絕；這讓 deterministic 工作消耗 agent repair budget。

2026-08-21 核對官方現行做法：OpenAI Apply Patch 由模型提出少量 create／update／delete diff、harness 在 working／in-memory workspace 套用並回傳錯誤；Claude Code／Anthropic agent 使用少量 view／create／exact replace editor、checkpoint 與 diff review。Deep Agents 0.7.5 已提供 provider-neutral `FilesystemMiddleware`、pluggable `StateBackend／CompositeBackend`、工具 allowlist、virtual path permissions、exact edit 與 structured errors。本 repo 已安裝這些成熟元件。

Caliburn 不需要把 JD 變成真正 host files，也不需要採 Git 當文件 authority；需要的是把 coding agents 已成熟的「brain／hands／workspace／review」機制投影到 JD editor，讓 framework 接手通用編輯，application 只保留職務語意、Evidence 與員工權威。

## Decision

1. **以 Deep Agents VFS 取代自寫 candidate mega-form。** 使用 `FilesystemMiddleware` 搭配 `StateBackend`／`CompositeBackend`，不再暴露 `job_document_candidate_edit`、`OutputDocumentChange` flat payload slots 或 sentinel 規則。VFS 是 LangGraph thread／run 內的候選工作面，不是新資料庫或第二份 Current JD。

2. **建立五個明確 namespace。** `/skills/**`、`/sources/**`、`/approved/**`、`/pending/**` 只讀；`/candidate/**` 可讀寫。application 只投影當前 document scope；`/pending/**` 必須標示非核准且不得默認疊到 approved baseline。`CompositeBackend` route 與 `BackendProtocol` policy wrapper 是 hard security boundary：只讀 route 必須自行拒絕 write／edit／delete，candidate route 必須重驗目前 run prefix與 resource type；public `FilesystemPermission` 只可作 defense in depth，不得依賴 private `_permissions` API。`FilesystemMiddleware` 必須明設 `tool_token_limit_before_evict=None` 與 `human_message_token_limit_before_evict=None`，不建立 `/large_tool_results/**` 或 `/conversation_history/**` 隱藏 route；check／source result 由 application 在原 Tool result 內確定性限量。不得使用 host `FilesystemBackend`、shell、`execute`、任意 network 或跨文件 Store query。

3. **Tool surface 改為 framework verbs＋一個薄 domain check。** 第一版只暴露 `ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete` 與 application-owned `check_candidate_document`；不暴露 `glob／execute`。Filesystem permission 限定 write 只到目前 `/candidate/<run_id>/**`。六個成熟 filesystem Tool 同時取代三個自寫 employee-source read Tool 與一個候選 write Tool；Skill、員工來源、approved／pending 與 candidate 都透過相同受限 workspace 按需讀取。`check_candidate_document` 不接受文件 payload、不修改 VFS／review／approved，只執行 framework 不知道的 JD／Evidence verifier並回 receipt。不新增 `add_task／split_task／merge_duty／revise_opks`。來源 backend 必須以 async BackendProtocol lazy 投影 current 原文、metadata 與 oldest-to-newest correction lineage；`grep` 只查 current 原文並保留 document scope、排序與結果上限，不得把 historical revision 當成目前員工說法，也不得把來源複製到 StateBackend 成為第二份 Evidence truth。

4. **候選採 canonical virtual resources，不採任意 host file。** `/candidate/<run_id>/header.json`、每個 Duty／Task／O／P／K／S 各一份固定欄位順序、pretty-printed canonical JSON，另有 review-group resource。現有 entity 由 application 提供短 local handle 對映 stable ID；新增 entity 只用 local handle，正式 UUID、display order 與 export position code 由 application 配置。模型不得選 document ID、authority revision 或正式 identity。`StateBackend` 雖隨 thread checkpoint，`ls／read／grep／write／edit／delete／check` 都只能作用於目前 run namespace；舊 run 即使留在 checkpoint history 也不得列出、讀取、寫入或發布。成功 publication 與 active candidate 清除必須是同一 semantic transition；失敗 scratch 只供同一 run retry，新一般 run 必須清除而非默認承接，除非員工明確選擇指定 pending bundle 繼續修。

5. **採 edit→check→observation→repair。** Deep Agents editor 立即回 path／permission／exact-match／backend 結果；薄 policy 將本 repo 鎖定版本的 `write_file` 收窄為只建立新 resource、`edit_file` 禁止 `replace_all=true`、`delete` 只刪合法 entity resource且不得遞迴刪 candidate namespace。LangGraph 可平行執行同一 AI message 的 Tool calls；平行 read 與不同 resource mutation 可保留，同一路徑或 ancestor／descendant 路徑的競爭 mutation 必須整波拒絕並要求順序重試。`check_candidate_document` 不得與 mutation 同一 Tool wave，必須等待 editor observations 回到模型後再單獨呼叫，避免檢查到 wave 前 snapshot。application 再讀 framework 真實 after-state、解析 Pydantic candidate、執行 scope／syntax／handle／linkage／Evidence／document diagnostics，回 candidate revision／digest／semantic diff／action handles／atomic subgroup或可行動錯誤。exact replace 零或多命中、非法 JSON、未知 handle 與 path 越界都必須精確回報，讓模型同 run 修正。

6. **允許非權威 workspace 暫時不完整，publication 必須 fail closed。** 像 coding agent 暫時讓測試紅燈，模型可用多次 editor calls 完成跨實體重組；但任何 blocking syntax、domain、Evidence、read-set 或 stale issue 未解時，final candidate 不得轉成 review bundle。未發布、未引用、未知、stale 或 superseded workspace 皆可丟棄且不得影響 approved document。

7. **final Structured Output 只發布已驗證 workspace receipt。** 模型不在 final 重送文件；只引用最後一次成功 `check_candidate_document` 產生的 candidate revision／digest／完整且有序 action handles。成功 check 後任何 candidate mutation 都使 receipt stale。application 比對 checkpoint state、digest、semantic diff、action order 與 final reference後，才建立 durable review bundle。VFS file diff 不直接呈現給員工，Web 只呈現 application 產生的 JD semantic diff。

8. **split／merge 是一般 editor operations 的 atomic composition。** 拆分 Task 是 create 新 Task、調整 Duty／OPKS references、delete 舊 Task；合併反向組合。application 依 semantic references 與經驗證 review-group resource建立 atomic subgroup；不可分割 group 整組接受／修改／拒絕／延後，互不相依項目可各自裁決。defer 只保存 durable pending 狀態、不改 approved JD。intent label 只供說明／audit，不建立額外模型權限。

9. **Evidence wire 不再包含 model-authored char offsets。** 模型只提供 source／segment handle、exact quote、必要時的 1-based occurrence 與分析 Skill references。application 對 immutable source revision exact match：唯一命中才產生 `start／end`；零命中回可修錯誤；多命中要求更長 quote／較細 segment／明確 occurrence，不得猜。`read_file／grep` observation 加上的 line gutter 不是原文，模型不得納入 quote，resolver 也只能對 Store raw revision 定位。最終仍保存 offsets 並經 deterministic verifier；不得為通過驗證改寫員工原話。

10. **Provider-native editor／citation 只可作 adapter optimization。** 第一版所有模型走相同 Deep Agents VFS contract，維持 OpenRouter／provider 可替換。日後若直接使用 OpenAI Apply Patch 或 Anthropic native citations，必須正規化成同一 candidate／Evidence internal result，且不得改 public API、employee authority 或形成 provider-specific truth。

11. **員工審核邊界不變。** candidate editor calls 可在隔離工作區內自動執行；員工不審每一步 Tool JSON。只有 accept／edit-accept／reject／defer 或員工 direct edit command 能裁決 durable review bundle；只有 accept／edit-accept／direct edit 能更新核准 JD。auto-accept 本輪不做。

12. **以窄驗證施工，不建立正式 eval 平台。** 新 editor 拓撲不再沿用 ADR 0063 的初始五次 model-step ceiling；第一版 profile 以八次作 hard ceiling，足以涵蓋兩波 lookup、edit、check、一次 repair、recheck 與 final，並保留總 Tool／token／cost／elapsed／recursion budgets。八次是可依 live smoke 下調的 operational profile，不是產品語意 invariant。先做 framework tool／permission／schema characterization、mega-form 與 quote-offset regression、candidate repair／publication／partial review integration，再跑 GPT-5.6 Luna 窄 live smoke 與 browser review。每完成 editor、Evidence、publication、review UI 一個切片就回看產品北極星；正式顧問品質 eval 仍延至產品核心完成後。

## Consequences

- 模型從「填所有可能欄位並清空無關欄位」改為像 Claude／Codex 一樣讀取、精確編輯並觀察真實 after-state；新 Duty／Task／OPKS 能力不再線性擴張 Tool schema。
- Deep Agents 直接承接 virtual state、read/write/edit/delete、pagination、exact replacement、allowlist、permission 與 checkpoint；Caliburn 自寫面縮成 JD resource projection／parser、diagnostics、Evidence resolver、semantic diff 與 employee authority。
- Tool 數量由四個自寫 read/write tools 改為六個 framework filesystem verbs＋一個無文件 payload的 domain check，但每個目的互斥且 schema 小；實作 gate 必須量測所有 Tool＋final output 的 provider grammar，不因「framework」字樣假定一定較小。
- 現行來源 Tool 的 stable-ID read、correction lineage 與 current-only lexical search 由 read-only source backend 重現；VFS 化不能降級員工更正與 Evidence validity。
- 關閉 FilesystemMiddleware 的 large-result／conversation-history eviction，避免 framework 在五個 namespace 外另存員工訊息或檢查結果；代價是每個 source／check observation 必須有明確上限與 omitted count。
- Candidate VFS 可暫時 invalid，因此 diagnostics 必須區分 editor-level failure、可修的候選缺口與 publication blocker；不能把 scratch issue 誤呈現成員工資料。
- 一個 entity 一個 canonical resource使局部 edit、split／merge 與 diff 更自然，也新增 parser／canonical formatting 的版本管理責任；resource format 只屬 internal harness，不得滲入 Web contract或資料庫 authority。
- 模型不再計算 quote offsets，降低中文、標點、換行與 Unicode 計數錯誤；Evidence 標準沒有放寬，反而由 application 保證 pointer 可重現。
- Pending candidate 仍非 approved truth；framework checkpoint／VFS state不能被 ORM、export 或 Web 當 document store 查詢。

## Rejected alternatives

- **只補 prompt／examples**：已能修單一 sentinel，但下一個 unused slot 與 offset 仍重演，根因未除。
- **維持自寫 compact patch DSL**：比 mega-form 小，仍重寫 Deep Agents 已有 backend、editor、permission、pagination與 errors。
- **每種 JD 操作一個 Tool**：增加重疊選擇與跨 Tool atomicity，將 split／merge誤做成權限。
- **任意 JSON Patch 直接寫 domain object**：讓模型操作 internal storage path／open payload，並把 application identity／invariant洩漏到 provider；canonical VFS resource＋typed publication gate較窄。
- **直接把 host filesystem 當 JD store**：不適合 Web API、不可逆且可能碰憑證；官方 Deep Agents 也建議 Web server 使用 State／Store／sandbox backend而非 host filesystem。
- **只用 OpenAI Apply Patch或Claude native editor**：可能在單一 provider效果好，但破壞 model／provider替換與OpenRouter路徑。
- **每次 edit 先讓員工核准**：把內部 repair loop變成連續彈窗；員工應審 semantic bundle，不是低階 editor call。
- **移除 final／deterministic verifier**：VFS成功只代表文字編輯成功，不代表職務語意、Evidence、read-set或authority合法。

## Sources

- [OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)
- [OpenAI — Codex code review](https://learn.chatgpt.com/docs/code-review)
- [OpenAI — Codex environments](https://learn.chatgpt.com/docs/environments/modes)
- [Anthropic — Raising the bar on SWE-bench Verified](https://www.anthropic.com/engineering/swe-bench-sonnet)
- [Anthropic — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- [Anthropic — Checkpointing](https://code.claude.com/docs/en/checkpointing)
- [Anthropic — Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Anthropic — Scaling Managed Agents](https://www.anthropic.com/engineering/managed-agents)
- [Anthropic — Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [Deep Agents — Permissions](https://docs.langchain.com/oss/python/deepagents/permissions)
- [Deep Agents — Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain — Tools](https://docs.langchain.com/oss/python/langchain/tools)
