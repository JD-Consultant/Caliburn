"""skill 判準教材載入(T7;ADR 0030 §6.8)。

- 教材=repo 版本化 `skills/<name>/SKILL.md`(調教 AI 首選改 skill 不改碼;
  改 skill 檔=CI 跑 regression 的維護閉環,T11)。
- `skills_for(phase, gap)`:欄位/階段 → 檔案清單,**確定性對應、零 LLM**(§6.2)。
- `load_skill(name)`:剝 frontmatter 回內文;lru_cache → 同 process 內 byte 級穩定,
  當 context 前綴的一部分可吃 provider 快取(改檔需重啟,與 prompt 常數同紀律)。
"""
from functools import lru_cache
from pathlib import Path

from app.interview import coverage as CO

_SKILLS_DIR = Path(__file__).parent / "skills"

ALL_SKILLS = ["consultant-principles", "duty-task-structure", "output-writing",
              "behavior-indicator", "ks-distinction", "level-judgment",
              "attitude-writing", "probing"]


def skills_for(phase: str, gap: str | None) -> list[str]:
    """常駐 principles;其餘按缺口欄位(kind)/階段掛載(plan T7 對應表)。"""
    names = ["consultant-principles"]
    g = gap or ""
    last = g.rsplit(".", 1)[-1]
    if g in (CO.ONBOARD_OCCUPATION, CO.CURATION_TASKS):
        names.append("duty-task-structure")
    elif last == "outputs":
        names.append("output-writing")
    elif last == "indicators":
        names.append("behavior-indicator")
    elif last in ("knowledge", "skills"):
        names += ["ks-distinction", "probing"]
    elif "level" in last:
        names.append("level-judgment")
    elif g == "ocs_attitude":
        names.append("attitude-writing")
    if phase == "opks_deep" and "probing" not in names:   # 深聊預設帶追問術
        names.append("probing")
    return names


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """極簡 frontmatter(--- k: v --- 內文);skill 檔只用 name/description 兩鍵。"""
    if not text.startswith("---"):
        return {}, text
    head, _, body = text[3:].partition("\n---")
    meta = {}
    for line in head.strip().splitlines():
        k, _, v = line.partition(":")
        if _:
            meta[k.strip()] = v.strip()
    return meta, body.lstrip("\n")


@lru_cache(maxsize=None)
def load_skill(name: str) -> str:
    """skill 內文(去 frontmatter)。檔案不在=部署錯誤,直接炸(fail-fast)。"""
    text = (_SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return body
