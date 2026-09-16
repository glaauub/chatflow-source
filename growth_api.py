"""Authenticated promotion/collection workbench; drafts never auto-publish."""
import copy, datetime, hashlib, html, json, re, uuid
from contextlib import closing
from flask import jsonify, request
from models import get_db, get_config, set_config
from catalog_data import LANGUAGES, localized, normalize_product


def register_growth_routes(app,login_required):
    def settings():
        from promotion_tools import validate_settings
        try:raw=json.loads(get_config('growth_settings','{}'))
        except ValueError:raw={}
        return validate_settings(raw)

    def data():return request.get_json(silent=True) or {}

    def read_draft(identifier):
        with closing(get_db()) as c:row=c.execute('SELECT payload FROM collection_drafts WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('采集草稿不存在，请刷新')
        return json.loads(row[0])

    def save_draft(product):
        normalized=normalize_product(product)
        normalized['warnings']=list(dict.fromkeys(normalized['warnings']+product.get('warnings',[])))
        normalized['collection_method']=product.get('collection_method','file')
        normalized['incomplete']=bool(product.get('incomplete'))
        identifier=uuid.uuid4().hex
        draft={'id':identifier,'product':normalized,'translations':{},'created_at':datetime.datetime.now().isoformat(timespec='seconds')}
        with closing(get_db()) as c:
            c.execute('INSERT INTO collection_drafts(id,payload) VALUES(?,?)',(identifier,json.dumps(draft,ensure_ascii=False)));c.commit()
        return draft

    def landing_items(payload):
        topics=payload.get('topics') or []
        if not isinstance(topics,list) or not 1<=len(topics)<=50:raise ValueError('一次填写 1—50 个主题，每行一个')
        topics=list(dict.fromkeys(str(x).strip() for x in topics if str(x).strip()))
        if not topics or any(len(x)>160 for x in topics):raise ValueError('主题不能为空且每条最多 160 字')
        ids=payload.get('product_ids') or []
        if not isinstance(ids,list) or len(ids)>100:raise ValueError('选择的产品过多')
        ids=[int(x) for x in ids]
        with closing(get_db()) as c:
            if ids:rows=c.execute('SELECT id,name,spec FROM products WHERE id IN (%s)'%','.join('?' for _ in ids),ids).fetchall()
            else:rows=c.execute('SELECT id,name,spec FROM products ORDER BY id DESC LIMIT 12').fetchall()
        if not rows:raise ValueError('先添加真实产品，再生成落地页')
        items=[]
        for topic in topics:
            slug='topic-'+hashlib.sha256(topic.encode()).hexdigest()[:16]
            content='<p>'+html.escape(topic)+'</p><ul>'
            for row in rows:
                content+='<li><a href="product_%d.html">%s</a> %s</li>'%(row['id'],html.escape(row['name']),html.escape(row['spec'] or ''))
            content+='</ul>'
            items.append({'title':topic,'slug':slug,'content':content})
        return items

    def endpoint(path,methods=['GET']):
        def decorate(fn):
            def wrapped(*args,**kwargs):
                try:return fn(*args,**kwargs)
                except (ValueError,TypeError,KeyError) as error:return jsonify({'error':str(error)}),400
                except Exception as error:return jsonify({'error':'操作没有完成：'+type(error).__name__+'。原数据未自动发布。'}),500
            wrapped.__name__='growth_'+fn.__name__
            app.route(path,methods=methods)(login_required(wrapped));return wrapped
        return decorate

    @endpoint('/api/growth/settings',['GET','POST'])
    def growth_settings():
        from promotion_tools import validate_settings
        if request.method=='POST':
            value=validate_settings(data());set_config('growth_settings',json.dumps(value,ensure_ascii=False))
        return jsonify(settings())

    @endpoint('/api/growth/landing-preview',['POST'])
    def preview_landings():return jsonify({'items':landing_items(data()),'notice':'仅按主题组织现有产品链接。请补充该主题独有的资料；重复模板不会自动提高排名。'})

    @endpoint('/api/growth/landing-create',['POST'])
    def create_landings():
        items=landing_items(data());created=[]
        with closing(get_db()) as c:
            for item in items:
                result=c.execute('INSERT OR IGNORE INTO pages(title,slug,content,enabled,seo_title,seo_description) VALUES(?,?,?,0,?,?)',(item['title'],item['slug'],item['content'],item['title'],item['title']))
                if result.rowcount:created.append({'id':result.lastrowid,'title':item['title']})
            c.commit()
        return jsonify({'created':created,'count':len(created),'notice':'已创建未启用的页面草稿，到板块与页面检查内容后开启。'})

    @endpoint('/api/collection/status')
    def collection_status():
        import collection_tools,local_ai
        catalog=collection_tools.platform_catalog()
        return jsonify({'languages':[{'id':k,'name':v} for k,v in LANGUAGES.items()],'platforms':catalog,'ai':local_ai.status()})

    @endpoint('/api/collection/ai/start',['POST'])
    def ai_start():
        import local_ai
        return jsonify(local_ai.start())

    @endpoint('/api/collection/ai/diagnostics')
    def ai_diagnostics():
        import local_ai
        path=local_ai.AI_HOME/'startup-error.json'
        if not path.is_file():raise ValueError('还没有 AI 启动错误记录，请先尝试启动 AI')
        result=jsonify(json.loads(path.read_text(encoding='utf-8')))
        result.headers['Content-Disposition']='attachment; filename="ChatFLOW-AI-startup-error.json"'
        return result

    @endpoint('/api/collection/collect',['POST'])
    def collect_product():
        from collection_tools import collect_url
        return jsonify({'draft':save_draft(collect_url(data().get('url','')))})

    @endpoint('/api/collection/search',['POST'])
    def search_products():
        from collection_tools import search_platform
        result=search_platform(data().get('platform',''),data().get('query',''))
        result['message']='；'.join(result.get('warnings',[])) or '已找到当前公开页面里的商品链接，不代表平台全部结果。'
        return jsonify(result)

    @endpoint('/api/collection/shop',['POST'])
    def shop_products():
        from collection_tools import scan_shop
        result=scan_shop(data().get('url',''),max_pages=min(max(int(data().get('max_pages',3)),1),3))
        result['message']='；'.join(result.get('warnings',[])) or '按页数上限发现商品链接，不保证覆盖整店所有商品。'
        return jsonify(result)

    @endpoint('/api/collection/html',['POST'])
    def collect_html():
        from collection_tools import extract_page
        upload=request.files.get('file')
        if not upload:raise ValueError('请选择保存的网页 HTML 文件')
        content=upload.read(5*1024*1024+1)
        if len(content)>5*1024*1024:raise ValueError('网页文件最多 5MB')
        source=request.form.get('url','').strip()
        if not source:
            # Extract a public canonical as source metadata only. Parser does not fetch it.
            match=re.search(r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',content.decode('utf-8','replace'),re.I)
            source=html.unescape(match.group(1)) if match else ''
        product=extract_page(content.decode('utf-8','replace'),source or 'https://imported-page.invalid/')
        if not source:
            # The synthetic base is used only while parsing. Never present it as
            # the real source or publish relative images resolved against it.
            from urllib.parse import urlsplit
            product['source_url']=''
            product['source_platform']='html'
            product['images']=[url for url in product['images'] if urlsplit(url).hostname!='imported-page.invalid']
            for variant in product['variants']:
                if urlsplit(variant.get('image','')).hostname=='imported-page.invalid':variant['image']=''
            product['warnings'].append('HTML 文件没有原商品链接，按文件内容去重；相对图片地址无法确定，已留空，请补充来源或本地图片')
            product['incomplete']=True
        draft=save_draft(product)
        if not source:
            digest=hashlib.sha256(content).hexdigest()
            draft['product']['source_file_sha256']=digest
            draft['product']['fingerprint']=hashlib.sha256(('html-file:'+digest).encode('ascii')).hexdigest()
            with closing(get_db()) as c:
                c.execute('UPDATE collection_drafts SET payload=? WHERE id=?',(json.dumps(draft,ensure_ascii=False),draft['id']));c.commit()
        return jsonify({'draft':draft})

    @endpoint('/api/collection/drafts')
    def drafts():
        with closing(get_db()) as c:rows=c.execute('SELECT payload FROM collection_drafts ORDER BY rowid DESC LIMIT 200').fetchall()
        return jsonify({'items':[json.loads(row[0]) for row in rows]})

    @endpoint('/api/collection/drafts/<identifier>/translate',['POST'])
    def translate_draft(identifier):
        import local_ai
        language=data().get('language');draft=read_draft(identifier)
        translated=local_ai.translate_product(draft['product'],language,source_language=data().get('source_language') or None)
        with closing(get_db()) as c:
            # Re-read within the transaction, preserving translations from earlier requests.
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM collection_drafts WHERE id=?',(identifier,)).fetchone()
            if not row:raise ValueError('草稿已被移除')
            draft=json.loads(row[0]);draft['translations'][language]=translated
            imported=c.execute('SELECT id,catalog_data FROM products WHERE catalog_fingerprint=?',(draft['product']['fingerprint'],)).fetchall()
            for product_row in imported:
                catalog=json.loads(product_row['catalog_data'])
                catalog.setdefault('translations',{})[language]=translated
                c.execute('UPDATE products SET catalog_data=? WHERE id=?',(json.dumps(catalog,ensure_ascii=False),product_row['id']))
            c.execute('UPDATE collection_drafts SET payload=? WHERE id=?',(json.dumps(draft,ensure_ascii=False),identifier));c.commit()
        return jsonify({'draft':draft})

    @endpoint('/api/collection/drafts/<identifier>/import',['POST'])
    def import_draft(identifier):
        draft=read_draft(identifier);language=data().get('language') or ''
        if language and language not in draft['translations']:raise ValueError('这个语言还没有翻译，请先翻译或选择原文导入')
        product=localized(draft['product'],language,draft['translations'])
        rich='<p>'+html.escape(product['description']).replace('\n','<br>')+'</p>'
        price=(product.get('currency','')+' '+product['price']).strip() if product['price'] is not None else ''
        catalog=json.dumps({'source':draft['product'],'translations':draft['translations'],'import_language':language},ensure_ascii=False)
        with closing(get_db()) as c:
            if c.execute('SELECT id FROM products WHERE catalog_fingerprint=?',(product['fingerprint'],)).fetchone():raise ValueError('这个来源商品已经导入过，已阻止重复新增')
        from collection_images import store_images
        images, failed_images = store_images(product['images'])
        with closing(get_db()) as c:
            if c.execute('SELECT id FROM products WHERE catalog_fingerprint=?',(product['fingerprint'],)).fetchone():raise ValueError('这个来源商品已经导入过，已阻止重复新增')
            main=images[0] if images else ''
            result=c.execute('INSERT INTO products(name,price,spec,img,sku,model,stock,category,images,description,meta_title,meta_description,catalog_data,catalog_fingerprint) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(product['name'],price,product['spec'],main,product['sku'],product['model'],None,product['category'],json.dumps(images),rich,product['meta_title'],product['meta_description'],catalog,product['fingerprint']))
            pid=result.lastrowid
            if product['category']:
                c.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)',(product['category'],))
            c.commit()
        notice='已导入产品，描述已保存，%d 张图片已存到本机。请检查后再生成并发布。' % (len(images)-failed_images)
        if not product['description']: notice='已导入产品，但来源没有提供描述，请补充。'+notice.split('已导入产品，描述已保存，',1)[-1]
        if failed_images: notice+=' %d 张图片下载失败，暂保留原网址，请在产品管理中补传。' % failed_images
        return jsonify({'product_id':pid,'notice':notice,'images_saved':len(images)-failed_images,'images_failed':failed_images})
