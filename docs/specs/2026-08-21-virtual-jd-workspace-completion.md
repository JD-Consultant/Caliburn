# Virtual JD workspace upgrade completion

- 日期：2026-08-22
- 狀態：**Phase C closure recorded；exact profile live smoke 仍為 partial，不是 live pass**
- 範圍：current virtual JD workspace、deterministic candidate check／repair、pending-only publication 與 employee authority review。

## Delivered

- 修正 provider-facing strict response schema：`OutputEvidenceReference.occurrence` 是 required strict integer sentinel；唯一 quote 使用 `0`，重複 quote 使用 1-based occurrence，application mapper 再把 `0` 還原為 workspace 的 `None`。agent prompt 與相關 fixtures／tests 同步更新，沒有新增 abstraction 或放寬 schema。
- 以同一份 `WorkspaceCatalog` 將本輪 model-safe `/sources/current/source-###.txt` 與 `/approved/index.json`／`/pending/index.json` 導覽入口放入 context orientation，減少模型為了連回 Evidence handle 或找到文件 projection 而盲列目錄；沒有新增 DB query、Tool 或 authority store。
- 以 TDD 把 Skill progressive disclosure 與 external-data lookup wave 分開：`/skills` 不消耗資料查詢波次，`/sources`、`/approved`、`/pending` 的真實第三波仍 fail closed。LangChain 全域 Tool 保險絲由 12／24 的失敗證據調整為 owner 核准的 48；它不是每輪目標。
- 在既有 `write_file` Tool description 補上最小 candidate creation contract：三筆可執行的 Duty／Task／Output JSONL 範例、P／K／S path-kind 對應，以及 candidate `occurrence=null`／final wire `occurrence=0` 的明確邊界。沒有新增 Tool、root、agent、model step 或 schema service。
- Web production 沒有 accessibility gap；`DocumentReviewPanel` 已是原生 checkbox。保留最小 integration coverage，以真鍵盤空白輸入驗證 focused accept 與 semantic review actions，並核對每個 command 的 action identity 與 edit payload。
- 更新 runtime design、live smoke spec、north-star audit ledger，並建立本 completion record。plan-local live／browser runners 仍是 ignored files，不是產品或交付來源。

## Evidence interpretation

### Provider schema

第一次 exact live run 被 OpenAI strict response schema 拒絕，原因是 optional `occurrence` 未列入 required。上述 sentinel mapping 是針對該 blocker 的最小修正；這不是新的 domain abstraction。

### Exact-profile live smoke

schema 修正後的第一輪已實際到達 `openai/gpt-5.6-luna`、OpenAI、`reasoning=max` 與既有八 call／兩 lookup-wave policy，並確認 exact seven-Tool surface 已 bound/exposed；當時在 edit/check 前觸發 `LookupWaveLimitExceeded`。

上述導覽與 guard 修正後，第一個有效 48-call run 在建立 candidate 前觸發第三波 external lookup；contract audit 將根因收斂為 first-resource bootstrap 缺口。owner 核准後以 TDD 補上 compact creation contract，focused regression 更新為 146 passed／6 skipped；同一 Luna 情境只重跑一次，模型成功修改既有 Task、建立兩個新 Task 與第一個 Output，並在第八個 model step 發出 candidate check。其後第九個 finalization call 被既有 `max_model_calls=8` fail closed，故沒有 final structured response／pending publication，仍不得寫成 live pass。

本輪八次 attempt receipt 合計 79,658 tokens（input 73,529、output 6,129），其中 cache read 58,079、cache write 15,426，總 provider cost US$0.01237768；prompt caching 已生效。22 個 model-issued Tool calls 低於 48，因此新 blocker 不是 Tool capacity。依停止條件未再重跑、未提高 model-call budget、未換模型或引入 multi-agent；後續需先比較「最小增加 finalization step」與「減少重複讀取／Skill 分波」的效果、成本與複雜度。

owner 隨後以 ADR 0065 核准 policy revision 2：11 model calls 與 160,000 cumulative raw tokens，其他 context／lookup／Tool／cost／elapsed／retry guard 不變；focused deterministic gate 為 148 passed／6 skipped。唯一獲准的新 Luna／OpenAI／`reasoning=max` smoke 沒有觸及這兩個上限，而是在第四步精確用滿 `max_tokens=4,096`、`finish_reason=length`，接著以 `StructuredOutputValidationError` fail closed；沒有 candidate mutation、check 或 publication。

四張 receipt 合計 41,447 tokens（input 35,003、output 6,444），cache read 21,652、cache write 13,339，cost US$0.01150299。依 Luna 官方單價，output／reasoning 約 US$0.00773280、占 67.2%；這份**失敗回合**線性換算 50 輪約 US$0.58、100 輪約 US$1.15。官方 contract 與既有 repo smoke 共同指出：reasoning 與 visible final 共用 output cap，OpenRouter `max` 約把 95% 配給 reasoning；repo 既有 `medium／8,192` 能完成 structured final，而 `max／4,096` 與 `max／16,384` 均曾截斷。因此不能把提高 output cap 當免費修正，也不能把 `max` 當每個長期訪談回合的預設。

owner 後續另核准一次 `Luna／xhigh／32,000` 試跑。Caliburn 原 profile literal 漏列 upstream 已支援的 `xhigh`，因此先以 TDD 加入 boundary support，production 預設不變。新 run 完成候選 Task/O/P 編輯與兩次 candidate check，最後 primary response 為 `stop`，沒有 output truncation；十二張 receipts（11 primary＋1 summarization）合計 134,575 tokens，其中 reasoning 8,472，cost US$0.02299813、model latency 125,548 ms。它最後在 semantic commit 前由 `ConsultantVerificationError` fail closed，沒有 pending publication。trace 同時顯示 summarization 後模型重讀五個已載入 Skill並被 one-load backend 拒絕；這是待 deterministic reproduction 的強烈交互訊號，不是已證實的 exact verifier branch。cleanup 後所有相關 persistence counts 仍回到零。

runner 只使用 disposable document，finally 以 exact document identity cleanup；controller evidence 顯示 cleanup 後相關 persistence records 回到零，沒有保留 live fixture 或 secret。

### Deterministic browser authority review

controller 以真 local Next、FastAPI 與 disposable PostgreSQL fixture 完成 semantic accept、edit-and-accept、reject with reason、defer，並保留單一 O pending。reload 後 decision status 保留；API snapshot 顯示 job title／work description 才進 approved，Duty／Task 維持原值，`opks_count=0`。畫面沒有 candidate path、`write_file`、`edit_file` 或 `check_candidate_document` 等內部細節。

fixture document 已精確刪除，相關 persistence records 回到零，servers 已停止。這是 deterministic employee-authority evidence，不替代 stochastic exact-profile provider smoke。

## Boundaries and deferred work

RAG／Reference consumer、能力級別／A、auto mode、multi-agent、formal quality eval、lookup-wave／Skill eligibility 與 model fallback 調整仍延後。全域 Tool guard 已依本輪 TDD 調整為 48；finalization model-call policy 已由 ADR 0065 收斂。尚未收斂的是多輪互動 model profile：production `Settings` 在沒有 env override 時仍是 Opus 5／high／4,096；Luna `xhigh／32,000` 已證明可完成候選操作但尚未通過 final commit，故不能只憑較高 reasoning 把它寫成最終 production 選型。下一個 blocker 是 deterministic 定位 final verifier 與摘要後 Skill continuity，不是再付費比較 effort。這次 closure 不引入第二份 document store、第二條 authority seam 或新的 UI production 行為。

後續 runtime 決策固定採「效果優先、成本與複雜度成比例」：先看代表性情境中的員工可見結果，再比較每份 JD 跨輪累計 token／cache、calls、延遲、provider cost、失敗率與新增維護邊界。少量效果提升不值得大幅成本或複雜度；預設維持單一顧問，不因本次 blocker 引入 multi-agent。現有 durable attempt receipts 已足以按 document 加總，第一版不為此另建 billing subsystem；但單輪 `max_cost_usd` 是 commit 前 fail-closed 驗證，不是 provider 付費前的即時預算器，不得誤稱為費用不會超過該值。

## Verification record

所有 DB-backed gates 使用 explicit disposable PostgreSQL target；未把 skipped DB tests 當作 green。完整 gate command 與結果以本次 task handoff／live smoke spec 為準，避免在文件內固化易漂移的 commit SHA 或測試數字。

最終獨立 review 找到兩個窄 canary 缺口：provider wire 原可 coercion boolean／string occurrence，Web 鍵盤測試也未核對 action identity。前者改成 strict integer 並補 ambiguous-quote fail-closed regression；後者只強化 request assertion，沒有新增 UI、狀態或 workflow。
