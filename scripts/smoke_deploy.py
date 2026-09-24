"""Run the actual frozen app with no system Git on PATH."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

binary = Path('dist/ChatFLOW/ChatFLOW.exe').resolve()
with tempfile.TemporaryDirectory(prefix='chatflow-deploy-smoke-') as folder:
    env = dict(os.environ, CF_DATA_DIR=folder, CF_NO_OPEN='1', PYTHONIOENCODING='utf-8')
    env['PATH'] = os.path.join(env.get('SystemRoot', r'C:\Windows'), 'System32')
    for key in list(env):
        if key.startswith('GIT_'): env.pop(key, None)
    env['GIT_CONFIG_NOSYSTEM'] = '1'
    env['GIT_CONFIG_GLOBAL'] = os.devnull
    result = subprocess.run([str(binary), '--self-test-deploy'], env=env, timeout=240)
    report = json.loads(Path(folder, 'self-test-deploy.json').read_text(encoding='utf-8'))
    print(json.dumps(report), flush=True)
    assert result.returncode == 0 and report['ok'], report
