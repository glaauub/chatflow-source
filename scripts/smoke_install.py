"""Verify installation and reinstallation preserve an existing customer profile."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='ChatFLOW upgrade ') as folder:
    root = Path(folder)
    profile = root / 'existing-profile'
    os.environ['CF_DATA_DIR'] = str(profile)
    import app as server
    from models import get_db, set_config
    set_config('company_name', 'Existing customer company')
    connection = get_db()
    connection.execute("INSERT INTO products(name,price,spec,img,description) VALUES(?,?,?,?,?)", ('Existing product', '18', 'SKU-OLD', 'existing.png', 'Existing description'))
    connection.commit(); connection.close()
    sentinels = {
        'static/uploads/existing.png': b'existing image fixture',
        'instance/license.json': b'{"customer_test_marker":true}',
        'models/existing-model.gguf': b'existing model fixture',
    }
    for name, content in sentinels.items():
        path = profile / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    server.remembered_login.save('existing-account', 'test-token-only')
    login_path = profile / 'instance/remembered_login.enc'
    saved_login = login_path.read_bytes()
    installer = Path('dist/ChatFLOW-Windows-x64-v2.1.7-Setup.exe').resolve()
    target = root / 'installed application'
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    env['PATH'] = os.path.join(env.get('SystemRoot', r'C:\Windows'), 'System32')
    for phase in (1, 2):
        subprocess.run([str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/DIR=' + str(target)], check=True, timeout=240)
        result = subprocess.run([str(target / 'ChatFLOW.exe'), '--self-test-deploy'], env=env, timeout=240)
        report = json.loads((profile / 'self-test-deploy.json').read_text(encoding='utf-8'))
        assert result.returncode == 0 and report['ok'], report
        connection = get_db()
        assert connection.execute("SELECT name,description FROM products WHERE name='Existing product'").fetchone() is not None
        assert connection.execute("SELECT value FROM site_config WHERE key='company_name'").fetchone()[0] == 'Existing customer company'
        connection.close()
        assert login_path.read_bytes() == saved_login
        for name, content in sentinels.items(): assert (profile / name).read_bytes() == content, name
    print('Installation and reinstallation preserved products, settings, image, activation file, saved credentials and model fixture.')
