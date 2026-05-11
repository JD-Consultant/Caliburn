"""Schema validation."""

from typing import Tuple, List
from jsonschema import validate, ValidationError as JsonSchemaError
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
        """
        Validate model against business rules.
        
        Returns:
            (is_valid, error_messages)
        """
        errors: List[str] = []

        # Rule 1: All top-level keys present
        try:
            model_dict = model.model_dump()
            missing_keys = self.REQUIRED_KEYS - set(model_dict.keys())
            if missing_keys:
                errors.append(f"Missing required keys: {missing_keys}")
        except Exception as e:
            errors.append(f"Failed to check top-level keys: {str(e)}")

        # Rule 2: competency blocks must carry P indicators, and knowledge/skills must be objects.
        if hasattr(model, "ocs_content") and model.ocs_content:
            for unit_idx, unit in enumerate(model.ocs_content.ocu_units):
                for task_idx, task in enumerate(unit.tasks):
                    blocks = getattr(task, "competency_blocks", [])
                    for block_idx, block in enumerate(blocks):
                        if not getattr(block, "indicators", None):
                            errors.append(
                                f"OCU {unit.ocu_code}, Task {task.task_code}, Block {block_idx}: missing behavioral indicators"
                            )

                        for skill_idx, skill in enumerate(block.skills_s):
                            if not hasattr(skill, "code") or not hasattr(skill, "name"):
                                errors.append(
                                    f"OCU {unit.ocu_code}, Task {task.task_code}, Block {block_idx}: "
                                    f"skill[{skill_idx}] missing code or name"
                                )
                        for knowl_idx, knowl in enumerate(block.knowledge_k):
                            if not hasattr(knowl, "code") or not hasattr(knowl, "name"):
                                errors.append(
                                    f"OCU {unit.ocu_code}, Task {task.task_code}, Block {block_idx}: "
                                    f"knowledge[{knowl_idx}] missing code or name"
                                )

        # Rule 3: attitude_description must have key (even if null)
        if hasattr(model, "ocs_attitude") and model.ocs_attitude:
            for att_idx, att in enumerate(model.ocs_attitude.attitudes):
                if not hasattr(att, "attitude_description"):
                    errors.append(f"Attitude[{att_idx}]: missing attitude_description key")

        if errors:
            logger.warning(f"Validation failed with {len(errors)} error(s)")
            for error in errors:
                logger.debug(f"  - {error}")

        return len(errors) == 0, errors
