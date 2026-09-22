# CT44：保留未變細節與整併收尾額度

2026-09-09 · LLM-Q019 · **局部採用；完整訪談G8仍OPEN**。
[計畫](../plans/2026-09-09-ct44-preserve-unchanged-clauses.md) · [前後正文](evidence/2026-09-09-ct44-review.md) · [全部請求／失敗／工具結果](evidence/2026-09-09-ct44-preservation.json) · [CT42基準](2026-09-09-ct42-long-interview-results.md)。

## 原因、官方依據與選擇

CT42舊未知沒清乾淨，medium／high對照又漏掉仍有效的子句。CT44只將一組一般保留提示，改成寫前以已讀正文為底稿、更新有依據的子句、核對刪除部分；不增加Agent、schema、語意驗證器或工具。這是產品約束的局部提示校準，**不是官方保證或廠商共通逐字prompt**。

- [OpenAI GPT-5.6 prompting guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)：定義成功條件與保留事實；一次改一組提示，以實際trace重測；不要把少工具循環排在正確性前，也不要全面提高effort。
- [Anthropic prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)：明確說明約束、用途與適量例子。僅參考通用原則，未假定Claude特定模型結果能直接保證Luna。原候選失敗期間曾考慮「初次／後續補充」例子，但第二次自行修正，**沒有再加入新例子**。
- [Anthropic Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)：模型請求操作，應用執行並回結果；不等於框架會自動保證語意不遺失。本輪不更換檔案操作／資料owner。
- [LangChain model/tool call limits](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)：可設定模型、工具額度控制成本；額度不是品質保證。沿用既有middleware與跨恢復計數，不新增retry loop、不清零失敗計數。

## 實測：同一保存輸入，兩個獨立複本

原CT42的最後B1／寫入前正文，Luna **high**、8192輸出；原PG唯讀，Store／Saver／publication在複本。不是新長訪談，不重做抽取、不手動補答案。兩次各自開始，不能把第二次說成第一個中断job的resume，也不能從單次隨機軌跡宣稱精確因果提升幅度。

| 請求 | 上限：模型／工具 | 實用模型／工具 | 結果 | 估費用 |
|---|---|---|---|---|
| 1–8 | 8／12 | 8／8 | 第8次validate_memory後，下一模型被額度攔截；沒有final或publication；原失敗保留 | US$0.01701013 |
| 9–20 | 12／12 | 12／11 | 完成並發布至複本；原PG前後一致 | US$0.03236701 |

第一組#2 patch漏列表符號被拒，#3修正後成功staging，但初次操作說明仍漏；不宣稱格式預檢已通過（該tool result沒有下一請求可觀察）。第二組#13初寫也暫時漏初次說明，**#16自主patch補回**；#18格式／引用預檢成功，#19回讀，#20才收尾發布。不是系統替模型補字，也不是validate_memory驗出了語意遺漏。

## 完整內容核對

原文與候選、寫前與最終正文逐段核對，獨立review無Critical／Important：

- 初次依案一次操作說明、文件受影響即更新、重大變動才補說明，三者同時存在。
- API不清楚先問後端；新案／範圍變動才估算；每天排查、週五彙整所有案件；不保證當天修好，均保留。
- 青禾「付費成功但權限畫面未刷新」與雲岸「連點重送／後端冪等」未混淆；權限與前後端責任保留。
- 低頻安全升級、相容性風險、客戶同意再上線及不負責後端／全面資安均保留。
- 已回答的雲岸部署、交付後排查、範圍確認有更新；退款核准人等真正未知未被造答案。
- 六個既有詳記引用均保留，新增引用是本批真實summary path。原CT42早先缺的交付詳記直接鏈結不是本輪修復範圍；詳記仍可搜尋，不聲稱所有來源路由完美。

Minor CT44-R02：共通／青禾仍泛稱「其他專案尚未確認」；全文明確記兩案已確認，非重要矛盾，但單獨讀段落可能含糊，保留為後續語句精確性檢查。另有一行列表前多空格，不改語意。沒有證據證明模型內在將初次／後續概念混淆，僅可證第一次寫入漏子句、第二組後來自行補回。

## 採用與未完成

局部採用一組保留提示＋B2預設**12模型／12工具**；前景CT43的12模型／11工具不變。不是新增工具種類，也不強迫用滿；模型effort預設仍A/B2 medium、B1 high，**本輪語意實測只有high，不能稱medium已驗收**。不改C政策、抽取、背景排程或production/JD。

提示接線RED→45通過；額度接線RED（8/8攔截）→46通過，包含預檢不發布、後續修正後才發布，以及原有耗盡／resume不清零測試。最終程式完整回歸**558通過／41skip**（47.52秒），skip的真PostgreSQL另跑**41通過**（31.47秒）；各有一則既有Starlette棄用警告。這些是接線與回歸安全網，不取代真模型語意／長訪談驗收。

20次合計**US$0.04937714**估費，24次／US$0.10內，帳本closed；不是供應商帳單。兩次前輪外傳拒絕保留，本輪已獲明確授權。ledger頂層effort沿用harness舊medium標籤，實際20筆request全為high/all_turns；封存已明確註記，不能讀錯設定。原始opaque不透明內容不封存，只留雜湊／必要metadata；不含key。

下一gate：固定此版本，做新補充／明確撤銷對照，再完整長訪談；不重跑已封存對照或把本次小測冒稱全面穩定。剩餘4個請求不足完整驗收，本輪不為用完額度而跑半套。

## Closure

Decision：局部採用提示及B2 12／12，不改分層、effort預設或production。獨立review再次核對程式、額度扣抵、resume、新測試及結果，無新增Critical／Important；既有Minor與G8限制保留。官方來源見首節，影響檔案為consolidation、其測試、fixture、app README、計畫與current register。重開條件：新補充／撤銷或固定版長訪談仍遺漏、誤留過時事實、費用不合理。下一gate只驗這些效果，不重新討論Memory架構；本地保存點使用 `analysis-agent-ct44-consolidation-20260909`，不merge／push。
