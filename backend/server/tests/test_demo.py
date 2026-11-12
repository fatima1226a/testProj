from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase
from pipeline.lastlight.demo import generate
from server.datasets.management.commands import load_demo
from server.datasets.models import DatasetRelease


class LoadDemoCommandTests(TestCase):
    def test_empty_database_loads_generated_demo_and_removes_temporary_files(self):
        with patch.object(load_demo, "generate", wraps=generate) as generator:
            output = StringIO()
            call_command("load_demo", stdout=output)
        self.assertIn("created", output.getvalue())
        self.assertFalse(Path(generator.call_args.args[0]).exists())
        release = DatasetRelease.objects.get()
        sites = json.loads(bytes(release.sites_body))
        self.assertEqual(release.mode, "demo")
        self.assertEqual(sites["window"]["count"], 1200)
        self.assertEqual([len(site["hours"]) for site in sites["sites"]], [1200, 1200])
        self.assertEqual(sha256(bytes(release.sites_body)).hexdigest(), release.sites_sha256)

    def test_restart_preserves_existing_immutable_reports(self):
        from datetime import datetime, timezone

        with patch("pipeline.lastlight.demo.datetime", wraps=datetime) as clock:
            clock.now.side_effect = [datetime(2026, 1, 1, tzinfo=timezone.utc),
                                     datetime(2026, 1, 2, tzinfo=timezone.utc)]
            call_command("load_demo", stdout=StringIO())
            release = DatasetRelease.objects.get()
            before = bytes(release.validation_body)
            output = StringIO()
            call_command("load_demo", stdout=output)
        release.refresh_from_db()
        self.assertEqual(DatasetRelease.objects.count(), 1)
        self.assertEqual(bytes(release.validation_body), before)
        self.assertIn("already loaded", output.getvalue())

    def test_changed_existing_content_is_rejected(self):
        call_command("load_demo", stdout=StringIO())
        release = DatasetRelease.objects.get()
        # Simulate a conflicting imported release without changing its id.
        DatasetRelease.objects.filter(pk=release.pk).update(provenance_body=b"conflicting metadata")
        with self.assertRaisesRegex(CommandError, "new datasetId"):
            call_command("load_demo", stdout=StringIO())
        self.assertEqual(DatasetRelease.objects.count(), 1)
        release.refresh_from_db()
        self.assertEqual(bytes(release.provenance_body), b"conflicting metadata")

    def test_generation_failure_does_not_create_a_release(self):
        with patch.object(load_demo, "generate", side_effect=ValueError("invalid demo")):
            with self.assertRaisesRegex(CommandError, "invalid demo"):
                call_command("load_demo", stdout=StringIO())
        self.assertFalse(DatasetRelease.objects.exists())

