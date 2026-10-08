"""Validate per-subquestion semantic decisions; never infer disclosure from keywords."""


def reviewed_answer(employee, question, decision):
    parts = decision.get("subquestions")
    if not isinstance(parts, list) or not parts or len(parts) > 12:
        raise ValueError("Semantic review must adjudicate every actual subquestion")
    selected = []
    unknown = []
    refused = []
    clarify = []
    refusal_topics = {
        fact["topic"] for fact in employee.profile["facts"] if fact.get("refused")
    }
    for part in parts:
        quote, mode, ids = part.get("quote"), part.get("mode"), part.get("fact_ids")
        if (
            not isinstance(quote, str)
            or quote not in question
            or not quote.strip()
            and mode != "no_question"
            or mode not in {"answer", "unknown", "refused", "clarify", "no_question"}
            or not isinstance(ids, list)
            or any(not isinstance(value, str) for value in ids)
            or (mode == "answer") != bool(ids)
            or not isinstance(part.get("reason"), str)
            or not part["reason"].strip()
        ):
            raise ValueError("Invalid actual subquestion decision")
        selected.extend(ids)
        if mode == "unknown":
            unknown.append(quote)
        if mode == "refused":
            topic = part.get("refused_topic")
            if topic not in refusal_topics:
                raise ValueError("Refusal must identify a frozen refusal scope")
            refused.append((quote, topic))
        if mode == "clarify":
            clarify.append(quote)
    selected = list(dict.fromkeys(selected))
    if selected != decision.get("fact_ids") or len(selected) > 4:
        raise ValueError("Selected frozen facts differ from subquestion decisions")
    if (decision.get("mode") == "answer") != bool(selected):
        raise ValueError("Aggregate review mode differs from subquestions")
    if not selected:
        expected_mode = next(
            (part["mode"] for part in parts if part["mode"] != "no_question"),
            "no_question",
        )
        if decision.get("mode") != expected_mode:
            raise ValueError(
                "Non-answer aggregate mode differs from actual subquestion decisions"
            )
    corrected = dict(decision)
    # A replay of an earlier provisional statement must include its already-public correction.
    if (
        "training" in selected
        and "training-boundary" in employee.disclosed
        and "training-boundary" not in selected
    ):
        if len(selected) >= 4:
            raise ValueError("Known correction does not fit the four-fact bound")
        corrected["fact_ids"] = [*selected, "training-boundary"]
    corrected["unknown_subtopics"] = unknown if selected else []
    answer = employee.reviewed_answer(question, corrected)
    for quote, topic in refused:
        if selected or len(parts) > 1:
            answer += f"\n\n關於你問的「{quote}」：這個個案我不想談，也不能提供他人個資，請先保留。"
        employee.refused_topics.add(topic)
    for quote in clarify:
        if selected or len(parts) > 1:
            answer += f"\n\n關於你問的「{quote}」：這個問題我還沒理解，請用實際工作步驟或責任再具體問一次。"
    if not selected and unknown and decision["mode"] != "unknown":
        answer += (
            "\n\n關於你問的「"
            + "」、「".join(unknown)
            + "」，我目前沒有確定資料，請保留未知，不補猜。"
        )
    employee.audit[-1]["employee_text"] = answer
    employee.audit[-1]["subquestions"] = parts
    employee.audit[-1]["refused_subquestions"] = [quote for quote, _topic in refused]
    employee.audit[-1]["clarify_subquestions"] = clarify
    return answer
