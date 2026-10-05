# 語意、更新與來源判讀

依 [凍結判準](live-01/grading.json)、[合成訪談](live-01/materials.json)與 `live-01` 的 workspace／result 原件逐項核對。判讀者為本助理，非真人顧問評分。核准範圍的一項措辭爭議另交未提供組別名稱的助理複核；其餘不是盲評，也沒有事後增加分母。

## 1. 維護結果：兩組均 33 項完整

33 是三批檢查次數（10＋10＋13），不是 33 名員工、33 個獨立樣本或 33 次模型重複。下表的事實在兩組相應正文中都可取得，必要員工序號也在該物件來源內；顧問問題不算事實來源。

| 凍結 check_id | 適用批次 | 必要來源序號 | 兩組結果與核對重點 |
|---|---|---|---|
| order_timeout | 三批 | 2 | 完整；甲防重複送單 |
| reservation_timeout | 三批 | 4 | 完整；乙保留已選日期，不混到甲 |
| shared_authority | 三批 | 6 | 完整；客戶確認需求、員工約定前端、同事後端規則與部署 |
| initial_deadline | 初始 | 8 | 完整；收到回報後 24 小時初判 |
| corrected_deadline | 更正、補充 | 8、12 | 完整；撤換為 48 小時，沒有並存兩個現行期限 |
| not_resolution_guarantee | 三批 | 8 | 完整；初判期限不是完成修復期限 |
| no_monthly_a | 三批 | 8 | 完整；甲無固定月維護 |
| initial_monthly_b | 初始 | 10 | 完整；乙每月一次 |
| maintenance_periods | 更正、補充 | 10、14 | 完整；10 月起每季第一個工作日，此前每月 |
| maintenance_scope | 三批 | 10 | 完整；頁面操作檢查、前端問題修正仍保留 |
| approval_required | 三批 | 10 | 完整；超約變更須先核准 |
| approver_unknown | 初始、更正 | 10 | 完整；仍未知，沒有偷看第三批答案 |
| approver_resolved | 補充 | 16 | 完整；客戶產品負責人核准，員工提影響與需求、不自行核准，舊未知已撤換 |
| approval_scope | 補充 | 16 | 完整；並非每次前端修復都須重新核准，措辭風險另述 |
| infrequent_materials | 補充 | 18 | 完整；甲約每年一次素材更換、圖片及連結檢查 |
| materials_authority | 補充 | 18 | 完整；客戶提供並確認，員工不規劃活動、不寫文案 |

物件位置可由三批[原方法初始](live-01/workspace-initial-baseline.json)、[更正](live-01/workspace-corrections-baseline.json)、[補充](live-01/workspace-extension-baseline.json)，及[候選初始](live-01/workspace-initial-coherent.json)、[更正](live-01/workspace-corrections-coherent.json)、[補充](live-01/workspace-extension-coherent.json)回查。

原方法按「逾時工作／交付後工作」組織；候選主要按甲、乙案組織。兩組第三批各新增促銷素材單元，最終均三項。兩組並未選擇完全相同的切分，也都沒有做到每種工作目的各成一項；不能從篇幅或物件數直接評優劣。

### 核准範圍的措辭風險，不加扣分

原方法寫「每次前端問題修正不需重新核准」，比來源「不是每次……都要」更絕對。其前句仍明列超出約定範圍須核准；依凍結判準，未把所有修復擴張成必須核准，也保留例外。因此本助理採另一位助理的匿名片段複核意見，判為完整，另留措辭風險；不為讓候選勝出事後降分。候選以「此核准要求適用於超出約定範圍」表達得較清楚。

## 2. 顧問讀取與 JD：原方法 15 完整／1 部分；候選 14 完整／2 部分

`shared_authority` 同時檢查客戶確認需求、員工約定前端、同事後端規則與部署。只保留其中一部分，記為部分，不當作完全遺失或錯誤。

| 題目／判準 | 原方法 | 候選 | 可核對差異 |
|---|---|---|---|
| 交付後：corrected_deadline | 完整 | 完整 | 48 小時初判 |
| 交付後：not_resolution_guarantee | 完整 | 完整 | 不是 48 小時修好 |
| 交付後：no_monthly_a | 完整 | 完整 | 無固定月維護 |
| 交付後：shared_authority | 完整 | 部分 | 候選省略「需求由客戶確認」；正文已讀到這句 |
| 例行維護：maintenance_periods | 完整 | 完整 | 保留新舊週期與生效月份 |
| 例行維護：maintenance_scope | 完整 | 完整 | 檢查與修正均在 |
| 例行維護：approval_required | 完整 | 完整 | 超約先核准 |
| 例行維護：approver_unknown | 完整 | 完整 | 未用第三批資料填答案 |
| 例行維護：shared_authority | 部分 | 部分 | 兩組都只寫前端範圍，省略已讀正文中的客戶與同事分工 |
| 低頻工作：infrequent_materials | 完整 | 完整 | 約每年一次，圖片與連結 |
| 低頻工作：materials_authority | 完整 | 完整 | 客戶提供、確認；非員工規劃及寫文案 |
| 已確認：maintenance_periods | 完整 | 完整 | 週期未因補核准人而遺漏 |
| 已確認：maintenance_scope | 完整 | 完整 | 工作範圍仍在 |
| 已確認：approver_resolved | 完整 | 完整 | 核准人已知，不再列舊未知 |
| 已確認：approval_scope | 完整 | 完整 | 保留超約核准與員工不自行核准；原方法同有上述措辭風險 |
| 已確認：shared_authority | 完整 | 完整 | 客戶需求確認、前端與後端分工均列出 |

因此整題全部滿足為原方法 **3／4**、候選 **2／4**，不是以平均分掩蓋漏項。這一對不能估計穩定成功率。

原件：[原方法交付後](live-01/result-read-post_delivery-baseline.json)、[候選交付後](live-01/result-read-post_delivery-coherent.json)、[原方法維護](live-01/result-read-maintenance-baseline.json)、[候選維護](live-01/result-read-maintenance-coherent.json)、[原方法低頻](live-01/result-read-infrequent_work-baseline.json)、[候選低頻](live-01/result-read-infrequent_work-coherent.json)、[原方法已確認](live-01/result-read-resolved_approval-baseline.json)、[候選已確認](live-01/result-read-resolved_approval-coherent.json)。每份均含實際工具回傳、已讀定位與最終文字。

## 3. 沒保存、沒讀到，還是沒用到？

本批三個部分項都屬於**已保存、已讀到、最終 JD 未完整保留**。不是來源不在 Memory，也不是工具沒回傳；不能據此加一層 Memory 或要求再讀原話。

八份 JD 都引用本次實際讀過的理解，沒有直接引用訪談、沒有未讀引用；其必要來源序號可沿理解回到對應訪談。這支持本批的來源鏈可用，不表示引用本身能保證 JD 已保留每一項必要限定。

另有兩項不加入凍結分母的觀察：候選把同一專案的逾時與交付後缺陷放在一起，交付後 JD 因而帶入訂單逾時例子，顯示同案不必然等於同一工作目的；候選最終導覽較長（429 字元對 355），少讀正文不等於所有資料面都變小。
