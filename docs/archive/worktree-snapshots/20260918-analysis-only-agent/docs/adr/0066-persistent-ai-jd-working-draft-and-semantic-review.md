# 0066. 持久 AI JD 工作草稿與語意審核

- **狀態**：Accepted
- **日期**：2026-08-22
- **Owner 對齊**：owner 於 2026-08-22 明確核准本書面版本：「一份 JD 一個持久、非權威的 AI working draft；員工最後以語意差異接受／修改後接受／拒絕／延後」，並澄清 VS Code 只作概念類比
- **研究**：[`2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md`](../specs/2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md)
- **Supersedes**：ADR 0064 決定 2 的 namespace、決定 3 的 model-facing `check_candidate_document`、決定 4 的 run-scoped candidate 生命週期、決定 5 的顯式 check wave、決定 6–7 的 publication receipt，以及決定 8 的第二份 pending-bundle 生命週期
- **保留**：ADR 0064 的 Deep Agents provider-neutral VFS、六個低階 filesystem verbs、canonical JD resources、禁止 business-specific write Tool、split／merge 一般操作組合、確定性 Evidence quote resolver、employee authority、provider-neutral adapter、no-RAG 與窄驗證原則；ADR 0065 的 model／token／cost／elapsed hard guards 先作保險絲保留，待新拓撲實測後才另開 successor 校準

## Context

ADR 0064 已解決 candidate mega-form 與 model-authored quote offsets 的根因，讓模型可透過成熟 VFS 讀、寫、修改與刪除 canonical JD resources。但實作仍把工作面綁在單次 run：每輪從 approved JD seed `/candidate/<run_id>/**`，模型顯式呼叫 `check_candidate_document`，再於 final Structured Output 回送 application 已知的 revision、digest 與 action handles，application 才建立另一份 durable review bundle。未發布或尚未決策的工作面不能自然成為下一輪 AI 的編輯基礎。

Owner 要的產品效果更接近文件／程式編輯器的共同生命週期：AI 可在一份隔離 working draft 持續工作；員工即使尚未決策，下一輪 AI 仍看得到這些改動並可繼續修正；員工最後看的是相對核准 JD 的語意變更，而且可逐項或按相依群組接受、修改後接受、拒絕或延後。只有接受後的內容才進核准 JD。VS Code、Claude Code、GitHub、Word 與 Google Docs只提供持久工作面、差異審核、stale review與部分決策的機制證據；Caliburn 不複製 Git、branch、commit、PR、檔案中心 UI或IDE權限模式。

OpenAI Apply Patch、Claude Code checkpoint、VS Code agent edits與Word／Google Docs建議模式共同支持「模型／工具先改隔離成果、application 驗證、使用者再審差異」；Deep Agents `StateBackend／CompositeBackend`、LangGraph checkpointer／state／interrupt／command與LangChain HITL已提供大部分通用機制。Caliburn只需要保留框架不知道的職務語意、Evidence與員工權威政策。

## Decision

1. **每份 JD 第一版只有一個持久、非權威的 active working draft。** `/workspace/**` 跨員工訊息、process restart與自然關閉保存；下一輪模型從既有 workspace 繼續，不再依 run ID 重建。`/approved/**` 是唯讀核准基線，export只讀 approved。第一版沒有多草稿、fork、branch或workspace chooser。

2. **由 framework persistence 承接 workspace，不建立另一套自寫文件資料庫。** canonical workspace resources放在document-scoped LangGraph state，由Deep Agents `StateBackend`透過同一state channel讀寫，PostgreSQL checkpointer依document thread持久化；`CompositeBackend`只負責把skills、sources、approved、workspace與review route到各自backend。跨thread的員工來源、更正與決策記憶使用LangGraph Store。不得使用host filesystem、Git、shell、execute、任意network或跨文件query。

3. **namespace收斂為五個目的。** `/skills/**`、`/sources/**`、`/approved/**`唯讀；`/workspace/**`可讀寫；`/review/**`唯讀且由application從approved↔workspace差異與員工決策metadata投影。`/review`不是模型另寫的proposal，也不是第二份JD；pending／deferred只是workspace中尚未整合的差異狀態。

4. **模型只使用六個低階編輯verbs。** 正式surface為`ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`；不新增`add_task／split_task／merge_duty／revise_opks`，也不保留model-facing `check_candidate_document`。Task／Duty／OPKS的拆分、合併、改名、重組與重新歸類由一般create／edit／delete組合，application依語意相依性形成可審群組。

5. **每波mutation後由graph自動驗證，不要求模型完成publication handshake。** validation node讀取framework真實after-state，解析Pydantic canonical resources，執行scope、syntax、identity、linkage、JD invariant、Evidence與read-set verifier。可由模型修復的錯誤以短、可行動diagnostic回到agent loop；需要員工裁決的衝突才用LangGraph interrupt暫停相依分支。invalid workspace可持久保存以便下一輪繼續修，但不得出現在可接受review、不得改approved、不得export。

6. **員工審核的是application產生的semantic change set。** 每個review group綁定approved revision、workspace revision、group digest、affected entity／field與dependency。互不相依項目可個別決策；拆分、合併或跨Duty／Task／OPKS不可分割變更整組決策。低階file diff與Tool JSON不直接作員工介面。

7. **四種員工決策具有明確workspace語意。** `accept`把該group原子寫入approved並把workspace重基線；`edit-accept`先套員工修改再同樣commit；`reject`從active workspace撤回該group並保存拒絕理由／decision memory，避免AI下輪把它當仍待核准內容；`defer`保留workspace差異供後續續談。只有accept、edit-accept或員工direct edit能改approved。

8. **review必須綁精確版本並fail stale。** workspace、approved或相依entity被後續AI／員工改動時，舊review command不得套到新內容。非重疊group可繼續決策；重疊group由application確定性rebase並重新驗證，無法安全rebase時才要求員工澄清。員工direct edit不得被workspace靜默覆蓋。

9. **model final不再承擔application已知狀態的回聲。** final Structured Output只保留顧問回覆、下一個訪談焦點／問題、必要澄清與少量受驗證分析effects；不再要求模型回送workspace revision、digest、action handles、完整Skill receipts或Evidence offsets。review identity、semantic diff、progress與Evidence offsets均由application從真實state確定性建立。

10. **持久workspace不等於每次把完整草稿送進prompt。** Skills、sources、approved與workspace仍由middleware依目前焦點按需`read／grep`；模型只收到必要摘要、相關resource與近期diagnostics。checkpoint負責恢復，不充當context dump。ADR 0065的hard ceilings先維持，實作後以一次窄smoke比較calls、tokens、cache、latency與cost，再決定是否另開ADR下調。

11. **第一版不擴張產品範圍。** 不做auto-accept、多workspace／版本歷史UI、Git／PR、RAG／Reference、能力級別／A、多Agent、正式eval平台或每個edit彈人類核准。員工仍可隨時停止傳訊息、關閉並下次繼續；不新增「本輪可停」狀態。

12. **施工按產品切片回歸。** workspace persistence、automatic validation、semantic review、partial authority與UI每完成一個切片，都必須回看產品北極星：一位專業職務分析顧問、當前焦點加背景吸收、Task／Duty／OPKS動態演化、所有AI內容先審後入、必要澄清與一般Gap分流、員工原話／更正跨回合可用、可信進度、目前不做RAG。框架若迫使產品退回wizard、一次生成或逐edit核准，應先討論並開successor，而不是讓實作反定義需求。

## Consequences

- 員工未決策時，AI仍能在同一草稿基礎上續寫與修正；不再因run結束忘記尚未接受的工作。
- 核准JD仍只有一份；持久workspace是可丟棄、可重建且不能export的工作面，不取得employee authority。
- Deep Agents／LangGraph承接VFS、state persistence、checkpoint、resume、interrupt與command；Caliburn自寫面縮成canonical JD codec、semantic differ／dependency grouping、Evidence verifier與authority transaction。
- 自動驗證移除一次顯式Tool call與易失敗的publication receipt回聲；模型仍能收到可修錯誤，但application不把已知ID交回模型抄寫。
- 部分接受後workspace會以新approved重基線；拒絕內容退出active draft但保留decision memory；延後內容仍可被下一輪AI看見。
- persistent state可能增大checkpoint；第一版必須量測多輪成長與restart round-trip，不先採beta delta channel或另建版本系統。

## Rejected alternatives

- **維持run-scoped candidate＋durable review bundle**：員工不決策時，下一輪AI無法自然在完整未決草稿上續寫，並重複workspace與pending兩套生命週期。
- **把每個patch當primary truth**：適合audit transport，不適合作為模型下一輪要讀的完整成果；仍需重播與處理半套用狀態。
- **完整複製VS Code／Git／PR**：引入branch、commit、merge、hunk與多人review概念，超出本機單一員工產品需求。
- **每個低階edit先讓員工核准**：把agent內部修復變成連續彈窗；員工應審職務語意結果，不是工具步驟。
- **保留`check_candidate_document`但改為自動呼叫**：仍多一個model-facing Tool與可繞錯順序；graph validation node更能保證每波mutation後執行。
- **只保留approved、未決內容每輪由對話重建**：會忘記完整結構、浪費context與tokens，也無法提供可靠semantic diff。

## Sources

- [OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)
- [OpenAI — Latest model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Anthropic — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- [Anthropic — Checkpointing](https://code.claude.com/docs/en/checkpointing)
- [VS Code — Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits)
- [GitHub — Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Microsoft Word — Track changes](https://support.microsoft.com/en-US/Word/training/track-changes-in-word)
- [Google Docs — Suggest edits](https://support.google.com/docs/answer/6033474)
- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [Deep Agents — Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain — Human-in-the-loop middleware](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
