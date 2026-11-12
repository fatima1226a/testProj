# LAST LIGHT Django backend

Run commands from this backend directory. The Django package remains `server`
to preserve imports and settings. Supporting pipeline libraries, schemas and
demo fixtures are included here; no root frontend changes are required.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3 manage.py check --settings=server.config.test_settings
```

See `server/README.md` for production secrets and server startup.

## Tests

```sh
LAST_LIGHT_API_BACKEND=django python3 manage.py test server --settings=server.config.test_settings --exclude-tag=drf
LAST_LIGHT_API_BACKEND=drf python3 manage.py test server --settings=server.config.test_settings --exclude-tag=django
```

The mission suite contains 49 tests. The DRF run requires the full requirements.
The snapshot also includes the existing server tests and the supporting pipeline libraries.
