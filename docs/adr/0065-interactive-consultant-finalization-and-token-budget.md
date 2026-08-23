# 0065. 互動顧問 finalization 與累計 Token 預算校準

- **狀態**：Accepted
- **日期**：2026-08-22
- **Owner 對齊**：owner 於 2026-08-22 核准把互動 run 的 model-call hard ceiling 由 8 校準為 11；在確認舊 32,000-token ceiling 與實測衝突後，再核准一併校準為 160,000，並要求以多輪訪談成本為優先約束
- **Supersedes**：ADR 0064 決定 12 的「第一版八次 model calls 足以涵蓋 repair／recheck／final」與其 operational ceiling
- **保留**：ADR 0064 其餘全部決策；總 Tool、兩波 external-data lookup、單次 context、retry、cost、elapsed、recursion、deterministic publication 與員工 authority 邊界不變

## Context

ADR 0064 把八次 model calls 視為可由 live smoke 校準的 operational profile，而非產品語意 invariant。exact `openai/gpt-5.6-luna` smoke 顯示模型在第七步完成候選編輯、第八步呼叫 `check_candidate_document`；framework 在第九次 finalization call 前依八次上限 fail closed，因此沒有 final Structured Output 或 pending review bundle。這不是增加 Tool、RAG、multi-agent 或更昂貴模型可以正當解決的問題。

同一 smoke 的八張 provider receipts 合計 79,658 raw tokens（input 73,529、output 6,129；cache read 58,079、cache write 15,426），provider cost 為 US$0.01237768。實作檢查另發現 production `max_total_tokens=32_000` 是三-call runtime 初建時的舊值；後續 model-call ceiling 先升到 5、再升到 8 時從未重新校準。若只把 call ceiling 改成 11，模型即使成功 finalization，也會在 semantic commit 前因早已超過 32,000 而整輪拒絕。

OpenAI／OpenRouter／LangChain 的現行 usage contract 都把 cached input 保留在 `input_tokens／total_tokens`，另以 cache detail 與實際 cost 表達折扣。故不能為通過舊上限而從 `total_tokens` 偷扣 cached tokens；raw throughput、provider cost 與 cache effectiveness 必須分開觀測。

本產品是多輪、可關閉後續談的職務訪談。每一輪都可能短路於較少 model calls；11 與 160,000 都是單一 employee turn 的 fail-closed ceiling，不是每輪配額、目標或固定消耗。文件生命週期成本則是各輪 receipt cost 的總和，不能用單輪上限冒充。

## Decision

1. **互動 run 的 model-call hard ceiling 設為 11。** LangChain `ModelCallLimitMiddleware` 繼續執行真正上限；模型產生 final result 就結束，不為湊滿 11 而繼續。第九步可直接 final；若 check 回傳 blocking diagnostic，最多保留 repair、recheck、final 三步。

2. **累計 raw-token hard ceiling 校準為 160,000。** `verify_attempt_budget()` 仍加總 provider receipts 的原始 `total_tokens`，包含 cached input，不改 usage 語意。此值以已量測的 79,658-token 八步 run、後段約 15–16k tokens／step、最多三個 finalization／repair steps，以及一次 transient provider retry 的 bounded headroom 校準。超過仍在 semantic commit 前 fail closed。

3. **互動 run policy revision 由 1 升為 2。** resolved execution 與 attempt receipt 必須記錄 revision 2，讓後續成本與成功率可以按政策版本比較；不得用相同 revision 靜默改 budget。

4. **成本與其餘 guard 不擴張。** `max_cost_usd=2.00`、單次 context 24,000、兩波 external-data lookup、48 個總 Tool calls、180 秒 elapsed、一次 model retry 與一次 Tool retry維持。160,000 只修復 stale raw-token guard，不能作為提高 prompt、Skill、Tool 或 reasoning 消耗的理由。

5. **本次只允許一次相同 Luna smoke。** 不換模型、不加入 multi-agent、不增加 lookup／Tool、不因 stochastic failure連續付費重跑。報告必須保存 input／output／cache／provider cost／latency 與 cleanup evidence，並將實際單輪 cost 線性換算為 50／100 輪的參考量級；換算不是費用保證。

6. **第一版不新增 document-wide budget service 或成本 UI。** 現有 durable run evidence 已保留每張 attempt receipt，可按 document 加總實際 provider cost。當代表性使用顯示每份 JD 的總成本、P95 單輪成本或失敗後浪費超出 owner 可接受範圍，再以實測決定文件級警示或 hard cap；本 ADR 不先建立第二套計費狀態。

## Consequences

- 已量測的 candidate edit→check 路徑可取得 finalization headroom，而不改候選、Evidence、publication 或員工審核語意。
- 160,000 是單輪最壞情況保險絲，不代表每輪會消耗 160,000；正常簡單回答仍應在較少 model calls 結束。
- prompt caching 繼續降低成本與延遲，但 cached tokens 仍留在 raw usage；實際金額以 provider `cost` 為準，避免把便宜 cache read 誤報成免費或把 raw token 直接當帳單。
- 以上一次複雜 smoke 的 US$0.01237768 作純線性參考，同等成本下 50 輪約 US$0.62、100 輪約 US$1.24；真實費用仍會受模型、provider、cache、回答長度與 repair 次數影響。
- 本次沒有建立跨輪預算 enforcement；風險由每輪 hard guards、durable receipts 與後續代表性成本觀測承接。若實際多輪成本失控，不能只繼續提高 ceiling。

## Rejected alternatives

- **只把 8 改為 11、保留 32,000**：已由同 profile 的 79,658-token trace 證明成功結果仍會在 commit 前被拒，等於花費更多後才失敗。
- **從 `total_tokens` 扣掉 cache read**：會把 provider 的 raw usage 指標改造成 Caliburn 私有指標，混淆 throughput 與費用；實際 cost 已有獨立 receipt 欄位。
- **移除 total-token guard 或提高 cost cap**：修復 stale ceiling 不需要移除 defense-in-depth，也沒有證據支持增加單輪金額風險。
- **先改 prompt／合併 Skill／減少 Tool reads**：可能日後降低平均成本，但目前沒有證據能在不降低職務分析效果下完成；會一次改動多個變因，無法判讀 finalization 修正。
- **立即建立文件級 budget／billing subsystem**：產品仍在核心升級與窄 live 驗證階段；現有 receipt 足以先量測，現在施工屬過度設計。

## Sources

- [OpenAI — Organization usage API](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage)
- [OpenAI — Latest model guidance／prompt caching](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenRouter — Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)
- [OpenRouter — Prompt Caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)
- [LangChain — ChatOpenRouter token usage and cached input](https://docs.langchain.com/oss/python/integrations/chat/openrouter)
- [LangChain — ModelCallLimitMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/model_call_limit/ModelCallLimitMiddleware)
