# Caliburn Current Decision Register
**JD-R002／隔離編輯核心通過（2026-09-12，G7）：**Task6已保存3d0445ae；[整體審查及有限修正](specs/evidence/jd-editor-core-review/review.md)F1–3／R1–2 CLOSED，root接受。最後47 Web／86受影響Python／19真JD PG及build/types/lint、真Chrome恢復PASS，原Task6完整旅程證據保留、不累加。當前完成六切片核心交接／本地tag；**下一工作為P3離線費用防護與執行包、A1採用清單**。P3-B01仍OPEN／0產品provider；G6、P5日常維護（含R3/R4呈現Minor）、P6真人與自然品質、P7成品未通過。未merge／push。
**JD-R002／Task6已接受（2026-09-12，隔離G7）：**[完整固定旅程與結果](specs/evidence/2026-09-10-jd-editor-core-integration.md)及[獨立審查closure](specs/evidence/jd-editor-task6/review.md)通過；來源metadata、JSONB相等、終態讀取及途中手改保護已修正。620離線／156真JD PG／45真Memory PG、68原生／41 Web與建置檢查通過，真瀏覽器及API重開全值一致；不累加重疊案例。**當前gate：精確保存Task6，接整體跨切片review／tag。**0產品provider；Claude工程審查已獲持續授權，非P3自然測試授權。自然品質、G6正式接合、日常維護及真人驗收仍未完成。

**CT51／G5比較完成（2026-09-09，LLM-Q019）：**[8K／16K結果、官方依據與內容核驗](specs/2026-09-09-ct51-output-budget-results.md)。相同CT49起點、Luna high、提示/tools/compaction不變，兩組續談／B／回查均完成，35請求估US$0.05009506、closed；34來源頁逐段相等、舊資料／產品source不變。單次最高生成2229／2806，均未用滿8K；未見明確容量或品質收益，維持CT50的顯式8192，16K為本情境測過可用備選，不宣稱更聰明／普遍更省。16項邊界＋68離線測試通過，Docker／helper失敗與兩組措辭限制保留。無production/JD/default改動或merge/push；只有截斷／更大工作量或Owner選擇才重開容量採用，不重做Memory研究。

**CT49–50限定驗收完成／隔離採用（2026-09-09，LLM-Q019/G8）：**[完整11輪與來源驗收](specs/2026-09-09-ct49-fixed-long-interview-results.md)、[CT50設定／官方依據／真服務補驗](specs/2026-09-09-ct50-tested-profile-results.md)。接案前端全職位、含糊→確認、頻率更正、案例細節與原話回查通過；原文／8份詳記引用核對相等，獨立review無未處理重大finding。採A/B2 16模型／15工具；API預設Luna A/B1/B2 high，A/B2可覆寫；已測顯式輸出8192，native compaction12000。135請求估US$0.16871788，兩帳本closed；564離線＋41真PG通過。不是全職位普遍100%或medium4096保證。Minor導覽繞路、重複措辭與修補延遲保留；下一步可試用此隔離配置／有新證據再局部優化，不再為同能力重跑舊研究。無production／JD、merge/push；下方CT48及以前為沿革，舊失敗不翻成成功。

**CT48局部採用／長訪談G8仍OPEN（2026-09-09，LLM-Q019）：**[CT45–48結果、官方來源、實際內容及下一gate](specs/2026-09-09-ct46-48-edit-routing-and-budget-results.md)。背景B2採已測編輯指引、16模型／15工具，A仍12／11；沿框架計數／錯誤／resume，無新Agent/schema/matcher。原CT45八輪第8輪失敗不改判，xhigh未解；候選兩局部replay7及11模型完成（低於12，不能證明加cap是成功原因）。新增引用保留，但label過寬／案例位置兩Minor仍留。112次估US$0.17919779，CT45–48帳本closed、原PG未改。最終560離線＋41真PG通過。預設effort A/B2 medium、B1 high不變；本次語意測試high不能冒稱預設已穩定。下一gate固定新版完整訪談／補充撤銷／回查，毋須重做分層研究；不進production/JD、不merge/push。

**CT44局部採用／完整訪談G8仍OPEN（2026-09-09，LLM-Q019）：**[結果、官方來源、前後正文與完整帳本](specs/2026-09-09-ct44-preservation-results.md)。隔離B2採寫前保留未變子句提示及12模型／12工具上限；8模型對照沒收尾，12模型／11工具對照完成，主要既有細節與兩案引用保留，原PG未變。20次Luna high估US$0.04937714，24次／US$0.10帳本closed。A仍12／11；effort預設A/B2 medium、B1 high，不能將本次high語意測試當成medium通過。最終回歸558＋真PG41通過；G8仍須固定版新補充／撤銷及長訪談驗收。無新Agent／schema／工具／重試loop，不進production／JD。下段未授權、候選還原及8／12均為歷史；舊失敗不改寫，後續只補新證據、不重做廣泛研究。

**CT43局部採用／CT44待外部測試許可（2026-09-09，LLM-Q019）：**[CT43結果](specs/2026-09-09-ct43-read-routing-results.md)：回查改用既有summary path→原話resolver，兩次9/8額度失敗保留；12/11對照分別9、11模型完成，38次估US$0.02671177，closed。前景預設12模型／11工具，框架及計數／恢復不變；不全面high。[CT42](specs/2026-09-09-ct42-long-interview-results.md)空白11輪完成但舊未知仍存，high另漏兩項有效子句，G8 OPEN；105次估US$0.15032348 closed，不改原結果。[CT44計畫](plans/2026-09-09-ct44-preserve-unchanged-clauses.md)局部寫前刪除核對候選45離線通過，但兩次執行被工具安全審查拒絕外傳；0次CT44請求，候選封存、B2還原未採用。需明確許可這批合成訪談／Memory送相同OpenAI API，以Luna high最多24次／US$0.10續測；不要重做研究或绕過拒絕。不進production／JD、merge／push；其他局部優化依Owner委任，重大才問。

**CT41局部採用／G8仍OPEN（2026-09-09，LLM-Q019）：**[結果／官方依據／封存問答及帳本](specs/2026-09-09-ct41-memory-edit-freshness-results.md)。局部校準新鮮讀取、同事實一致性、小型導覽及既有write_file／SDK patch選擇；無新Agent／schema／儲存／重試loop。A/B2獨立effort預設仍medium，B1 high；試驗A high／B1 high／B2 medium。最後556離線＋41真PG通過；原11輪失敗保留，最後B2重播5次，新採購3輪及回查27次通過所測內容，不能稱完整穩定。226次估US$0.30844346，三帳本closed。R01修補前fresh read不保證、舊導覽冗長仍留。下一gate：CT42固定最後版從空白重走長訪談及只讀回查；不重跑舊對照、不進production／JD，重大改變才問。

**CT40局部驗收完成／G8仍OPEN（2026-09-09，LLM-Q019）：**[結果／來源／唯一新問題](specs/2026-09-09-ct40-normal-interview-results.md)、[逐輪訪談](specs/evidence/2026-09-09-ct40-transcript.md)。5輪真API／PG訪談、兩批自然B、一次空近期Context只讀回查；31次估US$0.03033571，帳本closed（agent自訂請求護欄30→40有先說明並留事件，US$0.15不變）。B1 high／其他medium接線、初次不確定保留、案例差異與未回答事項主要通過；C更新核准者成功，但新增雲岸同名段落未移除舊未知，回查建議再次確認，收尾沒有B，矛盾未修好。**CT40-Q01 OPEN**：先審就地更新／修補後回查，不增新機制、不全面high、不重開框架；本輪只測試／記錄，產品src/tests不變，7既有接線測試通過。舊Memory不動，不稱完整長訪談完成。

**CT39 current（2026-09-09，LLM-Q019）：**Owner 委由 agent 決定局部修正，已將 CT37 候選提示＋B1 high 接入隔離 app，主顧問／B2 medium；[本輪結果／引用／限制](specs/2026-09-09-ct39-extraction-adoption-results.md)及[計畫](plans/2026-09-09-ct39-extraction-adoption.md)。只改官方 model binding 與既有注入；無新增 Agent／schema／Memory 機制，不改 production／舊 Memory／C 停放政策。整體 G8 OPEN，後續做正常訪談品質驗收；CT38「待接入」是下方歷史狀態。

- 最後核對：**2026-09-08**
- 狀態：**目前決策與閱讀路由的唯一入口**
- 流程：[`decision-process.md`](decision-process.md)

**CT38最新入口（2026-09-08，G5局部完成／G8 OPEN）：**[B1 high→B2 medium及增量保留](specs/2026-09-08-ct38-high-extraction-medium-consolidation-results.md)。只升high的現行提示仍失真；封存候選high接現行B2 medium，及追加澄清更新主要檢查通過，措辭瑕疵／測試限制明列。13次估US$0.01693435、帳本closed，118離線通過；實際來源／引用及B1產物交付核驗完成。未改任何產品prompt／模型預設／舊Memory。下一gate：審隔離app採候選並只讓B1 high，主顧問／B2仍medium，再續訪談；CT35/C停放不變。下方沿革不得當作已採用設定。

**CT37最新閱讀入口（2026-09-08）：**[B1提示／medium-high局部對照](specs/2026-09-08-ct37-prompt-effort-comparison-results.md)。medium候選原例仍漏記，high相同輸入單例保留關鍵差異；不是B2／長訪談完成。候選已封存還原、預設不變；9嘗試／6完成、usage估US$0.0116942，未知預留保留，帳本closed。候選及還原各118離線通過。下一gate依[主repo register](../../../docs/current-decisions.md)審背景抽取high局部評估，不再重問Memory架構或復活CT35/C停放候選；下方是歷史路由。

**CT33最新入口（2026-09-08）：**[壓縮來源與漏存恢復核對](specs/2026-09-08-ct33-compaction-provenance-and-recovery-review.md)。唯讀追溯完成：CT32沿用的opaque出自CT16首次口頭更正但漏存的#16；當時仍有optional修補指示，現行CT25已無，且目前規則／revision 3導覽10日與六工具確有送達。不解讀opaque內容、不宣稱壓縮是根因。建議下一gate先審「現行規則首次更正」與「恢復舊漏存」分開驗證；保留長context與原失敗，不改產品，不追加生成。完成檢查／強制tool仍未核准，G8 OPEN。CT32結果不改寫，下方為沿革。

**CT32本輪結果（2026-09-08）：**[舊可見問答／壓縮延續因素對照](specs/2026-09-08-ct32-context-factor-isolation.md)。G5完成／G8 OPEN：visible_only 8次／7工具，首patch不匹配後重讀，正文及導覽只改10→5日；opaque_only 1次／0工具，答5但Memory仍10。共9次Luna／medium、估US$0.01421874，20次／US$0.10帳本closed。原42＋新2問答、詳記引用與重開保存核驗通過，77離線測試通過。未改產品／提示／工具，不能定罪compaction或直接停用；下一gate唯讀追溯壓縮生成輸入及目前Memory／規則的重新注入，再審局部方案。編輯介面停放，Stop judge／強制tool未核准。下方為沿革。

**CT31結果入口（2026-09-08）：**[四情境局部驗證](specs/2026-09-08-ct31-memory-routing-calibration.md)。G5完成、候選不採用、提示已還原。明確更正仍1次／0工具、答5而Memory10；已存正確與完全未發布兩反例不誤寫；含糊組試寫未確認，兩次裸`***` patch被拒後通知B，不能算先釐清通過或已修好。共10次Luna／medium、估US$0.01225069，20次／US$0.10帳本closed，原文／引用及重開保存核驗通過。無production／JD／B時機／工具變更，G8 OPEN。下一gate審CT30既有context隔離或完成檢查；不再疊同义prompt、不自行加Agent／強制tool。下方為沿革。

**CT30最新入口（2026-09-08）：**[§7即時／背景邊界與§6提示核對](specs/2026-09-08-ct30-missed-memory-write-official-controls.md)。Owner要求先分清更正時機；重新核對官方及CT24既有分工：OpenAI live update對已核實的過時Memory要求同輪final前寫回，不是收到更正立即重跑B；無已存目標的新資訊依既有B策略累積，已正確不重寫，未釐清先問。Anthropic支持工作中修訂，但未公開相同的精確時機規則，不稱完全共識。A2仍屬已存舊值卻漏用C，根因未定。下一gate審此邊界與§6局部候選，再選驗證；Stop／額外模型檢查未核准。G8 OPEN；僅研究記錄，未改產品／prompt或付費生成。下方為沿革。

> **CT29官方補證（2026-09-08）：**[研究入口](specs/2026-09-08-ct29-stale-memory-official-failure-patterns.md)。A2當前guide已給10日；OpenAI要求核實後同輪真正寫入、Anthropic公開相近過早完成風險，但未證明本案零工具根因。CT25已含聊天≠保存規則，不再堆同義提示。G2補證完成／G8 OPEN；下一gate為拆開舊可見回答與原生延續的診斷設定，本輪無付費生成或產品修改，未重開closed帳本。下方為沿革。

> **CT28對照完成（2026-09-08）：**[唯一結果入口](specs/2026-09-08-ct28-live-repair-context-contrast.md)。A1短context以7次模型／6工具完成修補，首patch多句號被拒、重讀後成功；正文及導覽10→5日、其餘完全保留。A2原延續1次／0工具，仍漏存。共8次Luna／medium、估US$0.01237055，帳本closed；來源及重開保存核驗通過。只支持延續context值得隔離，不定罪compaction／reasoning，不改產品／prompt／工具／B。G8 OPEN；下一gate審是否拆開舊可見回答與opaque延續做進一步診斷。下方為沿革。

> **CT27後續更新（2026-09-08）：**Owner已同意A局部context診斷；先追問Sandbox patch差異，本輪答覆及框架接點見[CT27§6](specs/2026-09-08-ct27-live-repair-no-call-evidence-review.md#6-owner同意a追問sandbox介面差異與是否學習)。不重問A方向；尚未改介面或執行測試，G8 OPEN。下方「審A」為前次沿革。

> **LLM-Q019隔離實驗閱讀入口（2026-09-08）：**有效入口在[主repo register](../../../docs/current-decisions.md)。最新[CT27官方／實際續談核對](specs/2026-09-08-ct27-live-repair-no-call-evidence-review.md)：CT17／19／22／26沿同一fixture、opaque及可見續談；尚未隔離第一次更正與舊歷史延續。官方SDK Sandbox是custom patch tool，本案共用patch applier不等於相同模型工具介面，但不是已證實零工具根因。下一唯一gate：審A局部context診斷，不改提示、模型或B策略。本輪僅研究／記錄，無付費生成；[CT26](specs/2026-09-08-ct26-natural-live-repair-validation.md)FAIL、closed帳本及G8 OPEN保留，未授權產品改碼。下方為歷史快照，production仍須正式gate。

> 本表不取代現行 code、`AGENTS.md` 或 Accepted ADR。它負責指出「現在什麼有效、什麼只是候選、下一步只處理哪一題」。Working Decision 若與 production authority 衝突，必須經 successor ADR 與實作 gate，不能直接施工。

## 1. 閱讀順序

後續討論者、reviewer 與實作者依序閱讀：

1. [`../AGENTS.md`](../AGENTS.md)；
2. 本表；
3. 本表指定的 current ADR／contract／design；
4. 只有需要查理由或重新驗證時，才讀完整 research；
5. 只有進入 implementation gate，才讀對應 plan。

文件標題出現「latest／final／approved」不會自動高於本表與 Accepted ADR。聊天內已同意但未寫回本表的內容，必須先補登記，才能被下一個工作階段當成 durable decision。

## 2. 全域治理決策

| ID | 狀態 | 目前結論 | Authority／依據 | 重開條件 | 下一個 gate |
|---|---|---|---|---|---|
| `GOV-D001` | `WORKING` | 重大研究、設計、review 與施工一律使用 [`decision-process.md`](decision-process.md)；本表是第一閱讀入口。 | Product Owner 2026-09-03 核准；AWS／Microsoft ADR 與 Google review 官方來源見流程文件。 | 實際使用證明流程造成重大阻塞、漏掉關鍵決策，或 Owner 改變治理方式。 | 將現有主題逐一登記；不回頭重寫全部歷史。 |
| `GOV-D002` | `WORKING` | 每輪只能有一個 blocking decision ID；鄰近但不阻塞的問題進 parking lot。每輪結束必須寫回 status、理由、來源、重開條件與 next gate。 | `GOV-D001` 流程。 | 同上。 | 所有新研究立即適用。 |
| `GOV-D003` | `WORKING` | `WORKING` 在被明確 supersede 前約束後續研究／設計；它不能越過 Accepted ADR 或現行 code 授權 production。 | `GOV-D001` authority 分層。 | Owner 調整 Working／Accepted 邊界。 | 架構翻案一律另開 successor ADR。 |

## 3. Memory 主題目前狀態

### 3.1 現在仍有效的邊界

| ID | 狀態 | 目前結論 | Authority／依據 | 重開條件 | 下一個 gate |
|---|---|---|---|---|---|
| `MEM-D000` | `ACCEPTED` | Production 仍依現行 code、`AGENTS.md` 與 Accepted ADR 0060；2026-08-30～09-02 的 Memory 研究沒有自行改變 production authority。 | [`adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`](adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)、現行 code。 | Accepted successor ADR 通過且對應 implementation／verification 完成。 | 在此之前只允許 research／design／明確隔離 spike。 |
| `MEM-D001` | `WORKING` | Memory 的唯一產品目的，是讓長訪談後的 LLM 仍能完整理解員工工作與必要細節，支援產出、修訂及最終檢查高品質 JD；Memory 本身不是產品目的，也不操控 JD。 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) 的產品效果；Owner 多輪確認。 | 完美 JD 的產品目的或 Memory 必要效果被明確翻案。 | 作為候選機制與測試的效果門檻。 |
| `MEM-D002` | `WORKING` | 一名員工對應一份隔離文件、一個持續訪談 thread 與一份 JD；目前不需要跨 JD 共用員工 Memory。 | Owner 明確裁決；[`specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md`](specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md)。 | 產品範圍加入跨員工／跨 JD 知識共享。 | 約束 scope／namespace 候選。 |
| `MEM-D003` | `WORKING` | 日常回合不必把全部長期 Memory 放進 prompt；但最後全面製作／檢查 JD 時，必須具備可驗證地處理該 JD 全部有效 Memory 的能力。所有員工工作都不得因摘要或召回策略而永久遺失。 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) §3.4–3.5、M3／M9。 | 官方能力或代表性實驗證明需採不同效果契約。 | 納入 `MEM-Q001`～`MEM-Q003` 與後續 isolated smoke 的驗收情境。 |

### 3.2 Memory reconciliation 決策

| ID | 狀態 | 目前決策／待決問題 | Authority／階段 | 重開條件／已有資料 | 下一個 gate |
|---|---|---|---|---|---|
| `MEM-Q001` | `WORKING` | 採用三層責任：LangGraph Checkpointer 保存每份 JD 的完整員工↔顧問 conversation 與 graph/run/interrupt state；PostgreSQL Store 保存可修訂 semantic Memory collection；Memory manager 只產生 extraction／consolidation 候選；每輪 model context 非破壞性地由兩層資料有界組裝。第一版不建立重複 employee-source 文字 leaf；如日後需要 provenance，只引用 canonical message ID。 | Product Owner 2026-09-03 核准；完整證據與三方案比較見 [`specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md)。 | 真 PostgreSQL contract 顯示長 thread 儲存／延遲不可接受；產品加入獨立 event query/export/retention；官方 primitive 改變；或 Owner 改變一 JD／一 thread 邊界。 | 持續約束 `MEM-Q002`／`MEM-Q003` 與 successor ADR；production 現在仍禁止依此施工。 |
| `MEM-Q002` | `WORKING` | 採 canonical conversation＋選擇性 consolidation：全部案例原始對話耐久保留；重複資訊 no-op；同主題通用新細節 update；需要獨立搜尋／修訂且會影響 JD 的重要差異才 add focused Memory；更正 revise、未解衝突保留兩邊；不採每案例固定一筆。長距離案例指涉必須可按需回查 canonical conversation。 | Product Owner 2026-09-03 核准方案 C；完整官方證據、三方案、A／B／更正情境與八項驗收門檻見 [`specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md`](specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md)。 | 代表性驗證顯示重要案例差異會靜默遺失、同義案例造成近線性膨脹、長距離原始片段無法找回；官方 primitive 改變；或 Owner 改變產品效果。 | 約束 `MEM-Q003`；production 仍須 successor ADR，現在不授權 schema、索引或施工。 |
| `MEM-Q003` | `WORKING` | 採修正後方案 B：Checkpointer 保存 canonical conversation；Semantic Memory／小型導覽先 routing，按需依 canonical message reference 回讀原始問答；未命中才做有界 exact scan／澄清。第一版不替每則 raw message 建 semantic index；只有代表性 smoke 證明重要久遠細節無法找回，才重開 derived raw-conversation／hybrid index。 | Product Owner 2026-09-03 核准；五家官方共同邊界、OpenAI Codex／Agents SDK 與 Anthropic 實際 read path、三方案與限制見 [`specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md`](specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md)。 | 官方新增原生 Checkpointer conversation search；isolated spike 證明 recall、成本／延遲不可接受；或 Owner 改變完整細節找回要求。 | **G4／G5：**收斂 Semantic Memory routing、canonical reference／read contract 與 isolated spike；production 仍須 successor ADR。 |
| `MEM-Q004` | `WORKING` | G4 read contract 採 progressive disclosure：先由小型、可重建的 Semantic Memory 導覽定向；需要更多內容時，模型使用 `search_semantic_memory(query)`，Runtime 在目前 JD／文件 scope 內回傳少量但逐筆完整、自成一體的 current Semantic Memory，以及輕量 `message_refs[]`；只有需要核對原句或問答脈絡時才以 `read_conversation_context(message_ref)` 深讀 canonical conversation。兩個 Tool 都只有一個 required string；scope／limit／filter／窗口／retry 由 Runtime 管理。第一版不另建 conversation summary。Isolated spike 只替 focused Semantic Memory 啟用 LangGraph Store semantic index／embedding；raw conversation semantic index 維持 deferred。名稱與最小結果視圖是 Caliburn mapping，不冒充 vendor 標準。 | Product Owner 2026-09-03 核准 read shape、isolated semantic-index mechanism、兩個 Tool 名稱及 Revision 2 G5 隔離實驗；官方、框架及 pinned contract 稽核見 [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) §3、§6。 | Isolated spike 證明自然語言 routing、canonical deep-read、scope isolation、成本或延遲不可接受；或官方 primitive 改變。 | 執行 G5 隔離實驗並回到 report review；不授權 production。 |

### 3.3 現有 Memory 文件如何使用

| 類別 | 文件 | 目前效力 |
|---|---|---|
| 產品能力基線 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) | `WORKING` requirement input；可用來判斷候選是否覆蓋效果，不授權 mechanism。 |
| 跨家官方研究 | [`specs/2026-08-30-agent-memory-landscape-and-decision-working-research.md`](specs/2026-08-30-agent-memory-landscape-and-decision-working-research.md) | Evidence library；需回到原始官方連結，不能把彙整文字直接當廠商內部事實。 |
| Caliburn 能力 mapping | [`specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md`](specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md) | Working analysis；產品需求輸入，不是 framework 決策。 |
| 最新機制重驗 | [`specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)、[`specs/2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md`](specs/2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md) | Evidence／diagnosis；供 `MEM-Q001` 定向核對。 |
| `MEM-Q001` 定向 reconciliation | [`specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，但仍不授權 production 施工，須由 successor ADR 承接。 |
| `MEM-Q002` 定向 reconciliation | [`specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md`](specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，只裁決相似案例細節、共同理解、consolidation 與長距離回查責任，不授權 schema／搜尋索引或施工。 |
| `MEM-Q003` 定向 reconciliation | [`specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md`](specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，採 progressive disclosure＋canonical evidence deep-read，不授權 production schema、索引或 tool 施工。 |
| `MEM-Q004` read contract／isolated spike design | [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) | **G4 complete／G5 authorized**；read shape、focused Semantic Memory semantic index、兩個 Tool 名稱與最小 contract 已核准，raw conversation index 維持 deferred；只授權隔離 spike，不授權 production。 |
| `MEM-Q004` isolated spike plan | [`plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md`](plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md)、[`specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md`](specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md) | **Revision 2／G5 authorized**；已從產品流程、責任層、Context、Tool contract、framework wiring 到實驗參數逐層分類，並修正持久 conversation 與暫態 tool state 混層、強迫 tool call、重疊 error handling及價格上界四項 finding；Product Owner 於 2026-09-03 核准執行，附帶「由廣到細均以可追溯共識為先、未討論自訂不得冒充共識」條件。 |
| 候選切片與 framework 選擇 | [`specs/2026-09-02-memory-foundation-vertical-slice-design.md`](specs/2026-09-02-memory-foundation-vertical-slice-design.md)、[`specs/2026-09-02-memory-framework-selection-revalidation.md`](specs/2026-09-02-memory-framework-selection-revalidation.md) | **PAUSED**；其中 substrate／authority 結論與後續討論衝突，reconciliation 前不可施工。 |
| Design review packet | [`specs/2026-09-02-memory-foundation-design-review-packet.md`](specs/2026-09-02-memory-foundation-design-review-packet.md) | **PAUSED**；原核准只適用當時候選，不能越過後續重開的 `MEM-Q001`。 |
| Isolated spike plan | [`plans/2026-09-02-memory-foundation-isolated-spike.md`](plans/2026-09-02-memory-foundation-isolated-spike.md) | **PAUSED**；保留內容，不執行。待 `MEM-Q003` 與後續 Manager／Store design 收斂後重寫或 supersede。 |
| Proposed Memory ADR | [`adr/0071-revisable-work-understanding-context-and-review-provenance.md`](adr/0071-revisable-work-understanding-context-and-review-provenance.md)、[`adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md`](adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md) | 仍為 Proposed／deferred；不可當 production authority。 |

## 4. Memory 下一輪 preflight

```text
Topic ID: MEM-Q004
Current stage: G5 authorized；isolated spike plan revision 2 開始在隔離 worktree 執行
Binding decisions: MEM-D000～MEM-D003、MEM-Q001～MEM-Q004
This turn's only blocking question:
  無；下一個 blocking gate 是實驗 report 是否支持後續設計，須待 G5 完成後由 Product Owner review。
Already reviewed evidence:
  2026-09-03 MEM-Q001 已核准 Checkpointer 是 canonical conversation owner；
  2026-09-03 MEM-Q002 已核准 canonical conversation＋選擇性 consolidation，
  並把長距離案例 search／read 列為必要效果。
  2026-09-03 G2 已確認 OpenAI／Anthropic／Google／AWS／LangGraph
  均把 canonical event list/read 與 semantic retrieval 分離；
  補驗 OpenAI Codex／Agents SDK 與 Anthropic 公開 read path 後，
  Product Owner 已核准 Semantic Memory routing＋canonical evidence deep-read；
  不再預設建立 raw-message search_text 副本；
  LangMem 官方有 create_search_memory_tool，LangGraph Store 也有 namespace-scoped search，
  但自然語言 similarity search 必須配置 embedding index；
  Product Owner 已核准 isolated spike 只替 focused Semantic Memory 啟用該 index，
  raw conversation semantic index 仍 deferred；
  LangGraph Checkpointer 可取 latest state／state history，沒有公開的 message-id 內容搜尋 primitive；
  Product Owner 已核准 search_semantic_memory(query) 與
  read_conversation_context(message_ref)；兩者只暴露一個 required string，
  其餘已知 scope／policy 由 ToolRuntime 注入；
  框架已覆蓋 typed validation、tool loop、Store search、retry 與 transient context projection，
  只有 exact-scope guard、canonical message window 與安全結果整形保留為薄 adapter。
  最終稽核已確認 read-tool graph 應為不掛 checkpointer 的單次暫態 execution，
  不把 tool chatter 寫回 80 則 synthetic canonical conversation；
  live prompt 不再直接命令工具順序，而由需要精確原話的任務驗證 search／deep-read 選擇；
  expected tool errors 統一走一個 typed ToolNode handler；
  provider 價格無法建立保守上界時不發第一個 paid call。
Out of scope / parking lot:
  production Semantic Memory schema、Manager prompt／mutation schema、Reference RAG、production migration、
  UI、JD 編輯器、跨 JD Memory、raw-message semantic index；
  production embedding model／top-k／threshold／pgvector／Qdrant 仍不在本輪裁決。
```

`MEM-Q003` 已完成；`MEM-Q004` 的 read shape、isolated semantic-index mechanism、Tool 名稱與最小 contract 均已完成 G4 收斂。Product Owner 已於 2026-09-03 核准 [`isolated spike plan`](plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md) Revision 2 進入 G5；本次只可在隔離 worktree 產生實驗證據，完成後回到 report review，不授權 production、merge 或 push。
