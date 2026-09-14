"""Load the accepted jd_tools bytes only for this isolated pytest process."""
import hashlib
import importlib.util
from pathlib import Path
import runpy
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
relative = 'experiments/analysis-agent/src/analysis_agent/jd_tools.py'
accepted = subprocess.check_output(['git', 'show', '444416722190fd48c14f4423d101f36b25831de1:' + relative], cwd=root)
frozen = root / '.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-5-snapshot' / relative
assert accepted.decode().replace('\r\n', '\n') == frozen.read_text(encoding='utf-8').replace('\r\n', '\n')
print('RED accepted jd_tools SHA256:', hashlib.sha256(accepted).hexdigest(), flush=True)
print('RED frozen overlay SHA256:', hashlib.sha256(frozen.read_bytes()).hexdigest(), flush=True)
spec = importlib.util.spec_from_file_location('analysis_agent.jd_tools', frozen)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
runpy.run_path(str(root / 'experiments/analysis-agent/tests/task5_acceptance_runner.py'), run_name='__main__')
