"""verify 六查(ADR 0030 T3)= scribe 寫入前的 output guardrail(blocking)。

家規:
- **純函式、零 LLM、零 IO**——合法集合/逐字稿/現行文件全部當參數傳入;
  「模型不守自己的門」(§6.1 可靠性金字塔)。
- scribe 的每筆 op 必過全六查才落 `_pending`;錯誤是**可行動的**
  (哪筆 op 哪一查沒過+修正提示),供 retry 回灌(T4)。
- 位置碼(`code` 欄)誰寫都拒收——renumber 是 web 前端獨佔職權(0025/0029)。

op 形(T4 scribe_schema 正式化;此處吃 dict):
    {"target_path": str, "op": "add"|"mod"|"del", "value": str|int|None,
     "src": {"ref_urn": str|None, "quote": {"turn_id": int, "text": str}|None}|None}
- add:target_path 指**清單容器**(task_codes/indicators/outputs/knowledge/skills/
  ocu_units/attitudes),value=新條目的 name/text。
- mod:target_path 指**葉欄位**(….name/….text/details.<槽>/表頭欄/級別欄),value=新值。
- del:target_path 指**條目**(清單成員)或槽,value 忽略。
"""
import re
import unicodedata
from dataclasses import dataclass, field

from app.interview.docpath import get_at, resolve, step
from app.interview.slots import SLOT_DEFS

_WS = re.compile(r"\s+")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")

# add 容器白名單(最後一段);⑤ 結構不變量
# tasks = 整個 TaskGroup(加新任務);task_codes = 既有任務組內的名目條目。
# ocu_units(ADR 0032):**只有裁剪確定性落地**會發(官方殼;apply 建殼)——
# 書記 schema 無對應變體,生成端仍編不出「AI 自由加職責」;守衛=src 檢查(殼名/任務
# 皆池內官方)+ 落地端 provenance 由 ref_urn 程式導出。
_ADD_CONTAINERS = {"task_codes", "indicators", "outputs", "knowledge", "skills",
                   "attitudes", "tasks", "ocu_units"}
# mod 葉欄白名單(最後一段);details.<槽> 與表頭另判
_MOD_LEAVES = {"name", "text", "job_description", "ocs_code", "ocs_level",
               "competency_level"}
_LEVEL_FIELDS = {"ocs_level", "competency_level"}
_MAX_LEN_DEFAULT = 500
_MAX_LEN_SLOT = 200


def normalize(s: str) -> str:
    return _WS.sub("", unicodedata.normalize("NFKC", str(s or "")))


def quote_verified(quote: str, employee_texts: list[str]) -> bool:
    """整份逐字稿子串比對(v1 相容介面;attitudes/curation/backstop 沿用)。"""
    q = normalize(quote)
    if not q:
        return False
    return q in normalize("\n".join(employee_texts))


@dataclass
class VerifyError:
    op_index: int
    check: str          # contract|quote|src|permission|invariant|hygiene
    message: str        # 可行動:哪裡錯+怎麼修
    hint: str | None = None


@dataclass
class VerifyResult:
    ok: bool
    errors: list[VerifyError] = field(default_factory=list)


def _last_seg(path: str) -> str:
    return path.split(".")[-1]


def _is_slot_path(path: str) -> bool:
    segs = path.split(".")
    return len(segs) >= 2 and segs[-2] == "details" and segs[-1] in SLOT_DEFS


def _norm_level(value):
    """enum 正規化:'3'/'3級'→3;非法回 None。"""
    if isinstance(value, int):
        return value
    m = re.match(r"^\s*(\d)\s*級?\s*$", str(value or ""))
    return int(m.group(1)) if m else None


def _entry_texts(container: list) -> list[str]:
    out = []
    for it in container:
        if isinstance(it, dict):
            name = it.get("name") or it.get("text") or it.get("ocu_name") or ""
            if not name and isinstance(it.get("task_codes"), list):
                # TaskGroup:名目住 task_codes[0].name
                first = next((c for c in it["task_codes"] if isinstance(c, dict)), {})
                name = first.get("name") or ""
            out.append(normalize(name))
    return out


def verify_ops(ops: list[dict], *, doc: dict, turns: dict[int, str],
               ref_codes: set[str], header_codes: set[str]) -> VerifyResult:
    """六查。turns = {turn_id: 員工原話};ref_codes = 參考集合合法 URN/官方碼;
    header_codes = 表頭主基準合法值(profile.selected_ocs_codes)。"""
    errors: list[VerifyError] = []

    def err(i, check, message, hint=None):
        errors.append(VerifyError(i, check, message, hint))

    for i, op in enumerate(ops):
        path = str(op.get("target_path") or "")
        kind = op.get("op")
        value = op.get("value")
        src = op.get("src") or {}
        ref_urn = src.get("ref_urn")
        quote = src.get("quote") or None
        last = _last_seg(path)

        # --- ⑤ 結構不變量(先擋禁區,錯誤最明確) ---
        if last == "code" or (last == "ocs_code" and kind != "mod"):
            err(i, "invariant",
                f"op[{i}] 目標 {path}:位置碼/代碼欄不受理——編碼由前端 renumber 自動產生,"
                "請改寫 name/text 欄或移除這筆。")
            continue
        if last == "attitudes" and not path.startswith("ocs_attitude"):
            err(i, "invariant",
                f"op[{i}] 態度只能掛文件層 ocs_attitude.attitudes,不能進任務(§6.1 欄位表)。")
            continue

        # --- ① 契約合法 + ④ 寫入權限(存在性/狀態) ---
        if kind == "add":
            if last not in _ADD_CONTAINERS:
                err(i, "contract",
                    f"op[{i}] add 目標 {path} 不是可新增的清單容器"
                    f"(合法:{sorted(_ADD_CONTAINERS)})。")
                continue
            container = get_at(doc, path)
            if not isinstance(container, list):
                # 容器缺殼但父節點在(能力區塊懶建;落地端建殼)→ 視為空容器
                parent, leaf = resolve(doc, path)
                segs = path.split(".")
                if isinstance(parent, dict) and leaf == last:
                    container = parent.get(last) if isinstance(parent.get(last), list) else []
                elif (len(segs) >= 3 and segs[-3] == "competency_blocks"
                      and isinstance(get_at(doc, ".".join(segs[:-3])), dict)):
                    container = []   # blocks 整列缺殼但 task 在(落地端建殼)
                else:
                    err(i, "permission",
                        f"op[{i}] add 目標 {path} 在文件中不存在——任務必掛在已存在的"
                        "職責下;請先確認父節點,或改用現有容器路徑。")
                    continue
            if not isinstance(value, str) or not value.strip():
                err(i, "contract", f"op[{i}] add 需要非空字串 value(新條目名稱/文字)。")
                continue
            if normalize(value) in _entry_texts(container):
                err(i, "invariant",
                    f"op[{i}] 「{value}」在 {path} 已存在(含待審項)——不要重複新增;"
                    "若要修改請對既有條目發 mod。")
                continue
        elif kind in ("mod", "del"):
            if _is_slot_path(path):
                # details 殼懶建:task 節點在即視為可寫(落地端建殼)
                task_node = get_at(doc, ".".join(path.split(".")[:-2]))
                exists = isinstance(task_node, dict)
            else:
                parent, leaf = resolve(doc, path)
                exists = parent is not None and (
                    step(parent, leaf) is not None
                    if not isinstance(parent, dict) else leaf in parent)
            if not exists:
                err(i, "permission",
                    f"op[{i}] {kind} 目標 {path} 在文件中不存在——"
                    "確認路徑(用文件現況工具重讀)或改為 add。")
                continue
            if kind == "mod":
                if _is_slot_path(path) or last in ("name", "text", "job_description"):
                    if not isinstance(value, str) or not value.strip():
                        err(i, "contract", f"op[{i}] mod {path} 需要非空字串 value。")
                        continue
                elif last in _LEVEL_FIELDS:
                    lv = _norm_level(value)
                    if lv is None or not (1 <= lv <= 5):
                        err(i, "contract",
                            f"op[{i}] {path} 級別值「{value}」非法——必須是 1–5 的整數。")
                        continue
                elif last == "ocs_code":
                    pass  # 值域在⑤下方查
                elif last not in _MOD_LEAVES:
                    err(i, "contract",
                        f"op[{i}] mod 目標 {path} 不是可寫葉欄位"
                        f"(合法:name/text/details.<槽>/表頭欄/級別欄)。")
                    continue
        else:
            err(i, "contract", f"op[{i}] 未知動作 {kind!r}(只有 add/mod/del)。")
            continue

        # --- ⑤ 表頭主基準值域(mod ocs_profile.ocs_code) ---
        if kind == "mod" and last == "ocs_code":
            if str(value) not in header_codes:
                err(i, "invariant",
                    f"op[{i}] 主基準「{value}」不在本文件已掛的參考集合中"
                    f"(合法:{sorted(header_codes)})——想用新基準,先建議使用者掛參考。")
                continue

        # --- ③ 來源一致 ---
        if kind == "add" and last == "ocu_units" and ref_urn is None:
            err(i, "src",
                f"op[{i}] 職責殼必須帶官方出處 ref_urn(0032:殼只允許池內官方職責,"
                "自由新增職責不受理——內容請掛既有職責或走 add_custom_task)。")
            continue
        if ref_urn is not None and str(ref_urn) not in ref_codes:
            err(i, "src",
                f"op[{i}] ref_urn「{ref_urn}」不在參考集合——只能引用本文件掛的參考基準。")
            continue
        if kind in ("add", "mod") and ref_urn is None and quote is None:
            err(i, "src",
                f"op[{i}] 沒有任何出處——custom 內容必附訪談 quote,官方內容必附 ref_urn"
                "(可並存,至少一;查無出處的內容寧缺勿編)。")
            continue

        # --- ② quote 存在性(指到的那一輪逐字比對) ---
        if quote is not None:
            tid = quote.get("turn_id")
            qtext = quote.get("text") or ""
            turn_text = turns.get(tid)
            if turn_text is None:
                err(i, "quote", f"op[{i}] quote 指向第 {tid} 輪,但該輪不存在或非員工發言。")
                continue
            if normalize(qtext) not in normalize(turn_text):
                hit = next((f"第 {k} 輪" for k, v in turns.items()
                            if normalize(qtext) and normalize(qtext) in normalize(v)), None)
                err(i, "quote",
                    f"op[{i}] quote「{qtext[:40]}」在第 {tid} 輪逐字稿中找不到——"
                    "引用必須逐字,請改用原話或撤掉這筆。",
                    hint=(f"該原話出現在{hit},請改 turn_id。" if hit
                          else f"第 {tid} 輪開頭:「{turn_text[:40]}」"))
                continue

        # --- ⑥ 尺寸衛生 ---
        if isinstance(value, str):
            cap = _MAX_LEN_SLOT if _is_slot_path(path) else _MAX_LEN_DEFAULT
            if len(value) > cap:
                err(i, "hygiene", f"op[{i}] value 超長({len(value)}>{cap})——請精煉。")
                continue
            if _CTRL.search(value) or "```" in value:
                err(i, "hygiene",
                    f"op[{i}] value 含控制字元/換行/程式碼圍欄——表格欄位是單行純文字。")
                continue

    return VerifyResult(ok=not errors, errors=errors)
