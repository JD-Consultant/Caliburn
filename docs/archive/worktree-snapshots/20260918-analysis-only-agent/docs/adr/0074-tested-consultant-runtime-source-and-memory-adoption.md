# 0074. 採用已驗顧問 runtime、原始訪談與 Memory authority

- 狀態：**Proposed**；尚未改production。
- 日期：2026-09-10。
- Topic：JD-R002/R5、LLM-Q019。
- 依據：Owner要求實作[完整成品計畫](../plans/2026-09-10-jd-product-delivery.md)；詳細候選、現行證據、版本及驗收見[正式採用設計](../specs/2026-09-10-jd-production-adoption-design.md)。

## Context

既有隔離顧問已使用LangChain／LangGraph官方持久化與受測Memory流程，但production仍依ADR0060。隔離原始訪談由Saver checkpoint回查，Memory內容由Store與既有發布metadata管理；這不同於舊production原文Store及checkpoint理解owner。JD0073只負責文件工作稿，不能夾帶這項authority變更。完整產品需正式採用既有成果並移除research路徑依赖。

## Decision

1. 採核心接線驗收後固定manifest中的既有顧問、原生context／compaction、Memory／來源實作與Skill；保留受測Python3.12、精確框架／模型binding配置，不重做Memory、不接回舊candidate/approved loop。
2. 原始對話及執行項目由官方PostgresSaver唯一保存；確切原文由既有ConversationReader按document/checkpoint/message範圍讀。Memory內容由官方PostgresStore／StoreBackend保存，既有PublicationStore的head/receipt選擇有效版本。JD唯一authority依0073，checkpoint不另存可寫JD。
3. 正式runtime納入apps/api單composition，正式contract歸job-analysis-contract，原生editor模組納入正式package。無worktree／research import、雙寫或compatibility wrapper；現有架構邊界測試依此successor改成新實際責任，而非刪測試逃避邊界。
4. 明示新本機DB及fresh-root initialization；官方Saver/Store.setup與app migration在維護階段執行。日常啟動驗版本不改schema，不搬舊資料、不清現有DB。
5. 單worker、文件admission、scope與已驗取消／效果對帳保留；前景JD/手改互斥依0073。封存拒絕新前景與人編，保留全部資料及已收到來源的既有背景調度／恢復，不等背景歸零；內部catalog枚舉含封存文件。恢復後續談，不自動剪除來源checkpoint或永久刪除。
6. 全體資料備份及還原演練是成品交付條件；模型金鑰、資料庫設定、日常啟停、無模型服務時的本機讀写與錯誤出口明列，不因缺模型自動fallback。
7. 依[原生程序生命週期設計](../specs/2026-09-10-jd-native-process-lifecycle-design.md)採 Windows App 專用 Job Object 與 named mutex：API 在任何 DB／client／native 工作前取得單程序互斥、確認舊 Job 全部退出，再加入新 Job；子程序繼承 membership，不繼承 Job handle、不 breakaway。固定 Windows-only `pywin32==312`，先驗 wheel、授權及實際 bootstrap／crash。新程序以舊 Job 停止證據及 PG head-lock 後的 receipt 查詢恢復，不能從查無結果推定停止。手改 admission 的最多一筆 root-only identity binding 保存 operation／base／digest／request key，不保存候選、不偽造原話／AI run；terminal outcome 仍只由原 JD receipt 決定。依[有限人工恢復接點](../specs/2026-09-10-jd-manual-recovery-transport-design.md)，App以原key唯讀發現及一次明示清理／對帳，server投影完整write gate；無candidate重播或新authority。完整 Task 5 故障證據是採用輸入，不以本條當成已實作。

## Consequences

保留已驗能力並讓日常App使用同一資料責任；代價是有限namespace/import/config映射、正式契約、fresh setup及恢復回歸。原始來源依賴確切歷史checkpoint，不能套一般歷史清理建議。自然模型JD品質、延遲及員工可用性仍以成品P3/P6證據判定。

Windows Job 是程序生命週期 owner，不是文件或 Memory semantic owner；整個 API 異常結束會影響該 App 的其他文件與背景工作，沿既有 checkpoint／Memory 恢復。cache-lost恢復另需同一路徑GET/POST與actual API DTO→generated Web的有限seam；原完整manual-save仍獨立。此代價與 nested Job 相容條件須實驗記錄，不新增外部 supervisor、DB running 表或通用重播引擎。

## Supersedes when Accepted

- ADR0060中原始來源Store、checkpoint工作理解的具體owner與舊OpenRouter runtime組合，改成本ADR的受測runtime；單機、本機PG、來源隔離與no-RAG原則保留。
- ADR0073專門處理舊JD writers／pending／approved authority的取代；本ADR不重述它的文件schema或批准尚未通過的編輯能力。
- 0071／0072仍是未採用的較早候選，不藉本ADR接RAG、Qdrant或重啟廣搜。
- Accepted ADR原文保持immutable，接受後以索引及current design說明新效力。

## Gate

G6輸入為既有授權範圍的核心／P3證據、A1固定採用manifest、A2候選設計及0073/0074取代範圍獨立審查。G6完成後，才進A2正式契約實作、A3–A6的小型正式施工／驗證及A7 closure；不以尚未獲G6的正式施工結果作其前置。原六切片隔離接線已獲授權，無需等待本ADR；production切換尚不得執行。不得把Owner對總計畫的授權寫成自然模型／真人／恢復已驗收。本ADR不授權付費請求、DB清空或push。
