"""Offline publishing regression check for the frozen Windows application."""
import json
import os
from pathlib import Path
import shutil
import tempfile


def run(server):
    import site_builder as builder
    saved_builder_output = builder.OUTPUT_DIR
    saved = {name: getattr(server, name) for name in ('OUTPUT_DIR', 'run_git', 'get_config', 'ensure_github_repo', 'enable_github_pages', 'save_version')}
    license_check = server.license_client.check_license
    original = server.run_git
    try:
        executable = Path(server._discover_git()).resolve()
        if os.name == 'nt' and not executable.is_relative_to(Path(server.BUNDLE_DIR).resolve()):
            raise RuntimeError('Self-test accidentally used system Git')
        with tempfile.TemporaryDirectory(prefix='ChatFLOW 发布检查 ') as folder:
            remote = Path(folder, 'remote.git')
            first = original(folder, 'init', '--bare', str(remote))
            if first.returncode:
                raise RuntimeError(first.stderr)
            output = Path(folder, 'website'); output.mkdir()
            server.OUTPUT_DIR = str(output)
            builder.OUTPUT_DIR = str(output)
            server.get_config = lambda *args: ''
            server.ensure_github_repo = lambda *args: (True, 'test repository', False)
            server.enable_github_pages = lambda *args: (True, 'test pages')
            server.save_version = lambda *args, **kwargs: 1
            server.license_client.check_license = lambda *args, **kwargs: (True, 'test license')
            def local_git(directory, *args, **kwargs):
                if args[:3] == ('remote', 'add', 'origin'):
                    args = (*args[:3], str(remote))
                return original(directory, *args, **kwargs)
            server.run_git = local_git
            client = server.app.test_client()
            with client.session_transaction() as session:
                session['github_user'] = 'test-account'; session['github_token'] = 'test-only'
            for revision in (1, 2):
                builder.generate_site_files('Deployment check', 'business')
                (output / 'index.html').write_text('Product revision %d' % revision, encoding='utf-8')
                (output / '产品.txt').write_text('商品图片与描述', encoding='utf-8')
                (output / 'chatflow-build.json').write_text(json.dumps({'build_id': str(revision)}), encoding='utf-8')
                response = client.post('/api/deploy', json={'repo': 'test-site'})
                if response.status_code != 200 or response.json['overwrite'] != (revision == 2):
                    raise RuntimeError(str(response.json))
            result = original(folder, '--git-dir=' + str(remote), 'rev-list', '--count', 'main')
            if result.returncode or result.stdout.strip() != '2': raise RuntimeError('Commit history lost')
            result = original(folder, '--git-dir=' + str(remote), 'show', 'main:index.html')
            if result.returncode or result.stdout != 'Product revision 2': raise RuntimeError('Published content mismatch')
            result = original(folder, 'ls-remote', 'https://github.com/git/git.git', 'HEAD')
            if result.returncode or not result.stdout.strip(): raise RuntimeError('Bundled Git HTTPS failed: ' + result.stderr)
        return {'ok': True, 'first_publish': True, 'republish': True, 'history_preserved': True, 'https': True}
    finally:
        builder.OUTPUT_DIR = saved_builder_output
        for name, value in saved.items(): setattr(server, name, value)
        server.license_client.check_license = license_check
