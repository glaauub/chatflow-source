import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('CF_DATA_DIR', tempfile.mkdtemp(prefix='chatflow-deploy-test-'))
import app as server
import site_builder as builder

class DeploymentTests(unittest.TestCase):
    def test_republish_existing_repo_after_regenerating_output(self):
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            remote = Path(folder, 'remote.git')
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            output = Path(folder, 'website')
            output.mkdir()
            original = server.run_git
            def local_git(directory, *args, **kwargs):
                if args[:3] == ('remote', 'add', 'origin'):
                    args = (*args[:3], str(remote))
                return original(directory, *args, **kwargs)
            client = server.app.test_client()
            with client.session_transaction() as session:
                session['github_user'] = 'test-account'
                session['github_token'] = 'test-only'
            with patch.object(server, 'OUTPUT_DIR', str(output)), \
                 patch.object(server.license_client, 'check_license', return_value=(True, 'ok')), \
                 patch.object(server, 'get_config', return_value=''), \
                 patch.object(server, 'ensure_github_repo', return_value=(True, 'exists', False)), \
                 patch.object(server, 'enable_github_pages', return_value=(True, 'ok')), \
                 patch.object(server, 'save_version', return_value=1), \
                 patch.object(server, 'run_git', side_effect=local_git), \
                 patch.object(builder, 'OUTPUT_DIR', str(output)):
                for number in (1, 2):
                    builder.generate_site_files('Deployment test', 'business')
                    (output / 'index.html').write_text('Product revision %d' % number, encoding='utf-8')
                    (output / 'chatflow-build.json').write_text(json.dumps({'build_id': str(number)}), encoding='utf-8')
                    response = client.post('/api/deploy', json={'repo': 'test-site'})
                    self.assertEqual(response.status_code, 200, response.json)
                    self.assertEqual(response.json['overwrite'], number == 2)
            result = subprocess.run(['git', '--git-dir=' + str(remote), 'rev-list', '--count', 'main'], capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), '2')
            result = subprocess.run(['git', '--git-dir=' + str(remote), 'show', 'main:index.html'], capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, 'Product revision 2')

    def test_switching_repositories_updates_generated_site_address(self):
        from models import get_config, set_config
        import site_builder as builder
        client = server.app.test_client()
        with client.session_transaction() as session:
            session['github_user'] = 'test-account'
            session['github_token'] = 'test-only'
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(server.license_client, 'check_license', return_value=(True, 'ok')), \
             patch.object(builder, 'OUTPUT_DIR', folder):
            set_config('site_url', '')
            for repo in ('first-shop', 'second-shop'):
                response = client.post('/api/generate', json={'site_name': 'Store', 'repo': repo})
                self.assertEqual(response.status_code, 200, response.json)
                expected = 'https://test-account.github.io/' + repo
                self.assertEqual(get_config('site_url'), expected)
                self.assertIn(expected + '/', Path(folder, 'sitemap.xml').read_text(encoding='utf-8'))
            self.assertNotIn('first-shop', Path(folder, 'sitemap.xml').read_text(encoding='utf-8'))

    def test_switching_repositories_keeps_custom_domain(self):
        from models import get_config, set_config
        import site_builder as builder
        client = server.app.test_client()
        with client.session_transaction() as session:
            session['github_user'] = 'test-account'
            session['github_token'] = 'test-only'
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(server.license_client, 'check_license', return_value=(True, 'ok')), \
             patch.object(builder, 'OUTPUT_DIR', folder):
            set_config('site_url', 'https://shop.example.com')
            response = client.post('/api/generate', json={'site_name': 'Store', 'repo': 'second-shop'})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(get_config('site_url'), 'https://shop.example.com')
