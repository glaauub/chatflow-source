"""Verify the frozen binary can import the application and generate offline pages."""
import json,os,platform,subprocess,tempfile,time
from pathlib import Path
binary = Path('dist/ChatFLOW/ChatFLOW.exe') if os.name=='nt' else Path('dist/ChatFLOW.app/Contents/MacOS/ChatFLOW')
with tempfile.TemporaryDirectory(prefix='chatflow-bundle-check-') as data:
    env=dict(os.environ, CF_DATA_DIR=data, CF_NO_OPEN='1')
    result=subprocess.run([str(binary.resolve()), '--self-test', '--check-license-server'],env=env,timeout=120)
    status=Path(data,'self-test.json')
    if result.returncode or not status.exists(): raise SystemExit('Frozen binary self-test failed')
    report=json.loads(status.read_text())
    assert report['version']=='2.1.8' and report['ok'],report
    assert report['license_server_tls'],report
    assert report['architecture']==platform.machine(),report
    print(json.dumps(report))
