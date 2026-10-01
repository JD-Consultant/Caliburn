# Caliburn 從早期專案到新架構的演進素材

這是**歷史材料索引，不是定稿報告**。依 Owner 要求，從最早可查的前身專案找起，保留「遇到問題、研究或嘗試、修改、驗證、再發現問題」的過程；先提供簡述與原文引用，之後才挑選推甄／專題的敘事。不能把近期幾個成功案例當成整個開發歷程。

整理基準：2026-10-02，`target-rebuild@373968ed` 的文件、可達 Git 歷史及已封存分支。最早可查元件提交是 **2026-03-19 的 PDF 解析專案**；JobIntel 訪談系統的初始提交是 **2026-05-20**；三專案於 **2026-06-27** 匯入 Caliburn monorepo。這不是三者同一天誕生，也不代表更早沒有未留存的工作。

## 按問題找素材

| 要追查的過程 | 入口 |
|---|---|
| 以系所／教授公開的能力目標找實驗、反證、工程分析與取捨證據 | [按能力找證據](evidence-by-capability.md)；判準及官方來源見[研究能力研究](../admissions/research-readiness.md) |
| 早期資料解析、固定訪談流程、顧問重設計，以及整個 JD App 為什麼多次改架構 | [產品與架構演進](product-and-architecture.md) |
| 向量檢索為什麼不夠、搜尋資料及粒度如何調整、參考資料與員工事實如何分開 | [檢索與參考資料演進](retrieval.md) |
| 長訪談如何保存、更正與找回資訊，Memory／Context 的各次試驗與失敗 | [長訪談與記憶演進](memory-and-context.md) |
| 最近的 Prompt 比較、長旅程中斷、漏引與尚未解決的品質問題 | [既有案例摘要](../research-casebook.md) → [新目標實驗證據](../../plans/2026-09-29-target-rebuild/evidence/README.md) |
| 直接看最早期原本長什麼樣 | [3 月／5 月原文與 Git 出處](../../archive/early-projects/README.md) |

各主題是相互交錯的演進，不是三條完全獨立的開發線。研究與設計文件可能同時含多輪修改；引用時用列出的章節找原問題，再向後讀同題修訂。

## 先看整體變化

| 時期 | 當時架構或研究重點 | 當時暴露的問題／下一次改動 |
|---|---|---|
| 3–5 月：前身資料處理 | OCS PDF → 結構化 JSON；解析代碼、任務、產出、指標、知識與技能 | 真實 PDF 的斷行、合併儲存格與跨頁格式破壞解析；資料模型也由 Task 內清單改為 P-centric blocks。[原件](../../archive/early-projects/README.md) |
| 5 月：JobIntel | pgvector 參考檢索＋LangGraph 固定訪談階段，STAR → 5W2H → 指標 → 文件 | 短答、phase 過濾與切換判定造成重問／提早前進；此時尚非後來 A／B1／B2 架構。[原狀態機](../../archive/early-projects/2026-05-20-jobintel-graph-pipeline.md) |
| 6 月：知識服務與 monorepo | 獨立 indexer、catalog／精確讀取與向量查詢分工；可編輯選單＋深問；三 repo 整合 | 檢索範圍、輸出資料契約、保存責任與服務依賴要分清。[流程](../../archive/jobintel-v3/specs/2026-06-14-jd-authoring-flow.md)、[整體設計](../../specs/2026-06-27-system-architecture-design.md) |
| 7 月上旬：顧問而非填表 | 先後研究顧問／書記、工具、追蹤修訂與事件議程 | 真人及 persona 試訪分別出現填槽感、零任務卻有大量態度、長聊不產出 P；不只是換模型。[7/6](../../specs/2026-07-06-consultant-not-formfiller-redesign-research.md)、[7/9](../../specs/2026-07-09-interview-flow-task-curation-and-flexibility-research.md)、[7/14](../../specs/2026-07-14-interview-agenda-architecture-research.md) |
| 7 月中下旬：證據與分析工作流 | vNext Evidence workflow → 專業顧問 R1 比較 → 最小 one-stage 訪談閉環 | 短答需要前問；複雜的多階段不一定更好，評測器也可能漏判。[短答決策](../../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)、[R1a 結果](../../experiments/2026-07-27-r1-task-discovery/r1a-results.md) |
| 8 月：Framework 與編輯工作面 | LangChain／LangGraph、巨型編輯表單 → VFS → 持久草稿 → 共用目前稿 | 模型填無關參數與定位易錯；跨輪草稿與人工修改形成兩份競爭內容。[VFS 決策](../../adr/0064-deep-agents-virtual-jd-workspace-and-deterministic-evidence-anchor.md)、[共用稿決策](../../adr/0069-shared-current-jd-working-copy-and-semantic-approval.md) |
| 8 月底–9 月：長訪談與分層 Memory | 可修訂理解、routing、canonical 原話、分層分析與壓縮；多批 CT 實驗 | 路由找到候選不代表事實忠實；仍出現漏記、更正未吸收、未知消失等，詳[記憶沿革](memory-and-context.md) |
| 9 月：JD 編輯器與正式入口 | Plate 文件樹候選 → relational JD 管理編輯器；9/22 以 ADR0077 切正式權責 | 能編一份文件不等於能管理各欄位與關係；舊入口也會讓實作者用錯架構。[0075](../../adr/0075-relational-jd-authority-and-structured-editor.md)、[0077](../../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md) |
| 9 月底–10 月：新目標重建與驗證 | 重新確定原始訪談 → 情境 → 理解 → JD；明確 Snapshot、引用、Context、工具與恢復邊界 | 已有實作與分層證據，但品質／容量及正式切換仍各有界線；不能把計畫寫完或一場長旅程完成當整體通過。[計畫](../../plans/2026-09-29-target-rebuild/README.md)、[0079 草案](../../adr/0079-target-rebuild-production-cutover.md) |

這張表呈現「當時怎麼做、後來改了哪裡」，不把每次改架構都稱為已證明的優化。部分是實測驅動，部分是產品需求修正、研究推論或時程取捨。

## 怎麼讀每個節點

- **問題／發現**：優先找當時的逐字稿、失敗結果、程式反例或 Owner 試用回饋。
- **研究／嘗試**：連到當時查過的資料與方案；舊文件引用大廠，不代表每個推論都正確或至今適用。
- **結果／限制**：有實測就標範圍；只有設計、提交或測試程式就如實說明，不補寫成功。
- **接續**：保留後來修正／撤回，不將最終方案倒灌成早期就已經知道。

原始紀錄維持原位置與原結論；本索引不重抄實驗原件、不改 Accepted ADR、不新增產品要求，也不替申請者認領本人／AI／協作者貢獻。歷史方案中的「RAG」「Agent」「Memory」「turn」等用語可能與現在不同，引用時不得混用。

## 盤點範圍與仍需補證

本次涵蓋最早三個前身專案的可達歷史、6–9 月 ADR／研究／計畫、封存分支的獨有證據及新目標實驗入口；不是逐個 commit 的完整編年史。下列材料若日後要寫成主張，仍需回到原件核對：

1. 早期報告中寫「已修復／通過」，但只剩文字結論、程式或測試檔的項目，不能冒稱本次重跑或原始 log 齊全。
2. 本機 ignored 的模型 capture、DB 逐字稿及私人訪談，不因存在一份摘要就視為已公開、已保存或可對外展示。
3. 同一類問題可能在不同架構重新發生；除非原文有診斷，不推定是同一根因。
4. 日期優先取原文事件與提交紀錄；初始提交可能一次納入更早工作，不能用提交日推算實際投入天數。

下一步先沿引用確認哪些原件適合使用，再決定怎麼寫；**現在不先把其他歷史材料排除，只留下近期兩個案例。**

## 演進索引初次整理核對

2026-10-02：本次新增／調整的 14 份 Markdown 檔案，相對連結與章節錨點檢查為零失效；三份早期原文與列出的 Git blob 完全相同，相關提交日期亦已核對。此結果只涵蓋這次索引與入口，既有歷史文件內仍可能有已退役路徑，須沿封存索引或 Git 回讀。

沒有重跑舊模型實驗、修改產品或刪除原始證據；原件中「已驗證」的敘述仍屬各次原實驗的範圍，不是這次重新驗收。

同日後續按教授／系所公開能力目標補找的九組材料及該輪五份文件檢查，見[能力索引核對範圍](evidence-by-capability.md#本輪核對範圍)；不與以上初次整理的14份檔案混計。
