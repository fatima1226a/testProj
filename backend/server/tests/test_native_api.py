"""Real Django HTTP views and middleware, including enforced CSRF tests."""
from pathlib import Path
import tempfile
from unittest import skipUnless
from django.conf import settings  # type: ignore[reportMissingModuleSource]
from django.contrib.auth import get_user_model  # type: ignore[reportMissingModuleSource]
from django.test import Client, TestCase, override_settings, tag  # type: ignore[reportMissingModuleSource]
from pipeline.lastlight.demo import generate
from pipeline.lastlight.guard import inspect_release
from server.datasets.services import load_release
from server.runs.models import Run
from server.runs.services import create_run
from django.contrib import admin as django_admin  # type: ignore[reportMissingModuleSource]


@skipUnless(settings.API_BACKEND == "django", "Native session API suite")
@tag("django")
class NativeApiTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = generate(Path(self.temp.name) / "demo")
        self.release, _ = load_release(self.directory)
        self.user = get_user_model().objects.create_user(username="owner", email="owner@example.com", password="test-pass")
        self.payload = {"dataset_id": self.release.pk, "site_id": "A", "plan": {"siteId": "A"},
                        "result": {"ok": True}, "label": "first"}

    def post(self, url, data):
        return self.client.post(url, data, content_type="application/json")

    def login(self):
        result = self.post("/api/auth/login/", {"username": "owner", "password": "test-pass"})
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["authentication"], "session")

    def create(self):
        result = self.post("/api/runs/", self.payload)
        self.assertEqual(result.status_code, 201, result.content)
        return result.json()

    def test_public_datasets_and_guard_exact_bytes(self):
        listing = self.client.get("/api/datasets/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()[0]["dataset_id"], self.release.pk)
        bodies = {}
        for name in ("sites", "provenance", "validation"):
            result = self.client.get(f"/api/datasets/{self.release.pk}/{name}/", HTTP_AUTHORIZATION="Bearer invalid")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.content, (self.directory / f"{name}.json").read_bytes())
            bodies[name] = result.content
        report = inspect_release(self.directory, api_documents=bodies)
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(next(r for r in report.rules if r["rule"] == "C4")["status"], "passed")

    def test_registration_hash_and_email_normalization(self):
        result = self.post("/api/auth/register/", {"username": "new", "email": "NEW@example.com", "password": "sample-strong-password-3947"})
        self.assertEqual(result.status_code, 201, result.content)
        self.assertNotIn("password", result.json())
        user = get_user_model().objects.get(username="new")
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.check_password("sample-strong-password-3947"))

    def test_weak_password_duplicate_email_and_privilege_fields_rejected(self):
        data = {"username": "new", "email": "new@example.com", "password": "123"}
        self.assertEqual(self.post("/api/auth/register/", data).status_code, 400)
        data.update(password="sample-strong-password-3947", email="OWNER@example.com")
        self.assertEqual(self.post("/api/auth/register/", data).status_code, 400)
        data.update(email="new@example.com", is_staff=True)
        self.assertEqual(self.post("/api/auth/register/", data).status_code, 400)

    def test_login_logout_and_anonymous_denial(self):
        self.assertEqual(self.client.get("/api/runs/").status_code, 401)
        self.assertEqual(self.post("/api/auth/login/", {"username": "owner", "password": "wrong"}).status_code, 401)
        self.login()
        self.assertEqual(self.client.get("/api/runs/").status_code, 200)
        self.assertEqual(self.post("/api/auth/logout/", {}).status_code, 204)
        self.assertEqual(self.client.get("/api/runs/").status_code, 401)

    def test_jwt_unavailable_is_explicit_and_bearer_cannot_authenticate(self):
        self.assertEqual(self.post("/api/auth/token/", {"username": "owner", "password": "test-pass"}).status_code, 501)
        self.assertEqual(self.post("/api/auth/token/refresh/", {"refresh": "anything"}).status_code, 501)
        self.assertEqual(self.client.get("/api/runs/", HTTP_AUTHORIZATION="Bearer invalid").status_code, 401)

    def test_snapshot_label_only_edit_and_delete(self):
        self.login()
        run = self.create()
        self.assertEqual(run["dataset_mode"], "demo")
        self.assertEqual(run["dataset_notice"], "DEMO DATA")
        url = f"/api/runs/{run['id']}/"
        self.assertEqual(self.client.get(url).json()["result"], {"ok": True})
        result = self.client.patch(url, {"label": "renamed"}, content_type="application/json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["label"], "renamed")
        self.assertEqual(self.client.patch(url, {"result": {}}, content_type="application/json").status_code, 400)
        self.assertEqual(self.client.put(url, self.payload, content_type="application/json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_readonly_mode_notice_user_and_bad_sites_rejected(self):
        self.login()
        for changed in ({"dataset_mode": "final"}, {"dataset_notice": "REAL"}, {"user": 1},
                        {"site_id": "missing"}, {"plan": {"siteId": "B"}}, {"dataset_id": "missing"}):
            with self.subTest(changed=changed):
                self.assertEqual(self.post("/api/runs/", {**self.payload, **changed}).status_code, 400)

    def test_a4_guard_on_actual_history(self):
        self.login()
        self.create()
        history = self.client.get("/api/runs/").json()["results"]
        report = inspect_release(self.directory, history_records=history)
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(next(r for r in report.rules if r["rule"] == "A4")["status"], "passed")

    def test_limit_50_and_order(self):
        self.login()
        first = self.create()
        for i in range(50):
            self.create()
        data = self.client.get("/api/runs/").json()
        self.assertEqual(data["count"], 50)
        self.assertFalse(Run.objects.filter(pk=first["id"]).exists())
        ids = [item["id"] for item in data["results"]]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_history_limit_is_per_user(self):
        other = get_user_model().objects.create_user(username="other", email="other@example.com")
        kept = create_run(user=other, dataset=self.release, site_id="A", plan={"siteId": "A"}, result={})
        for _ in range(settings.RUN_HISTORY_LIMIT + 1):
            create_run(user=self.user, dataset=self.release, site_id="A", plan={"siteId": "A"}, result={})
        self.assertEqual(Run.objects.filter(user=self.user).count(), settings.RUN_HISTORY_LIMIT)
        self.assertTrue(Run.objects.filter(pk=kept.pk).exists())

    def test_patch_cannot_change_snapshot_fields(self):
        self.login()
        run = self.create()
        url = f"/api/runs/{run['id']}/"
        for changed in ({"dataset_id": self.release.pk}, {"site_id": "B"}, {"plan": {"siteId": "B"}},
                        {"label": "ok", "site_id": "B"}, {"dataset_mode": "final"}, {"id": 999}):
            with self.subTest(changed=changed):
                self.assertEqual(self.client.patch(url, changed, content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(url).json(), run)

    def test_admin_manages_users_but_not_runs(self):
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        admin = get_user_model().objects.create_superuser(username="root", email="root@example.com", password="x")
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertContains(self.client.get("/admin/accounts/user/"), "owner")
        self.assertEqual(self.client.get(f"/admin/accounts/user/{self.user.pk}/change/").status_code, 200)
        self.assertFalse(django_admin.site.is_registered(Run))
        self.assertEqual(self.client.get("/admin/runs/run/").status_code, 404)

    def test_other_user_and_staff_cannot_see_edit_or_delete(self):
        self.login()
        run = self.create()
        for is_staff in (False, True):
            other = get_user_model().objects.create_user(username=f"other-{is_staff}", email=f"other-{is_staff}@example.com",
                                                         is_staff=is_staff, is_superuser=is_staff)
            self.client.force_login(other)
            self.assertEqual(self.client.get("/api/runs/").json()["count"], 0)
            url = f"/api/runs/{run['id']}/"
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.patch(url, {"label": "stolen"}, content_type="application/json").status_code, 404)
            self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Run.objects.filter(pk=run["id"]).exists())

    def test_bad_json_types_unknown_fields_and_content_type(self):
        self.login()
        self.assertEqual(self.client.post("/api/runs/", self.payload).status_code, 415)
        for raw in ('not json', '[]', '{"x":1,"x":2}', '{"x":1e999}'):
            self.assertEqual(self.client.post("/api/runs/", raw, content_type="application/json").status_code, 400)
        for values in ({"result": []}, {"result": {"access_token": "secret"}}, {"label": 100}, {"label": "x" * 201}):
            self.assertEqual(self.post("/api/runs/", {**self.payload, **values}).status_code, 400)

    def test_camel_case_auth_keys_are_rejected(self):
        self.login()
        for key in ("accessToken", "refreshToken", "idToken", "Bearer", "sessionid", "csrftoken", "password"):
            with self.subTest(key=key):
                self.assertEqual(self.post("/api/runs/", {**self.payload, "result": {key: "opaque"}}).status_code, 400)

    def test_snapshot_types_match_drf_and_patch_label_rejects_null_character(self):
        self.login()
        self.assertEqual(self.post("/api/runs/", {**self.payload, "plan": '{"siteId": "A"}'}).status_code, 400)
        self.assertEqual(self.post("/api/runs/", {**self.payload, "result": {}}).status_code, 201)
        url = f"/api/runs/{self.create()['id']}/"
        self.assertEqual(self.client.patch(url, {"label": "a\x00b"}, content_type="application/json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"label": "  kept  "}, content_type="application/json").json()["label"], "kept")

    def test_deep_nesting_and_lone_surrogates_are_rejected_without_500(self):
        self.login()
        body = '{"dataset_id": "%s", "site_id": "A", "plan": {"siteId": "A", "x": %s}, "result": {}}'
        for depth in (100, 5000):
            with self.subTest(depth=depth):
                raw = body % (self.release.pk, "[" * depth + "]" * depth)
                self.assertEqual(self.client.post("/api/runs/", raw, content_type="application/json").status_code, 400)
        raw = '{"dataset_id": "%s", "site_id": "A", "plan": {"siteId": "A"}, "result": {}, "label": "\\ud800"}'
        self.assertEqual(self.client.post("/api/runs/", raw % self.release.pk, content_type="application/json").status_code, 400)
        url = f"/api/runs/{self.create()['id']}/"
        self.assertEqual(self.client.patch(url, '{"label": "\\udfff"}', content_type="application/json").status_code, 400)

    def test_missing_resources_and_bad_page(self):
        self.assertEqual(self.client.get("/api/datasets/missing/sites/").status_code, 404)
        self.login()
        self.assertEqual(self.client.get("/api/runs/99999/").status_code, 404)
        self.assertEqual(self.client.get("/api/runs/?page=bad").status_code, 404)

    @override_settings(CORS_ALLOWED_ORIGINS=["https://frontend.example"])
    def test_cors_allowlist_and_preflight(self):
        result = self.client.options("/api/runs/", HTTP_ORIGIN="https://frontend.example",
                                     HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST", HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,x-csrftoken")
        self.assertEqual(result.status_code, 204)
        self.assertEqual(result["Access-Control-Allow-Origin"], "https://frontend.example")
        self.assertEqual(result["Access-Control-Allow-Credentials"], "true")
        denied = self.client.options("/api/runs/", HTTP_ORIGIN="https://unknown.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", denied)

    def test_csrf_enforced_on_login_registration_and_snapshot_writes(self):
        client = Client(enforce_csrf_checks=True)
        credentials = {"username": "owner", "password": "test-pass"}
        self.assertEqual(client.post("/api/auth/login/", credentials, content_type="application/json").status_code, 403)
        self.assertEqual(client.post("/api/auth/register/", {}, content_type="application/json").status_code, 403)
        csrf = client.get("/api/auth/csrf/").json()["csrfToken"]
        result = client.post("/api/auth/login/", credentials, content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(result.status_code, 200)
        csrf = result.json()["csrfToken"]  # Login rotates the CSRF secret.
        self.assertEqual(client.post("/api/runs/", self.payload, content_type="application/json").status_code, 403)
        result = client.post("/api/runs/", self.payload, content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(result.status_code, 201, result.content)
        url = f"/api/runs/{result.json()['id']}/"
        self.assertEqual(client.patch(url, {"label": "unsafe"}, content_type="application/json").status_code, 403)
        self.assertEqual(client.delete(url).status_code, 403)
        self.assertEqual(client.delete(url, HTTP_X_CSRFTOKEN=csrf).status_code, 204)

    def test_csrf_rejects_untrusted_origin_even_with_valid_cookie_and_token(self):
        client = Client(enforce_csrf_checks=True)
        csrf = client.get("/api/auth/csrf/").json()["csrfToken"]
        result = client.post("/api/auth/login/", {"username": "owner", "password": "test-pass"},
                             content_type="application/json", HTTP_X_CSRFTOKEN=csrf, HTTP_ORIGIN="https://evil.example")
        self.assertEqual(result.status_code, 403)
