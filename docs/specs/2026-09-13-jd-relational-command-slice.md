# JD 關聯式 App：完整任務與一次更正切片

- 日期：2026-09-13；Topic：JD-R002；RS-1 第一個有界單位。
- 需求來源：[六章格式](2026-09-10-jd-format-review.md)、[完整 JD 欄位審核](2026-09-13-jd-field-sufficiency-audit.md)、[業務操作](2026-09-12-jd-business-operations-and-scope-design.md)、[模型工具](2026-09-12-jd-relational-agent-tool-contract.md)。
- 狀態：RS-1 首切片隔離實作／離線驗證完成；不是完整 RS-1、G4／G6 或成品通過。

後續八工具及共用 App 準備邊界見[第二單位](2026-09-13-jd-management-operations-slice.md)。本稿兩工具／128 項描述保留為 `5f92f29e` 的歷史證據，不代表目前整套驗收數。

## 1. 本次效果與停止邊界

先完成兩個可獨立驗證的效果：建立一項任務，連同多筆成果、多筆要求及既有共享知識技能；依新資訊一次修正正文、要求與引用，保留其他有效工作。員工入口及模型入口轉為同一業務輸入，使用同一驗證及候選建立方式。

`experiments/jd-relational-app` 是新隔離落點，不 import 正式產品或舊實驗業務。資料形狀對齊十三表的實體及關係；本次只建立**尚未保存的候選**，沒有 DB、revision 寫入、operation receipt、HTTP 服務或 App 畫面。輸入 snapshot 和 refs 是已驗讀取材料的合成 fixture，不是新通用文件格式、持久工作區或正式 ref 發配機制。

框架是可替換的實作選擇。Next、FastAPI、UI 元件與 Agent runtime 的取捨不得改變上述產品效果，也不要求先完成無相依的 UI 選型才驗證共同規則。RS-F 本單位只閉合契約生成及離線序列化所需依賴；RS-2 前仍須完成資料層／交易接點，RS-3 前完成畫面及暫存接點，RS-4 前完成顧問 runtime 接點。

## 2. 責任與資料流

1. JSON Schema 是這兩個工具輸入的唯一跨語言來源，生成 Python DTO 與 TypeScript 型別；不手改生成物。
2. 傳輸 adapter 檢查形狀並映入內部 command；domain 不 import DTO、SDK 或 UI。App 注入文件／base／refs／ID factory，模型不填 operation、revision 或資料表外鍵。
3. Domain 對原 snapshot 建立獨立候選，全部 refs 以同一 base 解譯、先核衝突，再驗最終欄位與關係；任何失敗不改原 snapshot。純候選不會假回「已保存」。
4. 保存層仍依[十三表與交易設計](2026-09-12-jd-relational-schema-and-write-contract.md)，後續才驗原子 COMMIT、重複操作、未知結果及重開。程序內未半改不等於 DB 原子性已證明。
5. 兩家官方 SDK 只在離線測試中以 MockTransport 捕捉序列化；固定 fake key、offline.invalid、關閉環境設定與重試。不發送真實訪談、不使用模型、不加入產品雙 provider 功能。

領域規則是 JD 的必要业务，不由一般框架自動提供。採標準驗證器、生成器與 SDK；不增造通用編輯、定位、交易或回退引擎。

## 3. 已查明的最小技術缺口

原契約已定來源綁定整筆內容，但 AI `basis_refs` 更新的合併規則及 canonical 欄位未唯一。反例：同次改 task.name 引用 A，再改 description 引用 B，不能讓最後一項蓋掉 A，也不能把來源 digest 算在中間版本。

本案收斂為：空陣列保留既有 links／basis；非空只新增或刷新明列來源，不刪未列者；同 target 多項更新按輸入順序穩定去重，全部以最終候選內容建立 basis。移除子項／解除關係會移除其 current links，不改掛其他項目。精確 canonical 欄位回写[來源表 §3.10](2026-09-12-jd-relational-schema-and-write-contract.md#310-jd_source_link)。這是本案來源語意的實作決定，不稱供應商統一格式；可讀性與 digest 匹配也不證明專業內容正確。

## 4. 現行工具與官方依據

以下於 2026-09-13 查阅；正式版均僅採於新隔離 lock，不升級正式產品。沒有以套件在舊環境已安裝作選擇理由。

| 能力 | 採用版本／授權 | 官方依據與適用限制 |
|---|---|---|
| Python DTO 生成 | datamodel-code-generator 0.79.0／MIT | [9/10 release](https://github.com/datamodel-code-generator/datamodel-code-generator/releases/tag/0.79.0)、[CLI](https://datamodel-code-generator.koxudaxi.dev/cli-reference/model-customization/)；使用 JSON Schema→Pydantic v2，不以 nullable 選項代替 required 語意 |
| TS 型別生成 | json-schema-to-typescript 16.0.0／MIT | [官方 repo](https://github.com/bcherny/json-schema-to-typescript)及 npm 正式 artifact；實際 package engines 為 >=16，不能用 master 的 >=22.19 冒充已發布契約。TS 型別不是 runtime 驗證 |
| Schema／DTO 驗證 | jsonschema 4.26.0、Pydantic 2.13.5／MIT | [Draft 2020-12 驗證](https://python-jsonschema.readthedocs.io/en/stable/validate/)、[Pydantic strict](https://docs.pydantic.dev/latest/concepts/strict_mode/)；正反 fixture 比較接受集合，不假定生成器完整保真 |
| OpenAI SDK | openai 3.13.0／Apache-2.0 | [9/10 release](https://github.com/openai/openai-python/releases/tag/v3.13.0)、[function calling](https://developers.openai.com/api/docs/guides/function-calling)；明示 strict，全部 object required／additionalProperties false，結果以 call_id 回配。App 仍驗業務約束 |
| Anthropic SDK | anthropic 1.5.0／MIT | [9/10 release](https://github.com/anthropics/anthropic-sdk-python/releases/tag/v1.5.0)、[strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)；tool schema 欄位名與結果 tool_use_id 依其正式契約，不照搬 OpenAI 外殼 |
| 離線傳輸 | httpx2 2.12.0／BSD-3-Clause | 兩家當前發布的 SDK 使用 httpx2；[官方 MockTransport](https://pydantic.dev/docs/httpx2/advanced/transports/)可攔截所有測試请求，不把舊 httpx.Client 傳入 |
| TS 生成物檢查 | TypeScript 7.0.2／Apache-2.0 | [官方下載](https://www.typescriptlang.org/download/)及本次 npm 正式 artifact；實際執行 strict／noEmit，不以生成完成代替型別檢查 |

本次 Node 24.19.0、Python 3.12.13；全部套件與間接依賴以隔離 lock 重現。SDK 能序列化只證明客戶端形狀，不證明服務端接受或模型能自然選對操作。工具描述取自專業方法及具名業務契約，不把數值上限／六種更正操作誤稱大廠共同設定。

文字拒絕 NUL，沒有偷偷替換字元；[PostgreSQL 現行字元型別](https://www.postgresql.org/docs/18/datatype-character.html)明示無法保存 code zero。UTF-8 無效 surrogate 同樣回輸入錯誤；64 KiB／1 MiB 上限仍是本案初始設定，不是 PostgreSQL 上限，也未因此改正式 DB 版本。

## 5. 通過與停止條件

- 正反 schema fixture 經标准 JSON Schema 與 generated DTO 接受集合一致；codegen 可重跑且無差異。
- 完整新任務的成果與要求數量可不同；K/S 共用不複製，無名稱但有敘述可保留；未知不自動補正文。
- 既有任務更正不破壞其他任務；name-only→description-only 按最終內容接受；同 anchor 新增保序。
- 任一錯文件、過時、錯 ref 類型、重複／相反命令、改刪衝突或超限整組拒絕，原資料不變。
- 人工與模型入口得到相同 command 及候選；兩家 SDK 離線请求根 object、strict、nullable、variant、context 隱藏及結果 identity 可查。
- 來源多欄合併、空 refs 保留、解除關係清來源、共享定義不刪均有反例。最後做獨立審查；有實作缺口就修正，不默默縮減已定效果。

固定 fixture 只驗保存前行為；自然訪談、專業真假、資料庫與員工可操作畫面分別留於相依切片。本單位一旦上述證據成立即停止擴大框架研究，接續剩餘具名業務及真 DB 前置。

## 6. 執行結果

實作與重現入口：[隔離核心 README](../../experiments/jd-relational-app/README.md)。root 最後執行 **128 passed in 2.82s**，codegen 比對 Python／TS 無差異，TypeScript 7.0.2 strict／noEmit 通過。

| 實測範圍 | 結果與限制 |
|---|---|
| 標準 schema vs generated DTO | 64 passed；包含每個 required key、null、六 variants、額外欄位與嚴格字串型別 |
| 共同 domain | 45 passed；完整新增、一次更正、最終欄位、錯引用全退、衝突、来源合併、共享引用、排序、上限與輸入資料不變 |
| 輸入／工具 adapter | 11 passed；人工／模型同 command、拒絕重複 JSON key、隱藏 App 欄位、provider 根 object 與結果 identity |
| 兩家真 SDK／離線傳輸 | 4 passed；兩工具各兩家、共 8 次 MockTransport POST，0 provider 呼叫／費用；不是模型品質驗證 |
| 完整共同操作流程 | 4 passed；三種入口得到相同候選；同名異義 K/S 只連指定 ref；A/B 月檢更正保留 A 缺陷修正及低頻工作；有效第一項＋過時第二項保持原稿 |

**首敗與修正保留：**契約生成器預設 StrEnum 令合法 kind/mode 字串在 Pydantic strict 被拒（3 failed／61 passed），改官方 `--enum-field-as-literal all` 後通過。SDK wire 首輪1 passed／3 failed：修訂工具描述誤為 tuple 及 Anthropic 新版本憑證探索碰到空環境；分別修成字串、僅在離線測試封住帳號探索。Domain 最初缺模組後，首輪行為4 failed／36 passed，修正 helper 參數與 detail kind 命名碰撞；稀疏排序追加反例2 failed／1 passed，修正來源／K/S 新增時保序正規化，不重排無新增的 idempotent link。

環境首敗另列：受限網路 npm 查詢被拒，改授權的公開套件下載；原全機 npm wrapper 選到較舊 Node，改以明確 Node24 執行；Windows 暫存 ACL 阻止產生器的暫存檔，改標準 CLI stdout；pytest 最後停用非必要 cache plugin。這些不是產品資料失敗，不以重試掩蓋。

**独立審查：**`contract_tooling_preflight` 審 root transport／來源與切片邊界；`jd_format_audit` 審正文、來源與 domain 保留／引用語意；domain 作者另安排獨立反例窄審。已見 finding 均修正，沒有未處理 P1/P2。最後新加共同流程由 root 執行並核確切 before／after，不把先前八項專業情境全稱模型已驗。

**下一單位：**沿 RS-1 完成其餘具名管理操作與讀取／HTTP／錯誤回執契約；並在 RS-2 前閉合 SQLAlchemy／Alembic／driver 的精確組合與十三表初始化／交易反例。RS-F 的畫面及 Agent 接點分別在相依施工前驗證，停止本單位的同層廣搜。當前沒有新資料表、正式 App 切換、真模型或員工試用證據。
