# -*- coding: utf-8 -*-
"""外贸一键建站工具 - Flask 主程序
功能：登录、Banner/联系方式/产品管理、实时预览、生成外贸网站、推送到 GitHub Pages
"""
import csv
import html
import io
import json
import os
import sys
import traceback

# 全局崩溃日志：打包后在 Windows/Mac 上若闪退，把未捕获异常写入
# %LOCALAPPDATA%\ChatFLOW\crash.log（Mac 为 ~/Library/Application Support/ChatFLOW/crash.log），便于定位
def _install_crash_logger():
    try:
        from runtime_paths import DATA_DIR
        _dir = DATA_DIR
        os.makedirs(_dir, exist_ok=True)
        _log = os.path.join(_dir, 'crash.log')

        def _hook(exc_type, exc_val, exc_tb):
            try:
                import datetime as _dt
                _tb = ''.join(traceback.format_exception(exc_type, exc_val, exc_tb))
                with open(_log, 'a', encoding='utf-8') as f:
                    f.write('\n=== %s ===\n' % _dt.datetime.now().isoformat())
                    f.write(_tb)
                # Windows 下弹窗提示，避免“黑框一闪没了”看不到报错
                try:
                    import os as _os2
                    if _os2.name == 'nt':
                        import ctypes
                        _msg = ('ChatFLOW 启动出错（完整记录见 crash.log）：\n\n'
                                + _tb[-1500:])
                        ctypes.windll.user32.MessageBoxW(0, _msg, 'ChatFLOW 错误', 0x10)
                except Exception:
                    pass
            except Exception:
                pass

        sys.excepthook = _hook
    except Exception:
        pass

_install_crash_logger()
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import threading
import uuid
import webbrowser
import zipfile
from datetime import datetime
from functools import wraps
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import urllib.request
import urllib.error
import ssl

# 统一 HTTPS 证书上下文：PyInstaller 冻结后的程序在 macOS/Windows 上
# 往往找不到系统 CA 证书，导致访问 api.github.com 报
# CERTIFICATE_VERIFY_FAILED。这里优先用 certifi 的 CA 包，并叠加系统证书，
# 所有对外 HTTPS 请求都传 context=_SSL_CTX，彻底规避该问题。
try:
    import certifi
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.load_verify_locations(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()
import time

from flask import (Flask, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)

from models import (get_db, init_db, get_config, set_config, get_all_config,
                    DB_PATH, PAGE_ABOUT_HTML, PAGE_FAQ_HTML,
                    normalize_domain, get_domain_binding, bind_domain_to_repo)
from site_themes import TEMPLATES, get_template, build_css
from runtime_paths import BUNDLE_DIR, DATA_DIR, ensure_data_dirs
import license_client

# 当前客户端版本号（与 chatflow.spec 的 CFBundleShortVersionString 保持一致）
APP_VERSION = '2.1.8'

# 源码运行=源码目录；打包运行=可写数据目录（上传图片/生成站点随数据目录走）
BASE_DIR = DATA_DIR
UPLOAD_DIR = os.path.join(DATA_DIR, 'static', 'uploads')
OUTPUT_DIR = os.path.join(DATA_DIR, 'output_site')
ALLOWED_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
CONTACT_TYPES = ('WhatsApp', '微信', '电话', 'QQ', 'Email', 'Telegram', 'Skype', 'LINE',
                 'Facebook', 'Instagram', 'YouTube', 'TikTok', 'LinkedIn', 'Website',
                 'Address', 'AliTrade', 'Trademanager')
CONTACT_ICONS = {'WhatsApp': '📱', '微信': '💬', '电话': '📞', 'QQ': '🐧',
                 'Email': '✉️', 'Telegram': '✈️', 'Skype': '💠', 'LINE': '💬',
                 'Facebook': '📘', 'Instagram': '📷', 'YouTube': '▶️', 'TikTok': '🎵',
                 'LinkedIn': '💼', 'Website': '🌐', 'Address': '📍', 'AliTrade': '🛒',
                 'Trademanager': '🤝'}

app = Flask(__name__,
            static_folder=os.path.join(BUNDLE_DIR, 'static'),
            template_folder=os.path.join(BUNDLE_DIR, 'templates'))


def _load_secret():
    """持久化 session 密钥，服务重启后登录状态仍有效"""
    secret_file = os.path.join(BASE_DIR, 'instance', 'secret.key')
    os.makedirs(os.path.dirname(secret_file), exist_ok=True)
    if os.path.exists(secret_file):
        if os.name != 'nt':
            os.chmod(secret_file, 0o600)
        with open(secret_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    key = uuid.uuid4().hex
    with os.fdopen(os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as f:
        f.write(key)
    return key


app.secret_key = _load_secret()
from login_session import EncryptedSessionInterface, RememberedLogin
app.session_interface = EncryptedSessionInterface()
remembered_login = RememberedLogin(DATA_DIR, app.secret_key)
app.config.update(SESSION_COOKIE_NAME='chatflow_session', SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax', SESSION_REFRESH_EACH_REQUEST=False)
app.config['MAX_CONTENT_LENGTH'] = 60 * 1024 * 1024  # 单次上传上限 60MB（覆盖表格 10MB + 图片另计 / zip ≤50MB 的批量导入场景）
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365 * 10)       # 登录有效期 10 年（基本永久）

os.makedirs(UPLOAD_DIR, exist_ok=True)
ensure_data_dirs()
init_db()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('github_user'):
            if request.path.startswith('/api/'):
                return jsonify({'error': '登录已失效，请重新登录；未保存内容请先复制留存。'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


_write_lock = threading.RLock()

@app.before_request
def _serialize_writes():
    if request.method in ('POST', 'PUT', 'DELETE'):
        from flask import g
        _write_lock.acquire()
        g.cf_write_locked = True

@app.teardown_request
def _release_write_lock(error=None):
    from flask import g
    if getattr(g, 'cf_write_locked', False):
        g.cf_write_locked = False
        _write_lock.release()


@app.before_request
def _license_gate():
    """授权拦截：未激活的电脑只能看到激活页（先激活，再登录使用）。
    静态资源与激活接口放行；其余页面跳激活页、其余接口返回 403。"""
    p = request.path
    if p.startswith('/static') or p.startswith('/uploads'):
        return None
    if p in ('/activate', '/api/activate', '/api/check_update', '/api/health'):
        return None
    allowed, _msg = license_client.check_license()
    if allowed:
        return None
    if p.startswith('/api/'):
        return jsonify({'error': '软件未激活或授权已失效，请先激活后再使用'}), 403
    return redirect(url_for('activate_page'))


@app.errorhandler(500)
def _handle_500(e):
    """兜底：任何请求处理中的未捕获异常都写详细堆栈到 error.log，并在页面显示，避免裸 500。"""
    import datetime as _dt
    import traceback as _tb
    _detail = _tb.format_exc()
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, 'error.log'), 'a', encoding='utf-8') as f:
            f.write('\n=== %s (500) ===\n' % _dt.datetime.now().isoformat())
            f.write(_detail)
    except Exception:
        pass
    return ('ChatFLOW 运行出错（完整堆栈已写入 %s/error.log）：\n\n%s'
            % (DATA_DIR, _detail[-4000:])), 500, {'Content-Type': 'text/plain; charset=utf-8'}


# ---------------- 激活 ----------------

@app.route('/activate')
def activate_page():
    return render_template('activate.html', machine_code=license_client.machine_code_display())


@app.route('/api/activate', methods=['POST'])
def api_activate():
    data = request.get_json(silent=True) or {}
    ok, msg = license_client.activate(data.get('code') or '')
    return jsonify({'ok': ok, 'msg': msg})


@app.route('/api/license_status')
def api_license_status():
    warn, rem = license_client.grace_warning()
    return jsonify({'activated': license_client.is_activated(),
                    'machine_code': license_client.machine_code_display(),
                    'grace_warning': warn,
                    'grace_remaining_seconds': rem})


@app.route('/api/check_update')
def api_check_update():
    """返回当前版本与最新版本（数据来自国内授权服务器，无需翻墙），前端据此弹出更新提示。"""
    latest = _get_latest_version()
    if not latest or not latest.get('tag'):
        return jsonify({'current': APP_VERSION, 'latest': APP_VERSION,
                        'update_available': False, 'url': '', 'note': ''})
    available = _semver_tuple(latest['tag']) > _semver_tuple(APP_VERSION)
    return jsonify({'current': APP_VERSION,
                    'latest': latest['tag'],
                    'update_available': available,
                    'url': latest['url'] if available else '',
                    'note': (latest.get('note') or '') if available else ''})


def _semver_tuple(v):
    """把版本号字符串转成可比较的 (major, minor, patch) 三元组。"""
    v = str(v or '').lstrip('vV')
    nums = []
    for part in v.replace('-', '.').split('.'):
        try:
            nums.append(int(part))
        except ValueError:
            break
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def _get_latest_version():
    """从国内授权服务器（uniCloud，无需翻墙）取最新版本。返回 {'tag','url'} 或 None。"""
    try:
        resp = license_client._server_post('/version', {}, timeout=10)
        if isinstance(resp, dict) and resp.get('version'):
            return {'tag': resp['version'], 'url': resp.get('url', '')}
    except Exception:
        return None
    return None


# ---------------- 新手引导（3 步快速开始） ----------------

@app.route('/api/onboarding/status')
@login_required
def onboarding_status():
    """首次打开（还没有任何内容且没做过引导）时，后台弹出 3 步引导"""
    conn = get_db()
    counts = {
        'products': conn.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c'],
        'banner': conn.execute('SELECT COUNT(*) AS c FROM banner').fetchone()['c'],
        'contacts': conn.execute('SELECT COUNT(*) AS c FROM contacts').fetchone()['c'],
    }
    conn.close()
    done = get_config('onboarding_done', '') == '1'
    show = (not done) and all(v == 0 for v in counts.values())
    return jsonify({'show': show, 'done': done})


@app.route('/api/onboarding/done', methods=['POST'])
@login_required
def onboarding_done():
    set_config('onboarding_done', '1')
    return jsonify({'ok': True})


@app.route('/api/onboarding/reset', methods=['POST'])
@login_required
def onboarding_reset():
    """清空演示数据：把产品/横幅/联系方式等客户数据全部清掉，从零开始录入自己的内容"""
    conn = get_db()
    for t in ('products', 'banner', 'contacts', 'inquiries', 'pages',
              'categories', 'friend_links'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit()
    conn.close()
    set_config('onboarding_done', '')
    return jsonify({'ok': True})


# ---------------- 内置「原始模板」：状态 / 加载示例 / 一键清空 ----------------
@app.route('/api/starter/status')
@login_required
def starter_status():
    import starter_preset
    return jsonify({'starter_loaded': starter_preset.is_starter_loaded(),
                    'preset_version': starter_preset.PRESET_VERSION})


@app.route('/api/starter/load', methods=['POST'])
@login_required
def starter_load():
    """加载内置示例模板（覆盖式）：填充全部示例内容，客户在此基础上修改即可。"""
    import starter_preset
    starter_preset.load_starter_preset()
    # 内容已更新，立即重新生成静态站，让前台预览/访问立刻反映新内容
    try:
        generate_site_files(get_config('site_name', 'My Export Site'), get_config('site_template', 'modern'))
    except Exception:
        pass
    return jsonify({'ok': True})


@app.route('/api/starter/clear', methods=['POST'])
@login_required
def starter_clear():
    """一键清空示例内容：保留 9 大板块框架骨架与模板/语言设置，清空所有填写的内容（含公司名）。"""
    import starter_preset
    starter_preset.clear_site_content()
    # 清空后重新生成静态站，让前台立即显示为空白框架（公司名等不再残留）
    try:
        generate_site_files(get_config('site_name', 'My Export Site'), get_config('site_template', 'modern'))
    except Exception:
        pass
    return jsonify({'ok': True})


def cors_allow_any(f):
    """允许跨域（部署站静态页面向主系统 POST 询盘）"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == 'OPTIONS':
            resp = app.make_default_options_response()
        else:
            resp = f(*args, **kwargs)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp
    return wrapper


# ---------------- 页面路由 ----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = (request.form.get('username') or '').strip()
        token = (request.form.get('token') or '').strip()
        if not user or not token:
            return render_template('login.html', error='用户名和 Token 不能为空')
        ok, err = _validate_github_creds(user, token)
        if not ok:
            return render_template('login.html', error=err)
        remember = request.form.get('remember') == '1'
        try:
            if remember:
                remembered_login.save(user, token)
            else:
                remembered_login.clear()
        except OSError:
            return render_template('login.html', error='登录资料未能保存，请检查本机数据文件夹是否可写后重试。'), 500
        session.clear()
        session['github_user'] = user
        session['github_token'] = token
        session.permanent = remember
        return redirect(url_for('admin'))
    if session.get('github_user'):
        return redirect(url_for('admin'))
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    remembered_login.clear()
    session.clear()
    return redirect(url_for('login'))


@app.route('/resume-login')
def resume_login():
    # Only the process that launches the window knows this short-lived,
    # single-use ticket. An arbitrary localhost request cannot auto-login.
    record = remembered_login.consume(request.args.get('ticket',''))
    if not record:
        return redirect(url_for('login'))
    session.clear()
    session['github_user']=record['username']
    session['github_token']=record['token']
    session.permanent=True
    return redirect(url_for('admin'))


@app.route('/')
def index():
    return redirect(url_for('admin') if session.get('github_user') else url_for('login'))


@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html', user=session.get('github_user'))


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ---------------- 模板与站点配置 ----------------

@app.route('/api/templates')
@login_required
def templates_list():
    """返回可选模板列表（供后台选择与预览切换）"""
    return jsonify(TEMPLATES)


def _read_pay_methods():
    """读取支付方式列表；仅当从未写入新结构时兼容旧版 4 个固定字段，
    显式保存的空列表 '[]'（用户清空渠道）不再回落旧字段。"""
    raw = get_config('pay_methods_json')
    has_new = raw is not None and str(raw).strip() != ''
    try:
        arr = json.loads(raw) if has_new else []
    except Exception:
        arr = []
    if not isinstance(arr, list):
        arr = []
    cleaned = [{'type': str(x.get('type', '')).strip(), 'value': str(x.get('value', '')).strip(),
                'name': str(x.get('name', '')).strip(), 'icon': str(x.get('icon', '')).strip()}
               for x in arr if isinstance(x, dict) and str(x.get('type', '')).strip()]
    if not cleaned and not has_new:
        # 兼容旧版固定字段（paypal_email / stripe_link / custom_link）
        legacy = [('paypal', get_config('paypal_email')), ('stripe', get_config('stripe_link')),
                  ('custom', get_config('custom_link'))]
        cleaned = [{'type': t, 'value': v, 'name': '', 'icon': ''} for t, v in legacy if v]
    return cleaned


@app.route('/api/config')
@login_required
def site_config_get():
    """读取站点配置：模板选择 + 支付方式 + 公司信息 + SEO"""
    pay = _read_pay_methods()
    return jsonify({
        'site_template': get_config('site_template', 'business'),
        'language': get_config('language', 'en'),
        'site_layout': get_config('site_layout', 'classic'),
        'pay_methods': pay,
        'paypal_email': get_config('paypal_email'),
        'stripe_link': get_config('stripe_link'),
        'custom_link': get_config('custom_link'),
        'custom_label': get_config('custom_label'),
        'company': company_info(),
        'seo': seo_site(),
        'site_logo': get_config('site_logo', ''),
    })


@app.route('/api/config', methods=['POST'])
@login_required
def site_config_save():
    """保存站点配置：模板选择 + 语言 + 支付方式（渠道列表，兼容旧 4 字段）"""
    data = request.get_json(silent=True) or {}
    template = (data.get('site_template') or 'business').strip()
    if template not in {t['id'] for t in TEMPLATES}:
        return jsonify({'error': '模板不存在'}), 400
    set_config('site_template', template)
    lang = (data.get('language') or 'en').strip()
    if lang not in i18n_languages():
        lang = 'en'
    set_config('language', lang)
    layout = (data.get('site_layout') or 'classic').strip()
    if layout not in {d['id'] for d in detail_layouts()}:
        layout = 'classic'
    set_config('site_layout', layout)
    # 支付方式：若提交了 pay_methods 列表（渠道自选填写）则整体更新并同步旧 4 键
    if 'pay_methods' in data:
        pm = data.get('pay_methods') or []
        cleaned, seen = [], set()
        for x in pm if isinstance(pm, list) else []:
            if not isinstance(x, dict):
                continue
            typ = str(x.get('type') or '').strip()[:40]
            val = str(x.get('value') or '').strip()[:300]
            nm = str(x.get('name') or '').strip()[:40]
            ic = str(x.get('icon') or '').strip()[:300]
            if typ == 'other':
                key = 'other:' + nm.lower()
            else:
                key = typ.lower()
                nm = ''
            if not typ or key in seen:
                continue
            seen.add(key)
            cleaned.append({'type': typ, 'value': val, 'name': nm, 'icon': ic})
        set_config('pay_methods_json', json.dumps(cleaned, ensure_ascii=False))
        # 同步旧版固定字段，保证旧端渲染/旧配置兼容
        def val_of(t):
            for it in cleaned:
                if it['type'].lower() == t:
                    return it['value']
            return ''
        set_config('paypal_email', val_of('paypal'))
        set_config('stripe_link', val_of('stripe'))
        set_config('custom_link', val_of('custom'))
        if not cleaned:
            set_config('custom_label', 'Buy Now')
    else:
        # 未携带列表（仅模板/语言保存）：保留旧字段，避免误清空
        if data.get('paypal_email') is not None:
            set_config('paypal_email', (data.get('paypal_email') or '').strip())
        if data.get('stripe_link') is not None:
            set_config('stripe_link', (data.get('stripe_link') or '').strip())
        if data.get('custom_link') is not None:
            set_config('custom_link', (data.get('custom_link') or '').strip())
        if data.get('custom_label') is not None:
            set_config('custom_label', (data.get('custom_label') or '').strip())
    return jsonify({'ok': True, 'site_template': template})


# ---------------- 公司信息 ----------------

@app.route('/api/company', methods=['POST'])
@login_required
def company_save():
    """保存公司信息（名/Logo/简介/地址/电话/邮箱/成立时间/规模/行业/主营产品/页脚版权/备案号）"""
    data = request.get_json(silent=True) or {}
    for k in ('company_name', 'company_logo', 'company_brief', 'company_address',
              'company_phone', 'company_email', 'company_founded', 'company_size',
              'company_industry', 'company_products',
              'footer_copyright', 'footer_icp'):
        set_config(k, (data.get(k) or '').strip())
    return jsonify({'ok': True, 'company': company_info()})


# ---------------- 公司简介：本地模板一键生成（离线，不调用外部 AI） ----------------

BRIEF_TEMPLATES = [
    {'id': 'factory', 'label': 'Factory / Manufacturer 工厂制造型',
     'desc': '强调自有工厂、产能、品质管控、OEM/ODM'},
    {'id': 'trading', 'label': 'Export Trading 贸易公司型',
     'desc': '强调选品采购、供应链、全球客户服务'},
    {'id': 'startup', 'label': 'Startup & Growth 初创成长型',
     'desc': '强调年轻灵活、快速响应、小批量合作'},
]


def _brief_field(fields, key, empty='our company'):
    """模板组合时取值，空值给兜底短语"""
    v = (fields.get(key) or '').strip()
    return v if v else empty


def _fmt_products(raw):
    """把主营产品（逗号/分号/换行分隔）转成自然列表；空则 []"""
    if not raw:
        return []
    parts = re.split(r'[,;，；\n\r]+', raw)
    return [p.strip() for p in parts if p.strip()]


def _extract_year(text):
    """从自由文本中提取 4 位年份（用于日/中/韩等语言的年份句）；无则 None"""
    if not text:
        return None
    m = re.search(r'(\d{4})', str(text))
    return m.group(1) if m else None


def build_company_brief(template_id='factory', lang=None):
    """依据后台已填公司信息与站点所选语言（site_config.language），按模板本地组合一段
    纯目标语言公司简介草稿。数据不足处使用同语言兜底短语，绝不混入英文/其它语言。
    纯本地规则拼接，无任何联网请求 / 外部 AI 调用。"""
    from company_brief_l10n import BRIEF_L10N, normalize_lang, join_list

    cfg = get_all_config()
    lang = normalize_lang(lang or cfg.get('language'))
    l10n = BRIEF_L10N[lang]
    punct = l10n['punct']
    name = _brief_field(cfg, 'company_name', l10n['name_fb'])
    industry = _brief_field(cfg, 'company_industry', l10n['industry_fb'])
    founded = (cfg.get('company_founded') or '').strip()
    size = (cfg.get('company_size') or '').strip()
    address = (cfg.get('company_address') or '').strip()
    year = _extract_year(founded)
    prods = _fmt_products(cfg.get('company_products') or '')
    if not prods:
        # 无主营产品字段时，尝试用 SEO 关键词中的产品词补位（关键词较长时只取前两个分词段）
        kw = (cfg.get('seo_site_keywords') or '').split(',')
        kw = [k.strip() for k in kw if k.strip()]
        prods = kw[:2] if kw else []

    def fmt(key):
        return l10n.get(key, '').format(name=name, industry=industry,
                                        prods=join_list(prods, lang),
                                        year=year or '', founded=founded,
                                        address=address, size=size).strip()

    # 句子内拼接符：中文/日文/韩文不加空格
    ispace = ' ' if lang not in ('zh', 'ja', 'ko') else ''

    # 主段落
    if template_id == 'trading':
        p1 = fmt('trading_p1')
        p2 = fmt('trading_main')
        if prods:
            p2 = p2.rstrip('.。') + ispace + fmt('products_sentence')
        p3 = fmt('trading_p3')
    elif template_id == 'startup':
        p1 = fmt('startup_p1')
        p2 = fmt('startup_main')
        if prods:
            p2 = p2.rstrip('.。') + ispace + fmt('products_sentence')
        p3 = fmt('startup_p3')
    else:  # factory
        p1 = fmt('factory_p1')
        p2 = fmt('factory_products') if prods else fmt('factory_main')
        if year:
            p2 = p2.rstrip('.。') + ispace + fmt('factory_founded')
        p3 = fmt('factory_p3')

    if size:
        p3 = p3.rstrip('.。') + ispace + fmt('size_suffix')

    # 结尾信息段：成立时间/所在地（随语言生成，使用本语言连接符）
    # factory 模板已含成立年份句时不再重复拼接成立时间
    origin = []
    if founded and not (template_id == 'factory' and year):
        founded_show = founded
        if year and lang in ('zh', 'ja', 'ko'):
            unit = {'zh': '年', 'ja': '年', 'ko': '년'}[lang]
            founded_show = year + unit
        origin.append(l10n['origin_since'].format(founded=founded_show, year=year or founded_show))
    if address:
        origin.append(fmt('origin_in'))
    tail = ''
    if origin:
        sep = '，' if lang in ('zh', 'ja') else ', '
        tail = sep.join(origin).rstrip('.。') + punct

    para = [s.strip() for s in (p1, p2, p3) if s.strip()]
    brief = '\n\n'.join(para)
    if tail:
        brief = (brief + '\n\n' + tail) if brief else tail
    return brief.strip()


@app.route('/api/company/brief_templates', methods=['GET'])
@login_required
def company_brief_templates():
    """返回可用的公司简介模板元信息 + 当前公司信息摘要（生成按钮选择模板用）"""
    return jsonify({'templates': BRIEF_TEMPLATES, 'company': company_info()})


@app.route('/api/company/generate_brief', methods=['POST'])
@login_required
def company_generate_brief():
    """本地一键生成公司简介草稿：按用户选择模板组合已填公司字段，不联网不调用外部 AI"""
    data = request.get_json(silent=True) or {}
    template = (data.get('template') or 'factory').strip()
    valid = {t['id'] for t in BRIEF_TEMPLATES}
    if template not in valid:
        return jsonify({'error': '模板不存在'}), 400
    try:
        brief = build_company_brief(template)
    except Exception:
        brief = ''
    if not brief:
        return jsonify({'error': '生成失败：缺少可用的公司信息，请先填写公司名称/行业等字段'}), 400
    return jsonify({'ok': True, 'template': template, 'brief': brief})


@app.route('/api/company/logo', methods=['POST'])
@login_required
def company_logo_upload():
    """公司 Logo 上传：直接上传图片文件，成功后回填 company_logo 路径"""
    file = request.files.get('logo') or request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': '未选择文件'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'error': '仅支持图片格式: png / jpg / jpeg / gif / webp'}), 400
    filename = uuid.uuid4().hex + ext
    file.save(os.path.join(UPLOAD_DIR, filename))
    old = get_config('company_logo', '')
    if old:
        old_path = os.path.join(UPLOAD_DIR, os.path.basename(old))
        if os.path.exists(old_path):
            os.remove(old_path)
    set_config('company_logo', '/uploads/' + filename)
    return jsonify({'ok': True, 'path': '/uploads/' + filename})


# ---------------- SEO / GEO ----------------

@app.route('/api/seo', methods=['POST'])
@login_required
def seo_save():
    """保存 SEO/GEO 设置（站点级）"""
    data = request.get_json(silent=True) or {}
    from visibility import valid_site_url
    entered_url = (data.get('site_url') or '').strip()
    if entered_url and not valid_site_url(entered_url):
        return jsonify({'error': '正式网址请填完整的 https:// 地址，不要带问号、井号或账号密码。'}), 400
    for k in ('seo_site_title', 'seo_site_description', 'seo_site_keywords',
              'seo_author', 'seo_robots', 'seo_hidden_keywords',
              'site_url'):
        set_config(k, (data.get(k) or '').strip())
    # AI GEO：多行卖点保留换行（供 llms.txt / JSON-LD 逐条输出）
    set_config('geo_brand_summary', (data.get('geo_brand_summary') or '').strip())
    set_config('geo_selling_points', (data.get('geo_selling_points') or '').strip('\r\n'))
    # P2 AI GEO 精致化：目标市场 / 认证 / 服务能力（多行文本）与 FAQ（JSON 数组）保存
    for _k in ('geo_target_markets', 'geo_certifications', 'geo_service_capabilities'):
        if _k in data:
            _v = data.get(_k)
            if isinstance(_v, list):
                _v = '\n'.join(str(x).strip() for x in _v if str(x).strip())
            set_config(_k, (str(_v) if _v is not None else '').strip('\r\n'))
    if 'geo_faq' in data:
        set_config('geo_faq', json.dumps(_clean_geo_faq(data.get('geo_faq')), ensure_ascii=False))
    # AI 展示开关（checkbox 未勾选时前端可能不上传该字段，需显式保存 0/1）
    if 'geo_ai_enabled' in data:
        set_config('geo_ai_enabled', '1' if data.get('geo_ai_enabled') in (1, '1', True, 'true', 'on') else '0')
    if 'geo_training_enabled' in data:
        set_config('geo_training_enabled', '1' if data['geo_training_enabled'] in (True, 1, '1') else '0')
    # 第三方统计代码（GA4 / 百度统计等 script 片段，注入所有页面 <head>）
    set_config('analytics_code', (data.get('analytics_code') or '').strip())
    # Cookie 同意横幅开关（0 关闭，默认开启）
    if 'cookie_enabled' in data:
        set_config('cookie_enabled', '1' if data.get('cookie_enabled') in (1, '1', True, 'true', 'on') else '0')
    # 兼容旧字段：仅当未启用 AI GEO 时保留地图式地址配置，避免误导（前台已不再输出地图式 meta）
    for k in ('geo_address', 'geo_region'):
        set_config(k, (data.get(k) or '').strip())
    return jsonify({'ok': True, 'seo': seo_site()})


@app.route('/api/visibility/audit', methods=['GET', 'POST'])
@login_required
def visibility_audit():
    from visibility import audit_output
    if request.method == 'POST':
        generate_site_files(get_config('site_name', 'My Export Site'), get_config('site_template', 'business'))
    return jsonify(audit_output(OUTPUT_DIR, get_config('site_url', '')))


@app.route('/api/visibility/product_drafts', methods=['GET', 'POST'])
@login_required
def product_search_drafts():
    from visibility import plain_text
    conn = get_db()
    rows = conn.execute('SELECT id, name, spec, description, meta_title, meta_description FROM products ORDER BY id').fetchall()
    drafts = []
    brand = get_config('company_name', '')
    for row in rows:
        title = row['name'] + (' - ' + brand if brand else '')
        desc = plain_text(' '.join(str(row[k] or '') for k in ('name', 'spec', 'description')))[:180]
        fields = {}
        if not (row['meta_title'] or '').strip(): fields['meta_title'] = title[:100]
        if not (row['meta_description'] or '').strip(): fields['meta_description'] = desc
        if fields: drafts.append({'id': row['id'], 'name': row['name'], 'fields': fields})
    if request.method == 'POST':
        # Only fill empty fields, rechecked inside the same transaction.
        for item in drafts:
            for key, value in item['fields'].items():
                conn.execute("UPDATE products SET %s=? WHERE id=? AND TRIM(COALESCE(%s,''))=''" % (key, key), (value,item['id']))
        conn.commit()
    conn.close()
    return jsonify({'items': drafts, 'count': len(drafts), 'notice': '根据已有产品资料整理，不调用 AI、不查搜索量、不覆盖已填写内容。请检查后再发布。'})


@app.route('/api/visibility/robots')
@login_required
def download_robots():
    from site_builder import _build_robots
    from flask import Response
    return Response(_build_robots(), mimetype='text/plain', headers={'Content-Disposition':'attachment; filename=robots.txt'})


@app.route('/api/visibility/experiments', methods=['GET', 'POST'])
@login_required
def visibility_experiments():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        set_config('seo_experiments_enabled', '1' if data.get('enabled') is True else '0')
    return jsonify({'enabled': get_config('seo_experiments_enabled', '0') == '1'})


@app.route('/api/visibility/settings', methods=['GET', 'POST'])
@login_required
def visibility_settings():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        for key in ('geo_ai_enabled', 'geo_training_enabled'):
            if key in data: set_config(key, '1' if data[key] is True else '0')
    return jsonify({'search': get_config('geo_ai_enabled', '1') == '1',
                    'training': get_config('geo_training_enabled', '0') == '1'})


@app.route('/api/visibility/results', methods=['GET', 'POST'])
@login_required
def visibility_results():
    # User-entered observations with evidence, never fabricated live analytics.
    try: rows = json.loads(get_config('visibility_results', '[]'))
    except ValueError: rows = []
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        day = str(data.get('date') or '')
        try:
            datetime.strptime(day, '%Y-%m-%d')
            nums = {k: int(data.get(k, 0)) for k in ('impressions', 'clicks', 'inquiries')}
            if any(v < 0 or v > 1000000000 for v in nums.values()): raise ValueError()
        except (ValueError, TypeError):
            return jsonify({'error': '请填写日期和大于等于 0 的整数。'}), 400
        row = dict(nums, date=day, source=str(data.get('source') or '')[:500],
                   ai_evidence=str(data.get('ai_evidence') or '')[:1000])
        rows = [x for x in rows if x.get('date') != day] + [row]
        rows = sorted(rows, key=lambda x: x['date'])[-365:]
        set_config('visibility_results', json.dumps(rows, ensure_ascii=False))
    return jsonify(rows)


@app.route('/api/health')
def application_health():
    return jsonify({'app': 'ChatFLOW', 'version': APP_VERSION})


@app.route('/api/seo/sample', methods=['POST'])
@login_required
def seo_sample():
    """P3 行业一键示例：factory / trading / startup 整套 SEO/GEO 示例文案

    只返回示例数据，由前端决定填充策略（只填空字段 + 撤销，B7 硬约束）：
    覆盖范围仅 site_title/site_description/site_keywords/brand_summary/
    selling_points/service_capabilities；
    不覆盖 seo_author/seo_robots/site_url/analytics_code/geo_faq/
    geo_target_markets/geo_certifications（作者与网址私有、市场与 FAQ 需人工、
    认证不可编造，D6）。
    文案语言跟随当前站点语言：geo_l10n 现仅 en/zh 两套，其余语言回退英文（D13）。"""
    from geo_l10n import SEO_SAMPLES
    data = request.get_json(silent=True) or {}
    industry = (data.get('industry') or 'factory').strip()
    if industry not in {t['id'] for t in BRIEF_TEMPLATES}:
        return jsonify({'error': '模板不存在'}), 400
    lang = _geo_lang()
    lang_data = SEO_SAMPLES.get(lang) or SEO_SAMPLES['en']
    sample = lang_data.get(industry) or {}
    return jsonify({'ok': True, 'industry': industry, 'lang': lang, 'sample': sample})


_AUDIT_LABELS = {
    'title': '标题长度合适',
    'desc': '描述长度合适',
    'keywords': '已填写站点关键词',
    'brand': 'AI GEO 品牌简介',
    'points': 'AI GEO 卖点列表（3-8 条）',
    'ai_on': 'AI 展示开关已开启',
    'site_url': '已配置正式网址',
    'robots': 'robots 未被禁止索引',
    'product_img': '所有产品都有主图',
    'llms': 'llms.txt 已生成',
    'sitemap': 'sitemap.xml 已生成',
    'meta_geo': '已移除旧版地图式 GEO 标签',
    'prod_seo': '产品级 SEO 标题/描述普及度',
    'prod_desc': '产品描述不缺失（JSON-LD 可读）',
    'cat_empty': '无空壳分类',
}


@app.route('/api/seo/audit')
@login_required
def seo_audit():
    """SEO 自检清单：逐项打勾 + 待补项 + '为什么重要'（小白友好）
    P4：每个检查项附带 action（jump=跳转 / fix=一键修复写库先确认 / open=弹层或触发操作），
    供前端统一渲染「修复」按钮，后端只下发结构与文案，不输出 HTML。"""
    seo = seo_site()
    checks = []

    def add(key, passed, detail='', action=None):
        checks.append({'id': key, 'label': _AUDIT_LABELS.get(key, key),
                       'passed': bool(passed), 'detail': detail, 'why': _AUDIT_WHY.get(key, ''),
                       'action': action})

    def jump(target, label='去填写', payload=None):
        return {'type': 'jump', 'target': target, 'label': label, 'payload': payload or {}}

    title = (seo.get('title') or '').strip()
    desc = (seo.get('description') or '').strip()
    keys = (seo.get('keywords') or '').strip()
    summary = (seo.get('brand_summary') or '').strip()
    points = [x for x in (seo.get('selling_points') or '').replace('\r\n', '\n').replace('\r', '\n').split('\n') if x.strip()]
    robots = (seo.get('robots') or 'index,follow').lower()
    site_url = (seo.get('site_url') or '').strip()
    company_name = ''
    company_industry = ''
    try:
        comp = company_info()
        company_name = (comp.get('name') or '').strip()
        company_industry = (comp.get('industry') or '').strip()
    except Exception:
        pass

    title_ok = 8 <= len(title) <= 80
    desc_ok = 0 < len(desc) <= 300
    if title_ok:
        add('title', True, '当前 %d 字符（建议 30-60，不超过 80）' % len(title))
    elif not title:
        _ind = company_industry or 'Professional'
        _def_title = ('%s Manufacturer & Supplier' % _ind)
        add('title', False, '未填写（建议格式：主营产品 + 身份，如「%s」）' % _def_title,
            action={'type': 'fix', 'target': 'seoSiteTitle', 'label': '一键填充默认标题',
                    'payload': {'write': True, 'fn': 'setFieldValue', 'field': 'seo_site_title',
                                'value': _def_title,
                                'preview': '将把「站点标题」填充为「%s」并保存；仅当该字段为空时执行，不会覆盖你已填写的内容。' % _def_title}})
    else:
        add('title', False, '当前 %d 字符（建议 30-60，不超过 80）' % len(title),
            action=jump('seoSiteTitle', '去修改标题'))
    add('desc', desc_ok, '当前 %d 字符（建议 50-160，让搜索结果完整显示）' % len(desc),
        action=jump('seoSiteDescription', '去填写描述') if not desc_ok else None)
    if keys:
        add('keywords', True, '当前：%s' % keys[:80])
    else:
        add('keywords', False, '未填写，可一键用本地建议生成',
            action={'type': 'fix', 'target': 'seoSiteKeywords', 'label': '一键生成关键词',
                    'payload': {'write': True, 'fn': 'suggestKeywords',
                                'preview': '将用产品/分类/公司名生成 5-8 个关键词填入「站点关键词」，保存后生效（不会覆盖已填字段）'}})
    add('brand', bool(summary), '当前：%s' % (summary[:80] or '未填写'),
        action=jump('geoBrandSummary', '去填写') if not summary else None)
    if 3 <= len(points) <= 8:
        add('points', True, '当前 %d 条' % len(points))
    elif points:
        add('points', False, '当前 %d 条（建议 3-8 条）' % len(points),
            action={'type': 'fix', 'target': 'geoSellingPoints', 'label': '起草卖点',
                    'payload': {'write': False, 'fn': 'geoDraft',
                                'preview': '将基于公司资料生成卖点草稿并只填入空行（不覆盖已填内容），随后可自行保存'}})
    else:
        add('points', False, '未填写',
            action={'type': 'fix', 'target': 'geoSellingPoints', 'label': '起草卖点',
                    'payload': {'write': False, 'fn': 'geoDraft',
                                'preview': '将基于公司资料生成卖点草稿并填入，随后可自行保存'}})
    ai_enabled = str(seo.get('ai_enabled', '1')).strip().lower() in ('1', 'true', 'on', 'yes')
    add('ai_on', ai_enabled, '开启后 AI 搜索引擎可引用站点内容',
        action={'type': 'fix', 'target': 'geoAiEnabled', 'label': '打开开关',
                'payload': {'write': True, 'fn': 'enableAI',
                            'preview': '将把「允许 AI 引用」开关置为开启并保存（不会改动其它设置）'}} if not ai_enabled else None)
    add('site_url', bool(site_url), '用于 canonical / hreflang / sitemap / llms.txt 绝对链接',
        action=jump('seoSiteUrl', '去填写网址') if not site_url else None)
    add('robots', 'noindex' not in robots and 'none' not in robots, '当前：%s' % robots,
        action=jump('seoRobots', '去检查 robots') if ('noindex' in robots or 'none' in robots) else None)
    prods = []
    try:
        conn = get_db()
        rows = conn.execute('SELECT * FROM products ORDER BY id').fetchall()
        conn.close()
        prods = [dict(r) for r in rows]
    except Exception:
        prods = []
    total = len(prods)
    with_img = sum(1 for p in prods if product_images(p))
    no_img = [p for p in prods if not product_images(p)]
    add('product_img', total == 0 or with_img == total,
        '产品 %d 个，%d 个有主图（前台会自动用产品名生成 alt）' % (total, with_img),
        action={'type': 'open', 'target': 'noimg_modal', 'label': '查看无图产品',
                'payload': {'items': [{'id': p['id'], 'name': p['name']} for p in no_img[:200]]}}
        if no_img else None)
    # P4 新增：产品级 SEO 普及度（不设硬失败，仅提示补全，避免吓跑已有站点）
    def _has_meta(p):
        return bool(((p.get('meta_title') or '').strip()) or ((p.get('meta_description') or '').strip()))
    seo_ok = sum(1 for p in prods if _has_meta(p))
    if total and seo_ok < total:
        add('prod_seo', True,
            '已有 %d/%d 个产品填写独立 SEO 标题/描述（不影响上线，建议逐个补全）' % (seo_ok, total),
            action={'type': 'open', 'target': 'noseo_modal', 'label': '查看待优化产品',
                    'payload': {'items': [{'id': p['id'], 'name': p['name']} for p in prods if not _has_meta(p)][:200]}})
    else:
        add('prod_seo', True, '产品数 %d，全部已填写或暂无产品' % total)
    # P4 新增：产品描述缺失率（影响 JSON-LD Product 可读性）
    no_desc = [p for p in prods if not ((p.get('description') or '').strip())]
    add('prod_desc', total == 0 or not no_desc,
        '有 %d 个产品未填写详情描述（会连带影响 JSON-LD 可读性与 SEO 摘要）' % len(no_desc),
        action={'type': 'open', 'target': 'nodesc_modal', 'label': '查看缺描述产品',
                'payload': {'items': [{'id': p['id'], 'name': p['name']} for p in no_desc[:200]]}}
        if no_desc else None)
    # P4 新增：分类空壳（只读提示，不删除）
    empty_cats = []
    try:
        conn = get_db()
        cats = conn.execute('SELECT c.name AS name, (SELECT COUNT(*) FROM products p WHERE p.category=c.name) AS cnt '
                            'FROM categories c ORDER BY c.id').fetchall()
        conn.close()
        empty_cats = [dict(c) for c in cats if (c['cnt'] or 0) == 0]
    except Exception:
        empty_cats = []
    if empty_cats:
        add('cat_empty', False, '存在 %d 个没有产品的空分类（可在「产品分类」中删除）' % len(empty_cats),
            action=jump('category_manager', '去分类管理'))
    else:
        add('cat_empty', True, '无空壳分类')
    has_llms = os.path.exists(os.path.join(OUTPUT_DIR, 'llms.txt'))
    has_sitemap = os.path.exists(os.path.join(OUTPUT_DIR, 'sitemap.xml'))
    add('llms', has_llms, '站点根目录 llms.txt：%s' % ('已生成' if has_llms else '未生成，点击右侧按钮生成'),
        action={'type': 'open', 'target': 'generate', 'label': '去生成网站',
                'payload': {'preview': '将重新生成整站（含 llms.txt / sitemap.xml），会覆盖站点输出目录，是否继续？'}} if not has_llms else None)
    add('sitemap', has_sitemap, '站点根目录 sitemap.xml：%s' % ('已生成' if has_sitemap else '未生成，点击右侧按钮生成'),
        action={'type': 'open', 'target': 'generate', 'label': '去生成网站',
                'payload': {'preview': '将重新生成整站（含 llms.txt / sitemap.xml），会覆盖站点输出目录，是否继续？'}} if not has_sitemap else None)
    add('meta_geo', True, '旧版 geo.position/ICBM 等地图式标签已停用')
    passed_n = sum(1 for c in checks if c['passed'])
    return jsonify({'ok': True, 'passed': passed_n, 'total': len(checks), 'checks': checks})


_AUDIT_WHY = {
    'title': '标题是搜索结果里最大的一行，也是 AI 识别页面主题的第一依据。',
    'desc': '描述会直接出现在搜索引擎摘要里，写清楚才能吸引点击。',
    'keywords': '关键词帮助搜索引擎和 AI 理解你的行业与产品线。',
    'brand': 'AI 搜索（ChatGPT/Gemini 等）引用你时优先使用这句话介绍品牌。',
    'points': '卖点会被 AI 引荐给用户，3-8 条最合适：太少没信息量，太多 AI 记不住。',
    'ai_on': '关闭后 AI 引擎不会被鼓励引用你的内容（默认开启更利于被 AI 推荐）。',
    'site_url': '没有正式网址时无法生成 canonical/hreflang，多语言站点容易被判重复内容。',
    'robots': 'noindex 会告诉搜索引擎不要收录你的页面。',
    'product_img': '产品图带 alt 既利于图片搜索，也让 AI 知道图片对应哪个产品。',
    'llms': 'llms.txt 是可选说明文件，不代表会被 AI 使用，也不是 Google AI 搜索的必要条件。',
    'sitemap': '网站地图帮助搜索引擎发现页面，不保证收录或排名。',
    'meta_geo': '旧版地图式 GEO 标签对 AI 搜索无意义，现已替换为生成式引擎优化体系。',
    'prod_seo': '产品页独立 SEO 标题/描述让每个产品在搜索里展示更精准；没填会自动用默认规则，不影响上线。',
    'prod_desc': '产品描述会进入 JSON-LD Product 结构化数据，AI 与搜索引擎靠它理解产品是什么。',
    'cat_empty': '空分类不影响前台，但会显得后台杂乱，建议清理。',
}


@app.route('/api/seo/suggest_keywords')
@login_required
def suggest_keywords():
    """关键词建议器：根据产品名/分类/公司信息自动生成推荐关键词与长尾词（小白友好）"""
    seo = seo_site()
    comp = company_info()
    brand = ((comp.get('name') or '').strip())
    site_nm = (get_config('site_name', '') or '').strip()
    if not brand:
        brand = site_nm
    lang = get_config('language', 'en') or 'en'
    stop = {'the', 'a', 'an', 'of', 'for', 'and', 'with', 'new', 'best', 'hot', 'top',
            'factory', 'supplier', 'manufacturer', 'wholesale', 'company', 'custom'}
    prods = []
    try:
        conn = get_db()
        rows = conn.execute('SELECT * FROM products ORDER BY id LIMIT 60').fetchall()
        conn.close()
        prods = [dict(r) for r in rows]
    except Exception:
        prods = []
    core = []
    cats = []
    for p in prods:
        nm = (p.get('name') or '').strip()
        if nm and nm.lower() not in core and nm.lower() not in stop:
            core.append(nm)
        ct = (p.get('category') or '').strip()
        if ct and ct.lower() not in cats:
            cats.append(ct)
    for ct in cats[:8]:
        core.append(ct)
    if brand and brand.lower() not in [c.lower() for c in core]:
        core.insert(0, brand)
    # 去重并裁剪
    seen = set()
    core_clean = []
    for w in core:
        k = w.lower()
        if k not in seen:
            seen.add(k)
            core_clean.append(w)
    core = core_clean[:20]
    # 长尾词：修饰词 + 产品词 / 品牌 + 产品词
    mods = ['wholesale', 'factory direct', 'high quality', 'custom', 'OEM', 'supplier', 'buy online']
    long_tail = []
    lseen = set()
    for nm in core_clean[:12]:
        for m in mods[:4]:
            w = '%s %s' % (m, nm)
            if w.lower() not in lseen and len(w) <= 60:
                lseen.add(w.lower())
                long_tail.append(w)
        if brand and brand.lower() not in nm.lower() and len(nm) < 40:
            w = '%s %s' % (nm, brand)
            if w.lower() not in lseen:
                lseen.add(w.lower())
                long_tail.append(w)
    if not core:
        core = ['your product name', 'your industry keyword']
    if not long_tail:
        long_tail = ['wholesale your product', 'factory your product', 'buy your product online']
    return jsonify({'ok': True, 'lang': lang, 'brand': brand,
                    'items': [
                        {'label': '核心关键词（品牌 / 产品 / 分类）', 'words': core},
                        {'label': '推荐长尾词（更精准的搜索词）', 'words': long_tail[:24]},
                    ]})


# ---------------- AI GEO 精致化（P2） ----------------


def _clean_geo_faq(raw):
    """geo_faq 清洗：兼容数组 / JSON 字符串 / [q,a] 二元组，输出 [{q,a}]（q 非空才保留）"""
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return []
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if isinstance(raw, dict):
        raw = [raw]
    items = []
    if isinstance(raw, list):
        for it in raw:
            if isinstance(it, (list, tuple)) and len(it) >= 2:
                it = {'q': it[0], 'a': it[1]}
            if not isinstance(it, dict):
                continue
            q = str(it.get('q') or '').strip()[:300]
            a = str(it.get('a') or '').strip()[:3000]
            if q:
                items.append({'q': q, 'a': a})
    return items[:50]


def _geo_lang():
    """P2 生成文案语言：精确匹配 geo_l10n 现有键（en/zh/zh-Hant）；其余回退英文模板

    与 company_brief_l10n.normalize_lang 的"精确键优先"语义对齐；geo_l10n 已含 zh-Hant
    繁体键，_geo_lang 必须显式包含以免 head 截断误落简体 zh。后续新增语言键时同步扩展
    本元组即可。"""
    lang = (get_config('language', 'en') or 'en').strip().lower()
    if lang == 'zh-hant':
        return 'zh-Hant'
    return lang if lang in ('en', 'zh') else 'en'


def _geo_health():
    """A content checklist, never an AI visibility or ranking prediction."""
    from visibility import plain_text
    seo = seo_site()
    fields = [('brand_summary', '公司介绍', seo.get('brand_summary'), 25, '写清是谁、做什么；填写真实资料。'),
              ('selling_points', '实际优势', seo.get('selling_points'), 20, '写客户能核实的优势，不要只写最好、第一。'),
              ('target_markets', '服务市场', seo.get('target_markets'), 15, '只写实际能服务的地区。'),
              ('service_capabilities', '服务说明', seo.get('service_capabilities'), 20, '写真实交期、起订量、样品和定制条件。'),
              ('faq', '客户常问的问题', seo.get('faq'), 20, '有问题也要有真实答案；没有答案先不要发布。')]
    items = []
    for key, label, value, maximum, hint in fields:
        text = plain_text(str(value or ''))
        passed = bool(value) and not re.search(r'待补充|to be completed', text, re.I)
        if key == 'faq': passed = bool(value) and all(q.strip() and a.strip() for q, a in value)
        items.append({'key': key, 'label': label, 'score': maximum if passed else 0,
                      'max': maximum, 'passed': passed, 'hint': hint})
    score = sum(x['score'] for x in items)
    return {'score': score, 'grade': '资料已填写，仍需核实' if score == 100 else '还有资料需要补充',
            'items': items, 'missing': [x['key'] for x in items if not x['passed']]}


@app.route('/api/geo/health', methods=['POST', 'GET'])
@login_required
def geo_health():
    """AI GEO 健康度评分（只读；P2 §2.2.3）"""
    return jsonify({'ok': True, **(_geo_health())})


@app.route('/api/geo/preview', methods=['POST', 'GET'])
@login_required
def geo_preview():
    """模拟 AI 引用预览（只读）：对话引用版 + 结构化数据（llms.txt/JSON-LD）版

    按当前已保存配置渲染；缺失项输出 <未填：xxx> 占位提示，督促补齐。"""
    from geo_l10n import GEO_DRAFT_TEMPLATES, GEO_SERVICE_PLACEHOLDERS, GEO_MISSING_PLACEHOLDERS
    lang = _geo_lang()
    l10n = GEO_DRAFT_TEMPLATES.get(lang) or GEO_DRAFT_TEMPLATES['en']
    miss = GEO_MISSING_PLACEHOLDERS.get(lang) or GEO_MISSING_PLACEHOLDERS['en']
    seo = seo_site()
    comp = company_info()
    industry = (comp.get('industry') or '').strip()
    products = (comp.get('products') or '').strip()
    brand = (seo.get('brand_summary') or '').strip()
    points = [x.strip() for x in re.split(r'[\r\n]+', (seo.get('selling_points') or '')) if x.strip()]
    mkts = seo.get('target_markets') or []
    certs = seo.get('certifications') or []
    caps = seo.get('service_capabilities') or []
    faq = seo.get('faq') or []
    sep = '，' if lang == 'zh' else ', '
    nf = miss.get('generic', '[待补充]')

    def has(v, k):
        return v[:1] if v else '<未填:%s>' % k

    if lang == 'zh':
        convo = ('Q: 推荐一个靠谱的 %s 供应商？ A: %s。%s%s%s，目标市场覆盖%s。最低起订 %s。'
                 % (has(industry, '行业'), has(brand, 'Brand Summary'),
                    (('核心卖点：' + '；'.join(points[:2])) if points else '核心卖点：' + nf),
                    ('；认证：' + '、'.join(certs[:2])) if certs else '；认证：' + nf,
                    ('；服务：' + '；'.join(caps[:2])) if caps else '；服务：' + nf,
                    ('、'.join(mkts[:3]) if mkts else nf), nf))
    else:
        convo = ('Q: Recommend a reliable %s supplier? A: %s. Selling points: %s; certifications: %s; '
                 'services: %s. Target markets: %s. MOQ: %s.'
                 % (has(industry, 'industry'), has(brand, 'Brand Summary'),
                    '; '.join(points[:2]) if points else nf,
                    ', '.join(certs[:2]) if certs else nf,
                    '; '.join(caps[:2]) if caps else nf,
                    ', '.join(mkts[:3]) if mkts else nf, nf))
    # 结构化数据版（llms.txt 节选 + FAQ 前 3）
    structured = []
    if mkts:
        structured.append('## %s' % ('目标市场' if lang == 'zh' else 'Target Markets'))
        structured.extend('- ' + m for m in mkts)
    if certs:
        structured.append('## %s' % ('认证资质' if lang == 'zh' else 'Certifications'))
        structured.extend('- ' + c for c in certs)
    if caps:
        structured.append('## %s' % ('服务能力' if lang == 'zh' else 'Service Capabilities'))
        structured.extend('- ' + c for c in caps)
    if faq:
        structured.append('## %s' % ('常见问题' if lang == 'zh' else 'FAQ'))
        # faq 兼容 [{q,a}] 与 [(q,a)] 两种结构（seo_site 返回 [q,a] 二元组列表）
        for f in faq[:3]:
            q = f.get('q') if isinstance(f, dict) else (f[0] if f and len(f) else '')
            a = f.get('a') if isinstance(f, dict) else (f[1] if f and len(f) > 1 else '')
            structured.append('- Q: %s' % q)
            if a:
                structured.append('  A: %s' % a)
    if not structured:
        structured = [nf]
    return jsonify({'ok': True, 'lang': lang,
                    'conversation': convo,
                    'structured': '\n'.join(structured),
                    'faq_count': len(faq)})


@app.route('/api/geo/generate_draft', methods=['POST'])
@login_required
def geo_generate_draft():
    """从公司资料一键生成 GEO 草稿（按当前站点语言；缺数据用 [待补充] 占位，不编造）

    只生成 brand_summary / selling_points / service_capabilities / target_markets 四段，
    由前端决定填充策略（只填空字段 / 整体覆盖）；FAQ 需人工业务答案，不自动生成。"""
    from geo_l10n import (GEO_DRAFT_TEMPLATES, GEO_ROLES, GEO_POINT_TEMPLATES,
                          GEO_SERVICE_PLACEHOLDERS, GEO_MISSING_PLACEHOLDERS, GEO_DRAFT_TIPS)
    data = request.get_json(silent=True) or {}
    template = (data.get('template') or 'factory').strip()
    if template not in {t['id'] for t in BRIEF_TEMPLATES}:
        return jsonify({'error': '模板不存在'}), 400
    lang = _geo_lang()
    l10n = GEO_DRAFT_TEMPLATES.get(lang) or GEO_DRAFT_TEMPLATES['en']
    roles = GEO_ROLES.get(lang) or GEO_ROLES['en']
    pts_l10n = GEO_POINT_TEMPLATES.get(lang) or GEO_POINT_TEMPLATES['en']
    ph = GEO_SERVICE_PLACEHOLDERS.get(lang) or GEO_SERVICE_PLACEHOLDERS['en']
    miss = GEO_MISSING_PLACEHOLDERS.get(lang) or GEO_MISSING_PLACEHOLDERS['en']
    tips = list(GEO_DRAFT_TIPS.values()) if lang == 'zh' else []

    cfg = get_all_config()
    fields = {
        'name': (cfg.get('company_name') or '').strip(),
        'industry': (cfg.get('company_industry') or '').strip(),
        'products': (cfg.get('company_products') or '').strip(),
        'brief': (cfg.get('company_brief') or '').strip(),
        'founded': (cfg.get('company_founded') or '').strip(),
        'size': (cfg.get('company_size') or '').strip(),
    }
    industry = fields['industry'] or miss['industry']
    role = roles.get(template, roles.get('factory', 'supplier'))
    brand_summary = l10n['brand_summary'].format(
        industry=industry, role=role,
        founded=fields['founded'] or miss['founded'],
        products=fields['products'] or miss['products'])
    # 卖点候选：仅用真实公司资料字段拼接；缺槽位用 [待补充] 占位，不编造具体数字
    candidate = []
    if fields['brief']:
        brief = fields['brief'][:220]
        candidate.append(brief)
    if fields['name'] or fields['industry']:
        candidate.append(pts_l10n['name_industry'].format(
            name=fields['name'] or (miss['generic'] if lang == 'en' else miss['generic']),
            industry=industry, role=role))
    if fields['founded']:
        candidate.append(pts_l10n['founded'].format(founded=fields['founded']))
    if fields['size']:
        candidate.append(pts_l10n['size'].format(size=fields['size']))
    if fields['products']:
        candidate.append(pts_l10n['products_lead'].format(products=fields['products']))
    elif fields['industry']:
        candidate.append(pts_l10n['industry_lead'].format(industry=fields['industry']))
    seen, points = set(), []
    for c in candidate:
        k = c.strip().lower()
        if c.strip() and k not in seen:
            seen.add(k)
            points.append(c.strip()[:200])
    # 保底：防止卖点全空时前端拿不到可编辑条目
    if not points:
        points.append(miss['generic'])
    points = points[:6]
    # 服务能力：四件套占位模板（交期/MOQ/样品天数用 [占位] 提示用户替换，不猜数字）
    service_capabilities = []
    for line in l10n['service_defaults']:
        service_capabilities.append(line.format(**ph))
    # 目标市场：只给占位，不猜测地区
    target_markets = [l10n['market_placeholder']]
    # 缺失数据提示（后台展示用中文）
    zh_tips = []
    if not fields['industry']:
        zh_tips.append(GEO_DRAFT_TIPS['no_industry'])
    if not fields['products']:
        zh_tips.append(GEO_DRAFT_TIPS['no_products'])
    if not fields['founded']:
        zh_tips.append(GEO_DRAFT_TIPS['no_founded'])
    zh_tips.append(GEO_DRAFT_TIPS['faq_suggest'])
    return jsonify({'ok': True, 'template': template, 'lang': lang,
                    'brand_summary': brand_summary,
                    'selling_points': points,
                    'service_capabilities': service_capabilities,
                    'target_markets': target_markets,
                    'faq_note': GEO_DRAFT_TIPS['faq_suggest'] if lang == 'zh'
                                else 'FAQ is not auto-generated (needs real business answers). Add delivery/MOQ/sample questions manually.',
                    'tips': zh_tips})


# ---------------- 板块管理 ----------------

def _normalize_section_content(raw):
    """把前端提交的 content（dict 或 JSON 字符串）规范化为 dict"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw.strip() else {}
        except Exception:
            return {}
    return {}


@app.route('/api/sections/types')
@login_required
def section_types():
    """板块库（含用途说明）"""
    return jsonify(SECTION_TYPES)


@app.route('/api/sections', methods=['GET'])
@login_required
def sections_list():
    return jsonify(get_sections(enabled_only=False))


@app.route('/api/sections', methods=['POST'])
@login_required
def sections_add():
    """新增板块（可传 content 完整配置）"""
    data = request.get_json(silent=True) or {}
    stype = (data.get('section_type') or '').strip()
    if stype not in SECTION_TYPE_IDS:
        return jsonify({'error': '板块类型无效'}), 400
    title = (data.get('title') or '').strip()
    content = _normalize_section_content(data.get('content'))
    enabled = 1 if data.get('enabled', True) else 0
    conn = get_db()
    row = conn.execute('SELECT COALESCE(MAX(sort_order), -1) AS m FROM sections').fetchone()
    sort_order = row['m'] + 1
    cur = conn.execute(
        'INSERT INTO sections (section_type, title, content, enabled, sort_order) VALUES (?, ?, ?, ?, ?)',
        (stype, title, json.dumps(content, ensure_ascii=False), enabled, sort_order))
    conn.commit()
    new_row = conn.execute('SELECT * FROM sections WHERE id=?', (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(new_row))


@app.route('/api/sections/<int:sid>', methods=['PUT'])
@login_required
def sections_update(sid):
    """更新板块（标题/内容/启停）"""
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute('SELECT * FROM sections WHERE id=?', (sid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '板块不存在'}), 404
    title = (data.get('title') if data.get('title') is not None else row['title']) or ''
    if 'section_type' in data:
        stype = (data.get('section_type') or row['section_type']).strip()
        if stype not in SECTION_TYPE_IDS:
            conn.close()
            return jsonify({'error': '板块类型无效'}), 400
    else:
        stype = row['section_type']
    content = _normalize_section_content(data.get('content')) if 'content' in data else (
        json.loads(row['content']) if row['content'] else {})
    enabled = int(data.get('enabled', row['enabled']))
    conn.execute('UPDATE sections SET section_type=?, title=?, content=?, enabled=? WHERE id=?',
                 (stype, title, json.dumps(content, ensure_ascii=False), enabled, sid))
    conn.commit()
    new_row = conn.execute('SELECT * FROM sections WHERE id=?', (sid,)).fetchone()
    conn.close()
    return jsonify(dict(new_row))


@app.route('/api/sections/<int:sid>', methods=['DELETE'])
@login_required
def sections_delete(sid):
    conn = get_db()
    row = conn.execute('SELECT * FROM sections WHERE id=?', (sid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '板块不存在'}), 404
    conn.execute('DELETE FROM sections WHERE id=?', (sid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/sections/reorder', methods=['POST'])
@login_required
def sections_reorder():
    """整体排序：{"ids": [id1, id2, ...]}，按列表顺序重写 sort_order"""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    if not ids:
        return jsonify({'error': '缺少 ids'}), 400
    conn = get_db()
    for i, sid in enumerate(ids):
        conn.execute('UPDATE sections SET sort_order=? WHERE id=?', (i, sid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/sections/<int:sid>/move', methods=['POST'])
@login_required
def sections_move(sid):
    """上下移动：{"direction": "up"|"down"}"""
    data = request.get_json(silent=True) or {}
    direction = data.get('direction')
    if direction not in ('up', 'down'):
        return jsonify({'error': 'direction 必须为 up/down'}), 400
    conn = get_db()
    row = conn.execute('SELECT * FROM sections WHERE id=?', (sid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '板块不存在'}), 404
    rows = conn.execute('SELECT * FROM sections ORDER BY sort_order ASC, id ASC').fetchall()
    conn.close()
    idx = next((i for i, r in enumerate(rows) if r['id'] == sid), None)
    if idx is None:
        return jsonify({'error': '板块不存在'}), 404
    swap_idx = idx - 1 if direction == 'up' else idx + 1
    if swap_idx < 0 or swap_idx >= len(rows):
        return jsonify({'ok': True, 'msg': '已在最边缘'})
    a, b = rows[idx], rows[swap_idx]
    conn = get_db()
    conn.execute('UPDATE sections SET sort_order=? WHERE id=?', (b['sort_order'], a['id']))
    conn.execute('UPDATE sections SET sort_order=? WHERE id=?', (a['sort_order'], b['id']))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------------- 页面管理 ----------------

def _gen_slug(title, base='page', exclude_id=None):
    """由标题生成唯一 slug（小写字母数字连字符）"""
    s = re.sub(r'[^a-zA-Z0-9]+', '-', title.strip().lower()).strip('-')
    if not s:
        s = base
    if not re.match(r'^[a-z0-9][a-z0-9-]*$', s):
        s = base
    conn = get_db()
    while True:
        row = conn.execute('SELECT id FROM pages WHERE slug=? AND (id IS NOT ? OR ? IS NULL)',
                           (s, exclude_id, exclude_id)).fetchone()
        if not row:
            break
        s += '-2'
    conn.close()
    return s


@app.route('/api/pages', methods=['GET'])
@login_required
def pages_list():
    return jsonify(get_pages(enabled_only=False))


@app.route('/api/pages', methods=['POST'])
@login_required
def pages_add():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': '页面标题不能为空'}), 400
    slug = (data.get('slug') or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', slug or ''):
        slug = _gen_slug(title)
    if slug in ('index', 'contact', 'products', 'faq'):
        return jsonify({'error': 'slug 不能为保留名称 index/contact/products/faq（faq 已由板块化 FAQ 自动生成）'}), 400
    content = data.get('content') or ''
    template = (data.get('template') or '').strip().lower()
    if template == 'about' and not content:
        content = PAGE_ABOUT_HTML
    enabled = 1 if data.get('enabled', True) else 0
    conn = get_db()
    exists = conn.execute('SELECT id FROM pages WHERE slug=?', (slug,)).fetchone()
    if exists:
        conn.close()
        return jsonify({'error': 'slug 已存在，请换一个（如 %s-2）' % slug}), 400
    row = conn.execute('SELECT COALESCE(MAX(sort_order), -1) AS m FROM pages').fetchone()
    sort_order = row['m'] + 1
    cur = conn.execute(
        'INSERT INTO pages (title, slug, content, enabled, sort_order, seo_title, seo_description, seo_keywords) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (title, slug, content, enabled, sort_order,
         data.get('seo_title') or title, data.get('seo_description') or '', data.get('seo_keywords') or ''))
    conn.commit()
    new_row = conn.execute('SELECT * FROM pages WHERE id=?', (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(new_row))


@app.route('/api/pages/<int:pid>', methods=['PUT'])
@login_required
def pages_update(pid):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute('SELECT * FROM pages WHERE id=?', (pid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '页面不存在'}), 404
    title = (data.get('title') if data.get('title') is not None else row['title']) or ''
    slug = (data.get('slug') if data.get('slug') is not None else row['slug']) or ''
    slug = slug.strip().lower()
    if slug and not re.fullmatch(r'[a-z0-9][a-z0-9-]*', slug):
        return jsonify({'error': 'slug 格式不正确（小写字母数字连字符）'}), 400
    if slug in ('index', 'contact', 'products', 'faq'):
        return jsonify({'error': 'slug 不能为保留名称 index/contact/products/faq（faq 已由板块化 FAQ 自动生成）'}), 400
    dup = conn.execute('SELECT id FROM pages WHERE slug=? AND id != ?', (slug, pid)).fetchone()
    if dup:
        conn.close()
        return jsonify({'error': 'slug 已存在'}), 400
    content = data.get('content', row['content'])
    enabled = int(data.get('enabled', row['enabled']))
    conn.execute('UPDATE pages SET title=?, slug=?, content=?, enabled=?, '
                 'seo_title=?, seo_description=?, seo_keywords=? WHERE id=?',
                 (title, slug, content, enabled,
                  data.get('seo_title', row['seo_title'] or title),
                  data.get('seo_description', row['seo_description'] or ''),
                  data.get('seo_keywords', row['seo_keywords'] or ''), pid))
    conn.commit()
    new_row = conn.execute('SELECT * FROM pages WHERE id=?', (pid,)).fetchone()
    conn.close()
    return jsonify(dict(new_row))


@app.route('/api/pages/<int:pid>', methods=['DELETE'])
@login_required
def pages_delete(pid):
    conn = get_db()
    row = conn.execute('SELECT * FROM pages WHERE id=?', (pid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '页面不存在'}), 404
    conn.execute('DELETE FROM pages WHERE id=?', (pid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------------- 友情链接 ----------------

@app.route('/api/friend_links', methods=['GET'])
@login_required
def friend_links_list():
    return jsonify(get_friend_links())


@app.route('/api/friend_links', methods=['POST'])
@login_required
def friend_links_add():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    url = (data.get('url') or '').strip()
    if not name or not url:
        return jsonify({'error': '名称与 URL 不能为空'}), 400
    nofollow = 1 if data.get('nofollow', True) else 0
    conn = get_db()
    row = conn.execute('SELECT COALESCE(MAX(sort_order), -1) AS m FROM friend_links').fetchone()
    sort_order = row['m'] + 1
    cur = conn.execute('INSERT INTO friend_links (name, url, nofollow, sort_order) VALUES (?, ?, ?, ?)',
                       (name, url, nofollow, sort_order))
    conn.commit()
    new_row = conn.execute('SELECT * FROM friend_links WHERE id=?', (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(new_row))


@app.route('/api/friend_links/<int:lid>', methods=['PUT'])
@login_required
def friend_links_update(lid):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute('SELECT * FROM friend_links WHERE id=?', (lid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '链接不存在'}), 404
    name = (data.get('name') if data.get('name') is not None else row['name']) or ''
    url = (data.get('url') if data.get('url') is not None else row['url']) or ''
    nofollow = int(data.get('nofollow', row['nofollow']))
    conn.execute('UPDATE friend_links SET name=?, url=?, nofollow=? WHERE id=?',
                 (name, url, nofollow, lid))
    conn.commit()
    new_row = conn.execute('SELECT * FROM friend_links WHERE id=?', (lid,)).fetchone()
    conn.close()
    return jsonify(dict(new_row))


@app.route('/api/friend_links/<int:lid>', methods=['DELETE'])
@login_required
def friend_links_delete(lid):
    conn = get_db()
    row = conn.execute('SELECT * FROM friend_links WHERE id=?', (lid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '链接不存在'}), 404
    conn.execute('DELETE FROM friend_links WHERE id=?', (lid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------------- 版本历史 ----------------

@app.route('/api/versions', methods=['GET'])
@login_required
def versions_list():
    conn = get_db()
    rows = conn.execute('SELECT id, created_at, template, note, snapshot FROM versions ORDER BY id DESC').fetchall()
    conn.close()
    out = []
    for r in rows:
        try:
            snap = json.loads(r['snapshot']) if r['snapshot'] else {}
        except Exception:
            snap = {}
        out.append({
            'id': r['id'], 'created_at': r['created_at'], 'template': r['template'],
            'note': r['note'],
            'site_name': snap.get('site_name', ''),
            'section_count': len(snap.get('sections', [])),
            'page_count': len(snap.get('pages', [])),
        })
    return jsonify(out)


@app.route('/api/versions/<int:vid>', methods=['GET'])
@login_required
def versions_detail(vid):
    conn = get_db()
    row = conn.execute('SELECT * FROM versions WHERE id=?', (vid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': '版本不存在'}), 404
    try:
        snap = json.loads(row['snapshot'])
    except Exception:
        return jsonify({'error': '版本数据损坏'}), 500
    return jsonify({
        'id': row['id'], 'created_at': row['created_at'], 'template': row['template'],
        'note': row['note'], 'snapshot': snap,
    })


@app.route('/api/versions/<int:vid>/restore', methods=['POST'])
@login_required
def versions_restore(vid):
    """恢复版本：回写 sections/pages/friend_links/site_config（含模板）"""
    try:
        safety = _create_backup_archive()
        ok, msg, summary = restore_version(vid)
        summary['pre_backup'] = safety
    except Exception as e:
        app.logger.exception('版本恢复接口异常')
        return jsonify({'error': '恢复失败：%s' % str(e)}), 500
    if not ok:
        return jsonify({'error': msg}), 400
    return jsonify({'ok': True, 'msg': msg, 'summary': summary})


# ---------------- 横幅管理 ----------------

@app.route('/api/logo', methods=['GET', 'POST', 'DELETE'])
@login_required
def logo_api():
    """网站 Logo：GET 获取 / POST 上传 / DELETE 移除"""
    if request.method == 'GET':
        return jsonify({'path': get_config('site_logo', '')})
    if request.method == 'DELETE':
        old = get_config('site_logo', '')
        if old:
            p = os.path.join(UPLOAD_DIR, os.path.basename(old))
            if os.path.exists(p):
                os.remove(p)
        set_config('site_logo', '')
        return jsonify({'ok': True})
    # POST 上传
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': '未选择文件'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'error': '仅支持图片格式: png / jpg / jpeg / gif / webp'}), 400
    filename = uuid.uuid4().hex + ext
    file.save(os.path.join(UPLOAD_DIR, filename))
    old = get_config('site_logo', '')
    if old:
        old_path = os.path.join(UPLOAD_DIR, os.path.basename(old))
        if os.path.exists(old_path):
            os.remove(old_path)
    set_config('site_logo', '/uploads/' + filename)
    return jsonify({'ok': True, 'path': '/uploads/' + filename})


@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    """通用图片上传：返回可插入 HTML 的图片 URL（用于产品描述插图等）"""
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': '未选择文件'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'error': '仅支持图片格式: png / jpg / jpeg / gif / webp'}), 400
    filename = uuid.uuid4().hex + ext
    file.save(os.path.join(UPLOAD_DIR, filename))
    return jsonify({'ok': True, 'path': '/uploads/' + filename})


@app.route('/api/banner', methods=['GET'])
@login_required
def banner_list():
    conn = get_db()
    rows = conn.execute('SELECT * FROM banner ORDER BY sort_order ASC, id ASC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/banner/upload', methods=['POST'])
@login_required
def banner_upload():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': '未选择文件'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'error': '仅支持图片格式: png / jpg / jpeg / gif / webp'}), 400
    filename = uuid.uuid4().hex + ext
    file.save(os.path.join(UPLOAD_DIR, filename))
    conn = get_db()
    row = conn.execute('SELECT COALESCE(MAX(sort_order), -1) AS m FROM banner').fetchone()
    sort_order = row['m'] + 1
    cur = conn.execute('INSERT INTO banner (image_path, sort_order) VALUES (?, ?)',
                       ('/uploads/' + filename, sort_order))
    conn.commit()
    new_row = conn.execute('SELECT * FROM banner WHERE id=?', (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(new_row))


@app.route('/api/banner/<int:banner_id>', methods=['DELETE'])
@login_required
def banner_delete(banner_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM banner WHERE id=?', (banner_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '记录不存在'}), 404
    path = os.path.join(UPLOAD_DIR, os.path.basename(row['image_path']))
    if os.path.exists(path):
        os.remove(path)
    conn.execute('DELETE FROM banner WHERE id=?', (banner_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------------- 联系方式管理 ----------------

@app.route('/api/contacts', methods=['GET'])
@login_required
def contacts_list():
    conn = get_db()
    rows = conn.execute('SELECT id, contact_type, contact_value FROM contacts ORDER BY id ASC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/contacts', methods=['POST'])
@login_required
def contacts_add():
    data = request.get_json(silent=True) or {}
    ctype = (data.get('contact_type') or '').strip()
    cvalue = (data.get('contact_value') or '').strip()
    if ctype not in CONTACT_TYPES:
        return jsonify({'error': '联系方式类型无效'}), 400
    if not cvalue:
        return jsonify({'error': '号码/ID 不能为空'}), 400
    conn = get_db()
    cur = conn.execute('INSERT INTO contacts (contact_type, contact_value) VALUES (?, ?)',
                       (ctype, cvalue))
    conn.commit()
    row = conn.execute('SELECT id, contact_type, contact_value FROM contacts WHERE id=?', (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(row))


@app.route('/api/contacts/<int:cid>', methods=['DELETE'])
@login_required
def contacts_delete(cid):
    conn = get_db()
    row = conn.execute('SELECT id FROM contacts WHERE id=?', (cid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '记录不存在'}), 404
    conn.execute('DELETE FROM contacts WHERE id=?', (cid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------------- 产品管理 ----------------

@app.route('/api/products', methods=['GET'])
@login_required
def products_list():
    conn = get_db()
    rows = conn.execute('SELECT * FROM products ORDER BY sort_order ASC, id DESC').fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d['images'] = json.loads(d.get('images') or '[]')
        except Exception:
            d['images'] = []
        out.append(d)
    return jsonify(out)


def _parse_images(form, old_images=None, upload_dir=UPLOAD_DIR):
    """解析图片字段，返回 (images 最终列表, 需物理删除的 URL 列表)

    支持两种模式：
    - 前端统一上传模式：images_order（完整顺序 JSON）+ removed（删除 URL JSON）
    - 兼容旧模式：imgs 文件字段追加
    """
    old_images = list(old_images or [])
    files = request.files.getlist('imgs')
    new_urls = []
    try:
        for f in files:
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1].lower()
                if ext not in ALLOWED_EXT:
                    raise ValueError('仅支持图片格式: png / jpg / jpeg / gif / webp')
                filename = uuid.uuid4().hex + ext
                f.save(os.path.join(upload_dir, filename))
                new_urls.append('/uploads/' + filename)
    except ValueError as e:
        raise e

    order_raw = (form.get('images_order') or '').strip()
    if order_raw:
        try:
            order = json.loads(order_raw)
            if not isinstance(order, list):
                order = []
        except Exception:
            order = []
        from catalog_data import web_url
        base = []
        for image_url in order:
            if not isinstance(image_url, str):
                continue
            if image_url.startswith('/uploads/'):
                base.append(image_url)
            elif image_url.startswith(('https://', 'http://')):
                base.append(web_url(image_url))
    else:
        base = list(old_images) + new_urls

    removed_raw = (form.get('removed') or '').strip()
    removed = []
    if removed_raw:
        try:
            removed = json.loads(removed_raw)
            if not isinstance(removed, list):
                removed = [x.strip() for x in removed_raw.split(',') if x.strip()]
        except Exception:
            removed = [x.strip() for x in removed_raw.split(',') if x.strip()]
        removed = [u for u in removed if isinstance(u, str) and (u.startswith('/uploads/') or u in base)]

    images = [u for u in base if u not in removed]
    return images, removed


def _delete_uploaded(urls, upload_dir=UPLOAD_DIR):
    for u in urls:
        if not u or not u.startswith('/uploads/'):
            continue
        fpath = os.path.join(upload_dir, os.path.basename(u))
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
        except OSError:
            pass


def _ensure_category(conn, name):
    """产品保存时若填了全新分类名称，自动并入 categories（兼容旧的自由文本分类）"""
    name = (name or '').strip()
    if not name:
        return
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS categories '
                     '(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, sort_order INTEGER DEFAULT 0)')
    except Exception:
        pass
    exists = conn.execute('SELECT id FROM categories WHERE name=?', (name,)).fetchone()
    if not exists:
        m = conn.execute('SELECT COALESCE(MAX(sort_order), 0) AS m FROM categories').fetchone()
        conn.execute('INSERT INTO categories (name, sort_order) VALUES (?, ?)',
                     (name, (m['m'] if m else 0) + 1))
        conn.commit()


# ================= 产品批量导入（P1） =================
# 单进程互斥锁：同一时刻只允许一个导入任务，防止并发写入错乱
_PRODUCT_IMPORT_LOCK = threading.Lock()
IMPORT_MAX_ROWS = 500                    # 单次最多导入 500 行数据
IMPORT_MAX_BYTES = 10 * 1024 * 1024      # 表格文件 ≤ 10MB（与全局 MAX_CONTENT_LENGTH 的表格部分一致）
IMPORT_ZIP_MAX_BYTES = 50 * 1024 * 1024  # zip 打包上传 ≤ 50MB（内部含 1 个表格 + 图片文件任意层级）
# 批量导入模板列：图片列可填文件名（如 led-lamp.jpg），多张用 | 分隔；图片文件随表格一起上传或打包 zip
_PROUDCT_IMPORT_IMG_HINT = '选填；图片文件名，如 led-lamp.jpg；多张用 | 分隔，如 a.jpg|b.jpg；文件需和本表格一起上传（或打包 zip）'
_PRODUCT_IMPORT_IMG_HEADER = '图片'
# 历史兼容：旧模板第 10 列是“图片（本版本不通过表格传图…）”提示列，表头仍以“图片”开头，可被识别为图片列但值为空，不报未知列

# 模板列：(中文列名, 字段键, 是否必填, 最大长度, 第二行用户说明)
# 说明：模板第 10 列为真正的“图片”列——填图片文件名，随表上传或打 zip 后按文件名匹配入库。
_PRODUCT_IMPORT_COLUMNS = [
    ('产品名称', 'name', True, 200, '必填；不能与已有产品同名，如：LED Lamp'),
    ('价格', 'price', False, 60, '选填；原样保存，如 $9.90 或 9.90'),
    ('分类', 'category', False, 60, '选填；空=未分类，不存在的分类会自动创建，如 LED 灯具'),
    ('库存数量', 'stock', False, None, '选填；整数 ≥0，未知留空；非法值会跳过该行并提示'),
    ('SKU', 'sku', False, 60, '选填；库存编码，如 LED-100W-A'),
    ('型号', 'model', False, 60, '选填；如 XT-880'),
    ('规格', 'spec', False, 200, '选填；如 10x10x5cm'),
    ('产品视频链接', 'product_video', False, 300, '选填；YouTube / Vimeo 分享链接'),
    ('详细描述', 'description', False, None, '选填；产品介绍文本，导入后为纯文本'),
    (_PRODUCT_IMPORT_IMG_HEADER, 'images', False, None, _PROUDCT_IMPORT_IMG_HINT),
]
_PRODUCT_IMPORT_EXAMPLE = {
    'name': '示例-请删除本行', 'price': '$9.90', 'category': 'LED 灯具', 'stock': '100',
    'sku': 'LED-100W-A', 'model': 'XT-880', 'spec': '10x10x5cm',
    'product_video': 'https://www.youtube.com/watch?v=xxxx',
    'description': '这是一段示例产品介绍。整行示例在导入时会自动跳过，不会进入系统。',
}


def _import_openpyxl():
    """按需加载 openpyxl（P1 新增依赖），缺失时返回 None 由路由给出友好提示"""
    try:
        import openpyxl
        return openpyxl
    except ImportError:
        return None


def _cell_str(v):
    """单元格统一转字符串：None -> ''；xlsx 数字 100.0 -> '100'"""
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (int, float)):
        v = str(v)
    s = str(v).strip()
    return s


def _match_header_key(text):
    """表头中文列名 -> 字段键。容错：去首尾空格；支持“产品名称（必填）”括号注释与 * 标记"""
    t = (text or '').strip().replace('\u3000', ' ')
    t = re.split(r'[（(]', t)[0].strip().rstrip('*').strip()
    t = t.replace(' ', '')
    for col_name, key, *_ in _PRODUCT_IMPORT_COLUMNS:
        if t == col_name:
            return key
    return None


def _scan_header(rows, max_scan=20):
    """在前若干行内定位表头，返回 (表头行索引, {字段键: 列索引}, 未识别列清单) 或 (None, {}, [])"""
    exact_idx, loose_idx = None, None
    for i, cells in enumerate(rows[:max_scan]):
        if not cells:
            continue
        first = _cell_str(cells[0])
        if first == '产品名称':
            exact_idx = i
            break
        if first.startswith('产品名称') and loose_idx is None:
            loose_idx = i
    hidx = exact_idx if exact_idx is not None else loose_idx
    if hidx is None:
        return None, {}, []
    col_map, unknown = {}, []
    for idx, cell in enumerate(rows[hidx]):
        key = _match_header_key(_cell_str(cell))
        if key:
            col_map.setdefault(key, idx)
        else:
            name = _cell_str(cell)
            # “图片（本版本不通过表格传图…）”是官方提示列，不属于未识别列，避免打扰
            if name and not name.startswith('图片'):
                unknown.append(name)
    return hidx, col_map, unknown


def _import_ensure_category(conn, name, newly_created):
    """等价复用 _ensure_category：自动创建分类并登记到 newly_created（不即时 commit）"""
    name = (name or '').strip()
    if not name:
        return
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS categories '
                     '(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, sort_order INTEGER DEFAULT 0)')
    except Exception:
        pass
    exists = conn.execute('SELECT id FROM categories WHERE name=?', (name,)).fetchone()
    if not exists:
        m = conn.execute('SELECT COALESCE(MAX(sort_order), 0) AS m FROM categories').fetchone()
        conn.execute('INSERT INTO categories (name, sort_order) VALUES (?, ?)',
                     (name, (m['m'] if m else 0) + 1))
        newly_created.add(name)


def _build_template_rows():
    """生成模板表格内容：第 1 行表头 / 第 2 行说明 / 第 3 行示例（xlsx 与 csv 同构）"""
    headers = [c[0] for c in _PRODUCT_IMPORT_COLUMNS]
    hints = [c[4] for c in _PRODUCT_IMPORT_COLUMNS]
    example = [_PRODUCT_IMPORT_EXAMPLE.get(c[1], '') for c in _PRODUCT_IMPORT_COLUMNS]
    # 示例行会被自动跳过，图片列给一个直观文件名示例便于用户照抄格式
    example[-1] = 'led-lamp.jpg|led-lamp-2.jpg'
    return headers, hints, example


@app.route('/api/products/template', methods=['GET'])
@login_required
def products_template_download():
    """下载 Excel(.xlsx) 导入模板；CSV 模板由前端 JS 直接生成下载（避免后端双实现）"""
    openpyxl = _import_openpyxl()
    if openpyxl is None:
        return jsonify({'error': '缺少 openpyxl 依赖，请先安装（pip install "openpyxl>=3.1"）'}), 500
    try:
        from openpyxl.styles import Font, PatternFill
    except Exception:
        Font = PatternFill = None
    headers, hints, example = _build_template_rows()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '产品导入模板'
    ws.append(headers)
    ws.append(hints)
    ws.append(example)
    # 表头加粗 + 底色，便于用户识别首行为列名
    try:
        fill = PatternFill(start_color='FFE7E9F0', end_color='FFE7E9F0', fill_type='solid')
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = fill
    except Exception:
        pass
    widths = {1: 34, 2: 22, 3: 18, 4: 16, 5: 18, 6: 16, 7: 18, 8: 40, 9: 60, 10: 40}
    for idx, w in widths.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = w
    ws.freeze_panes = 'A2'
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    try:
        from flask import send_file
    except ImportError:
        return jsonify({'error': 'send_file 不可用'}), 500
    return send_file(
        bio, as_attachment=True,
        download_name='ChatFLOW产品批量导入模板.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/api/products/import', methods=['POST'])
@login_required
def products_import():
    """批量导入产品：xlsx/csv → 解析 → 逐行校验 → 入库 → 返回逐行报告"""
    if not _PRODUCT_IMPORT_LOCK.acquire(blocking=False):
        return jsonify({'error': '已有导入任务正在进行中，请稍候再试'}), 409
    try:
        return _products_import_impl()
    finally:
        _PRODUCT_IMPORT_LOCK.release()


def _import_save_upload_image(src_path):
    """把暂存的批量导入图片物理复制为 static/uploads/<uuid>.<ext>，返回 /uploads/ 相对 URL。
    每次引用都复制独立 uuid 文件：同名图片被多行引用时各产品拥有独立文件，删除互不误伤。"""
    ext = os.path.splitext(src_path)[1].lower()
    fname = uuid.uuid4().hex + ext
    dst = os.path.join(UPLOAD_DIR, fname)
    shutil.copy2(src_path, dst)
    return '/uploads/' + fname


def _products_import_impl():
    # 主表：兼容 multipart 字段 table（新规范）与 file（旧前端/自测）两种命名
    f = request.files.get('table') or request.files.get('file')
    if f is None or not getattr(f, 'filename', ''):
        return jsonify({'error': '请选择要导入的文件'}), 400
    filename = (f.filename or '').split('/')[-1].split('\\')[-1]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ('.xlsx', '.csv', '.zip'):
        return jsonify({'error': '仅支持 .xlsx / .csv 表格文件，或内含表格+图片的 .zip 压缩包'}), 400

    tmp_root = tempfile.mkdtemp(prefix='p1img_import_')
    upload_pics = {}   # {图片文件名小写: 暂存物理路径}，用于按文件名匹配（大小写不敏感）

    if ext == '.zip':
        # B 形态：单个 zip，内含 1 个 xlsx/csv + 图片文件（任意层级）
        zip_bytes = f.read(IMPORT_ZIP_MAX_BYTES + 1)
        if len(zip_bytes) > IMPORT_ZIP_MAX_BYTES:
            return jsonify({'error': '压缩包超过 50MB 上限，请拆分后导入'}), 400
        if not zip_bytes:
            return jsonify({'error': '压缩包为空，请重新打包后再导入'}), 400
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except Exception:
            return jsonify({'error': '压缩包无法打开，请确认为有效的 .zip 文件'}), 400
        table_candidates = []
        try:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # 防 zip 路径穿越：仅取文件名末段，忽略 zip 内部任意层级目录
                base = os.path.basename(info.filename)
                if not base:
                    continue
                e = os.path.splitext(base)[1].lower()
                if e in ('.xlsx', '.csv'):
                    table_candidates.append(info.filename)
                elif e in ALLOWED_EXT:
                    img_data = zf.read(info)
                    if not img_data:
                        continue
                    dst = os.path.join(tmp_root, 'pic_' + uuid.uuid4().hex + e)
                    with open(dst, 'wb') as fo:
                        fo.write(img_data)
                    upload_pics.setdefault(base.lower(), dst)
            if not table_candidates:
                return jsonify({'error': '压缩包内没有找到 .xlsx 或 .csv 表格文件'}), 400
            # 多个表格时优先 basename 含“产品/模板/import”的，否则取 zip 中顺序第一个
            def _score(p):
                b = os.path.basename(p).lower()
                return sum(1 for k in ('产品', '模板', 'product', 'import') if k in b)
            pick = sorted(table_candidates, key=_score, reverse=True)[0]
            data = zf.read(pick)
            filename = os.path.basename(pick)
            ext = os.path.splitext(filename)[1].lower()
        finally:
            zf.close()
    else:
        # A 形态：表格字段（table/file）+ 多个图片文件字段（images/image，普通文件名匹配）
        data = f.read(IMPORT_MAX_BYTES + 1)
        if len(data) > IMPORT_MAX_BYTES:
            return jsonify({'error': '表格文件超过 10MB 上限，请拆分后导入'}), 400
        if not data:
            return jsonify({'error': '文件为空，请重新填写后再导入'}), 400
        pic_files = request.files.getlist('images') or request.files.getlist('image')
        for pf in pic_files:
            pname = (pf.filename or '').split('/')[-1].split('\\')[-1]
            pext = os.path.splitext(pname)[1].lower()
            if not pname or pext not in ALLOWED_EXT:
                continue   # 非图片字段/非图片格式直接忽略，不影响表格导入
            dst = os.path.join(tmp_root, 'pic_' + uuid.uuid4().hex + pext)
            pf.save(dst)
            upload_pics.setdefault(pname.lower(), dst)

    if ext == '.csv':
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                text = data.decode('gbk')
            except UnicodeDecodeError:
                return jsonify({'error': '无法识别 CSV 编码，请将文件另存为 UTF-8 或 GBK 后重试'}), 400
        rows = [list(r) for r in csv.reader(io.StringIO(text))]
    else:
        openpyxl = _import_openpyxl()
        if openpyxl is None:
            return jsonify({'error': '缺少 openpyxl 依赖，请先安装（pip install "openpyxl>=3.1"）'}), 500
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            ws = wb.active
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            wb.close()
        except Exception as e:
            return jsonify({'error': 'Excel 文件解析失败：%s' % e}), 400

    rows = [[_cell_str(v) for v in r] for r in rows]
    if not rows:
        return jsonify({'error': '文件里没有找到表头，请用我们提供的模板填写后重试'}), 400
    hidx, col_map, unknown_cols = _scan_header(rows)
    if hidx is None or 'name' not in col_map:
        return jsonify({'error': '文件里没有找到表头（缺少“产品名称”列），请用我们提供的模板填写后重试'}), 400

    conn = get_db()
    newly_created = set()
    try:
        existing_names = set(
            (r['name'] or '').strip() for r in conn.execute('SELECT name FROM products').fetchall())
        # 逐行处理
        success = 0
        failed = []            # {'row': 物理行号, 'name': 产品名, 'reason': 失败原因}
        skipped_dups = []      # {'row': 物理行号, 'name': 产品名}
        warnings = []
        note_rows = 0          # 被跳过的说明行/示例行数量
        processed = 0          # 有效数据行计数（含失败与重复，不含说明/示例/空行）
        batch_names = set()
        row_no = hidx + 1      # 表头所在物理行号
        for r in rows[hidx + 1:]:
            row_no += 1
            if not any(v for v in r):
                continue
            cells = {}
            for key, col in col_map.items():
                cells[key] = _cell_str(r[col]) if col < len(r) else ''
            name = cells.get('name', '')

            # 模板说明行 / 示例行自动跳过（不计入有效行）
            if name.startswith('产品名称') or '必填' in name or '示例' in name or '请删除本行' in name:
                note_rows += 1
                continue
            if processed >= IMPORT_MAX_ROWS:
                remaining = len(rows[hidx + 1:]) - (row_no - hidx - 1)
                if remaining > 0:
                    warnings.append('超过单次最多 %d 行：第 %d 行起剩余 %d 行未导入（已完成的前 %d 行正常入库）'
                                    % (IMPORT_MAX_ROWS, row_no, remaining, success))
                break
            processed += 1

            # ---- 校验 ----
            reason = None
            if not name:
                reason = '产品名称不能为空'
            elif len(name) > _PRODUCT_IMPORT_COLUMNS[0][3]:
                reason = '产品名称超过 %d 字符' % _PRODUCT_IMPORT_COLUMNS[0][3]
            elif name in existing_names or name in batch_names:
                skipped_dups.append({'row': row_no, 'name': name})
                continue
            if reason is None:
                for col_name, key, required, maxlen, _hint in _PRODUCT_IMPORT_COLUMNS:
                    if key == 'name':
                        continue
                    val = cells.get(key, '')
                    if maxlen and len(val) > maxlen:
                        reason = '%s超过 %d 字符（当前 %d 字）' % (col_name, maxlen, len(val))
                        break
            stock_raw = cells.get('stock', '')
            if reason is None and stock_raw:
                if not re.fullmatch(r'[0-9]+', stock_raw):
                    reason = '库存请填非负整数，未知可留空；该行未导入'
                elif len(stock_raw) > 19 or int(stock_raw) > 9223372036854775807:
                    reason = '库存数量超过可保存范围；该行未导入'
            if reason:
                failed.append({'row': row_no, 'name': name, 'reason': reason})
                continue

            # ---- 入库（只 INSERT 不覆盖；失败行跳过，成功行照常入库）----
            stock = int(stock_raw) if stock_raw else None
            category = cells.get('category', '')
            # 图片匹配：按文件名从随表上传/zip 的资源中匹配；缺失/格式不支持仅告警，不阻塞行导入
            img_urls = []
            for token in (cells.get('images', '') or '').split('|'):
                token = token.strip()
                if not token:
                    continue
                tok_base = token.replace('\\', '/').rsplit('/', 1)[-1].strip()
                if not tok_base:
                    continue
                tok_ext = os.path.splitext(tok_base)[1].lower()
                src = upload_pics.get(tok_base.lower())
                if tok_ext not in ALLOWED_EXT:
                    warnings.append('第 %d 行：图片「%s」不是支持的图片格式（png/jpg/jpeg/gif/webp/svg），已跳过该行图片'
                                    % (row_no, tok_base))
                elif not src:
                    warnings.append('第 %d 行：图片 %s 未找到，已跳过该行图片' % (row_no, tok_base))
                else:
                    try:
                        img_urls.append(_import_save_upload_image(src))
                    except Exception:
                        warnings.append('第 %d 行：图片 %s 保存失败，已跳过该行图片' % (row_no, tok_base))
            img = img_urls[0] if img_urls else ''
            images_json = json.dumps(img_urls, ensure_ascii=False) if img_urls else ''
            _import_ensure_category(conn, category, newly_created)
            conn.execute(
                'INSERT INTO products (name, price, spec, img, sku, model, stock, category, '
                'images, description, detail_layout, product_video) '
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'classic', ?)",
                (name, cells.get('price', ''), cells.get('spec', ''), img, cells.get('sku', ''),
                 cells.get('model', ''), stock, category, images_json, cells.get('description', ''),
                 cells.get('product_video', '')))
            batch_names.add(name)
            success += 1
        conn.commit()
    finally:
        conn.close()
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass

    result = {
        'ok': True,
        'success': success,
        'failed': failed,
        'skipped_duplicates': len(skipped_dups),
        'skipped_duplicate_names': skipped_dups,
        'new_categories': sorted(newly_created),
        'warnings': warnings,
        'note_rows': note_rows,
        'imported_rows': processed,
        'filename': filename,
    }
    if unknown_cols:
        result['unknown_cols'] = unknown_cols
    return jsonify(result)


def _parse_manual_stock(raw):
    """Preserve unknown inventory and keep integers within SQLite's storage range."""
    raw = raw.strip()
    if not raw:
        return None
    if not re.fullmatch(r'[0-9]+', raw):
        raise ValueError('库存请填非负整数，未知可留空')
    digits = raw.lstrip('0') or '0'
    if len(digits) > 19 or int(digits) > 9223372036854775807:
        raise ValueError('库存数量过大，无法保存；未知可留空')
    return int(digits)


@app.route('/api/products', methods=['POST'])
@login_required
def products_add():
    name = (request.form.get('name') or '').strip()
    price = (request.form.get('price') or '').strip()
    spec = (request.form.get('spec') or '').strip()
    sku = (request.form.get('sku') or '').strip()
    model = (request.form.get('model') or '').strip()
    category = (request.form.get('category') or '').strip()
    desc = (request.form.get('description') or '').strip()
    detail_layout = (request.form.get('detail_layout') or 'classic').strip()
    product_video = (request.form.get('product_video') or '').strip()
    # P4 产品级独立 SEO：meta_title ≤80 / meta_description 50-160（后端只存取，前端做字数建议）
    meta_title = (request.form.get('meta_title') or '').strip()
    meta_description = (request.form.get('meta_description') or '').strip()
    if detail_layout not in {d['id'] for d in detail_layouts()}:
        detail_layout = 'classic'
    try:
        stock = _parse_manual_stock(request.form.get('stock', '0'))
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    if not name:
        return jsonify({'error': '产品名称不能为空'}), 400

    def _save_img(file):
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise ValueError('仅支持图片格式: png / jpg / jpeg / gif / webp')
        filename = uuid.uuid4().hex + ext
        file.save(os.path.join(UPLOAD_DIR, filename))
        return '/uploads/' + filename

    try:
        images, removed = _parse_images(request.form)
        _delete_uploaded(removed)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    img = images[0] if images else ''
    images_json = json.dumps(images, ensure_ascii=False) if images else ''

    conn = get_db()
    _ensure_category(conn, category)
    cur = conn.execute(
        'INSERT INTO products (name, price, spec, img, sku, model, stock, category, images, description, detail_layout, product_video, meta_title, meta_description) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (name, price, spec, img, sku, model, stock, category, images_json, desc, detail_layout, product_video, meta_title, meta_description))
    conn.commit()
    row = conn.execute('SELECT * FROM products WHERE id=?', (cur.lastrowid,)).fetchone()
    conn.close()
    data = dict(row)
    try:
        data['images'] = json.loads(data.get('images') or '[]')
    except Exception:
        data['images'] = []
    return jsonify(data)


@app.route('/api/products/<int:pid>', methods=['GET'])
@login_required
def products_get(pid):
    """编辑时回填单个产品"""
    conn = get_db()
    row = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': '记录不存在'}), 404
    data = dict(row)
    try:
        data['images'] = json.loads(data.get('images') or '[]')
    except Exception:
        data['images'] = []
    return jsonify(data)


@app.route('/api/products/<int:pid>', methods=['PUT'])
@login_required
def products_update(pid):
    """编辑产品：更新除图片外的字段，并可追加新图片（旧图保持不变）"""
    conn = get_db()
    row = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '记录不存在'}), 404
    name = (request.form.get('name') or '').strip()
    if not name:
        conn.close()
        return jsonify({'error': '产品名称不能为空'}), 400
    price = (request.form.get('price') or '').strip()
    spec = (request.form.get('spec') or '').strip()
    sku = (request.form.get('sku') or '').strip()
    model = (request.form.get('model') or '').strip()
    category = (request.form.get('category') or '').strip()
    desc = (request.form.get('description') or '').strip()
    product_video = (request.form.get('product_video') or '').strip()
    # P4 产品级独立 SEO（编辑回填与保存）
    meta_title = (request.form.get('meta_title') or '').strip()
    meta_description = (request.form.get('meta_description') or '').strip()
    try:
        stock = _parse_manual_stock(request.form.get('stock', '0'))
    except ValueError as error:
        conn.close()
        return jsonify({'error': str(error)}), 400

    def _save_img(file):
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise ValueError('仅支持图片格式: png / jpg / jpeg / gif / webp')
        filename = uuid.uuid4().hex + ext
        file.save(os.path.join(UPLOAD_DIR, filename))
        return '/uploads/' + filename

    try:
        old_images = json.loads(row['images'] or '[]')
    except Exception:
        old_images = []
    try:
        images, removed = _parse_images(request.form, old_images=old_images)
        _delete_uploaded(removed)
    except ValueError as e:
        conn.close()
        return jsonify({'error': str(e)}), 400
    img = images[0] if images else ''
    images_json = json.dumps(images, ensure_ascii=False)

    _ensure_category(conn, category)
    conn.execute(
        'UPDATE products SET name=?, price=?, spec=?, img=?, sku=?, model=?, stock=?, category=?, images=?, description=?, product_video=?, meta_title=?, meta_description=? WHERE id=?',
        (name, price, spec, img, sku, model, stock, category, images_json, desc, product_video, meta_title, meta_description, pid))
    conn.commit()
    row = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    conn.close()
    data = dict(row)
    try:
        data['images'] = json.loads(data.get('images') or '[]')
    except Exception:
        data['images'] = []
    return jsonify(data)


@app.route('/api/products/<int:pid>', methods=['DELETE'])
@login_required
def products_delete(pid):
    conn = get_db()
    row = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '记录不存在'}), 404
    path = os.path.join(UPLOAD_DIR, os.path.basename(row['img'] or ''))
    if str(row['img'] or '').startswith('/uploads/') and os.path.isfile(path):
        os.remove(path)
    conn.execute('DELETE FROM products WHERE id=?', (pid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


def _copy_uploaded_url(url, upload_dir=UPLOAD_DIR):
    """复制 /uploads/ 下的物理图片为新文件（避免副本与原产品共享文件，防止删除一方误伤另一方）。
    非上传目录（外链等）原样保留引用。"""
    if not url or not str(url).startswith('/uploads/'):
        return url
    src = os.path.join(upload_dir, os.path.basename(url))
    if not os.path.exists(src):
        return url
    ext = os.path.splitext(str(url))[1].lower() or '.png'
    filename = uuid.uuid4().hex + ext
    try:
        shutil.copy2(src, os.path.join(upload_dir, filename))
    except OSError:
        return url
    return '/uploads/' + filename


@app.route('/api/products/<int:pid>/copy', methods=['POST'])
@login_required
def products_copy(pid):
    """复制产品：完整复制全部字段为新记录（图片物理复制为独立文件），名称自动带副本标识。"""
    conn = get_db()
    row = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '记录不存在'}), 404
    d = dict(row)
    # 图片：主图 + 多图全部物理复制成新文件，避免共享文件导致误删
    try:
        old_imgs = json.loads(d.get('images') or '[]')
    except Exception:
        old_imgs = []
    if not old_imgs and d.get('img'):
        old_imgs = [d['img']]
    new_imgs = [_copy_uploaded_url(u) for u in old_imgs]
    new_img = new_imgs[0] if new_imgs else ''
    # 名称副本标识：若原名已带 - Copy，保留单个标识避免叠加
    base_name = re.sub(r'\s*[-–—]\s*Copy\s*$', '', (d.get('name') or '').strip())
    new_name = (base_name + ' - Copy').strip() or 'Copy Product'
    # P4 产品级 SEO 复制策略：meta_title 非空则追加 "- Copy"（避免重复标题）；meta_description 原样复制
    old_meta_title = (d.get('meta_title') or '').strip()
    new_meta_title = re.sub(r'\s*[-–—]\s*Copy\s*$', '', old_meta_title)
    new_meta_title = (new_meta_title + ' - Copy').strip() if old_meta_title else ''
    new_meta_description = d.get('meta_description') or ''
    _ensure_category(conn, d.get('category') or '')
    cur = conn.execute(
        'INSERT INTO products (name, price, spec, img, sku, model, stock, category, images, description, '
        'detail_layout, product_video, meta_title, meta_description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (new_name, d.get('price') or '', d.get('spec') or '', new_img, d.get('sku') or '',
         d.get('model') or '', d.get('stock', 0), d.get('category') or '',
         json.dumps(new_imgs, ensure_ascii=False) if new_imgs else '',
         d.get('description') or '', d.get('detail_layout') or 'classic', d.get('product_video') or '',
         new_meta_title, new_meta_description))
    conn.commit()
    new_id = cur.lastrowid
    conn.execute('UPDATE products SET catalog_data=? WHERE id=?',(d.get('catalog_data') or '',new_id))
    conn.commit()
    nrow = conn.execute('SELECT * FROM products WHERE id=?', (new_id,)).fetchone()
    conn.close()
    data = dict(nrow)
    try:
        data['images'] = json.loads(data.get('images') or '[]')
    except Exception:
        data['images'] = []
    data['copied_from'] = pid
    return jsonify(data)


# ---------------- 产品分类管理 / 产品排序 ----------------

@app.route('/api/categories', methods=['GET'])
@login_required
def categories_list():
    conn = get_db()
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS categories '
                     '(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, sort_order INTEGER DEFAULT 0)')
    except Exception:
        pass
    rows = conn.execute('SELECT c.*, (SELECT COUNT(*) FROM products p WHERE p.category=c.name) AS product_count '
                        'FROM categories c ORDER BY c.sort_order ASC, c.id ASC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/categories', methods=['POST'])
@login_required
def categories_add():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': '分类名称不能为空'}), 400
    conn = get_db()
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS categories '
                     '(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, sort_order INTEGER DEFAULT 0)')
    except Exception:
        pass
    if conn.execute('SELECT id FROM categories WHERE name=?', (name,)).fetchone():
        conn.close()
        return jsonify({'error': '分类「%s」已存在' % name}), 400
    m = conn.execute('SELECT COALESCE(MAX(sort_order), 0) AS m FROM categories').fetchone()
    cur = conn.execute('INSERT INTO categories (name, sort_order) VALUES (?, ?)',
                       (name, (m['m'] if m else 0) + 1))
    conn.commit()
    row = conn.execute('SELECT * FROM categories WHERE id=?', (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(row))


@app.route('/api/categories/<int:cid>', methods=['PUT'])
@login_required
def categories_update(cid):
    """重命名分类：同步修改引用它的产品 category 文本，保证前台不丢分类"""
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute('SELECT * FROM categories WHERE id=?', (cid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '分类不存在'}), 404
    name = (data.get('name') if data.get('name') is not None else row['name']) or ''
    name = name.strip()
    if not name:
        conn.close()
        return jsonify({'error': '分类名称不能为空'}), 400
    old_name = row['name']
    if name != old_name:
        if conn.execute('SELECT id FROM categories WHERE name=? AND id!=?', (name, cid)).fetchone():
            conn.close()
            return jsonify({'error': '分类「%s」已存在' % name}), 400
        conn.execute('UPDATE products SET category=? WHERE category=?', (name, old_name))
        conn.execute('UPDATE categories SET name=? WHERE id=?', (name, cid))
    if 'sort_order' in data:
        conn.execute('UPDATE categories SET sort_order=? WHERE id=?', (int(data.get('sort_order')), cid))
    conn.commit()
    row = conn.execute('SELECT * FROM categories WHERE id=?', (cid,)).fetchone()
    conn.close()
    return jsonify(dict(row))


@app.route('/api/categories/reorder', methods=['POST'])
@login_required
def categories_reorder():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    conn = get_db()
    for i, cid in enumerate(ids, start=1):
        conn.execute('UPDATE categories SET sort_order=? WHERE id=?', (i, int(cid)))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/categories/<int:cid>', methods=['DELETE'])
@login_required
def categories_delete(cid):
    """删除分类：产品保留但置为未分类，避免误删产品"""
    conn = get_db()
    row = conn.execute('SELECT * FROM categories WHERE id=?', (cid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '分类不存在'}), 404
    conn.execute('UPDATE products SET category=\'\' WHERE category=?', (row['name'],))
    conn.execute('DELETE FROM categories WHERE id=?', (cid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/products/reorder', methods=['POST'])
@login_required
def products_reorder():
    """按前端顺序重排产品（sort_order 依次 1..n）"""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    if not isinstance(ids, list):
        return jsonify({'error': '参数错误'}), 400
    conn = get_db()
    for i, pid in enumerate(ids, start=1):
        conn.execute('UPDATE products SET sort_order=? WHERE id=?', (i, int(pid)))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------------- 数据备份 / 恢复 ----------------

BACKUP_DIR = os.path.join(DATA_DIR, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)


def _backup_meta():
    conn = get_db()
    counts = {}
    for t in ('products', 'pages', 'sections', 'banners', 'contacts', 'categories', 'friend_links', 'versions'):
        try:
            counts[t] = conn.execute('SELECT COUNT(*) AS c FROM %s' % t).fetchone()['c']
        except Exception:
            counts[t] = 0
    conn.close()
    return {'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'site_name': get_config('site_name', ''), 'counts': counts}


def _create_backup_archive():
    fname = datetime.now().strftime('backup_%Y%m%d_%H%M%S_%f') + '.zip'
    fpath = os.path.join(BACKUP_DIR, fname)
    tmp_db = os.path.join(BACKUP_DIR, '_tmp_' + uuid.uuid4().hex + '.db')
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(tmp_db)
    try:
        src.backup(dst)
    finally:
        src.close(); dst.close()
    with zipfile.ZipFile(fpath, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(tmp_db, 'app.db')
        zf.writestr('meta.json', json.dumps(_backup_meta(), ensure_ascii=False, indent=2))
        for root, _dirs, files in os.walk(UPLOAD_DIR):
            for fn in files:
                full = os.path.join(root, fn)
                zf.write(full, os.path.join('uploads', os.path.relpath(full, UPLOAD_DIR)))
    os.remove(tmp_db)
    return fname


@app.route('/api/backup/create', methods=['POST'])
@login_required
def backup_create():
    """一键备份：app.db + uploads 素材 + 配置/版本元信息 -> zip（文件名带日期）"""
    try:
        fname = _create_backup_archive()
        fpath = os.path.join(BACKUP_DIR, fname)
        return jsonify({'ok': True, 'file': fname, 'path': fpath,
                        'meta': _backup_meta()})
    except Exception as e:
        return jsonify({'error': '备份失败：' + str(e)}), 500


@app.route('/api/backup/list', methods=['GET'])
@login_required
def backup_list():
    out = []
    for fn in sorted(os.listdir(BACKUP_DIR)):
        if fn.startswith('backup_') and fn.endswith('.zip') and fn != '_tmp_':
            fp = os.path.join(BACKUP_DIR, fn)
            out.append({'file': fn, 'size': os.path.getsize(fp),
                        'mtime': datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M:%S')})
    out.reverse()
    return jsonify(out)


@app.route('/api/backup/download/<path:name>')
@login_required
def backup_download(name):
    """下载备份 zip（仅允许 backups 目录内 backup_*.zip）"""
    safe = os.path.basename(name)
    fp = os.path.join(BACKUP_DIR, safe)
    if not (safe.startswith('backup_') and safe.endswith('.zip') and os.path.exists(fp)):
        return jsonify({'error': '备份文件不存在'}), 404
    return send_from_directory(BACKUP_DIR, safe, as_attachment=True, download_name=safe)


@app.route('/api/backup/restore', methods=['POST'])
@login_required
def backup_restore():
    """Validate and stage first; preserve a complete undo archive and roll back on failure."""
    from pathlib import Path
    from contextlib import closing
    upload = request.files.get('file')
    if not upload or not (upload.filename or '').lower().endswith('.zip'):
        return jsonify({'error': '请选择 .zip 备份文件'}), 400
    safety = None
    with tempfile.TemporaryDirectory(prefix='restore_', dir=BACKUP_DIR) as work:
        archive = Path(work) / 'incoming.zip'
        upload.save(str(archive))
        staged = Path(work) / 'staged'; staged.mkdir()
        try:
            with zipfile.ZipFile(archive) as z:
                entries = z.infolist()
                if len(entries) > 20000 or sum(i.file_size for i in entries) > 512 * 1024 * 1024:
                    raise ValueError('备份解压后太大')
                for item in entries:
                    name = item.filename.replace('\\', '/')
                    if name not in ('app.db', 'meta.json') and not name.startswith('uploads/'):
                        raise ValueError('备份含有不支持的文件')
                    target = (staged / name).resolve()
                    if staged.resolve() not in target.parents:
                        raise ValueError('备份包含不安全的路径')
                    if (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError('备份包含不支持的链接文件')
                z.extractall(staged)
            incoming = staged / 'app.db'
            if not incoming.is_file(): raise ValueError('备份缺少数据库')
            with closing(sqlite3.connect(str(incoming))) as check:
                if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('数据库损坏')
                required = {'site_config', 'products', 'sections', 'pages', 'contacts', 'banner'}
                tables = {x[0] for x in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not required <= tables: raise ValueError('不是完整的 ChatFLOW 备份')
            safety = _create_backup_archive()
            with closing(sqlite3.connect(str(incoming))) as src, closing(sqlite3.connect(DB_PATH)) as dst:
                src.backup(dst)
            init_db()  # Migrate backups from previous supported versions.
            new_uploads = staged / 'uploads'; new_uploads.mkdir(exist_ok=True)
            old_uploads = Path(work) / 'old_uploads'
            os.replace(UPLOAD_DIR, str(old_uploads))
            try: os.replace(str(new_uploads), UPLOAD_DIR)
            except Exception:
                os.replace(str(old_uploads), UPLOAD_DIR)
                raise
            return jsonify({'ok': True, 'msg': '已还原。操作前的完整备份保存在备份记录中。', 'pre_backup': safety})
        except Exception as error:
            if safety:
                # Restore the original DB if applying the incoming archive failed.
                with zipfile.ZipFile(os.path.join(BACKUP_DIR, safety)) as z:
                    original = Path(work) / 'original.db'; original.write_bytes(z.read('app.db'))
                with closing(sqlite3.connect(str(original))) as src, closing(sqlite3.connect(DB_PATH)) as dst:
                    src.backup(dst)
            return jsonify({'error': '还原未完成，原数据已保留：' + str(error)}), 400


# ---------------- 平台风格 / 多语言 / 询盘 / 教程 / 统计 ----------------

@app.route('/api/detail_layouts')
@login_required
def api_detail_layouts():
    """返回详情页平台风格列表（供产品表单下拉与预览）"""
    return jsonify(detail_layouts())


@app.route('/api/languages')
@login_required
def api_languages():
    """返回支持的语言列表（含本地名称）"""
    return jsonify([{'id': lang, 'name': t(lang, 'lang_name', lang)} for lang in i18n_languages()])


@app.route('/api/inquiry', methods=['POST', 'OPTIONS'])
@cors_allow_any
def api_inquiry():
    """站点前台询盘表单提交（无需登录）"""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    country = (data.get('country') or '').strip()
    message = (data.get('message') or '').strip()
    whatsapp = (data.get('whatsapp') or '').strip()
    wechat = (data.get('wechat') or '').strip()
    product_id = data.get('product_id')
    product_name = (data.get('product_name') or '').strip()
    if not name:
        return jsonify({'error': 'missing_name'}), 400
    if not (email or whatsapp or wechat):
        return jsonify({'error': 'missing_contact'}), 400
    if len(name) > 200 or len(email) > 200 or len(country) > 100 or len(message) > 5000 \
            or len(whatsapp) > 100 or len(wechat) > 100:
        return jsonify({'error': 'too_long'}), 400
    try:
        save_inquiry(name, email, country, message, product_id, product_name, whatsapp, wechat)
    except Exception:
        return jsonify({'error': 'db'}), 500
    return jsonify({'ok': True})


@app.route('/api/inquiries', methods=['GET'])
@login_required
def api_inquiries():
    """后台询盘管理列表"""
    return jsonify(get_inquiries())


@app.route('/api/inquiries/<int:iid>', methods=['DELETE'])
@login_required
def api_inquiries_delete(iid):
    """后台删除询盘"""
    if not delete_inquiry(iid):
        return jsonify({'error': '记录不存在'}), 404
    return jsonify({'ok': True})


@app.route('/api/tutorial')
@login_required
def api_tutorial():
    """新手注册教程内容"""
    return jsonify(tutorial_content())


@app.route('/api/stats')
@login_required
def api_stats():
    """站点基础统计面板"""
    return jsonify(site_stats())


# ---------------- 站点生成 ----------------

from site_builder import (build_site_html, build_product_page_html,
                          build_contact_page_html, build_page_html,
                          build_faq_page_html,
                          generate_site_files, esc, site_img, contact_href,
                          get_sections, get_pages, get_friend_links,
                          SECTION_TYPES, SECTION_TYPE_IDS,
                          company_info, seo_site,
                          save_version, restore_version,
                          detail_layouts, i18n_languages, t,
                          get_inquiries, save_inquiry, delete_inquiry,
                          tutorial_content, site_stats,
                          product_images, PAY_BRANDS, pay_icon_files)


@app.route('/api/pay_brands')
@login_required
def api_pay_brands():
    """返回支付渠道品牌色表（后台行预览用，单源在后端 PAY_BRANDS）"""
    return jsonify(PAY_BRANDS)


@app.route('/api/pay_icons')
@login_required
def api_pay_icons():
    """返回系统内置真实品牌 logo SVG 清单（渠道 id -> 'pay_icons/xxx.svg' 相对路径，
    后台预览拼 /static/ 前缀，前台生成站复制到 output_site/static/pay_icons/ 后同路径加载，
    单源在 static/pay_icons/ 目录，禁止自绘徽章冒充官方 logo）。"""
    return jsonify(pay_icon_files())


@app.route('/api/preview_product')
@login_required
def preview_product():
    """预览单个产品详情页（带模板样式）"""
    pid = request.args.get('pid', type=int)
    site_name = request.args.get('site_name', 'My Export Site')
    template = request.args.get('template') or get_config('site_template', 'business')
    if template not in {t['id'] for t in TEMPLATES}:
        template = 'business'
    conn = get_db()
    p = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    conn.close()
    if not p:
        return '产品不存在', 404
    page_html = build_product_page_html(p, site_name, img_prefix='/uploads/', page='preview', template_id=template)
    return page_html.replace('<link rel="stylesheet" href="style.css">',
                             '<style>' + build_css(template) + '</style>')


@app.route('/api/preview_contact')
@login_required
def preview_contact():
    """预览联系我们页（带模板样式，与部署后一致）"""
    site_name = request.args.get('site_name', 'My Export Site')
    template = request.args.get('template') or get_config('site_template', 'business')
    if template not in {t['id'] for t in TEMPLATES}:
        template = 'business'
    page_html = build_contact_page_html(site_name, img_prefix='/uploads/', page='preview', template_id=template)
    return page_html.replace('<link rel="stylesheet" href="style.css">',
                             '<style>' + build_css(template) + '</style>')


@app.route('/api/preview_page')
@login_required
def preview_page():
    """预览自定义页面（About/FAQ 等）"""
    slug = request.args.get('slug', '')
    site_name = request.args.get('site_name', 'My Export Site')
    template = request.args.get('template') or get_config('site_template', 'business')
    if template not in {t['id'] for t in TEMPLATES}:
        template = 'business'
    conn = get_db()
    pg = conn.execute('SELECT * FROM pages WHERE slug=? AND enabled=1', (slug,)).fetchone()
    conn.close()
    if not pg:
        return '页面不存在', 404
    page_html = build_page_html(dict(pg), site_name, img_prefix='/uploads/', page='preview', template_id=template)
    return page_html.replace('<link rel="stylesheet" href="style.css">',
                             '<style>' + build_css(template) + '</style>')


@app.route('/api/preview_faq')
@login_required
def preview_faq():
    """预览 FAQ 独立页（数据源：板块化建站 FAQ 板块；板块停用时 404/不展示）"""
    site_name = request.args.get('site_name', 'My Export Site')
    template = request.args.get('template') or get_config('site_template', 'business')
    if template not in {t['id'] for t in TEMPLATES}:
        template = 'business'
    page_html = build_faq_page_html(site_name, img_prefix='/uploads/', page='preview', template_id=template)
    if not page_html:
        return 'FAQ 板块未启用，暂无可预览的 FAQ 页面', 404
    return page_html.replace('<link rel="stylesheet" href="style.css">',
                             '<style>' + build_css(template) + '</style>')


@app.route('/api/preview')
@login_required
def preview():
    site_name = request.args.get('site_name', 'My Export Site')
    template = request.args.get('template') or get_config('site_template', 'business')
    if template not in {t['id'] for t in TEMPLATES}:
        template = 'business'
    page_html = build_site_html(site_name, img_prefix='/uploads/', page='preview', template_id=template)
    # 预览时内嵌模板样式，避免 style.css 相对路径 404
    return page_html.replace('<link rel="stylesheet" href="style.css">',
                             '<style>' + build_css(template) + '</style>')


@app.route('/api/generate', methods=['POST'])
@login_required
def generate():
    data = request.get_json(silent=True) or {}
    site_name = (data.get('site_name') or 'My Export Site').strip()
    template = (data.get('template') or get_config('site_template', 'business')).strip()
    if template not in {t['id'] for t in TEMPLATES}:
        return jsonify({'error': '模板不存在'}), 400
    repo = str(data.get('repo') or '').strip()
    if repo:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', repo):
            return jsonify({'error': '仓库名格式不正确'}), 400
        user = session.get('github_user', '')
        current_url = (get_config('site_url', '') or '').strip()
        from urllib.parse import urlsplit
        current_host = (urlsplit(current_url).hostname or '').lower()
        # A GitHub Pages address follows the selected repository. Preserve a
        # separately configured custom domain instead of replacing it.
        if not current_url or current_host == (user + '.github.io').lower():
            set_config('site_url', 'https://%s.github.io%s' % (user, '' if repo.lower() == (user + '.github.io').lower() else '/' + repo))
    set_config('site_name', site_name)
    try:
        copied, detail_count, tpl_id, tpl_name, page_count = generate_site_files(site_name, template)
        return jsonify({'ok': True, 'copied': copied, 'detail_pages': detail_count,
                        'custom_pages': page_count,
                        'template': tpl_id, 'template_name': tpl_name, 'output_dir': OUTPUT_DIR})
    except Exception as e:
        return jsonify({'error': '生成失败：' + str(e)}), 500


# ---------------- 自动部署 ----------------

def _discover_git():
    """定位可用的 git 可执行文件，且不依赖调用方进程的 PATH。

    背景（Windows 特有坑）：打包后的 ChatFLOW.exe 直接
    subprocess.run(["git", ...]) 时，Windows 的 CreateProcess 只会在【父进程
    （ChatFLOW.exe）启动时的 PATH】里查找 "git"。若系统没装 Git for Windows、
    也没随包捆绑便携 Git，就会抛 FileNotFoundError [WinError 2]（系统找不到指定的文件）。
    干净的 Windows 不像 macOS/Linux 预装 Git，所以这个错在任意未装 Git 的 Win 电脑上 100% 复现。

    解决：部署功能【自带便携 Git】，并在调用前用【绝对路径】拉起 git（绝对路径不走
    PATH 查找），同时把 git 所在目录补进子进程 PATH（供 git 自身拉起内部 helper/ssh）。

    查找顺序：
      1) 随包捆绑的便携 Git（onedir 在 exe 同目录 / _internal；onefile 在 _MEIPASS）
      2) 当前 PATH 中的 git（shutil.which）
      3) Git for Windows 常见安装路径
    返回 git.exe 绝对路径；都找不到返回 None。
    """
    import shutil as _shutil
    candidates = []
    # 1) 随包捆绑的便携 Git
    try:
        _base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(sys.executable))
    except Exception:
        _base = os.path.dirname(os.path.abspath(sys.executable))
    for _rel in ('PortableGit/cmd/git.exe', 'PortableGit/bin/git.exe',
                 '_internal/PortableGit/cmd/git.exe', '_internal/PortableGit/bin/git.exe'):
        candidates.append(os.path.join(_base, _rel))
    # 2) 当前 PATH
    _gw = _shutil.which('git')
    if _gw:
        candidates.append(_gw)
    # 3) Git for Windows 常见安装路径
    for _bd in (os.environ.get('LOCALAPPDATA', ''), r'C:\Program Files', r'C:\Program Files (x86)'):
        if not _bd or not os.path.isdir(_bd):
            continue
        for _sub in ('Git/cmd/git.exe', 'Git/bin/git.exe', 'Git/mingw64/bin/git.exe',
                    'Programs/Git/cmd/git.exe'):
            candidates.append(os.path.join(_bd, _sub))
    _seen = set()
    for _c in candidates:
        _cp = os.path.abspath(_c)
        if _cp in _seen:
            continue
        _seen.add(_cp)
        if os.path.isfile(_cp):
            return _cp
    return None


def run_git(site_dir, *args, timeout=120, auth_token=''):
    """Token only travels in the child environment, never in URLs, arguments or logs.

    git 可执行文件通过 _discover_git() 用【绝对路径】拉起，彻底规避 Windows
    CreateProcess 只在父进程启动 PATH 中查找 "git" 的坑；并把 git 所在目录
    （及 mingw64/bin、bin）补进子进程 PATH，供 git 内部 helper/ssh 解析使用。
    若完全找不到 git，抛出带中文指引的清晰错误，而不是直接抛生硬的 FileNotFoundError。
    """
    import base64
    git_bin = _discover_git()
    if not git_bin:
        raise RuntimeError(
            '本机未找到 Git 可执行文件（git.exe）。ChatFLOW 的「一键部署」依赖 Git，'
            '而当前系统 PATH 中没有，也未按预期捆绑便携 Git。'
            '请在 Windows 上安装 Git for Windows（https://git-scm.com/download/win）后重试，'
            '或使用随包自带的启动方式打开本软件。')
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    # 把 git 所在目录（及 mingw64/bin、bin）补进子进程 PATH，
    # 否则 git 拉起内部 helper（ssh / credential 等）会找不到依赖。
    _git_dir = os.path.dirname(git_bin)
    _git_root = os.path.dirname(_git_dir)
    for _p in (_git_dir, os.path.join(_git_root, 'bin'), os.path.join(_git_root, 'mingw64', 'bin')):
        if os.path.isdir(_p) and _p not in env.get('PATH', '').split(os.pathsep):
            env['PATH'] = _p + os.pathsep + env.get('PATH', '')
    if auth_token:
        credential = base64.b64encode(('x-access-token:' + auth_token).encode()).decode()
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
                   GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + credential)
    return subprocess.run([git_bin, '-c', 'http.sslVerify=true'] + list(args), cwd=site_dir,
                          capture_output=True, text=True, timeout=timeout, env=env)


def _gh_api(url, token, method='GET', payload=None, timeout=30):
    """调用 GitHub API，返回 (ok, data_or_error_msg)。

    稳健性（彻底修复「部署出错：IncompleteRead」——代理把响应截断到一半）：
    - 优先用 curl 子进程：curl 自带 --retry/--retry-all-errors，对「连接被代理
      截断的半包」会自动重传，比 Python urllib 抗代理得多（urllib 一旦读到
      Content-Length 与实际字节不符就直接抛 IncompleteRead，且不会自动重传）。
    - 多次重试 + 退避；加 Connection: close 禁 keep-alive 规避半包截断。
    - curl 不可用时回退 urllib（同样捕获 IncompleteRead/HTTPException 并重试）。
    - 错误以 'HTTP <code>: <msg>' 文本返回，调用方仍可靠 '404'/'409' 等子串判断。
    """
    import subprocess, tempfile, os, json, time, http.client

    # —— 路径 1：curl（首选，抗代理截断）——
    try:
        probe = subprocess.run(['curl', '--retry-all-errors', '--version'], capture_output=True, timeout=10)
        supports_retry_all = probe.returncode == 0
        old_curl = (b'--retry-all-errors' in probe.stderr and b'unknown' in probe.stderr.lower())
        use_curl = supports_retry_all or old_curl
    except Exception:
        use_curl = False

    if use_curl:
        cmd = [
            'curl', '-sS', '-L',
            '--retry', '6', '--retry-delay', '1', '--retry-max-time', '180',
            '--connect-timeout', '20', '--max-time', str(timeout + 120),
            '-H', 'Authorization: token %s' % token,
            '-H', 'Accept: application/vnd.github+json',
            '-H', 'Connection: close',
            '-X', method,
            '-w', '\n%{http_code}',
            url,
        ]
        if supports_retry_all:
            cmd.insert(5, '--retry-all-errors')
        tf = None
        if payload is not None:
            data = json.dumps(payload)
            tf = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
            tf.write(data)
            tf.close()
            cmd += ['-H', 'Content-Type: application/json', '--data-binary', '@' + tf.name]
        last_err = '网络错误'
        for attempt in range(4):
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=timeout + 200, env=dict(os.environ))
                raw = r.stdout.decode('utf-8', 'ignore')
                body, _, code = raw.rpartition('\n')
                code = code.strip()
                if r.returncode != 0:
                    last_err = 'curl 失败(%s): %s' % (r.returncode, r.stderr.decode('utf-8', 'ignore')[:200])
                elif not code.isdigit():
                    last_err = '无法解析 HTTP 状态码'
                elif 200 <= int(code) < 300:
                    try:
                        return True, (json.loads(body) if body.strip() else {})
                    except Exception:
                        return True, body
                else:
                    msg = ''
                    try:
                        j = json.loads(body) if body.strip() else {}
                        msg = j.get('message', body[:200])
                    except Exception:
                        msg = body[:200]
                    if code in ('429', '500', '502', '503', '504'):
                        last_err = 'HTTP %s: %s' % (code, msg)  # 可重试
                    else:
                        return False, 'HTTP %s: %s' % (code, msg)
            except subprocess.TimeoutExpired:
                last_err = '网络超时'
            except Exception as e:
                last_err = str(e)
            if attempt < 3:
                time.sleep(min(1.0 * (attempt + 1), 5))
        if tf:
            try:
                os.unlink(tf.name)
            except Exception:
                pass
        return False, last_err

    # —— 路径 2：urllib 兜底（curl 不可用时的兼容路径）——
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, method=method)
    req.add_header('Authorization', 'token %s' % token)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Connection', 'close')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    openers = [None, urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                urllib.request.HTTPSHandler(context=_SSL_CTX))]
    last_err = '网络错误'
    for attempt in range(3):
        for opener in openers:
            try:
                call = (lambda: opener.open(req, timeout=timeout)) if opener is not None else \
                       (lambda: urlopen(req, timeout=timeout, context=_SSL_CTX))
                with call() as resp:
                    body = resp.read().decode('utf-8', 'ignore')
                    return True, json.loads(body) if body else {}
            except HTTPError as e:
                body = e.read().decode('utf-8', 'ignore')[:300]
                if e.code in (429, 500, 502, 503, 504):
                    last_err = 'HTTP %s: %s' % (e.code, body)
                    break
                return False, 'HTTP %s: %s' % (e.code, body)
            except (URLError, http.client.IncompleteRead, http.client.HTTPException) as e:
                last_err = '网络错误: %s' % (getattr(e, 'reason', None) or e)
                continue
            except Exception as e:
                last_err = str(e)
                continue
        if attempt < 2:
            time.sleep(min(1.0 * (attempt + 1), 4))
    return False, last_err


def _github_reachable(timeout=8):
    """显式探测 api.github.com 是否可达（联网 / VPN 是否就绪）。
    这是离线登录防护的第一道闸：不可达时直接拒绝，绝不静默放行。"""
    try:
        req = Request('https://api.github.com', method='GET')
        with urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            return getattr(resp, 'status', 0) < 500
    except Exception:
        return False


def _validate_github_creds(username, token):
    """登录严格校验：必须能连 GitHub 且 token 有效、用户名与 token 账号一致才放行。
    不再「连不上就静默放行」——否则任意账号密码都能进，客户会持续质疑。
    离线 / 无 VPN 时显式拒绝并提示联网，绝不允许任意账号登录。"""
    # 第一道闸：显式探测 GitHub 是否可达。不可达直接拒绝，避免任何误放行。
    if not _github_reachable():
        return False, '无法连接 GitHub（本机网络访问不到 api.github.com）。请先联网，或开启 VPN/代理后再登录。软件必须联网校验账号，离线状态不允许登录。'
    try:
        ok, data = _gh_api('https://api.github.com/user', token, timeout=10)
    except Exception as e:
        return False, '无法连接 GitHub（%s）。请确认本机网络可访问 api.github.com，或在能联网的环境下重试。' % str(e)[:80]
    if not ok:
        msg = str(data)
        if '401' in msg:
            return False, 'GitHub Token 无效或已过期，请在 GitHub 重新生成 Token（需 repo 权限）'
        if '403' in msg:
            return False, 'GitHub 拒绝了该 Token（可能权限不足或触发接口限流），请确认 Token 有效且未超限'
        return False, 'GitHub 校验未通过：%s' % msg[:120]
    login = (data.get('login') or '').lower() if isinstance(data, dict) else ''
    if not login:
        return False, 'GitHub 返回的账号信息异常，请重试'
    if login != username.lower():
        return False, 'Token 对应的 GitHub 账号是「%s」，与输入的用户名「%s」不匹配' % (login, username)
    return True, None


def ensure_github_repo(user, token, repo):
    """确保 GitHub 仓库存在，不存在则自动创建（个人仓库）。

    返回 (ok, msg, fatal)：
    - fatal=True  → 硬性错误（Token 无效/无权限），必须中止部署并提示用户。
    - fatal=False → 只是网络抖动探测不到（代理截断等）；不应阻塞部署，
      直接交给后面的 git push 去上传（git 自带稳健传输，会自行鉴权）。
    """
    ok, data = _gh_api('https://api.github.com/repos/%s/%s' % (user, repo), token)
    if ok:
        return True, '仓库已存在', False
    msg = str(data)
    if '401' in msg or '403' in msg:
        return False, 'GitHub Token 无效或无权限（%s）' % msg[:120], True
    if '404' in msg:
        ok2, data2 = _gh_api(
            'https://api.github.com/user/repos', token, method='POST',
            payload={'name': repo, 'private': False, 'description': '外贸网站'})
        if ok2:
            return True, '仓库不存在，已自动创建', False
        m2 = str(data2)
        if '401' in m2 or '403' in m2:
            return False, 'Token 无创建仓库权限（%s）' % m2[:120], True
        # 创建失败但原因不明（多为网络）→ 不阻塞，git push 仍可能成功
        return True, '仓库探测失败（网络），将直接尝试推送', False
    # 其他网络错误 → 不阻塞部署
    return True, '仓库探测失败（网络），将直接尝试推送', False


def enable_github_pages(user, token, repo):
    """通过 GitHub API 自动启用 Pages，无需手动去 Settings 开启。返回 (ok, msg)"""
    ok, data = _gh_api(
        'https://api.github.com/repos/%s/%s/pages' % (user, repo), token, method='POST',
        payload={'source': {'branch': 'main', 'path': '/'}})
    if ok:
        return True, 'GitHub Pages 已自动启用'
    if isinstance(data, str) and '409' in data:
        return True, 'GitHub Pages 已启用'
    if isinstance(data, str) and '404' in data:
        return False, '启用 Pages 失败：仓库或 Token 权限不足（404）'
    return False, '启用 Pages 失败：' + str(data)[:200]


@app.route('/api/deploy', methods=['POST'])
@login_required
def deploy():
    user = session.get('github_user', '')
    token = session.get('github_token', '')
    data = request.get_json(silent=True) or {}
    repo = (data.get('repo') or '').strip()
    if not repo:
        return jsonify({'error': '请填写 GitHub 仓库名'}), 400
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', repo):
        return jsonify({'error': '仓库名格式不正确：只能包含字母、数字、-、_、.，请只填写仓库名本身（如 my-export-site）'}), 400
    if not os.path.exists(os.path.join(OUTPUT_DIR, 'index.html')):
        return jsonify({'error': '网站尚未生成，请先执行「一键生成」'}), 400

    # —— 站点正式网址（自定义域名）处理 ——
    # 1) 抽域名；2) 同一域名只能绑一个仓库，重复绑定直接拦截并大白话说明；3) 部署时自动把域名写进仓库 CNAME
    site_url = (get_config('site_url', '') or '').strip()
    from urllib.parse import urlsplit
    host = urlsplit(site_url).hostname or ''
    domain = normalize_domain(site_url) if site_url and not host.endswith('.github.io') else ''
    if domain:
        bound = get_domain_binding(domain)
        if bound and bound != repo:
            # 域名已被别的仓库占用：拦截，并给出大白话解释与处理方案
            return jsonify({'error': _domain_conflict_msg(domain, bound, repo)}), 409
        # 同一仓库重部署：放行并刷新绑定（同时释放该仓库此前占用的其它域名）
        bind_domain_to_repo(domain, repo, user)

    try:
        print('[deploy] repo=%r user=%r domain=%r' % (repo, user, domain), flush=True)
        preflight = run_git(OUTPUT_DIR, '--version')
        if preflight.returncode:
            raise RuntimeError('发布组件无法启动，请重新安装完整的 ChatFLOW 修复包。')
        repo_ok, repo_msg, repo_fatal = ensure_github_repo(user, token, repo)
        if not repo_ok and repo_fatal:
            hint = ''
            if '网络' in repo_msg:
                hint = '（无法连接 GitHub：部署上线需要能访问 github.com，请确认本机已联网并可访问 GitHub，必要时使用科学上网工具后再试。）'
            return jsonify({'error': repo_msg + hint}), 500
        # 非致命（网络抖动探测不到仓库）：仍继续，交给 git push 上传
        if not repo_ok:
            print('[deploy] 仓库探测未确认（%s），继续尝试 git push' % repo_msg, flush=True)
        # 自定义域名 → 写 CNAME 文件进仓库，GitHub Pages 会自动按它绑定域名；
        # 没填域名 → 清掉历史 CNAME，回退到默认的 *.github.io 地址
        if domain:
            _write_cname(OUTPUT_DIR, domain)
        else:
            _remove_cname(OUTPUT_DIR)

        remote = 'https://github.com/%s/%s.git' % (user, repo)
        def git(*args, **kwargs):
            result = run_git(OUTPUT_DIR, *args, auth_token=token, **kwargs)
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout or 'Git 操作失败')[-600:])
            return result
        git('init')
        run_git(OUTPUT_DIR, 'remote', 'remove', 'origin')
        git('remote', 'add', 'origin', remote)
        git('branch', '-M', 'main')
        probe = git('ls-remote', '--heads', 'origin', 'main')
        overwrite = bool(probe.stdout.strip())
        # Keep the prior commit history. Refuse remote races instead of force-pushing.
        if overwrite:
            git('fetch', '--depth=1', 'origin', 'main')
            git('update-ref', 'HEAD', 'FETCH_HEAD')
        git('add', '-A')
        git('-c', 'user.name=ChatFLOW', '-c', 'user.email=export@site.local',
            'commit', '--allow-empty', '-m', 'Publish website with ChatFLOW '+APP_VERSION)
        git('push', '-u', 'origin', 'main', timeout=180)
        print('[deploy] PUSH OK', flush=True)
        pages_ok, pages_msg = enable_github_pages(user, token, repo)
        print('[deploy] pages ok=%s msg=%s' % (pages_ok, pages_msg[:80]), flush=True)
        # 每次部署生成版本快照（含模板/板块/页面/SEO 全量配置）
        try:
            site_name = data.get('site_name') or get_config('site_name', 'My Export Site')
            template = get_config('site_template', 'business')
            vid = save_version(site_name, template, note='部署上线 → %s' % repo)
        except Exception as e:
            vid = None
            print('[deploy] save version failed: %s' % e, flush=True)
        notice = ''
        if overwrite:
            notice = '已用最新内容覆盖更新仓库「%s」（仓库名不变，原访客链接 / 书签依旧有效）。' % repo
        return jsonify({
            'ok': True,
            'url': site_url or 'https://%s.github.io/%s' % (user, repo),
            'build_id': json.load(open(os.path.join(OUTPUT_DIR, 'chatflow-build.json'), encoding='utf-8'))['build_id'],
            'pages': {'ok': pages_ok, 'msg': pages_msg},
            'version_id': vid,
            'overwrite': overwrite,
            'domain': domain,
            'notice': notice,
        })
    except Exception as e:
        # 不再用统一文案掩盖真实异常：带上异常类型，并把完整堆栈写进
        # startup.log（Win=%LOCALAPPDATA%\ChatFLOW\startup.log，Mac=~/Library/...），
        # 这样部署失败时能拿到“到底是哪一步、什么错”，而不是笼统的“部署出错”。
        import traceback as _tb
        _stack = _tb.format_exc()
        try:
            _startup_log('[deploy] FAILED stage=%s\n%s' % (type(e).__name__, _stack))
        except Exception:
            pass
        print('[deploy] EXCEPTION %s: %s\n%s' % (type(e).__name__, e, _stack), flush=True)
        return jsonify({'error': '部署出错（%s）：%s' % (type(e).__name__, str(e))}), 500


def _write_cname(output_dir, domain):
    """把自定义域名写入仓库根目录的 CNAME 文件，GitHub Pages 会据此绑定域名。"""
    try:
        with open(os.path.join(output_dir, 'CNAME'), 'w', encoding='utf-8') as f:
            f.write(domain.strip() + '\n')
        print('[deploy] CNAME 已写入: %s' % domain, flush=True)
    except Exception as e:
        print('[deploy] write CNAME failed: %s' % e, flush=True)


def _remove_cname(output_dir):
    try:
        p = os.path.join(output_dir, 'CNAME')
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass


def _domain_conflict_msg(domain, bound_repo, repo):
    """域名已被别的仓库占用时，给客户的大白话说明 + 处理方案。"""
    return (
        '⚠️ 域名冲突：%s 已经绑定到仓库「%s」，一个域名只能对应一个仓库，不能重复绑定。\n\n'
        '大白话解释：域名就像门牌号，只能对应一套房子（一个仓库）。你现在想把这个门牌号也装到「%s」这套房子里，系统会乱，所以拦住了。\n\n'
        '你可以这样处理（任选其一）：\n'
        '1）换一个没用过的域名（最省事）；\n'
        '2）去 GitHub 把「%s」仓库删掉或改名，腾出这个域名后，再绑到新仓库；\n'
        '3）如果你其实只是想更新「%s」这个仓库，那就把仓库名填成「%s」重新部署，'
        '系统会直接覆盖更新（仓库名不变），不需要新域名。\n\n'
        '提示：这不需要你花钱再买域名，而是这个域名已经在别处用过了，得换一个或沿用原仓库。'
    ) % (domain, bound_repo, repo, bound_repo, bound_repo, bound_repo)


@app.route('/api/check_site', methods=['POST'])
@login_required
def check_site():
    """Verify this generated build, not merely a 200 response from an old page."""
    from urllib.parse import urlsplit
    data = request.get_json(silent=True) or {}
    url = str(data.get('url') or '').strip().rstrip('/')
    expected = str(data.get('build_id') or '')
    configured = get_config('site_url', '').rstrip('/')
    if url != configured or not url.startswith('https://') or not re.fullmatch(r'[a-f0-9]{24}', expected):
        return jsonify({'error': '请先生成并发布网站，再检查本次更新。'}), 400
    try:
        req = Request(url + '/chatflow-build.json?_cf=' + expected, headers={'Cache-Control': 'no-cache'})
        with urlopen(req, timeout=15, context=_SSL_CTX) as response:
            data = json.loads(response.read(65536))
        return jsonify({'ok': data.get('app') == 'ChatFLOW' and data.get('build_id') == expected,
                        'status': 200})
    except HTTPError as e:
        return jsonify({'ok': False, 'status': e.code})
    except Exception:
        return jsonify({'ok': False, 'status': 0, 'msg': '还未读到本次更新，稍后重试。'})


def _win_webview2_available():
    """Windows：探测 Microsoft Edge WebView2 运行时是否已安装。
    未安装时 pywebview 原生窗口会在 C 层崩溃（表现为黑框闪退、无 Python 异常可捕获），
    因此启动前先探测；缺失则上层直接走浏览器模式兜底，绝不无声崩溃。返回 (ok, detail)。"""
    try:
        import winreg
    except Exception:
        return True, 'winreg 不可用（非 Windows 或受限），跳过探测'
    clients = '{F3017226-FE2A-4295-8E18-1CDC1A1A0B68}'
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\EdgeUpdate\Clients\%s' % clients),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\%s' % clients),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\EdgeUpdate\Clients\%s' % clients),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\%s' % clients),
    ]
    for hkey, sub in keys:
        try:
            with winreg.OpenKey(hkey, sub) as k:
                pv = winreg.QueryValueEx(k, 'pv')[0]
                if pv:
                    return True, 'WebView2 运行时已安装: %s' % pv
        except OSError:
            continue
    # 兜底：检查 Evergreen 固定安装目录
    try:
        import os as _os
        for p in (r'C:\Program Files (x86)\Microsoft\EdgeWebView\Application',
                  r'C:\Program Files\Microsoft\EdgeWebView\Application'):
            if _os.path.isdir(p):
                return True, 'WebView2 目录存在: %s' % p
    except Exception:
        pass
    return False, '未检测到 WebView2 运行时'


def _win_message_box(title, message):
    """Windows 下用系统 MessageBox 弹中文提示（无控制台窗口也能看到）。失败静默。"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
    except Exception:
        pass


def _startup_log(msg):
    """启动日志（写到 DATA_DIR/startup.log，跨平台：Win=%LOCALAPPDATA%\\ChatFLOW，Mac=~/Library/Application Support/ChatFLOW）。
    即使 console=False（窗口化/无控制台），也能通过此文件取证定位"双击没反应"的根因。"""
    try:
        import datetime as _dt
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, 'startup.log'), 'a', encoding='utf-8') as f:
            f.write('%s  %s\n' % (_dt.datetime.now().isoformat(), msg))
    except Exception:
        pass


from growth_api import register_growth_routes
register_growth_routes(app, login_required)

if __name__ == '__main__':
    _login_window_check = None
    if '--self-test-deploy' in sys.argv:
        from pathlib import Path
        import native_deploy_check
        try:
            report = native_deploy_check.run(sys.modules[__name__])
        except Exception as exc:
            report = {'ok': False, 'error': str(exc), 'traceback': traceback.format_exc()}
        Path(DATA_DIR, 'self-test-deploy.json').write_text(json.dumps(report), encoding='utf-8')
        sys.exit(0 if report['ok'] else 1)

    if '--self-test-login-window' in sys.argv:
        from native_login_check import configure
        _login_window_check = configure(app, license_client, globals())
    if '--self-test-ai' in sys.argv:
        import local_ai
        from pathlib import Path
        report = {'version': APP_VERSION, 'ok': False, 'local_only': True}
        try:
            local_ai.start()
            started = time.monotonic()
            while local_ai.status()['state'] not in ('ready', 'error'):
                if time.monotonic() - started > 780:
                    raise RuntimeError('本地 AI 自检准备超时')
                time.sleep(1)
            if not local_ai.status()['ready']:
                raise RuntimeError(local_ai.status()['message'])
            value = local_ai.translate_texts({'name': '棉质衬衫', 'description': '红色，重量 250 克。'}, 'en')
            assert 'cotton' in value['name'].lower() and '250' in value['description']
            assert not re.search(r'[\u4e00-\u9fff]', ''.join(value.values()))
            report.update(ok=True, seconds=round(time.monotonic()-started, 1), model=local_ai.MODEL_NAME)
        except Exception as error:
            report['error'] = type(error).__name__ + ': ' + str(error)
        finally:
            local_ai.shutdown()
        Path(DATA_DIR, 'self-test-ai.json').write_text(json.dumps(report), encoding='utf-8')
        print(json.dumps(report), flush=True)
        sys.exit(0 if report['ok'] else 1)

    if '--self-test' in sys.argv:
        import platform
        from pathlib import Path
        generate_site_files('ChatFLOW self-test', 'business')
        import collection_tools, local_ai, promotion_tools
        from opencc import OpenCC
        assert OpenCC('s2t').convert('产品规格') == '產品規格'
        sample = collection_tools.extract_page('<script type="application/ld+json">{"@type":"Product","name":"Steel part","sku":"CF-123"}</script>', 'https://example.com/products/part')
        promoted = promotion_tools.apply_promotions('<html><body>Steel part</body></html>', {'hidden_keywords_enabled': True, 'hidden_keywords': ['steel']})
        features = sample['sku'] == 'CF-123' and 'data-cf-experiment' in promoted and len(local_ai.LANGUAGES) == 11
        assets = all(Path(BUNDLE_DIR, 'static', name).is_file() for name in ('visibility.js', 'growth_tools.js')) and Path(BUNDLE_DIR, 'templates', 'growth_tools.html').is_file()
        report = {'ok': Path(OUTPUT_DIR, 'index.html').is_file() and assets and features,
                  'collection_and_growth': features, 'local_ai_module': True,
                  'version': APP_VERSION, 'architecture': platform.machine()}
        if '--check-license-server' in sys.argv:
            reply = license_client._server_post('/version', {}, timeout=30)
            report['license_server_tls'] = bool(reply.get('ok') and reply.get('version'))
            report['ok'] = report['ok'] and report['license_server_tls']
        Path(DATA_DIR, 'self-test.json').write_text(json.dumps(report), encoding='utf-8')
        sys.exit(0 if report['ok'] else 1)

    import os as _os
    import platform
    import socket
    import threading
    import time as _t
    import webbrowser
    import urllib.request as _urllib

    def _find_free_port(start=5001, end=5020):
        """从 5001 起找一个空闲端口，避免被系统服务/残留实例占用导致后端起不来"""
        for p in range(start, end + 1):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(('127.0.0.1', p))
                s.close()
                return p
            except OSError:
                continue
        return start

    port = _find_free_port()
    url = 'http://127.0.0.1:%d' % port
    print('外贸一键建站工具已启动: %s' % url)

    # 后台启动 Flask 本地服务（原生窗口与浏览器模式都依赖它）
    flask_thread = threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()

    # 等 Flask 真正在监听后再开原生窗口，避免窗口先开后端没起导致白屏
    _ready = False
    for _i in range(50):
        try:
            _urllib.urlopen(url, timeout=1)
            _ready = True
            break
        except Exception:
            _t.sleep(0.2)
    if not _ready:
        print('警告：本地服务未能在预期时间内启动，将改用浏览器模式')

    # Readiness probes must not consume the one-time login ticket. The ticket
    # goes only to the window/browser launched by this process, never the PAT.
    url = remembered_login.launch_url(url)

    # 强制浏览器模式开关（双触发）：
    #   1) 环境变量 CF_BROWSER=1
    #   2) 数据目录下存在 force_browser 标记文件（由“浏览器模式”启动脚本创建）
    # 任何原生窗口失败 / 后端未就绪都退回浏览器模式，保证软件一定能打开
    _data_dir = DATA_DIR
    force_browser = (_os.environ.get('CF_BROWSER') == '1') or \
                    _os.path.exists(_os.path.join(_data_dir, 'force_browser'))
    _window_test = '--self-test-window' in sys.argv
    if _window_test or _login_window_check:
        force_browser = False

    # ── 跨次启动崩溃恢复（解决 Windows "双击没反应"） ──
    # 原生窗口尝试前写 native_pending 标记；如果进程 C 层硬崩溃（WebView2 运行时
    # 损坏/版本冲突等），标记不会被清除。下次启动检测到该标记 → 自动切浏览器模式。
    _pending_marker = _os.path.join(_data_dir, 'native_pending')
    if not force_browser and _os.path.exists(_pending_marker):
        try:
            _os.remove(_pending_marker)
            force_browser = True
            _startup_log('CRASH-RECOVERY: 上次原生窗口异常退出(未清除native_pending)，本次自动切浏览器模式')
            _win_message_box('ChatFLOW 建站系统',
                '上次启动原生窗口时发生异常退出（可能 Edge WebView2 运行时问题）。\n\n'
                '本次已自动改用浏览器模式打开，功能完全一致。\n\n'
                '日志: %LOCALAPPDATA%\\ChatFLOW\\startup.log')
        except Exception:
            pass

    _startup_log('=== ChatFLOW v%s 启动 ===' % APP_VERSION)
    _startup_log('数据目录: %s' % _data_dir)
    _startup_log('端口: %d' % port)
    _startup_log('force_browser=%s  flask_ready=%s' % (force_browser, _ready))

    # Windows：启动前探测 Edge WebView2 运行时。缺失会导致原生窗口 C 层崩溃（黑框闪退），
    # 故直接切浏览器模式并弹大白话提示，保证软件一定能打开。
    if not force_browser and platform.system() == 'Windows':
        _wv_ok, _wv_detail = _win_webview2_available()
        print('[startup] WebView2 探测: %s' % _wv_detail)
        _startup_log('WebView2 探测: ok=%s  %s' % (_wv_ok, _wv_detail))
        if not _wv_ok:
            force_browser = True
            _msg = ('未检测到 Microsoft Edge WebView2 运行时，无法使用原生窗口。\n\n'
                    '已自动改用浏览器模式打开（功能完全一致）。\n\n'
                    '如需原生窗口，请到微软官网下载安装“WebView2 Runtime”：\n'
                    'https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/')
            print('[startup] %s' % _msg)
            _win_message_box('ChatFLOW 建站系统', _msg)

    def _browser_mode():
        import subprocess as _sp
        _opened = False
        # CF_NO_OPEN=1 时由外部启动器负责开浏览器（macOS 原生 open 更可靠，避免首次静默失败）
        if _os.environ.get('CF_NO_OPEN') != '1':
            for _attempt in range(5):
                try:
                    if _attempt == 0:
                        if not webbrowser.open(url):
                            raise RuntimeError('系统浏览器没有接受打开请求')
                    else:
                        if platform.system() == 'Darwin':
                            _sp.run(['open', url], check=True)
                        elif not webbrowser.open(url):
                            raise RuntimeError('系统浏览器没有接受打开请求')
                    _opened = True
                    break
                except Exception as e:
                    print('浏览器打开失败(重试 %d): %s' % (_attempt + 1, e))
                    _t.sleep(1.5)
        if not _opened:
            print('浏览器未能自动打开，请手动访问: %s' % url)
        # 保持本地服务运行，直到手动退出
        try:
            while True:
                _t.sleep(3600)
        except KeyboardInterrupt:
            pass

    if force_browser or not _ready:
        _startup_log('进入浏览器模式 (force_browser=%s, ready=%s)' % (force_browser, _ready))
        print('使用浏览器模式打开: %s' % url)
        threading.Timer(1.0, _browser_mode).start()
        try:
            while True:
                _t.sleep(3600)
        except KeyboardInterrupt:
            pass
    else:
        _startup_log('进入原生窗口模式')
        # 优先用原生窗口（Mac=系统 WKWebView，不弹系统浏览器，像真软件）
        # 关键修复（M 芯片"需打开两次"问题）：Cocoa 事件循环必须在【主线程】跑。
        # 旧实现把 webview.create_window 丢到子线程，Apple Silicon 上首次启动窗口
        # 不被系统激活/不提到前台，表现为"打开→强退→再打开才好用"。
        # 主线程创建窗口后，必须调用 webview.start 运行 GUI 事件循环；
        # 另起一个守护线程在窗口起来后反复尝试激活 App，确保首次启动就提到前台。
        # 任何异常都回退浏览器模式，绝不回归"双击没反应"。
        # 写入"原生窗口尝试中"标记：如果进程 C 层硬崩溃，标记不会被清除，
        # 下次启动检测到后自动切浏览器模式（见上方 CRASH-RECOVERY）。
        try:
            open(_pending_marker, 'w').close()
            _startup_log('写入 native_pending，开始原生窗口')
        except Exception:
            pass
        try:
            import webview
            import platform
            # macOS 首启「窗口不弹到前台 / 需关了再打开一次」根因：
            # NSApp.activateIgnoringOtherApps_ 这类 Cocoa UI 调用【必须在主线程】执行。
            # 旧实现把它丢进后台线程（且 pywebview 的 start(func) 也是后台线程跑 func），
            # 等于从未在主线程激活，所以首启窗口不提到前台，关了再开才好用。
            # 正确做法：用 PyObjCTools.AppHelper.callAfter 把激活逻辑排进【主线程的事件循环】
            # （主线程正被 pywebview 的 Cocoa 事件循环占着，callAfter 会在其内于主线程触发）。
            if platform.system() == 'Darwin':
                try:
                    from AppKit import NSApp, NSApplicationActivationPolicyRegular
                    from PyObjCTools import AppHelper
                    def _bring_front():
                        try:
                            _a = NSApp()
                            if _a is not None:
                                try:
                                    _a.setActivationPolicy_(NSApplicationActivationPolicyRegular)
                                except Exception:
                                    pass
                                _a.activateIgnoringOtherApps_(True)
                        except Exception:
                            pass
                    AppHelper.callAfter(_bring_front)
                except Exception:
                    pass
            # create_window 只登记窗口；start 才显示窗口并保持本地服务运行。
            _window = webview.create_window('ChatFLOW '+APP_VERSION+' 建站系统', url, width=1280, height=800)
            _window.events.shown += lambda: _startup_log('原生窗口已显示')
            _window.events.loaded += lambda: _startup_log('原生窗口页面已加载')
            def _check_window():
                from pathlib import Path
                report = {'ok': False, 'version': APP_VERSION, 'architecture': platform.machine()}
                try:
                    shown = _window.events.shown.wait(30)
                    loaded = _window.events.loaded.wait(30)
                    health = json.loads(_urllib.urlopen(url + '/api/health', timeout=5).read())
                    report.update(shown=bool(shown), loaded=bool(loaded), health=health,
                                  ok=bool(shown and loaded and health.get('app') == 'ChatFLOW' and health.get('version') == APP_VERSION))
                except Exception as error:
                    report['error'] = str(error)
                finally:
                    Path(DATA_DIR, 'self-test-window.json').write_text(json.dumps(report), encoding='utf-8')
                    _window.destroy()
            webview.start(_check_window if _window_test else (lambda: _login_window_check(_window)) if _login_window_check else None)
            if _window_test:
                from pathlib import Path
                report = json.loads(Path(DATA_DIR, 'self-test-window.json').read_text(encoding='utf-8'))
                sys.exit(0 if report['ok'] else 1)
            # 原生窗口正常关闭（用户点了 X），清除 pending 标记
            try:
                if _os.path.exists(_pending_marker):
                    _os.remove(_pending_marker)
                    _startup_log('原生窗口正常关闭，已清除 native_pending')
            except Exception:
                pass
            if _login_window_check:
                from pathlib import Path
                _result = json.loads(Path(DATA_DIR, 'login-' + os.environ['CF_LOGIN_CHECK_PHASE'] + '.json').read_text(encoding='utf-8'))
                sys.exit(0 if _result['ok'] else 1)
        except Exception as e:
            _startup_log('原生窗口失败(可捕获): %s' % e)
            if _window_test or _login_window_check:
                raise
            print('原生窗口失败，改用浏览器模式: %s' % e)
            # 清除 pending（这次是可捕获异常，不是硬崩溃）
            try:
                if _os.path.exists(_pending_marker):
                    _os.remove(_pending_marker)
            except Exception:
                pass
            if platform.system() == 'Windows':
                _win_message_box('ChatFLOW 建站系统',
                    '原生窗口启动失败，已自动改用浏览器模式打开。\n\n'
                    '功能完全一致。错误详情见:\n%LOCALAPPDATA%\\ChatFLOW\\startup.log')
            _browser_mode()
