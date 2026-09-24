import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('CF_DATA_DIR', tempfile.mkdtemp(prefix='chatflow-curl-compat-'))
import app as server


class CurlCompatibilityTests(unittest.TestCase):
    def test_old_curl_can_validate_github_account(self):
        def old_curl(command, **kwargs):
            if '--version' in command and '--retry-all-errors' not in command:
                return subprocess.CompletedProcess(command, 0, b'curl 7.55.1', b'')
            if '--retry-all-errors' in command:
                return subprocess.CompletedProcess(command, 2, b'', b'curl: option --retry-all-errors: is unknown')
            return subprocess.CompletedProcess(command, 0, b'{"login":"alice"}\n200', b'')
        with patch.object(server, '_github_reachable', return_value=True), \
             patch.object(server.subprocess, 'run', side_effect=old_curl), \
             patch.object(server.time, 'sleep'):
            self.assertEqual(server._validate_github_creds('alice', 'test-token'), (True, None))

    def test_new_curl_keeps_retry_all_errors(self):
        commands = []
        def new_curl(command, **kwargs):
            commands.append(command)
            if '--version' in command:
                return subprocess.CompletedProcess(command, 0, b'curl 8.7.1', b'')
            return subprocess.CompletedProcess(command, 0, b'{"login":"alice"}\n200', b'')
        with patch.object(server, '_github_reachable', return_value=True), \
             patch.object(server.subprocess, 'run', side_effect=new_curl):
            self.assertEqual(server._validate_github_creds('alice', 'test-token'), (True, None))
        self.assertIn('--retry-all-errors', commands[-1])
