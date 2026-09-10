import pytest


def test_fixed_node_validates_complete_value():
    from analysis_agent.jd_engine import JdEngine
    value = [{'type': 'p', 'id': 'first', 'children': [{'text': '工作'}]}]
    result = JdEngine().validate_value(value)
    assert result.value == value
    assert result.operations == []


def test_fixed_node_rejects_invalid_value():
    from analysis_agent.jd_engine import JdEngine, JdEngineFailure
    with pytest.raises(JdEngineFailure):
        JdEngine().validate_value([])


@pytest.mark.parametrize('script', [
    'import time; time.sleep(60)',
    "import sys; sys.stdout.write('{')",
    "import sys; sys.stdout.write('x' * 4096)",
    "import sys; sys.stderr.write('x' * 10000)",
])
def test_faults_stop_and_reap_without_replay(monkeypatch, script):
    import subprocess
    import sys
    from analysis_agent.jd_engine import JdEngine, JdEngineFailure
    original, processes = subprocess.Popen, []
    def launch(argv, **kwargs):
        assert len(argv) == 3 and argv[-1] == 'validate-value' and kwargs['shell'] is False
        assert not any('KEY' in key or 'DATABASE' in key or key == 'NODE_OPTIONS' for key in kwargs['env'])
        proc = original([sys.executable, '-c', script], **kwargs)
        processes.append(proc)
        return proc
    monkeypatch.setattr(subprocess, 'Popen', launch)
    with pytest.raises(JdEngineFailure) as caught:
        JdEngine(timeout=.3, max_bytes=1024).validate_value([{'id': 'p', 'type': 'p', 'children': [{'text': ''}]}])
    assert caught.value.quiescent
    assert len(processes) == 1 and processes[0].poll() is not None


def test_cancel_reaps_active_process(monkeypatch):
    import subprocess
    import sys
    from threading import Event, Timer
    from analysis_agent.jd_engine import JdEngine, JdEngineFailure
    original, processes, stop = subprocess.Popen, [], Event()
    def launch(argv, **kwargs):
        proc = original([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        processes.append(proc)
        Timer(.1, stop.set).start()
        return proc
    monkeypatch.setattr(subprocess, 'Popen', launch)
    with pytest.raises(JdEngineFailure):
        JdEngine().validate_value([{'id': 'p', 'type': 'p', 'children': [{'text': ''}]}], cancel=stop)
    assert len(processes) == 1 and processes[0].poll() is not None


def test_full_r2_and_design_batch_measurements():
    import json
    from pathlib import Path
    import time
    from analysis_agent.jd_engine import JdEngine
    value = json.loads((Path(__file__).parents[2] / 'jd-editor/fixtures/r2-canonical.json').read_text(encoding='utf-8'))
    start = time.monotonic()
    result = JdEngine().validate_value(value)
    validated = time.monotonic()
    assert result.value == value
    # Schema has no count cap: use 100 real commands as a measured stress batch,
    # and report that no schema-defined maximum exists rather than invent one.
    target = next(node for node in value if node['type'] == 'p')
    commands = [{'type': 'replace_block_content', 'target_id': target['id'], 'content': [{'text': '批次' + str(i)}]} for i in range(100)]
    transformed = JdEngine().transform(value, commands)
    assert transformed.value != value
    print(json.dumps({'r2_bytes': len(json.dumps(value, ensure_ascii=False).encode()),
        'batch_commands': 100, 'operations': len(transformed.operations),
        'request_bytes': len(json.dumps({'profile': {'format_version': 2, 'engine_profile': 'jd-plate-clean-v2'},
            'base_value': value, 'commands': commands}, ensure_ascii=False).encode()),
        'output_bytes': len(json.dumps(transformed.value, ensure_ascii=False).encode()),
        'validate_elapsed_seconds': validated - start,
        'transform_elapsed_seconds': time.monotonic() - validated,
        'elapsed_seconds': time.monotonic() - start}))
