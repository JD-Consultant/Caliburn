"""Schema validation."""

from typing import Tuple, List
from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.utils.logger import logger


class OCSSchemaValidator:
    """Validate OCS model against schema rules."""

    REQUIRED_KEYS = {
        "version_info",
        "ocs_profile",
        "ocs_content",
        "ocs_attitude",
        "notes_and_appendix",
    }

    def validate(self, model: OCSDocument) -> Tuple[bool, List[str]]:
        """Validate model against business rules. Returns (is_valid, error_messages)."""
        errors: List[str] = []

        # Rule 1: all top-level keys present
        try:
            missing_keys = self.REQUIRED_KEYS - set(model.model_dump().keys())
            if missing_keys:
                errors.append(f"Missing required keys: {missing_keys}")
        except Exception as e:
            errors.append(f"Failed to check top-level keys: {str(e)}")

        # Rule 2: every competency block must have at least one indicator;
        #         knowledge/skill items must have code and name
        for unit in model.ocs_content.ocu_units:
            for task in unit.tasks:
                for block_idx, block in enumerate(task.competency_blocks):
                    loc = f"OCU {unit.ocu_code}, Task {task.task_code}, Block {block_idx}"
                    if not block.indicators:
                        errors.append(f"{loc}: missing behavioral indicators")
                    for i, item in enumerate(block.knowledge):
                        if not item.code or not item.name:
                            errors.append(f"{loc}: knowledge[{i}] missing code or name")
                    for i, item in enumerate(block.skills):
                        if not item.code or not item.name:
                            errors.append(f"{loc}: skill[{i}] missing code or name")

        # Rule 3: attitude description key must always exist (even if null)
        for i, att in enumerate(model.ocs_attitude.attitudes):
            if not hasattr(att, "description"):
                errors.append(f"Attitude[{i}]: missing description key")

        if errors:
            for error in errors:
                logger.debug(f"  - {error}")

        return len(errors) == 0, errors
