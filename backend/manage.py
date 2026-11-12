"""Django entry point for the team backend directory."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "server" / "manage.py"), run_name="__main__")
