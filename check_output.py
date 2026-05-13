"""Quick audit of all output JSONs for common format issues."""
import json
import re
from pathlib import Path

out_dir = Path("output")
files = list(out_dir.glob("*.json"))

issues = {
    "empty_indicators": 0,
    "merged_attitudes": 0,
    "newline_in_ks_name": 0,
    "empty_ocu_units": 0,
    "missing_job_category": 0,
}
files_with_issues = set()
merged_examples = []

for f in files:
    data = json.loads(f.read_text(encoding="utf-8"))
    has_issue = False

    # Check ocs_content
    for unit in data.get("ocs_content", {}).get("ocu_units", []):
        for task in unit.get("tasks", []):
            for block in task.get("competency_blocks", []):
                if not block.get("indicators"):
                    issues["empty_indicators"] += 1
                    has_issue = True

    if not data.get("ocs_content", {}).get("ocu_units"):
        issues["empty_ocu_units"] += 1
        has_issue = True

    # Check attitudes merged into one item
    attitudes = data.get("ocs_attitude", {}).get("attitudes", [])
    for att in attitudes:
        name = att.get("name", "")
        codes_found = re.findall(r"A\d{2}", name)
        if len(codes_found) > 1:
            issues["merged_attitudes"] += 1
            has_issue = True
            if len(merged_examples) < 3:
                merged_examples.append((f.name, name[:80]))
            break

    # Check newlines in K/S names
    for unit in data.get("ocs_content", {}).get("ocu_units", []):
        for task in unit.get("tasks", []):
            for block in task.get("competency_blocks", []):
                for item in block.get("knowledge", []) + block.get("skills", []):
                    if "\n" in item.get("name", ""):
                        issues["newline_in_ks_name"] += 1

    # Check job_category_name missing (null is valid per schema; only flag if key is absent)
    ocs_name = data.get("ocs_profile", {}).get("ocs_name", {})
    if "job_category_name" not in ocs_name:
        issues["missing_job_category"] += 1
        has_issue = True

    if has_issue:
        files_with_issues.add(f.name)

print(f"Total files: {len(files)}")
print(f"\nIssues found:")
for k, v in issues.items():
    print(f"  {k}: {v}")
print(f"\nFiles with at least one issue: {len(files_with_issues)}")
print(f"\nMerged attitude examples:")
for fname, ex in merged_examples:
    print(f"  [{fname}] {ex}")
