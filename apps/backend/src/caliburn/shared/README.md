# Shared

共用技術與基底契約，不持有 Workspace／JD 的業務規則，不引用 `modules`。

- [domain](domain)：Entity／Aggregate／VO 等領域基底。
- [application](application)：DTO、Repository 與 UoW 契約。
- [infrastructure](infrastructure)：資料庫連線與 ORM 基底。
- [presentation](presentation)：HTTP 共用值格式、錯誤格式與安全診斷；業務有效值規則仍由各領域負責。

`BaseValueObject` 統一嚴格型別、禁止額外欄位、預設值驗證與欄位凍結；`BaseDomainPrimitive` 提供單值結構，具體型別定義有效值規則。VO／DP 的內容使用不可變型別；已驗證的不可變實例可共用，變更則經正常建構取得新值。業務建構不使用會略過驗證的 `model_construct` 或 `model_copy(update=...)`。

預留的 Domain Event、Specification、Service、Factory 尚無業務消費者；不要求每個模組採用。新增共用抽象須有相同語意與實際消費者，避免把業務流程收進基底。
