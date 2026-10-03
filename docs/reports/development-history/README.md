# Caliburn 從早期專案到新架構的演進素材

這是**歷史材料索引，不是定稿報告**。依 Owner 要求，從最早可查的前身專案找起，保留「遇到問題、研究或嘗試、修改、驗證、再發現問題」的過程；先提供簡述與原文引用，之後才挑選推甄／專題的敘事。不能把近期幾個成功案例當成整個開發歷程。

初次整理基準：2026-10-02，`target-rebuild@373968ed` 的文件、可達 Git 歷史及已封存分支；同日後續補充見本頁末尾，各原實驗保留自己的版本與狀態。最早可查元件提交是 **2026-03-19 的 PDF 解析專案**；JobIntel 訪談系統的初始提交是 **2026-05-20**；三專案於 **2026-06-27** 匯入 Caliburn monorepo。這不是三者同一天誕生，也不代表更早沒有未留存的工作。

## 按問題找素材

不只整理 Memory。下表將已有材料按產品、分析、資料、互動與工程問題分開；同一案例跨多個面向時，只連回一份主摘要，不另外複製。

| 面向 | 要追查的問題 | 主入口 |
|---|---|---|
| 產品定位與整體架構 | 從知識檢索、固定訪談到自主顧問，何時發現做得像填表 | [產品與架構](product-and-architecture.md) |
| 原始資料解析與資料品質 | PDF斷行／跨頁如何破壞解析，資料模型如何變更，多值資料如何遺失 | [產品沿革前身專案](product-and-architecture.md#前身專案與最初資料流)、[能力索引第7–9例](evidence-by-capability.md#早期資料與程式診斷) |
| 檢索與相似度 | 檢索粒度、精確讀取、相似但不可合併、embedding相容性 | [檢索沿革](retrieval.md)、[程式演進第1、2、4例](code-evolution.md) |
| 工作分析方法與JD品質 | 職責、任務、OPKS、來源支持與員工核准怎麼區分，如何避免堆欄位 | [領域研究與更正](evidence-by-capability.md#文獻判讀領域分析與研究倫理)、[指南及樣稿](../../guides/README.md) |
| 訪談策略與Agent分工 | 填槽、長聊不產出、雙重控制、模組未接入、多階段與一步分析取捨 | [訪談重設計](product-and-architecture.md#訪談能跑不代表會分析工作)、[程式演進第5–8例](code-evolution.md) |
| Memory與來源關係 | 從歷史視窗、詳記到情境／理解，工作面、快照及引用如何演變 | [Memory與Context沿革](memory-and-context.md) |
| Prompt、工具與Context | 規則是否真的送達、格式是否妨礙編輯、schema／回傳冗餘、提示改善與副作用 | [長訪談工具反例](memory-and-context.md)、[JD工具沿革](jd-authoring-and-delivery.md)、[指引比較案例](../research-casebook.md#案例一-訪談能進行但-jd-的資訊密度不足) |
| JD編輯、引用、UI與PDF | 文件與關聯項目、人機共稿、待核對、定位、候選預覽與成品交付 | [JD與交付沿革](jd-authoring-and-delivery.md) |
| 保存、交易與恢復 | 保存與模型可用性、取消、回查原結果、程序中斷怎麼分責 | [工程沿革第2、3例](engineering-and-verification.md)、[真事故案例](../research-casebook.md#案例二-長訪談中斷後如何避免重複與假成功) |
| 安全、維護性與效能 | 來源轉送、憑證、依賴方向、慢點與不必立即優化的取捨 | [工程沿革第1、4–6例](engineering-and-verification.md) |
| 評測、實驗與交付驗證 | judge是否可靠、有無資訊洩漏、失敗何時停止、開發環境外能否執行 | [量測與反證](evidence-by-capability.md#量測可信度控制變因與反證)、[工程交付與驗證](engineering-and-verification.md#評測方法與結案材料另外怎麼找) |

各主題是相互交錯的演進，不是獨立開發線。研究與設計文件可能同時含多輪修改；引用時用列出的章節找原問題，再向後讀同題修訂。

## 三種找法與原件位置

- **依時間及問題找：**本頁五份主題沿革（產品、檢索、Memory、JD、工程），由摘要往原件深入。
- **依研究能力找：**[按能力找證據](evidence-by-capability.md)，判準來自[系所／教授公開資料研究](../../history.md#source-518e00bdc0f3f08d2efa)，不是代替學校評分。
- **查文件未展開的實作：**[前後程式與測試](code-evolution.md)，區分直接觀察、當時說明與事後推論。

原始研究仍在 `research/`／歷史 `specs/`，決策在 `adr/`，實驗在 `experiments/`或各任務 `evidence/`，原始輸出在其 `data/`；本區只放摘要及引用。最早原件從[3月／5月存檔](../../history.md#source-662ea57dd88fb5eb0879)找，封存分支從[歷史恢復索引](../../history.md#source-7ab1424323b9555aac83)找。[案例集](../research-casebook.md)僅展開少數案例，不是另一份完整歷史。

## 先看整體變化

| 時期 | 當時架構或研究重點 | 當時暴露的問題／下一次改動 |
|---|---|---|
| 3–5 月：前身資料處理 | OCS PDF → 結構化 JSON；解析代碼、任務、產出、指標、知識與技能 | 真實 PDF 的斷行、合併儲存格與跨頁格式破壞解析；資料模型也由 Task 內清單改為 P-centric blocks。[原件](../../history.md#source-662ea57dd88fb5eb0879) |
| 5 月：JobIntel | pgvector 參考檢索＋LangGraph 固定訪談階段，STAR → 5W2H → 指標 → 文件 | 短答、phase 過濾與切換判定造成重問／提早前進；此時尚非後來 A／B1／B2 架構。[原狀態機](../../history.md#source-f6099bd5a1a81730042d) |
| 6 月：知識服務與 monorepo | 獨立 indexer、catalog／精確讀取與向量查詢分工；可編輯選單＋深問；三 repo 整合 | 檢索範圍、輸出資料契約、保存責任與服務依賴要分清。[流程](../../history.md#source-63e4ec03038b45bbe58e)、[整體設計](../../history.md#source-f661c579036f7cefc3f9) |
| 7 月上旬：顧問而非填表 | 先後研究顧問／書記、工具、追蹤修訂與事件議程 | 真人及 persona 試訪分別出現填槽感、零任務卻有大量態度、長聊不產出 P；不只是換模型。[7/6](../../research/work-analysis/2026-07-06-consultant-not-formfiller-redesign-research.md)、[7/9](../../research/work-analysis/2026-07-09-interview-flow-task-curation-and-flexibility-research.md)、[7/14](../../research/work-analysis/2026-07-14-interview-agenda-architecture-research.md) |
| 7 月中下旬：證據與分析工作流 | vNext Evidence workflow → 專業顧問 R1 比較 → 最小 one-stage 訪談閉環 | 短答需要前問；複雜的多階段不一定更好，評測器也可能漏判。[短答決策](../../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)、[R1a 結果](../../experiments/2026-07-27-r1-task-discovery/r1a-results.md) |
| 8 月：Framework 與編輯工作面 | LangChain／LangGraph、巨型編輯表單 → VFS → 持久草稿 → 共用目前稿 | 模型填無關參數與定位易錯；跨輪草稿與人工修改形成兩份競爭內容。[VFS 決策](../../adr/0064-deep-agents-virtual-jd-workspace-and-deterministic-evidence-anchor.md)、[共用稿決策](../../adr/0069-shared-current-jd-working-copy-and-semantic-approval.md) |
| 8 月底–9 月：長訪談與分層 Memory | 可修訂理解、routing、canonical 原話、分層分析與壓縮；多批 CT 實驗 | 路由找到候選不代表事實忠實；仍出現漏記、更正未吸收、未知消失等，詳[記憶沿革](memory-and-context.md) |
| 9 月：JD 編輯器與正式入口 | Plate 文件樹候選 → relational JD 管理編輯器；9/22 以 ADR0077 切正式權責 | 能編一份文件不等於能管理各欄位與關係；舊入口也會讓實作者用錯架構。[0075](../../adr/0075-relational-jd-authority-and-structured-editor.md)、[0077](../../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md) |
| 9 月底–10 月：新目標重建與驗證 | 重新確定原始訪談 → 情境 → 理解 → JD；明確 Snapshot、引用、Context、工具與恢復邊界 | 已有實作與分層證據，但品質／容量及正式切換仍各有界線；不能把計畫寫完或一場長旅程完成當整體通過。[計畫](../../history.md#source-ee8cbce8eb3c303d1765)、[0079 草案](../../adr/0079-target-rebuild-production-cutover.md) |

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

目前各主要面向均有閱讀入口；不表示每次未成文決策都已找回。尚缺本人貢獻確認、未保存的當時判斷、部分原capture、真人效果及部分交付環境實測。下一步沿引用選取適合公開的原件，再決定怎麼寫；**不先排除早期及失敗材料，只留下近期成功案例。**

## 演進索引初次整理核對

2026-10-02：本次新增／調整的 14 份 Markdown 檔案，相對連結與章節錨點檢查為零失效；三份早期原文與列出的 Git blob 完全相同，相關提交日期亦已核對。此結果只涵蓋這次索引與入口，既有歷史文件內仍可能有已退役路徑，須沿封存索引或 Git 回讀。

沒有重跑舊模型實驗、修改產品或刪除原始證據；原件中「已驗證」的敘述仍屬各次原實驗的範圍，不是這次重新驗收。

同日後續按教授／系所公開能力目標補找的九組材料及該輪五份文件檢查，見[能力索引核對範圍](evidence-by-capability.md#本輪核對範圍)；不與以上初次整理的14份檔案混計。

同日再往程式及測試追查的材料見[程式演進](code-evolution.md)。這是對既有時間線的深化與補充，不把每份原碼當成獨立實驗，也不宣稱所有未成文決策都已找回。

## 跨面向補充與分類核對

2026-10-02 後續依「不只 Memory，其他面向也要整理」補充：

- 新增[JD編輯與交付](jd-authoring-and-delivery.md)七組素材：參考身分、工具建立契約、人機共稿、編輯器比較、業務操作、來源核對及PDF；不是七次均通過的獨立實驗。
- 新增[工程與驗證](engineering-and-verification.md)七組素材：依賴方向、原輸入查回、取消交接、可信來源、容量效能、程式維護與套件交付；另路由既有評測／事故及本輪讀到的T16／T17更新。
- [Memory沿革](memory-and-context.md#9月底重建前的六個轉折)補出六個轉折，保留C退役、多案例返工漏案、角色分責、引用確認方案撤回、候選與快照、有效訊息序列的次序及限制。
- 本頁改為十一面向索引、五份主題沿革；報告入口只保留閱讀路由，原始研究與實驗不搬移、不複製成第二份結果。

本輪變更五份文件；驗證範圍擴及報告入口與全部八份演進文件，**九份Markdown的相對連結／章節錨點零失效**，新增引用的九個Git原件均可取回。核對中修正兩個任務章節定位；這不是重新驗收歷史程式。分工查找後由主代理回讀主要原件與程式diff，區分文件判斷、固定harness、真PG、自然模型與瀏覽器證據。

沒有刪除原件、修改產品、呼叫付費模型或將歷史失敗改寫為成功。仍缺的本人貢獻、未成文動機、部分原始capture與真人成效，繼續留作後續挑選材料時的補證項目。
