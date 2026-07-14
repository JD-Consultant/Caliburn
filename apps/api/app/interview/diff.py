"""文件 diff → 變動 path 列表(訪談引擎 T3;ADR 0025 provenance)。

用途:人工 PATCH 存檔時,算出這次改了哪些 path,併入 session.human_touched
——之後引擎對這些 path 只能提建議、不能直改(通道分流在 executor)。

Path 文法(引擎全域共用):段以 `.` 連接;list 項目若帶穩定 id(`_tid`/`_uid`/`_id`)
用 id 當段(拖拉重排不會誤標整棵樹),否則用 index。只記「葉」變動;
整項新增/刪除記到該項的 path。純函式、零 I/O。
"""

STABLE_ID_KEYS = ("_tid", "_uid", "_id")


def _seg(item, idx: int) -> str:
    if isinstance(item, dict):
        for k in STABLE_ID_KEYS:
            v = item.get(k)
            if v:
                return str(v)
    return str(idx)


def _walk(old, new, prefix: str, out: list[str]) -> None:
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            p = f"{prefix}.{k}" if prefix else k
            _walk(old.get(k), new.get(k), p, out)
    elif isinstance(old, list) and isinstance(new, list):
        old_map = {_seg(v, i): v for i, v in enumerate(old)}
        new_map = {_seg(v, i): v for i, v in enumerate(new)}
        keys = list(old_map) + [k for k in new_map if k not in old_map]
        for key in keys:
            p = f"{prefix}.{key}" if prefix else key
            in_old, in_new = key in old_map, key in new_map
            if in_old and in_new:
                _walk(old_map[key], new_map[key], p, out)
            else:
                out.append(p)   # 整項新增/刪除
    else:
        if old != new:
            out.append(prefix)


def doc_paths_changed(old: dict | None, new: dict | None) -> list[str]:
    out: list[str] = []
    _walk(old or {}, new or {}, "", out)
    return out
