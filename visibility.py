"""Checks the actual generated pages; never estimates ranking or AI citations."""
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote


def plain_text(value):
    value = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', str(value or ''), flags=re.S | re.I)
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', value))).strip()


def valid_site_url(value):
    value = str(value or '').strip().rstrip('/')
    try:
        u = urlsplit(value)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.port:
            return ''
        if any(c.isspace() for c in value) or any(c in value for c in '<>"\\'):
            return ''
        return value
    except ValueError:
        return ''


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.title = ''; self.description = ''; self.canon = ''; self.robots = ''
        self.h1 = 0; self.images = []; self.links = []; self.ld = []; self.visible = []
        self._title = False; self._script = False; self._style = False; self._ld = False; self._buf = []
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title': self._title = True
        if tag == 'h1': self.h1 += 1
        if tag == 'meta':
            if a.get('name') == 'description': self.description = a.get('content', '')
            if a.get('name') == 'robots': self.robots = a.get('content', '')
        if tag == 'link' and a.get('rel') == 'canonical': self.canon = a.get('href', '')
        if tag == 'img': self.images.append(a)
        if tag == 'a': self.links.append(a.get('href', ''))
        if tag == 'script':
            self._script = True; self._ld = a.get('type') == 'application/ld+json'; self._buf = []
        if tag == 'style': self._style = True
    def handle_endtag(self, tag):
        if tag == 'title': self._title = False
        if tag == 'style': self._style = False
        if tag == 'script':
            if self._ld:
                try: self.ld.append(json.loads(''.join(self._buf)))
                except ValueError: self.ld.append(None)
            self._script = False; self._ld = False
    def handle_data(self, data):
        if self._title: self.title += data
        if self._ld: self._buf.append(data)
        if not self._script and not self._style: self.visible.append(data)


def write_manifest(output):
    root = Path(output)
    hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and '.git' not in p.parts and p.name != 'chatflow-build.json'}
    build_id = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:24]
    data = {'app': 'ChatFLOW', 'version': '2.1.1', 'build_id': build_id,
            'generated_at': datetime.now(timezone.utc).isoformat(), 'pages': hashes}
    (root / 'chatflow-build.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    return data


def audit_output(output, site_url=''):
    root = Path(output); files = sorted(root.glob('*.html')); issues = []
    titles = defaultdict(list); descriptions = defaultdict(list)
    def add(level, page, problem, fix):
        issues.append(dict(level=level, page=page, problem=problem, fix=fix))
    if not files: add('error', '全站', '还没有生成网站', '先保存资料，再点击“生成并检查”。')
    if valid_site_url(site_url) and urlsplit(site_url).path.strip('/'):
        add('warning', 'robots.txt', '网站在子目录，机器人规则需要放到域名根目录', '例如 GitHub 项目站：将访问规则放到账号主站根目录，或绑定独立域名。子目录文件不控制机器人访问。')
    if not valid_site_url(site_url): add('error', '全站', '没有有效的正式网址', '填写实际发布的完整 https:// 网址，才能生成正确的页面地址和网站地图。')
    for path in files:
        raw = path.read_text(encoding='utf-8'); p = Page(raw); name = path.name
        titles[p.title.strip()].append(name); descriptions[p.description.strip()].append(name)
        if not p.title.strip(): add('error', name, '缺少搜索标题', '填写页面或产品的搜索标题。')
        if not p.description.strip(): add('warning', name, '缺少搜索摘要', '用一两句话说明这页独有的内容。')
        if not p.canon or not valid_site_url(p.canon): add('error', name, '页面正式地址缺失或无效', '检查正式网址并重新生成。')
        if re.search(r'\b(noindex|none)\b', p.robots, re.I): add('error', name, '这页设置了不让搜索引擎收录', '如果想让客户搜到，请把收录设置改为允许。')
        if p.h1 != 1: add('warning', name, '页面主标题数量为 %d' % p.h1, '每页保留一个能说明内容的主标题。')
        text = ' '.join(p.visible)
        if re.search(r'\[(?:待补充|to be completed|your[^\]]*)\]|示例-请删除本行', text, re.I):
            add('warning', name, '还有示例文字或待补充内容', '换成真实资料后再发布；不要编造认证、交期或客户评价。')
        if any(not im.get('alt', '').strip() for im in p.images): add('warning', name, '部分图片没有文字说明', '为产品图片填写简短准确的说明。')
        for src in p.links + [im.get('src', '') for im in p.images]:
            u = urlsplit(src)
            if not src or u.scheme or u.netloc or src.startswith(('#', '/')): continue
            target = root / unquote(u.path)
            if u.path and not target.exists(): add('error', name, '有找不到的文件：' + u.path[:100], '重新上传缺失图片或修正页面链接。')
        if re.search(r'(?:spider-pool|block-spider-pool)', raw):
            add('warning', name, '发现旧隐藏链接池标记', '停止发布隐藏链接，把相关链接改成访客能看到的真实推荐。')
        if re.search(r'navigator\.userAgent[\s\S]{0,300}(?:Googlebot|bingbot|crawler)', raw, re.I):
            add('warning', name, '发现可能按搜索机器人改变内容的脚本', '检查是否给访客和搜索程序展示不同内容；移除操纵搜索结果的分流逻辑。')
        if re.search(r'<a\b[^>]*style=[\"\'][^\"\']*(?:display\s*:\s*none|opacity\s*:\s*0)',raw,re.I):
            add('warning', name, '发现直接隐藏的链接', '人工检查用途；正常菜单可折叠，不要用隐藏链接操纵排名。')
        if None in p.ld: add('error', name, '搜索资料格式有错误', '重新生成网站；仍然出错时导出检查结果联系支持。')
        for item in p.ld:
            if isinstance(item, dict) and item.get('@type') == 'FAQPage':
                for qa in item.get('mainEntity', []):
                    if plain_text(qa.get('name')) not in plain_text(text) or plain_text(qa.get('acceptedAnswer', {}).get('text')) not in plain_text(text):
                        add('error', name, '搜索资料里的问答在页面上看不到', '只标记访客能在当前页读到的真实问答。'); break
    for label, groups in [('搜索标题', titles), ('搜索摘要', descriptions)]:
        for value, pages in groups.items():
            if value and len(pages) > 1: add('warning', '、'.join(pages[:8]), label + '重复', '给不同页面写不同的介绍，尤其是不同产品。')
    # These are local checks, not evidence of indexing, ranking or citations.
    return {'pages': len(files), 'issues': issues, 'errors': sum(i['level']=='error' for i in issues),
            'warnings': sum(i['level']=='warning' for i in issues), 'checked_at': datetime.now(timezone.utc).isoformat(),
            'notice': '这是本机页面检查，不代表已被收录、获得排名或被 AI 推荐。上线后请用真实的曝光、访问和询盘数据判断效果。'}
