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
