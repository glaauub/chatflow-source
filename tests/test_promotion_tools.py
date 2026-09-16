import unittest

from promotion_tools import apply_promotions, normalize_keyword_lines, validate_settings


class PromotionToolsTests(unittest.TestCase):
    def settings(self, **overrides):
        result = {
            "internal_links_enabled": True,
            "internal_links": [{"keyword": "steel", "url": "/steel.html"}],
        }
        result.update(overrides)
        return result

    def test_default_has_no_output_and_switches_are_off(self):
        result = validate_settings({})
        for key in ("hidden_keywords_enabled", "hidden_links_enabled", "internal_links_enabled"):
            self.assertFalse(result[key])
        source = '<!DOCTYPE html><html><body><p>steel</p></body></html>'
        self.assertEqual(apply_promotions(source, {}), source)

    def test_normalization_and_ambiguous_destinations(self):
        self.assertEqual(normalize_keyword_lines(' steel,Steel；铜\n 铜, brass '), ['steel', '铜', 'brass'])
        self.assertEqual(validate_settings({"hidden_keywords": "steel,STEEL\n铜"})["hidden_keywords"], ["steel", "铜"])
        with self.assertRaises(ValueError):
            validate_settings(self.settings(internal_links=[{"keyword": "Steel", "url": "/one"}, {"keyword": "steel", "url": "/two"}]))

    def test_invalid_inputs_are_rejected(self):
        for value in [None, [], "enabled"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_settings(value)
        for limit in [0, 4, -1, 2.5, "3", True]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                validate_settings({"max_links_per_page": limit})
        for switch in ["false", "1", 1, None]:
            with self.subTest(switch=switch), self.assertRaises(ValueError):
                validate_settings({"hidden_links_enabled": switch})

    def test_urls_reject_executable_obfuscated_or_credential_forms(self):
        for url in ['javascript:alert(1)', 'data:text/html,x', '//evil.test/x', '\\evil.test',
                    'https://u:p@a.test', 'https://', 'https://a.test:invalid/x',
                    'java%73cript:alert(1)', '%2f%2fevil.test/x', '/%0aevil',
                    '/%255cevil', 'https://a.test/"onmouseover="bad', 'http://a.test',
                    'https://a.test/a b']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_settings(self.settings(internal_links=[{"keyword": "steel", "url": url}]))
        for url in ['/products/p.html', '../p.html', 'p.html', 'https://shop.test/p?q=1&lang=en', '#parts']:
            self.assertEqual(validate_settings(self.settings(internal_links=[{"keyword": "steel", "url": url}]))["internal_links"][0]["url"], url)

    def test_max_three_links_in_visible_body_and_untouched_head(self):
        head = '<HEAD><TITLE>steel</TITLE><script>const x="steel";</script><style>.steel{}</style></HEAD>'
        source = '<!DOCTYPE html><html>' + head + '<body><p>steel steel steel steel</p></body></html>'
        output = apply_promotions(source, self.settings(), 'https://shop.test/home.html')
        self.assertIn(head, output)
        self.assertEqual(output.count('data-cf-promotion="internal"'), 3)
        self.assertTrue(output.endswith(' steel</p></body></html>'))

    def test_links_do_not_touch_attributes_links_scripts_controls_or_hidden_text(self):
        excluded = ('<a href="/steel">steel</a><script>steel</script><style>steel</style>'
                    '<textarea>steel</textarea><pre>steel</pre><code>steel</code>'
                    '<div hidden>steel</div><div aria-hidden="true">steel</div>'
                    '<div style="display : none">steel</div><div class="spider-pool">steel</div>'
                    '<template>steel</template><button>steel</button><svg><text>steel</text></svg>'
                    '<div data-cf-experiment="anything"><span>steel</span></div>')
        source = '<body>' + excluded + '<p title="steel">steel</p></body>'
        output = apply_promotions(source, self.settings())
        self.assertIn(excluded, output)
        self.assertEqual(output.count('data-cf-promotion="internal"'), 1)
        self.assertIn('<p title="steel"><a ', output)

    def test_self_links_and_external_internal_rules_are_skipped(self):
        for url in ['item.html', '/products/item.html', 'https://shop.test/products/item.html#details', '#details', '?color=red', 'https://other.test/items']:
            source = '<body>steel</body>'
            settings = self.settings(internal_links=[{"keyword": "steel", "url": url}])
            with self.subTest(url=url):
                self.assertEqual(apply_promotions(source, settings, 'https://shop.test/products/item.html'), source)
        source = '<body>steel</body>'
        self.assertEqual(apply_promotions(source, self.settings(internal_links=[{"keyword": "steel", "url": "/index.html"}]), 'https://shop.test/'), source)
        self.assertIn('data-cf-promotion', apply_promotions(source, self.settings(), 'https://shop.test/'))

    def test_word_boundaries_longer_keywords_and_chinese(self):
        settings = self.settings(internal_links=[{"keyword": "steel", "url": "/steel"}, {"keyword": "steel pipe", "url": "/pipe"}, {"keyword": "钢管", "url": "/tube"}])
        output = apply_promotions('<p>steelwork stainless steel pipe 不锈钢管 STEEL</p>', settings)
        self.assertIn('>steel pipe</a>', output)
        self.assertIn('不锈<a href="/tube"', output)
        self.assertIn('>STEEL</a>', output)
        self.assertIn('<p>steelwork stainless ', output)

    def test_entities_tags_comments_and_source_format_are_preserved(self):
        source = '<!DOCTYPE html>\n<html><body><!-- steel -->\n<P data-x=\'a&amp;b\'>Steel &amp; <b>steel</b></P></body></html>'
        output = apply_promotions(source, self.settings())
        self.assertIn('<!-- steel -->', output)
        self.assertIn('<P data-x=\'a&amp;b\'>', output)
        self.assertIn('</a> &amp; <b><a', output)
        self.assertTrue(output.startswith('<!DOCTYPE html>\n<html>'))
        self.assertTrue(output.endswith('</b></P></body></html>'))

    def test_hidden_experiments_require_opt_in_escape_and_respect_rel(self):
        settings = {"hidden_keywords": ['<script>alert(1)</script>', '钢管'],
                    "hidden_links": [{"name": '<img src=x onerror=alert(1)>', "url": 'https://partner.test/?a=1&b=2', "rel": "follow"},
                                     {"name": 'Two', "url": '/two', "rel": "nofollow"},
                                     {"name": 'Three', "url": '/three', "rel": "sponsored"}]}
        source = '<html><body><p>Visible</p></body></html>'
        self.assertEqual(apply_promotions(source, settings), source)
        settings.update(hidden_keywords_enabled=True, hidden_links_enabled=True)
        output = apply_promotions(source, settings)
        self.assertIn('data-cf-experiment="hidden-keywords"', output)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', output)
        self.assertNotIn('<img src=x', output)
        self.assertIn('href="https://partner.test/?a=1&amp;b=2">', output)
        self.assertIn('href="/two" rel="nofollow"', output)
        self.assertIn('href="/three" rel="sponsored"', output)
        self.assertTrue(output.endswith('</div></body></html>'))

    def test_output_is_idempotent_and_disabling_removes_generated_content(self):
        source = '<html><body><p>steel steel steel steel</p></body></html>'
        settings = self.settings(hidden_keywords_enabled=True, hidden_keywords=['steel'],
                                 hidden_links_enabled=True, hidden_links=[{"name": "steel", "url": "/hidden", "rel": "follow"}])
        output = apply_promotions(source, settings)
        self.assertEqual(apply_promotions(output, settings), output)
        self.assertEqual(apply_promotions(output, {}), source)
        self.assertEqual(output.count('data-cf-promotion="internal"'), 3)

    def test_relative_self_link_and_configured_limit(self):
        source = '<p>steel steel steel steel</p>'
        settings = self.settings(max_links_per_page=1)
        self.assertEqual(apply_promotions(source, settings).count('data-cf-promotion="internal"'), 1)
        self.assertEqual(apply_promotions(source, settings, '/steel.html'), source)

    def test_comparison_text_is_preserved_across_repeated_processing(self):
        source = '<body><p>Strength > 20 MPa</p></body>'
        settings = self.settings(internal_links=[{'keyword': 'Strength > 20 MPa', 'url': '/strength'}])
        output = apply_promotions(source, settings)
        self.assertIn('>Strength > 20 MPa</a>', output)
        self.assertEqual(apply_promotions(output, settings), output)
        self.assertEqual(apply_promotions(output, {}), source)


if __name__ == '__main__':
    unittest.main()
