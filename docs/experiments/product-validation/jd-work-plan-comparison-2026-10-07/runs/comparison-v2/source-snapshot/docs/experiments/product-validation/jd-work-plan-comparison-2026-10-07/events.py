"""Anonymous public manual-editor intent, executed only by formal product HTTP."""

from uuid import uuid4

from caliburn.contracts.generated.edit_jd_tasks_request import EditJdTasksRequest
from materials import MANUAL_TEXT, PROFILES


def manual_pending(profile, work, question_id):
    return {
        "question_id": question_id,
        "review_kind": "manual_jd_edit",
        "current_jd": work,
        "public_initial": PROFILES[profile]["initial"],
        "required_text": MANUAL_TEXT[profile],
        "instruction": "只按公开语意局部修订相應task，保留其他有效细節；等价no_op，无相應task可create。不得讀Plan、oracle、arm。",
    }


def manual_command(pending, decision):
    if decision.get("question_id") != pending["question_id"]:
        raise ValueError("Manual decision belongs to another event")
    if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
        raise ValueError("Manual edit needs a public semantic reason")
    action = decision.get("action")
    if action == "no_op":
        return None
    description = decision.get("description")
    if not isinstance(description, str) or pending["required_text"] not in description:
        raise ValueError("Manual edit must retain the frozen public expression")
    if action == "revise_task":
        task_id = decision.get("task_id")
        if task_id not in {item["task_id"] for item in pending["current_jd"]["tasks"]}:
            raise ValueError(
                "Manual task identity is not in the current formal revision"
            )
        change = {
            "action": action,
            "task_id": task_id,
            "changes": [
                {"action": "set_field", "field": "description", "value": description}
            ],
        }
    elif action == "create_task":
        change = {
            "action": action,
            "area_id": None,
            "title": decision.get("title"),
            "description": description,
            "outcomes": [],
            "requirements": [],
        }
    else:
        raise ValueError("Manual action is not within the frozen event")
    return EditJdTasksRequest.model_validate(
        {
            "command_id": str(uuid4()),
            "expected_revision_id": pending["current_jd"]["revision_id"],
            "change": change,
        }
    ).model_dump(mode="json")
