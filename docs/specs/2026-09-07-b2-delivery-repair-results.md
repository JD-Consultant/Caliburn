# Q019／MP-02f：整併交付窄修結果

> 2026-09-07 · **方案 A 隔離窄修及局部 review 完成；528 項回歸通過。**本段只驗機制，不宣稱自然 Memory 品質通過。
> 決策入口：[主 register](../../../../docs/current-decisions.md)。設計及 A/B/C 比較：[官方底層複核 §2–4](2026-09-07-b2-delivery-official-implementation-review.md)。原始失敗：[小額實驗 §6](2026-09-07-memory-prompt-live-calibration.md#6-同組材料續測有進展但不能只靠再加提示收尾)。

## 1. 授權與實際改動

基準 `c844932e`，隔離 `codex/analysis-only-agent`。Owner「OK 同意，記得不知道該怎麼做就去找資料研究」核准既有工具＋完成檢查；不採新 patch／structured output／框架，不提高步數或費用。

| 接點 | 本段修復 | 不代表什麼 |
|---|---|---|
| B2 操作指令＋官方工具說明 | 完整可見、輸出可容納的短檔可 `write_file` 一次替換；長檔／只看過部分時仍 `read_file/grep`→局部 `edit_file`。同步覆寫框架 tool description，避免原「不需先讀／優先 edit」與應用規則互相矛盾。 | 沒有新增「已完整讀取」追蹤器、模糊比對或語意補字；短檔策略是模型使用指引，不是程式保證無遺漏。 |
| 最終成對檢查 | 下載兩份真實 staging 內容並通過原格式／引用驗證後，才檢查「正文非空、導覽空白」。以既有 `StagedMemoryValidationError` 回模型補導覽。 | 不把條件塞入逐檔共用 validator；不要求所有檔案／每次整理都非空，不強迫重寫有效舊導覽。 |
| 可選預檢 | `validate_memory` 保留為零參數工具；模型可不呼叫。最後回覆時 Runtime 仍必驗，collect 再驗，合格才進既有保存／CAS 發布。 | 不是模型自報成功、不是取消驗證，不新增一個成功路徑模型呼叫。 |
| 錯誤與額度 | 完成錯誤包含檔案、原因、補救；走同一 Agent 的 final hook／jump 與現有 model/tool 限制。額度耗尽仍失敗，重開不重設額度。 | 不新增外層盲重跑，不把拒絕／不完整回覆／未知基礎設施錯誤都丟給模型重試。 |

程式只改 `consolidation.py`、`consolidation_tools.py`、`consolidation_feedback.py`。B1、主顧問、原文保存、详記、來源／引用解析、C、schema、Store／Checkpointer、發布 owner、provider 与限制不變。原始碼連結由 [README 現況](../../experiments/analysis-agent/README.md#consolidation-slice-2026-09-06)及 Git 變更提供，不複製另一份流程全文。

## 2. 為什麼這樣修：官方事實與本案映射分開

- **官方事實：**已安裝 Deep Agents 0.7.13 `StateBackend.write` 原生可覆寫；`edit` 精確匹配。`read_file` 有行數與字元回傳限制，讀一頁不是讀完。[官方 backend](https://github.com/langchain-ai/deepagents/blob/deepagents==0.7.13/libs/deepagents/deepagents/backends/state.py#L175-L247)、[官方工具與格式化](https://github.com/langchain-ai/deepagents/blob/deepagents==0.7.13/libs/deepagents/deepagents/middleware/filesystem.py)。**本案映射：**按完整可見程度與輸出預算選短檔整寫／長檔局部改，不保證一定比 patch 便宜。
- **官方事實：**Codex 整併 runner 結束後有程式產物檢查；該固定版檢查含 MEMORY 檔案及導覽首行 `v1`，不是語意驗證。[Codex validator](https://github.com/openai/codex/blob/1fb5158b3496a05abb89fb992d45737a02511d47/codex-rs/memories/write/src/workspace.rs#L51-L82)。**本案映射：**檢查有正文就不可空導覽；不照抄 `v1`，不宣稱所有 OpenAI 產品使用同一驗收。
- **官方事實：**LangChain 公開 final middleware hooks／agent jumps；OpenAI 工具指引要求清楚用途及使用時機，能由程式處理的事情不讓模型重複負擔。[LangChain hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom#agent-jumps)、[OpenAI function best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)。**本案映射：**保留已接好的最後檢查，將重複預檢改可選；只有真的錯誤才在既有額度內回模型。

本輪重讀實際安裝版 backend／工具說明、共用 validator、B2 workflow／feedback 及既有測試；再查 OpenAI 官方工具設計指引。沿用前輪固定 revision 的整併底層研究，不重做 Memory 總研究，不以文件名稱推斷功能。

## 3. 驗證與審核

- **紅燈：**新測試先在原碼跑出 `5 failed / 3 passed`：空字串或空白導覽被發布、預檢沒錯誤、最後缺導覽不會觸發原額度停止。失敗對應本次完成缺口。
- **局部綠燈：**補修後原8項全過；既有6檔＋新檔 focused **192 passed，15.32s**。後續再補字元截斷邊界測例，不把100行預設誤當完整可見。
- **舊測試材料同步：**原有引用修復／恢復成功情境只填正文，現在在同個模型步驟提供正文修復＋導覽兩個工具呼叫；保留原錯誤、恢復、來源、發布斷言，按實際工具數調整。未刪失敗測試或降低新完成規則。
- **環境失敗：**沙箱 pytest 預設與新建暫存目錄均遇 WinError5；使用授權的專用暫存目錄重跑，未改產品程式來繞過測試，也沒重啟 Docker。
- **整批驗證：**第一次含 PG 跑 `524 passed / 3 failed`，失敗都是舊 PG 成功 fixture 缺導覽；同樣補成對成果，保留中断／重建 client／未知寫入對帳驗證。最終主審 **528 passed / 0 skipped，66.66s**，包含 `127.0.0.1:55433/q019_agent_test`，1 項既有 TestClient deprecation warning。新9項 delivery 測例全部包含在內。
- **其他檢查：**`compileall src tests`、`uv lock --check --offline`、`git diff --check` 通過；本段3份研究／結果及 README 的本地連結可解析。鎖檔檢查曾被沙箱拒讀 uv 快取，授權重跑通過，未升級依賴。
- **獨立 review：**局部審查通過，無 Critical／Important finding；明確區分主審528項與未驗的自然模型品質。唯一 DOC-01／P3 為 register 舊章節錨點，主審已修為現行 `#4-三個選項與建議` 並回查，CLOSED。reviewer 為唯讀、未派工／付費，沒有把它的檢視當成另跑一次全套測試。

新增交付測試使用真實 `create_agent`、Deep Agents tools／StateBackend、Saver／Store、publication；只替換外部 HTTP 為指定回覆，無付費模型。驗空導覽錯誤／可選預檢／不呼叫預檢也修正／2或4步耗盡／重開不再請求／有效空 no-op／短檔完整改寫且保留另一案例／沿用導覽／長檔行數及字元截斷後局部修改保留不可見尾段。這些測試證明機械行為，**不證明自然模型一定選對工具、保留所有語意或比較便宜**。

## 4. Closure 與下一個 gate

- **狀態：**MP-02f「非空正文／空导覽誤完成」機械缺口局部 CLOSED；官方工具使用策略已接線，效果／成本仍未實測。沒有未處理的本段 review finding。
- **本輪費用：US$0，沒有真模型請求。**既有5次試驗66請求／US$0.03212434 保持不變。
- **仍 OPEN：**MP-02d 候選只帶未知而漏已知工作、MP-02e 未答追問誤當否定；MP-02f 的自然工具效率／細節保留與整組 fresh-context 回查尚待驗。MP-01 計數端點404／原生延續相容也沒在本段修復。
- **下一步：**交付本段機制與限制後，再確認同組 Luna／medium 有界品質校準的 gate；不直接重跑相同付費試驗，不增加額度。若實際長文或必要多步讀寫仍不適合，帶證據討論 patch／其他交付方式，不再盲加 prompt。
- **重開條件：**本段真框架測試反例、原樣本操作仍失敗、長正文細節遺失、官方契約變動或 Owner 改需求。不改 ABC／五產物，不接 JD／UI／production，不 merge/push。
