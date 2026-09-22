# H4 採用映射提交後審查

2026-09-13；JD-R002／OI-01、OI-02。受審提交 `2e243d15`／tag `jd-consultant-adoption-mapping-20260913`；產品基準仍是 H2–H3 已完成版本。本輪由主代理審查背景恢復／生命週期，兩位獨立代理分別核來源版本、已驗方法與完成窗口。**只查來源及修正文檔，沒有改產品碼、跑產品測試或呼叫 provider。**

## 1. 結論與施工範圍

**採用既有顧問、先补完成窗口的方向正確；原稿不能不修正就作完整施工指令。**五組文檔問題見下節，已回寫[採用映射](../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)、[接續計畫](../../plans/2026-09-13-jd-app-continuation-handoff.md)與[未解事項](../2026-09-13-jd-app-open-issues.md)。它們是尚未施工的設計／交接缺口，不是新 App 已發生資料損失的證據。

H2–H3 不重開；不新增產品需求、不重寫顧問、不另選框架。下一仍先做完成窗口 source port，先落實其具體介面與固定情境再施工。背景持久狀態的具體落點在背景接線前有限閉合，不以「不新增表」取代責任設計，也不據此直接批准新表。H4 整體仍未通過固定完整旅程，日常 AI 未啟用，ADR0074／0075 Proposed、production ADR0060 不變。

## 2. 發現與修正

下列行號是受審提交 `2e243d15` 的原映射位置，修正版行號可能改變。舊程式证據以 `git show 4f94fbfb:experiments/analysis-agent/...` 讀取，不以 checkout 的最新檔案代替固定來源。

### F1／P2：把 C 的只查回政策套到全部 B1／B2，並先禁背景狀態落點

- 原位置：映射 §3.3–3.4（61–64 行）、§6 第4項（91行）。
- 反例：B1 已存第一個窗口、第二個窗口尚未完成時，本來沒有 publication receipt；舊 `ExtractionWorkflow._resume` 會以同一原 config／已存窗口／剩餘更正次數 `invoke(None)`。B2 `resume` 同樣保留原工作，stale 後帶入新 C 更正的來源及剩餘模型／工具預算。只准查 receipt 就會把既有可續作工作變成無法完成，或迫使接手者另造重啟方式。
- `scheduling.BackgroundRow` 保存 target/source、status、error、recovery_count；`BackgroundAvailability` 讓本輪知道整理受阻。新 `ManualRuntime.close` 目前只排空人工、前景與登記讀取，`ManualHost.close` 隨後就關 Store／Saver。前景 owner 並不自動提供背景持久狀態或新程序續作。
- 修正：C 原政策不變；B 沿既有有界原生續作與同意圖冪等發布。背景共用宿主生命週期，需明列准入、原工作、預算、錯誤、停止／重開與可用性責任。不搬舊全域鎖／整套 host，不把背景硬放入前景手改門閘；也不先禁掉一切最小准入表或框架喚醒機制。
- 狀態：錯誤限制已從文件移除；新背景狀態落點及跨程序接合仍是 H4 必做設計／驗證，不是本輪已實作。

### F2／P2：漏接已驗整理通知，將工具清單數誤當不可改上限

- 原位置：§2 sources／scheduling、§5「十五工具」（75行）、§6（88、92行）。
- 原證據：`consolidation_request.py:16–48` 的 `request_memory_consolidation` 是無參數純通知；`has_saved_request` 以真正且不歧義的原 call/result artifact 辨識。`sources.py:49–78` 的待整併清單只選安全收尾且有此通知的回合；`scheduling.py:156–161` 在沒有通知、也未達明示字數後備時不啟動新批次。CT51 的兩組自然續談都自行發出通知。
- 影響：只接 source／B 而不接通知，就沒有原已驗的自然觸發；若把終局直接當請求，又會變成每輪整理。兩者都偏離既有訪談节奏。
- 修正：補通知、`MEMORY_ACTION_GUIDANCE`、結果驗證與安全收尾後辨識的映射；不讓 LLM 填 ID／窗口／排程欄位，不以通知聲稱已更新 Memory。十五只是 H1–H3 工具清單的現況數字，不是 H4 的產品上限。
- 狀態：映射已補；真正工具註冊、分類及固定 wire／停止驗收仍待施工。

### F3／P2：把未驗的後續 JD 增量與已驗 A 指引／三項分析 Skills 一起排除

- 原位置：§1（20行）、§2 host 不採用列（34行）、§5（75–84行）。
- 原證據：`4f94fbfb:api.py` 的 `AnalysisService(instructions=...)` 含未知不反覆追問、主體／條件保留與收尾方式；同版 `service.py` 接 `SkillAssets`／分析 Skills middleware。`work-scope-interview`、`compare-work-patterns`、`outcomes-and-expertise` 已在 CT49 之前存在；後續主要是接上 JD 尾句，不代表整份 Skill 都未驗。
- 影響：照原表只讀新的 JD 文件，可能漏接或重新寫過已完成的訪談方法，與「採用既有顧問」矛盾。
- 修正：已驗 A 指引、三項 Skills、按需載入與唯讀路由各有落點；舊「目前不製作 JD」等範圍句單列必要差異。後加 `write-customized-jd` 不整批採用；新 JD 方法另依現有完整 JD 研究映射。
- 狀態：映射已補；實際 system／Skill 與載入工具仍須接合驗證。沒有趁本輪修改 B1／B2 prompt。

### F4／P2：source port 缺少 B1 真正使用的引用／讀取契約與終局條件

- 原位置：§3.1（42–52行）、§6 第1–2項（88–89行）。
- 原證據：B1 `start` 直接呼叫舊 `parse_reference`；`_source` 需要分頁 `segments / turns / omitted_content_types / next_offset`。新 App 的來源引用使用簽章，`MemorySourceReader.read` 只供 `SourceExcerpt(messages)`。因此只增窗口切分函式仍接不上；不能搬舊無簽章 parser 或另發一套引用繞過驗證。
- 新 `_settle` 核效果後的 terminal run record＋`observed.closed` 可作安全邊界；此方向沒有找到反證。但需逐輪確認同一固定祖先鏈，而非只看最新終局。安全收尾的 failed／cancelled 仍保留員工已存原話，以 `answer_succeeded=false` 投影；終局不等於回答成功或請求整理。
- `processed_source` 已由 publication head 保存；新 source port 缺的是比較／覆蓋語意，不是再建游標權威。B1 已處理工作位置、B2 發布游標、語意請求分開。
- 修正：補來源 interface／adapter、簽章驗證／解碼、角色與分頁、重抽原窗口、未安全收尾不可跳過、缺鏈／超256祖先／消歧超量明示失敗。先做有限契約與案例，不建第二原話庫、不在此重寫所有長歷史策略。
- 狀態：映射要求已補；具體介面是下一施工單位的第一項交付，不冒稱已設計或驗證完成。

### F5／P2：角色配置寫法可能把 B1 改成另一個工具 Agent

- 原位置：§4 配置列（70行）。
- 原證據：CT50／CT51 的 A、B2 為16模型步／15工具呼叫；B1 是 structured extraction graph，`max_windows=16`、`max_validation_corrections=1`。三者 high、顯式輸出8192；B1 類別預設4096不等於驗收入口的設定。
- 修正：按角色列限制，保留 provider／budget 接點及显式配置；不把「15個可用工具」「15次工具呼叫」混為一談。換 provider／加入 JD 後的自然品質仍須新驗收。
- 狀態：配置語意已澄清，尚未接新 App 的 B1／B2。

## 3. 可保留的來源判定與文字勘誤

1. 顧問採用 `4f94fbfb` 的判定合理。13個 Memory 模組在 `309eaf21..033540ce` 加起點逐 commit／逐檔 blob hash 各只有一種，`adoption.json` 既有來源與 hash 不須因本次審查改指。
2. 2853 是該区間 `src` 的新增行數，另有83刪除行；不是整份已驗顧問都不採用。CT50「3檔8行」指 `src` 的替換量，整個提交另有文件／測試。
3. `622e548d` 是 CT51 8K／16K紀錄，原稿誤稱 CT50。CT51 維持8192，這個名稱修正不改配置結論，也不要求重做容量實驗。
4. 既有 B2 已有 stale 與 `RECENT_REPAIRS` 保護；需要的是新 adapter 的配對驗收，不能稱原顧問從未處理。CAS 只保護發布基準，不能單獨證明內容沒有蓋回新更正。
5. CT49 證明原訪談／Memory 的限定自然能力，不是完整 JD 產稿驗收。「最新原話也要用於 JD 收尾」是新接點需驗的採用要求。

## 4. 官方依據、版本與界線

查閱日期：2026-09-13。新 App lock：LangGraph **1.2.11**、LangChain **1.4.0**；免費開源核心 MIT，沿目前鎖定版本，沒有升級或採用託管服務。本輪只核 native continuation／冪等的已存在契約，沒有新增 LLM 提示策略；模型與方法依 CT49／50／51 固定來源及既有 OpenAI／Anthropic 研究，不把本次文檔修正包裝成新模型共識。

| 官方來源 | 官方事實 | 本案使用與限制 |
|---|---|---|
| [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | checkpoint 保存執行狀態以支援故障恢復；同 super-step 中已保存的成功节点結果可在續作時使用 | 與舊 B 的原生 `invoke(None)` 實作相符。不是承諾任一失敗節點內副作用都不會重跑；原 request、receipt 及預算仍要核對。現行核心文件，所用基本 API 無 preview 標記 |
| [AWS：Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | 重試需辨識同一請求意圖並維持冪等語意，對結果不確定的操作尤其有用 | 支持沿原工作／原發布請求查回，並不支持把所有 B 都禁止續作，亦不規定本案必須用幾張表。Builders’ Library 設計文章，非採用套件／無套件授權或 preview 版本 |

跨來源共同原則是保留可核對的原意圖、持久進度與已發生效果；**C 與 B 要採不同恢復政策是本案已驗行為的映射，不宣稱 OpenAI、Anthropic 或 AWS 規定同一流程。**沒有因單一產品做法新增本案需求。

## 5. 本輪證據與後續

- 唯讀核對：受審提交四檔差異、固定 CT 原碼、13模組逐 commit blob、App 現行 source／run record／owner、既有完成與節奏文件；兩份獨立審查與主代理交叉確認。
- 文件驗證：修正差異與空白檢查通過，四份責任文件的80個本地連結均可解析；入口／計畫／唯一 OI 清單一致。兩位非作者對各自發現再做窄複核，均無剩餘阻擋。產品測試、真 DB、真模型均未執行，不借用實作者舊測試數字當本輪通過數。
- 本輪只修文件；H4 source／B1／B2／背景／指引的實作與完整旅程仍未完成。後續沿採用映射 §6，不重做 H2–H3，不加歷史選輪 UI、不改 JD 格式、不啟用日常 AI。
