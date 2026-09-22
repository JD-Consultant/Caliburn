# 2026-09-22 本機 `main` R0／R1 封存

## 為什麼封存

正式 relational JD App 合併後，發現本機舊 `main` 仍有一條未進入 GitHub 新 `main` 的歷史。它包含舊 `apps/api` 架構下的 R0／R1 professional consultant 研究、設計、提示詞、合成案例、ablation、blind grader 與測試工具。

舊程式不再恢復為 production authority；本目錄保存該分支完整的 **303 份 `docs/` 文件**，並把相對共同基準新增或修改的 **76 份相關頂層說明、提示詞、合成案例、eval 與測試檔**依原路徑一併放進 `docs/archive`。這樣舊文件的相對連結仍可閱讀，也避免研究與實驗證據因本機分支整理而消失。

## 來源定位

- 共同基準：`82cc50f9c6f5e0777f9bf8383253ec91b354ba7f`
- 本機歷史末端：`06ac2235cb0b2b09b435f5f3167f98050b5cb9f1`
- 封存內容：完整 `docs/` 歷史樹、頂層設計說明，以及 `apps/api` 下的 professional consultant 提示詞、離線 eval、案例、rubric 與相應測試；共 380 份檔案（包含本說明）。
- 未封存內容：依賴、cache、暫存資料庫、本機執行產物與其他未提交檔案。

## 提交先後

以下依原分支由舊到新排列，供報告重建「遇到問題 → 研究 → 實作 → 驗證」的順序：

1. `39bc4a2f` — docs: lock R0 production cutover architecture
2. `936c59b3` — docs: configure local agent workflow
3. `3c84802a` — docs: record hybrid job discovery decision
4. `4819430d` — docs: clarify employee-confirmed JD draft boundary
5. `056227ae` — docs: defer future review platform option
6. `99806304` — docs: require real employee pilot release gate
7. `9cd283a8` — docs: correct server-deployed product scope
8. `78e4dcb4` — feat(api): establish R1 task discovery offline authority
9. `712e2d52` — feat(api): add R1 scripted task discovery runners
10. `f06c35e0` — feat(api): add R1 ablation capture harness
11. `4b672318` — feat(api): add R1 blind eval grader
12. `06ac2235` — Merge origin/main into the offline R1 branch

## 使用界線

- 這裡的 `apps/api/...` 是封存路徑中的歷史副本，不會被 workspace、package manager、Python package 或正式啟動器載入。
- 內容可能已被後續決策修正或取代；理解現況時先讀現行決策，再把本 snapshot 當成演進證據。
- 若要引用研究結論，應同時標示原提交順序與後續 successor 決策，不把舊 proposal 當成現在已採用的需求。
