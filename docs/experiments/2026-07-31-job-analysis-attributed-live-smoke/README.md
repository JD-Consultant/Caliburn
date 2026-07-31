# Job Analysis attributed live smoke：環境診斷（未執行付費 run）

日期：2026-07-31
狀態：**preflight 停線；0 次 generation call、US$0 支出**
計畫：[2026-07-31 attributed live smoke plan](../../plans/2026-07-31-job-analysis-attributed-live-smoke-plan.md)
研究：[OpenRouter 歸因與最小 live smoke](../../specs/2026-07-31-job-analysis-openrouter-attribution-and-live-smoke-research.md)

## 1. 結論

三回合 live smoke **沒有執行**。付費前的 catalog preflight 依計畫 §Stop Conditions 停線：
設定的 `anthropic` endpoint 在執行當下不是 active。

```text
{"status": "stopped", "reason": "catalog preflight failed: endpoint status -2 is not the active value 0"}
```

因此本檔**不含任何模型品質、prompt、Task 邊界或路由歸因結論**——沒有 transcript 可讀。

## 2. 執行紀錄

| 項目 | 值 |
|---|---|
| commit | `760b2f1`（working tree clean） |
| 指令 | `uv run python scripts/job_analysis_live_smoke.py --max-generation-calls 0`（working directory `apps/api`） |
| generation calls | 0 |
| 支出 | US$0 |
| PostgreSQL migration | `0013 (head)` |
| 建立的文件 | 無（preflight 在建文件之前就停止） |
| raw capture | 無（未進入 run，未建立 output directory） |

離線 gates 在停線前已綠：`apps/api` 全部 `test_job_analysis_*` 386 passed（含真 PostgreSQL
三回合 vertical，transport 為 scripted）。

## 3. Catalog 觀測（2026-07-31T07:08:01Z，`GET /api/v1/models/anthropic/claude-opus-5/endpoints`）

| tag | provider_name | status | uptime 5m / 30m / 1d |
|---|---|---|---|
| `anthropic` | Anthropic | **-2** | 84.07 / 94.05 / 99.38 |
| `amazon-bedrock` | Amazon Bedrock | 0 | 100 / 100 / 98.30 |
| `amazon-bedrock/claude-on-aws` | Amazon Bedrock | 0 | 99.75 / 99.82 / 99.75 |
| `claude-on-aws` | Claude Platform on AWS | 0 | — / — / 99.27 |
| `azure/us-east-2` | Azure | 0 | — / — / 99.48 |
| `google-vertex/global` | Google | 0 | 100 / 100 / 99.82 |
| `google-vertex/europe` | Google | 0 | — / — / 99.86 |

未變動的事實：

- model ID `anthropic/claude-opus-5` 仍存在，`tag = anthropic` 仍唯一；
- 價格仍是每 token prompt `0.000005`／completion `0.000025`，與研究紀錄 §2 相同；
- 該 endpoint 仍宣稱支援 `max_tokens`、`reasoning`、`reasoning_effort`、`response_format`、
  `structured_outputs`，能力沒有縮減。

唯一改變的是 `status`：研究紀錄 §2 於同日稍早記為 `0`，執行當下為 `-2`。

## 4. 已知不確定

- **OpenRouter 未公開 `status` 的數值語意。** 官方 provider routing 與 API reference 頁面都沒有列出
  0／-1／-2 的定義。本 repo（以及 R1 preflight 與 `select_catalog_endpoint()`）一律把 `0` 當唯一
  active 值，非 0 就 fail closed；這是保守約定，不是官方對照表。
- 1 日 uptime 99.38% 而 5 分鐘 uptime 84.07%，且 `latency_last_30m`／`throughput_last_30m` 為 null，
  形狀像**當下的短期事件**而非永久下架。它可能自行恢復，也可能不會——本檔不預測。
- **產品現況未實測。** production adapter 是 `only: ["anthropic"]` ＋ `allow_fallbacks: false`，
  在同一時窗理論上會受同一個 endpoint 影響；但這一點沒有被真實請求驗證，不得寫成已知故障。

## 5. 下一步（需 owner 決定，皆未執行）

1. **等該 endpoint 回到 `status = 0` 後重跑同一支 CLI。** 不改任何設定，計畫其餘步驟原樣可用。
2. **改走另一個 active endpoint**（例如 `amazon-bedrock` 或 `azure/us-east-2`）。這會改變
   `job_analysis_provider`，屬於路由決策，須先確認該 endpoint 的 structured output strict 保證，
   不能因為「它現在是綠的」就換。
3. **接受 preflight 的 status 判準過嚴並放寬。** 只有在取得官方 `status` 語意後才值得討論；
   在那之前放寬等於在不知道落點健康度的情況下付費。

實作與判準未被否決：Task 1／Task 2 的 parser、budget、recording transport 與三回合 driver 已完成且測試綠，
恢復後不需重做。
