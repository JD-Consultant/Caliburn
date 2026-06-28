# 產品 / UX 決策與延後項

> 不夠「架構」到要開 ADR、但需要被記住的產品 / UX 決策與**刻意延後**的項目。
> 每項標清楚:**現況是不是刻意的**、**為什麼延後**、**未定的取捨**。

---

## 選取即自動填(autofill on selection)— 延後

**使用者期望的 UX**(2026-06-26 提出,當下決定先不動、晚點討論):

- **選職類後**自動填表頭:所屬類別、職能基準名稱、工作描述、基準級別、態度 A、應備資格、補充說明。
- **選任務後**自動填每個任務的 O / P / K / S。

**現況是刻意的「catalog 取出 + 人工 curate」,不是 bug:**

- 選職類(web `OccupationPicker` → `setOccupations`)只寫 `ocs_code` + 職類名 / 工作描述(且取 **profile** 的 job_title/job_summary,非 catalog 官方值)。類別 / 級別 / 態度 / 資格 / 補充要另開〔表頭分類〕面板(預設全勾)按「套用」才寫。
- 選任務(web `TaskCuratePanel`)只建**空** K/S/O/P 格;每格走 `CellFillerPanel` 手動挑 / 打。
- api 的 header-meta 服務 docstring 明講**刻意永不自動寫**,以免重選職類洗掉使用者的編輯。

**實作可行性**:`apps/api/app/services/knowledge/task_detail.py` 的 `task_competencies(pool, task_code)` 正好能取「該任務官方 K/S/O/P」拿來自動填任務格;表頭可重用「全勾套用」邏輯改成 `setOccupations` 後自動套。

**未定的取捨(晚點討論)**:

1. **覆寫策略** = 只填空(保護使用者編輯)vs 每次都從 catalog 覆寫。
2. **任務填什麼** = 「該任務官方 K/S/O/P」vs「整職類池」。

> 注意:上面的檔名 / 函式為 2026-06 觀察,動手前請對照現行 `apps/api` / `apps/web` 確認(api 已做過六邊形重構,服務位置可能調整過)。
