# 客製化完整 JD：關聯式欄位充分性與必要性審核

- 日期：2026-09-13；Topic：JD-R002/C01、C03。
- 目的：依既有完整工作分析、客製化深度、成品及樣稿研究，最後核對欄位不足、過度拆欄、重複權威及關係錯置。不是再次用 schema 對照 schema 自證。
- 基準：[目前決策](../current-decisions.md)、[關聯式保存稿](2026-09-12-jd-relational-schema-and-write-contract.md)、[業務操作](2026-09-12-jd-business-operations-and-scope-design.md)。本輪尚未建表或執行自然模型。
- Owner 範圍更新：先完成 App、業務邏輯、LLM 接線及測試；Excel 延後，不再以匯出樣本阻擋本輪主線。既有匯出方向保留，詳[需求](2026-09-12-jd-relational-editing-requirements.md)。

## 1. 審核方法與來源

本次分三層：研究需要保留的工作事實能否表達；成品是否有多餘欄位；資料關係及保存規則是否允許持續修正。只有已知的重要資訊無適當落點，或必須維護矛盾的兩份內容，才是增刪欄的理由。

| 原始責任文件 | 本次核對的問題 |
|---|---|
| [完整工作分析指南](2026-09-09-complete-work-analysis-guide.md) §2–6 | 工作廣度、本人判斷、低頻、情境差異、未知及更正是否保留；十四個分析面向不等於十四個必填欄 |
| [客製化深度與訪談校準](2026-09-09-customized-jd-depth-and-interview-calibration.md) §2–7 | 不套公版、不逐案列永久任務、不把實際工作改寫為理想職位；招募／訓練／KPI 分界 |
| [欄位與寫作指南](2026-09-09-jd-field-and-writing-guide.md)、[最新六章格式](2026-09-10-jd-format-review.md) | 核心資訊不是初次保存必填；成果／要求並列；K/S 定義與用途；條件按適用對象落位 |
| [完整樣稿 r2](2026-09-09-frontend-engineer-jd-sample.md)、[15 筆情境與雙向審查](2026-09-09-jd-sample-basis-and-review.md) | 用已明示內容檢驗落點，不補新員工事實；樣稿不是固定數量／label／DB 模板 |
| [格式品質與保存核對](2026-09-10-jd-format-quality-and-storage-review.md) | 區分後來 Owner 裁決及歷史路線，不恢復已被取代的成果／要求合併或隱藏條件繼承 |

以上研究已記 OPM、O*NET、NOS 等依據與限制；本輪對已有內容作追溯，不把再搜同一來源當進度。工程新主張另在[框架與施工前置](2026-09-13-jd-native-framework-and-integration-preflight.md)核官方現行資料。

## 2. 工作資訊到實際欄位的追溯

| 要保留的資訊 | 正文／關係落點 | 為何不另加固定欄 |
|---|---|---|
| 角色、單位、直接匯報及可選姓名 | `jd_profile` 四項基本欄 | 沒有必要複製成另一組 HR 職位主檔；文件名稱另屬 catalog |
| 服務誰、整體範圍及價值 | `jd_profile.purpose` | 可完整敘述，不需拆成多個同義短格 |
| 與誰合作、合作什麼 | 多筆 `jd_collaborator.name/scope_text` | 主要對象與全職位交接權責不同，不要求任務—協作者另建 N:N |
| 例行、專案、周期、事件、支援及低頻重要工作 | 多筆 duty/task；未分組 task 合法 | 不需固定工作類型配額；不能因低頻或無職責而漏列 |
| 本人行動、對象、觸發、輸入、必要判斷與交接 | `jd_task.name/description` | 確實影響工作者保留完整文字；不是每個任務都需填輸入、判斷、交接三欄 |
| 成果、服務結果或維持狀態及接收者 | 多筆 `jd_task_detail(kind=outcome).text` | 不強迫都是文件／報表，也不因沒有已知成果就阻保存 |
| 過程、品質、安全、期限、返工及例外要求 | 多筆 `jd_task_detail(kind=requirement).text` | 與成果同屬 task，不設成果→要求配對；有根據的數值可寫在要求內 |
| 頻率、負荷與適用情境 | 任務敘述或該項要求；全職位共通者進 condition | 避免把「有月檢約定才每月」壓成無條件 frequency=monthly |
| 主責、協助、核准、升級與他人工作 | 任務文字／要求；全職位共通 authority/collaboration condition | 管理行為若是工作本身就列 task，不能只用一個「是否主管」取代 |
| 場所、工具、設備、體力／感官／持續注意等實際要求 | 特定 task／requirement；共同環境進 condition | 不以辦公工作視角漏掉條件；不新增個人能力診斷／量表 |
| 知識內涵與用途／範圍 | capability(kind=knowledge) 名稱＋說明 | 名稱不唯一；同名異義不自動合併 |
| 實際運用的方法與技能 | capability(kind=skill) 名稱＋說明 | 不把員工現有程度／訓練缺口變職務欄位 |
| 任務需要的知識／技能 | `jd_task_capability` 共享關係 | 反向用途由相同關係查出，不存第二份可編清單 |
| 全職位工時、輪班、出差、環境、權限、交接及必要資格 | 五類 `jd_condition`，各類可多筆 | 只因員工有學位／證照不足以設為職位門檻；未知不等於無要求 |
| 目前／以前／將來、通則／單案／尚未釐清 | 目前有效內容進 JD；必要不確定表述就近保留；訪談、案例與 Memory 沿原 owner | 不追加每列推測置信度、永久案例清單或另一份待整理工作區 |
| 內容依據與後續更正 | `jd_source_link` 指既有原始問答；target 改後提示重新核對 | K/S 引用回答所需專業，來源引用回答依據，兩者不可混用；Memory 不複製進正文 |
| 新增、移動、刪除及反覆修正 | 穩定 ID／同文件 FK／position；head、revision、operation | 技術欄位由 App 管理，不讓員工或模型填保存證明 |

## 3. 代表性反例走查

以下是文件／人工語意走查，**不是 SQL、瀏覽器或自然模型測試**。

| 檢查 | 既有情境與預期 | 欄位判斷 |
|---|---|---|
| F01 月檢條件 | 情境7、8、12：A 僅缺陷修正，B 有月檢；任務8敘述保留有約定才月檢，要求保留不自動擴大 | 不缺獨立頻率欄；須防 mapper 遺漏 r2 的「執行時機」文字 |
| F02 同名異常 | 情境6–8：查詢逾時保留輸入／重試；訂單結果不明避免重複、查實際狀態 | task4 下多筆 requirement 可保留差異，不需每案新增永久 task |
| F03 本人權限 | 情境4、9–11：估算與建議屬本人，對外承諾／客戶驗收不屬本人 | task2/5/6/7 及全職位邊界有落點，不需 RACI 表／核准工作流 |
| F04 未完整任務 | 已知工作描述，未確認名稱／成果／專業 | name 或 description 有內容即可；子清單可空，不假填「無」 |
| F05 移動與刪分類 | task7/8 移到其他職責或移除其 duty，任務必要條件與自有內容保留 | 0..1 duty、穩定 task ID、從屬清單足夠；職責摘要不作自動繼承 |
| F06 共享專業 | 同一知識供多任務用；另一同名知識用途不同 | ID＋N:N 足夠；不以名稱唯一、不逐 task 重抄 |
| F07 設備／管理職位 | 樣稿審查 §6 的非辦公及管理反例 | 真正工作仍列 task，安全要求／負荷／核准範圍就近呈現；不需 Abilities 分數、管理人數必填 |
| F08 下游越界 | 情境15：想學 AI 與一次較快交付 | 不增加模型訓練責任、KPI 權重／成績、學習計畫欄 |
| F09 未知及真實更正 | 未提供證照不推成依法無需證照；月檢更正不刪上線異常處理 | nullable／空清單及局部原子修訂足夠；不新增虛構完成率 |

樣稿四 duty、八 task、五 K／五 S 是教材內容，不是 SQL／模型數量約束。r2 的「主要產出」「完成要求」「執行時機」需依最新語意映射，不能按標籤硬轉新欄或略掉文字。K/S 對應清單須由可核對工作依據建立，不能從排版位置猜連線。

## 4. 必要性與關係結論

目前未找到需增加或刪除**正文業務欄位**的反例：profile、collaborator、duty、task、detail、capability、task-capability、condition 與 source-link 各有不同責任。outcome／requirement 及 knowledge／skill 共表按 kind 區分可維持兩類語意；使用共表不是省略欄位，亦不改各自在畫面的管理功能。

保留 1:1 profile、JD 1:N 業務項目、task 0..1 duty、task 1:N outcomes／requirements、task N:N K/S。技術 ID、順序、版本與 operation 不列為員工填寫欄；name 不當主鍵。catalog、current head、歷史 snapshot、操作結果有不同生命週期，不能單為降低表數合併成一份可寫 JSON。

本結論不宣稱物理 schema、constraints 或模型生成已通過。source 精度、交易與候選操作可能出現的是工程契約問題，須與「缺 JD 欄位」分開記錄。未來真的需要獨立查詢／管理目前文字內的特定業務概念，再以真用途及案例重開；不先建通用擴充欄／動態表單引擎。

## 5. 獨立審核與下一步

本輪由 root 作上述研究追溯；`jd_format_audit` 獨立回查十四面向、十五筆情境及非辦公／管理／混合職位反例，未發現 P1／P2 正文欄位缺漏、冗餘必填或語意錯置。`jd_storage_audit` 核 PK/FK、草稿、D01、來源、snapshot／receipt／整輪撤回，沒有增減表的反例，但找到下列 P3 文件不一致。

| ID | 反例／判斷 | 修正與驗證狀態 |
|---|---|---|
| FA-R01／P3 | ERD 的 revision 自關聯允許多個 successor，文字又說「非 initial parent」，可能讓實作者誤以為初版 r1 可同時成為 r2、r3 的 parent，違反線性歷史 | **DESIGN CLOSED**：已修圖為至多一 successor；明定同文件每個非 NULL parent 值唯一，包含指向 initial。依 PostgreSQL 原生 UNIQUE／NULL 語意，初版唯一仍另外保證。`jd_storage_audit` 窄複核通過；不是 runtime 已有分叉的發現 |

內容充分性審查完成；FA-R01 不改正文欄位／表數，屬工程關係表述修正。生成 DDL 的直接 document FK、來源 exactly-one、初始完整性、還原順序、原子失敗及讀取一致性仍須真 PostgreSQL 驗證，不能由本報告標 PASS。

`jd_format_audit` 對本報告與完整管理旅程再次窄審 PASS：六章無漏項，未增加必填；新任務整組保存、既有文字自動保存、共享K/S及來源責任未偏移，文件／固定／自然／真人驗證界線清楚。

欄位核定後主線接[完整管理旅程](2026-09-13-jd-complete-app-journey-design.md)及[新版施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。Excel 留後續；不靠少填內容或略過恢復、來源、LLM 通知換取表面完成。

本輪 11 份文件的 174 個本地連結、41 個章節錨點、UTF-8／圍欄／尾端空白核對通過。Python 驗證首次遇全機 uv cache 權限限制，改用工作區專用 cache 後離線完成；未安裝套件。只有文件與研究查核，未執行新 DB、瀏覽器、自然模型或真人驗收。
