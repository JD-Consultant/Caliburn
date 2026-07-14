"""文件 path 解析(與 diff.py 同文法):段以 `.` 連接;list 段用穩定 id
(_tid/_uid/_id)或 index。

原住 executor.py(v1);ADR 0030 T3 抽出成中性模組——verify/scribe/context 都用,
v1 的 executor.py 退場(T12)後這裡是唯一家。純函式,不改輸入。
"""
from app.interview.diff import STABLE_ID_KEYS


def step(node, seg: str):
    if isinstance(node, dict):
        return node.get(seg)
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict) and any(str(item.get(k)) == seg for k in STABLE_ID_KEYS):
                return item
        if seg.isdigit() and int(seg) < len(node):
            return node[int(seg)]
    return None


def resolve(doc: dict, path: str):
    """回 (parent, last_seg) 供讀寫;走不到 → (None, None)。"""
    segs = path.split(".")
    node = doc
    for seg in segs[:-1]:
        node = step(node, seg)
        if node is None:
            return None, None
    return node, segs[-1]


def get_at(doc: dict, path: str):
    parent, last = resolve(doc, path)
    if parent is None:
        return None
    return step(parent, last) if not isinstance(parent, dict) else parent.get(last)


def set_at(doc: dict, path: str, value) -> bool:
    """葉寫入;task 段存在但 `details` 尚無 → 自動建殼。成功回 True。"""
    parent, last = resolve(doc, path)
    if parent is None:
        # 容許 …<task>.details.<slot> 的 details 缺殼:找 task(= "details" 的 parent)建殼
        segs = path.split(".")
        if len(segs) >= 2 and segs[-2] == "details":
            tparent, tlast = resolve(doc, ".".join(segs[:-1]))
            if isinstance(tparent, dict) and tlast == "details":
                tparent.setdefault("details", {})[segs[-1]] = value
                return True
        return False
    if isinstance(parent, dict):
        parent[last] = value
        return True
    return False
