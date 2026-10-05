"""Small outcome-level corrections, without case answers in the prompt."""

from pathlib import Path


def instructions(previous: Path) -> dict:
    result = {}
    for role in ("b2", "reader"):
        control = (previous / f"{role}-method.md").read_text(encoding="utf-8")
        if role == "b2":
            old = "來源是深入入口，不在正文要求顧問逐條回查。"
            new = (
                old
                + " 本項不需要其他案件的條件來成立時，只寫本項事實與未知，不複製其他案件的數值作排除比較。"
                "修訂相關理解時移除既有多餘比較；確有必要的比較則核對兩側最新事實並補齊來源。正文、標題及導覽描述皆適用。"
            )
        else:
            old = "完成前從已讀資料核對：省略是否改變誰執行、誰決定、何時適用、承諾做到哪裡？有影響就補回，無關經過與重複語句可省。資訊足夠就停止取讀。"
            new = (
                "完整任務的責任關係要寫完整：保留已知的本人行動、必要的核准者與接手者；"
                "不能用『不由本人負責』取代已知由誰負責，也不把未知分工補成事實。"
                "只問單一細節時，仍只保留解讀該細節必需的限定。完成前核對省略是否改變責任、適用條件或承諾；資訊足夠就停止取讀。"
            )
        if control.count(old) != 1:
            raise ValueError("Prompt baseline changed")
        result[role] = {"control": control, "candidate": control.replace(old, new)}
    return result
