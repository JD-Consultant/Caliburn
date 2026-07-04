"""知識包組裝器(ADR 0021):純函式,吃 indexer-contract DTO、產 pack dict。

規則 = spec ``2026-07-03-editor-provenance-knowledge-pack-decisions.md`` §5:
池 = append 序(職位優先序,A 先 append B)+ key 去重 + srcs 累積(欄位名照
indexer-contract);source_tasks 以任務 URN byId,掛 o/p/k/s_refs(池 key)。
名字**不做正規化**(維護者拍板:key = 原始字串精確比對)。
去重 key 表(§5.1):K/S/O/units/tasks/attitudes=name、P/notes=text、三類=code。
"""
from __future__ import annotations

from app.core.knowledge_dto import CompetencyPool, OccupationDetail, OccupationTasks

POOL_NAMES = ("units", "tasks", "knowledge", "skills", "outputs", "indicators",
              "attitudes", "job_categories", "occupations", "industries",
              "prerequisites", "supplements")


def _task_urn(ocs_code: str, task_code: str) -> str:
    return f"ocs:{ocs_code}:T:{task_code}"  # scheme 同 indexer api/urn.py


def _occ_name(d: OccupationDetail) -> str:
    return d.ocs_name.occupation_name or d.ocs_name.job_category_name or d.ocs_code


def _row(pool: dict, key: str) -> dict:
    return pool.setdefault(key, {"srcs": []})


def build_pack(order: list[str], details: dict[str, OccupationDetail],
               tasks_by_code: dict[str, OccupationTasks],
               pools_by_code: dict[str, CompetencyPool]) -> dict:
    pack: dict = {"occupation_details": [], "pools": {n: {} for n in POOL_NAMES},
                  "source_tasks": {}}
    pools = pack["pools"]
    for code in order:                        # append 序 = 職位優先序
        d = details.get(code)
        if d is None:
            continue                          # 該 code 抓失敗(partial 由路由標)
        name = _occ_name(d)
        pack["occupation_details"].append(d.model_dump())
        # 表頭池:態度 = name key(A5:碼為文件自編,code key 跨職類必撞);
        # 三類 = code key(國家分類碼);notes = text key。
        for a in d.attitudes:
            if a.name:
                _row(pools["attitudes"], a.name)["srcs"].append(
                    {"ocs_code": code, "ocs_name": name, "code": a.code})
        for pool_name, items in (("job_categories", d.job_categories),
                                 ("occupations", d.occupations),
                                 ("industries", d.industries)):
            for c in items:
                if not c.code:
                    continue
                row = pools[pool_name].setdefault(c.code, {"name": c.name, "srcs": []})
                row["srcs"].append({"ocs_code": code, "ocs_name": name})
        for pool_name, texts in (("prerequisites", d.prerequisites),
                                 ("supplements", d.supplements)):
            i = 0  # 來源位置碼 n{i}(1-based、不補零;spec 2026-07-04 §3):跳過空白不佔號
            for t in texts:
                if t.strip():
                    i += 1
                    _row(pools[pool_name], t)["srcs"].append(
                        {"ocs_code": code, "ocs_name": name, "code": f"n{i}"})
        # 結構層:units/tasks 池(name key)+ source_tasks 骨架(URN byId)。
        occ_tasks = tasks_by_code.get(code)
        for u in (occ_tasks.units if occ_tasks else []):
            if u.ocu_name:
                _row(pools["units"], u.ocu_name)["srcs"].append(
                    {"ocs_code": code, "ocs_name": name,
                     "ocu_code": u.ocu_code, "ocu_name": u.ocu_name})
            for t in u.tasks:
                urn = _task_urn(code, t.task_code)
                if t.task_name:
                    row = _row(pools["tasks"], t.task_name)
                    if urn not in row["srcs"]:
                        row["srcs"].append(urn)   # 任務池 srcs = source_tasks 的 URN
                pack["source_tasks"][urn] = {
                    "ocs_code": code, "ocs_name": name,
                    "ocu_code": u.ocu_code, "ocu_name": u.ocu_name,
                    "task_code": t.task_code, "task_name": t.task_name,
                    "competency_level": None,
                    "o_refs": [], "p_refs": [], "k_refs": [], "s_refs": []}
        # 能力池:K/S/O = name key、P = text key;同時反向掛 refs + 補 level。
        comp = pools_by_code.get(code)
        for pool_name, ref_field, items, textual in (
                ("knowledge", "k_refs", comp.knowledge if comp else [], False),
                ("skills", "s_refs", comp.skills if comp else [], False),
                ("outputs", "o_refs", comp.outputs if comp else [], False),
                ("indicators", "p_refs", comp.indicators if comp else [], True)):
            for it in items:
                key = (it.text if textual else it.name) or ""
                if not key:
                    continue
                row = _row(pools[pool_name], key)
                for s in it.sources:
                    row["srcs"].append({
                        "ocs_code": code, "ocs_name": name, "code": it.code,
                        "ocu_code": s.ocu_code, "ocu_name": s.ocu_name,
                        "task_code": s.task_code, "task_name": s.task_name,
                        "competency_level": s.competency_level})
                    node = pack["source_tasks"].get(_task_urn(code, s.task_code or ""))
                    if node is None:
                        continue
                    if key not in node[ref_field]:
                        node[ref_field].append(key)
                    if node["competency_level"] is None and s.competency_level is not None:
                        node["competency_level"] = s.competency_level
    return pack
