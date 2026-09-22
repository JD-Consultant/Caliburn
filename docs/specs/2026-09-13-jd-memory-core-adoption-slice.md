# JD 顧問：既有 Memory 核心採用

2026-09-13；JD-R002／OI-01、OI-02。隔離施工，正式產品 ADR0060 不變；ADR0074／0075 仍 Proposed。沿[計畫](../plans/2026-09-13-jd-relational-app-implementation.md)及[既有成果接點](evidence/jd-consultant-source-integration/memory-seams.md)，接續已完成的當輪原話來源。

## 目標與本次接合

讓既有 Memory 的詳記、工作理解、導覽及發布規則成為新 App 可直接依賴的模組，接上新原話 owner；不再透過 worktree 或研究套件 import。完整目標仍包含顧問讀取、即時修補與背景整理，本次依相依順序先落可保存／發布／固定版本讀取的核心，接著接模型工具與宿主生命週期，不用這一段 PASS 代稱完整 Memory 已接。

核對舊測試 checkout `033540cef870d1f92baa5c69133a799231c46d48`：`memory.py`、`publication.py`、`references.py` 不依賴 JD 或 AnalysisService。其餘來源程式綁舊 root／Responses，不能直接移植；B1/B2／C 的完成判定及背景範圍依舊有界接合，不刪除它們的完整性檢查。

## 模組與資料責任

- 新 Python 套件 `packages/consultant-memory`（import `caliburn_memory`），標準 pyproject／Hatchling，主 App 用明確本地套件依賴。保留三個已驗核心的 StoreBackend、不可變 artifact、新版本準備、完整 readback、SQLAlchemy head CAS 與同交易 receipt；記錄原碼 hash 及實際調整，不重寫一套 Memory 引擎。
- 只分離真正會改變的来源依賴：小型 `SourceReader` 埠提供 `document_id`、`validate_reference(ref)`、`read(ref)`。前者只驗來源身分／形狀，不讀 DB；後者真讀固定原話。`PublicationStore` 經 artifacts 驗來源，不再 import 舊 parser。原回執優先，不因來源暫不可讀就重新發布或重建操作。
- 新 App adapter 綁同一 `ConversationSourceService`。來源 owner 自行發出可辨識的 `conversation:` 加 signed opaque token，讓既有 CommonMark 引用核對不漏掉來源；不是舊四欄 base64 位址，也不是 JD 重簽 alias。之前已保存的裸 signed v1 refs仍能原樣讀回，查回操作不改寫字串。模型照抄 App 發配值，不負責組裝。
- Memory 內容留官方 Store；目前版／回執留原兩張發布 metadata 表。原 `q019-memory` namespace 與表名只是既有元件識別，本次不為改名搬資料。沒有第二份 current Memory、原话或 JD；修補不前進背景 processed-source，JD 撤回不改 Memory。
- 新 package 不含 provider、舊 SourceReader、service／API、排程器或通用 repository。核心沒有模型呼叫；B/C 真正模型與原生 Saver 接線在其相依工作完成時導入，不把任意未知工具標成 read-only。

## 官方依據與取捨

查閱日 2026-09-13。這些支持責任與接點，不代表所有大廠使用本案表名或三層 Memory；保留精確已驗版本，不為「新」而無據升級。

| 來源 | 官方事實／本案映射 | 適用版本、授權及限制 |
|---|---|---|
| [AWS ports／adapters](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html) | 將業務與技術依賴分開；本案只抽實際需要替換的原話讀取埠，不增加通用分層或微服務。 | 現行 Prescriptive Guidance；AWS 文件條款，不是可執行框架。 |
| [Deep Agents backends](https://docs.langchain.com/oss/python/deepagents/backends) | StoreBackend 可用 LangGraph Store 保存；不需把 Memory 寫到使用者電腦檔案。 | 已驗 0.7.13，MIT，套件仍標 Beta；本次只採既有公開 backend，有限版本驗證，不啟用 hosted／shell 功能。 |
| [LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores) | Store 與 checkpoint 各有保存責任；持久 Store 初始化明示執行。 | LangGraph 1.2.11、Postgres 3.1.2，MIT；本案無向量索引／TTL，原話 checkpoint 不清除。 |
| [OpenAI 工具最佳做法](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions) | App 可推導的參數由程式處理；工具定義需清楚說明結果與使用時機。 | 現行官方 API 契約，商業服务條款；來源身分、版本及 operation 仍由 App 處理。 |
| [Anthropic Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) | client 負責執行及保存，模型可透過工具反覆讀／修。 | 現行官方工具契約，商業服務條款；不表示需要沿其固定工具名稱或它指定了 DB schema。 |

## 失敗、驗收與後續接合

保存 artifact 失敗不發布；CAS 失配不覆蓋晚期修正；COMMIT 結果不明查原回執，不以未回覆當未保存。來源格式、scope、不可讀與真內容變更分清；未驗語意不宣稱核實。

驗證順序：帶入已驗核心的來源／固定版本／發布反例，測真 StoreBackend；新 App 原話建立詳記→準備 Memory→發布→後續修補→原版與目前版讀取；原回執重取不倒退 head、修補不前進 processed-source。套件必須能獨立 build/install，不能因測試的 PYTHONPATH 指向研究路徑而假通過。

宿主 Store connection、明示初始化、exact schema profile、備份還原及全部 Memory 工作排空是後續必接，不能在一般 open 偷呼叫 setup。新版來源目前只涵蓋當輪／前問，B1完整未處理窗口尚需接既有規則；不得把當輪來源當全部待整理內容。模型／自然品質／來源 UI 仍在原成品範圍，0付費規則不變。

## 實際結果與下一接點

已完成 [獨立套件](../../packages/consultant-memory/README.md)、[原碼採用紀錄](../../packages/consultant-memory/adoption.json)及新 App 的 doc-scoped source adapter。核心 **44 PASS**；來源／context **71 PASS**；受影響接線 **113 PASS**；真 PG 縱向 **1 PASS**；獨立 wheel 安裝／隔離 import／保存發布通過。[整合結果](evidence/jd-memory-core-adoption/integration-results.md)分清測試層級、重疊、首敗及修正；[独立審查](evidence/jd-memory-core-adoption/review.md) **98 PASS**，限定範圍無 P1／P2。

只為真 PG 驗證明示建立專用 `jd_memory_core_test` 的官方 Store＋原發布四表；public JD／Saver 與日常 host profile 不變。模型工具數／provider 呼叫未增加。此結果證明既有核心能用新來源保存、修正、查回與重開，尚非完整顧問接合。

下一先接同宿主的 Store 資源、明示初始化及排空，確保讀取／修補與背景整理有同一份可恢復 Memory，再接原生模型工具與既有專業指引。B1/B2 完整未處理來源範圍、C 修補、背景整理的 provider 完成判定逐項接實際責任；不拿当輪來源充作全部訪談。問題仍集中原 OI 清單，不新增舊對話選輪 UI。
