# Case records

本目錄在執行前放置六個固定 JSON case。每個 case 同時包含四個 arm 所需的 paired Context；
四者必須來自同一 transcript，不得額外替某個 arm 補答案。

## Case JSON 格式

```json
{
  "case_id": "CR-01-tools-not-tasks",
  "case_family_id": "CR-01",
  "source_type": "constructed_edge",
  "title": "工具不得升格為工作",
  "primary_risk": "員工提到 Java、Python 與 HTML，但它們只是完成工作的手段",
  "applicable_critical_checks": [
    "C1_TOOL_BOUNDARY",
    "C6_SOURCE_FIDELITY"
  ],
  "transcript": [
    {
      "source_id": "turn-001",
      "role": "consultant",
      "text": "請描述最近一次完成這項工作的過程。"
    },
    {
      "source_id": "turn-002",
      "role": "employee",
      "text": "案例正式內容會在執行前寫入。"
    }
  ],
  "claim_table": [
    {
      "claim_id": "claim-001",
      "speaker": "employee",
      "literal_text": "必須是 source_turn_ids 所指 turn text 的逐字子字串",
      "source_turn_ids": ["turn-002"],
      "sequence_index": 1
    }
  ],
  "relevant_span_ids": ["turn-002"],
  "adjudication": {
    "must_retain_tasks": [],
    "must_not_create_tasks_from": ["Java", "Python", "HTML"],
    "allowed_task_variants": [],
    "required_uncertainties": [],
    "notes": "正式裁決在 trial 前固定，不傳給受測 subagent。"
  }
}
```

上例只定義格式，示意文字不得直接拿去跑 trial。正式案例建立後，不得保留「正式內容會在執行前寫入」
等模板文字。

## claim_table 構造規則（硬性）

claim table 是 P0 的**唯一自變數**。它只做原子化切分，不做任何職務分析判斷。

**只有這五個欄位**：`claim_id`、`speaker`、`literal_text`、`source_turn_ids`、`sequence_index`。

**禁止欄位**：`actor`、`time_scope`、`responsibility`、`candidate_kind`、`corrections`、`unresolved`、
`qualifiers`，以及任何等價命名。這些欄位與 rubric 的 C1／C2／C4／C5 幾乎一對一，
填了就是把答案卡交給受測模型（見 README §3.1）。

1. **逐字**：`literal_text` 必須是 `source_turn_ids` 所指 turn `text` 的**逐字子字串**，
   不得改寫、摘要、補主詞或修正錯字。建立案例後以字串包含檢查驗證全部 claim。
2. **完整覆蓋**：claim table 必須收錄員工的**每一條陳述**，包含工具提及、過去工作、他人責任、
   假設語氣與後來被撤回的說法。**不得因為「那不是 Task」而不收** —— 用省略排除等於用答案卡排除，
   而且會讓 `structured_only` 塌成 `raw_only` 的改名版。
3. **切分規則寫死**：一條獨立陳述一個 claim（可獨立判真假的最小主張）。
   一個 turn 通常產生多個 claim；一個 claim 不得跨 turn。
   **切分不得剝掉附著在該陳述上的否定、時間與對比標記**：「後來停掉了」「那不是我做的」
   「只有旺季才」「本來是我，現在換人」這類詞必須留在同一個 `literal_text` 裡。
   把標記切掉會人工製造 C4／C2 失敗，那是切分瑕疵，不是結構化表示的性質。
4. **順序保留**：`sequence_index` 從 1 連號，依 transcript 出現順序。這是模型能判更正／否定
   先後關係的唯一線索——因為 `corrections` 欄位已刪除。
5. **顧問 turns 不進 claim table，但不能從 structured-only 消失**：claim table 只收
   `speaker: "employee"` 的陳述；所有 `role: "consultant"` turns 必須逐字、完整、依原順序保留在
   `structured_only` payload。短回答依賴提問才能理解，刪掉提問會預先製造資訊損失，而不是公平測試
   員工原話被字面 claims 取代的效果。

### `structured_only` 現在能損失什麼（收窄後的診斷射程）

顧問提問逐字保留、員工陳述逐字覆蓋、順序保留、標記不剝離——四條規則會大幅縮小
`structured_only` 與 `raw_only` 的資訊差距，但兩者仍不只差句間連接詞。`structured_only`
同時引入原子化切分、row 邊界、claim ID 與顯式 `sequence_index`，並省略未進 claim 的非主張片段
（「不過…」「講到這個」「嗯，那個…」等）。因此這個 arm 量的是**整個字面原子化表示轉換的淨影響**，
不能把結果歸因成單一的「句間膠效果」。

反過來說，這個 arm 已經不能宣稱「用結構取代原文會遺失脈絡」這種大結論——
它只回答「這一種人工字面原子化表示，相對完整員工原話的淨影響為何」。案例作者若把切分做到
幾乎逐句照搬，表示差異會很薄；若為了製造損失而剝掉標記，就違反規則 3。兩種情況都要在
`adjudication.notes` 說明切分判斷，讓 `report.md` 能誠實界定這個 arm 的射程。

## Context 組裝

四個 arm 都保留原始 `source_id`，讓輸出的 `source_ids` 可驗證：

- `raw_only`：只傳 `transcript`。
- `raw_plus_spans`：傳 `transcript`，再把 `relevant_span_ids` 指向的 turns **逐字重貼一次**
  為「相關片段」；不含 claim table。
- `hybrid`：傳 `transcript` ＋ 相同的逐字相關片段 ＋ `claim_table`。
- `structured_only`：依 transcript 原順序組裝一條混合 stream：顧問 turns 逐字保留；每個員工 turn
  以其 `source_turn_ids` 對應的 claim rows 取代。不得遺漏任何顧問 turn，也不得把完整員工 turn
  偷渡回 payload。

**`hybrid` 必須含完整 transcript。** 原設計省略未選中的 turns，於是同時改動「結構」與「資訊刪減」，
差異無法歸因。長對話壓縮另開實驗。

`raw_plus_spans` 與 `hybrid` 的相關片段必須是**同一組** `relevant_span_ids`，逐字相同、順序相同，
否則兩者的差異就不只是 claim table。

`adjudication` 不傳給受測 subagent；reviewer subagent 會收到（判 `C6_SOURCE_FIDELITY` 需要）。

實際 Context 與完整 `subject_request` 由實驗目錄內的 `assemble_context.py` 組裝。例如：

```powershell
python assemble_context.py cases/CR-01-tools-not-tasks.json raw_only
```

合法 arm 為 `raw_only`、`raw_plus_spans`、`hybrid`、`structured_only`。CLI 輸出的 envelope
只供 orchestrator 保存 metadata；受測 subagent 只收到其中的 `subject_request`。

## 驗證

在實驗目錄執行：

```powershell
python validate_cases.py cases
python -m unittest test_assemble_context.py -v
python -m unittest test_validate_cases.py -v
```

驗證器只檢查可決定的機械規則：固定六案、欄位白名單、逐字子字串、單一 employee source turn、
turn／claim 連號與順序、每個 employee turn 至少一個 claim、相關片段引用及模板占位文字。
它**不宣稱**能驗證「每一條語意陳述皆完整覆蓋」或切分是否公平；這兩項仍須依本文件規則人工審查，
並寫入 `adjudication.notes`。

## 凍結規則

- 六個案例一次完成後才開始 trial。
- `relevant_span_ids` 的選取本身帶人工判斷，因此選取理由寫進 `adjudication.notes`；
  選取不得只挑「支持正確答案」的 turns，也要納入容易誤導的關鍵句。
- 若 transcript、claim table、`relevant_span_ids` 或 `adjudication` 有任何實質修改，
  既有 trial 不得混入新版結果。
- P0 不沿用舊 Evidence schema、gold、loader、grader 名稱或 suite hash；舊案例只能提供語意陷阱靈感。
