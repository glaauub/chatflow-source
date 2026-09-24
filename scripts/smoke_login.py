"""Close and relaunch the actual packaged GUI using the same persistent profile."""
import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

binary = Path(os.environ['CF_TEST_BINARY']) if os.environ.get('CF_TEST_BINARY') else (Path('dist/ChatFLOW/ChatFLOW.exe') if os.name == 'nt' else Path('dist/ChatFLOW.app/Contents/MacOS/ChatFLOW'))
with tempfile.TemporaryDirectory(prefix='chatflow-login-check-', ignore_cleanup_errors=True) as data:
    for phase in ('write','restore','logout','cleared','temporary','temporary-cleared'):
        env = dict(os.environ,CF_DATA_DIR=data,CF_NO_OPEN='1',CF_LOGIN_CHECK_PHASE=phase,PYTHONIOENCODING='utf-8')
        command = [sys.executable, 'app.py'] if '--source' in sys.argv else [str(binary.resolve())]
        try:
            process=subprocess.run(command+['--self-test-login-window'],env=env,timeout=90)
            returncode=process.returncode
        except subprocess.TimeoutExpired:
            returncode=-1
        result_path=Path(data,'login-'+phase+'.json')
        result=json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {'ok':False,'phase':phase,'error':'no report'}
        print(json.dumps(result),flush=True)
        if returncode or not result['ok']:
            for name in ('startup.log','crash.log','error.log'):
                path=Path(data,name)
                if path.exists():print(name,json.dumps(path.read_text(encoding='utf-8')[-12000:]),flush=True)
        assert returncode == 0 and result['ok'],result
