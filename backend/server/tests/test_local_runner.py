from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from server import run_local


class LocalRunnerTests(SimpleTestCase):
    def test_installed_django_is_used_without_subprocess(self):
        module = object()
        with patch.object(run_local.importlib, 'import_module', return_value=module), patch.object(run_local.subprocess, 'run') as probe:
            self.assertIs(run_local.ensure_django(), module)
            probe.assert_not_called()

    def test_empty_venv_uses_base_python_when_django_is_installed_there(self):
        missing = ModuleNotFoundError("No module named 'django'", name='django')
        with patch.object(run_local.importlib, 'import_module', side_effect=missing), \
             patch.object(run_local.sys, '_base_executable', '/base/python'), \
             patch.object(run_local.sys, 'executable', '/moved/.venv/bin/python'), \
             patch.object(run_local.sys, 'platform', 'darwin'), \
             patch.object(run_local.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as probe, \
             patch.object(run_local.os, 'execv', side_effect=RuntimeError('re-exec')) as execute:
            with self.assertRaisesRegex(RuntimeError, 're-exec'):
                run_local.ensure_django()
            probe.assert_called_once_with(['/base/python', '-c', 'import django'], capture_output=True)
            self.assertEqual(execute.call_args.args[0], '/base/python')
            self.assertIn('run_local.py', execute.call_args.args[1][1])

    def test_windows_reruns_base_python_as_subprocess_and_keeps_exit_code(self):
        missing = ModuleNotFoundError("No module named 'django'", name='django')
        with patch.object(run_local.importlib, 'import_module', side_effect=missing), \
             patch.object(run_local.sys, '_base_executable', r'C:\Python311\python.exe'), \
             patch.object(run_local.sys, 'executable', r'C:\Рабочий стол\server\.venv-win\Scripts\python.exe'), \
             patch.object(run_local.sys, 'platform', 'win32'), \
             patch.object(run_local.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
             patch.object(run_local.subprocess, 'call', return_value=3) as call, \
             patch.object(run_local.os, 'execv') as execute:
            with self.assertRaises(SystemExit) as error:
                run_local.ensure_django()
            self.assertEqual(error.exception.code, 3)
            execute.assert_not_called()
            self.assertEqual(call.call_args.args[0][0], r'C:\Python311\python.exe')
            self.assertIn('run_local.py', call.call_args.args[0][1])

    def test_missing_django_explains_installation_when_base_has_no_django(self):
        missing = ModuleNotFoundError("No module named 'django'", name='django')
        with patch.object(run_local.importlib, 'import_module', side_effect=missing), \
             patch.object(run_local.sys, '_base_executable', '/base/python'), \
             patch.object(run_local.sys, 'executable', '/empty/.venv/bin/python'), \
             patch.object(run_local.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(SystemExit) as error:
                run_local.ensure_django()
            self.assertIn('/empty/.venv/bin/python -m pip install -r', str(error.exception))
            self.assertIn('requirements.txt', str(error.exception))

    def test_broken_django_dependency_is_not_silently_replaced(self):
        missing = ModuleNotFoundError("No module named 'asgiref'", name='asgiref')
        with patch.object(run_local.importlib, 'import_module', side_effect=missing):
            with self.assertRaises(ModuleNotFoundError):
                run_local.ensure_django()

    def test_permission_denied_has_actionable_message(self):
        import errno
        with patch.object(run_local.socket, 'socket') as socket:
            socket.return_value.__enter__.return_value.bind.side_effect = PermissionError(errno.EPERM, 'denied')
            with self.assertRaisesRegex(SystemExit, 'обычном терминале'):
                run_local.check_local_port(8000)

    def test_occupied_port_suggests_another_port(self):
        import errno
        with patch.object(run_local.socket, 'socket') as socket:
            socket.return_value.__enter__.return_value.bind.side_effect = OSError(errno.EADDRINUSE, 'busy')
            with self.assertRaisesRegex(SystemExit, '--port 8001'):
                run_local.check_local_port(8000)

    def test_browser_opens_only_after_our_schema_responds(self):
        from io import BytesIO
        with patch.object(run_local, 'urlopen', side_effect=[OSError('starting'), BytesIO(b'{"info":{"title":"LAST LIGHT API"}}')]), \
             patch.object(run_local.time, 'sleep'), patch.object(run_local.webbrowser, 'open', return_value=True) as browser:
            run_local.open_docs_when_ready(8012)
            browser.assert_called_once_with('http://127.0.0.1:8012/swagger/')

    def test_browser_does_not_open_an_unrelated_server(self):
        from io import BytesIO
        with patch.object(run_local, 'urlopen', side_effect=lambda *a, **kw: BytesIO(b'{"info":{"title":"Other API"}}')), \
             patch.object(run_local.time, 'sleep'), patch.object(run_local.webbrowser, 'open') as browser:
            run_local.open_docs_when_ready(8012)
            browser.assert_not_called()
