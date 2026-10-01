"""Compare simulated-interview runs by version and persona. Usage: analyze_eval.py <version> [<version> ...]"""

import glob
import json
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
DIR = r"S:\caliburn\.research-tmp\eval"
YES_NO = re.compile(r"嗎[？?]")


def load(version: str) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(glob.glob(f"{DIR}\\{version}-*-?.json")):
        run = json.load(open(path, encoding="utf-8"))
        run["_path"] = path
        runs[run["persona"]].append(run)
    return runs


def strings_of(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [x for v in value.values() for x in strings_of(v)]
    if isinstance(value, list):
        return [x for v in value for x in strings_of(v)]
    return []


def jd_chars(run: dict) -> int:
    work = {k: v for k, v in run["jd"]["work"].items() if k not in ("revision_id",)}
    ids = ("_id",)
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items() if not k.endswith(ids)}
        if isinstance(v, list):
            return [clean(x) for x in v]
        return v
    return sum(len(x) for x in strings_of(clean(run["jd"]["profile"])) + strings_of(clean(work)))


def consultant_texts(run: dict) -> list[str]:
    return [t["consultant"] for t in run["turns"] if t.get("consultant")]


def redundancy(run: dict) -> tuple[int, int]:
    """(details whose text mostly repeats their task description, all details); coarse bigram overlap."""
    def grams(text: str) -> set[str]:
        text = re.sub(r"\s+", "", text)
        return {text[i : i + 2] for i in range(len(text) - 1)}

    repeated = total = 0
    for task in run["jd"]["work"]["tasks"]:
        base = grams(task["title"] + task["description"])
        for detail in task["outcomes"] + task["requirements"]:
            mine = grams(detail["text"])
            if not mine:
                continue
            total += 1
            if len(mine & base) / len(mine) >= 0.7:
                repeated += 1
    return repeated, total


def summarize(version: str) -> None:
    runs = load(version)
    print(f"\n########## {version} ##########")
    for persona, items in runs.items():
        print(f"\n=== {persona}: {len(items)} runs")
        gaps_rec: dict[str, int] = defaultdict(int)
        gaps_eli: dict[str, int] = defaultdict(int)
        for run in items:
            c = run["checks"]
            texts = consultant_texts(run)
            yn = sum(len(YES_NO.findall(t)) for t in texts)
            statuses = [t.get("status") for t in run["turns"]]
            print(
                f"  turns={len(run['turns'])} ok={statuses.count('completed')} "
                f"jd_chars={jd_chars(run)} chars/turn={c['style']['mean_consultant_chars']} q/turn={c['style']['questions_per_turn']} "
                f"lead={c['style']['leading_phrases']} yes/no={yn} | "
                f"areas={c['shape']['areas']} tasks={c['shape']['tasks']} out={c['shape']['outcomes']} "
                f"req={c['shape']['requirements']} cap={c['shape']['capabilities']} "
                f"collab={c['shape']['collaborator_items']} cond={c['shape']['condition_items']} refs={c['shape']['references']}"
            )
            rep, tot = redundancy(run)
            print(f"     redundancy: {rep}/{tot} outcomes/requirements mostly repeat their task text; purpose={'yes' if run['jd']['profile'].get('purpose') else 'NO'}")
            cor = c["correction"]
            src = {k: ("ok" if v["supported"] else ("MISSING" if not v["cited"] else "WRONG")) for k, v in c["profile_sources"].items()}
            print(f"     correction new={cor['new_present']} old_current={cor['old_left_as_current']} kept={cor['unchanged_kept']} | profile_src={src}")
            print(f"     record_gaps={c['recording_gaps']} elicit_gaps={c['elicitation_gaps']}")
            cit = c.get("citations")
            if cit:
                print(f"     citations: checked {cit['checked']} unsupported {len(cit['unsupported'])} rate {cit['support_rate']} {[(u['fact'], u['item'][:18]) for u in cit['unsupported'][:3]]}")
            for k in c["recording_gaps"]:
                gaps_rec[k] += 1
            for k in c["elicitation_gaps"]:
                gaps_eli[k] += 1
        print(f"  -- recording gaps (surfaced but not in JD): {dict(gaps_rec)}")
        print(f"  -- elicitation gaps (never surfaced):       {dict(gaps_eli)}")


for version in sys.argv[1:]:
    summarize(version)
