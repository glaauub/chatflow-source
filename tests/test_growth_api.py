"""Exercise authenticated workbench routes with an isolated database, no cloud calls."""
import io
import hashlib
import json
import unittest
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch

import test_v2 as release_tests
from catalog_data import normalize_product, translation_input

server, models, builder = release_tests.server, release_tests.models, release_tests.builder


class GrowthAPITests(unittest.TestCase):
    tearDown = release_tests.ReleaseTests.tearDown
    product = release_tests.ReleaseTests.product

    def setUp(self):
        release_tests.ReleaseTests.setUp(self)
        image_network = patch('collection_images.fetch_public', side_effect=__import__('collection_tools').CollectionError('offline test'))
        image_network.start(); self.addCleanup(image_network.stop)
        conn = models.get_db()
        conn.execute('DELETE FROM collection_drafts')
        conn.commit(); conn.close()

    def source_product(self):
        return normalize_product({
            'name': 'Steel fitting 304', 'description': 'Length 12 mm, steel 304.',
            'spec': '12 mm', 'sku': 'BASE-304', 'source_platform': 'generic',
            'source_id': 'source-304', 'source_url': 'https://factory.example.com/products/fitting',
            'price': '19.99', 'currency': 'USD', 'images': ['https://factory.example.com/photo.jpg'],
            'variants': [
                {'source_sku': '00012', 'sku': 'ORIGINAL-0012', 'attributes': [{'name': 'Color', 'value': 'Blue'}],
                 'price': '19.99', 'stock': None, 'image': 'https://factory.example.com/blue.jpg'},
                {'source_sku': '00013', 'sku': 'ORIGINAL-0013', 'attributes': [{'name': 'Color', 'value': 'Red'}],
                 'price': '29.90', 'stock': 0, 'image': 'https://factory.example.com/red.jpg'}]})

    def create_draft(self):
        product = self.source_product()
        with patch('collection_tools.collect_url', return_value=product) as collect:
            response = self.client.post('/api/collection/collect', json={'url': product['source_url']})
        self.assertEqual(response.status_code, 200, response.json)
        collect.assert_called_once_with(product['source_url'])
        return response.json['draft']

    def test_collected_product_saved_only_as_draft(self):
        draft = self.create_draft()
        items = self.client.get('/api/collection/drafts').json['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], draft['id'])
        self.assertEqual(items[0]['product']['source_url'], self.source_product()['source_url'])
        conn = models.get_db()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)
        conn.close()

    def test_import_downloads_images_and_preserves_description_and_source(self):
        draft = self.create_draft()
        content = b'\x89PNG\r\n\x1a\n' + b'fixture'
        with patch('collection_images.fetch_public', return_value={'data': content, 'extension': '.png'}):
            response = self.client.post('/api/collection/drafts/' + draft['id'] + '/import', json={})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['images_failed'], 0)
        saved = self.client.get('/api/products/' + str(response.json['product_id'])).json
        self.assertIn('Length 12 mm, steel 304.', saved['description'])
        self.assertTrue(saved['img'].startswith('/uploads/collected_'))
        with self.client.get(saved['img']) as picture:
            self.assertEqual(picture.data, content)
        self.assertIn('https://factory.example.com/photo.jpg', saved['catalog_data'])

    def test_html_import_uses_real_parser_and_stores_source(self):
        payload = {'@type': 'ProductGroup', 'name': 'Original coat', 'productGroupID': 'COAT',
                   'hasVariant': [{'@type': 'Product', 'name': 'Blue', 'sku': 'BLUE-01', 'color': 'Blue',
                                   'offers': {'price': '35.25', 'priceCurrency': 'EUR'}}]}
        body = '<html><script type="application/ld+json">' + json.dumps(payload) + '</script></html>'
        response = self.client.post('/api/collection/html', data={'url': 'https://shop.example.com/products/coat',
                                    'file': (io.BytesIO(body.encode()), 'product.html')})
        self.assertEqual(response.status_code, 200, response.json)
        product = response.json['draft']['product']
        self.assertEqual(product['collection_method'], 'jsonld')
        self.assertEqual(product['variants'][0]['sku'], 'BLUE-01')
        self.assertEqual(product['variants'][0]['price'], '35.25')
        self.assertEqual(product['currency'], 'EUR')
        self.assertEqual(product['source_url'], 'https://shop.example.com/products/coat')

    def test_html_without_source_uses_file_content_identity_and_deduplicates_same_file(self):
        def document(name):
            payload = {'@type': 'Product', 'name': name, 'image': '/relative-photo.jpg'}
            return ('<html><script type="application/ld+json">' + json.dumps(payload) + '</script></html>').encode()
        first_body = document('Unknown source first item')
        second_body = document('Unknown source second item')
        drafts = []
        for index, body in enumerate([first_body, second_body, first_body]):
            response = self.client.post('/api/collection/html', data={'file': (io.BytesIO(body), 'saved-%s.html' % index)})
            self.assertEqual(response.status_code, 200, response.json)
            draft = response.json['draft']; drafts.append(draft)
            self.assertEqual(draft['product']['source_url'], '')
            self.assertEqual(draft['product']['source_file_sha256'], hashlib.sha256(body).hexdigest())
            self.assertEqual(draft['product']['images'], [])
            self.assertNotIn('imported-page.invalid', json.dumps(draft))
        self.assertNotEqual(drafts[0]['product']['fingerprint'], drafts[1]['product']['fingerprint'])
        self.assertEqual(drafts[0]['product']['fingerprint'], drafts[2]['product']['fingerprint'])
        for draft in drafts[:2]:
            imported = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
            self.assertEqual(imported.status_code, 200, imported.json)
        duplicate = self.client.post('/api/collection/drafts/%s/import' % drafts[2]['id'], json={})
        self.assertEqual(duplicate.status_code, 400, duplicate.json)
        self.assertIn('已经导入', duplicate.json['error'])
        conn = models.get_db()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 2)
        conn.close()

    def test_csv_unknown_stock_is_null_and_invalid_rows_are_skipped(self):
        body = ('产品名称,库存数量,SKU\n'
                'Unknown fitting,,SKU-U\n'
                'Zero fitting,0,SKU-Z\n'
                'Known fitting,12,SKU-K\n'
                'Negative fitting,-1,SKU-N\n'
                'Invalid fitting,unknown,SKU-I\n'
                'Too large fitting,99999999999999999999,SKU-B\n').encode('utf-8-sig')
        response = self.client.post('/api/products/import', data={'file': (io.BytesIO(body), 'products.csv')})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['success'], 3)
        self.assertEqual(len(response.json['failed']), 3)
        self.assertTrue(all(item['reason'] for item in response.json['failed']))
        conn = models.get_db()
        rows = {row['name']: row['stock'] for row in conn.execute('SELECT name,stock FROM products')}
        conn.close()
        self.assertEqual(rows, {'Unknown fitting': None, 'Zero fitting': 0, 'Known fitting': 12})

    def test_multi_sku_import_keeps_identifiers_numbers_and_unknown_stock(self):
        draft = self.create_draft()
        response = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
        self.assertEqual(response.status_code, 200, response.json)
        conn = models.get_db()
        row = dict(conn.execute('SELECT * FROM products WHERE id=?', (response.json['product_id'],)).fetchone())
        conn.close()
        catalog = json.loads(row['catalog_data'])
        self.assertEqual(catalog['source']['variants'], self.source_product()['variants'])
        self.assertEqual(row['sku'], 'BASE-304')
        self.assertEqual(row['price'], 'USD 19.99')
        self.assertIsNone(row['stock'])
        self.assertIsNone(catalog['source']['variants'][0]['stock'])
        self.assertEqual(catalog['source']['variants'][1]['stock'], 0)
        self.assertEqual(catalog['source']['variants'][0]['source_sku'], '00012')

    def test_untranslated_language_cannot_be_imported(self):
        draft = self.create_draft()
        response = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={'language': 'ja'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('还没有翻译', response.json['error'])
        conn = models.get_db()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)
        conn.close()

    def test_same_source_cannot_be_imported_twice(self):
        first = self.create_draft(); second = self.create_draft()
        result = self.client.post('/api/collection/drafts/%s/import' % first['id'], json={})
        self.assertEqual(result.status_code, 200, result.json)
        duplicate = self.client.post('/api/collection/drafts/%s/import' % second['id'], json={})
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn('已经导入', duplicate.json['error'])
        conn = models.get_db()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)
        conn.close()

    def test_translation_keeps_previous_languages_and_source_untouched(self):
        draft = self.create_draft()
        german = translation_input(draft['product']); german['name'] = 'Stahlanschluss 304'
        chinese = translation_input(draft['product']); chinese['name'] = '304 不锈钢接头'
        chinese['variants'][0]['attributes'] = [{'name': '颜色', 'value': '蓝色'}]
        path = '/api/collection/drafts/%s/translate' % draft['id']
        with patch('local_ai.translate_product', side_effect=[german, chinese]):
            first = self.client.post(path, json={'language': 'de'})
            second = self.client.post(path, json={'language': 'zh'})
        self.assertEqual(first.status_code, 200, first.json)
        self.assertEqual(second.status_code, 200, second.json)
        result = second.json['draft']
        self.assertEqual(result['translations']['de']['name'], 'Stahlanschluss 304')
        self.assertEqual(result['translations']['zh']['name'], '304 不锈钢接头')
        self.assertEqual(result['product'], draft['product'])
        imported = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={'language': 'zh'})
        self.assertEqual(imported.status_code, 200, imported.json)
        conn = models.get_db()
        row = dict(conn.execute('SELECT * FROM products WHERE id=?', (imported.json['product_id'],)).fetchone())
        conn.close()
        self.assertEqual(row['name'], '304 不锈钢接头')
        self.assertEqual(json.loads(row['catalog_data'])['source']['variants'], draft['product']['variants'])

    def test_workbench_routes_require_login(self):
        client = server.app.test_client()
        for path, method in [('/api/collection/drafts', 'get'), ('/api/collection/status', 'get'),
                             ('/api/collection/collect', 'post'), ('/api/collection/search', 'post'),
                             ('/api/collection/shop', 'post'), ('/api/collection/ai/start', 'post'),
                             ('/api/growth/settings', 'get'), ('/api/growth/landing-create', 'post')]:
            with self.subTest(path=path):
                response = getattr(client, method)(path)
                self.assertEqual(response.status_code, 401)
                self.assertIsNotNone(response.json)

    def test_landing_pages_are_disabled_drafts_and_escape_topics(self):
        self.product('Real product')
        topic = 'Steel <script>alert(1)</script>'
        preview = self.client.post('/api/growth/landing-preview', json={'topics': [topic]})
        self.assertEqual(preview.status_code, 200, preview.json)
        self.assertNotIn('<script>', preview.json['items'][0]['content'])
        created = self.client.post('/api/growth/landing-create', json={'topics': [topic]})
        self.assertEqual(created.status_code, 200, created.json)
        conn = models.get_db()
        row = conn.execute('SELECT * FROM pages WHERE id=?', (created.json['created'][0]['id'],)).fetchone()
        self.assertEqual(row['enabled'], 0)
        self.assertIn('Real product', row['content'])
        conn.close()

    def test_promotion_settings_roundtrip_and_invalid_input_does_not_replace(self):
        settings = {'hidden_keywords_enabled': True, 'hidden_keywords': ['Steel', 'steel', 'OEM'],
                    'hidden_links_enabled': True, 'hidden_links': [{'name': 'Partner', 'url': 'https://partner.example.com/', 'rel': 'nofollow'}],
                    'internal_links_enabled': True, 'internal_links': [{'keyword': 'Steel', 'url': 'product_1.html'}], 'max_links_per_page': 2}
        response = self.client.post('/api/growth/settings', json=settings)
        self.assertEqual(response.status_code, 200, response.json)
        expected = response.json
        self.assertEqual(expected['hidden_keywords'], ['Steel', 'OEM'])
        self.assertEqual(self.client.get('/api/growth/settings').json, expected)
        invalid = dict(settings, hidden_links=[{'name': 'Bad', 'url': 'javascript:alert(1)'}])
        self.assertEqual(self.client.post('/api/growth/settings', json=invalid).status_code, 400)
        self.assertEqual(self.client.get('/api/growth/settings').json, expected)

    def translated_import(self):
        draft = self.create_draft()
        chinese = translation_input(draft['product']); chinese['name'] = '304 不锈钢接头'
        chinese['variants'][0]['attributes'] = [{'name': '颜色', 'value': '蓝色'}]
        german = translation_input(draft['product']); german['name'] = 'Stahlanschluss 304'
        german['description'] = 'Länge 12 mm, Stahl 304.'
        german['variants'][0]['attributes'] = [{'name': 'Farbe', 'value': 'Blau'}]
        with patch('local_ai.translate_product', side_effect=[chinese, german]):
            for language in ['zh', 'de']:
                response = self.client.post('/api/collection/drafts/%s/translate' % draft['id'], json={'language': language})
                self.assertEqual(response.status_code, 200, response.json)
        response = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={'language': 'zh'})
        self.assertEqual(response.status_code, 200, response.json)
        conn = models.get_db()
        row = dict(conn.execute('SELECT * FROM products WHERE id=?', (response.json['product_id'],)).fetchone())
        conn.close()
        return row

    def test_saved_translations_render_and_import_language_keeps_manual_edits(self):
        product = self.translated_import()
        product['name'] = '人工修改的接头名称'
        chinese = builder.catalog_product(product, 'zh')
        self.assertEqual(chinese['name'], '人工修改的接头名称')
        self.assertEqual(chinese['catalog_variants'][0]['attributes'][0], {'name': '颜色', 'value': '蓝色'})
        german = builder.catalog_product(product, 'de')
        self.assertEqual(german['name'], 'Stahlanschluss 304')
        self.assertIn('Länge 12 mm', german['description'])
        self.assertEqual(german['catalog_variants'][0]['source_sku'], '00012')
        self.assertEqual(german['catalog_variants'][0]['sku'], 'ORIGINAL-0012')
        table = builder._catalog_variants_html(german, 'de')
        self.assertIn('Farbe: Blau', table)
        self.assertIn('USD 19.99', table)
        self.assertIn('<td>—</td>', table)
        self.assertIn('<td>0</td>', table)
        models.set_config('language', 'de')
        page = builder.build_product_page_html(product)
        self.assertIn('Stahlanschluss 304', page)
        self.assertIn('catalog-variants', page)
        self.assertIn('ORIGINAL-0012', page)
        cards = builder.products_html('static/uploads/')
        self.assertIn('Stahlanschluss 304', cards)

    def test_translation_after_import_updates_existing_product_without_reimport(self):
        draft = self.create_draft()
        imported = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
        self.assertEqual(imported.status_code, 200, imported.json)
        german = translation_input(draft['product']); german['name'] = 'Stahlanschluss 304'
        german['variants'][0]['attributes'] = [{'name': 'Farbe', 'value': 'Blau'}]
        with patch('local_ai.translate_product', return_value=german):
            translated = self.client.post('/api/collection/drafts/%s/translate' % draft['id'], json={'language': 'de'})
        self.assertEqual(translated.status_code, 200, translated.json)
        conn = models.get_db()
        row = dict(conn.execute('SELECT * FROM products WHERE id=?', (imported.json['product_id'],)).fetchone())
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)
        conn.close()
        saved = json.loads(row['catalog_data'])
        self.assertIn('de', saved['translations'])
        self.assertEqual(saved['source']['variants'], draft['product']['variants'])
        localized = builder.catalog_product(row, 'de')
        self.assertEqual(localized['name'], 'Stahlanschluss 304')
        self.assertEqual(localized['catalog_variants'][0]['attributes'][0], {'name': 'Farbe', 'value': 'Blau'})

    def test_missing_target_translation_keeps_imported_language_for_variants_too(self):
        product = self.translated_import()
        product['name'] = '人工修改的接头名称'
        fallback = builder.catalog_product(product, 'es')
        self.assertEqual(fallback['name'], '人工修改的接头名称')
        self.assertEqual(fallback['catalog_variants'][0]['attributes'][0], {'name': '颜色', 'value': '蓝色'})
        self.assertEqual(fallback['catalog_variants'][0]['sku'], 'ORIGINAL-0012')
        self.assertIsNone(fallback['catalog_variants'][0]['stock'])

    def test_preview_internal_links_point_to_working_preview_routes(self):
        product = self.product('Fitting')
        config = {'internal_links_enabled': True, 'internal_links': [{'keyword': 'Steel', 'url': 'contact.html'}]}
        self.assertEqual(self.client.post('/api/growth/settings', json=config).status_code, 200)
        response = self.client.get('/api/preview_product?pid=%s&site_name=TestFactory&template=business' % product['id'])
        self.assertEqual(response.status_code, 200)
        class Links(HTMLParser):
            def __init__(self): super().__init__(); self.items = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'a' and attrs.get('data-cf-promotion') == 'internal': self.items.append(attrs.get('href', ''))
        links = Links(); links.feed(response.get_data(as_text=True))
        self.assertTrue(links.items, 'The visible specification should contain a generated internal link')
        target = links.items[0]
        self.assertEqual(urlsplit(target).path, '/api/preview_contact')
        self.assertEqual(parse_qs(urlsplit(target).query).get('site_name'), ['TestFactory'])
        self.assertEqual(parse_qs(urlsplit(target).query).get('template'), ['business'])
        self.assertEqual(self.client.get(target).status_code, 200)

    def test_imported_remote_images_keep_real_urls_in_detail_and_cards(self):
        product = self.source_product()
        product['images'] = ['https://cdn.example.com/photo.jpg?width=500&crop=center',
                             'https://cdn.example.com/second.jpg?width=250&quality=80']
        with patch('collection_tools.collect_url', return_value=product):
            collected = self.client.post('/api/collection/collect', json={'url': product['source_url']})
        self.assertEqual(collected.status_code, 200, collected.json)
        draft = collected.json['draft']
        imported = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
        self.assertEqual(imported.status_code, 200, imported.json)
        response = self.client.get('/api/preview_product?pid=%s&template=business' % imported.json['product_id'])
        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        page = release_tests.Page(content)
        sources = [item.get('src') for item in page.images]
        for expected in product['images']:
            self.assertIn(expected, sources)
        self.assertIn('width=500&amp;crop=center', content)
        self.assertFalse('width=500&amp;amp;crop=center' in content, 'Product image URLs must not be double escaped in metadata')
        structured_product = next(item for item in page.ld if isinstance(item, dict) and item.get('@type') == 'Product')
        self.assertEqual(structured_product['image'], product['images'])
        self.assertNotIn('/uploads/photo.jpg', content)
        cards = builder.products_html('/uploads/')
        card_sources = [item.get('src') for item in release_tests.Page(cards).images]
        for expected in product['images']:
            self.assertIn(expected, card_sources)
        for unsafe in ['javascript:alert(1)', 'https://user:password@cdn.example.com/photo.jpg',
                       "https://cdn.example.com/photo.jpg');alert(1);//", 'https://cdn.example.com/photo.jpg%27);alert(1);//',
                       'https://cdn.example.com/evil\\photo.jpg']:
            with self.subTest(unsafe=unsafe):
                try:
                    value = builder.site_img(unsafe, '/uploads/')
                except ValueError:
                    continue
                self.assertEqual(value, '')

    def test_parent_unknown_stock_stays_unknown_and_explicit_zero_shows_unavailable(self):
        draft = self.create_draft()
        imported = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
        self.assertEqual(imported.status_code, 200, imported.json)
        identifier = imported.json['product_id']
        path = '/api/preview_product?pid=%s&template=business' % identifier
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        unknown_text = ' '.join(release_tests.Page(response.get_data(as_text=True)).visible)
        self.assertNotIn(builder.t('en', 'out_stock'), unknown_text)
        self.assertIn('—', unknown_text)
        cards = ' '.join(release_tests.Page(builder.products_html('/uploads/')).visible)
        self.assertNotIn(builder.t('en', 'out_stock_short'), cards)
        self.assertIn('—', cards)
        conn = models.get_db()
        conn.execute('UPDATE products SET stock=0 WHERE id=?', (identifier,)); conn.commit(); conn.close()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        zero_text = ' '.join(release_tests.Page(response.get_data(as_text=True)).visible)
        self.assertIn(builder.t('en', 'out_stock'), zero_text)
        cards = ' '.join(release_tests.Page(builder.products_html('/uploads/')).visible)
        self.assertIn(builder.t('en', 'out_stock_short'), cards)

    def test_manual_edit_preserves_imported_images_catalog_and_unknown_stock(self):
        draft = self.create_draft()
        imported = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
        self.assertEqual(imported.status_code, 200, imported.json)
        path = '/api/products/%s' % imported.json['product_id']
        original = self.client.get(path).json
        form = {key: original.get(key) or '' for key in ('name', 'price', 'spec', 'sku', 'model', 'category',
                                                        'description', 'meta_title', 'meta_description')}
        form.update(name='Manually updated fitting', stock='', images_order=json.dumps(original['images']), removed='[]')
        edited = self.client.put(path, data=form)
        self.assertEqual(edited.status_code, 200, edited.json)
        self.assertEqual(edited.json['name'], 'Manually updated fitting')
        self.assertEqual(edited.json['images'], original['images'])
        self.assertEqual(edited.json['img'], original['images'][0])
        self.assertIsNone(edited.json['stock'])
        self.assertEqual(edited.json['catalog_data'], original['catalog_data'])
        self.assertEqual(edited.json['catalog_fingerprint'], original['catalog_fingerprint'])
        zero = self.client.put(path, data=dict(form, stock='0'))
        self.assertEqual(zero.status_code, 200, zero.json)
        self.assertEqual(zero.json['stock'], 0)
        self.assertEqual(zero.json['images'], original['images'])
        self.assertEqual(zero.json['catalog_data'], original['catalog_data'])
        invalid = self.client.put(path, data=dict(form, stock='-1', name='Must not save', images_order='[]'))
        self.assertEqual(invalid.status_code, 400, invalid.json)
        unchanged = self.client.get(path).json
        self.assertEqual(unchanged, zero.json)

    def test_copy_imported_product_preserves_unknown_parent_stock(self):
        draft = self.create_draft()
        imported = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
        self.assertEqual(imported.status_code, 200, imported.json)
        identifier = imported.json['product_id']
        original = self.client.get('/api/products/%s' % identifier).json
        copied = self.client.post('/api/products/%s/copy' % identifier)
        self.assertEqual(copied.status_code, 200, copied.json)
        self.assertIsNone(copied.json['stock'])
        self.assertEqual(copied.json['images'], original['images'])
        self.assertEqual(copied.json['catalog_data'], original['catalog_data'])
        self.assertEqual(copied.json['copied_from'], identifier)
        preview = self.client.get('/api/preview_product?pid=%s' % copied.json['id'])
        self.assertEqual(preview.status_code, 200)
        visible = ' '.join(release_tests.Page(preview.get_data(as_text=True)).visible)
        self.assertNotIn(builder.t('en', 'out_stock'), visible)

    def test_manual_stock_above_sqlite_limit_is_400_without_partial_changes(self):
        product = self.product()
        path = '/api/products/%s' % product['id']
        before = self.client.get(path).json
        for stock in ['9223372036854775808', '9' * 9000]:
            with self.subTest(length=len(stock)):
                added = self.client.post('/api/products', data={'name': 'Must not add', 'stock': stock})
                self.assertEqual(added.status_code, 400, added.json)
                self.assertIn('过大', added.json['error'])
                updated = self.client.put(path, data={'name': 'Must not update', 'stock': stock})
                self.assertEqual(updated.status_code, 400, updated.json)
                self.assertEqual(self.client.get(path).json, before)
        conn = models.get_db()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)
        conn.close()
        maximum = self.client.post('/api/products', data={'name': 'Maximum stock', 'stock': '9223372036854775807'})
        self.assertEqual(maximum.status_code, 200, maximum.json)
        self.assertEqual(maximum.json['stock'], 9223372036854775807)

    def test_removing_imported_remote_picture_does_not_delete_local_namesake(self):
        draft = self.create_draft()
        imported = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
        self.assertEqual(imported.status_code, 200, imported.json)
        path = '/api/products/%s' % imported.json['product_id']
        original = self.client.get(path).json
        remote = original['images'][0]
        # A local file with the same basename belongs to something else.
        local = Path(server.UPLOAD_DIR, urlsplit(remote).path.rsplit('/', 1)[-1])
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(b'local file must survive a remote image removal')
        form = {key: original.get(key) or '' for key in ('name', 'price', 'spec', 'sku', 'model', 'category',
                                                        'description', 'meta_title', 'meta_description')}
        form.update(stock='', images_order=json.dumps(original['images']), removed=json.dumps([remote]))
        with patch.object(server.os, 'remove') as remove:
            edited = self.client.put(path, data=form)
        self.assertEqual(edited.status_code, 200, edited.json)
        self.assertEqual(edited.json['images'], [])
        self.assertEqual(edited.json['img'], '')
        self.assertEqual(edited.json['catalog_data'], original['catalog_data'])
        self.assertIsNone(edited.json['stock'])
        remove.assert_not_called()
        self.assertEqual(local.read_bytes(), b'local file must survive a remote image removal')

    def test_version_restore_preserves_catalog_translations_and_identifiers(self):
        product = self.translated_import()
        version_id = builder.save_version()
        conn = models.get_db()
        conn.execute("UPDATE products SET catalog_data='',catalog_fingerprint='',stock=999 WHERE id=?", (product['id'],))
        conn.commit(); conn.close()
        response = self.client.post('/api/versions/%s/restore' % version_id)
        self.assertEqual(response.status_code, 200, response.json)
        conn = models.get_db()
        restored = dict(conn.execute('SELECT * FROM products WHERE id=?', (product['id'],)).fetchone())
        conn.close()
        self.assertEqual(json.loads(restored['catalog_data']), json.loads(product['catalog_data']))
        self.assertEqual(restored['catalog_fingerprint'], product['catalog_fingerprint'])
        self.assertIsNone(restored['stock'])
        self.assertTrue((Path(server.BACKUP_DIR) / response.json['summary']['pre_backup']).is_file())

    def test_generated_pages_apply_and_remove_promotions_with_matching_manifest(self):
        self.product('Steel fitting')
        config = {'hidden_keywords_enabled': True, 'hidden_keywords': ['Hidden factory term'],
                  'hidden_links_enabled': True, 'hidden_links': [{'name': 'Partner', 'url': 'https://partner.example.com/', 'rel': 'nofollow'}],
                  'internal_links_enabled': True, 'internal_links': [{'keyword': 'Steel', 'url': 'contact.html'}]}
        self.assertEqual(self.client.post('/api/growth/settings', json=config).status_code, 200)
        builder.generate_site_files('Factory', 'business')
        root = Path(builder.OUTPUT_DIR)
        pages = list(root.glob('*.html'))
        self.assertTrue(pages)
        for page in pages:
            content = page.read_text(encoding='utf-8')
            self.assertIn('data-cf-experiment="hidden-keywords"', content)
            self.assertIn('data-cf-experiment="hidden-links"', content)
            self.assertIn('Hidden factory term', content)
        enabled_manifest = json.loads(root.joinpath('chatflow-build.json').read_text())
        for filename, digest in enabled_manifest['pages'].items():
            self.assertEqual(hashlib.sha256(root.joinpath(filename).read_bytes()).hexdigest(), digest)
        self.assertEqual(self.client.post('/api/growth/settings', json={}).status_code, 200)
        builder.generate_site_files('Factory', 'business')
        for page in root.glob('*.html'):
            content = page.read_text(encoding='utf-8')
            self.assertNotIn('data-cf-experiment=', content)
            self.assertNotIn('Hidden factory term', content)
        disabled_manifest = json.loads(root.joinpath('chatflow-build.json').read_text())
        self.assertNotEqual(enabled_manifest['build_id'], disabled_manifest['build_id'])
        for filename, digest in disabled_manifest['pages'].items():
            self.assertEqual(hashlib.sha256(root.joinpath(filename).read_bytes()).hexdigest(), digest)


    def test_delete_imported_remote_main_image_keeps_local_namesake(self):
        draft = self.create_draft()
        response = self.client.post('/api/collection/drafts/%s/import' % draft['id'], json={})
        identifier = response.json['product_id']
        local = Path(server.UPLOAD_DIR, 'photo.jpg')
        local.write_bytes(b'belongs to a different local product')
        deleted = self.client.delete('/api/products/%s' % identifier)
        self.assertEqual(deleted.status_code, 200, deleted.json)
        self.assertEqual(local.read_bytes(), b'belongs to a different local product')


if __name__ == '__main__': unittest.main()
