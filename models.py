# -*- coding: utf-8 -*-
"""SQLite 数据库模型与初始化"""
import os
import sqlite3

from runtime_paths import data_path

# 源码运行=源码目录；打包运行=可写数据目录
DB_DIR = data_path('instance')
DB_PATH = os.path.join(DB_DIR, 'app.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn, table, column):
    cols = [r['name'] for r in conn.execute('PRAGMA table_info(%s)' % table).fetchall()]
    return column in cols


# ---- 内置页面模板（页面管理「新增页面」可选；同时作为空库种子） ----
PAGE_ABOUT_HTML = (
    '<p>Welcome to our company. We are a professional manufacturer and exporter, '
    'dedicated to providing high-quality products and reliable service to customers worldwide.</p>'
    '<h3>Our Mission</h3>'
    '<p>To deliver products that meet international quality standards while building long-term '
    'trust with every client.</p>'
    '<h3>Why Choose Us</h3>'
    '<ul><li>Professional production and strict quality control</li>'
    '<li>Fast response and reliable delivery</li>'
    '<li>Flexible customization and OEM/ODM support</li></ul>'
)

PAGE_FAQ_HTML = (
    '<h3>What is your minimum order quantity (MOQ)?</h3>'
    '<p>Our MOQ is flexible. For regular items, samples and small trial orders are welcome. '
    'We will confirm the details according to your requirements.</p>'
    '<h3>Can you customize products?</h3>'
    '<p>Yes, OEM and ODM services are available. Please send us your drawings or specifications '
    'and our engineers will reply within 24 hours.</p>'
    '<h3>What about delivery time?</h3>'
    '<p>For stock items, delivery takes 3-7 days. For customized production, delivery normally '
    'takes 15-30 days after confirmation of details.</p>'
    '<h3>How do you control quality?</h3>'
    '<p>We implement a complete quality control system from raw materials to finished products, '
    'and inspection reports are available upon request.</p>'
    '<h3>What is your payment term?</h3>'
    '<p>We accept T/T, PayPal, Western Union, and other payment methods. Details will be '
    'confirmed during quotation.</p>'
    '<h3>Do you provide after-sales service?</h3>'
    '<p>Yes, our team offers technical support and timely after-sales service. '
    'Any issue will be handled within 24 hours.</p>'
)


def _table_exists(conn, table):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchall()
    return len(rows) > 0


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db()
    # 全新数据库判定：仅当数据文件此前不存在任何表时才视为「全新」。
    # 还原备份 / 升级老库时也会再次调用 init_db()，此时表已存在，
    # 不应重复加载内置模板，否则会覆盖用户已备份 / 已填写的数据。
    fresh_db = not _table_exists(conn, 'site_config')
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price TEXT,
        spec TEXT,
        img TEXT,
        sku TEXT,
        model TEXT,
        stock INTEGER DEFAULT 0,
        category TEXT,
        images TEXT,
        description TEXT,
        meta_title TEXT DEFAULT '',
        meta_description TEXT DEFAULT ''
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS banner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_path TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_type TEXT NOT NULL,
        contact_value TEXT NOT NULL
    )''')
    # 站点配置表：模板选择、支付方式等 key-value 配置
    conn.execute('''CREATE TABLE IF NOT EXISTS site_config (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    # 板块化建站：预设板块库（hero/products/about/...），content 存各板块配置 JSON
    conn.execute('''CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_type TEXT NOT NULL,
        title TEXT DEFAULT '',
        content TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0
    )''')
    # 自定义页面（slug 唯一，content 为富文本 HTML，seo_* 为页面级 SEO）
    conn.execute('''CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        content TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        seo_title TEXT DEFAULT '',
        seo_description TEXT DEFAULT '',
        seo_keywords TEXT DEFAULT ''
    )''')
    # 产品分类（后台可增删改名排序；产品表 category 仍存名称文本以便前台筛选与旧数据兼容）
    conn.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        sort_order INTEGER DEFAULT 0
    )''')
    # 友情链接（蜘蛛池外链存板块 content，不在此表）
    conn.execute('''CREATE TABLE IF NOT EXISTS friend_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        nofollow INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0
    )''')
    # 版本历史快照：部署/生成时保存完整配置，支持回滚
    conn.execute('''CREATE TABLE IF NOT EXISTS versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        template TEXT DEFAULT '',
        note TEXT DEFAULT '',
        snapshot TEXT DEFAULT ''
    )''')
    # 询盘收集：详情页/联系页表单提交（B2B 询盘场景）
    conn.execute('''CREATE TABLE IF NOT EXISTS inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER DEFAULT 0,
        product_name TEXT DEFAULT '',
        name TEXT DEFAULT '',
        email TEXT DEFAULT '',
        whatsapp TEXT DEFAULT '',
        wechat TEXT DEFAULT '',
        country TEXT DEFAULT '',
        message TEXT DEFAULT '',
        created_at TEXT NOT NULL
    )''')
    # 域名→仓库绑定登记表：一个「站点正式网址（域名）」只能绑定一个 GitHub 仓库，
    # 防止客户在多个仓库重复绑定同一域名，导致 GitHub Pages 冲突 / 站点互相覆盖
    conn.execute('''CREATE TABLE IF NOT EXISTS domain_bindings (
        domain TEXT PRIMARY KEY,
        repo TEXT NOT NULL,
        gh_user TEXT DEFAULT '',
        updated_at INTEGER DEFAULT 0
    )''')
    conn.execute('CREATE TABLE IF NOT EXISTS collection_drafts (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    # 兼容旧库：products 增加新列（SKU/型号/库存/分类/多图/描述）
    for col, ddl in [
        ('catalog_data', "ALTER TABLE products ADD COLUMN catalog_data TEXT DEFAULT ''"),
        ('catalog_fingerprint', "ALTER TABLE products ADD COLUMN catalog_fingerprint TEXT DEFAULT ''"),
        ('description', 'ALTER TABLE products ADD COLUMN description TEXT'),
        ('sku', 'ALTER TABLE products ADD COLUMN sku TEXT'),
        ('model', 'ALTER TABLE products ADD COLUMN model TEXT'),
        ('stock', 'ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 0'),
        ('category', 'ALTER TABLE products ADD COLUMN category TEXT'),
        ('images', 'ALTER TABLE products ADD COLUMN images TEXT'),
        ('detail_layout', 'ALTER TABLE products ADD COLUMN detail_layout TEXT DEFAULT \'classic\''),
        ('product_video', 'ALTER TABLE products ADD COLUMN product_video TEXT DEFAULT \'\''),
        ('meta_title', 'ALTER TABLE products ADD COLUMN meta_title TEXT DEFAULT \'\''),
        ('meta_description', 'ALTER TABLE products ADD COLUMN meta_description TEXT DEFAULT \'\''),
        ('sort_order', 'ALTER TABLE products ADD COLUMN sort_order INTEGER DEFAULT 0'),
    ]:
        if not _column_exists(conn, 'products', col):
            conn.execute(ddl)
    # 兼容旧库：inquiries 增加 WhatsApp/微信列（旧库无这两列时 save_inquiry 会报错）
    if not _column_exists(conn, 'inquiries', 'whatsapp'):
        conn.execute('ALTER TABLE inquiries ADD COLUMN whatsapp TEXT DEFAULT \'\'')
    if not _column_exists(conn, 'inquiries', 'wechat'):
        conn.execute('ALTER TABLE inquiries ADD COLUMN wechat TEXT DEFAULT \'\'')
    # 默认站点配置：语言 + 部署计数
    conn.execute('INSERT OR IGNORE INTO site_config (key, value) VALUES (\'language\', \'en\')')
    conn.execute('INSERT OR IGNORE INTO site_config (key, value) VALUES (\'deploy_count\', \'0\')')
    _seed_default_sections(conn)
    # 全新数据库：自动加载内置「原始模板」，让客户打开即见完整可演示站点；
    # 仅 fresh_db（数据文件此前无表）时触发，还原备份 / 升级老库不重复加载，避免覆盖用户数据。
    if fresh_db:
        try:
            import starter_preset
            starter_preset.load_starter_preset(conn)
        except Exception:
            import traceback as _tb
            _tb.print_exc()
    # 产品排序：旧库所有 sort_order 均为 0（未编号）时，按添加先后倒序（即原前台顺序）一次性编号，
    # 保证后台「上移/下移」排序可正确交换；新添加产品 sort_order=0 会排在列表最前
    prow = conn.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
    if prow:
        zc = conn.execute('SELECT COUNT(*) AS c FROM products WHERE sort_order IS NULL OR sort_order = 0').fetchone()['c']
        if zc == prow:
            for i, r in enumerate(conn.execute('SELECT id FROM products ORDER BY id DESC').fetchall(), start=1):
                conn.execute('UPDATE products SET sort_order=? WHERE id=?', (i, r['id']))
    conn.commit()
    conn.close()


def _seed_default_sections(conn):
    """新版默认框架：9 大板块骨架（hero/products/why_us/stats/certificates/news/faq/cta/contacts）。

    仅当 sections 表为空时补入，保证「以后框架就用这一套」。板块内容为空，
    由内置「原始模板」(starter_preset) 在首次运行时填充；老库不受影响。
    """
    if _table_exists(conn, 'sections'):
        cnt = conn.execute('SELECT COUNT(*) AS c FROM sections').fetchone()['c']
        if cnt == 0:
            defaults = [
                ('hero', 'Hero Banner', '', 1, 10),
                ('products', 'Our Products', '', 1, 20),
                ('why_us', 'Why Choose YourBrand', '', 1, 30),
                ('stats', 'YourBrand by the Numbers', '', 1, 40),
                ('certificates', 'Certifications & Quality Standards', '', 1, 50),
                ('news', 'News & Industry Updates', '', 1, 60),
                ('faq', '常见问题', '', 1, 70),
                ('cta', 'Get a Wholesale Quote in 24 Hours', '', 1, 80),
                ('contacts', 'Contact Us', '', 1, 90),
            ]
            conn.executemany(
                'INSERT INTO sections (section_type, title, content, enabled, sort_order) '
                'VALUES (?, ?, ?, ?, ?)', defaults)
    if _table_exists(conn, 'pages'):
        pcnt = conn.execute('SELECT COUNT(*) AS c FROM pages').fetchone()['c']
        if pcnt == 0:
            # 内置页面模板：About Us（页面管理新增页面时可选择模板一键创建；
            # FAQ 已改为「板块化建站 FAQ」管理，由 FAQ 板块启用时自动生成前台页面）
            conn.executemany(
                "INSERT INTO pages (title, slug, content, enabled, sort_order) VALUES (?, ?, ?, ?, ?)",
                [
                    ('About Us', 'about', PAGE_ABOUT_HTML, 1, 10),
                ])


def get_config(key, default=''):
    """读取站点配置"""
    conn = get_db()
    row = conn.execute('SELECT value FROM site_config WHERE key=?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_config(key, value):
    """写入站点配置"""
    conn = get_db()
    conn.execute('INSERT INTO site_config (key, value) VALUES (?, ?) '
                 'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                 (key, '' if value is None else str(value)))
    conn.commit()
    conn.close()


def get_all_config():
    """读取全部站点配置（key-value dict）"""
    conn = get_db()
    rows = conn.execute('SELECT key, value FROM site_config').fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}


# ---- 域名→仓库绑定登记（防止同一域名绑到多个仓库）----

def normalize_domain(site_url):
    """从「站点正式网址」抽出纯域名（小写、去协议 / 端口 / 路径）。空串返回 ''。"""
    from urllib.parse import urlparse
    s = (site_url or '').strip()
    if not s:
        return ''
    if '://' not in s:
        s = 'http://' + s
    host = urlparse(s).netloc.lower()
    return host.split(':')[0]


def get_domain_binding(domain):
    """返回该域名已绑定的仓库名；未绑定返回 None。"""
    if not domain:
        return None
    conn = get_db()
    row = conn.execute('SELECT repo FROM domain_bindings WHERE domain=?', (domain,)).fetchone()
    conn.close()
    return row['repo'] if row else None


def bind_domain_to_repo(domain, repo, gh_user=''):
    """登记 / 刷新「域名→仓库」绑定。会先释放该仓库之前占用的其它域名，避免脏数据残留。"""
    if not domain:
        return
    import time as _time
    conn = get_db()
    conn.execute('DELETE FROM domain_bindings WHERE repo=? AND domain<>?', (repo, domain))
    conn.execute('INSERT OR REPLACE INTO domain_bindings (domain, repo, gh_user, updated_at) '
                 'VALUES (?,?,?,?)', (domain, repo, gh_user, int(_time.time())))
    conn.commit()
    conn.close()
