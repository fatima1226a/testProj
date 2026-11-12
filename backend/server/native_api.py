"""JSON API using Django sessions, forms and CSRF; no DRF or JWT emulation."""
from functools import wraps
from hashlib import sha256
from django import forms
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from pipeline.lastlight.validate import parse_json
from .datasets.models import DatasetRelease
from .native_forms import RegisterForm, RunCreateForm
from .runs.models import Run
from .runs.payloads import check_json_tree
from .runs.services import create_run


class ApiError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def response(value, status=200):
    return JsonResponse(value, status=status, safe=not isinstance(value, list), json_dumps_params={"allow_nan": False})


def endpoint(methods, *, authenticated=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                result = response({"detail": "Method not allowed"}, 405)
                result["Allow"] = ", ".join(methods)
                return result
            if authenticated and not request.user.is_authenticated:
                return response({"detail": "Authentication required"}, 401)
            try:
                return view(request, *args, **kwargs)
            except Http404:
                return response({"detail": "Not found"}, 404)
            except ApiError as error:
                return response({"detail": str(error)}, error.status)
            except ValidationError as error:
                return response({"detail": error.messages}, 400)
        return wrapped
    return decorate


def payload(request, allowed, required=()):
    if request.content_type != "application/json":
        raise ApiError("Expected application/json", 415)
    try:
        data = parse_json(request.body, "request")
    except RequestDataTooBig as error:
        raise ApiError("Request body too large", 413) from error
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise ApiError("Invalid JSON") from error
    if not isinstance(data, dict) or data.keys() - set(allowed) or set(required) - data.keys():
        raise ApiError("Missing, unknown or read-only fields")
    check_json_tree(data)
    return data


def csrf_failure(request, reason=""):
    return response({"detail": "CSRF verification failed"}, 403)


@endpoint(("GET", "HEAD"))
def csrf(request):
    return response({"csrfToken": get_token(request), "authentication": "session"})


@endpoint(("POST",))
def register(request):
    data = payload(request, ("username", "email", "password"), ("username", "email", "password"))
    if not all(isinstance(value, str) for value in data.values()):
        raise ApiError("Registration fields must be strings")
    form = RegisterForm(data)
    if not form.is_valid():
        return response({"errors": form.errors.get_json_data()}, 400)
    try:
        with transaction.atomic():
            user = form.save()
    except IntegrityError:
        return response({"detail": "Username or email already exists"}, 400)
    return response({"id": user.pk, "username": user.username, "email": user.email}, 201)


@endpoint(("POST",))
def session_login(request):
    data = payload(request, ("username", "password"), ("username", "password"))
    if not all(isinstance(value, str) and value for value in data.values()):
        raise ApiError("Username and password must be nonempty strings")
    user = authenticate(request, **data)
    if user is None:
        raise ApiError("Invalid credentials", 401)
    login(request, user)
    return response({"id": user.pk, "username": user.username, "authentication": "session", "csrfToken": get_token(request)})


@endpoint(("POST",), authenticated=True)
def session_logout(request):
    logout(request)
    return HttpResponse(status=204)


@endpoint(("POST",))
def jwt_unavailable(request):
    return response({"detail": "JWT endpoints are unavailable in Django session mode"}, 501)


@endpoint(("GET", "HEAD"))
def datasets(request):
    return response(list(DatasetRelease.objects.order_by("dataset_id").values("dataset_id", "mode", "created_at")))


@endpoint(("GET", "HEAD"))
def dataset_document(request, dataset_id, document):
    release = get_object_or_404(DatasetRelease, pk=dataset_id)
    body = bytes(getattr(release, f"{document}_body"))
    return HttpResponse(body, content_type="application/json", headers={"ETag": f'"{sha256(body).hexdigest()}"'})


def run_json(run):
    return {"id": run.pk, "created_at": run.created_at, "site_id": run.site_id,
            "plan": run.plan, "result": run.result, "dataset_id": run.dataset_id,
            "dataset_mode": run.dataset_mode, "dataset_notice": "DEMO DATA" if run.dataset_mode == "demo" else None,
            "label": run.label}


@endpoint(("GET", "HEAD", "POST"), authenticated=True)
def runs(request):
    if request.method == "POST":
        data = payload(request, ("dataset_id", "site_id", "plan", "result", "label"),
                       ("dataset_id", "site_id", "plan", "result"))
        if not isinstance(data["site_id"], str) or not isinstance(data["dataset_id"], str) or not isinstance(data.get("label", ""), str):
            raise ApiError("dataset_id, site_id and label must be strings")
        form = RunCreateForm(data)
        if not form.is_valid():
            return response({"errors": form.errors.get_json_data()}, 400)
        values = dict(form.cleaned_data)
        values["dataset"] = values.pop("dataset_id")
        return response(run_json(create_run(user=request.user, **values)), 201)
    paginator = Paginator(Run.objects.filter(user=request.user), 50)
    try:
        page = paginator.page(request.GET.get("page", 1))
    except (EmptyPage, PageNotAnInteger) as error:
        raise Http404 from error
    def page_url(number):
        return request.build_absolute_uri(request.path + f"?page={number}")
    return response({"count": paginator.count,
                     "next": page_url(page.next_page_number()) if page.has_next() else None,
                     "previous": page_url(page.previous_page_number()) if page.has_previous() else None,
                     "results": [run_json(run) for run in page]})


@endpoint(("GET", "HEAD", "PATCH", "DELETE"), authenticated=True)
def run_detail(request, pk):
    run = get_object_or_404(Run.objects.filter(user=request.user), pk=pk)
    if request.method == "DELETE":
        run.delete()
        return HttpResponse(status=204)
    if request.method == "PATCH":
        data = payload(request, ("label",))
        if "label" in data:
            if not isinstance(data["label"], str):
                raise ApiError("label must be a string of at most 200 characters")
            # Same field rules as on create, including the null-character validator.
            run.label = forms.CharField(max_length=200, required=False).clean(data["label"])
            run.save(update_fields=["label"])
    return response(run_json(run))
