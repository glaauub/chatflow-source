"""Read public product pages into reviewable drafts, without login or API credentials.

Adapters identify marketplace URLs; identification does not mean those marketplaces
allow their dynamic pages to be fetched. No JavaScript, cookies, logins or CAPTCHA
workarounds are used. Shopify format follows shopify.dev/docs/api/ajax/reference/product.
"""
import gzip
import html
import http.client
import ipaddress
import io
import json
import re
import socket
import ssl
import time
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from catalog_data import normalize_product

MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 15
USER_AGENT = 'ChatFLOW/2.1 PublicProductImporter'


class CollectionError(ValueError):
    pass


PLATFORMS = {
    '1688': {'label': '1688', 'domains': ['1688.com'], 'search_url': 'https://s.1688.com/selloffer/offer_search.htm?keywords={query}&beginPage={page}'},
    'taobao': {'label': '淘宝', 'domains': ['taobao.com'], 'search_url': 'https://s.taobao.com/search?q={query}&s={offset44}'},
    'tmall': {'label': '天猫', 'domains': ['tmall.com'], 'search_url': 'https://list.tmall.com/search_product.htm?q={query}&s={offset60}'},
    'jd': {'label': '京东', 'domains': ['jd.com'], 'search_url': 'https://search.jd.com/Search?keyword={query}&enc=utf-8&page={oddpage}'},
    'pinduoduo': {'label': '拼多多', 'domains': ['pinduoduo.com', 'yangkeduo.com'], 'search_url': 'https://mobile.yangkeduo.com/search_result.html?search_key={query}'},
    'alibaba': {'label': '阿里巴巴国际站', 'domains': ['alibaba.com'], 'search_url': 'https://www.alibaba.com/trade/search?SearchText={query}&page={page}'},
    'aliexpress': {'label': '速卖通', 'domains': ['aliexpress.com', 'aliexpress.us'], 'search_url': 'https://www.aliexpress.com/w/wholesale-{slug}.html?page={page}'},
    'amazon': {'label': 'Amazon', 'domains': ['amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr', 'amazon.es', 'amazon.it', 'amazon.ca', 'amazon.co.jp', 'amazon.com.au', 'amazon.in', 'amazon.com.br', 'amazon.com.mx', 'amazon.ae', 'amazon.sa', 'amazon.nl', 'amazon.se', 'amazon.pl'], 'search_url': 'https://www.amazon.com/s?k={query}&page={page}'},
    'ebay': {'label': 'eBay', 'domains': ['ebay.com', 'ebay.co.uk', 'ebay.de', 'ebay.fr', 'ebay.com.au', 'ebay.ca', 'ebay.it', 'ebay.es'], 'search_url': 'https://www.ebay.com/sch/i.html?_nkw={query}&_pgn={page}'},
    'shopee': {'label': 'Shopee', 'domains': ['shopee.com', 'shopee.sg', 'shopee.com.my', 'shopee.co.th', 'shopee.vn', 'shopee.ph', 'shopee.co.id', 'shopee.tw', 'shopee.com.br'], 'search_url': 'https://shopee.sg/search?keyword={query}&page={zero_page}'},
    'lazada': {'label': 'Lazada', 'domains': ['lazada.sg', 'lazada.com.my', 'lazada.co.th', 'lazada.vn', 'lazada.com.ph', 'lazada.co.id'], 'search_url': 'https://www.lazada.sg/catalog/?q={query}&page={page}'},
    'temu': {'label': 'Temu', 'domains': ['temu.com'], 'search_url': 'https://www.temu.com/search_result.html?search_key={query}'},
    'shein': {'label': 'SHEIN', 'domains': ['shein.com', 'shein.co.uk'], 'search_url': 'https://www.shein.com/pdsearch/{query}/?page={page}'},
    'etsy': {'label': 'Etsy', 'domains': ['etsy.com'], 'search_url': 'https://www.etsy.com/search?q={query}&page={page}'},
    'walmart': {'label': 'Walmart', 'domains': ['walmart.com', 'walmart.ca'], 'search_url': 'https://www.walmart.com/search?q={query}&page={page}'},
    'rakuten': {'label': '乐天', 'domains': ['rakuten.co.jp'], 'search_url': 'https://search.rakuten.co.jp/search/mall/{query}/?p={page}'},
    'dhgate': {'label': '敦煌网', 'domains': ['dhgate.com'], 'search_url': 'https://www.dhgate.com/wholesale/search.do?searchkey={query}&pageNum={page}'},
    'made_in_china': {'label': '中国制造网', 'domains': ['made-in-china.com'], 'search_url': 'https://www.made-in-china.com/products-search/hot-china-products/{slug}.html'},
    'banggood': {'label': 'Banggood', 'domains': ['banggood.com'], 'search_url': 'https://www.banggood.com/search/{slug}.html'},
    'shopify': {'label': 'Shopify 独立站', 'domains': ['myshopify.com'], 'search_url': None},
    'generic': {'label': '其他公开商品页', 'domains': [], 'search_url': None},
}


def platform_catalog():
    return [{'id': key, 'name': row['label'], 'label': row['label'],
             'search': bool(row['search_url']), 'domains': row['domains'],
             'status': '公开页面解析，能否读取取决于平台；未逐个平台实测，不保证完整 SKU'}
            for key, row in PLATFORMS.items()]


def _basic_url(url):
    if not isinstance(url, str) or not url.strip() or len(url) > 4000:
        raise CollectionError('请填写完整的商品或店铺网址')
    url = url.strip()
    if re.search(r'[\x00-\x20\x7f\\]', url):
        raise CollectionError('网址包含不允许的字符')
    try:
        parts = urlsplit(url)
        host = (parts.hostname or '').rstrip('.').encode('idna').decode('ascii').lower()
        port = parts.port
    except (ValueError, UnicodeError):
        raise CollectionError('网址格式不正确')
    if parts.scheme not in ('https', 'http') or not host or parts.username or parts.password:
        raise CollectionError('只支持不含账号密码的 http 或 https 网页地址')
    if port not in (None, 80, 443) or (parts.scheme == 'https' and port == 80):
        raise CollectionError('只支持普通网页端口')
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '.' not in host and ':' not in host:
        raise CollectionError('不能采集本机或内网地址')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise CollectionError('不能采集本机或内网地址')
    netloc = '[' + host + ']' if ':' in host else host
    if port: netloc += ':' + str(port)
    return urlunsplit((parts.scheme, netloc, parts.path or '/', parts.query, ''))


def validate_public_url(url):
    """Validate the URL and resolve public addresses. Network connections use these IPs."""
    url = _basic_url(url)
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    try:
        records = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        raise CollectionError('找不到这个网站，请检查网址和网络')
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise CollectionError('不能采集本机、内网或异常解析地址')
    return url, addresses


def identify_platform(url):
    host = (urlsplit(_basic_url(url)).hostname or '').lower()
    for key, row in PLATFORMS.items():
        if any(host == domain or host.endswith('.' + domain) for domain in row['domains']):
            return key
    return 'generic'


def _ssl_context():
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return context


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, addresses, secure):
        super().__init__(host, port=port, timeout=TIMEOUT)
        self.addresses = addresses
        self.secure = secure

    def connect(self):
        last = None
        for address in self.addresses:
            sock = None
            try:
                sock = socket.create_connection((address, self.port), self.timeout)
                if self.secure:
                    sock = _ssl_context().wrap_socket(sock, server_hostname=self.host)
                self.sock = sock
                return
            except OSError as exc:
                last = exc
                if sock: sock.close()
        raise last or OSError('connection failed')


def fetch_public(url, *, image=False):
    """Return {'text', 'url', 'content_type'}; reject private IPs and unsafe redirects."""
    for redirects in range(5):
        url, addresses = validate_public_url(url)
        parts = urlsplit(url)
        conn = _PinnedHTTP(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80), addresses, parts.scheme == 'https')
        try:
            conn.request('GET', (parts.path or '/') + ('?' + parts.query if parts.query else ''),
                         headers={'User-Agent': USER_AGENT, 'Accept': 'image/*' if image else 'text/html,application/json,application/ld+json;q=0.9', 'Accept-Encoding': 'identity'})
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = response.getheader('Location')
                if not target or redirects >= 4: raise CollectionError('网站跳转过多或地址无效')
                target = _basic_url(urljoin(url, target))
                if parts.scheme == 'https' and urlsplit(target).scheme != 'https':
                    raise CollectionError('网站跳转到了不安全的连接，已停止读取')
                url = target
                continue
            if response.status in (401, 403, 429):
                raise CollectionError('平台要求登录、验证或限制访问；请用浏览器保存商品网页后导入')
            if response.status != 200:
                raise CollectionError('商品页没有正常返回（HTTP %s），请检查链接' % response.status)
            length = response.getheader('Content-Length') or ''
            if length.isdigit() and int(length) > MAX_BYTES:
                raise CollectionError('页面超过 5 MB，请保存较小的商品网页后导入')
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES: raise CollectionError('页面超过 5 MB，已停止读取')
            encoding = (response.getheader('Content-Encoding') or '').lower()
            if encoding == 'gzip':
                with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                    data = compressed.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES: raise CollectionError('页面解压后超过 5 MB，已停止读取')
            elif encoding not in ('', 'identity'):
                raise CollectionError('这个网站的压缩格式暂不支持，请保存 HTML 后导入')
            mime = response.getheader('Content-Type') or ''
            if image:
                signatures = [(b'\xff\xd8\xff', '.jpg'), (b'\x89PNG\r\n\x1a\n', '.png'), (b'GIF87a', '.gif'), (b'GIF89a', '.gif')]
                extension = next((ext for signature, ext in signatures if data.startswith(signature)), None)
                if data.startswith(b'RIFF') and data[8:12] == b'WEBP': extension = '.webp'
                if not extension or not mime.lower().startswith('image/'):
                    raise CollectionError('图片地址没有返回支持的图片文件')
                return {'data': data, 'url': url, 'extension': extension}
            if mime and not any(kind in mime.lower() for kind in ('html', 'json', 'text/plain', 'javascript')):
                raise CollectionError('链接返回的不是商品网页或商品 JSON')
            charset = re.search(r'charset=["\']?([\w-]+)', mime, re.I)
            if not charset:
                charset = re.search(r'charset=["\']?([\w-]+)', data[:4096].decode('ascii', errors='ignore'), re.I)
            charset = charset.group(1) if charset else 'utf-8'
            try: result = data.decode(charset, errors='replace')
            except LookupError: result = data.decode('utf-8', errors='replace')
            return {'text': result, 'url': url, 'content_type': mime}
        except CollectionError:
            raise
        except ssl.SSLError:
            raise CollectionError('网站证书验证失败，请检查系统时间或网站证书；没有关闭证书验证')
        except (OSError, http.client.HTTPException, EOFError):
            raise CollectionError('网站连接失败或超时，请稍后再试，也可以保存商品 HTML 后导入')
        finally:
            conn.close()
    raise CollectionError('网站跳转过多')


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}; self.blocks = []; self.links = []; self.title = []; self.visible = []
        self._script = None; self._in_title = False; self._hidden = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'script':
            self._script = [] if (values.get('type') or '').lower().split(';')[0] == 'application/ld+json' else False
        if tag in ('style', 'noscript'): self._hidden += 1
        if tag == 'title': self._in_title = True
        if tag == 'meta':
            key = (values.get('property') or values.get('name') or values.get('itemprop') or '').lower()
            if key and values.get('content'): self.meta.setdefault(key, values['content'])
        if tag in ('a', 'link') and values.get('href'):
            self.links.append((values['href'], values.get('rel', '')))

    def handle_endtag(self, tag):
        if tag == 'script':
            if isinstance(self._script, list): self.blocks.append(''.join(self._script))
            self._script = None
        if tag in ('style', 'noscript'): self._hidden = max(0, self._hidden - 1)
        if tag == 'title': self._in_title = False

    def handle_data(self, data):
        if isinstance(self._script, list): self._script.append(data)
        elif self._script is None and not self._hidden:
            if self._in_title: self.title.append(data)
            if len(self.visible) < 5000: self.visible.append(data)


def _words(value, limit=20000):
    if isinstance(value, dict): value = value.get('name') or value.get('value') or ''
    if not isinstance(value, (str, int, float)): return ''
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(value)))).strip()[:limit]


def _description_images(markup, base):
    """Only extract images from the product description, never unrelated page ads."""
    class Images(HTMLParser):
        def __init__(self):
            super().__init__(); self.urls = []
        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == 'img':
                self.urls.extend(_image_urls(values.get('src') or values.get('data-src'), base))
    parser = Images()
    parser.feed(markup if isinstance(markup, str) else '')
    return parser.urls[:100]


def _list(value):
    return value if isinstance(value, list) else ([value] if value is not None else [])


def _types(node):
    return {str(value).rsplit('/', 1)[-1] for value in _list(node.get('@type'))}


def _blocked(page):
    title = ' '.join(page.title).lower()
    text = ' '.join(page.visible)[:1800].lower()
    return bool(re.search(r'captcha|access denied|robot check|security verification|just a moment|验证码|安全验证|访问受限|登录|sign in|\blog[ -]?in\b', title) or
                re.search(r'verify (?:that )?you are (?:a )?human|complete the security check|请输入验证码|请完成安全验证|请先登录后', text))


def _image_urls(value, base):
    result = []
    for item in _list(value):
        if isinstance(item, dict): item = item.get('url') or item.get('contentUrl') or item.get('src')
        if not isinstance(item, str): continue
        try: item = _basic_url(urljoin(base, item))
        except CollectionError: continue
        if item not in result: result.append(item)
    return result[:100]


def _number(value):
    if value is None or isinstance(value, bool): return None
    try:
        number = Decimal(str(value))
        if number.is_finite() and number >= 0: return str(number)
    except (InvalidOperation, ValueError):
        pass
    return None


def _offers(node, warnings):
    offers = [value for value in _list(node.get('offers')) if isinstance(value, dict)]
    rows = []
    for offer in offers:
        price = _number(offer.get('price'))
        spec = offer.get('priceSpecification')
        currency = _words(offer.get('priceCurrency'), 8).upper()
        if price is None and isinstance(spec, dict):
            price = _number(spec.get('price')); currency = currency or _words(spec.get('priceCurrency'), 8).upper()
        if currency and not re.fullmatch('[A-Z]{3}', currency): currency = ''
        if price is not None: rows.append((price, currency))
        elif offer.get('lowPrice') is not None:
            warnings.append('来源只提供价格区间，实际商品价格留空，避免把最低价当成交价')
    if len(set(rows)) > 1:
        warnings.append('来源有多个不同报价，主商品价格留空，请按 SKU 核对')
        return None, ''
    return rows[0] if rows else (None, '')


def _stock(node):
    # Availability=InStock is not an inventory count.
    inventory = node.get('inventoryLevel')
    if isinstance(inventory, dict): inventory = inventory.get('value')
    if inventory is not None and not isinstance(inventory, bool) and re.fullmatch(r'\d+', str(inventory)):
        return int(inventory)
    for offer in _list(node.get('offers')):
        if isinstance(offer, dict) and 'inventoryLevel' in offer:
            return _stock({'inventoryLevel': offer['inventoryLevel']})
    return None


def _attributes(node):
    result = []
    for key in ('color', 'size', 'material', 'pattern'):
        if _words(node.get(key), 300): result.append({'name': key, 'value': _words(node[key], 300)})
    for prop in _list(node.get('additionalProperty')):
        if isinstance(prop, dict):
            name, value = _words(prop.get('name'), 120), _words(prop.get('value'), 300)
            if name and value and {'name': name, 'value': value} not in result:
                result.append({'name': name, 'value': value})
    return result[:30]


def _finish(raw, warnings, method, incomplete=False):
    try: product = normalize_product(raw)
    except ValueError as exc: raise CollectionError('商品资料格式不完整：' + str(exc))
    if not product['description']: warnings.append('来源没有提供商品介绍，请补充后再发布')
    if not product['variants']: warnings.append('来源没有完整的规格 SKU 列表，请对照原商品检查')
    if any(v['stock'] is None for v in product['variants']): warnings.append('来源没有提供部分 SKU 的库存数量，已留空')
    product['warnings'] = list(dict.fromkeys(product['warnings'] + warnings))
    product['collection_method'] = method
    product['incomplete'] = bool(incomplete or product['warnings'])
    return product


def _from_schema(node, base, pool):
    warnings = []; price, currency = _offers(node, warnings)
    variants = []; identifiers = set()
    children = _list(node.get('hasVariant'))
    if not children and node.get('@id'):
        for value in pool.values():
            group = value.get('isVariantOf')
            if isinstance(group, dict) and group.get('@id') == node['@id']: children.append(value)
    for variant in children[:1000]:
        if not isinstance(variant, dict): continue
        if '@id' in variant: variant = dict(pool.get(variant['@id'], {}), **variant)
        identifier = _words(variant.get('sku') or variant.get('productID'), 160)
        if not identifier:
            warnings.append('部分规格没有原 SKU 编号，已跳过这些规格，不能视为完整采集'); continue
        if identifier in identifiers:
            warnings.append('来源有重复 SKU 编号，已保留第一条，请人工核对'); continue
        identifiers.add(identifier)
        variant_price, variant_currency = _offers(variant, warnings)
        if currency and variant_currency and variant_currency != currency:
            warnings.append('来源 SKU 币种不一致，该 SKU 价格已留空'); variant_price = None
        elif not currency: currency = variant_currency
        images = _image_urls(variant.get('image'), base)
        variants.append({'source_sku': identifier, 'sku': _words(variant.get('sku') or identifier, 160),
                         'attributes': _attributes(dict(node, **variant)), 'price': variant_price,
                         'stock': _stock(variant), 'image': images[0] if images else ''})
    if len(children) > 1000: warnings.append('规格超过 1000 个，本次仅保留前 1000 个')
    images = _image_urls(node.get('image'), base) + _description_images(node.get('description'), base)
    images = list(dict.fromkeys(images + [v['image'] for v in variants if v['image']]))[:100]
    attrs = _attributes(node)
    raw = {'name': _words(node.get('name')), 'description': _words(node.get('description')),
           'source_platform': identify_platform(base), 'source_url': base,
           'source_id': _words(node.get('productGroupID') or node.get('productID') or node.get('sku') or node.get('mpn'), 160),
           'sku': _words(node.get('sku'), 160), 'model': _words(node.get('model') or node.get('mpn'), 160),
           'category': _words(node.get('category')), 'price': price, 'currency': currency,
           'images': images, 'variants': variants, 'spec': '\n'.join(a['name'] + ': ' + a['value'] for a in attrs)}
    return _finish(raw, warnings, 'jsonld')


def extract_page(html_text, url):
    """Parse saved or fetched HTML without fetching any additional resource."""
    url = _basic_url(url)
    if not isinstance(html_text, str) or len(html_text.encode('utf-8')) > MAX_BYTES:
        raise CollectionError('请导入不超过 5 MB 的 HTML 商品网页')
    page = _Page(); page.feed(html_text)
    if _blocked(page): raise CollectionError('这是登录或验证页面，没有可读取的商品；请保存已打开的商品网页后导入')
    nodes = []; pool = {}
    def walk(value, depth=0):
        if depth > 30 or len(nodes) > 20000: return
        if isinstance(value, list):
            for child in value: walk(child, depth + 1)
        elif isinstance(value, dict):
            nodes.append(value)
            if isinstance(value.get('@id'), str):
                pool[value['@id']] = dict(pool.get(value['@id'], {}), **value)
            for child in value.values():
                if isinstance(child, (dict, list)): walk(child, depth + 1)
    for block in page.blocks[:100]:
        try: walk(json.loads(block))
        except (ValueError, RecursionError): continue
    products = [node for node in nodes if _types(node) & {'Product', 'ProductGroup'} and node.get('name')]
    groups = [node for node in products if 'ProductGroup' in _types(node)]
    candidates = groups or products
    if candidates:
        exact = [node for node in candidates if node.get('url') and urljoin(url, str(node['url'])).split('#')[0].split('?')[0] == url.split('?')[0]]
        main = [node['mainEntity'] for node in nodes if isinstance(node.get('mainEntity'), dict) and node['mainEntity'] in candidates]
        selected = exact[0] if exact else (main[0] if main else (candidates[0] if len(candidates) == 1 else None))
        if selected is None: raise CollectionError('页面包含多个不同商品，请粘贴单个商品详情链接，或使用店铺扫描')
        return _from_schema(selected, url, pool)
    meta = page.meta
    is_product = (meta.get('og:type', '').lower() in ('product', 'product.item') or
                  any(key in meta for key in ('product:price:amount', 'product:retailer_item_id', 'og:price:amount')))
    name = meta.get('og:title') or meta.get('twitter:title') or ' '.join(page.title)
    if not is_product or not name:
        raise CollectionError('网页没有可读取的商品资料，可能需要登录或由浏览器加载；请保存商品 HTML 后导入，不能保证完整 SKU')
    raw = {'name': _words(name), 'description': _words(meta.get('og:description') or meta.get('description')),
           'source_platform': identify_platform(url), 'source_url': url,
           'source_id': meta.get('product:retailer_item_id', ''), 'sku': meta.get('product:retailer_item_id', ''),
           'price': _number(meta.get('product:price:amount') or meta.get('og:price:amount')),
           'currency': meta.get('product:price:currency') or meta.get('og:price:currency') or '',
           'images': _image_urls(meta.get('og:image') or meta.get('twitter:image'), url), 'variants': []}
    return _finish(raw, ['只读取到网页摘要，介绍和规格可能不全，请对照原商品检查'], 'html_meta', True)


def _shopify_product(payload, url, currency=''):
    if not isinstance(payload, dict) or not payload.get('title') or not isinstance(payload.get('variants'), list) or payload.get('id') is None:
        raise CollectionError('这个链接没有返回 Shopify 商品资料')
    warnings = ['Shopify 公开接口最多返回 250 个规格，数量和库存请对照原店铺核对']
    variants = []; images = list(dict.fromkeys(_image_urls(payload.get('images'), url) + _description_images(payload.get('description'), url)))[:100]
    option_names = [item.get('name') if isinstance(item, dict) else str(item) for item in payload.get('options', [])]
    def money(value):
        parsed = _number(value)
        return str(Decimal(parsed) / 100) if parsed is not None else None
    for item in payload['variants'][:1000]:
        if not isinstance(item, dict) or item.get('id') is None:
            warnings.append('有规格缺少原平台编号，已跳过'); continue
        options = item.get('options') or [item.get('option' + str(i + 1)) for i in range(len(option_names))]
        attributes = [{'name': _words(name, 120), 'value': _words(value, 300)} for name, value in zip(option_names, options) if name and value and value != 'Default Title']
        image = _image_urls(item.get('featured_image'), url)
        variants.append({'source_sku': str(item['id']), 'sku': _words(item.get('sku') or item['id'], 160),
                         'attributes': attributes, 'price': money(item.get('price')),
                         'stock': _stock({'inventoryLevel': item.get('inventory_quantity')}), 'image': image[0] if image else ''})
    if not currency: warnings.append('接口没有确认币种，请填写实际币种后再使用价格')
    raw = {'name': _words(payload['title']), 'description': _words(payload.get('description')),
           'source_platform': 'shopify', 'source_url': re.sub(r'\.js(?=\?|$)', '', url), 'source_id': str(payload['id']),
           'category': _words(payload.get('type')), 'price': money(payload.get('price')) if not payload.get('price_varies') else None,
           'currency': currency, 'images': images, 'variants': variants}
    return _finish(raw, warnings, 'shopify_ajax')


def collect_url(url):
    """Fetch one public URL and return a normalized product draft with honest warnings."""
    response = fetch_public(url)
    page_url = response['url']; text = response['text']
    match = re.search(r'^(.*?/)(?:collections/[^/]+/)?products/([^/]+?)(?:\.js)?$', urlsplit(page_url).path)
    shopify_hint = identify_platform(page_url) == 'shopify' or 'cdn.shopify.com' in text or 'Shopify.theme' in text
    if match and (shopify_hint or urlsplit(page_url).path.endswith('.js')):
        parts = urlsplit(page_url); product_path = match.group(1) + 'products/' + match.group(2) + '.js'
        try:
            data = response if parts.path.endswith('.js') else fetch_public(urlunsplit((parts.scheme, parts.netloc, product_path, parts.query, '')))
            payload = json.loads(data['text']); currency = ''
            if isinstance(payload, dict) and re.fullmatch('[A-Z]{3}', str(payload.get('currency', ''))): currency = payload['currency']
            if not currency:
                try:
                    cart = fetch_public(urlunsplit((parts.scheme, parts.netloc, match.group(1) + 'cart.js', '', '')))
                    value = json.loads(cart['text']).get('currency', '')
                    if re.fullmatch('[A-Z]{3}', str(value)): currency = value
                except (CollectionError, ValueError, AttributeError): pass
            return _shopify_product(payload, page_url, currency)
        except (CollectionError, ValueError):
            if parts.path.endswith('.js'): raise CollectionError('Shopify 商品 JSON 无法读取，请使用商品网页链接')
    return extract_page(text, page_url)


PRODUCT_PATTERNS = {
    '1688': r'/offer/\d+\.html', 'taobao': r'/item\.htm', 'tmall': r'/item\.htm',
    'jd': r'/\d+\.html|/product/\d+', 'pinduoduo': r'/goods(?:\d*|_detail)?\.html',
    'alibaba': r'/product-detail/', 'aliexpress': r'/item/\d+', 'amazon': r'/(?:dp|gp/product)/[A-Z0-9]{10}(?:[/?]|$)',
    'ebay': r'/itm/', 'shopee': r'(?:-i\.\d+\.\d+|/product/\d+/\d+)', 'lazada': r'-i\d+(?:-s\d+)?\.html|/products/',
    'temu': r'(?:-g-\d+\.html|/goods\.html)', 'shein': r'-p-\d+\.html',
    'etsy': r'/listing/\d+', 'walmart': r'/ip/', 'rakuten': r'item\.rakuten\.co\.jp/[^/]+/[^/]+',
    'dhgate': r'/product/', 'made_in_china': r'/product/', 'banggood': r'-p-\d+\.html',
    'shopify': r'/products/[^/?]+', 'generic': r'/(?:products?|items?)/[^/?]+',
}


def _product_link(url):
    try: platform = identify_platform(url)
    except CollectionError: return False
    return bool(re.search(PRODUCT_PATTERNS[platform], url, re.I))


def _discover(text, source_url, limit, same_host=False):
    page = _Page(); page.feed(text)
    if _blocked(page): raise CollectionError('平台要求登录或验证，无法读取搜索或店铺商品链接')
    host = urlsplit(source_url).hostname; platform = identify_platform(source_url)
    urls = []; next_pages = []
    for href, rel in page.links:
        try: link = _basic_url(urljoin(source_url, href))
        except CollectionError: continue
        link_host = urlsplit(link).hostname
        if same_host and link_host != host: continue
        if not same_host and link_host != host and (platform == 'generic' or identify_platform(link) != platform): continue
        if _product_link(link) and link not in urls:
            urls.append(link)
        elif link_host == host and ('next' in rel.lower().split() or
                re.search(r'[?&](?:page|p)=\d+(?:&|$)', link) or
                re.fullmatch(r'/(?:[a-z]{2}(?:-[A-Z]{2})?/)?collections/[^/]+/?', urlsplit(link).path)) and link not in next_pages:
            next_pages.append(link)
    return urls[:limit], next_pages


def search_platform(platform, query, page=1):
    """Read a platform's public search page; return discovered links, never invented hits."""
    if platform not in PLATFORMS or not PLATFORMS[platform]['search_url']:
        raise CollectionError('此类型请直接填写商品或店铺链接，不提供统一关键词搜索')
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise CollectionError('请输入 1 至 200 字的搜索词')
    if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 10:
        raise CollectionError('搜索页码需在 1 至 10 之间')
    template = PLATFORMS[platform]['search_url']
    if page != 1 and not any(marker in template for marker in ('{page}', '{zero_page}', '{offset44}', '{offset60}', '{oddpage}')):
        raise CollectionError('此平台暂时只能读取首屏搜索，请使用商品链接导入更多')
    url = template.format(query=quote(query.strip(), safe=''), slug=quote(re.sub(r'\s+', '-', query.strip()), safe=''),
                          page=page, zero_page=page - 1, offset44=(page - 1) * 44, offset60=(page - 1) * 60, oddpage=page * 2 - 1)
    response = fetch_public(url)
    urls, _ = _discover(response['text'], response['url'], 100)
    if not urls: raise CollectionError('这次没有读到商品链接，平台可能需要登录或浏览器加载；可以复制商品链接或保存 HTML 导入')
    return {'urls': urls, 'source_url': response['url'], 'platform': platform, 'pages_scanned': 1,
            'complete': False, 'warnings': ['只列出这次公开搜索页实际读到的商品，未确认价格、库存和完整 SKU']}


def scan_shop(url, max_pages=3, max_products=30):
    """Discover a bounded number of same-host product links; not an entire-shop guarantee."""
    url = _basic_url(url)
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 10:
        raise CollectionError('每次扫描页数需在 1 至 10 之间')
    if isinstance(max_products, bool) or not isinstance(max_products, int) or not 1 <= max_products <= 100:
        raise CollectionError('每次最多读取 1 至 100 个商品链接')
    queue = [url]; visited = set(); urls = []; warnings = []
    start_host = urlsplit(url).hostname
    while queue and len(visited) < max_pages and len(urls) < max_products:
        current = queue.pop(0)
        if current in visited: continue
        try:
            response = fetch_public(current)
            if urlsplit(response['url']).hostname != start_host:
                raise CollectionError('店铺跳转到了其他域名，请直接填写跳转后的店铺网址')
            found, next_pages = _discover(response['text'], response['url'], max_products, same_host=True)
        except CollectionError:
            if not visited: raise
            warnings.append('部分店铺页面读取失败，本次结果不是完整商品清单'); break
        visited.add(current)
        for link in found:
            if link not in urls: urls.append(link)
            if len(urls) >= max_products: break
        for link in next_pages:
            if link not in visited and link not in queue: queue.append(link)
        if queue and len(visited) < max_pages and len(urls) < max_products: time.sleep(0.6)
    if not urls: raise CollectionError('店铺页面没有可读取的商品链接，可能需要登录或浏览器加载；请粘贴单个商品链接或保存 HTML 导入')
    warnings.append('本次只扫描了 %s 页、发现 %s 个商品链接，不代表全店商品；采集详情后还需核对 SKU' % (len(visited), len(urls)))
    return {'urls': urls, 'source_url': url, 'platform': identify_platform(url), 'pages_scanned': len(visited),
            'complete': False, 'warnings': warnings}
