# 0069. 共用目前 JD 工作副本與語意核准

- **狀態**：Accepted
- **日期**：2026-08-26
- **Owner 對齊**：owner 在 2026-08-26 核准依最新官方研究開始施工，並要求 UI 一併改為共用編輯面；外部產品只作機制參考，不要求沿用舊實作或舊名稱
- **研究**：[`2026-08-25-shared-current-jd-working-copy-and-semantic-approval-research.md`](../specs/2026-08-25-shared-current-jd-working-copy-and-semantic-approval-research.md)
- **Supersedes**：ADR 0066 決定 1／3／7／8 中「AI working draft 與正式 editor 是兩個員工可感知編輯面」、`defer` decision、direct edit 後三方 rebase conflict，以及 pending review 可阻擋後續訪談的部分；ADR 0067 決定 5 中 direct edit rebase 與 `defer` 的部分
- **保留**：ADR 0060 的 LangGraph durable authority、員工 authority 與 AI 無 approved write edge；ADR 0066／0067 的單一 Store-backed workspace、derived semantic review、低階 VFS Tool、自動驗證、partial authority、stale guard、approved-only export、按需 context 與 no-RAG／no-auto／no-Git 邊界

## Context

ADR 0066／0067 已完成一份 JD 一個持久 workspace、核准文件與 semantic review，但產品仍把 `approved_document` 做成員工的主要 editor，再把員工修改三方 rebase 回 AI workspace。當同一欄位兩邊都變更時，application 保留 AI working value 並產生 `workspace-rebase-conflict`。員工眼前因此像有兩份競爭文件：自己已修改的正式內容，以及 AI 仍維持另一值的草稿。

這不符合 owner 已確認的產品心智模型。產品應像成熟 coding agent 的共同 working surface：員工與 AI 都從目前成果繼續；也必須像正式文件的 suggestion mode：AI 內容未經員工核准，不得進入匯出基線。VS Code、Codex 與 Claude Code 證明同一 working surface、後續 follow-up 與事後 diff 是成熟機制；Google Docs 證明建議內容可在文件脈絡內顯示，接受後才成為正式內容。Caliburn 需要混合兩者，而不是複製 Git、PR、line hunk 或兩個可編輯文件。

現行 run failure 另會讓 Web textarea 進入 retry-only 狀態，主要畫面也提供逐段「更正這段原話」。Owner 已澄清正常訪談應允許員工直接說「我剛剛說錯了，是……才對」；來源 lineage 留在內部與進階追溯，不應成為一般員工的主要操作。

## Decision

1. **員工只操作一個「目前 JD」主編輯面。** 它是 `/workspace/**` 中經 application 驗證的 current working document，包含核准內容及尚待決定的 AI 差異。AI 下一輪也從同一 working document 繼續。`approved_document` 保留為只讀核准基線與 export authority，不再是另一個主要 editor。

2. **review 是核准基線與目前 JD 的 derived semantic diff。** 不新增第三份 draft、patch queue、Git index 或模型填寫的 proposal form。application 仍保存產生穩定 review identity、dependency、Evidence 與 decision memory 所需的最薄 metadata，但不得讓 metadata 成為另一份 document truth。

3. **AI 低階編輯不逐 Tool 要求人類核准。** Deep Agents VFS 先實際修改 workspace，middleware／Pydantic／JD／Evidence verifier 驗證真實 after-state；valid 差異才投影到目前 JD 與審核 UI。員工可以不審而繼續訪談，AI 也可在尚未核准內容上繼續修正，但必須知道其 pending authority。

4. **接受與拒絕直接改變兩份必要 snapshot。** `accept` 把所選 atomic semantic group 的目前值提升到核准基線，working copy 不跳動；`reject` 把該 group 的 working value 還原成核准基線並保存拒絕理由。拆分、合併、重新歸類及跨 Duty／Task／OPKS 相依變更仍由 application 計算最小合法 atomic group。

5. **移除 `defer` decision。** 員工未操作的差異自然保留，已經等同稍後處理；不得再保存 deferred status、提供按鈕或把 pending／deferred 拆成兩套生命週期。既有研究歷史中的 defer 不再是 production 要求。

6. **員工 direct edit 以 server-derived delta 為 authority。** UI 以 current working revision／digest 為基礎送出 typed edits 或完整 after-document；server 重新讀 exact before／after，自行計算員工 touched semantic components，不信任 client 自稱 paths，也不得把整份 current document 視為全部接受。每個 touched component 同時更新 current 與 approved；與 AI pending 重疊時，以員工 after-state 為準並使舊 review identity 失效；未重疊 AI pending 完整保留。

7. **編輯 AI 新增 entity 時，儲存代表修改後接受最小合法 group。** 若核准基線尚無該 entity，application 必須包含維持文件 invariant 所需的 dependency closure，UI 在儲存前明示範圍。不得只提交半個 Task／Duty／OPKS linkage，也不得順便接受不相依差異。

8. **同範圍並行變更 fail stale，不建立 UI rebase conflict。** 員工編輯期間若 AI 又修改同一 workspace generation／digest，server 拒絕舊提交並保留瀏覽器輸入；不做隱藏 merge。第一版本機單一操作者沿用 document lock／active-run guard／expected revision，不導入 CRDT／OT。

9. **pending review 不阻擋訪談。** 移除 contract／Web 中由文件待審驅動的 `blocked_branches`、`safe_interview_work_available` 與 `decision_required_before_more_interview` lifecycle。只有來源衝突、責任邊界不明等真正缺少員工決定的事實，才建立獨立 required clarification 並以 LangGraph `interrupt／Command(resume)` 暫停相依分析。

10. **分析失敗後仍可自然對話。** 員工原話先 durable 保存；run failure 不禁用 textarea，retry 只是快捷操作。新訊息可表達補充或「我剛剛說錯了」；顧問判斷 `supersede／qualify／rebut` 意圖，application 驗證 target 與 document scope，不唯一時才走 required clarification。主要畫面移除逐段更正按鈕與 source-specific correction mode，來源 lineage 只在未來進階追溯呈現。

11. **匯出只讀核准基線。** readiness 的強制匯出只放寬缺口確認，不得將 AI pending 差異自動納入。UI 必須在有 pending 差異時明示它們不會出現在匯出檔案。

12. **UI 使用同骨架、文件內審核。** 主畫面以乾淨的 Duty → Task → OPKS 階層呈現目前 JD，另有尚未歸屬區；K／S 在 UI 以 Task 關聯投影協助閱讀，不改變底層多對多分析。`審核變更` 在同一骨架的變動位置顯示紅色刪除線、綠色新增與移動前後位置，接受／拒絕靠近目前差異；已核准版本只作次要只讀查看。聊天與工作地圖可收合，讓 JD 成為主要工作面。

13. **不新增框架。** Deep Agents `StoreBackend／CompositeBackend`、低階 file tools、LangGraph Saver／Store／interrupt、Pydantic models 與 React contract 已覆蓋通用機制。Caliburn 只保留通用框架不知道的 JD semantic differ、dependency closure、Evidence lineage、員工 authority transaction 與 domain UI。

14. **分切片施工並回看產品北極星。** 契約／projection、direct-edit authority、對話失敗／更正、文件與 review UI 各自有測試與 commit；每一切片完成後確認仍是多輪專業訪談、動態 Duty／Task／OPKS、AI 內容先審後入、必要澄清與一般 Gap 分流、approved-only export，且目前不加入 RAG、A／能力級別分析、auto-accept、多 Agent 或正式 eval 平台。

## Consequences

- 員工與 AI 不再心算兩份可編輯 JD；尚未審核也能跨輪持續工作。
- 底層仍有核准基線與 working copy，因為部分接受、拒絕還原與 approved-only export 無法只靠一份 snapshot 正確完成；但產品只有一個主編輯面。
- direct edit 從「approved-first 後三方 rebase」改為「current-based employee delta 同步提交」，需要新增 workspace generation／digest stale guard 與 dependency closure 測試。
- `defer`、review blocker 與 source-specific correction UI 可刪除，狀態與 Web 分支減少。
- 通用 persistence、VFS、checkpoint、interrupt 與 schema validation 繼續交給成熟框架；沒有第二個 workflow／memory／document framework。
- semantic diff、atomic group 與 Evidence 仍是必要領域程式，因官方框架不理解 Duty／Task／OPKS 的合法關係。

## Rejected alternatives

- **保留正式 JD editor＋AI draft editor 再 rebase**：同一內容有兩個現在值，員工修改後仍可能被要求解決 AI 草稿衝突。
- **只有一份 snapshot，不保留 approved baseline**：無法可靠部分拒絕、顯示 before／after，亦無法保證匯出不含未核准 AI 內容。
- **每個低階 Tool edit 先核准**：把 agent 修錯過程暴露成連續彈窗，阻礙訪談且不是員工真正要審的職務語意。
- **以 patch／operation ledger 作主要文件真相**：需要重播並產生第三套 lifecycle；operation metadata可供 audit，不能取代完整 current working document。
- **引入 Git／JSON Patch authority／CRDT／OT／另一套 editor framework**：第一版本機單一操作者沒有相應需求，增加狀態與維護成本。

## Sources

- [VS Code — Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits)
- [OpenAI — Codex IDE extension](https://learn.chatgpt.com/docs/codex/ide)
- [OpenAI — Code review](https://learn.chatgpt.com/docs/code-review)
- [OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)
- [Anthropic — Permission modes](https://code.claude.com/docs/en/permission-modes)
- [Anthropic — Checkpointing](https://code.claude.com/docs/en/checkpointing)
- [Google Docs — Suggest edits](https://support.google.com/docs/answer/6033474)
- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain — Human-in-the-loop middleware](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
