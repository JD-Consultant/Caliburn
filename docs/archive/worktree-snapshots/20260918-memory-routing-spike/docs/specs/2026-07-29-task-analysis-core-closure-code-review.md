# Task Analysis Core closure code review

- 日期：2026-07-29
- 範圍：`app/job_analysis` T1–T7、顧問流程、最終 LLM 架構、ADR 0040–0042
- 結論：`task-analysis-core-v1-scripted` 是有效的隔離式 scripted vertical，但需完成本文件的修正後，才可開始 persistence。

## 1. 已確認保留

- `app/job_analysis` 維持 greenfield，不 import `interview`、`interview_vnext`、DB 或 Web。
- 保留 A6 第一版方向：強模型、light schema、one-stage、full harness。
- 保留 Source／Current Work Model／Current JD 的權威分層。
- 保留 ordinal-only 模型介面、逐字 source anchor、deterministic verifier、無隱藏 retry／fallback。
- scripted smoke 只證明管線，不宣稱模型品質或完整顧問流程。

## 2. 必修

### C1. Merge／split 的來源閉包

即時 merge 不能只保留本輪 anchor；新 Task 必須繼承並去重來源 Task 的有效 SupportLink，再加本輪來源。Split 不可把母 Task 的全部來源無差別複製到每個 child；模型輸出的每個 child 必須能指明它沿用母 Task 的哪些 support ordinal，application 再解析成 SupportLink。

跨 Current JD 的 staged merge／split 也必須保存同一份、已由 application 解析完成的 support links，否則員工接受時無法建立符合「active Task 至少一條有效支持」的不變量。

### C2. 狀態與 proposal 一致性

- `JobAnalysisState` 拒絕重複或非 canonical 的 Current JD task ID、Proposal ID。
- `StagedWorkModelDelta` 拒絕重複 lineage／new task ID，並依 action 鎖定合法欄位。
- 新 Task／Proposal ID 採 insert-only；ID 撞到不同內容時整輪 typed rejection，不覆寫。
- 完全相同的兩筆 `add` work signal 由 verifier 拒絕；不做模糊文字相似度去重。
- 本輪重新判定某 Task、但沒有建立 replacement Proposal 時，重疊的 pending／deferred Proposal 必須 visible stale closure。
- withdraw／merge／split 的 retirement source 必須來自該 signal 實際引用的 employee-turn anchor，不可無條件寫 current turn。

### C3. Provider 可歸因

R1a A6 使用 `reasoning effort = high` 且不保存 reasoning；第一版 adapter 必須明確送出相同 treatment，或另開決策撤銷 A6 對應。本次採前者。

OpenRouter 官方文件說最終使用模型會回在 response `model`，因此 200 response 必須帶與 request 相同的 exact model；不符時 typed failure。Request 端繼續維持單一 provider、`allow_fallbacks: false`、`require_parameters: true`：

- [OpenRouter — Model Fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks)
- [OpenRouter — Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter — Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)

### C4. 文件權威

更新 root `README.md`、`ARCHITECTURE.md`、`apps/api/README.md`、`docs/README.md` 與既有 plan writeback，使其一致表達：

- 本機 Web、員工使用、無登入、非 SaaS；
- `job_analysis` 是隔離的新顧問引擎開發線，尚未 route 到產品；
- ADR 0042 與 R1a 結果已存在；
- plan 的 PowerShell focused test 命令不得依賴 shell glob 展開。

## 3. 明確不做（過度設計檢查）

本次不新增：

- DB、revision、event sourcing、hash chain；
- Story Graph、通用 workflow／agent runtime；
- Web route、登入、多租戶、SaaS；
- semantic similarity dedupe、工具字典；
- 新模型矩陣、pass³ 或大量測試排列；
- Role／coverage／OPKS 等下一階段功能。

測試只增加能重現上述具體錯誤的最小 regression cases。完整顧問流程缺口仍維持已揭露狀態，待本修正完成後另行排定。
