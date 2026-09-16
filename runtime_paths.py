# -*- coding: utf-8 -*-
"""运行路径模块：兼顾「源码运行」和「打包后运行（PyInstaller exe/dmg）」

- 源码运行：一切照旧，数据都在源码目录（instance / static/uploads / output_site / backups）
- 打包运行：
    * 程序本体的只读资源（内置模板、图标、字体等）在 BUNDLE_DIR（解包临时目录）
    * 需要写入的数据（数据库、上传图片、生成站点、备份、授权缓存）统一放 DATA_DIR
      Windows:  %LOCALAPPDATA%\\ChatFLOW
      macOS:    ~/Library/Application Support/ChatFLOW
      Linux:    ~/.local/share/ChatFLOW
  这样客户不需要管理员权限，重装/升级软件也不丢数据。
"""
import os
import sys


def is_frozen():
    """是否处于 PyInstaller 打包运行状态"""
    return getattr(sys, 'frozen', False)


# 程序只读资源目录：源码运行=源码目录；打包后=解包临时目录
if is_frozen():
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))


def _default_data_dir():
    """打包运行时的可写数据目录"""
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~\\AppData\\Local')
        return os.path.join(base, 'ChatFLOW')
    if sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Application Support/ChatFLOW')
    base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, 'ChatFLOW')


# 可写数据目录：源码运行=源码目录（保持旧行为）；打包后=平台数据目录
DATA_DIR = os.path.abspath(os.environ.get('CF_DATA_DIR') or (BUNDLE_DIR if not is_frozen() else _default_data_dir()))


def ensure_data_dirs():
    """确保所有可写子目录存在（打包后首次运行自动创建）"""
    for sub in ('instance', os.path.join('static', 'uploads'), 'output_site', 'backups'):
        os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)


def data_path(*parts):
    """拼 DATA_DIR 下的路径"""
    return os.path.join(DATA_DIR, *parts)


def bundle_path(*parts):
    """拼 BUNDLE_DIR 下的路径（只读资源）"""
    return os.path.join(BUNDLE_DIR, *parts)
