# JD App：業務邊界、錯誤與本機紀錄的官方證據

- 查閱日：2026-09-13；Topic：JD-R002；供 RS-1 下一單位設計與獨立審查使用。
- 性質：有界研究與本案映射，非 Accepted ADR、正式接合或實作完成證明。
- 已讀基線：[目前決策](../../current-decisions.md)、[契約策略](../../contract-strategy.md)、[工具契約 §6–7](../2026-09-12-jd-relational-agent-tool-contract.md#6-統一-mutation-result)、[保存契約 §4.3／6.2／7](../2026-09-12-jd-relational-schema-and-write-contract.md#43-jd_operation)、[施工計畫](../../plans/2026-09-13-jd-relational-app-implementation.md)、[首切片範圍](../2026-09-13-jd-relational-command-slice.md)。
- 研究者僅新增本文件，程式由 root 單一寫入者修改；研究者另唯讀窄審 application／transport，執行一組記憶體 logging 故障注入及修正後 33 項窄測試。未改 schema／依賴，未呼叫模型或執行 DB／HTTP 產品測試。網路只查公開官方資料，沒有傳送私有程式或訪談。

## 1. 結論與適用範圍

保留一份共同 JD 業務規則與一份 application 結果，HTTP、模型工具及本機紀錄各自投影。Domain 判斷內容／關係是否有效；App 判斷原 operation 的實際效果與回執是否已確認；HTTP／provider adapter 負責傳輸；logs 協助定位故障。這四種責任不能靠共用一個 `status` 字串或通用 exception handler 混在一起。

此方向支持繼續純 CRUD，不需先建 observability 平台。建議第一個本機紀錄接點使用 Python 標準 `logging` 與有容量上限的本機 handler；OpenTelemetry 先借用穩定欄位語意，未採其 Python Logs SDK、Collector 或外送服務。精確結果 DTO、錯誤分類及 mapper 是 RS-1 的有界工程工作，不需再請 Owner 選框架 API。

## 2. 官方來源、版本、穩定性與授權

下表各頁均於 **2026-09-13** 讀取正文；「現行文件」不等於已做實際服務驗證。

| ID | 正式來源及適用版本 | 穩定性／授權／限制 |
|---|---|---|
| S1 | [AWS Prescriptive Guidance：Hexagonal architecture overview](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html) | 公開 `latest` 架構指引，非版本化套件或跨大廠共識；只引用依賴方向，未採 AWS 程式碼、Lambda、DynamoDB 或雲端服務，亦未由文件推定任何服務授權。 |
| S2 | [IETF RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html)，2023-07，取代 RFC 7807 | Internet Standards Track；BCP 78／IETF Trust 條款，抽取程式元件須保留 Revised BSD 條款。它規範 HTTP problem details，未規定 Caliburn 的保存狀態或重試政策。 |
| S3 | [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)，Responses function tool 的現行文件 | 本輪對照已鎖 `openai 3.13.0`；本地正式 artifact METADATA 核為 Apache-2.0。文件不是 API 費用／帳號權限授權，沒有 paid call；SDK 序列化也不證明模型會正確使用工具。 |
| S4 | [Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，Messages client tools 現行文件 | 對照已鎖 `anthropic 1.5.0`；本地正式 artifact METADATA 核為 MIT。只研究一般 client tools，不增 server tools、Tool Runner 或第二套 agent loop；SDK 授權不等於模型服務免費。 |
| S5 | [Python logging](https://docs.python.org/3.12/library/logging.html)、[logging.handlers](https://docs.python.org/3.12/library/logging.handlers.html) | 使用 Python 3.12 線的穩定標準 API；查閱頁顯示 3.12.14，首切片記錄 runtime 為 3.12.13，不據此升級。Python／文件為 [PSF License v2](https://docs.python.org/3.12/license.html)，文件範例另可用 0BSD；無額外 logging 套件。 |
| S6 | [OpenTelemetry spec 1.60.0](https://opentelemetry.io/docs/specs/otel/)、[Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)、[Python status](https://opentelemetry.io/docs/languages/python/) | Logs Data Model 標示 Stable；Python 主頁仍列 Logs 為 Development，不能把規格穩定性當成 Python SDK 同等承諾。規格 repo 為 [Apache-2.0](https://github.com/open-telemetry/opentelemetry-specification/)。本輪不鎖或安裝 OTel 套件，不宣稱 OTLP 相容。 |
| S7 | [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) | 持續更新的工程指引，無套件版號；頁尾標示 CC BY-SA 4.0。只取與單人本機 App 有關的事件、敏感資料、容量及故障原則，沒有新增登入／ACL、集中監控或法遵產品範圍。 |

OpenAI 的正文以官方 documentation search／fetch 取得；其餘以官方頁面讀取。SDK 授權／精確版本另以隔離環境 `openai-3.13.0.dist-info/METADATA`、`anthropic-1.5.0.dist-info/METADATA` 核對。上列文件未公開的內部實作不推測；本輪不因發現更新文件而更換已鎖依賴。

## 3. 十二條可直接用於設計的證據與映射

### BE-01：共同業務不依賴 HTTP 或 provider

**官方事實：**AWS 將 domain 放在核心，由 ports／adapters 隔離外部元件；資料庫、畫面、外部 API 不應決定 domain 的依賴方向。[S1](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)

**本案映射：**人與 AI 都先映為同一 command，再進同一候選／規則。Domain 不 import FastAPI、HTTPException、generated HTTP DTO、OpenAI／Anthropic SDK 或 logging handler。少數 Python 內部型別維持 shared module／Protocol，跨語言外形才按本案契約策略由 SSOT 生成；不為分層另建服務或通用框架。

### BE-02：已知業務拒絕與程式故障分開

**官方事實：**AWS 的隔離原則使不同入口可重用核心；RFC 9457 的人讀 `detail` 不宜由機器解析。[S1](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)、[S2 §3.1.4](https://www.rfc-editor.org/rfc/rfc9457.html#section-3.1.4)

**本案映射：**Domain 回具名 code 與已核 target metadata，例如 `target_missing`、`relationship_conflict`、`dependent_items`；不把全部業務拒絕壓成 `invalid_input`。傳輸解析失敗由 adapter 分類；未預期的程式／I/O 例外走 App 故障邊界，不能冒充「員工輸入錯誤」。員工文案與模型可採動作由固定表生成，不對 exception 字串做 substring 分支。

### BE-03：錯誤 code 不足以決定保存效果

**本案已定權責：**[工具 §6](../2026-09-12-jd-relational-agent-tool-contract.md#6-統一-mutation-result)分開 `effect` 與 `receipt_durability`；binding 前拒絕、已證 rollback 但回執未確認、COMMIT 未知是不同狀態。

**本案映射：**Domain 的「候選不合法」不自行產生 confirmed receipt。App 依 admission、DB／receipt 觀察補足結果；已 binding 但沒有確認 terminal 時，`reconcile_operation` 優先於重讀／修正／新寫。HTTP 500、SDK timeout、取消事件或某條成功 log 都不能獨自推出 rollback／committed。RFC 的 HTTP 格式不取代此領域契約。[S2 §4](https://www.rfc-editor.org/rfc/rfc9457.html#section-4)

### BE-04：Problem Details 是 HTTP 投影，不是另一個領域結果

**官方事實：**RFC 9457 定義 `type`、`title`、數值 `status`、`detail`、`instance` 及 extensions；若提供 `status`，須與實際 HTTP status 一致。它明說不取代既有 domain-specific 格式。[S2 §3–4](https://www.rfc-editor.org/rfc/rfc9457.html#section-3)

**本案映射：**若採 `application/problem+json`，用 typed extension 包裝同一份 JD result；不要把 JD 字串 `status='stale_view'` 平攤到 RFC 數值 `status`，也不要另算一遍 effect／durability。`instance` 可識別這次 HTTP 錯誤，不能取代 operation ID。精確 HTTP code／type URI 表由 RS-1 定稿，RFC 本身沒有指定本案每個 code 應回 409、422 或其他狀態；HTTP 寫入結果與「GET 成功查得先前失敗回執」也必須區分。

### BE-05：工具呼叫 ID 只負責回配

**官方事實：**OpenAI function output 引用 `call_id`；Anthropic `tool_result.tool_use_id` 引用對應 `tool_use.id`。[S3](https://developers.openai.com/api/docs/guides/function-calling)、[S4](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)

**本案映射：**App 分開持有 provider call ID、可信 `ai_run_id`、`operation_id` 與 HTTP request ID。回覆要配回原工具呼叫；重連／重新取得結果仍查同一 operation。不能以新 tool-call ID、新 request ID 或 log correlation ID 當作可重播寫入的授權；也不能把由模型輸入的字串當作可信 operation 歸屬。

### BE-06：模型錯誤外殼沿 provider，重試意圖沿 App

**官方事實：**OpenAI tool output 可傳包含 error code 的字串／JSON；Anthropic 以 `is_error=true` 表示工具執行錯誤，並建議提供可採取動作。Claude 的 tool results 須緊接對應工具訊息，且置於該 user content 的前部。[S3](https://developers.openai.com/api/docs/guides/function-calling)、[S4](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)

**本案映射：**從共同 typed result 映出 provider 外殼；`committed`／`no_change` 不標工具錯誤，具名拒絕／保存故障依明列狀態表標示，不只判 `status=='error'`。錯誤外殼不改 effect／durability。模型一次有據修正、run budget、未確認先對帳，均沿[本案 §7](../2026-09-12-jd-relational-agent-tool-contract.md#7-錯誤重讀與重試矩陣)，不是照抄供應商示例的重試次數。

### BE-07：logs 是診斷觀察，operation 是保存權威

**官方事實：**OWASP 要求 logging 故障不應阻止應用本身運作，並要求測試寫入／容量故障。[S7 Event collection／Verification](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html#event-collection)

**本案映射：**可記 `operation_bound`、`candidate_rejected`、`receipt_observed`、`reconciliation_required` 等觀察事件，但沒有任何 log event 能建立／覆寫[operation receipt](../2026-09-12-jd-relational-schema-and-write-contract.md#43-jd_operation)。缺 log 不代表未提交；有 log 不代表提交確認。回執與原 request digest 仍由原交易／對帳取得，不從檔案、timestamp 或模型文字重建。

### BE-08：只記足夠關聯故障的結構欄位

**官方事實：**OTel 模型區分 Timestamp、ObservedTimestamp、Severity、EventName、Attributes，以及可選 TraceId／SpanId；OWASP 建議事件保留 interaction identifier。[S6 Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)、[S7 Event attributes](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html#event-attributes)

**本案映射：**首版 allowlist 可為 `event_name`、UTC `timestamp`、`severity`、`component`、`app_version`、`process_instance_id`、`request_id`、已存在的 `document_id`／`operation_id`／`ai_run_id`／`provider_call_id`、`command_name`、`phase`、`error_code`、`effect`、`receipt_durability`、`next_action`、`duration_ms`，以及確認後才有的 base／result revision ID。沒有的身分留空，不臨時補造。JSON 欄位名是本案映射，未宣稱符合完整 OTel；不為記 log 而產 trace/span 系統。HTTP code 只在 HTTP 邊界記錄。

### BE-09：診斷欄位不接收訪談或金鑰

**官方事實：**OWASP 列出通常不應直接記錄的 access token、password、DB connection string、key、敏感個資與商業資訊，並要求處理 log injection。[S7 Data to exclude／Event collection](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html#data-to-exclude)

**本案映射：**一般 logs 不記原始問答、JD 正文、Memory／prompt、tool arguments／完整 tool result、HTTP body/header dump、provider response body、DSN 或環境設定。只用固定訊息模板＋allowlist metadata；原始訪談留既有 owner，依法獲授權的自然測試證據另沿 RS-6 資料／費用邊界，不能借 debug level 擴大收集。未知 opaque ref 也可能是模型提供的任意文字，先驗型別／長度，記拒絕類別而非照抄 token；`related_refs` 的對外安全投影與 log 投影分開核對。

### BE-10：使用標準 logging，但配置與例外資料需受控

**官方事實：**Python `logging` 有 named logger、`extra` 與 formatter；同時在子 logger／祖先裝 handler 可能重複輸出，祖先 logger 的 filter 不會重套於 propagated record。`exc_info` 會附例外資訊。[S5 logging](https://docs.python.org/3.12/library/logging.html)

**本案映射：**在 App 組裝入口集中配置；業務模組只發固定結構事件，或完全由 App 邊界記錄。不要把 request dict 傳入 `extra`；遮蔽須作用於實際送出 handler 的安全欄位，不只掛 root logger filter。可預期的解析／業務錯誤不直接 `logger.exception(error)`；未預期故障也需避免 raw exception chain／locals 回灌資料。這是小型配置及 mapper，不另造 logging 引擎。

### BE-11：規格穩定不等於每個語言實作穩定

**官方事實：**OTel 1.60.0 的 Logs Data Model 是 Stable；目前 Python 官方狀態表仍列 Logs 為 Development。[S6 規格](https://opentelemetry.io/docs/specs/otel/logs/data-model/)、[S6 Python](https://opentelemetry.io/docs/languages/python/)

**本案映射：**現階段保留標準 `logging` 接口及有界結構欄位；若未來確有跨程序 trace／外送需求，再核精確 SDK／exporter 版本與資料授權。此差異不阻擋 CRUD，也不構成採用雲端 collector 的理由。本輪沒有啟動 instrumentation、自動抓 HTTP payload 或設定外送 endpoint。

### BE-12：紀錄容量與故障處理不能改寫業務結果

**官方事實：**標準 `RotatingFileHandler` 需要非零 `maxBytes` 與 `backupCount` 才會輪替；OWASP要求測試 disk full、無寫入權與 logging runtime failure。[S5 handlers](https://docs.python.org/3.12/library/logging.handlers.html#rotatingfilehandler)、[S7 Verification](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html#verification)

**本案映射：**首版 handler 配置必須有明確容量／保留界線，使用本機非 Web 公開目錄；數值按本案取捨設定，不冒稱官方建議值。formatter／handler 故障不能把已確認 committed 改成 save_failed，也不能吞掉未知 operation；故障提示不能再遞迴呼叫同一壞 handler。程序停止後僅餘部分 logs 仍按原 operation 對帳，不將 flush 視為提交屏障。

## 4. 本輪實作收斂與獨立窄審

研究起點為首切片的 [domain.py](../../../experiments/jd-relational-app/src/jd_relational/domain.py)純候選與 [transport.py](../../../experiments/jd-relational-app/src/jd_relational/transport.py)輸入／SDK 外殼；`DomainError` 有 code／message／refs。root 在本輪新增 [application.py](../../../experiments/jd-relational-app/src/jd_relational/application.py)，用一次候選建構與標準 logging 接點分開記 prepared／rejected／failed。這不是 HTTP、DB、operation 保存、完整 logging 配置或正式 result DTO 完成宣稱。

1. **BEL-R01 的已知狀態外殼修正：**原 `is_error` 只判 `status=='error'`，首切片測試只用 `candidate_ready`／泛型 `error`。root 先加入十個具名 failure status 與未知 status 反例，回報 **11 FAIL**；再改明確 success／failure 白名單，未知 status 拒絕。研究者已讀修正及 [test_transport.py](../../../experiments/jd-relational-app/tests/test_transport.py)。這只閉合外殼旗標，未驗完整 result 欄位、effect／durability 組合或持久結果。
2. **BEL-R02 的標準 traceback 修正：**原 `model_command()` 對外只有 `invalid_input`，但保留驗證例外 cause。root 用短 synthetic sentinel 透過 Pydantic 驗證錯誤確認標準 traceback 會露出輸入，回報 **1 FAIL**；修正為 `raise TransportError(...) from None`。研究者已讀修正及對應 testcase。這閉合標準 traceback 的該路徑，不宣稱任意 debug dumper／所有宿主 handler 已安全。
3. **application 的已實作界線：**只記固定 event／message、UUID request ID、可信 context document ID、allowlisted command／outcome／error code 與耗時；不記 args、refs 或 exception object，不 retry。root 回報 application＋transport **30 tests 通過**；本段是實作者結果，獨立驗證另列下一項。
4. **窄審首敗與閉合 BEL-R04a：**研究者以 `uv --no-cache run --no-sync` 在記憶體替換 `LOG.log`，令它拋出 synthetic handler failure。候選成功被改成 RuntimeError；原 `DomainError('stale_view')` 也被 RuntimeError 蓋掉，`original DomainError preserved=False`。root 隨後在 `record()` 隔離診斷 Exception，不重試／不遞迴記錄。研究者已讀修正，並實跑 `tests/test_application.py`＋`tests/test_transport.py`，**33 passed**；prepared、DomainError、unexpected exception 三路的 logging 故障都保留原結果或原例外物件。此項 **CLOSED／窄審 PASS**，無新增 finding。這是純準備邊界，未證明 DB 提交／真檔案輪替／程序退出後效果。
5. 八個 CRUD 編輯操作的最後結果與結構／選區獨立審查由[本次切片](../2026-09-13-jd-management-operations-slice.md)保存，本研究未重審其全套業務；完整 read／HTTP／result DTO 仍依計畫承接，不把 `candidate_ready` 混入持久 mutation terminal。

獨立窄複核版本：`application.py` SHA-256 `27EDE799D4E84ABA39A43E4116F30C1A30C8F2DCDF5149F32B9858C7C0534451`；`transport.py` SHA-256 `F63816087B320025F2710A7059AE6B6061B747405B726205F7AE806431DA1CA9`。33 項最後結果不與 root 的先前 30 項加總，也不與首切片 128 項累計為新的完整產品驗收數。

## 5. 真正阻擋點與下一步

**其餘純 CRUD 可以續做，沒有等待 RFC 或 OTel 的阻擋點。**先沿同一 domain validator 補各具名業務效果及已定拒絕 code。下列是相依實作前需閉合的工程決定，不是新的 Owner 產品選擇：

| 工作單位 | 真正須閉合事項 | 有界驗證 |
|---|---|---|
| RS-1 結果／錯誤 SSOT | 定義已知 domain code、transport parse code、內部故障分類；完整 `status/effect/receipt_durability/next_action` 合法組合，區分 pre-binding 與未確認 binding | 正反結果 fixture；對同一 App 結果生成手動／模型投影，非法 confirmed／unknown 組合拒絕；無 DB 時不製造 confirmed receipt |
| RS-1 HTTP／provider mapper | RFC status 與 JD status 不撞名；HTTP method/context 對應表；兩家 call identity 與 error flag；不能由自由文字判 retry | 逐個正式 status、空／不明 call ID、一般查回結果與寫入拒絕；两家離線 wire shape。此段是格式驗證，不再執行 mutation |
| RS-1 logging 接口／RS-2 實際持久邊界 | 安全欄位 allowlist、例外 sanitization、單一配置、有限檔案容量；App 持有 operation identity，logs 不能新增 authority | synthetic 秘密／正文／CRLF 不出 log；formatter／handler 故障不改結果；真 DB commit／receipt 未知反例留 RS-2，不能以記憶體測試代證 |

停止研究條件已满足：上述主張有官方依據；剩餘是少數 mapper／契約／故障反例，無需再廣搜其他 logging 品牌、微服務架構或 agent framework。

## 6. 計畫大項尚未列成具體驗收的五個風險

以下補強 [RS-1／RS-2](../../plans/2026-09-13-jd-relational-app-implementation.md#3-切片順序與驗收)的既有責任，不另開產品範圍。

| ID | 具體失敗觸發 | 承接切片／最小驗收 |
|---|---|---|
| BEL-R01 | 正式 `stale_view`／`invalid_input` 被舊泛型 `status=='error'` 判斷包成 Anthropic 成功工具結果 | RS-1：本輪旗標白名單／未知值拒絕已修，首敗見 §4；完整 result mapper仍須保留 call ID、effect／durability 及有限 next action。依 BE-06。 |
| BEL-R02 | 顯示訊息已去敏，但 exception cause、Pydantic 驗證內容或未核 ref 經 handler 重新輸出原話／金鑰樣本 | RS-1：本輪標準 traceback sentinel路徑已修，首敗見 §4；宿主logging仍須驗 invalid JSON、DTO error、DomainError、未預期 exception 四條路與實際handler；不使用真人資料。依 BE-09／10。 |
| BEL-R03 | 把 JD 的字串 `status` 展開到 RFC 數值欄位，或 GET 回執查詢把原寫入拒絕誤作本次 HTTP 失敗 | RS-1 HTTP mapper：相同 domain result 在「寫入回覆／成功查回回執」兩情境的精確輸出；未知 extension可忽略但不得混淆機器 code。依 BE-04。 |
| BEL-R04 | DB 已提交／已確認回執後，最後一條 log 輪替失敗，被通用 except 轉成失敗並誘發新 operation | RS-1 純候選子例 BEL-R04a 已修且窄複核 CLOSED，見 §4；RS-2 仍須在回執已確認後注入 handler failure，結果維持原 confirmed；未確認者走原 key 對帳，不能因 log failure 重播。分清真 DB 證據。依 BE-03／07／12。 |
| BEL-R05 | 重複初始化 handler，或不同文件共用可變 log context，導致重複事件／錯文件 operation 歸屬 | RS-1 logging＋RS-2程序接線：同程序兩次初始化不重複輸出；交錯 A/B 請求各用自己的已核 IDs；新程序有不同 instance ID且不以時間推導 run。依 BE-05／08／10。 |

本文件未把「能查到更多資訊」當成採用理由；沒有新增第二份訪談、operation audit 表、永久事件庫或可變模型筆記。正式權責仍沿目前決策與 successor／G6。
