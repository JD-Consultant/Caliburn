---
title: JD deterministic export——資料組裝、位置碼、格式與 ocs-contract 重用問題（研究紀錄）
date: 2026-08-06
purpose: 為匯出切片開 ADR 與 plan 的權威研究依據
---

# JD deterministic export 研究紀錄

> 本切片是「可交付 JD 成品」的最後一塊：ADR [0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md)
> 決定 14 明文「**正式匯出為 deterministic，不讓 LLM 參與。本 ADR 不實作匯出。**」——那份 ADR 只裁決了
> header／readiness／代碼權責，把匯出本身留白。這份研究把留白補上，供接下來的 ADR 與 plan 依據。

## 1. 官方一手來源（複用既有核對，不重跑）

匯出的表格版型、欄位與代碼權責已由兩份既有研究紀錄逐字核對過，本文件直接引用，不重新下載 PDF：

- [`2026-08-02-icap-2026-quality-manual-form-authority.md`](2026-08-02-icap-2026-quality-manual-form-authority.md)
  ——2026-01-27《職能基準品質認證作業手冊》，2026-08-02 自 icap.wda.gov.tw 逐字核對。
- [`2026-07-13-ai-redesign-raw-icap-field-standards.md`](2026-07-13-ai-redesign-raw-icap-field-standards.md)
  ——2022《職能基準發展指引》，欄位定義與撰寫標準（表格版型改以上述 2026 手冊為準）。

官方表格結構（附錄二／F3-3，兩份研究一致）：

```
表頭：職能基準名稱（職類／職業擇一） | 所屬類別（職類別／職業別／行業別＋代碼） | 工作描述 | 基準級別
表身：主要職責(T1) → 工作任務(T1.1) → 工作產出(O1.1.1) → 行為指標(P1.1.1) → 職能級別
      → 職能內涵 知識(K01) → 技能(S01)
態度：文件層一次列出（A01…），「態度內涵將於後續職能應用時視需求納入考量」
說明與補充事項：條件式欄位
```

`職能基準代碼`／`職類別代碼` 標「（iCAP 計畫執行單位提供）」——ADR 0052 決定 8 已裁定不開欄、不列缺漏、
不得生成，本研究沿用，不重新論證。

## 2. 現有資料模型盤點：官方欄位 vs `app/job_analysis` 現況

| 官方欄位 | 現有型別／欄位 | 缺口 |
|---|---|---|
| 職能基準名稱 | `JdHeader.competency_name` | 無 |
| 所屬類別（職類別／職業別／行業別＋代碼） | `JdHeader.occupation_category_name/occupation_name/occupation_code/industry_name/industry_code` | 無（`職能基準代碼`／`職類別代碼` 依 0052 決定 8 刻意不開欄，見上） |
| 工作描述 | `JdHeader.work_description` | 無 |
| 基準級別 | `JdHeader.competency_level`（1–6，nullable） | 無 |
| 主要職責 T{i} | `Duty`（`duty_id`／`statement`／`display_order`） | 無——**位置碼待算**，`duty_id` 不是 `T1` |
| 工作任務 T{i}.{j} | `JdTask`（`duty_id`／`statement`／`display_order`） | 同上；`display_order` 是**文件層**唯一，`T{i}.{j}` 的 `{j}` 要在同一 Duty 內重新從 1 編 |
| 職能級別（每任務） | `JdTask.competency_level`（1–6，nullable） | 無 |
| 工作產出 O{i}.{j}.{k} | `OpksItem(entity_kind=OUTPUT)`，`task_refs` 恰一個 | **無序**——見 §4 |
| 行為指標 P{i}.{j}.{k} | `OpksItem(entity_kind=INDICATOR)`，`task_refs` 恰一個 | 同上 |
| 職能內涵 知識 K{n} | `OpksItem(entity_kind=KNOWLEDGE)`，文件層、多對多 `task_refs` | **無序**——見 §4 |
| 職能內涵 技能 S{n} | `OpksItem(entity_kind=SKILL)`，文件層、多對多 `task_refs` | 同上 |
| 態度 A{n} | `OpksItem(entity_kind=ATTITUDE)`，文件層、無 refs | 同上；Web 已可新增（`OpksEditor.tsx` 有「新增態度」） |
| 說明與補充事項 | `JdHeader.notes` | 無 |

**六個公版欄位已全部有位子**，不需要新的 domain 欄位。真正缺的只有**位置碼推導**與**排序**兩件事。

`JdTask` 另有四個公版沒有的欄位：`purpose_result`／`context`／`frequency_text`／`responsibility_role`／`enablers`。
`docs/product-notes.md`「內部 Job Model 不等於政府公版」一節已裁定：這些是內部分析詳情，**公版是 export
profile，不是內部資料上限**——同一節也說「未來匯出才要求與公版格式一模一樣」。這句話目前唯一懸而未決的
是：**匯出時這些欄位完全不出現，還是以附錄形式跟著公版表一起交付？** 兩種讀法都不違反已有裁決，需要在
ADR 裡選一邊（§7 開放問題之一）。

## 3. 位置碼推導規則（決定性算法，不落庫）

ADR 0052 決定 10 已定調「依 Duty／Task／O／P 的排序決定性產生」。具體算法：

```
T{i}         = duties 依 display_order 排序後的第 i 個（1-based）
T{i}.{j}     = 該 Duty 底下的 tasks 依 display_order 排序後的第 j 個
O{i}.{j}.{k} = 該 Task 底下 entity_kind=OUTPUT 的項目，依「§4 的排序」排序後的第 k 個
P{i}.{j}.{k} = 同上，entity_kind=INDICATOR
K{n}         = 全文件 entity_kind=KNOWLEDGE，依「§4 的排序」排序後的第 n 個（文件層平坦編號，不分 Duty/Task）
S{n}         = 同上，entity_kind=SKILL
A{n}         = 同上，entity_kind=ATTITUDE
```

**未指派 Duty 的 Task 沒有 `T{i}.{j}`。** 這不是這個切片的邊角案例，是 Duty 切片 T1–T6 已經處理過的
一等公民狀態（`readiness` 的 `task_duty_missing`）。匯出必須**如實顯示「未歸入主要職責」**，不得為了湊出
一個位置碼而編造一個假 Duty——這正是 ADR 0052 決定 13「不得自動合成假的 T1」的匯出端體現。

## 4. 一個尚未被任何 ADR 回答的空缺：O/P/K/S 在同一 Task／文件內的順序

`Duty` 與 `JdTask` 都有員工可排序的 `display_order`（reorder route、Web 上下移按鈕）。**`OpksItem` 沒有**。

實測 `SqlAlchemyOpksRepository.list()`：

```python
.order_by(JobAnalysisOpksItemRow.created_at, JobAnalysisOpksItemRow.entity_id)
```

即讀出順序是**建立時間**，決定性、跨次讀取穩定，但**員工無法重新排序**——不像 Duty／Task 那樣有上下移按鈕。
這對「一個 Task 下有兩條工作產出，`O1.1.1` 該算哪一條」是個真實問題：目前的答案是「先建立的算 1」，
這是一個**產品決定**（要不要讓員工控制 O/P/K/S 在表上的先後），不是純技術問題，本研究不代為決定
（§7 開放問題）。

## 5. `ocs-contract` 能不能直接當匯出目標？——**不建議，且要修正一份現有文件**

`docs/contract-strategy.md` §5 對契約 #4（`job-analysis-contract`）的既有預答寫著：

> 「`ocs-contract` remains the public/export shape and neither contract imports or redefines
> the other.」

這句話寫於 2026-07-30（`f45b268`），**早於**兩個後來讓它站不住腳的決定：

1. **2026-08-01（ADR 0048/0049）**：K/S/A 從「掛在某條行為指標下」修正為**文件層平坦編號、與 Task/Indicator
   多對多**。而 `packages/ocs-contract` 的 `TaskGroup.competency_blocks[].knowledge/skills` 是**巢狀在
   每個 Task 的 CompetencyBlock 底下**——那正是 2026-08-01 更正框特別否掉的舊讀法（「一條 K 只能掛一條 P」）。
   直接塞進 OCS 形狀，等於把 0048/0049 費了兩輪修正才理清的多對多關係，逼回巢狀單一擁有——K/S 若支援多個
   Task，要嘛在每個 Task 底下複製一份（製造 0049 明確要避免的重複），要嘛選一個 Task 掛、其餘 Task 的關聯
   丟失。
2. **本切片本身（Duty）**：`OcsProfile.ocs_code` 是**必填**欄位，而它正是 ADR 0052 決定 8「不得生成」的
   `職能基準代碼`。若照抄 OCS 形狀，匯出時要嘛違反決定 8 生一個假代碼，要嘛把必填欄位留空——兩者都是在
   繞開一個已經裁決過的規則，而不是在遵守它。

**結論：`ocs-contract` 目前的形狀不適合直接當本產品的匯出目標，`contract-strategy.md` 那句預答需要在 ADR
裡明確覆蓋（不是默默繞過）。** `ocs-contract` 本身仍該保留——它是 `pdf-to-json`／`ocs-indexer` 那個 bounded
context 的既有契約（解析既有官方 PDF、餵 Qdrant reference 檢索），跟 `app/job_analysis` 產出全新客製 JD
是兩件事，不搬、不重寫、不繼承。

`contract-strategy.md` 的判準本身仍然適用：匯出的中介資料形狀是不是要走 JSON-Schema seam，取決於它有沒有
**非 Python 消費者**。若匯出全在 API 端完成（組裝 → 直接渲染成檔案位元組回應），Web 端**不需要解析**匯出用
的中介形狀，只需要觸發下載——那就不构成新的跨語言 seam，不必新開一份 JSON Schema 契約（§6 呼應）。

## 6. 檔案格式：三個函式庫已裝好、零使用

```
apps/api/pyproject.toml:  python-docx==1.1.2
apps/api/pyproject.toml:  openpyxl==3.1.5
apps/api/pyproject.toml:  reportlab==4.2.2
apps/api/pyproject.toml:  jinja2==3.1.4
```

全部從 2026-07-26 那次大合併（PR #5）進來，`app/` 底下**完全沒有任何 import**——是懸而未用的依賴，不是
已經選定的路線；不能當作既有決定引用，只能當作「這三條路都預先鋪好了地」。

三個選項各自對應官方送審與「交主管／HR 審閱」兩種使用情境：

| 格式 | 對應函式庫 | 優勢 | 劣勢 |
|---|---|---|---|
| **DOCX** | `python-docx`（已裝） | 主管／HR 最熟悉的審閱格式，可直接留言、修改；`docs/product-notes.md`「可匯出後交主管／HR 審閱」最直接對應這個情境 | 表格版面（T1/T1.1/O1.1.1 巢狀縮排）在 Word 表格裡做起來比 Excel 囉唆 |
| **XLSX** | `openpyxl`（已裝） | 官方 F3-3 本質是一張大表，欄列對應最直覺；許多政府單位習慣收 Excel | 不利於「請主管寫審閱意見」這種敘事性回饋 |
| **PDF** | `reportlab`（已裝） | 唯讀、版面穩定，適合最終交付 | 主管／HR 沒辦法直接在上面改字或留言，來回審閱要另外開會或口頭講 |

**本研究的建議（不是決定）**：先做 **DOCX**，理由是它最貼合 `docs/product-notes.md` 已經定調的
「員工確認 JD 草稿，可匯出後交主管／HR 審閱」——審閱意味著會有回饋迴圈，DOCX 是唯一原生支援这件事的格式。
XLSX／PDF 留給日後切片，不在本次範圍內拍板。這是建議，最終選擇留給 ADR。

## 7. 開放問題與其後續裁決

本節原為「待決」清單，[ADR 0058](../adr/0058-jd-deterministic-export-shape-and-format.md) 已裁決其中三項，
於此標明結果，避免下一個讀者把已決事項當成仍然開放。

| 問題 | 結果 |
|---|---|
| O/P/K/S 的顯示順序要不要員工可控？（§4） | **已裁決：要**（0058 決定 5）。`OpksItem` 取得 `display_order`，在 `(document_id, entity_kind)` 內唯一，沿用 Duty／Task 先例。因此拆出前置排序切片。 |
| `JdTask` 四個內部欄位匯出時出不出現？ | **第一版不印**（0058「不在本 ADR 範圍」）。公版表沒有這些欄位。 |
| 職業別／行業別代碼要不要格式檢查？ | **仍開放**，不擋匯出。 |
| readiness 缺漏要不要印在匯出檔案上？ | **已裁決：公版表留白 ＋ 獨立缺漏工作表**（0058 決定 12）。關鍵是 ADR 0052 決定 **4**（「未來 exporter 呼叫同一套 assessment」）——本研究初稿漏讀了這條，若匯出完全不呼叫 assessment，該決定會變成死條文。 |

另有一項本研究未列、由 ADR 0058 決定 4 處理的文件矛盾：**行為指標位置碼是三段還是四段**。
ADR 0052 決定 10 與兩份逐字核對官方 PDF 的研究紀錄都寫三段 `P1.1.1`，只有 ADR 0055 的**脈絡散文**
寫成四段 `P1.1.1.1`。三段為準——官方允許操作性任務省略 O、成果併入 P，若 P 巢狀於 O 底下，
省略 O 就會讓 P 無處可掛。

### O 與 P 的關係（本研究初稿未處理，補記）

結構上 O 與 P 是 Task 底下的**平行**項目，公版表格**沒有**表達兩者對應的欄位；
`domain/opks.py` 也明文禁止 OUTPUT 帶 `indicator_refs`（ADR 0048 決定 5 依官方編號裁定 O/P 掛 Task）。

但**官方語意確實耦合**：O 是「對應該工作任務**及行為指標**之關鍵產出項目」，且操作性任務的成果
「列於行為指標之描述中」。這個耦合目前由 **rubric** 接住而非 schema 連結——ADR 0048 決定 18–19：
無實體交付物時 O 寫成維持的狀態／避免的後果／遵循的規章；連這都寫不出來則標記 Task 邊界可疑、
退回 `work.reconcile`、不硬補 O。是否要在模型層表示該耦合，屬品質工作面，匯出不需要。

## 8. 對 ADR 的建議走向（已由 ADR 0058 採納，保留原文以供追溯）

- 匯出分兩層：**純組裝**（`ExportDocument` 值物件，零 IO，比照 `assess_readiness()`）與**渲染**。
- `ExportDocument` **不進 `packages/job-analysis-contract`**——不跨語言邊界，Web 只觸發下載。
- 單一 `GET /documents/{id}/export`，回傳檔案位元組，不經過 JSON 型別。
- 匯出永遠放行（ADR 0052 決定 5 已裁決，本切片只是實作它）。

**與最終 ADR 的差異**：本研究建議 DOCX 為第一版格式（理由是主管／HR 審閱需要回饋迴圈）；
owner 於 2026-08-06 裁定改為 **XLSX**——官方 F3-3 本質是一張大表，且政府單位與 HR 慣於收 Excel。
