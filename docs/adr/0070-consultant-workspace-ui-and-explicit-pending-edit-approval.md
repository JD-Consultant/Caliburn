# 0070. 顧問工作區 UI 與待審編輯仍需明確核准

- **狀態**：Proposed
- **日期**：2026-08-27
- **Owner 對齊**：owner 已於 2026-08-27 複核完整書面規格並授權實作；本 ADR 仍待 implementation gate 全綠後才改為 Accepted
- **設計與研究**：[`2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md`](../specs/2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md)
- **Supersedes when Accepted**：ADR 0069 決定 6／7 中「員工編輯重疊 AI pending 就直接更新 approved」與「儲存 AI 新 entity 等同 edit-and-accept」的部分；決定 10 中由 application 判斷 `supersede／qualify／rebut` 並建立來源更正 lineage 的專用流程；決定 13 的「不新增任何 Web framework」；並澄清決定 12 的 running lock 與完整工作區 UI
- **保留**：ADR 0060／0067 的 LangGraph／Deep Agents Store-backed workspace、Saver／Store authority、AI 無 approved write edge、derived semantic review、Evidence、stale guard、approved-only export；ADR 0069 的單一目前 JD 主編輯面、只讀核准基線、移除 defer、一般待審不阻塞訪談，以及失敗後可繼續一般對話

## Context

ADR 0069 已把員工從「正式 editor＋AI draft editor」收斂到一個共用目前 JD，但對員工修改 AI pending 的語意仍過度積極：決定 6 讓與 AI pending 重疊的員工 edit 同時進 current 與 approved；決定 7 更把編輯 AI 新 entity 的儲存定義成 edit-and-accept。UI 模擬後 owner 澄清，員工可能要修改同一 atomic group 的多個欄位，再整組檢查；改一個綠色欄位不代表已核准整組 AI 建議。

同一輪 UI 討論也確認：目前 JD 必須成為中央主要工作面，訪談工作地圖與聊天是可收合、可調寬且各自滾動的 side panels。現行 Web 已有 Base UI、TanStack Query、Tailwind 與 shadcn，但沒有適合大型 nested JD 的 form state 或三欄 resizable layout；一律「不新增 framework」會迫使產品重寫成熟通用機制。

現行 code 稽核另顯示：核准 domain 要求 O／P 恰好連一個 Task，K／S 才是文件層多對多；workspace resource 雖可暫時解析空 links，validated current document 不能把未連結 O／P 當合法 JD。產品需要允許 AI 先發現 OPKS，但不能為 UI 建立第二種寬鬆核准文件。

## Decision

1. **一個目前 JD、兩個必要 snapshot。** 員工只操作一個 Store-backed current working copy；approved baseline 保持只讀與 export authority；review 由兩者衍生，不新增第三份文件、patch truth 或 proposal form。

2. **編輯 AI pending 仍保持 pending。** 員工修改任何帶 active AI semantic difference 的綠色 after-state時，只更新 working copy；application 重新推導 semantic group、dependency 與 digest。儲存不代表接受，也不得更新 approved baseline。

3. **接受是獨立 authority command。** 員工可修改同一 atomic group 的多處後再按接受；接受才將最新 working values 提升到 approved baseline。拒絕則將 group 還原 baseline 並保存拒絕理由。`edit_and_accept` 不再是一般編輯／autosave 的產品語意。

4. **普通 direct edit 維持員工 authority。** touched semantic component 沒有 active AI difference 時，員工 autosave 由 server-derived delta 同步更新 working copy 與 approved baseline；client 不自稱 accepted paths，stale 時不隱藏 merge。

5. **API 投影目前 JD。** `ConsultantSnapshot`／generated contract 必須提供 validated current working document 與 review metadata；Web 不得從 approved document 加 patch 自行重算 domain state。新增 pending-workspace edit command，帶 approved revision、workspace generation／digest。

6. **分析順序不綁文件順序。** O／P／K／S 可先被 AI 保存為有來源的待定位分析線索；成為 JD item 前才要求合法 linkage。O／P 必須恰好連到一個 Task；新的 AI K／S 至少連一個 Task 後才形成待審文件變更。未定位線索住訪談工作投影，不是另一份 JD。

7. **尚未歸屬只容納合法 working entities。** 未歸屬 Task 可以帶完整工作細節與 O／P／K／S。已核准 K／S 因重組失去最後 link 時保留在「待重新連結 K／S」；不建立未連結 O／P 或一般空 K／S 倉庫。

8. **生命週期依 ownership。** 解散 Duty 預設保留 Tasks 並移到未歸屬；cascade delete 才刪 Duty、Tasks、工作細節與 O／P。刪 Task 連帶刪工作細節與 O／P，但 K／S 只解除 link。Task 內移除 K／S 只解除關係，永久刪 canonical K／S 必須另行明確操作。

9. **可逆與高影響操作分流。** 解散、移動、取消連結與可逆單項刪除立即生效並提供短期 Undo；多 Task cascade 先列 blast radius 再確認。使用「解散／移除／解除連結／刪除」準確命名，不用同一個 `×` 表達不同結果。

10. **中央同骨架 semantic review。** 目前 JD 以 Duty→Task→工作細節＋O／P／K／S 呈現。AI 修改在原位置顯示紅色 baseline 與綠色 after-state；move 在舊／新位置顯示同一 stable identity。點擊差異才開就近 popover 接受／拒絕與按需 Evidence，不另建主要 review editor。

11. **工作地圖不是第二份 JD。** 左欄呈現訪談概況、白話目前焦點、一般待釐清、必要澄清與 Duty→Task 導覽；Focus 與待釐清不強迫綁 Task／OPKS。完整文件只在中央編輯。

12. **三欄工作區使用成熟 Web primitives。** 保留 Next／React／Tailwind／shadcn／TanStack Query；Base UI 由 1.4.1 經 compatibility gate 升到 1.7.x；加入 TanStack Form v1 與 shadcn Resizable／react-resizable-panels v4。三欄各自滾動、左右可收合／調寬，聊天 composer 固定底部；中窄 viewport 改為單側 panel／drawer。

13. **不引入重型 editor 與重複 workflow。** 不採 Tiptap、Lexical、Monaco、XState、dnd-kit、Carbon／Primer 套件、`@langchain/react`／AG-UI 或預先 virtualization。Base UI 承接 touched popup／focus primitives；現行 Radix／cmdk consumer 在改到時逐步遷移，避免同一 primitive 兩套 lifecycle。

14. **active run 使整個工作區的寫入面唯讀，failure 必解鎖。** 員工送出前先等待同 document 已排程的 autosave 完成；保存失敗就不啟動分析並保留聊天草稿。從送出開始至 durable `SOURCE_SAVED`／active run 結束，composer、目前 JD 文字編輯、新增／刪除／移動／重排、Undo 與 Accept／Reject 全部不可寫；閱讀、捲動、展開／收合、panel 調整與查看 diff／Evidence 仍可用，不加全頁遮罩。成功、錯誤或 timeout 都立即解除唯讀。失敗保留員工原訊息，可重試同一 input event，也可直接送全新的普通訊息；一般待審本身不鎖工作區。

15. **一般補充或更正就是一般對話。** 員工說「我剛才說錯了，是……才對」時只新增一則 immutable conversation turn；不要求找舊訊息、不新增 source-specific 表單、model output 欄位、`supersede／qualify／rebut` classifier 或自動來源 lineage mutation。顧問讀取本輪訊息、受 token budget 限制的近期雙向對話、目前理解與目前 JD，透過既有理解／文件編輯能力正常修訂；語意真的不明確時才用同一聊天 composer 提出必要澄清。歷史原話不改寫。

16. **第一版採明確 reject，而非 queue／steer。** 同一 document 一次只允許一個 active analysis run；durable run status 與 process-local admission 都要擋第二個 run 或員工文件 mutation。第一版不引入 Agent Server、訊息佇列、中途 steer／interrupt、rollback 或 concurrent branch。

17. **本 ADR 不改 export 與分析範圍。** 匯出維持 approved-only 現況；不加入 RAG／Reference、AI 產生 A／能力級別、auto-accept、多 Agent、版本歷史 UI、拖放或正式 eval。

## Consequences

- 員工可以像編輯共同文件一樣修正 AI after-state，又不會因 autosave 偷偷核准內容。
- 分析執行期間沒有員工與 AI 同時改同一份 JD 的競態；代價是該輪完成前不能繼續輸入或修改，但仍可閱讀與整理畫面。
- 員工的口頭更正不會被 application 擅自分類或改寫舊原話；長期效果由可修訂理解與目前 JD 承接，近期語意由正常對話 context 承接。
- 後端需要 current working document projection、pending workspace edit command、結構 intent command與契約更新；仍沿用同一 Store workspace、approved checkpoint 與 Postgres，不新增表或第二份 authority。
- O／P／K／S 可以在分析上任意先後出現，但只有合法結構進 JD；避免為孤立 O／P 放寬核准模型。
- Duty／Task 刪除結果由 ownership 決定，K／S 共用項目不會因視覺父層刪除而意外消失。
- Base UI、TanStack Form／Query 與 resizable panels 接手通用互動；Caliburn 只保留 framework 不理解的 semantic diff、Evidence、dependency closure 與 authority transaction。
- Accepted ADR 0069 保留為歷史；若本 ADR 接受，以 0070 的 editing、framework、relation 與 UI lifecycle 為現行裁決。

## Rejected alternatives

- **編輯綠色內容立即 edit-and-accept**：員工無法先修改整組再決定，autosave 會變成隱藏 authority action。
- **所有員工 edit 都只改 working copy**：會要求員工再核准自己的普通修改，違反員工文件 authority。
- **Web 從 approved＋actions 重建 current JD**：把 domain apply／dependency invariant複製到前端，且容易與 server 真實 workspace 漂移。
- **允許未連結 O／P 作正式 working document entity**：與 iCAP／ADR 0048 的 Task 層關係及現行 domain invariant 衝突，需建立第二種寬鬆文件模型。
- **刪除 Duty／Task 一律全刪**：把分組、組成與參照三種關係混為一談，會誤刪可共用 K／S。
- **刪除 Task 後保留孤立 O／P**：O／P 失去定義它的 Task；要保留就應移動整個 Task 到未歸屬。
- **只改 CSS，不補 current projection／pending edit command**：畫面看似共用文件，authority 行為仍是舊 edit-and-accept。
- **導入 rich-text／IDE editor framework**：typed JD 不需要其 AST、collaboration 或 language-service 成本。
- **把普通更正轉成 source supersession protocol**：Codex／Claude 的官方互動證據支持沿同一對話補充與修正，沒有支持一般使用者先定位舊原話或由 application 猜測來源 target；此機制增加 schema、錯誤分類與 Evidence 失效傳播，且偏離 owner 的顧問訪談心智模型。
- **running 時允許 queue／steer／parallel edit**：VS Code、Claude 與 LangGraph 都把它當成需要明確處理策略的進階能力；本機單一員工、單一結構化 JD 第一版沒有足夠收益承擔中斷與部分寫入恢復。

## Sources

- [VS Code — Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits)
- [VS Code — Send messages while a request is running](https://code.visualstudio.com/docs/chat/chat-overview#_send-messages-while-a-request-is-running)
- [OpenAI — Model guidance: apply patch](https://developers.openai.com/api/docs/guides/latest-model#the-apply-patch-tool)
- [OpenAI — Introducing upgrades to Codex](https://openai.com/index/introducing-upgrades-to-codex/)
- [Anthropic — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- [LangGraph — Double texting](https://docs.langchain.com/langsmith/double-texting)
- [Google Docs — Suggest edits](https://support.google.com/docs/answer/6033474)
- [Apple HIG — Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
- [Apple HIG — Sidebars](https://developer.apple.com/design/human-interface-guidelines/sidebars)
- [GitHub Primer — Delegate](https://primer.style/product/scenario-patterns/delegate/)
- [GitHub Primer — Delete](https://www.primer.style/product/scenario-patterns/delete/)
- [Atlassian Design System — Inline edit](https://atlassian.design/components/inline-edit)
- [Base UI — Releases](https://base-ui.com/react/overview/releases)
- [Base UI — Accessibility](https://base-ui.com/react/overview/accessibility)
- [Base UI — Scroll Area](https://base-ui.com/react/components/scroll-area)
- [TanStack Form — Arrays](https://tanstack.com/form/latest/docs/framework/react/guides/arrays)
- [TanStack Form — Basic concepts](https://tanstack.com/form/latest/docs/framework/react/guides/basic-concepts)
- [TanStack Query — Mutation scopes](https://tanstack.com/query/latest/docs/framework/react/guides/mutations#mutation-scopes)
- [shadcn/ui — Resizable](https://ui.shadcn.com/docs/components/base/resizable)
- [`react-resizable-panels` releases](https://github.com/bvaughn/react-resizable-panels/releases)
- [WHATWG HTML — `readonly` and `disabled`](https://html.spec.whatwg.org/multipage/input.html#the-readonly-attribute)
- [WAI-ARIA 1.2 — `aria-busy`](https://www.w3.org/TR/wai-aria-1.2/#aria-busy)
- [RFC 9110 — `If-Match`](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match)
- [Kubernetes — Garbage collection](https://kubernetes.io/docs/concepts/architecture/garbage-collection/)
- [U.S. OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)
- [ADR 0048 — OPKS evidence axes and document-level competencies](0048-opks-evidence-axes-and-document-level-competencies.md)
