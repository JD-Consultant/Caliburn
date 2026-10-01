# 聊天 HTTP 正式契約生成與驗證

查閱／實作日期：2026-09-13。基準：`2734b82b`。範圍限隔離 `experiments/jd-relational-app` 的 JSON Schema、標準生成及純契約測試；沒有執行 provider、資料庫、HTTP 或瀏覽器。

## 1. 已落實的接點

依[前置格式 §3](../jd-relational-chat-control/schema-preflight.md)與[契約策略](../../../contract-strategy.md)，新增 [jd-chat-http.schema.json](../../../../experiments/jd-relational-app/contracts/jd-chat-http.schema.json)，由現有固定版本標準生成器產出 [Python DTO](../../../../experiments/jd-relational-app/src/jd_relational/generated/chat_http.py)及 [TypeScript DTO](../../../../experiments/jd-relational-app/src/jd_relational/generated/jd-chat-http.ts)。沒有手改生成物、改舊工具 schema 或新增持久表。

| 根 DTO | 實際規則 |
|---|---|
| `ChatStartInput` | 僅 `run_id / text / expected_jd_revision_ref` 三個必填欄；原話逐字保存、不 trim 或正規化；非空非全白且無 NUL。route 文件與 dataset header 不重抄進 body。 |
| `ChatRunState` | 八個具名合法分支，分開 `run_status / input_state / jd_effects`；dataset、document、run 三個 UUID scope 與原 `write_state` 均必填。 |
| `ChatHistoryPage` | 每頁最多 50 則原生 ID 的公開訊息；有固定 anchor 與 nullable cursor。anchor 為 null 時只允許空訊息與 null cursor。 |
| `ChatMessage` | 只含 `message_id / run_id / role / text`；role 為 user／assistant。無時間戳、工具參數、工具結果、thinking、usage 或 provider JSON。 |
| `ChatProblem` | RFC 9457 七欄與封閉 code／next_action；HTTP 錯誤不宣稱原話、原 JD 已回滾或未保存。 |

`ChatRunState` 具名分支是 `ChatRunNotFound / ChatRunRunning / ChatRunClosing / ChatRunRecoveryRequired / ChatRunCompleted / ChatRunCancelled / ChatRunFailedSaved / ChatRunFailedNotSaved`。Python 的總 union 是原生 `RootModel`；`model_dump(mode="json")` 沒有額外 root wrapper。

- `not_found` 必須是 input unconfirmed、空 unconfirmed effects、無 response／stop。未找到不代表未保存或沒有在途請求。
- running／closing／recovery_required 的 `write_state` 直接 external-ref 原 `ManualBlockedState`；effects 只能 unconfirmed，仍可包括已確認 A 與未知 B。
- terminal 已存分支只能 settled，結果只允許既有 confirmed 回執；**failed＋已 committed JD 合法**。terminal／not_found 不要求目前文件可寫，因為另一回合、人工保存或封存仍可能阻擋。
- failed／not_saved 只能空 settled effects、null response。此形狀不創造「未存」證據；服務須沿原本地 attempt 的證明規則產生。
- `ChatBoundResult / ChatConfirmedResult` 只列 `jd-result.schema.json` 的 external refs，排除所有 Unbound。Python 生成物 import 原 results 類別，沒有平行定義或修改回執欄位。effects 最多 96 筆，超界必須失敗，不能截斷後宣稱 settled。

## 2. 首敗與最後驗證

先建立 [Python 契約測試](../../../../experiments/jd-relational-app/tests/test_chat_contract.py)，在 schema／生成物尚不存在時執行，保存的首敗為：

```text
ImportError: cannot import name 'chat_http' from 'jd_relational.generated'
1 error in 0.65s
```

生成後新契約 **90 passed in 4.61s**。再與被重用的 manual／catalog 契約一併窄跑：

```text
tests/test_chat_contract.py tests/test_manual_http_contract.py tests/test_catalog_contract.py
300 passed in 6.69s
```

每份案例同時核對 raw JSON Schema、generated Python 公布的 JSON Schema、strict model validation 與 JSON round trip。涵蓋八種 run 分支、缺／多欄位、UUID、原話、錯誤型別、三事實矛盾、全部 bound／unbound 回執類別、96／97 effects、50／51 messages、空歷史與 Problem。

[純 TS consumer](../../../../experiments/jd-relational-app/tests/chat_contract.consumer.ts)的正例與 `@ts-expect-error` 反例通過；首次因測試錯引既有名稱 `UnboundBusyResult` 出現 TS2305／TS2578，改用既有正式 `UnboundBusy` 後通過，未放寬契約。

```text
node node_modules/typescript/bin/tsc --project tsconfig.json --noEmit
PASS (exit 0)
node node_modules/typescript/bin/tsc --ignoreConfig --strict --noEmit --target ES2022 --module ESNext --moduleResolution bundler --types node tests/chat_contract.consumer.ts
PASS (exit 0)
python scripts/generate_contract.py --check
Contract generation matches: Python and TypeScript.
git diff --check -- <本輪指定檔案>
PASS (exit 0)
```

Python 指令在隔離目錄沿 `uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache`，pytest 加 `-q -p no:cacheprovider`；沒有網路安裝。生成器對舊生成物的內容 diff 為空。

## 3. 消費者責任與實際限制

- 現 `datamodel-code-generator 0.79.0 / Pydantic 2.13.5` 的既有 `Literal[bool]` 仍會接受相等的 0／1。raw schema 與 Python published schema 均拒絕數字；測試明列該限制。App 投影在 DTO 前必須核四個 `write_state` flag 的 `type(value) is bool`，不得冒稱 generated strict 已足夠。新 stop_requested 使用原生 `StrictBool`，數字與字串均拒。
- TypeScript 7.0.2 的靜態型別不是 wire validator。`json-schema-to-typescript 16.0.0` 保留字面分支、空 tuple 與必要欄位；UUID pattern、字串長度、非空原話與 50／96 上限仍由正式 schema／App 邊界驗證。TS external refs 由標準生成器展開為結構型別，Python 則 import 原類別。
- 原話 **128 KiB UTF-8** 與 HTTP **1 MiB** 位元組限制由服務／HTTP 接點實作。Schema 不拿字元 maxLength 代替位元組上限；長繁中文本契約正例不代表 HTTP 已接受該超界 request。
- Schema 只能拒矛盾形狀。actual Future 是否已停、完整原 Human 是否保存、terminal closure 與原 run 回執是否齊全、公開正文 ID 是否屬本輪、dataset scope／signed refs／cursor 是否有效，仍由 App 查真實保存後投影。`completed` 不表示 JD 專業內容已完整或滿分。
- HTTP／服務固定錯誤映射、歷史固定 snapshot 分頁與正文挑選由後續接線驗收。本次通過不代表真模型、真 PG、真程序或聊天畫面已通過。

本稿記錄前輪已研究方案的有界實作，不重開品牌廣搜；OpenAI／Anthropic 的來源與本案映射沿前置格式，不將本案 DTO 欄位宣稱為大廠指定契約。

## 4. 日常入口未啟用 AI 的明確出口

同日窄擴 `ChatProblem.code` 加入 `ai_unavailable`，沿既有 status 503／next_action stop，與可暫時恢復的 `service_unavailable` 分開。標準文案為「AI 訪談尚未啟用；請保留輸入。目前仍可查看原有對話及編輯 JD。」映射由 App 負責，契約不新增 capabilities 或設定權威。

新增合法分支測試先在原 schema 得到 **1 failed in 0.25s**（raw schema 拒 `ai_unavailable`）；更新來源並標準重生成後，聊天契約 **91 passed in 5.52s**。codegen 一致性、全部生成 TS 及含新 code 正例的 TS consumer 均通過。原 300 案是前段修改時的執行紀錄，這次只窄驗被修改的聊天契約，不冒稱重跑其他案例。沒有改 API、其他 runtime 或 provider 設定。
