# 匯出格式說明

入口：`POST /api/v1/documents/{profile_id}/export?format=<format>`  
實作：`app/services/document_service.py`

---

## JSON

`get_enriched_export_json(profile_data)` — 回傳完整可追溯 JSON（Stage 4 #17）。

```json
{
  "ocs_document": { ... },
  "evidence_refs": [
    {
      "source_type": "star_slot",
      "evidence_kind": "direct",
      "source_phase": "star_task_001",
      "field": "A",
      "value": "從 ERP 匯出原始資料，用 Python 清洗合併"
    }
  ],
  "icap_reference_pack": {
    "icap_mode": "reference",
    "icap_hit": true,
    "candidates": [
      { "ocs_code": "INF-001", "icap_title": "資料工程師", "similarity": 0.82, "confidence": "high" }
    ]
  },
  "quality_scores": {
    "設計 ETL Pipeline": { "quality_score": 0.86, "quality_status": "ok" },
    "資料品質監控":       { "quality_score": 0.43, "quality_status": "force_accepted" }
  }
}
```

`evidence_refs` 是所有 task / indicator 的 evidence 展開列表，方便審閱工具直接掃描。  
OCS 文件結構見 [ocs-schema.md](./ocs-schema.md)。

---

## DOCX（Word）

`generate_docx(profile_id, profile_data)` — 使用 `python-docx`。

### 文件結構
1. **標題**：職稱（Heading 1）
2. **基本資訊表**：部門、OCS 代碼、iCAP 候選信心（高/中/低信心）
3. **職務描述**：`ocs_profile.job_description`
4. **iCAP 對應**：候選清單（信心標籤 + 職稱 + 推薦等級 + 檢索分數）
5. **職能單元與任務**：
   - 每個 OCU 一個 Heading 2（代碼 + 名稱）
   - 每個 Task 一個 Heading 3（代碼 + 名稱）
   - 行為指標表：P代碼 / 指標文字
   - 工作產出表：O代碼 / 名稱
   - 知識/技能表：代碼 / 名稱 / 來源（iCAP 或企業）
6. **工作態度**：態度表（A代碼 / 名稱 / 來源）
7. **說明與補充事項**：`ocs_profile.notes`（若有）

---

## PDF

`generate_pdf(profile_id, profile_data)` — 使用 `reportlab`。

佈局與 DOCX 相同，以 ReportLab `SimpleDocTemplate` + 各種 Flowable 渲染。

**字型解析**（P0 修正）：`_find_cjk_font()` 依平台自動搜尋，優先使用 Noto Sans TC。

| 環境 | 字型搜尋路徑 |
|------|------------|
| Docker / Linux | `/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf`（由 `fonts-noto-cjk` 安裝） |
| Windows | `C:/Windows/Fonts/NotoSansTC-VF.ttf` → `NotoSansCJKtc-Regular.otf` → `msjh.ttc` |
| macOS | `/Library/Fonts/NotoSansTC-Regular.ttf` → `PingFang.ttc` |

自訂覆蓋：設定 `FONT_PATH` 環境變數（空值 = 自動偵測）。找不到任何字型時 fallback 至 `Helvetica`（無 CJK 支援，但不崩潰）。

---

## Excel（XLSX）

`generate_xlsx(profile_id, profile_data)` — 使用 `openpyxl`。

### 版面（仿 iCAP 官方單張格式）

```
Row 1:  [標題列] 職能基準單（合併 A1:G1）
Row 2:  OCS 代碼 / 職稱
Row 3:  職務描述（合併 B3:G3）
Row 4:  職業代碼 / 職類別 / 產業別（三格各自 label + value）
Row 5:  （空白間隔）
Row 6:  欄位標題列（藍色背景）
        A: 主要職責 | B: 工作任務 | C: 工作產出 | D: 行為指標 | E: 職能等級 | F: 知識 K | G: 技能 S
Row 7+: 資料列
```

### 合併邏輯
- 同一 OCU 的所有資料列合併 A 欄（主要職責）
- 同一 Task 的所有資料列合併 B 欄（工作任務）
- C 欄（工作產出）：`O1.1.1 名稱\nO1.1.2 名稱\n...` 多行合併
- D 欄（行為指標）：`P1.1.1 文字\nP1.1.2 文字\n...`
- F 欄（知識 K）：`K01 名稱[iCAP]\nK02 名稱\n...`（iCAP 官方標 ✓）
- G 欄（技能 S）：同上

### 態度區段
主表格後加入橘色標題列「工作態度 Attitude」，再列出 A01~A0n。

### 說明與補充事項
最後以淺藍色標題列 + 內容文字呈現 `ocs_profile.notes`（若有）。

---

## 欄寬設定

| 欄 | 說明 | 寬度 |
|----|------|------|
| A | 主要職責 | 16 |
| B | 工作任務 | 20 |
| C | 工作產出 | 22 |
| D | 行為指標 | 40 |
| E | 職能等級 | 10 |
| F | 知識 K | 30 |
| G | 技能 S | 30 |

---

## 檔名規則

`<ocs_code>.<format>` — 例如 `DAT-001.xlsx`  
若 `ocs_code` 無法取得，fallback 為 `<profile_uuid>.<format>`。

---

## 來源標籤（display_label）

每個指標、K/S/A、態度項目均在文件中標示 `display_label`。

> **注意：匯出文件顏色與前端 UI 顏色不同。** 前端 `SourceBadge` 元件使用 Tailwind 色票（藍/紫/琥珀/灰）；匯出文件使用以下 HEX 值，符合印刷可讀性要求。

### 匯出文件顏色（DOCX / PDF / XLSX，`document_service.py` 定義）

| 標籤 | 顏色（HEX） | 意義 |
|------|-----------|------|
| `[訪談確認]` | `#05966B`（綠）| 有工作者直接引述或 STAR slot |
| `[iCAP參考]` | `#1D4ED8`（藍）| 來自 iCAP 官方或 icap_reference |
| `[AI整理]` | `#6B7280`（灰）| AI 從結構化欄位萃取，未直接引述 |
| `[待確認]` | `#D97706`（橘）| 品質不足或尚未確認 |

### 前端 UI 顏色（`SourceBadge.tsx` 定義）

| 標籤 | Tailwind 色票 | 視覺色 |
|------|-------------|------|
| `[訪談確認]` | `bg-blue-100 text-blue-700` | 藍 |
| `[AI整理]` | `bg-violet-100 text-violet-700` | 紫 |
| `[iCAP參考]` | `bg-amber-100 text-amber-700` | 琥珀 |
| `[待確認]` | `bg-gray-100 text-gray-600` | 灰 |

DOCX：以括號文字附在內容後。  
PDF：以彩色小字標示於行尾。  
XLSX：對應儲存格顯示彩色標籤文字（K/F/G 欄知識技能態度區）。

---

## 已知問題與改善方向（Review 結論）

> **P0 問題已於 2026-05-20 全部解決。** 以下保留原始問題描述與解決方式供參考。

### ✅ 來源標籤（P0 已解決）

**已實作**：DOCX / PDF / XLSX 中的指標、K/S/A、態度均標示 `display_label`，4 種標籤以顏色區分（見上方說明）。

### ✅ PDF 字型跨平台問題（P0 已解決）

**已實作**：
1. 移除硬編碼路徑，改用 `_find_cjk_font()` 平台自動偵測
2. Dockerfile 安裝 `fonts-noto-cjk`（Linux/Docker 無需額外設定）
3. 支援 `FONT_PATH` 環境變數覆蓋（`.env.example` 已加入說明）
4. XLSX 字型同步改為 `_resolve_xlsx_font()` 平台感知（Windows: 微軟正黑體 / macOS: PingFang TC / Linux: Noto Sans CJK TC）

### ✅ JSON 匯出補充（Stage 4 #17 已完成）

**已實作**：`get_enriched_export_json()` 回傳 `ocs_document` + `evidence_refs`（展開）+ `icap_reference_pack`（mode/hit/candidates）+ `quality_scores`（任務品質摘要），見上方 JSON 結構範例。

### ✅ document freeze API（Bug #3 已解決）

**已實作**：`POST /documents/{profile_id}/freeze` 直接從 `graph_state["ocs_document"]` 建立 `DocumentVersion`，無需先 export；設 `stage = "preview"` 後 ocs_builder 不再觸發。
