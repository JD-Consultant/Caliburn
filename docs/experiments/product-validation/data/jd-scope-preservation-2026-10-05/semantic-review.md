# 逐題語意與來源核對

本頁以 [cases](live-01/cases.json)、[凍結判準](live-01/grading.json)、[合成原話](live-01/materials.json)及每題實際工具回傳核對最終 `task.work`／`unknowns`。判的是意義，不要求逐字相同。這是助理的離線判讀，沒有真人評分者或統計顯著性主張。

以下 **C = complete、P = partial**；沒有落在 missing 或 incorrect 的既定檢查項。額外發現另列，不更改既有分母。「已讀到」依工具正文，不因 map 有名稱就算已讀。

## 1. 完整任務

各列分數依下列固定順序：

| 題目 | 判準順序 | 最小員工來源聯集 |
|---|---|---|
| post_delivery | corrected_deadline、not_resolution_guarantee、no_monthly_a、shared_authority | 6、8、12 |
| maintenance | maintenance_periods、maintenance_scope、approval_required、approver_unknown、shared_authority | 6、10、14 |
| infrequent_work | infrequent_materials、materials_authority | 18 |
| resolved_approval | maintenance_periods、maintenance_scope、approver_resolved、approval_scope、shared_authority | 6、10、14、16 |

| 題次 | baseline：依序判讀 | scoped：依序判讀 |
|---|---|---|
| post_delivery r1 | [C C C P](live-01/result-read-post_delivery-r1-baseline.json) | [C C C C](live-01/result-read-post_delivery-r1-scoped.json) |
| maintenance r1 | [C C C C P](live-01/result-read-maintenance-r1-baseline.json) | [C C C C P](live-01/result-read-maintenance-r1-scoped.json) |
| infrequent_work r1 | [C C](live-01/result-read-infrequent_work-r1-baseline.json) | [C C](live-01/result-read-infrequent_work-r1-scoped.json) |
| resolved_approval r1 | [C C C C C](live-01/result-read-resolved_approval-r1-baseline.json) | [C C C C C](live-01/result-read-resolved_approval-r1-scoped.json) |
| post_delivery r2 | [C C C P](live-01/result-read-post_delivery-r2-baseline.json) | [C C C C](live-01/result-read-post_delivery-r2-scoped.json) |
| maintenance r2 | [C C C C P](live-01/result-read-maintenance-r2-baseline.json) | [C C C C C](live-01/result-read-maintenance-r2-scoped.json) |
| 合計 | **21 C、4 P** | **24 C、1 P** |

### 判讀理由

- **交付後缺陷：**四份均採更正後 48 小時、從缺陷回報起算，區分初判與完成修復，保留甲無固定月維護。baseline r1／r2 都有本人前端與同事後端／部署，卻沒有客戶確認需求，因此 shared_authority 為 P；scoped 兩份皆寫齊。
- **例行維護：**四份都區分原每月與 10 月起每季第一個工作日、保留檢查頁面及修正前端、超約先核准且核准人仍未知。baseline 兩份及 scoped r1 均只寫約定前端，沒有客戶確認需求與同事後端／部署，因此 shared_authority 為 P。scoped r2 補齊；沒有把需求確認當成已知的超約核准人。
- **低頻工作：**兩份都保留約每年一次、本人檢查圖片及連結、客戶供稿與確認、本人不規劃活動或撰稿，兩項既定檢查為 C。scoped 的「本人上線」不由此自動取得來源支持，見下方額外發現。
- **核准人已補充：**兩份都保留新舊周期、檢查及修正、本人整理影響與提出需求、客戶產品負責人核准而非本人、客戶確認需求及同事後端／部署。不再把核准人列未知。scoped 沒逐字重述「不是每次修復都要核准」，但其核准條件明確限定超約，故 approval_scope 仍為 C。

來源正文中的「自 10 月起」沒有年份。輸出將年份列為未知有依據，但不代表顧問下一輪一定要追問；本批只評草稿及未知保存，沒有測訪談收束。

## 2. 局部片段反例

| 題目與輸出 | 必要條件 | 無關展開 | 最小員工來源 |
|---|---|---|---|
| [deadline baseline](live-01/result-read-deadline_only-r1-baseline.json) | 2／2：缺陷回報後 48 小時初判，非修復保證 | 無 | 8、12 |
| [deadline scoped](live-01/result-read-deadline_only-r1-scoped.json) | 2／2，同上 | 無 | 8、12 |
| [approver baseline](live-01/result-read-approver_only-r1-baseline.json) | 3／3：超約才核准、本人整理提出不自批、產品負責人決定 | 無 | 16 |
| [approver scoped](live-01/result-read-approver_only-r1-scoped.json) | 3／3，同上 | 無 | 16 |

依事前規則，無關展開只看 work 與 unknowns，不把較長的來源標題算成帶入其他工作。四份均未加入無關周期、其他案工作或部署分工；unknowns 皆為空。

## 3. 引用與讀取

16 份輸出都引用本題實際讀過的一項工作理解。按凍結的 [corrections](live-01/workspace-corrections.json)／[extension](live-01/workspace-extension.json)回查，各題引用的來源序號聯集均涵蓋上表所列最小員工來源，沒有引用越界序號。這是鏈可達與必要證據核對，不代表每個正文的新推論都成立。

各題必要資訊都在實際讀取的正文中；共通分工在甲、乙理解的「分工與需求」段。原話工具本批未使用。baseline 低頻題額外讀了甲、乙另兩項，其他 15 題都只讀本題一項理解。讀取數、map 次數與 usage 可由 [analysis](live-01/analysis.json)回到各題工具事件。

## 4. 不加入凍結分數的額外發現

| 輸出 | 具體表述／現象 | 判斷與界線 |
|---|---|---|
| scoped post_delivery r1；baseline post_delivery r2 | 把訂單逾時、防重複送單放進「交付後缺陷」任務 | 這項工作在理解內有依據，但訪談沒有把它指定為交付後缺陷；觀察為同案其他工作混入，不宣稱原功能本身捏造。 |
| baseline／scoped resolved_approval r1 | 維護與變更處理題帶入查詢逾時保留日期 | 同樣有來源，但超出題目指定的維護／變更範圍；兩組各一次。 |
| scoped infrequent_work r1 | 「本人僅在客戶確認後上線」 | 員工原話 18 與理解均為「客戶確認後才上線」，未指明上線執行者。候選把時序條件改成員工行動，有缺乏依據的責任擴張風險；原定素材分工檢查不能充分捕捉它。 |

這些發現應成為下一次事前反例，不能事後增加本批分母、改寫原件或用補跑挑掉不好的輸出。完整任務共通分工應否重述的適用界線，另見[方法核對](method-review.md)。
