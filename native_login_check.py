"""Explicit, isolated packaged GUI regression check; never enabled by normal launch."""
import json
import os
import time
from pathlib import Path


def configure(app, license_client, namespace):
    root = Path(os.environ.get('CF_DATA_DIR', ''))
    if not root.name.startswith('chatflow-login-check-') or not root.is_dir():
        raise RuntimeError('Login self-test requires its own temporary data directory')
    phase = os.environ['CF_LOGIN_CHECK_PHASE']
    if phase not in ('write','restore','logout','cleared','temporary','temporary-cleared'):
        raise RuntimeError('Unknown login check phase')
    # This fixture is not a real GitHub credential. Production validation is
    # unchanged, and no testing endpoint is registered in normal execution.
    namespace['_validate_github_creds'] = lambda user, token: (
        user == 'gui-fixture' and token == 'gui-fixture-not-a-real-token', 'invalid fixture')
    license_client.check_license = lambda: (True, 'isolated GUI test')
    # Cocoa uses the application data store rather than storage_path. A unique
    # cookie name prevents tests from touching the user's actual login cookie.
    app.config['SESSION_COOKIE_NAME'] = 'cf_gui_' + root.name.replace('-','_')
    requests = []
    from flask import request
    @app.after_request
    def trace_response(response):
        requests.append({'method': request.method, 'path': request.path,
                         'status': response.status_code,
                         'redirect': response.headers.get('Location', '').split('?')[0]})
        return response
    def check(window):
        report = {'ok':False,'phase':phase}
        try:
            assert window.events.shown.wait(30) and window.events.loaded.wait(30)
            if phase in ('write','temporary'):
                assert window.get_current_url().endswith('/login'), window.get_current_url()
                # Return across the JS bridge before navigating away; otherwise
                # WebView2 can discard the pending evaluate_js response.
                window.evaluate_js("document.querySelector('[name=username]').value='gui-fixture'; document.querySelector('[name=token]').value='gui-fixture-not-a-real-token'; document.querySelector('[name=remember]').checked=" + ('true' if phase=='write' else 'false') + "; setTimeout(()=>document.querySelector('form').requestSubmit(),100); null;")
            elif phase == 'logout':
                assert window.get_current_url().endswith('/admin'), window.get_current_url()
                window.evaluate_js("setTimeout(()=>document.querySelector('form[action=\"/logout\"]').requestSubmit(),100); null;")
            expected = '/admin' if phase in ('write','restore','temporary') else '/login'
            deadline=time.monotonic()+30
            while not window.get_current_url().endswith(expected):
                if time.monotonic()>deadline:raise RuntimeError('Expected '+expected)
                time.sleep(.2)
            # Exercise a normal close; remembered credentials belong to the
            # application and do not depend on WebView profile persistence.
            time.sleep(3)
            report.update(ok=True, destination=expected)
        except Exception as error:
            report['error']=type(error).__name__+': '+str(error)
            report['current_url']=window.get_current_url()
            try:
                report['dom']=window.evaluate_js("({url:location.href,events:window.__loginEvents,form:document.querySelector('form[action=\"/logout\"]')?.outerHTML})")
            except Exception:
                pass
        finally:
            report['requests'] = requests[-50:]
            (root/('login-'+phase+'.json')).write_text(json.dumps(report),encoding='utf-8')
            window.destroy()
    return check
