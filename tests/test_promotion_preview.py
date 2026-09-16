"""Static export links stay unchanged; preview links stay in the local preview."""
import json
import unittest
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import test_v2 as release_tests

builder = release_tests.builder


class Links(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.links = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':self.links.append(dict(attrs).get('href'))


class PromotionPreviewTests(unittest.TestCase):
    def rewrite(self, content, base='https://shop.test/catalog', page='index.html'):
        with patch.object(builder, '_site_url_base', return_value=base):
            return builder._preview_static_links(content, page, 'My & Company', 'business')

    def test_all_static_routes_keep_template_and_site_name(self):
        files = ['index.html', 'contact.html', 'faq.html', 'product_23.html', 'page_about-us.html']
        routes = ['/api/preview', '/api/preview_contact', '/api/preview_faq', '/api/preview_product', '/api/preview_page']
        content = ''.join('<a href="%s">Link</a>' % filename for filename in files)
        links = Links(self.rewrite(content)).links
        for href, route in zip(links, routes):
            parsed = urlsplit(href)
            self.assertEqual(parsed.path, route)
            self.assertEqual(parse_qs(parsed.query)['site_name'], ['My & Company'])
            self.assertEqual(parse_qs(parsed.query)['template'], ['business'])
        self.assertEqual(parse_qs(urlsplit(links[3]).query)['pid'], ['23'])
        self.assertEqual(parse_qs(urlsplit(links[4]).query)['slug'], ['about-us'])

    def test_external_same_filename_other_site_folder_and_anchors_are_untouched(self):
        content = ('<a href="https://other.test/catalog/product_23.html">External</a>'
                   '<a href="https://shop.test/other/product_23.html">Other folder</a>'
                   '<a href="#specification">Anchor</a><a href="?color=red">Query</a>'
                   '<a href="/api/preview_contact?template=business">Already preview</a>'
                   '<a href="downloads/file.zip">Download</a>')
        self.assertEqual(self.rewrite(content), content)

    def test_same_site_absolute_path_queries_and_fragments_are_preserved(self):
        content = '<a href="https://shop.test/catalog/product_23.html?color=red&pid=99&template=wrong#details">Part</a>'
        href = Links(self.rewrite(content)).links[0]
        parsed = urlsplit(href)
        self.assertEqual(parsed.path, '/api/preview_product')
        self.assertEqual(parsed.fragment, 'details')
        self.assertEqual(parse_qs(parsed.query)['pid'], ['23'])
        self.assertEqual(parse_qs(parsed.query)['template'], ['business'])
        self.assertEqual(parse_qs(parsed.query)['color'], ['red'])

    def test_unconfigured_site_accepts_relative_links_only(self):
        content = '<a href="/product_23.html">Local</a><a href="https://shop.test/product_23.html">External</a>'
        links = Links(self.rewrite(content, base='')).links
        self.assertEqual(urlsplit(links[0]).path, '/api/preview_product')
        self.assertEqual(links[1], 'https://shop.test/product_23.html')

    def test_only_actual_href_is_rewritten_and_scripts_are_not_parsed_as_markup(self):
        content = ('<script>const text=\'<a href="product_23.html">x</a>\';</script>'
                   '<A title="href=contact.html" data-href="faq.html" HREF=product_23.html>Part</A>')
        output = self.rewrite(content)
        self.assertIn('<script>const text=\'<a href="product_23.html">x</a>\';</script>', output)
        self.assertIn('title="href=contact.html" data-href="faq.html"', output)
        self.assertEqual(urlsplit(Links(output).links[0]).path, '/api/preview_product')

    def test_wrapper_binds_positional_keyword_and_default_preview_parameters(self):
        def render(site_name='Default', img_prefix='', page='preview', template_id='business'):
            return '<body>steel <a href="product_23.html">Part</a></body>'
        wrapped = builder._promotion_page(lambda *args, **kwargs: 'index.html')(render)
        config = {'internal_links_enabled': True, 'internal_links': [{'keyword': 'steel', 'url': 'contact.html'}]}
        with patch.object(builder, 'get_config', side_effect=lambda key, default='': json.dumps(config) if key == 'growth_settings' else 'https://shop.test'), \
                patch.object(builder, '_site_url_base', return_value='https://shop.test'):
            for call in [lambda: wrapped(), lambda: wrapped('Positional', '', 'preview', 'business'), lambda: wrapped(site_name='Keyword', page='preview')]:
                links = Links(call()).links
                self.assertEqual([urlsplit(link).path for link in links], ['/api/preview_contact', '/api/preview_product'])
            exported = wrapped(page='index')
            self.assertEqual(Links(exported).links, ['contact.html', 'product_23.html'])

    def test_empty_page_remains_empty_when_hidden_experiments_are_enabled(self):
        wrapped = builder._promotion_page(lambda: 'faq.html')(lambda: '')
        with patch.object(builder, 'get_config', return_value=json.dumps({'hidden_keywords_enabled': True, 'hidden_keywords': ['steel']})) as config:
            self.assertEqual(wrapped(), '')
            config.assert_not_called()


if __name__ == '__main__':
    unittest.main()
