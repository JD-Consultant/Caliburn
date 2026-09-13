# 關聯式 JD：AI、App 與員工操作契約

- 日期：2026-09-12
- Topic：JD-R002/C02、C03
- 階段：G4 WORKING；八操作、真 PG 共同保存、读取／原次差異及查詢、人工 writer／Windows 重啟恢復已隔離驗證。[人工 HTTP 接合](2026-09-13-jd-manual-http-slice.md)再接保存／原操作查回／狀態／明示恢復，原結果不因斷線或新版本重做。文件入口 HTTP、持久配置、AI call 綁定、source owner／選區、人工 notice 與完整 App 仍待完成；不是整體 G4 或 production 採用。
- 上層設計：[整體設計](2026-09-12-jd-relational-editor-design.md)
- 保存契約：[資料庫與保存](2026-09-12-jd-relational-schema-and-write-contract.md)

## 1. 契約目的

模型應專注於理解工作及撰寫內容；App 應承擔身分、定位、關係、版本、排序、交易與真實結果。模型不需要填一整份 JD JSON，也不需要算行號、DB UUID、外鍵、position、revision 或 operation key。

OpenAI 與 Anthropic 的現行官方資料共同支持「模型回結構化工具意圖、App 執行、再回帶 call identity 的真實結果」；strict schema 降低參數形狀錯誤，但不取代 App 的業務驗證。[OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)、[Anthropic How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)、[Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)

## 2. 工具按完整業務效果設計

既有 v2 `jd_edit` 面向完整文件樹；本稿原七工具又把部分完整工作拆得過細。依[業務操作研究 §1–2](2026-09-12-jd-business-operations-and-scope-design.md)，採具名操作，補完整新增任務、有界整組內容修訂及選區替換；不凍結工具數，也不直接開任意 command array。OpenAI 的連續功能合併與 Anthropic 的工作流程導向支持這個方向，strict schema 本身不決定操作粒度。

App 將所有 mutation 映入相同 domain command、validator、短交易與結果 owner。一次跨欄責任更正必須用一個原子入口，不讓人工整組保存、模型只能逐欄碰運氣。具體輸入如下；generated schema、固定操作及真 PG 保存的局部結果沿頁首路由。正式模型接線／自然操作尚未驗證，不能把合成工具序列當自然訪談成果。

## 3. Model-facing 工具

### 3.1 `jd_read`

**何時使用：**開始撰寫前、收到人工變更通知後、target 過時／不存在後，或需要查看某項完整內容與關係時。

```json
{
  "view": "current | item | section | history",
  "target_ref": "issued ref or null",
  "cursor": "issued cursor or null"
}
```

所有三欄在 strict schema 中 required；可空欄使用 JSON null。模型不填 document ID 或 revision。App 從目前 run scope 注入 document，回傳：

- `revision_ref`
- 可讀的 profile／items／relations
- typed `section_ref`、`item_ref`、`field_ref`、`container_ref`
- source refs 及 `current | needs_recheck`
- 分頁 cursor 與是否還有未讀內容

current read 的 refs 綁定該 revision。正文、head、關係、來源目標狀態及 refs 的一致讀取依[保存契約 §9](2026-09-12-jd-relational-schema-and-write-contract.md#9-歷史diff-與-export-read)：同一次短唯讀交易 materialize 後再產 refs；不得另查最新 head。分頁 cursor 綁 revision，下一頁若 head 改變就要求重讀，不接混版頁面。外部原始問答來源／可讀性另由 source port 查核並分開標示，不承諾跨系統同一快照。名稱可重複，模型靠 ref 定位，不靠名稱搜尋後直接寫。

2026-09-13 局部實作：[讀取 SSOT](../../experiments/jd-relational-app/contracts/jd-read.schema.json)已生成 Python／TS 的 `ReadInput`、`ReadPage`、`ReadFailure`，由[讀取投影](../../experiments/jd-relational-app/src/jd_relational/reads.py)及[兩家 adapter](../../experiments/jd-relational-app/src/jd_relational/read_transport.py)共用。`current` 的 target 必須 null；`item`／`section` 使用同類 issued ref；`history` 的 null target 列出固定上界歷史，revision ref 讀指定舊稿。歷史 item／section 可續讀原版，回 `access=history`；即使該版等於 head，其 refs 仍不可寫。

`ReadPage` 固定版本 1，交付 `view`、`access`、`revision_ref`、typed records、`start_index`、`total_records`、`has_more`、`next_cursor`、`oversized_unit`。records 包含章節、容器、項目、完整欄位、任務 K/S 關係、來源，歷史索引另含版次／origin／時間／原 producer 的 operation/change refs。頁面按 UTF-8 bytes 有界分段，過大的單一允許欄位用明示單項頁完整交付，不截斷正文。沿原 view／target 與 cursor 續讀，讀完頁不等於專業內容已完整。source 的 `basis_status` 可由本版材料判斷，`readability` 目前回 `not_checked`；source owner 的真正查回另待接線。真 PG 接合與 SDK 離線序列化證據分列於[本輪結果](2026-09-13-jd-read-change-implementation.md)，後續 HTTP 查詢已由[接合切片](2026-09-13-jd-query-api-and-recovery-identity-slice.md)驗證；顧問／自然模型仍未接通。

### 3.2 `jd_set_text`

**何時使用：**單獨更正一個已存在欄位的完整文字。不可接受 selection_ref；依選區修改用 §3.9，多欄必須同時正確用 §3.10。

```json
{
  "target_field_ref": "issued field ref only",
  "text": "new complete field text",
  "basis_refs": ["issued source ref"]
}
```

`target_field_ref` 可指 profile field、duty name/scope、task name/description、detail text、capability name/description、condition text 或 collaborator field。`text` 永遠是該欄完整新全文，不是要插入的一小段。清空文字仍驗 item 是否有有意義內容，不用清空模擬刪除整筆 item。

`basis_refs` 可為空陣列，表示這次沒有可引用來源；模型不能自行拼 source ID。App 驗 scope、可讀性與 target type。

可空欄的 text 允許 null；非空欄／整筆 item 仍依最終約束驗證。來源沿 §9，不能因一欄提供 basis 就聲稱整筆 target 的其他內容已被核實。

### 3.3 `jd_insert_item`

**何時使用：**新增職責、成果、要求、知識、技能、條件或協作對象；task 改用 §3.8 完整新增。一次提供目前已知且屬該項的內容，未知可空；不強制先保存名稱再補正文。

```json
{
  "item": {
    "kind": "knowledge",
    "container_ref": "issued knowledge container",
    "after_ref": null,
    "name": "資料介面與失敗情境",
    "description": "理解前端與後端交換資料時的狀態、失敗訊號及可能的重複操作。",
    "basis_refs": ["issued source ref"]
  }
}
```

`item` 依 kind 生成明確形狀，外層是固定 object；不把全部 nullable 欄位塞到所有種類：duty／collaborator 用 name＋scope_text；knowledge／skill 用 name＋description；outcome／requirement／condition 用 text。共同項為適型 container_ref、after_ref、basis_refs。每個 variant 的所有 keys 在 strict schema required，可選文字用 null；name／正文任一有意義即可，純 text item 需有正文。App 配發 ID／position，核同文件／container／after sibling；成功回 change_ref，下一次寫入以 current read 取得新 refs。不要求模型挑 SQL 欄位或從 initial_text 猜名稱。

kind 的 domain 名稱穩定；requirement 的中文 label 可調整而不改 enum。typed nested variant 的兩家 adapter 相容性列 §10 零副作用驗證，不能因例子可讀就聲稱 provider 已接受。

### 3.4 `jd_delete_item`

**何時使用：**員工已明確要求移除一筆 item，或顧問確認該項是錯誤且刪除影響已理解。不要用空字串更新模擬刪除。

```json
{
  "target_ref": "issued item ref",
  "content_changes": []
}
```

App 決定 ownership effects；保存回傳 §6 的輕量結果，完整實際差異由 §3.7 讀取。capability 還被引用時回 dependent_items。D01 刪 duty 保留 tasks，由 App 一次解除分組再刪 duty，不讓模型逐項改 FK。刪 duty 時 content_changes 只接受 §3.10 的 set_field／add_task_detail：既有欄位限該 duty 下存活任務的 name／description／detail text；新增成果／要求限這些任務，不含被刪 duty 或其他獨立工作。非 duty 刪除只接受空陣列。內容與結構同一候選、同一交易；失敗不丟原 scope。完整相關上下文與來源處理依[業務設計 §3](2026-09-12-jd-business-operations-and-scope-design.md#3-r05-裁決必要範圍隨任務職責摘要不產生繼承)。

### 3.5 `jd_move_item`

**何時使用：**改變 task 所屬職責，或調整同一清單中的 item 順序。不要以刪除＋重建模擬移動。

```json
{
  "target_ref": "issued item ref",
  "destination_container_ref": "issued container ref",
  "after_ref": "issued sibling ref or null",
  "content_changes": []
}
```

App 保留 stable ID、從屬內容、K/S 與各自來源，不以刪除重建模擬移動。task 跨職責／未分組移動時，content_changes 只接受 §3.10 的 set_field／add_task_detail：修正該任務 name／description／detail text 及來源／目的 duty 的既有摘要，或為該任務新增成果／要求；其他排序只接受空陣列。App 核全部 targets 屬此次相關範圍、同基準且存活；不能改旁邊獨立 task。無內容調整只改 parent／positions，有調整則全部原子保存，不能先移後補。after_ref=null 表示容器第一個；未分組仍使用 App-issued container ref。

### 3.6 `jd_set_task_capability`

**何時使用：**新增或解除某 task 對既有 knowledge／skill 的引用。不要另存可漂移的整份能力定義副本或反向 task list；任務特有的應用方式／限制仍可寫在任務內容。

```json
{
  "task_ref": "issued task ref",
  "capability_ref": "issued knowledge or skill ref",
  "mode": "link | unlink",
  "basis_refs": ["issued source ref"]
}
```

App 檢查兩者存在、同文件且 capability kind 合法，對 junction relation 做 idempotent set/unset。link 的來源可附在 relation target；unlink 不因 capability 沒有其他使用者就自動刪除定義。

unlink 的 basis_refs 必須為空；不能對已移除的關係新增 current source link。

### 3.7 `jd_change_read`

**何時使用：**需要知道某次人工／AI 保存到底改了什麼，或人工變更通知的摘要不足以繼續判斷時。

```json
{
  "change_ref": "issued change ref",
  "cursor": "issued cursor or null"
}
```

App 回確切 before/after revision refs、origin、create/update/delete/move/reorder/link/unlink、field before/after、受影響 item refs、source link 變動及分頁狀態。工具不依 AI 先前摘要重建差異。

2026-09-13 實作：`ChangeReadInput`／`ChangeReadPage` 已由 read SSOT 生成，[ChangeReadService](../../experiments/jd-relational-app/src/jd_relational/change_reads.py)重用原 `HistoryReader` 的 receipt／base／result 與固定 `compare_snapshots`；兩家 adapter／HTTP 查詢／真 PG 及新程序依[切片結果](2026-09-13-jd-query-api-and-recovery-identity-slice.md)通過。結果含原 operation/change/base/result refs、origin、records/counts/cursor。每個 `change_index` 對應一個淨變更，header、前後完整值、來源 basis/position、排序鄰項及受影響任務可跨頁；每個允許欄位不截斷。所有內容 refs 都是唯讀歷史，cursor 綁原 operation/result，不改用目前 head。reorder 比较存活 sibling 的相對順序，鄰項只表示當版順序，不宣稱還原真實拖動動作；插入／刪除引起的 position 正規化不另冒稱使用者修改。實際來源回查仍未接線。

### 3.8 `jd_create_task`

**何時使用：**某項工作已有足夠資訊，可建立一個能辨識的任務；同時寫入其目前已知內容，不必等待全部資訊完整。

```json
{
  "container_ref": "issued duty or unassigned-tasks container",
  "after_ref": null,
  "name": "處理約定範圍的前端異常",
  "description": "依服務約定釐清及處理前端異常；超出本人範圍的部分交由相應角色處理。",
  "basis_refs": [],
  "outcomes": [{"text": "已排除的異常或清楚轉交的處理資訊", "basis_refs": []}],
  "requirements": [{"text": "處理過程保留辨識問題所需的資訊，不能確認結果時不冒稱已修復。", "basis_refs": []}],
  "capabilities": [{"capability_ref": "issued existing knowledge or skill ref", "basis_refs": []}]
}
```

這是合成外形示例，不得拿示例內容當員工事實。name／description 可 null，但至少一個有意義；三個清單可空，不能為填滿補造。清單順序就是希望顯示的順序，ID／FK／position 全由 App 產生。同一 capability 最多引用一次；每項 basis 只屬自己的來源目標。App 在同一候選建立 task、owned details、K/S relations 與來源，全部驗證後一次保存；任何失敗都不留下 task 空殼。新增結果回原 operation／result revision／change refs，整組確切變更由 change read 取得；續編先讀 current，不由名稱猜新項定位。

### 3.9 `jd_replace_selection`

**何時使用：**員工已選取單一文字欄位內的片段，App 已在確認保存後發配 selection_ref；只修該片段。

```json
{
  "selection_ref": "issued selection ref only",
  "replacement_text": "每季",
  "basis_refs": []
}
```

replacement_text 永遠只替換選區，不是整欄新全文；不接受 field_ref、不讓模型填舊文字／行號／offset。精確候選為 prefix＋replacement＋suffix；basis refs 必須支持正式來源目標的完整內容，未核全段則保留空陣列，不把局部來源升格。欄位／版本過時或選區不符就拒絕，不能搜尋同字續寫。Web 原生 UTF-16 範圍與後端標準字串轉換、LF 及保存前交接依[業務設計 §4](2026-09-12-jd-business-operations-and-scope-design.md#4-r04整欄與選區的唯一語意)。

### 3.10 `jd_revise_work`

**何時使用：**依新資訊修訂同一項工作理解，需要使正文、成果／要求、K/S 引用或全職位條件一起正確；一般獨立單欄使用 jd_set_text。

```json
{
  "changes": [
    {"kind": "set_field", "target_field_ref": "issued task description field", "text": "釐清前端異常並提供技術診斷；後續客戶承諾由負責窗口處理。", "basis_refs": []},
    {"kind": "add_task_detail", "task_ref": "issued task ref", "detail_kind": "requirement", "after_ref": null, "text": "無法確認根因時，清楚區分觀察結果與待驗證假設再轉交。", "basis_refs": []},
    {"kind": "set_task_capability", "task_ref": "issued task ref", "capability_ref": "issued erroneous service skill ref", "mode": "unlink", "basis_refs": []}
  ]
}
```

這是合成外形，不是員工事實。外層固定 changes object，每項依 kind 生成下表的嚴格型別，非遞迴 commands；至少一項。

| kind | 該 variant 的其餘 required keys／語意 |
|---|---|
| set_field | target_field_ref、text（完整新全文，可 null）、basis_refs；允許 §3.2 的欄位，null 仍須通過最終欄位／item 約束 |
| add_task_detail | task_ref、detail_kind（outcome／requirement）、after_ref、text、basis_refs；為既有任務新增有意義子項 |
| remove_task_detail | detail_ref；移除既有成果／要求及其 current source links |
| set_task_capability | task_ref、capability_ref、mode、basis_refs；同 §3.6，unlink 時 basis_refs 必須為空，不為已刪關係留來源 |
| add_condition | container_ref、after_ref、text、basis_refs；container 綁定既有第六章 condition kind |
| remove_condition | condition_ref；移除該條件與其 current source links |

不允許職責／任務／K/S 定義／協作對象的新增刪除、任何移動、選區替換、任意 JSON path 或本次新 ID 的相依引用。這些另走具名操作；無新 condition 種類或條件繼承引擎。

所有 refs 先按同文件、同 base 解譯。每欄最多一次；同項又改又刪、同關係重複或相反設定、anchor 指向本次刪項、混版本／錯型別，全部拒絕，不以陣列順序暗中覆蓋。after_ref 必須是同容器與 kind 的存活既有 sibling，null 表示第一個；同 anchor 的新增按輸入順序呈現。App 產新 ID，模型不引用尚未保存的新列。先組出完整候選並驗證，再把同列最終欄位一起寫入；名稱清空＋有意義敘述一起新增應按最終狀態通過。

任一項無效、過時或整組超限，全部不套用。上限依[業務設計 §2](2026-09-12-jd-business-operations-and-scope-design.md#2-工具粒度保留具名操作補完整工作)，不偷偷拆成多次呼叫。來源逐變更指定，移除不會自動把 link 改掛新項。專業含義由顧問核實，App 負責候選、版本、關係與保存結果。

2026-09-13 精確化：所有具名內容工具的 `basis_refs=[]` 表示此次不新增／刷新來源，保留舊 links 與 basis；非空只新增或刷新列出的 refs，不刪未列者。同 target 多欄更新的 refs 穩定合併，以最終候選正文計算 basis，不能最後一欄覆蓋前一欄的來源。精確集合與去重／順序見[來源保存 §3.10](2026-09-12-jd-relational-schema-and-write-contract.md#310-jd_source_link)。來源能讀或 basis 匹配都不保證專業內容已核實。

## 4. App command 與模型工具的關係

員工一次有意義的保存可含多個相依內容變更，例如「改 task 描述、加兩項成果、把 task 移到另一 duty」。2026-09-13 [HTTP 接合](2026-09-13-jd-manual-http-slice.md)釐清早期通用 ordered commands 草案：Web 實際送 generated `ManualSaveInput`，使用同一具名完整業務操作；上述移動及必要內容調整由 `jd_move_item.content_changes` 原子處理，其他相依更正用 `jd_revise_work`，不提供任意 batch：

```text
document scope（route 注入）
base view token（App 持有）
operation identity（App 配發）
command（Web 從實際 UI 意圖選具名操作及 generated arguments）
```

Web 不向員工顯示 JSON。模型不直接取得這個通用 transport，而是使用上述完整業務入口；两者映入相同 service、validator、transaction、snapshot 與 receipt。人能在一個已定業務意圖中做的原子更正，AI 也必須有對應入口；不存在「只有人工可以全部成功或全不改」的規則。

完整 create_task、有界 revise_work、含必要內容調整的 move／delete 都是一個原子業務效果。彼此獨立的多次呼叫才各自保存並如實回報；後一次失敗不撤銷前一次已確認結果。同一責任更正不能用多個 set_text 逐次提交。App 不跨模型回合保持 SQL transaction，不替模型自動合併多個 tool call，也不因某家回多個 tool_use 就推定共同 atomic batch；同文件 mutation 依既有 gate 與版本逐一處理。

## 5. App 發配的 refs

| ref | 綁定內容 | 模型能做什麼 | 失效條件 |
|---|---|---|---|
| `revision_ref` | document＋revision | 識別讀到的版本 | head 前進仍可歷史讀，不可 current 寫 |
| `section_ref` | document＋revision＋六章 section kind＋current/history 用途 | 讀完整章節 | current 過時拒絕；history 保留原版且不可寫 |
| `item_ref` | document＋revision＋entity kind＋stable ID | 刪除、移動、讀完整項目 | target 被刪或 current 已改到不能安全套用 |
| `field_ref` | item/profile＋field name＋base value digest | 更新完整欄位 | field／revision 過時 |
| `selection_ref` | field ref＋exact selection digest/range，由 App 產生 | 替換選取內容 | 選取欄位被改或內容不再匹配 |
| `container_ref` | document＋revision＋允許的 child kind | 新增／移動 | container 被刪或過時 |
| `source_ref` | source owner＋document scope＋可讀範圍 | 作 basis、回查原文 | scope 不符、來源不存在或權限失效 |
| `operation_ref` | document＋原 operation，observation 用途 | 識別原保存結果 | 不因 head 前進改指新操作；只讀 |
| `change_ref` | document＋原 operation＋原 result revision；base 從原 receipt 查得 | 讀真實差異 | 不因 head 前進失效；只讀 |

refs 是由 App 驗證的固定型別定位字串，不是 writer permission；模型以 opaque token 使用，不能拼接或推導另一個 ref。2026-09-13 [ReferenceCodec](../../experiments/jd-relational-app/src/jd_relational/references.py)已用 ItsDangerous 標準簽章核 document、dataset、revision、purpose 及 ref/cursor 用途；payload 可解碼，沒有加密或身分授權宣稱。`current` refs 才可經 resolver 組成可信 CommandContext；`history`／`observation` 只讀，同版 head 也不升格。source refs 仍由 source owner 發配，不重簽成 JD 來源別名；selection issuer 尚未接線，不將一般 field token 當 selection。宿主 key／dataset 持久化及還原世代仍依 DA-03 完成，不建立第二份資料權威。

## 6. 統一 mutation result

所有模型 mutation 工具回同一外形；provider adapter 以 OpenAI 的 call ID 或 Anthropic 的 tool-use ID 回到正確工具迴圈。

App 從既有持久 run／可信 binding 注入 `ai_run_id`，與每筆 operation 的意圖、base／result 和確認回執一起保存；模型不填此欄，不因下一輪清除暫態 binding 而丟掉歷史歸屬。詳細約束依[保存契約 §4.3](2026-09-12-jd-relational-schema-and-write-contract.md#43-jd_operation)，不以 model-view 通知基準代替回合起點。

```json
{
  "status": "committed",
  "effect": "changed",
  "receipt_durability": "confirmed",
  "operation_ref": "op_...",
  "result_revision_ref": "rev_...",
  "change_ref": "chg_...",
  "error": null,
  "next_action": "continue"
}
```

失敗範例（只適用於已綁定原 operation，且 failure receipt 已實際提交成功）：

```json
{
  "status": "stale_view",
  "effect": "unchanged",
  "receipt_durability": "confirmed",
  "operation_ref": "op_...",
  "result_revision_ref": null,
  "change_ref": null,
  "error": {
    "code": "stale_view",
    "message": "這個任務在你讀取後已被修改；目前文件沒有套用本次內容。",
    "related_refs": ["task_..."]
  },
  "next_action": "reread_current"
}
```

`effect` 與 `receipt_durability` 是兩個獨立事實，沿原 v2 契約區分 confirmed／unconfirmed，不新增第三種 durability：binding 前拒絕為 unchanged／unconfirmed 且無 operation ref。binding 後若尚未查明原回執是否存在就讀取／連線失敗，維持 unknown／unconfirmed；不能因本次未寫 SQL 而判定原操作未改內容。已跨原操作邊界並證正文 rollback，但回執未確認時為 unchanged／unconfirmed。COMMIT 未確認時，可能改正文者為 unknown；只提交 no_change／failure receipt 則仍為 unchanged。**只要原 operation 已 binding 但無確認 terminal，App 的 next action 必須先 reconcile_operation，優先於要求模型修正或重讀後新寫。**App 持有 operation identity，不要求 LLM 補填；原結果查回及 failure-only 閉合詳[保存契約 §6.2–7](2026-09-12-jd-relational-schema-and-write-contract.md#62-人工或-ai-保存)。同 key 改 base／payload 拒絕，不可當成重試原意圖。

Anthropic 官方建議 tool error 說明發生什麼及可採取動作；本案將它固定成 machine-readable status＋員工可讀 message＋有限 next action，不讓模型從自由文字猜是否重試。[Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)

2026-09-13 精確化：[結果 SSOT](../../experiments/jd-relational-app/contracts/jd-result.schema.json)固定以上八 keys 與合法狀態分支，拒絕 `candidate_ready`。mutation result 保持輕量，移除舊例 `actual_changes`；完整前後文字／結構／來源差異沿原 immutable base/result，公開入口依 §3.7 完成，不以 AI 摘要替代。永久 receipt 只保存穩定身分／結果語意；[原觀察投影](../../experiments/jd-relational-app/src/jd_relational/observation_projection.py)已由真實 `WriteObservation` 發配原 operation／result／change refs 並驗 shared result，未確認仍先 reconcile。此投影不查新 head、不重播、不改 receipt，投影失敗也不改稱保存失敗；寫入 HTTP host 與正式顧問接線仍待完成。永久／對外邊界仍沿[讀取前置](evidence/2026-09-13-jd-read-reference-preflight.md)。

[HTTP 投影](2026-09-13-jd-result-and-storage-foundation.md#http-與模型外殼)在寫入回應使用 200 成功、202 待對帳及具名 4xx／5xx Problem；成功查回觀察使用 200，body 保留原結果。查回服務自身失敗另由 host 回報。`operation_conflict` 不接受衝突意圖、無本次 operation ref，原 receipt 保留。未 binding 的內部保存前錯誤可回 `save_failed/unchanged/unconfirmed` 並停止；已 binding 而未確認則一律 reconcile。這些是本案映射，非兩家供應商指定的 HTTP 或資料表格式。

## 7. 錯誤、重讀與重試矩陣

| status | 誰處理 | 允許行為 | 禁止行為 |
|---|---|---|---|
| `invalid_input` | 模型／App | 依欄位說明修正一次；仍失敗停止 | 換 operation key 重送相同錯誤 payload |
| `target_missing` | 模型 | `jd_read current`，確認新狀態後再決定 | 按名稱猜另一 target |
| `stale_view` | 模型／Web | 重讀；人工保留 dirty buffer，重新比較 | App 偷換 latest token 自動覆蓋 |
| `relationship_conflict` | 模型 | 讀相關 items，修正 relation | App 以同名或第一筆自動接線 |
| `dependent_items` | App 呈現，員工／顧問判斷內容意圖 | 顯示仍被引用的 K/S 等相依內容，依已定明示解除／改接流程處理 | 模型自行選 cascade／set NULL；僅因 duty 有 tasks 就要求重選 D01 政策 |
| `save_failed` | App | 保留候選，停止寫入並顯示原因 | 在不知根因時自動多次 retry |
| `outcome_unknown` | App | 用同 operation identity 對帳 | 新 operation 重做、向員工宣稱失敗或成功 |
| `operation_conflict` | App | 停止，保存原 receipt | 覆寫原 operation payload/result |
| `busy`／`archived` | App／Web | 閱讀；閉合 writer 或恢復文件後再開始新意圖 | 只解除 UI disabled 後直接 POST |

模型最多就同一語意錯誤做一次有根據的修正；額外工具與 token／時間／費用仍沿既有 run budget。這個次數是 Caliburn 的保守起始策略，不冒稱 OpenAI 或 Anthropic 規定。

## 8. 人工修改如何進下一輪 context

以下為尚待接線的人工 notice 設計；本輪已能讀原歷史與算純差異，尚未實作 response-backed 基準或將 notice 注入顧問。App 保存一個 response-backed `last_model_view`，只記模型最後確實收到的 JD revision／change boundary。下一輪組 request 前：

1. App 先完成手改保存與 AI 交接，依保存契約 §9 在同一次讀取交易取得 current head H；
2. 由同份讀取材料查 `(last_model_view, H]` 的 committed operations，不能在另一快照接上 H 之後事件；
3. 分開 manual／AI／no-change，不能只看兩端文字是否相同；
4. 組成有界 App context notice；
5. notice 放在模型 request 的 application context，不改員工原始 HumanMessage，不寫 Memory；
6. request 實際送達並與 AI response／checkpoint閉合後，才前進 last_model_view。

概念外形：

```json
{
  "type": "jd_change_notice",
  "current_revision_ref": "rev_H",
  "manual_change_count": 2,
  "ai_change_count": 0,
  "events": [
    {
      "change_ref": "chg_1",
      "origin": "manual",
      "summary": "員工修改任務『客戶需求釐清』的敘述",
      "before_preview": "...",
      "after_preview": "..."
    }
  ],
  "details_omitted": false,
  "instruction": "這是 App 保存事件，不是員工新說的一句話。需要完整內容時使用 jd_change_read；知道有變動不代表本輪必須修改 JD。"
}
```

大量改動只放固定上限的事件與預覽，保留總數、界線及 `details_omitted=true`；模型按需讀。改了又改回仍有兩個 manual events，不因 head 文字等於舊版就稱沒有改過。

員工整份還原 JD 有實際變更時，亦產生新的 manual event；App 附具名還原種類、實際 base/result、已核的歷史來源 revision 與 change ref，說明「只還原 JD、沿用舊版依據，未重新核對較新訪談」。no_change 只留下操作結果，不偽造內容事件。不把模型已讀基準、聊天或 Memory 一起倒退，也不把歷史 target refs 當新 current refs。對大量內容仍有界預覽及完整回讀入口；實際 DTO 欄位沿 SSOT 生成，模型無須填這些欄位。[還原與續談](2026-09-12-jd-history-and-recovery-design.md#5-身分來源與-ai-續談)

[HR-02 整輪撤回](2026-09-12-jd-ai-turn-undo-design.md#6-與工作理解案例及原始對話的關係)亦沿 manual notice，附 `undo_ai_turn`、被撤回 T 與實際 JD 前後版本，說明只撤 JD、不代表否定本輪工作資訊。不自動寫 Memory 或重套原稿；沒有原因時由顧問依下一輪意圖釐清。`undo_ai_turn` 只供人工端，模型不新增此工具，也不負責計算是否可撤回。

## 9. 來源引用契約

本版 source_ref 限 source owner 實際發配、可回讀精確原始問答的引用；H4 的 `purpose="window"` 只有在[完成窗口契約](2026-09-13-jd-interview-window-source-contract.md)及用途感知 owner adapter 通過後才是合法種類，不能由 JD 端重簽或把 `purpose="source"` 默認改解。Memory／詳記協助找回材料，不把可變 Memory 路徑當永久來源；尚無 Memory-version locator。沿[既有來源研究 §4](2026-09-10-jd-context-change-and-source-research.md#4-jd-是否要引用-memory)，較新更正的效力仍由顧問核對，不靠 target digest 自動判斷。

2026-09-13 接合已驗來源 resolver 回跨 scope／不可讀時，在 binding 前拒絕；真保存後人工改文令舊 basis 成為 `needs_recheck`，明示刷新才更新 basis，歷史不變。這些測試使用合成 Source；原始問答 owner 尚未接到新版 port，readability 不偽報已查證。

- AI 新增／改寫文字時可提交已發配 `basis_refs`；App 驗來源屬同文件且可讀，再建立 `jd_source_link`。
- 員工手改不自動新增 source，也不把員工操作當成原始訪談。舊 source link 保留但因 basis digest 不符顯示 `needs_recheck`。
- AI 可讀原來源後，確認仍支持新文字時重新連結／更新 basis；不能只因 Memory 摘要看起來相似便自動背書。
- K/S relation 本身是專業主張，可把 basis link 掛在 `jd_task_capability` relation；反向 task list不再另存來源。
- source 有效只證明能回查原材料，不等於文字完整、專業或沒有誤解；顧問仍做 JD→source 及 work→JD 雙向核對。
- 人工整份還原的有界分支由 server 從同文件內部歷史恢復原 source links／basis，不因暫時不可讀而靜默丟棄，也不重新宣稱專業支持。這不是 AI 新增来源的豁免；來源的新建／重連仍須查核。還原的範圍與來源提示沿[歷史契約](2026-09-12-jd-history-and-recovery-design.md#5-身分來源與-ai-續談)。

## 10. 需要 provider schema spike 的一點

八個編輯工具、`jd_read` 與 `jd_change_read` 已由 SSOT 生成並完成兩家 SDK 的離線 serialization fixture；精確範圍見頁首切片。後續擴充仍沿下列檢查，不因十個入口已驗便凍結工具數或宣稱 provider／模型已接受：

- 所有 properties required，optional 語意用 nullable；`additionalProperties=false`；strict enabled。
- tool name、description、enum 大小、refs 長度與 output parsing 在兩家 adapter 各驗一次。
- 特別驗 nested discriminated variants、完整任務與 bounded changes，避免 root union／無關 null 欄位；離線驗證不代表 provider 實際接受，服務端接受與自然選用留核准的模型批次。
- 不把 provider 不支援的 regex、union 或 schema feature放入正式契約。
- fixture 只驗 wire shape，不宣稱自然模型會在正確時機選對工具；後者另用自然訪談案例驗。

若工具的 prompt／cache 成本或選擇錯誤在實測成為主要問題，再比較合併相鄰入口或工具發現能力。先驗證明確工作流程，不以固定七個工具作架構要求。

## 11. 本輪 OPEN 與非目標

- JD-R002/D01 任務保留政策已依 Owner 授權裁決；工具與人工共用完整效果。JR-R02／03 已通過[保存文件窄複核](evidence/2026-09-12-jd-relational-save-contract-review.md)，JR-R01／04／05 已通過[完整操作文件複核](evidence/2026-09-12-jd-business-operations-review.md)；均未實測。草稿／還原產品選擇已記[需求 §11](2026-09-12-jd-relational-editing-requirements.md#11-本輪裁決草稿歷史與還原2026-09-12)，恢復工程前置與整體 G4 仍待閉合。
- 2026-09-13 Owner 延後 Excel，先完整 App／業務／LLM；匯出不進 model tools，也不阻本輪契約。之後優先 Excel／原話分開輸出的方向保留。
- 不增加模型用 archive、rename、history restore、DB query 或 raw JSON edit。JD 工具不重建 Memory 寫入入口；顧問仍可沿既有即時修補與背景整併反覆修訂工作理解。
- 不讓 AI 每輪自動改 JD；是否撰寫由顧問方法與已理解資訊決定。
- 新隔離目錄已接 generated 輸入／結果／snapshot／read／query Problem、共同保存、原操作完整差異、兩個 HTTP 查詢及原身分恢復；尚未取代正式產品契約。實際 writer／持久 runtime、source owner、selection issuer、人工 notice、寫入 HTTP／Web／autosave、還原／整輪撤回及採用仍沿新版計畫。不混寫舊 v2；完整驗收界線見[查詢接合](2026-09-13-jd-query-api-and-recovery-identity-slice.md)。
