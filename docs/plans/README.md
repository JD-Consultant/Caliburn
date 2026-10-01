# 計畫與施工進度

計畫回答「依哪份規格、分哪些任務、如何驗收」。計畫不是產品規則的副本，也不能把待執行步驟當成已通過證據。

## 當前接手入口

1. [新目標重建 Goal／計畫](2026-09-29-target-rebuild/README.md)：範圍、授權、退出條件。
2. [T01–T18 任務與下一步](2026-09-29-target-rebuild/tasks.md)：唯一任務狀態入口。
3. [計畫審查](2026-09-29-target-rebuild/review.md)：規範與要求覆蓋。
4. [任務證據分類](2026-09-29-target-rebuild/evidence/README.md)：已驗、未驗、失敗及限制；原件在相應 `data/`。

任務涉及的契約由[架構地圖](../target-architecture-map.md)路由；SDD／TDD、命名、模組與寫法由[實作入口](../implementation/README.md)路由。不要從日期較新的某個 plan 自行推導 production 已切換。

## 較早計畫怎麼看

本目錄其他日期檔案保留各階段施工及研究計畫。是否完成、被取代或仍有獨立用途，須對照[目前決策](../current-decisions.md)、相關 ADR 與該計畫證據；本次不批量把「較早」等同「不用」。

- 早期已封存的獨立施工計畫：[archive/implementation-plans](../archive/implementation-plans/README.md)。
- 不同歷史工作樹的計畫及研究：[工作樹歷史索引](../archive/worktree-history-index.md)。
- 需查舊檔名：[整理前文件索引](../archive/2026-10-02-document-index.md)；本次路徑變更另見[對照表](../archive/document-classification-2026-10-02.csv)。

新任務沿既有計畫更新，不為每輪進度另建一個平行計畫；實驗結果留在證據文件，不能只寫「完成」而遺失怎麼發現、怎麼解決、怎麼驗證。
