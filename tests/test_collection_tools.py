import json
import ssl
import unittest
from unittest.mock import patch

import collection_tools as c


BASE = 'https://store.example.com/products/coat'


def page(product):
    return '<html><head><script type="application/ld+json">' + json.dumps(product) + '</script></head><body>Product</body></html>'


def response(text, url=BASE, content_type='text/html'):
    return {'text': text, 'url': url, 'content_type': content_type}


class ProductExtractionTests(unittest.TestCase):
    def test_group_preserves_real_skus_prices_images_and_unknown_stock(self):
        raw = {'@type': 'ProductGroup', 'name': 'Cotton coat', 'productGroupID': 'group-12',
               'description': '<p>100% cotton</p>', 'image': '/coat.jpg',
               'hasVariant': [
                   {'@type': 'Product', 'name': 'Blue coat', 'sku': 'SKU-B', 'color': 'Blue', 'size': 'L',
                    'image': '/blue.jpg', 'offers': {'@type': 'Offer', 'price': '19.99', 'priceCurrency': 'USD', 'availability': 'https://schema.org/InStock'}},
                   {'@type': 'Product', 'name': 'Red coat', 'sku': 'SKU-R', 'color': 'Red',
                    'offers': {'price': '21.99', 'priceCurrency': 'USD', 'inventoryLevel': {'value': 7}}}]}
        result = c.extract_page(page(raw), BASE)
        self.assertEqual(result['source_id'], 'group-12')
        self.assertEqual(result['description'], '100% cotton')
        self.assertEqual(result['variants'][0]['source_sku'], 'SKU-B')
        self.assertEqual(result['variants'][0]['price'], '19.99')
        self.assertIsNone(result['variants'][0]['stock'])
        self.assertEqual(result['variants'][1]['stock'], 7)
        self.assertEqual(result['variants'][0]['image'], 'https://store.example.com/blue.jpg')
        self.assertEqual(result['currency'], 'USD')

    def test_aggregate_price_is_not_invented_actual_price(self):
        product = {'@type': 'Product', 'name': 'Bolts', 'offers': {'@type': 'AggregateOffer', 'lowPrice': 1, 'highPrice': 20, 'priceCurrency': 'USD'}}
        result = c.extract_page(page(product), BASE)
        self.assertIsNone(result['price'])
        self.assertTrue(any('价格区间' in warning for warning in result['warnings']))

    def test_duplicate_and_missing_sku_are_reported(self):
        product = {'@type': 'ProductGroup', 'name': 'Coat', 'hasVariant': [
            {'@type': 'Product', 'name': 'A', 'sku': 'same'},
            {'@type': 'Product', 'name': 'B', 'sku': 'same'},
            {'@type': 'Product', 'name': 'C', 'color': 'Blue'}]}
        result = c.extract_page(page(product), BASE)
        self.assertEqual(len(result['variants']), 1)
        self.assertTrue(result['incomplete'])
        self.assertTrue(any('原 SKU' in w for w in result['warnings']))
        self.assertTrue(any('重复 SKU' in w for w in result['warnings']))

    def test_graph_references_keep_variant_details(self):
        payload = {'@graph': [
            {'@id': '#a', '@type': 'Product', 'name': 'Variant A', 'sku': 'A', 'color': 'Red'},
            {'@id': '#g', '@type': 'ProductGroup', 'name': 'Product', 'hasVariant': [{'@id': '#a'}]}]}
        result = c.extract_page(page(payload), BASE)
        self.assertEqual(result['variants'][0]['source_sku'], 'A')

    def test_separate_is_variant_of_references(self):
        payload = {'@graph': [
            {'@id': '#g', '@type': 'ProductGroup', 'name': 'Product'},
            {'@id': '#a', '@type': 'Product', 'name': 'Variant A', 'sku': 'A', 'isVariantOf': {'@id': '#g'}}]}
        self.assertEqual(c.extract_page(page(payload), BASE)['variants'][0]['sku'], 'A')

    def test_collection_page_is_not_arbitrarily_first_product(self):
        raw = [{'@type': 'Product', 'name': 'A'}, {'@type': 'Product', 'name': 'B'}]
        with self.assertRaisesRegex(c.CollectionError, '多个不同商品'):
            c.extract_page(page(raw), BASE)

    def test_meta_fallback_is_explicitly_incomplete(self):
        raw = '<meta property="og:type" content="product"><meta property="og:title" content="Coat"><meta property="og:image" content="/img.jpg"><meta property="product:price:amount" content="12.30"><meta property="product:price:currency" content="USD">'
        product = c.extract_page(raw, BASE)
        self.assertEqual(product['price'], '12.30')
        self.assertEqual(product['collection_method'], 'html_meta')
        self.assertTrue(product['incomplete'])
        self.assertEqual(product['variants'], [])

    def test_login_page_and_generic_homepage_fail(self):
        for raw in ['<title>Security verification</title>' + page({'@type': 'Product', 'name': 'bait'}),
                    '<title>Login</title><p>请先登录后继续</p>',
                    '<meta property="og:title" content="My store">']:
            with self.assertRaises(c.CollectionError): c.extract_page(raw, BASE)

    def test_html_scripts_are_never_evaluated(self):
        result = c.extract_page('<script>throw new Error("run");</script>' + page({'@type': 'Product', 'name': 'Safe'}), BASE)
        self.assertEqual(result['name'], 'Safe')

    def test_shopify_prices_skus_options_and_currency(self):
        payload = {'id': 111, 'title': 'Rain Coat', 'description': '<p>Water resistant</p>', 'price': 1099,
                   'images': ['//cdn.example.com/a.jpg'], 'options': [{'name': 'Color'}, {'name': 'Size'}],
                   'variants': [{'id': 123, 'sku': 'OUR-SKU', 'price': 1099, 'available': True,
                                 'options': ['Blue', 'L'], 'featured_image': {'src': '/blue.jpg'}}]}
        with patch.object(c, 'fetch_public', side_effect=[
            response('<script src="https://cdn.shopify.com/theme.js"></script>'),
            response(json.dumps(payload), BASE + '.js', 'application/json'),
            response('{"currency":"USD"}', 'https://store.example.com/cart.js', 'application/json')]) as fetch:
            result = c.collect_url(BASE)
        self.assertEqual(result['collection_method'], 'shopify_ajax')
        self.assertEqual(result['price'], '10.99')
        self.assertEqual(result['variants'][0]['source_sku'], '123')
        self.assertEqual(result['variants'][0]['sku'], 'OUR-SKU')
        self.assertIsNone(result['variants'][0]['stock'])
        self.assertEqual(result['variants'][0]['attributes'][0], {'name': 'Color', 'value': 'Blue'})
        self.assertEqual(fetch.call_args_list[1].args[0], BASE + '.js')

    def test_shopify_failed_ajax_falls_back_to_real_html(self):
        raw = '<script src="https://cdn.shopify.com/a.js"></script>' + page({'@type': 'Product', 'name': 'Coat'})
        with patch.object(c, 'fetch_public', side_effect=[response(raw), c.CollectionError('blocked')]):
            self.assertEqual(c.collect_url(BASE)['collection_method'], 'jsonld')


class NetworkAndDiscoveryTests(unittest.TestCase):
    def test_private_and_credentials_and_schemes_are_rejected(self):
        for url in ['http://localhost/x', 'http://127.0.0.1/x', 'http://[::1]/', 'http://169.254.169.254/',
                    'http://10.0.0.2/', 'file:///etc/passwd', 'https://user:pass@example.com/',
                    'http://example.local/', 'https://example.com:9000/', 'https://example.com\\@127.0.0.1/']:
            with self.subTest(url=url), self.assertRaises(c.CollectionError): c._basic_url(url)

    def test_dns_private_result_and_mixed_results_rejected(self):
        rows = [(2, 1, 6, '', ('93.184.216.34', 443)), (2, 1, 6, '', ('127.0.0.1', 443))]
        with patch.object(c.socket, 'getaddrinfo', return_value=rows), self.assertRaisesRegex(c.CollectionError, '异常解析'):
            c.validate_public_url(BASE)

    def test_ssl_certificate_validation_enabled(self):
        context = c._ssl_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_platform_host_boundary(self):
        self.assertEqual(c.identify_platform('https://detail.1688.com/offer/123.html'), '1688')
        self.assertEqual(c.identify_platform('https://www.amazon.co.jp/dp/ABCDEF1234'), 'amazon')
        self.assertEqual(c.identify_platform('https://amazon.com.evil.example/products/x'), 'generic')
        self.assertEqual(c.identify_platform('https://notamazon.com/products/x'), 'generic')

    def test_search_reads_actual_page_and_filters_external_urls(self):
        raw = '<a href="https://www.ebay.com/itm/123">A</a><a href="https://evil.example/itm/999">X</a>'
        with patch.object(c, 'fetch_public', return_value=response(raw, 'https://www.ebay.com/sch/i.html')) as fetch:
            result = c.search_platform('ebay', 'red coat', 2)
        self.assertEqual(result['urls'], ['https://www.ebay.com/itm/123'])
        self.assertIn('_nkw=red%20coat', fetch.call_args.args[0])
        self.assertIn('_pgn=2', fetch.call_args.args[0])
        self.assertFalse(result['complete'])

    def test_empty_search_fails_instead_of_fake_products(self):
        with patch.object(c, 'fetch_public', return_value=response('<div>Loading</div>', 'https://www.amazon.com/s')):
            with self.assertRaisesRegex(c.CollectionError, '没有读到商品'): c.search_platform('amazon', 'coat')

    def test_shop_scan_is_same_host_and_bounded(self):
        start = 'https://store.example.com/collections/all'
        raw1 = '<a href="/products/a">A</a><a href="/collections/all?page=2" rel="next">Next</a><a href="https://other.example.com/products/c">C</a>'
        raw2 = '<a href="/products/a">A</a><a href="/products/b">B</a><a href="/collections/all?page=3" rel="next">Next</a>'
        with patch.object(c, 'fetch_public', side_effect=[response(raw1, start), response(raw2, start + '?page=2')]) as fetch, patch.object(c.time, 'sleep'):
            result = c.scan_shop(start, max_pages=2, max_products=10)
        self.assertEqual(result['urls'], ['https://store.example.com/products/a', 'https://store.example.com/products/b'])
        self.assertEqual(result['pages_scanned'], 2)
        self.assertEqual(fetch.call_count, 2)
        self.assertFalse(result['complete'])

    def test_scan_limit_stops_before_fetching_more_pages(self):
        raw = '<a href="/products/a">A</a><a href="/?page=2" rel="next">Next</a>'
        with patch.object(c, 'fetch_public', return_value=response(raw, 'https://store.example.com/')) as fetch:
            result = c.scan_shop('https://store.example.com/', max_products=1)
        self.assertEqual(len(result['urls']), 1)
        self.assertEqual(fetch.call_count, 1)

    def test_private_redirect_is_rejected_before_second_connection(self):
        class FakeResponse:
            status = 302
            def getheader(self, name): return 'http://127.0.0.1/private' if name == 'Location' else None
        class FakeConnection:
            calls = 0
            def __init__(self, *args): FakeConnection.calls += 1
            def request(self, *args, **kwargs): pass
            def getresponse(self): return FakeResponse()
            def close(self): pass
        with patch.object(c, 'validate_public_url', return_value=(BASE, ['93.184.216.34'])), patch.object(c, '_PinnedHTTP', FakeConnection):
            with self.assertRaises(c.CollectionError): c.fetch_public(BASE)
        self.assertEqual(FakeConnection.calls, 1)


if __name__ == '__main__': unittest.main()
