#!/usr/bin/env python3
import os
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
