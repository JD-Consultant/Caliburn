"""
End-to-end API test for OCS export endpoints.
Creates a test profile with ocs_document in DB, then calls all 4 export formats.
Run: python scripts/test_ocs_api.py
"""
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

BASE = "http://localhost:8000/api/v1"

OCS_DOC = {
    "version_info": {"versions": [{"status": "最新版本", "ocs_code": "ENT-TST-001"}]},
    "ocs_profile": {
        "ocs_code": "ENT-TST-001",
        "ocs_name": {"occupation_name": "測試職稱"},
        "job_description": "這是一個測試用職務描述。",
        "ocs_level": 3,
        "category": {"job_categories": [{"name": "測試"}], "industries": [{"name": "測試業"}]},
    },
    "ocs_content": {
        "ocu_units": [
            {
                "ocu_code": "ENT-U001",
                "ocu_name": "核心職責執行",
                "tasks": [
                    {
                        "task_codes": [{"code": "ENT-T001", "name": "執行測試任務"}],
                        "competency_blocks": [
                            {
                                "competency_level": 3,
                                "indicators": [{"code": "ENT-P001", "text": "在接收任務後完成測試並回報結果。"}],
                                "outputs": [{"code": "ENT-O001", "name": "測試報告"}],
                                "knowledge": [
                                    {"code": "ENT-K001", "name": "測試知識", "source_type": "company_defined"}
                                ],
                                "skills": [
                                    {"code": "ENT-S001", "name": "測試技能", "source_type": "icap_official", "icap_ref": "TST-S001"}
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    },
    "ocs_attitude": {
        "attitudes": [
            {"code": "ENT-A001", "name": "認真負責", "source_type": "icap_official", "icap_ref": "TST-A001"}
        ]
    },
}


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Create user
        email = f"test-ocs-{uuid.uuid4().hex[:6]}@example.com"
        r = await client.post(f"{BASE}/users/", json={"email": email, "name": "OCS Test User"})
        assert r.status_code == 201, f"Create user failed: {r.text}"
        user_id = r.json()["id"]
        print(f"User created: {user_id}")

        # 2. Create profile
        r = await client.post(
            f"{BASE}/job-profiles/?user_id={user_id}",
            json={"job_title": "測試職稱", "department": "測試部"},
        )
        assert r.status_code == 201, f"Create profile failed: {r.text}"
        profile_id = r.json()["id"]
        print(f"Profile created: {profile_id}")

        # 3. Directly patch graph_state + stage via SQLAlchemy (bypass interview)
        from app.database import AsyncSessionLocal
        from app.models import JobProfile
        async with AsyncSessionLocal() as db:
            p = await db.get(JobProfile, uuid.UUID(profile_id))
            p.stage = "preview"
            p.graph_state = {
                "ocs_document": OCS_DOC,
                "icap_candidates": [],
            }
            await db.commit()
        print("Profile patched to preview stage with ocs_document")

        # 4. Test all 4 export formats
        errors = []
        for fmt in ["json", "docx", "pdf", "xlsx"]:
            r = await client.post(f"{BASE}/documents/{profile_id}/export?format={fmt}")
            if r.status_code == 200:
                size = len(r.content)
                ct = r.headers.get("content-type", "")
                print(f"  {fmt.upper():5s} OK — {size:,} bytes  ({ct[:40]})")
            else:
                print(f"  {fmt.upper():5s} FAIL — {r.status_code}: {r.text[:120]}")
                errors.append(fmt)

        # 5. Verify /versions endpoint
        r = await client.get(f"{BASE}/documents/{profile_id}/versions")
        versions = r.json()
        print(f"\n/versions returns {len(versions)} entries: {[v['format'] for v in versions]}")

        # 6. Verify JSON structure correctness
        r = await client.post(f"{BASE}/documents/{profile_id}/export?format=json")
        ocs_returned = r.json()
        assert ocs_returned.get("ocs_profile", {}).get("ocs_code") == "ENT-TST-001"
        units = ocs_returned.get("ocs_content", {}).get("ocu_units", [])
        assert len(units) == 1
        tasks = units[0]["tasks"]
        assert tasks[0]["task_codes"][0]["code"] == "ENT-T001"
        block = tasks[0]["competency_blocks"][0]
        assert block["indicators"][0]["code"] == "ENT-P001"
        assert block["knowledge"][0]["source_type"] == "company_defined"
        assert block["skills"][0]["icap_ref"] == "TST-S001"
        attitudes = ocs_returned.get("ocs_attitude", {}).get("attitudes", [])
        assert attitudes[0]["icap_ref"] == "TST-A001"
        print("\nJSON structure validation passed — all OCS fields intact.")

        print()
        if errors:
            print(f"FAILED formats: {errors}")
            sys.exit(1)
        else:
            print("All API export endpoints passed.")


if __name__ == "__main__":
    asyncio.run(main())
