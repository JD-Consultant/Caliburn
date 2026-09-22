# Memory 更正核心：官方 patch、完整發布與原結果查回

2026-09-13；JD-R002／OI-02 局部；基準 `7d3f474a`。本次將已驗 Memory 修補形成新 App 可依賴的獨立套件能力，修正採用前發現的三個保存／錯誤缺口。沒有新增 Memory 表、App 頁面、模型迴圈或通用恢復引擎；日常 `enable_chat=False`、零 provider，ADR0074／0075 仍 Proposed，production ADR0060 不變。

## 完成效果與界線

- 以 OpenAI SDK 的公開 `apply_diff` 修改原生暫存中的 knowledge／guide；一個 diff 完整成功才寫入暫存，兩檔與引用全部合格後才由既有 PublicationStore 發布。
- 模型可修的格式／地址問題與來源／儲存故障分開。未知 I/O 停止，不回傳原診斷給模型，也不暗示改寫 patch 能修好服務。
- 結果遺失時，只拿原生已保存的 `PublishRequest` 查原回執；同一 operation 帶另一份內容不能借原成功結果。查無回執仍未知，不重播 patch、prepare 或 publish。
- 修補不推進背景處理游標，不改原話或 JD。較晚背景版已生效時，回覆分清原操作 `applied_head` 與明示讀取 `head`；不倒退目前 Memory。

**完成的是可安裝的 C 核心及新來源錯誤接點，尚未把 C 掛到新 App 的模型工具／原生收尾。**App 的原 call binding、取消與未知結果門閘、同輪讀取更新，以及 B1／B2、專業指引仍依[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)續接。固定 native／SQL 測試不是自然模型理解或完整成品驗收。

## 採用依據與分工

查閱日均為 2026-09-13；精確 SDK 原碼、wheel hash 及首敗由[patch 證據](evidence/jd-memory-repair-core/patch-results.md)負責，原模組與新檔 hash 在[採用清單](../../packages/consultant-memory/adoption.json)。

| 依據 | 官方事實／版本與限制 | 本案映射 |
|---|---|---|
| [OpenAI patch harness](https://developers.openai.com/api/docs/guides/tools-apply-patch) | 官方提供 SDK `apply_diff`，App 負責真正操作及回報。採已發布 `openai-agents==0.22.0`、MIT；不是未鎖定最新版或長期支援承諾。 | 只用純文字轉換，不啟動 Runner／client。沿既有兩條 Memory 路徑與單一 diff body；不複製 matcher。 |
| [Anthropic text editor](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool) | 精確替換及行位置操作仍並存，執行與工具結果由 App 負責；API 工具契約不是本地開源函式。 | 不把 line／exact replace 宣判淘汰；本案沿已驗 SDK patch，模型使用真 context，不能把套用成功當語意位置必然正確。 |
| [LangGraph 子圖](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)、[checkpoint](https://docs.langchain.com/oss/python/langgraph/checkpointers)；[Deep Agents backend](https://docs.langchain.com/oss/python/deepagents/backends) | 採已發布 LangGraph 1.2.11／Deep Agents 0.7.13、MIT。子圖沿父 Saver，StateBackend 保存 graph 暫存；公開 snapshot 與真正重啟要分開驗。 | 保留 `seed → edit → validate → save → prepare → publish`；不用第二份對話或自製 workflow。SDK latest overlay 與固定 checkpoint 的差異以真 PG 結果記錄。 |
| [AWS 安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | 同 request ID／不同意圖應拒絕；操作與防重紀錄須原子保存。官方現行工程文章，非套件或特定 schema 規定。 | 沿既有 receipt／CAS；對帳比原 request digest，查回不執行。永久保留策略、Memory head 及本案表名不是大廠共同指定。 |

共同原則是 App 執行與誠實回報、保留原操作身分及避免未知結果造成重複副作用。六節點、兩路徑、1–8 patches／12000 diff 字元、原請求對帳 API 是本案具體取捨，不稱為所有大廠相同實作。官方 matcher 的 first-match／空白 fallback 與 advisory anchor 限制仍在；已知限制靠原讀取 context 與實際模型驗收核對，不默默新增唯一定位器。

App 接線時分工如下：模型只提供修改內容 `path`／`diff`；App 從已保存原 call 決定 operation／base／source，管理同一前景工作及實際停止證據；C 子圖暫存與驗證；既有 Store／PublicationStore 保存內容、原子發布與回執。原始對話仍屬 ConversationSourceService／Saver，Web 不重算 Memory 規則。

## 三個缺口的有限修正

[採用前核對](evidence/jd-memory-repair-core/runtime-preflight.md)保留原反例；[獨立審查](evidence/jd-memory-repair-core/review.md)確認 CR-R01／02／03 核心 CLOSED。

1. `RepairWorkflow.reconcile(request: PublishRequest)` 核對完整原請求及回執；不再接受／回傳 caller edits。回執證明發布內容，不能單憑回執證明某段 patch 文字。App 後續必須使用原生已保存工具呼叫，不能重新構造它。
2. `_validate` 只將 `StagedMemoryValidationError` 回作可修內容錯誤。SourceReader 新增 `InvalidSourceReference`；App adapter 只轉原 owner 的 `invalid_ref`，既有 read_conversation 兩條入口同步處理。未知 ValueError／OSError／source_not_available 繼續停止。
3. 正常發布與查回均核 applied／current 同文件，且 current 至少涵蓋 applied。缺目前版或讀到落後版本時不給成功的讀取更新；合法較晚背景版仍允許，原 applied 結果保留。

## 實際驗證

範圍重疊的測試數不相加；原測試输出及首敗另見各證據頁。

| 驗證層級 | 實際結果 |
|---|---|
| 套件完整離線回歸 | **124 PASS／14.95s**；包含官方 patch、原生 staging／子圖、InMemorySaver／Store、SQLite 發布及既有 Memory／publication／只讀工具。 |
| App 來源適配與 staged 分類 | **51 PASS／15.29s**；新 typed 地址錯誤、未知來源故障不降格、原話與換行續頁。 |
| 受影響 App 回歸 | **90 PASS／12.90s**；原來源、固定 Memory context、讀取中斷／收尾及 managed App。 |
| 獨立審查 | patch／staging／source **73 PASS／15.14s**；repair **32 PASS／13.29s**，分批執行，沒有新增 P1／P2。 |
| 真 PostgreSQL／原生 Saver／Store | 作者最後 **1 PASS／8.01s**；root 獨立同案 **1 PASS／14.90s**。兩檔 patch、原 request、提交回覆遺失與新連線查回；JD／原話不變。這是同一情境兩次驗證，不相加為兩案。 |
| 封裝與來源隔離 | offline build 成功；`python -I` 從 wheel 載入修補模組，封鎖 socket 及 HTTP client 建構仍可執行純 patch。未載入舊 analysis_agent 模組，零 provider。 |

真 PostgreSQL 的兩檔修改、發布回覆遺失、原生固定 request 與新連線查回，由[整合結果](evidence/jd-memory-repair-core/postgres-results.md)記錄。這是核心 nested graph 的持久化，不等於新 App 已有 C 工具／取消收尾。

root 最後合成 document 為 `c8ee91e8-5954-4aec-ac11-9f011f211cca`、repair thread 為 `538c8c32-9abe-46f1-94aa-1e79a3e62df3`；實際 Memory head3／applied2／回執3／patch2／JD head1，provider0。

首敗分開保留：新 patch 模組／SDK 尚未準備時的 collection errors；原錯誤分類／head 與 reconcile 行為反例；真 PG 測試對 latest overlay 的錯誤假定。Root 首次 wheel smoke 將來源 docstring 中的 `analysis_agent` 字樣也視為 import，故 assertion 失敗；改為檢查 AST import 與實際載入模組後通過，沒有刪掉來源說明或改產品掩蓋錯誤。offline lock 首次因未快取 SDK 失敗；只取得公開固定套件後 frozen sync 成功，新增八包、既有版本零升降。

已核 standalone wheel SHA256：`8f83a05812ac5991237adb3f679ebcf2980cb88549793622e13d5395e557ef58`。沒有本輪新 Windows 程序、真模型、自然訪談、真人操作或 UI 驗收；不引用前輪測試當本輪已重新執行。

## 接續與停止廣搜

目前核心採用所需官方能力及反例已足夠，不重選 matcher／Memory 保存架構。接下來沿[最小接線點](evidence/jd-memory-repair-core/runtime-preflight.md#新-app-必要接線沒有另造資料權威)將 C 接到既有 Agent、同 owner、原生 task／request 觀察及同輪讀取更新，再接 B1／B2／專業指引。未知結果保留原 pending，不能因已讀回 receipt 便假稱 App 已解除門閘。

UI 維持只需知道**當輪 LLM 改了哪些 JD**；不增加從舊對話選輪的入口。Excel 延後，其他未完成事項只在[收尾清單](2026-09-13-jd-app-open-issues.md)追蹤。
