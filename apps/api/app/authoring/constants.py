"""共用常數 — 統一兩處 _REQUIRED_FIELDS 的定義，避免 five_w2h / indicator / tasks 三份各自不同。"""

# 5W2H 訪談補洞欄位（每欄一個問題）
# 順序 = 追問優先順序；已由 star_case 預填的欄位通常會被跳過
FIVE_W2H_REQUIRED: dict[str, tuple[str, str]] = {
    "situation":         ("When/Where",   "這項工作通常在什麼時候、什麼場景下發生？"),
    "purpose":           ("Why",          "做這項工作的目的是什麼？要解決什麼問題？"),
    "collaborators":     ("Who/協作",     "這項工作需要與哪些人或部門協作？他們在流程中負責什麼？"),
    "stakeholders":      ("Who/服務對象", "這項工作面對誰、服務誰、或最終影響誰？"),
    "workflow_steps":    ("How/步驟",     "完成這項工作的主要步驟是什麼？請依序描述。"),
    "tools":             ("How/工具",     "你使用哪些系統、工具、表單或平台來完成這件事？"),
    "outputs":           ("What/產出",    "這項工作最後產出什麼？（文件、資料、報表、通知…）"),
    "quality_standards": ("How much/品質","怎樣才算做好？有哪些品質要求或驗收標準？"),
    "time_standards":    ("How much/時效","這項工作有什麼時效要求？例如幾天內完成、截止時間或回覆時限。"),
}

# indicator 生成 Guardrail — 與 5W2H 保持一致
INDICATOR_REQUIRED_FIELDS: list[str] = list(FIVE_W2H_REQUIRED.keys())

# tasks API 完整度計算 — 包含最終的 behavior_indicator_5w2h
TASK_COMPLETENESS_FIELDS: list[str] = [
    "situation", "purpose", "collaborators", "stakeholders",
    "workflow_steps", "tools", "outputs", "quality_standards",
    "time_standards", "behavior_indicator_5w2h",
]

# list 欄位：使用者回答應存為 list 而非純字串
FIVE_W2H_LIST_FIELDS: frozenset[str] = frozenset({
    "stakeholders", "collaborators", "tools", "outputs",
    "quality_standards", "time_standards", "workflow_steps",
})
