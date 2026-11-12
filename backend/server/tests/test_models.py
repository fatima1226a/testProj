from hashlib import sha256
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from pipeline.lastlight.demo import generate, write_json
from pipeline.lastlight.validate import read_json
from server.datasets.models import DatasetRelease
from server.datasets.services import load_release
from server.runs.models import Run
from server.runs.services import create_run
from server.runs.payloads import validate_snapshots
from unittest.mock import patch


class ModelTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = generate(Path(self.temp.name) / "demo")
        self.release, _ = load_release(self.directory)
        self.user = get_user_model().objects.create_user(username="owner", email="owner@example.com", password="test")

    def run_snapshot(self, **kwargs):
        return create_run(user=self.user, dataset=self.release, site_id="A",
                          plan={"siteId": "A"}, result={"ok": True}, **kwargs)

    def test_user_password_is_hashed_and_email_unique_case_insensitive(self):
        self.assertNotEqual(self.user.password, "test")
        self.assertTrue(self.user.check_password("test"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(username="other", email="OWNER@example.com")

    def test_release_import_is_idempotent_and_byte_preserving(self):
        release, created = load_release(self.directory)
        self.assertFalse(created)
        self.assertEqual(DatasetRelease.objects.count(), 1)
        self.assertEqual(bytes(release.sites_body), (self.directory / "sites.json").read_bytes())

    def test_release_command(self):
        from io import StringIO
        output = StringIO()
        call_command("load_release", str(self.directory), stdout=output)
        self.assertIn("already loaded", output.getvalue())

    def test_changed_same_id_is_rejected(self):
        data = read_json(self.directory / "sites.json")
        data["sites"][0]["name"] = "changed"
        write_json(self.directory / "sites.json", data)
        provenance = read_json(self.directory / "provenance.json")
        provenance["sitesSha256"] = sha256((self.directory / "sites.json").read_bytes()).hexdigest()
        write_json(self.directory / "provenance.json", provenance)
        with self.assertRaises(ValidationError):
            load_release(self.directory)
        self.release.refresh_from_db()
        self.assertNotEqual(bytes(self.release.sites_body), (self.directory / "sites.json").read_bytes())

    def test_release_orm_change_rejected(self):
        self.release.mode = "final"
        with self.assertRaises(ValidationError):
            self.release.save()

    def test_mode_is_set_by_server_and_result_is_frozen(self):
        run = self.run_snapshot()
        self.assertEqual(run.dataset_mode, "demo")
        run.label = "My plan"
        run.save()
        run.refresh_from_db()
        self.assertEqual(run.label, "My plan")
        run.result = {"ok": False}
        with self.assertRaises(ValidationError):
            run.save()

    def test_history_limit_and_user_isolation(self):
        other = get_user_model().objects.create_user(username="other", email="other@example.com")
        other_run = create_run(user=other, dataset=self.release, site_id="A", plan={}, result={})
        first = self.run_snapshot()
        for i in range(50):
            self.run_snapshot(label=str(i))
        self.assertEqual(Run.objects.filter(user=self.user).count(), 50)
        self.assertFalse(Run.objects.filter(pk=first.pk).exists())
        self.assertTrue(Run.objects.filter(pk=other_run.pk).exists())

    def test_release_cannot_be_deleted_while_referenced(self):
        from django.db.models.deletion import ProtectedError
        self.run_snapshot()
        with self.assertRaises(ProtectedError):
            self.release.delete()

    def test_snapshot_token_and_nonfinite_values_rejected(self):
        for value in ({"nested": {"access_token": "secret"}}, {"score": float("nan")},
                      {"note": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOjF9.signature"}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_snapshots({"siteId": "A"}, value)

    def test_guard_failure_prevents_database_insert(self):
        other = generate(Path(self.temp.name) / "broken", seed=7)
        data = read_json(other / "provenance.json")
        data["sitesSha256"] = "0" * 64
        write_json(other / "provenance.json", data)
        before = DatasetRelease.objects.count()
        with self.assertRaisesRegex(ValidationError, "D1"):
            load_release(other)
        self.assertEqual(DatasetRelease.objects.count(), before)

    def test_command_reports_rule_id_and_fails_on_invalid_release(self):
        from django.core.management.base import CommandError
        provenance = read_json(self.directory / "provenance.json")
        provenance["sitesSha256"] = "0" * 64
        write_json(self.directory / "provenance.json", provenance)
        with self.assertRaisesRegex(CommandError, "D1"):
            call_command("load_release", str(self.directory))

    def test_d2_has_rule_number_and_preserves_existing_release(self):
        old_bytes = bytes(self.release.validation_body)
        # Same sites hash, different valid validation bytes: stronger immutable-release policy.
        path = self.directory / "validation.json"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValidationError, "D2"):
            load_release(self.directory)
        self.release.refresh_from_db()
        self.assertEqual(bytes(self.release.validation_body), old_bytes)

    def test_persisted_bytes_are_the_guarded_snapshot(self):
        from pipeline.lastlight.guard import inspect_release
        other = generate(Path(self.temp.name) / "snapshot", seed=8)
        expected = (other / "sites.json").read_bytes()

        def inspect_then_change(*args, **kwargs):
            result = inspect_release(*args, **kwargs)
            (other / "sites.json").write_bytes(b"changed after validation")
            return result

        with patch("server.datasets.services.inspect_release", side_effect=inspect_then_change):
            release, created = load_release(other)
        self.assertTrue(created)
        self.assertEqual(bytes(release.sites_body), expected)
