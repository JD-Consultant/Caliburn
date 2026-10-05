# 分層比較：正文、來源與 JD 的語意核對

本批顯示顧問能只讀工作理解完成指定任務；同時抓到一個跨物件舊期限殘留，以及一次 JD 省略接手者。以下依執行前凍結的 [grading.json](live-01/grading.json)逐項核對，不用「有引用」替代「正文正確」。這是工程代理依合成資料所做的語意審閱，不是外部職務分析專家的評分。

## 1. 三批整理結果

每格依序為「正文／來源」。C＝complete、P＝partial、I＝incorrect；—＝該批不適用。相同事實若出現在多個物件，各承載物件都須有支持依據，不能以別的物件已引用來補足。

| 固定檢查項 | initial B1 | initial B2 | corrections B1 | corrections B2 | extension B1 | extension B2 |
|---|---|---|---|---|---|---|
| order_timeout | C/C | C/C | C/C | C/C | C/C | C/C |
| reservation_timeout | C/C | C/C | C/C | C/C | C/C | C/C |
| shared_authority | C/C | C/C | C/C | C/C | C/C | C/C |
| initial_deadline | C/C | C/P | — | — | — | — |
| corrected_deadline | — | — | C/C | I/P | C/C | I/P |
| not_resolution_guarantee | C/C | C/C | C/C | C/C | C/C | C/C |
| no_monthly_a | C/C | C/C | C/C | C/C | C/C | C/C |
| initial_monthly_b | C/C | C/C | — | — | — | — |
| maintenance_periods | — | — | C/C | C/C | C/C | C/C |
| maintenance_scope | C/C | C/C | C/C | C/C | C/C | C/C |
| approval_required | C/C | C/C | C/C | C/C | C/C | C/C |
| approver_unknown | C/C | C/C | C/C | C/C | — | — |
| approver_resolved | — | — | — | — | C/C | C/C |
| approval_scope | — | — | — | — | C/C | C/C |
| infrequent_materials | — | — | — | — | C/C | C/C |
| materials_authority | — | — | — | — | C/C | C/C |

B1 正文與來源均 33 C。B2 正文 31 C／2 I，來源 30 C／3 P；兩項正文錯誤是同一舊期限問題跨批延續，不是兩個獨立缺陷。

### 原件與具體證據

- [第一批 B2 快照](live-01/workspace-initial-b2.json)：`object_1`／`object_3` 承接訂單逾時防重複，`object_2`／`object_5` 承接查詢逾時保留日期；共同分工明列「客戶確認需求」「後端業務規則與服務端部署由同事負責」。`object_4` 保存「24 小時內回覆初步判斷」及不保證修復、無固定月維護；`object_6` 保存每月維護、檢查及修正、範圍外核准與核准人未知。
- [更正後快照](live-01/workspace-corrections-b2.json)：`object_1`／`object_4` 改成「48 小時內回覆初步判斷」，保留非修復保證；`object_2`／`object_6` 保存「先前……每月一次；自 10 月起改為每季第一個工作日一次」及原工作範圍、核准人未知。兩項逾時處理理解 `object_3`、`object_5` 未改寫。
- [第三批快照](live-01/workspace-extension-b2.json)：`object_2`／`object_6` 以「由員工整理變更影響並提出」「客戶產品負責人事前核准」替換核准人未知，並保留「一般前端問題修正不需逐次重新核准」。`object_7`／`object_8` 新增約每年一次促銷素材檢查、客戶供稿及確認、非員工活動規劃或文案責任；未替員工指定實際上稿責任。

### 舊期限為何判錯

三批 `object_6` 均留有「甲電商的 24 小時初步判斷回覆要求不適用於此案」。這句只說甲的期限不套用乙，仍把甲的期限陳述為 24 小時；第二批原話 #12 已明確更正為 48 小時。不能因甲自己的理解已改正，就把另一物件的殘留當成沒問題。

而 `object_6` 只引用乙情境 `object_2`，三批可達原話依序為 `[4,6,10]`、`[4,6,10,14]`、`[4,6,10,14,16]`，均沒有甲期限的 #8／#12。`object_4→object_1` 的來源完整，所以此事實的來源評為部分，而非全部缺失。

判準外另記：甲情境 `object_1.description` 在後兩批仍以乙的「月維護條件」作對照；乙自己的導覽與正文已更新。這是跨案比較語句多存一份後未同步的同類問題，不另加分母。

## 2. 四組成對 JD 作答

表內按凍結順序列出每個檢查項；C＝完整、P＝部分。

| 題目與檢查項 | 分層 | 完整原話 | 具體判讀 |
|---|---|---|---|
| post_delivery：corrected_deadline、not_resolution_guarantee、no_monthly_a、shared_authority | C／C／C／C | C／C／C／C | 兩組均有 48 小時初判、非修復保證、無月維護、客戶確認與同事後端分工 |
| maintenance：maintenance_periods、maintenance_scope、approval_required、approver_unknown、shared_authority | C／C／C／C／P | C／C／C／C／C | 分層寫「不將後端業務規則或服務端部署列為本人維護範圍」，但沒保留「由同事負責」；不是完全缺少界線，也不能算完整分工 |
| infrequent_work：infrequent_materials、materials_authority | C／C | C／C | 兩組均保留年度低頻、圖片及連結檢查、客戶供稿確認、非員工規劃與文案責任 |
| resolved_approval：maintenance_periods、maintenance_scope、approver_resolved、approval_scope、shared_authority | C／C／C／C／C | C／C／C／C／C | 兩組均更新核准人、員工提出不自行核准、一般修正不重複核准，同時保留週期與分工 |

總計：分層 **15 C／1 P**；完整原話 **16 C**。完整符合全部指定項目的題目為分層 3／4、完整原話 4／4。兩組低頻題皆另列實際上稿／上線執行者未知，沒有再出現先前實驗擅自替員工增加上線責任的表述；這是本批觀察，不是跨批受控改善率。

原件：

- 交付後：[分層](live-01/result-read-post_delivery-layered.json)、[完整原話](live-01/result-read-post_delivery-full_history.json)。
- 例行維護：[分層](live-01/result-read-maintenance-layered.json)、[完整原話](live-01/result-read-maintenance-full_history.json)。
- 低頻工作：[分層](live-01/result-read-infrequent_work-layered.json)、[完整原話](live-01/result-read-infrequent_work-full_history.json)。
- 核准人補齊：[分層](live-01/result-read-resolved_approval-layered.json)、[完整原話](live-01/result-read-resolved_approval-full_history.json)。

## 3. 讀取與引用是否真的成立

四個分層題各實際讀一項理解正文並引用同一項，未讀情境、原話或重讀導覽；不是只看標題就回答。交付後、維護、低頻、核准補齊的引用鏈可達原話依序為 `[2,6,8,12]`、`[4,6,10,14]`、`[18]`、`[4,6,10,14,16]`，均包含各題必要支持。完整原話組引用依序為 `[6,8,12]`、`[6,10,14]`、`[18]`、`[6,10,14,16]`。

八份作答的既存引用均能支持實際寫出的內容；分層維護題漏掉同事，是「有讀到但省略」，不是 Memory 沒有保存或引用鏈斷裂。B2 的舊 24 小時比較句並未出現在四份分層 JD 作答中，但仍須作為儲存內容問題保留，不能因本次未擴散而刪去記錄。
