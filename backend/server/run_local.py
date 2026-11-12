"""Start the local Django session API using the environment or server/.env."""
import argparse
import importlib
import os
from pathlib import Path
import sys
import subprocess
import threading
import time
import json
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser
import errno
import socket


def check_local_port(port):
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    except OSError as error:
        # Windows reports WSAEACCES (10013) for reserved ports instead of EACCES.
        if error.errno in (errno.EACCES, errno.EPERM, getattr(errno, "WSAEACCES", None)):
            raise SystemExit(f"Среда запрещает открыть порт {port}. Запустите сервер в обычном терминале или выберите другой порт.") from None
        if error.errno == errno.EADDRINUSE:
            raise SystemExit(f"Порт {port} занят. Запустите с другим портом: --port {port + 1 if port < 65535 else 8000}") from None
        raise


def open_docs_when_ready(port):
    """Open only after this application's schema responds, never on a blind timer."""
    origin = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urlopen(f"{origin}/api/schema/", timeout=1) as response:
                schema = json.load(response)
            if isinstance(schema, dict) and schema.get("info", {}).get("title") == "LAST LIGHT API":
                if not webbrowser.open(f"{origin}/swagger/"):
                    print(f"Откройте в браузере: {origin}/swagger/", flush=True)
                return
        except (OSError, URLError, ValueError, webbrowser.Error):
            pass
        time.sleep(0.2)
    print(f"API пока не ответил. Проверьте ошибки запуска выше: {origin}/swagger/", flush=True)


def ensure_django():
    """Recover from a moved/empty venv when its base Python has Django."""
    try:
        return importlib.import_module("django")
    except ModuleNotFoundError as error:
        if error.name != "django":
            raise
        base = getattr(sys, "_base_executable", sys.executable)
        if Path(base).resolve() != Path(sys.executable).resolve() or sys.prefix != sys.base_prefix:
            probe = subprocess.run([base, "-c", "import django"], capture_output=True)
            if probe.returncode == 0:
                print(f"Django отсутствует в {sys.executable}; запускаю через {base}", flush=True)
                arguments = [base, str(Path(__file__).resolve()), *sys.argv[1:]]
                if sys.platform == "win32":
                    # os.execv does not quote arguments on Windows and splits paths with spaces.
                    raise SystemExit(subprocess.call(arguments))
                os.execv(base, arguments)
        raise SystemExit(
            f"Django не установлен в {sys.executable}.\n"
            f"Установите зависимости: {sys.executable} -m pip install -r {Path(__file__).with_name('requirements.txt')}"
        ) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check", action="store_true", help="Check Django, migrations and documentation without opening a port")
    parser.add_argument("--open", action="store_true", help="Open documentation in the browser after the API is ready")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be in [1,65535]")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ["LAST_LIGHT_DEBUG"] = "1"
    os.environ["LAST_LIGHT_API_BACKEND"] = "django"
    os.environ["DJANGO_SETTINGS_MODULE"] = "server.config.settings"
    django = ensure_django()
    call_command = importlib.import_module("django.core.management").call_command
    django.setup()
    if args.check:
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        from django.test import Client
        call_command("check")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise SystemExit("Есть неприменённые миграции. Запустите run_local.py без --check.")
        client = Client(HTTP_HOST="localhost")
        for url in ("/api/", "/swagger/", "/api/schema/", "/api/docs/assets/docs.js", "/api/datasets/"):
            response = client.get(url)
            print(f"{url}: HTTP {response.status_code}")
            if response.status_code != 200:
                raise SystemExit("Проверка HTTP завершилась ошибкой")
            response.close()
        print(f"Python: {sys.executable}; Django: {django.get_version()}")
        print("Проверки пройдены. TCP-порт и браузер этим режимом не проверяются.")
        return
    check_local_port(args.port)
    call_command("migrate", interactive=False)
    call_command("load_release", str(root / "packages/sim/fixtures/mini-2x200"))
    print(f"Swagger: http://127.0.0.1:{args.port}/swagger/", flush=True)
    if args.open:
        threading.Thread(target=open_docs_when_ready, args=(args.port,), daemon=True).start()
    call_command("runserver", f"127.0.0.1:{args.port}", use_reloader=False)


if __name__ == "__main__":
    main()
