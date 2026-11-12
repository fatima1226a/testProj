"""Run with config.test_settings and real DRF/SimpleJWT/CORS dependencies."""
from pathlib import Path
import tempfile
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.conf import settings
from django.test import TestCase, tag
from unittest import skipUnless
if settings.API_BACKEND == "drf":
    from rest_framework.test import APITestCase
else:
    APITestCase = TestCase
from pipeline.lastlight.demo import generate
from server.datasets.services import load_release
from pipeline.lastlight.guard import inspect_release
from server.runs.models import Run


@skipUnless(settings.API_BACKEND == "drf", "DRF/JWT suite requires LAST_LIGHT_API_BACKEND=drf")
@tag("drf")
class ApiTests(APITestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = generate(Path(self.temp.name) / "demo")
        self.release, _ = load_release(self.directory)
        self.user = get_user_model().objects.create_user(username="owner", email="owner@example.com", password="test-pass")
        self.payload = {"dataset_id": self.release.pk, "site_id": "A", "plan": {"siteId": "A"},
                        "result": {"ok": True}, "label": "first"}

    def login(self):
        response = self.client.post("/api/auth/token/", {"username": "owner", "password": "test-pass"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])
        return response.data["refresh"]

    def test_public_dataset_exact_bytes(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid")
        for name in ("sites", "provenance", "validation"):
            response = self.client.get(f"/api/datasets/{self.release.pk}/{name}/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, (self.directory / f"{name}.json").read_bytes())

    def test_release_guard_checks_actual_dataset_http_responses(self):
        bodies = {name: self.client.get(f"/api/datasets/{self.release.pk}/{name}/").content
                  for name in ("sites", "provenance", "validation")}
        report = inspect_release(self.directory, api_documents=bodies)
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(next(r for r in report.rules if r["rule"] == "C4")["status"], "passed")

    def test_register_hashes_password(self):
        response = self.client.post("/api/auth/register/", {"username": "new-user", "email": "NEW@example.com",
                                    "password": "sample-strong-password-3947"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data)
        user = get_user_model().objects.get(username="new-user")
        self.assertTrue(user.check_password("sample-strong-password-3947"))
        self.assertEqual(user.email, "new@example.com")

    def test_jwt_refresh_and_anonymous_denial(self):
        self.assertEqual(self.client.get("/api/runs/").status_code, 401)
        refresh = self.login()
        self.assertEqual(self.client.get("/api/runs/").status_code, 200)
        self.client.credentials()
        response = self.client.post("/api/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_snapshot_and_label_only_edit(self):
        self.login()
        response = self.client.post("/api/runs/", self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["dataset_mode"], "demo")
        self.assertEqual(response.data["dataset_notice"], "DEMO DATA")
        url = f"/api/runs/{response.data['id']}/"
        self.assertEqual(self.client.patch(url, {"label": "renamed"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"result": {}}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_mode_spoof_and_wrong_site_rejected(self):
        self.login()
        for changed in ({"dataset_mode": "final"}, {"dataset_notice": "REAL DATA"}, {"site_id": "missing"}):
            self.assertEqual(self.client.post("/api/runs/", {**self.payload, **changed}, format="json").status_code, 400)

    def test_a4_guard_reads_actual_history_response(self):
        self.login()
        self.client.post("/api/runs/", self.payload, format="json")
        history = self.client.get("/api/runs/").data["results"]
        report = inspect_release(self.directory, history_records=history)
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(next(r for r in report.rules if r["rule"] == "A4")["status"], "passed")

    def test_history_retains_last_50_through_api(self):
        self.login()
        ids = []
        for index in range(51):
            response = self.client.post("/api/runs/", {**self.payload, "label": str(index)}, format="json")
            self.assertEqual(response.status_code, 201)
            ids.append(response.data["id"])
        response = self.client.get("/api/runs/")
        self.assertEqual(response.data["count"], 50)
        self.assertFalse(Run.objects.filter(pk=ids[0]).exists())
        self.assertEqual(response.data["results"][0]["id"], ids[-1])

    def test_invalid_jwt_and_cross_user_modifications_are_denied(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid")
        self.assertEqual(self.client.get("/api/runs/").status_code, 401)
        self.login()
        run_id = self.client.post("/api/runs/", self.payload, format="json").data["id"]
        other = get_user_model().objects.create_user(username="other", email="other@example.com")
        self.client.force_authenticate(user=other)
        url = f"/api/runs/{run_id}/"
        self.assertEqual(self.client.patch(url, {"label": "stolen"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Run.objects.filter(pk=run_id).exists())

    def test_unknown_dataset_and_missing_release_are_errors(self):
        self.assertEqual(self.client.get("/api/datasets/unknown/sites/").status_code, 404)
        self.login()
        response = self.client.post("/api/runs/", {**self.payload, "dataset_id": "unknown"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_password_validation_and_duplicate_email(self):
        data = {"username": "new", "email": "new@example.com", "password": "123"}
        self.assertEqual(self.client.post("/api/auth/register/", data, format="json").status_code, 400)
        data.update(password="sample-strong-password-3947", email="OWNER@example.com")
        self.assertEqual(self.client.post("/api/auth/register/", data, format="json").status_code, 400)

    def test_token_payload_is_rejected(self):
        self.login()
        bad = {**self.payload, "result": {"nested": {"access_token": "secret"}}}
        self.assertEqual(self.client.post("/api/runs/", bad, format="json").status_code, 400)

    def test_hostile_json_is_rejected_without_500(self):
        self.login()
        for key in ("accessToken", "Bearer", "sessionid"):
            with self.subTest(key=key):
                bad = {**self.payload, "result": {key: "opaque"}}
                self.assertEqual(self.client.post("/api/runs/", bad, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/runs/", {**self.payload, "plan": '{"siteId": "A"}'}, format="json").status_code, 400)
        body = '{"dataset_id": "%s", "site_id": "A", "plan": {"siteId": "A", "x": %s}, "result": {}}'
        for depth in (100, 5000):
            with self.subTest(depth=depth):
                raw = body % (self.release.pk, "[" * depth + "]" * depth)
                self.assertEqual(self.client.post("/api/runs/", raw, content_type="application/json").status_code, 400)
        raw = '{"dataset_id": "%s", "site_id": "A", "plan": {"siteId": "A"}, "result": {}, "label": "\\ud800"}'
        self.assertEqual(self.client.post("/api/runs/", raw % self.release.pk, content_type="application/json").status_code, 400)
        url = f"/api/runs/{self.client.post('/api/runs/', self.payload, format='json').data['id']}/"
        for raw in ('{"label": "\\udfff"}', '{"label": "a\\u0000b"}'):
            with self.subTest(raw=raw):
                self.assertEqual(self.client.patch(url, raw, content_type="application/json").status_code, 400)

    def test_staff_sees_only_own_history(self):
        self.login()
        run_id = self.client.post("/api/runs/", self.payload, format="json").data["id"]
        staff = get_user_model().objects.create_user(username="staff", email="staff@example.com", is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=staff)
        self.assertEqual(self.client.get("/api/runs/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/runs/{run_id}/").status_code, 404)

    @override_settings(CORS_ALLOWED_ORIGINS=["https://frontend.example"])
    def test_cors_allowlist(self):
        allowed = self.client.options("/api/datasets/", HTTP_ORIGIN="https://frontend.example",
                                      HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET")
        self.assertEqual(allowed["Access-Control-Allow-Origin"], "https://frontend.example")
        denied = self.client.options("/api/datasets/", HTTP_ORIGIN="https://unknown.example",
                                     HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET")
        self.assertNotIn("Access-Control-Allow-Origin", denied)
