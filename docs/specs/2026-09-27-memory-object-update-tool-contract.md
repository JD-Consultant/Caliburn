# Memory 單物件更新工具契約

Memory 更新工具讓 B1／B2 一次修訂同一候選物件的內容與來源，共同成功或拒絕。來源集合可空，各層內標題唯一；刪除情境時同步解除候選理解綁定。背景依 B1 → B2 → 發布，不回交；Memory 不做逐條 `confirm_reference_alignment`。

讀取與來源回查見[讀取契約](2026-09-27-memory-read-and-source-navigation-contract.md)，共同語意見[工具契約](2026-09-27-agent-tool-contract-design-research.md)與[產品概念](../product-concept.md)。接續、保存與工具接線見[共用執行](2026-09-27-shared-agent-execution-and-state-design.md)、[Memory 保存](../implementation/memory-storage.md)及[Memory 工具](../implementation/memory-tools.md)；[CRUD 範例](2026-09-28-memory-tools-crud-examples.md)展示使用方式。正式 schema 依契約策略生成，契約與資料庫證據不代表模型語意品質已通過，實測範圍見[驗收矩陣](../architecture/verification.md)。

## 1. 目的與已定邊界

**讓責任 Agent 一次修訂同一個候選物件：短欄位給新值，長正文給 V4A diff；共同成功或共同拒絕。** 不為同一修訂拆成「先改名、再改描述、最後正文失敗」的半套狀態。

產品邊界是：B1 只改工作情境，B2 只改工作理解；物件有 `title`、`description`、Markdown `body`；同一職務檔案、同版 Memory **各層內** 的有效 title 唯一，跨層可同名；正文須受控模糊匹配且定位唯一，多處拒絕；候選更新不是完整 Memory 發布。 `target_title` 是外層定位名稱，不是不可變 ID；五個操作參數的名稱／含意依[共同命名記錄](2026-09-27-agent-tool-contract-design-research.md#2-命名與-description-規範)，其餘模型分支及結果依下文工程設計，wire 與機制須分層驗證。

採用：**每層一個受限更新入口，合併該物件的三種內容修改及該層允許的引用修改。** 這是模型可見權限，不要求兩套實作，不提供萬用 `memory_execute(action, payload)`。建立、刪除各有自己的入口。

代表性反例：改標題、描述及正文兩處，第二處有歧義 → 本次三欄均不保存；其他早已成功的候選修改仍保留。

## 2. 工具能力與權限

| 工具名稱 | 可用者 | 作用範圍 |
|---|---|---|
| `update_work_situation` | B1 工作情境分析 Agent | 本批工作情境候選中的一個物件。 |
| `update_work_understanding` | B2 工作理解分析 Agent | 本批工作理解候選中的一個物件。 |

模型不填 `layer` 切換權限；App 綁定 Agent 可改的層。B2 能讀情境不代表可修改情境；B1 的錯誤結果也不能洩露理解內容。A 不透過這兩個入口改 Memory。隱藏工具與執行授權是不同防線。

兩個入口共用輸入型別與編輯機制，但各角色的分析方法、可見資料及修改權限分開。

## 3. 模型輸入：一個目標與有限 changes

**內容欄位與操作參數是兩層，不是二選一。** 物件內容仍是 `title`（標題）、`description`（導覽描述）、`body`（Markdown 正文）；在此更新表示中，它們是 `field` 的三個可選值。`field: title`／`field: description` 搭配 `value` 表達完整新內容；`field: body` 搭配 `diff` 表達局部修改。`target_title` 用來選原物件，與 `field: title` 要寫入的新標題不同。這只是邏輯內容／工具輸入的關係，不新增五個 Memory 內容欄位，也不決定 DB schema。

`changes[]` 表達同一物件多欄一次修改，包含三種內容及 §10 的本層引用；不拆成逐欄工具、不要求全量重傳。成功結果須可核對實際效果；範例不替代序列化或 provider 驗證。

| 參數 | 含意／來源 | 約束 |
|---|---|---|
| `target_title` | 導覽、讀取或先前成功結果提供的目前標題，定位修改前的物件。 | 不靠 diff 猜另一物件，不提供模糊物件選取；精確標題比較與名稱重用見 §9。 |
| `changes` | 本次修訂的欄位集合。 | 1–4 筆：三種內容＋本層一種引用；每欄至多一筆，未列欄位保持不變，不是依序逐筆保存。 |
| `field: title`＋`value` | 完整新標題。 | 非空白，不與目前候選**同層** 其他有效物件重名；跨層可同名。 |
| `field: description`＋`value` | 完整新導覽描述，可含關鍵詞。 | 非空白，說清範圍與閱讀線索；關鍵詞沿 [009 的內容定義](../product-concept.md#分層工作記憶)，不另傳 keywords；App 不替模型補寫。 |
| `field: body`＋`diff` | 對所讀候選正文的 V4A 更新 diff。 | 一筆可含多個 hunk；依唯一匹配要求處理，結果 body 仍須有效、非空白。 |
| `field: interview_references`＋按需 `add`／`remove` | B1 選正式訪談序號，增刪情境的訪談引用。 | 僅工作情境更新入口可用；選取及不改引用的語意依 §10。 |
| `field: work_situation_references`＋按需 `add`／`remove` | B2 選工作情境標題，增刪理解的情境引用。 | 僅工作理解更新入口可用；不讓模型填 scope／版本，不藉增刪默認完成版本重評。 |

不採 `null = unchanged`，也不因 strict 要求三欄全部重傳。三欄是有效內容的必要欄位，本入口不提供清空或刪除物件的隱含操作。未知／重複 field、空 changes、錯型別及非法空白值拒絕，不採 last-write-wins。

以下是**語意示例，不是已通過 SDK／provider 的正式 wire** ；假設讀到的正文確實含相應段落：

```json
{
  "target_title": "網站維護",
  "changes": [
    {"field": "title", "value": "電商網站前端例行維護"},
    {"field": "description", "value": "每週檢查前端頁面與下單流程；後端故障交由工程同事處理。"},
    {"field": "body", "diff": "@@\n ## 處理頻率\n-每月檢查一次。\n+每週檢查一次。\n 後端故障交由工程同事處理。"}
  ]
}
```

`diff` 只承載 body 的更新 hunks，不帶另一個可自由選擇的檔案 path，也不能藉 `Add File`／`Delete File` 改其他物件。外層已定位物件，不需模型再填一份可能矛盾的目標。


### Strict 表示

Root 為 object，required 為 `target_title`／`changes`；`changes.items` 採 **nested `anyOf`** ：短欄位分支只有 `field`（enum：title／description）與 `value`，正文分支只有 `field`（enum：body）與 `diff`；本層引用另有僅 `add`、僅 `remove`、同時 `add`／`remove` 三種分支。各分支全部 properties required，所有 object 均 `additionalProperties:false`；B1／B2 不互相取得禁止的引用修改分支。

不需 `value:null`／`diff:null` 或空增刪陣列佔位。工程設計選定 `minItems:1`、`maxItems:4`，引用操作的每個陣列至少一項；這只限制形狀，不能代替重複 field 與業務檢查。訪談值為正整數，情境值為非空白標題；同一側重複選取按解析後身分去重，同一身分同時 add／remove 則整次拒絕。未列欄位保留，明列空操作或 null 拒絕；來源最後成為空集合仍合法。最終序列化仍須另驗，不能由設計示例推定 provider 已接受。

依據：[OpenAI strict](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)與[支援子集](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)。[V4A 官方契約](https://developers.openai.com/api/docs/guides/tools-apply-patch#apply-patch-operations)讓執行方處理 diff，**不替本案保證唯一匹配、原子保存或語意正確** 。


## 4. Description

以 `update_work_situation` 為例：

> 修訂本批尚未發布的一個工作情境。從導覽或讀取結果選 target_title；title／description 給完整新值，body 給含足夠真實上下文的 V4A diff，interview_references 以已提供的訪談序號按需 add／remove。每欄最多一筆，未列欄位不變。App 先固定目標再處理改名；內容與引用全部通過才保存本次候選修改，不發布 Memory。正文無匹配或多處匹配會拒絕並提供原因，請先重讀或補足辨識上下文，不要原樣反覆重送。

理解入口改成自身層的用途，不暗示可改情境。參數 description 採 §3 的含意與來源，不逐欄重貼權限／恢復手冊。工作分析方法沿原指南，工具不塞第二份分析 Prompt。

已有足夠且有效的正文觀察，不強制重讀；只有 map 或正文已過時時，先取得所需正文再寫 diff。文字曾被提供不等於基準仍有效，具體綁定接線仍依 §9。

## 5. App／Domain 責任與一次修改邊界

模型只選目標與修改意圖。App 提供職務檔案、Agent 權限、原工作批次、已 pin Memory、候選範圍、內部身分／基準、原操作識別及 call/result 配對；模型不填版本、保存成功或發布結果。

以下是**工程責任流程** ；候選與原結果的短交易邊界依[資料與交易](../architecture/persistence.md#3-交易邊界)，不是新增元件或資料表：

```text
已可恢復辨認的原工具請求
  → App 將允許範圍的 target_title 映射為 ID，固定原物件與候選基準
  → 在工作副本計算新 title／description／body 及明確要求的引用變化
  → 原 Domain／編輯執行器檢查內容、引用資格、目前候選同層標題唯一及全部 hunks
  → Memory 業務模組核對基準仍有效，採用整份結果
  → 與原呼叫配對，可靠承接真實工具結果
```

- **先固定目標，再改名：** 同次 diff 不以新標題重新搜尋；後續新呼叫使用成功結果的新名稱。改名不改固定身分或歷史來源。
- **資料庫只以 ID 定位：** 依 [010](../product-concept.md#分層工作記憶)，target_title 不傳成資料庫的目標尋址鍵；App 先完成映射，候選讀寫與正式引用使用 ID。新 title 是修改內容，不是 UPDATE／DELETE 的目標條件；這不取消標題唯一性檢查。
- **只採用完整修改：** 任一欄或 hunk 被拒絕，整個呼叫的更新不採用；不同 calls 不自動共享此原子邊界。
- **候選與原結果一致可恢復才算成功：** 候選修改與原操作結果由業務保存；checkpoint 承接執行位置及候選參照。沿[資料與交易](../architecture/persistence.md)的單一責任模組／短交易接線，不同時保存第二份可編輯候選或 receipt。
- **保存時仍檢查競爭：** 不能先查未重名／未過時，再無條件寫入；不能因 Runtime 注入版本就假設永無過期。不偷偷換 latest 套 diff。
- **沒有實際差異不冒充修改：** 內容與引用集合均完全未變且基準有效時回報無變更；只改引用仍是更新，不由工具憑空建立正式物件版本；候選修訂號的處理仍隨保存設計。

同層標題唯一、引用與發布由原 Domain／Memory 責任處理，不複製 validator。重名檢查只看目前候選同層有效物件集合，不拿全歷史版本作全域唯一限制；錯誤只提供 Agent 權限允許的資訊。情境變更後的 B2 重評沿背景依賴／語意影響流程，此工具不自行啟動另一個 Agent。

## 6. 成功回傳：已成立的候選效果

**更新結果：** Update 保留已確認的「實際效果可核對」目標，正常成功固定回實際 `title`、`description` 與非空 `applied_changes`，省略 `stage`、內部回執與未變正文。Create／Delete／已知無變更可只回 status，並非所有工具都使用同一 envelope；見[共同結果規則](2026-09-27-agent-tool-contract-design-research.md#6-成功回傳提供下一步需要的真實觀察)。候選寫入不等於發布。

```json
{
  "status": "updated",
  "title": "月末庫存盤點",
  "description": "每月核對實際庫存與帳面差異，異常交由主管確認。",
  "applied_changes": [
    {"field": "interview_references", "added": [28], "removed": [6]}
  ]
}
```

輸入 `changes` 是意圖，輸出 `applied_changes` 是 App 已確認成立的效果，不另列一份可能矛盾的欄位清單。引用使用相同的 `field` 名稱，輸入 `add`／`remove` 對應輸出 `added`／`removed`；只有新增就只回 `added`，不要求空的 `removed`。只列真正成立的改動，不能把原請求原樣回送就稱為成功。

改名後回新 title，供後續操作使用；短欄位變更只列 `{"field":"title"}`／`{"field":"description"}`，實際新值已在頂層，不重複。body 變更列 `{"field":"body","diff":"實際套用位置的差異與必要前後文"}`；此結果 diff 是程式由前後內容形成的觀察，不是再執行一次的指令，也不是無條件 echo 模型輸入。引用只列實際 `added`／`removed`；原來就有的 add 不列為新增。完整結果必須足以核對所有實際變更；容量不足不能靜默截斷或事後謊稱拒絕，沿既有容量／恢復邊界準備及保留原結果，必要全文再 read。確切容量數值、差異排版與輸出接線的實際效果仍需對應證據。

這不是全 App 強制相同 envelope，也不新增結果儲存或 receipt。[OpenAI 結果格式](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)允許 `function_call_output` 以字串承載 JSON／文字；回傳不是模型的 strict args schema，不因輸入的 required 限制強填無用欄位。

內容與引用比對均確認無變更才回 `{"status":"unchanged"}`；保存不明不得回 `updated` 或 `unchanged`。結果用 OpenAI 原生 `function_call_output` 配對原 call，不改成 system 指令或員工原話。

## 7. 錯誤與中斷

**結果語意：** `unchanged` 僅表示核對後沒有實際差異；`rejected` 表示本次全部未改，回具體原因與可行的修正方向；保存不明則先由 App 核對，不當成未修改交模型盲目重送。工程錯誤形狀與 scope／目標分類沿[共同錯誤契約](2026-09-27-agent-tool-contract-design-research.md#7-錯誤回傳與恢復責任)，以下補寫入特有分類；不是另建 validator。

寫入特有的 `code` 選定：同層重名 `title_conflict`；V4A 不合法 `invalid_patch`；無合格匹配 `patch_context_not_found`；多處匹配 `ambiguous_patch_context`；移除非既有引用 `reference_not_found`。帶 `status: rejected`、原因及可行 `next_action`，只有必要時加 field／hunk 或授權片段。這是錯誤語意，wire 接受性仍有各自證據。

| 情況 | 確定未保存時的必要回饋 | 下一動作 |
|---|---|---|
| 空／重複 changes、非法欄位／型別 | entry／field、合法形狀、本次未改。 | 模型修正意圖，不原樣重送。 |
| 找不到目標、同層改名重名 | 名稱問題及有權查看的定位資訊；不可藉錯誤展開禁止層內容。 | 重讀有權查看的導覽、重新選取或命名；不模糊改成他物。 |
| V4A 無法解析、零處／多處合格匹配 | hunk、原因、必要候選上下文，本次全部未改。 | 依實際正文補上下文／修 diff；不可默選第一處或最高分。 |
| 基準過時、原目標身分不明 | 不能依原觀察保存。 | 重讀與重新判斷，不偷偷重定向目標。 |
| 權限／執行資格不符 | 必要原因，不洩露禁止層內容。 | App 阻止執行，模型不得改 scope 繞過。 |

拒絕本次更新不清空整批候選。**保存結果不明不是普通拒絕：** 原責任模組先對帳，不說「沒改，請再送」。已成功則承接原結果，不重複套 diff；尚不明則交共用有界恢復／停止策略，不讓模型猜，也不以最新候選冒充原操作結果。

暫時故障由執行責任處理；有界恢復仍失敗才呈現必要狀態。不要回 raw exception、金鑰或其他職務檔案資料。依[共同錯誤規則](2026-09-27-agent-tool-contract-design-research.md#7-錯誤回傳與恢復責任)，不新增 retry 計數器、receipt 或通用 status 表。


## 8. 更新邊界與證據層級

| 行為範圍 | 預期效果與證據界線 |
|---|---|
| 靜態契約／wire | 最終註冊 schema 的 root、required、additionalProperties、nested anyOf 合法；不暴露 App 所有的 scope／版本；兩個權限面分開。 |
| 局部更新 | 只改一欄其餘不變；三欄及多 hunk 一起成功；後段失敗三欄均未改；空白／重複／未知 field 拒絕。 |
| 引用與回傳 | 三種內容＋本層引用可同次表示；只新增不必補 remove；B1／B2 分支隔離；內容或引用任一拒絕不半套保存；回傳實際效果與目前標題，不重印 stage、不是請求複本或已發布聲明；只改引用仍回 updated。 |
| 定位／權限 | 跨檔案隔離；目前候選同層重名拒絕，跨層可同名；不同版本／不同檔案沿用標題不誤拒；舊名稱重用後新呼叫選目前同名物件，既有引用／原操作重入不改綁；B1 不取得理解，B2 不改情境。 |
| V4A | 長 Markdown 帶上下文多處修改、唯一近似定位、重複／近似歧義拒絕、未指定內容原樣保留。既有探針只沿用已證範圍。 |
| 保存／恢復 | 計算完未保存、採用後確認遺失、基準已變：能區分原結果、不半套採用、不重複效果。真 PostgreSQL 業務保存與 checkpoint 接縫的證據不能只涵蓋其中一方。 |
| 模型行為 | 選對目標、正確修改、利用錯誤修正；量測誤改、呼叫／tokens／延遲。離線 PASS 不能證明模型行為。 |

上表說明更新行為與證據界線；實際覆蓋見驗收矩陣。文件檢查不構成功能通過，也不能由離線或 PG 結果推定模型品質。


## 9. 定位、來源與恢復界線

1. **title 比較與身分綁定已定：** 依[讀取契約 §4](2026-09-27-memory-read-and-source-navigation-contract.md#4-定位與權限界線)採精確字串比較、同層唯一、App 在本次 scope 解析 ID。C 從 X 改成 Y 後，D 可使用 X；新的 `target_title: X` 就選 D，不推測模型心中的 C、不強加先 read／proof。已綁 C 的引用或原操作重入仍是 C，不重新解析 X。Runtime 的原操作、候選基準及競爭保護須驗證，但不另建 alias registry 或要求模型猜 UUID。
2. **正文與來源的共同修改已定：** 三欄不是完整物件；來源引用不放 body，V4A 只修改正文。§10 的增刪與內容共同成功或拒絕；空來源合法，保留關係跟隨候選 identity，Memory 無逐引用確認。B2 語意重評與整包發布資格沿背景生命週期，不因一次寫入成功而通過；wire 與保存各自驗證。
3. **候選保存與恢復接線：** 依[共用執行](2026-09-27-shared-agent-execution-and-state-design.md)及[資料與交易](../architecture/persistence.md)已選定的責任，保存候選／原結果並在重入時補接；實測層級依驗收矩陣。

上述操作保持既定分責、歧義保護與共同發布；接線存在不代表各層效果已有實測證據。



## 10. 來源與正文共同修訂

來源不放 Markdown 正文的規則見[009 內容與來源邊界](../product-concept.md#分層工作記憶)。目的：修改工作事實時，能同時調整其依據，不因分開保存留下「新正文＋未調整的引用」。本節沿用[固定版本鏈](2026-09-24-caliburn-layered-architecture-map.md#來源與版本)、[B1／B2 分責及變更後重評](2026-09-25-b1-b2-information-gap-lifecycle.md#影響範圍與檢查責任)，不定資料表或長期短代碼；schema 依正式來源生成。

### 官方契約與可借鑑範圍

- **OpenAI 官方：** [file search](https://developers.openai.com/api/docs/guides/tools-file-search)的文字與 `annotations` 分開；`file_citation` 帶 `file_id`、`filename` 等資訊。顯示名稱與來源身分並非同一欄。這是 hosted file search 的契約，不表示自訂 Memory 工具自動取得引用功能，也不要求本案導入 file search／vector store。
- **Anthropic 官方：** [citations](https://platform.claude.com/docs/en/build-with-claude/citations)回傳來源 document index 與位置，文件 title／context 和可引用的 source 內容分開；官方保證有效來源指標的能力屬其原生 citations。不能把這項保證搬到本案自訂工具，亦不能由指標存在推導理解內容一定正確。
- **可借鑑的共同方向：** 引用有明確的結構化定位，不能只依正文裡的名稱／連結。**Caliburn 取捨：** 來源由模型選擇、身分與版本由 App 依明確意圖及實際核對基準處理；來源與正文可同次採用是本案已確認的目標，不是上述官方規定的唯一做法。查閱日：2026-09-27；無 provider／產品實測。


### 內容與結構化來源共同更新

同一物件更新可一併修改內容與結構化來源，共同成功或拒絕。來源只寫正文無法保證改名、版本及正式關係；拆成兩次呼叫則可能留下半套修改，因此均不作同一修訂的預設路徑。

來源依引用對象使用 `interview_references`／`work_situation_references`，不是第四個自由文字欄位。B1 保留有效訪談依據，B2 保留情境引用並沿鏈回查原話；JD 混合來源與關聯式編輯沿自己的契約。

已確認「可以一起改」，不要求每次 body 修改都重傳全部來源，也不要求每次來源調整都改正文。沒有來源修改意圖時保持原候選關係；有新增或解除依據時明確提出，不由 App 從新正文猜出引用。採明確增刪而非預設重傳全清單的目標已確認；命名與按需表示依 §3，不使用 `field: sources`。來源集合可為空；完整 wire 須以實際生成與 provider 接受證據驗證。

### 模型意圖、固定版本與反例

語意示例（不是正式工具參數）：

```text
目標：預約網站例行維護
正文：把「每月檢查」改成「每週檢查」
來源：保留仍相關的既有訪談，補入員工釐清頻率的那輪
    ↓
App 核對原物件、修改基準、來源資格與本批範圍
    ↓
正文與來源變更全部通過，才共同保存本次候選修改
```

「補入更正」不代表一律刪除舊原話；哪些舊來源仍有助理解經過，由責任 Agent 判斷。引用存在／版本合法由程式檢查，來源是否真的支持新敘述由 Agent 核對；有衝突仍按既定規則保留與釐清，不能靠格式驗證宣稱解決。

**title 選物件與正式固定引用仍分開。** 模型以 `target_title` 在有權限的層選當前候選；App 解析穩定物件身分，不用 title 作資料庫目標。候選關係綁定物件身分，沿來源讀取當前候選；正式發布後，快照才固定所選修訂及引用鏈。不得把歷史已發布引用偷偷解析成目前同名物件。

B1 修改情境 C 後，候選理解的既有關係仍指向 C；App 不因引用可解析成新版就宣稱 B2 已完成分析。B1 交接後不再修改本批情境，B2 依交付資料完成理解，才由 App 發布。歷史已發布理解保持原版本鏈。

**驗收條件：** 正文修改失敗或新增來源無效時，本次內容與來源均不採用；未改來源保留；候選來源不得外露成 A／JD 的正式依據；同名改指不得造成身分誤綁。候選保留關係沿同一身分讀當前上游，B2 仍須依變更資料重評語意，並非逐條換版或自動宣稱重評完成。已發布歷史不改寫。實際覆蓋依驗收矩陣。

**讀取：** map、物件回傳與逐層來源的詳細語意見[讀取契約](2026-09-27-memory-read-and-source-navigation-contract.md)。


### 來源選取與增刪

B1 選 App 提供的訪談序號；B2 選目前可見情境的 title。`add`／`remove` 只改關係成員，未提及者保留；保留的候選關係依物件身分跟隨當前候選內容，無需逐條換版動作。B2 依變更資料完成語意重評後，App 在正式發布時固定整包修訂鏈，見[生命週期](2026-09-25-b1-b2-information-gap-lifecycle.md#候選操作快照與三個安全點)。來源與正文可同次更新、共同成功或拒絕；本節不處理 JD 的混合來源寫入。

**研究比較：** [JSON:API 關係更新](https://jsonapi.org/format/#crud-updating-relationships)明確區分整組替換與指定成員新增／移除，也區分移除關係與刪除被引用物件。[Google AIP-134](https://google.aip.dev/134)則支持明確指定局部更新範圍，避免全物件替換誤清未指定資料。這些是成熟 API 契約的參考，**不證明某種表示對 LLM 一定最好，也不要求採用 JSON:API、field mask 或新框架** 。查閱日：2026-09-28；尚無本案模型比較實測。

採指定新增／移除、未提及者保留；不要求每次補一則來源都重列整組清單，避免漏列造成誤清。不另開通用關係管理工具。

**模型選現成的來源，App 處理正式身分：**

| 寫入者 | 選擇方式 | App 必須核對 |
|---|---|---|
| B1 修改工作情境來源 | 使用 App 已提供的訪談序號，例如 12、14、28；不是 Agent Turn 或自行編出的 ID。 | 映射固定來源 ID；同一職務檔案、有效訪談及本批固定上界。可用較早歷史，不限本批新訪談。 |
| B2 修改工作理解來源 | 使用允許範圍內工作情境的 title，例如「月末庫存盤點」。 | 映射目前候選情境的身分；不得以 title 作 DB 操作目標，也不能把歷史來源名稱偷換成目前同名物件。 |

移除須指向**目標物件目前來源集合中的關係** ，不是把同名／同序號的資料刪除。先在合法 scope 將目前標題解析成身分，再查該身分是否屬目標現有來源。例：理解仍連 C，C 改名 Y、D 使用舊名 X；`remove: ["X"]` 選 D，不得藉歷史名稱刪掉 C；若理解未連 D，整次回 `reference_not_found`，可讀理解目前來源後用 Y 選 C。這不新增讀取 proof 或把 X 永久保留給 C。


#### 引用修改命名與按需輸入

**`field` 明確指出被修改的引用類型，`add`／`remove` 表達該類引用的新增／移除。** 不再以籠統的 `sources` 或 `references` 作這兩種引用修改的 field，也不在操作名稱重複引用類型。此處確認的是模型可見名稱與語意，不要求 DB 改欄名或以標題操作資料。

| 可用者 | `field` | `add`／`remove` 的值 |
|---|---|---|
| B1 | `interview_references` | App 已提供的正式訪談序號，映射至符合資格與本批範圍的歷史訪談來源。不是 Agent Turn、DB ID 或模型新編序號。 |
| B2 | `work_situation_references` | App 提供、允許讀取的工作情境標題；`add`／`remove` 表達關係新增／移除，不以重新 `add` 同名情境冒充版本更新。 |

按需提供：只新增就只寫 `add`，只移除就只寫 `remove`，兩者都有才同時寫；不修改引用就省略整筆引用修改。不要求用空陣列或 `null` 補齊未執行的操作。未提及的引用保持不變；移除關係不刪原始資料或歷史版本。

以下是已確認命名／按需語意的示例，**不是完成序列化驗收的 wire** ：

```json
{
  "target_title": "月末庫存盤點",
  "changes": [
    {"field": "interview_references", "add": [28]}
  ]
}
```

需要同時移除訪談 6 的引用時，在同一筆加入 `"remove": [6]`，不建立兩筆相同 field。B2 的對應示例為 `{"field":"work_situation_references","add":["月末庫存盤點"]}`。

**引用分支：** 三種引用分支、筆數、非空操作與去重政策集中 §3；實際 strict wire 由正式來源生成驗證，不放寬成任意 JSON。來源集合允許空，不把空集合誤判為不合法；無效來源仍須拒絕。

**更新語意：** 不提供來源變更則保留；新增或移除都須明確指定。可與同次 title／description／body 更新一起採用，任一來源無效或正文修改被拒絕，本次整個更新不採用。同一來源同次又加又移除拒絕，不猜先後順序。確定是同一物件身分的已存在候選關係，重複新增為無變更；移除非既有成員拒絕，避免掩蓋 title 重用造成的誤選。保存結果不明仍走原責任模組對帳，不冒充拒絕或無變更。官方關係 API 的借鑑及本案差別見[工程方法依據](2026-09-27-agent-tool-contract-design-research.md#工程選擇與官方依據)。

例如 B1 修改某情境的頻率，同時新增訪談 28、移除誤綁的訪談 6，其他來源保留。移除 6 不刪除訪談 6，也不修改過去已發布 Memory 的來源鏈。訪談 28 是後續更正，**不代表較早原話都應刪除** ；仍有助理解條件或更正過程的來源可保留。來源指標有效不等於內容支持成立，語意仍由責任 Agent 核對。

**候選關係跟隨身分，重評是語意工作。** 理解已關聯情境 C，B1 修改 C：候選關係仍指向 C 的身分，B2 read 取得當前 C，App 提供前後變更讓 B2 判斷是否需修改理解正文、增刪關係或保留不變。B2 不需填修訂版本，不以 `remove`／`add` 換版，也沒有逐條確認工具。B1 交接後不再修改本批情境；歷史已發布鏈保持不變。

B1 不處理理解對情境的關係；B2 決定自己的理解內容及關係，不提交逐條換版確認。

**驗證界線：** 模型可見完整 wire、改名與名稱重用時的身分解析、候選保存與恢復。無來源物件可以存在；Agent 不得把無依據推測寫成已確認事實。正式發布的快照版本與歷史回查仍須正確。

**驗收反例：** 只加一筆不遺失舊來源；移除不刪來源原文／歷史；跨檔案、超界或取消來源拒絕；來源失敗不留下正文半改；同名異物不誤連；相同情境新版不被重複新增冒充重評。B1 連續修改不新增逐次 B2 審查；交接後由 B2 完成分析。反例不是通過紀錄。


## 11. 建立與候選刪除

建立、刪除與更新只作用本批同一份候選；以下定義模型參數與結果，wire 與實測分開。

建立與刪除入口為 `create_work_situation`／`create_work_understanding`、`delete_work_situation`／`delete_work_understanding`；前者各屬 B1／B2。Create 根含 `title`、`description`、`body` 與本層 `interview_references`／`work_situation_references`，全部必填；無來源明列 `[]`，不用 null，不放 changes。來源值、精確標題與去重沿本頁及 read 契約；Create 的空集合不受 Update 增刪操作非空限制。Delete 根僅含 `target_title`；所有物件禁止額外欄位，模型不填 scope、cascade 或版本。

1. **建立：** 模型提供 `title`、`description`、初始 Markdown `body`；可選合法來源，來源集合允許空。缺少來源不等於允許憑空捏造正文；已知／未知的語意由責任 Agent 如實表達。標題在目前候選的**同層** 有效集合內唯一，跨層同名可成立。
2. **刪除情境：** 從目前候選移除情境，App 在同一採用邊界解除所有指向它的候選理解關係；理解物件本身仍在，B1 不取得理解名稱／正文。B2 在自己的分析中看新增、移除及受影響資訊，決定是否修訂或移除理解。不猜替代來源，不改寫已發布 Memory／JD 歷史依據。
3. **刪除理解：** 從目前候選移除理解及其候選關係，不刪上游情境、訪談或正式 JD。

**操作保證：** 每次有效候選操作須共同成功或共同拒絕，map／read 隨採用結果顯示目前候選；不讓懸空候選關係等到發布才由第二套修復流程處理。空來源理解可如實保留，是否有助於工作分析由 B2 判斷。B2 的語意完成與 App 操作有效是兩種不同責任；已發布歷史仍可回查。

**行為邊界：** 無來源建立或移除最後來源可成立；無效來源拒絕；B1 移除被引用情境時候選關係同步解除且不洩露理解；B2 對變更完成語意分析後才能發布；舊 Memory／JD 的固定依據仍可回查。實際覆蓋依驗收矩陣。模型可見範例見 [CRUD 範例](2026-09-28-memory-tools-crud-examples.md)。

**建立結果：** 依提交內容完整建立並可可靠承接後，正常成功只回 `{"status":"created"}`，不重複 title、description、引用清單或 stage。候選限定由工具契約及 App 執行保證，不靠每次重印欄位成立；若未完整採用或結果不明，不可套用此成功回傳。共同取捨見[工具結果規則](2026-09-27-agent-tool-contract-design-research.md#6-成功回傳提供下一步需要的真實觀察)。

**Delete 最小結果：** 物件從候選移除、必要的候選關係解除及原結果均可靠成立後，回 `{"status":"deleted"}`；不是僅記錄未執行意圖，不是永久刪除歷史或發布成功。不回受影響理解清單給 B1。新的 delete 找不到目前目標回 `target_not_found`，不偽稱刪除；同一原操作恢復則取原結果，不重執行、不把舊 title 重新綁到新物件。此選擇沿共同規範的高訊號短結果原則，內部保存資料不縮減為 status。

**保存與恢復界線：** 一般候選編輯維持 title 選取＋App 身分綁定；正式歷史回查仍讀當時固定快照，不能只取同名最新物件。B2 的變更閱讀、語意完成與候選提交須能在中斷後辨認；不增加每筆關係確認、不要求模型填版本，也不先恢復所有操作必填 `read_ref`。
