# 開發計畫

計畫保存施工範圍、進度、驗收及證據去向。後續工作先由[目前決策](../current-decisions.md)定位責任文件，再依[開發規範](../implementation/development-standard.md)界定切片；計畫不另抄產品規格，也不自行構成施工授權。

## 活動計畫

目前沒有進行中的施工計畫；候選設計及未驗效果由[目前決策](../current-decisions.md)指向責任文件，不以計畫清單推定已授權。

## 已結案

| 計畫 | 結果與證據入口 |
|---|---|
| [文件整體整理與維護](2026-10-08-docs-maintenance.md) | 導覽、現行契約與沿革分離、集中圖源、引用檢查及交叉審核；範圍與驗證見原紀錄 |
| [架構文件與圖面重構](2026-10-08-architecture-documentation-review.md) | 架構／實作分工、正文、索引及圖面審查；覆蓋與文件驗證見原紀錄 |
| [全系統程式、資料與架構審查及重構](2026-10-08-full-system-review-and-refactoring.md) | 工程切片、獨立審查與整合重驗；實際覆蓋、原失敗、修正及限制見計畫 evidence，未部署至共用服務 |
| [JD 工作計畫對齊與有限比較](2026-10-07-jd-work-plan-alignment.md) | 沿 Accepted ADR0082 的工程及有限比較；命令、原件與限制見[工程證據](evidence/jd-work-plan-2026-10-08.md) |
| [原規劃筆記實作與 P1／P2 比較](2026-10-07-interview-plan-implementation-and-comparison.md) | ADR0081 舊未知筆記的工程及比較沿革；現行 Plan 契約見[JD 工作計畫](../specs/jd-work-plan.md) |

結案不等於模型品質全面達標，實際證據沿[驗證範圍](../architecture/verification.md)判讀。JD 工作計畫的[後續品質問題](../architecture/verification.md#41-jd-工作計畫後續待辦)由架構驗證文件維護，不重開已完成切片或自動追加原八場測試。公版按需導覽與收尾品質的後續範圍見[公版工具與用途](../specs/2026-10-04-public-reference-completion-design.md)。

## 較早施工與原件

新架構 T01–T18 已於 2026-10-02 結案並完成本機正式切換，不重置或重跑。原施工、公版檢索 API、工具及角色接線的結案計畫已封存；已提交版本與本機材料分別依[歷史查閱方式](../history.md)取回。

方法、結果與原始輸出保留在[實驗目錄](../experiments/README.md)，API／工具的反例與重播見[工程驗證](../experiments/engineering/README.md)。少數舊路徑保留歷史入口，供固定雜湊的原件追讀，不另存第二份計畫正文。
