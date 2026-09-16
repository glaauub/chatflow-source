"""Encrypted local login cookies, compatible with previously signed sessions."""
import base64
import hashlib
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadSignature


class EncryptedSerializer:
    def __init__(self, signed, secret):
        self.signed = signed
        key = hashlib.sha256(('chatflow-login-v1:' + str(secret)).encode()).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key))

    def dumps(self, value):
        return 'enc1.' + self.cipher.encrypt(self.signed.dumps(value).encode()).decode()

    def loads(self, value, max_age=None):
        if not value.startswith('enc1.'):
            raise BadSignature('Not an encrypted login cookie')
        try:
            signed = self.cipher.decrypt(value[5:].encode(), ttl=max_age).decode()
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise BadSignature('Invalid encrypted login cookie') from exc
        return self.signed.loads(signed, max_age=max_age)


class EncryptedSessionInterface(SecureCookieSessionInterface):
    def get_signing_serializer(self, app):
        signed = super().get_signing_serializer(app)
        return EncryptedSerializer(signed, app.secret_key) if signed else None

    def open_session(self, app, request):
        # New cookies have their own name so unrelated localhost apps cannot
        # overwrite the login. Import only a valid, old ChatFLOW login once.
        if request.cookies.get(self.get_cookie_name(app)):
            return super().open_session(app, request)
        old = request.cookies.get('session')
        if old:
            signed = super().get_signing_serializer(app)
            try:
                data = signed.loads(old, max_age=int(app.permanent_session_lifetime.total_seconds()))
                if data.get('github_user') and data.get('github_token'):
                    result = self.session_class(data)
                    result.permanent = True
                    result.modified = True
                    return result
            except BadSignature:
                pass
        return self.session_class()

    def save_session(self, app, session, response):
        super().save_session(app, session, response)
        # Remove the legacy signed-only cookie after migration or logout. The
        # new encrypted cookie is the only credential-bearing browser value.
        from flask import request
        if request.cookies.get('session'):
            response.delete_cookie('session', path='/', httponly=True, samesite='Lax')


class RememberedLogin:
    """App-owned encrypted login; independent of WebView's cache lifecycle."""
    def __init__(self, data_dir, secret):
        self.path = Path(data_dir, 'instance', 'remembered_login.enc')
        key=hashlib.sha256(('chatflow-saved-login-v1:' + str(secret)).encode()).digest()
        self.cipher=Fernet(base64.urlsafe_b64encode(key))
        self.ticket=None

    def save(self, username, token):
        value=self.cipher.encrypt(json.dumps({'username':username,'token':token}).encode())
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='.login-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(value);f.flush();os.fsync(f.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)

    def load(self):
        try:
            record=json.loads(self.cipher.decrypt(self.path.read_bytes()))
            if all(isinstance(record.get(k),str) and record[k] for k in ('username','token')):
                return record
        except (OSError,InvalidToken,ValueError,TypeError):
            pass
        return None

    def clear(self):
        self.path.unlink(missing_ok=True)
        self.ticket=None

    def launch_url(self, base):
        if not self.load():return base
        nonce=secrets.token_urlsafe(32)
        self.ticket=(nonce,time.monotonic()+90)
        return base+'/resume-login?ticket='+nonce

    def consume(self, nonce):
        value=self.ticket
        if not value or time.monotonic()>value[1] or not secrets.compare_digest(value[0],nonce):return None
        self.ticket=None
        return self.load()
