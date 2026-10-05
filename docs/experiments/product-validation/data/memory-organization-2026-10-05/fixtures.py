"""Frozen material projection for B2 comparisons; no database or provider access."""

from copy import deepcopy


def bounded_material(material):
    messages = material["messages"]
    frontier = material["snapshot"]["covered_through_sequence"]
    if [item["interview_sequence"] for item in messages] != list(
        range(1, len(messages) + 1)
    ):
        raise ValueError("Interview sequences are not contiguous")
    if (
        not 0 < frontier <= len(messages)
        or messages[frontier - 1]["speaker"] != "employee"
    ):
        raise ValueError("Memory must end at its original formal employee source")
    for key, item in material["objects"].items():
        if key.startswith("work_situation:") and any(
            type(sequence) is not int or not 1 <= sequence <= frontier
            for sequence in item["interview_references"]
        ):
            raise ValueError("Situation reference exceeds the original source boundary")
    result = deepcopy(material)
    result["messages"] = result["messages"][:frontier]
    return result
