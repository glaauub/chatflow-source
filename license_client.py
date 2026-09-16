# -*- coding: utf-8 -*-
"""ChatFLOW 授权模块（一码一机，永久买断）

规则：
- 每个激活码首次激活时绑定当前电脑的机器指纹，之后只能在绑定的电脑上使用
- 客户换电脑：卖家在后台作废旧码并解绑/发新码，旧电脑下次联网校验失败自动锁死
- 联网校验：软件启动时校验一次（本地缓存 24 小时内不重复请求）
- 断网宽限：断网时若 7 天内校验成功过，允许继续使用（避免客户断网被误锁）

本模块只负责客户端逻辑；服务端为 uniCloud 云函数（见 license-server/ 目录）。
"""
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid

from runtime_paths import data_path, is_frozen, bundle_path

# ---------------- 配置 ----------------
# 授权服务器地址（uniCloud 云对象 URL 化之后的地址）
# 可被环境变量 CHATFLOW_LICENSE_URL 或 数据目录下 license_server.txt 覆盖
DEFAULT_LICENSE_SERVER = 'https://env-00jy6t9r6yik.dev-hz.cloudbasefunction.cn/license'
VERIFY_INTERVAL = 24 * 3600        # 联网校验间隔：24 小时
OFFLINE_GRACE = 2 * 3600           # 断网/作废宽限期：2 小时（到期前提示用户备份）

LICENSE_FILE = data_path('instance', 'license.json')


# ---------------- 机器指纹 ----------------

def _read_cmd_output(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (out.stdout or '').strip()
    except Exception:
        return ''


def _hardware_uuid():
    """取跨平台稳定的硬件标识，取不到返回空串"""
    sy = sys.platform
    if sy == 'darwin':
        out = _read_cmd_output(['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'])
        m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
        return m.group(1) if m else ''
    if sy == 'win32':
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r'SOFTWARE\Microsoft\Cryptography')
            val, _ = winreg.QueryValueEx(k, 'MachineGuid')
            return str(val)
        except Exception:
            return ''
    for p in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            continue
    return ''


def machine_id():
    """机器指纹：硬件标识 + 系统信息 的 SHA256，取不到硬件标识时兜底用 MAC 地址"""
    raw = _hardware_uuid()
    if not raw:
        raw = str(uuid.getnode())
    raw = '|%s|%s|%s' % (raw, platform.system(), platform.machine())
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32].upper()


def machine_code_display():
    """给人看的机器码（后台激活失败时，老板可凭这个手动绑定）"""
    mid = machine_id()
    return '-'.join(mid[i:i + 8] for i in range(0, len(mid), 8))


# ---------------- 授权服务器地址 ----------------

def license_server_url():
    url = os.environ.get('CHATFLOW_LICENSE_URL', '').strip()
    if url:
        return url.rstrip('/')
    # 运行时数据目录（客户机可写，优先）
    try:
        with open(data_path('instance', 'license_server.txt'), 'r', encoding='utf-8') as f:
            url = f.read().strip()
            if url:
                return url.rstrip('/')
    except Exception:
        pass
    # 打包内置的只读副本（PyInstaller _MEIPASS）
    try:
        with open(bundle_path('instance', 'license_server.txt'), 'r', encoding='utf-8') as f:
            url = f.read().strip()
            if url:
                return url.rstrip('/')
    except Exception:
        pass
    return DEFAULT_LICENSE_SERVER


# ---------------- 本地授权状态 ----------------

def _load_state():
    try:
        with open(LICENSE_FILE, 'r', encoding='utf-8') as f:
            st = json.load(f)
        if isinstance(st, dict):
            return st
    except Exception:
        pass
    return {}


def _save_state(st):
    os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
    with open(LICENSE_FILE, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def clear_state():
    """锁死/清除本地授权缓存"""
    try:
        os.remove(LICENSE_FILE)
    except Exception:
        pass


def is_activated():
    """本地快速判断：有缓存的激活记录即视为已激活（真伪由联网校验兜底）"""
    st = _load_state()
    return bool(st.get('code')) and st.get('status') == 'active'


def _server_post(path, payload, timeout=15):
    """调用授权服务器（绕过系统代理，直连云函数）"""
    import urllib.request
    import urllib.error
    url = license_server_url() + path
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    # Frozen Python cannot rely on the build machine's certificate paths.
    import ssl
    import certifi
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context))
    with opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', 'ignore'))


# ---------------- 对外动作 ----------------

def activate(code):
    """用激活码激活当前电脑。返回 (ok, msg)"""
    code = (code or '').strip().upper()
    if not code:
        return False, '请输入激活码'
    mid = machine_id()
    try:
        resp = _server_post('/activate', {'code': code, 'machine_id': mid})
    except Exception as e:
        return False, '联系不上激活服务器，请检查网络后重试（%s）' % str(e)[:80]
    if resp.get('ok'):
        _save_state({'code': code, 'status': 'active', 'machine_id': mid,
                     'activated_at': int(time.time()), 'last_verify': int(time.time())})
        return True, '激活成功'
    return False, resp.get('msg') or '激活失败，请核对激活码'


def license_server_configured():
    """是否配置了真实授权服务器（环境变量或 license_server.txt）。
    都没配 → 视为开发模式，不校验授权（DEFAULT 地址只是占位符）。"""
    if os.environ.get('CHATFLOW_LICENSE_URL', '').strip():
        return True
    try:
        with open(data_path('instance', 'license_server.txt'), 'r', encoding='utf-8') as f:
            return bool(f.read().strip())
    except Exception:
        return False


def _fmt_grace(rem, revoked):
    """把剩余秒数格式化成宽限警告文案。强调：到期只需重输授权码，数据不会丢失。"""
    rem = max(0, int(rem))
    hrs = rem // 3600
    mins = (rem % 3600) // 60
    if revoked:
        return '⚠️ 授权已被收回，本机将在约 %d小时%d分后停止使用，请重新输入新授权码继续使用（你的数据不会丢失）' % (hrs, mins)
    return '⚠️ 授权即将到期（约 %d小时%d分后），到期后重新输入授权码即可继续使用，数据都会保留。' % (hrs, mins)


def grace_warning():
    """只读计算当前授权宽限警告，供前端轮询展示。返回 (msg_or_None, remaining_seconds)。"""
    st = _load_state()
    now = int(time.time())
    rgu = st.get('revoke_grace_until')
    if rgu:
        rem = rgu - now
        if rem > 0:
            return _fmt_grace(rem, True), rem
        return None, 0
    off = st.get('offline_since')
    if off:
        rem = OFFLINE_GRACE - (now - off)
        if rem > 0:
            return _fmt_grace(rem, False), rem
    return None, 0


def _offline_grace(st, now):
    """断网 / 授权服务器异常时的 2 小时宽限：期间放行并提示备份，超时才锁死。"""
    off = st.get('offline_since') or now
    st['offline_since'] = off
    _save_state(st)
    rem = OFFLINE_GRACE - (now - off)
    if rem > 0:
        return True, _fmt_grace(rem, False)
    clear_state()
    return False, '已超过 2 小时没有联网验证，授权已到期。请重新输入新的授权码激活即可继续使用，数据不会丢失。'


def check_license():
    """判断当前电脑是否允许使用软件。

    返回 (allowed, msg)：
    - allowed=True  继续启动（msg 可能携带宽限警告，供前端提示）
    - allowed=False 显示激活页（未激活 / 宽限已耗尽锁死）

    重要：任何意外异常（网络/服务器返回异常格式等）都兜底为「离线宽限/临时放行」，
    绝不允许抛出未捕获异常导致页面 500。
    """
    try:
        if os.environ.get('CHATFLOW_SKIP_LICENSE') == '1':
            return True, '开发模式'
        # 源码运行（没打包、没配授权服务器）= 开发模式，不校验，老板自己用不被锁
        if not is_frozen() and not license_server_configured():
            return True, '源码开发模式'
        st = _load_state()
        code = st.get('code')
        if not code:
            return False, '软件未激活，请输入激活码'

        now = int(time.time())

        # 已被服务端作废，但给予 2 小时宽限（让用户有时间备份数据）后再锁死
        rgu = st.get('revoke_grace_until')
        if rgu:
            if now < rgu:
                return True, _fmt_grace(rgu - now, True)
            clear_state()
            return False, '该授权码已失效，本机已停止使用。请重新输入新的授权码激活即可继续使用，你的数据不会丢失。'

        # 本地缓存显示已锁死
        if st.get('status') == 'revoked':
            clear_state()
            return False, '该授权码已失效，本机已停止使用。请重新输入新的授权码激活即可继续使用，你的数据不会丢失。'

        last = int(st.get('last_verify') or 0)
        if now - last < VERIFY_INTERVAL:
            # 正常窗口内：清掉离线标记，避免误判
            if st.get('offline_since'):
                st.pop('offline_since', None)
                _save_state(st)
            return True, ''

        # 需要联网校验
        try:
            resp = _server_post('/verify', {'code': code, 'machine_id': st.get('machine_id') or machine_id()})
        except Exception:
            # 断网：从“首次检测到离线”起算 2 小时宽限，期间提示备份
            return _offline_grace(st, now)
        # 授权服务器返回了非字典（异常格式/错误页），按断网宽限处理，避免 resp.get 崩
        if not isinstance(resp, dict):
            return _offline_grace(st, now)
        if resp.get('ok'):
            st['last_verify'] = now
            st['status'] = 'active'
            st.pop('offline_since', None)
            _save_state(st)
            return True, ''
        # 服务端明确拒绝（码被作废 / 换机未换码）：给予 2 小时宽限再锁死
        st['revoke_grace_until'] = now + OFFLINE_GRACE
        st['status'] = 'revoked_pending'
        _save_state(st)
        return True, _fmt_grace(OFFLINE_GRACE, True)
    except Exception as e:
        # 兜底：任何意外都不应让软件 500 / 锁死；临时放行并在下次启动时留痕
        return True, '授权校验异常，已临时放行（%s）' % e
