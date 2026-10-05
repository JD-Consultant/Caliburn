"""Exact public synthetic interview projection; no paraphrase or employee fact inference."""


def span(turn, speaker, text, start=0, end=None):
    end = len(text) if end is None else end
    return {'turn': turn, 'speaker': speaker, 'start': start, 'end': end, 'text': text[start:end]}


def project_turns(turns, question_turns):
    units = []
    for index, turn in enumerate(turns):
        if turn['status'] != 'completed' or not turn['employee']:
            raise ValueError('source turn is not a completed employee answer')
        if turn['turn'] != index + 1:
            raise ValueError('source chronology incomplete')
        question = None
        if turn['turn'] in question_turns:
            if index == 0:
                raise ValueError('opening cannot use an invented preceding question')
            previous = turns[index - 1]
            body = previous['consultant']
            separator = body.rfind('\n\n')
            start = separator + 2 if separator >= 0 else 0
            question = span(previous['turn'], 'consultant', body, start)
        units.append({'answer': span(turn['turn'], 'employee', turn['employee']), 'question': question})
    return units


def query_from_units(units, turn_ids, anchor=None):
    requested = set(turn_ids)
    if not requested <= {unit['answer']['turn'] for unit in units}:
        raise ValueError('query refers to absent employee turn')
    parts, spans = [], []
    if anchor is not None:
        parts.append('員工共同脈絡：' + anchor['text'])
        spans.append(anchor)
    for unit in units:
        if unit['answer']['turn'] not in requested:
            continue
        if unit['question'] is not None:
            parts.append('顧問提問：' + unit['question']['text'])
            spans.append(unit['question'])
        parts.append('員工回答：' + unit['answer']['text'])
        spans.append(unit['answer'])
    return '\n'.join(parts), spans
