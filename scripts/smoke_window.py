"""Exercise the actual packaged native GUI event loop, not just module imports."""
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

binary = Path('dist/ChatFLOW/ChatFLOW.exe') if os.name == 'nt' else Path('dist/ChatFLOW.app/Contents/MacOS/ChatFLOW')
with tempfile.TemporaryDirectory(prefix='chatflow-window-check-', ignore_cleanup_errors=True) as data:
    env = dict(os.environ, CF_DATA_DIR=data, CF_NO_OPEN='1')
    process = subprocess.run([str(binary.resolve()), '--self-test-window'], env=env, timeout=90)
    report_path = Path(data, 'self-test-window.json')
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {'ok':False,'error':'No window report'}
    print(json.dumps(report),flush=True)
    if process.returncode or not report['ok']:
        for name in ('startup.log','crash.log','error.log'):
            path=Path(data,name)
            if path.exists():print(name,path.read_text(encoding='utf-8')[-12000:],flush=True)
    assert process.returncode == 0 and report['ok'] and report['shown'] and report['loaded'], report
    assert report['architecture'] == platform.machine(), report
    print(json.dumps(report))
