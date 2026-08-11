"""Stable citable identifiers (URN) for OCS entities. Composed at query time
from payload fields; never stored. Scheme: ocs:{ocs_code}[:{TYPE}:{code}]."""
from __future__ import annotations


def occupation_urn(ocs_code: str) -> str:
    return f"ocs:{ocs_code}"


def unit_urn(ocs_code: str, ocu_code: str) -> str:
    return f"ocs:{ocs_code}:U:{ocu_code}"


def task_urn(ocs_code: str, task_code: str) -> str:
    return f"ocs:{ocs_code}:T:{task_code}"


def item_urn(ocs_code: str, type_: str, code: str) -> str:
    return f"ocs:{ocs_code}:{type_}:{code}"
