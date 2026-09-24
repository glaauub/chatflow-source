"""Exercise the optional AI engine from each real frozen app, with public model data."""
import json, os, subprocess, tempfile
from pathlib import Path
binary = Path('dist/ChatFLOW/ChatFLOW.exe') if os.name == 'nt' else Path('dist/ChatFLOW.app/Contents/MacOS/ChatFLOW')
with tempfile.TemporaryDirectory(prefix='chatflow-local-ai-check-') as data:
    env = dict(os.environ, CF_DATA_DIR=data, CF_NO_OPEN='1', CF_AI_HOME=str(Path(data, 'ai')))
    result = subprocess.run([str(binary.resolve()), '--self-test-ai'], env=env, timeout=900)
    status = Path(data, 'self-test-ai.json')
    if result.returncode or not status.exists():
        if status.exists(): print(status.read_text(encoding='utf-8'))
        raise SystemExit('Frozen local AI self-test failed')
    report = json.loads(status.read_text(encoding='utf-8'))
    assert report['version'] == '2.1.8' and report['ok'] and report['local_only'], report
    print(json.dumps(report))
