"""Usage: python3 -m pipeline.lastlight.guard RELEASE_DIR [--commit SHA]."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from .rules import inspect_release
from ..validate import read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--history", type=Path, help="JSON array of actual API history records")
    parser.add_argument("--api-base-url", help="Public /api/datasets/<datasetId>/ URL")
    parser.add_argument("--require-complete", action="store_true", help="Fail also on pending backend rules")
    args = parser.parse_args()
    try:
        api = None
        if args.api_base_url:
            if urlsplit(args.api_base_url).scheme not in ("http", "https"):
                raise ValueError("API URL must use http or https")
            api = {}
            for name in ("sites", "provenance", "validation"):
                with urlopen(args.api_base_url.rstrip("/") + f"/{name}/", timeout=30) as response:
                    api[name] = response.read()
        history = read_json(args.history) if args.history else None
        report = inspect_release(args.directory, current_commit=args.commit, manifest_path=args.manifest,
                                 history_records=history, api_documents=api)
        result = report.as_dict()
        if args.require_complete and any(r["status"] == "pending" for r in report.rules):
            result["ok"] = False
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except (ValueError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
