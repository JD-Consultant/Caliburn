# T14：全合成品質試例與離線指引契約（2026-09-30）

## 範圍與狀態

第一輪主線分派約 20 分鐘獨立切片，只新增 fixtures、tests 與本 evidence；主線正在真 Demo，不改 runtime、instructions、設定、schema 或既有測試。**未完成 T14／T16／T17，更不代表整個 Goal 完成。**該輪不 commit、不載入 key／env、不呼叫模型 API、不操作 DB。後續主線委派的指定合成 DB 唯讀品質審讀，獨立記於文末，不回填成第一輪已驗。

完整回讀本題的 [工作分析指南](../../../specs/2026-09-09-complete-work-analysis-guide.md)、[JD 寫作指南](../../../specs/2026-09-09-jd-field-and-writing-guide.md)、[訪談深度校準](../../../specs/2026-09-09-customized-jd-depth-and-interview-calibration.md)及[方法研究入口](../../../specs/2026-09-09-job-analysis-and-jd-content-research.md)，核對 T14、開發規範 §7、驗證層級與目前 A／B1／B2 instructions／組裝。歷史研究狀態不等於現行產品驗收；指南內容不因本切片改寫。

## 官方研究與採用

先用官方文件搜尋／網路搜尋，再取得 OpenAI、Anthropic 官方實頁；非只讀 snippet：

- [OpenAI Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)：任務特定案例與人工校準；本案不用單一自評或文字表面指標代替正確性。
- [Anthropic Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)：成果與軌跡分開、正反方向、可行且明確的測例，容許不同工具路徑。
- [Anthropic Define success criteria and build evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests)：具體多面向判準與邊界案例。小樣本不冒充大規模能力量測。

採既有 pytest＋JSON／Markdown，後續沿現有 runner、parent 與 domain workflows；沒有引入評測套件、API platform、judge agent、fallback validator 或通用評測引擎。官方原則與 Caliburn 內容判準的分界記在 rubric。

## 新增交付

| 檔案（repo root 起） | 作用 |
| --- | --- |
| `apps/api/tests/fixtures/job_analysis_quality/cases.json` | 9 個完整短合成情境，7 development＋2 holdout_candidate；正式舊問答／pending 當次原文／既有情境及草稿分開 |
| `apps/api/tests/fixtures/job_analysis_quality/oracles.json` | 評分者專用依據與 A／B1／B2 正反例、hard failures、可接受變體；不給模型 |
| `apps/api/tests/fixtures/job_analysis_quality/rubric.md` | 可見範圍、既有框架接線、逐項人工評分、失敗及未觀察狀態、後續 provider 邊界 |
| `apps/api/tests/unit/test_job_analysis_quality_fixtures.py` | 資料完整性、正式序號／speaker、種子沿既有契約、oracle 來源可定位、人工稿反例不變成 gold |
| `apps/api/tests/unit/test_role_prompt_contracts.py` | 實際三角色組裝到輪前 template、B JSON 範例沿既有 parser、canonical tools 權限 |

素材與使用入口：[rubric](../../../../apps/api/tests/fixtures/job_analysis_quality/rubric.md)。本輪只建立定向品質材料，沒新增正式業務 schema；例子中的 fixture 欄位不是產品格式。

### 主線回報轉成反例，而非先判現有產品錯誤

主線回報全合成真 A→B1→B2 已發布 snapshot `23deb276..`、F=4；訊息 2 月底「我先複點」，訊息 4 每日請現場複點。每日任務或 shared collaborator 描述若無範圍地寫成本人不複點，可能反向污染月底責任。

新增 `daily_vs_month_end_recount_scope`：同時檢查局部任務、共用協作對象正文／關係及整體邊界，要求每日與月底各自的本人行動成立。**第一輪建立 fixture 時未查該 snapshot／DB，當時是轉述風險與合成測例，不是獨立重現的 production finding。**沒有因此改 prompt；後續唯讀核對見文末。

## 驗證層級與結果

本輪是資料與現行契約 characterization，沒有產品行為修改，所以不表演產品 Red→Green，也不將 authored 正反例當模型已失敗／已修復。第一組 8 例＋prompt 契約 **23 passed**；加入跨情境案例與實際三角色 template 接線檢查後 **28 passed（1.68s）**。

離線命令（cwd `S:/caliburn/apps/api`）：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py -q -p no:cacheprovider --tb=short
```

加入既有 A／B 工具路由及 import boundary 的相關回歸後，**65 passed（最後重跑 2.11s）**；兩個新增 Python 檔 Ruff 檢查／格式檢查通過。11 個本地文件連結有效，三份 instructions 的原始檔案 hash 交付前再核與下方一致。完整聚焦命令：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py tests/unit/test_memory_analysis_tools.py tests/unit/test_consultant_tools.py tests/unit/test_import_boundaries.py -q -p no:cacheprovider --tb=short
./.venv-target/Scripts/python.exe -B -m ruff check tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py
./.venv-target/Scripts/python.exe -B -m ruff format --check tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py
```

組裝測試只替換 DB／history I/O 邊界，執行實際角色 runner 到 history template 即停止；沒有 provider／count／compact 或持久化。它能發現接錯角色指引或範例不符 parser，**不能判自然語意是否被遵守**。資料 integrity 測試只驗來源定位及材料可用性，不是引用語意 validator。

已閱讀的 instructions 原始檔案 SHA-256（此切片不修改）：

- A：`0e8df44181877adf6688640524d5db09a480941e297fd623ee9c3da67124bdd0`
- B1：`159ea1f626bd3f48b8a05f4eadb431665c971fa61931aa081c655ac9d3853cc3`
- B2：`761d62d03f89eefd7a8ee1c05395e9b8a8f654f1630aed03c2b5ed6859fe5f37`

原始檔案 hash 只是本次讀取定位；後續 provider 評測另記實際組裝 instructions／tools／context 的 fingerprint，不能用檔案 hash 冒充已外送內容。

## 尚未判定／下一個有界步驟

- **人工 rubric 可靠性未驗：**工程代理草擬的 oracle 還需獨立領域人工審查與分歧校準；不冒稱專家共識。
- **真 provider 品質未跑：**既有真 Demo 成功與 T10 count 接受都不能替這九例評分；T16 另寫有界 manifest 後用同版材料及既有框架跑，保存完整失敗而非挑成功。
- **保留例非盲測：**兩例未用於調 prompt，但不是編寫者未見；若後續用於調整，就移出保留集並補新例。
- **長訪談、引用語意、context／成本及品質分布未驗：**繼續原 T16／T17 gates；V25 真人耗時／ROI 沒有新資料，不能宣稱節省。
- **現有 instructions 是否足以穩定處理跨情境責任仍未知：**不因關鍵詞存在、parser 接受或 28 個離線測試通過而下結論。

最小下一步先由人工檢查 oracle 是否公平可解，再鎖定版本，在既有授權下分批進 T16。這份 evidence 不新增外送授權、不降低原 Goal／T01–T18 完成條件，也不要求改成固定問卷、固定工具序列或全稿審核 Agent。

## 第二輪：既有真模型合成產物唯讀審讀（2026-09-30）

### 授權、固定樣本與方法

主線委派限時唯讀複核，依上述 guides／rubric 審讀指定合成 Demo 的既有輸出，只更新本 evidence；**0 新 model／count／compact／judge API、0 DB 寫入、不讀 env／key、不改 prompt／runtime、不 commit**。這是工程代理逐條審讀並提出候選評分，不冒充人類領域專家已簽認，也不是生成模型自報合格；rubric 的獨立人類校準仍待進行。

讀取時間約 11:17–11:20（Asia/Taipei）。先讀實際 persistence／read models，使用現有 `list_formal_interviews`、`read_snapshot_map`／`read_snapshot_object`、`read_revision`、`read_work_at`、`read_source_references`。連線明選 `caliburn_target_demo`（loopback `127.0.0.1:55439`），catalog 確認 schema `caliburn`；服務端 `default_transaction_read_only=on`、`statement_timeout=5000`，隔離 `REPEATABLE READ`，session 關閉前 rollback。沒有啟動 App、執行 migration、pytest fixture 或重跑訪談。

- Job：`b6e76e87-817c-4c9e-8c82-3564b329c7f2`。
- 正式訪談：`formal_interviews` join `interview_texts`，序號 **1–5**（App 開場、員工、A、員工、A）。本次只評前兩個成功 A Turn。
- 固定 Memory：snapshot `23deb276-1e4d-44b0-b72a-018871cbb71f`，position `27fea144-27c7-4a3a-9e54-12a93effce62`，**F=4**。不包含 A 第 5 則是正確的固定上界，不是漏處理。
- 固定 JD：revision `1d17ce47-ca32-4efa-9b2e-3afad693c15c`。第一次取得 formal head 後第二次核對仍相同；後續不再追讀 current head。
- 主線後續通知第三輪 execution `a9850a7e-bcd1-4673-96ef-0ece3202568f` 暫停後繼續；**該輪及其更正全部排除**，不拿新資料回判舊 snapshot，也不把新候選混入此評分。

實際查詢成功 exit 0，確認 `('caliburn_target_demo', 'caliburn', 'on', 'repeatable read')`。同一固定樣本有 **2 B1、1 B2；JD 1 area、2 tasks、8 details、2 capabilities、2 task-capability links、1 collaborator、0 conditions、20 direct sources**。20 條 JD 來源全指正式員工原話：序號 2／4 各 10 條，`needs_review=false`；此旗標不替語意正確性背書。另核對 B2 的兩個情境引用與 snapshot 選定修訂一致、無直接訪談引用；B1 引用均位於 F 內。

核對用 canonical JSON（keys `interviews/snapshot/memory/profile/work/sources`，dataclass 展開、UUID 字串、集合依字串排序，`ensure_ascii=False, sort_keys=True, separators=(',', ':')`，UTF-8）SHA-256：`fd8fc088f05ed3cfca9be258847d2adb260d71d5a9448ee2faa05457e5d4c808`。這是本次讀取投影 fingerprint，不是 provider request 或私人 trace 的 hash。初次診斷腳本遇 Windows Proactor 不相容、另一次漏載 ORM `job_files` metadata；只修臨時讀取腳本的 Selector loop／model imports 後成功，未改產品。

### 可重現定位與語意核對

| 代號 | 固定物件／來源 | 本次核對的內容 |
| --- | --- | --- |
| I2 | interview 2，source `79a66fca-8b85-4d46-a636-517e303fa595` | 「我是營運部的庫存管理專員，向倉儲主管報告」；月底「有差異時我會先複點，再查當月入出庫單據」 |
| I4 | interview 4，source `04cbce28-3f82-413c-80a6-fcd699d4335c` | 每日「再請現場複點」；「現場同事負責實際搬貨和複點，我負責查核與追蹤，不負責搬貨」 |
| S月 | B1 object `e240ca3e-2aea-45c3-a732-f348dfb45ccf`，revision `a61682eb-1ba5-4c2a-b610-dab84036c9c9` | 「月底庫存盤點與差異證據整理」，引用 I2；本人行動第 3 點仍是差異先複點 |
| S日 | B1 object `d11382a2-ee1f-4926-8f81-7bb299b4e8c6`，revision `800c9445-7f5f-4a3a-9c38-e82b28511edd` | 「每日庫存異常查核與追蹤」，引用 I4；請現場複點、本人查核追蹤，保留當天交主管條件 |
| U | B2 object `aa8b2106-b163-4386-b637-f441ac76ce01`，revision `ad6a822a-f3d1-4b32-9ae4-230f191a3e2c` | 「庫存核對、異常追蹤與差異證據整理」，引用 S月／S日；分開每日及每月段落 |
| J月 | task `6e17dea9-f97b-40b7-93c6-181aaf8dbfc4`，detail `791f71e4-27af-45fc-bf1b-1aae8849a5c1` | 「發現差異時先複點，再查核當月入庫及出庫單據」；引用 I2 |
| J日 | task `78bf9988-745d-4005-b01e-4b67285e0144`，detail `74f0a163-c9b9-41b4-a00a-9442f5d6f0f9` | 每日任務下「本人負責查核與追蹤，不負責搬貨或複點實物」；引用 I4 |
| J協 | collaborator `e3394ed1-f7c2-4ab3-9ff4-80f70a9de1e5`，content revision `824e680f-485a-4dc3-97cd-1aea4046ca79` | 「倉管同事通報帳物不符；現場同事負責實物複點及搬貨，庫存管理專員負責查核與追蹤」；引用 I4 |

**G1／partial：B1 未承接職務背景，但 B2 不是捏造。**U 第一段寫「本人是營運部庫存管理專員，向倉儲主管報告」，I2 完整支持；U→S月→I2 可回查，所以不報錯來源／無據職稱。實際讀完兩份 B1 的 title、description、body，職稱與單位沒有語意等價敘述；S日「交倉儲主管決定」支持異常交接，不等同正式匯報關係。這是**情境正文的已知背景涵蓋缺口**，不是非逐字重複，也不是資料遺失或 schema 非法。只按 B1 情境導覽／正文理解角色的人需多下查一次原話。可操作改善方向：在適當既有情境保留簡短職務背景並沿 I2 引用；不必每情境重抄、不造新 profile 層、不讓 B2 代改 B1，也不要求為每項摘要差異固定回交。

**G2／partial：共用協作文字需要明示每日適用範圍；沒有重現月底責任被刪除。**J月、S月、U 的每月段落都保留本人複點；J日位於每日任務，且 I4 明說每日請現場複點，這項局部摘要可成立。J協 則獨立列於職務共用協作資料，未寫「每日異常追蹤時」，也沒有 task-collaborator 關係替它限定範圍（現有 work model 只有 task-capability links）。A 第 5 則雖從每日工作開始，後接「您不負責搬貨、複點或核准改帳的界線」也省略該範圍。兩處都有讀成全職位分工的風險，但沒有明說「月底不複點」，因此**不把可能誤讀升為已確認跨情境責任覆寫／hard fail**。可操作改善：共用協作與對話摘要明說這是每日異常的分工，月底本人複點仍成立；不是把 J日 的正確局部文字一律刪掉。

**正面對照／不是缺口：**「查核入出庫紀錄、試算表篩選比對」在 I4 有據，JD K／S 及其每日任務連結對應正確；不因不是逐字原文而扣分。月底「每月最後一個工作日」、每日短少／查不清「當天」交主管、無核准權、非採購／補貨決策均未消失。U 保留兩種觸發、本人與現場／主管分工、兩種表單用途及必要未知，不是只剩通用職業句；必要重述不是自動冗長失敗。

### Rubric 候選評分（不取平均）

| 維度 | 結果 | 可觀察理由及邊界 |
| --- | --- | --- |
| 事實與更正 | pass（已觀察事實）；更正 not_observed | 職稱、單位、匯報關係、任務與方法能對到 I2／I4；兩者是不同條件的補充，不先當矛盾。第三輪更正未納入。 |
| 責任與條件 | partial | B1／B2 及兩項局部 JD 保留日／月差別；共用措辭有 G2 範圍歧義。 |
| 未知及訪談廣度 | pass（本樣本） | B1／B2 明說結案標準、後續處理等未確認；U 用「目前已知主要工作」，A 第 5 則繼續問其他工作，未宣稱全職位完成。員工反覆答不出來的處理未觀察。 |
| 有效工作保留 | pass（兩項已知工作）；低頻壓力 not_observed | 新增每日工作後月底仍在三層；本樣本沒有已提供的低頻高影響事件，不能因 A 有問低頻就宣稱該 gate 通過。 |
| 內容粒度／高訊號 | pass（本樣本），另記 minor | 可辨觸發、查核／判斷、產物、交接與權限；K／S 連到實際用途。未知中的表格格式／欄位不是當前最優先訪談目標，不要求現在補齊。 |
| 引用與實際效果 | partial（涵蓋）；固定鏈／保存 pass | 20 條 JD 正式原話引用及 U→S→I 固定鏈可解析，JD／snapshot 實際存在，不只是口頭「已改」；G1 是 B1 正文涵蓋，不把引用可下查當作所有層都已完整。 |
| A 引導 | pass（已觀察問句） | 第 3 則追問已提但未說明的每日異常觸發、本人處理與去向；第 5 則問其他工作／低頻例子及觸發，不重問已知職稱、不誘導固定期限、不宣稱完成。G2 摘要措辭另計。 |
| B1／B2 分工 | 產物結構 pass；執行權限 not_observed | 已發布物件的 owner／來源層符合分責；本次未讀完整工具軌跡，不能僅靠結果宣稱 B1 沒看理解、或驗證每次回交／compaction。 |

**整體：partial，0 已確認 rubric hard failure；不是品質全面通過。**G1／G2 是可定位且可改善的局部缺口；現有樣本不足以將其升為 P1／P2 的確定責任覆寫、捏造或引用破壞。這也不表示一筆成功樣本能證明一般模型可靠。

Minor：J日 outcome `8c646862-35ac-4afa-aefc-00118a10ffbd` 的「實物短少或原因無法查清時，於當天交倉儲主管決定」兼有交接效果與條件／期限；按 JD 指南 §4，後續可把條件／當天時限在 requirement 表達得更清楚。原話有據、文字未遺失，不因此判錯責任或要求此刻為排版重寫整項工作。

### Declined to judge／未判定

- 不判第三輪更正及新候選、新 snapshot、恢復／暫停是否成功：主線明確要求固定前兩輪，且本輪只審內容。
- 不判九個品質 fixtures 已通、無主語／人工稿／10%案例／低頻保存等全套品質、長訪談穩定性與 provider 成功率：本樣本只有兩次資訊相當完整的合成員工回答。
- 不判「內容不足時 A 一定會正確引導」：看到了從局部資訊追問每日工作及擴展廣度，沒看到持續含糊、答不出來或不確定的員工回應。
- 不判所有下層事實都必須在每個上層逐字重現、不要求 B1／B2 一案一物件；語意等價、合理分組與必要重述均可接受。
- 不判 B2 是否曾真正讀過某則原話／何時決定不回交、私人推理、完整工具權限與成本：未開讀執行 trace／budget；保存內容有據不等於這些執行 gate 已驗。
- 不把工程候選評分當獨立領域人審共識。下一步先由 Owner／第二位評者核對 G1／G2 的重要性，再決定是否調整指引及跑有界對照；本次沒有修 prompt，也沒有新增自動 validator、judge、保存 owner 或互審關卡。

本輪只更新本文件。三份 instructions hash 仍與第一輪記錄相同；本地連結、行尾空白及檔尾換行檢查通過。沒有因追加審讀紀錄重跑 provider 或整套測試。

## 第三輪：G1 的 B1 背景取捨澄清與離線對照

主線委派的離線窄切片；可等價調整 B1 指引，不另增 Owner 核准關卡。只改 B1 instructions、對應 fixtures／tests／本 evidence；A／B2 instructions、runner、tools、runtime 不動。已在交接 commentary 明示此範圍；可用工具未提供其他並行角色的直接訊息通道，不宣稱已逐一送達。**沒有模型 API／count／compact／judge、DB、env／key 或 commit。**官方文件搜尋／讀取不外送職務樣本。

### 審核結論與最小改法

G1 的原結論維持：職稱等有 I2 原話支持，固定引用鏈正常，缺的是 B1 正文背景承接，不是幻覺。單一產物不足以證明根因完全是 prompt，也不能證明加提示一定改善；但現有 B1 雖要求保存責任、適用條件與有助理解的細節，未明說操作步驟之外的**角色／服務範圍背景如何保留，以及共用背景如何避免每案重抄**。本輪選擇三句一般化澄清，保留原角色與工具責任。

依[工作分析指南 §9](../../../specs/2026-09-09-complete-work-analysis-guide.md#9-工作理解正文要寫到多清楚2026-09-25-研究補核對)的反事實省略檢查，只有省略會影響辨認工作／責任／條件的背景才需承接；§9 原本是理解正文取捨，**不將其偷換成 B1 每案必填 profile**。另依同指南 §2／4 的職務定位與情境脈絡責任，補入 B1 選材原則；不把整篇指南塞進提示。

`agents/work_situation_analyst/instructions.py` 在原本的情境保存原則後只加三句：

> 在相關情境正文保留有助辨認本人角色、服務範圍或責任界線的已知工作背景，不只留下操作步驟。
> 共用背景不必每案重複完整職務資料；放在適當情境並保留來源，各情境仍須清楚交代影響解讀的局部條件。
> 未說明的背景仍是未知，不為填滿職務資料而補造，也不從職稱推定分工。

否決兩端：完全不澄清會繼續依靠籠統的「有助理解」自行選材；硬訂職稱／單位／匯報必填欄、每案複製 profile 或新增背景層，會放大重複及補造風險。本次不要求固定物件數、固定回交、來源數量門檻或額外 validator。庫存 Demo 的詞句、ID、職稱與單位沒有進 production prompt。

### 官方查證及本案取捨

2026-09-30 先查官方搜尋，再取得實頁：

- [OpenAI Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering#version-prompts-in-code)建議在程式中管理提示，修改前準備代表性 fixtures、測試及 eval。本次沿既有 instructions 模組與 pytest，不另建提示平台；明確目標與限制是提示方法，不是品質保證。
- [OpenAI Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)區分指令遵循、產物正確性與工具行為，包含邊界案例及人工校準。本次將離線組裝契約與待模型／人工評測分開，不用關鍵字測試或單一 judge 宣告品質改善。
- 以現有設定的 `gpt-6-luna` 精確搜尋並讀[GPT-6 的 API／模型參數指引](https://developers.openai.com/api/docs/guides/latest-model#gpt-6-astra-update-api-and-model-parameters)，未替換型號、調 reasoning 或改傳輸。沒有取得「此三句已改善 Luna 的 G1」的官方或實測保證，也不把 Astra 的表現推給 Luna。

### Fixtures v2 與 TDD 證據

既有格式沿用，`cases.json`／`oracles.json` 版本增為 2；增加兩個 development 案例，合計 **11 例＝9 development＋2 holdout_candidate**。原九例內容與兩個保留候選未改，仍不宣稱盲測。

- `shared_work_background_is_not_per_case_profile`：課程行政的單位、角色、匯報及成人課程範圍只在較早原話說一次，舊 seed 刻意僅保留動作。允許在適當情境承接共用背景、各案清楚限定，不要求每案 profile；單純正文缺背景仍判 partial，無據擴成兒童課程／決定開課才是 hard failure。
- `unconfirmed_background_is_not_a_profile_blank`：設備支援的稱呼不等於正式職稱，工作交接不等於匯報關係。已知北館報修接收／回覆保留，未確認單位與職稱不靠常識補齊；這是防止新提示被誤解成必填表的反方向。

先改 fixture coverage／對照檢查及實際 role assembly 的 B1 輸入契約，再跑：**3 failed、26 passed（1.62s）**。其中兩項是尚缺新材料的 coverage guard，另項是在真 `WorkSituationAnalystRunner` 產生的 history template payload 中，確實缺少本次三項取捨提示。不是 import／依賴錯誤，不把缺 fixture 的失敗冒充自然模型失敗。

再新增材料與三句指引，原命令 **33 passed（1.44s）**；加既有工具權限、路由與 import boundary，**70 passed（1.65s）**。三個受影響 Python 檔 Ruff check／format check 通過。組裝測試停在既有 history I/O 邊界；驗的是實際送入準備流程的提示契約、而非原始檔案 grep，但仍不能驗模型是否理解／遵守。文字契約若未來等價改寫，須隨審查更新；不把中文完全相同當成唯一正確行為。

命令（cwd `S:/caliburn/apps/api`）：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py -q -p no:cacheprovider --tb=short
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py tests/unit/test_memory_analysis_tools.py tests/unit/test_consultant_tools.py tests/unit/test_import_boundaries.py -q -p no:cacheprovider --tb=short
./.venv-target/Scripts/python.exe -B -m ruff check src/caliburn/agents/work_situation_analyst/instructions.py tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py
./.venv-target/Scripts/python.exe -B -m ruff format --check src/caliburn/agents/work_situation_analyst/instructions.py tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py
```

B1 檔案 SHA-256：`159ea1f626bd3f48b8a05f4eadb431665c971fa61931aa081c655ac9d3853cc3` → `a0a36a70a778fe7f23c8a386226f2501a4ac4f760c1edb33c1d39b7d48ca298c`。A／B2 hash 維持第一輪值。本次品質提升、成本／長度變化及普遍穩定性**未驗**；不追加 provider，不把離線 Red→Green 宣稱 G1 已被真模型修復。依開發規範 §3.1，本次跑受影響離線回歸，不藉窄 prompt 變更重跑 PG／全產品 gate。

### G2 後續證據只路由，不改寫原審核

主線已在 [T08 §5.4](t08-consultant-turn.md)記錄 A3 接到新的明確更正後，自然修訂每日分工適用範圍。這是後續新輸入與新輸出的證據，不是本代理重跑，也不使用本次 B1 新提示證明 A3 的改善。第二輪固定前兩 A／snapshot `23deb276…`／JD `1d17ce47…` 的 G2 partial 保留原判；不回填成當時已修好。

**交付界線：**本輪等價澄清已落檔，未增加核准關卡；T14 正式完成 gate、G1 的後續模型對照與獨立人工校準由主線整合評估。原 T01–T18 與 Goal 保證不縮減。

## 第四輪：指定第二版 Memory／更正後 JD 的唯讀品質審讀

2026-09-30 主線分派的八分鐘有界審查；實際 DB 讀取於 11:47–11:48（Asia/Taipei）。沿本文件指南及 fixtures rubric v2，僅檢查全合成 job `b6e76e87-817c-4c9e-8c82-3564b329c7f2`、指定快照及正式訊息 1–7。**沒有讀 env／key、寫 DB、呼叫模型、修改 code 或 commit。**本輪不重跑舊批次，不改寫第二輪固定產物的判分。

### 固定 revision 與來源

- Memory snapshot `08e75187-9ad6-477e-9f85-d2cefc779663`；position `44fce8ed-9220-4c2d-95d4-2c4e16efbfbb`；F=6，截止來源 `c56f9247-b4c3-4efe-a456-0f85b6d6a315`。訊息 7 僅作 A 公開答覆審讀，沒有將它算進此 Memory 的輸入邊界。
- 同一 repeatable-read 交易先固定正式 JD head，再讀其內容：`c7e29da3-a9cc-43ec-aac4-fd08091b8346`；不是 candidate。1 area、2 tasks、9 details、2 capabilities、2 links、1 collaborator、0 conditions。
- 月底情境：object `e240ca3e-2aea-45c3-a732-f348dfb45ccf`，revision `0c77e700-32b3-4a48-9460-cd0ef15df78a`，來源 I2／I6。
- 每日情境：object `d11382a2-ee1f-4926-8f81-7bb299b4e8c6`，revision `df5cf2a9-a2d5-4397-be08-947a1aad84c7`，來源 I4／I6。
- 工作理解：object `aa8b2106-b163-4386-b637-f441ac76ce01`，revision `70982659-409c-4f57-8d9d-231b8c16121f`；兩條情境引用均選用上述修訂。
- I6 原話明確區分「每日異常的實物複點由現場同事做」與「月底盤點發現差異時，是我自己先複點」；並補充每日結案條件與不負責核准。I2／I4 的原來源身分沿第二輪記錄。
- JD 共 24 筆來源，均指向已讀的員工原話：I2 10 筆、I4 11 筆、I6 3 筆；`needs_review` 均為 false。這是保存狀態，不直接等於每筆語意都正確，亦不能證明 JD 已使用新版 Memory 引用。

讀取使用既有 `interviews.persistence.list_formal_interviews`、`work_memory.candidate_queries.read_snapshot/read_snapshot_map/read_snapshot_object`、`job_description.persistence.read_document/read_revision`、`work_queries.read_work_at` 及 `source_persistence.read_source_references`；沒有另寫資料投影或掃其他 job／snapshot。明確連線 `127.0.0.1:55439/caliburn_target_demo`，schema `caliburn`；兩次交易均核對 `(database, schema, transaction_read_only, isolation) = ('caliburn_target_demo', 'caliburn', 'on', 'repeatable read')`，使用 `default_transaction_read_only=on`、connect 3s、statement 5s、lock 1s、idle-in-transaction 15s timeout，讀後 rollback／dispose。第二次為修正本地 stdout 中文編碼並補讀來源，固定 JD revision 相同，不是模型重跑。第二次完整讀取投影（含訊息 1–7／兩層／JD／來源，排序 JSON）SHA-256：`5394726eadb029daf744529f582a8987168894c80ada840e3494733b82c6da17`；未另存資料副本。

### 發現與 rubric 判定

| 檢查項 | 本次固定產物證據 | 判定 |
| --- | --- | --- |
| 月／日分工與更正 | 月底 B1 明寫「發現差異時由本人先複點」；每日 B1 由現場同事複點。B2 分節保留兩者，另明說每日分工不等於月底分工。JD 月底 requirement `71ca56a7-14d5-4ec2-bf64-dd2732b99f49` 保留本人先複點；每日 requirement `c17ae321-aabd-454f-8817-2dc89a2b649e` 限定「每日異常」 | 本樣本 pass；原 G2 的混淆在此次相關正文已消除，不回填舊 revision |
| 共用文字不反向污染 | collaborator `e3394ed1-f7c2-4ab3-9ff4-80f70a9de1e5` revision `3bc8e883-8f84-4322-9927-ba8f05488ceb` 已以「每日庫存異常時」限定；I7 亦明說月末本人／每日現場，未再一概排除本人複點 | 本樣本 pass |
| 閉環條件 | 每日 B1、B2、JD outcome `b164b2ed-14e3-4c92-b8dc-b01a6cbb6670` 均保留：（單據或系統紀錄更正 **且** 數量一致）**或**（主管確認原因 **及** 處理方式），才記結果／結案日期，否則繼續追蹤 | 本樣本 pass；不是只留下「追蹤至結案」 |
| 權限與例外 | B1／B2／JD 均保留主管核准，短少／原因查不清當天升級；不增加本人改帳核准、採購或補貨決策 | 本樣本 pass，未見越權捏造 |
| G1 背景承接 | 兩個 B1 正文仍沒有承接 I2 已知的「營運部／庫存管理專員／向倉儲主管報告」背景；B2 開頭與 JD profile 有保留，且情境來源可回查 I2 | 維持 partial：是 B1 背景承接缺口，不是無來源幻覺；不能報新提示已修復 |
| 未知與高訊號 | B1「追蹤表的欄位」概括為未知，但已有原因、單據、待辦、結果及結案日期；宜理解為完整格式尚未知，不宜抹掉已知欄位。B2 亦重述兩案大量流程，仍有跨層重複的壓縮空間 | partial／後續取捨項；未因此要求固定字數或新增元件 |
| 引導與引用結構 | I7 修正後繼續問其他低頻／支援工作；B1 新引用包含 I6，B2 引用符合快照選用修訂 | 此可見範圍 pass；完整訪談涵蓋率、所有逐欄引用語意及工具權限執行未全面驗證 |

**收斂：**本次新增可定位的產物證據支持「更正已傳到 B1→B2，JD 亦保留責任與結案條件」；本次目標檢查未確認 rubric hard failure，但整體仍為 **partial**，不宣告 T14 或專業 JD 全面達標。

### B1 新 prompt 是否已有新證據／限制

本次重讀 B1 instructions，檔案 SHA-256 仍為第三輪的 `a0a36a70a778fe7f23c8a386226f2501a4ac4f760c1edb33c1d39b7d48ca298c`。**檔案現況不證明生成此 snapshot 時載入了同一提示。**本輪沒有查模型請求歷史、啟動程序版本或重新呼叫 provider；[主線 T08 §5.4](t08-consultant-turn.md#54-第三輪更正真模型暫停接續1129-台北核對)記錄的是新 I6 加入後的第二批生成，不是提示 A/B 對照。因此：有新 Memory 產物品質證據，**沒有足以歸因新 B1 背景提示改善 G1 的證據**；其背景缺口在此快照仍可見。不得把 I6 新增事實帶來的改善，算成三句提示的效果，也不反推新提示必然失效。

本輪僅以既有合成資料做代理審讀，沒有獨立領域專家校準、長訪談／其他職種測試、延遲成本對照或新 provider 驗證。前兩輪歷史結論保留；只追加本輪固定產物證據，另依主線要求將文首兩處 Owner 歸因更正為主線分派／回報。

## 2026-10-01：指引、參數語意與實際 Context 交叉審核

Owner 要求一起檢查 Agent prompt、tool description、參數 description 與實際 Context；不把品質問題一律歸因模型、不無限加提示。沿上述指南及共同工具規範，重新取得 [GPT-6 prompting 指引](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)與 [function calling 參數設計建議](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)。官方支持排除互相矛盾的指令、清楚說明參數用途及限制、在實際型號評測；不保證某句提示消除錯引。本片維持 `gpt-6-luna`／medium，不把 Astra 建議當 Luna 品質保證，也不複製 coding agent 的廣泛自主權限。

### 改動範圍與非改動

- A／B1／B2 主指引、工具權限、14 項 A 工具集合與既有 Context 組裝不變。B1 只寫情境、B2 只寫理解、A 只讀 Memory 的分界無本片證據要求改動。
- 四份 JD canonical schema 只補 `description`：職責／任務／成果／要求／K/S 關係的意義、文字更新與來源增刪的差別、整筆移除引用的語意，以及 App 提供的引用定位。Profile 明說直接匯報對象不是所有成果收件人。沒有增加參數、必填欄、來源數量門檻或新的保存機制。
- 說明放在發生選擇的位置，不把所有工具語意再次抄入角色指引。既有 tool description 已有讀／寫時機與候選效果，本片不另加一份。來源選擇仍由模型依原話判斷，App 不猜補、不禁用合法刪除；`confirm_reference_alignment` 仍只作用於指定引用，不代表全項完成。
- 參數契約由既有 generator 同步 Python、TypeScript 與 packaged schema；不手改生成檔。這是提示／契約澄清，不是新 Domain 行為，不用中文 exact-match 單元測試冒充模型品質 Red–Green。

### 有界 provider 檢查（執行前 manifest）

最多 4 次生成＋4 次 count、總預算 US$1，每次 input ≤40K／output ≤8,192、120 秒、零自動重試／compact，仍為 direct Responses、store=false／all_turns。兩次取 T17 已保存的第四輪「讀 JD 後」合成請求，只替換當前 canonical tool definitions；保留原生歷史及 instructions，不重寫原 checkpoint。另兩次使用全合成、無私人資料的相反情境：舊主管被明確更正，舊來源確實不再支持該欄，不能因保留指引而禁止合法移除。這兩次是乾淨構造的工具選擇 fixture，不冒充保存過的產品旅程。

只讀模型公開工具選擇、文字與使用量，不執行寫入、不偽造成功、不輸出 opaque reasoning；只選讀取或沒有目標修訂時記未觀察。判準為「剩餘來源共同支持修改後的內容」，不是強制某個操作序列或引用數量。沿原自然失敗作基準，本片不再次廣跑 baseline。無穩定改善即停止，不改原 fail，也不宣告 T14／T17 通過。忽略目錄原件預定為 `jd-tool-descriptions-20261001.json`。

首試在 sandbox 的 count 呼叫回 `APIConnectionError`，未開始生成，錯誤原件保留、不覆寫。改經已授權的網路執行環境作上述四次有限檢查，輸出另為 `jd-tool-descriptions-direct-20261001.json`；最多 4 次生成及 5 次 count 嘗試（含該連線失敗），不提高 US$1 上界、不啟用 SDK 自動重試。

首次外送審查因保存 Context 可能含私人資料而拒絕，未換路徑繞過。先唯讀核對出處：`verify_core_journey.py` 新建隔離 `_test` DB schema、四個輸入逐字等於 `simulate_interview.py` 從 repo `personas.json` 的 `course_admin` 合成人設產生的 b0 第 2 試次（4/4 相等）；實際 Context 的歷史亦與同一合成檔案相符。提供此新增證據後，原有界執行獲准，沒有傳 Demo、真員工資料或金鑰正文。

### 實際 Context：A 的固定請求審核

唯讀核對 `core_journey_20261001_c2e1fcd8`、檔案 `c0aaed2f-22e5-40fa-98f5-a6bc12c0a2ef` 的第四輪，沒有改 DB 或呼叫 provider：

- **48 項順序**：前三輪合法原生歷史 42 項 → App 參考資料（user）→ 本次員工原話（user）→ reasoning → assistant commentary → `read_jd` → 配對結果。12 組 call/result 完整、無重複 call ID、phase 保留；本次原話只出現一次，不在歷史訪談中。
- 正式歷史保留說話者、訪談序號及歷史標記，原文與正式訪談一致。舊原生發言與後來 App 歷史投影有重複，但都是原順序中的歷史，不是重新加工成當次新輸入；本片不擅刪歷史以減 token。
- 起始固定資料比首版 Memory 發布約早 7 秒；本 Turn 繼續用空快照基底和未整理訪談是正確 pin，不是漏刷新。讀 JD 的結果確實包含原引用及序號 2，不能把刪引用歸因來源沒提供。
- 最初指定 checkpoint `1f1bcf19-6520-6c9d-8007-e9acb8a5dc69` 的**主 snapshot**仍是 44 項，但前次 probe 查的是 `checkpoint_writes.request_snapshot`，為完整 48 項；與後繼 `1f1bcf19-652f-6cc8-8008-8e4080d47cde` 主 snapshot 完全一致。另重算前次四個 request 指紋，皆與原件相符；不存在誤讀前置造成假對照的問題。

未在這個自然樣本測 cancelled Turn 或 compact；取消隔離另以本次重跑的既有 `test_role_context_history.py` 提供確定性證據，不把它冒充壓縮後語意品質。

### 實際 Context：B1／B2 的批次起始審核

同一合成職務檔案的兩批 Memory，共四份已保存且具有外送紀錄的起始請求，唯讀比對角色指引、工具集合、原生歷史與 App 資料：

| 批次 ID 前綴 | 角色 | input 項數 | 新增 App 參考資料 |
|---|---|---|---|
| `eeb6f87d…` | B1 | 1 | 情境導覽 0 筆、正式訪談序號 1–4 |
| 同上 | B2 | 1 | 情境導覽 1 筆、理解導覽 0 筆、1 筆新增情境差異 |
| `86b9dbd7…` | B1 | 9＝既有 8＋本批 1 | 情境導覽 1 筆、正式訪談序號 5–8 |
| 同上 | B2 | 18＝既有 17＋本批 1 | 情境導覽 3 筆、理解導覽 1 筆、2 筆新增與 1 筆修改差異 |

- 實際 instructions 與各自角色常數一致。B1 六項工具只含情境導覽／讀寫及訪談讀取；B2 八項工具含兩層導覽／讀取、理解寫入及訪談讀取，沒有情境寫入。未見 B1 混入理解資料或另一角色私有歷史。
- 後一批請求前綴逐項承接該角色先前完成的原生歷史，再追加一則 user-role App 資料，明標非員工新發話。B2 收到非空 Markdown diff 及受影響理解；第二批修改指出一筆既有理解依賴。
- 兩批固定訪談邊界分別為 `(K,F]=(0,4]`、`(4,8]`，截止於觸發整理且已完成的 A 輪之員工輸入。B1 原話與正式訪談逐項一致，B2 訪談讀取上限也沿用本批 F。

本抽查未見角色資料、順序或批次邊界偏差；**不是四份請求之外所有中途請求的保證**，也未驗回交 B1、壓縮或語意分析品質。不因沒有發現組裝錯誤，就把自然模型的引用失敗判成已解決。

### 真模型結果、審核與取捨

最終描述經獨立覆核修正兩項過度表述：移除來源不能被寫成「只要仍有支持力就永遠不得移除」；確認引用不能被寫成整項／整欄核對。主代理對照既有來源行為測例後採用修正。最終資料形狀、權限及 Domain 操作未變。

| 情境 | 試次 | 結果 |
|---|---|---|
| 綜合職責只更正出席彙整頻率 | 1、3 | 兩次均正確改為每季，但仍移除支持其他保留工作的原引用，只加本次更正。**來源語意缺口仍在，不採作已修復證據。**第 3 次另提出兩個有據任務，不抵銷這項失敗。 |
| 直接匯報對象整欄由主任更正為校長 | 2、4 | 兩次均只改該欄、移除原主管引用、增加本次來源；職稱／單位引用保留。沒有因保留指引而禁止合法移除，也未把全部交接對象一起改掉。 |

共 **4 次生成、4 次成功 count＋1 次連線失敗 count**；零工具執行、零自動重試／compact。成功生成 input 47,160、output 1,449（含 reasoning）。綜合職責請求由前次 baseline 的 14,109 增為 15,500 input tokens（約 +9.9%）；不能宣稱此次已降低 Context 耗用。增加的是可讀參數語意，不是更多業務欄位或載入全部指南。

原件 `jd-tool-descriptions-direct-20261001.json` SHA-256 `ff53b45f375e6cd221a18fc746cb162452e4194ff3bc886bbe1851161ce5b847`；兩種 request SHA-256 分別為 `53e0e53473e2422f58407e838701732d5b40053738c4cb50095ff21afca29cd8`、`1151a6ac468ca2e5ac6895c3e22d0967c0f0f4051b062db0bab0e8e4e2e98fcd`。沒有保存或輸出私人 reasoning 明文。這是工具選擇檢查，沒有正式保存／PDF／UI 新旅程，不以 API completed 代替產品驗收。

**採用界線：**保留參數契約的可讀性澄清，不把它標成錯引修復；A／B1／B2 主 prompt／工具集合／Context 均不為此再改一次。局部更正缺口需要後續獨立品質取捨，停止同假說的重試，不加 MUST、來源自動猜補、reviewer 或強制每輪全稿核對。T14／T17 維持未完成。

### 確定性驗證

在 `apps/api` 使用 `.venv-target/Scripts/python.exe -B`：

- `-m pytest tests/contracts/test_tool_schema_strictness.py tests/contracts/test_jd_source_actions_wire.py tests/contracts/test_jd_item_revision_schema.py tests/contracts/test_jd_item_creation_wire.py tests/unit/test_role_prompt_contracts.py tests/unit/test_consultant_tools.py -q -p no:cacheprovider --tb=short`：最終措辭 **71 passed，1.81s**。實際定義載入 canonical 生成資源，所有角色 strict schema 保留；不是中文片語測試。
- 設定隔離 `CALIBURN_TEST_DATABASE_URL` 後，`-m pytest tests/integration/test_jd_model_item_roundtrip.py tests/integration/test_jd_item_revision.py tests/integration/test_jd_source_tool_actions.py tests/integration/test_role_context_history.py -q -p no:cacheprovider --tb=short`：**13 passed，9.48s**。驗實際編碼／候選修改、逐筆來源確認、保存結果接續和取消歷史隔離；假模型，不證明自然來源品質。最終第二次文案修正未改任何資料形狀／Domain，沿用此結果。
- `scripts/generate_contracts.py --check` 通過；首輪 sandbox 暫存寫入被拒後，使用同一既有生成器的核准環境完成，未手改生成檔。
- 四份 canonical schema 與 HEAD 作遞迴比較，僅排除字串型 `description` 註解後完全一致；未刪除名為 description 的業務欄位。確認此次 wire shape 不變。
- 前端在 `apps/web` 執行既有 `node node_modules/typescript/bin/tsc --noEmit` 通過。`pnpm typecheck` 在編譯前因套件管理器欲重整依賴、無互動終端而退出，未允許移除／重裝依賴；因此只聲明直接 TypeScript 檢查通過，不宣稱 pnpm wrapper 成功或重跑前端全套。

## 2026-10-01：來源保留的 reasoning effort 對照

基準 `adbbb922`。上一片已定位原生請求、完整舊來源和 App 操作語意；模型仍主動送出 `remove_source`，不是 DB 隱性清除。停止重複調提示後，本片只檢查**同一模型在較高 reasoning effort 下的來源判斷**，不改產品、不裁歷史、不換模型、不自動補引或增 reviewer。

研究：[Luna 官方規格](https://developers.openai.com/api/docs/models/gpt-6-luna)支持 medium／high；[部署指引](https://developers.openai.com/api/docs/guides/deployment-checklist#set-up-reasoningeffort)要求針對品質、延遲及成本驗證 effort，而非預設越高越好；[模型選擇](https://developers.openai.com/api/docs/guides/model-selection)同樣建議以相同輸入比較。這些只支持驗證方法，不保證 high 修復錯引，也不構成改採 Astra／Sol 的授權或證據。

### 執行前 manifest

沿上節已核明全合成的兩個請求，重用現行 canonical tools。兩次 partial、一次 whole-field，順序 partial → whole-field → partial；只將 `reasoning.effort` 從 medium 改成 high，深比較其餘完整 payload 必須相等。舊模型原件／phase 原序保留，不改資料庫 checkpoint；whole-field 是明示合成的工具選擇 fixture，不冒充真產品已執行的工具結果。

- 上限：3 次 create＋3 次 count、零自動重試／compact；仍 `gpt-6-luna`、store=false、all_turns、direct SDK 3.20.0。每次 input ≤40K、output ≤8,192、120 秒、全批 600 秒，管理預算 US$1。
- 只讀隔離 `_test` DB 中既有合成 fixture；只經安全 loader 讀 OpenAI key，不讀／改 Demo 或私人資料。只記公開工具參數、用量、延遲及 hash，不保存 opaque reasoning，不执行模型寫入工具。
- `.research-tmp/eval/reasoning-effort-high-20261001.jsonl` 獨占建立；錯誤／超限立即停止，不換模型或增加試次。沒有目標修改記未觀察，不把重新讀取或 API 200 算來源成功。
- 基準重用上節 medium 的原件（partial 0/2、whole-field 2/2），不再付費重跑已重現的基準；這不是同批隨機比較或顯著性證明。判準仍是剩餘來源共同支持保留的完整內容，且合法整欄更正不受阻；不要求固定 ID 或唯一工具序列。
- 本片只是診斷校準，不是產品設定改動／TDD。若有改善仍須短產品接續驗證才能採納；無改善就保留限制，不能因同一案例試到成功便關閉 T14／T17。

### 局部結果與產品接續 manifest

三次均正常完成；兩次 partial 保留舊來源＋新增本次更正，未再移除仍支持報名／課前／異動等工作的引用。其中一次職責用「定期」，但新建任務明確寫每季；另一次職責與任務均明確寫每季。whole-field 只更正直接主管為校長、移除該欄失效來源，職稱／單位未動。主代理核對公開參數與合成原文，獨立代理覆核輸入指紋及來源語意：partial 由 medium 0/2 變為 high 2/2，觀察到局部工具選擇改善；whole-field 的 medium 原已 2/2，high 1/1 只表示未觀察到退步。未作獨立領域評分、未執行工具，不宣稱穩定修復。

兩次 partial latency 13.802／19.745 秒，output 1,511／2,089（reasoning 897／1,511）；whole-field 2.859 秒、output 181（reasoning 64）。原 medium partial output 276／750 等為較早試次，不宣稱嚴格同批延遲比較；本片 high 的完整參數選擇與原件存於上述 JSONL。

**下一階段在執行前另限：**沿既有 `verify_core_journey.py` 真 App／PG probe，新隨機 `core_journey_20261001_*` schema，只用 b0-2 已核明的前四則合成員工原文，最多 4 A Turn、4 自然啟動 Memory 批次。A／B1／B2 使用既有共同 ModelSettings，僅本次測試改為 Luna／high（**不是只改 A 的因果對照**），Prompt／工具／Context／產品預設不變。每 execution ≤16 steps、48 outbound attempts、每請求最多1次、1次compact、240秒、output≤8,192；每 execution 測試上限 US$0.25，整批≤US$2，無自動重跑。失敗停止該旅程並等自有工作收尾；不擴到其他人設、不重跑 medium、不重驗未修改的 PDF／UI。

新結果 `.research-tmp/eval/core-journey-high-20261001.json` 不覆寫原證據；回讀保存的 JD、逐筆來源與背景結果，檢查同一來源保留反例、既有工作及責任邊界是否仍成立。沒有真保存或來源缺漏就不採納新預設；即使此片通過，也不單憑四轮宣告所有長訪談、T14／T17 過關。

### 真 App 保存結果與採納界線

一次執行，沒有重跑至通過。隔離 schema `core_journey_20261001_635da286`、職務檔案 `a40b19dc-da6f-4105-9a4c-2c068edcaafa`；4 A Turn、3 自然 Memory 批次均 completed，無 active／failed 殘留。最新 Memory 處理至訪談序號 6，**沒有宣稱已吸收序號 8 的季度更正**；A 直接引用本輪原話，後续仍須保留尚未整理的近期原話。

正式 JD revision `d6c4160e-dd83-4476-8a95-54e5e9962353` 有 1 職責、2 任務、4 協作對象。主代理逐項閱讀 JD／訪談／來源，獨立代理另行覆核：

| 檢查 | 保存結果 |
|---|---|
| 身分／職務範圍與不授課、不決定開課收費 | 4 profile 欄位及職責引用序號 2，沒有錯引後輪 |
| 保留綜合行政任務 | 同一任務保留序號 2／4／6，新增序號 8；沒有因新出席細節刪掉報名、課前、異動的有效依據 |
| 季度更正 | 出席彙整任務、成果及要求引用 8；行政組長協作內容也改每季，沒有把課前两工作天或每日工作一起改掉 |
| 來源回讀 | 28 筆引用均成功讀取；正文、角色與對應正式訪談逐字相符。序號 2／4／6／8 分別 8／7／5／8 筆 |
| 訪談引導 | 每轮有後續問題；最後詢問課後紀錄是否就是出席紀錄、是否還有其他紀錄，沒有假稱已完成全稿 |

Memory 最新快照另作唯讀抽查：3 情境、1 理解保留已知工作、權責與未知；月度說法仍是其截止於序號 6 的歷史，不是未吸收序號 8 仍假稱已更新。**限制：**理解仍大量複述情境；情境／理解把原話「還有人付款資料對不起來」写成「另有一人」，原話未明示確切人數，不能把此語意細節當成已核實。此片不以 Graph completed 宣告 Memory 分析品質全過。

持久外送紀錄：A 27 次 model＋30 次 count、Memory 28 次 model＋32 次 count，無 compact／重試／已記錄 provider failure；55 次 model 均有本機費率估算，A US$0.020545710、Memory US$0.012881840，合計 **US$0.033427550**，不是供應商帳單。前三次工具選擇探針 input 39,080、output 3,781、reasoning 2,472，依現有費率估 US$0.004100260；兩階段合計估 US$0.037527810，未超 manifest。

原件：`core-journey-high-20261001.json` SHA-256 `dbb1d46495ce6367119c224d98e34be15f5dd22649b46ab245258c12fb48e644`；`reasoning-effort-high-20261001.jsonl` SHA-256 `ba820af92bc913d8a3a9deb0cd736bc2d7644f17c71244f259c56253102db3ab`。探針及隔離資料保留於既有忽略位置，不輸出憑證／opaque reasoning，也不改 Demo。

**採納：**在原 `ModelSettings` 將預設 medium 改 high，保留顯式較低 effort 的測試／校準能力；無角色設定平台、新欄位、新 Agent、自動补引用或額外 prompt。產品重啟後的新請求才使用新預設，已保存原生請求／歷史不改。改善證據限於上述已知反例及一次短旅程；不宣稱所有角色都有提升或來源失誤已根治。行政任務偏大、知識／技能未分析、長訪談穩定性仍由原品質 gate 管理。

**串流清理待釐清：**真旅程 stdout 一次出現 `Exception ignored while closing generator ... AsyncResponseStream.__aiter__`／`ValueError: async generator already executing`。正式結果、工具來源及全部工作均可取得，未見本次工作失敗；但不能宣稱無警告或已修復。已對照鎖定 SDK 的 stream 關閉實作及原 adapter，現有資料尚不足定位警告原因，不猜是 saver／provider 故障、不修改框架私有欄位、不為此再跑付費旅程。保留至原串流接線範圍做有限離線重現，非新恢復平台。

### 設定接線驗證

在既有 `test_role_prompt_contracts.py` 的實際角色組裝邊界補預設／明確 override 檢查，不用 prompt 文字比對宣稱品質：舊碼 A／B1／B2 三個預設例均因送 medium 而 Red，三個 low override 例通過；只改一行設定後：

`./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_role_prompt_contracts.py tests/unit/test_model_settings.py tests/unit/test_response_streaming.py tests/unit/test_terminal_response_handoff.py tests/contracts/test_openai_responses.py -q -p no:cacheprovider --tb=short`

**59 passed，1.94s**；Ruff check 與 format --check 通過。這只證明設定、角色、公開串流及原件交接契約未被本改動破壞，不能消除上面的真旅程清理警告。未改 PDF／UI／資料庫交易，沿風險分層不重跑其全套。T14／T16／T17 維持未完成。

## 2026-10-01：指南覆蓋與下一個品質缺口收斂

基準 `d0d9452b`；本片是審查與既有測例驗證，**未再改角色指引、schema、模型設定或 Context**。完整回讀三份內容指南及三角色 instructions，對照既有 13 個品質情境、rubric 和前節實際請求證據；不因方法素材齊備就勾選 T14，也不要求每個簡單案例再重跑完整旅程。

| 責任 | 目前已表達／已交付 | 不能因此推導的效果 |
|---|---|---|
| A 訪談與成稿 | 全工作廣度、本人責任、條件、未知、按需讀取、足夠即寫、主動引導；13 例有更正、無主語、低頻、人工稿及部分覆蓋反例 | 有指令不等於每次提問皆中立，或完整 JD 已達標 |
| B1 情境 | 已知工作背景、具體處理、條件、未知與原話來源；不讀理解、不造新事實 | 四輪樣本的「還有人」變「另有一人」仍是未經支持的精確化，不能算已核實 |
| B2 理解 | 跨情境共同模式、必要邊界、可下查依據；不逐案複製，不因新資料未提就刪舊工作 | 指令已禁止過度複製，不代表本次理解正文已足夠精煉 |
| Tool／參數 | 工作內容與來源分開，參數明示語意、修改與確認界線；既有知識／技能建立與任務關聯入口俱在 | 工具可用不等於模型會適時選用；不因集合空白就自動填入公版能力 |
| Context／評分材料 | 真請求抽查見前節；fixture 只把 input 作資料，oracle 明確限 reviewer 使用 | 不把 oracle、理想答案或下一輪資訊塞進產品 Context 來取得通過 |

### 知識／技能：先分清未觀察與功能故障

唯讀六份既有 `b0-*.json`：它們保存的 `jd.work.capabilities` 都為空。這是**先前 medium 配置的有限訪談樣本**，不是 high 新預設的對照結果。另完整讀 `b0-warehouse-2` 的 12 輪公開訪談與 JD：員工已說明採購／送貨單核對、儲位規則、掃碼、先進先出、盤點及退貨分工；後幾輪多次表示交接或作法尚不清楚，顧問仍詢問未明細節，尚未進入知識／技能的專業整理。不能把 12 輪截點當成模型已宣告整份完成，也不能因沒有 K/S 項目就推論 DB 丟資料。

目前 `create_jd_item` 公開說明、`CapabilityItem.description` 與 parser 已提供 `knowledge`／`skill`，而且明示「從實際工作推得」；不是缺少工具或只能等員工自己說出 K/S 術語。指南要求的下一個品質問題是：**能否由已確認的實際工作提煉必要專業及用途，缺會改變結論的資料才中立追問，而非重抄任務、從職稱猜能力或為填空而寫。**本片沒有改成強制 K/S、每輪收尾清單或固定問卷；是否要改 Prompt 仍須由這項行為的有限對照決定。

本片在 `apps/api` 重跑：

- `./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_job_analysis_quality_fixtures.py tests/unit/test_role_prompt_contracts.py -q -p no:cacheprovider --tb=short`：**40 passed，1.58s**。驗素材、角色組裝及預設／override 接線，不代表 13 例自然模型皆通過。
- 指定既有 loopback `_test` DB 後，`./.venv-target/Scripts/python.exe -B -m pytest tests/integration/test_jd_item_creation.py tests/integration/test_jd_model_item_roundtrip.py tests/contracts/test_jd_item_creation_wire.py -q -p no:cacheprovider --tb=short`：**14 passed，6.59s**。覆蓋知識／技能候選、來源、任務關聯及原操作重入，也驗模型 codec 的既有職責往返；不冒稱每種 K/S 都已真模型自然產生。fixture 只建立、清理自己新建的隨機 schema，原合成旅程和 Demo 不變。

### 串流警告的有限離線診斷

依 systematic-debugging 先找 owner／反例，而非看到關閉警告就加恢復包裝。獨立診斷回報：現有 streaming／terminal handoff **26 passed**；160 次離線合成串流比較 adapter、SDK 直接迭代及 httpx2 transport wrapper，terminal 均完整，GC／排程收尾後沒有重現終結警告或殘留 task。探針為 ignored `stream-finalization-probe-20261001-0243.py`；此結果由診斷代理執行，不算主代理另跑一輪。

產品呼叫走 SDK `AsyncStream`；httpx2 transport 也有名為 `AsyncResponseStream` 的 generator。因此原警告的類名與 `jsonplus` 堆疊不足以歸責 SDK 高階 helper、serializer、`break` 或 effort。**根因仍未證實、不修改產品碼**；真 socket、連線池及實際並行 GC 時序未覆蓋。若自然再現，才取去敏完整 traceback／原碼位置與資源狀態；不為此再跑付費長旅程、改框架私有欄位或新建 cleanup／恢復機制。

本片零 provider 外送、零 Demo 操作，沒有新增測試平台。T14 保持未完成：先補「專業提煉及成稿品質」的代表性觀察，再決定是否需要提示調整；不把「全部素材未逐一跑模型」當成必須無限擴測的理由，也不把獨立代理審讀冒充人類領域校準。

## 2026-10-01：既有 high 旅程的專業提煉檢查

### 執行前 manifest

基準 `4a85f6eb`，不先改 Prompt／Tool／Context。沿前述合成 `core_journey_20261001_635da286` 職務檔案續接最多兩輪：先回答原第 9 則顧問對課後紀錄的問題，補充實際資料核對與試算表整理方法；再要求整理已談工作、保留未知及指出剩餘缺口。這是新的合成訪談資訊，不是把評分 oracle 塞進 Context；不提示 K/S 欄位名稱、不指定工具或要求必填空欄。

假設：現有 high 指引及已提供的建立／關聯工具，能把充分說明的工作方法提煉成有用途、有來源的知識與技能，而不只持續補大任務或追問未知。以真保存結果判斷；K/S 仍未出現時先查原生請求／公開工具選擇，不直接加 MUST 或自動填資料。亦查來源保留、每季口徑與未知邊界，避免只看新增欄位。

- 執行前核對舊證據 hash、同一合成 job、正式訪談末序號 9、原 JD revision，且沒有 active execution；不符合就零外送停止，不重建／清除資料。
- `gpt-6-luna`／high、direct SDK、store=false／all_turns，現行角色／工具；最多 2 A Turn、2 自然觸發 Memory 批次。每 execution ≤16 model steps、48 outbound attempts、每請求1次、compact≤1、240秒、output≤8,192、測試上限 US$0.25；總上限 US$1，不自動重跑失敗旅程。
- 只使用既有隔離 `_test` schema 和合成文字；不操作 Demo／私人資料，不輸出憑證或 opaque reasoning。結果新存 `.research-tmp/eval/core-capabilities-high-20261001.json`，不覆寫原四輪證據；腳本記錄本次角色及工具檔案指紋。
- 驗收限本例專業提煉及回歸，非普遍品質證明、盲測或領域專家校準。不因一次成功勾選全部 T14／T17，也不為未改的 PDF／UI 重跑整套。

方法依據：[OpenAI GPT-6 提示與驗證建議](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)要求按實際型號／工作負載驗證，並在有未解疑點時才擴測；其 Astra 觀察不是 Luna 能力保證。專業內容仍依本案三份分析／訪談／JD 指南。

### 首次執行中斷與一次補驗界線

第 5 輪自然讀取 JD／Memory／舊原話，建立「試算表資料整理與核對」技能，並成功連到兩項候選任務；之後第 7 次模型請求記錄 `transient_service`，依本批每請求 1 次限制終止。6 個完整回應、21 個成功工具結果已保存，沒有工具錯誤；**候選不等於正式成稿**。App 結束後正式 JD revision 與訪談末序號 9 均不變，失敗輸入沒有取得正式訪談資格。此前已接受的第 4 輪背景整理另行完成至序號 8，不包含本失敗輸入。

這是已記錄的服務中斷，不以空正式 K/S 反推提示失效，也不把已保存候選視為驗收成功。基於此具體失敗，**另限一次補驗**：相同兩則合成文字、相同模型／角色／工具，從目前安全點重新輸入；每請求最多 2 次、每 execution 300 秒，其餘前述限額不變，最多 2 A＋2 Memory、追加上限 US$1。不修改產品的既有重試政策；補驗仍失敗就停止，不第三次重跑。新證據 `core-capabilities-high-retry-20261001.json` 獨占建立並保留首次結果。此為可用性受阻後的有限補驗，因已發布 Memory 已前進，不宣稱同 Context A/B 對照。

### 本次實際 Context 抽查

從上述失敗 execution `a728e82d-145f-462a-9376-3d6af71e6d55` 已保存原件唯讀核對，未讀內部推理。輪前歷史計量用 snapshot 與已加入新輸入的模型 snapshot 分開，不能把前者誤判為漏掉當輪輸入。

- 首次加入本輪資料的 request 有 160 items；instructions 與現行 `CONSULTANT_INSTRUCTIONS` 全文相等，tools 與現行 `consultant_tool_definitions()` 相等；`store=false`、沒有 `previous_response_id`、reasoning 為 high／all_turns。
- 最新兩個 user items 依序是 App 參考資料、逐字本次合成員工輸入。App 包含兩層 map、近期歷史與讀取邊界；本輪固定 Memory 涵蓋至 6，近期原話是 7／8／9。背景稍後發布至 8 沒有改寫本輪基準。
- 既有歷史保留 message／reasoning／function_call／function_call_output，assistant 的 commentary／final_answer 仍在；沒有把參考資料升成 developer／system 訊息，沒有 oracle、下一則測試輸入或全稿 JD 注入。
- 8 個保存的計量值由 41,949（舊歷史計量）至 63,790 tokens；其中 7 次模型請求，末次服務失敗；未達壓縮門檻。本例不宣稱已測高容量 compaction。
- 已加入本輪輸入的 request，以排序 key 的 UTF-8 JSON 計 SHA-256：`0e95760278f5e1f8c48067b9aa8e2c144de1ae84f93759eabe93c106ee75027b`。這只識別本機保存原件，不是供應商實際計费或網路 bytes 的證明。

目前沒有本例 Context 錯放資料的反例，不改歷史、不加另一份 state 或資料管理層。

### 補驗正式結果與限制

唯一一次補驗已結束，沒有第三次重跑：

- 第 5 輪 `375613cc-87f5-41d5-9b8b-0a809cfde096` 在一次暫時服務錯誤後完成，正式 JD `f76545e8-d4b9-43ce-871b-2e72fe07252a` 保存 1 職責、3 任務、1 技能及 2 任務↔技能關係。新增「整理成人進修班出席紀錄」從原大任務拆出，保留報名／課前／通知、每季彙整及原責任界線。
- 「試算表整理、彙總與核對」取自員工實際篩選缺漏、樞紐彙總及核對原表的方法，連到每日紀錄及季度彙整。沒有要求模型填 K/S，沒有手改產品資料；由此可觀察到現行 Prompt＋工具能自然產生並保存有據技能。**知識提煉與整份收尾仍未觀察**，不把一項技能當成全部專業分析完成。
- 第 6 輪 `1651623f-fea4-423f-bb56-35b1edf04e6d` 兩次模型請求都記 `transient_service`，依測試限額結束。正式 JD 仍為上述第 5 輪版本，正式訪談末序號 11；失敗收尾輸入沒有進正式序列。原因只證實到這個安全分類，不臆測具體 HTTP 狀態、服務商事故或扣款結果。
- 第 5 輪觸發的 Memory `2df56253-82c0-4afe-b778-539579ea7404` 正常完成；快照 `0ad00867-27c1-4f28-b8c5-8409a417aa59` 涵蓋至員工序號 10，3 情境、1 理解納入方法及季度更正。沒有吸收第 6 輪未完成輸入。所有本片工作已終止，App 已關閉，無 active 殘留。
- 唯讀比對原生 items：首次失敗輪的 21 個工具呼叫 ID 都沒有進入補驗的新輪 Context；沒有把已放棄候選的工具結果冒充目前正式狀態。這只驗本次回退，不替代既有取消／故障測試。

37 筆正式來源皆可回讀，其序號、角色與原文字句逐一和正式訪談相符；技能與兩項技能關係引用序號 10。**這是原文保存正確性，不是每項語意引用充分性的保證。**新拆出的出席任務及成果僅引用 10，但「每個有開課的日子、老師交表、存指定資料夾」來自 8；這個跨輪內容搬移的來源涵蓋仍需保留為品質缺口，不自動替模型補引用。獨立審讀核對完成後的同一原件 hash，判為引用不足而非內容捏造；序號 10 已足以支持的核對／篩漏要求不需機械式補引 8。顧問最後確認每季原始表是哪份，沒有宣告全稿完成。

獨立工程審讀認為技能概括及任務拆分有內容依據；不是人類專家校準。Memory 仍沿用前次「還有人」被寫成「另有一人」的未支持精確化，理解也仍偏逐情境複述；兩點未因 Graph 完成而視為修復。

費用依持久使用紀錄的本機費率估算：首次失敗 A 已回報 US$0.011899205、補驗第 5 輪 US$0.014360840、其 Memory US$0.011782120，合計已回報 **US$0.038042165**。期間前次第 4 輪的待整理工作另外完成，已回報 US$0.006946040；不混成本次新輸入產物。4 次失敗模型 attempt 無回報 usage，**不能宣稱免費或上述為完整帳單**；保留既有預留額及限額。沒有本片 compact。

補驗中自然再現 `Response.aiter_raw` 及 `BoundAsyncStream.__aiter__` 的 generator 清理警告，兩者都以 `ValueError: async generator already executing` 出現在 serde 觸發 GC 的堆疊；尚未證明是本次服務錯誤原因，不新增恢復機制或改框架私有碼。

原件 SHA-256：首次 `8e8eac0228e141d374cf6a3ac8a31cd0e99915d19c63927393c8c14a4b96675b`；補驗 `49037d17f1d8e93c2019402fbfa1d2b2a7dc50dbb2d3772aeba554345860fe7a`。本片維持現行 Prompt／工具／Context：不能因服務失敗猜提示有錯，也不因個案有技能就宣稱品質全過。T14／T16／T17 未完成，下一切片沿既有跨輪來源品質問題處理，避免再無界擴測或重跑整套訪談。

## 2026-10-01：來源選項的參數語意對照

### 反例定位與執行前 manifest

基準 `e4fac6ef`。唯讀上述成功第 5 輪的原生 request／公開工具結果，發現模型在拆分前已讀到原大任務的完整內容與序號 2／4／6／8 的依據，其中出席成果清楚引用 8。下一次 `create_jd_task` 卻將新拆任務及含「指定資料夾」的成果只引用 `current_input`。後來模型重讀 2／4／6／8，仍只核對兩項舊任務，沒有補上新任務來源。這不是來源未提供、工具保存掉資料，也不代表內容捏造。

角色指引已有出處原則，先前加「保留來源」句未穩定改善，本片不重試相同假說。三種 Source 選項本身仍缺 description；**候選假說**是模型將 `current_input` 選項誤用為整輪已知資訊。只補三個來源選項的語意：本次一則原話／歷史指定發話／固定 Memory 物件；不加新工具、例外驗證器、自動補引用、固定工具順序或 reviewer。這是待測解釋，不宣稱已查明模型內部原因。

依 [OpenAI 函式說明建議](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)將容易誤用的語意放在參數附近；[GPT-6 提示指引](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)要求在選用模型及實際負載驗證。官方並未保證加 description 必定改善，也提示範例可能反而傷害 reasoning 模型表現，故本片不堆範例或照抄工程代理自主權限。

- 只重播隔離合成 request：184 items、14 tools，原件 SHA-256 `d16389f573d8f3ca82ff0e2efc50db27a8a973047a487acb690b8d53fc60e931`；不改歷史、主指引或模型設定。兩組均改非串流、output 上限 8,192，維持 Luna／high／all_turns、store=false。
- 基準／候選交替各 2 次；至多 4 次 count＋4 次 model，單請求 120 秒、零重試、串行。input 上限 70,000 tokens、總費用預留 US$1；任一外送失敗即停，不重跑旅程。不執行返回的業務工具、不寫業務 DB、不操作 Demo。
- 觀察跨來源任務／成果是否保留真實依據，也檢查其他內容／來源不因補引而錯配；若改為先讀取，記為尚不能判定，不能把「沒有犯錯」當作已完成編輯。不用唯一工具序列或正文逐字一致評分。
- 只在有改善時才納入唯一 schema 並驗生成／接線及原局部更正反例；沒有改善就不採用。此為自然模型的有限品質比較，非單元 TDD 或普遍可靠性證明。原件寫入 ignored `source-scope-20261001.jsonl`，獨占建立避免無意重跑；腳本 `probe_source_scope.py`。

### 實際結果：未採用候選，不追加重跑

外送前核對固定 request hash、隔離合成 job、五則員工輸入逐字等於既有合成素材及五份 App 參考資料；沒有私人訪談或憑證輸出。完成 4 次 count、4 次 model，沒有執行返回工具或寫業務資料。

| 試次 | 變體 | 實際行為／判斷 | input／output tokens |
|---|---|---|---|
| 1 | 原說明 | 只讀協作對象；尚未觀察到編輯，不判通過 | 49,412／3,507 |
| 2 | 三種來源補 description | 同樣只讀協作對象；尚未觀察到編輯 | 49,694／4,775 |
| 3 | 原說明 | 修改既有任務、建立技能；新合併要求仍只引本次輸入，未證明跨輪來源問題消失 | 49,412／4,726 |
| 4 | 三種來源補 description | `incomplete`，8,192 output 全為 reasoning tokens，沒有可執行呼叫；不算品質通過 | 49,694／8,192 |

本片只是自然下一 Step 比較，不執行工具續跑整個 Turn；模型先閱讀是合法選擇。結果**不足以證明描述候選有效或無效**，依 manifest 不納入產品、不再自動加長上限或重播。試次 4 是本探針的輸出上限，不能由此推導正式產品的 Context 容量錯誤。按既有本機費率與已回報 usage 估算 US$0.018297665，不作供應商帳單保證。原件 SHA-256：`76d45370064a6e0ac8d1ad0d5110853024275c4070426c83132c88bff018039c`。

### B1／B2 實際 Context 與接線回歸

唯讀已完成合成批次 `2df56253-82c0-4afe-b778-539579ea7404` 的原生 stage request；排除只計量舊歷史的 preparation snapshot，避免誤判新資料遺漏。以下核對於本節末的指引修正**之前**執行，對照基準 `e4fac6ef`，不以新指引冒充過去請求。探針 `audit_memory_context.py` 零 provider 呼叫、零 DB 寫入。

- B1：4 份相異請求，78→101 items；本批 App 資料是情境 map（3 項）、必處理 9–10、顧問 9／員工 10 的原話。無理解 map、無 B2 私人歷史；6 項工具與現行定義全等。
- B2：6 份相異請求，93→123 items；本批 App 資料是情境 map（3）、理解 map（1）、3 筆上游變更概覽；沒有預載整批原話，仍有按需歷史讀取工具。8 項工具與現行定義全等。
- 每份請求的 instructions 與各自現行角色原文全等；`store=false`、high／all_turns、無 `previous_response_id`。App 資料均為 user，不升為 system／developer；各自原生 reasoning、工具呼叫與結果、assistant `phase` 保留。沒有把本次資料反覆新增到每 Step。此批沒有回交／壓縮，不冒稱其實際 provider 行為已驗。
- 首份 stage request SHA-256（排序 key 的 UTF-8 JSON，沿探針序列化）：B1 `beb84bf74c539c4067bf11abfb8ec012e6337485b53db71b6d34e68377789bb0`；B2 `78589592a21bcba6a6fed45e5d301085325117b0b6e05bcebed944124a1649b7`。

本次在 `apps/api` 執行 `./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_role_prompt_contracts.py tests/integration/test_consultant_context_binding.py tests/integration/test_memory_source_windows.py tests/integration/test_memory_parent_roles.py -q -p no:cacheprovider --tb=short`：**31 passed，11.72s**。PG fixture 只建立及清理本次隨機測試 schema，Demo 與既有旅程不變。覆蓋角色接線、A 固定資料／重連、B 取材上界及正常／回交續批，模型輸出為合成；不等於自然分析品質全部通過。

### 指引審查後的兩項小修

平行唯讀審查分開查 B1／B2 方法、模型工具文字；主代理核對原契約後只修兩項：

1. `revise_jd_item` 原說明「排序／移動另用 move_jd_item」與既有 `reorder_capability` 不一致。現在區分**任務內 K/S 引用順序**與**共用項目／明細順序、任務移動**，對齊 [JD 工具契約 §4.1](../../../specs/2026-09-29-jd-model-tool-contract-review.md#41-有限修訂動作與精確來源目標推薦設計待實作驗證)。不改 schema、實際操作或增加工具。
2. B1／B2 已有保留未知、局部補充不刪舊工作的要求，但未明述未解衝突不能以最後一句為準。各補一行一般判準，依 [工作分析指南 §4](../../../specs/2026-09-09-complete-work-analysis-guide.md#4-案例工作理解與-jd如何取捨而不丟失)區分時期／條件／更正，只改明確範圍，未解矛盾保留說法、來源與待釐清。不加固定回交、禁止正常更正或特定樣本答案。

沒有對「另有一人」再追加案例專用禁令，也不重複既有 B2 精簡規則。已保存的歷史請求不改寫；新指引適用後續新準備，既有恢復仍承接其原設定。

先新增公開工具文字與實際角色組裝的契約檢查：**5 failed、13 passed**，失敗均指向上述缺句；修正後連既有 wire／來源接線：**22 passed，1.62s**。命令為 `./.venv-target/Scripts/python.exe -X utf8 -B -m pytest tests/contracts/test_jd_item_revision_schema.py tests/unit/test_role_prompt_contracts.py tests/unit/test_jd_item_revision_wire.py tests/contracts/test_jd_source_actions_wire.py -q -p no:cacheprovider --tb=short`。五個受影響 Python 檔 Ruff check／format check 通過。

這是**文字契約缺口的修正與接線驗證**，不是證明自然模型更懂衝突或引用：沒有以字串 assertion 冒充語意評測，也沒有為文案小修追加付費長旅程。前述新拆任務漏依據、Memory 精確化及精煉問題仍列 T14 品質限制，未勾全項完成。

提交前獨立工程審查五份程式／測試差異，未發現須先修的權責或契約問題；審查未另跑測試，不計成另一份執行證據。

## 2026-10-01：來源參數選擇的模型能力診斷

### 執行前 manifest

基準 `ebc9bd10`。前一組補 description 的自然下一 Step 比較未證明改善，停止同假說加字。原件已證實舊任務及真實來源在 Context 內；本片改問一個有限問題：**現行角色與工具文字，在短而明確的新舊合成訪談下能否選對來源，換模型是否出現差異？**不是先宣稱 Luna 能力不足或切換產品模型。

依本次已搜尋並取得的 [OpenAI 模型選擇指南](https://developers.openai.com/api/docs/guides/model-selection)、[GPT-6 提示建議](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)，以相同工作負載比較，不由型號／宣傳推定效果。[GPT-6.1 Sol 官方模型頁](https://developers.openai.com/api/docs/models/gpt-6.1-sol)列支援 high 及 function calling；僅列為診斷對照，產品仍是 Luna。新請求不攜帶其他型號的加密推理，不測跨模型 reasoning 相容性。

- 兩個全合成案例：歷史出席工作＋本次新核對方法；歷史設備工作＋本次獨立的通知工作。後者用來檢查是否過度借用無關舊來源。各由 Luna／high、GPT-6.1 Sol／high 執行一次，最多 4 count＋4 create、零重試、串行。
- 共用現行 `CONSULTANT_INSTRUCTIONS` 與 `create_jd_task` 原 schema／description，只有模型不同。使用腳本化空 JD map 讀取結果與官方 [指定 function](https://developers.openai.com/api/docs/guides/function-calling#tool-choice)選項，隔離「填參數」；**不是自然讀取／規劃、既有任務拆分或完整 App 旅程**，不將合成讀取冒充真 DB 效果。只有訪談資料傳模型，評分標籤／判準不傳。
- store=false、all_turns，input≤16,000／output≤8,192、單請求120秒／整批600秒、預留 US$1。任一外送失敗、非 completed 或非單一指定工具回應即停，不自動加額補跑。官方標準費率以 [Pricing](https://developers.openai.com/api/docs/pricing)當日 Sol input US$2／output US$10 每百萬、Luna US$0.1／US$0.5 估算；實際 usage／帳單分開。
- 不執行返回工具、不寫 DB、不動 Demo、不改正式模型／設定。沿既有 parser 檢查 wire，語意另看正文與逐項來源，schema 有效不等於引用正確。只保存公開文字／參數、指紋與用量，無 opaque reasoning／憑證／原始錯誤。
- 腳本 `.research-tmp/eval/probe_source_model.py`、獨占建立結果 `source-model-20261001.jsonl`。若短例成功，只能排除「連基本選項都無法辨認」，不能消除長 Context 拆分反例；若模型間有差異，也先保留樣本限制，不直接採用新模型或新增自動補引。

### 實際結果與取捨

4 次 count、4 次 create 全部完成，零重試；各模型各案例只有一次，不估計成功率。四個呼叫均由現行 `parse_task_write` 接受；未執行業務工具。

| 案例／模型 | 逐項來源與正文審讀 | input／output tokens | count＋create 秒數 |
|---|---|---|---|
| 舊出席工作＋新方法／Luna | 任務引歷史 2＋本次；「老師交表、逐堂人數／缺席、指定資料夾、主管查看」成果引 2；新核對要求只引本次，未混淆 | 3,086／330 | 5.57 |
| 同例／Sol | 相同來源分工；將新要求分兩項，各引本次，合法等價寫法 | 3,086／614 | 15.19 |
| 新通知工作／Luna | 任務、成果、要求只引本次；沒有把設備清單舊事實／來源借入新任務 | 3,063／315 | 4.51 |
| 同例／Sol | 同樣只引本次，保留主管確認新教室及未回覆電話追蹤的界線 | 3,063／507 | 10.89 |

本表是工程代理依原話逐項核對，不冒充人類領域校準。這次短輸入約 3K，且強制建立指定任務，**與原 49K、184 items、多工具、拆分既有任務的自然執行不同**。兩者都能選對基本來源，沒有依據直接換模型、增加來源描述，或宣稱原拆分漏引已修復；也不能由短／長例差異直接認定 Context 長度是根因。Luna 本次沒有公開 commentary，Sol 有；強制呼叫的結果不取代自然串流／對話行為驗收。

事後對照 `read_recent_interviews` 發現探針的 `context_sequences=[1,2,3]` 把所有合成歷史列為前問脈絡；正式投影在本例 covered=0 時應是空集合。這是**診斷素材的邊界 metadata 不準確，不是產品 Context 錯放**。原話、說話者、正式序號本身及兩模型的可見資料相同，仍可觀察四次參數選擇，但不據此推導正式 Context 行為或模型優劣；不修資料後悄悄覆蓋／挑掉原結果，也不為此重付費。後續 App 品質驗證沿實際 owner 投影或完整保存請求，避免手抄正式邊界。

沿已回報 cache read／write／uncached input／output 分項，以前述官方費率估算四次 generation 合計 **US$0.02104171**；不是帳單，亦未證實 count 的計費。腳本 SHA-256 `15318886dc1e5ba9f776cdc53c2a1b32f2f299837985446a2a9eae1c923a94e1`；結果 SHA-256 `bc07dbc4d139943fd0aa5da3bc2121713711e7125dce60951bb1a1623f0d4f65`。各 request 指紋、公開參數與 usage 留本機原件；本批已關閉，不以重複短例堆 pass 數。

本片**不改產品 Prompt／Tool／Context／模型**；只更新證據和任務路由。下一個有價值的品質驗證須回到既有任務重組及逐項來源承接的真實負載，先選能辨別原因的單一變因，不再重做「基本來源會不會選」或相同 description 微調。未驗的知識提煉、Memory 精確化／精簡及完整旅程仍留原 T14／T17，不擴建 reviewer／來源自動猜補。T14／T16／T17 維持未完成。

### 讀寫責任與驗收範圍的後續審查

同一基準的程式追查確認 `jd_detail_projection` 在任務、成果、要求各自回傳其直接來源；`JdTaskWriteWorkflow` 在原候選交易中分別保存模型指定的來源，不因建立新任務就自動繼承父項或改為本輪。既有 `move_jd_item` 是保留身分的移動／排序，不是跨任務複製明細的工具。此為唯讀責任審查，不是新真模型證據；尚無依據改保存 owner、添加自動補引或新 copy 工具。

獨立工程審查同意：長歷史漏引仍阻擋相應品質驗收，但不要把 T17 全部長旅程塞回 T14。T14 已有方法／判準／素材與部分效果證據，未完品質仍明示；T16 wire／容量、T17 整體旅程及真人試點分屬原 gate，不以未觀察到知識欄位直接推定故障。停止同假說提示加字，本輪零新增 provider 呼叫，不改產品模型或已保存歷史；其他不受影響的交付接線可以繼續。

## 2026-10-01：長 Context 的來源欄位順序診斷

### 執行前 manifest

基準 `ac75493b`。原高推理旅程已證實模型讀到舊任務和來源，保存 owner 也依原呼叫保存；本片只檢查 **schema 先列來源、再列內容是否有幫助**，不再補來源說明或改訪談資料。唯讀比對本 execution 全部 request snapshot，確認 184 items 後至漏引呼叫前只有模型 reasoning items，沒有遺漏另一份更近的工具觀察；沿用原 `d16389f573d8f3ca82ff0e2efc50db27a8a973047a487acb690b8d53fc60e931` 請求。

依據及限制：

- [GPT-6 提示建議](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra#prompting-best-practices)要求檢查衝突指引並在所選型號／工作負載評估；該頁主要觀察 Astra，不直接推導 Luna 品質。
- [OpenAI Structured Outputs key ordering](https://developers.openai.com/api/docs/guides/structured-outputs#key-ordering)說明輸出與 schema key 順序相同，**沒有保證先產生來源欄位就能提高語意引用正確率**。
- [Anthropic 長 Context 建議](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)提出先定位相關引文再處理任務；只用來形成這次「證據先行」假設，不將 Claude 建議或欄位排序稱為 GPT-6 已驗證解法。

兩次自然下一 Step：原順序、來源欄位優先各一次；候選只將各工具 schema 的 `supporting_sources` property 移到同層開頭，欄位內容、required、主指引、歷史及工具選擇不變。保留全部 184 個原生 input items，Luna／high／all_turns、auto tool choice、store=false。兩組均非串流且 output≤16,384，讓本探針有足夠輸出空間；不改產品上限，也不把過去 8,192 上限結果冒充同條件基準。

上限：2 count＋2 create、input≤70,000、零重試、串行、每請求 150 秒／整批 480 秒、預留 US$1；外送失敗或未完整輸出即停止，不加額重跑。沿原素材逐字確認全合成來源後才讀憑證；不執行返回工具、不寫業務 DB、不動 Demo、不保存 opaque reasoning。只觀察返回的寫入意圖正文及逐項來源；合法先讀取仍屬未判定，不能算通過。

腳本 `.research-tmp/eval/probe_source_order.py`，結果以獨占建立 `source-order-20261001.jsonl` 保護；同記忽略 key 順序的內容指紋與保留順序的 wire 指紋，避免排序 JSON 的 hash 掩蓋本次唯一變因。若沒有可判定改善，就不修改產品 schema、不續跑更多同類探針。本片是有限非確定品質診斷，不是 TDD、正式旅程或產品通過。

### 結果與採用決定

兩次 count、兩次 create 均完成，零重試、零工具執行／業務寫入。原指引與現行 A 完全相同；候選只改 schema property 順序，兩組忽略順序的 request 指紋同為 `325c39c952fa3e4a8b3f7c697637ff73c91c8e8ea91536bf392550f6d5fd519e`。本次不控制隨機生成，單次觀察不能估計成功率或因果。

| 變體 | 實際返回的編輯意圖 | input／output tokens | count＋create 秒數 |
|---|---|---|---|
| 原順序 | 5 個呼叫；拆出的出席任務／成果仍保留「有開課的每天、老師交表、指定資料夾」，卻只引本次輸入，未納入來源 8 | 49,412／8,422 | 65.62 |
| 來源欄位優先 | 3 個呼叫；修改原綜合任務，未拆分，不能直接比較新任務的來源承接；新增明細僅描述本次事實，仍可只引本次。另產生 `job_wide_condition`、`work_environment`、正文 `q`，無有效工作依據 | 49,410／8,162 | 44.98 |

候選的明細／條件參數確實先輸出 `supporting_sources`，但八個呼叫全部可通過現行生成模型的 wire 驗證，仍含上述語意問題。這證明「schema 合法／欄位順序符合」不足以充當內容品質；**不證明排序造成 `q`，也不能因未做拆分就說漏引已修復**。候選組對既有任務加本次來源不抹除舊來源，本輪未執行工具，沒有建立新的正式 JD 或驗證完整 Turn 後是否修正。

**決定：不採用來源優先排序、不改產品 Prompt／schema／Context／模型，結束本假說探針，不繼續加字或付費重播。**按已保存的 usage 與本機 2026-09-30 Luna 標準費率（普通／cache read／cache write／output 分計），兩次 generation 估算 US$0.020644600；不是供應商帳單，count 計費未另證實。腳本 SHA-256 `7853396ebff8687122eaba9a090b0a7ebbadbd081add586fdd168092348e088f`；結果 `507e9762827f2a52b75561557b0fd817f26c04f56bcb1484d5aad1d9c63ba342`。兩組 ordered request 指紋留本機原件，沒有輸出憑證或 opaque reasoning。

使用者本輪要求的 Prompt／Tool descriptions／實際 Context 審查結論，應與前述成果一起讀：已修正的具體指引矛盾有原測試證據；已查請求未發現錯放資料或丟失舊來源；自然長歷史重組的漏引、Memory 不受原文支持的精確化／冗長仍屬品質限制。不要用新 schema 排序、固定 reviewer 或自動猜來源繞過它們。後續只在新的可辨別假說或實際產品反例出現時驗證，保留原 T14／T17 gate，不能把本次否決候選算成產品品質通過。

本輪僅改證據與任務路由；`git diff --check` 及兩檔 140 個相對檔案連結檢查通過，不為純文件重跑全產品。獨立唯讀審查核對後未提出阻擋性問題，同意上述不採用及因果／未執行邊界；它不是額外的模型品質測試。
