# JD 模型工具：按需讀寫與來源契約（研究／審核與推薦設計）

- 日期／最後核對：2026-09-29；狀態：**已定產品效果＋依授權選定的工程設計／未實作驗證**。新增工程細節不是 Owner 逐欄選型，也不再懸為待討論。JD map 的精簡 JSON、按需讀取、最少必要模型輸入、詳細差異用 Markdown，以及既定欄位／UI／關係保持已確認目標。§2 補足最小完整能力組，§6 保留缺口與現況證據，§7 列剩餘 gate；不代表 production 工具已切換或已驗收。
- 決策者：Product Owner；本稿維護：JD 契約維護者。依[討論規範](../architecture-discussion-standard.md)與[決策流程](../decision-process.md)分開產品決定、工程推薦、實作及驗收；本次為全產品文件整理，不授權 production 修改或切換。
- 責任範圍：職務顧問 A 對**同一份關聯式 JD 候選**的模型可見讀取、編輯意圖與直接來源。人工編輯、正式保存、原操作回執與 UI 仍由原業務責任承接；Memory／歷史訪談的內容讀取仍由各自來源責任提供。
- 已確認上位效果：[JD 結構](../product-concept.md#jd-的關聯式結構與逐項編輯已確認目標)、[JD 導覽與讀取 §3.2–3.3](2026-09-26-consultant-context-and-state-design.md#32-jd-導覽的按需定位目標已確認未實作)、[欄位與寫作](2026-09-09-jd-field-and-writing-guide.md)、[共同工具規範](2026-09-27-agent-tool-contract-design-research.md)。本稿不重定這些內容、不把現行 `jd_read`／十個工具冒充新目標。
- 本輪問題：怎樣讓 A 在資訊足夠時，以少而清楚的參數讀到相關 JD、修改正確的關聯式項目、選對直接依據，並以最少必要回傳延續分析？

## 1. 取捨與適用邊界

| 作法 | 得失 | 本稿判斷 |
|---|---|---|
| 每欄及每種關係各有工具 | 每個輸入小，卻有許多選擇與往返；同一更正易留下半套候選。 | 不作預設。 |
| `execute_jd(action, payload)` 一個萬用入口 | 名義上工具少，實際格式、權限與錯誤都藏在 payload。 | 不採。 |
| **按業務效果的少量具名工具；同一項目的相關修訂合在一次呼叫** | 類型與責任較清楚；建立完整任務、局部修訂及結構移動仍各有邊界。 | **推薦候選，待模型與 wire 驗證。** |

本稿只給 A 看需要的 JD 能力，不把 Memory B1／B2 編輯、資料庫操作、員工撤回、整版發布或內部診斷塞進 JD 工具。App 提供職務檔案、當輪 JD 候選、固定 Memory 基準、原操作與儲存資訊；模型只選**目標、要寫的內容、必要的直接來源**。名稱使用 `動作_業務對象` snake_case；多個同義入口不並存。OpenAI 官方建議清楚描述函式、參數與結果，且程式已知值不要求模型填；這不是官方指定本稿的名稱、數量或輸出格式。[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)

**審核結論：沒有發現需要 Owner 重新裁決的真正產品衝突。**原六入口草案漏列基本資料寫入、明細編修／排序及兩類差異的可操作契約；這些是達成既定效果所需的工程缺口，不是新增產品需求。指南較早的全稿雙向核對保留為後續品質目標；依[最新產品範圍](../product-concept.md#完整可交付與目前稿的界線2026-09-29-owner-已確認目標未驗收)，近期不加全稿審核 Agent、審核狀態或固定評改循環，也不把全稿完成列為逐步編修的 gate。

## 2. 建議的模型可見入口

**工程設計選定八個具名入口：七個承接 JD 內容讀寫，一個承接已確認的差異閱讀。**這是本次審核的最小完整分工，不宣稱八個是理論最少、官方要求或 Owner 逐欄選定；名稱、schema 與結果仍待 §7 驗證。Memory／訪談讀取沿各自工具，不計入 JD 八入口。不新增 tool search 或 registry。下文「推薦」均表示選定供實作驗證的工程接法，不表示尚待產品裁決。

| 工程設計名稱（註冊未驗） | 何時用／最少的模型選擇 | 不做什麼 |
|---|---|---|
| `read_jd` | 已確認：以 `view` 和需要時的 `read_ref` 讀 map、全稿、單項或指定區域。 | 不寫入、不讓模型選職務檔案／JD 版本；不另建 JD map。 |
| `revise_jd_profile` | 修訂已核對的職務名稱、單位／範圍、匯報關係及職務目的；`changes[]` 選欄位、文字或該欄直接來源。 | 不要求虛構 profile ID，不改職務檔案顯示名稱／員工姓名；未列欄位保留。 |
| `create_jd_task` | 有足夠資訊時，一次建立任務及目前已知的成果、要求與既有知識／技能關聯；模型選所屬職責或未歸屬位置並填內容。 | 不為填滿欄位補造資料；不先建空殼再強迫逐欄補齊。 |
| `create_jd_item` | 建立職責、共用知識／技能、協作對象或共通條件；`kind` 決定該型別真正需要的欄位。 | 不做任務或任務明細的第二個建立入口，不要求模型選已知的頂層容器。 |
| `revise_jd_item` | 以 JD `read_ref` 選一個既有項目；有限 `changes[]` 修文字、增刪改成果／要求、增刪或排序任務－能力關係，以及新增／移除／明確確認直接來源。 | 不收任意 JSON path、SQL、整份 JD 或無關項目的批次命令。明細增刪只走此入口；單欄更新不另設 `set_jd_text`。 |
| `move_jd_item` | 任務換職責／未歸屬，或同類項目／同任務同組成果或要求改排序；保留身分、內容與關係。跨職責所需的有界內容調整可隨同操作。 | 不用刪除＋重建模擬移動，不將成果變要求或跨任務搬明細；不讓位置隱含條件繼承。 |
| `delete_jd_item` | 確認需移除職責、任務、共用知識／技能、協作對象或共通條件；App 依 JD 既定關係效果處理。例如刪職責時任務保留為未歸屬；仍被任務使用的共用知識／技能先拒絕，不能自動解綁。 | 任務成果／要求由所屬任務的 `revise_jd_item` 移除；不用空文字模擬刪除，不讓模型填 cascade、FK 或 SQL。 |
| `read_jd_changes` | 按需讀「人工改稿」或「某筆既存 JD 來源」的詳細差異，回 Markdown；由 App 固定比較兩端。語意與參數見 §4.3。 | 不增加 `read_jd` view、不改 map，不是任意歷史／Memory 舊正文查詢；讀過不確認來源。 |

**與首輪草案的演進：**原先暫不另列差異入口，審核已找到具體反例：只讀目前 JD 無法區分人工改動，只讀新版 Memory 無法知道某筆 JD 原來依據的修訂變了什麼。因此推薦由 `read_jd_changes` 薄接既有 JD 修訂／操作及來源 owner，涵蓋這兩種已確認比較；不另存 diff、不提供任意歷史選版，也不重新建立 change engine。來源確認留在所屬修訂入口，不新增 `update_jd_basis`。本輪自己的精確修改先用實際工具結果與目前候選接續；額外的任意本輪操作歷史查詢仍須有反例才擴充。現行 `jd_change_read` 與人的改動查看功能不因本稿退役。

### 2.1 欄位與操作覆蓋

下表審核的是**模型能力覆蓋**，不是新的欄位、UI 或資料表。建立是建立 JD 內容項目；職務檔案及單一 profile 的建立仍由 App 管理。

| 既定內容／效果 | 讀／建立／局部修改 | 刪除、移動與關係 | 來源與核對 |
|---|---|---|---|
| 基本資料、目的 | `read_jd(profile)`；`revise_jd_profile` 可首次填值與改值 | 合法可空欄以明確 clear 清空，不刪 profile | 四個可編欄各有直接依據，可增刪與確認 |
| 職責 | `read_jd(item/responsibility_areas)`；create／revise item | 職責排序；刪除保留任務為未歸屬 | 來源屬該職責，不由任務自動繼承 |
| 任務 | item／work_tasks／unassigned view；完整 create task、局部 revise | 跨職責或未歸屬移動、排序；刪任務清自身明細及關係，保留共用 K／S | 任務來源不代替成果、要求或能力關係的來源 |
| 成果、要求 | 隨任務完整讀；create task 可附多筆；revise task 可逐筆增刪改 | 兩組各自排序；不配對、不互為父子、不擅自跨組／跨任務搬動 | 每筆明細有自己的來源及精確引用定位 |
| 共用知識、技能 | item／對應區域讀；create／revise item | 各型別總覽排序；仍被使用時拒刪 | 定義的來源與任務使用此能力的來源分開 |
| 任務－能力關係 | 任務讀取列關係；K／S 讀取可查反向用途；create task 或 revise task 建立 link | revise task 可 unlink、調引用順序；不刪共用定義，不維護第二份反向清單 | 以該 task＋capability 關係為來源目標；解除時清此關係的 current links |
| 協作、共通條件 | 對應 view／item；create／revise item | 同容器同類排序、刪項；條件沿既有分類，不發明標題或自動繼承 | 來源屬該項；任務特有條件仍在任務敘述／要求 |
| 人工差異、來源確認 | `read_jd_changes` 回兩端與局部詳細比較；完整新來源沿 Memory／訪談 read | 差異讀取無寫入副作用 | revise profile／item 的 `confirm_reference_alignment` 明確核對保留引用 |

## 3. 讀取結果：按需深入，避免重複投影

`read_jd` 的輸入效果與 `view` 範圍由已確認的[§3.3](2026-09-26-consultant-context-and-state-design.md#33-jd-導覽後的按需深入讀取owner-已確認目標未實作)維護，不在本稿複製另一張 view 表。**已確認的目標：map 用精簡 JSON**，便於帶回定位；模型只在按需呼叫時填本次必須選的參數。**其他 view 的工程表示：**full 採完整可讀的 JD Markdown，不逐項附 refs 或來源 metadata；item／profile／區域採精簡 JSON，保留完整業務內容、關係及 App 提供的必要定位。這是依閱讀與後續操作用途選定的接法，不從 map JSON 或差異 Markdown 推導所有結果都要同格式；實際模型品質與容量仍待驗。OpenAI 的 function result 允許字串形式的 JSON 或文字；Markdown 不是 provider 的必選要求。[OpenAI result formatting](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)

例如讀 map 中的 `task_example_1`：

```json
{"view":"item","read_ref":"task_example_1"}
```

供模型看的局部結果採下列**工程表示／未實作驗證**；內容與參照均為示意，不新增 JD 業務欄位：

```json
{
  "kind": "work_task",
  "title": "實作網站頁面",
  "description": "依已確認設計稿實作頁面及互動，核對資料介面行為。",
  "outcomes": [{"read_ref":"outcome_example_1","text":"交付符合已確認需求的可操作頁面。","supporting_sources":[]}],
  "requirements": [{"read_ref":"requirement_example_1","text":"依已確認的介面契約檢查主要行為。","supporting_sources":[]}],
  "required_knowledge": [{"read_ref":"knowledge_example","name":"資料介面","supporting_sources":[]}],
  "required_skills": [{"read_ref":"skill_example","name":"介面實作","supporting_sources":[]}],
  "supporting_sources": [{"citation_ref":"citation_1","kind":"work_understanding","target_title":"網站前端交付","needs_recheck":true}]
}
```

成果／要求各自可有多筆；上例只有一筆，不暗示固定配對。**依本次範圍指示，JD 模型定位沿既有 `read_ref`，不另發一套 `item_ref`／明細短 ID。**在局部讀取沿相同表示提供明細定位，是本稿推薦接法；不增加 map 欄位。定位仍不是寫入授權：模型在修改意圖帶回 App 已給的選擇值，App 在當輪可見 JD／候選中核對身分、完整內容基準、型別、權限與業務規則後，才轉成原 Domain 可執行命令；不能把現行 navigation ref 直接送入 writer，或只憑 map 預覽准寫。已具足夠有效內容不強迫反覆 read；實際過時或缺內容才重讀，不新增已讀游標／refresh token。

局部讀取只列被選項目及直屬明細所需定位，不複製其他項目的 refs。知識／技能先只給名稱與可讀定位，需要完整定義再讀；共用 K／S 的反向任務用途由既有關係投影，才能判斷修改或刪除的影響。直接來源先顯示可辨認名稱及必要的既存引用定位，原話或 Memory 完整鏈不在每次 JD 讀取自動重貼。完整局部內容的來源集合無成員時回 `[]`；例中的空集合不是繼承父任務來源。能力列的 `supporting_sources` 屬任務－能力關係，能力定義自己的來源須另讀該項目。一般來源不印「目前相符」；只有需要核對時才標示。

對預期過大的讀取，工具不可把被截斷結果叫完整；先使用 map 與局部 view，真正超出容量時明示無法完整交付，再依實測反例處理。不為本稿先加入 cursor、固定 `response_format` 參數或靜默裁切。Anthropic 公開工具工程研究也將返回格式、精簡與詳細程度視為應依任務評估的選擇，而非一種普遍最優格式。[Anthropic tool engineering](https://www.anthropic.com/engineering/writing-tools-for-agents)

## 4. 編輯輸入：只傳模型必須決定的內容

下列是**推薦語意形狀，待實作驗證**，尚非可直接送 provider 的完整 schema。推薦顯式 `strict:true`；所有宣告屬性 required、每個 object `additionalProperties:false`，根必須是 object，有限 variants 放在屬性或陣列元素內；須核對實際序列化是否落在支援子集。`read_jd` 語意上不需定位時用 null 的 wire 細節沿原契約核對，不加新的參數。不為了符合 wire 規則把 Domain 的「未提及＝不修改」改成清空。[OpenAI strict mode](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)、[支援 schema](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)

| 操作 | 候選模型欄位 | App 自行提供／驗證 |
|---|---|---|
| 基本資料／目的 | `changes[]` 每筆明確選 `field` 與 set／clear／來源動作；欄位限 `job_title`、`organization_unit`、`reports_to`、`purpose`。 | 當輪同一 profile、可空限制及逐欄來源；不由模型建立 profile 或改員工姓名。 |
| 建立任務 | `parent_read_ref` 選 map 中職責的既有 `read_ref`，null 表未歸屬；任務標題／敘述；已知成果、要求、關聯知識／技能及各自適用的直接來源。沒有的子項用空集合，不創造占位內容。 | 職務檔案、候選、任務及明細 ID、排序預設、原操作；檢查關係資格與整組候選。 |
| 建立其他項目 | `kind` 與該型別的內容，限職責、共用知識／技能、協作對象及共通條件；來源只附實際支持的項目。 | `kind` 決定的合法欄位及容器、ID、預設末尾排序。 |
| 修訂 | `read_ref` ＋有限 `changes[]`，詳見 §4.1。每筆只填其動作真正需要的值。 | 固定目標、型別與權限；驗所有 changes，**同一呼叫全成或全拒**。未列的欄位與來源保留。 |
| 移動 | `read_ref`、需要換職責時的 `parent_read_ref`（null 表未歸屬）；排序以 first／last 或指定同組鄰項的 `read_ref` 表意，不填 position。必要的相關 `content_changes` 沿既有結構操作。 | 保留身分、明細、K／S 及來源；只允許任務換容器，其餘同容器同類排序；處理受影響順序。 |
| 刪除 | `read_ref`，限職責、任務、共用知識／技能、協作對象及共通條件；刪職責可附存活任務所需的有界 `content_changes`。成果／要求由所屬任務移除。 | 刪任務清其明細／關係及所附 current source links，保留共用 K／S；刪職責保留任務及原順序、轉未歸屬。固定歷史快照及當時依據不被刪掉。 |

`parent_read_ref`、`detail_read_ref`、`capability_read_ref` 等名稱只區分**同一 JD `read_ref` 的參數用途**，不是另一種 ID、token 或新儲存。模型不填 revision、operation key、文件 ID 或 source owner。參照不能猜造；App 不能因同名重建便將舊參照改指新物件。基本資料以四個固定欄位選擇，不為它再製造 profile 定位。

同一 A Turn 可做數次定向操作，在共同候選中核對後才正式生效；這不取消**既有單次業務操作的完整性**。現行跨職責移動與刪職責已有必要內容調整、一次全成或全拒的能力，本推薦保留：移動只可連帶調整該任務及來源／目的職責摘要，刪職責只可調整其存活任務，詳見[既有操作 §3.4–3.5](2026-09-12-jd-relational-agent-tool-contract.md#34-jd_delete_item)。不讓結構先變、必要限制遺漏，也不將無關項目塞進 `content_changes`。更廣的跨項目原子需求須先有反例；不先建任意 batch engine。單次 `updated` 只表示候選效果，不能當正式 JD 已提交。

### 4.1 有限修訂動作與精確來源目標（推薦設計，待實作驗證）

| 動作 | 模型必須選擇的內容／限制 |
|---|---|
| `set_field`／`clear_field` | 既有合法欄位與完整新值；clear 只用於既有可空欄。非 profile 項目仍須有有意義內容，必填明細文字不得清成空殼。只改一個欄位不覆蓋同項其他欄位。 |
| `add_detail`／`revise_detail`／`remove_detail` | 所屬任務為外層目標；新增選 outcome／requirement、文字及各自來源，修改／移除用讀取所得 `detail_read_ref`。不以移除重建代替正文修正。排序走 `move_jd_item`，同任務同 kind 才合法。 |
| `set_capability` | 外層任務＋已存在 K／S 的 `capability_read_ref`＋link／unlink。link 可附該關係的來源；unlink 不附新來源、不刪定義。要新建 K／S 時先 create item，再用結果的 JD `read_ref` 連結；不猜未建立物件 ID。 |
| `reorder_capability` | 外層任務內既有能力關係及 first／last／同任務鄰項。只改引用順序，不改共用能力總覽順序或正文。此能力為沿既有關係 position 的推薦接線，須驗 Domain 是否足夠，不宣稱現行已有此模型操作。 |
| `add_source` | 精確來源目標＋§4.2 的來源選擇；不暗中更新已存在的過期引用，既存同來源須走明確確認。 |
| `remove_source` | 該目標已有的 `citation_ref`；只移除此 JD 引用，不刪 Memory／訪談或改其他項目的依據。 |
| `confirm_reference_alignment` | 該目標已有的 `citation_ref`；A 已重評仍支持目前 JD 才提出，App 綁到本 Turn 固定可見的同身分新修訂。沒有換版但 JD 被改過時，也須針對目前內容重核；不能僅因讀過或文字相似而解除待核對。 |

來源目標沿既有 Domain，不升級成「每個 JSON 葉節點都可掛來源」：profile 是指定 `field`；一般項目是自身；任務明細用其 `detail_read_ref`；任務－能力關係用外層 task `read_ref`＋`capability_read_ref`。**普通任務的 name／description 屬同一 task 來源目標**，不是新建兩份逐欄來源；依[現行來源目標與 basis](../../experiments/jd-relational-app/src/jd_relational/domain.py)核對。來源動作中的 target 使用有限具型別選擇，不接受任意路徑。

同一呼叫不得重複或相反修改同一效果鍵：同欄 set／clear、同明細重複修訂、同關係 link／unlink、同引用 remove／confirm 均拒絕；**同目標的文字修訂＋來源確認則合法**，確認須針對本次最終文字，不以修改前的支持狀態通過。不得一面刪來源或 target、一面確認它；明細必須屬所選任務，關係兩端須同份 JD。App 先組最終候選，再驗全部改動與來源；任一失敗整次拒絕。文字修訂省略來源動作時保留原引用，但由既有規則判斷是否待核對；`add_source` 不暗示取代整份來源集合。空來源表示沒有新增依據，不表示內容已受核實，也不為了讓 schema 通過而補造。

**2026-10-01 參數說明澄清（已實作說明，非語意品質通過）：**`remove_source` 移除的是所選 target 的整筆引用，不是只排除原文中被更正的一句。局部更正後，剩餘依據仍應共同支持該 target 保留的事實；失效、重複或已有充分替代的引用可移除，不要求永久保留全部舊引用。`confirm_reference_alignment` 只確認指定 `citation_ref` 的支持關係，其他引用仍可待核對。這些語意及 JD 欄位意義落在 canonical schema 的參數 description，與既有角色指引分工，不另增參數／validator 或自動猜配來源。[實測與限制](../plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md#2026-10-01指引參數語意與實際-context-交叉審核)明示：工具形狀可用，不表示已解決局部更正的語意漏引用。

### 4.2 直接來源的最小選擇（推薦設計，待實作驗證）

JD 可直接依據已核對的有效訪談、A 當次輸入或本 Turn 固定已發布 Memory 中的工作情境／工作理解；依據貼在**它實際支持的 JD 項目、成果／要求或任務－能力關係**，不把任務所有來源無差別複製到每個子項。建議模型只填一個有意義的來源選擇值，App 再映射正式身分與版本：

```json
[{"kind":"interview","interview_sequence":42},{"kind":"work_situation","target_title":"網站頁面交付"},{"kind":"work_understanding","target_title":"網站前端交付"},{"kind":"current_input"}]
```

這些是四種**替代選擇型別**，不是一筆來源同時填四欄。正式序號及 `target_title` 來自有權看到的歷史訪談或固定 Memory 導覽／讀取；`current_input` 由 App 綁定本輪尚無正式序號的員工原話，若本輪取消，相關候選引用也不能正式留下。**Memory 定位只用 `target_title`，層別由 kind 區分，不自創 Memory 短 ID、read_ref、版本或 refresh token。**App 依固定已發布版映射真實身分，不以同名替代已刪物件，也不將標題字串當成 DB 身分。完整來源與資格依[來源讀取契約](2026-09-27-memory-read-and-source-navigation-contract.md)；開場／顧問原話保留出處及語境，不冒充員工已確認事實，公開中間訊息／取消輸入不得引用。只見導覽名稱不能宣稱內容已核對支持；需要時讀來源。

讀 JD 時，**已存在的直接來源**用 `citation_ref` 精確定位，供模型指定移除或明確核對那一筆；這是 **JD 所擁有的引用定位，不是 Memory 物件短 ID**，也不能用它任意讀舊版 Memory 正文。局部結果須附來源 `kind` 及正確讀取線索：訪談提供正式 `interview_sequence`；Memory 若同身分仍存在，提供本 Turn 固定版的 `target_title`，另有舊名時清楚標為歷史名稱；`current_input` 指本輪已提供的原話，不編造正式序號。來源線索跟隨 profile field／item／detail／relation 的實際所屬，不把子項引用全攤成父項的來源。

`confirm_reference_alignment` 對 Memory 才有「綁到本 Turn 固定同身分新修訂」的效果；對不可變歷史訪談則保留原來源身分，只重核它是否支持目前 JD 內容，不製造訪談新版或假來源 diff。來源沒變但 JD 改過，仍須針對目前內容重評。`current_input` 僅在本輪候選中核對，A 成功完成後由 App 映射其正式訪談序號；取消／最終失敗不留下該輪候選引用。單純讀到 diff／新版、改寫 JD 或來源同名都不等於核對。來源被移除、無權或無法核對時不可確認；可保留待核對、移除不適用引用或追問，不盲目改綁。Memory source diff 由來源 owner 產生，JD 工具按該引用取回；不覆蓋[跨層核對規則](../product-concept.md#分層按需分析與下游重評目標已確認未實作)。

### 4.3 兩類差異的按需入口（推薦設計，待實作驗證）

`read_jd_changes` 的根輸入選定為固定 `query` object，內含兩種有限分支；不增加既定 `read_jd` 的 views 或 map 欄位。兩端基準由 App 取得，模型不傳版本、時間戳、已讀游標或 refresh token。`source` **僅限 Memory 來源**，不是通用歷史文字比較入口；不可變訪談原話沿共同 `read_interview` 讀取。

| 查詢 | 最少模型選擇 | App 固定的比較範圍及回傳 |
|---|---|---|
| `query.kind = manual` | 全部人工改動，或以既有區域名稱／某存活項目的 `read_ref`／profile `field` 縮小範圍 | 上一個成功完成 A Turn 所形成的正式 JD → 本 Turn 起始正式 JD；回人工操作的受影響範圍與淨差異。明說新增、刪除、移動、關聯及文字前後；「有人改過又改回」與「沒有操作」分開。本 Turn 自己的候選不混入人工差異。 |
| `query.kind = source` | 從局部 JD 讀到、來源 kind 為 work_situation／work_understanding 的 `citation_ref` | 該引用固定舊來源修訂 → A 本 Turn 固定 Memory 中同身分新修訂；回內容／引用鏈的相關變化、可用新版 `target_title` 及來源可用性。原來源確定不在新版時明示，不按同名替代。 |

**參數分支（工程設計／未實作驗證）：**source 分支僅含 `kind`／`citation_ref`；manual 分支含 `kind`／`scope`。scope 為四種互斥物件：`{kind:"all"}`、`{kind:"area",view:已定區域名}`、`{kind:"item",read_ref:存活項目定位}`、`{kind:"profile_field",field:四個可編欄之一}`。area 只接受原 `read_jd` 中不需另選目標的區域 view，不接受 map／full／item，也不把需職責定位的 work_tasks 查詢猜成全稿；這類精確範圍用 item 分支。各分支只帶自身必要屬性且全部 required，禁止其他分支屬性、null 佔位與未知值；nested variants 的正式 schema 仍須生成及驗證。未知／非法形狀為 `invalid_arguments`，不能退回 all。

**人工差異基底的工程定義：**前文的「A 上次已見」不是推測模型記得哪些字句，也不逐項維護已讀游標。本次選用既有成功 Turn 完成結果中的正式 JD 位置；沒有成功 A 歷史時，用職務檔案建立時的空 JD 基底。因此首輪前人工已寫的內容也會列為新增。兩端在本 Turn 準備時固定，read／暫停／恢復／取消都不推進基底；下一個成功完成 Turn 才提供下一輪的比較起點。這只表示兩次成功工作之間有何人工變動，**不代表其內容已被 A 審核，也不解除既存來源的待核對**。之前提示仍沿原生歷史接續，需要目前內容時按需讀 JD；不增加一套人工問題待辦。若應存在的基底不可取回，明確報比較無法完成，不偷偷改用另一版或空稿。

**來源型別、scope 與兩端可用性：**先核對呼叫者及本 Turn scope，再辨認其中引用與來源；沿[共同錯誤契約](2026-09-27-agent-tool-contract-design-research.md#7-錯誤回傳與恢復責任)回可修正錯誤，不建立第二套狀態／回執。

| 情況 | 結果與下一步 |
|---|---|
| 合法 Memory 引用，固定兩端均可讀 | 詳細 Markdown 比較；已核確定相同可明說淨差異為零，但不自動確認 JD 引用。 |
| 同身分確定已從本 Turn Memory 移除 | 合法比較明示「來源已移除」、保留舊依據定位及相關差異；不回同名新物件的 title 作替代。移除不等於歷史資料不存在。 |
| 固定舊端或應存在的新端無法取得／無法證明移除 | `source_not_available`，說明不能完成比較；不造「已刪除」或零差異。 |
| 引用來自歷史訪談 | `source_kind_not_supported`，提供已有正式序號，指向 `read_interview`；原話不可變，不製造訪談版本比較。 |
| 引用來自本輪 current_input | `source_kind_not_supported`，指向本輪已提供的原話；未完成前不能假造序號交共享歷史 read。 |
| 跨職務檔案、未授權或不屬本 Turn 的 scope | `scope_not_allowed`，不洩露引用、舊端或新端細節；不降級成空差異。 |
| 合法 scope 中沒有該引用／所選目標已失效 | `target_not_found`／`target_stale`，依實際原因引導重讀目前 JD 定位，不猜另一筆引用。 |

例：`{"query":{"kind":"source","citation_ref":"citation_1"}}` 只有在 citation_1 是合法 Memory 引用時才回兩端 Markdown。若它其實引用訪談 42，回 `rejected: source_kind_not_supported` 及「請以 read_interview 選取正式序號 42」；不是 `unchanged`，也不是來源被刪除。只讀舊固定來源的相關差異，仍不新增 Agent 的任意舊版 Memory 全文入口。

人工概覽須在下一輪讓 A 辨認有受影響內容；它是既有改動提示的投影，**不改已確認 JD map，也不恢復起始預載 JD 導覽**。詳細 Markdown 必須交代比較兩端與位置，不只列事件數。已刪項目可從人工比較的全部／區域範圍讀到，不要求先取得已不存在的 current `read_ref`；歷史位置不能送 writer。比較基底依上段正式完成位置，不以本輪 read 建立新進度。任一範圍超出完整交付容量時明示未完整，提供可縮小範圍；不靜默漏掉上限外事件、不新加 cursor。

同一 JD 同時有人改稿與來源換版時，兩個比較仍各自成立；A 應用目前 JD、新來源及必要原話重評。來源差異不包含人工改稿，人工差異不證明工作事實；讀兩種差異都無寫入效果。確認只透過所屬修訂入口，且只處理被指定的保留引用，不把整個 JD 或同批 Memory 全部刷新。

## 5. 模型可見結果與失敗

**以下選定模型可見的 tool 回傳，不規定 UI API 或正式回執。**Responses 原生 call／result 已配對，模型在該歷史仍有效時看得到自己提交的 arguments；因此正常成功不重抄輸入內容、職務檔案、Memory 版、操作 key、完整 before／after 或 `stage: candidate`。App 另保留可靠業務結果供中斷對帳；compaction 後若模型需要舊細節，按需讀真實資料，不另建一份永久成功通知。**JD map 用已定精簡 JSON；full 與詳細差異採 Markdown；item／profile／區域沿 §3 精簡 JSON，保留可操作定位及關係；單純寫入結果採下表短文字。**這是工程設計／未實作驗證，不為外觀一致把純文字包成 `{"message":"..."}`，也不為欄位外觀統一填 `null`。

`read_jd` 只回**所請求的那一層**。`map` 回已確認的導覽結構及讀取定位，沒有整份正文；`full` 回目前完整 JD 的可讀成品文字，不逐項重貼定位／來源；`item` 回選定項目的自身完整內容及直屬子項，必要時附下一步可讀／可編輯定位與直接來源（上節範例）；`profile`、`responsibility_areas`、`work_tasks` 等已確認的區域 view 回指定範圍，不越界遞迴展開其他區域或整條引用鏈。例如讀某職責的 `work_tasks`，回 `items[]`，每項附其 JD `read_ref` 與 §3 的完整任務投影；不另外重貼同職責文字。其他集合區域同樣以 `items[]` 承載其型別的完整自身內容，profile 則回四個既定欄位的完整值及逐欄 `supporting_sources`，不虛構項目 ID。

若任務有多筆成果／要求，須完整列出並提供相應明細定位；不能以「更多內容略」冒充完整。合法空區域明列 `items: []`，不把空白誤解成讀取失敗。區域內容過大而無法完整交付時，回**未完整讀取**與可縮小的合法範圍，不靜默截斷。

| 本次效果 | 候選的最短模型回傳 | 何時必須增加資訊 |
|---|---|---|
| 建立如實成立 | `created · read_ref: task_example_new`；新 JD 定位是輸入中沒有、後續選取需要的資訊，不重複正文或來源，也不擴用成 Memory 短 ID。 | 實際內容被正規化或部分未成立時不能只回 created；拒絕半套建立。明細後續需要定位時沿局部 read 取得。 |
| 精確修訂／移動 | `updated`／`moved`。 | App 實際效果與輸入不同、移動解除關係、內容位置需核對時，回**實際**影響的短摘要或差異；不冒充原參數即已套用。 |
| 刪除 | `deleted`。 | 刪職責使任務變未歸屬等模型下一步需要知道的非直觀效果，簡短提示即可；不回整份 JD。 |
| 來源確認 | `aligned`，只表示指定 JD 引用在本輪候選中已對齊。 | 改綁到哪個可見來源、是否仍有其他待核對依據須可判讀；不表示全項／全稿審核通過或正式提交。 |
| 已核確定沒有差異 | `unchanged`。 | 不產生假更新或新的已提交事實。 |
| 確定拒絕且未修改 | `rejected: <code>`＋可理解原因／下一步。 | 歧義、目標失效、來源不可用等，說明合法修正方式；不露 stack trace 或禁止層內容。 |
| 提交結果不明 | **App 先對帳原操作**，不能回 `unchanged` 叫模型重送。 | 只有確定的原結果才能回模型繼續；不能以目前最新版 JD 冒充原操作結果。 |

模型可見範例（短字串足夠時，不再包 JSON）：

```text
created · read_ref: task_example_new
updated
moved · 原所屬職責已解除，任務現在未歸屬
deleted · 原職責下 2 項任務仍保留，已轉為未歸屬
```

示意錯誤（可用簡短文字，不需要固定 JSON 外殼）：

```text
rejected: target_stale；本次未修改。
請重新 read_jd(map) 並讀取相關項目後，再決定是否提出新修改。
```

未知、無權或本次讀取不完整時不能對模型偽稱成功；已恢復的短暫基礎設施錯誤不必逐筆塞回模型。最後正式 JD 是否提交、取消或回退，由已定 A Turn／業務 owner 的生命週期判定，不靠模型工具回傳文字。

## 6. 審核發現、沿用證據與取捨

**首輪審核的缺口保留為追蹤紀錄；本次補到推薦設計，不將文件補全當成已實作。**已確認產品效果優先於較早文件的候選；現行程式只證明可沿用哪些能力，不自動決定新目標的模型介面。

| 發現／反例 | 可核對的基線 | 本次處理與剩餘限制 |
|---|---|---|
| 只給 `read_jd(profile)`，A 無法完成基本資料與目的 | [欄位指南 §2.1](2026-09-09-jd-field-and-writing-guide.md#21-基本資料與職務目的jd-r001c01)、[profile 與逐欄來源](2026-09-12-jd-relational-schema-and-write-contract.md#32-jd_profile)；現行 `jd_set_text` 可修改 profile | §2／§4 推薦專用 `revise_jd_profile`，不建新表或 validator。限定四個 JD 欄位；資料表已有姓名不代表這次開放 AI 改員工資料。 |
| 原稿只有明細增刪，未明說改文字、兩組排序與能力引用排序 | [關聯式產品結構](../product-concept.md#jd-的關聯式結構與逐項編輯已確認目標)、[明細及關係](2026-09-12-jd-relational-schema-and-write-contract.md#36-jd_task_detail) | §2.1／§4.1 補覆蓋；成果與要求各自多筆、各自修改排序；關係排序接點仍待實作查驗，不把 position 當模型身分。 |
| 父任務有來源，不代表其每個成果／要求及 K／S 關係都有依據 | [source link target](2026-09-12-jd-relational-schema-and-write-contract.md#310-jd_source_link)、[Domain 的 `_basis_content`](../../experiments/jd-relational-app/src/jd_relational/domain.py) | §4.1 明列 profile field／item／detail／relation；不新增普通項目的逐欄來源，不將來源全貼父任務。 |
| 原稿另發 `item_ref`，仍未解釋 map 選擇如何安全成為修改意圖 | [既定 JD `read_ref`](2026-09-26-consultant-context-and-state-design.md#32-jd-導覽的按需定位目標已確認未實作)、[現行完整讀取檢查](../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py) | 依本次指示收斂為同一 JD `read_ref` 選擇；App 另驗權限、內容基準並轉譯。現行 `navigation` ref 仍不可直接進 writer；新接線未驗。Memory 仍只選 `target_title`。 |
| 只讀現在內容，無法知道人工改稿或來源換版差在哪裡 | [A 的兩類差異](2026-09-26-consultant-context-and-state-design.md#3-資料真相模型可見性與生命週期)；[`NoticeHistoryReader`](../../experiments/jd-relational-app/src/jd_relational/notice_history.py)提供固定修訂邊界與操作概覽，[`ChangeReadService`](../../experiments/jd-relational-app/src/jd_relational/change_reads.py)讀單次操作，`project_revision_changes` 比兩快照 | §4.3 推薦一個受限差異入口；現行單次 JSON 結果不等於跨次人工 Markdown 比較，更不等於新 Memory 來源 diff。沿 owner 投影，精確基準及跨 owner 接點待驗。 |
| 刪職責或移動若丟掉仍有效的限制，JD 文字與結構會脫節 | [既有操作契約](2026-09-12-jd-relational-agent-tool-contract.md#34-jd_delete_item)、[Domain 的 `_structural_changes`／`_delete_item`／`_move_item`](../../experiments/jd-relational-app/src/jd_relational/domain.py) | 保留既有有界內容調整的單次完整效果；不能僅以「最後整輪才提交」為理由省略。刪職責保留任務，刪任務保留共用 K／S，仍有使用者的 K／S 回 `dependent_items`。 |
| 呼叫成功容易被誤讀成正式稿成功；一次模型回覆亦可能有多個 call | [共用 Step／完成契約](2026-09-27-shared-agent-execution-and-state-design.md)、[現行 JD 工具接線](../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py) | §5 的結果只描述本次候選；相依寫入依共同執行責任排序及配對，不另造 JD 執行器。現行 `execute_foreground` 正式提交路徑不能冒充新候選語意。 |

### 為何推薦這個工具組

基本資料有兩種可行接法：併入 `revise_jd_item` 可少一個名稱，但 profile 沒有 map item ref，且大量任務明細／關係動作在此不合法；**推薦分出 `revise_jd_profile`**，只選固定四欄和逐欄來源。這是模型契約的工程取捨，待同一組試例驗證；若合併能保持清楚且效果更好，可在不改產品語意下調整，不要求 Owner 再選一次欄位。

差異也有「擴充 `read_jd` views」或「薄接專用讀取」兩種接法。**推薦 `read_jd_changes`**，保持已確認內容讀取 views／map 不變，兩種比較都由 App 固定兩端；來源正文仍由原 owner 提供。代價是多一個名稱及兩種查詢分支，收益是能觀察已確認的兩種變動，並避免把看差異混成確認來源。這不採納任意歷史查詢、第二份 diff 儲存或通用比較引擎。

`revise_jd_item` 內保留具型別的明細、關係與來源動作，是因它們可以屬同一任務更正；建立、刪除及移動仍是不同業務效果。能在同次修訂改文字並確認來源，不要求每條引用單獨一次模型往返。官方來源沒有證明這個數量／拆法最優；優劣由 §7 的選對率、修正能力及成本判斷。

### 代表性生命週期（目標／推薦接法，未實作）

1. App 固定本 Turn 的 JD 起點、可見候選、有效訪談與已發布 Memory；A 按需讀 map／相關完整內容。
2. A 選 JD `read_ref`、內容及來源；App 核對選擇與基準，原 Domain 驗最終候選，可靠成立後才回配對工具結果。若結果不明，沿原操作對帳。
3. 下一步 read 能看見本 Turn 自己已成立的候選；來源 Memory 仍固定，不追逐背景新發布。若同回應有相依 calls，依共同 Step 契約有序處理，後一個失敗不誤稱全部成功。
4. A 成功結束且業務完成邊界成立，候選 JD 與本輪合法來源依既定契約一致生效；取消／最終失敗捨棄本輪候選。工具不可自行提交整輪，也不能藉「重試」復活已取消候選。
5. 使用者處理中看到的候選預覽不改正式讀取／PDF 邊界；PDF 仍取最後完成稿。下輪可能遇到新 Memory 與人工改稿，再以各自固定基準按需重評。

上述不另設保存系統；完成、取消、恢復與交易責任引用[跨層閉環](2026-09-29-core-value-loop-lifecycle.md)及[目標責任分界](../target-architecture-map.md#業務規則與交易機制owner-已確認目標未實作未驗收)。本稿只標出 JD 工具參與的位置。

## 7. 剩餘工程 gate（全部待實作驗證）

下表是有限工程驗收清單，不是新的 Owner 產品選擇，也不是本次施工或付費模型授權。依[契約策略](../contract-strategy.md)從正式來源生成介面；先驗現有 Domain／來源／操作 owner，缺能力才在相應責任內補接，不能複製 validator 或 receipt。

| Gate／責任 | 必須可觀察的 pass／fail | 證據層級與停止條件 |
|---|---|---|
| JDT-01 工具契約與 provider wire | 八入口的名稱／description 足以選對；所有 variants、enum、required／null／空集合、root object、`additionalProperties:false` 合法。未列 mutation 保留；clear 有別於省略。 | 生成 schema＋實際 SDK 序列化，再驗 provider 接受；未跑前不得稱 strict 通過。 |
| JDT-02 欄位與 CRUD 完整覆蓋 | 從空 JD 寫四個 profile 欄、職責／未歸屬任務、多成果與要求、共用 K／S、協作與各既有條件；逐欄／逐筆修改、移除、排序與關聯增刪都可達成，不改姓名／檔案名稱或發明欄位。 | 離線契約及 Domain 測例；需覆蓋兩個同名 K／S、兩筆相同明細文字等不能靠標題猜的反例。缺一類效果即不完整。 |
| JDT-03 定位與內容基準 | JD `read_ref` 正確映射同份當輪候選；跨檔案、錯類型、已刪重建／過時內容均不誤寫。map 預覽不足不准寫，已有充分有效觀察不額外重讀。明細與關係不能越出所屬任務。 | App resolver／Domain 整合；確認後續自身修改如何承接合法定位，不能自創 refresh token、Memory ID 或讀取進度儲存解決。 |
| JDT-04 來源粒度與確認 | 來源只掛正確 profile field／item／detail／relation；只看新版／diff、改 JD、同名標題或重加既存來源均不自動確認。Memory 明確確認只綁本 Turn 固定同身分修訂；不可變訪談只核對目前 JD 支持，不造來源新版；來源刪除、同名重用不可替代。 | 來源 owner＋JD 整合；測「確認後又改文字」「確認前 target 已改」「新 Memory 晚到」「current_input 後取消」。不得以引用可回讀等同語意支持。 |
| JDT-05 刪除、移動與單次完整效果 | 刪職責保留任務；刪任務清 owned 明細／關係／其 current links，保留共用 K／S；仍被用的 K／S 拒刪。跨職責必要文字修正全成或全拒，同組排序保留身分與來源。 | Domain／交易測例；`changes[]` 後段非法、重複 field、相反 link／unlink 或刪除後確認都整次拒絕。關係排序若原 Domain 無命令，列明必要有界補接。 |
| JDT-06 兩類差異與容量 | 人工新增、刪除、移動、改稿、改回、跨多次操作、概覽上限外事件可辨認；Memory 來源差異綁固定兩端，Markdown 保留位置／必要前後內容；非 Memory 走原話 read，錯誤 scope 不回假差異。人工稿與員工原話區分。 | 固定快照／來源投影測例；含缺少先前基準、被刪目標與超大區域。事件存在不等於淨文字改變，未完整交付不得稱完整；不加 cursor。 |
| JDT-07 候選、恢復與正式效果 | 同輪 read 看自己的候選；正式讀者／PDF 不看未完成候選。成功一致生效；取消／最終失敗不殘留 JD 或引用，也不抹掉 Turn 前人工稿或獨立 Memory 發布。 | 真實保存／重啟層驗原操作結果、提交成功但回覆遺失、取消與完成競爭；unknown 先對帳，不能重送新操作。不得以離線 schema 代稱通過。 |
| JDT-08 原生 call/result 與多工具 | 零／一／多 call 都正確配對；相依修改不平行競爭；恢復取原結果，不以目前 head 冒充。普通成功可精簡，有正規化、關聯影響或拒絕時回必要實際觀察。 | 共同 Step／SDK 接線；工程上可先限制 mutation 的平行呼叫，但 provider 選項不代替 App 次序／保存保證，未選成全產品固定政策。 |
| JDT-09 有界模型與產品效果 | 同案例比較目標／來源選對率、錯改率、錯誤修正、工具步數、輸入／回傳 tokens、延遲及實際 JD 內容；含壓縮後重讀、人工與來源同時變更、多來源逐筆確認。 | 先離線，再依有效授權做有界真模型與代表旅程。不能只比 JSON bytes；不要求唯一工具序列，不把全稿審核或專用審核 Agent 放回近期 gate。 |

**下一步：**由實作者把 §2–5 收斂成可生成的模型 schema 與既有責任接點，先完成 JDT-01～06 的有限測例，再接 JDT-07～09。若實測只影響工具名稱、結果排版或同等效果的拆法，直接修推薦設計；若必須改產品效果、來源資格、完成／取消保證或權責，再帶具體反例請 Owner 決定。此刻沒有這種產品阻塞。

## 8. 當前第一手依據與研究界線

2026-09-29 重新取得下列官方頁面；OpenAI 由官方文件搜尋後取得正文，Anthropic／Google 直接核對官方正文。這是查閱當日的公開契約，**不是鎖定 SDK 版本、實際 provider wire 或自然模型驗收**；不推測 ChatGPT／Codex／Claude 未公開的內部儲存與 JD 工具。

| 第一手來源 | 官方明文／適用範圍 | Caliburn 的推薦映射或不能外推處 |
|---|---|---|
| [OpenAI：Function calling 設計](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions) | 清楚描述用途、參數、結果；程式已知值不由模型填；常固定連用的能力可合併；工具數宜以 eval 判斷。 | 支持隱藏執行範圍與具名業務效果，未指定八個工具、CRUD 拆法或 `changes[]`。少於 20 是軟建議，不是必須新增 tool search 的理由。 |
| [OpenAI：Strict mode](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)、[Structured Outputs 支援子集](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas) | strict 的 required／禁止額外屬性規則；根為 object、不可 root `anyOf`。明設 `strict:true` 不符會拒絕；Responses 省略 strict 可能正規化或回落 best effort。 | 推薦顯式 strict 並驗送出 schema；形狀約束不證明來源、授權、語意或提交成功，不用 nullable 大包取代 partial update 意圖。 |
| [OpenAI：Handling function calls](https://developers.openai.com/api/docs/guides/function-calling#handling-function-calls)、[結果格式](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)、[平行呼叫](https://developers.openai.com/api/docs/guides/function-calling#parallel-function-calling) | 回應可能有多個 calls；結果依 `call_id` 配對，可用文字或 JSON 等表示；可限制平行呼叫。 | 原生配對不是業務交易。map JSON／差異 Markdown 是本案已定效果；短成功、八入口分組及串行寫入接法仍需驗證。 |
| [Anthropic：Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions) | 說明用途、時機、參數、限制；建議整合相關操作、清楚命名及回傳有用資訊。 | 與 OpenAI 共同支持清楚、低歧義的工具；Anthropic 建議 action 合併，不證明 Caliburn 應用單一萬用入口。其 ID 建議不推翻本案 Memory `target_title` 或 JD `read_ref`。 |
| [Anthropic：Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents)（文章 2025-09-11；本次重新核對） | 依任務設計工具，衡量成功、錯誤、呼叫、耗用；JSON／Markdown 等格式的效果依任務與模型而異。 | 支持有限比較及保留必要操作定位；不是「永遠越短越好」、固定分頁／截斷或新增審核 Agent 的規定。 |
| [Google Docs：batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate)（頁面更新 2026-07-07） | 一次更新內先驗請求，任一無效整次不套用；多個更新共同原子生效，回傳依序對應。 | 僅作編輯操作完整性的公開比較；不採 Google 保存、collaboration merge 或任意 batch，也不能由這份 API 推論 Caliburn 已有相同保證。 |

公開資料足以支持這次工具契約比較；**停止廣搜，剩餘交由 §7 有界驗證**。本次完整閱讀 JD 欄位指南、共同工具規範及指定審核稿，另核有效決策、現行相關程式／測試內容與官方來源；只有文件修改，未執行產品、PostgreSQL 或付費模型測試，未改 UI／map／欄位、未 commit。

**承接結論：**已確認產品範圍沒有真正衝突；八入口、參數 variants、JD 引用定位名稱、內容／差異投影及精簡結果均屬推薦設計待實作驗證。原六入口草案的功能缺口已在文件層補齊，production 接線、保存／取消、provider 相容與模型品質仍 OPEN。唯一編輯責任文件是本稿；其他來源保持原有 authority。
