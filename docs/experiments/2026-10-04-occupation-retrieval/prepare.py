"""Freeze existing published synthetic Memory and cleaned public OCS records."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from evaluation import clean_text

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "docs/experiments/product-validation/data"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_self_title(text):
    # Exact known disclosure in this frozen synthetic procurement employee;
    # reporting-line roles remain evidence of responsibility boundaries.
    return text.replace("我是電子零件組裝廠的採購專員，", "我在電子零件組裝廠工作，").replace(
        "本人是電子零件組裝廠的採購專員，", "本人在電子零件組裝廠工作，")


def corpus_records(directory):
    records = []
    for path in sorted(directory.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        profile = document["ocs_profile"]
        parts = [profile.get("job_description") or ""]
        ks = []
        for unit in document["ocs_content"]["ocu_units"]:
            parts.append(unit.get("ocu_name") or "")
            for task in unit["tasks"]:
                parts.extend(item.get("name") or "" for item in task["task_codes"])
                for block in task["competency_blocks"]:
                    parts.extend(item.get("name") or "" for item in block["outputs"])
                    parts.extend(item.get("text") or "" for item in block["indicators"])
                    ks.extend(item.get("name") or "" for item in block["knowledge"] + block["skills"])

        def unique_text(values):
            return "\n".join(dict.fromkeys(value for part in values
                              if (value := clean_text(part).replace("\n", ""))))

        records.append({
            "id": profile["ocs_code"], "title": profile["ocs_name"]["occupation_name"],
            "source": path.relative_to(ROOT).as_posix(), "source_sha256": sha(path),
            "texts": {"description": unique_text(parts[:1]), "top": unique_text(parts),
                      "topks": unique_text(parts + ks)},
        })
    counts = Counter(record["id"] for record in records)
    quarantine = [record for record in records
                  if counts[record["id"]] > 1 or record["id"] == "Unknown" or not record["title"]]
    for record in quarantine:
        record["quarantine_reason"] = (
            "missing occupation title" if not record["title"] else "duplicate or Unknown OCS code")
    write_json(HERE / "quarantine.json", quarantine)
    return [record for record in records if record not in quarantine]


def memory_case(case_id, group, snapshot, baseline, sources, grades, rationale, negatives):
    objects = snapshot["objects"]
    understandings = [obj for obj in objects if obj["layer"] == "work_understanding"]
    if not understandings:
        raise ValueError("No published understanding")
    referenced = {}
    for obj in understandings:
        refs = obj["work_situation_references"]
        if isinstance(refs, str):
            pairs = re.findall(r"object_id=UUID\('([^']+)'\), revision_id=UUID\('([^']+)'\)", refs)
            if not pairs:
                raise ValueError("Unrecognized historical reference serialization")
            referenced.update(pairs)
        else:
            referenced.update({ref["object_id"]: ref["revision_id"] for ref in refs})
    situations = [obj for obj in objects if obj["layer"] == "work_situation"
                  and obj["object_id"] in referenced]
    if not situations or {obj["object_id"] for obj in situations} != set(referenced) or any(
            obj["revision_id"] != referenced[obj["object_id"]] for obj in situations):
        raise ValueError("Every B1 reference must resolve at its exact published revision")
    raw_b2 = "\n\n".join(obj["content"]["body"] for obj in understandings)
    raw_c = raw_b2 + "\n\n" + "\n\n".join(obj["content"]["body"] for obj in situations)
    raw = {"A_facts": baseline, "B_b2": raw_b2, "C_b2_b1": raw_c}
    return {
        "case_id": case_id, "employee_group": group, "kind": "natural_memory_synthetic_employee",
        "snapshot": snapshot["snapshot"], "sources": sources, "grades": grades,
        "label_rationale": rationale, "hard_negatives": negatives,
        "raw_inputs": raw,
        "inputs": {arm: clean_text(remove_self_title(text)) for arm, text in raw.items()},
        "b2_object_ids": [obj["object_id"] for obj in understandings],
        "included_b1_object_ids": [obj["object_id"] for obj in situations],
    }


def prepare():
    corpus = corpus_records(ROOT / "apps/pdf-to-json/data/json-checked-2026-10-04")
    path = DATA / "long-interview-memory-2026-10-04/live-01/snapshot-1.json"
    transcript = DATA / "long-interview-memory-2026-10-04/live-01/corpus.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    baseline = (
        "在電子零件組裝廠負責原物料與包材的需求處理及供應商往來。檢核請購規格、數量、需求日和預算，缺漏退回補齊。"
        "新料或大額找至少三家報價，比較價格、交期、品質紀錄及付款條件，整理比價表與選擇理由；常用品使用合約價。"
        "核准後於ERP開單，每週和生管核對物料需求、缺口及安全庫存並下單。大宗框架合約逐次叫貨、準備續約資料，主管負責談判。"
        "每週催未交貨品，回報新交期；停線風險當天通知生管與主管，談急件或分批交货，不自行決定未認證替代料。"
        "農曆年前與第四季提早兩個月下單，緊急件先口頭叫货、當天補請購原因。"
        "收貨與檢驗由倉庫、品保執行；本人協調退換货或扣款，異常接受由主管決定，要求七天改善報告，連續兩次不合格提報。"
        "收集供應商登記、稅籍、銀行及品質認證文件交品保；審核通過才建檔。配合ERP升級整理重複主檔。"
        "每半年依交期、品質、配合度整理績效表交主管決定合作；十一月準備去年用量和市場行情，聯絡並陪同品保到廠稽核。"
        "平常小品項調價先協商，無法達成則交主管。核對發票、採購單、驗收單一致後送財務，付款日由財務安排，不承諾付款時間。"
        "本人核准五萬元含以下；上至五十萬元含由採購主管，以上副總。正式單位、未交货清單来源、稽核判定與部分流程未知。"
        "使用Excel整理比價、績效、談判資料及郵件聯絡。"
    )
    messages = json.loads(transcript.read_text(encoding="utf-8"))
    cases = [memory_case(
        "procurement-cut44", "procurement", snapshot, baseline,
        [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)},
         {"path": transcript.relative_to(ROOT).as_posix(), "sha256": sha(transcript),
          "employee_sequences": [row["interview_sequence"] for row in messages
                                  if row["speaker"] == "employee" and row["interview_sequence"] <= 44]}],
        {"BAS3323-001v4": 3, "BAS3323-003v3": 2, "KRM3323-001v4": 1, "KRM3323-002v4": 1},
        "自主詢比價、下單、催貨、供應商維護符合採購人員；助理是較弱但可接受參考；零售採購有產業差異。未制定採購政策或管理團隊。",
        ["BAS3323-002v4", "MQM2141-008v1"])]
    path = DATA / "memory-compaction-publish-2026-10-04/live-02/readback.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    for sample in raw:
        cutoff = sample["snapshot"]["covered_through_sequence"]
        baseline = "核對帳面庫存與實物，記錄差異交倉庫主管；ERP調整須主管核准，本人沒有核准權。每年準備年度查核盤點表和單據，不負責查核結論。"
        baseline = ("每月" if cutoff == 2 else "目前每季") + baseline
        if cutoff == 4:
            baseline += "每週核對客戶退货品項數量，記錄差異交品保，依品保結論登錄；商品可售性由品保決定。"
        cases.append(memory_case(
            f"inventory-{sample['arm']}-cut{cutoff}", "inventory", sample, baseline,
            [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}],
            {"MMP4321-003v4": 3, "RLM4323-002v4": 2, "RLM9330-001v1": 1},
            "帳物盤點與差異回報可借鑑倉儲管理標準；未確認行業，只是候選參考。未負責品質檢驗、品保判定、查核結論或物流策略。",
            ["MQM2141-008v1", "MQM7993-001v4", "RLM1324-001v4"]))
    write_json(HERE / "corpus.json", corpus)
    write_json(HERE / "cases.json", cases)
    write_json(HERE / "manifest.json", {
        "schema": 1, "corpus_count": len(corpus), "independent_employee_groups": 2,
        "input_case_count": len(cases), "corpus_sha256": sha(HERE / "corpus.json"),
        "cases_sha256": sha(HERE / "cases.json"), "protocol_sha256": sha(HERE / "protocol.md"),
        "probes_sha256": sha(HERE / "probes.json"),
        "truth_source": "engineering semantic review before retrieval; synthetic only, not expert ground truth",
        "transformations": ["exact self-title replacement", "markdown markers and generic OPKS headings removed",
                            "TOPKS codes removed", "stable dedup corpus text, names retained"],
    })
    print(f"Frozen {len(corpus)} OCS records, {len(cases)} paired inputs / 2 employee groups")


if __name__ == "__main__":
    prepare()
