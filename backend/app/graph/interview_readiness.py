"""
訪談成熟度評估模組。

compute_readiness(messages) → ReadinessResult:
  score                       float 0–1
  ready                       bool  score >= READY_THRESHOLD (0.70)
  signals                     list[SignalResult]  全部六個維度
  missing_signals             list[SignalResult]  未達標維度
  detected_signals            list[SignalResult]  已達標維度（含偵測到的範例詞）
  suggested_follow_up_question  str | None  下一個最重要的追問問題
"""
import re
from typing import Optional

READY_THRESHOLD   = 0.70   # score >= 此值 → 進入任務萃取
PARTIAL_THRESHOLD = 0.45   # score >= 此值 → 針對缺漏維度補問

# ── TypedDict-style dicts（不依賴 TypedDict，避免 Python 版本差異） ──────

def SignalResult(
    key: str,
    label: str,
    detected: bool,
    examples: list,
    weight: int,
    follow_up_question: str,
) -> dict:
    return {
        "key": key,
        "label": label,
        "detected": detected,
        "examples": examples,
        "weight": weight,
        "follow_up_question": follow_up_question,
    }


def ReadinessResult(
    score: float,
    ready: bool,
    signals: list,
    missing_signals: list,
    detected_signals: list,
    suggested_follow_up_question: Optional[str],
) -> dict:
    return {
        "score": score,
        "ready": ready,
        "signals": signals,
        "missing_signals": missing_signals,
        "detected_signals": detected_signals,
        "suggested_follow_up_question": suggested_follow_up_question,
    }


# ── 維度定義（order = 追問優先順序）──────────────────────────────────────

_SIGNAL_DEFS: list[dict] = [
    {
        "key": "tasks",
        "label": "工作任務項目（至少 2 項）",
        "weight": 2,
        "keywords": frozenset(),   # 用 _count_tasks 特殊計算
        "follow_up_question": (
            "除了剛才說的，你每天還有哪些主要工作嗎？"
            "能再說一項你覺得最花時間或最重要的任務嗎？"
        ),
    },
    {
        "key": "outputs",
        "label": "工作產出（文件、報表、資料等）",
        "weight": 1,
        "keywords": frozenset({
            "報告", "報表", "文件", "資料", "清單", "表格", "記錄", "結果", "成果",
            "產出", "通知", "簡報", "圖表", "分析", "提案", "計畫", "合約", "表單",
            "紀錄", "日報", "週報", "月報", "明細", "憑證",
        }),
        "follow_up_question": (
            "你這些工作最後會產出什麼？"
            "比如說報告、表格、通知，還是其他需要交付或存檔的東西？"
        ),
    },
    {
        "key": "tools",
        "label": "使用的工具或系統",
        "weight": 1,
        "keywords": frozenset({
            "系統", "ERP", "Excel", "SAP", "軟體", "平台", "工具", "程式", "資料庫",
            "email", "Email", "Teams", "Line", "Slack", "表單", "CRM", "Word",
            "PowerPoint", "Power BI", "SQL", "Python", "Jira", "Notion", "MES",
            "WMS", "OA", "HR系統", "採購系統", "財務系統", "出勤系統", "差勤",
        }),
        "follow_up_question": (
            "你在工作中主要使用哪些系統或工具？"
            "比如 ERP、Excel，還是其他公司內部的軟體或平台？"
        ),
    },
    {
        "key": "stakeholders",
        "label": "協作或服務對象",
        "weight": 1,
        "keywords": frozenset({
            "客戶", "同事", "主管", "部門", "業務", "採購", "財務", "會計", "工程",
            "研發", "廠商", "供應商", "老闆", "跨部門", "協作", "配合", "對接",
            "生產", "倉儲", "品管", "QC", "PM", "HR", "行政", "總務", "倉管",
        }),
        "follow_up_question": (
            "你的這些工作需要跟哪些人或部門配合？"
            "他們在流程中主要做什麼、或提供什麼資訊給你？"
        ),
    },
    {
        "key": "quality",
        "label": "品質標準或時效要求",
        "weight": 1,
        "keywords": frozenset({
            "時效", "期限", "準確", "正確率", "標準", "規範", "截止", "deadline",
            "要求", "品質", "良率", "達成率", "KPI", "小時內", "天內", "工作天",
            "幾天", "幾小時", "完成時間", "回覆時間", "不能超過", "必須在", "合格",
        }),
        "follow_up_question": (
            "這些工作通常有沒有時間要求或品質標準？"
            "比如幾天內要完成、有沒有準確率要求，或有哪些規定不能出錯？"
        ),
    },
    {
        "key": "context",
        "label": "工作情境或頻率",
        "weight": 1,
        "keywords": frozenset({
            "每天", "每日", "每週", "每月", "定期", "通常", "發生", "流程",
            "步驟", "一般來說", "主要是", "月初", "月底", "季", "年度",
            "專案", "臨時", "固定", "例行", "不定期", "當",
        }),
        "follow_up_question": (
            "這些工作是每天都有，還是定期進行？"
            "通常在什麼情況下會發生，有什麼固定的觸發條件嗎？"
        ),
    },
]

_TOTAL_WEIGHT = sum(d["weight"] for d in _SIGNAL_DEFS)   # = 7

_TASK_VERBS = frozenset({
    "負責", "管理", "處理", "執行", "追蹤", "準備", "協調", "整理", "分析",
    "製作", "撰寫", "彙整", "安排", "審核", "回報", "確認", "更新", "監控",
    "維護", "規劃", "設計", "建立", "建置", "操作", "檢查", "驗收", "評估",
    "統計", "彙報", "計算", "核對", "比對", "送出", "發送", "提交", "完成",
})


# ── 工具函式 ──────────────────────────────────────────────────────────────

def _user_text(messages: list[dict]) -> str:
    return " ".join(
        m["content"]
        for m in messages
        if isinstance(m, dict) and m.get("role") == "user"
    )


def _count_tasks(messages: list[dict]) -> int:
    """粗估使用者提到的不同工作任務數量。"""
    text = _user_text(messages)
    numbered = len(re.findall(
        r'[一二三四五六七八九十\d１２３４５６７８９０][、.．。]\s*\S',
        text,
    ))
    if numbered >= 2:
        return numbered
    sentences = re.split(r'[。！？\n；;，,]', text)
    return sum(
        1 for s in sentences
        if len(s.strip()) > 4 and any(v in s for v in _TASK_VERBS)
    )


def _task_examples(messages: list[dict]) -> list[str]:
    """擷取含任務動詞的短句作為 examples。"""
    text = _user_text(messages)
    sentences = re.split(r'[。！？\n；;]', text)
    hits = [
        s.strip()[:25]
        for s in sentences
        if len(s.strip()) > 4 and any(v in s for v in _TASK_VERBS)
    ]
    return hits[:3]


def _find_examples(text: str, keywords: frozenset) -> list[str]:
    return [k for k in keywords if k in text][:5]


# ── 主要函式 ──────────────────────────────────────────────────────────────

def compute_readiness(messages: list[dict]) -> dict:
    """
    評估訪談成熟度。

    Returns ReadinessResult dict。
    """
    text = _user_text(messages)
    task_count = _count_tasks(messages)

    signals: list[dict] = []
    for defn in _SIGNAL_DEFS:
        key = defn["key"]
        if key == "tasks":
            detected = task_count >= 2
            examples = _task_examples(messages) if detected else []
        else:
            kws = defn["keywords"]
            detected = any(k in text for k in kws)
            examples = _find_examples(text, kws)

        signals.append(SignalResult(
            key=key,
            label=defn["label"],
            detected=detected,
            examples=examples,
            weight=defn["weight"],
            follow_up_question=defn["follow_up_question"],
        ))

    score = sum(s["weight"] for s in signals if s["detected"]) / _TOTAL_WEIGHT
    ready = score >= READY_THRESHOLD
    missing  = sorted([s for s in signals if not s["detected"]], key=lambda s: s["weight"], reverse=True)
    detected = [s for s in signals if s["detected"]]
    suggested = missing[0]["follow_up_question"] if missing else None

    return ReadinessResult(
        score=round(score, 3),
        ready=ready,
        signals=signals,
        missing_signals=missing,
        detected_signals=detected,
        suggested_follow_up_question=suggested,
    )
