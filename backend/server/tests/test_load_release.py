"""load_release command: CI evidence flags for passed level-1/parity claims (synthetic, test-only evidence)."""
from hashlib import sha256
from io import StringIO
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from django.core.management import CommandError, call_command
from django.test import TestCase
from pipeline.lastlight.demo import generate, write_json
from pipeline.lastlight.validate import read_json
from server.datasets.models import DatasetRelease

COMMIT = "a" * 40
WHEN = "2026-01-01T00:00:00Z"


class LoadReleaseCommandTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = generate(Path(self.temp.name) / "demo")

    def edit(self, name, action):
        path = self.directory / f"{name}.json"
        value = read_json(path)
        action(value)
        write_json(path, value)

    def claim_level_one(self, manifest):
        """Same synthetic final release with a passed level-1 check as pipeline/tests/test_guard.py."""
        source = {"id": "unit-test-source", "synthetic": False, "url": "https://example.invalid/unit-test",
                  "query": None, "version": "test-only", "accessedAt": WHEN,
                  "sha256": sha256(b"unit-test-input").hexdigest()}
        self.edit("provenance", lambda p: p.update(mode="final", sources=[source]))
        write_json(self.directory / "fetch-manifest.json", {"sources": [{"id": source["id"], "sha256": source["sha256"]}]})
        write_json(manifest, {"files": {}})
        report = self.directory / "ci-report.json"
        write_json(report, {"commit": COMMIT, "versions": {"python": "unit-test"},
                            "sitesSha256": read_json(self.directory / "provenance.json")["sitesSha256"],
                            "manifestSha256": sha256(manifest.read_bytes()).hexdigest(),
                            "checks": {"level-1": {"status": "passed"}}})

        def passed(value):
            check = next(c for c in value["checks"] if c["level"] == 1)
            check.update(status="passed", ranAt=WHEN, measurement={"error": 0}, tolerance={"error": 0},
                         report={"path": "ci-report.json", "sha256": sha256(report.read_bytes()).hexdigest()})
        self.edit("validation", passed)

    def load(self, *arguments):
        output = StringIO()
        call_command("load_release", str(self.directory), *arguments, stdout=output)
        return output.getvalue()

    def test_passed_level_one_requires_matching_commit(self):
        self.claim_level_one(self.directory / "manifest.json")
        with patch.dict(os.environ, {"GITHUB_SHA": ""}):
            with self.assertRaisesRegex(CommandError, "B2"):
                self.load()
            with self.assertRaisesRegex(CommandError, "B2"):
                self.load("--commit", "b" * 40)
        self.assertFalse(DatasetRelease.objects.exists())
        self.assertIn("created", self.load("--commit", COMMIT))
        self.assertIn("already loaded", self.load("--commit", COMMIT))

    def test_github_sha_is_accepted_as_commit_evidence(self):
        self.claim_level_one(self.directory / "manifest.json")
        with patch.dict(os.environ, {"GITHUB_SHA": COMMIT}):
            self.assertIn("created", self.load())

    def test_external_manifest_is_used_instead_of_release_copy(self):
        external = Path(self.temp.name) / "external-manifest.json"
        self.claim_level_one(external)
        with self.assertRaisesRegex(CommandError, "B2"):
            self.load("--commit", COMMIT)
        self.assertIn("created", self.load("--commit", COMMIT, "--manifest", str(external)))

    def test_missing_directory_is_a_command_error_without_writes(self):
        with self.assertRaisesRegex(CommandError, "D3"):
            call_command("load_release", str(Path(self.temp.name) / "missing"), stdout=StringIO())
        self.assertFalse(DatasetRelease.objects.exists())
