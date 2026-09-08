# CT34：首次更正與舊漏存恢復——隔離對照計畫

> 狀態：G5對照／保存核驗／獨立審查完成，G8 OPEN；依 executing-plans在既有隔離工作區執行。非產品施工。

**Goal:** 分清現行 CT25 規則在首次更正是否能寫入，與舊口頭確認後的漏存恢復是否同樣失敗。
**Architecture:** CT16 合成資料建立兩個隔離副本。首次組用官方 LangGraph 歷史 checkpoint 分支；恢復組保留原42則可見問答。均沿用原服務、reasoning、inline compaction、提示與工具，不修改 request view。
**Tech Stack:** Luna／medium、ChatOpenAI Responses、LangChain、LangGraph PostgreSQL Saver／Store。
**Spec:** [CT33研究與待驗假設](../specs/2026-09-08-ct33-compaction-provenance-and-recovery-review.md)。Owner本輪同意方向，另明確核准總20次／US$0.10，達上限停止，不重開既有closed帳本。

## 邊界與官方依據

- [LangGraph time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)：`get_state_history` 讀保存點，`update_state` 建立分支而非覆寫原歷史；重播會重新呼叫模型，準備阶段禁止 `invoke`。**不包含 Store 回滾**，必須另驗版本與來源一致。
- [OpenAI inline compaction](https://developers.openai.com/api/docs/guides/compaction#server-side-compaction)：保留原生輸出與不透明延續，不解密、不重建；不是停用壓縮實驗。
- 不改 `src/`／產品測試／JD／B排程／工具／prompt／模型。只停兩組副本的背景排程，避免B代寫；這是既有測試隔離，不是產品政策。
- 不增加完成檢查、強制tool或額外Agent。以實際文件差異、工具回執與重開保存判定，不以口頭回答判成功。

## 1. 保存點與離線一致性

- [x] `.test-tmp/ct34_inspect.py` 唯讀找首次更正前完整38則可見問答，與CT16封存前38則完全相同；空文字工具回應不計為可見問答，只輸出opaque hash。
- [x] `.test-tmp/ct34_run.py` 建立兩個 `q019_ct34_*` 副本；原資料庫不變。
- [x] 首次組從 `1f1aae1d-0c59-6fd3-8025-24d6cb524b92` 呼叫 `update_state(saved.config, {'turn_outcome': saved.values['turn_outcome']}, as_node='analysis')`，只建立完成態分支；斷言values完全相同、next空、原歷史仍可讀。
- [x] 該點正是revision3的processed_source指向checkpoint；驗knowledge／guide／cursor與CT16已發布rev3相同，引用全部在該點以前，兩組初始Memory完全相同。若不一致即停止，不拼湊來源。
- [x] HTTP外送禁止時驗問答／引用；執行既有context、prompt、source回歸與ledger上限測試。

## 2. 真實對照

- [x] 兩組使用原 CT16 首次更正同一句話，不追加「使用工具」。首次组保留當時真實長對話／opaque；恢復組保留CT16原42則與舊opaque。
- [x] 每組一次，從 `/documents/{id}/runs` 發送。共用新帳本20次／US$0.10（含重試），每次請求前驗Luna／medium、CT25規則／導覽／六工具，首請求opaque與對應封存比對。
- [x] API或基礎設施失敗停止，不自動重跑。語意漏存照實記fail，可完成另一組；保存回執、完整Memory前後、逐字差異與成本。

## 3. 核驗與收尾

- [x] 重開兩副本、禁止網路，驗保存結果一致、原問答與新增問答及詳記來源頁逐字相符；C回執可回到當輪更正。
- [x] 唯讀再查原CT16最新checkpoint／head，確認未變；封存結果、脚本與hash，但不封存密鑰或opaque內容。
- [x] 短增量研究稿記兩組結果，不以單次成功當穩定或唯一根因；更新register，只提交本輪文件，保留原dirty，不push／merge。

## 診斷脚本更正記錄

首次唯讀檢查誤把 `_visible` 中空文字的工具AI訊息算進38則，prefix斷言拒絕。已與服務對齊只計非空可見文字後，核對原文／ID。零API、零DB寫入；不是產品bug，未繞過來源一致性檢查。
