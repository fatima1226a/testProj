import re
from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings, tag
from django.urls import resolve


class SwaggerTests(SimpleTestCase):
    def test_root_opens_documentation_and_slash_redirect_works(self):
        self.assertRedirects(self.client.get("/"), "/swagger/", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/swagger"), "/swagger/", status_code=301, fetch_redirect_response=False)

    def test_documentation_is_public_and_loads_local_schema(self):
        for url in ("/api/", "/swagger/", "/api/docs/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'data-schema-url="/api/schema/"')
                self.assertContains(response, 'src="/api/docs/assets/docs.js"')
                self.assertNotContains(response, '<script src="https://')

    def test_schema_documents_resolvable_routes(self):
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["openapi"], "3.0.3")
        for path in schema["paths"]:
            resolve(path.replace("{id}", "1").replace("{dataset_id}", "demo"))
        scheme = "sessionAuth" if settings.API_BACKEND == "django" else "bearerAuth"
        self.assertEqual(schema["paths"]["/api/runs/"]["post"]["security"], [{scheme: []}])

    def test_schema_and_csrf_behavior_follow_selected_backend(self):
        for backend in ("django", "drf"):
            # The URLconf is built once per process; the session-only csrf route exists only in django mode.
            if backend == "django" and settings.API_BACKEND != "django":
                continue
            with self.subTest(backend=backend), override_settings(API_BACKEND=backend):
                paths = self.client.get("/api/schema/").json()["paths"]
                html = self.client.get("/swagger/").content.decode()
                if backend == "django":
                    self.assertIn("/api/auth/login/", paths)
                    self.assertNotIn("/api/auth/token/", paths)
                    self.assertIn('data-csrf-url="/api/auth/csrf/"', html)
                    self.assertIn('data-session-backend="true"', html)
                else:
                    self.assertIn("/api/auth/token/", paths)
                    self.assertNotIn("/api/auth/login/", paths)
                    self.assertNotIn('data-csrf-url=', html)
                    self.assertIn('data-session-backend="false"', html)

    def test_local_assets_are_public_even_without_debug(self):
        with override_settings(DEBUG=False):
            for name, content_type in (("docs.js", "application/javascript"), ("docs.css", "text/css")):
                response = self.client.get(f"/api/docs/assets/{name}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], content_type)
                self.assertGreater(len(b"".join(response.streaming_content)), 100)
                response.close()
        self.assertEqual(self.client.get("/api/docs/assets/settings.py").status_code, 404)

    def test_documentation_rejects_writes(self):
        for url in ("/swagger/", "/api/schema/", "/api/docs/assets/docs.js"):
            self.assertEqual(self.client.post(url).status_code, 405)

    def test_schema_path_parameters_and_request_bodies_are_consistent(self):
        schema = self.client.get("/api/schema/").json()
        for path, item in schema["paths"].items():
            parameters = {p["name"] for p in item.get("parameters", []) if p["in"] == "path" and p["required"]}
            self.assertEqual(set(re.findall(r"\{(\w+)\}", path)), parameters)
            for method, operation in item.items():
                if method == "parameters":
                    continue
                self.assertTrue(operation["responses"])
                if "requestBody" in operation:
                    body = operation["requestBody"]["content"]["application/json"]["schema"]
                    self.assertLessEqual(set(body.get("required", [])), set(body["properties"]))


@override_settings(DEBUG=True, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
@tag("django")
class DocumentationSessionFlowTests(TestCase):
    def test_documented_flow_with_real_csrf_and_rotated_login_token(self):
        if settings.API_BACKEND != "django":
            self.skipTest("Session flow only")
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get("/swagger/").status_code, 200)
        self.assertEqual(client.get("/api/runs/").status_code, 401)
        credentials = {"username": "docs-user", "password": "docs-check-Strong3947"}

        def post(url, data):
            token = client.get("/api/auth/csrf/").json()["csrfToken"]
            return client.post(url, data, content_type="application/json", HTTP_X_CSRFTOKEN=token)

        self.assertEqual(post("/api/auth/register/", {**credentials, "email": "docs@example.com"}).status_code, 201)
        old_token = client.cookies["csrftoken"].value
        login = post("/api/auth/login/", credentials)
        self.assertEqual(login.status_code, 200)
        self.assertIn("sessionid", client.cookies)
        self.assertFalse(client.cookies["sessionid"]["secure"])
        self.assertNotEqual(client.cookies["csrftoken"].value, old_token)
        self.assertEqual(client.get("/api/runs/").status_code, 200)
        # An interceptor caching the pre-login token would fail here.
        stale = client.post("/api/auth/logout/", {}, content_type="application/json", HTTP_X_CSRFTOKEN=old_token)
        self.assertEqual(stale.status_code, 403)
        self.assertEqual(post("/api/auth/logout/", {}).status_code, 204)
        self.assertEqual(client.get("/api/runs/").status_code, 401)
