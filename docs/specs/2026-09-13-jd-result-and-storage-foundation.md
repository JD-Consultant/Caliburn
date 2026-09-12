# JD：真實結果契約與關聯資料庫基礎

- 日期：2026-09-13；Topic：JD-R002；RS-1／RS-2 局部施工成果。
- 承接[八個共同編輯操作](2026-09-13-jd-management-operations-slice.md)及[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。框架是可替換的工程選擇；六章內容與管理效果仍由[欄位充分性審核](2026-09-13-jd-field-sufficiency-audit.md)約束。
- 已完成輸出驗證、HTTP 投影、十三表固定 migration 與獨立 PostgreSQL 實測。**尚無完整 command 保存 service、讀取／ref、HTTP endpoint、App 畫面或自然模型流程。**沒有接正式產品，ADR0060／G6 不變；0 產品模型呼叫。

## 1. 這次實際完成什麼

1. 同一份標準 JSON Schema 生成 Python／TypeScript 結果。不能把 `candidate_ready` 或只有 `status=committed` 的物件當作已保存；`status`、效果、回執持久性、引用、錯誤與下一步須一致。
2. 已 binding 但結果未確認時先查回原操作；不因已證正文沒變就允許另發新操作。HTTP 區分「原寫入的結果」與「本次查回是否成功」。
3. 十三張 JD 表已用固定 Alembic migration 建入獨立 PostgreSQL 18.6。正文使用關聯欄位；JSONB 僅用於版本 snapshot 與操作 receipt。
4. 真 PG 驗證未分組任務、同文件外鍵、移動、D01 刪職責保留任務、共享 K/S 保護、來源目標、線性版本及操作結果約束；另在新 Python 程序讀回已提交的繁中／換行內容。

第 4 點是直接 SQL 的資料層實驗，**不是八個工具已經能保存**。測試 snapshot／receipt 使用標明 `DDL only` 的合成材料，未宣稱通過正式 snapshot／永久 receipt schema。完整交易、失敗恢復及差異 API 仍在下一單位。

## 2. 結果責任與輕量輸出

SSOT：[mutation result](../../experiments/jd-relational-app/contracts/jd-result.schema.json)；[HTTP Problem](../../experiments/jd-relational-app/contracts/jd-http.schema.json)。`MutationResult` 是具名 union；`ResultCatalog` 是生成入口，不是線上多包一層。

固定八個 keys：`status`、`effect`、`receipt_durability`、`operation_ref`、`result_revision_ref`、`change_ref`、`error`、`next_action`。文字／ref 有長度界線；錯誤碼與 status 相同；純候選與底層例外不能穿過此 adapter。

| 觀察 | 必須保持的含義 |
|---|---|
| committed／no_change | confirmed；有原 operation 及結果 revision；前者 changed 且有 change_ref，後者 unchanged 且 change_ref=null |
| 已確認語意／保存失敗 | unchanged／confirmed；原 operation 存在，沒有 result revision 或 change；依具名錯誤决定動作 |
| 已 binding、回執未確認 | 保留 operation；即使正文已證 unchanged 也一律 reconcile_operation；不能新 key 重做 |
| COMMIT 結果不明 | outcome_unknown／unknown／unconfirmed；不能宣稱失敗或成功 |
| admission 前拒絕 | unchanged／unconfirmed；三種 refs 均 null，不發明已持久 operation |

`operation_conflict` 的無 binding 指本次衝突意圖未被接納，不表示原操作不存在；原記錄不可覆寫。對結果 DTO 的驗證只查外形與一致性，**資料庫的真實觀察必須由 App 保存／對帳 owner 提供**，不能拿合成 fixture 當持久證明。

永久 receipt 保存穩定 identity／原結果語意，不保存會失效的外部 token。外部 refs 由原材料投影，result revision 不得偷換成最新 head。`actual_changes` 不放在輕量 mutation response；`change_ref` 供取得原 base/result 的完整確切差異。下一次修改須讀 current 取得適用的新 refs。這是本案取捨，兩家供應商均未指定這套 JD 結果欄位。責任與待驗證項目見[讀取與 refs 前置](evidence/2026-09-13-jd-read-reference-preflight.md)。

### HTTP 與模型外殼

`project_result` 不執行或重試寫入。成功結果回 200 JSON；已接納但待對帳回 202 JSON，帶原 operation_ref／reconcile 動作；確定拒絕依類型回 404／409／422／500 的 Problem。成功取得原觀察的 lookup 回 200，body 仍保留原成功／失敗／未確認結果；查不到或無法讀 receipt 的 host error 不能偽裝成已取得觀察。

Problem schema 限定四組合法 status／title／結果分支，禁止 success 或待對帳結果混進 Problem。`about:blank`、instance、detail 及 `jd_result` 擴充不取代 domain 狀態。對外都有 `Cache-Control: no-store`；沒有暗中加入 Retry-After／重播策略。

HTTP endpoint 尚未實作；正式接線必提供 operation 查回路由及其失敗外形，才能交付 202 的 status monitor。模型外殼保持 OpenAI call ID／Anthropic tool-use ID；Anthropic 依結果 `error` 設 `is_error`。

## 3. 官方依據與精確範圍

查閱日均為 2026-09-13。資料層精確版本、授權、API 限制及替代比較詳[DB 前置](evidence/2026-09-13-jd-relational-db-preflight.md)，工具／錯誤及安全紀錄沿[前次證據](evidence/2026-09-13-jd-app-boundaries-errors-logging-evidence.md)。

| 一手依據 | 支持範圍／本案映射 |
|---|---|
| [OpenAI function-calling results](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)，現行 Responses 指引 | 結果格式由 App 決定，回到原 call；JSON 是可用形式。未要求本案八 keys，也未公開 ChatGPT／Codex 的 JD 保存表。 |
| [Anthropic handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，現行 Claude API 指引 | tool result 與 tool-use 對應；工具失敗標記及可行動資訊。兩家的外殼不同，共同原則是明確結果與原呼叫相連。 |
| [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html)，2023 Proposed Standard，現行 | HTTP Problem Details 的標準外形及擴充；本案的四組狀態映射屬產品契約，不是 RFC 指定的 JD 錯誤碼。 |
| [RFC 9110 §15.3.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)，2022 Internet Standard，現行 | 202 不保證操作完成，回應應指出狀態查詢；本案待對帳映射要以原 operation 查回接點落實。 |
| [PG18 error codes](https://www.postgresql.org/docs/18/errcodes-appendix.html)、[PG18 CREATE TABLE](https://www.postgresql.org/docs/18/sql-createtable.html)、[官方 REL_18_STABLE ri_triggers.c](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/utils/adt/ri_triggers.c) | RESTRICT 與 FK 找不到目標有不同錯誤；實測 RESTRICT 回 23001，跨文件 FK 回 23503。後續 App 映射需同時核 SQLSTATE 與具名 constraint，不解析資料內容／本地化錯誤句。 |

套件採免費 OSS 穩定版：SQLAlchemy 2.0.52／Alembic 1.20.0（MIT）、Psycopg 3.3.5（LGPL-3.0-only）；只在新隔離 lock 安裝。標準 schema generator 使用已鎖 datamodel-code-generator 0.79.0 的 `--external-ref-mapping`、`--fail-on-multi-module-stdout`、`--no-allow-remote-refs`，沒有自製 ref resolver 或手改生成檔。

## 4. 真 PostgreSQL 環境與結果

- 隔離 Compose：`caliburn-jd-relational-test`；容器 `caliburn-jd-relational-test-postgres-1`；本機 `127.0.0.1:55436`。
- 只用固定合成資料庫 `caliburn_jd_relational_test` 與公开測試憑證；不讀產品 `.env`。既有 5432／55433 容器及 volume 未調整。
- 映像 `postgres:18.6-bookworm`，digest `sha256:1c59e2c3c818eaa0f0628f695b36e7c9e362d6b219b36a54a32df645cbd7e1af`；真 server_version_num=180006。
- PG18 新 volume 掛 `/var/lib/postgresql`；沒有挪用 PG16 data directory。
- 明示 initializer 核 database/user/version/既有表集合，才用 caller-owned transaction 執行固定 `20260913_0001`；13 JD 業務表＋1 `alembic_version` 技術表，20 個顯式 indexes（不含 PK／UNIQUE 自帶索引）。沒有日常啟動 migration 或清資料。

測試連線以 savepoint 保留預期約束錯誤後的外層交易；一般資料回滾。新程序回讀案例留下合成已提交文件作真 roundtrip 證據，不清空 volume。此 probe 已捕捉主程序所有 statements 的 `executemany=False`；這只能證明本次直接 SQL 路徑，未來 writer 仍須同樣驗證。

| 實際執行 | 結果與限制 |
|---|---|
| 完整離線 suite（補兩個 junction 反例前） | 404 PASS、20 真 PG opt-in cases SKIP；新增兩例隨後在真 PG 執行，不把 skip 算 PASS |
| 真 PG constraint／新程序回讀 | 22 PASS；不等於 command service、COMMIT 未知、程序死亡或恢復已通過 |
| metadata／固定 migration 離線 | 31 PASS，已含於 404；十三表／索引／constraint 比對，線上無明示 Connection 時拒絕 |
| 結果＋HTTP | 85 PASS，已含於 404；SSOT／published schema／strict DTO 三者一致 |
| 兩家 SDK wire | 16 tests，已含於 404；32 POST 被 MockTransport 攔截，0 provider requests；只使用合成結果 |
| 生成與型別 | `generate_contract.py --check`、TypeScript 檢查 PASS；未手改生成物 |

### 首敗與獨立審查

1. 結果 adapter 原 whitelist 的 12 項首測為 11 FAIL／1 PASS；補完整狀態驗證後通過，擴大為本次結果 tests。
2. generator 外部 root ref 曾造成 stdout 多 module 合併、Python import SyntaxError；native external mapping 需要具名 fragment。改具名 `$defs/MutationResult`＋catalog 入口，CLI 禁多 module stdout，生成相容後通過；未繞過外部 ref 解析。
3. 獨立審查發現 HTTP Problem 允許成功、未確認結果或錯誤 status 組合。首反例 22 FAIL／17 PASS；修成四個標準 schema 分支後 HTTP 39 PASS。其他生成檔雜湊未變，主代理再讀差異複核。
4. 真 PG 首次 16 PASS／4 FAIL：兩處測試錯把 RESTRICT 預期為 23503；兩處 fixture 同時違反多個 CHECK 卻指定其中一個。核官方原碼／錯誤碼後改正預期，將 fixture 收斂到單項反例；schema／migration 不變，20 PASS。
5. 獨立 schema／固定 migration 窄審 PASS；結果本體另有 840 組獨立置換比對 PASS。這些不擴稱 DB service 或模型品質驗收。
6. 獨立真 PG 測試審查指出原 `relation_scope` 案例只驗 task 外鍵。改名並補「同文件端點存在但無 junction」及「另一文件完整 junction」兩個負例，均由 `fk_jd_source_link_relation` 阻擋；22 PASS。觀察只宣稱 SQLAlchemy `executemany=False`，未把它等同直接量到驅動內部 pipeline。

## 5. 唯一下一施工單位

沿 RS-1／RS-2 把已完成的 domain 接上**一致讀取、永久 receipt 與同一保存交易**：完整 snapshot／receipt 型别、document→head 鎖序、候選 savepoint、原意圖 idempotency、COMMIT 未確認及 failure-only 查回。read refs／cursor 只做已定範圍接點；refs 簽章候選尚未採用。

之後才進同頁 CRUD／自動保存／改動呈現與顧問接線。不新增通用編輯、逆操作或 workspace 引擎；不再為同層框架品牌廣搜。成品仍按完整旅程／自然模型／員工使用驗收。
