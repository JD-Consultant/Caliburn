# Interview vNext prototype／donor rules

本 package 是已完成多個 durable runtime／provider 實驗的**隔離 prototype**，不是現行使用者路徑，也不是 ADR 0040
新專業顧問引擎的實作前提。`apps/api/app/api/router.py` 與 composition root 不得 import 本 package。

## 現行 authority

- 新專業顧問核心與 R1 gate：`docs/adr/0040-professional-consultant-engine-and-r1-validation-contract.md`
- R0 production cutover／退役：`docs/adr/0041-document-boundary-single-writer-cutover.md`
- R0 living boundary：`docs/design/professional-consultant-engine.md`
- R0–R9 順序：`docs/specs/2026-07-25-professional-consultant-architecture-realization-roadmap.md`
- current-row Authoring：`docs/specs/2026-07-24-job-authoring-v2-relational-storage-research.md`

ADR 0038 已被 0040 **完整取代**。舊 `turn.interpret`／`question.select`、Evidence／state shape、prompt、schema、
Context Builder、loader、grader、gold 與 suite hash 都不是新工作的 authority；不得以「已完成」為由直接 promotion 或接 Web。

## 可以保留作候選 donor 的部分

- provider-neutral operation/result/failure 邊界；
- OpenRouter wire adapter、binding、routing attribution 與 conformance；
- Capture artifact/event、outbox、checkpoint、attempt 與 recovery 基礎；
- deterministic idempotency／CAS／transaction 實作技巧；
- transcript 與案例意圖，但 expected output 必須依新 Task rubric 重新裁決。

每項 donor 都要由新 operation 的 contract／test 明確承重；禁止整包 import 舊 application/domain。

## 不變量

- 不 import 或 wrap `app.interview.consultant`、`scribe`、`harvest`、`select` 或其中介狀態。
- domain 只 import Python standard library、Pydantic 與同一新 domain package；provider SDK／ORM／FastAPI／Web DTO 停在 adapter。
- LLM 只能提出 proposal；application 產生 identity，deterministic verifier/reducer 決定是否合法。
- employee Evidence 與 reference knowledge 分離；reference candidate 不得冒充 employee Evidence。
- 新文件 authority 不可寫回 `DocumentVersion.content`、`_pending` 或 v1 `snapshot_json`。
- 不把 deployment ingress、登入、organization/member/ACL、quota、billing、tenant product behavior、Graph framework 或
  multi-agent runtime 塞進本 donor package。
- 下一個產品工程階段是 **R1 Task Discovery fixture／CLI 品質 gate**，不是直接掛 production route／Web。

## 歷史實作指路

本 package 的已完成 V0–V3-5A、R5、0010 persistence、question loop 與 provider 證據仍記在
[`README.md`](README.md) 及既有 `docs/plans/2026-07-16-*`～`2026-07-23-*` 文件；它們是歷史實作／donor 證據，
不能取代上列現行 authority。
