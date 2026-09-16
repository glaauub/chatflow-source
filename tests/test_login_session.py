import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadSignature

import test_v2 as release_tests
from login_session import EncryptedSessionInterface, RememberedLogin

server = release_tests.server


class LoginSessionTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        self.temp=tempfile.TemporaryDirectory(prefix='chatflow-login-unit-')
        self.addCleanup(self.temp.cleanup)
        store=RememberedLogin(self.temp.name,server.app.secret_key)
        patcher=patch.object(server,'remembered_login',store)
        patcher.start();self.addCleanup(patcher.stop)
        self.license = patch.object(server.license_client, 'check_license', return_value=(True, 'ok'))
        self.license.start()
        self.addCleanup(self.license.stop)

    def login(self, remember=True):
        data = {'username': 'fixture-user', 'token': 'fixture-private-token'}
        if remember:
            data['remember'] = '1'
        with patch.object(server, '_validate_github_creds', return_value=(True, None)):
            return self.client.post('/login', data=data)

    def test_remember_survives_new_client_and_serializer(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        header = response.headers['Set-Cookie']
        self.assertIn('Expires=', header)
        self.assertIn('HttpOnly', header)
        cookie = self.client.get_cookie('chatflow_session').value
        self.assertTrue(cookie.startswith('enc1.'))
        self.assertNotIn('fixture-private-token', cookie)
        app2 = Flask('restart')
        app2.secret_key = server._load_secret()
        serializer = EncryptedSessionInterface().get_signing_serializer(app2)
        decoded = serializer.loads(cookie, max_age=3600)
        self.assertEqual(decoded['github_token'], 'fixture-private-token')
        self.assertTrue(decoded['_permanent'])
        fresh = server.app.test_client()
        fresh.set_cookie('chatflow_session', cookie)
        self.assertEqual(fresh.get('/login').location, '/admin')
        with patch.object(server, '_validate_github_creds', side_effect=RuntimeError('network unavailable')):
            self.assertEqual(fresh.get('/admin').status_code, 200)

    def test_optional_session_only_and_logout(self):
        response = self.login(False)
        self.assertNotIn('Expires=', response.headers['Set-Cookie'])
        response = self.client.post('/logout')
        self.assertEqual(response.location, '/login')
        self.assertIsNone(self.client.get_cookie('chatflow_session'))
        self.assertEqual(self.client.get('/admin').location, '/login')

    def test_bad_credentials_are_not_saved(self):
        with patch.object(server, '_validate_github_creds', return_value=(False, 'invalid')):
            response = self.client.post('/login', data={'username':'wrong','token':'bad','remember':'1'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.get_cookie('chatflow_session'))

    def test_token_never_rendered_into_login_or_admin(self):
        self.login()
        self.assertNotIn(b'fixture-private-token', self.client.get('/admin').data)
        self.client.post('/logout')
        self.assertNotIn(b'fixture-private-token', self.client.get('/login').data)

    def test_background_reads_do_not_reissue_cookie_after_logout(self):
        self.login()
        cookie = self.client.get_cookie('chatflow_session').value
        late = server.app.test_client()
        late.set_cookie('chatflow_session', cookie)
        self.client.post('/logout')
        # An already-running browser request must not restore the cleared
        # cookie when its response arrives after the logout response.
        self.assertNotIn('Set-Cookie', late.get('/api/config').headers)

    def test_restart_restores_without_any_browser_cookie(self):
        self.login()
        saved=server.remembered_login.path.read_bytes()
        self.assertNotIn(b'fixture-private-token',saved)
        fresh_store=RememberedLogin(self.temp.name,server._load_secret())
        with patch.object(server,'remembered_login',fresh_store):
            launch=fresh_store.launch_url('http://localhost')
            fresh=server.app.test_client()
            self.assertEqual(fresh.get('/admin').location,'/login')
            self.assertEqual(fresh.get(launch).location,'/admin')
            self.assertEqual(fresh.get('/admin').status_code,200)
            self.assertEqual(server.app.test_client().get(launch).location,'/login')
            fresh.post('/logout')
            self.assertIsNone(fresh_store.load())

    def test_temporary_login_and_invalid_ticket_do_not_restore(self):
        self.login(False)
        self.assertFalse(server.remembered_login.path.exists())
        self.assertEqual(server.remembered_login.launch_url('http://localhost'),'http://localhost')
        self.assertEqual(server.app.test_client().get('/resume-login?ticket=wrong').location,'/login')

    def test_tamper_or_other_secret_rejected(self):
        self.login()
        cookie = self.client.get_cookie('chatflow_session').value
        other = Flask('other'); other.secret_key='different-private-key'
        with self.assertRaises(BadSignature):
            EncryptedSessionInterface().get_signing_serializer(other).loads(cookie, max_age=3600)
        self.client.set_cookie('chatflow_session', cookie[:-12]+'corrupted123')
        self.assertEqual(self.client.get('/admin').location, '/login')

    def test_old_signed_session_migrates_then_logout_cannot_reimport(self):
        old = SecureCookieSessionInterface().get_signing_serializer(server.app).dumps(
            {'github_user':'fixture-user','github_token':'fixture-private-token'})
        self.client.set_cookie('session',old)
        self.assertEqual(self.client.get('/admin').status_code,200)
        self.assertIsNone(self.client.get_cookie('session'))
        self.assertTrue(self.client.get_cookie('chatflow_session').value.startswith('enc1.'))
        self.client.post('/logout')
        self.assertEqual(self.client.get('/admin').location,'/login')

    def test_backup_excludes_login_key_and_browser_storage(self):
        self.login()
        name=server._create_backup_archive()
        import zipfile
        with zipfile.ZipFile(Path(server.BACKUP_DIR,name)) as z:
            self.assertFalse(any('secret.key' in x or 'webview' in x or 'remembered_login' in x for x in z.namelist()))

if __name__ == '__main__':
    unittest.main()
