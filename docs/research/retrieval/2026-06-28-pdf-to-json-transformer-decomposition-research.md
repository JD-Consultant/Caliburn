# 研究紀錄 — pdf-to-json `ocs_transformer.py` god-file 拆解(Phase 3b)

> 研究紀錄(decision log）。執行前的權威研究 + 現狀分析 + 方案取捨。對應 plan:稍後 `docs/plans/…phase3b…`。日期 2026-06-28。

## 1. 問題

`apps/pdf-to-json/src/jd_pdf_to_json/transformers/ocs_transformer.py` = **1492 行的單一 god-file**(`OCSTransformer` 一個類別),涵蓋「PDF → OCSDocument」的全部邏輯。違反單一職責,難維護、難測、難讀。Phase 3b 目標:拆成內聚的小單元,**行為不變**。

## 2. 現狀分析(實際結構 — 已有自然縫)

`OCSTransformer` 內部其實**已分區**(原始碼已有區段註解),且「主擷取器」與 OCS 文件區段一一對應:

| 群組 | 方法 | 性質 |
|---|---|---|
| **Orchestrator** | `transform()`(83–130) | 呼叫各主擷取器、組 OCSDocument |
| **主擷取器(對齊 OCS 區段)** | `_extract_version_info`(770)、`_extract_profile`(825,~170 行)、`_extract_content`(996)+`_parse_ocu_table_units`(1122,~300 行)、`_extract_attitude`(1421)、`_extract_notes`(1451) | 每個對應一個文件區段 → **天然的 filter 邊界** |
| 共用:文字正規化 | `_normalize_text`/`_compact_wrapped_text`/`_split_lines`/… | utility |
| 共用:表格工具 | `_clean_table_rows`/`_detect_table_type`/`_build_column_map`/`_find_*`… | utility |
| 共用:條目擷取 | `_extract_output_items`/`_extract_behavioral_indicators`/`_extract_competency_items`/`_extract_task_level` | 被 content 擷取器用 |
| 共用:去重 | `_dedupe*`/`_dedupe_block` | utility |
| 共用:歷史 PDF 掃描 | `_scan_ocu_names_from_text`/`_scan_task_names_from_words`/`_derive_task_code…` | 被 content 用 |
| 共用:單元組裝 / profile 小工具 | `_merge_ocu_unit`/`_extract_*_from_table`/`_match_profile_label`… | utility |

**關鍵觀察:拆分縫已經存在** —— 主擷取器(version/profile/content/attitude/notes)是天然的「區段 filter」,其餘是它們共用的工具。而且這些區段**正好對齊 `ocs-contract` 的文件結構**(Phase 2 的成果),前後呼應。

**測試現況**:只有 `tests/test_ocs_transformer.py`(11 passed),**無 golden/真實 PDF fixture**(`tests/fixtures/sample_pdfs` 等 ARCHITECTURE.md 提到但不存在)。覆蓋率 ~31%。→ 安全網不足,拆前要補。

## 3. 權威方法(研究)

- **Extract Class / Extract Function**(Martin Fowler, *Refactoring* 2nd ed):類別做太多 → 把內聚的欄位/方法搬到新類別,降耦合提內聚;大方法切小。god class 的標準解。[R1]
- **Replace Conditional with Polymorphism / Strategy**(Fowler):若 `_detect_table_type` + 大量 if/分支依「表格型別」走不同邏輯,可改多型/策略。視實際分支密度採用。[R1]
- **Pipes-and-Filters**(Gregor Hohpe & Bobby Woolf, *Enterprise Integration Patterns*;Microsoft Azure Architecture Center):把單體處理拆成一串單一職責 filter,以 pipe 串接;每個 filter 可獨立測試/替換。**正好套在「各區段擷取器」上**。[R2]
- **安全重構 legacy(Michael Feathers, *Working Effectively with Legacy Code*)**:先寫 **characterization tests**(把現有行為——含怪癖——釘住的 golden 測試),建立 **seam**,再動;workflow = 找變更點 → 找測試點 → 斷依賴 → 寫 characterization 測試 → 才重構。[R3]

## 4. 方案取捨

| 方案 | 評估 |
|---|---|
| **A. 不動** | ❌ god-file 持續腐化 |
| **B. 全部重寫** | ❌ 高風險、易改壞行為(尤其 PDF 解析的怪癖多) |
| **C. Extract Class「搬移」式拆解(推薦)** | ✅ **行為由構造保證不變**(搬方法、不改邏輯);對齊既有區段縫;低風險 |

**選 C。** 因為內部已分區、主擷取器對齊文件區段,Extract Class 是「搬移」而非「重寫」——邏輯逐字搬到新類別,`transform()` 改成薄 orchestrator 串接。行為不變由「沒改邏輯」保證,再加測試雙保險。

## 5. 目標結構(提案)

```
transformers/
├── base.py                      # BaseOCSTransformer(port,不動)
├── ocs_transformer.py           # 瘦 orchestrator:跑 version→profile→content→attitude→notes 並組 OCSDocument
├── sections/                    # 各區段 filter(Extract Class)
│   ├── version_extractor.py
│   ├── profile_extractor.py
│   ├── content_extractor.py     # 最大(含 _parse_ocu_table_units)
│   ├── attitude_extractor.py
│   └── notes_extractor.py
└── support/                     # 共用工具(被 section 擷取器用)
    ├── text.py                  # 文字正規化
    ├── tables.py                # 表格工具(clean/detect/column_map/find)
    ├── items.py                 # 條目擷取(outputs/indicators/competencies/level)
    ├── dedupe.py                # 去重
    └── scanning.py              # 歷史 PDF 掃描 + 單元組裝
```
各 section 擷取器接收 `pdf`/`raw_data` + 需要的 support，回傳對應的 `ocs-contract` 區段型別。`transform()` 變成數行的管線編排。

## 6. 安全策略(Feathers)

1. **先補 characterization / golden 測試**:拿真實 OCS PDF(查 `/s/jd-pdf-to-json/data` 是否有 sample PDF;若有)跑 `transform()`,把輸出存成 golden JSON;拆解過程每步比對 golden **逐字節相同**。
2. 若無真實 PDF 可用,退而以**現有 11 測試 + 「只搬不改」**為保證(Extract Class 不改邏輯),並盡量為主擷取器補單元測試。
3. 每搬一塊 = 跑 `uv run --extra dev pytest -q` 綠 + golden 比對綠,才下一塊。

## 7. 結論

god-file 拆解採 **Extract Class（搬移式）+ Pipes-and-Filters 區段化**，安全網用 **characterization/golden 測試**。內部既有分區讓這是低風險的「搬移」而非重寫;區段邊界與 `ocs-contract` 一致。→ 進 plan。

## References

- [R1] Martin Fowler, *Refactoring: Improving the Design of Existing Code* (2nd ed)；refactoring.com catalog — Extract Class / Extract Function / Replace Conditional with Polymorphism。
- [R2] Gregor Hohpe & Bobby Woolf, *Enterprise Integration Patterns* — Pipes and Filters；Microsoft Azure Architecture Center — Pipes and Filters。
- [R3] Michael Feathers, *Working Effectively with Legacy Code* — characterization tests、seams、安全重構 workflow。
