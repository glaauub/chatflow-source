import unittest,copy,ast
from pathlib import Path
from catalog_data import *

class CatalogTests(unittest.TestCase):
    def sample(self):
        return normalize_product({'name':'棉衬衫','source_platform':'test','source_id':'p1','price':'12.50','currency':'CNY','variants':[{'source_sku':'CN-红-L','sku':'LOCAL-001','attributes':[{'name':'颜色','value':'红色'},{'name':'尺码','value':'L'}],'price':'13.50','stock':None,'image':'https://example.com/red.jpg'}]})
    def test_all_existing_languages_are_available(self):
        tree=ast.parse(Path('site_builder.py').read_text(encoding='utf-8'));keys=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='I18N' for t in n.targets):keys.extend(k.value for k in n.value.keys)
        self.assertEqual(set(LANGUAGES),set(keys))
    def test_translation_preserves_sku_price_inventory_images(self):
        p=self.sample();t=translation_input(p);t['name']='Cotton shirt';t['variants'][0]['attributes'][0]={'name':'Color','value':'Red'}
        for lang in LANGUAGES:
            accepted=accept_translation(p,lang,t);out=localized(p,lang,{lang:accepted})
            for k in ['source_sku','sku','price','stock','image']:self.assertEqual(out['variants'][0][k],p['variants'][0][k])
        self.assertEqual(p['name'],'棉衬衫')
    def test_unknown_stock_remains_unknown(self):self.assertIsNone(self.sample()['variants'][0]['stock'])
    def test_translated_units_keep_quantity_and_physical_measurement(self):
        for translated in ['Weight 250 g', 'Gewicht 250 Gramm', '重さ 250 グラム', '무게 250g']:
            validate_translation_text('重量 250 克', translated)
        for translated in ['Weight 250 kg', 'Weight 25 g', 'Weight 250 ml', 'Weight 250']:
            with self.assertRaises(ValueError):validate_translation_text('重量 250 克', translated)
        for source,translated in [('250 ml','250 mililitros'),('250 ml','250 مل'),('250 kg','250 Kilogramm'),('10 cm','10 centímetros'),('250 ℃','250 °C')]:
            validate_translation_text(source,translated)
        with self.assertRaises(ValueError):validate_translation_text('250 °C','250 °F')
    def test_currency_not_invented(self):
        p=normalize_product({'name':'Part','price':'1.25'});self.assertEqual(p['currency'],'');self.assertTrue(p['warnings'])
    def test_injected_translation_fields_rejected(self):
        p=self.sample();t=translation_input(p);t['variants'][0]['price']='0.01'
        with self.assertRaises(ValueError):accept_translation(p,'en',t)
    def test_missing_variant_rejected(self):
        p=self.sample();t=translation_input(p);t['variants']=[]
        with self.assertRaises(ValueError):accept_translation(p,'en',t)
    def test_duplicate_sku_rejected(self):
        p=self.sample();p['variants'].append(copy.deepcopy(p['variants'][0]))
        with self.assertRaises(ValueError):normalize_product(p)
    def test_invalid_price_rejected(self):
        for value in ['NaN','Infinity','-1']:
            with self.assertRaises(ValueError):normalize_product({'name':'Part','price':value})
    def test_credential_url_rejected(self):
        with self.assertRaises(ValueError):normalize_product({'name':'Part','source_url':'https://user:password@example.com'})
    def test_provider_data_keeps_variants(self):
        p=from_onebound_item({'item':{'title':'样品','num_iid':123,'price':'-1','skus':{'sku':[{'sku_id':'456','price':'2.30','properties_name':'1:2:颜色:蓝色;3:4:尺码:L','quantity':'5'}]}}})
        self.assertEqual(p['variants'][0]['attributes'][0]['value'],'蓝色');self.assertIsNone(p['price']);self.assertEqual(p['variants'][0]['stock'],5)
    def test_provider_error_is_not_an_empty_success(self):
        with self.assertRaises(ValueError):from_onebound_item({'error':'login required'})

if __name__=='__main__':unittest.main()
