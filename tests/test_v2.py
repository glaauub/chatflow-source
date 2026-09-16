import os
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch
os.environ['CF_DATA_DIR'] = tempfile.mkdtemp(prefix='chatflow-test-')
import app as server
import models
import site_builder as builder
from visibility import Page, audit_output, valid_site_url, write_manifest

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.license = patch.object(server.license_client, 'check_license', return_value=(True, 'ok'))
        self.license.start()
        self.client = server.app.test_client()
        with self.client.session_transaction() as s:
            s['github_user'] = 'test-account'; s['github_token'] = 'test-only'
        conn = models.get_db()
        for table in ['products','sections','pages','contacts','banner','categories','friend_links','versions','site_config']:
            conn.execute('DELETE FROM '+table)
        conn.commit();conn.close()
        models.set_config('site_url','https://example.com/catalog')
        models.set_config('company_name','Actual Factory')
        models.set_config('language','en')
    def tearDown(self): self.license.stop()
    def product(self,name='Part A', price='Contact for quote'):
        c=models.get_db();p=c.execute("INSERT INTO products(name,price,spec,img,description,meta_title,meta_description) VALUES(?,?,?,?,?,?,?)",(name,price,'Steel 304','','A corrosion resistant steel part.','Unique '+name,'Description '+name)).lastrowid;c.commit();c.close()
        c=models.get_db();row=dict(c.execute('SELECT * FROM products WHERE id=?',(p,)).fetchone());c.close();return row
    def test_product_metadata_and_no_invented_offer(self):
        p=self.product();models.set_config('geo_faq',json.dumps([{'q':'Global question?','a':'Real answer.'}]))
        page=Page(builder.build_product_page_html(p))
        self.assertEqual(page.title,'Unique Part A');self.assertEqual(page.description,'Description Part A')
        self.assertFalse(any(x.get('@type')=='FAQPage' for x in page.ld))
        product=next(x for x in page.ld if x.get('@type')=='Product');self.assertNotIn('offers',product)
        org=next(x for x in page.ld if x.get('@type')=='Organization');self.assertEqual(org['url'],'https://example.com/catalog/');self.assertNotIn('alternateName',org)
    def test_page_title_and_description(self):
        page=Page(builder.build_page_html({'title':'About','slug':'about','content':'<p>Actual production details.</p>','seo_title':'Factory capabilities'}))
        self.assertEqual(page.title,'Factory capabilities');self.assertEqual(page.description,'Actual production details.')
    def test_search_training_independent(self):
        models.set_config('geo_ai_enabled','0');models.set_config('geo_training_enabled','1')
        robots=builder._build_robots();self.assertIn('OAI-SearchBot\nDisallow: /',robots);self.assertIn('GPTBot\nAllow: /',robots)
        self.assertIn('Sitemap: https://example.com/catalog/sitemap.xml',robots)
    def test_config_roundtrip(self):
        res=self.client.post('/api/seo',json={'seo_site_title':'Saved title','seo_site_description':'Saved description','site_url':'https://example.com'})
        self.assertEqual(res.status_code,200)
        seo=self.client.get('/api/config').json['seo'];self.assertEqual(seo['site_title'],'Saved title')
    def test_invalid_url_rejected_before_write(self):
        self.assertEqual(self.client.post('/api/seo',json={'site_url':'javascript:bad'}).status_code,400)
        self.assertEqual(models.get_config('site_url'),'https://example.com/catalog')
        for bad in ['https://u:p@a.com','https://a.com?x=1','https://a.com/#x','http://a.com']:
            self.assertFalse(valid_site_url(bad))
    def test_restoration_keeps_metadata_and_creates_backup(self):
        self.product();vid=builder.save_version()
        models.set_config('company_name','New Name')
        res=self.client.post('/api/versions/%s/restore'%vid)
        self.assertEqual(res.status_code,200,res.json)
        self.assertTrue((Path(server.BACKUP_DIR)/res.json['summary']['pre_backup']).exists())
        c=models.get_db();self.assertEqual(c.execute('SELECT meta_title FROM products').fetchone()[0],'Unique Part A');self.assertEqual(c.execute('SELECT COUNT(*) FROM versions').fetchone()[0],1);c.close()
    def test_audit_finds_actual_errors(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'a.html').write_text('<title>Same</title><meta name="description" content="same"><h1>A</h1><img src="missing.png"><p>[待补充]</p>', encoding='utf-8')
            Path(d,'b.html').write_text('<title>Same</title><meta name="description" content="same">')
            r=audit_output(d,'https://example.com');messages=' '.join(i['problem'] for i in r['issues'])
            self.assertIn('搜索标题重复',messages);self.assertIn('找不到',messages);self.assertIn('待补充',messages)
    def test_all_templates_generate_and_manifest_matches(self):
        self.product();models.set_config('geo_brand_summary','We make precision parts with documented materials.')
        models.set_config('geo_faq',json.dumps([{'q':'What material?','a':'Steel 304.'}]))
        for template in builder.get_template.__globals__['TEMPLATES']:
            builder.generate_site_files('Factory',template['id'])
            out=Path(builder.OUTPUT_DIR)
            self.assertIn('precision parts',out.joinpath('index.html').read_text(encoding='utf-8'))
            faq=Page(out.joinpath('faq.html').read_text(encoding='utf-8'));self.assertTrue(any(x.get('@type')=='FAQPage' for x in faq.ld))
            report=audit_output(out,'https://example.com/catalog')
            self.assertFalse([x for x in report['issues'] if '问答' in x['problem']],report)
            manifest=json.loads(out.joinpath('chatflow-build.json').read_text(encoding='utf-8'));self.assertEqual(manifest['version'],'2.1.1')
    def test_missing_login_returns_json(self):
        c=server.app.test_client();res=c.get('/api/visibility/results');self.assertEqual(res.status_code,401);self.assertIsNotNone(res.json)
    def test_fake_ai_results_are_not_generated(self):
        self.assertEqual(self.client.get('/api/visibility/results').json,[])
        self.assertEqual(self.client.post('/api/visibility/results',json={'date':'2026-09-10','clicks':-1}).status_code,400)
    def test_login_fails_closed(self):
        with patch.object(server,'_github_reachable',return_value=False):
            self.assertFalse(server._validate_github_creds('any','any')[0])
    def test_hidden_links_never_publish(self):
        self.assertEqual(builder.hidden_links_html([{'url':'https://example.org','name':'Hidden'}]),'')
    def test_old_build_not_marked_online(self):
        from io import BytesIO
        class Response(BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with patch.object(server,'urlopen',return_value=Response(b'{"app":"ChatFLOW","build_id":"old"}')):
            res=self.client.post('/api/check_site',json={'url':'https://example.com/catalog','build_id':'a'*24})
        self.assertFalse(res.json['ok'])
    def test_backup_rejects_invalid_database(self):
        import io,zipfile
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('app.db',b'not sqlite')
        b.seek(0);res=self.client.post('/api/backup/restore',data={'file':(b,'bad.zip')})
        self.assertEqual(res.status_code,400);self.assertEqual(models.get_config('company_name'),'Actual Factory')

class AdditionalTests(unittest.TestCase):
    setUp = ReleaseTests.setUp
    tearDown = ReleaseTests.tearDown
    product = ReleaseTests.product
    def test_manifest_changes_when_css_changes(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'index.html').write_text('<h1>Same page</h1>')
            Path(d,'style.css').write_text('body{color:red}')
            first=write_manifest(d)['build_id']
            Path(d,'style.css').write_text('body{color:blue}')
            self.assertNotEqual(first,write_manifest(d)['build_id'])
    def test_product_bulk_fill_does_not_overwrite(self):
        self.product()
        c=models.get_db();c.execute("INSERT INTO products(name,price,spec,img,description) VALUES('New part','','Real spec','','Real description')");c.commit();c.close()
        draft=self.client.get('/api/visibility/product_drafts').json
        self.assertEqual(draft['count'],1)
        self.assertEqual(self.client.post('/api/visibility/product_drafts',json={}).status_code,200)
        self.assertEqual(self.client.get('/api/visibility/product_drafts').json['count'],0)
        c=models.get_db();self.assertEqual(c.execute("SELECT meta_title FROM products WHERE name='Part A'").fetchone()[0],'Unique Part A');c.close()
    def test_jsonld_script_breakout_is_escaped(self):
        data={'name':'</script><script>alert(1)</script>'}
        encoded=builder._jsonld_script(data)
        self.assertEqual(encoded.count('</script>'),1)
        self.assertEqual(Page(encoded).ld[0],data)
    def test_valid_backup_roundtrip_with_nested_image(self):
        image=Path(server.UPLOAD_DIR,'nested','photo.png');image.parent.mkdir(exist_ok=True);image.write_bytes(b'photo')
        name=server._create_backup_archive()
        models.set_config('company_name','Changed')
        with open(Path(server.BACKUP_DIR,name),'rb') as f:
            response=self.client.post('/api/backup/restore',data={'file':(f,name)})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(image.read_bytes(),b'photo');self.assertEqual(models.get_config('company_name'),'Actual Factory')

    def test_hidden_links_require_explicit_opt_in(self):
        links=[{'url':'https://example.org','name':'Experiment'}]
        self.assertEqual(builder.hidden_links_html(links),'')
        self.client.post('/api/visibility/experiments',json={'enabled':True})
        self.assertIn('https://example.org',builder.hidden_links_html(links))
        self.client.post('/api/visibility/experiments',json={'enabled':False})
        self.assertEqual(builder.hidden_links_html(links),'')

class LicensingTLSTests(unittest.TestCase):
    def test_license_opener_loads_bundled_ca_and_uses_verified_context(self):
        import ssl, types, urllib.request
        from unittest.mock import MagicMock
        context=ssl.create_default_context()
        fake_context=MagicMock(wraps=context)
        fake_certifi=types.SimpleNamespace(where=lambda:'/bundled/cacert.pem')
        fake_context.load_verify_locations=MagicMock()
        response=MagicMock()
        response.__enter__.return_value.read.return_value=b'{"ok":true}'
        opener=MagicMock();opener.open.return_value=response
        with patch.dict('sys.modules',{'certifi':fake_certifi}), patch('ssl.create_default_context',return_value=fake_context), patch('urllib.request.build_opener',return_value=opener) as build:
            self.assertTrue(server.license_client._server_post('/version',{})['ok'])
        fake_context.load_verify_locations.assert_called_once_with(cafile='/bundled/cacert.pem')
        handlers=build.call_args.args
        handler=next(h for h in handlers if isinstance(h,urllib.request.HTTPSHandler))
        self.assertIs(handler._context,fake_context)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)

if __name__=='__main__': unittest.main(verbosity=2)
