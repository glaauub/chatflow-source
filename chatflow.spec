# -*- mode: python ; coding: utf-8 -*-
# ChatFLOW 工作室建站系统 - PyInstaller 打包配置
# 用法：pyinstaller chatflow.spec --noconfirm
# 产物：Windows → dist/ChatFLOW/ 目录（ChatFLOW.exe + 依赖，打包 zip 发客户）
#       macOS   → dist/ChatFLOW.app
#
# 原则：只打包程序本体（只读资源），不打任何数据库/用户数据。
# 客户首次打开 = 全新空系统；数据落在系统数据目录（见 runtime_paths.py）。

import sys, os

# macOS 打包目标架构：arm64（Apple Silicon）。GitHub Actions macos-latest 与本机一致。
if sys.platform == 'darwin':
    target_arch = os.environ.get('CF_ARCH', __import__('platform').machine())

datas = [
    ('instance/license_server.txt', 'instance'),
    ('templates', 'templates'),
    ('static/vendor', 'static/vendor'),
    ('static/pay_icons', 'static/pay_icons'),
    ('static/admin.css', 'static'),
    ('static/admin.js', 'static'),
    ('static/visibility.js', 'static'),
    ('static/growth_tools.js', 'static'),
    ('static/seo_help.js', 'static'),
    # macOS .app 图标：显式打进 Resources，确保 CFBundleIconFile 引用的文件存在
    ('assets/icon.icns', '.'),
    # 内置「原始模板」占位资源（logo/banner/产品/认证图）：必须打进冻结包，
    # 否则客户首次打开看到的预览站点会缺图（starter_preset._copy_assets 从
    # bundle_path('data','preset_assets') 拷贝到可写数据目录的 static/uploads）。
    ('data/preset_assets', 'data/preset_assets'),
]

from PyInstaller.utils.hooks import collect_data_files
datas += collect_data_files('opencc')

# Ship the official Visual Studio redistributable beside the downloaded AI
# engine, so a clean Windows computer does not depend on developer tools.
if sys.platform == 'win32':
    from pathlib import Path
    crt_dirs = []
    for variable in ('ProgramFiles', 'ProgramFiles(x86)'):
        base = os.environ.get(variable)
        if base:
            crt_dirs += list(Path(base, 'Microsoft Visual Studio').glob('2022/*/VC/Redist/MSVC/*/x64/Microsoft.VC143.CRT'))
    if not crt_dirs:
        raise RuntimeError('Microsoft Visual C++ x64 redistributable files were not found; refusing an incomplete AI package')
    crt_dir = sorted(crt_dirs, key=lambda p: tuple(int(x) for x in p.parents[1].name.split('.')))[-1]
    runtime_files = {p.name.lower(): p for p in crt_dir.glob('*.dll')}
    for required in ('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
        if required not in runtime_files: raise RuntimeError('Missing AI runtime: ' + required)
    datas += [(str(p), 'ai-runtime') for p in runtime_files.values()]

    # 捆绑便携 Git（MinGit），让「一键部署」在【未安装 Git for Windows】的干净
    # Windows 上也能工作。否则 subprocess.run(["git", ...]) 会抛
    # FileNotFoundError [WinError 2]。CI 在打包前会把 MinGit 下载到 PortableGit/。
    if os.path.isfile('PortableGit/cmd/git.exe') and os.path.isfile('PortableGit/mingw64/libexec/git-core/git-remote-https.exe'):
        datas.append(('PortableGit', 'PortableGit'))
        print('bundle PortableGit (self-contained deploy):', os.path.abspath('PortableGit'))
    else:
        raise RuntimeError('Missing complete PortableGit runtime; refusing to build a broken Windows package')

# 需额外收集进冻结包的二进制（Windows 下会追加 WebView2Loader.dll）
binaries = []

# 打包 certifi 的 CA 证书：PyInstaller 冻结后程序需自带根证书，否则访问
# https://api.github.com 会报 CERTIFICATE_VERIFY_FAILED（尤其 macOS）。
try:
    import certifi
    datas.append((certifi.where(), 'certifi'))
except Exception:
    pass

# 原生窗口依赖（pywebview）：macOS 用 Cocoa/WebKit，Windows 用 EdgeChromium
if sys.platform == 'darwin':
    hiddenimports = [
        'webview', 'webview.platforms', 'webview.platforms.cocoa',
        'objc', 'AppKit', 'WebKit', 'Foundation', 'PyObjCTools', 'PyObjCTools.AppHelper',
        'certifi',
    ]
else:
    hiddenimports = [
        'webview', 'webview.platforms', 'webview.platforms.edgechromium',
        'webview.lib',
        'certifi',
    ]
    # Windows：把 pywebview 自带的 WebView2Loader.dll 一并打进包，
    # 避免原生窗口因缺该 DLL 而在 C 层崩溃（黑框闪退）。
    try:
        import webview as _wv
        _loader = os.path.join(os.path.dirname(_wv.__file__), 'lib', 'WebView2Loader.dll')
        if os.path.exists(_loader):
            binaries.append((_loader, 'webview/lib'))
            print('collect WebView2Loader.dll:', _loader)
    except Exception as _e:
        print('WebView2Loader collect skipped:', _e)

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc_data'],
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='ChatFLOW',
        debug=False,
        console=False,
        icon='assets/icon.icns',
        target_arch=target_arch,
    )
    app = BUNDLE(
        exe,
        a.binaries,
        a.datas,
        name='ChatFLOW.app',
        info_plist={
            'CFBundleName': 'ChatFLOW',
            'CFBundleDisplayName': 'ChatFLOW 建站系统',
            'CFBundleIdentifier': 'com.chatflow.studio',
            'CFBundleShortVersionString': '2.1.7',
            'CFBundleIconFile': 'icon.icns',
            'NSHighResolutionCapable': True,
        },
    )
    # Apple Silicon 首次启动需"打开两次"：ad-hoc 签名让 macOS 信任 App，
    # 减少 Gatekeeper/WebKit 首次扫描导致的窗口不激活/打不开。失败也不影响打包。
    try:
        import subprocess
        _app = os.path.join('dist', 'ChatFLOW.app')
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', _app],
                       check=True, capture_output=True)
        print('ad-hoc codesign 完成:', _app)
    except Exception as _ce:
        print('codesign 跳过（不影响打包）:', _ce)
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='ChatFLOW',
        debug=False,
        console=False,
        icon='assets/icon.ico',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name='ChatFLOW',
    )
