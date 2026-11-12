"""Prepare server/.venv; --full installs DRF/JWT and saves Swagger UI for offline use."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import venv

BASE_DIR = Path(__file__).resolve().parent
SWAGGER_CDN = "https://unpkg.com/swagger-ui-dist@5.11.0"


def download_swagger(destination):
    """Stage all files before publishing them, so failed downloads leave no partial bundle."""
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        staged = Path(temporary)
        for filename in ("swagger-ui-bundle.js", "swagger-ui.css", "LICENSE", "NOTICE"):
            with urlopen(f"{SWAGGER_CDN}/{filename}", timeout=20) as response:
                data = response.read(5_000_001)
            if not data or len(data) > 5_000_000 or data.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                raise ValueError(f"Invalid Swagger download: {filename}")
            (staged / filename).write_bytes(data)
        for file in staged.iterdir():
            os.replace(file, destination / file.name)


def runs(python):
    try:
        return subprocess.run([str(python), "-c", "import sys"], capture_output=True).returncode == 0
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Install all requirements and download Swagger UI (requires Internet)")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        raise SystemExit("Нужен Python 3.10 или новее (Django 5.2). Установите Python 3 с python.org.")
    # Separate per-OS venvs: a synced folder (OneDrive) shares pyvenv.cfg, so one venv cannot serve both systems.
    environment = BASE_DIR / (".venv-win" if os.name == "nt" else ".venv")
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # A working venv is left untouched: recreating it fails while its python.exe runs the server.
    if not runs(python):
        # A moved venv or a removed base Python keeps dead links; venv skips them without clear.
        if environment.exists():
            print(f"Окружение {environment} повреждено или создано на другом компьютере; пересоздаю.", flush=True)
        # Use an already installed Django for the offline session backend.
        venv.EnvBuilder(with_pip=True, system_site_packages=True, symlinks=os.name != "nt",
                        clear=environment.exists()).create(environment)
    if args.full:
        result = subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                                 "--retries", "0", "--timeout", "15", "-r", str(BASE_DIR / "requirements.txt")])
        if result.returncode:
            raise SystemExit("Не удалось установить зависимости. Проверьте доступ к PyPI; локальный Django-режим сохранён.")
        try:
            download_swagger(BASE_DIR / "docs_assets" / "vendor")
        except (OSError, ValueError) as error:
            raise SystemExit(f"Не удалось сохранить Swagger UI: {error}. Локальный интерфейс API доступен.") from None
    elif subprocess.run([str(python), "-c", "import sys, django; sys.exit(django.VERSION < (5, 2))"],
                        capture_output=True).returncode:
        result = subprocess.run([str(python), "-m", "pip", "install", "--retries", "0", "--timeout", "15", "Django>=5.2,<6.2"])
        if result.returncode:
            raise SystemExit("Не удалось установить Django. Проверьте доступ к PyPI и повторите setup_local.py.")
    subprocess.run([str(python), str(BASE_DIR / "run_local.py"), "--check"], check=True)
    print(f"Запуск: {BASE_DIR / ('start.bat' if os.name == 'nt' else 'start.command')}")


if __name__ == "__main__":
    main()
