"""Small CORS allowlist for the dependency-free session API."""
from django.conf import settings
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers

class CorsMiddleware:
    methods = "GET, HEAD, POST, PATCH, DELETE, OPTIONS"
    headers = {"content-type", "x-csrftoken"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        origin = request.headers.get("Origin")
        allowed = origin and origin != "*" and origin in settings.CORS_ALLOWED_ORIGINS
        preflight = request.method == "OPTIONS" and "Access-Control-Request-Method" in request.headers
        if preflight:
            method = request.headers["Access-Control-Request-Method"]
            headers = {h.strip().lower() for h in request.headers.get("Access-Control-Request-Headers", "").split(",") if h.strip()}
            accepted = allowed and method in self.methods.split(", ") and headers <= self.headers
            response = HttpResponse(status=204 if accepted else 403)
            if accepted:
                response["Access-Control-Allow-Methods"] = self.methods
                response["Access-Control-Allow-Headers"] = ", ".join(sorted(self.headers))
            patch_vary_headers(response, ("Access-Control-Request-Method", "Access-Control-Request-Headers"))
        else:
            response = self.get_response(request)
        if allowed:
            response["Access-Control-Allow-Origin"] = origin
            if settings.CORS_ALLOW_CREDENTIALS:
                response["Access-Control-Allow-Credentials"] = "true"
        patch_vary_headers(response, ("Origin",))
        return response
