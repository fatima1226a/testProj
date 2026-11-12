"""OpenAPI documentation for both the session and JWT backends."""
from django.conf import settings
from pathlib import Path
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe
from django.urls import reverse

VENDOR_DIR = Path(__file__).parent / "docs_assets" / "vendor"
SWAGGER_CDN = "https://unpkg.com/swagger-ui-dist@5.11.0"
# The CDN script runs on the API origin with the session cookie, so pin its exact bytes.
SWAGGER_SRI = {"swagger-ui-bundle.js": "sha384-qn5tagrAjZi8cSmvZ+k3zk4+eDEEUcP9myuR2J6V+/H6rne++v6ChO7EeHAEzqxQ",
               "swagger-ui.css": "sha384-+yyzNgM3K92sROwsXxYCxaiLWxWJ0G+v/9A+qIZ2rgefKgkdcmJI+L601cqPD/Ut"}


def operation(summary, tag, *, body=None, status="200", authenticated=False):
    result = {
        "summary": summary,
        "tags": [tag],
        "responses": {status: {"description": "Successful response"}},
    }
    if authenticated:
        scheme = "sessionAuth" if settings.API_BACKEND == "django" else "bearerAuth"
        result["security"] = [{scheme: []}]
        result["responses"]["401"] = {"description": "Authentication required"}
    if body:
        result["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": body}},
        }
        result["responses"]["400"] = {"description": "Invalid request"}
    return result


def object_schema(properties, required=()):
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = list(required)
    return schema


@require_safe
def openapi_schema(request):
    string = {"type": "string"}
    credentials = object_schema(
        {"username": string, "password": {"type": "string", "format": "password"}},
        ("username", "password"),
    )
    paths = {
        "/api/auth/register/": {"post": operation(
            "Register an account", "Auth", status="201", body=object_schema(
                {**credentials["properties"], "email": {"type": "string", "format": "email"}},
                ("username", "email", "password")))},
        "/api/datasets/": {"get": operation("List dataset releases", "Datasets")},
        "/api/runs/": {
            "get": {**operation("List your saved runs", "Runs", authenticated=True),
                    "parameters": [{"name": "page", "in": "query",
                                    "schema": {"type": "integer", "minimum": 1}}]},
            "post": operation("Save a run", "Runs", status="201", authenticated=True,
                              body=object_schema({
                                  "dataset_id": string, "site_id": string,
                                  "plan": {"type": "object"}, "result": {"type": "object"},
                                  "label": {"type": "string", "maxLength": 200},
                              }, ("dataset_id", "site_id", "plan", "result"))),
        },
        "/api/runs/{id}/": {
            "parameters": [{"name": "id", "in": "path", "required": True,
                            "schema": {"type": "integer", "minimum": 1}}],
            "get": operation("Get your saved run", "Runs", authenticated=True),
            "patch": operation("Rename your saved run", "Runs", authenticated=True,
                               body=object_schema({"label": {"type": "string", "maxLength": 200}})),
            "delete": operation("Delete your saved run", "Runs", authenticated=True, status="204"),
        },
    }
    for document in ("sites", "provenance", "validation"):
        paths[f"/api/datasets/{{dataset_id}}/{document}/"] = {
            "parameters": [{"name": "dataset_id", "in": "path", "required": True,
                            "schema": string}],
            "get": operation(f"Get dataset {document}", "Datasets"),
        }
    if settings.API_BACKEND == "django":
        paths.update({
            "/api/auth/csrf/": {"get": operation("Get a CSRF token", "Auth")},
            "/api/auth/login/": {"post": operation("Log in with a session", "Auth", body=credentials)},
            "/api/auth/logout/": {"post": operation("Log out", "Auth", authenticated=True, status="204")},
        })
        security = {"sessionAuth": {"type": "apiKey", "in": "cookie", "name": "sessionid",
                                    "description": "Use POST /api/auth/login/; the browser stores the session cookie."}}
        description = "Session authentication. Log in using /api/auth/login/. Swagger adds CSRF tokens automatically."
    else:
        paths.update({
            "/api/auth/token/": {"post": operation("Get JWT access and refresh tokens", "Auth", body=credentials)},
            "/api/auth/token/refresh/": {"post": operation("Refresh a JWT access token", "Auth", body=object_schema(
                {"refresh": string}, ("refresh",)))},
        })
        security = {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}
        description = "JWT authentication. Get an access token using /api/auth/token/, then enter it in Authorize."
    return JsonResponse({
        "openapi": "3.0.3",
        "info": {"title": "LAST LIGHT API", "version": "1.0.0", "description": description},
        "servers": [{"url": "/"}],
        "paths": paths,
        "components": {"securitySchemes": security},
    })


@require_safe
def swagger_ui(request):
    local = all((VENDOR_DIR / name).is_file() for name in ("swagger-ui-bundle.js", "swagger-ui.css"))
    def asset_url(name):
        return reverse("docs-asset", kwargs={"filename": name}) if local else f"{SWAGGER_CDN}/{name}"
    return render(request, "swagger.html", {
        "session_backend": settings.API_BACKEND == "django",
        "swagger_js_url": asset_url("swagger-ui-bundle.js"),
        "swagger_css_url": asset_url("swagger-ui.css"),
        "swagger_js_integrity": "" if local else SWAGGER_SRI["swagger-ui-bundle.js"],
        "swagger_css_integrity": "" if local else SWAGGER_SRI["swagger-ui.css"],
    })


@require_safe
def docs_asset(request, filename):
    content_types = {"docs.js": "application/javascript", "docs.css": "text/css",
                     "swagger-ui-bundle.js": "application/javascript", "swagger-ui.css": "text/css"}
    if filename not in content_types:
        raise Http404
    directory = VENDOR_DIR if filename.startswith("swagger-ui") else Path(__file__).parent / "docs_assets"
    try:
        stream = (directory / filename).open("rb")
    except FileNotFoundError as error:
        raise Http404 from error
    return FileResponse(stream, content_type=content_types[filename])
