# Interview vNext — eval-only provider adapters(V3-4)

**Status: mocked complete, live gate pending(2026-07-17)**

- mocked suite:`test_interview_vnext_openai_eval_adapter.py` + `test_interview_vnext_openai_live_probe.py`
  共 **66 passed, 0 skipped**;完整 API + PostgreSQL regression **614 passed, 0 skipped**。
- live gate(§16.5)**尚未執行**:本機只有 `OPENROUTER_API_KEY`,規格 §7.4 禁止以
  OpenAI-compatible relay 代打官方 endpoint。取得官方 `OPENAI_API_KEY` 後跑下方 live probe
  一次並人工檢查 bundle,才可宣稱 V3-4 完成。

本目錄是 ADR 0034 vNext 的 **eval-only** 邊界:驗證「官方 provider API 真實 shape 能否無損映射到
V2/V3 已發布的 provider-neutral contract(`app.interview_vnext.llm`)」。

- 權威規格:`docs/plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md`
  (上游研究:`docs/specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md`)。
- **production `apps/api/app/` 不得 import 本目錄**;dependency guard 測試強制。
- 這裡沒有品質評測:V3-4 只做 adapter conformance;12-case 品質/多 trial 是 V3-5。

## 檔案

| 檔案 | 責任 |
|---|---|
| `provider_config.py` | secret-free eval profile(model allowlist、reasoning、timeout)+ config hash;hard invariants(`store=false`、`sdk_max_retries=0`、`truncation=disabled` 等)以 `Literal` 鎖死 |
| `schema_catalog.py` | `output_schema_id + hash` → exact published portable schema 的封閉映射 |
| `providers/openai_responses.py` | `AsyncOpenAI.responses.create()` 的 request projection、response/error normalization、supporting artifacts |
| `live_probe.py` | opt-in 單次 live conformance probe + immutable Capture bundle |
| `probes/*.json` | synthetic test-only probe 輸入 |

## 不變量(摘錄;完整見規格 §1)

- `openai==2.46.0`、`max_retries=0`——一個 durable attempt 恰好一次 HTTP call;retry 決策屬 V3-3 executor。
- 送出的 schema 是 V3-2 published portable schema(hash 驗證),**不用** `responses.parse` 重生。
- `store/background/stream=false`、`truncation=disabled`;不送 conversation/tools/cache/sampling 參數。
- typed traversal 全部 `response.output` items;禁 `output[0]`、禁 `output_text` 串接。
- adapter 成功只到 `StructuredPayload`;完整 Pydantic/semantic 驗證仍在既有 executor。

## 驗收命令

```powershell
cd apps/api
uv run --locked pytest -q tests/test_interview_vnext_openai_eval_adapter.py tests/test_interview_vnext_openai_live_probe.py
```

Live probe(需 `OPENAI_API_KEY`;不進 CI secretless 測試):

```powershell
cd apps/api
$env:OPENAI_API_KEY='<secret>'
uv run python -m evals.interview_vnext.live_probe `
  --probe turn-interpret-smoke.v1 `
  --model gpt-5.6 `
  --accepted-resolved-model gpt-5.6 `
  --accepted-resolved-model gpt-5.6-sol `
  --reasoning-mode standard `
  --reasoning-effort medium `
  --output-dir ../../output/interview_vnext/live-probes
```

無 key:exit 2、不建 run、不打 network。輸出 bundle 已 gitignore(`output/`),不進 Git。
