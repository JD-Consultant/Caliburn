# Virtual JD workspace upgrade completion

- 日期：2026-08-22
- 狀態：**Phase C closure recorded；exact profile live smoke 仍為 partial，不是 live pass**
- 範圍：current virtual JD workspace、deterministic candidate check／repair、pending-only publication 與 employee authority review。

## Delivered

- 修正 provider-facing strict response schema：`OutputEvidenceReference.occurrence` 是 required strict integer sentinel；唯一 quote 使用 `0`，重複 quote 使用 1-based occurrence，application mapper 再把 `0` 還原為 workspace 的 `None`。agent prompt 與相關 fixtures／tests 同步更新，沒有新增 abstraction 或放寬 schema。
- Web production 沒有 accessibility gap；`DocumentReviewPanel` 已是原生 checkbox。保留最小 integration coverage，以真鍵盤空白輸入驗證 focused accept 與 semantic review actions，並核對每個 command 的 action identity 與 edit payload。
- 更新 runtime design、live smoke spec、north-star audit ledger，並建立本 completion record。plan-local live／browser runners 仍是 ignored files，不是產品或交付來源。

## Evidence interpretation

### Provider schema

第一次 exact live run 被 OpenAI strict response schema 拒絕，原因是 optional `occurrence` 未列入 required。上述 sentinel mapping 是針對該 blocker 的最小修正；這不是新的 domain abstraction。

### Exact-profile live smoke

修正後已實際到達 `openai/gpt-5.6-luna`、OpenAI、`reasoning=max` 與既有八 call／兩 lookup-wave policy，並確認 exact seven-Tool surface 已 bound/exposed。實際 Tool calls 只觀察到 `ls`／`read_file`；Luna 重複這兩個 lookup，在 edit/check 前觸發 `LookupWaveLimitExceeded`。因此 exact-profile live 是 unresolved blocker，不提高 budget、不換 model/provider、不加 fallback、不放寬 policy，也不把它寫成 live pass。

runner 只使用 disposable document，finally 以 exact document identity cleanup；controller evidence 顯示 cleanup 後相關 persistence records 回到零，沒有保留 live fixture 或 secret。

### Deterministic browser authority review

controller 以真 local Next、FastAPI 與 disposable PostgreSQL fixture 完成 semantic accept、edit-and-accept、reject with reason、defer，並保留單一 O pending。reload 後 decision status 保留；API snapshot 顯示 job title／work description 才進 approved，Duty／Task 維持原值，`opks_count=0`。畫面沒有 candidate path、`write_file`、`edit_file` 或 `check_candidate_document` 等內部細節。

fixture document 已精確刪除，相關 persistence records 回到零，servers 已停止。這是 deterministic employee-authority evidence，不替代 stochastic exact-profile provider smoke。

## Boundaries and deferred work

RAG／Reference consumer、能力級別／A、auto mode、multi-agent、formal quality eval 與任何 lookup-budget／model fallback 調整仍延後。這次 closure 不引入第二份 document store、第二條 authority seam 或新的 UI production 行為。

## Verification record

所有 DB-backed gates 使用 explicit disposable PostgreSQL target；未把 skipped DB tests 當作 green。完整 gate command 與結果以本次 task handoff／live smoke spec 為準，避免在文件內固化易漂移的 commit SHA 或測試數字。

最終獨立 review 找到兩個窄 canary 缺口：provider wire 原可 coercion boolean／string occurrence，Web 鍵盤測試也未核對 action identity。前者改成 strict integer 並補 ambiguous-quote fail-closed regression；後者只強化 request assertion，沒有新增 UI、狀態或 workflow。
